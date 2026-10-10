from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _parameters(path: str) -> dict[str, dict]:
    operation = app.openapi()["paths"][path]["get"]
    return {parameter["name"]: parameter for parameter in operation["parameters"]}


def test_first_api_routes_are_exposed_in_openapi():
    paths = app.openapi()["paths"]
    assert {
        "/api/v1/wells",
        "/api/v1/wells/{well_id}",
        "/api/v1/sectors",
        "/api/v1/sectors/{sector_id}",
        "/api/v1/measurements",
    }.issubset(paths)


def test_collection_routes_document_pagination_and_filters():
    well_parameters = _parameters("/api/v1/wells")
    assert {"page", "page_size", "q", "municipality", "sector_id", "state", "is_active", "source"} == set(
        well_parameters
    )
    assert well_parameters["page_size"]["schema"]["maximum"] == 100

    sector_parameters = _parameters("/api/v1/sectors")
    assert {"page", "page_size", "q"} == set(sector_parameters)

    measurement_parameters = _parameters("/api/v1/measurements")
    assert {
        "page",
        "page_size",
        "type",
        "well_id",
        "sector_id",
        "measured_from",
        "measured_to",
        "classification",
        "source",
    } == set(measurement_parameters)


def test_collection_response_contract_is_paginated():
    schema = app.openapi()["components"]["schemas"]["Page_WellResponse_"]
    assert set(schema["required"]) == {"items", "total", "page", "page_size", "pages"}


def test_measurement_rejects_an_inverted_time_range_before_querying_database():
    response = client.get(
        "/api/v1/measurements",
        params={
            "measured_from": "2026-02-02T00:00:00Z",
            "measured_to": "2026-02-01T00:00:00Z",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "measured_from deve ser anterior ou igual a measured_to"


def test_pagination_is_validated_by_fastapi():
    assert client.get("/api/v1/wells", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/sectors", params={"page_size": 101}).status_code == 422
