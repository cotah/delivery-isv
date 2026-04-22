"""Testes do repositório Product — list_store_products."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.enums import ProductStatus
from app.repositories import products as products_repository


class TestListStoreProducts:
    def test_returns_products_of_the_store(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory()
        product = product_factory(store=store)

        items = products_repository.list_store_products(db_session, store.id, 500)

        assert len(items) == 1
        assert items[0].id == product.id

    def test_excludes_products_paused(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory()
        product_factory(store=store, status=ProductStatus.ACTIVE)
        product_factory(store=store, status=ProductStatus.PAUSED)

        items = products_repository.list_store_products(db_session, store.id, 500)

        assert len(items) == 1
        assert items[0].status == ProductStatus.ACTIVE

    def test_includes_products_active(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory()
        product_factory(store=store, status=ProductStatus.ACTIVE)

        items = products_repository.list_store_products(db_session, store.id, 500)

        assert len(items) == 1
        assert items[0].status == ProductStatus.ACTIVE

    def test_includes_products_out_of_stock(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory()
        product_factory(store=store, status=ProductStatus.OUT_OF_STOCK)

        items = products_repository.list_store_products(db_session, store.id, 500)

        assert len(items) == 1
        assert items[0].status == ProductStatus.OUT_OF_STOCK

    def test_excludes_products_soft_deleted(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory()
        product = product_factory(store=store)
        product.deleted_at = datetime.now(UTC)
        db_session.flush()

        items = products_repository.list_store_products(db_session, store.id, 500)

        assert items == []

    def test_ordered_by_name_asc(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory()
        product_factory(store=store, name="Banana Split")
        product_factory(store=store, name="Abacaxi Assado")
        product_factory(store=store, name="Caju Doce")

        items = products_repository.list_store_products(db_session, store.id, 500)

        names = [p.name for p in items]
        assert names == ["Abacaxi Assado", "Banana Split", "Caju Doce"]

    def test_eager_loads_variations_addon_groups_and_addons(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
        product_variation_factory: Any,
        addon_group_factory: Any,
        addon_factory: Any,
        product_addon_group_factory: Any,
    ) -> None:
        """N+1 protection: lazy='raise' em toda a cadeia força eager load."""
        store = store_factory()
        product = product_factory(store=store)
        product_variation_factory(product=product, name="Único", price_cents=2000)
        group = addon_group_factory(store=store, name="Bordas")
        addon_factory(group=group, name="Catupiry")
        product_addon_group_factory(product=product, group=group)

        items = products_repository.list_store_products(db_session, store.id, 500)

        assert len(items) == 1
        p = items[0]
        # lazy='raise' levantaria InvalidRequestError se eager load não rodou
        assert len(p.variations) == 1
        assert p.variations[0].name == "Único"
        assert len(p.addon_groups) == 1
        assert p.addon_groups[0].name == "Bordas"
        assert len(p.addon_groups[0].addons) == 1
        assert p.addon_groups[0].addons[0].name == "Catupiry"

    def test_respects_limit(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store = store_factory()
        for i in range(3):
            product_factory(store=store, name=f"Produto {i:02d}")

        items = products_repository.list_store_products(db_session, store.id, 2)

        assert len(items) == 2

    def test_does_not_include_products_from_other_stores(
        self,
        db_session: Session,
        store_factory: Any,
        product_factory: Any,
    ) -> None:
        store_a = store_factory()
        store_b = store_factory()
        own = product_factory(store=store_a)
        product_factory(store=store_b)

        items = products_repository.list_store_products(db_session, store_a.id, 500)

        assert len(items) == 1
        assert items[0].id == own.id

    def test_empty_list_when_store_has_no_products(
        self,
        db_session: Session,
        store_factory: Any,
    ) -> None:
        store = store_factory()

        items = products_repository.list_store_products(db_session, store.id, 500)

        assert items == []
