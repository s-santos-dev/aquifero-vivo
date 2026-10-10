import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .mappings import URL, VERSION


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def extract(client, directory, **selection):
    batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    folder = Path(directory) / batch
    manifest = dict(source_url=URL, extracted_at=datetime.now(timezone.utc).isoformat(), batch=batch, version=VERSION, selection=selection)
    metadata = client.get()
    save(folder / "metadata.json", metadata)
    pages = []
    for index, page in enumerate(client.pages(metadata, **selection)):
        save(folder / f"page-{index:04d}.json", page)
        pages.append(page)
    envelope = {**manifest, "pages": pages}
    save(folder / "extraction.json", envelope)
    return envelope


def from_file(path, *, source_url, **selection):
    if not source_url.startswith(("https://siagasweb.sgb.gov.br/", "https://geoportal.sgb.gov.br/", "https://www.sgb.gov.br/")):
        raise ValueError("Informe a URL oficial de obtenção do arquivo")
    path = Path(path)
    if path.suffix.lower() == ".csv":
        import csv
        with path.open(encoding="utf-8-sig", newline="") as stream:
            features = [{"attributes": row} for row in csv.DictReader(stream)]
        pages = [{"spatialReference": {"wkid": 4326}, "features": features}]
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if "pages" in data:
            # Keep original extraction clock; do not claim a new source update.
            return {**data, "selection": selection}
        if data.get("type") == "FeatureCollection":
            if "crs" in data:
                raise ValueError("GeoJSON deve ser RFC 7946 (4326, sem CRS alternativo)")
            features = []
            for f in data["features"]:
                g = f.get("geometry")
                if not g or g.get("type") != "Point":
                    features.append({"attributes": f["properties"], "geometry": None})
                else:
                    features.append({"attributes": f["properties"], "geometry": dict(zip(("x", "y"), g["coordinates"]))})
            pages = [{"spatialReference": {"wkid": 4326}, "features": features}]
        elif "features" in data:
            pages = [data]
        else:
            raise ValueError("Formato não suportado")
    return dict(source_url=source_url, extracted_at=datetime.now(timezone.utc).isoformat(), batch=uuid4().hex, version=VERSION, selection=selection, pages=pages)
