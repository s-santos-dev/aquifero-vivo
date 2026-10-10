"""Validate again, preflight revisions, then append under protected-data snapshots."""
import hashlib
import json
from geoalchemy2.elements import WKTElement
from sqlalchemy import select, text, func
from app.models import ClimateStation, RainfallObservation
from .transform import transform

PROTECTED_TABLES = ("wells", "service_sectors", "well_sectors", "groundwater_measurements", "operational_measurements", "rainfall_measurements", "groundwater_observations", "risk_assessments", "risk_factors", "alerts")


def snapshot(session):
    result = {}
    for table in PROTECTED_TABLES:
        digest, count = hashlib.sha256(), 0
        for row in session.execute(text(f'SELECT row_to_json(t)::text FROM (SELECT * FROM "{table}" ORDER BY id) t')):
            digest.update(row[0].encode("utf8") + b"\n")
            count += 1
        result[table] = dict(count=count, sha256=digest.hexdigest())
    return result


def signature(row):
    return tuple(getattr(row, k) for k in ("station_id", "measured_at", "value_mm", "unit", "source", "availability")) + (row.source_metadata["original_row"],)


def load(session, content, meta):
    station, records, report = transform(content, meta)
    if report["rejected"] or not report["observed"]:
        raise ValueError("Lote com rejeições ou sem observações válidas")
    # Same locks as previous public and synthetic loaders, in fixed order.
    for lock in (71840261,71840262):
        session.execute(text(f"SELECT pg_advisory_xact_lock({lock})"))
    before = snapshot(session)
    old_station = session.scalar(select(ClimateStation).where(ClimateStation.official_code==station["official_code"], ClimateStation.source=="INMET"))
    if old_station:
        lon, lat = session.execute(select(func.ST_X(ClimateStation.location),func.ST_Y(ClimateStation.location)).where(ClimateStation.id==old_station.id)).one()
        if (old_station.id,old_station.name,old_station.observation_type,lon,lat,old_station.source_metadata["original_header"]) != (station["id"],station["name"],station["observation_type"],station["longitude"],station["latitude"],station["source_metadata"]["original_header"]):
            raise ValueError("Cadastro climático divergente")
    existing = {r.measured_at:r for r in session.scalars(select(RainfallObservation).where(RainfallObservation.station_id==station["id"], RainfallObservation.measured_at>=records[0]["measured_at"], RainfallObservation.measured_at<=records[-1]["measured_at"]))}
    additions = []
    for row in records:
        old = existing.get(row["measured_at"])
        expected = tuple(row[k] for k in ("station_id","measured_at","value_mm","unit","source","availability")) + (row["source_metadata"]["original_row"],)
        if old and (signature(old)!=expected or old.id!=row["id"]):
            raise ValueError("Observação existente divergente; revisão requer análise explícita")
        if not old:
            additions.append(row)
    if not old_station:
        lon,lat = station.pop("longitude"),station.pop("latitude")
        session.add(ClimateStation(**station,location=WKTElement(f"POINT({lon} {lat})",srid=4326)))
        session.flush()
    session.add_all(RainfallObservation(**r) for r in additions)
    session.flush()
    after = snapshot(session)
    if before != after:
        raise ValueError("Integridade dos dados anteriores alterada; carga deve ser revertida")
    return dict(created_stations=int(not old_station),created_observations=len(additions),unchanged_observations=len(records)-len(additions),
        preserved=True,before=before,after=after)
