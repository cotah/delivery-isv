"""Rotas HTTP de Store (ADR-020 layer: api, ADR-021 versioning)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.errors import ErrorCode, ErrorResponse
from app.schemas.products import ProductListResponse
from app.schemas.stores import StoreDetail, StoreListQuery, StoreListResponse
from app.services import products as products_service
from app.services import stores as stores_service

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get(
    "",
    response_model=StoreListResponse,
    summary="Listar lojas aprovadas",
    description=(
        "Retorna lojas com status=APPROVED, paginadas. "
        "Cada item expõe identidade pública + logo + minimum_order_cents pra UX "
        "de listagem (ADR-026). Detalhes completos (description, phone, "
        "cover_image, endereço granular) ficam em GET /stores/{id}. "
        "Endpoint público — não exige autenticação."
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
        "Retorna detalhe completo de uma loja aprovada — identidade pública, "
        "endereço granular, descrição, telefone E.164, pedido mínimo, "
        "cover_image, logo (ADR-026 dec. 6: HttpUrl validado). "
        "opening_hours: lista de slots ordenados por (day_of_week, open_time). "
        "Lista vazia = sem horário cadastrado (ADR-026 dec. 4). "
        "is_open_now: bool calculado em runtime (sem cache no MVP — "
        "ADR-026 reforço D7; plano de Redis quando latência for problema). "
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


@router.get(
    "/{store_id}/products",
    response_model=ProductListResponse,
    summary="Cardápio da loja",
    description=(
        "Retorna o cardápio completo da loja aprovada, com produtos, variações e "
        "adicionais aninhados. Produtos PAUSED ficam escondidos. Produtos "
        "OUT_OF_STOCK aparecem com is_available=false. Variations INACTIVE "
        "(toggle individual) são filtradas do response — produto com todas "
        "variations INACTIVE vira is_available=false. Ordenação dos produtos: "
        "featured DESC, display_order ASC, name ASC (HIGH debt #2). Frontend "
        "agrupa por menu_section (campo enum no item). Não pagina "
        "tradicionalmente — query param `limit` (default 500, max 1000) "
        "como limite de segurança. "
        "Retorna 404 se loja não existe, não está aprovada ou foi removida. "
        "Endpoint público — não exige autenticação."
    ),
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Loja não encontrada",
        },
        422: {
            "model": ErrorResponse,
            "description": "store_id inválido ou limit fora de faixa",
        },
    },
)
def list_store_products_endpoint(
    store_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> ProductListResponse:
    result = products_service.list_store_products(
        session=session,
        store_id=store_id,
        limit=limit,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.STORE_NOT_FOUND.value,
                "message": "Loja não encontrada",
            },
        )
    return result
