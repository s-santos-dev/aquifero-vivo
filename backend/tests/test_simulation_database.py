"""PostGIS integration: isolated transaction/schema, rolled back after every test."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.main import app
from app.models import GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, Well, ServiceSector, WellSector
from app.simulation import SimulationConfig, generate_dataset
from app.simulation.normalize import SOURCE, identifier, timestamp
from app.simulation.seed_database import seed_dataset

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGIS_TESTS") != "1", reason="Use RUN_POSTGIS_TESTS=1 with migrated PostGIS")


@pytest.fixture
def db():
    with engine.connect() as connection:
        transaction = connection.begin()
        schema = "test_sim_" + uuid4().hex
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        Base.metadata.create_all(connection, checkfirst=False)
        with Session(bind=connection) as session:
            yield session
        transaction.rollback()


@pytest.fixture
def dataset():
    return generate_dataset(SimulationConfig(well_count=6, sector_count=2, days=5))


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_postgis_relationships_api_and_reseed(db, dataset):
    first = seed_dataset(db, dataset)
    assert first == seed_dataset(db, dataset)
    assert count(db, Well) == 6
    assert count(db, ServiceSector) == 2
    assert count(db, WellSector) == 6
    assert count(db, GroundwaterMeasurement) == count(db, OperationalMeasurement) == 30
    assert count(db, RainfallMeasurement) == 10
    assert db.scalar(select(func.count()).select_from(Well).join(WellSector).join(ServiceSector)) == 6
    assert db.scalar(select(func.bool_and(func.ST_Covers(ServiceSector.boundary, Well.location))).select_from(Well).join(WellSector).join(ServiceSector))
    assert db.scalar(select(func.bool_and(func.ST_IsValid(ServiceSector.boundary))))
    assert db.scalar(select(func.min(func.ST_SRID(Well.location)))) == 4326
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            wells = client.get("/api/v1/wells", params={"page_size": 100}).json()
            assert wells["total"] == 6
            assert all(w["is_synthetic"] and w["source"] == SOURCE for w in wells["items"])
            well_id = wells["items"][0]["id"]
            assert client.get(f"/api/v1/wells/{well_id}").json()["code"].startswith("SIM-PI-")
            sectors = client.get("/api/v1/sectors").json()
            assert sectors["total"] == 2
            assert client.get("/api/v1/sectors/" + sectors["items"][0]["id"]).status_code == 200
            filtered = client.get("/api/v1/wells", params={"sector_id": sectors["items"][0]["id"]}).json()
            assert filtered["total"] == 3
            for kind, total in (("groundwater", 30), ("operational", 30), ("rainfall", 10)):
                response = client.get("/api/v1/measurements", params={"type": kind, "classification": "SIMULATED"})
                assert response.status_code == 200, response.text
                result = response.json()
                assert result["total"] == total
                assert all(r["is_synthetic"] for r in result["items"])
                if kind == "groundwater":
                    assert result["items"][0]["dynamic_level_m"] is not None
                if kind == "operational":
                    assert result["items"][0]["daily_demand_m3"] is not None
            assert client.get("/api/v1/measurements").json()["total"] == 70
    finally:
        app.dependency_overrides.clear()


def test_indicator_routes_respect_historical_cutoff(db, dataset):
    seed_dataset(db, dataset)
    well_id = identifier(dataset.wells[0]["well_id"])
    sector_id = identifier(dataset.sectors[0]["sector_id"])
    reference = dataset.well_daily[2]["date"]
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            path = f"/api/v1/wells/{well_id}/indicators"
            before = client.get(path, params={"reference_date": reference})
            assert before.status_code == 200, before.text
            payload = before.json()
            assert payload["reference_date"] == reference
            assert payload["groundwater"]["current_static_level"]["status"] == "AVAILABLE"
            assert payload["rainfall"]["rainfall_30d"]["status"] == "INSUFFICIENT_DATA"
            assert payload["data_classification"] == "SIMULATED"
            future = GroundwaterMeasurement(well_id=well_id, measured_at=timestamp("2099-01-01"),
                                            water_level_m=999, dynamic_level_m=999,
                                            data_classification="SIMULATED", source=SOURCE)
            db.add(future)
            db.add(GroundwaterMeasurement(well_id=well_id, measured_at=timestamp(reference),
                                          water_level_m=999, dynamic_level_m=999,
                                          data_classification="PUBLIC", source="OTHER_SOURCE"))
            db.flush()
            assert client.get(path, params={"reference_date": reference}).json() == payload
            sector = client.get(f"/api/v1/sectors/{sector_id}/indicators", params={"reference_date": reference})
            assert sector.status_code == 200, sector.text
            assert sector.json()["aggregation"]["well_count"]["value"] == 3
            assert client.get(path, params={"reference_date": "not-a-date"}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_reset_preserves_public_real_unknown_and_foreign_simulations(db, dataset):
    seed_dataset(db, dataset)
    well = db.get(Well, identifier(dataset.wells[0]["well_id"]))
    sector = db.get(ServiceSector, identifier(dataset.sectors[0]["sector_id"]))
    ids = []
    for classification, source in (("PUBLIC", SOURCE), ("REAL", "TEST"), ("SIMULATED", "OTHER_SIMULATOR")):
        gw = GroundwaterMeasurement(well_id=well.id, measured_at=timestamp("2020-01-01"), water_level_m=10,
            data_classification=classification, source=source)
        rain = RainfallMeasurement(service_sector_id=sector.id, measured_at=timestamp("2020-01-01"), precipitation_mm=2,
            data_classification=classification, source=source, location=WKTElement("POINT(-42.8 -5.1)", srid=4326))
        db.add_all([gw, rain]); db.flush()
        ids.append((gw.id, rain.id))
    for classification in ("PUBLIC", "REAL", "UNKNOWN"):
        db.add(Well(code="TEST-" + classification, name="Fixture", data_classification=classification,
                    location=WKTElement("POINT(-42.8 -5.1)", srid=4326)))
    db.flush()
    seed_dataset(db, dataset, reset=True)
    db.expire_all()
    assert count(db, Well) == 9
    assert count(db, GroundwaterMeasurement) == 33
    assert count(db, RainfallMeasurement) == 13
    for groundwater_id, rain_id in ids:
        assert db.get(GroundwaterMeasurement, groundwater_id) is not None
        assert db.get(RainfallMeasurement, rain_id).service_sector_id == sector.id


def test_foreign_provenance_collision_aborts_and_rolls_back_reset(db, dataset):
    seed_dataset(db, dataset)
    well = db.get(Well, identifier(dataset.wells[0]["well_id"]))
    well.data_classification = "PUBLIC"
    db.flush()
    with pytest.raises(ValueError, match="Colisão"):
        with db.begin_nested():
            seed_dataset(db, dataset, reset=True)
    db.expire_all()
    assert well.data_classification == "PUBLIC"
    assert count(db, GroundwaterMeasurement) == 30


def test_foreign_code_collision_is_atomic(db, dataset):
    from sqlalchemy.exc import IntegrityError
    public = Well(code=dataset.wells[0]["well_id"], name="PUBLIC fixture",
                  data_classification="PUBLIC", source="TEST",
                  location=WKTElement("POINT(-42.8 -5.1)", srid=4326))
    db.add(public)
    db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            seed_dataset(db, dataset)
    assert count(db, Well) == 1
    assert count(db, ServiceSector) == 0
    assert db.get(Well, public.id).data_classification == "PUBLIC"


def test_reset_prunes_only_obsolete_simulator_wells_without_foreign_references(db, dataset):
    seed_dataset(db, dataset)
    retained = db.get(Well, identifier(dataset.wells[-1]["well_id"]))
    db.add(
        GroundwaterMeasurement(
            well_id=retained.id,
            measured_at=timestamp("2020-01-01"),
            water_level_m=10,
            data_classification="PUBLIC",
            source="TEST",
        )
    )
    db.flush()
    reduced = generate_dataset(SimulationConfig(well_count=4, sector_count=2, days=5))
    seed_dataset(db, reduced, reset=True)
    db.expire_all()
    assert count(db, Well) == 5
    assert db.get(Well, retained.id) is not None
    assert count(db, GroundwaterMeasurement) == 21
