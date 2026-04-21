from uuid import uuid4

from sqlalchemy import CheckConstraint, Table

from app.domain.enums import AddonGroupType
from app.models.addon_group import AddonGroup


class TestAddonGroupStructure:
    def test_has_correct_tablename(self) -> None:
        assert AddonGroup.__tablename__ == "addon_groups"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = AddonGroup.__table__.columns
        required = (
            "id",
            "store_id",
            "name",
            "type",
            "min_selections",
            "max_selections",
            "sort_order",
        )
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_fk_to_stores_with_restrict(self) -> None:
        # ADR-011: store é entidade — RESTRICT, não CASCADE
        table = AddonGroup.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["store_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "stores"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT", (
            f"ADR-011: expected RESTRICT (entidade), got {fk.ondelete!r}"
        )

    def test_has_check_on_type(self) -> None:
        table = AddonGroup.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        type_check = next((c for c in checks if c.name == "ck_addon_groups_type"), None)
        assert type_check is not None, "ck_addon_groups_type not found"
        sql_text = str(type_check.sqltext)
        for value in ("single", "multiple"):
            assert f"'{value}'" in sql_text, f"CHECK missing enum value: {value}"

    def test_has_check_min_non_negative(self) -> None:
        table = AddonGroup.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        check = next(
            (c for c in checks if c.name == "ck_addon_groups_min_selections_non_negative"),
            None,
        )
        assert check is not None, "ck_addon_groups_min_selections_non_negative not found"
        sql_text = str(check.sqltext)
        assert "min_selections" in sql_text
        assert ">=" in sql_text

    def test_has_check_max_gte_min(self) -> None:
        table = AddonGroup.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        check = next(
            (c for c in checks if c.name == "ck_addon_groups_max_selections_gte_min"),
            None,
        )
        assert check is not None, "ck_addon_groups_max_selections_gte_min not found"
        sql_text = str(check.sqltext)
        assert "max_selections" in sql_text
        assert "min_selections" in sql_text
        assert ">=" in sql_text

    def test_has_index_on_store_id(self) -> None:
        table = AddonGroup.__table__
        assert isinstance(table, Table)
        ix = next((i for i in table.indexes if i.name == "ix_addon_groups_store_id"), None)
        assert ix is not None

    def test_has_soft_delete(self) -> None:
        cols = AddonGroup.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True

    def test_has_timestamps(self) -> None:
        cols = AddonGroup.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_default_values(self) -> None:
        cols = AddonGroup.__table__.columns
        # min_selections = 0
        assert cols["min_selections"].default is not None
        assert cols["min_selections"].default.arg == 0
        assert cols["min_selections"].server_default is not None
        # max_selections = 1
        assert cols["max_selections"].default is not None
        assert cols["max_selections"].default.arg == 1
        assert cols["max_selections"].server_default is not None
        # sort_order = 0
        assert cols["sort_order"].default is not None
        assert cols["sort_order"].default.arg == 0
        assert cols["sort_order"].server_default is not None


class TestAddonGroupBehavior:
    def test_addon_group_type_enum_values(self) -> None:
        assert {v.value for v in AddonGroupType} == {"single", "multiple"}

    def test_repr_contains_name_type_min_max(self) -> None:
        group = AddonGroup(
            store_id=uuid4(),
            name="Frutas",
            type=AddonGroupType.MULTIPLE,
            min_selections=0,
            max_selections=3,
            sort_order=0,
        )
        r = repr(group)
        assert "Frutas" in r
        assert "multiple" in r.lower()
        assert "min=0" in r
        assert "max=3" in r
