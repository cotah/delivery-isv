from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.domain.enums import ProductStatus

if TYPE_CHECKING:
    from app.models.addon_group import AddonGroup
    from app.models.product_variation import ProductVariation
    from app.models.store import Store

# CHECK constraint gerada dinamicamente do enum (ADR-006)
_PRODUCT_STATUS_CHECK = "status IN (" + ", ".join(f"'{s.value}'" for s in ProductStatus) + ")"


class Product(Base, TimestampMixin, SoftDeleteMixin):
    """Produto do cardápio de uma Store (ADR-014).

    Produto BASE — preço real fica em ProductVariation (mesmo produto
    pode ter tamanhos com preços diferentes: Pizza P R$35, M R$45, G R$55).

    Se produto não tem variações (ex: coxinha unitária), cria 1 variation
    default "Único" com o preço do produto.

    Adicionais ficam em tabelas relacionadas (AddonGroup + Addon +
    ProductAddonGroup) conforme ADR-014.

    FK store_id com ondelete=RESTRICT (ADR-011): loja anonimizada/pausada
    não deleta produtos, preserva histórico de pedidos.

    Imagem: 1 URL por produto (image_url). Variations e addons reusam
    a imagem do produto pai (ADR-014).
    """

    __tablename__ = "products"

    id: Mapped[UUIDPK]

    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[ProductStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ProductStatus.ACTIVE,
        server_default=ProductStatus.ACTIVE.value,
    )

    preparation_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # ORM relationships — lazy="raise" obriga eager load explícito (selectinload).
    # N+1 vira bug detectável em vez de silencioso.
    store: Mapped["Store"] = relationship("Store", lazy="raise")
    variations: Mapped[list["ProductVariation"]] = relationship(
        "ProductVariation",
        lazy="raise",
    )
    addon_groups: Mapped[list["AddonGroup"]] = relationship(
        "AddonGroup",
        secondary="product_addon_groups",
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(_PRODUCT_STATUS_CHECK, name="status"),
        Index("ix_products_store_id", "store_id"),
        Index("ix_products_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Product id={self.id} name={self.name!r} "
            f"store_id={self.store_id} status={self.status}>"
        )
