"""Rotas HTTP de Store (ADR-020 layer: api, ADR-021 versioning)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.stores import StoreListQuery, StoreListResponse
from app.services import stores as stores_service

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get(
    "",
    response_model=StoreListResponse,
    summary="Listar lojas aprovadas",
    description=(
        "Retorna lojas com status=APPROVED, paginadas. Endpoint público — não exige autenticação."
    ),
)
def list_stores(
    query: Annotated[StoreListQuery, Depends()],
    session: Annotated[Session, Depends(get_db_session)],
) -> StoreListResponse:
    return stores_service.list_active_stores(
        session=session,
        offset=query.offset,
        limit=query.limit,
    )
