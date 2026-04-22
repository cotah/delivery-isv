"""Testes do endpoint GET /api/v1/stores/{store_id}/products."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import ProductStatus, StoreStatus


class TestListStoreProductsEndpoint:
    def test_returns_200_with_items_when_store_approved(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product_factory(store=store)

        response = client.get(f"/api/v1/stores/{store.id}/products")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_returns_404_when_store_does_not_exist(self, client: TestClient) -> None:
        response = client.get(f"/api/v1/stores/{uuid.uuid4()}/products")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "store_not_found"
        assert body["error"]["message"] == "Loja não encontrada"

    def test_returns_404_when_store_pending(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.PENDING)
        response = client.get(f"/api/v1/stores/{store.id}/products")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "store_not_found"

    def test_returns_404_when_store_soft_deleted(
        self,
        client: TestClient,
        store_factory: Any,
        db_session: Session,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        store.deleted_at = datetime.now(UTC)
        db_session.flush()
        response = client.get(f"/api/v1/stores/{store.id}/products")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "store_not_found"

    def test_returns_422_when_store_id_invalid_uuid(self, client: TestClient) -> None:
        response = client.get("/api/v1/stores/not-a-uuid/products")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_422_when_limit_over_1000(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        response = client.get(f"/api/v1/stores/{store.id}/products?limit=1500")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_422_when_limit_below_1(
        self,
        client: TestClient,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        response = client.get(f"/api/v1/stores/{store.id}/products?limit=0")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_default_limit_is_500(self, client: TestClient) -> None:
        """Contract: limit default documentado é 500 (OpenAPI)."""
        schema = client.get("/openapi.json").json()
        params = schema["paths"]["/api/v1/stores/{store_id}/products"]["get"]["parameters"]
        limit_param = next(p for p in params if p["name"] == "limit")
        assert limit_param["schema"]["default"] == 500
        assert limit_param["schema"]["maximum"] == 1000
        assert limit_param["schema"]["minimum"] == 1

    def test_product_is_available_true_when_active(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product_factory(store=store, status=ProductStatus.ACTIVE)

        response = client.get(f"/api/v1/stores/{store.id}/products")
        body = response.json()

        assert body["items"][0]["is_available"] is True

    def test_product_is_available_false_when_out_of_stock(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product_factory(store=store, status=ProductStatus.OUT_OF_STOCK)

        response = client.get(f"/api/v1/stores/{store.id}/products")
        body = response.json()

        assert body["items"][0]["is_available"] is False

    def test_variation_is_available_follows_product_status(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
        product_variation_factory: Any,
    ) -> None:
        """is_available da variation herda do produto pai (débito HIGH documentado)."""
        store = store_factory(status=StoreStatus.APPROVED)
        active_product = product_factory(
            store=store,
            status=ProductStatus.ACTIVE,
            name="Ativo",
        )
        oos_product = product_factory(
            store=store,
            status=ProductStatus.OUT_OF_STOCK,
            name="Esgotado",
        )
        product_variation_factory(product=active_product, name="Único")
        product_variation_factory(product=oos_product, name="Único")

        response = client.get(f"/api/v1/stores/{store.id}/products")
        body = response.json()

        by_name = {p["name"]: p for p in body["items"]}
        assert by_name["Ativo"]["variations"][0]["is_available"] is True
        assert by_name["Esgotado"]["variations"][0]["is_available"] is False

    def test_paused_products_excluded(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product_factory(store=store, status=ProductStatus.ACTIVE, name="Aparece")
        product_factory(store=store, status=ProductStatus.PAUSED, name="Escondido")

        response = client.get(f"/api/v1/stores/{store.id}/products")
        body = response.json()

        names = [p["name"] for p in body["items"]]
        assert names == ["Aparece"]

    def test_soft_deleted_variations_excluded(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
        product_variation_factory: Any,
        db_session: Session,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product = product_factory(store=store)
        product_variation_factory(product=product, name="Visível")
        hidden = product_variation_factory(product=product, name="Apagada")
        hidden.deleted_at = datetime.now(UTC)
        db_session.flush()

        response = client.get(f"/api/v1/stores/{store.id}/products")
        variations = response.json()["items"][0]["variations"]

        names = [v["name"] for v in variations]
        assert names == ["Visível"]

    def test_soft_deleted_addon_groups_excluded(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
        addon_group_factory: Any,
        product_addon_group_factory: Any,
        db_session: Session,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product = product_factory(store=store)
        visible = addon_group_factory(store=store, name="Visível")
        hidden = addon_group_factory(store=store, name="Apagado")
        hidden.deleted_at = datetime.now(UTC)
        db_session.flush()
        product_addon_group_factory(product=product, group=visible)
        product_addon_group_factory(product=product, group=hidden)

        response = client.get(f"/api/v1/stores/{store.id}/products")
        groups = response.json()["items"][0]["addon_groups"]

        names = [g["name"] for g in groups]
        assert names == ["Visível"]

    def test_soft_deleted_addons_excluded(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
        addon_group_factory: Any,
        addon_factory: Any,
        product_addon_group_factory: Any,
        db_session: Session,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product = product_factory(store=store)
        group = addon_group_factory(store=store)
        product_addon_group_factory(product=product, group=group)
        addon_factory(group=group, name="Visível")
        hidden = addon_factory(group=group, name="Apagado")
        hidden.deleted_at = datetime.now(UTC)
        db_session.flush()

        response = client.get(f"/api/v1/stores/{store.id}/products")
        addons = response.json()["items"][0]["addon_groups"][0]["addons"]

        names = [a["name"] for a in addons]
        assert names == ["Visível"]

    def test_full_response_shape(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
        product_variation_factory: Any,
        addon_group_factory: Any,
        addon_factory: Any,
        product_addon_group_factory: Any,
    ) -> None:
        """Regressão: shape completo do JSON em cada nível."""
        store = store_factory(status=StoreStatus.APPROVED)
        product = product_factory(store=store, name="Pizza Margherita")
        product_variation_factory(product=product, name="Média", sort_order=0)
        product_variation_factory(product=product, name="Grande", sort_order=1)
        group = addon_group_factory(store=store, name="Bordas")
        product_addon_group_factory(product=product, group=group)
        addon_factory(group=group, name="Catupiry", sort_order=0)
        addon_factory(group=group, name="Cheddar", sort_order=1)

        response = client.get(f"/api/v1/stores/{store.id}/products")
        body = response.json()

        assert set(body.keys()) == {"items", "total"}

        item = body["items"][0]
        assert set(item.keys()) == {
            "id",
            "name",
            "description",
            "image_url",
            "preparation_minutes",
            "is_available",
            "variations",
            "addon_groups",
        }

        variation = item["variations"][0]
        assert set(variation.keys()) == {"id", "name", "price_cents", "is_available"}

        ag = item["addon_groups"][0]
        assert set(ag.keys()) == {
            "id",
            "name",
            "type",
            "min_selections",
            "max_selections",
            "addons",
        }

        addon = ag["addons"][0]
        assert set(addon.keys()) == {"id", "name", "price_cents", "is_available"}

    def test_ordered_alphabetically_by_name(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product_factory(store=store, name="Banana Split")
        product_factory(store=store, name="Abacaxi Assado")
        product_factory(store=store, name="Caju Doce")

        response = client.get(f"/api/v1/stores/{store.id}/products")
        names = [p["name"] for p in response.json()["items"]]

        assert names == ["Abacaxi Assado", "Banana Split", "Caju Doce"]

    def test_addons_ordered_by_sort_order_then_name(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
        addon_group_factory: Any,
        addon_factory: Any,
        product_addon_group_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product = product_factory(store=store)
        group = addon_group_factory(store=store)
        product_addon_group_factory(product=product, group=group)
        # sort_order define ordem primário; name resolve empate.
        addon_factory(group=group, name="Beta", sort_order=1)
        addon_factory(group=group, name="Alfa", sort_order=1)
        addon_factory(group=group, name="Gama", sort_order=0)

        response = client.get(f"/api/v1/stores/{store.id}/products")
        names = [a["name"] for a in response.json()["items"][0]["addon_groups"][0]["addons"]]

        assert names == ["Gama", "Alfa", "Beta"]

    def test_addon_groups_ordered_by_sort_order_then_name(
        self,
        client: TestClient,
        store_factory: Any,
        product_factory: Any,
        addon_group_factory: Any,
        product_addon_group_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        product = product_factory(store=store)
        g1 = addon_group_factory(store=store, name="Beta", sort_order=1)
        g2 = addon_group_factory(store=store, name="Alfa", sort_order=1)
        g3 = addon_group_factory(store=store, name="Gama", sort_order=0)
        product_addon_group_factory(product=product, group=g1)
        product_addon_group_factory(product=product, group=g2)
        product_addon_group_factory(product=product, group=g3)

        response = client.get(f"/api/v1/stores/{store.id}/products")
        names = [g["name"] for g in response.json()["items"][0]["addon_groups"]]

        assert names == ["Gama", "Alfa", "Beta"]
