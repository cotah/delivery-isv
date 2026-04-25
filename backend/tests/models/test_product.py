from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, Table

from app.domain.enums import MenuSection, ProductStatus
from app.models.product import Product


class TestProductStructure:
    def test_has_correct_tablename(self) -> None:
        assert Product.__tablename__ == "products"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = Product.__table__.columns
        required = ("id", "store_id", "name", "status")
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_optional_columns_nullable(self) -> None:
        cols = Product.__table__.columns
        optional = ("description", "image_url", "preparation_minutes")
        for col_name in optional:
            assert col_name in cols, f"missing optional column: {col_name}"
            assert cols[col_name].nullable is True, f"{col_name} should be NULLABLE"

    def test_has_fk_to_stores(self) -> None:
        table = Product.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["store_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "stores"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_has_check_constraint_on_status(self) -> None:
        table = Product.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        status_check = next((c for c in checks if c.name == "ck_products_status"), None)
        assert status_check is not None, "ck_products_status not found"
        sql_text = str(status_check.sqltext)
        for value in ("active", "out_of_stock", "paused"):
            assert f"'{value}'" in sql_text, f"CHECK missing status value: {value}"

    def test_has_index_on_store_id(self) -> None:
        table = Product.__table__
        assert isinstance(table, Table)
        ix = next((i for i in table.indexes if i.name == "ix_products_store_id"), None)
        assert ix is not None

    def test_has_index_on_status(self) -> None:
        table = Product.__table__
        assert isinstance(table, Table)
        ix = next((i for i in table.indexes if i.name == "ix_products_status"), None)
        assert ix is not None

    def test_has_soft_delete(self) -> None:
        cols = Product.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True

    def test_has_timestamps(self) -> None:
        cols = Product.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_status_default_is_active(self) -> None:
        col = Product.__table__.columns["status"]
        # Python default (usado quando ORM cria sem passar status)
        assert col.default is not None
        assert col.default.arg == ProductStatus.ACTIVE
        # Server default (usado em raw SQL / seeds)
        assert col.server_default is not None


class TestProductBehavior:
    def test_product_status_enum_values(self) -> None:
        assert {v.value for v in ProductStatus} == {"active", "out_of_stock", "paused"}

    def test_repr_contains_name_and_status(self) -> None:
        prod = Product(
            store_id=uuid4(),
            name="Pizza Margherita",
            status=ProductStatus.ACTIVE,
        )
        r = repr(prod)
        assert "Pizza Margherita" in r
        assert "active" in r.lower()


class TestProductMenuFields:
    """Organização do cardápio (HIGH debt #2, 2026-04-26).

    display_order, menu_section, featured. Lojista organiza menu sem mexer
    no nome do produto. Frontend agrupa response plano por menu_section.
    """

    def test_display_order_default_zero(self) -> None:
        col = Product.__table__.columns["display_order"]
        assert col.default is not None
        assert col.default.arg == 0
        assert col.server_default is not None
        assert "0" in str(col.server_default.arg)

    def test_display_order_is_not_nullable(self) -> None:
        assert Product.__table__.columns["display_order"].nullable is False

    def test_menu_section_default_is_other(self) -> None:
        col = Product.__table__.columns["menu_section"]
        # Python default — novo Product Python pega OTHER no construtor
        assert col.default is not None
        assert col.default.arg == MenuSection.OTHER
        # DB-side default — rows pré-existentes recebem 'other'
        assert col.server_default is not None
        assert "other" in str(col.server_default.arg)

    def test_menu_section_is_not_nullable(self) -> None:
        assert Product.__table__.columns["menu_section"].nullable is False

    def test_menu_section_check_constraint_present(self) -> None:
        table = Product.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        section_check = next((c for c in checks if c.name == "ck_products_menu_section"), None)
        assert section_check is not None, "ck_products_menu_section not found"
        sql_text = str(section_check.sqltext)
        for value in MenuSection:
            assert f"'{value.value}'" in sql_text, f"CHECK missing: {value.value}"

    def test_validates_rejects_invalid_menu_section_string(self) -> None:
        # @validates roda antes de persistir — defense-in-depth ADR-010.
        with pytest.raises(ValueError, match="Invalid menu section"):
            Product(
                store_id=uuid4(),
                name="Test",
                menu_section="bogus_section",
            )

    def test_validates_accepts_enum_directly(self) -> None:
        prod = Product(
            store_id=uuid4(),
            name="Test",
            menu_section=MenuSection.PIZZA,
        )
        assert prod.menu_section == MenuSection.PIZZA

    def test_featured_default_false(self) -> None:
        col = Product.__table__.columns["featured"]
        assert col.default is not None
        assert col.default.arg is False
        assert col.server_default is not None
        assert "false" in str(col.server_default.arg).lower()

    def test_featured_is_not_nullable(self) -> None:
        assert Product.__table__.columns["featured"].nullable is False

    def test_repr_includes_menu_fields(self) -> None:
        prod = Product(
            store_id=uuid4(),
            name="Pizza M",
            status=ProductStatus.ACTIVE,
            menu_section=MenuSection.PIZZA,
            display_order=3,
            featured=True,
        )
        r = repr(prod)
        assert "pizza" in r.lower()
        assert "3" in r
        assert "True" in r or "true" in r.lower()
