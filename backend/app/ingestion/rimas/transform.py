import csv
import hashlib
import io
import unicodedata
from collections import Counter
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from app.ingestion.siagas.transform import transform as registry_transform
from .mappings import DATASET, HEADERS, MAX_BYTES, MAX_ROWS
from .validate import selection, provenance, level


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.strip()) if not unicodedata.combining(c))


def transform(content, meta):
    provenance(meta)
    start, end = selection(meta["station"], meta["start"], meta["end"])
    if len(content) > MAX_BYTES or hashlib.sha256(content).hexdigest() != meta["raw_sha256"]:
        raise ValueError("Checksum/tamanho bruto inválido")
    if meta.get("unit") != "m" or meta.get("timezone") != "UNKNOWN" or meta.get("level_reference") != "UNKNOWN":
        raise ValueError("Contrato de unidade/referência/fuso não verificado")
    # Official download uses single-byte Western encoding; UTF-8 files also supported.
    try: decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError: decoded = content.decode("cp1252")
    rows = list(csv.reader(io.StringIO(decoded), delimiter=";"))
    if len(rows) < 3 or rows[0] != ["Id Ponto:", meta["station"]] or rows[1][0] != "Consulta em:":
        raise ValueError("Identidade/cabeçalho do CSV oficial inválido")
    if [normalize(v) for v in rows[2][:6]] != HEADERS:
        raise ValueError("Contrato CSV mudou; revise mapeamento")
    registry = meta["registry"]
    features = registry.get("features", [])
    if len(features) != 1 or str(features[0].get("attributes", {}).get("idt_ponto")) != meta["station"] or features[0]["attributes"].get("status_rimas") != "Rimas":
        raise ValueError("Cadastro RIMAS ausente/ambíguo; identidade exata exigida")
    wells, report = registry_transform(dict(source_url=meta["registry_url"], extracted_at=meta["extracted_at"], batch=meta["batch"], selection=dict(state="PI", limit=1), pages=[registry]))
    if len(wells) != 1:
        raise ValueError(f"Cadastro não validado no Piauí: {report['rejected']}")
    original = [r for r in rows[3:] if any(v.strip() for v in r)]
    if len(original) > MAX_ROWS:
        raise ValueError("Quantidade excede limite do piloto")
    # Conflicting repeated IDs are all rejected, regardless of input ordering.
    groups = {}
    for row in original: groups.setdefault(row[0], set()).add(tuple(row))
    accepted, rejected, duplicates, seen = [], [], [], set()
    for position, row in enumerate(original, start=4):
        seq = row[0]
        try:
            if len(row) not in (6, 7) or (len(row) == 7 and row[6]):
                raise ValueError("Número de campos inválido")
            if not seq.isdigit() or len(seq) > 64:
                raise ValueError("Sequência original ausente/inválida")
            if len(groups[seq]) > 1:
                raise ValueError("Sequência repetida com conteúdo conflitante")
            when = datetime.strptime(row[1] + " " + row[2], "%d/%m/%Y %H:%M")
            if not start <= when.date() <= end:
                raise ValueError("Data fora do período solicitado")
            val = level(row[3])
            if row[5] not in ("N", "S", ""):
                raise ValueError("Marcador de bombeamento não reconhecido")
            if seq in seen:
                duplicates.append(dict(row=position, source_record_id=seq)); continue
            seen.add(seq)
            metadata = {k: meta[k] for k in ("source_url", "registry_url", "extracted_at", "batch", "raw_sha256", "unit_evidence", "timezone", "level_reference", "treatment")}
            metadata.update(original_date=row[1], original_time=row[2], original_datetime=when.isoformat(),
                original_value=row[3], original_flow=row[4], original_pumping=row[5], original_row=row,
                portal_query_time=rows[1][1], quality_status="NOT_PROVIDED", eligible_for_indicators=False,
                timestamp_semantics="ORIGINAL_WALL_CLOCK", level_semantics="UNVERIFIED_REFERENCE")
            accepted.append(dict(id=uuid5(NAMESPACE_URL, f"RIMAS:{DATASET}:{meta['station']}:{seq}"),
                well_id=wells[0]["id"], measured_at=when, observed_level_m=val, unit="m", source="RIMAS",
                data_classification="PUBLIC", dataset=DATASET, station_code=meta["station"],
                source_record_id=seq, pumping=row[5] or None, source_metadata=metadata))
        except (ValueError, IndexError) as exc:
            rejected.append(dict(row=position, source_record_id=seq, reason=str(exc), original=row))
    days = Counter(r["measured_at"].date().isoformat() for r in accepted)
    return wells[0], accepted, dict(batch=meta["batch"], consulted=len(original), accepted=len(accepted), rejected=rejected,
        duplicates=duplicates, days=len(days), multiple_reading_days={d:n for d,n in days.items() if n>1},
        missing_days=(end-start).days+1-len(days), temporal_policy="ORIGINAL_OBSERVATIONS_NO_CONSOLIDATION")
