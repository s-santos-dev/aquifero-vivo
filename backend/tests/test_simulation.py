import json

import numpy as np
import pytest
from pydantic import ValidationError

from app.data_provenance import DataClassification, require_observation
from app.schemas import OperationalMeasurementCreate
from app.simulation import Scenario, SimulationConfig, generate_dataset, write_dataset


def _mean(records, field):
    return float(np.mean([record[field] for record in records]))


@pytest.fixture(scope="module")
def scenarios():
    common = dict(seed=77, well_count=30, sector_count=3, days=180)
    return {
        scenario: generate_dataset(SimulationConfig(scenario=scenario, **common))
        for scenario in Scenario
    }


def test_default_scale_matches_requested_operational_dataset():
    config = SimulationConfig()
    assert config.well_count == 80
    assert config.sector_count == 20
    assert config.days == 730


def test_seed_is_reproducible():
    config = SimulationConfig(seed=123, well_count=8, sector_count=2, days=15)
    first = generate_dataset(config)
    second = generate_dataset(config)
    assert first.sectors == second.sectors
    assert first.wells == second.wells
    assert first.sector_daily == second.sector_daily
    assert first.well_daily == second.well_daily


def test_dataset_cardinality_and_physical_invariants():
    config = SimulationConfig(seed=9, well_count=12, sector_count=3, days=40)
    dataset = generate_dataset(config)
    assert dataset.counts == {
        "sectors": 3,
        "wells": 12,
        "sector_daily": 120,
        "well_daily": 480,
    }
    assert all(row["dynamic_level_m"] >= row["static_level_m"] for row in dataset.well_daily)
    assert all(
        row["drawdown_m"] == pytest.approx(row["dynamic_level_m"] - row["static_level_m"], abs=0.002)
        for row in dataset.well_daily
    )
    assert all(0 <= row["runtime_hours"] <= 24 for row in dataset.well_daily)
    assert all(row["pumped_volume_m3"] >= 0 for row in dataset.well_daily)
    assert all(row["precipitation_mm"] >= 0 for row in dataset.sector_daily)


def test_scenarios_have_ordered_rain_recharge_demand_and_stress(scenarios):
    normal = scenarios[Scenario.NORMAL]
    drought = scenarios[Scenario.DROUGHT]
    severe = scenarios[Scenario.SEVERE_STRESS]

    assert _mean(normal.sector_daily, "precipitation_mm") > _mean(
        drought.sector_daily, "precipitation_mm"
    ) > _mean(severe.sector_daily, "precipitation_mm")
    assert _mean(normal.sector_daily, "recharge_index") > _mean(
        drought.sector_daily, "recharge_index"
    ) > _mean(severe.sector_daily, "recharge_index")
    assert _mean(normal.sector_daily, "daily_demand_m3") < _mean(
        drought.sector_daily, "daily_demand_m3"
    ) < _mean(severe.sector_daily, "daily_demand_m3")
    assert _mean(normal.sector_daily, "system_utilization") < _mean(
        drought.sector_daily, "system_utilization"
    ) < _mean(severe.sector_daily, "system_utilization")
    assert _mean(normal.well_daily, "risk_score") < _mean(
        drought.well_daily, "risk_score"
    ) < _mean(severe.well_daily, "risk_score")


def test_pumping_pressure_and_persistent_drawdown_are_coherent(scenarios):
    normal = scenarios[Scenario.NORMAL]
    operating = [row for row in normal.well_daily if not row["operational_failure"]]
    correlation = np.corrcoef(
        [row["pumped_volume_m3"] for row in operating],
        [row["drawdown_m"] for row in operating],
    )[0, 1]
    assert correlation > 0.5

    deltas = {}
    per_day = normal.config.well_count
    for scenario, dataset in scenarios.items():
        first = _mean(dataset.well_daily[:per_day], "static_level_m")
        last = _mean(dataset.well_daily[-per_day:], "static_level_m")
        deltas[scenario] = last - first
    assert deltas[Scenario.NORMAL] < deltas[Scenario.DROUGHT] < deltas[Scenario.SEVERE_STRESS]
    assert deltas[Scenario.SEVERE_STRESS] > 4.0

    # Levels are depths below the simulator reference: a larger value is deeper water.
    final_static = {
        scenario: _mean(dataset.well_daily[-per_day:], "static_level_m")
        for scenario, dataset in scenarios.items()
    }
    assert final_static[Scenario.NORMAL] < final_static[Scenario.DROUGHT] < final_static[Scenario.SEVERE_STRESS]


def test_well_utilization_is_planned_daily_capacity_fraction(scenarios):
    dataset = scenarios[Scenario.NORMAL]
    sector_utilization = {
        (row["date"], row["sector_id"]): row["system_utilization"]
        for row in dataset.sector_daily
    }
    # Capacity-proportional allocation makes each well's requested-runtime/24
    # equal to its sector's requested-volume / nominal daily capacity.
    assert all(
        row["utilization"] == pytest.approx(
            sector_utilization[(row["date"], row["sector_id"])], abs=0.00001
        )
        for row in dataset.well_daily
    )


def test_prolonged_drought_and_high_demand_create_critical_conditions(scenarios):
    critical_rates = {
        scenario: np.mean([row["risk_level"] == "CRITICAL" for row in dataset.well_daily])
        for scenario, dataset in scenarios.items()
    }
    failure_rates = {
        scenario: np.mean([row["operational_failure"] for row in dataset.well_daily])
        for scenario, dataset in scenarios.items()
    }
    assert critical_rates[Scenario.NORMAL] < critical_rates[Scenario.DROUGHT]
    assert critical_rates[Scenario.DROUGHT] < critical_rates[Scenario.SEVERE_STRESS]
    assert critical_rates[Scenario.SEVERE_STRESS] > 0.35
    assert failure_rates[Scenario.NORMAL] < failure_rates[Scenario.DROUGHT]
    assert failure_rates[Scenario.DROUGHT] < failure_rates[Scenario.SEVERE_STRESS]


def test_all_generated_rows_and_manifest_are_unambiguously_simulated(tmp_path):
    dataset = generate_dataset(
        SimulationConfig(seed=5, well_count=4, sector_count=2, days=3)
    )
    for collection in (
        dataset.sectors,
        dataset.wells,
        dataset.sector_daily,
        dataset.well_daily,
    ):
        assert all(row["data_classification"] == "SIMULATED" for row in collection)
        assert all(row["is_synthetic"] is True for row in collection)

    output = write_dataset(dataset, tmp_path / "synthetic-output")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_classification"] == "SIMULATED"
    assert manifest["is_synthetic"] is True
    assert set(manifest["sha256"]) == {
        "sectors.csv",
        "wells.csv",
        "sector_daily.csv",
        "well_daily.csv",
    }


def test_shared_contract_accepts_explicitly_simulated_data():
    payload = {
        "well_id": "69299fc0-7dfe-4e06-b6ac-34c5e55277b4",
        "measured_at": "2026-01-01T00:00:00Z",
        "flow_rate_m3_h": 30,
        "data_classification": "SIMULATED",
    }
    assert OperationalMeasurementCreate.model_validate(payload).data_classification == "SIMULATED"
    with pytest.raises(ValueError, match="não pode ser exposto"):
        require_observation(DataClassification.SIMULATED)

    payload["data_classification"] = "PUBLIC"
    assert OperationalMeasurementCreate.model_validate(payload).data_classification == "PUBLIC"
