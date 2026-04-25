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
**16 aplicadas** em sequência:
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

### Qualidade
- **481 testes** passando em ~2.3s
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

### Arquitetura documentada
- **25 ADRs** em `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\11 - Decisões Técnicas (log).md`
- 7 StrEnums em `app/domain/enums.py`: `Environment`, `AddressType`, `TaxIdType`, `StoreStatus`, `ProductStatus`, `AddonGroupType`, `OrderStatus`

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

**Status:** Ciclo Auth COMPLETO. Decisão estratégica revisada em 2026-04-26 (pós-descanso): próximo ciclo é Débitos HIGH (zerar débito antes de features novas).

**Nova ordem dos ciclos (revisada em 2026-04-26):**

1. **Débitos HIGH pré-piloto** (próximo)
2. Customer endpoints (depois dos HIGH)
3. Order endpoints (requer Customer, depois)

Decisão anterior (2026-04-25, commit 34c8513) era Customer como próximo. Após descanso, Henrique revisou: zerar débito é prioridade antes de features novas. Pattern profissional pra evitar que débito vire crise no piloto Tarumirim.

**Próximo passo: Débitos HIGH pré-piloto**

3 débitos HIGH registrados no roadmap, todos pré-piloto:

1. **Expansão Store** — adicionar campos: description, phone, opening_hours, minimum_order, cover_image, logo. Crítico pra apresentar app pra cliente real (loja sem horário nem foto não funciona).

2. **Organização do cardápio** — display_order em Product/Category, menu_section, featured. Cardápio em ordem aleatória não é aceitável pra UX de delivery.

3. **Toggle ProductVariation individual** — status column + enum. Permitir desativar variação específica sem mexer no produto inteiro (ex: "carne extra" temporariamente fora de estoque).

Estimativa total: 3-5 dias com ritmo intenso. Cada débito é CRUD focado em modelo existente — patterns de schema, repository, service, endpoint todos já estabelecidos.

**Mobile React Native:**

Será iniciado APÓS os 3 débitos HIGH terminarem. Henrique vai abrir segundo agente dedicado ao frontend nesse momento. Backend até lá cobre todas as telas iniciais necessárias (catálogo + login + perfil + cardápio organizado).

**Após Débitos HIGH:**

- Ciclo Customer (cadastro + endereço + perfil) — 6-10h, 3-4 sub-checkpoints
- Ciclo Order (core do produto, requer Customer) — 15-25h
- Integração Pagar.me + Zenvia (depende CNPJ)

---

## 7. Filosofia

Cada linha de código neste backend foi escrita com a premissa de ser **cirurgia**, não tutorial. Se algo parece "complicado sem motivo claro", é porque há um ADR explicando o motivo. Antes de simplificar, **leia o ADR correspondente**. Antes de adicionar feature/flag/complexidade, **registre a decisão**.

A meta não é volume de código — é que cada decisão seja **rastreável** ao problema real de delivery em Tarumirim/MG.
