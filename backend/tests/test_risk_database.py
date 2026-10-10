"""Real PostGIS queries in the existing rollback-only fixture."""
from datetime import date
from fastapi.testclient import TestClient
from app.database import get_db
from app.main import app
from app.models import Well
from app.simulation import SimulationConfig, generate_dataset
from app.simulation.seed_database import seed_dataset
from sqlalchemy import select
from test_simulation_database import db, pytestmark


def test_risk_endpoint_with_real_historical_queries(db):
    dataset = generate_dataset(SimulationConfig(well_count=6, sector_count=2, days=90))
    seed_dataset(db, dataset)
    well = db.scalar(select(Well).order_by(Well.code))
    end = date.fromisoformat(dataset.well_daily[-1]["date"])
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        path = f"/api/v1/wells/{well.id}/risk"
        result = client.get(path, params={"reference_date": end.isoformat()})
        assert result.status_code == 200
        risk = result.json()
        assert risk["status"] == "AVAILABLE" and risk["coverage"] == 1
        assert risk["score"] == sum(f["contribution"] for f in risk["factors"])
        assert client.get(path).json() == risk
        first = dataset.well_daily[0]["date"]
        early = client.get(path, params={"reference_date": first}).json()
        assert early["reference_date"] == first
        assert early["score"] is None and early["classification"] is None
        assert early["coverage"] == 0
    finally:
        app.dependency_overrides.clear()
