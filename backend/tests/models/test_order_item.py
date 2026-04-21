from typing import Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Integer, String, Table, UniqueConstraint

from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_variation import ProductVariation


def _valid_order_item_kwargs(**overrides: Any) -> dict[str, Any]:
    """Kwargs mínimos pra instanciar OrderItem válido. Overrides opcionais."""
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "order_id": uuid4(),
        "product_variation_id": uuid4(),
        "product_name_snapshot": "Pizza Margherita",
        "variation_name_snapshot": "Grande",
        "unit_price_cents": 5500,
        "quantity": 1,
        "line_total_cents": 5500,
    }
    defaults.update(overrides)
    return defaults


class TestOrderItemStructure:
    def test_has_correct_tablename(self) -> None:
        assert OrderItem.__tablename__ == "order_items"

    def test_has_all_9_domain_columns(self) -> None:
        cols = OrderItem.__table__.columns
        expected = {
            "id",
            "order_id",
            "product_variation_id",
            "product_name_snapshot",
            "variation_name_snapshot",
            "unit_price_cents",
            "quantity",
            "line_total_cents",
            "notes",
        }
        actual = {c.name for c in cols}
        missing = expected - actual
        assert not missing, f"missing columns: {missing}"

    def test_required_columns_not_nullable(self) -> None:
        cols = OrderItem.__table__.columns
        required = (
            "id",
            "order_id",
            "product_variation_id",
            "product_name_snapshot",
            "variation_name_snapshot",
            "unit_price_cents",
            "quantity",
            "line_total_cents",
        )
        for col_name in required:
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_notes_nullable(self) -> None:
        cols = OrderItem.__table__.columns
        assert cols["notes"].nullable is True

    def test_string_column_lengths(self) -> None:
        cols = OrderItem.__table__.columns
        expected_lengths = {
            "product_name_snapshot": 150,
            "variation_name_snapshot": 100,
        }
        for col_name, length in expected_lengths.items():
            col_type = cols[col_name].type
            assert isinstance(col_type, String)
            assert col_type.length == length, (
                f"{col_name} expected String({length}), got {col_type.length}"
            )

    def test_cents_and_quantity_are_integer(self) -> None:
        # ADR-007: dinheiro em _cents INTEGER; quantity também Integer
        cols = OrderItem.__table__.columns
        for col_name in ("unit_price_cents", "quantity", "line_total_cents"):
            assert isinstance(cols[col_name].type, Integer)

    def test_fk_order_id_cascade(self) -> None:
        # ADR-015: composição estrita — CASCADE
        table = OrderItem.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["order_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "orders"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE", f"ADR-015: expected CASCADE, got {fk.ondelete!r}"

    def test_fk_product_variation_id_restrict(self) -> None:
        # ADR-016: histórico preservado — RESTRICT em FK de catálogo
        table = OrderItem.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["product_variation_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "product_variations"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT", f"ADR-016: expected RESTRICT, got {fk.ondelete!r}"

    def test_has_three_check_constraints(self) -> None:
        table = OrderItem.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        assert len(checks) == 3, f"expected 3 CHECKs, got {len(checks)}"

    def test_check_names_with_naming_convention_prefix(self) -> None:
        table = OrderItem.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        names = {c.name for c in checks if isinstance(c.name, str)}
        expected = {
            "ck_order_items_quantity_positive",
            "ck_order_items_unit_price_cents_non_negative",
            "ck_order_items_line_total_cents_non_negative",
        }
        assert expected.issubset(names), f"missing: {expected - names}"

    def test_has_two_non_unique_indexes(self) -> None:
        table = OrderItem.__table__
        assert isinstance(table, Table)
        for ix_name in (
            "ix_order_items_order_id",
            "ix_order_items_product_variation_id",
        ):
            ix = next((i for i in table.indexes if i.name == ix_name), None)
            assert ix is not None, f"missing index: {ix_name}"

    def test_no_unique_constraint(self) -> None:
        """OrderItem permite mesma variation múltiplas vezes no pedido (ADR-016)."""
        table = OrderItem.__table__
        assert isinstance(table, Table)
        uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        assert len(uniques) == 0, f"unexpected UNIQUE constraints: {uniques}"


class TestOrderItemBehavior:
    def test_repr_contains_ids_quantity_total(self) -> None:
        item = OrderItem(**_valid_order_item_kwargs())
        r = repr(item)
        assert str(item.order_id) in r
        assert str(item.product_variation_id) in r
        assert "quantity=1" in r
        assert "5500" in r

    def test_repr_does_not_expose_snapshots_or_notes(self) -> None:
        item = OrderItem(**_valid_order_item_kwargs(notes="sem cebola"))
        r = repr(item)
        assert "Pizza Margherita" not in r
        assert "Grande" not in r
        assert "sem cebola" not in r

    def test_composes_timestamp_mixin(self) -> None:
        cols = OrderItem.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_composes_soft_delete_mixin(self) -> None:
        cols = OrderItem.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True


class TestSnapshotSizesMatchSource:
    """ADR-016: snapshots de nome devem ter o MESMO tamanho da coluna source.

    Teste de regressão: se Product.name ou ProductVariation.name forem
    redimensionados no futuro, os snapshots em OrderItem têm que acompanhar
    pra evitar truncamento silencioso no momento do pedido.
    """

    def test_variation_name_snapshot_matches_variation_name(self) -> None:
        oi_table = OrderItem.__table__
        var_table = ProductVariation.__table__
        assert isinstance(oi_table, Table)
        assert isinstance(var_table, Table)

        oi_type = oi_table.c.variation_name_snapshot.type
        src_type = var_table.c.name.type
        assert isinstance(oi_type, String)
        assert isinstance(src_type, String)

        assert oi_type.length == src_type.length, (
            f"variation_name_snapshot String({oi_type.length}) != "
            f"ProductVariation.name String({src_type.length})"
        )

    def test_product_name_snapshot_matches_product_name(self) -> None:
        oi_table = OrderItem.__table__
        prod_table = Product.__table__
        assert isinstance(oi_table, Table)
        assert isinstance(prod_table, Table)

        oi_type = oi_table.c.product_name_snapshot.type
        src_type = prod_table.c.name.type
        assert isinstance(oi_type, String)
        assert isinstance(src_type, String)

        assert oi_type.length == src_type.length, (
            f"product_name_snapshot String({oi_type.length}) != "
            f"Product.name String({src_type.length})"
        )
