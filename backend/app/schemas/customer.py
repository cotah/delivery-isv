"""Schemas Pydantic para Customer (ADR-027, ADR-020 layer: schema)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerRead(BaseModel):
    """Resposta para GET /api/v1/customers/me, POST /api/v1/customers,
    PATCH /api/v1/customers/me.

    Retorna perfil do Customer associado ao User autenticado.
    Endpoint protegido — só o dono do JWT vê seus próprios dados.

    Campos expostos (todos os do model exceto user_id que é detalhe interno
    e is_active que só backend controla — ADR-027 dec. 13).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="UUID do Customer.")
    phone: str = Field(
        ...,
        examples=["+5531999887766"],
        description="Telefone E.164 (vem do User automaticamente, ADR-027 dec. 6, imutável).",
    )
    name: str = Field(..., examples=["João da Silva"], description="Nome do cliente.")
    email: str | None = Field(
        None,
        examples=["joao@example.com"],
        description="Email opcional (MVP, ADR-027 dec. 12).",
    )
    cpf: str | None = Field(
        None,
        examples=["52998224725"],
        description="CPF opcional (11 dígitos sem máscara). Validado via @validates.",
    )
    birth_date: date | None = Field(
        None,
        examples=["1990-05-15"],
        description="Data de nascimento opcional.",
    )
    created_at: datetime = Field(..., description="Data e hora de criação do Customer.")
    updated_at: datetime = Field(..., description="Data e hora da última atualização.")


class CustomerCreate(BaseModel):
    """Body de POST /api/v1/customers (ADR-027 dec. 3).

    POST mínimo: apenas `name` é obrigatório. Email, cpf e birth_date são
    opcionais — cliente pode preencher tudo de uma vez ou só o mínimo.

    Phone NÃO entra no body — vem automaticamente do User logado
    (ADR-027 dec. 6: garante User.phone == Customer.phone).
    is_active também NÃO — só backend controla (ADR-027 dec. 13).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        examples=["João da Silva"],
        description="Nome do cliente. Único campo obrigatório no cadastro.",
    )
    email: str | None = Field(
        None,
        max_length=254,
        examples=["joao@example.com"],
        description="Email opcional, max 254 chars (RFC 5321).",
    )
    cpf: str | None = Field(
        None,
        examples=["52998224725"],
        description="CPF opcional, 11 dígitos sem máscara. Validado via @validates no model.",
    )
    birth_date: date | None = Field(
        None,
        examples=["1990-05-15"],
        description="Data de nascimento opcional.",
    )


class CustomerUpdate(BaseModel):
    """Body de PATCH /api/v1/customers/me (ADR-027 dec. 5).

    Todos campos opcionais — cliente atualiza só o que quer mudar.

    Service usa `model_dump(exclude_unset=True)` (ADR-027 dec. 8): distingue
    "campo não enviado" (mantém valor atual) de "campo enviado como null"
    (limpa o valor). Pattern Pydantic v2.

    NÃO permite atualizar:
    - phone (imutável após criação, ADR-027 dec. 7 — mudança vira fluxo OTP)
    - is_active (só backend, ADR-027 dec. 13)
    - id, user_id, timestamps (sistema)
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        None,
        min_length=1,
        max_length=150,
        examples=["João da Silva Santos"],
    )
    email: str | None = Field(
        None,
        max_length=254,
        examples=["novo-email@example.com"],
        description="Enviar null limpa o email cadastrado. Max 254 chars (RFC 5321).",
    )
    cpf: str | None = Field(
        None,
        examples=["52998224725"],
        description="Enviar null limpa o CPF cadastrado.",
    )
    birth_date: date | None = Field(
        None,
        examples=["1990-05-15"],
        description="Enviar null limpa a data cadastrada.",
    )
