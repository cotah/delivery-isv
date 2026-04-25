# Backend — Guia Permanente pro Agente

> Este arquivo é lido automaticamente quando o Claude Code trabalha na pasta `backend/`. Complementa o `CLAUDE.md` da raiz do monorepo e as regras globais do Henrique.

---

## 1. Estado atual (2026-04-26)

### Schema de domínio
**17 tabelas no Postgres:**
- `cities` — 3 rows (seed MG: Tarumirim, Itanhomi, Alvarenga)
- `customers` — 0 rows (produção real, sem seed)
- `addresses` — 0 rows (depende de Customer)
- `categories` — 3 rows (seed: Pizzaria, Lanchonete, Marmita)
- `stores` — 0 rows (produção real)
- `products` — 0 rows
- `product_variations` — 0 rows
- `addon_groups` — 0 rows
- `addons` — 0 rows
- `product_addon_groups` — 0 rows (tabela de junção M:N)
- `orders` — 0 rows (produção real, sem seed)
- `order_items` — 0 rows (produção real)
- `order_item_addons` — 0 rows (produção real)
- `order_status_logs` — 0 rows (primeiro modelo append-only do projeto, ADR-019)
- `users` — 0 rows (identidade via OTP, ADR-025)
- `otp_codes` — 0 rows (códigos OTP descartáveis, ADR-025)
- `alembic_version` — 1 row (controle do Alembic)

### Migrations
**20 aplicadas** em sequência:
1. `57aa2a205690` — create cities table
2. `ffd2034a50bd` — seed mg cities
3. `6ebc0349ab8c` — create customers table
4. `d1797ce9df3e` — create addresses table
5. `5bef01ffe1ab` — create categories table
6. `cd2dbc905b1a` — seed initial store categories
7. `248dec4751ff` — create stores table
8. `96cedd3fafb7` — create products table
9. `f13cab7f836a` — create product_variations table
10. `11aa25d907f3` — create addon_groups and addons tables
11. `c19dc1358909` — create product_addon_groups junction table
12. `ce147e4e4268` — create orders table
13. `9235020fd72d` — create order_items table
14. `9fc0a1ebd6ab` — create order_item_addons table
15. `e16e2e9ee921` — create order_status_logs table
16. `2e0d02f42dab` — create users and otp_codes tables
17. `661195884f97` — add status to product_variations (HIGH debt #3)
18. `90b06a960788` — add display_order/menu_section/featured to products + display_order to categories (HIGH debt #2)
19. `d9a8d7e19f52` — rename product_variations status constraint (LOW debt fix — remove duplicate prefix from CP1 HIGH)
20. `b964b10e6672` — add Store extension fields description/phone/minimum_order_cents/cover_image/logo (HIGH debt #1, CP1a — ADR-026)

### Qualidade
- **535 testes** passando em ~2.8s
- **mypy strict** limpo em **110 source files**
- **ruff check** + **ruff format** limpos
- Zero `# noqa`, zero `# type: ignore` novos (2 narrow ignores legítimos pré-existentes em test_base.py CP2 com justificativa documentada)

### API REST — catálogo público + Auth completos
- **Versionamento:** `/api/v1/` (ADR-021)
- **Estrutura em 4 camadas:** schemas → api/v1 → services → repositories → models (ADR-020)
- **Endpoints implementados:** 6 (3 catálogo público + 2 auth + 1 protegido)
  - `GET /api/v1/stores` — lista lojas aprovadas com category/city aninhados, paginação offset/limit
  - `GET /api/v1/stores/{store_id}` — detalhe com endereço completo, 404 `store_not_found` específico, 404 opaco pra soft-deleted (ADR-022)
  - `GET /api/v1/stores/{store_id}/products` — cardápio aninhado 3 níveis (produto → variações + grupos de adicionais → adicionais), is_available calculado, ordenação alfabética placeholder, limit query param default 500 max 1000 (ADR-024 variante sem paginação tradicional)
  - `POST /api/v1/auth/request-otp` — valida E.164 via field_validator, invalida OTPs anteriores, gera código 6 dígitos + sha256 hash, persiste OtpCode, commit, chama SMSProvider. Rate limit IP via slowapi+Redis (10/h). 422/429/502 (ADR-025).
  - `POST /api/v1/auth/verify-otp` — valida hash com hmac.compare_digest (constant-time), incrementa attempts ANTES da validação (anti brute force), marca consumed, cria User lazy se não existir, retorna JWT. Anti-enumeração: 5 cenários de erro (not_found, hash errado, expired, consumed, attempts esgotados) → 1 response 400 `invalid_otp_code` com mesma mensagem. Rate limit IP via slowapi+Redis (30/h). 400/422/429 (ADR-025).
  - `GET /api/v1/users/me` — primeiro endpoint protegido. Requer Bearer JWT no header Authorization. Retorna UserRead. 401 com WWW-Authenticate header (RFC 6750) em 4 cenários: unauthenticated, token_expired, invalid_token (malformed), invalid_token (user not in DB). Diferenciação UX (ADR-025).
- **Padrões estabelecidos:**
  - Formato de erro uniforme `{"error": {"code", "message", "details"}}` (ADR-022)
  - Envelope de paginação `{"items", "total", "offset", "limit"}` (ADR-023)
  - Relacionamentos via `lazy="raise"` + `selectinload` (N+1 vira bug detectável)
  - `validation_alias` pro padrão "API expõe nome de usuário, modelo preserva semântica fiscal"
  - Factories de teste com SAVEPOINT rollback + gerador programático de CNPJ
  - HTTPException com detail dict `{code, message}` — handler detecta e usa code específico (ex: `store_not_found`). Reusável para qualquer endpoint futuro sem mudar handler.
  - Relationships M:N via `secondary="tabela_junção"` — schema consumidor não vê tabela associativa (pattern AddonGroup em Product)
  - Aninhamento 3 níveis com `selectinload` em cadeia — queries O(N) fixas independente do tamanho do cardápio
  - Filtros de soft-delete no service (Python, não SQL) quando eager load traz tudo — simples e flexível

**Ciclo Auth (ADR-025) — COMPLETO (4/4 checkpoints):**

Checkpoint 1 (commit a8524c7) — Modelos User + OtpCode + migration 2e0d02f42dab.

Checkpoint 2 (commit ccd0c33) — Infraestrutura SMS. Protocol SMSProvider + MockSMSProvider + fail-fast em produção + MAGIC_FAILURE_PHONE.

Checkpoint 3a (commit 92d06ec) — JWT utils (HS256, secret 86 chars, hierarquia ExpiredTokenError/MalformedTokenError/InvalidTokenError, AccessTokenPayload frozen).

Checkpoint 3b (commit 7d71f39) — POST /api/v1/auth/request-otp. Pattern commit-antes-de-HTTP estabelecido.

Checkpoint 3c (commit 9602808) — POST /api/v1/auth/verify-otp + rate limit slowapi+Redis IP-only. Anti-enumeração por construção via INVALID_OTP_MESSAGE constante. SELECT FOR UPDATE em OtpCode. hmac.compare_digest. find_or_create_user com retry IntegrityError.

Checkpoint 4 (commit 9b7ac20) — Middleware JWT (get_current_user dependency com HTTPBearer + auto_error=False). GET /api/v1/users/me protegido. Diferenciação token_expired vs invalid_token na response (UX bom + log de segurança só em malformed). RFC 6750 compliance via WWW-Authenticate header. Catch arquitetural: _build_response em errors.py preservando exc.headers (sem isso, header WWW-Authenticate silenciosamente descartado).

**Fluxo end-to-end operacional:**
Cliente real consegue: POST /auth/request-otp → recebe SMS → POST /auth/verify-otp → recebe JWT → usa Bearer token em rotas protegidas (exemplo: GET /users/me).

**Defense-in-depth em 6 camadas:**
1. Rate limit IP (slowapi+Redis): request-otp 10/h, verify-otp 30/h
2. Attempts no OtpCode (3 max, brute force defense)
3. MAGIC_FAILURE_PHONE fail-fast (DDD impossível)
4. hmac.compare_digest no hash (timing attack defense)
5. sha256 no código (DB leak defense)
6. Anti-enumeração (1 mensagem 5 cenários em verify-otp; differentiation only between expired vs invalid in JWT)

**Patterns reusáveis estabelecidos no Ciclo Auth (pra futuros ciclos):**
- @dataclass(frozen=True) para DTOs internos (SendResult, AccessTokenPayload)
- Hierarquia de exceções (base + subclasses) para granularidade sem overhead
- Pattern "commit antes de HTTP externo" em services com provider externo
- Pattern PASSO 0 inspeção obrigatória — 41 divergências pegas em 7 checkpoints
- Constantes module-level forçando consistência (INVALID_OTP_MESSAGE)
- Singleton + lru_cache para providers e config
- HTTPBearer(auto_error=False) + 401 manual com formato ErrorResponse
- mask_phone_for_log vs mask_phone_for_display (separação por contexto)
- get_or_create com retry IntegrityError (race condition handling)
- SELECT FOR UPDATE pra serializar operações concorrentes
- Cast explícito vs # type: ignore (cast para produção, narrow ignore aceitável em testes que verificam erros que mypy detecta estaticamente)

**Débitos abertos do Ciclo Auth (3 MEDIUM, registrados no roadmap):**
1. Estratégia de secrets no Claude Code (CP3a) — antes de staging ou multi-dev
2. Rate limit phone-based (CP3c) — slowapi async key_func limitation, antes de scale
3. Fail-open runtime Redis (CP3c) — middleware custom, antes de staging Railway

**Ciclo Débitos HIGH pré-piloto — EM ANDAMENTO (2/3 checkpoints + CP1a do #1 feito):**

Decisão estratégica revisada em 2026-04-26 (pós-descanso): zerar débitos HIGH antes de Customer/Order. Pattern profissional pra evitar que débito vire crise no piloto Tarumirim.

Checkpoint 1 (commit 3159442) — Toggle ProductVariation individual. Resolve débito HIGH #3.
- Novo `ProductVariationStatus(StrEnum)` com ACTIVE/INACTIVE em `app/domain/enums.py`
- Coluna `status` em ProductVariation (`String(20)`, default ACTIVE, server_default `'active'`, CHECK dinâmico, `@validates`)
- Migration aditiva `661195884f97` (zero downtime — coluna nullable=False com server_default popula linhas existentes)
- Service combinou contratos: variations INACTIVE filtradas DO ARRAY + variation.is_available HERDA do Product.status (pattern "combine, não substitua" — preservou contrato CP3 catálogo)
- Defense-in-depth ADR-010: Pydantic + @validates + CHECK constraint
- 11 testes novos (6 model status + 5 API filtering), 481 → 492 testes

Decisões deste CP1:
- **D1 binário ACTIVE/INACTIVE** (não OUT_OF_STOCK/PAUSED como Product). Simetria não vale o custo — variation não tem visibilidade pública independente do produto pai (ADR-014 — variation reusa descrição/imagem do Product).
- **D2 migration aditiva** com `server_default='active'`. Zero downtime, linhas pré-existentes (zero em prod local) recebem ACTIVE automaticamente.
- **D3 BRANDA** (preservar `is_available=true` para Product com 0 variations cadastradas — estado anômalo de configuração). Backward compat com testes CP3 catálogo, reversível depois quando bootstrapping de loja for definido.
- **D4 filtro no service** (não no repository SQL). Eager-load já traz tudo, filtragem em Python é simples e flexível. Ordem: filtro primeiro, depois ordenação.

**Patterns reusáveis emergidos no CP1 HIGH:**
- StrEnum binário ACTIVE/INACTIVE pra toggle individual em entidades dependentes
- "Combine contratos, não substitua" quando feature nova precisa preservar contrato existente
- Migration aditiva com `server_default` cobre rows pré-existentes sem backfill manual
- Manual edit de migration pra adicionar `op.create_check_constraint(...)` quando autogenerate não detecta CheckConstraint em ADD COLUMN (limitação alembic)

Checkpoint 2 (commit 16e664d) — Menu organization. Resolve débito HIGH #2.
- Product ganha 3 campos: `display_order` (Integer), `menu_section` (StrEnum `MenuSection` 9 valores incluindo PIZZA e SNACK pra contexto BR — pizzaria + lanchonete em Tarumirim piloto), `featured` (Boolean).
- Category ganha `display_order` (Integer).
- Migration `90b06a960788` aditiva, com `op.create_check_constraint('menu_section', 'products', ...)` manual (autogenerate não detecta CHECK em ADD COLUMN — pattern já visto no CP1).
- ROW_NUMBER OVER (ORDER BY created_at) popula display_order: global em categories (3 rows seed → 1/2/3), PARTITION BY store_id em products (cada loja independente; 0 rows reais = no-op limpo).
- Repository `list_store_products` ordena por (`featured DESC, display_order ASC, name ASC`) — composição com ordenação alfabética existente em vez de substituição.
- 19 testes novos. 492 → 511.

**Débito LOW resolvido na sessão 2026-04-26 (commit b9e79c7):**

CheckConstraint do CP1 HIGH (3159442) tinha nome com prefixo duplicado no banco: `ck_product_variations_ck_product_variations_status`. Causa: passou nome já-prefixado para `op.create_check_constraint()`; naming_convention adicionou prefixo de novo. Descoberto durante CP2 HIGH (Claude Code identificou pattern correto: passar só sufixo). Fix: migration `d9a8d7e19f52` dedicada, drop nome bugado + create nome limpo. Roundtrip 3x validado. Padrão profissional: bug descoberto → bug resolvido na mesma sessão. ~30min do diagnóstico ao commit.

**Patterns reusáveis emergidos no CP2 HIGH + fix LOW:**
- Pattern correto de CheckConstraint com `naming_convention`: passar SÓ o sufixo em `op.create_check_constraint()` E em `op.drop_constraint()`. naming_convention sempre prefixa com `ck_<table>_` automaticamente. Passar nome já-prefixado causa duplicação.
- alembic `--sql` preview obrigatório antes de aplicar migration de rename de constraint (naming_convention re-prefixa nomes passados a `drop_constraint`, podendo gerar nomes truncados + hash sufixos imprevisíveis).
- ROW_NUMBER OVER + PARTITION BY pattern pra popular `display_order` em rows pré-existentes — funciona com tabelas vazias (no-op limpo) e populadas (atribui sequência por grupo).
- Repository com ordenação composta (`featured DESC, display_order ASC, name ASC`) — combina sinal de destaque + ordem manual + fallback alfabético, pattern aplicável a qualquer listagem ordenável.

CP1a do Débito #1 (commit c3dfecc) — Store expansion parte 1. Resolve 5 dos 7 itens do débito HIGH #1.
- Store ganha 5 campos: `description` (Text, max 2000 Pydantic), `phone` (E.164 obrigatório NOT NULL via Opção E), `minimum_order_cents` (Integer nullable, NULL=sem mínimo), `cover_image` (URL HttpUrl), `logo` (URL HttpUrl).
- Migration aditiva `b964b10e6672` (banco vazio confirmado: 0 stores). Opção E: `phone NOT NULL` direto, sem placeholder.
- CheckConstraint `ck_stores_minimum_order_cents_non_negative` (NULL-safe) — só sufixo passado, naming_convention prefixa.
- `@validates("phone")` reusa `validate_phone_e164` do User (pattern ADR-009).
- `__repr__` aplica `mask_phone_for_log` proativamente (ADR-026 dec. 8) — antecipa débito LGPD do User.
- `ProductRead.image_url` evolui `str | None` → `HttpUrl | None` (Caminho 2 escopo total — pattern HttpUrl em TODOS campos URL do projeto). Cast em service preserva mypy strict sem `# type: ignore`.
- ADR-026 criado cobrindo as 8 decisões do HIGH #1 inteiro (CP1a + CP1b futuro).
- 24 testes novos (16 model TestStoreExtensionFields + 5 endpoint TestStoreExtensionResponseShape + 3 PII regression). 511 → 535.

Decisões deste CP1a (referência rápida — todas em ADR-026):
- **D1 phone Store** = E.164 obrigatório, **não-unique** (lojas diferentes podem usar mesma central). Reusa validador do User.
- **D2 Phone NOT NULL strategy** = Opção E (banco vazio, sem placeholder). Plano de remediação documentado pra futuro DB com dados.
- **D3 HttpUrl pattern** em TODOS campos URL (cover_image, logo, image_url). Sem fragmentação "este sim, aquele não".
- **D4 description** = Text + max_length=2000 Pydantic (validação na camada certa, pattern Order.notes/Product.description).
- **D5 mask phone proativo** no `__repr__` (custo zero, antecipa débito LGPD).

**Patterns reusáveis emergidos no CP1a HIGH #1:**
- Verificação de segurança de dados ANTES de mudar schema validador (count + URLs válidas antes de virar HttpUrl). Pattern profissional pra futuras migrações de schema. Caught em CP1a — products vazio liberou Caminho 2 escopo total.
- Opção E pra migration NOT NULL em banco vazio: mais honesto que placeholder. Plano de remediação documentado no ADR pra cenário futuro com dados.
- HttpUrl em TODOS campos URL do projeto (cover_image, logo, image_url): consistência arquitetural. Não introduzir fragmentação "este sim, aquele não".
- Pattern proativo de aplicar fixes preventivos quando custo é zero: `mask_phone_for_log` em Store antes mesmo do User ser corrigido. Evita criar 2 débitos LGPD idênticos.

**Débitos HIGH restantes (apenas CP1b do #1):**
1. CP1b do Débito #1 — `StoreOpeningHours` table + service helper "aberto agora?" + endpoints expõem horários. **ÚLTIMO sub-checkpoint do ciclo HIGH.**

### Arquitetura documentada
- **26 ADRs** em `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\11 - Decisões Técnicas (log).md`
- 9 StrEnums em `app/domain/enums.py`: `Environment`, `AddressType`, `TaxIdType`, `StoreStatus`, `ProductStatus`, `ProductVariationStatus`, `AddonGroupType`, `MenuSection`, `OrderStatus`

---

## 2. Patterns obrigatórios — não negociáveis

Estas regras saíram de ADRs e foram validadas empiricamente. **Desvio requer novo ADR justificando.**

### Identificadores (ADR-003)
- **Toda PK usa `UUIDPK`** (type alias em `app/db/types.py`).
- Python default `new_uuid()` + Postgres `server_default=text("gen_random_uuid()")` — duplo default.
- `public_id` (VARCHAR curto) **só** em tabelas expostas ao usuário/suporte (orders, payments, refunds, support_tickets).

### Mixins (ADR-004, ADR-005, ADR-019) — 3 mixins composáveis

- **`TimestampMixin`** (`created_at` + `updated_at`) em entidades com estado mutável. **NÃO** usar em logs append-only.
- **`SoftDeleteMixin`** (`deleted_at`) em entidades persistentes que podem ser "descontinuadas" (Customer, Address, Store, Product, ProductVariation, AddonGroup, Addon, Order). Composto com TimestampMixin.
- **`CreatedAtMixin`** (apenas `created_at`) em modelos append-only — logs, eventos, auditoria (futuro: OrderStatusLog, admin_logs, notifications). **Mutuamente exclusivo com TimestampMixin.**

**NÃO** usar `SoftDeleteMixin` em tabelas de junção (`ProductAddonGroup`), tabelas lookup (`Category`) ou tabelas com `is_active` dedicado (`City`, `Category` — ADR-008/013).

### Enums com CHECK (ADR-006) — DUPLO CUIDADO
- `Mapped[MyStrEnum]` **SEM** `mapped_column(String(N))` explícito → SQLAlchemy gera `sa.Enum` nativo do Postgres (**NÃO QUEREMOS ISSO**).
- **Sempre passar `mapped_column(String(N))` explícito** pra honrar VARCHAR + CHECK.
- **CHECK constraint gerada dinamicamente** do `StrEnum` (fonte única de verdade):
  ```python
  _STATUS_CHECK = "status IN (" + ", ".join(f"'{s.value}'" for s in MyStatus) + ")"
  ```
- Se o enum ganhar valor novo: migration `DROP + ADD CHECK` + atualizar `StrEnum` — a expressão reconstruída acompanha.

### Dinheiro (ADR-007)
- **Sempre `<name>_cents INTEGER`.** Nunca `Numeric`, `Decimal`, nem `Float`.
- CHECK `price_cents >= 0` em toda coluna monetária.

### Foreign Keys (ADR-011 vs ADR-015) — DECISÃO CENTRAL
- **FK de entidade** (referência a `Customer`, `Store`, `City`, `Category`, etc.): `ondelete="RESTRICT"`.
  Protege histórico. Hard-delete do pai exige soft-delete/anonimização prévia via service.
- **FK de composição estrita** (variations de um Product, addons de um AddonGroup, linhas de junção M:N): `ondelete="CASCADE"`.
  Deletar pai remove filhos automaticamente. Composição, não relação.

**Tabela de referência rápida:**
| Relação | Tipo | `ondelete` |
|---|---|---|
| Address → Customer | entidade | RESTRICT |
| Address → City | entidade | RESTRICT |
| Store → Category | entidade | RESTRICT |
| Store → City | entidade | RESTRICT |
| Product → Store | entidade | RESTRICT |
| ProductVariation → Product | composição | CASCADE |
| AddonGroup → Store | entidade | RESTRICT |
| Addon → AddonGroup | composição | CASCADE |
| ProductAddonGroup → Product | composição (junção) | CASCADE |
| ProductAddonGroup → AddonGroup | composição (junção) | CASCADE |
| Order → Customer | entidade | RESTRICT |
| Order → Store | entidade | RESTRICT |
| OrderItem → Order | composição | CASCADE |
| OrderItem → ProductVariation | entidade (histórico) | RESTRICT |
| OrderItemAddon → OrderItem | composição | CASCADE |
| OrderItemAddon → Addon | entidade (histórico) | RESTRICT |
| OrderStatusLog → Order | composição | CASCADE |

### UniqueConstraint multi-coluna
**Armadilha:** `naming_convention` do metadata usa `%(column_0_name)s` pra UNIQUE — só pega a 1ª coluna, gerando nome ambíguo em constraints multi-coluna.

**Regra:** pra UniqueConstraint com 2+ colunas, **passar nome completo explícito**:
```python
UniqueConstraint(
    "product_id", "group_id",
    name="uq_product_addon_groups_product_id_group_id",
)
```
Formato: `uq_<table>_<col1>_<col2>_...`.

**Obs:** string literal em `name=...` é honrada **diretamente** pelo SQLAlchemy — `naming_convention` só entra em ação quando `name=None`.

### UNIQUE parcial (ADR-017)

SQLAlchemy `UniqueConstraint` **não suporta** cláusula `WHERE`. Para UNIQUE parcial no Postgres, usar `Index(..., unique=True, postgresql_where=text("..."))`:

```python
Index(
    "uq_orders_payment_gateway_transaction_id",
    "payment_gateway_transaction_id",
    unique=True,
    postgresql_where=text("payment_gateway_transaction_id IS NOT NULL"),
)
```

Nome segue padrão `uq_<table>_<col>` mesmo sendo declarado como Index. Caso real de uso: idempotência de webhook externo (Pagar.me charge_id) onde muitos registros têm valor NULL (pedidos pré-pagamento) e apenas os não-NULL devem ser únicos.

### public_id (ADR-003, ADR-018)

Formato `<PREFIX>-XXXXXXXX` — 8 caracteres sobre alfabeto reduzido de 31 símbolos (`ABCDEFGHJKMNPQRSTUVWXYZ23456789`, exclui `0`, `O`, `I`, `1`, `L`). Coluna sempre `VARCHAR(12)` (prefixo 4 + sufixo 8).

Geração via `new_public_id(prefix: str = "ISV")` em `app/db/identifiers.py` — stateless, `secrets.choice()`, sem server_default no banco. UNIQUE constraint como proteção final contra colisão.

Prefixos por entidade: `ISV-` (Order), `REF-` (Refund futuro), `TKT-` (SupportTicket futuro). Display sequencial por dia é responsabilidade do frontend via `ROW_NUMBER() OVER (...)`.

### Validação (ADR-010)
- **Defense-in-depth**: Pydantic na borda (HTTP 422) + SQLAlchemy `@validates` no modelo (última linha).
- Função canônica única em `app/utils/validators.py` — chamada pelas 2 camadas.
- **Cross-field validation** (ex: `validate_tax_id(tax_id, tax_id_type)`): usar `@validates("campo1", "campo2")` com guard `hasattr(self, "outro_campo")` pra proteger contra ordem de assignment no `__init__`.

### PII mascarada em logs
- CPF → `mask_cpf_for_log` → `529.***.***-25`
- CNPJ → `mask_cnpj_for_log` → `11.***.***/***1-81`
- Phone E.164 → `mask_phone_for_log` → `+55*********66`
- `tax_id` polimorfo → `mask_tax_id_for_log(tax_id, tax_id_type=None)` (infere por tipo ou tamanho)
- `__repr__` de modelos com PII **nunca** expõe o valor cru.

---

## 3. Workflow obrigatório por ciclo de modelo

Segue esta ordem sem pular passos. Cada passo é unidade fechada que pode ser revista.

1. **Registrar ADR no vault** (se o modelo introduz decisão nova)
2. **Criar o modelo** em `app/models/<name>.py` + atualizar `app/domain/enums.py` se precisar
3. **Escrever testes Python-only** em `tests/models/test_<name>.py` (estrutura + comportamento)
4. **Atualizar `alembic/env.py`** com o import do modelo novo (formato multi-linha, ordem alfabética)
5. **Validar localmente**: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app tests` — **TUDO verde**
6. **PARAR e confirmar** com o Henrique antes de gerar migration
7. **Gerar migration**: `uv run alembic revision --autogenerate -m "..."`
8. **PARAR e revisar linha-a-linha** (especialmente FKs com `ondelete`, CHECKs sem virar `sa.Enum`, UNIQUE multi-coluna com nome correto)
9. **PARAR e confirmar** com o Henrique antes de aplicar
10. **Aplicar**: `uv run alembic upgrade head` → `alembic current` → `alembic check` (drift = zero)
11. **Inspecionar DDL real**: `docker exec delivery-postgres-1 psql -U isv -d isv_delivery -c "\d+ <table>"`
12. **Testar ativamente as constraints no Postgres**:
    - INSERT negativo por cada CHECK → deve falhar
    - INSERT com FK fake → deve falhar
    - Se tem CASCADE: criar hierarquia real + deletar pai + confirmar filhos sumiram
    - Se tem UNIQUE: tentar duplicata + deve falhar
    - Deletar linhas de teste no final (produção continua vazia)
13. **Commit atômico** por feature (ou ciclo de modelos relacionados). Paths explícitos em `git add`, nunca `-A` ou `.`.
14. **Atualizar vault**: `Sessões/<data>.md` com hash real do commit + `09 - Roadmap.md` marcando concluído
15. **Atualizar este CLAUDE.md** se o ciclo muda contagens (tabelas, testes, ADRs) ou adiciona pattern novo
16. **Push**: `git push origin main`

---

## 4. Armadilhas conhecidas (aprendidas na prática)

### `sa.Enum` nativo indesejado (ADR-006 risco)
`Mapped[MyStrEnum]` sem `mapped_column(String(N))` faz SQLAlchemy criar ENUM type nativo no Postgres. Migration vai ter `CREATE TYPE ... AS ENUM (...)` — difícil de alterar depois (ADR-006 rejeita). **Solução**: sempre passar `String(N)` explícito em colunas com enum.

### UniqueConstraint multi-coluna sem prefixo
`UniqueConstraint("col1", "col2", name="col1_col2")` vira `col1_col2` literal no banco, sem prefixo `uq_`. `naming_convention` é ignorada quando `name=...` é literal. **Solução**: passar nome completo `"uq_<table>_<col1>_<col2>"`.

### Python default vs DB default (momento de aplicação)
`mapped_column(default=X)` **só** aplica em `session.flush()` / `session.commit()`. Em testes Python puros (só `Model(...)` sem sessão), o campo fica `None`. **Solução**: passar valor explícito em testes de `__repr__` e comportamento; testar o default acessando `col.default.arg` no schema.

### Cross-field `@validates` e ordem de assignment
`@validates("a", "b")` é chamado a cada assignment, independente da ordem. No primeiro assignment, o outro campo ainda não foi setado. **Solução**: `hasattr(self, "other_field")` + curto-circuito — só validar quando ambos setados.

Em mypy strict, declarar tipos explícitos no início do validator (`tax_id: str | None`, etc.) pra evitar narrowing através de branches do `if`.

### `__table__` como `FromClause` genérico
Mypy tipa `Model.__table__` como `FromClause`, que não tem `.indexes`, `.constraints`, `.foreign_keys` específicos. **Solução**: `from sqlalchemy import Table` + `assert isinstance(table, Table)` como type narrowing antes de acessar essas properties.

### `c.name` de constraint é `str | _NoneName`, não `str | None`
`_NoneName` é sentinel interno do SQLAlchemy. Filter `if c.name and ...` não funciona (retorna `_NoneName` que é truthy). **Solução**: `if isinstance(c.name, str) and "address_type" in c.name`.

### Teste isolado de modelo com FK falha se pais não importados
Rodar `pytest tests/models/test_product_addon_group.py` **sozinho** falha porque `Product` e `AddonGroup` não estão no `Base.metadata` (não foram importados). Na suíte completa funciona — outros tests importam os pais antes. **Solução** (futura): importar pais no topo do arquivo de teste da junção.

### Postgres normaliza `IN (...)` como `= ANY(ARRAY[...])`
`CHECK (col IN ('a', 'b'))` no DDL do alembic vira `CHECK ((col)::text = ANY ((ARRAY['a', 'b'])::text[]))` no `pg_get_constraintdef`. Semanticamente equivalente — não é bug, é decisão do planner.

### `VARCHAR(N)` menor que valor bloqueia CHECK
Se coluna é `VARCHAR(10)` e você testa CHECK violation com string de 12 chars, o Postgres rejeita por **tamanho** antes de avaliar a CHECK. Dupla proteção — pra forçar teste da CHECK específica, use valor dentro do tamanho.

### Commit de linha de teste criada no happy path
Se criar dados temporários em teste ativo (store temp, product temp), **delete no final do teste**. `stores`, `products`, etc. são tabelas de produção — permanecer vazias. Seeds só em `cities` e `categories`.

### ADR escrito sem verificar código existente

ADR novo deve ser escrito **depois** de verificar o que já existe no código. Caso real (ciclo Order fase 1): ADR-018 foi redigido com formato `ISV-XXXXXX` (6 chars) sem consultar `new_public_id()` existente em `app/db/identifiers.py`, que já gerava 8 chars desde o commit 158fa23. Divergência só foi detectada na hora de escrever testes. **Solução:** antes de redigir qualquer ADR, listar arquivos/funções relacionados e ler o código atual. ADR reflete decisão baseada em realidade, não intenção projetada por cima.

### UNIQUE parcial ≠ UniqueConstraint

`UniqueConstraint` do SQLAlchemy não aceita `postgresql_where`. Tentar `UniqueConstraint("col", postgresql_where=...)` falha silenciosamente ou gera DDL errado. **Solução:** declarar como `Index(..., unique=True, postgresql_where=text("..."))`. Nome começa com `uq_` por convenção do projeto, mesmo sendo Index. Ver subseção nova na seção 2.

---

## 5. Credenciais / Infra (referência)

### Postgres local (ADR-002)
- Container: `delivery-postgres-1`
- Host port: `5433` (não-padrão — coexistência com outros projetos do Henrique)
- Container port: `5432`
- User: `isv`
- Password: `isvpass` (local dev, não-produção)
- Database: `isv_delivery`
- Connection string (backend): `postgresql+psycopg://isv:isvpass@localhost:5433/isv_delivery`

### Redis local (ADR-002)
- Container: `delivery-redis-1`
- Host port: `6380` (não-padrão)
- Container port: `6379`
- Connection: `redis://localhost:6380/0`

### Comandos úteis
```bash
docker compose ps                  # status dos containers
docker compose up -d               # sobe tudo em background
docker compose logs -f postgres    # logs do Postgres
uv run pytest                      # suite completa (deve passar 100%)
uv run ruff check .                # lint
uv run ruff format --check .       # format check
uv run mypy app tests              # type-check strict
uv run alembic current             # revision atual
uv run alembic check               # drift model/DB (zero ops = OK)
uv run alembic upgrade head        # aplica migrations pendentes
uv run alembic revision --autogenerate -m "..."  # gera migration
```

### Inspeção do banco
```bash
docker exec delivery-postgres-1 psql -U isv -d isv_delivery -c "\d+ <table>"
docker exec delivery-postgres-1 psql -U isv -d isv_delivery -c "SELECT ..."
```

### Paths chave
- Código: `C:\Users\henri\Desktop\delivery\backend\`
- Vault (cérebro): `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\`
- ADRs: `<vault>\11 - Decisões Técnicas (log).md`
- Roadmap: `<vault>\09 - Roadmap.md`
- Sessões: `<vault>\Sessões\<YYYY-MM-DD>.md`

---

## 6. Próximo passo sugerido

**Status:** Ciclo Débitos HIGH em construção. **2/3 débitos resolvidos + CP1a do #1 feito** (commit c3dfecc). Falta apenas **CP1b do Débito #1** (`StoreOpeningHours` + service + endpoints) para fechar ciclo HIGH 3/3.

**Ordem dos ciclos (revisada em 2026-04-26):**

1. **Débitos HIGH pré-piloto** ← em andamento, 2/3 + CP1a done
2. Customer endpoints (depois dos HIGH)
3. Order endpoints (requer Customer, depois)

**Débitos HIGH — status atual:**

- [x] **#3 Toggle ProductVariation individual** — commit 3159442 (CP1 do ciclo HIGH).
- [x] **#2 Organização do cardápio** — commit 16e664d (CP2 do ciclo HIGH).
- [ ] **#1 Expansão Store** — em andamento (CP1a feito, falta CP1b):
  - [x] **CP1a** — 5 campos triviais + phone NOT NULL + ADR-026 (commit c3dfecc, 2026-04-26)
  - [ ] **CP1b** — `StoreOpeningHours` table + service "aberto agora?" + endpoints

**Débito LOW resolvido em paralelo:** commit b9e79c7 — rename de `ck_product_variations_status` removendo prefix duplicado herdado do CP1 HIGH. Cosmético, descoberto durante CP2 HIGH, resolvido na mesma sessão (~30min).

**Próximo passo: CP1b do Débito HIGH #1 — `StoreOpeningHours`**

Escopo (todas as decisões já documentadas no ADR-026):
- Tabela nova `store_opening_hours(id, store_id FK CASCADE, day_of_week 0-6, open_time Time, close_time Time)`
- Service helper "loja aberta agora?" com lógica de timezone `America/Sao_Paulo` + cruzar meia-noite (`close_time < open_time` — ADR-026 dec. 3)
- Endpoint expõe `opening_hours: []` em `StoreDetail` (lojas existentes pós-migration ficam sem horário, lojista preenche depois via painel admin futuro — ADR-026 dec. 4)

**Tamanho:** médio (~2-3h ritmo Henrique). Decisões já tomadas no ADR-026, implementação é execução.

**Após CP1b, ciclo HIGH 100% completo.** Então:

- Ciclo Customer (cadastro + endereço + perfil) — ~3-5 dias
- Ciclo Order (core do produto, requer Customer) — ~8-12 dias
- Mobile React Native em paralelo (segundo agente)
- Pagar.me + Zenvia (depende CNPJ)

**Mobile React Native:**

Será iniciado APÓS o ciclo HIGH 100% (CP1b fecha o último). Henrique vai abrir segundo agente dedicado ao frontend nesse momento. Backend até lá cobre todas as telas iniciais necessárias (catálogo + login + perfil + cardápio organizado + dados expandidos da loja).

---

## 7. Filosofia

Cada linha de código neste backend foi escrita com a premissa de ser **cirurgia**, não tutorial. Se algo parece "complicado sem motivo claro", é porque há um ADR explicando o motivo. Antes de simplificar, **leia o ADR correspondente**. Antes de adicionar feature/flag/complexidade, **registre a decisão**.

A meta não é volume de código — é que cada decisão seja **rastreável** ao problema real de delivery em Tarumirim/MG.
