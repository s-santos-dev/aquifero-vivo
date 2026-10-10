"""Caller-owned transaction; exact SIAGAS identity and append-only observations."""
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import or_, select, text
from app.models import GroundwaterObservation, Well
from app.ingestion.siagas.load import load as load_registry
from .mappings import DATASET
from .validate import provenance, level


def signature(row):
    return (row["well_id"], row["measured_at"], row["observed_level_m"], row["unit"], row["source"],
        row["data_classification"], row["dataset"], row["station_code"], row["source_record_id"], row["pumping"],
        row["source_metadata"]["original_row"])


def load(session, well, records):
    station = well["source_record_id"]
    expected_well = uuid5(NAMESPACE_URL, "SIAGAS:"+station)
    if well["id"] != expected_well or well["source"] != "SIAGAS" or well["data_classification"] != "PUBLIC" or well["state"] != "PI":
        raise ValueError("Cadastro protegido/identidade inválida")
    seen = set()
    for row in records:
        meta = row["source_metadata"]
        provenance(meta)
        seq = row["source_record_id"]
        if (not seq.isdigit() or row["id"] != uuid5(NAMESPACE_URL, f"RIMAS:{DATASET}:{station}:{seq}")
            or row["well_id"] != expected_well or row["station_code"] != station or row["source"] != "RIMAS"
            or row["data_classification"] != "PUBLIC" or row["dataset"] != DATASET or row["unit"] != "m"
            or row["measured_at"].tzinfo is not None or meta.get("eligible_for_indicators") is not False
            or meta.get("timezone") != "UNKNOWN" or meta.get("level_reference") != "UNKNOWN"):
            raise ValueError("Observação/proveniência protegida")
        original = meta.get("original_row", [])
        if (len(original) not in (6, 7) or original[0] != seq
            or datetime.strptime(original[1]+" "+original[2], "%d/%m/%Y %H:%M") != row["measured_at"]
            or meta.get("original_datetime") != row["measured_at"].isoformat()
            or level(original[3]) != row["observed_level_m"] or original[5] not in ("", "N", "S")
            or (original[5] or None) != row["pumping"]):
            raise ValueError("Observação diverge do registro original")
        if row["id"] in seen:
            raise ValueError("Lote com identidade duplicada")
        seen.add(row["id"])
    session.execute(text("SELECT pg_advisory_xact_lock(71840262)"))
    matches = session.scalars(select(Well).where(or_(Well.id == expected_well,
        Well.code == "SIAGAS-"+station, Well.source_record_id == station)).with_for_update()).all()
    if len(matches) > 1 or any((w.id, w.source, w.data_classification, w.source_record_id, w.code) !=
        (expected_well, "SIAGAS", "PUBLIC", station, "SIAGAS-"+station) for w in matches):
        raise ValueError("Vínculo oficial ambíguo/protegido; nenhuma associação por nome/proximidade")
    pending, unchanged = [], 0
    # Preflight all collisions before inserting even the new catalog entry.
    for row in records:
        existing = session.scalars(select(GroundwaterObservation).where(or_(GroundwaterObservation.id == row["id"],
            (GroundwaterObservation.source == "RIMAS") & (GroundwaterObservation.dataset == DATASET)
            & (GroundwaterObservation.station_code == station) & (GroundwaterObservation.source_record_id == row["source_record_id"]))).with_for_update()).all()
        if existing:
            if len(existing) != 1 or existing[0].id != row["id"] or signature({k: getattr(existing[0], k) for k in row}) != signature(row):
                raise ValueError("Registro existente divergente; revisão oficial exige análise explícita")
            unchanged += 1
        else:
            pending.append(row)
    if not records:
        return dict(created_wells=0, created_observations=0, unchanged_observations=0)
    if not matches:
        load_registry(session, [well])
    session.add_all(GroundwaterObservation(**row) for row in pending)
    session.flush()
    return dict(created_wells=int(not matches), created_observations=len(pending), unchanged_observations=unchanged)
