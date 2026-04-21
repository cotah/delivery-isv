from uuid import uuid4

from sqlalchemy import CheckConstraint, Integer, Table

from app.models.product_variation import ProductVariation


class TestProductVariationStructure:
    def test_has_correct_tablename(self) -> None:
        assert ProductVariation.__tablename__ == "product_variations"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = ProductVariation.__table__.columns
        required = ("id", "product_id", "name", "price_cents", "sort_order")
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_fk_to_products_with_cascade(self) -> None:
        # Primeira aplicação do ADR-015 — CASCADE em FK de composição
        table = ProductVariation.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["product_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "products"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE", (
            f"ADR-015: expected CASCADE (composição estrita), got {fk.ondelete!r}"
        )

    def test_has_check_price_non_negative(self) -> None:
        table = ProductVariation.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        price_check = next(
            (c for c in checks if c.name == "ck_product_variations_price_cents_non_negative"),
            None,
        )
        assert price_check is not None, "ck_product_variations_price_cents_non_negative not found"
        sql_text = str(price_check.sqltext)
        assert "price_cents" in sql_text
        assert ">=" in sql_text
        assert "0" in sql_text

    def test_has_index_on_product_id(self) -> None:
        table = ProductVariation.__table__
        assert isinstance(table, Table)
        ix = next(
            (i for i in table.indexes if i.name == "ix_product_variations_product_id"),
            None,
        )
        assert ix is not None

    def test_has_soft_delete(self) -> None:
        cols = ProductVariation.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True

    def test_has_timestamps(self) -> None:
        cols = ProductVariation.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_sort_order_default_zero(self) -> None:
        col = ProductVariation.__table__.columns["sort_order"]
        # Python default
        assert col.default is not None
        assert col.default.arg == 0
        # DB-side server_default
        assert col.server_default is not None

    def test_does_not_have_is_default_column(self) -> None:
        # ADR-014: is_default documentado mas não implementado no MVP.
        # Lojista garante 1 default por produto via camada de aplicação.
        cols = ProductVariation.__table__.columns
        assert "is_default" not in cols


class TestProductVariationBehavior:
    def test_repr_contains_name_and_price(self) -> None:
        var = ProductVariation(
            product_id=uuid4(),
            name="Pequena",
            price_cents=3500,
            sort_order=0,
        )
        r = repr(var)
        assert "Pequena" in r
        assert "3500" in r

    def test_repr_does_not_expose_description(self) -> None:
        # ADR-014: variações reusam descrição do Product pai — não têm
        # coluna description própria. Este teste documenta a decisão
        # e garante que repr não vaza nada do gênero.
        assert "description" not in ProductVariation.__table__.columns
        var = ProductVariation(
            product_id=uuid4(),
            name="Pequena",
            price_cents=3500,
            sort_order=0,
        )
        assert "description" not in repr(var).lower()

    def test_price_cents_is_integer_type(self) -> None:
        # ADR-007: dinheiro em _cents INTEGER — nunca FLOAT nem DECIMAL
        col = ProductVariation.__table__.columns["price_cents"]
        assert isinstance(col.type, Integer)
