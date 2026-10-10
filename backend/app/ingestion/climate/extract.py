import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .client import MAX_BYTES, source_url
from .validate import selection


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def station_file(archive, station):
    if Path(archive).stat().st_size > MAX_BYTES:
        raise ValueError("Arquivo excede limite")
    with zipfile.ZipFile(archive) as z:
        members = [n for n in z.namelist() if re.search(rf"_{station}_.*\.CSV$", n, re.I)]
        if len(members) != 1:
            raise ValueError("Estação ausente ou ambígua no ZIP oficial")
        entry = z.getinfo(members[0])
        if entry.file_size > 5 * 1024 * 1024:
            raise ValueError("CSV excede limite")
        return z.read(entry), members[0]


def extract(client, directory, *, station, start, end, file=None):
    start, end = selection(station, start, end)
    acquired = datetime.now(timezone.utc)
    batch = acquired.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    folder = Path(directory) / batch
    folder.mkdir(parents=True, exist_ok=False)
    archive = folder / "annual.zip"
    try:
        if file:
            if Path(file).stat().st_size > MAX_BYTES:
                raise ValueError("Arquivo excede limite")
            with Path(file).open("rb") as src, archive.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            headers = {}
        else:
            headers = client.download(start.year, archive)
        content, member = station_file(archive, station)
        with (folder / "station.csv").open("xb") as f:
            f.write(content)
        meta = dict(batch=batch, extracted_at=acquired.isoformat(), source="INMET", station=station,
                    start=start.isoformat(), end=end.isoformat(), source_url=source_url(start.year),
                    request={"method": "GET", "url": source_url(start.year)}, response_headers=headers,
                    acquisition="official_browser_download" if file else "official_http_download",
                    archive_member=member, archive_sha256=checksum(archive),
                    raw_sha256=hashlib.sha256(content).hexdigest(), timezone="UTC",
                    unit="mm", interval="previous_hour", format="INMET_ANNUAL_AUTOMATIC_CSV")
        (folder / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf8")
        return content, meta
    except Exception as exc:
        (folder / "failure.json").write_text(json.dumps(dict(request={"method": "GET", "url": source_url(start.year)}, extracted_at=acquired.isoformat(), error=str(exc)), ensure_ascii=False, indent=2), encoding="utf8")
        raise


def from_batch(folder):
    folder = Path(folder)
    meta = json.loads((folder / "manifest.json").read_text(encoding="utf8"))
    content = (folder / "station.csv").read_bytes()
    if hashlib.sha256(content).hexdigest() != meta["raw_sha256"] or checksum(folder / "annual.zip") != meta["archive_sha256"]:
        raise ValueError("Checksum divergente")
    original, member = station_file(folder / "annual.zip", meta["station"])
    if original != content or member != meta["archive_member"]:
        raise ValueError("CSV não corresponde ao arquivo anual")
    return content, meta
