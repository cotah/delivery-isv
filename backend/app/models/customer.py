from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.utils.validators import (
    mask_phone_for_log,
    validate_cpf,
    validate_phone_e164,
)

if TYPE_CHECKING:
    from app.models.user import User


class Customer(Base, TimestampMixin, SoftDeleteMixin):
    """Cliente final do ISV Delivery.

    Login por telefone via OTP (ADR-009). Email e CPF opcionais.

    Conexão com User (ADR-027 dec. 1): user_id UNIQUE NOT NULL FK users(id)
    ondelete=RESTRICT. User pode existir sem Customer (login feito mas
    cadastro pendente — lazy creation via POST /customers, ADR-027 dec. 2).
    Customer obrigatoriamente tem 1 User (não dá pra cadastrar perfil
    sem ter feito login OTP).

    Aplica soft delete com anonimização de PII (ADR-004).
    Validação defense-in-depth em PII (ADR-010) — mesmo validador
    é chamado pelo Pydantic na borda da API e pelo SQLAlchemy aqui
    como última linha de defesa.
    """

    __tablename__ = "customers"

    id: Mapped[UUIDPK]

    # FK 1:1 para User (ADR-027 dec. 1).
    # ondelete=RESTRICT preserva histórico Order via Customer (ADR-011).
    # unique=True inline — naming_convention prefixa pra uq_customers_user_id.
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

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

    # ORM relationship pra User (ADR-027 dec. 1).
    # lazy="raise" pattern projeto — força eager load explícito (selectinload).
    # Sem back_populates — User declara seu próprio relationship com lazy="raise".
    # overlaps="customer" linka este lado ao User.customer reverso sem
    # back_populates (silencia SAWarning sobre 2 relationships na mesma FK).
    user: Mapped["User"] = relationship("User", lazy="raise", overlaps="customer")

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
        return (
            f"<Customer id={self.id} user_id={self.user_id} phone={mask_phone_for_log(self.phone)}>"
        )
