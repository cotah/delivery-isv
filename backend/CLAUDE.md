# Backend — Guia Permanente pro Agente

> Este arquivo é lido automaticamente quando o Claude Code trabalha na pasta `backend/`. Complementa o `CLAUDE.md` da raiz do monorepo e as regras globais do Henrique.

---

## 1. Estado atual (2026-04-26)

### Schema de domínio
**18 tabelas no Postgres:**
- `cities` — 3 rows (seed MG: Tarumirim, Itanhomi, Alvarenga)
- `customers` — 0 rows (produção real, sem seed)
- `addresses` — 0 rows (depende de Customer)
- `categories` — 3 rows (seed: Pizzaria, Lanchonete, Marmita)
- `stores` — 0 rows (produção real)
- `store_opening_hours` — 0 rows (slots de horário de funcionamento, ADR-026 dec. 1)
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
**22 aplicadas** em sequência:
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
21. `9a74dcc91e93` — create store_opening_hours table (HIGH debt #1, CP1b — ADR-026 dec. 1) — closes HIGH cycle 3/3
22. `64f6e6cef194` — add user_id FK to customers (Customer cycle CP1 — ADR-027 dec. 1)

### Qualidade
- **637 testes** passando em ~5s
- **mypy strict** limpo em **123 source files**
- **ruff check** + **ruff format** limpos
- Zero `# noqa`, zero `# type: ignore` novos (2 narrow ignores legítimos pré-existentes em test_base.py CP2 com justificativa documentada)

### API REST — catálogo público + Auth + Customer completos
- **Versionamento:** `/api/v1/` (ADR-021)
- **Estrutura em 4 camadas:** schemas → api/v1 → services → repositories → models (ADR-020)
- **14 ErrorCodes** em `app/api/errors.py`: validation_failed, not_found, store_not_found, customer_not_found, customer_already_exists, address_not_found, city_not_found, sms_provider_error, invalid_otp_code, rate_limited, unauthenticated, token_expired, invalid_token, internal_error
- **Endpoints implementados:** 13 (3 catálogo público + 2 auth + 1 protegido + 3 Customer + 4 Address)
  - `GET /api/v1/stores` — lista lojas aprovadas com category/city aninhados, paginação offset/limit
  - `GET /api/v1/stores/{store_id}` — detalhe com endereço completo + horários + is_open_now (ADR-026)
  - `GET /api/v1/stores/{store_id}/products` — cardápio aninhado 3 níveis (ADR-024)
  - `POST /api/v1/auth/request-otp` — OTP por SMS, rate limit slowapi+Redis (ADR-025)
  - `POST /api/v1/auth/verify-otp` — verifica OTP, retorna JWT (ADR-025)
  - `GET /api/v1/users/me` — primeiro endpoint protegido (ADR-025)
  - `GET /api/v1/customers/me` — perfil do User logado, 404 `customer_not_found` se não cadastrou (ADR-027 dec. 2)
  - `POST /api/v1/customers` — cria Customer (lazy creation), 201, 409 `customer_already_exists` se já tem (ADR-027 dec. 4). Phone vem do User (ADR-027 dec. 6).
  - `PATCH /api/v1/customers/me` — atualiza name/email/cpf/birth_date, exclude_unset (ADR-027 dec. 8)
  - `GET /api/v1/customers/me/addresses` — lista, ordering is_default DESC + created_at DESC (ADR-027)
  - `POST /api/v1/customers/me/addresses` — cria, 201, is_default switch transacional (ADR-027 dec. 8)
  - `PATCH /api/v1/customers/me/addresses/{address_id}` — atualiza, 404 disfarçado se de outro customer (ADR-027 A)
  - `DELETE /api/v1/customers/me/addresses/{address_id}` — soft-delete, 204, sem auto-promoção (ADR-027 dec. 10)
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

**Ciclo Débitos HIGH pré-piloto — COMPLETO em 2026-04-26 (3/3 débitos resolvidos + 1 LOW em paralelo):**

Decisão estratégica revisada em 2026-04-26 (pós-descanso): zerar débitos HIGH antes de Customer/Order. Pattern profissional pra evitar que débito vire crise no piloto Tarumirim. Resultado: 3/3 débitos HIGH zerados + 1 LOW resolvido em paralelo, todos na mesma sessão (9 commits — maior dia do projeto).

Débito #3 (commit 3159442) — Toggle ProductVariation individual. ProductVariation ganhou status (StrEnum binário ACTIVE/INACTIVE). is_available do Product combina: filtro novo (INACTIVE removida do array) + herança CP3 (variations herdam Product.status). Migration 661195884f97. 11 testes novos.

Débito #2 (commit 16e664d) — Menu organization. Product ganhou display_order/menu_section/featured. Category ganhou display_order. MenuSection enum 9 valores incluindo PIZZA e SNACK pro contexto BR (pizzaria + lanchonete em Tarumirim piloto). Repository ordena por (featured DESC, display_order ASC, name ASC). Migration 90b06a960788 com ROW_NUMBER OVER created_at (categories global, products PARTITION BY store_id). 19 testes novos.

Débito #1 CP1a (commit c3dfecc) — Store expansion parte 1. 5 campos novos: description (Text), phone (E.164 obrigatório Opção E), minimum_order_cents (NULL=sem mínimo), cover_image, logo (HttpUrl). ProductRead.image_url também virou HttpUrl (Caminho 2 escopo total — pattern HttpUrl em TODOS campos URL). Migration b964b10e6672. ADR-026 criado cobrindo 8 decisões do HIGH #1 inteiro. 24 testes novos.

Débito #1 CP1b (commit 1c56b38) — Store expansion parte 2 (FECHA O CICLO). Tabela `store_opening_hours` + service helper `is_store_open(store, dt)` com guard contra naive datetime + endpoint StoreDetail expõe `opening_hours: list` + `is_open_now: bool` computed. ADR-026 estendido com 4 reforços (D1 DOW comment, D3 UNIQUE nuance, D4 deferred validation, D5 naive guard, D7 cache policy). Migration 9a74dcc91e93. 40 testes novos.

Débito LOW resolvido em paralelo (commit b9e79c7) — CheckConstraint duplicate prefix do CP1 HIGH (3159442). Migration d9a8d7e19f52 dedicada. Pattern profissional: bug descoberto no CP2 → bug resolvido em ~30min via micro-CP entre CP2 e CP1a.

**Patterns reusáveis estabelecidos no Ciclo HIGH (pra futuros ciclos):**

1. **PASSO 0 inspeção obrigatória** — pegou 41+ divergências acumuladas em 7 checkpoints anteriores + ~10 desvios sutis no HIGH (autogenerate vs manual edit, naming_convention always-on, lazy=raise vs back_populates, etc.).
2. **`--sql` preview obrigatório antes de migration não-trivial** — pegou bug-do-bug no fix LOW da constraint, salvou aplicação do CP2 HIGH no banco local pós-reboot.
3. **CheckConstraint pattern correto** — passar SÓ sufixo em `op.create_check_constraint()`; naming_convention sempre prefixa com `ck_<table>_`. Multi-coluna UNIQUE/Index passar nome COMPLETO (CLAUDE.md armadilha #2 — naming_convention só pega 1ª coluna).
4. **Verificação de segurança antes de mudar schema validador** — count + URLs válidas antes de virar HttpUrl. Pattern aplicável a futuras mudanças de validação.
5. **Opção E para migration NOT NULL em banco vazio** — honesta, sem placeholder. Plano de remediação pra futuro DB com dados documentado no ADR.
6. **HttpUrl em TODOS campos URL** — sem fragmentação "este sim, aquele não". Caminho 2 escopo total.
7. **`mask_phone_for_log` no `__repr__` proativamente** — evita criar mesmo débito LGPD que User tem. Pattern: aplicar fix preventivo quando custo é zero.
8. **`relationship` lazy="raise" sem back_populates + sem cascade Python** — pattern do projeto. `ondelete=CASCADE` no DB faz trabalho real, Python cascade é redundante.
9. **`populate_by_name=True` no schema com `validation_alias`** — necessário quando service constrói explicitamente em vez de `model_validate`.
10. **Testar lógica pura (helper) com objetos em memória + testar comportamento DB com SQL direto** — separa concerns. lazy="raise" força disciplina.
11. **Combinar contratos novos com existentes em vez de substituir** — preserva regressão + adiciona feature.
12. **Documentar timezone hardcoded com plano de migração futura desde dia 1** — evita assumption errado de próximo agente.
13. **Pattern proativo de revisar pós-descanso decisões estratégicas com prazo curto** — Henrique mudou de Customer pra HIGH primeiro com cabeça descansada. Documentado.
14. **Bug descoberto = bug resolvido na mesma sessão quando custo é ~30min** — preserva invariante "zero débito antes de avançar features".

**Marco do projeto (fim do Ciclo HIGH):**
- 481 testes ao fim do Ciclo Auth → **575 ao fim do Ciclo HIGH** (+94 testes em 3 dias, +19.5%)
- 16 migrations → **21 migrations** (+5: HIGH #3 + HIGH #2 + LOW fix + CP1a + CP1b)
- 17 tabelas → **18 tabelas** (+`store_opening_hours`)
- ADRs: 25 → **26** (ADR-026 com 8 decisões + 4 reforços documentando HIGH #1 inteiro)
- Backend agora **mobile-ready**: cliente real consegue abrir app, ver lista de lojas com logo + minimum_order, ver cardápio organizado por seção com produtos em destaque, login via SMS, perfil pessoal, e em cada loja vê foto, descrição, telefone, horários completos com badge "Aberto agora".

**Ciclo Customer (ADR-027) — COMPLETO em 2026-04-26 (3 sub-checkpoints feat + 1 docs final):**

CP1 (commit acd8e99) — Foundation User ↔ Customer. `Customer.user_id` UUID UNIQUE NOT NULL FK `users(id)` RESTRICT. Migration `64f6e6cef194`. Pattern novo: `uselist=False` em `User.customer` (1:1 reverso do lado da PK) + `foreign_keys` explícito + `overlaps` (descoberto em CP2 e formalizado em CP4). ADR-027 criado com 15 decisões cobrindo o ciclo inteiro. `customer_factory` novo. +8 testes.

CP2 (commit 3563624) — Customer endpoints. 3 endpoints: `GET /customers/me` (200/404/401), `POST /customers` (201/404/422/401), `PATCH /customers/me` (200/404/422/401). Schemas `extra="forbid"` + `exclude_unset=True` no PATCH. Hierarquia `CustomerError → CustomerNotFoundError + CustomerAlreadyExistsError` traduzida pra HTTPException no endpoint. Pattern novo: POST 201 Created + service recebe `current_user` (User completo, não só id). +20 testes.

CP3 (commit d72ebc4) — Address CRUD. 4 endpoints em `/customers/me/addresses`: GET (200/404/401), POST (201/404/422/401), PATCH (200/404/422/401), DELETE (204/404/401). `is_default` switch transacional no service (UNIQUE parcial protege race no banco). `city_id` validation pre-insert via `session.get(City, id)` → `CityNotFoundError` → 422 `CITY_NOT_FOUND`. Pattern novo: DELETE 204 No Content (primeiro do projeto) + helpers `_raise_*` DRY. `address_factory` novo. +34 testes (incluindo 7 cenários `is_default` explícitos).

CP4 (este commit) — Pausa de docs final. Decisão 15 do ADR-027 estendida com pattern `overlaps` descoberto em runtime no CP2.

**Patterns reusáveis estabelecidos no Ciclo Customer (5 novos):**

1. **POST que cria recurso REST com `status_code=status.HTTP_201_CREATED` explícito** (CP2 — primeiro do projeto)
2. **Hierarquia de exceções no service traduzida pra HTTPException no endpoint** (CP2 + CP3)
3. **Service recebe `current_user` completo (não só user_id)** — necessário pra phone match (ADR-027 dec. 6)
4. **DELETE 204 No Content** (CP3 — primeiro do projeto). Helpers `_raise_*` DRY no endpoint module.
5. **Pattern `overlaps` em ambos os lados de relationship 1:1 reverso sem `back_populates`** (descoberto em runtime no CP2, formalizado em CP4 — ADR-027 dec. 15 estendida).

**Marco do projeto (fim do Ciclo Customer):**
- 575 testes (fim HIGH) → **637 ao fim do Customer** (+62, +10.8%)
- 21 → **22 migrations** (+1: customers.user_id FK)
- 9 → **13 endpoints** (+4 Customer/Address; +3 Customer no CP2)
- 113 → **123 source files mypy** (+10 módulos: 5 customer + 5 address)
- 12 → **14 ErrorCodes** (+CUSTOMER_NOT_FOUND, +CUSTOMER_ALREADY_EXISTS, +ADDRESS_NOT_FOUND, +CITY_NOT_FOUND)
- ADRs: 26 → **27** (ADR-027 com 15 decisões; refinamento Dec. 15 com `overlaps` em CP4)

**Cliente real consegue ponta-a-ponta exceto Order:**
1. Splash + lista de lojas
2. Detalhe da loja com horários + is_open_now
3. Cardápio organizado
4. Login OTP
5. Perfil User + Customer
6. Gerenciar endereços de entrega

Falta apenas Order (próximo grande ciclo).

**Débitos novos rastreados durante o Ciclo Customer (2):**

**LOW**: Email validation rigorosa de formato. Hoje `CustomerCreate/Update` usam `str + max_length=254` sem validação de formato (pode aceitar `"abc"` como email no banco). Solução: adicionar `email-validator` dep + `EmailStr` no schema. Custo: ~5 min. Bloqueante: não (emails ainda não são usados em comunicação real). Resolver antes do piloto.

**MEDIUM**: `ValueError` em `@validates` do model retorna 500 Internal Server Error em vez de 422 `validation_failed`. Afeta CPF (e potencialmente phone, embora improvável via API já que phone vem do User logado). Solução: global exception handler em FastAPI capturando `ValueError` → `HTTPException(422, validation_failed)` com message do error. Custo: ~30 min. **Bloqueante pra UX**: sim (cliente recebe 500 ao mandar CPF malformatado, vira ticket de suporte). Resolver antes do piloto.

### Arquitetura documentada
- **27 ADRs** em `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\11 - Decisões Técnicas (log).md`
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

**Status:** Auth completo + HIGH 3/3 + **Customer cycle 100% completo**. Backend cobre fluxo cliente real ponta-a-ponta exceto Order.

**Próximo grande ciclo: Order endpoints**

Foundation existe há várias sessões (commits `26d7243`, `5dfc717`, `d706566`, `99e486a`):
- `Order` model
- `OrderItem` model
- `OrderItemAddon` model
- `OrderStatusLog` model
- FK `Order.customer_id` RESTRICT
- FK `Order.store_id` RESTRICT

Falta apenas camada de aplicação (schemas + repository + service + endpoints). Estimativa otimista: 6-10h ritmo Henrique (~4-5 sub-CPs).

**Estrutura provável:**
- **CP1**: Schemas Pydantic Order/OrderItem/OrderItemAddon + Read endpoints (`GET /orders`, `GET /orders/{id}`)
- **CP2**: `POST /orders` (criar pedido novo, transação Customer + Store + Items + Addons + status inicial)
- **CP3**: Status transitions (`PATCH /orders/{id}/status` — lojista atualiza)
- **CP4**: Listagem por lojista (`GET /stores/{store_id}/orders` pra dashboard)
- **CP5**: Pausa de docs final

**Após Order cycle:**
- Mobile React Native (segundo agente, pode iniciar AGORA mesmo)
- Pagar.me integration (CNPJ pendente)
- LGPD cycle (`anonymize_customer` real + `DELETE /users/me` + global ValueError handler)

**Débitos pré-piloto a resolver:**
- LOW `email-validator` (~5min)
- MEDIUM `ValueError` → 422 handler (~30min)
- 3 MEDIUM herdados do Auth cycle (secrets strategy, rate limit phone, Redis fail-open)

---

## 7. Filosofia

Cada linha de código neste backend foi escrita com a premissa de ser **cirurgia**, não tutorial. Se algo parece "complicado sem motivo claro", é porque há um ADR explicando o motivo. Antes de simplificar, **leia o ADR correspondente**. Antes de adicionar feature/flag/complexidade, **registre a decisão**.

A meta não é volume de código — é que cada decisão seja **rastreável** ao problema real de delivery em Tarumirim/MG.
