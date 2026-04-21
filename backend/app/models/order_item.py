from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK


class OrderItem(Base, TimestampMixin, SoftDeleteMixin):
    """Item de um pedido (ADR-003, ADR-007, ADR-014, ADR-015, ADR-016).

    Linha do pedido — cada ProductVariation escolhida pelo cliente vira um
    OrderItem. Se mesma variation for pedida 2x com customizações diferentes
    (ex: uma "sem cebola" e outra normal), vira 2 linhas distintas. Mesma
    variation repetida sem customização pode ser 1 linha com quantity=2. A
    decisão fica no frontend/service — schema não impede nem obriga.

    Relacionamentos (ADR-015, ADR-016):
    - order_id -> orders.id (CASCADE — composição estrita: se o pedido
      é hard-deletado, seus itens somem junto)
    - product_variation_id -> product_variations.id (RESTRICT — histórico
      preservado: variation soft-deletada depois não corrompe item já pedido)

    Snapshots (ADR-016):
    - product_name_snapshot: String(150) igual Product.name — nome exibido
      no comprovante, estável mesmo se a loja renomear o produto depois
    - variation_name_snapshot: String(100) igual ProductVariation.name
    - unit_price_cents: preço da variation congelado no momento do pedido

    Valores financeiros em cents (ADR-007) — todos NOT NULL com CHECK:
    - unit_price_cents >= 0
    - quantity >= 1 (não faz sentido quantidade 0 ou negativa)
    - line_total_cents >= 0 (fórmula: unit_price_cents * quantity; addons
      vêm em OrderItemAddon e somam fora desta linha)

    Sem UNIQUE em (order_id, product_variation_id): mesma variation pode
    aparecer 2x no pedido com notes diferentes — comportamento legítimo.
    """

    __tablename__ = "order_items"

    # Identidade
    id: Mapped[UUIDPK]

    # FKs (ADR-015: CASCADE em composição; ADR-016: RESTRICT em catálogo)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_variation_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_variations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Snapshots (ADR-016) — tamanhos alinhados com as colunas source
    product_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    variation_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    # Preço e quantidade (ADR-007)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    # Notes do item (opcional — "sem cebola", "massa fina", etc.)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="quantity_positive"),
        CheckConstraint("unit_price_cents >= 0", name="unit_price_cents_non_negative"),
        CheckConstraint("line_total_cents >= 0", name="line_total_cents_non_negative"),
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_product_variation_id", "product_variation_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrderItem id={self.id} order_id={self.order_id} "
            f"product_variation_id={self.product_variation_id} "
            f"quantity={self.quantity} line_total_cents={self.line_total_cents}>"
        )
