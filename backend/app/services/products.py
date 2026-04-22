"""Lógica de negócio do cardápio (ADR-020 layer: service, ADR-024)."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.enums import ProductStatus
from app.repositories import products as products_repository
from app.repositories import stores as stores_repository
from app.schemas.products import (
    AddonGroupSummary,
    AddonSummary,
    ProductListResponse,
    ProductRead,
    ProductVariationSummary,
)

if TYPE_CHECKING:
    from app.models.addon_group import AddonGroup
    from app.models.product import Product


def _build_addon_group_summary(group: "AddonGroup") -> AddonGroupSummary | None:
    """Monta AddonGroupSummary com addons ordenados e filtrados.

    Retorna None se grupo estiver soft-deleted (caller filtra).
    Addons soft-deletados são descartados; ordenação por
    (sort_order, name) dá posição estável mesmo com sort_order repetido.
    """
    if group.deleted_at is not None:
        return None

    addons_summaries = [
        AddonSummary.model_validate(a)
        for a in sorted(group.addons, key=lambda x: (x.sort_order, x.name))
        if a.deleted_at is None
    ]
    return AddonGroupSummary(
        id=group.id,
        name=group.name,
        type=group.type,
        min_selections=group.min_selections,
        max_selections=group.max_selections,
        addons=addons_summaries,
    )


def _build_product_read(product: "Product") -> ProductRead:
    """Monta ProductRead com aninhamento + is_available calculado.

    is_available herdado nas variations a partir do status do produto pai
    (débito documentado: toggle fino por variation exige
    ProductVariationStatus em ciclo próprio).
    """
    is_product_available = product.status == ProductStatus.ACTIVE

    variations_summaries = [
        ProductVariationSummary(
            id=v.id,
            name=v.name,
            price_cents=v.price_cents,
            is_available=is_product_available,
        )
        for v in sorted(product.variations, key=lambda x: (x.sort_order, x.name))
        if v.deleted_at is None
    ]

    groups_raw_sorted = sorted(
        product.addon_groups,
        key=lambda g: (g.sort_order, g.name),
    )
    addon_groups_summaries = [
        summary
        for summary in (_build_addon_group_summary(g) for g in groups_raw_sorted)
        if summary is not None
    ]

    return ProductRead(
        id=product.id,
        name=product.name,
        description=product.description,
        image_url=product.image_url,
        preparation_minutes=product.preparation_minutes,
        is_available=is_product_available,
        variations=variations_summaries,
        addon_groups=addon_groups_summaries,
    )


def list_store_products(
    session: Session,
    store_id: UUID,
    limit: int,
) -> ProductListResponse | None:
    """Lista cardápio de loja aprovada, aninhado 3 níveis.

    Retorna None se store não existe, não está aprovada ou foi soft-deletada —
    route converte pra 404 store_not_found.
    """
    store = stores_repository.get_active_store(session, store_id)
    if store is None:
        return None

    products = products_repository.list_store_products(session, store_id, limit)
    items = [_build_product_read(p) for p in products]
    return ProductListResponse(items=items, total=len(items))
