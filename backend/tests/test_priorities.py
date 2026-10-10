from copy import deepcopy
from uuid import UUID
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.schemas.priority import PriorityWell
from app.risk.territorial import key, filtered, alerts
from app.risk.recommendations import recommendations
from test_risk import sample, score, END


def priority(value=70, code='SIM-001'):
    risk = score(sample()).model_copy(update={'score': value, 'classification': 'HIGH' if value else 'NORMAL'})
    return PriorityWell(**risk.model_dump(), municipality='Teste', sector_id=None, sector_code=None, sector_name=None, recommendations=recommendations(risk)).model_copy(update={'well_code': code})


def test_ranking_filters_and_stable_ties():
    low = priority(30)
    low.classification = 'NORMAL'
    high = priority(70)
    other = priority(70, 'SIM-002')
    missing = priority().model_copy(update={'score': None, 'classification': None, 'status': 'INSUFFICIENT_DATA'})
    assert sorted([missing, other, low, high], key=key) == [high, other, low, missing]
    assert filtered([low, high, missing], 'INSUFFICIENT_DATA') == [missing]
    assert filtered([high], municipality='teste') == [high]
    assert filtered([high], sector_id=UUID(int=9)) == []


def test_alerts_deterministic_and_separate_quality():
    high = priority()
    missing = priority().model_copy(update={'score': None, 'classification': None, 'status': 'INSUFFICIENT_DATA'})
    result = alerts([high, missing, priority(0)])
    assert result == alerts([high, missing, priority(0)])
    assert len(set(a.id for a in result)) == 2
    assert [a.kind for a in result] == ['INVESTIGATION', 'DATA_QUALITY']


def test_recommendations_require_available_evidence():
    response = sample()
    assert recommendations(score(response)) == []
    inputs = [('groundwater', 'static_level_trend_30d', .05, 'STATIC_TREND'), ('rainfall', 'recent_rainfall_deficit_30d', .5, 'RAINFALL_DEFICIT'), ('operations', 'pumping_hours_avg_30d', 20, 'PUMPING_LOAD'), ('operations', 'demand_pressure_30d', .3, 'DEMAND_PRESSURE'), ('operations', 'failures_30d', 1, 'RECENT_FAILURES')]
    for section, indicator, value, rule in inputs:
        changed = deepcopy(response)
        item = getattr(changed, section)[indicator]
        item.value = value
        suggestions = recommendations(score(changed))
        assert [r.rule_id for r in suggestions] == [rule]
        assert suggestions[0].evidence[0].value == value
        item.status = 'INSUFFICIENT_DATA'
        assert rule not in [r.rule_id for r in recommendations(score(changed))]
    assert recommendations(score(None))[0].rule_id == 'DATA_COVERAGE'


def test_collection_contract_pagination_reference_and_validation(monkeypatch):
    from app.api import v1
    items = [priority(70, f'SIM-{i}') for i in range(3)]
    seen = []
    def batch(db, requested):
        seen.append(requested)
        return items, requested or END
    monkeypatch.setattr(v1, 'assessments', batch)
    app.dependency_overrides[get_db] = lambda: object()
    try:
        client = TestClient(app)
        result = client.get('/api/v1/risks/wells?reference_date=2026-09-20&page=2&page_size=2').json()
        assert result['total'] == 3 and result['pages'] == 2
        assert len(result['items']) == 1 and result['reference_date'] == END.isoformat()
        assert result['high_priority'] == 3
        assert seen == [END]
        assert client.get('/api/v1/alerts').json()['total'] == 3
        assert client.get('/api/v1/risks/wells?classification=INVALID').status_code == 422
        assert client.get('/api/v1/alerts?page_size=101').status_code == 422
        assert client.get('/api/v1/alerts?reference_date=invalid').status_code == 422
    finally:
        app.dependency_overrides.clear()
