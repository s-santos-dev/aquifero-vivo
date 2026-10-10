"""Transactional, source-protected PostgreSQL upsert of validated wells only."""
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from app.models import Well
from app.schemas.domain import WellCreate
from .mappings import SOURCE
from .validate import coordinates
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5


def load(session, records):
    # Validate the entire batch before touching persistence. Caller owns commit.
    rows, ids = [], set()
    for record in records:
        if record["source"] != SOURCE or record["data_classification"] != "PUBLIC" or not record["source_record_id"] or record["is_active"] is not None:
            raise ValueError("Proveniência/status inválido")
        if record["source_record_id"] in ids:
            raise ValueError("Lote com duplicatas")
        official_id = record["source_record_id"]
        if not official_id.isdigit() or record["id"] != uuid5(NAMESPACE_URL, "SIAGAS:" + official_id) or record["code"] != "SIAGAS-" + official_id:
            raise ValueError("Identidade SIAGAS inválida")
        metadata = record.get("source_metadata") or {}
        if not metadata.get("batch") or not metadata.get("source_url") or datetime.fromisoformat(metadata.get("extracted_at", "")).tzinfo is None:
            raise ValueError("Proveniência de extração incompleta")
        ids.add(record["source_record_id"])
        row = dict(record)
        lon, lat = row.pop("longitude"), row.pop("latitude")
        coordinates(lon, lat, state=row["state"])
        WellCreate(**row, location={"type": "Point", "coordinates": [lon, lat]})
        row["location"] = WKTElement(f"POINT({lon} {lat})", srid=4326)
        rows.append(row)
    session.execute(text("SELECT pg_advisory_xact_lock(71840262)"))
    for row in rows:
        conflicts = session.scalars(select(Well).where(or_(Well.id == row["id"], Well.code == row["code"], (Well.source == SOURCE) & (Well.source_record_id == row["source_record_id"]))).with_for_update()).all()
        if any((w.source, w.data_classification, w.source_record_id, w.id, w.code) != (SOURCE, "PUBLIC", row["source_record_id"], row["id"], row["code"]) for w in conflicts):
            raise ValueError(f"Conflito protegido: {row['code']}")
    created = updated = 0
    for row in rows:
        exists = session.get(Well, row["id"]) is not None
        statement = insert(Well).values(**row)
        updates = {k: getattr(statement.excluded, k) for k in row if k not in ("id", "source", "source_record_id", "code")}
        updates["updated_at"] = func.now()
        result = session.execute(statement.on_conflict_do_update(index_elements=[Well.source, Well.source_record_id], set_=updates, where=(Well.data_classification == "PUBLIC") & (Well.source == SOURCE) & (Well.id == row["id"]) & (Well.code == row["code"])).returning(Well.id)).scalar_one_or_none()
        if result is None:
            raise ValueError("Conflito de proveniência durante upsert")
        created += not exists
        updated += exists
    session.flush()
    session.expire_all()
    return dict(created=created, updated=updated)
