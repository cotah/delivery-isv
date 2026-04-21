from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.domain.enums import AddressType

# CHECK constraint string gerada a partir do enum (ADR-006)
# Fonte única de verdade: se AddressType ganhar valor novo, CHECK atualiza junto
_ADDRESS_TYPE_CHECK = "address_type IN (" + ", ".join(f"'{t.value}'" for t in AddressType) + ")"


class Address(Base, TimestampMixin, SoftDeleteMixin):
    """Endereço de entrega de um Customer.

    Relacionamentos:
    - customer_id → customers.id (ondelete RESTRICT — força anonimização)
    - city_id → cities.id (ondelete RESTRICT — força uso de is_active=false em vez de delete)

    Coordenadas (latitude, longitude) preenchidas via Google Maps Geocoding
    quando o endereço é cadastrado. Nullable porque geocoding pode falhar
    temporariamente.

    is_default: banco garante no máximo um endereço default por customer
    ativo (via UNIQUE parcial em customer_id WHERE is_default=true AND
    deleted_at IS NULL). Aplicação deve primeiro desmarcar o default
    antigo antes de marcar o novo (ADR-011).
    """

    __tablename__ = "addresses"

    id: Mapped[UUIDPK]

    # FKs (ADR-011)
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    city_id: Mapped[UUID] = mapped_column(
        ForeignKey("cities.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Tipo (ADR-006 — VARCHAR + StrEnum + CHECK)
    address_type: Mapped[AddressType] = mapped_column(
        String(10),
        nullable=False,
    )

    # Flag de endereço principal
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Endereço textual
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    complement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    neighborhood: Mapped[str] = mapped_column(String(100), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(8), nullable=False)
    reference_point: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Coordenadas (ADR-011 — NUMERIC(10, 7) com ~1cm de precisão)
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )

    __table_args__ = (
        # CHECK constraint validando address_type (defense-in-depth com StrEnum)
        # Nome final aplicado pela naming_convention: ck_addresses_address_type
        CheckConstraint(
            _ADDRESS_TYPE_CHECK,
            name="address_type",
        ),
        # UNIQUE parcial: só 1 endereço default por customer ativo (ADR-011)
        Index(
            "uq_addresses_customer_default",
            "customer_id",
            unique=True,
            postgresql_where="is_default = true AND deleted_at IS NULL",
        ),
        # Índices pra lookup rápido (FKs frequentemente consultadas)
        Index("ix_addresses_customer_id", "customer_id"),
        Index("ix_addresses_city_id", "city_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Address id={self.id} customer_id={self.customer_id} "
            f"type={self.address_type} default={self.is_default}>"
        )
