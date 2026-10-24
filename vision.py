"""Extract foods from receipts and match them to EcoScan CSV categories."""
import json
import mimetypes
from pathlib import Path

import pandas as pd

MODEL_NAME = "gemini-3.8-flash"
MAX_FILE_BYTES = 50 * 1024 * 1024
OUTPUT_COLUMNS = [
    "item", "match", "quantity", "unit",
    "weight_per_item", "weight_unit", "confidence", "similar_products",
]

RECEIPT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "item": {"type": "string"},
            "match": {"type": ["string", "null"]},
            "quantity": {"type": ["number", "null"]},
            "unit": {"type": ["string", "null"]},
            "weight_per_item": {"type": ["number", "null"]},
            "weight_unit": {"type": ["string", "null"]},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
        },
        "required": [
            "item", "match", "quantity", "unit",
            "weight_per_item", "weight_unit", "confidence",
        ],
        "additionalProperties": False,
    },
}


def _read_file(file):
    """Read a path, Streamlit upload, or camera image."""
    if hasattr(file, "getvalue"):
        file_bytes = file.getvalue()
        filename = getattr(file, "name", "receipt")
        mime_type = getattr(file, "type", None)
    elif hasattr(file, "read") and not isinstance(file, (str, Path)):
        file_bytes = file.read()
        filename = getattr(file, "name", "receipt")
        mime_type = getattr(file, "type", None)
    else:
        filename = str(file)
        file_bytes = Path(file).read_bytes()
        mime_type = None

    mime_type = mime_type or mimetypes.guess_type(str(filename))[0]
    if not mime_type or not (
        mime_type.startswith("image/") or mime_type == "application/pdf"
    ):
        raise ValueError("Upload an image or PDF receipt.")
    if not file_bytes:
        raise ValueError("The uploaded receipt is empty.")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise ValueError("The receipt file is larger than 50 MB.")
    return file_bytes, mime_type


def _optional_number(value, field_name, row_number):
    """Validate an optional non-negative number returned by Gemini."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"Receipt row {row_number}: {field_name} must be a number or null."
        )
    if value < 0:
        raise ValueError(
            f"Receipt row {row_number}: {field_name} cannot be negative."
        )
    return float(value)


def _build_similar_products_by_food(environmental_data):
    """Build only database-approved alternatives sharing a similarity group."""
    if not isinstance(environmental_data, pd.DataFrame):
        return {}

    columns = {str(column).strip().casefold(): column for column in environmental_data.columns}
    food_column = columns.get("food")
    group_column = columns.get("similar_group")
    if food_column is None or group_column is None:
        return {}

    grouped_names = {}
    for _, row in environmental_data[[food_column, group_column]].iterrows():
        food = row[food_column]
        group = row[group_column]
        if pd.isna(food) or pd.isna(group):
            continue
        food = str(food).strip()
        group = str(group).strip().casefold()
        if food and group:
            grouped_names.setdefault(group, []).append(food)

    alternatives = {}
    for names in grouped_names.values():
        for food in names:
            alternatives[food.casefold()] = [
                other for other in names if other.casefold() != food.casefold()
            ]
    return alternatives


def validate_and_match_rows(rows, food_names, similar_products_by_food=None):
    """Validate CSV matches and attach their database-approved alternatives."""
    if not isinstance(rows, list):
        raise ValueError("Gemini's response must be a JSON list.")

    allowed_foods = [
        str(name).strip()
        for name in food_names
        if name is not None and str(name).strip()
    ]
    canonical_by_key = {name.casefold(): name for name in allowed_foods}
    cleaned_rows = []

    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Receipt row {row_number} must be an object.")

        item = row.get("item")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Receipt row {row_number} has no food name.")
        item = item.strip()

        proposed_match = row.get("match")
        match = None
        if isinstance(proposed_match, str) and proposed_match.strip():
            # A model suggestion is accepted only if it exists in the CSV.
            match = canonical_by_key.get(proposed_match.strip().casefold())

        quantity = _optional_number(row.get("quantity"), "quantity", row_number)
        weight_per_item = _optional_number(
            row.get("weight_per_item"), "weight_per_item", row_number
        )

        unit = row.get("unit")
        if unit is not None:
            if not isinstance(unit, str):
                raise ValueError(f"Receipt row {row_number}: unit must be text or null.")
            unit = unit.strip().casefold() or None
            if unit in {"gm", "gms", "gram", "grams"}:
                unit = "g"

        weight_unit = row.get("weight_unit")
        if weight_unit is not None:
            if not isinstance(weight_unit, str):
                raise ValueError(
                    f"Receipt row {row_number}: weight_unit must be text or null."
                )
            weight_unit = weight_unit.strip().casefold() or None

        confidence = row.get("confidence", "low")
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"

        cleaned_rows.append({
            "item": item,
            "match": match,
            "quantity": quantity,
            "unit": unit,
            "weight_per_item": weight_per_item,
            "weight_unit": weight_unit,
            "confidence": confidence,
            # Candidates come from the CSV's explicit group, never from
            # substring matching or an unverified model guess.
            "similar_products": (
                list((similar_products_by_food or {}).get(match.casefold(), []))
                if match
                else []
            ),
        })

    return pd.DataFrame(cleaned_rows, columns=OUTPUT_COLUMNS)


def parse_receipt(file, food_names, client=None):
    """Extract foods from a receipt image/PDF and match them to CSV names.

    file can be a path, Streamlit uploader result, or camera_input result.
    Pass the full CSV DataFrame to attach alternatives from its similar_group
    column. Passing only food names keeps older callers working without advice.
    The returned DataFrame has OUTPUT_COLUMNS and does not calculate impacts.
    """
    if food_names is None:
        raise ValueError("Pass data.csv or its food-name column to this function.")

    similar_products_by_food = _build_similar_products_by_food(food_names)
    if isinstance(food_names, pd.DataFrame):
        columns = {str(column).strip().casefold(): column for column in food_names.columns}
        food_column = columns.get("food")
        if food_column is None:
            raise ValueError("The database must contain a 'food' column.")
        food_names = food_names[food_column].tolist()
    else:
        food_names = list(food_names)
    if not food_names:
        raise ValueError("The CSV food-name list is empty.")

    file_bytes, mime_type = _read_file(file)

    # Client reads GEMINI_API_KEY from the environment.
    if client is None:
        from google import genai
        client = genai.Client()

    prompt = f"""
Read this grocery or restaurant bill. Return only actual food products bought.
Ignore the hotel/store/restaurant name, address, phone number, date, invoice
number, prices, taxes, discounts, subtotal, total, payment details, and other
non-food text.

For each food line:
- Keep the printed food name in item.
- Choose match only when a CSV category below is the same food or a safe
  near-name equivalent. Copy the category exactly from the list. For example,
  red apple can match Apple if Apple is listed.
- If there is no safe match, set match to null. Do not force a different food.
- Read quantity and unit from the bill. If a food line has no quantity number
  printed, assume quantity=1. If a printed number is present but unreadable,
  set quantity=null. Never invent a weight.
- Return common mass units in standard form: kg, g, lb, or oz. For example,
  normalize gm, gram, and grams to g.
- For 3 apples, 500 g each: quantity=3, unit=pieces,
  weight_per_item=500, weight_unit=g.
- For apples, 500 g total: quantity=500, unit=g, and both per-item fields=null.
- If quantity or unit is unclear, set it to null so the user can review it.
- Set confidence to high, medium, or low.

Allowed CSV food categories:
{json.dumps(food_names, ensure_ascii=False)}
"""

    from google.genai import types

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=RECEIPT_SCHEMA,
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned no receipt data. Try a clearer photo.")

    try:
        rows = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini returned invalid JSON for the receipt.") from error

    return validate_and_match_rows(
        rows, food_names, similar_products_by_food=similar_products_by_food
    )

