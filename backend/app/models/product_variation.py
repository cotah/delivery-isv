from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.domain.enums import ProductVariationStatus

# CHECK constraint gerada dinamicamente do enum (ADR-006, espelha _PRODUCT_STATUS_CHECK).
_VARIATION_STATUS_CHECK = (
    "status IN (" + ", ".join(f"'{s.value}'" for s in ProductVariationStatus) + ")"
)


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
    status: Mapped[ProductVariationStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ProductVariationStatus.ACTIVE,
        server_default=ProductVariationStatus.ACTIVE.value,
    )

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="price_cents_non_negative"),
        CheckConstraint(_VARIATION_STATUS_CHECK, name="status"),
        Index("ix_product_variations_product_id", "product_id"),
    )

    @validates("status")
    def _validate_status(
        self, _key: str, value: str | ProductVariationStatus
    ) -> ProductVariationStatus:
        """Defense-in-depth (ADR-010) — rejeita valores fora do enum em runtime.

        SQLAlchemy aceita string crua atribuída a Mapped[StrEnum]; @validates
        roda antes da persistência e levanta ValueError se valor inválido,
        sem chegar no CheckConstraint do banco.
        """
        if isinstance(value, ProductVariationStatus):
            return value
        try:
            return ProductVariationStatus(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid variation status: {value!r}. "
                f"Expected one of {[s.value for s in ProductVariationStatus]}"
            ) from exc

    def __repr__(self) -> str:
        return (
            f"<ProductVariation id={self.id} name={self.name!r} "
            f"price_cents={self.price_cents} status={self.status} "
            f"product_id={self.product_id}>"
        )
