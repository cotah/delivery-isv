"""Smoke tests da infra HTTP (ADR-020 + ADR-021 + ADR-022).

Validam que:
1. Endpoint /health pré-existente continua respondendo (regressão).
2. Rotas inexistentes retornam 404 no formato uniforme do ADR-022.
3. Router /api/v1 está montado e captura 404 via handler do projeto.
"""

from fastapi.testclient import TestClient


class TestHealthRegression:
    def test_health_still_returns_200(self, client: TestClient) -> None:
        """Regressão: /health existente continua funcionando após mudança de main.py."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_body_preserved(self, client: TestClient) -> None:
        """Regressão: corpo de /health mantém os 3 campos esperados."""
        response = client.get("/health")
        body = response.json()
        assert set(body.keys()) == {"status", "env", "version"}
        assert body["status"] == "ok"


class TestErrorFormatADR022:
    def test_404_returns_uniform_error_shape(self, client: TestClient) -> None:
        """ADR-022: rota inexistente retorna error.code=not_found no envelope uniforme."""
        response = client.get("/api/v1/inexistente")
        assert response.status_code == 404
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "not_found"
        assert "message" in body["error"]

    def test_v1_router_mounted(self, client: TestClient) -> None:
        """Router /api/v1 está montado; 404 em rota inexistente usa formato ADR-022."""
        response = client.get("/api/v1/")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "not_found"

    def test_404_response_has_no_fastapi_default_detail(self, client: TestClient) -> None:
        """ADR-022: `{"detail": "..."}` do default FastAPI foi substituído
        pelo envelope uniforme — não deve aparecer nas respostas de erro.
        """
        response = client.get("/api/v1/rota-qualquer")
        body = response.json()
        assert "detail" not in body, "default FastAPI leaked — handler ADR-022 não está ativo"
