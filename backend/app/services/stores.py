"""Lógica de negócio de Store (ADR-020 layer: service)."""

from datetime import datetime
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import HttpUrl
from sqlalchemy.orm import Session

from app.models.store import Store
from app.repositories import stores as stores_repository
from app.schemas.stores import (
    CategorySummary,
    CitySummary,
    StoreDetail,
    StoreListResponse,
    StoreOpeningHoursRead,
    StoreRead,
)

# Timezone hardcoded no MVP (ADR-026 dec. 2). Pattern de migração futura
# documentado no ADR pra quando ISV expandir pra outros fusos.
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def is_store_open(store: Store, dt: datetime) -> bool:
    """Verifica se a loja está aberta no datetime fornecido (ADR-026).

    Args:
        store: Store com `opening_hours` carregado (eager via selectinload).
        dt: datetime timezone-aware. Naive datetime levanta ValueError
            (ADR-026 reforço D5: crash explícito > bug silencioso).

    Returns:
        True se algum slot do `day_of_week` atual cobrir o time atual.
        False caso contrário (incluindo lojas sem opening_hours cadastrado).

    Lógica de cruzar meia-noite (ADR-026 dec. 3):
    - Slot 18h-02h: close_time < open_time
    - "Aberto" se time >= open_time OU time <= close_time

    Convenção DOW (ADR-026 reforço D1):
    - Postgres EXTRACT(DOW): 0=domingo..6=sábado
    - Conversão segura: dt.isoweekday() % 7 (NUNCA dt.weekday())

    NÃO cacheado (ADR-026 reforço D7). Recalculado a cada chamada.
    """
    if dt.tzinfo is None:
        raise ValueError(
            "is_store_open requires timezone-aware datetime. Use datetime.now(SAO_PAULO_TZ)."
        )

    # Converter pra fuso da loja (MVP: hardcoded São Paulo, ADR-026 dec. 2).
    dt_local = dt.astimezone(SAO_PAULO_TZ)

    # Postgres DOW: 0=domingo..6=sábado.
    # isoweekday: 1=segunda..7=domingo. % 7 → 1..6, 0 (domingo).
    day_of_week = dt_local.isoweekday() % 7
    current_time = dt_local.time()

    for slot in store.opening_hours:
        if slot.day_of_week != day_of_week:
            continue

        if slot.open_time <= slot.close_time:
            # Slot regular (não cruza meia-noite).
            if slot.open_time <= current_time <= slot.close_time:
                return True
        else:
            # Slot cruza meia-noite (close_time < open_time).
            if current_time >= slot.open_time or current_time <= slot.close_time:
                return True

    return False


def is_store_open_now(store: Store) -> bool:
    """Wrapper conveniente: verifica se loja está aberta AGORA (São Paulo)."""
    return is_store_open(store, datetime.now(SAO_PAULO_TZ))


def _build_store_detail(store: Store) -> StoreDetail:
    """Monta StoreDetail combinando campos do model + is_open_now computado.

    Pattern análogo a `_build_product_read` em services/products.py (CP1
    HIGH). Necessário porque is_open_now é calculado em runtime e não
    existe no model — model_validate puro não funciona.

    Requer store.opening_hours carregado (eager via selectinload no
    repository). Sem isso, lazy="raise" no model levanta InvalidRequestError.
    """
    # cast (HttpUrl): Pydantic coerce str -> HttpUrl em runtime, mypy precisa
    # do hint estático porque init_typed=True (pattern do CP1a, commit c3dfecc).
    # model_validate (Category/City): converte ORM model -> Pydantic schema
    # explicitamente (StoreDetail espera schemas, não models).
    return StoreDetail(
        id=store.id,
        name=store.trade_name,  # validation_alias trade_name -> name no schema
        slug=store.slug,
        description=store.description,
        phone=store.phone,
        minimum_order_cents=store.minimum_order_cents,
        cover_image=cast("HttpUrl | None", store.cover_image),
        logo=cast("HttpUrl | None", store.logo),
        street=store.street,
        number=store.number,
        complement=store.complement,
        neighborhood=store.neighborhood,
        zip_code=store.zip_code,
        category=CategorySummary.model_validate(store.category),
        city=CitySummary.model_validate(store.city),
        opening_hours=[StoreOpeningHoursRead.model_validate(s) for s in store.opening_hours],
        is_open_now=is_store_open_now(store),
    )


def list_active_stores(
    session: Session,
    offset: int,
    limit: int,
) -> StoreListResponse:
    """Lista lojas aprovadas no catálogo público.

    Magra por design — camada engorda quando entrar regras de
    negócio (filtros de disponibilidade por horário, geo-filtros,
    ranking de relevância).
    """
    items, total = stores_repository.list_active_stores(session, offset, limit)
    return StoreListResponse(
        items=[StoreRead.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


def get_store_detail(
    session: Session,
    store_id: UUID,
) -> StoreDetail | None:
    """Retorna detalhe da loja, ou None se não encontrada/inativa.

    None propagado pra route lidar com HTTPException 404. Layer magra —
    filtro de APPROVED + deleted_at IS NULL fica no repository.

    is_open_now computado em runtime via _build_store_detail (ADR-026
    reforço D7 — sem cache no MVP).
    """
    store = stores_repository.get_active_store(session, store_id)
    if store is None:
        return None
    return _build_store_detail(store)
