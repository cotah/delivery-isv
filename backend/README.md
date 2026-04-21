# ISV Delivery Backend

## Visão

API REST do ISV Delivery construída com **FastAPI + SQLAlchemy 2 + Alembic + Postgres + Redis**. É o coração de negócio da plataforma: autentica usuários, gerencia catálogo, cria pedidos, orquestra pagamentos e entregas. Este subprojeto vive em `backend/` dentro do monorepo ISV Delivery.

## Pré-requisitos

- **Python 3.12** — instalado via `uv`. NÃO usar o Python 3.14 global (projeto trava em `>=3.12,<3.13`).
- **Docker Desktop** rodando — necessário para Postgres e Redis locais.
- **uv 0.11+** — instalar: https://docs.astral.sh/uv/getting-started/installation/

Confira as versões:

```bash
uv --version              # >= 0.11
docker --version          # 24+
docker compose version    # v2+
```

## Setup inicial

A partir do diretório `backend/`:

```bash
# 1. Instala dependências (cria .venv automaticamente com Python 3.12)
uv sync

# 2. Copia o template de variáveis e edita SECRET_KEY
cp .env.example .env
# Abra .env e substitua SECRET_KEY por um valor real, gerado com:
#   openssl rand -hex 32

# 3. Sobe Postgres e Redis via Docker Compose (a partir da raiz do monorepo)
cd ..
docker compose up -d
cd backend

# 4. Aplica as migrations (no-op hoje; mantenha no fluxo)
uv run alembic upgrade head

# 5. Inicia a API com reload automático
uv run uvicorn app.main:app --reload --port 8000
```

Abra no navegador:

- http://localhost:8000/health — deve retornar `{"status": "ok", "env": "local", "version": "..."}`
- http://localhost:8000/docs — Swagger UI com a especificação OpenAPI

## Como testar

```bash
# Suíte completa (config padrão vem do pyproject.toml: -v --tb=short)
uv run pytest

# Explicitando flags, caso queira sobrescrever
uv run pytest -v --tb=short
```

## Como verificar qualidade

Os três comandos abaixo devem passar **sem warnings** antes de cada commit:

```bash
uv run ruff check .              # lint
uv run ruff format --check .     # formatação
uv run mypy app tests            # type check (strict + plugin Pydantic)
```

Para aplicar formatação automaticamente: `uv run ruff format .`

## Estrutura do código

```
backend/
├── app/
│   ├── __init__.py       # exporta __version__
│   ├── main.py           # instancia FastAPI, middlewares, routers
│   ├── api/              # endpoints REST agrupados por domínio
│   │   └── health.py     # GET /health (liveness probe)
│   ├── core/             # configuração e utilitários transversais
│   │   └── config.py     # Settings (pydantic-settings), lê .env
│   ├── db/               # camada de banco
│   │   └── base.py       # DeclarativeBase do SQLAlchemy 2.x
│   ├── models/           # modelos ORM (a ser preenchido)
│   └── schemas/          # schemas Pydantic de request/response (a ser preenchido)
├── tests/                # suíte pytest
│   ├── conftest.py       # fixtures compartilhadas (TestClient)
│   └── test_health.py    # testes do /health
├── alembic/              # migrations de banco
│   ├── env.py            # configurado para ler DATABASE_URL do .env
│   ├── versions/         # migrations geradas (vazio por enquanto)
│   ├── script.py.mako    # template para novas revisões
│   └── README
├── alembic.ini           # config do alembic (sqlalchemy.url injetado via env.py)
├── pyproject.toml        # dependências + config de ruff, mypy, pytest
├── uv.lock               # lockfile (SEMPRE commitar)
├── .env.example          # template das variáveis (commitado)
└── .env                  # valores locais reais (gitignored)
```

## Portas em uso (dev local)

| Serviço         | Porta host | Porta interna | Nota                    |
| --------------- | ---------- | ------------- | ----------------------- |
| Backend FastAPI | 8000       | —             | `uvicorn`               |
| Postgres        | **5433**   | 5432          | ver ADR-002 no vault    |
| Redis           | **6380**   | 6379          | ver ADR-002 no vault    |

Em staging/produção (Railway) as portas padrão são usadas — a customização é apenas local para coexistir com outros projetos.

## Variáveis de ambiente

Todas definidas em `.env` (baseadas em `.env.example`).

| Variável       | Tipo                                      | Onde é usada          | Descrição                                                                                    |
| -------------- | ----------------------------------------- | --------------------- | -------------------------------------------------------------------------------------------- |
| `APP_ENV`      | `"local" \| "staging" \| "production"`    | `app/core/config.py`  | ambiente corrente; valida com `Literal`                                                      |
| `APP_URL`      | `str`                                     | `app/core/config.py`  | URL base onde a API escuta externamente                                                      |
| `SECRET_KEY`   | `SecretStr` (obrigatória)                 | `app/core/config.py`  | chave pra assinar tokens/cookies; **gerar com `openssl rand -hex 32`**                       |
| `DATABASE_URL` | `str` (obrigatória)                       | SQLAlchemy + Alembic  | conexão Postgres; usa driver `postgresql+psycopg`                                            |
| `REDIS_URL`    | `str` (obrigatória)                       | (futuro cache/filas)  | conexão com Redis                                                                            |

Campos obrigatórios sem default causam **erro no startup** (fail-loud — intencional). Ver `.env.example` para o formato exato.

## Links para documentação

Todo o contexto de produto, arquitetura e decisões vive no vault Obsidian:

- **Cérebro do projeto:** `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\`
- **Arquitetura geral:** `02 - Stack & Arquitetura.md`
- **Decisões técnicas (ADRs):** `11 - Decisões Técnicas (log).md`
- **Roadmap:** `09 - Roadmap.md`
- **Modelo de dados:** `05 - Modelo de Dados (entidades).md`
- **Segurança & LGPD:** `08 - Segurança & LGPD.md`

Regras de trabalho com a IA: `../CLAUDE.md` (raiz do monorepo).
