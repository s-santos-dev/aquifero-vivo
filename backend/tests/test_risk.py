from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.indicators.calculation import metric, groundwater_metrics, operational_metrics, rainfall_metrics
from app.schemas.indicators import IndicatorResponse
from app.risk.config import GROUPS
from app.risk.normalization import normalize
from app.risk.classification import classify
from app.risk.scoring import evaluate
from app.risk.service import well_risk

ID = UUID("00000000-0000-0000-0000-000000000001")
END = date(2026, 9, 20)


def sample():
    response = IndicatorResponse(entity_id=ID, reference_date=END, data_classification="SIMULATED", source="fixture")
    for _, _, criteria in GROUPS.values():
        for c in criteria:
            getattr(response, c.section)[c.key] = metric(c.low * c.direction, "fixture", 90, 90)
    return response


def score(response):
    return evaluate(response, ID, "SIM-PI-001", "SIMULATED", "fixture")


@pytest.mark.parametrize("criterion", [c for _, _, criteria in GROUPS.values() for c in criteria])
def test_normalization_bounds_monotonicity_and_missing(criterion):
    values = [normalize(criterion.direction * v, criterion) for v in (criterion.low - 10, criterion.low, (criterion.low + criterion.high) / 2, criterion.high, criterion.high + 10)]
    assert values == [0, 0, 50, 100, 100]
    assert values == sorted(values)
    assert normalize(None, criterion) is None
    assert normalize(float("nan"), criterion) is None


@pytest.mark.parametrize("value,expected", [(0,"NORMAL"),(39.999,"NORMAL"),(40,"ATTENTION"),(59.999,"ATTENTION"),(60,"HIGH"),(79.999,"HIGH"),(80,"CRITICAL"),(100,"CRITICAL"),(None,None)])
def test_classification(value, expected):
    assert classify(value) == expected


def test_weights_and_contributions():
    response = sample()
    for _, _, criteria in GROUPS.values():
        for c in criteria:
            getattr(response, c.section)[c.key] = metric(c.high * c.direction, "fixture", 90, 90)
    result = score(response)
    assert result.score == pytest.approx(100)
    assert result.coverage == 1
    assert sum(f.contribution for f in result.factors) == result.score
    assert sum(f.weight for f in result.factors) == pytest.approx(1)
    assert all(f.indicators and "→" in f.explanation for f in result.factors)
    assert [f.contribution for f in result.factors] == sorted([f.contribution for f in result.factors], reverse=True)


@pytest.mark.parametrize("missing", ["rainfall", "demand", "pumping", "operations"])
def test_saturation_with_optional_group_missing(missing):
    response = sample()
    for group, (_, _, criteria) in GROUPS.items():
        for c in criteria:
            getattr(response, c.section)[c.key] = metric(c.high * c.direction, "fixture", 90, 90)
            if group == missing:
                getattr(response, c.section).pop(c.key)
    result = score(response)
    assert result.score == pytest.approx(100)
    assert sum(f.contribution or 0 for f in result.factors) == pytest.approx(result.score)


@pytest.mark.parametrize("criterion", [c for _, _, criteria in GROUPS.values() for c in criteria])
def test_adverse_change_never_reduces_score(criterion):
    response = sample()
    previous = score(response).score
    getattr(response, criterion.section)[criterion.key] = metric(criterion.high * criterion.direction, "fixture", 90, 90)
    assert score(response).score > previous


def test_coverage_renormalization_and_essential_group():
    response = sample()
    response.rainfall = {}
    result = score(response)
    assert result.coverage == .8 and result.status == "AVAILABLE"
    assert result.unavailable_groups == ["rainfall"]
    assert sum(f.effective_weight or 0 for f in result.factors) == pytest.approx(1)
    assert sum(f.contribution or 0 for f in result.factors) == result.score
    assert result.factors[-1].subscore is None
    response.operations.pop("failures_30d")
    assert score(response).score is None
    response = sample()
    response.groundwater = {}
    assert score(response).classification is None
    response = sample()
    response.groundwater["static_level_trend_30d"].status = "INSUFFICIENT_DATA"
    assert score(response).score is None
    assert score(None).reference_date is None


def test_history_excludes_future_measurements():
    records = [SimpleNamespace(measured_at=datetime.combine(END - timedelta(days=89-i), datetime.min.time(), timezone.utc), water_level_m=20+i*.01, dynamic_level_m=25+i*.02, flow_rate_m3_h=10-i*.01, runtime_hours=12, daily_demand_m3=100+i, pumped_volume_m3=120, utilization=.8, operational_failure=False, precipitation_mm=2) for i in range(90)]
    def response():
        return IndicatorResponse(entity_id=ID, reference_date=END, data_classification="SIMULATED", source="fixture", groundwater=groundwater_metrics(records, END), operations=operational_metrics(records, END), rainfall=rainfall_metrics(records, END))
    before = score(response())
    future = SimpleNamespace(**vars(records[-1]))
    future.measured_at += timedelta(days=1)
    future.water_level_m = 999999
    future.daily_demand_m3 = 999999
    future.operational_failure = True
    records.append(future)
    assert score(response()) == before
    assert before.reference_date == END


def test_api_contract_and_reference_forwarding(monkeypatch):
    from app.risk import service
    well = SimpleNamespace(id=ID, code="SIM-PI-001", data_classification="SIMULATED", source="fixture")
    db = SimpleNamespace(get=lambda model, id: well if id == ID else None)
    response = sample()
    seen = []
    def indicators(db, well, requested):
        seen.append(requested)
        return response.model_copy(update={"reference_date": requested or END})
    monkeypatch.setattr(service, "well_indicators", indicators)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        result = client.get(f"/api/v1/wells/{ID}/risk?reference_date=2026-08-01")
        assert result.status_code == 200
        assert result.json()["reference_date"] == "2026-08-01"
        assert seen == [date(2026, 8, 1)]
        assert result.json()["experimental"] is True
        assert client.get(f"/api/v1/wells/{ID}/risk?reference_date=invalid").status_code == 422
        assert client.get("/api/v1/wells/00000000-0000-0000-0000-000000000002/risk").status_code == 404
        response.groundwater = {}
        assert client.get(f"/api/v1/wells/{ID}/risk").json()["score"] is None
        monkeypatch.setattr(service, "well_indicators", lambda *args: None)
        assert client.get(f"/api/v1/wells/{ID}/risk").json()["status"] == "INSUFFICIENT_DATA"
    finally:
        app.dependency_overrides.clear()


def test_incompatible_sector_provenance_is_not_combined(monkeypatch):
    from app.risk import service
    response = sample()
    response.sector_id = ID
    monkeypatch.setattr(service, "well_indicators", lambda *args: response)
    db = SimpleNamespace(get=lambda *args: SimpleNamespace(data_classification="REAL", source="other"))
    well = SimpleNamespace(id=ID, code="SIM-PI-001", data_classification="SIMULATED", source="fixture")
    assert well_risk(db, well, END).unavailable_groups == ["rainfall"]


def test_small_scenario_comparison():
    from statistics import mean
    from app.simulation import SimulationConfig, generate_dataset
    from app.simulation.scenarios import Scenario
    summaries = {}
    for scenario in Scenario:
        dataset = generate_dataset(SimulationConfig(well_count=6, sector_count=2, days=180, scenario=scenario))
        end = date.fromisoformat(dataset.well_daily[-1]["date"])
        results = []
        for well in dataset.wells:
            operations = [SimpleNamespace(**row, measured_at=datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc)) for row in dataset.well_daily if row["well_id"] == well["well_id"]]
            groundwater = [SimpleNamespace(measured_at=row.measured_at, water_level_m=row.static_level_m, dynamic_level_m=row.dynamic_level_m) for row in operations]
            rain = [SimpleNamespace(**row, measured_at=datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc)) for row in dataset.sector_daily if row["sector_id"] == well["sector_id"]]
            response = IndicatorResponse(entity_id=ID, reference_date=end, data_classification="SIMULATED", source="fixture", groundwater=groundwater_metrics(groundwater, end), operations=operational_metrics(operations, end), rainfall=rainfall_metrics(rain, end))
            result = score(response)
            assert result.status == "AVAILABLE"
            assert 0 <= result.score <= 100
            results.append(result.score)
        summaries[scenario.value] = round(mean(results), 4)
    print("Scenario mean scores:", summaries)
