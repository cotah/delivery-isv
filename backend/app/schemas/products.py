"""Schemas Pydantic do cardápio público (ADR-020, ADR-024).

Árvore de 3 níveis (Product → Variation/AddonGroup → Addon) reflete o modelo
de domínio ADR-014. Respostas são serializadas pelo service em vez de direto
do ORM pra suportar filtros por deleted_at e cálculo de is_available (status
não exposto cru)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.domain.enums import MenuSection


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

    Lógica do response (HIGH debt #3 resolvido em 2026-04-26):
    - Variations INACTIVE (toggle individual do lojista) são FILTRADAS
      do array antes de virar Summary — não aparecem no response.
    - Variations ACTIVE no array têm is_available HERDADO do Product.status:
      produto ACTIVE → variation.is_available=true; produto OUT_OF_STOCK →
      variation.is_available=false (UX: variation acinzentada quando produto
      todo está fora de estoque).
    - Produto com TODAS variations INACTIVE → product.is_available=false
      e variations=[]. Nenhuma variation selecionável.
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

    Organização do cardápio (HIGH debt #2, 2026-04-26):
    - display_order: posição definida pelo lojista no painel
    - menu_section: seção pra agrupamento (D5: frontend agrupa, backend retorna plano)
    - featured: destaque no topo (similar "em promoção" do iFood)

    Backend ordena por (featured DESC, display_order ASC, name ASC). Frontend
    lê menu_section de cada item e agrupa visualmente.

    NÃO expõe:
    - store_id (cliente já conhece pela URL)
    - status cru (frontend usa is_available)
    - timestamps, deleted_at
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., examples=["Pizza Margherita"])
    description: str | None = Field(None)
    # image_url validado como HttpUrl (ADR-026 dec. 6) — pattern do projeto
    # pra todos campos URL. Banco armazena str (Mapped[str | None] no model).
    image_url: HttpUrl | None = Field(None, examples=["https://cdn.example.com/pizza.jpg"])
    preparation_minutes: int | None = Field(None, ge=0, examples=[30])
    is_available: bool = Field(..., examples=[True])
    display_order: int = Field(..., ge=0, examples=[1])
    menu_section: MenuSection = Field(..., examples=[MenuSection.PIZZA])
    featured: bool = Field(..., examples=[False])
    variations: list[ProductVariationSummary]
    addon_groups: list[AddonGroupSummary]


class ProductListResponse(BaseModel):
    """Envelope do cardápio. Sem paginação tradicional (ADR-024 variante).

    total reflete contagem após filtros do repository.
    """

    items: list[ProductRead]
    total: int = Field(..., ge=0, examples=[15])
