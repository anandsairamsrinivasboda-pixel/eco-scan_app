
import json
import mimetypes

import pandas as pd
from google import genai
from google.genai import types


def parse_receipt(file, food_names=None):
    """Extract receipt items and return a DataFrame for calc.py."""

    # Accept either a file path or a Streamlit uploaded file.
    if hasattr(file, "getvalue"):
        file_bytes = file.getvalue()
        filename = file.name
    else:
        filename = str(file)
        with open(filename, "rb") as image_file:
            file_bytes = image_file.read()

    mime_type = mimetypes.guess_type(filename)[0]

    if mime_type is None or not (
        mime_type.startswith("image/") or mime_type == "application/pdf"
    ):
        raise ValueError("Please upload an image or PDF receipt.")

    prompt = (
        "Read this grocery receipt. Return a JSON list. "
        "Each list item must have exactly these fields: "
        "'item' (string), 'quantity' (number or null), "
        "and 'unit' (string). "
        "Use the quantity and unit printed on the receipt. "
        "Do not guess a quantity or unit if it is unclear; use null "
        "for quantity and 'unknown' for unit. "
    )

    if food_names:
        prompt += (
            "For each item, use the closest matching food name from this list "
            "when appropriate. If there is no suitable match, keep the receipt "
            "item name. Food names: " + ", ".join(food_names)
        )

    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )

    if not response.text:
        raise ValueError("Gemini did not return any receipt data.")

    try:
        rows = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini returned data that was not valid JSON.") from error

    if not isinstance(rows, list):
        raise ValueError("Gemini's response should be a list of receipt items.")

    for row in rows:
        if not isinstance(row, dict) or not all(
            key in row for key in ("item", "quantity", "unit")
        ):
            raise ValueError(
                "Each receipt item needs item, quantity, and unit fields."
            )

    # The column names match the lowercase names accepted by calc.py.
    return pd.DataFrame(rows, columns=["item", "quantity", "unit"])
