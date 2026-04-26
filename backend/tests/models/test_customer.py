from typing import Any

import pytest
from sqlalchemy import Table, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.user import User

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


class TestCustomerUserRelationship:
    """FK 1:1 Customer ↔ User (ADR-027 dec. 1, CP1 do Ciclo Customer)."""

    def test_user_id_column_is_uuid_not_null(self) -> None:
        cols = Customer.__table__.columns
        assert "user_id" in cols
        assert cols["user_id"].nullable is False
        # SQLAlchemy 2.x Uuid type — str(Uuid()) retorna 'CHAR(32)' (non-PG dialect),
        # então comparar via class name é mais confiável.
        assert cols["user_id"].type.__class__.__name__ == "Uuid"

    def test_user_id_is_unique_constraint(self) -> None:
        """unique=True inline → naming_convention prefixa pra uq_customers_user_id."""
        table = Customer.__table__
        assert isinstance(table, Table)
        # unique=True inline aparece como UNIQUE no metadata da coluna
        assert table.columns["user_id"].unique is True

    def test_user_id_fk_is_restrict(self) -> None:
        """ADR-011 + ADR-027: RESTRICT preserva histórico Order via Customer."""
        table = Customer.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["user_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "users"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_customer_relationship_loads_user(
        self, db_session: Session, customer_factory: Any
    ) -> None:
        """selectinload(Customer.user) carrega User real."""
        customer = customer_factory()
        # Re-query com eager load explícito (lazy="raise" exige).
        result = db_session.execute(
            select(Customer).where(Customer.id == customer.id).options(selectinload(Customer.user))
        ).scalar_one()
        assert result.user is not None
        assert isinstance(result.user, User)
        assert result.user.id == customer.user_id

    def test_user_customer_relationship_returns_none_when_no_customer(
        self, db_session: Session, user_factory: Any
    ) -> None:
        """User.customer é None quando ainda não há Customer (lazy creation)."""
        user = user_factory()
        result = db_session.execute(
            select(User).where(User.id == user.id).options(selectinload(User.customer))
        ).scalar_one()
        assert result.customer is None

    def test_user_customer_relationship_is_one_to_one(
        self, db_session: Session, customer_factory: Any
    ) -> None:
        """uselist=False força singular (não retorna list[Customer])."""
        customer = customer_factory()
        result = db_session.execute(
            select(User).where(User.id == customer.user_id).options(selectinload(User.customer))
        ).scalar_one()
        # Single Customer, não lista (pattern uselist=False — primeira ocorrência no projeto).
        assert isinstance(result.customer, Customer)
        assert result.customer.id == customer.id

    def test_user_id_unique_rejects_duplicate(
        self, db_session: Session, user_factory: Any, customer_factory: Any
    ) -> None:
        """1:1 garantido no banco — não dá pra criar 2 Customer pro mesmo User."""
        user = user_factory()
        customer_factory(user=user)
        # Tentar criar segundo Customer pro mesmo User → UNIQUE violation
        duplicate = Customer(
            user_id=user.id,
            phone=VALID_PHONE,
            name="Outro",
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_fk_restrict_prevents_user_delete_when_customer_exists(
        self, db_session: Session, customer_factory: Any
    ) -> None:
        """ADR-011: RESTRICT bloqueia hard-delete de User com Customer."""
        from sqlalchemy import delete

        customer = customer_factory()
        user_id = customer.user_id

        db_session.expunge(customer)  # evita cascade Python
        # Tentar DELETE direto no DB — RESTRICT deve bloquear.
        with pytest.raises(IntegrityError):
            db_session.execute(delete(User).where(User.id == user_id))
            db_session.flush()
        db_session.rollback()
