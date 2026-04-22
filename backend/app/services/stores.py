"""Lógica de negócio de Store (ADR-020 layer: service)."""

from sqlalchemy.orm import Session

from app.repositories import stores as stores_repository
from app.schemas.stores import StoreListResponse, StoreRead


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
