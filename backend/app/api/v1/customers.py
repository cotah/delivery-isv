"""Rotas HTTP de Customer (ADR-020 layer: api, ADR-021 versioning, ADR-027).

Endpoints:
- GET /api/v1/customers/me — perfil do User logado (404 se não cadastrou)
- POST /api/v1/customers — cria Customer (lazy creation, 409 se já existe)
- PATCH /api/v1/customers/me — atualiza name/email/cpf/birth_date

Todos exigem JWT (pattern get_current_user do CP4 Auth).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.api.errors import ErrorCode, ErrorResponse
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services import customer as customer_service
from app.services.customer import (
    CustomerAlreadyExistsError,
    CustomerNotFoundError,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get(
    "/me",
    response_model=CustomerRead,
    status_code=status.HTTP_200_OK,
    summary="Retorna perfil do Customer do usuário autenticado",
    description=(
        "Endpoint protegido. Requer header `Authorization: Bearer <jwt>`. "
        "Retorna perfil do Customer associado ao User logado. "
        "Retorna 404 `customer_not_found` se User ainda não fez "
        "POST /customers (lazy creation, ADR-027 dec. 2). "
        "Frontend roteia 404 → tela de cadastro."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
        404: {"model": ErrorResponse, "description": "Customer ainda não cadastrado"},
    },
)
def get_my_customer(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CustomerRead:
    try:
        customer = customer_service.get_customer_for_user(session, current_user)
    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CUSTOMER_NOT_FOUND.value,
                "message": str(exc),
            },
        ) from exc
    return CustomerRead.model_validate(customer)


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria perfil de Customer pro usuário autenticado",
    description=(
        "Endpoint protegido. Requer header `Authorization: Bearer <jwt>`. "
        "Cria Customer associado ao User logado (lazy creation, ADR-027 dec. 2). "
        "POST mínimo: apenas `name` obrigatório (ADR-027 dec. 3). "
        "Phone vem automaticamente do User logado (ADR-027 dec. 6, imutável). "
        "Retorna 201 com Customer completo. "
        "Retorna 409 `customer_already_exists` se User já tem Customer "
        "(ADR-027 dec. 4 — frontend redireciona pra tela de perfil)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
        409: {"model": ErrorResponse, "description": "Customer já existe pra este User"},
        422: {"model": ErrorResponse, "description": "Validation falhou (name vazio, etc.)"},
    },
)
def create_my_customer(
    payload: CustomerCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CustomerRead:
    try:
        customer = customer_service.create_customer_for_user(
            session=session,
            user=current_user,
            payload=payload,
        )
    except CustomerAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ErrorCode.CUSTOMER_ALREADY_EXISTS.value,
                "message": str(exc),
            },
        ) from exc
    return CustomerRead.model_validate(customer)


@router.patch(
    "/me",
    response_model=CustomerRead,
    status_code=status.HTTP_200_OK,
    summary="Atualiza perfil do Customer do usuário autenticado",
    description=(
        "Endpoint protegido. Requer header `Authorization: Bearer <jwt>`. "
        "Atualiza apenas name/email/cpf/birth_date (ADR-027 dec. 5). "
        "Phone NÃO atualizável (imutável, ADR-027 dec. 7). "
        "Pattern `exclude_unset=True` (ADR-027 dec. 8): omitir campo no JSON "
        "mantém valor atual; enviar `null` explícito limpa o valor. "
        "Retorna 404 `customer_not_found` se User ainda não fez POST."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
        404: {"model": ErrorResponse, "description": "Customer ainda não cadastrado"},
        422: {"model": ErrorResponse, "description": "Validation falhou (email/cpf inválido)"},
    },
)
def update_my_customer(
    payload: CustomerUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CustomerRead:
    try:
        customer = customer_service.update_customer_for_user(
            session=session,
            user=current_user,
            payload=payload,
        )
    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CUSTOMER_NOT_FOUND.value,
                "message": str(exc),
            },
        ) from exc
    return CustomerRead.model_validate(customer)
