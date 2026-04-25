"""Rotas HTTP de usuários (ADR-020 layer: api, ADR-021 versioning, ADR-025)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.api.errors import ErrorResponse
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Retorna dados do usuário autenticado",
    description=(
        "Endpoint protegido. Requer header `Authorization: Bearer <jwt>`. "
        "Retorna dados do User correspondente ao JWT validado. "
        "Cliente identifica o usuário logado e exibe perfil/dashboard."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, expirado ou inválido"},
    },
)
def get_current_user_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
