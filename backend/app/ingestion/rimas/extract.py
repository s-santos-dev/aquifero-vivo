import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .mappings import EXPORT_URL, REGISTRY_URL, MAX_BYTES
from .validate import selection


def extract(client, directory, *, station, start, end, file=None):
    start, end = selection(station, start, end)
    registry = client.station(station)
    if file:
        content = Path(file).read_bytes()
        params, headers = {}, {}
    else:
        content, params, headers = client.export(station, start, end)
    if len(content) > MAX_BYTES:
        raise ValueError("Arquivo excede limite do piloto")
    batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid4())[:8]
    folder = Path(directory) / batch
    folder.mkdir(parents=True, exist_ok=False)
    with (folder / "observations.csv").open("xb") as f: f.write(content)
    meta = dict(batch=batch, extracted_at=datetime.now(timezone.utc).isoformat(), source_url=EXPORT_URL,
        registry_url=REGISTRY_URL, station=station, start=start.isoformat(), end=end.isoformat(),
        raw_sha256=hashlib.sha256(content).hexdigest(), request=params, response_headers=headers,
        acquisition="official_file" if file else "official_csv_export", registry=registry,
        unit="m", unit_evidence=f"https://rimasweb.sgb.gov.br/layout/detalhe.php?ponto={station}",
        timezone="UNKNOWN", level_reference="UNKNOWN", treatment="PORTAL_EXPORT_UNSPECIFIED")
    with (folder / "manifest.json").open("x", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=2)
    return content, meta


def from_batch(folder):
    folder = Path(folder)
    content = (folder / "observations.csv").read_bytes()
    meta = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(content).hexdigest() != meta.get("raw_sha256"):
        raise ValueError("Arquivo bruto alterado; checksum divergente")
    return content, meta
