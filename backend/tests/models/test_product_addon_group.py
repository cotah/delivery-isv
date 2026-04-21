from uuid import uuid4

from sqlalchemy import Table, UniqueConstraint

from app.models.product_addon_group import ProductAddonGroup


class TestProductAddonGroupStructure:
    def test_has_correct_tablename(self) -> None:
        assert ProductAddonGroup.__tablename__ == "product_addon_groups"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = ProductAddonGroup.__table__.columns
        required = ("id", "product_id", "group_id", "sort_order")
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_fk_to_products_with_cascade(self) -> None:
        # ADR-015: composição — CASCADE em ambos os lados da junção
        table = ProductAddonGroup.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["product_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "products"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE", f"ADR-015: expected CASCADE (junção), got {fk.ondelete!r}"

    def test_has_fk_to_addon_groups_with_cascade(self) -> None:
        # ADR-015: composição — CASCADE em ambos os lados da junção
        table = ProductAddonGroup.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["group_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "addon_groups"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE", f"ADR-015: expected CASCADE (junção), got {fk.ondelete!r}"

    def test_has_unique_constraint_on_product_group_pair(self) -> None:
        # Protege contra ligação duplicada (mesmo grupo aplicado 2x ao mesmo produto)
        table = ProductAddonGroup.__table__
        assert isinstance(table, Table)
        uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        pair_unique = next(
            (c for c in uniques if {col.name for col in c.columns} == {"product_id", "group_id"}),
            None,
        )
        assert pair_unique is not None, "UniqueConstraint on (product_id, group_id) not found"

    def test_has_index_on_product_id(self) -> None:
        table = ProductAddonGroup.__table__
        assert isinstance(table, Table)
        ix = next(
            (i for i in table.indexes if i.name == "ix_product_addon_groups_product_id"),
            None,
        )
        assert ix is not None

    def test_has_index_on_group_id(self) -> None:
        table = ProductAddonGroup.__table__
        assert isinstance(table, Table)
        ix = next(
            (i for i in table.indexes if i.name == "ix_product_addon_groups_group_id"),
            None,
        )
        assert ix is not None

    def test_does_not_have_soft_delete(self) -> None:
        # ADR-014: junção não é entidade — sem SoftDeleteMixin
        cols = ProductAddonGroup.__table__.columns
        assert "deleted_at" not in cols

    def test_has_timestamps(self) -> None:
        # Tem TimestampMixin (created_at + updated_at) mas NÃO SoftDelete
        cols = ProductAddonGroup.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False


class TestProductAddonGroupBehavior:
    def test_repr_contains_product_and_group(self) -> None:
        product_id = uuid4()
        group_id = uuid4()
        link = ProductAddonGroup(
            product_id=product_id,
            group_id=group_id,
            sort_order=0,
        )
        r = repr(link)
        assert str(product_id) in r
        assert str(group_id) in r
        assert "sort_order=0" in r

    def test_sort_order_default_zero(self) -> None:
        col = ProductAddonGroup.__table__.columns["sort_order"]
        assert col.default is not None
        assert col.default.arg == 0
        assert col.server_default is not None
