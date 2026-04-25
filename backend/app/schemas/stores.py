"""Schemas Pydantic pra endpoints de Store (ADR-020, ADR-022, ADR-023)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    - category (aninhado): render direto sem N+1
    - city (aninhado): render direto sem N+1

    NÃO expostos aqui:
    - legal_name (razão social — dado fiscal)
    - tax_id, tax_id_type (PII fiscal — ADR-012)
    - street, number, complement, zip_code (endereço granular — detalhe
      vai em GET /stores/{id})
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
    category: CategorySummary
    city: CitySummary


class StoreDetail(BaseModel):
    """Detalhe da loja (ADR-022, ADR-024). Exposto em GET /stores/{id}.

    Expande StoreRead com endereço completo (street, number, complement, zip_code).
    Campos de negócio (description, opening_hours, minimum_order, cover_image, phone)
    NÃO existem no modelo Store atual — débito técnico documentado, ciclo próprio
    antes do piloto. Por ora detalhe expande apenas endereço granular.

    Continua NÃO expondo:
    - legal_name (razão social — fiscal)
    - tax_id, tax_id_type (PII fiscal, ADR-012)
    - status (rota filtra APPROVED, implícito)
    - is_active (campo interno)
    - created_at, updated_at, deleted_at (timestamps internos)

    zip_code retornado crú (8 dígitos sem hífen) — frontend formata.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., validation_alias="trade_name", examples=["Pizzaria do Zé"])
    slug: str = Field(..., examples=["pizzaria-do-ze"])
    street: str = Field(..., examples=["Rua das Flores"])
    number: str = Field(..., examples=["123"])
    complement: str | None = Field(None, examples=["Loja 2"])
    neighborhood: str = Field(..., examples=["Centro"])
    zip_code: str = Field(..., examples=["35855000"], description="CEP com 8 dígitos sem hífen")
    category: CategorySummary
    city: CitySummary


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
