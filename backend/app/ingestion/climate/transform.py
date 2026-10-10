"""Keep hourly intervals. Daily totals require all 24 distinct previous-hour intervals."""
import csv
import hashlib
import re
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
from .client import source_url
from .validate import selection, coordinates, rainfall


def transform(content, meta):
    start, end = selection(meta["station"], meta["start"], meta["end"])
    if (hashlib.sha256(content).hexdigest() != meta["raw_sha256"] or meta.get("source") != "INMET" or meta.get("source_url") != source_url(start.year)
            or meta.get("timezone") != "UTC" or meta.get("unit") != "mm" or meta.get("interval") != "previous_hour"
            or not meta.get("batch") or datetime.fromisoformat(meta["extracted_at"]).utcoffset() is None):
        raise ValueError("Proveniência inválida")
    lines = list(csv.reader(content.decode("latin1").splitlines(), delimiter=";"))
    if len(lines) < 10:
        raise ValueError("CSV vazio ou inesperado")
    expected = ["REGIAO:", "UF:", "ESTACAO:", "CODIGO (WMO):", "LATITUDE:", "LONGITUDE:", "ALTITUDE:", "DATA DE FUNDACAO:"]
    if any(len(r) != 2 or r[0] != label for r, label in zip(lines[:8], expected)):
        raise ValueError("Cabeçalho cadastral inesperado")
    values = [r[1] for r in lines[:8]]
    if values[3] != meta["station"] or not values[2] or not re.fullmatch(r"[A-Z]{2}", values[1]):
        raise ValueError("Identidade oficial divergente")
    lat, lon = (float(v.replace(",", ".")) for v in values[4:6])
    coordinates(lon, lat)
    header = lines[8]
    if header[:2] != ["Data", "Hora UTC"] or header[2] != "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)":
        raise ValueError("Unidade, frequência ou timezone inesperados")
    station_id = uuid5(NAMESPACE_URL, "INMET:" + values[3])
    station = dict(id=station_id, official_code=values[3], name=values[2], source="INMET",
                   observation_type="STATION_OBSERVATION", longitude=lon, latitude=lat,
                   source_metadata=dict(meta, original_header=lines[:9], state=values[1],
                       spatial_reference="EPSG:4326", spatial_reference_note="Coordenadas geográficas publicadas; datum original não declarado no CSV",
                       quality_status="NOT_PROVIDED", eligible_for_risk=False))
    begin = datetime.combine(start, datetime.min.time(), timezone.utc)
    finish = datetime.combine(end + timedelta(days=1), datetime.min.time(), timezone.utc)
    grouped, rejected = {}, []
    for line_number, row in enumerate(lines[9:], 10):
        if not row or not any(row):
            continue
        try:
            if len(row) != len(header):
                raise ValueError("Quantidade de campos inesperada")
            if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", row[0]) or not re.fullmatch(r"(?:[01]\d|2[0-3])00 UTC", row[1]):
                raise ValueError("Data ou hora inválida")
            stamp = datetime.strptime(row[0] + " " + row[1], "%Y/%m/%d %H%M UTC").replace(tzinfo=timezone.utc)
            # The reading ends its interval. Include next-day midnight, exclude first midnight.
            if not begin < stamp <= finish:
                continue
            grouped.setdefault(stamp, []).append((line_number, row))
        except ValueError as exc:
            rejected.append(dict(line=line_number, reason=str(exc), original_row=row))
    records, duplicates = [], 0
    for stamp, members in sorted(grouped.items()):
        if any(r != members[0][1] for _, r in members):
            rejected.extend(dict(line=n, reason="Duplicata conflitante", original_row=r) for n, r in members)
            continue
        duplicates += len(members) - 1
        n, row = members[0]
        try:
            value = rainfall(row[2])
        except ValueError as exc:
            rejected.append(dict(line=n, reason=str(exc), original_row=row))
            continue
        records.append(dict(id=uuid5(NAMESPACE_URL, f"INMET:{values[3]}:{stamp.isoformat()}"), station_id=station_id,
            measured_at=stamp, value_mm=value, unit="mm", source="INMET", availability="MISSING" if value is None else "OBSERVED",
            source_metadata=dict(meta, original_date=row[0], original_time=row[1], original_value=row[2], original_unit="mm",
                original_row=row, original_line=n, source_record_id=None, interval_start=(stamp-timedelta(hours=1)).isoformat(),
                interval_end=stamp.isoformat(), quality_status="NOT_PROVIDED", eligible_for_risk=False)))
    from app.climate.service import daily_series
    daily = daily_series(records, start, end)
    missing_intervals = int((finish-begin).total_seconds()/3600) - len(records)
    report = dict(station=values[3], batch=meta["batch"], start=start.isoformat(), end=end.isoformat(),
        accepted=len(records), observed=sum(r["availability"] == "OBSERVED" for r in records),
        missing_values=sum(r["availability"] == "MISSING" for r in records), absent_or_rejected_intervals=missing_intervals,
        duplicates=duplicates, rejected=rejected, complete_days=sum(d["availability"] == "COMPLETE" for d in daily),
        expected_days=len(daily), daily=daily, provenance=meta)
    return station, records, report
