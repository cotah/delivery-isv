from uuid import uuid4

from sqlalchemy import CheckConstraint, Table

from app.domain.enums import AddressType
from app.models.address import _ADDRESS_TYPE_CHECK, Address


class TestAddressStructure:
    def test_has_correct_tablename(self) -> None:
        assert Address.__tablename__ == "addresses"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = Address.__table__.columns
        required = (
            "id",
            "customer_id",
            "city_id",
            "address_type",
            "is_default",
            "street",
            "number",
            "neighborhood",
            "zip_code",
        )
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_optional_columns_nullable(self) -> None:
        cols = Address.__table__.columns
        optional = ("complement", "reference_point", "latitude", "longitude")
        for col_name in optional:
            assert col_name in cols, f"missing optional column: {col_name}"
            assert cols[col_name].nullable is True, f"{col_name} should be NULLABLE"

    def test_has_soft_delete(self) -> None:
        cols = Address.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True

    def test_has_timestamps(self) -> None:
        cols = Address.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_has_fk_to_customers(self) -> None:
        table = Address.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["customer_id"].foreign_keys)
        assert len(fks) == 1, "customer_id should have exactly 1 FK"
        fk = fks[0]
        assert fk.column.table.name == "customers"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_has_fk_to_cities(self) -> None:
        table = Address.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["city_id"].foreign_keys)
        assert len(fks) == 1, "city_id should have exactly 1 FK"
        fk = fks[0]
        assert fk.column.table.name == "cities"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_has_check_constraint_on_address_type(self) -> None:
        table = Address.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        address_type_check = next(
            (c for c in checks if isinstance(c.name, str) and "address_type" in c.name),
            None,
        )
        assert address_type_check is not None, "address_type CHECK constraint not found"
        sql_text = str(address_type_check.sqltext)
        for value in ("home", "work", "other"):
            assert f"'{value}'" in sql_text, f"CHECK missing enum value: {value}"

    def test_has_partial_unique_index_on_customer_default(self) -> None:
        table = Address.__table__
        assert isinstance(table, Table)
        default_ix = next(
            (ix for ix in table.indexes if ix.name == "uq_addresses_customer_default"),
            None,
        )
        assert default_ix is not None, "uq_addresses_customer_default index not found"
        assert default_ix.unique is True
        where = default_ix.dialect_kwargs.get("postgresql_where")
        assert where == "is_default = true AND deleted_at IS NULL"

    def test_has_index_on_customer_id(self) -> None:
        table = Address.__table__
        assert isinstance(table, Table)
        ix = next((ix for ix in table.indexes if ix.name == "ix_addresses_customer_id"), None)
        assert ix is not None, "ix_addresses_customer_id index not found"

    def test_has_index_on_city_id(self) -> None:
        table = Address.__table__
        assert isinstance(table, Table)
        ix = next((ix for ix in table.indexes if ix.name == "ix_addresses_city_id"), None)
        assert ix is not None, "ix_addresses_city_id index not found"


class TestAddressBehavior:
    def test_address_type_enum_values(self) -> None:
        assert {v.value for v in AddressType} == {"home", "work", "other"}

    def test_address_type_check_includes_all_enum_values(self) -> None:
        for value in ("home", "work", "other"):
            assert f"'{value}'" in _ADDRESS_TYPE_CHECK

    def test_repr_does_not_leak_address(self) -> None:
        addr = Address(
            customer_id=uuid4(),
            city_id=uuid4(),
            address_type=AddressType.HOME,
            street="Rua das Acácias",
            number="123",
            neighborhood="Centro",
            zip_code="35180000",
        )
        r = repr(addr)
        # Deve mostrar identidade e tipo
        assert "home" in r.lower(), "repr should contain address_type"
        # NÃO pode vazar dados de localização
        assert "Rua das Acácias" not in r, "repr leaked street"
        assert "35180000" not in r, "repr leaked zip_code"
        assert "Centro" not in r, "repr leaked neighborhood"
        assert "123" not in r, "repr leaked number"
