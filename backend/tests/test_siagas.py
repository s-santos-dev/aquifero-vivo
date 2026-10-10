import copy
import json
import math
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import pytest
from app.ingestion.siagas.client import Client, SourceError
from app.ingestion.siagas.extract import extract, from_file
from app.ingestion.siagas.transform import transform

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def envelope():
    return dict(source_url="https://geoportal.sgb.gov.br/server/rest/services/hidrologia/SIAGAS_MODDAD/FeatureServer/0", extracted_at="2026-10-10T16:00:00+00:00", batch="official-fixture", selection=dict(state="PI", municipality="Teresina", limit=25), pages=[json.loads((FIXTURES / "siagas-teresina.json").read_text(encoding="utf-8"))])


def test_official_parsing_units_provenance(envelope):
    rows, report = transform(envelope)
    assert report["accepted"] == 3 and report["rejected"] == []
    row = rows[0]
    assert row["source_record_id"] == "2200009783"
    assert row["name"] == "SIAGAS 2200009783"  # Explicit label, not an invented source name.
    assert row["source"] == "SIAGAS" and row["data_classification"] == "PUBLIC"
    assert row["is_active"] is None and row["depth_m"] == 100
    assert row["source_metadata"]["static_level_m"] == 7
    assert row["source_metadata"]["dynamic_level_m"] == 46
    assert row["source_metadata"]["units"]["num_vazao_especifica"] == "m³/h/m"
    assert "flow_rate_m3_h" not in row and "measured_at" not in row
    assert row["source_metadata"]["original_updated_at"] is None
    assert row["id"] == transform(envelope)[0][0]["id"]


def test_missing_optional_fields(envelope):
    a = envelope["pages"][0]["features"][0]["attributes"]
    for key in ("num_profundidade", "ne", "nd", "str_aquifero", "data_cadastro"):
        a.pop(key, None)
    row = transform(envelope)[0][0]
    assert row["depth_m"] is None and row["source_metadata"]["aquifer"] is None
    assert row["source_metadata"]["static_level_m"] is None


@pytest.mark.parametrize("change", ["id", "null", "invalid", "swap", "state", "municipality", "bbox", "srid", "depth"])
def test_rejects_invalid_records(envelope, change):
    page = envelope["pages"][0]
    page["features"] = page["features"][:1]
    f = page["features"][0]
    if change == "id": f["attributes"].pop("idt_ponto")
    if change == "null": f["geometry"] = None
    if change == "invalid": f["geometry"]["y"] = float("nan")
    if change == "swap": f["geometry"]["x"], f["geometry"]["y"] = f["geometry"]["y"], f["geometry"]["x"]
    if change == "state": f["attributes"]["str_uf"] = "CE"
    if change == "municipality": f["attributes"]["str_municipio"] = "Picos"
    if change == "bbox": envelope["selection"]["bbox"] = [-42, -6, -41, -5]
    if change == "srid": page["spatialReference"] = {"wkid": 31983}
    if change == "depth": f["attributes"]["num_profundidade"] = -1
    rows, report = transform(envelope)
    assert rows == [] and len(report["rejected"]) == 1


def test_mercator_conversion(envelope):
    base = transform(envelope)[0][0]
    page = envelope["pages"][0]; page["features"] = page["features"][:1]
    page["spatialReference"] = {"wkid": 3857}
    page["features"][0]["geometry"] = dict(x=6378137*math.radians(base["longitude"]), y=6378137*math.log(math.tan(math.pi/4+math.radians(base["latitude"])/2)))
    row = transform(envelope)[0][0]
    assert row["longitude"] == pytest.approx(base["longitude"])
    assert row["latitude"] == pytest.approx(base["latitude"])


def test_duplicate_rejected(envelope):
    envelope["pages"][0]["features"].append(copy.deepcopy(envelope["pages"][0]["features"][0]))
    rows, report = transform(envelope)
    assert len(rows) == 3 and "duplicado" in report["rejected"][0]["reason"]


def test_invalid_levels_stay_in_raw_metadata(envelope):
    a = envelope["pages"][0]["features"][0]["attributes"]
    a.update(ne=10, nd=1)
    row = transform(envelope)[0][0]
    assert row["source_metadata"]["static_level_m"] is None
    assert row["source_metadata"]["attributes"]["ne"] == 10
    assert row["source_metadata"]["warnings"]


def test_pagination_limit_filters_and_raw_copy(envelope, tmp_path):
    meta = json.loads((FIXTURES / "siagas-metadata.json").read_text(encoding="utf-8"))
    features = envelope["pages"][0]["features"]
    calls = []
    client = Client(pause=0)
    def get(path="", **params):
        if not path: return meta
        calls.append(params)
        offset, size = params["resultOffset"], params["resultRecordCount"]
        return dict(geometryType="esriGeometryPoint", spatialReference={"wkid": 4326}, features=features[offset:offset+size], exceededTransferLimit=offset+size < 3)
    client.get = get
    result = extract(client, tmp_path, state="PI", municipality="Teresina", limit=3, page_size=2)
    assert [c["resultOffset"] for c in calls] == [0, 2]
    assert [c["resultRecordCount"] for c in calls] == [2, 1]
    assert "UPPER(str_municipio)='TERESINA'" in calls[0]["where"]
    assert calls[0]["outSR"] == 4326
    assert len(transform(result)[0]) == 3
    assert len(list(tmp_path.rglob("page-*.json"))) == 2


def test_repeating_page_aborts(envelope):
    meta = json.loads((FIXTURES / "siagas-metadata.json").read_text(encoding="utf-8"))
    client = Client(pause=0)
    client.get = lambda *a, **k: {**envelope["pages"][0], "features": envelope["pages"][0]["features"][:1], "exceededTransferLimit": True}
    with pytest.raises(SourceError, match="Paginação"):
        list(client.pages(meta, limit=2, page_size=1))


def test_retries_bounded_and_access_not_bypassed():
    with patch("app.ingestion.siagas.client.urlopen", side_effect=URLError("offline")) as call, patch("app.ingestion.siagas.client.time.sleep") as sleep:
        with pytest.raises(SourceError, match="3 tentativas"): Client().get()
        assert call.call_count == 3 and sleep.call_count == 2
    with patch("app.ingestion.siagas.client.urlopen", side_effect=HTTPError("url", 403, "Forbidden", {}, None)) as call:
        with pytest.raises(SourceError, match="HTTP 403"): Client().get()
        assert call.call_count == 1


def test_arcgis_json_error():
    from io import BytesIO
    with patch("app.ingestion.siagas.client.urlopen", return_value=BytesIO(b'{"error":{"code":400}}')):
        with pytest.raises(SourceError, match="ArcGIS"): Client().get()


def test_file_import_csv_geojson(envelope, tmp_path):
    chosen = envelope["selection"]
    csv = tmp_path / "official.csv"
    csv.write_text("idt_ponto,str_uf,str_municipio,num_latitude_decimal,num_longitude_decimal\n2200009783,PI,Teresina,-5.091388,-42.814444\n", encoding="utf-8")
    assert len(transform(from_file(csv, source_url=envelope["source_url"], **chosen))[0]) == 1
    f = envelope["pages"][0]["features"][0]
    geo = tmp_path / "official.geojson"
    geo.write_text(json.dumps(dict(type="FeatureCollection", features=[dict(type="Feature", properties=f["attributes"], geometry=dict(type="Point", coordinates=[f["geometry"]["x"], f["geometry"]["y"]]))])), encoding="utf-8")
    assert len(transform(from_file(geo, source_url=envelope["source_url"], **chosen))[0]) == 1
    with pytest.raises(ValueError, match="URL oficial"):
        from_file(csv, source_url="https://example.com/", **chosen)
