"""Normaliza o simulador nos mesmos schemas internos usados por qualquer origem."""
from datetime import datetime, timezone
from uuid import UUID, uuid5

from app.models import GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, ServiceSector, Well, WellSector
from app.schemas.domain import (
    GroundwaterMeasurementCreate, OperationalMeasurementCreate, RainfallMeasurementCreate,
    ServiceSectorCreate, WellCreate, WellSectorCreate,
)

from app.data_provenance import SIMULATION_SOURCE as SOURCE
NAMESPACE = UUID("d58d808d-32a8-48ba-b4b0-d942f11b5228")
PROVENANCE = {"source": SOURCE, "data_classification": "SIMULATED"}


def identifier(key):
    return uuid5(NAMESPACE, key)


def timestamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def normalized_batches(dataset):
    """Yield a model and validated rows; no synthetic persistence entities."""
    def record(schema, key, **values):
        parsed = schema(**PROVENANCE, **values)
        payload = parsed.model_dump(exclude={"is_synthetic"})
        payload["id"] = identifier(key)
        return payload

    sectors = {r["sector_id"]: r for r in dataset.sectors}
    yield ServiceSector, [record(ServiceSectorCreate, r["sector_id"], code=r["sector_id"], name=r["name"],
        description="Setor sintético de demonstração; não representa área real de atendimento.",
        boundary={"type": "MultiPolygon", "coordinates": [[[ [r["west"], r["south"]], [r["east"], r["south"]],
            [r["east"], r["north"]], [r["west"], r["north"]], [r["west"], r["south"]] ]]]}) for r in dataset.sectors]
    final = {r["well_id"]: r for r in dataset.well_daily}
    yield Well, [record(WellCreate, r["well_id"], code=r["well_id"], name=r["name"],
        municipality=dataset.config.region, state="PI", depth_m=r["depth_m"],
        is_active=not final[r["well_id"]]["operational_failure"],
        location={"type": "Point", "coordinates": [r["longitude"], r["latitude"]]}) for r in dataset.wells]
    # Fixed start for demo membership keeps its identity stable across historical windows.
    yield WellSector, [record(WellSectorCreate, "link:" + r["well_id"], well_id=identifier(r["well_id"]),
        sector_id=identifier(r["sector_id"]), valid_from=timestamp("1900-01-01")) for r in dataset.wells]
    yield RainfallMeasurement, [record(RainfallMeasurementCreate, "rain:" + r["sector_id"] + r["date"],
        service_sector_id=identifier(r["sector_id"]), measured_at=timestamp(r["date"]), precipitation_mm=r["precipitation_mm"],
        accumulation_minutes=1440, station_code=r["sector_id"],
        location={"type": "Point", "coordinates": [sectors[r["sector_id"]]["longitude"], sectors[r["sector_id"]]["latitude"]]}) for r in dataset.sector_daily]
    yield GroundwaterMeasurement, [record(GroundwaterMeasurementCreate, "gw:" + r["well_id"] + r["date"],
        well_id=identifier(r["well_id"]), measured_at=timestamp(r["date"]), water_level_m=r["static_level_m"],
        dynamic_level_m=r["dynamic_level_m"]) for r in dataset.well_daily]
    yield OperationalMeasurement, [record(OperationalMeasurementCreate, "op:" + r["well_id"] + r["date"],
        well_id=identifier(r["well_id"]), measured_at=timestamp(r["date"]), flow_rate_m3_h=r["flow_rate_m3_h"],
        pumped_volume_m3=r["pumped_volume_m3"], runtime_hours=r["runtime_hours"], daily_demand_m3=r["daily_demand_m3"],
        utilization=r["utilization"], operational_failure=r["operational_failure"], operating_status=r["operating_status"])
        for r in dataset.well_daily]
