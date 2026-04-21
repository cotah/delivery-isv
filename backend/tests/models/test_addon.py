from uuid import uuid4

from sqlalchemy import CheckConstraint, Integer, Table

from app.models.addon import Addon


class TestAddonStructure:
    def test_has_correct_tablename(self) -> None:
        assert Addon.__tablename__ == "addons"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = Addon.__table__.columns
        required = ("id", "group_id", "name", "price_cents", "is_available", "sort_order")
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_fk_to_addon_groups_with_cascade(self) -> None:
        # ADR-015: composição estrita — CASCADE
        table = Addon.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["group_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "addon_groups"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE", (
            f"ADR-015: expected CASCADE (composição), got {fk.ondelete!r}"
        )

    def test_has_check_price_non_negative(self) -> None:
        table = Addon.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        check = next(
            (c for c in checks if c.name == "ck_addons_price_cents_non_negative"),
            None,
        )
        assert check is not None, "ck_addons_price_cents_non_negative not found"
        sql_text = str(check.sqltext)
        assert "price_cents" in sql_text
        assert ">=" in sql_text

    def test_has_index_on_group_id(self) -> None:
        table = Addon.__table__
        assert isinstance(table, Table)
        ix = next((i for i in table.indexes if i.name == "ix_addons_group_id"), None)
        assert ix is not None

    def test_has_soft_delete(self) -> None:
        cols = Addon.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True

    def test_has_timestamps(self) -> None:
        cols = Addon.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_is_available_default_true(self) -> None:
        col = Addon.__table__.columns["is_available"]
        assert col.default is not None
        assert col.default.arg is True
        assert col.server_default is not None

    def test_sort_order_default_zero(self) -> None:
        col = Addon.__table__.columns["sort_order"]
        assert col.default is not None
        assert col.default.arg == 0
        assert col.server_default is not None


class TestAddonBehavior:
    def test_repr_contains_name_price_available(self) -> None:
        addon = Addon(
            group_id=uuid4(),
            name="Cheddar",
            price_cents=500,
            is_available=True,
            sort_order=0,
        )
        r = repr(addon)
        assert "Cheddar" in r
        assert "500" in r
        assert "available" in r.lower()

    def test_price_cents_is_integer_type(self) -> None:
        # ADR-007: dinheiro em _cents INTEGER — nunca FLOAT nem DECIMAL
        col = Addon.__table__.columns["price_cents"]
        assert isinstance(col.type, Integer)
