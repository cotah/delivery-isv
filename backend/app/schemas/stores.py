"""Schemas Pydantic pra endpoints de Store (ADR-020, ADR-022, ADR-023, ADR-026)."""

from datetime import time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CategorySummary(BaseModel):
    """Categoria resumida pra embed em listagens (ADR-020).

    display_order populado sequencialmente pela migration HIGH debt #2
    (ROW_NUMBER OVER ORDER BY created_at). Admin reorganiza depois pelo
    painel. Frontend pode usar pra ordenar lista de stores por categoria.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., examples=["Pizzaria"])
    slug: str = Field(..., examples=["pizzaria"])
    display_order: int = Field(..., ge=0, examples=[1])


class CitySummary(BaseModel):
    """Cidade resumida pra embed em listagens."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., examples=["Tarumirim"])
    state: str = Field(..., examples=["MG"])


class StoreRead(BaseModel):
    """Loja no catálogo público (ADR-020, ADR-022, ADR-024).

    validation_alias lê de obj.trade_name (ORM) mas serializa como 'name' no JSON
    pra API pública (pattern iFood/Rappi) — expõe nome comercial
    ('Pizzaria do Zé'), não razão social fiscal ('Pizzaria do Zé LTDA ME').
    Semântica fiscal preservada no modelo.

    Campos expostos:
    - id, name (=trade_name), slug: identidade pública
    - neighborhood: ajuda cliente decidir localização
    - logo: avatar pequeno na listagem (UX iFood/Rappi). HttpUrl validado (ADR-026 dec. 6).
    - minimum_order_cents: permite filtro/ordenação por pedido mínimo na lista (ADR-026 dec. 7).
    - category (aninhado): render direto sem N+1
    - city (aninhado): render direto sem N+1

    NÃO expostos aqui:
    - legal_name (razão social — dado fiscal)
    - tax_id, tax_id_type (PII fiscal — ADR-012)
    - street, number, complement, zip_code (endereço granular — detalhe
      vai em GET /stores/{id})
    - description, phone, cover_image (escopo da tela de detalhe — StoreDetail)
    - status (rota filtra APPROVED, implícito)
    - delivery_fee: taxa de entrega é calculada no checkout, não atributo
      da loja
    - timestamps
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., validation_alias="trade_name", examples=["Pizzaria do Zé"])
    slug: str = Field(..., examples=["pizzaria-do-ze"])
    neighborhood: str = Field(..., examples=["Centro"])
    logo: HttpUrl | None = Field(None, examples=["https://cdn.example.com/logo.png"])
    minimum_order_cents: int | None = Field(None, ge=0, examples=[2500])
    category: CategorySummary
    city: CitySummary


class StoreOpeningHoursRead(BaseModel):
    """Slot de horário de funcionamento (ADR-026 dec. 1, CP1b).

    Frontend agrupa por `day_of_week` pra exibir tabela/lista de horários.

    `day_of_week` segue convenção Postgres EXTRACT(DOW): 0=domingo..6=sábado
    (ADR-026 reforço D1). Cruzar meia-noite: `close_time < open_time`
    (ADR-026 dec. 3) — ex: pizzaria 18h-02h.
    """

    model_config = ConfigDict(from_attributes=True)

    day_of_week: int = Field(
        ...,
        ge=0,
        le=6,
        examples=[1],
        description="0=domingo..6=sábado (Postgres DOW). NÃO Python weekday().",
    )
    open_time: time = Field(..., examples=["11:00"])
    close_time: time = Field(..., examples=["23:00"])


class StoreDetail(BaseModel):
    """Detalhe da loja (ADR-022, ADR-024, ADR-026). Exposto em GET /stores/{id}.

    Expande StoreRead com endereço completo (street, number, complement, zip_code)
    e campos de negócio do CP1a do HIGH #1 (ADR-026): description, phone,
    minimum_order_cents, cover_image, logo. CP1b adicionou opening_hours +
    is_open_now (recalculado em runtime sem cache, ADR-026 reforço D7).

    Continua NÃO expondo:
    - legal_name (razão social — fiscal)
    - tax_id, tax_id_type (PII fiscal, ADR-012)
    - status (rota filtra APPROVED, implícito)
    - is_active (campo interno)
    - created_at, updated_at, deleted_at (timestamps internos)

    zip_code retornado crú (8 dígitos sem hífen) — frontend formata.
    phone retornado em E.164 (validado por @validates no model + validate_phone_e164).
    cover_image / logo: HttpUrl validados (ADR-026 dec. 6).
    opening_hours: lista vazia = sem horário cadastrado (ADR-026 dec. 4).
    is_open_now: bool calculado em runtime via is_store_open_now() (ADR-026 reforço D7).
    """

    # populate_by_name=True permite construtor direto usar `name=...` além do
    # validation_alias `trade_name` (necessário pro _build_store_detail no service).
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str = Field(..., validation_alias="trade_name", examples=["Pizzaria do Zé"])
    slug: str = Field(..., examples=["pizzaria-do-ze"])
    description: str | None = Field(
        None,
        max_length=2000,
        examples=["A melhor pizza de Tarumirim, massa fina e fermentação natural."],
    )
    phone: str = Field(..., examples=["+5531999887766"], description="Telefone E.164")
    minimum_order_cents: int | None = Field(None, ge=0, examples=[2500])
    cover_image: HttpUrl | None = Field(None, examples=["https://cdn.example.com/cover.jpg"])
    logo: HttpUrl | None = Field(None, examples=["https://cdn.example.com/logo.png"])
    street: str = Field(..., examples=["Rua das Flores"])
    number: str = Field(..., examples=["123"])
    complement: str | None = Field(None, examples=["Loja 2"])
    neighborhood: str = Field(..., examples=["Centro"])
    zip_code: str = Field(..., examples=["35855000"], description="CEP com 8 dígitos sem hífen")
    category: CategorySummary
    city: CitySummary
    opening_hours: list[StoreOpeningHoursRead] = Field(
        default_factory=list,
        description=(
            "Slots ordenados por (day_of_week, open_time). "
            "Lista vazia = sem horário cadastrado (ADR-026 dec. 4)."
        ),
    )
    is_open_now: bool = Field(
        ...,
        description="Calculado em runtime por GET (sem cache, ADR-026 reforço D7).",
    )


class StoreListQuery(BaseModel):
    """Query params de GET /stores (ADR-023)."""

    offset: int = Field(0, ge=0, examples=[0])
    limit: int = Field(20, ge=1, le=100, examples=[20])


class StoreListResponse(BaseModel):
    """Envelope paginado (ADR-023)."""

    items: list[StoreRead]
    total: int = Field(..., ge=0, examples=[42])
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
