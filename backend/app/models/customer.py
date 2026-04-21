from datetime import date

from sqlalchemy import Boolean, Date, Index, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.utils.validators import (
    mask_phone_for_log,
    validate_cpf,
    validate_phone_e164,
)


class Customer(Base, TimestampMixin, SoftDeleteMixin):
    """Cliente final do ISV Delivery.

    Login por telefone via OTP (ADR-009). Email e CPF opcionais.

    Aplica soft delete com anonimização de PII (ADR-004).
    Validação defense-in-depth em PII (ADR-010) — mesmo validador
    é chamado pelo Pydantic na borda da API e pelo SQLAlchemy aqui
    como última linha de defesa.
    """

    __tablename__ = "customers"

    id: Mapped[UUIDPK]

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(254),  # RFC 5321 max email length
        nullable=True,
    )
    cpf: Mapped[str | None] = mapped_column(
        String(11),
        nullable=True,
    )
    birth_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    __table_args__ = (
        # UNIQUE parcial em email (só considera rows com email != NULL)
        Index(
            "uq_customers_email",
            "email",
            unique=True,
            postgresql_where="email IS NOT NULL",
        ),
    )

    @validates("phone")
    def _validate_phone(self, _key: str, value: str) -> str:
        return validate_phone_e164(value)

    @validates("cpf")
    def _validate_cpf(self, _key: str, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_cpf(value)

    def __repr__(self) -> str:
        return f"<Customer id={self.id} phone={mask_phone_for_log(self.phone)}>"
