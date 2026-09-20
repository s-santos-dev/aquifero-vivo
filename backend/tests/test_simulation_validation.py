from dataclasses import replace
import pytest
from app.simulation import SimulationConfig, generate_dataset
from app.simulation.validate import validate_dataset
from app.simulation.normalize import normalized_batches
from app.simulation.relationships import recharge_step, stress_step


@pytest.fixture
def dataset():
    return generate_dataset(SimulationConfig(well_count=6, sector_count=2, days=10))


def test_valid_unique_geographic_and_normalized_contracts(dataset):
    validate_dataset(dataset)
    assert len({r["well_id"] for r in dataset.wells}) == 6
    for model, rows in normalized_batches(dataset):
        assert all(r["data_classification"] == "SIMULATED" and r["source"] for r in rows)
        assert len({r["id"] for r in rows}) == len(rows)


@pytest.mark.parametrize("collection,field,value", [
    ("wells", "latitude", 91), ("wells", "longitude", -181),
    ("wells", "depth_m", 0), ("wells", "is_synthetic", False),
    ("wells", "source", None), ("wells", "data_classification", "PUBLIC"), ("wells", "sector_id", "missing"),
    ("well_daily", "flow_rate_m3_h", -1), ("well_daily", "runtime_hours", 25),
    ("well_daily", "runtime_hours", -1), ("well_daily", "daily_demand_m3", -1),
    ("well_daily", "pumped_volume_m3", -1), ("well_daily", "dynamic_level_m", 0),
    ("well_daily", "static_level_m", float("nan")), ("sector_daily", "precipitation_mm", -1),
    ("sector_daily", "date", "1900-01-01"),
])
def test_impossible_values_rejected(dataset, collection, field, value):
    getattr(dataset, collection)[0][field] = value
    with pytest.raises(ValueError):
        validate_dataset(dataset)


def test_duplicates_and_incomplete_series_rejected(dataset):
    dataset.wells[1]["well_id"] = dataset.wells[0]["well_id"]
    with pytest.raises(ValueError, match="duplicados"):
        validate_dataset(dataset)


def test_return_of_rain_recovers_state_progressively():
    dry = 0.1
    wet = recharge_step(dry, 1.0, 1.0)
    assert dry < wet < 1
    assert recharge_step(wet, 1.0, 1.0) > wet
    assert stress_step(2, 0, 0, 1) < 2


def test_env_configuration(monkeypatch):
    monkeypatch.setenv("SIMULATION_SEED", "123")
    monkeypatch.setenv("SIMULATION_WELLS", "10")
    monkeypatch.setenv("SIMULATION_SECTORS", "2")
    config = SimulationConfig.from_env()
    assert config.seed == 123 and config.well_count == 10
    assert SimulationConfig.from_env(seed=42).seed == 42
    with pytest.raises(ValueError):
        replace(config, max_latitude=95)


def test_incomplete_series_rejected(dataset):
    dataset.well_daily.pop()
    with pytest.raises(ValueError, match="incompleta"):
        validate_dataset(dataset)


def test_provenance_missing_rejected(dataset):
    del dataset.well_daily[0]["data_classification"]
    with pytest.raises(ValueError, match="Proveniência"):
        validate_dataset(dataset)
