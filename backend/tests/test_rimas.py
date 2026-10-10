import copy
import csv
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import pytest
from app.ingestion.rimas.client import Client, SourceError
from app.ingestion.rimas.extract import extract, from_batch
from app.ingestion.rimas.transform import transform
from app.ingestion.rimas.validate import selection

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def rimas():
    return (FIXTURES / "rimas-rete.csv").read_bytes(), json.loads((FIXTURES / "rimas-rete-manifest.json").read_text(encoding="utf-8"))


def replace_rows(fixture, modify):
    content, meta = fixture
    rows = list(csv.reader(io.StringIO(content.decode("cp1252")), delimiter=";"))
    modify(rows)
    buf = io.StringIO(); csv.writer(buf, delimiter=";", lineterminator="\n").writerows(rows)
    content = buf.getvalue().encode("cp1252")
    meta = copy.deepcopy(meta); meta["raw_sha256"] = hashlib.sha256(content).hexdigest()
    return content, meta


def test_original_fields_multiple_readings_and_no_daily_fill(rimas):
    well, rows, report = transform(*rimas)
    assert well["source_record_id"] == "2200034952" and well["source"] == "SIAGAS"
    assert len(rows) == 5 and report["multiple_reading_days"] == {"2025-01-28": 2}
    assert report["missing_days"] == 86 and report["rejected"] == []
    first = rows[0]
    assert first["measured_at"] == datetime(2025, 1, 1, 8) and first["measured_at"].tzinfo is None
    assert str(first["observed_level_m"]) == "18.73" and first["unit"] == "m"
    assert first["pumping"] == "N" and first["source"] == "RIMAS" and first["data_classification"] == "PUBLIC"
    meta = first["source_metadata"]
    assert meta["timezone"] == meta["level_reference"] == "UNKNOWN"
    assert not meta["eligible_for_indicators"] and meta["quality_status"] == "NOT_PROVIDED"
    assert meta["original_value"] == "18,73" and meta["original_flow"] == ""
    assert meta["batch"] and meta["extracted_at"] and len(meta["raw_sha256"]) == 64
    assert "water_level_m" not in first and "flow_rate_m3_h" not in first


def test_exact_duplicate_vs_conflicting_id(rimas):
    result = replace_rows(rimas, lambda rows: rows.append(rows[3].copy()))
    _, rows, report = transform(*result)
    assert len(rows) == 5 and len(report["duplicates"]) == 1
    def conflict(rows):
        extra = rows[3].copy(); extra[3] = "19,99"; rows.append(extra)
    _, rows, report = transform(*replace_rows(rimas, conflict))
    assert len(rows) == 4 and len(report["rejected"]) == 2


@pytest.mark.parametrize("field,value", [(0,""),(1,"31/02/2025"),(1,"01/01/2024"),(2,"25:10"),(3,""),(3,"NaN"),(3,"100000000"),(3,"1,12345"),(5,"X")])
def test_invalid_observation_is_reported_without_zero_fill(rimas, field, value):
    def change(rows): rows[3][field] = value
    _, rows, report = transform(*replace_rows(rimas, change))
    assert len(rows) == 4 and len(report["rejected"]) == 1


def test_negative_reference_unknown_and_pumping_are_preserved(rimas):
    def change(rows): rows[3][3] = "-0,42"; rows[3][4] = "UNKNOWN_FLOW_UNIT"; rows[3][5] = "S"
    _, rows, _ = transform(*replace_rows(rimas, change))
    assert str(rows[0]["observed_level_m"]) == "-0.42" and rows[0]["pumping"] == "S"
    assert rows[0]["source_metadata"]["original_flow"] == "UNKNOWN_FLOW_UNIT"
    assert not rows[0]["source_metadata"]["eligible_for_indicators"]


def test_empty_export_has_no_records(rimas):
    _, rows, report = transform(*replace_rows(rimas, lambda rows: rows.__delitem__(slice(3, None))))
    assert rows == [] and report["accepted"] == 0 and report["missing_days"] == 90


@pytest.mark.parametrize("change", ["station", "unit", "timezone", "reference", "registry", "ambiguous", "non_pi", "checksum", "url", "extraction"])
def test_contract_identity_and_provenance_fail_closed(rimas, change):
    content, meta = rimas
    if change == "station": meta["station"] = "2200000000"
    if change == "unit": meta["unit"] = "cm"
    if change == "timezone": meta["timezone"] = "UTC"
    if change == "reference": meta["level_reference"] = "STATIC"
    if change == "registry": meta["registry"]["features"][0]["attributes"]["idt_ponto"] = 2200000000
    if change == "ambiguous": meta["registry"]["features"] *= 2
    if change == "non_pi": meta["registry"]["features"][0]["attributes"]["str_uf"] = "BA"
    if change == "checksum": content += b"0"
    if change == "url": meta["source_url"] = "https://example.com"
    if change == "extraction": meta["extracted_at"] = "2026-10-10T12:00:00"
    with pytest.raises(ValueError): transform(content, meta)


def test_extraction_immutable_raw_and_reprocessing(rimas, tmp_path):
    content, meta = rimas
    client = Client(); client.station = lambda station: meta["registry"]
    client.export = lambda *args: (content, {"idponto": "2200034952"}, {"Content-Type": "application/csv"})
    result = extract(client, tmp_path, station="2200034952", start="2025-01-01", end="2025-03-31")
    folder = tmp_path / result[1]["batch"]
    assert from_batch(folder)[0] == content and transform(*from_batch(folder))[2]["accepted"] == 5
    (folder / "observations.csv").write_bytes(content+b"x")
    with pytest.raises(ValueError, match="checksum"): from_batch(folder)


def test_period_bounded():
    for station, start, end in [("x", "2025-01-01", "2025-01-02"), ("22", "2025-02-01", "2025-01-01"), ("22", "2024-01-01", "2025-01-01")]:
        with pytest.raises(ValueError): selection(station, start, end)


def test_csv_service_retries_and_does_not_bypass_access():
    with patch("app.ingestion.rimas.client.urlopen", side_effect=URLError("offline")) as call, patch("app.ingestion.rimas.client.time.sleep"):
        with pytest.raises(SourceError, match="3 tentativas"): Client().export("2200034952", "2025-01-01", "2025-01-02")
        assert call.call_count == 3
    with patch("app.ingestion.rimas.client.urlopen", side_effect=HTTPError("url", 403, "Forbidden", {}, None)) as call:
        with pytest.raises(SourceError, match="403"): Client().export("2200034952", "2025-01-01", "2025-01-02")
        assert call.call_count == 1


def test_csv_response_contract_and_size(rimas):
    class Response(io.BytesIO): headers = {"Content-Type": "application/csv"}
    for content in (b"<html>failure</html>", b"Id Ponto:;" + b"x"*2_000_000):
        with patch("app.ingestion.rimas.client.urlopen", return_value=Response(content)):
            with pytest.raises(SourceError): Client().export("2200034952", "2025-01-01", "2025-01-02")
    with patch("app.ingestion.rimas.client.urlopen", return_value=Response(rimas[0])):
        assert Client().export("2200034952", "2025-01-01", "2025-03-31")[0] == rimas[0]


def test_station_query_rejects_truncated_ambiguous_or_different_identity(rimas):
    for mutate in (lambda d: d.update(exceededTransferLimit=True), lambda d: d["features"].append(copy.deepcopy(d["features"][0])), lambda d: d["features"][0]["attributes"].update(idt_ponto=123)):
        data = copy.deepcopy(rimas[1]["registry"]); mutate(data)
        client = Client(); client.registry.get = lambda *a, **kw: data
        with pytest.raises(SourceError): client.station("2200034952")
