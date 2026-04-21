import pytest
from sqlalchemy import Table

from app.models.customer import Customer

VALID_PHONE = "+5531999887766"
VALID_CPF = "52998224725"


class TestCustomerStructure:
    def test_has_correct_tablename(self) -> None:
        assert Customer.__tablename__ == "customers"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = Customer.__table__.columns
        for col_name in ("id", "phone", "name", "is_active"):
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_optional_columns_nullable(self) -> None:
        cols = Customer.__table__.columns
        for col_name in ("email", "cpf", "birth_date"):
            assert col_name in cols, f"missing optional column: {col_name}"
            assert cols[col_name].nullable is True, f"{col_name} should be NULLABLE"

    def test_phone_is_unique(self) -> None:
        assert Customer.__table__.columns["phone"].unique is True

    def test_email_has_partial_unique_index(self) -> None:
        table = Customer.__table__
        assert isinstance(table, Table)  # type narrowing: __table__ é FromClause genérico
        email_ix = next((ix for ix in table.indexes if ix.name == "uq_customers_email"), None)
        assert email_ix is not None, "uq_customers_email index not found"
        assert email_ix.unique is True
        where_clause = email_ix.dialect_kwargs.get("postgresql_where")
        assert where_clause == "email IS NOT NULL"

    def test_has_deleted_at_from_soft_delete_mixin(self) -> None:
        cols = Customer.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True

    def test_has_timestamps_from_mixin(self) -> None:
        cols = Customer.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False


class TestCustomerBehavior:
    def test_repr_masks_phone(self) -> None:
        customer = Customer(phone=VALID_PHONE, name="Teste")
        r = repr(customer)
        assert VALID_PHONE not in r, "repr must not expose full phone"
        assert "+55*********66" in r, "repr must contain masked phone"

    def test_validator_rejects_invalid_phone(self) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            Customer(phone="5531999887766", name="Teste")

    def test_validator_rejects_invalid_cpf(self) -> None:
        with pytest.raises(ValueError, match=r"11 digits"):
            Customer(phone=VALID_PHONE, name="Teste", cpf="529.982.247-25")

    def test_validator_accepts_none_cpf(self) -> None:
        customer = Customer(phone=VALID_PHONE, name="Teste", cpf=None)
        assert customer.cpf is None

    def test_validator_accepts_valid_cpf(self) -> None:
        customer = Customer(phone=VALID_PHONE, name="Teste", cpf=VALID_CPF)
        assert customer.cpf == VALID_CPF
