import copy
from datetime import date
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import func, select
import pytest
from app.database import get_db
from app.main import app
from app.models import GroundwaterObservation, GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, Well, WellSector, ServiceSector
from app.ingestion.rimas.transform import transform
from app.ingestion.rimas.load import load
from app.ingestion.siagas.load import load as load_registry
from app.simulation import SimulationConfig, generate_dataset
from app.simulation.seed_database import seed_dataset
from test_simulation_database import db, pytestmark
from test_rimas import rimas


def snapshot(db, models):
    return {m.__tablename__: [tuple(str(getattr(r,c.key)) for c in m.__table__.columns) for r in db.scalars(select(m).order_by(m.id))] for m in models}


def test_public_history_pagination_risk_idempotence_and_preservation(db, rimas):
    seed_dataset(db, generate_dataset(SimulationConfig(well_count=2, sector_count=1, days=60)))
    well, rows, _ = transform(*rimas)
    load_registry(db, [well])
    models = (Well, ServiceSector, WellSector, GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement)
    before = snapshot(db, models)
    assert load(db, well, rows) == dict(created_wells=0, created_observations=5, unchanged_observations=0)
    original = snapshot(db, (GroundwaterObservation,))
    # Different extraction batch must not overwrite first-acquisition provenance.
    again = copy.deepcopy(rows)
    for row in again: row["source_metadata"]["batch"] = "repeat"
    assert load(db, well, again) == dict(created_wells=0, created_observations=0, unchanged_observations=5)
    assert snapshot(db, models) == before and snapshot(db, (GroundwaterObservation,)) == original
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/measurements?well_id={well['id']}&source=RIMAS&type=groundwater&page_size=2").json()
            assert response["total"] == 5 and response["pages"] == 3
            latest = response["items"][0]
            assert latest["measured_at"] == "2025-03-31T21:00:00" and latest["water_level_m"] is None
            assert latest["observed_level_m"] == "18.5900" and latest["unit"] == "m" and not latest["is_synthetic"]
            assert latest["flow_rate_m3_h"] is None and latest["source_metadata"]["eligible_for_indicators"] is False
            ids = []
            for page in range(1, 4):
                ids += [r["id"] for r in client.get(f"/api/v1/measurements?source=RIMAS&page_size=2&page={page}").json()["items"]]
            assert len(set(ids)) == 5
            for suffix in ("", "Z", "-03:00"):
                day = client.get(f"/api/v1/measurements?source=RIMAS&measured_from=2025-01-28T00:00:00{suffix}&measured_to=2025-01-28T23:59:59{suffix}").json()
                assert day["total"] == 2
            assert client.get("/api/v1/measurements?source=RIMAS&classification=SIMULATED").json()["total"] == 0
            assert client.get("/api/v1/measurements?source=RIMAS&type=operational").json()["total"] == 0
            assert client.get("/api/v1/wells?source=RIMAS").json()["total"] == 1
            assert client.get(f"/api/v1/wells/{well['id']}").json()["has_rimas_observations"] is True
            for query in ("", "?reference_date=2025-03-31"):
                risk = client.get(f"/api/v1/wells/{well['id']}/risk{query}").json()
                assert risk["status"] == "INSUFFICIENT_DATA" and risk["score"] is None
            summary = client.get("/api/v1/dashboard/summary").json()
            assert summary["rimas_observations"] == 5 and summary["evaluable_wells"] == 2
            assert summary["analysis_date"] == "2024-02-29"  # Synthetic clock; later RIMAS does not move it.
    finally: app.dependency_overrides.clear()


def test_new_registry_and_empty_export(db, rimas):
    well, rows, _ = transform(*rimas)
    assert load(db, well, []) == dict(created_wells=0, created_observations=0, unchanged_observations=0)
    assert db.scalar(select(func.count()).select_from(Well)) == 0
    assert load(db, well, rows)["created_wells"] == 1
    assert db.scalar(select(func.count()).select_from(WellSector)) == 0
    assert db.get(Well, well["id"]).is_active is None


def test_ambiguous_official_id_rejected(db, rimas):
    well, rows, _ = transform(*rimas)
    load_registry(db, [well])
    db.add(Well(id=uuid4(), code="OTHER-RETE", name="RETE", location=db.get(Well, well["id"]).location,
        source="OTHER", data_classification="PUBLIC", source_record_id=well["source_record_id"]))
    db.flush()
    with pytest.raises(ValueError, match="ambíguo"): load(db, well, rows)
    assert db.scalar(select(func.count()).select_from(GroundwaterObservation)) == 0


def test_conflicting_existing_observation_never_overwritten(db, rimas):
    well, rows, _ = transform(*rimas); load(db, well, rows)
    before = snapshot(db, (GroundwaterObservation, Well))
    changed = copy.deepcopy(rows); changed[0]["source_metadata"]["original_row"][4] = "1"
    with pytest.raises(ValueError, match="divergente"): load(db, well, changed)
    assert snapshot(db, (GroundwaterObservation, Well)) == before


@pytest.mark.parametrize("change", ["synthetic", "level", "time", "eligibility", "duplicate"])
def test_loader_preflight_before_creating_well(db, rimas, change):
    well, rows, _ = transform(*rimas)
    if change == "synthetic": rows[-1]["data_classification"] = "SIMULATED"
    if change == "level": rows[-1]["observed_level_m"] += 1
    if change == "time": rows[-1]["measured_at"] = rows[0]["measured_at"]
    if change == "eligibility": rows[-1]["source_metadata"]["eligible_for_indicators"] = True
    if change == "duplicate": rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(ValueError): load(db, well, rows)
    assert db.scalar(select(func.count()).select_from(Well)) == 0
