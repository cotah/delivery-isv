"""Rotas HTTP de Address (ADR-020 layer: api, ADR-021 versioning, ADR-027).

Endpoints sob /api/v1/customers/me/addresses (sub-router separado mas
prefix coerente com customers — addresses pertencem a customer logado):
- GET    /api/v1/customers/me/addresses             — lista
- POST   /api/v1/customers/me/addresses             — cria (201)
- PATCH  /api/v1/customers/me/addresses/{address_id} — atualiza
- DELETE /api/v1/customers/me/addresses/{address_id} — soft delete (204)

Todos exigem JWT (pattern get_current_user). Cliente sem Customer
cadastrado → 404 customer_not_found em qualquer endpoint (ADR-027 C/D).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.api.errors import ErrorCode, ErrorResponse
from app.models.user import User
from app.schemas.address import AddressCreate, AddressRead, AddressUpdate
from app.services import address as address_service
from app.services.address import (
    AddressNotFoundError,
    CityNotFoundError,
)
from app.services.customer import CustomerNotFoundError

router = APIRouter(prefix="/customers/me/addresses", tags=["addresses"])


def _raise_customer_not_found(exc: CustomerNotFoundError) -> None:
    """Helper: traduz CustomerNotFoundError → 404 (ADR-027 C/D)."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": ErrorCode.CUSTOMER_NOT_FOUND.value,
            "message": str(exc),
        },
    ) from exc


def _raise_city_not_found(exc: CityNotFoundError) -> None:
    """Helper: traduz CityNotFoundError → 422 (ADR-027 D5 — payload inválido)."""
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": ErrorCode.CITY_NOT_FOUND.value,
            "message": str(exc),
        },
    ) from exc


def _raise_address_not_found(exc: AddressNotFoundError) -> None:
    """Helper: traduz AddressNotFoundError → 404 (ADR-027 A — UUID opacity)."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": ErrorCode.ADDRESS_NOT_FOUND.value,
            "message": str(exc),
        },
    ) from exc


@router.get(
    "",
    response_model=list[AddressRead],
    status_code=status.HTTP_200_OK,
    summary="Lista endereços do customer autenticado",
    description=(
        "Endpoint protegido. Lista vazia retorna 200 com `[]` (ADR-027 E). "
        "Ordenação: is_default DESC, created_at DESC. "
        "404 `customer_not_found` se User ainda não fez POST /customers."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
        404: {"model": ErrorResponse, "description": "Customer ainda não cadastrado"},
    },
)
def list_my_addresses(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[AddressRead]:
    try:
        addresses = address_service.list_my_addresses(session, current_user)
    except CustomerNotFoundError as exc:
        _raise_customer_not_found(exc)
        raise  # unreachable — _raise sempre raise; appease mypy
    return [AddressRead.model_validate(a) for a in addresses]


@router.post(
    "",
    response_model=AddressRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria endereço novo pro customer autenticado",
    description=(
        "Endpoint protegido. POST com endereço completo. "
        "Se `is_default=true`, troca o default atual atomicamente (ADR-027 dec. 8). "
        "city_id deve existir (422 `city_not_found` se inválido — ADR-027 D5). "
        "404 `customer_not_found` se User ainda não fez POST /customers."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
        404: {"model": ErrorResponse, "description": "Customer ainda não cadastrado"},
        422: {
            "model": ErrorResponse,
            "description": "Validation falhou OU city_id inexistente",
        },
    },
)
def create_my_address(
    payload: AddressCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AddressRead:
    try:
        address = address_service.create_my_address(session, current_user, payload)
    except CustomerNotFoundError as exc:
        _raise_customer_not_found(exc)
        raise
    except CityNotFoundError as exc:
        _raise_city_not_found(exc)
        raise
    return AddressRead.model_validate(address)


@router.patch(
    "/{address_id}",
    response_model=AddressRead,
    status_code=status.HTTP_200_OK,
    summary="Atualiza endereço do customer autenticado",
    description=(
        "Endpoint protegido. PATCH com `exclude_unset=True` (ADR-027 dec. 8). "
        "Se `is_default=true`, troca o default atual atomicamente. "
        "404 `customer_not_found` se User ainda não fez POST /customers. "
        "404 `address_not_found` se address_id não existe OU pertence a outro "
        "customer (UUID opacity — ADR-027 A). "
        "422 `city_not_found` se city_id inexistente (ADR-027 D5)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
        404: {"model": ErrorResponse, "description": "Customer ou Address não encontrado"},
        422: {
            "model": ErrorResponse,
            "description": "Validation falhou OU city_id inexistente",
        },
    },
)
def update_my_address(
    address_id: UUID,
    payload: AddressUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AddressRead:
    try:
        address = address_service.update_my_address(
            session=session,
            user=current_user,
            address_id=address_id,
            payload=payload,
        )
    except CustomerNotFoundError as exc:
        _raise_customer_not_found(exc)
        raise
    except AddressNotFoundError as exc:
        _raise_address_not_found(exc)
        raise
    except CityNotFoundError as exc:
        _raise_city_not_found(exc)
        raise
    return AddressRead.model_validate(address)


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-deleta endereço do customer autenticado",
    description=(
        "Endpoint protegido. Soft-delete (deleted_at = now). DELETE de default "
        "NÃO auto-promove outro endereço (ADR-027 dec. 10 — cliente escolhe "
        "novo no próximo pedido). 204 No Content em sucesso. "
        "404 `customer_not_found` se User ainda não fez POST /customers. "
        "404 `address_not_found` se address_id não existe OU pertence a outro "
        "customer (UUID opacity — ADR-027 A)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
        404: {"model": ErrorResponse, "description": "Customer ou Address não encontrado"},
    },
)
def delete_my_address(
    address_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        address_service.delete_my_address(session, current_user, address_id)
    except CustomerNotFoundError as exc:
        _raise_customer_not_found(exc)
        raise
    except AddressNotFoundError as exc:
        _raise_address_not_found(exc)
        raise
    return None
