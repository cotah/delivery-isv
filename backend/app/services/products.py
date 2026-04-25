"""Lógica de negócio do cardápio (ADR-020 layer: service, ADR-024)."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.enums import ProductStatus, ProductVariationStatus
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

    is_available do Product (HIGH debt #3 resolvido em 2026-04-26):
    - Product.status deve ser ACTIVE
    - SE Product tem variations cadastradas, pelo menos 1 deve estar ACTIVE
      (caso contrário é_available=false — sem variation selecionável)
    - SE Product tem 0 variations cadastradas (estado anômalo de configuração),
      preserva is_available=true — backward compat com testes do CP3 catálogo.
      Frontend lida com produto sem variation (FK NOT NULL em OrderItem
      bloqueia compra de qualquer forma).

    Variations INACTIVE filtradas DO RESPONSE (não aparecem no array).
    Variations soft-deleted também filtradas.
    """
    active_variations = [
        v
        for v in product.variations
        if v.deleted_at is None and v.status == ProductVariationStatus.ACTIVE
    ]

    is_product_available = product.status == ProductStatus.ACTIVE and (
        not product.variations or len(active_variations) > 0
    )

    # Variation.is_available HERDA do Product.status (UX: produto OUT_OF_STOCK
    # mostra variations acinzentadas, mesmo sendo ACTIVE em si). Variations
    # INACTIVE já foram filtradas — não aparecem no array. Lógica preserva
    # contrato do CP3 catálogo (variation reflete estado do produto pai pra UX)
    # E adiciona filtro do toggle individual (CP1 ciclo Débitos HIGH).
    variations_summaries = [
        ProductVariationSummary(
            id=v.id,
            name=v.name,
            price_cents=v.price_cents,
            is_available=(product.status == ProductStatus.ACTIVE),
        )
        for v in sorted(active_variations, key=lambda x: (x.sort_order, x.name))
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
