"""Queries ORM de Product (ADR-020 layer: repository, ADR-014)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import ProductStatus
from app.models.addon_group import AddonGroup
from app.models.product import Product


def list_store_products(
    session: Session,
    store_id: UUID,
    limit: int,
) -> list[Product]:
    """Lista produtos de uma loja, com eager loading em cadeia (ADR-014).

    Filtros SQL:
    - store_id = store_id
    - status != PAUSED (mantém ACTIVE + OUT_OF_STOCK)
    - deleted_at IS NULL

    Eager loads:
    - Product.variations (filtro por deleted_at aplicado no service)
    - Product.addon_groups via M:N (secondary=product_addon_groups)
    - Product.addon_groups -> AddonGroup.addons (cadeia)

    Ordenação (HIGH debt #2, 2026-04-26): featured DESC, display_order ASC,
    name ASC. featured=True vem primeiro (Boolean.desc() = TRUE > FALSE).
    display_order é INT ASC (lojista define no painel admin futuro).
    name ASC é tiebreaker determinístico quando featured/display_order
    empatam (rows pré-existentes têm featured=False e display_order=0).
    Frontend agrupa o response plano por menu_section (D5).
    """
    stmt = (
        select(Product)
        .where(
            Product.store_id == store_id,
            Product.status != ProductStatus.PAUSED,
            Product.deleted_at.is_(None),
        )
        .options(
            selectinload(Product.variations),
            selectinload(Product.addon_groups).selectinload(AddonGroup.addons),
        )
        .order_by(
            Product.featured.desc(),
            Product.display_order.asc(),
            Product.name.asc(),
        )
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
