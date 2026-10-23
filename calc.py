import pandas as pd


# Kilograms in one unit of mass.
UNIT_TO_KG = {
    "kg": 1.0,
    "kilogram": 1.0,
    "kilograms": 1.0,
    "g": 0.001,
    "gram": 0.001,
    "grams": 0.001,
    "lb": 0.45359237,
    "lbs": 0.45359237,
    "pound": 0.45359237,
    "pounds": 0.45359237,
    "oz": 0.028349523125,
    "ounce": 0.028349523125,
    "ounces": 0.028349523125,
}

# These units mean the customer gave a count, not a weight.
COUNT_UNITS = {"piece", "pieces", "each", "item", "items"}


def load_environmental_data(file="data.csv"):
    """Load the food database from a CSV or Excel file."""
    filename = getattr(file, "name", str(file)).lower()

    if filename.endswith(".csv"):
        return pd.read_csv(file)
    elif filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    else:
        raise ValueError("Please provide a CSV or Excel file.")


def calculate_impact(products, environmental_data):
    """
    Calculate impacts for foods on a receipt.

    products must contain:
        Product, Quantity, Unit

    For counted foods, it must also contain:
        Weight_per_item, Weight_unit

    Examples:
        Apple, 2, lb
        Apple, 3, pieces, 500, g

    environmental_data must contain the columns from your CSV:
        food, land_m2_per_kg, water_used, carbon_footprint

    Returns:
        result: calculated impacts for each receipt line
        summary: impacts combined by food, totals, and highest contributors
    """
    env = environmental_data.copy()
    items = products.copy()

    env.columns = env.columns.astype(str).str.strip()
    items.columns = items.columns.astype(str).str.strip()

    # Accept the lowercase column names returned by vision.py.
    items = items.rename(columns={
        "item": "Product",
        "quantity": "Quantity",
        "unit": "Unit",
        "weight_per_item": "Weight_per_item",
        "weight_unit": "Weight_unit",
    })

    # vision.py returns both the wording printed on the receipt (item) and
    # the verified canonical CSV category (match). Prefer that verified match
    # for calculations. If it is empty, keep the receipt wording so the
    # matching step below can report the food as unavailable.
    if "match" in items.columns:
        suggested_match = items["match"].astype("string").str.strip()
        has_match = suggested_match.notna() & suggested_match.ne("")
        items.loc[has_match, "Product"] = suggested_match[has_match]

    # Rename your CSV columns to the names used in the calculations.
    env = env.rename(columns={
        "food": "Product",
        "carbon_footprint": "CO2_kg_per_kg",
        "water_used": "Water_litres_per_kg",
        "land_m2_per_kg": "Land_m2_per_kg",
    })

    required_env = [
        "Product",
        "CO2_kg_per_kg",
        "Water_litres_per_kg",
        "Land_m2_per_kg",
    ]
    required_items = ["Product", "Quantity", "Unit"]

    missing_env = [col for col in required_env if col not in env.columns]
    missing_items = [col for col in required_items if col not in items.columns]

    if missing_env:
        raise ValueError(f"Database is missing columns: {missing_env}")

    if missing_items:
        raise ValueError(f"Products are missing columns: {missing_items}")

    # These fields are optional for foods sold by mass.
    # They are required when the receipt gives a count like "3 pieces".
    for column in ["Weight_per_item", "Weight_unit"]:
        if column not in items.columns:
            items[column] = pd.NA

    # Check that food names are present.
    for table, label in [(env, "database"), (items, "products")]:
        if (
            table["Product"].isna().any()
            or table["Product"].astype(str).str.strip().eq("").any()
        ):
            raise ValueError(f"A food name is missing from the {label}.")

    # Convert the receipt quantities to numbers.
    items["Quantity"] = pd.to_numeric(items["Quantity"], errors="coerce")

    if items["Quantity"].isna().any():
        raise ValueError("A quantity is missing or is not a valid number.")

    if (items["Quantity"] < 0).any():
        raise ValueError("Food quantities cannot be negative.")

    missing_units = (
        items["Unit"].isna()
        | items["Unit"].astype(str).str.strip().eq("")
    )
    if missing_units.any():
        foods = items.loc[missing_units, "Product"].tolist()
        raise ValueError("A quantity unit is missing for: " + ", ".join(foods))

    items["Unit_key"] = (
        items["Unit"].astype(str).str.strip().str.casefold()
    )

    mass_rows = items["Unit_key"].isin(UNIT_TO_KG)
    count_rows = items["Unit_key"].isin(COUNT_UNITS)
    unsupported_rows = ~(mass_rows | count_rows)

    if unsupported_rows.any():
        bad_units = items.loc[unsupported_rows, "Unit"].unique()
        raise ValueError(
            "Unsupported unit(s): "
            + ", ".join(str(unit) for unit in bad_units)
            + ". Use kg, g, lb, oz, or pieces with a per-item weight."
        )

    items["Quantity_kg"] = 0.0

    # Foods sold by mass: quantity × kg in each unit.
    items.loc[mass_rows, "Quantity_kg"] = (
        items.loc[mass_rows, "Quantity"]
        * items.loc[mass_rows, "Unit_key"].map(UNIT_TO_KG)
    )

    # Convert the per-item weight to a number for counted foods.
    items["Weight_per_item"] = pd.to_numeric(
        items["Weight_per_item"], errors="coerce"
    )
    items["Weight_unit_key"] = (
        items["Weight_unit"].astype(str).str.strip().str.casefold()
    )

    missing_item_weight = count_rows & (
        items["Weight_per_item"].isna()
        | items["Weight_unit"].isna()
        | items["Weight_unit"].astype(str).str.strip().eq("")
    )

    if missing_item_weight.any():
        foods = items.loc[missing_item_weight, "Product"].tolist()
        raise ValueError(
            "Add the weight of one piece/item for: " + ", ".join(foods)
        )

    if (
        count_rows
        & items["Weight_per_item"].notna()
        & (items["Weight_per_item"] <= 0)
    ).any():
        raise ValueError("The weight of each piece/item must be greater than zero.")

    bad_weight_unit = count_rows & ~items["Weight_unit_key"].isin(UNIT_TO_KG)

    if bad_weight_unit.any():
        bad_units = items.loc[bad_weight_unit, "Weight_unit"].unique()
        raise ValueError(
            "Unsupported per-item weight unit(s): "
            + ", ".join(str(unit) for unit in bad_units)
            + ". Use kg, g, lb, or oz."
        )

    # Counted foods: number of items × weight per item × kg conversion.
    items.loc[count_rows, "Quantity_kg"] = (
        items.loc[count_rows, "Quantity"]
        * items.loc[count_rows, "Weight_per_item"]
        * items.loc[count_rows, "Weight_unit_key"].map(UNIT_TO_KG)
    )

    # Match food names without being sensitive to capitalization or extra spaces.
    env["Product_key"] = (
        env["Product"].astype(str).str.strip().str.casefold()
    )
    items["Product_key"] = (
        items["Product"].astype(str).str.strip().str.casefold()
    )

    if env["Product_key"].duplicated().any():
        raise ValueError("The database contains duplicate food names.")

    # Convert "not available" to missing data, not zero.
    missing_words = {"", "not available", "na", "n/a", "none", "null"}
    impact_columns = [
        "CO2_kg_per_kg",
        "Water_litres_per_kg",
        "Land_m2_per_kg",
    ]

    for column in impact_columns:
        original = env[column]
        marked_missing = (
            original.isna()
            | original.astype(str).str.strip().str.casefold().isin(missing_words)
        )
        numbers = pd.to_numeric(original.mask(marked_missing), errors="coerce")

        invalid = ~marked_missing & numbers.isna()
        if invalid.any():
            bad_foods = env.loc[invalid, "Product"].tolist()
            raise ValueError(f"Invalid values in {column} for: {bad_foods}")

        if (numbers.dropna() < 0).any():
            raise ValueError(f"Values in {column} cannot be negative.")

        env[column] = numbers

    # Match receipt products to foods in the database.
    database_for_merge = env.drop(columns=["Product"])

    result = items.merge(
        database_for_merge,
        on="Product_key",
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    unmatched = result.loc[result["_merge"] == "left_only", "Product"].unique()

    if len(unmatched):
        raise ValueError(
            "No database match found for: " + ", ".join(unmatched)
        )

    result = result.drop(
        columns=["_merge", "Unit_key", "Weight_unit_key"]
    )

    # Item impact = total kg × the database impact per kg.
    result["CO2_total_kg"] = (
        result["Quantity_kg"] * result["CO2_kg_per_kg"]
    )
    result["Water_total_litres"] = (
        result["Quantity_kg"] * result["Water_litres_per_kg"]
    )
    result["Land_total_m2"] = (
        result["Quantity_kg"] * result["Land_m2_per_kg"]
    )

    # Combine duplicate receipt lines for the same food.
    # min_count=1 keeps missing impacts missing instead of turning them into zero.
    by_food = result.groupby("Product_key", as_index=False).agg(
        Product=("Product", "first"),
        Quantity_kg=("Quantity_kg", "sum"),
        CO2_total_kg=("CO2_total_kg", lambda values: values.sum(min_count=1)),
        Water_total_litres=(
            "Water_total_litres",
            lambda values: values.sum(min_count=1),
        ),
        Land_total_m2=(
            "Land_total_m2",
            lambda values: values.sum(min_count=1),
        ),
    )

    by_food = by_food.drop(columns=["Product_key"])

    # Calculate totals and find the highest-contributing food for each measure.
    measures = {
        "carbon": ("CO2_total_kg", "kg CO2e"),
        "water": ("Water_total_litres", "litres"),
        "land": ("Land_total_m2", "m²"),
    }

    totals = {}
    highest_contributors = {}

    for measure, (column, unit) in measures.items():
        known_values = by_food[column].dropna()
        missing_foods = by_food.loc[
            by_food[column].isna(), "Product"
        ].tolist()

        known_subtotal = float(known_values.sum())
        complete = len(missing_foods) == 0

        # A full total is shown only if every food has data for that measure.
        total = known_subtotal if complete else None

        totals[measure] = {
            "total": total,
            "unit": unit,
            "known_subtotal": known_subtotal,
            "complete": complete,
            "missing_foods": missing_foods,
        }

        if known_values.empty:
            highest_contributors[measure] = None
            continue

        top_index = by_food[column].idxmax()
        top_food = by_food.loc[top_index]
        top_value = float(top_food[column])

        highest_contributors[measure] = {
            "food": top_food["Product"],
            "impact": top_value,
            "unit": unit,
            "share_of_known_subtotal_percent": (
                top_value / known_subtotal * 100
                if known_subtotal > 0
                else None
            ),
            "share_of_total_percent": (
                top_value / total * 100
                if complete and total and total > 0
                else None
            ),
        }

    summary = {
        "by_food": by_food,
        "totals": totals,
        "highest_contributors": highest_contributors,
    }

    return result, summary
