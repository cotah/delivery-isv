from typing import Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Integer, String, Table, UniqueConstraint

from app.models.addon import Addon
from app.models.order_item_addon import OrderItemAddon


def _valid_order_item_addon_kwargs(**overrides: Any) -> dict[str, Any]:
    """Kwargs mínimos pra instanciar OrderItemAddon válido. Overrides opcionais."""
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "order_item_id": uuid4(),
        "addon_id": uuid4(),
        "addon_name_snapshot": "Borda Cheddar",
        "unit_price_cents": 500,
    }
    defaults.update(overrides)
    return defaults


class TestOrderItemAddonStructure:
    def test_has_correct_tablename(self) -> None:
        assert OrderItemAddon.__tablename__ == "order_item_addons"

    def test_has_all_5_domain_columns(self) -> None:
        cols = OrderItemAddon.__table__.columns
        expected = {
            "id",
            "order_item_id",
            "addon_id",
            "addon_name_snapshot",
            "unit_price_cents",
        }
        actual = {c.name for c in cols}
        missing = expected - actual
        assert not missing, f"missing columns: {missing}"

    def test_required_columns_not_nullable(self) -> None:
        cols = OrderItemAddon.__table__.columns
        required = (
            "id",
            "order_item_id",
            "addon_id",
            "addon_name_snapshot",
            "unit_price_cents",
        )
        for col_name in required:
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_addon_name_snapshot_string_length(self) -> None:
        col = OrderItemAddon.__table__.columns["addon_name_snapshot"]
        assert isinstance(col.type, String)
        assert col.type.length == 100

    def test_unit_price_cents_is_integer(self) -> None:
        # ADR-007: dinheiro em _cents INTEGER — nunca FLOAT nem DECIMAL
        col = OrderItemAddon.__table__.columns["unit_price_cents"]
        assert isinstance(col.type, Integer)

    def test_fk_order_item_id_cascade(self) -> None:
        # ADR-015: composição estrita — CASCADE
        table = OrderItemAddon.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["order_item_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "order_items"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE", f"ADR-015: expected CASCADE, got {fk.ondelete!r}"

    def test_fk_addon_id_restrict(self) -> None:
        # ADR-016: histórico preservado — RESTRICT em FK de catálogo
        table = OrderItemAddon.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["addon_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "addons"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT", f"ADR-016: expected RESTRICT, got {fk.ondelete!r}"

    def test_has_one_check_constraint(self) -> None:
        table = OrderItemAddon.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        assert len(checks) == 1, f"expected 1 CHECK, got {len(checks)}"

    def test_check_name_with_naming_convention_prefix(self) -> None:
        table = OrderItemAddon.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        names = {c.name for c in checks if isinstance(c.name, str)}
        assert "ck_order_item_addons_unit_price_cents_non_negative" in names, (
            f"missing naming_convention prefix; got names: {names}"
        )

    def test_has_two_non_unique_indexes(self) -> None:
        table = OrderItemAddon.__table__
        assert isinstance(table, Table)
        for ix_name in (
            "ix_order_item_addons_order_item_id",
            "ix_order_item_addons_addon_id",
        ):
            ix = next((i for i in table.indexes if i.name == ix_name), None)
            assert ix is not None, f"missing index: {ix_name}"

    def test_no_unique_constraint(self) -> None:
        """OrderItemAddon permite mesmo addon múltiplas vezes no item (ADR-016)."""
        table = OrderItemAddon.__table__
        assert isinstance(table, Table)
        uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        assert len(uniques) == 0, f"unexpected UNIQUE constraints: {uniques}"


class TestOrderItemAddonBehavior:
    def test_repr_contains_ids_and_price(self) -> None:
        oia = OrderItemAddon(**_valid_order_item_addon_kwargs())
        r = repr(oia)
        assert str(oia.order_item_id) in r
        assert str(oia.addon_id) in r
        assert "500" in r  # unit_price_cents

    def test_repr_does_not_expose_snapshot(self) -> None:
        oia = OrderItemAddon(**_valid_order_item_addon_kwargs())
        r = repr(oia)
        assert "Borda Cheddar" not in r

    def test_composes_timestamp_mixin(self) -> None:
        cols = OrderItemAddon.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_composes_soft_delete_mixin(self) -> None:
        cols = OrderItemAddon.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True


class TestSnapshotSizeMatchesSource:
    """ADR-016: addon_name_snapshot tem mesmo tamanho que Addon.name.

    Regressão: se Addon.name for redimensionado no futuro, o snapshot em
    OrderItemAddon tem que acompanhar pra evitar truncamento silencioso.
    """

    def test_addon_name_snapshot_matches_addon_name(self) -> None:
        oia_table = OrderItemAddon.__table__
        addon_table = Addon.__table__
        assert isinstance(oia_table, Table)
        assert isinstance(addon_table, Table)

        oia_type = oia_table.c.addon_name_snapshot.type
        src_type = addon_table.c.name.type
        assert isinstance(oia_type, String)
        assert isinstance(src_type, String)

        assert oia_type.length == src_type.length, (
            f"addon_name_snapshot String({oia_type.length}) != Addon.name String({src_type.length})"
        )
