from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.types import UUIDPK


class ProductAddonGroup(Base, TimestampMixin):
    """Junção many-to-many entre Product e AddonGroup (ADR-014).

    Um produto pode ter vários grupos de adicionais aplicados
    (ex: Pizza Margherita tem "Bordas" E "Complementos").
    Um grupo pode ser reutilizado em vários produtos da mesma loja
    (ex: "Bordas" serve todas as pizzas da pizzaria).

    Ambos os FKs CASCADE (ADR-015): quando product OU group some,
    a ligação some junto automaticamente. Hard-delete seguro em
    ambos os lados.

    SEM SoftDeleteMixin — junção é registro de ligação, não entidade
    de domínio. Se lojista remove um grupo do produto, delete direto
    (sem histórico de ligação removida).

    sort_order: posição do grupo na UI do produto (ex: Bordas aparece
    antes de Complementos).

    unique constraint em (product_id, group_id): protege contra
    ligação duplicada (mesmo grupo aplicado 2x ao mesmo produto).
    """

    __tablename__ = "product_addon_groups"

    id: Mapped[UUIDPK]

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("addon_groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "group_id",
            name="uq_product_addon_groups_product_id_group_id",
        ),
        Index("ix_product_addon_groups_product_id", "product_id"),
        Index("ix_product_addon_groups_group_id", "group_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductAddonGroup product_id={self.product_id} "
            f"group_id={self.group_id} sort_order={self.sort_order}>"
        )
