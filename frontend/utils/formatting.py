"""
frontend/utils/formatting.py — Indian number formatting and unit display helpers
"""


METRIC_LABELS = {
    "energy_kwh":         ("Energy Consumption", "kWh",    "⚡"),
    "pm25":               ("PM2.5 Air Quality",   "µg/m³", "🌫️"),
    "pm10":               ("PM10 Air Quality",    "µg/m³", "🌫️"),
    "water_litres":       ("Water Usage",         "L",     "💧"),
    "bin_fill_pct":       ("Waste Bin Fill",       "%",     "🗑️"),
    "temperature_c":      ("Temperature",          "°C",    "🌡️"),
    "humidity_pct":       ("Humidity",             "%",     "💦"),
    "occupancy_count":    ("Occupancy",            "people","👥"),
    "parking_count":      ("Parking",              "vehicles","🚗"),
    "equipment_util_pct": ("Equipment Utilisation","%",    "🔧"),
}

SEVERITY_COLORS = {
    "critical": "#FF4B4B",
    "high":     "#FF8C00",
    "medium":   "#FFD700",
    "low":      "#2E8B57",
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
}

STATUS_EMOJI = {
    "open":        "🔓",
    "in_progress": "🔄",
    "resolved":    "✅",
}

SOURCE_BADGE = {
    "synthetic": "🔵 DEMO",
    "manual":    "✏️ MANUAL",
    "esp32":     "📡 LIVE",
}


def metric_label(metric_type: str) -> str:
    return METRIC_LABELS.get(metric_type, (metric_type, "", ""))[0]


def metric_unit(metric_type: str) -> str:
    return METRIC_LABELS.get(metric_type, (metric_type, "", ""))[1]


def metric_emoji(metric_type: str) -> str:
    return METRIC_LABELS.get(metric_type, (metric_type, "", ""))[2]


def fmt_value(value: float, metric_type: str) -> str:
    """Format a numeric value with its unit."""
    unit = metric_unit(metric_type)
    if metric_type in ("occupancy_count", "parking_count"):
        return f"{int(value):,} {unit}"
    if metric_type in ("bin_fill_pct", "humidity_pct", "equipment_util_pct"):
        return f"{value:.1f} {unit}"
    return f"{value:.2f} {unit}"


def fmt_inr(amount: float) -> str:
    """Format as Indian Rupees with ₹ symbol and comma separation."""
    if abs(amount) >= 1_00_000:
        return f"₹{amount/1_00_000:.2f}L"
    if abs(amount) >= 1_000:
        return f"₹{amount:,.0f}"
    return f"₹{amount:.2f}"


def fmt_delta(value: float, unit: str = "", higher_is_better: bool = False) -> str:
    """Format a delta with + / - and colour hint."""
    sign  = "+" if value > 0 else ""
    arrow = "▲" if value > 0 else "▼"
    return f"{arrow} {sign}{value:.2f} {unit}".strip()


def score_color(score: float) -> str:
    if score >= 80:
        return "#2E8B57"
    if score >= 60:
        return "#FFD700"
    if score >= 40:
        return "#FF8C00"
    return "#FF4B4B"


def priority_tier(score: float) -> tuple[str, str]:
    """Returns (tier_label, color_hex)."""
    if score >= 80:
        return ("🔴 Critical", "#FF4B4B")
    if score >= 60:
        return ("🟠 High",     "#FF8C00")
    if score >= 40:
        return ("🟡 Medium",   "#FFD700")
    return ("🟢 Low",          "#2E8B57")
