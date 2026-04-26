"""Schemas Pydantic para Address (ADR-027 dec. 8-10, ADR-020 layer: schema)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AddressType


class AddressRead(BaseModel):
    """Resposta para GET /api/v1/customers/me/addresses, POST/PATCH single,
    e itens da lista.

    Expõe TODOS os 16 campos do model (cliente quer ver tudo do endereço
    de entrega cadastrado), exceto deleted_at (campo interno de soft-delete).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="UUID do Address.")
    customer_id: UUID = Field(..., description="UUID do Customer dono.")
    city_id: UUID = Field(..., description="UUID da City.")
    address_type: AddressType = Field(
        ...,
        examples=[AddressType.HOME],
        description="Tipo: home, work ou other (ADR-006).",
    )
    is_default: bool = Field(
        ...,
        examples=[False],
        description="Se este é o endereço default do customer (ADR-027 dec. 8).",
    )
    street: str = Field(..., examples=["Rua das Flores"])
    number: str = Field(..., examples=["123"])
    complement: str | None = Field(None, examples=["Apto 401"])
    neighborhood: str = Field(..., examples=["Centro"])
    zip_code: str = Field(
        ...,
        examples=["35855000"],
        description="CEP com 8 dígitos sem hífen.",
    )
    reference_point: str | None = Field(
        None,
        examples=["Próximo à praça"],
        description="Ponto de referência opcional pra o entregador.",
    )
    latitude: Decimal | None = Field(
        None,
        examples=["-19.6411"],
        description="Latitude geocoded (NUMERIC(10,7)). Frontend envia via Google Maps.",
    )
    longitude: Decimal | None = Field(
        None,
        examples=["-42.7544"],
        description="Longitude geocoded (NUMERIC(10,7)). Frontend envia via Google Maps.",
    )
    created_at: datetime = Field(..., description="Data/hora de criação.")
    updated_at: datetime = Field(..., description="Data/hora da última atualização.")


class AddressCreate(BaseModel):
    """Body de POST /api/v1/customers/me/addresses (ADR-027 dec. 8-9).

    Cliente cadastra endereço de entrega. Pode marcar is_default=true (service
    troca o default existente atomicamente) OU is_default=false (Address sem
    default permitido — ADR-027 dec. 9).

    customer_id NÃO entra no body — vem do User logado (current_user.customer.id).
    """

    model_config = ConfigDict(extra="forbid")

    city_id: UUID = Field(
        ...,
        description="UUID da City. Validado pelo service (422 se inexistente).",
    )
    address_type: AddressType = Field(
        ...,
        examples=[AddressType.HOME],
        description="Tipo do endereço: home, work ou other.",
    )
    is_default: bool = Field(
        False,
        description="Se true, troca o default atual atomicamente (ADR-027 dec. 8).",
    )
    street: str = Field(..., min_length=1, max_length=200, examples=["Rua das Flores"])
    number: str = Field(..., min_length=1, max_length=20, examples=["123"])
    complement: str | None = Field(None, max_length=100, examples=["Apto 401"])
    neighborhood: str = Field(..., min_length=1, max_length=100, examples=["Centro"])
    zip_code: str = Field(
        ...,
        min_length=8,
        max_length=8,
        pattern=r"^\d{8}$",
        examples=["35855000"],
        description="CEP 8 dígitos sem hífen.",
    )
    reference_point: str | None = Field(None, max_length=200, examples=["Próximo à praça"])
    latitude: Decimal | None = Field(None, examples=["-19.6411"])
    longitude: Decimal | None = Field(None, examples=["-42.7544"])


class AddressUpdate(BaseModel):
    """Body de PATCH /api/v1/customers/me/addresses/{id} (ADR-027 dec. 5, 8).

    Todos campos opcionais. Service usa `model_dump(exclude_unset=True)`
    pra distinguir "não enviado" (mantém) de "null explícito" (limpa).

    Campo is_default tem semântica especial:
    - Não enviado: mantém valor atual
    - Enviado como true: troca o default atual atomicamente (ADR-027 dec. 8)
    - Enviado como false: Address fica sem flag default (ADR-027 dec. 9 — pode
      acabar sem nenhum default; cliente escolhe novo no próximo pedido).

    NÃO permite atualizar:
    - id, customer_id, timestamps, deleted_at (sistema)
    """

    model_config = ConfigDict(extra="forbid")

    city_id: UUID | None = Field(None)
    address_type: AddressType | None = Field(None, examples=[AddressType.HOME])
    is_default: bool | None = Field(None)
    street: str | None = Field(None, min_length=1, max_length=200)
    number: str | None = Field(None, min_length=1, max_length=20)
    complement: str | None = Field(None, max_length=100)
    neighborhood: str | None = Field(None, min_length=1, max_length=100)
    zip_code: str | None = Field(None, min_length=8, max_length=8, pattern=r"^\d{8}$")
    reference_point: str | None = Field(None, max_length=200)
    latitude: Decimal | None = Field(None)
    longitude: Decimal | None = Field(None)
