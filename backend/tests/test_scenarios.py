from types import SimpleNamespace
from uuid import uuid4
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.database import get_db
from app.main import app
from app.indicators.calculation import metric
from app.scenarios.assumptions import apply
from app.scenarios.schemas import SimulationRequest, Parameters
from app.scenarios.simulator import simulate
from app.scenarios.service import simulate_well
from test_risk import sample, ID, END

WELL = SimpleNamespace(id=ID, code="SIM-PI-001", data_classification="SIMULATED", source="fixture")


def inputs():
    result = sample()
    result.rainfall.update(rainfall_30d=metric(60, "mm", 30, 30), rainfall_avg_previous_30d=metric(4, "mm/dia", 30, 30), recent_rainfall_deficit_30d=metric(.5, "fração", 60, 60))
    for key, value in {"demand_avg_30d": 120, "demand_pressure_30d": .2, "pumping_hours_avg_30d": 12, "utilization_avg_30d": .6, "pumped_volume_avg_30d": 120}.items():
        result.operations[key] = metric(value, "fixture", 60, 60)
    return result


def run(data=None, **kwargs):
    return simulate(data if data is not None else inputs(), WELL, SimulationRequest(well_id=ID, **kwargs))


def test_zero_identity_determinism_and_no_mutation():
    data = inputs()
    snapshot = data.model_dump()
    response = run(data)
    assert all(r.risk == response.baseline and r.indicators == data and r.delta_points == 0 for r in response.results)
    request = dict(rainfall_change_pct=-60, demand_change_pct=30, pumping_change_pct=100)
    assert run(data, **request) == run(data, **request)
    assert data.model_dump() == snapshot


def test_scenario_recommendations_reuse_evidence_rules():
    from app.risk.recommendations import recommendations
    response = run(rainfall_change_pct=-30, demand_change_pct=20, pumping_change_pct=10)
    for result in response.results:
        assert result.recommendations == recommendations(result.risk)
        inputs_by_name = {i.indicator: i for f in result.risk.factors for i in f.indicators}
        for suggestion in result.recommendations:
            for evidence in suggestion.evidence:
                assert evidence == inputs_by_name[evidence.indicator]
    assert 'DEMAND_PRESSURE' in [r.rule_id for r in response.results[-1].recommendations]


@pytest.mark.parametrize("key", list(Parameters.model_fields))
@pytest.mark.parametrize("value", [-101, 101, float("nan"), float("inf")])
def test_parameter_limits(key, value):
    with pytest.raises(ValidationError):
        SimulationRequest(well_id=ID, **{key: value})


@pytest.mark.parametrize("horizons", [[], [30, 30], [1], [30, 60, 90, 90]])
def test_invalid_horizons(horizons):
    with pytest.raises(ValidationError):
        SimulationRequest(well_id=ID, horizons=horizons)


def test_formulas_progression_comparison_explanations_and_origin():
    response = run(rainfall_change_pct=-60, demand_change_pct=30, pumping_change_pct=100)
    for result, fraction in zip(response.results, [1 / 3, 2 / 3, 1]):
        assert result.applied_parameters.rainfall_change_pct == pytest.approx(-60 * fraction)
        assert result.indicators.rainfall["rainfall_30d"].value == pytest.approx(60 * (1 - .6 * fraction))
        assert result.indicators.rainfall["recent_rainfall_deficit_30d"].value == pytest.approx(1 - 60 * (1 - .6 * fraction) / 120)
        assert result.indicators.operations["demand_pressure_30d"].value == pytest.approx(1.2 * (1 + .3 * fraction) - 1)
        assert result.delta_points == pytest.approx(result.risk.score - response.baseline.score)
        assert result.delta_pct == pytest.approx(result.delta_points / response.baseline.score * 100)
        assert sum(f.contribution_delta for f in result.factors) == pytest.approx(result.delta_points)
        assert result.risk.reference_date == END
        assert (result.risk.source, result.risk.data_classification) == (WELL.source, WELL.data_classification)
        assert 0 <= result.risk.score <= 100
        for factor in result.factors:
            assert factor.delta_points == pytest.approx(result.risk.subscores[factor.group] - response.baseline.subscores[factor.group])
            assert ("aumentou" if factor.delta_points > 1e-9 else "permaneceu estável") in factor.explanation
    assert response.results[-1].indicators.groundwater == inputs().groundwater
    assert response.results[-1].indicators.operations["flow_trend_30d"] == inputs().operations["flow_trend_30d"]


@pytest.mark.parametrize("key,group,values", [("demand_change_pct", "demand", [-100, -30, 0, 30, 100]), ("pumping_change_pct", "pumping", [-100, -30, 0, 30, 100]), ("rainfall_change_pct", "rainfall", [100, 30, 0, -30, -100])])
def test_monotonicity(key, group, values):
    scores = [run(**{key: v}).results[-1].risk.subscores[group] for v in values]
    assert scores == sorted(scores)


def test_nonnegative_hours_cap_and_saturation():
    for percentage in [-100, 100]:
        data, warnings = apply(inputs(), Parameters(rainfall_change_pct=percentage, demand_change_pct=percentage, pumping_change_pct=percentage))
        for section, keys in [("rainfall", ["rainfall_30d"]), ("operations", ["demand_avg_30d", "pumped_volume_avg_30d", "utilization_avg_30d"])]:
            assert all(getattr(data, section)[key].value >= 0 for key in keys)
        assert 0 <= data.operations["pumping_hours_avg_30d"].value <= 24
    data = inputs()
    data.operations["pumping_hours_avg_30d"].value = 24
    data.operations["utilization_avg_30d"].value = 1
    response = run(data, pumping_change_pct=100)
    assert response.results[-1].risk.subscores["pumping"] == response.baseline.subscores["pumping"] == 100
    assert response.results[-1].warnings


def test_rainfall_uses_unclipped_window_ratio_and_subset_keeps_90_day_anchor():
    data = inputs()
    data.rainfall["rainfall_30d"].value = 180
    data.rainfall["recent_rainfall_deficit_30d"].value = 0
    mild = run(data, rainfall_change_pct=-20).results[-1]
    assert mild.risk.subscores["rainfall"] == 0  # 144 remains above previous 120.
    severe = run(data, rainfall_change_pct=-60).results[-1]
    assert severe.indicators.rainfall["recent_rainfall_deficit_30d"].value == pytest.approx(.4)
    subset = run(data, rainfall_change_pct=-60, horizons=[30])
    assert subset.results[0].applied_parameters.rainfall_change_pct == -20
    assert severe.indicators.operations == data.operations


def test_missing_demand_is_not_fabricated_and_other_groups_stay_fixed():
    data = inputs()
    data.operations["demand_pressure_30d"] = metric(None, "fração", 12, 60)
    result = run(data, demand_change_pct=100)
    assert result.results[-1].risk.subscores["demand"] is None
    assert result.results[-1].indicators.rainfall == data.rainfall
    assert result.results[-1].indicators.groundwater == data.groundwater
    for key in ["pumping_hours_avg_30d", "utilization_avg_30d", "flow_trend_30d", "failures_30d"]:
        assert result.results[-1].indicators.operations[key] == data.operations[key]


def test_missing_data_and_zero_denominator():
    response = simulate(None, WELL, SimulationRequest(well_id=ID, demand_change_pct=10))
    assert response.baseline.score is None
    assert all(r.risk.score is None and r.delta_points is None for r in response.results)
    data = inputs()
    data.groundwater = {}
    assert run(data).results[0].risk.status == "INSUFFICIENT_DATA"
    data.rainfall["rainfall_avg_previous_30d"].value = 0
    transformed, warnings = apply(data, Parameters(rainfall_change_pct=-30))
    assert transformed.rainfall["recent_rainfall_deficit_30d"].value is None
    assert warnings
    data = inputs()
    for group in (data.groundwater, data.operations, data.rainfall):
        for item in group.values():
            item.value = 0
    response = run(data)
    assert response.baseline.score == 0
    assert response.results[0].delta_pct is None


def test_service_reference_origin_and_no_writes(monkeypatch):
    from app.risk import service
    data = inputs()
    seen = []
    monkeypatch.setattr(service, "well_indicators", lambda db, well, ref: seen.append(ref) or data)
    db = SimpleNamespace()
    result = simulate_well(db, WELL, SimulationRequest(well_id=ID, reference_date=END))
    assert seen == [END] and result.baseline.reference_date == END
    data.sector_id = uuid4()
    db.get = lambda *args: SimpleNamespace(data_classification="REAL", source="other")
    result = simulate_well(db, WELL, SimulationRequest(well_id=ID, rainfall_change_pct=-30))
    assert "rainfall" in result.baseline.unavailable_groups
    assert data.rainfall


def test_api_validation_not_found_and_cors(monkeypatch):
    from app.risk import service
    monkeypatch.setattr(service, "well_indicators", lambda *args: inputs())
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(get=lambda model, id: WELL if id == ID else None)
    try:
        client = TestClient(app)
        path = "/api/v1/scenarios/simulate"
        payload = {"well_id": str(ID), "reference_date": END.isoformat(), "rainfall_change_pct": -20}
        response = client.post(path, json=payload)
        assert response.status_code == 200
        assert response.json()["nature"] == "HYPOTHETICAL_SENSITIVITY"
        from app.risk.recommendations import recommendations
        from app.schemas.risk import RiskResponse
        for result in response.json()['results']:
            assert result['recommendations'] == [r.model_dump(mode='json') for r in recommendations(RiskResponse(**result['risk']))]
        assert client.post(path, json={**payload, "well_id": str(uuid4())}).status_code == 404
        for invalid in [{"demand_change_pct": 101}, {"reference_date": "oops"}, {"horizons": [30, 30]}, {"extra": 1}]:
            assert client.post(path, json={**payload, **invalid}).status_code == 422
        assert client.get("/api/v1/scenarios/config").json()["presets"]["favorable"]["demand_change_pct"] < 0
        preflight = client.options(path, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        assert preflight.status_code == 200
        assert "POST" in preflight.headers["access-control-allow-methods"]
    finally:
        app.dependency_overrides.clear()
