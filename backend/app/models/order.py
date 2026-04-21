from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.identifiers import new_public_id
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.domain.enums import OrderStatus

# CHECK constraint gerada dinamicamente do enum (ADR-006)
_STATUS_CHECK = "status IN (" + ", ".join(f"'{s.value}'" for s in OrderStatus) + ")"


class Order(Base, TimestampMixin, SoftDeleteMixin):
    """Pedido de delivery (ADR-003, ADR-011, ADR-016, ADR-017, ADR-018).

    Entidade central do piloto ISV Delivery em Tarumirim/MG. Primeiro modelo
    do projeto com ciclo de vida não-trivial (máquina de estados em
    OrderStatus, ADR-017) e primeiro com snapshots granulares de dados
    relacionais (ADR-016).

    Identificação:
    - id (UUIDPK) pra integridade interna (ADR-003)
    - public_id "ISV-XXXXXXXX" exibido ao cliente/suporte (ADR-018 — 8 chars
      sobre alfabeto reduzido de 31 símbolos, gerado via new_public_id)

    Relacionamentos FK viva com RESTRICT (ADR-011):
    - customer_id -> customers.id
    - store_id -> stores.id

    Snapshots (ADR-016):
    - customer_name_snapshot: nome exibido no comprovante, mesmo que Customer
      mude de nome depois ou seja anonimizado
    - delivery_*_snapshot (7 campos): endereço textual congelado no momento
      do pedido, SEM FK pra Address — snapshot é fonte única da entrega

    Status (ADR-006 + ADR-017):
    - VARCHAR(20) com CHECK dinâmico reconstruído do StrEnum OrderStatus
    - 7 estados, transições validadas na service layer (ciclo futuro)

    Valores financeiros em cents (ADR-007):
    - subtotal, delivery_fee, service_fee (default 0), discount (default 0), total
    - total é campo materializado; fórmula evolui em service layer

    Pagamento (ADR-017 R3):
    - payment_gateway_transaction_id nullable com UNIQUE parcial
    - Rede de segurança contra webhooks duplicados do Pagar.me

    Timestamps de transição (ADR-017, padrão iFood) — queries rápidas sem
    JOIN com OrderStatusLog:
    - confirmed_at, delivered_at, canceled_at (todos nullable)

    ETA (ADR-017):
    - estimated_delivery_at calculado no backend quando pedido é criado
    """

    __tablename__ = "orders"

    # Identidade
    id: Mapped[UUIDPK]
    public_id: Mapped[str] = mapped_column(
        String(12),  # ADR-003: "ISV-" (4) + 8 chars sufixo = 12 total
        nullable=False,
        default=lambda: new_public_id("ISV"),
    )

    # FKs viva RESTRICT (ADR-011)
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Snapshot Customer (ADR-016)
    customer_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)

    # Snapshot Address textual completo (ADR-016) — 7 campos, sem FK
    delivery_address_line1_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    delivery_address_line2_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivery_neighborhood_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_city_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_state_snapshot: Mapped[str] = mapped_column(String(2), nullable=False)
    delivery_postal_code_snapshot: Mapped[str] = mapped_column(String(9), nullable=False)
    delivery_reference_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Status (ADR-006 + ADR-017)
    status: Mapped[OrderStatus] = mapped_column(
        String(20),
        nullable=False,
        default=OrderStatus.PENDING,
        server_default=OrderStatus.PENDING.value,
    )

    # Valores em cents (ADR-007 + ADR-017)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    service_fee_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    discount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    # Cupom snapshot (modelo Coupon em ciclo futuro)
    coupon_code_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Pagamento (ADR-017 R3)
    payment_gateway_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Notes do cliente
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps de transição críticos (ADR-017, padrão iFood) — além de TimestampMixin
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ETA (ADR-017)
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="status_valid"),
        CheckConstraint("subtotal_cents >= 0", name="subtotal_cents_non_negative"),
        CheckConstraint("delivery_fee_cents >= 0", name="delivery_fee_cents_non_negative"),
        CheckConstraint("service_fee_cents >= 0", name="service_fee_cents_non_negative"),
        CheckConstraint("discount_cents >= 0", name="discount_cents_non_negative"),
        CheckConstraint("total_cents >= 0", name="total_cents_non_negative"),
        UniqueConstraint("public_id", name="uq_orders_public_id"),
        Index(
            "uq_orders_payment_gateway_transaction_id",
            "payment_gateway_transaction_id",
            unique=True,
            postgresql_where=text("payment_gateway_transaction_id IS NOT NULL"),
        ),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_store_id", "store_id"),
        Index("ix_orders_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} public_id={self.public_id} "
            f"status={self.status} store_id={self.store_id} "
            f"total_cents={self.total_cents}>"
        )
