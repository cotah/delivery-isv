"""Testes do endpoint GET /api/v1/stores via TestClient."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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

        # Embed de category (display_order adicionado em HIGH debt #2, 2026-04-26)
        assert set(item["category"].keys()) == {"id", "name", "slug", "display_order"}

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


class TestGetStoreDetailEndpoint:
    def test_returns_200_with_store_when_approved(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        response = client.get(f"/api/v1/stores/{store.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(store.id)

    def test_returns_404_when_store_does_not_exist(self, client: TestClient) -> None:
        import uuid

        fake_id = uuid.uuid4()
        response = client.get(f"/api/v1/stores/{fake_id}")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "store_not_found"
        assert body["error"]["message"] == "Loja não encontrada"

    def test_returns_404_when_store_is_pending(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.PENDING)
        response = client.get(f"/api/v1/stores/{store.id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "store_not_found"

    def test_returns_404_when_store_is_soft_deleted(
        self,
        client: TestClient,
        store_factory: Any,
        db_session: Session,
    ) -> None:
        """Security: soft-deleted store returns 404 (not 410). Preserves UUID opacity."""
        from datetime import UTC, datetime

        store = store_factory(status=StoreStatus.APPROVED)
        store.deleted_at = datetime.now(UTC)
        db_session.flush()
        response = client.get(f"/api/v1/stores/{store.id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "store_not_found"

    def test_returns_422_when_store_id_is_invalid_uuid(self, client: TestClient) -> None:
        """ADR-022: validation_exception_handler formata erro de UUID inválido."""
        response = client.get("/api/v1/stores/not-a-uuid")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_response_has_all_expected_fields(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        response = client.get(f"/api/v1/stores/{store.id}")
        body = response.json()
        expected = {
            "id",
            "name",
            "slug",
            "street",
            "number",
            "complement",
            "neighborhood",
            "zip_code",
            "category",
            "city",
        }
        assert set(body.keys()) == expected

    def test_response_has_nested_category_and_city(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        response = client.get(f"/api/v1/stores/{store.id}")
        body = response.json()
        # display_order adicionado em HIGH debt #2 (2026-04-26)
        assert set(body["category"].keys()) == {"id", "name", "slug", "display_order"}
        assert "id" in body["city"]
        assert "name" in body["city"]

    def test_does_not_expose_pii(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        """Regressão: detalhe continua sem expor PII ou campos internos."""
        store = store_factory(status=StoreStatus.APPROVED)
        response = client.get(f"/api/v1/stores/{store.id}")
        keys = set(response.json().keys())
        forbidden = {
            "legal_name",
            "tax_id",
            "tax_id_type",
            "status",
            "is_active",
            "deleted_at",
            "created_at",
            "updated_at",
            "trade_name",  # deve sair como "name" via alias
        }
        leaked = keys & forbidden
        assert not leaked, f"PII/internal fields leaked: {leaked}"

    def test_name_field_is_trade_name_value(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        """Regressão: detalhe também usa alias name→trade_name (pattern iFood)."""
        store = store_factory(status=StoreStatus.APPROVED, trade_name="Pizzaria do Zé")
        response = client.get(f"/api/v1/stores/{store.id}")
        item = response.json()
        assert item["name"] == "Pizzaria do Zé"
        assert "trade_name" not in item

    def test_zip_code_returned_without_hyphen(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        """Contract: zip_code retornado crú, 8 dígitos, sem hífen.

        Backend retorna dado, frontend formata (pattern Stripe/Google Maps).
        """
        store = store_factory(status=StoreStatus.APPROVED, zip_code="35855000")
        response = client.get(f"/api/v1/stores/{store.id}")
        zip_code = response.json()["zip_code"]
        assert zip_code == "35855000"
        assert "-" not in zip_code
        assert len(zip_code) == 8
