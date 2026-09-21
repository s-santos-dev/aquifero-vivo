from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.indicators.calculation import aggregate, demand_pressure, groundwater_metrics, operational_metrics, rainfall_metrics
from app.simulation import SimulationConfig, generate_dataset


END = date(2026, 9, 20)


def rows(length=180, **fields):
    return [SimpleNamespace(measured_at=datetime.combine(END - timedelta(days=length - index - 1), datetime.min.time(), timezone.utc),
                            **{key: value(index) if callable(value) else value for key, value in fields.items()})
            for index in range(length)]


def test_rainfall_windows_and_previous_reference():
    result = rainfall_metrics(rows(180, precipitation_mm=2), END)
    for length in (7, 30, 60, 90):
        assert result[f"rainfall_{length}d"].value == 2 * length
    assert result["rainfall_avg_previous_30d"].value == 2
    assert result["rainfall_avg_previous_90d"].value == 2
    assert result["recent_rainfall_deficit_30d"].value == 0


def test_deficit_and_zero_reference_are_distinct():
    values = rows(60, precipitation_mm=lambda index: 10 if index < 30 else 5)
    assert rainfall_metrics(values, END)["recent_rainfall_deficit_30d"].value == .5
    zero = rows(60, precipitation_mm=lambda index: 0 if index < 30 else 5)
    assert rainfall_metrics(zero, END)["recent_rainfall_deficit_30d"].status == "INSUFFICIENT_DATA"


def test_missing_or_duplicate_days_are_not_zero():
    missing = rows(30, precipitation_mm=0)[:-1]
    value = rainfall_metrics(missing, END)["rainfall_30d"]
    assert value.value is None and value.observed_days == 29
    duplicate = rows(30, precipitation_mm=1)
    duplicate.append(duplicate[-1])
    assert rainfall_metrics(duplicate, END)["rainfall_30d"].value is None


@pytest.mark.parametrize("slope", [0, 1, -1])
def test_level_trends_and_drawdown(slope):
    records = rows(180, water_level_m=lambda i: 200 + slope * i, dynamic_level_m=lambda i: 205 + slope * i)
    result = groundwater_metrics(records, END)
    for length in (30, 60, 90):
        assert result[f"static_level_trend_{length}d"].value == slope
        assert result[f"dynamic_level_trend_{length}d"].value == slope
        assert result[f"drawdown_avg_{length}d"].value == 5
    assert result["current_drawdown"].value == 5


def test_level_history_insufficient_and_future_excluded():
    records = rows(90, water_level_m=20, dynamic_level_m=24)
    result = groundwater_metrics(records, END)
    assert result["static_level_change_30d"].value == 0
    assert result["static_level_change_60d"].value is None
    assert result["static_level_change_90d"].value is None
    assert result["dynamic_level_trend_90d"].value == 0
    assert result["current_static_level"].value == 20


def test_operational_changes_averages_utilization_and_failures():
    records = rows(180, flow_rate_m3_h=10, runtime_hours=8,
                   pumped_volume_m3=lambda i: 80 if i < 90 else 120,
                   daily_demand_m3=lambda i: 100 if i < 90 else 150,
                   utilization=.5, operational_failure=lambda i: i == 179)
    result = operational_metrics(records, END)
    assert result["current_flow_rate"].value == 10
    assert result["current_utilization"].value == .5
    assert result["demand_change_90d"].value == 50
    assert result["pumped_volume_change_90d"].value == 40
    assert result["demand_pressure_30d"].value == 0
    assert result["pumping_hours_avg_7d"].value == 8
    assert result["failures_30d"].value == 1
    assert result["days_since_last_failure"].value == 0


def test_demand_pressure_increase_decrease_and_zero_reference():
    from app.indicators.calculation import days
    increasing = days(rows(60, daily_demand_m3=lambda i: 100 if i < 30 else 150), "daily_demand_m3")
    decreasing = days(rows(60, daily_demand_m3=lambda i: 150 if i < 30 else 100), "daily_demand_m3")
    zero = days(rows(60, daily_demand_m3=lambda i: 0 if i < 30 else 100), "daily_demand_m3")
    assert demand_pressure(increasing, END).value == .5
    assert demand_pressure(decreasing, END).value == pytest.approx(-1 / 3, abs=1e-5)
    assert demand_pressure(zero, END).value is None


def test_reference_date_is_a_hard_boundary_for_pure_calculation():
    at = END - timedelta(days=10)
    recorded = rows(90, precipitation_mm=3)
    series = {row.measured_at.date(): float(row.precipitation_mm) for row in recorded}
    assert aggregate(series, at, 30, "mm", "sum").value == 90
    assert rainfall_metrics(recorded, at)["rainfall_30d"].value == 90
    recorded.append(SimpleNamespace(measured_at=datetime.combine(END + timedelta(days=1), datetime.min.time(), timezone.utc), precipitation_mm=99999))
    assert rainfall_metrics(recorded, at)["rainfall_30d"].value == 90


def test_scenario_indicators_reflect_simulated_pressure():
    from app.simulation.scenarios import Scenario
    summaries = {}
    for scenario in Scenario:
        dataset = generate_dataset(SimulationConfig(well_count=6, sector_count=2, days=180, scenario=scenario))
        end = date.fromisoformat(dataset.sector_daily[-1]["date"])
        rain = [SimpleNamespace(measured_at=datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc),
                                precipitation_mm=row["precipitation_mm"])
                for row in dataset.sector_daily if row["sector_id"] == dataset.sectors[0]["sector_id"]]
        well = dataset.wells[0]["well_id"]
        ops = [SimpleNamespace(measured_at=datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc),
                               daily_demand_m3=row["daily_demand_m3"], flow_rate_m3_h=row["flow_rate_m3_h"],
                               runtime_hours=row["runtime_hours"], pumped_volume_m3=row["pumped_volume_m3"],
                               utilization=row["utilization"], operational_failure=row["operational_failure"])
               for row in dataset.well_daily if row["well_id"] == well]
        groundwater = [SimpleNamespace(measured_at=datetime.fromisoformat(item["date"]).replace(tzinfo=timezone.utc),
                                       water_level_m=item["static_level_m"], dynamic_level_m=item["dynamic_level_m"])
                       for item in dataset.well_daily if item["well_id"] == well]
        summaries[scenario.value] = (rainfall_metrics(rain, end)["rainfall_90d"].value,
                                     operational_metrics(ops, end)["demand_avg_90d"].value,
                                     groundwater_metrics(groundwater, end)["drawdown_avg_30d"].value)
    assert summaries["NORMAL"][0] > summaries["DROUGHT"][0] > summaries["SEVERE_STRESS"][0]
    assert summaries["NORMAL"][1] < summaries["SEVERE_STRESS"][1]
    assert summaries["NORMAL"][2] < summaries["SEVERE_STRESS"][2]
