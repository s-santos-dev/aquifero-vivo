"""Pure daily calculations. Missing or duplicate days never become zeroes."""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any

from app.schemas.indicators import IndicatorValue


def metric(value: float | None, unit: str, observed: int, required: int) -> IndicatorValue:
    return IndicatorValue(
        value=round(value, 5) if value is not None else None,
        status="AVAILABLE" if value is not None else "INSUFFICIENT_DATA",
        unit=unit,
        observed_days=observed,
        required_days=required,
    )


def days(rows: list[Any], field: str) -> dict[date, float | None]:
    """One observation per UTC day; duplicates are ambiguous and therefore missing."""
    result: dict[date, float | None] = {}
    for row in rows:
        day = row.measured_at.date()
        value = getattr(row, field)
        if day in result:
            result[day] = None
        else:
            result[day] = float(value) if value is not None else None
    return result


def window(series: dict[date, float | None], end: date, length: int) -> tuple[list[float], int]:
    values = [series.get(end - timedelta(days=offset)) for offset in range(length - 1, -1, -1)]
    present = [value for value in values if value is not None]
    return present, length


def aggregate(series: dict[date, float | None], end: date, length: int, unit: str, operation: str) -> IndicatorValue:
    values, required = window(series, end, length)
    if len(values) != required:
        return metric(None, unit, len(values), required)
    return metric(sum(values) if operation == "sum" else mean(values), unit, required, required)


def trend(series: dict[date, float | None], end: date, length: int, unit: str) -> IndicatorValue:
    values, required = window(series, end, length)
    if len(values) != required or length < 2:
        return metric(None, unit + "/dia", len(values), required)
    center = (length - 1) / 2
    denominator = sum((index - center) ** 2 for index in range(length))
    slope = sum((index - center) * value for index, value in enumerate(values)) / denominator
    return metric(slope, unit + "/dia", required, required)


def change(series: dict[date, float | None], end: date, length: int, unit: str) -> IndicatorValue:
    """Difference between adjacent complete window means, in the original unit."""
    recent = aggregate(series, end, length, unit, "avg")
    previous = aggregate(series, end - timedelta(days=length), length, unit, "avg")
    observed = recent.observed_days + previous.observed_days
    value = recent.value - previous.value if recent.value is not None and previous.value is not None else None
    return metric(value, unit, observed, 2 * length)


def deficit(series: dict[date, float | None], end: date) -> IndicatorValue:
    """Positive fraction of prior 30-day rain missing in the recent 30 days."""
    recent = aggregate(series, end, 30, "mm", "sum")
    previous = aggregate(series, end - timedelta(days=30), 30, "mm", "sum")
    observed = recent.observed_days + previous.observed_days
    if recent.value is None or previous.value is None or previous.value == 0:
        return metric(None, "fração", observed, 60)
    return metric(max(0.0, 1 - recent.value / previous.value), "fração", 60, 60)


def demand_pressure(series: dict[date, float | None], end: date) -> IndicatorValue:
    """Signed relative demand change versus the immediately preceding 30 days."""
    recent = aggregate(series, end, 30, "m³/dia", "avg")
    previous = aggregate(series, end - timedelta(days=30), 30, "m³/dia", "avg")
    observed = recent.observed_days + previous.observed_days
    if recent.value is None or previous.value is None or previous.value == 0:
        return metric(None, "fração", observed, 60)
    return metric(recent.value / previous.value - 1, "fração", 60, 60)


def latest(series: dict[date, float | None], end: date, unit: str) -> IndicatorValue:
    value = series.get(end)
    return metric(value, unit, int(value is not None), 1)


def rainfall_metrics(rows: list[Any], end: date) -> dict[str, IndicatorValue]:
    rain = days(rows, "precipitation_mm")
    result = {f"rainfall_{length}d": aggregate(rain, end, length, "mm", "sum") for length in (7, 30, 60, 90)}
    result["rainfall_avg_previous_30d"] = aggregate(rain, end - timedelta(days=30), 30, "mm/dia", "avg")
    result["rainfall_avg_previous_90d"] = aggregate(rain, end - timedelta(days=90), 90, "mm/dia", "avg")
    # This compares adjacent observations, never a climatological normal.
    result["recent_rainfall_deficit_30d"] = deficit(rain, end)
    return result


def groundwater_metrics(rows: list[Any], end: date) -> dict[str, IndicatorValue]:
    static = days(rows, "water_level_m")
    dynamic = days(rows, "dynamic_level_m")
    drawdown = {day: (value - static[day] if value is not None and static.get(day) is not None else None) for day, value in dynamic.items()}
    result = {
        "current_static_level": latest(static, end, "m"),
        "current_dynamic_level": latest(dynamic, end, "m"),
        "current_drawdown": latest(drawdown, end, "m"),
    }
    for length in (30, 60, 90):
        for name, series in (("static_level", static), ("dynamic_level", dynamic)):
            result[f"{name}_change_{length}d"] = change(series, end, length, "m")
            result[f"{name}_trend_{length}d"] = trend(series, end, length, "m")
        result[f"drawdown_avg_{length}d"] = aggregate(drawdown, end, length, "m", "avg")
    for length in (30, 90):
        result[f"drawdown_trend_{length}d"] = trend(drawdown, end, length, "m")
    return result


def operational_metrics(rows: list[Any], end: date) -> dict[str, IndicatorValue]:
    fields = {
        "flow": ("flow_rate_m3_h", "m³/h"),
        "pumping_hours": ("runtime_hours", "h/dia"),
        "pumped_volume": ("pumped_volume_m3", "m³/dia"),
        "demand": ("daily_demand_m3", "m³/dia"),
        "utilization": ("utilization", "fração"),
    }
    series = {name: days(rows, field) for name, (field, _) in fields.items()}
    result = {"current_flow_rate": latest(series["flow"], end, "m³/h"), "current_utilization": latest(series["utilization"], end, "fração")}
    for name, (_, unit) in fields.items():
        lengths = (7, 30, 90)
        for length in lengths:
            result[f"{name}_avg_{length}d"] = aggregate(series[name], end, length, unit, "avg")
    for name in ("flow", "demand", "pumped_volume"):
        unit = fields[name][1]
        for length in (30, 90):
            result[f"{name}_change_{length}d"] = change(series[name], end, length, unit)
            result[f"{name}_trend_{length}d"] = trend(series[name], end, length, unit)
    result["demand_pressure_30d"] = demand_pressure(series["demand"], end)
    failure = days(rows, "operational_failure")
    # False is an observed zero; None is missing.
    for length in (30, 90):
        result[f"failures_{length}d"] = aggregate(failure, end, length, "falhas", "sum")
    occurred = [day for day, value in failure.items() if day <= end and value == 1]
    result["days_since_last_failure"] = metric((end - max(occurred)).days if occurred else None, "dias", len(failure), 1)
    return result
