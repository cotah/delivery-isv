"""Lógica de negócio de Store (ADR-020 layer: service)."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories import stores as stores_repository
from app.schemas.stores import StoreDetail, StoreListResponse, StoreRead


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
    """
    store = stores_repository.get_active_store(session, store_id)
    if store is None:
        return None
    return StoreDetail.model_validate(store)
