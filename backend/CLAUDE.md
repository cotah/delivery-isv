# Backend — Guia Permanente pro Agente

> Este arquivo é lido automaticamente quando o Claude Code trabalha na pasta `backend/`. Complementa o `CLAUDE.md` da raiz do monorepo e as regras globais do Henrique.

---

## 1. Estado atual (2026-04-22)

### Schema de domínio
**15 tabelas no Postgres:**
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
- `alembic_version` — 1 row (controle do Alembic)

### Migrations
**15 aplicadas** em sequência:
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

### Qualidade
- **279 testes** passando em ~0.35s
- **mypy strict** limpo em **57 source files**
- **ruff check** + **ruff format** limpos
- Zero `# noqa`, zero `# type: ignore`, zero warnings

### Arquitetura documentada
- **19 ADRs** em `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\11 - Decisões Técnicas (log).md`
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

Ciclo Order completo — fundação de dados do MVP chegou ao fim. 15 tabelas cobrem:
- Entidades de domínio (cities, customers, addresses, categories, stores)
- Catálogo (products, product_variations, addon_groups, addons, product_addon_groups)
- Fluxo de pedido (orders, order_items, order_item_addons, order_status_logs)

Próximos caminhos possíveis — decisão do Henrique baseada em prioridade de negócio:

### Opção A — API REST (endpoints HTTP) — começa a destravar integração
Backend deixa de ser schema-only e vira API funcional. FastAPI + Pydantic schemas + service layer + repository pattern. Bloqueia frontend real.
- Decisões a tomar: organização de endpoints, auth strategy, paginação, filtros, padrão de resposta de erro.

### Opção B — Auth OTP + JWT + Sessions
Login via SMS. Destrava qualquer endpoint protegido.
- Decisões a tomar: provider SMS (Zenvia/Twilio/Total Voice), rate limit, expiração OTP, JWT rotation, refresh tokens.

### Opção C — Driver (entregador) — ampliar schema em paralelo
Modelo similar a Customer. Destrava recrutamento paralelo de entregadores pelo sócio comercial.
- Pattern já estabelecido (PII + E.164 + anonymization stub).

### Opção D — Coupon (cupom de desconto) — fechar lacuna do ciclo Order
Order fase 2 já tem discount_cents e coupon_code_snapshot, mas sem modelo Coupon. Admin aplica manualmente via painel hoje. Modelar quando decidir formalizar.

Recomendação minha: A ou B primeiro, depois C e D conforme priorização. A destrava frontend e experiência real; B destrava qualquer protected route. C e D são menos bloqueantes.

---

## 7. Filosofia

Cada linha de código neste backend foi escrita com a premissa de ser **cirurgia**, não tutorial. Se algo parece "complicado sem motivo claro", é porque há um ADR explicando o motivo. Antes de simplificar, **leia o ADR correspondente**. Antes de adicionar feature/flag/complexidade, **registre a decisão**.

A meta não é volume de código — é que cada decisão seja **rastreável** ao problema real de delivery em Tarumirim/MG.
