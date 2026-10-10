from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.database import get_db
from app.main import app
from app.models import Well, GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, WellSector
from app.ingestion.siagas.transform import transform
from app.ingestion.siagas.load import load
from app.simulation import SimulationConfig, generate_dataset
from app.simulation.seed_database import seed_dataset
from test_simulation_database import db, pytestmark
from test_siagas import envelope
import pytest


def test_public_import_api_idempotence_and_synthetic_preservation(db, envelope):
    seed_dataset(db, generate_dataset(SimulationConfig(well_count=2, sector_count=1, days=60)))
    models = (GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, WellSector)
    before = {m.__tablename__: [tuple(str(getattr(r, c.key)) for c in m.__table__.columns) for r in db.scalars(select(m).order_by(m.id))] for m in models}
    synthetic = [(w.id, w.code, str(w.location), w.source, w.is_active) for w in db.scalars(select(Well).order_by(Well.id))]
    rows, _ = transform(envelope)
    assert load(db, rows) == dict(created=3, updated=0)
    assert load(db, rows) == dict(created=0, updated=3)
    assert db.scalar(select(func.count()).select_from(Well)) == 5
    for m in models:
        assert before[m.__tablename__] == [tuple(str(getattr(r, c.key)) for c in m.__table__.columns) for r in db.scalars(select(m).order_by(m.id))]
    assert synthetic == [(w.id, w.code, str(w.location), w.source, w.is_active) for w in db.scalars(select(Well).where(Well.data_classification == "SIMULATED").order_by(Well.id))]
    assert db.scalar(select(func.min(func.ST_SRID(Well.location))).where(Well.source == "SIAGAS")) == 4326
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            result = client.get("/api/v1/wells?source=SIAGAS&page_size=2").json()
            assert result["total"] == 3 and result["pages"] == 2
            assert all(w["source"] == "SIAGAS" and w["data_classification"] == "PUBLIC" and not w["is_synthetic"] and w["is_active"] is None for w in result["items"])
            assert client.get("/api/v1/wells?source=SIMULATED").json()["total"] == 2
            assert client.get("/api/v1/wells?source=SIAGAS&municipality=Teresina&q=9783").json()["total"] == 1
            assert client.get("/api/v1/wells?source=SIAGAS&is_active=false").json()["total"] == 0
            for row in rows:
                path = f"/api/v1/wells/{row['id']}"
                assert client.get(path).json()["source_record_id"] == row["source_record_id"]
                for query in ("", "?reference_date=2024-02-29"):
                    risk = client.get(path + "/risk" + query).json()
                    assert risk["status"] == "INSUFFICIENT_DATA" and risk["score"] is None and risk["classification"] is None
                assert client.get(f"/api/v1/measurements?well_id={row['id']}").json()["total"] == 0
            summary = client.get("/api/v1/dashboard/summary").json()
            assert summary["simulated_wells"] == 2 and summary["siagas_wells"] == 3 and summary["unknown_status_wells"] == 3
            assert summary["evaluable_wells"] == 2
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("source,classification", [("OTHER", "PUBLIC"), ("SIMULATED:AQUIFERO_VIVO", "SIMULATED"), ("SIAGAS", "REAL")])
def test_foreign_conflict_aborts_before_any_insert(db, envelope, source, classification):
    rows, _ = transform(envelope)
    load(db, rows[-1:])
    foreign = db.get(Well, rows[-1]["id"])
    foreign.source, foreign.data_classification = source, classification
    db.flush()
    with pytest.raises(ValueError, match="Conflito protegido"):
        load(db, rows)
    assert db.scalar(select(func.count()).select_from(Well)) == 1
    assert db.get(Well, foreign.id).source == source
