from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_without_database():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_allowed_origin():
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_origin_is_not_allowed():
    response = client.get("/health", headers={"Origin": "https://example.org"})
    assert "access-control-allow-origin" not in response.headers
