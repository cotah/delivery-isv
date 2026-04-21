from uuid import UUID

from sqlalchemy import (
    Boolean,
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


class Addon(Base, TimestampMixin, SoftDeleteMixin):
    """Opção dentro de um AddonGroup (ADR-014).

    Exemplos:
    - Borda Cheddar (R$ 5, pago)
    - Borda Catupiry (R$ 5, pago)
    - Banana (grátis = price_cents 0)
    - Granola extra (R$ 2, pago)

    price_cents = 0 significa addon grátis (incluído no produto
    base — ex: primeira fruta do açaí).
    price_cents > 0 significa addon que cobra extra.

    FK group_id CASCADE (ADR-015): composição estrita — deletar
    AddonGroup remove todos os Addons dele.

    is_available: controla se addon aparece pra seleção. Diferente
    de deleted_at (soft delete permanente) — is_available é "em
    falta temporariamente".
    """

    __tablename__ = "addons"

    id: Mapped[UUIDPK]

    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("addon_groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        CheckConstraint(
            "price_cents >= 0",
            name="price_cents_non_negative",
        ),
        Index("ix_addons_group_id", "group_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Addon id={self.id} name={self.name!r} "
            f"price_cents={self.price_cents} available={self.is_available}>"
        )
