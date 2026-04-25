from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.domain.enums import MenuSection, ProductStatus

if TYPE_CHECKING:
    from app.models.addon_group import AddonGroup
    from app.models.product_variation import ProductVariation
    from app.models.store import Store

# CHECK constraints geradas dinamicamente dos enums (ADR-006).
# Padrão _<TABLE>_<COLUMN>_CHECK pra constantes module-level.
_PRODUCT_STATUS_CHECK = "status IN (" + ", ".join(f"'{s.value}'" for s in ProductStatus) + ")"
_PRODUCT_MENU_SECTION_CHECK = (
    "menu_section IN (" + ", ".join(f"'{s.value}'" for s in MenuSection) + ")"
)


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

    # Organização do cardápio (HIGH debt #2, 2026-04-26).
    # display_order: posição dentro do menu da loja (lojista define no painel).
    # menu_section: seção pra agrupamento no frontend (D5: frontend agrupa).
    # featured: destaque no topo (similar "em promoção" do iFood).
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    menu_section: Mapped[MenuSection] = mapped_column(
        String(20),
        nullable=False,
        default=MenuSection.OTHER,
        server_default=MenuSection.OTHER.value,
    )
    featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
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
        CheckConstraint(_PRODUCT_MENU_SECTION_CHECK, name="menu_section"),
        Index("ix_products_store_id", "store_id"),
        Index("ix_products_status", "status"),
    )

    @validates("menu_section")
    def _validate_menu_section(self, _key: str, value: str | MenuSection) -> MenuSection:
        """Defense-in-depth ADR-010: rejeita valor inválido antes do flush.

        Aceita instância de MenuSection direto OU string crua válida.
        Pattern espelha _validate_status em ProductVariation (CP1 HIGH).
        """
        if isinstance(value, MenuSection):
            return value
        try:
            return MenuSection(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid menu section: {value!r}. Expected one of {[s.value for s in MenuSection]}"
            ) from exc

    def __repr__(self) -> str:
        return (
            f"<Product id={self.id} name={self.name!r} "
            f"store_id={self.store_id} status={self.status} "
            f"section={self.menu_section} order={self.display_order} "
            f"featured={self.featured}>"
        )
