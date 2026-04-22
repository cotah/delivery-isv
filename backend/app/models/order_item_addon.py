from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK


class OrderItemAddon(Base, TimestampMixin, SoftDeleteMixin):
    """Addon selecionado pelo cliente num OrderItem (ADR-003, ADR-007, ADR-014, ADR-015, ADR-016).

    Cada Addon escolhido pelo cliente pra um OrderItem específico vira uma
    linha em OrderItemAddon. Ex: pedido tem Pizza Margherita Média + borda
    Cheddar + borda Catupiry → 1 OrderItem + 2 OrderItemAddons.

    Relacionamentos (ADR-015, ADR-016):
    - order_item_id -> order_items.id (CASCADE — composição estrita: se
      o item do pedido é hard-deletado, seus addons somem junto)
    - addon_id -> addons.id (RESTRICT — histórico preservado: addon
      soft-deletado depois não corrompe pedido antigo)

    Snapshots (ADR-016):
    - addon_name_snapshot: String(100) igual Addon.name — nome exibido no
      comprovante, estável mesmo se o addon for renomeado depois
    - unit_price_cents: preço do addon congelado no momento do pedido

    Valores financeiros em cents (ADR-007) — CHECK unit_price_cents >= 0.
    Addon grátis (price_cents = 0) gera OrderItemAddon com unit_price_cents
    = 0, coerente com a regra do ADR-014 (grátis vs pago se distingue
    apenas pelo valor).

    Sem UNIQUE em (order_item_id, addon_id): cliente pode escolher o mesmo
    addon 2x no mesmo item (ex: 2 bordas cheddar) — schema não impede nem
    obriga. Decisão de UI/service.
    """

    __tablename__ = "order_item_addons"

    # Identidade
    id: Mapped[UUIDPK]

    # FKs (ADR-015: CASCADE em composição; ADR-016: RESTRICT em catálogo)
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    addon_id: Mapped[UUID] = mapped_column(
        ForeignKey("addons.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Snapshot (ADR-016) — tamanho alinhado com Addon.name
    addon_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    # Preço snapshot (ADR-007)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("unit_price_cents >= 0", name="unit_price_cents_non_negative"),
        Index("ix_order_item_addons_order_item_id", "order_item_id"),
        Index("ix_order_item_addons_addon_id", "addon_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrderItemAddon id={self.id} order_item_id={self.order_item_id} "
            f"addon_id={self.addon_id} unit_price_cents={self.unit_price_cents}>"
        )
