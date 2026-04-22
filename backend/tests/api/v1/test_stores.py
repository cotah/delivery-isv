"""Testes do endpoint GET /api/v1/stores via TestClient."""

from typing import Any

from fastapi.testclient import TestClient

from app.domain.enums import StoreStatus


class TestGetStoresEndpoint:
    def test_empty_returns_200_with_empty_items(
        self,
        client: TestClient,
    ) -> None:
        response = client.get("/api/v1/stores")
        assert response.status_code == 200
        body = response.json()
        assert body == {"items": [], "total": 0, "offset": 0, "limit": 20}

    def test_returns_approved_only(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        approved = store_factory(status=StoreStatus.APPROVED)
        store_factory(status=StoreStatus.PENDING)

        response = client.get("/api/v1/stores")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["id"] == str(approved.id)

    def test_response_shape_has_nested_category_and_city(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store_factory(status=StoreStatus.APPROVED)

        response = client.get("/api/v1/stores")
        item = response.json()["items"][0]

        # Campos top-level (sem delivery_fee_cents — não existe em Store)
        assert set(item.keys()) == {"id", "name", "slug", "neighborhood", "category", "city"}

        # Embed de category
        assert set(item["category"].keys()) == {"id", "name", "slug"}

        # Embed de city (com state, já que City.state existe)
        assert set(item["city"].keys()) == {"id", "name", "state"}

    def test_does_not_expose_pii(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        """Regressão: endpoint público não expõe PII nem detalhe fiscal/granular."""
        store_factory(status=StoreStatus.APPROVED)

        response = client.get("/api/v1/stores")
        item = response.json()["items"][0]

        forbidden = {
            "legal_name",
            "tax_id",
            "tax_id_type",
            "street",
            "number",
            "complement",
            "zip_code",
            "status",
            "deleted_at",
            "created_at",
            "updated_at",
            "trade_name",  # deve sair como "name" via alias — se vazar cru, é bug
        }
        leaked = set(item.keys()) & forbidden
        assert not leaked, f"PII or detail fields leaked: {leaked}"

    def test_name_field_is_trade_name_value(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        """API expõe 'name' mapeado de trade_name (pattern iFood)."""
        store_factory(status=StoreStatus.APPROVED, trade_name="Pizzaria do Zé")

        response = client.get("/api/v1/stores")
        item = response.json()["items"][0]

        assert item["name"] == "Pizzaria do Zé"
        assert "trade_name" not in item
        assert "legal_name" not in item

    def test_default_pagination(self, client: TestClient) -> None:
        response = client.get("/api/v1/stores")
        body = response.json()
        assert body["offset"] == 0
        assert body["limit"] == 20

    def test_custom_pagination(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        for _ in range(5):
            store_factory(status=StoreStatus.APPROVED)

        response = client.get("/api/v1/stores?offset=2&limit=2")
        body = response.json()
        assert len(body["items"]) == 2
        assert body["offset"] == 2
        assert body["limit"] == 2
        assert body["total"] == 5

    def test_limit_over_100_returns_422(self, client: TestClient) -> None:
        response = client.get("/api/v1/stores?limit=150")
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "validation_failed"
        assert any("limit" in d.get("field", "") for d in body["error"]["details"])

    def test_negative_offset_returns_422(self, client: TestClient) -> None:
        response = client.get("/api/v1/stores?offset=-1")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_limit_zero_returns_422(self, client: TestClient) -> None:
        response = client.get("/api/v1/stores?limit=0")
        assert response.status_code == 422
