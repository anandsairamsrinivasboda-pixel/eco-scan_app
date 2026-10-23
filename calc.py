import pandas as pd


def load_environmental_data(file):
    """Load environmental data from CSV or Excel."""
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    elif file.name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(file)
    else:
        raise ValueError("Please upload a CSV or Excel file.")

    return df


def calculate_impact(products, environmental_data):
    """
    Calculate environmental impact for food quantities in kg.

    Environmental data must contain:
    Product
    CO2_kg_per_kg
    Water_litres_per_kg
    Land_m2_per_kg

    Products must contain:
    Product
    Quantity_kg
    """

    env = environmental_data.copy()
    items = products.copy()

    # Check required columns
    env_columns = [
        "Product",
        "CO2_kg_per_kg",
        "Water_litres_per_kg",
        "Land_m2_per_kg"
    ]

    item_columns = ["Product", "Quantity_kg"]

    missing_env = [
        col for col in env_columns if col not in env.columns
    ]
    missing_items = [
        col for col in item_columns if col not in items.columns
    ]

    if missing_env:
        raise ValueError(
            f"Environmental data is missing columns: {missing_env}"
        )

    if missing_items:
        raise ValueError(
            f"Product data is missing columns: {missing_items}"
        )

    # Standardize product names for matching
    env["Product"] = (
        env["Product"].astype(str).str.strip().str.casefold()
    )
    items["Product"] = (
        items["Product"].astype(str).str.strip().str.casefold()
    )

    # Convert numerical columns
    impact_columns = [
        "CO2_kg_per_kg",
        "Water_litres_per_kg",
        "Land_m2_per_kg"
    ]

    for col in impact_columns:
        env[col] = pd.to_numeric(env[col], errors="coerce")

    items["Quantity_kg"] = pd.to_numeric(
        items["Quantity_kg"], errors="coerce"
    )

    # Validate data
    if env["Product"].duplicated().any():
        raise ValueError(
            "Environmental data contains duplicate product names."
        )

    if env[impact_columns].isna().any().any():
        raise ValueError(
            "Environmental data has missing or invalid impact values."
        )

    if (env[impact_columns] < 0).any().any():
        raise ValueError("Impact values cannot be negative.")

    if items["Product"].isna().any() or (
        items["Product"] == ""
    ).any():
        raise ValueError("A product name is missing.")

    if items["Quantity_kg"].isna().any():
        raise ValueError("A product quantity is missing or invalid.")

    if (items["Quantity_kg"] < 0).any():
        raise ValueError("Food quantities cannot be negative.")

    # Match food products with their environmental data
    result = items.merge(
        env,
        on="Product",
        how="left",
        validate="many_to_one",
        indicator=True
    )

    unmatched = result.loc[
        result["_merge"] == "left_only", "Product"
    ].unique()

    if len(unmatched):
        raise ValueError(
            "No environmental data found for: "
            + ", ".join(unmatched)
        )

    result = result.drop(columns="_merge")

    # Calculate impact for each food item
    result["CO2_total_kg"] = (
        result["Quantity_kg"] * result["CO2_kg_per_kg"]
    )

    result["Water_total_litres"] = (
        result["Quantity_kg"] * result["Water_litres_per_kg"]
    )

    result["Land_total_m2"] = (
        result["Quantity_kg"] * result["Land_m2_per_kg"]
    )

    # Calculate total environmental impact
    totals = {
        "CO2_kg": result["CO2_total_kg"].sum(),
        "Water_litres": result["Water_total_litres"].sum(),
        "Land_m2": result["Land_total_m2"].sum()
    }

    return result, totals
