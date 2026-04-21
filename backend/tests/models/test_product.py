from uuid import uuid4

from sqlalchemy import CheckConstraint, Table

from app.domain.enums import ProductStatus
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
