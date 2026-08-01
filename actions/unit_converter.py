def unit_converter(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "convert").strip().lower()

    if player:
        player.write_log(f"[UnitConverter] action={action}")

    try:
        if action in ("convert", "converter"):
            value = params.get("value", 0)
            from_unit = params.get("from", "").strip().lower()
            to_unit = params.get("to", "").strip().lower()
            category = params.get("category", "").strip().lower()

            try:
                value = float(value)
            except (ValueError, TypeError):
                return f"Invalid value: {value}"

            if not from_unit or not to_unit:
                return "Both 'from' and 'to' units are required."

            return _convert(value, from_unit, to_unit, category)

        elif action in ("list", "units", "categories"):
            category = params.get("category", "").strip().lower()
            return _list_units(category)

        return (
            f"Unknown action: '{action}'. "
            f"Available: convert, list"
        )

    except Exception as e:
        return f"Unit converter failed: {e}"


UNITS = {
    "length": {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
        "inch": 0.0254, "inches": 0.0254, "feet": 0.3048, "foot": 0.3048,
        "yard": 0.9144, "yards": 0.9144, "mile": 1609.344, "miles": 1609.344,
        "millimeter": 0.001, "centimeter": 0.01, "meter": 1.0, "kilometer": 1000.0,
    },
    "weight": {
        "mg": 0.000001, "g": 0.001, "kg": 1.0, "ton": 1000.0,
        "oz": 0.0283495, "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592,
        "milligram": 0.000001, "gram": 0.001, "kilogram": 1.0, "ounce": 0.0283495,
    },
    "temperature": "special",
    "volume": {
        "ml": 0.001, "l": 1.0, "liter": 1.0, "liters": 1.0, "litre": 1.0,
        "gal": 3.78541, "gallon": 3.78541, "gallons": 3.78541,
        "qt": 0.946353, "quart": 0.946353,
        "pt": 0.473176, "pint": 0.473176,
        "cup": 0.236588, "cups": 0.236588,
        "fl_oz": 0.0295735, "tbsp": 0.0147868, "tsp": 0.00492892,
        "milliliter": 0.001, "milliliters": 0.001,
    },
    "area": {
        "mm2": 0.000001, "cm2": 0.0001, "m2": 1.0, "km2": 1000000.0,
        "ha": 10000.0, "acre": 4046.86, "ft2": 0.092903, "in2": 0.00064516,
        "hectare": 10000.0, "acres": 4046.86,
    },
    "speed": {
        "m/s": 1.0, "km/h": 0.277778, "mph": 0.44704, "knot": 0.514444,
        "kph": 0.277778,
    },
    "time": {
        "s": 1.0, "sec": 1.0, "second": 1.0,
        "min": 60.0, "minute": 60.0,
        "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
        "day": 86400.0, "days": 86400.0,
        "week": 604800.0, "weeks": 604800.0,
        "month": 2592000.0, "year": 31536000.0,
    },
    "data": {
        "b": 1.0, "byte": 1.0, "bytes": 1.0,
        "kb": 1024.0, "kilobyte": 1024.0,
        "mb": 1048576.0, "megabyte": 1048576.0,
        "gb": 1073741824.0, "gigabyte": 1073741824.0,
        "tb": 1099511627776.0, "terabyte": 1099511627776.0,
        "kib": 1024.0, "mib": 1048576.0, "gib": 1073741824.0, "tib": 1099511627776.0,
    },
}


def _convert(value: float, from_unit: str, to_unit: str, category: str) -> str:
    if category:
        cat_units = UNITS.get(category)
        if cat_units is None:
            return f"Unknown category: {category}. Available: {', '.join(UNITS.keys())}"
    else:
        cat_units = None
        for cat, units in UNITS.items():
            if units == "special":
                if from_unit in ("c", "f", "k", "celsius", "fahrenheit", "kelvin"):
                    cat_units = units
                    category = cat
                    break
                continue
            if from_unit in units and to_unit in units:
                cat_units = units
                category = cat
                break
        if cat_units is None:
            return (
                f"Could not determine conversion category for '{from_unit}' → '{to_unit}'. "
                f"Use 'list' to see supported units."
            )

    if category == "temperature":
        return _convert_temperature(value, from_unit, to_unit)

    if from_unit == to_unit:
        return f"{value} {from_unit} = {value} {to_unit}"

    base_value = value * cat_units[from_unit]
    result = base_value / cat_units[to_unit]

    return f"{value} {from_unit} = {result:.4f} {to_unit}"


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> str:
    from_lower = from_unit[:1].lower()
    to_lower = to_unit[:1].lower()

    if from_lower == to_lower:
        return f"{value} {from_unit} = {value} {to_unit}"

    if from_lower == "c":
        celsius = value
    elif from_lower == "f":
        celsius = (value - 32) * 5 / 9
    elif from_lower == "k":
        celsius = value - 273.15
    else:
        return f"Unknown temperature unit: {from_unit}"

    if to_lower == "c":
        result = celsius
    elif to_lower == "f":
        result = celsius * 9 / 5 + 32
    elif to_lower == "k":
        result = celsius + 273.15
    else:
        return f"Unknown temperature unit: {to_unit}"

    return f"{value} {from_unit} = {result:.2f} {to_unit}"


def _list_units(category: str) -> str:
    if category:
        units = UNITS.get(category)
        if units is None:
            return f"Unknown category: {category}. Available: {', '.join(UNITS.keys())}"
        if units == "special":
            return "Temperature units: C (Celsius), F (Fahrenheit), K (Kelvin)"
        display = sorted(set(k for k in units.keys() if not k.endswith("s") and k == k.lower()))
        return f"{category.title()} units: {', '.join(display)}"

    lines = ["Available conversion categories:"]
    for cat in UNITS:
        lines.append(f"  - {cat.title()}: temperature, length, weight, volume, speed, time, data, area")
    return "\n".join(lines)
