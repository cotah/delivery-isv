from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_correct_body(client: TestClient) -> None:
    response = client.get("/health")
    assert response.json() == {
        "status": "ok",
        "env": "local",
        "version": "0.1.0",
    }


def test_health_response_has_required_fields(client: TestClient) -> None:
    response = client.get("/health")
    body = response.json()
    assert set(body.keys()) == {"status", "env", "version"}
    assert isinstance(body["status"], str)
    assert isinstance(body["env"], str)
    assert isinstance(body["version"], str)
