from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import event, select, func
from app.database import get_db
from app.main import app
from app.models import Well, Alert
from app.risk.territorial import assessments
from app.risk.service import well_risk
from app.simulation import SimulationConfig, generate_dataset
from app.simulation.seed_database import seed_dataset
from test_simulation_database import db, pytestmark


def test_batch_equivalence_bounded_queries_temporal_and_read_only(db):
    dataset = generate_dataset(SimulationConfig(well_count=6, sector_count=2, days=90))
    seed_dataset(db, dataset)
    day = date.fromisoformat(dataset.well_daily[-1]['date'])
    calls = []
    connection = db.connection()
    def record(conn, cursor, statement, parameters, context, executemany):
        calls.append(statement)
    event.listen(connection, 'before_cursor_execute', record)
    try:
        items, actual = assessments(db)
        assert len(calls) == 8  # catalog, 2 clocks, sectors, links, 3 measurement batches
        assert actual == day and len(items) == 6
    finally:
        event.remove(connection, 'before_cursor_execute', record)
    for item in items:
        risk = well_risk(db, db.get(Well, item.well_id), day)
        assert item.score == risk.score and item.factors == risk.factors
        assert item.reference_date == day and item.data_classification == 'SIMULATED'
    first = date.fromisoformat(dataset.well_daily[0]['date'])
    early, _ = assessments(db, first)
    assert all(item.score is None and item.reference_date == first for item in early)
    assert assessments(db, day)[0] == items
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        path = f'/api/v1/wells/{items[0].well_id}/recommendations'
        assert client.get(path).status_code == 200
        assert client.get('/api/v1/wells/00000000-0000-0000-0000-000000000000/recommendations').status_code == 404
        alerts = client.get('/api/v1/alerts', params={'reference_date': first}).json()
        assert alerts == client.get('/api/v1/alerts', params={'reference_date': first}).json()
        assert alerts['total'] == 6
        assert db.scalar(select(func.count()).select_from(Alert)) == 0
        sector_id = str(items[0].sector_id)
        result = client.get('/api/v1/risks/wells', params={'sector_id': sector_id, 'page_size': 2}).json()
        assert result['total'] == 3 and len(result['items']) == 2
    finally:
        app.dependency_overrides.clear()
