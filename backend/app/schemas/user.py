"""Schemas Pydantic para User (ADR-025, ADR-020 layer: schema)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    """Resposta para GET /api/v1/users/me e endpoints similares.

    Retorna dados do User autenticado. Endpoint protegido por get_current_user
    — usuário só vê seu próprio perfil. Phone exposto em claro (User está
    consultando seu próprio dado, não há vazamento — pattern OAuth2 padrão).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(
        ...,
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
        description="UUID do User.",
    )
    phone: str = Field(
        ...,
        examples=["+5531999887766"],
        description="Telefone E.164 do User. Mesmo formato armazenado no banco.",
    )
    created_at: datetime = Field(
        ...,
        description="Data e hora de criação do User (lazy creation no primeiro verify-otp).",
    )
    updated_at: datetime = Field(
        ...,
        description="Data e hora da última atualização do User.",
    )
