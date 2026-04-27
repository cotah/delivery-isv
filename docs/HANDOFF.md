# ISV Delivery — Handoff Briefing

> **Snapshot congelado em 2026-04-27.** Última sessão fechou o marco
> **ZERO débitos pré-piloto** (commit `7bb07f1`). Backend pronto pro
> próximo grande ciclo (Order endpoints) sem dividas herdadas.
>
> **Documento auto-suficiente pra onboarding de nova sessão Claude**
> (Claude Code, claude.ai web, ou outro contexto). Cole integral na
> primeira mensagem e a sessão entra com contexto completo.

---

## 0. Como usar este documento

**Para o Henrique:**
- Cola este markdown integral na primeira mensagem da nova sessão.
- Pede pra Claude confirmar leitura + ler `backend/CLAUDE.md` e `docs/SECRETS.md`.
- Pede também pra ela ler a última sessão em `vault/Sessões/2026-04-27.md`.

**Para a nova Claude (sessão receptora):**

1. **Lê este documento integral antes de qualquer ação.**
2. **Lê em seguida** (na ordem):
   - `backend/CLAUDE.md` — guia permanente do agente backend (482 linhas, fonte da verdade técnica)
   - `docs/SECRETS.md` — gestão operacional de secrets (12 seções)
   - `vault/Sessões/2026-04-27.md` — última sessão (3 mini-CPs MEDIUM + pausa de docs final)
3. **Dá um resumo curto (max 5 linhas) em português** pro Henrique:
   - Onde paramos
   - O que está em andamento
   - Qual o próximo passo lógico
4. **Espera confirmação** do Henrique antes de começar a trabalhar.

---

## 1. Identidade do projeto

**Nome:** ISV Delivery

**Visão:** Plataforma de delivery local para pequenas cidades do Brasil,
começando por **Tarumirim/MG** (piloto). Diferencial: taxa menor que
iFood/Rappi, foco em cidades pequenas onde os grandes não operam bem.

**Stakeholders:**
- **Henrique Pasquetto** — sole developer + sole operator. cotah.pasquetto@gmail.com
- Sócio comercial (não-técnico) — fechamento de contratos com lojistas piloto

**Restrições reais:**
- Pré-piloto, dev solo, sem CI/CD ativo, sem deploy em produção ainda
- CNPJ pendente (bloqueia Pagar.me + Zenvia provider real)
- Plataforma de hospedagem decidida: **Railway** (staging + produção)
- Lições do incidente outubro 2025 (Service Account Google Play exposta) aplicadas preventivamente

**Documentação fonte da verdade:**
- **Vault Obsidian** (cérebro do projeto): `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\`
- **Repo monorepo:** `C:\Users\henri\Desktop\delivery\` (https://github.com/cotah/delivery-isv)
- **Branch primária:** `main`

---

## 2. Stack técnico

| Camada | Tech | Estado |
|---|---|---|
| Backend API | Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic | **Feature-complete exceto Order cycle** |
| Banco | PostgreSQL 16 (Docker local: porta 5433) | 18 tabelas, 22 migrations |
| Cache/rate limit | Redis 7 (Docker local: porta 6380) | Operacional |
| Mobile cliente | React Native (decidido) ou Flutter (legacy) | **Não iniciado** (`apps/customer/` vazio) |
| Mobile entregador | React Native ou Flutter | **Não iniciado** (`apps/driver/` vazio) |
| Painel lojista | Next.js | **Não iniciado** (`web/merchant/` vazio) |
| Painel admin | Next.js | **Não iniciado** (`web/admin/` vazio) |
| Hospedagem | Railway | **Configuração não criada ainda** |
| Pagamentos | Pagar.me | **Pendente CNPJ** |
| SMS | Zenvia | **Pendente CNPJ** (hoje: MockSMSProvider) |
| Mapas | Google Maps APIs | Não usado ainda |
| Push | Firebase + APNs | Não usado ainda |
| Tooling Python | `uv` + `ruff` + `mypy strict` + `pytest` | Tudo verde |
| Secrets management | Railway Secrets (built-in) — ADR-028 | Pre-piloto, sem rotação automática |
| Detecção de leak | gitleaks pre-commit hook (fallback gracioso) | Hook instalado, binário não-instalado ainda no Windows |

---

## 3. Estado atual congelado (2026-04-27)

**HEAD:** `7bb07f1` — `docs(backend): close pre-pilot debts cycle — ZERO debts achieved`

**Métricas técnicas:**
- **651 testes** passando (~5s)
- **123 source files** com mypy strict limpo
- **22 migrations** aplicadas (alembic head: `64f6e6cef194`)
- **18 tabelas** no Postgres
- **13 endpoints REST** em `/api/v1/`
- **14 ErrorCodes** no envelope canônico (ADR-022)
- **9 StrEnums** em `app/domain/enums.py`
- **29 ADRs** registrados no vault
- Zero `# noqa`, zero `# type: ignore` novos (2 narrow ignores legítimos pré-existentes em `tests/services/sms/test_base.py`)

**Lista de débitos pré-piloto: ✅ ZERO**

Backend pronto pro Order cycle sem dividas técnicas bloqueantes pré-piloto.

**O que cliente real consegue fazer hoje (ponta-a-ponta exceto Order):**
1. Splash + lista de lojas com category/city aninhados, paginação
2. Detalhe da loja com endereço completo + horários de funcionamento + `is_open_now` calculado em runtime
3. Cardápio organizado por seção (`menu_section` enum), produtos em destaque (`featured`), variações + addons aninhados 3 níveis
4. Login OTP via SMS (Mock provider local; Zenvia real depende de CNPJ)
5. Perfil User + Customer (lazy creation, validação CPF/email/birth_date)
6. Gerenciar endereços de entrega (CRUD completo, `is_default` switch transacional, soft-delete)

**Falta apenas Order cycle** pra cliente fazer pedido.

---

## 4. Estrutura do monorepo

```
delivery/
├── backend/                    # FastAPI + Postgres + Redis (FEATURE-COMPLETE EXCETO ORDER)
│   ├── app/
│   │   ├── __init__.py        # exporta __version__
│   │   ├── main.py            # FastAPI app + middlewares + routers + handlers
│   │   ├── api/
│   │   │   ├── deps.py        # get_db_session, get_sms_provider, get_current_user
│   │   │   ├── errors.py      # ErrorCode StrEnum + handlers ADR-022
│   │   │   ├── health.py      # GET /health (liveness)
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       ├── auth.py    # POST /auth/request-otp, POST /auth/verify-otp
│   │   │       ├── users.py   # GET /users/me (protegido)
│   │   │       ├── customers.py  # GET/POST/PATCH /customers/me
│   │   │       ├── addresses.py  # CRUD /customers/me/addresses
│   │   │       └── stores.py  # GET /stores, /stores/{id}, /stores/{id}/products
│   │   ├── core/
│   │   │   ├── config.py      # Pydantic Settings (lru_cache)
│   │   │   └── rate_limit.py  # slowapi Limiter + check_phone_rate_limit + handler 429
│   │   ├── db/
│   │   │   ├── base.py        # DeclarativeBase + naming_convention
│   │   │   ├── session.py     # engine + get_db_session
│   │   │   ├── types.py       # UUIDPK type alias
│   │   │   ├── identifiers.py # new_uuid + new_public_id
│   │   │   └── mixins.py      # TimestampMixin, SoftDeleteMixin, CreatedAtMixin
│   │   ├── domain/
│   │   │   └── enums.py       # 9 StrEnums (Environment, AddressType, ...)
│   │   ├── models/            # 14 modelos SQLAlchemy
│   │   ├── repositories/      # camada de leitura
│   │   ├── services/          # camada de regra de negócio
│   │   │   ├── auth/
│   │   │   │   ├── jwt.py     # HS256, hierarquia ExpiredTokenError/MalformedTokenError
│   │   │   │   └── otp.py     # request_otp + verify_otp + find_or_create_user
│   │   │   ├── sms/
│   │   │   │   ├── base.py    # SMSProvider Protocol + MAGIC_FAILURE_PHONE
│   │   │   │   └── mock.py    # MockSMSProvider (dev only, fail-fast em prod)
│   │   │   ├── customers.py   # CustomerError + 2 subclasses
│   │   │   ├── addresses.py   # is_default switch transacional
│   │   │   └── stores.py      # is_store_open helper
│   │   ├── schemas/           # Pydantic request/response
│   │   └── utils/
│   │       └── validators.py  # validate_cpf/cnpj/phone_e164/email + mask_*_for_log
│   ├── tests/                 # 651 testes pytest
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/          # 22 migrations
│   ├── scripts/               # vazio (probe scripts são throwaway)
│   ├── pyproject.toml         # deps + ruff/mypy/pytest config
│   ├── uv.lock                # lockfile (commitado)
│   ├── .env                   # GITIGNORED (valores reais locais)
│   ├── .env.example           # template (commitado)
│   ├── README.md
│   └── CLAUDE.md              # GUIA PERMANENTE — auto-loaded em sessão Claude Code
│
├── apps/
│   ├── customer/              # VAZIO (mobile RN não iniciado)
│   └── driver/                # VAZIO (mobile RN não iniciado)
├── web/
│   ├── merchant/              # VAZIO (Next.js não iniciado)
│   └── admin/                 # VAZIO (Next.js não iniciado)
├── docs/
│   ├── SECRETS.md             # GESTÃO DE SECRETS — operacional
│   └── HANDOFF.md             # ESTE DOCUMENTO
├── .github/
│   └── workflows/.gitkeep     # CI/CD não iniciado
├── scripts/                   # vazio
├── docker-compose.yml         # Postgres 16 + Redis 7 (local dev)
├── .gitleaks.toml             # config gitleaks (raiz, ADR-028)
├── .gitignore                 # cobre .env + Service Account JSON defensivo
├── .git/hooks/pre-commit      # NÃO TRACKED (gitleaks com fallback gracioso)
├── CLAUDE.md                  # regras de IA do monorepo (raiz)
└── README.md
```

**Vault (fora do repo, fonte da verdade arquitetural):**
```
C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\
├── 00 - Visão & Problema.md
├── 01 - Escopo MVP (resumo).md
├── 02 - Stack & Arquitetura.md
├── 09 - Roadmap.md            # UTF-8 SEM BOM
├── 11 - Decisões Técnicas (log).md  # UTF-16 LE COM BOM (FF FE)
├── 12 - Bugs & Fixes.md
└── Sessões/
    ├── _template.md           # 7 seções: Contexto, O que foi feito, Decisões, Bugs encontrados, Bugs corrigidos, Próximos passos, Observações
    ├── 2026-04-21.md ... 2026-04-27.md  # diários por sessão (UTF-8 SEM BOM)
```

---

## 5. Convenções e workflow obrigatórios

### 5.1 Filosofia
- **Cirurgia, não tutorial.** Cada linha de código tem motivo rastreável.
- **PASSO 0 inspeção obrigatória** antes de cada mini-CP — pegou 41+ divergências em ciclos anteriores. Padrão profissional.
- **ADR antes de implementar** quando decisão é arquitetural ou nova.
- **Defense-in-depth** sempre que possível (Pydantic + @validates + DB constraints + service guards).
- **Fail-loud no startup** vs **fail-open em camadas secundárias** (rate limit, observability).

### 5.2 Mini-CP cirúrgico (pattern de execução)
Cada unidade de trabalho segue:
1. **PASSO 0** — inspeção do código real, mapeamento de patterns existentes, descoberta de armadilhas
2. **Decisões alinhadas** com Henrique antes de implementar (sub-decisões nomeadas D1, D2, ... ou Q1, Q2, ...)
3. **Implementação cirúrgica** — escopo único, zero refactor fora do escopo
4. **Validação** com 5 comandos: `pytest`, `ruff check`, `ruff format --check`, `mypy app tests`, `alembic check`
5. **Reprodução empírica** quando comportamento de lib externa é central (script Python descartável)
6. **Pausa pra revisão** antes do commit
7. **Commit + push** com mensagem detalhada
8. **Atualização do vault** (Roadmap + Sessão do dia)

### 5.3 Padrões obrigatórios — não negociáveis
Detalhes em `backend/CLAUDE.md` seção 2. Resumo:
- **PK:** sempre `UUIDPK` (type alias). Python `default=new_uuid()` + Postgres `server_default=text("gen_random_uuid()")`.
- **Mixins:** `TimestampMixin` (entidades mutáveis), `SoftDeleteMixin` (descontinuáveis), `CreatedAtMixin` (logs append-only). Mutuamente exclusivos.
- **Enums:** sempre `mapped_column(String(N))` explícito + CHECK dinâmico do StrEnum. NUNCA `sa.Enum` nativo.
- **Dinheiro:** sempre `<name>_cents INTEGER`. CHECK >= 0. NUNCA Numeric/Decimal/Float.
- **FKs:** entidade=`RESTRICT`, composição=`CASCADE`. Tabela de referência completa em CLAUDE.md.
- **Validação:** Pydantic na borda + `@validates` no model (defense-in-depth ADR-010). Função canônica única em `app/utils/validators.py`.
- **PII em logs:** sempre mascarado (`mask_phone_for_log`, `mask_cpf_for_log`, `mask_cnpj_for_log`, `mask_tax_id_for_log`).
- **`__repr__` nunca expõe valor cru de PII.**

### 5.4 Proibições explícitas
- ❌ NUNCA usar `sed`/regex em batch pra substituir strings em múltiplos arquivos (regra herdada — quebrou tudo uma vez)
- ❌ NUNCA commitar `.env`, chaves privadas, tokens, senhas
- ❌ NUNCA deletar migrations já aplicadas em staging/produção
- ❌ NUNCA `git push --force` em `main`
- ❌ NUNCA `git commit --no-verify` recorrente (apenas com justificativa em commit dedicado)
- ❌ NUNCA usar emojis em nomes de pastas, arquivos, caminhos ou identificadores técnicos (compatibilidade Windows)
- ❌ NUNCA escrever ADR sem antes verificar código existente
- ❌ NUNCA assumir comportamento de lib externa sem reprodução empírica quando central pra fix

---

## 6. Schema do banco (18 tabelas, 22 migrations)

| # | Tabela | Rows | Notas |
|---|---|---|---|
| 1 | `cities` | 3 | Seed MG: Tarumirim, Itanhomi, Alvarenga |
| 2 | `customers` | 0 | Produção real, sem seed. FK customers.user_id UNIQUE NOT NULL |
| 3 | `addresses` | 0 | FK customer + city + UNIQUE parcial em is_default |
| 4 | `categories` | 3 | Seed: Pizzaria, Lanchonete, Marmita. Tabela lookup ADR-013 |
| 5 | `stores` | 0 | tax_id polimorfo CPF/CNPJ. 5 campos extension HIGH #1 |
| 6 | `store_opening_hours` | 0 | Slots de horário ADR-026 dec.1 |
| 7 | `products` | 0 | Status enum + display_order/menu_section/featured |
| 8 | `product_variations` | 0 | Status binário ACTIVE/INACTIVE (HIGH #3) |
| 9 | `addon_groups` | 0 | type SINGLE/MULTIPLE + min/max selections |
| 10 | `addons` | 0 | price_cents (0 = grátis) |
| 11 | `product_addon_groups` | 0 | Junção M:N com dual CASCADE |
| 12 | `orders` | 0 | 20 colunas, public_id ISV-XXXXXXXX (8 chars), payment fields |
| 13 | `order_items` | 0 | Snapshot granular de Product+Variation no momento do pedido |
| 14 | `order_item_addons` | 0 | Snapshot granular de Addon no momento do pedido |
| 15 | `order_status_logs` | 0 | Append-only (CreatedAtMixin), primeiro do projeto |
| 16 | `users` | 0 | Identidade via OTP. Phone E.164 UNIQUE |
| 17 | `otp_codes` | 0 | Códigos descartáveis. attempts (max 3) + sha256 hash |
| 18 | `alembic_version` | 1 | Controle Alembic |

**Migrations** em `backend/alembic/versions/` (22 aplicadas em sequência). Ver lista completa em `backend/CLAUDE.md` seção 1.

**Convenção de FK** (decisão central ADR-011 vs ADR-015):
- Customer/Store/City/Category/etc. → `RESTRICT` (entidade)
- variations de Product, addons de AddonGroup, junções M:N → `CASCADE` (composição estrita)

---

## 7. Endpoints REST implementados (13 em `/api/v1/`)

| Método | Path | Auth | ErrorCodes | Notas |
|---|---|---|---|---|
| GET | `/api/v1/stores` | público | `validation_failed` | Lista lojas APPROVED. Paginação offset/limit. category+city aninhados |
| GET | `/api/v1/stores/{store_id}` | público | `store_not_found` | Detalhe + endereço + horários + `is_open_now` |
| GET | `/api/v1/stores/{store_id}/products` | público | `store_not_found` | Cardápio aninhado 3 níveis (variations+addons) |
| POST | `/api/v1/auth/request-otp` | público | `sms_provider_error`, `rate_limited` | Rate limit IP (10/h) + phone (3/h). 502 se SMS falhar |
| POST | `/api/v1/auth/verify-otp` | público | `invalid_otp_code`, `rate_limited` | Rate limit IP (30/h) + phone (10/h). Retorna JWT |
| GET | `/api/v1/users/me` | JWT | `unauthenticated`, `token_expired`, `invalid_token` | Primeiro endpoint protegido |
| GET | `/api/v1/customers/me` | JWT | `customer_not_found` | 404 se User não tem Customer ainda |
| POST | `/api/v1/customers` | JWT | `customer_already_exists`, `validation_failed` | 201 lazy creation. Phone vem do User (ADR-027 dec.6) |
| PATCH | `/api/v1/customers/me` | JWT | `customer_not_found`, `validation_failed` | exclude_unset, atualiza name/email/cpf/birth_date |
| GET | `/api/v1/customers/me/addresses` | JWT | — | Ordering is_default DESC + created_at DESC |
| POST | `/api/v1/customers/me/addresses` | JWT | `city_not_found`, `validation_failed` | 201. is_default switch transacional |
| PATCH | `/api/v1/customers/me/addresses/{id}` | JWT | `address_not_found` (disfarçado), `validation_failed` | 404 se de outro customer (ADR-027 A) |
| DELETE | `/api/v1/customers/me/addresses/{id}` | JWT | `address_not_found` | 204. Soft-delete. Sem auto-promoção |

**Padrões REST:**
- Envelope de erro `{"error": {"code", "message", "details"?}}` (ADR-022)
- Envelope de paginação `{"items", "total", "offset", "limit"}` (ADR-023)
- 14 ErrorCodes machine-readable em `app/api/errors.py`
- HTTPException com `detail={"code", "message"}` reusa o handler genérico
- 429 com `Retry-After` header + `retry_after_seconds=3600` (hardcoded enquanto todos os limits forem `/hour`)

---

## 8. Auth — defesa em camadas

**Stack do auth (ADR-025):**

```
Cliente → POST /auth/request-otp (phone E.164)
    ↓
[Camada 1] @limiter.limit IP slowapi+Redis (10/h request, 30/h verify)
    ↓
[Camada 2] check_phone_rate_limit phone-based (3/h request, 10/h verify) — fail-open replicado
    ↓
[Pydantic] validate_phone_e164 STRICT (rejeita variantes "+55 31 99988-7766")
    ↓
[Service] request_otp: invalida OTPs anteriores, gera código novo, sha256 hash, persist
    ↓
[Provider] MockSMSProvider (local) / Zenvia (futuro com CNPJ)
    ↓
Cliente recebe SMS → POST /auth/verify-otp (phone + code)
    ↓
[Camadas 1+2] mesmas defesas
    ↓
[Service] verify_otp: SELECT FOR UPDATE em OtpCode, hmac.compare_digest, attempts (max 3)
    ↓
[Service] find_or_create_user com retry IntegrityError (race condition handling)
    ↓
[JWT] HS256, expiração 60min, claims sub/phone/iat/exp/type
    ↓
Cliente recebe JWT → GET /users/me Bearer token
    ↓
[Middleware] get_current_user dependency — diferenciação token_expired vs invalid_token
    ↓
[RFC 6750] WWW-Authenticate header em 401
```

**Camadas de proteção contra abuse:**
1. Rate limit IP (anti-scrape)
2. Rate limit phone (anti-targeted-abuse)
3. `OtpCode.attempts` (max 3, anti-brute-force no DB)
4. `MAGIC_FAILURE_PHONE` em prod (DDD impossível, fail-fast)
5. `hmac.compare_digest` (timing attack defense)
6. sha256 do código (DB leak defense)
7. Anti-enumeração (1 mensagem genérica em verify-otp pra 5 cenários falha)
8. Zenvia upstream (rate limit no provider, futuro)
9. Fail-open Redis (slowapi flags + helper try/except — outage não vira 500)

---

## 9. ADRs ativos (29 — todas no vault `11 - Decisões Técnicas (log).md`)

| # | Resumo |
|---|---|
| 003 | UUID PK + public_id curto só pra entidades expostas |
| 004 | TimestampMixin (created_at + updated_at) |
| 005 | onupdate=func.now() — limitação testabilidade documentada |
| 006 | Enums via String(N) + CHECK dinâmico, NÃO sa.Enum nativo |
| 007 | Dinheiro sempre <name>_cents INTEGER |
| 008 | City lookup table dedicada |
| 010 | Defense-in-depth Pydantic + @validates |
| 011 | FK entidade RESTRICT |
| 012 | tax_id polimorfo CPF/CNPJ |
| 013 | Category lookup table |
| 014 | Product com variations e addons em tabelas separadas |
| 015 | FK composição CASCADE |
| 016 | Snapshot granular Order/OrderItem/OrderItemAddon |
| 017 | Máquina de estados Order com Pagar.me |
| 018 | public_id ISV-XXXXXXXX (8 chars, alfabeto reduzido 31 símbolos) |
| 019 | Append-only log + CreatedAtMixin |
| 020 | Estrutura 4 camadas: schemas → api → services → repositories → models |
| 021 | API versioning /api/v1/ |
| 022 | Formato de erro uniforme {"error": {"code", "message", "details"?}} |
| 023 | Envelope paginação {"items", "total", "offset", "limit"} |
| 024 | Catálogo público — cardápio aninhado 3 níveis |
| 025 | Auth via OTP por SMS + JWT HS256, 6 camadas defense-in-depth |
| 026 | Store extension (8 decisões + 4 reforços CP1b) — HIGH #1 |
| 027 | User ↔ Customer FK 1:1 + 15 decisões do Customer cycle |
| 028 | **Estratégia de gestão de secrets** (este ciclo MEDIUM) — Railway pre-piloto + 3 triggers Doppler + gitleaks soft enforcement + docs/SECRETS.md |
| 029 | **Estratégia de identidade multi-papel** — User → Customer + Merchant + Delivery (Modelo A, 14 decisões em 4 blocos: estratégia raiz, Merchant cycle, Delivery cycle, login multi-perfil) |

---

## 10. Patterns reusáveis estabelecidos (categorizados)

### 10.1 Auth cycle (10 patterns)
- `@dataclass(frozen=True)` para DTOs internos (SendResult, AccessTokenPayload)
- Hierarquia de exceções (base + subclasses) para granularidade sem overhead
- "Commit antes de HTTP externo" em services com provider externo
- PASSO 0 inspeção obrigatória — pegou 41+ divergências
- Constantes module-level forçando consistência (INVALID_OTP_MESSAGE)
- Singleton + lru_cache para providers e config
- HTTPBearer(auto_error=False) + 401 manual com formato ErrorResponse
- mask_phone_for_log vs mask_phone_for_display (separação por contexto)
- get_or_create com retry IntegrityError (race condition handling)
- SELECT FOR UPDATE pra serializar operações concorrentes

### 10.2 HIGH cycle (14 patterns)
- `--sql` preview obrigatório antes de migration não-trivial
- CheckConstraint pattern correto (sufixo só, naming_convention prefixa)
- Verificação de segurança antes de mudar schema validador
- Opção E para migration NOT NULL em banco vazio (honesta, sem placeholder)
- HttpUrl em TODOS campos URL (sem fragmentação)
- mask_phone_for_log proativamente no `__repr__` (evita débito LGPD)
- relationship lazy="raise" sem back_populates + sem cascade Python
- populate_by_name=True com validation_alias quando service constrói explicitamente
- Testar lógica pura com objetos em memória + DB com SQL direto
- Combinar contratos novos com existentes em vez de substituir
- Documentar timezone hardcoded com plano de migração desde dia 1
- Pattern proativo de revisar pós-descanso decisões com prazo curto
- Bug descoberto = bug resolvido na mesma sessão (custo ~30min)
- Migration aditiva com server_default cobre rows pré-existentes (zero downtime)

### 10.3 Customer cycle (5 patterns)
- POST que cria recurso REST com `status_code=status.HTTP_201_CREATED` explícito
- Hierarquia de exceções no service traduzida pra HTTPException no endpoint
- Service recebe `current_user` completo (não só user_id)
- DELETE 204 No Content + helpers `_raise_*` DRY no endpoint module
- Pattern `overlaps` em ambos os lados de relationship 1:1 reverso sem `back_populates`

### 10.4 MEDIUM cycle (7 patterns)
- Reprodução empírica antes de implementar handler de exception
- Slowapi flags nativas sobre middleware custom (preferir features upstream)
- Helper manual com fail-open replicado (slowapi swallow_errors NÃO cobre hit manual)
- Defesa em camadas independentes pra endpoints sensíveis
- Regra inviolável valores de secrets em chat (mesmo se solicitado, recusar)
- Documentação operacional em `docs/SECRETS.md` (NÃO SECURITY.md/RUNBOOK.md)
- Soft enforcement com upgrade path (gitleaks com fallback gracioso)

---

## 11. Débitos pendentes (TODOS pós-piloto, NÃO bloqueiam staging nem MVP)

### 11.1 LOW
- **Impossibilidade de testar empiricamente `onupdate=func.now()`** no setup atual de fixture. Aceito via ADR-005 (limitação documentada). Ciclo dedicado a infraestrutura de testes futuro.
- **Padronização retroativa dos ADRs 016-024** — débito LOW antigo, não bloqueante.

### 11.2 Pós-piloto previstos
- **LGPD cycle** — `anonymize_customer` real + `DELETE /users/me` + auditoria completa de PII em logs
- **Observability ops** — Sentry/Datadog integration (logger `slowapi` deve ser capturado)
- **Order rotation com graceful fallback JWT** — quando volume justificar (hoje mass logout aceito)
- **Decisões pendentes Order cycle** (ver seção 12)

### 11.3 Ações manuais não-bloqueantes
- `scoop install gitleaks` (Windows) pra ativar pre-commit hook (hoje em fallback gracioso)

---

## 12. Próximo grande ciclo: Order endpoints

### 12.1 Foundation existente
- `Order`, `OrderItem`, `OrderItemAddon`, `OrderStatusLog` models (commits `26d7243`, `5dfc717`, `d706566`, `99e486a`)
- FK `Order.customer_id` RESTRICT + FK `Order.store_id` RESTRICT
- public_id `ISV-XXXXXXXX` (8 chars, alfabeto reduzido)
- Snapshot granular (ADR-016): Product+Variation+Addon snapshotados no momento do pedido

### 12.2 Falta apenas camada de aplicação
Schemas Pydantic + repository + service + endpoints. Estimativa: 6-10h ritmo Henrique, 4-5 sub-CPs. ADR-031 provavelmente revisitando ADR-017.

### 12.3 Estrutura provável (a confirmar via PASSO 0 do CP1)
- **CP1**: Schemas Pydantic Order/OrderItem/OrderItemAddon + Read endpoints (`GET /orders`, `GET /orders/{id}`)
- **CP2**: `POST /orders` — criar pedido (transação Customer + Store + Items + Addons + status inicial)
- **CP3**: Status transitions (`PATCH /orders/{id}/status` — lojista atualiza)
- **CP4**: Listagem por lojista (`GET /stores/{store_id}/orders` pra dashboard)
- **CP5**: Pausa de docs final

### 12.4 Decisões pendentes (a confirmar ANTES de implementar CP1)
1. **`user_type` strategy** (cliente / lojista / entregador) — bloqueia trabalho multi-perfil. Hoje só temos User genérico via OTP.
2. **Real-time strategy** — WebSocket vs polling pra atualização de status do pedido
3. **Status transitions** — state machine formal (XState? statemachine library?) vs ad-hoc com `@validates`
4. **Matching algorithm** (entregador → pedido) — proximidade geográfica, FIFO, híbrido?

---

## 13. Comandos úteis

### 13.1 Backend (a partir de `backend/`)
```bash
uv sync                                    # instala deps + cria .venv
uv run pytest                              # suite completa (651 testes)
uv run pytest tests/api/v1/test_auth.py    # arquivo específico
uv run pytest -k "rate_limit"              # padrão de nome
uv run ruff check .                        # lint
uv run ruff format --check .               # format check
uv run ruff format .                       # aplica formatação
uv run mypy app tests                      # type check strict (123 source files)
uv run alembic current                     # revision atual
uv run alembic check                       # drift model/DB (zero ops = OK)
uv run alembic upgrade head                # aplica migrations pendentes
uv run alembic revision --autogenerate -m "..."  # gera migration
uv run uvicorn app.main:app --reload --port 8000  # roda API local
```

### 13.2 Docker (a partir do repo root)
```bash
docker compose ps                          # status dos containers
docker compose up -d                       # sobe Postgres + Redis em background
docker compose logs -f postgres            # logs ao vivo
docker compose stop redis                  # parar serviço específico (debug)
docker compose start redis                 # reiniciar
docker exec delivery-postgres-1 psql -U isv -d isv_delivery -c "\d+ <table>"  # inspeção DDL
```

### 13.3 Git
```bash
git status
git log --oneline -10
git diff backend/path/to/file.py
git add backend/path/to/file.py            # paths explícitos, NUNCA -A nem .
git commit -m "$(cat <<'EOF'
feat(backend): description...

[detailed body]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main                       # NUNCA --force em main
```

### 13.4 Vault (PowerShell, encoding-aware)
```powershell
# Ler arquivo UTF-8 sem BOM (Roadmap, Sessões)
[System.IO.File]::ReadAllText("C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\09 - Roadmap.md")

# Escrever UTF-8 sem BOM
[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $false))

# Ler arquivo UTF-16 LE (Decisões Técnicas)
Get-Content -LiteralPath $path -Encoding Unicode -Raw

# Escrever UTF-16 LE preservando BOM
Set-Content -LiteralPath $path -Value $content -Encoding Unicode -NoNewline

# Verificar BOM
Get-Content -LiteralPath $path -Encoding Byte -TotalCount 4 | ForEach-Object { '{0:X2}' -f $_ }
# UTF-8 sem BOM: começa com bytes ASCII do conteúdo
# UTF-8 com BOM: EF BB BF ...
# UTF-16 LE com BOM: FF FE ...
```

---

## 14. Infraestrutura local (ADR-002)

### Postgres
- Container: `delivery-postgres-1`
- Host port: **5433** (não-padrão pra coexistência com outros projetos)
- Container port: 5432
- Credenciais dev: `isv` / `isvpass` / `isv_delivery`
- Conexão: `postgresql+psycopg://isv:isvpass@localhost:5433/isv_delivery`

### Redis
- Container: `delivery-redis-1`
- Host port: **6380** (não-padrão)
- Container port: 6379
- Conexão: `redis://localhost:6380/0`

### Configuração Pydantic Settings
- 13 vars declaradas em `app/core/config.py`
- 2 `SecretStr` (REQUIRED, fail-loud no startup): `SECRET_KEY` e `JWT_SECRET_KEY`
- 3 strs REQUIRED: `DATABASE_URL`, `REDIS_URL` (parcial — contém credencial), `JWT_SECRET_KEY`
- Restantes têm defaults
- Acesso 100% via `get_settings()` (lru_cache). **Zero `os.environ` direto em `backend/app/`.**

---

## 15. Caminhos chave

| Recurso | Path |
|---|---|
| Repo monorepo | `C:\Users\henri\Desktop\delivery\` |
| Backend | `C:\Users\henri\Desktop\delivery\backend\` |
| Vault Obsidian (cérebro) | `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\` |
| ADRs (vault) | `<vault>\11 - Decisões Técnicas (log).md` (UTF-16 LE) |
| Roadmap (vault) | `<vault>\09 - Roadmap.md` (UTF-8 sem BOM) |
| Sessões (vault) | `<vault>\Sessões\<YYYY-MM-DD>.md` (UTF-8 sem BOM) |
| Template sessão | `<vault>\Sessões\_template.md` |
| Doc operacional secrets | `C:\Users\henri\Desktop\delivery\docs\SECRETS.md` |
| Este handoff | `C:\Users\henri\Desktop\delivery\docs\HANDOFF.md` |
| GitHub remote | https://github.com/cotah/delivery-isv |
| User email | cotah.pasquetto@gmail.com |

---

## 16. Regras invioláveis (NUNCA QUEBRAR)

### 16.1 Valores de secrets em chat
**NUNCA trazer valores reais de secrets pra conversa. Sem exceção.**

Proibido (mesmo se solicitado explicitamente pelo Henrique):
- Valor literal: `JWT_SECRET_KEY=abc123...`
- Valor mascarado: `JWT_SECRET_KEY=abc1***456`
- Valor parcial: `começa com "abc"`
- Hash do valor
- Qualquer codificação (base64, hex, etc.)

Permitido:
- Nome da variável: `JWT_SECRET_KEY`
- Localização: `backend/.env linha 5`, `app/core/config.py:30`
- Status: presente/ausente
- Atributos estruturais: comprimento aproximado, tipo (string/int), formato esperado (UUID, urlsafe base64)

**Razão:** chat com IA conta como exposição. Valor de secret só vive em 3 lugares: memória do processo, cofre operacional (Railway Secrets), `.env` local de cada dev (gitignored).

Lesson learned do incidente outubro 2025 (Service Account Google Play exposta). Detalhes em `docs/SECRETS.md` seção 12.

### 16.2 Ações destrutivas exigem confirmação explícita
NUNCA executar sem aviso prévio:
- `rm -rf`
- `git push --force`
- `git reset --hard`
- `DROP TABLE`
- `TRUNCATE`
- Comandos que afetam staging/produção

Em caso de dúvida: **PARAR e perguntar antes**.

### 16.3 PASSO 0 obrigatório
Antes de qualquer mini-CP de fix ou feature: inspecionar código real, mapear patterns existentes, descobrir armadilhas. Pegou 41+ divergências em ciclos anteriores.

### 16.4 ADR antes de implementar
Decisão arquitetural ou nova exige ADR registrado no vault ANTES da implementação. ADR baseado em código real, não intenção projetada.

### 16.5 Linting + tests verdes ANTES de commit
5 comandos sempre verdes: `pytest`, `ruff check`, `ruff format --check`, `mypy app tests`, `alembic check`. Zero tolerância pra warning ou type ignore não-justificado.

### 16.6 Defesa em camadas
Endpoints sensíveis (auth, payment, etc.) sempre múltiplas camadas independentes. Falha de uma não compromete outras.

### 16.7 Encoding preservado em arquivos do vault
- UTF-16 LE em `11 - Decisões Técnicas (log).md` (BOM `FF FE`)
- UTF-8 SEM BOM em `09 - Roadmap.md` e `Sessões/*.md`
- Pattern read-modify-write via PowerShell pra preservar (comandos em seção 13.4)

### 16.8 Não acumular débito enquanto barato de resolver
Pattern profissional: bug descoberto → bug resolvido na mesma sessão se custo ~30min. Pré-piloto entrar com lista limpa.

---

## 17. Lessons learned chave

### 17.1 Outubro 2025 — Service Account Google Play exposta
Service Account JSON commitada acidentalmente em commit público. Conta desabilitada após descoberta. Sem dano operacional confirmado mas chave considerada comprometida.

**Lessons aplicadas no projeto:**
1. "Uma vez exposto, considere comprometido" → base do princípio "rotacionar pós-incidente"
2. "Valor de secret só vive em 3 lugares" → regra de ouro do `docs/SECRETS.md`
3. `.gitignore` defensivo pré-uso → entries pra Service Account adicionadas mesmo antes de uso real
4. Chat com IA conta como exposição → política formal de NUNCA trazer valores reais (regra inviolável 16.1)

### 17.2 Abril 2026 — Drift `.env` vs `.env.example`
Mini-CP MEDIUM #1 detectou 5 vars em `.env.example` ausentes em `.env`. Funcionou via defaults mas confundia devs futuros. **Lesson:** processo explícito de sincronia documentado em `docs/SECRETS.md` seção 9.

### 17.3 Abril 2026 — Slowapi swallow_errors NÃO cobre hit manual
Mini-CP MEDIUM #2 descobriu que `swallow_errors=True` aplica APENAS ao `_check_request_limit` interno do slowapi (chamado pelos decorators `@limiter.limit`). Chamada manual a `limiter.limiter.hit()` bypassa essa lógica. **Lesson:** quando hit manual é necessário, replicar try/except no helper pra preservar fail-open.

### 17.4 Bug-do-bug em CheckConstraint
Mini-CP HIGH #3 fix LOW: `op.create_check_constraint(...)` com nome já-prefixado (`ck_product_variations_status`) ficou `ck_product_variations_ck_product_variations_status` no banco. **Lesson:** passar SÓ sufixo; naming_convention sempre prefixa. Detectado no CP2 e resolvido em ~30min via micro-CP entre CP2 e CP1a.

### 17.5 ADR escrito sem verificar código existente
ADR-018 redigido com formato `ISV-XXXXXX` (6 chars) sem consultar `new_public_id()` que já gerava 8 chars. Divergência detectada na hora de escrever testes. **Lesson:** antes de redigir qualquer ADR, listar arquivos/funções relacionados e ler código atual.

---

## 18. Como conduzir uma nova sessão

### 18.1 Início (obrigatório)
1. Ler este documento integral
2. Ler `backend/CLAUDE.md` (se Claude Code, é auto-loaded)
3. Ler `docs/SECRETS.md`
4. Ler última sessão em `vault/Sessões/<data-mais-recente>.md`
5. Confirmar leitura com resumo de 5 linhas em português pro Henrique:
   - Onde paramos
   - O que está em andamento
   - Qual o próximo passo lógico
6. **Esperar confirmação** do Henrique antes de começar

### 18.2 Durante a sessão
- Cada unidade de trabalho = mini-CP cirúrgico (PASSO 0 → decisões → implementação → validação → revisão → commit)
- Atualizar vault em tempo real:
  - Decisão arquitetural → ADR no `11 - Decisões Técnicas (log).md`
  - Bug descoberto/corrigido → `12 - Bugs & Fixes.md`
  - Risco novo → `10 - Riscos & Decisões em Aberto.md`
  - Feature completada → marcar `[x]` em `09 - Roadmap.md`
  - Nova dependência técnica → `02 - Stack & Arquitetura.md`

### 18.3 Fim de sessão (obrigatório)
1. Criar `vault/Sessões/<YYYY-MM-DD>.md` (se não existe ainda) seguindo `_template.md`
2. Preencher 7 seções: Contexto inicial, O que foi feito, Decisões tomadas, Bugs encontrados, Bugs corrigidos, Próximos passos, Observações
3. Atualizar `09 - Roadmap.md` marcando tarefas concluídas
4. Commit no repo de código com mensagem `chore(docs): session YYYY-MM-DD — <resumo 1 linha>`
5. Push pra origin/main

### 18.4 Sinais de fim de sessão
Henrique sinaliza com:
- "por hoje é só"
- "pode encerrar"
- "vamos parar aqui"
- ou equivalente

### 18.5 Pausas de docs entre ciclos
Pausa dedicada quando:
- Ciclo grande fecha (Auth, Customer, HIGH, MEDIUM, etc.)
- Marco do projeto bate (ZERO débitos, primeira venda, primeiro contratado)
- Decisão estratégica revisada após descanso

---

## 19. Histórico recente (últimos 15 commits — 2026-04-26 + 2026-04-27)

```
7bb07f1 docs(backend): close pre-pilot debts cycle — ZERO debts achieved
6f93a00 fix(backend): resolve MEDIUM #1 — secrets strategy + gitleaks + docs/SECRETS.md
a76c512 fix(backend): resolve MEDIUM #2 — phone-based rate limit em endpoints Auth
752a1dc fix(backend): resolve MEDIUM #3 — Redis fail-open runtime via slowapi flags
dadaced fix(backend): resolve 2 LOW pre-pilot debts — User repr LGPD + ADR-005 testability limitation
b36a01d fix(backend): resolve 2 pre-pilot debts — EmailStr + global ValueError handler
6f8eb49 docs(backend): close Customer cycle 4/4 — backend feature-complete except Order
d72ebc4 feat(backend): add Address CRUD endpoints (Customer cycle CP3 — closes feature work)
3563624 feat(backend): add Customer endpoints GET/POST/PATCH /customers/me (Customer cycle CP2 — ADR-027)
acd8e99 feat(backend): connect User <-> Customer via FK 1:1 (Customer cycle CP1 — ADR-027)
6140d7c docs(backend): close HIGH cycle 3/3 — backend mobile-ready
1c56b38 feat(backend): add StoreOpeningHours + is_open_now (HIGH debt #1 CP1b — closes HIGH 3/3)
b779b15 docs(backend): close CP1a HIGH #1, plan CP1b
c3dfecc feat(backend): expand Store with 5 fields (HIGH debt #1, CP1a — ADR-026)
1000cad docs(backend): close HIGH debt #2 + LOW debt fix
```

**Marcos do projeto fechados em ordem cronológica:**
- 2026-04-21 — Setup inicial + Order foundation (4 modelos)
- 2026-04-22 — Catálogo público completo (3 endpoints, ADR-024)
- 2026-04-25 — Auth cycle completo (4/4 checkpoints, ADR-025)
- 2026-04-26 — HIGH cycle completo (3/3 débitos, ADR-026) + Customer cycle completo (4/4, ADR-027) + 2 LOW pre-pilot resolvidos
- **2026-04-27 — MEDIUM cycle completo (3/3 débitos) + ZERO débitos pré-piloto + ADR-028**

---

## 20. Filosofia final

> Cada linha de código neste backend foi escrita com a premissa de ser
> **cirurgia**, não tutorial. Se algo parece "complicado sem motivo claro",
> é porque há um ADR explicando o motivo. Antes de simplificar, **leia o
> ADR correspondente**. Antes de adicionar feature/flag/complexidade,
> **registre a decisão**.
>
> A meta não é volume de código — é que cada decisão seja **rastreável**
> ao problema real de delivery em Tarumirim/MG.
>
> **Perfeccionismo pragmático vence produtividade descuidada.** Somos uma
> plataforma de pagamento financeiro com vidas de entregadores envolvidas.
> Erros têm custo real.

---

**Última atualização:** 2026-04-27 (após commit `7bb07f1`).

**Próxima atualização:** após próximo marco do projeto (provavelmente fim do Order cycle CP1).

**Autor:** Henrique Pasquetto + Claude (sessões consecutivas Auth → Catálogo → HIGH → Customer → MEDIUM → ZERO débitos).
