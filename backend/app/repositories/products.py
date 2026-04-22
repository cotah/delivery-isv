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

    Ordenação: Product.name ASC. Débito técnico HIGH:
    display_order/menu_section/featured em ciclo próprio.
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
        .order_by(Product.name.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
