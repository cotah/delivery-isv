"""Schemas Pydantic do cardápio público (ADR-020, ADR-024).

Árvore de 3 níveis (Product → Variation/AddonGroup → Addon) reflete o modelo
de domínio ADR-014. Respostas são serializadas pelo service em vez de direto
do ORM pra suportar filtros por deleted_at e cálculo de is_available (status
não exposto cru)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AddonSummary(BaseModel):
    """Addon individual (folha da árvore do cardápio, ADR-020)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., examples=["Cheddar Extra"])
    price_cents: int = Field(..., ge=0, examples=[500])
    is_available: bool = Field(..., examples=[True])


class AddonGroupSummary(BaseModel):
    """Grupo de adicionais aplicável a um produto (ADR-020).

    type indica se é escolha única (single) ou múltipla (multiple).
    min_selections/max_selections controlam obrigatoriedade e limite.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., examples=["Borda"])
    type: str = Field(..., examples=["single"], description="single ou multiple")
    min_selections: int = Field(..., ge=0, examples=[0])
    max_selections: int = Field(..., ge=1, examples=[1])
    addons: list[AddonSummary]


class ProductVariationSummary(BaseModel):
    """Variação do produto (tamanho, por exemplo). ADR-020.

    is_available herdado do produto pai: produto ACTIVE → variação available,
    produto OUT_OF_STOCK → variação não-available.
    Débito técnico HIGH: toggle individual via ProductVariationStatus.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., examples=["Grande"])
    price_cents: int = Field(..., ge=0, examples=[6200])
    is_available: bool = Field(..., examples=[True])


class ProductRead(BaseModel):
    """Produto do cardápio (ADR-020, ADR-024). Raiz da árvore de resposta.

    is_available é calculado: True apenas quando status == ACTIVE.
    status OUT_OF_STOCK -> is_available=False (produto aparece acinzentado).
    status PAUSED -> produto NÃO aparece na resposta (filtrado no repository).

    NÃO expõe:
    - store_id (cliente já conhece pela URL)
    - status cru (frontend usa is_available)
    - timestamps, deleted_at
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., examples=["Pizza Margherita"])
    description: str | None = Field(None)
    image_url: str | None = Field(None)
    preparation_minutes: int | None = Field(None, ge=0, examples=[30])
    is_available: bool = Field(..., examples=[True])
    variations: list[ProductVariationSummary]
    addon_groups: list[AddonGroupSummary]


class ProductListResponse(BaseModel):
    """Envelope do cardápio. Sem paginação tradicional (ADR-024 variante).

    total reflete contagem após filtros do repository.
    """

    items: list[ProductRead]
    total: int = Field(..., ge=0, examples=[15])
