"""Rotas HTTP de Store (ADR-020 layer: api, ADR-021 versioning)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.errors import ErrorCode, ErrorResponse
from app.schemas.stores import StoreDetail, StoreListQuery, StoreListResponse
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


@router.get(
    "/{store_id}",
    response_model=StoreDetail,
    summary="Detalhe de uma loja",
    description=(
        "Retorna detalhe completo de uma loja aprovada. "
        "Retorna 404 se loja não existe, não está aprovada ou foi removida. "
        "Retorna 422 se store_id não for UUID válido. "
        "Endpoint público — não exige autenticação."
    ),
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Loja não encontrada",
        },
        422: {
            "model": ErrorResponse,
            "description": "store_id inválido (não é UUID)",
        },
    },
)
def get_store(
    store_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> StoreDetail:
    store = stores_service.get_store_detail(session=session, store_id=store_id)
    if store is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.STORE_NOT_FOUND.value,
                "message": "Loja não encontrada",
            },
        )
    return store
