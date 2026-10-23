import pandas as pd


# How many kilograms are in one unit of each supported measurement?
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
    products needs these columns:
        Product, Quantity, Unit

    Example:
        Apple, 2, lb

    The database needs these columns:
        food, land_m2_per_kg, water_used, carbon_footprint

    Quantities are converted to kg before calculating impacts.
    """
    env = environmental_data.copy()
    items = products.copy()

    env.columns = env.columns.astype(str).str.strip()
    items.columns = items.columns.astype(str).str.strip()

    # Accept the lowercase names used by the vision model too:
    # item, quantity, unit
    items = items.rename(columns={
        "item": "Product",
        "quantity": "Quantity",
        "unit": "Unit",
    })

    # Convert your CSV's headers to the calculation names.
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

    # Make sure each food has a name.
    for table, label in [(env, "database"), (items, "products")]:
        if table["Product"].isna().any() or table["Product"].astype(str).str.strip().eq("").any():
            raise ValueError(f"A food name is missing from the {label}.")

    # Convert each quantity to kg.
    items["Quantity"] = pd.to_numeric(items["Quantity"], errors="coerce")

    if items["Quantity"].isna().any():
        raise ValueError("A quantity is missing or is not a valid number.")

    if (items["Quantity"] < 0).any():
        raise ValueError("Food quantities cannot be negative.")

    items["Unit_key"] = items["Unit"].astype(str).str.strip().str.casefold()
    items["Kg_per_unit"] = items["Unit_key"].map(UNIT_TO_KG)

    if items["Kg_per_unit"].isna().any():
        unknown_units = items.loc[items["Kg_per_unit"].isna(), "Unit"].unique()
        raise ValueError(
            "Unsupported unit(s): "
            + ", ".join(str(unit) for unit in unknown_units)
            + ". Use kg, g, lb, or oz."
        )

    items["Quantity_kg"] = items["Quantity"] * items["Kg_per_unit"]

    # Clean food names for matching; capitalization and outer spaces won't matter.
    env["Product_key"] = env["Product"].astype(str).str.strip().str.casefold()
    items["Product_key"] = items["Product"].astype(str).str.strip().str.casefold()

    if env["Product_key"].duplicated().any():
        raise ValueError("The database contains duplicate food names.")

    # Turn "not available" into a missing value, not zero.
    missing_words = {"", "not available", "na", "n/a", "none", "null"}
    impact_columns = [
        "CO2_kg_per_kg",
        "Water_litres_per_kg",
        "Land_m2_per_kg",
    ]

    for col in impact_columns:
        original = env[col]
        marked_missing = (
            original.isna()
            | original.astype(str).str.strip().str.casefold().isin(missing_words)
        )
        numbers = pd.to_numeric(original.mask(marked_missing), errors="coerce")

        # Unexpected text, such as "unknown??", should be fixed in the CSV.
        invalid = ~marked_missing & numbers.isna()
        if invalid.any():
            bad_foods = env.loc[invalid, "Product"].tolist()
            raise ValueError(f"Invalid values in {col} for: {bad_foods}")

        if (numbers.dropna() < 0).any():
            raise ValueError(f"Values in {col} cannot be negative.")

        env[col] = numbers

    # Match products in the receipt to foods in the database.
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
        raise ValueError("No database match found for: " + ", ".join(unmatched))

    result = result.drop(columns=["_merge", "Product_key", "Unit_key", "Kg_per_unit"])

    # Quantity_kg is multiplied by each database value, which is per kg.
    result["CO2_total_kg"] = result["Quantity_kg"] * result["CO2_kg_per_kg"]
    result["Water_total_litres"] = (
        result["Quantity_kg"] * result["Water_litres_per_kg"]
    )
    result["Land_total_m2"] = result["Quantity_kg"] * result["Land_m2_per_kg"]

    # If any item is missing a measurement, mark the full total as unknown.
    total_columns = {
        "CO2_kg": "CO2_total_kg",
        "Water_litres": "Water_total_litres",
        "Land_m2": "Land_total_m2",
    }

    totals = {}

    for total_name, result_column in total_columns.items():
        known_values = result[result_column].dropna()
        missing_foods = (
            result.loc[result[result_column].isna(), "Product"]
            .drop_duplicates()
            .tolist()
        )

        totals[total_name] = (
            float(known_values.sum()) if not missing_foods else None
        )
        totals[f"{total_name}_known_subtotal"] = float(known_values.sum())
        totals[f"{total_name}_missing_foods"] = missing_foods

    return result, totals
