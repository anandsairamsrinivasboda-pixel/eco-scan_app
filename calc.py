import pandas as pd


# Kilograms in one unit of mass.
UNIT_TO_KG = {
    "kg": 1.0,
    "kilogram": 1.0,
    "kilograms": 1.0,
    "g": 0.001,
    "gm": 0.001,
    "gms": 0.001,
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


def _report_value(value, digits=3):
    """Format a report number, showing missing values as unavailable."""
    if pd.isna(value):
        return "Unavailable"
    return f"{float(value):,.{digits}f}"


def format_report(summary):
    """Return the customer-facing report in the requested text layout."""
    table = summary["report_table"]
    lines = [
        "Food name | Water usage (L) | Land usage (m²) | Carbon footprint (kg CO₂)",
        "----------|-----------------|----------------|--------------------------",
    ]

    for _, row in table.iterrows():
        lines.append(
            f"{row['Food name']} | "
            f"{_report_value(row['Water usage (L)'])} | "
            f"{_report_value(row['Land usage (m²)'], 4)} | "
            f"{_report_value(row['Carbon footprint (kg CO₂)'], 4)}"
        )

    totals = summary["totals"]
    lines.extend([
        "",
        f"Total land usage: {_format_report_total(totals['land'])}",
        f"Total water usage: {_format_report_total(totals['water'])}",
        f"Total carbon footprint: {_format_report_total(totals['carbon'])}",
    ])

    phrases = {
        "land": "consumes most of land in your bill",
        "water": "consumes most of water in your bill",
        "carbon": "produces most of CO₂ in your bill",
    }
    for measure in ("land", "water", "carbon"):
        contributor = summary["highest_contributors"][measure]
        if contributor is None:
            lines.append(f"No {measure} data is available for comparison.")
            continue

        percentage = contributor["share_of_total_percent"]
        basis = "total"
        if percentage is None:
            percentage = contributor["share_of_known_subtotal_percent"]
            basis = "known subtotal"
        if percentage is None:
            percentage_text = "unknown"
        else:
            percentage_text = f"{percentage:.2f}% of {basis}"

        lines.append(
            f"{contributor['food']} {phrases[measure]}: {percentage_text}"
        )

    if summary.get("suggestions"):
        lines.extend(["", "Suggestions:"])
        labels = {
            "land": "land usage",
            "water": "water consumption",
            "carbon": "carbon footprint",
        }
        for suggestion in summary["suggestions"]:
            label = labels[suggestion["measure"]]
            lines.append(
                f"For better {label}, you can prefer {suggestion['alternative']} "
                f"instead of {suggestion['food']}, which could reduce {label} "
                f"by {suggestion['reduction_percent']:.2f}% for the same quantity."
            )

    return "\n".join(lines)


def _format_report_total(total):
    if total["complete"]:
        return f"{total['total']:,.4f} {total['unit']}"
    return (
        f"incomplete (known subtotal {total['known_subtotal']:,.4f} "
        f"{total['unit']})"
    )


def _clean_candidate_names(value):
    """Accept only a list of possible alternatives provided by vision.py."""
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(name).strip() for name in value if name is not None and str(name).strip()]


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

    # Food alternatives must be deliberately assigned to a shared group in
    # data.csv. Older databases without this column safely produce no advice.
    if "similar_group" not in env.columns:
        env["similar_group"] = pd.NA
    env["similar_group"] = env["similar_group"].astype("string").str.strip()
    env.loc[env["similar_group"].eq(""), "similar_group"] = pd.NA
    env["similar_group_key"] = env["similar_group"].str.casefold()

    # These fields are optional for foods sold by mass.
    # They are required when the receipt gives a count like "3 pieces".
    for column in ["Weight_per_item", "Weight_unit"]:
        if column not in items.columns:
            items[column] = pd.NA
    if "similar_products" not in items.columns:
        items["similar_products"] = pd.Series(
            [[] for _ in range(len(items))], index=items.index, dtype=object
        )
    else:
        items["similar_products"] = items["similar_products"].apply(
            _clean_candidate_names
        )

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
    if mass_rows.any():
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
    if count_rows.any():
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

    # Cross-check every candidate against the CSV and require the same
    # similarity group. This protects calc.py if a candidate is incorrect.
    env_by_key = env.set_index("Product_key")
    similar_by_food_key = {}
    for _, row in result.iterrows():
        source_key = row["Product_key"]
        group_key = row["similar_group_key"]
        accepted = set()
        if pd.notna(group_key):
            for candidate in _clean_candidate_names(row["similar_products"]):
                candidate_key = candidate.casefold()
                if candidate_key not in env_by_key.index or candidate_key == source_key:
                    continue
                candidate_group = env_by_key.loc[candidate_key, "similar_group_key"]
                if pd.notna(candidate_group) and candidate_group == group_key:
                    accepted.add(candidate_key)
        similar_by_food_key.setdefault(source_key, set()).update(accepted)
    result = result.drop(columns=["similar_products"])

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

    # Calculate totals and find the highest-contributing food for each measure.
    measures = {
        "carbon": ("CO2_total_kg", "CO2_kg_per_kg", "kg CO2e"),
        "water": ("Water_total_litres", "Water_litres_per_kg", "litres"),
        "land": ("Land_total_m2", "Land_m2_per_kg", "m²"),
    }

    totals = {}
    highest_contributors = {}

    for measure, (column, _, unit) in measures.items():
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

    # Suggest the lowest-impact same-group alternative for the top food in
    # each measure. The comparison assumes the same purchased weight.
    suggestions = []
    for measure, (_, rate_column, unit) in measures.items():
        top = highest_contributors[measure]
        if top is None or top["impact"] <= 0:
            continue

        top_row = by_food.loc[by_food["Product"] == top["food"]].iloc[0]
        top_key = top_row["Product_key"]
        if not similar_by_food_key.get(top_key):
            continue

        current_rate = env_by_key.loc[top_key, rate_column]
        if pd.isna(current_rate) or current_rate <= 0:
            continue

        choices = []
        for candidate_key in similar_by_food_key[top_key]:
            candidate_rate = env_by_key.loc[candidate_key, rate_column]
            if pd.isna(candidate_rate) or candidate_rate < 0 or candidate_rate >= current_rate:
                continue
            candidate_impact = float(top_row["Quantity_kg"]) * float(candidate_rate)
            choices.append((float(candidate_rate), candidate_key, candidate_impact))

        if choices:
            _, candidate_key, alternative_impact = min(
                choices, key=lambda candidate: candidate[0]
            )
            suggestions.append({
                "measure": measure,
                "food": top["food"],
                "alternative": env_by_key.loc[candidate_key, "Product"],
                "reduction_percent": (
                    (top["impact"] - alternative_impact) / top["impact"] * 100
                ),
                "current_impact": top["impact"],
                "alternative_impact": alternative_impact,
                "unit": unit,
            })

    by_food = by_food.drop(columns=["Product_key"])

    summary = {
        "by_food": by_food,
        "totals": totals,
        "highest_contributors": highest_contributors,
        "suggestions": suggestions,
    }

    # Customer-facing table in the exact column order requested. Keep the
    # detailed `result` DataFrame and existing summary fields for app.py use.
    def report_food_name(row):
        # Show the combined purchased amount beside the food name.
        quantity_kg = float(row["Quantity_kg"])
        if abs(quantity_kg - round(quantity_kg)) < 1e-10:
            quantity_text = f"{int(round(quantity_kg))}"
            unit_text = "Kg"
        else:
            grams = quantity_kg * 1000
            if abs(grams - round(grams)) < 1e-8:
                quantity_text = f"{int(round(grams))}"
            else:
                quantity_text = f"{grams:.3f}".rstrip("0").rstrip(".")
            unit_text = "gm"
        return f"{row['Product']} {quantity_text} {unit_text}"

    report_foods = by_food.copy()
    report_foods["Food name"] = report_foods.apply(report_food_name, axis=1)
    summary["report_table"] = by_food[[
        "Product",
        "Water_total_litres",
        "Land_total_m2",
        "CO2_total_kg",
    ]].rename(columns={
        "Water_total_litres": "Water usage (L)",
        "Land_total_m2": "Land usage (m²)",
        "CO2_total_kg": "Carbon footprint (kg CO₂)",
    })
    summary["report_table"]["Food name"] = report_foods["Food name"].to_numpy()
    summary["report_table"] = summary["report_table"][
        ["Food name", "Water usage (L)", "Land usage (m²)", "Carbon footprint (kg CO₂)"]
    ]
    summary["report_text"] = format_report(summary)

    return result, summary
