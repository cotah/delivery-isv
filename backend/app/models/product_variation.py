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


class ProductVariation(Base, TimestampMixin, SoftDeleteMixin):
    """Variação de um Product (ADR-014).

    Ex: Pizza Margherita tem 3 variations (P R$35, M R$45, G R$55).
    Açaí tem 3 variations (300ml, 500ml, 700ml) com preços diferentes.

    Se produto não tem variação real, lojista cria 1 variation única
    (ex: "Único" com o preço do item).

    FK product_id com ondelete=CASCADE (ADR-015): composição estrita —
    deletar Product remove Variations junto.

    Preço em _cents INTEGER (ADR-007 aplicado pela primeira vez em
    modelo real de negócio).

    is_default: marca a variation padrão exibida primeiro na UI.
    Lojista garante 1 default por produto via camada de aplicação
    (sem UNIQUE parcial aqui — não é crítico; UX ruim se 2 default
    mas não quebra sistema).
    """

    __tablename__ = "product_variations"

    id: Mapped[UUIDPK]

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="price_cents_non_negative"),
        Index("ix_product_variations_product_id", "product_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductVariation id={self.id} name={self.name!r} "
            f"price_cents={self.price_cents} product_id={self.product_id}>"
        )
