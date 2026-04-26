# Secrets Strategy — ISV Delivery

> Documento operacional de gestao de secrets. Vive no repo (versionado) pra
> revisao por peer e auditoria. Conteudo aprovado em ADR-028 (vault).
>
> **Regra de ouro:** valor de secret so vive em 3 lugares:
> 1. Memoria do processo em runtime
> 2. Cofre operacional (Railway Secrets pre-piloto)
> 3. `.env` local de cada dev (gitignored)
>
> **Nunca** em commits, logs, screenshots, paste em chat (incluindo IA),
> issues do GitHub, mensagens de Slack/Telegram. Uma vez exposto = comprometido.

---

## 1. Inventario atual

13 variaveis declaradas em `backend/app/core/config.py` (Pydantic Settings).
Apenas 2 sao **secrets reais** (SecretStr). As demais sao configs operacionais
nao-sensiveis.

| Nome | Tipo | Sensivel? | Proposito | Rotacao recomendada |
|---|---|---|---|---|
| `APP_ENV` | `Literal["local","staging","production"]` | nao | Indica ambiente corrente | nunca |
| `APP_URL` | `str` | nao | URL externa da API | quando dominio mudar |
| `SECRET_KEY` | `SecretStr` (REQUIRED) | **SIM** | Chave reservada pra sessions/cookies futuros (sem callsite hoje, ver P1 abaixo) | quando ativar uso + a cada 12 meses |
| `DATABASE_URL` | `str` (REQUIRED) | **SIM** (contem credencial) | Conexao Postgres | apos rotacao de senha do DB |
| `REDIS_URL` | `str` (REQUIRED) | parcial (contem credencial em prod) | Conexao Redis | apos rotacao de senha do Redis |
| `SMS_PROVIDER` | `str` | nao | Seletor de provider (mock/zenvia) | quando trocar provider |
| `JWT_SECRET_KEY` | `SecretStr` (REQUIRED) | **SIM** | Assina JWT access tokens HS256 | apos incidente OU a cada 6-12 meses |
| `JWT_EXPIRATION_MINUTES` | `int` | nao | TTL do access token (padrao 60) | quando politica mudar |
| `RATE_LIMIT_ENABLED` | `bool` | nao | Liga/desliga rate limit globalmente | nunca em prod |
| `RATE_LIMIT_REQUEST_OTP_PHONE` | `str` | nao | Limite por phone em /auth/request-otp | conforme demanda |
| `RATE_LIMIT_REQUEST_OTP_IP` | `str` | nao | Limite por IP em /auth/request-otp | conforme demanda |
| `RATE_LIMIT_VERIFY_OTP_PHONE` | `str` | nao | Limite por phone em /auth/verify-otp | conforme demanda |
| `RATE_LIMIT_VERIFY_OTP_IP` | `str` | nao | Limite por IP em /auth/verify-otp | conforme demanda |

**Pattern de declaracao:** todos via `pydantic-settings` `BaseSettings` em
`config.py`. SecretStr aplicado nos 2 campos sensiveis primarios — mascara
em `repr()`, exige `.get_secret_value()` explicito pra ler.

**P1 — `SECRET_KEY` esta declarada mas SEM callsite atual.** Reserva pra
futuras sessions/cookies. Quando for ativada, aplicar mesmo procedimento
de rotacao.

---

## 2. Tooling

### Pre-piloto (atual): Railway Secrets

**Razoes da escolha:**
- Zero ferramenta extra (Railway ja eh decisao tomada como plataforma de deploy)
- Built-in da plataforma — variaveis injetadas como env padrao
- Free tier OK pra dev solo
- Lock-in moderado (env vars padrao = migracao trivial pra qualquer cofre futuro)

**Pattern operacional:**
- UI Railway: `Project > Settings > Variables`
- Variaveis injetadas em runtime no container do app
- App consome via Pydantic Settings (sem mudanca de codigo)

**Limitacoes aceitas pre-piloto:**
- Sem rotacao automatica agendada (manual via UI)
- Audit trail basico (log do Railway)
- Lock-in moderado (mitigado pelo plano de migracao)

### Triggers de migracao para Doppler

Avaliar troca quando QUALQUER um dos 3 ativar:

1. **Primeiro contratado** — multi-dev requer cofre compartilhado com
   roles. Doppler tem UI clara pra isso, Railway tem so toggle binario.
2. **Necessidade de rotacao automatica agendada** — Doppler suporta
   triggers, Railway nao.
3. **Staging + producao separados com fluxo dev->staging->prod** — Doppler
   tem `environments` nativo pra promocao, Railway exige projetos separados.

Quando trigger ativar: ADR novo dedicado, plano de migracao registrado.

---

## 3. Procedimento de rotacao — `JWT_SECRET_KEY`

### Quando rotacionar

- **Apos incidente de exposicao** (vazamento confirmado — qualquer ambiente)
- **Periodicamente em producao** (sugerido: a cada 6-12 meses)
- **Antes do piloto Tarumirim entrar em producao** (limpeza pre-launch)

### Como rotacionar

1. **Gerar novo valor:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
   (NUNCA paste o output em chat, log, screenshot.)

2. **Atualizar variavel no Railway:** UI > Settings > Variables > edit
   `JWT_SECRET_KEY` > paste novo valor > Save.

3. **Trigger redeploy** (Railway auto-deploy ou manual via UI).

4. **Mass logout esperado** — todos os JWTs ativos sao invalidados.
   Usuarios precisam fazer login novamente.

5. **Comunicar clientes** (se piloto ativo):
   > "Atualizacao de seguranca do app. Por favor faca login novamente."

6. **Janela aceitavel:** off-peak horario brasileiro (~04:00 BRT — minimo
   trafego ativo).

### Mitigacao do mass logout

Aceito como trade-off pre-piloto (volume baixo, custo operacional zero).

Em producao com volume real, considerar **rotacao com graceful fallback**
(2 chaves validas em paralelo durante janela de transicao). Implementacao:
fora de escopo MVP — registrar como debito quando volume justificar.

---

## 4. Procedimento de rotacao — `SECRET_KEY`

Reservada pra sessions/cookies futuros — **sem callsite hoje** (P1 acima).
Quando ativar:

1. Mesmo comando de geracao: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. Mesmo procedimento de rotacao via Railway
3. Mass logout aplicavel se sessions baseadas em essa chave

---

## 5. Procedimento de rotacao — `DATABASE_URL` / `REDIS_URL`

Sao secrets parciais (contem credencial inline na URI).

### Quando rotacionar

- Apos rotacao de senha do servico (Postgres/Redis)
- Apos suspeita de exposicao
- Periodicamente em prod (a cada 12 meses)

### Como rotacionar

1. Trocar senha no Postgres/Redis (Railway plugin UI)
2. Railway atualiza `DATABASE_URL`/`REDIS_URL` automaticamente quando
   plugin gerencia o servico
3. Se servico externo: atualizar manualmente no Railway Variables
4. Redeploy

---

## 6. Acesso ao cofre

### Atual (pre-piloto)

**Apenas Henrique** — sole developer, sole operator.

### Onboarding novo contratado (futuro)

1. Convite ao Railway team (`View` role minimo necessario)
2. **Lista explicita de secrets que NAO precisa ver** — separar via:
   - Projetos Railway separados (admin secrets em projeto isolado)
   - OU migracao pra Doppler com role-based access (trigger 1)
3. **Audit trail:** registrar acesso em changelog interno (commit em
   `docs/ACCESS-LOG.md` quando arquivo for criado)

### Offboarding

1. **Revogar acesso Railway imediatamente** (no minuto da decisao,
   nao no fim do dia)
2. **Rotacionar todas as secrets que o contratado teve acesso** —
   conservador, mesmo se relacionamento amistoso
3. **Verificar logs de acesso pos-revogacao** — Railway audit log se
   disponivel

---

## 7. Future secrets previsiveis

Nao declarados ainda, mas previstos no roadmap.

| Secret | Quando entrara | Sensivel | Notas |
|---|---|---|---|
| `ZENVIA_API_TOKEN` | CP3c Auth — quando provider real ativar | **SIM** | Pendente CNPJ. Substitui MockSMSProvider. |
| `PAGARME_API_KEY` | Order cycle — payment integration | **SIM** | Chave de API pro gateway. |
| `PAGARME_WEBHOOK_SECRET` | Order cycle — payment integration | **SIM** | Valida assinatura HMAC dos webhooks. |
| `GOOGLE_MAPS_API_KEY` | Order cycle — delivery routing | **SIM** | Restringir por dominio + IP em produc. |
| `FIREBASE_SERVER_KEY` | Notifications — push | **SIM** | Service account JSON, ver procedimento secao 8. |
| Service Account Google Play | Mobile — publishing | **SIM** | JSON file fora do repo, ver procedimento secao 8. |
| `EXPO_PUBLIC_*` | Mobile — quando React Native entrar | **NAO** (publicas) | Bundled no app, visiveis ao usuario final. **Nao tratar como secret** — sao chaves anon. |

Quando cada um entrar, atualizar inventario na secao 1 + ADR dedicado se
mudar pattern de gestao.

---

## 8. Service Account Google Play — procedimento pos-incidente outubro 2025

### Lesson learned

Em outubro 2025, Service Account JSON do Google Play Console foi commitada
acidentalmente. Conta foi desabilitada apos descoberta. Lesson: **uma vez
exposto, considere comprometido**. Mesmo principio aplicado a chat com IA.

### Procedimento preventivo permanente

1. **NUNCA commitar arquivo JSON de Service Account.** `.gitignore`
   linhas 72,74 cobrem (`google-services.json`, `service-account*.json`).
   Defensivo mesmo sem uso atual.

2. **Service Account fica em `$HOME` ou cofre fora do repo.** Path
   referenciado via env var (`GOOGLE_APPLICATION_CREDENTIALS`).

3. **CI consome via secret variable**. GitHub Actions:
   ```yaml
   - name: Setup GCP credentials
     run: echo "${{ secrets.GOOGLE_APPLICATION_CREDENTIALS_JSON }}" > /tmp/sa.json
     env:
       GOOGLE_APPLICATION_CREDENTIALS: /tmp/sa.json
   ```
   Arquivo gerado em runtime, deletado no final do job.

4. **Auditoria trimestral:** rodar regex check em git log (sem `-p` pra
   nao expor diffs):
   ```bash
   git log --all --name-only --pretty=format: | grep -E "service-account.*\.json|google-services\.json"
   ```
   Esperado: zero matches (alem do `.gitignore` em si).

---

## 9. Pattern de sincronia `.env` vs `.env.example`

### Problema observado

Drift entre `.env` (local) e `.env.example` (template) pode confundir devs
futuros e gerar bugs sutis (variavel declarada via default sem aparecer no
`.env`).

Caso real: pre mini-CP MEDIUM #1, 5 vars `RATE_LIMIT_*` estavam em
`.env.example` mas ausentes em `.env` local. Funcionou via defaults do
Settings, mas inconsistencia gerava risco.

### Procedimento ao adicionar secret novo

1. Adicionar em `backend/.env.example` (com placeholder ou default explicito)
2. Adicionar em `backend/app/core/config.py` (Settings)
3. Adicionar em `backend/.env` LOCAL com valor real
4. **Documentar neste arquivo** se eh secret operacional (atualizar
   tabela secao 1)

### Auditoria periodica (sugerido a cada feature commit que toque secrets)

Comparar nomes de variaveis (sem expor valores):

```bash
# Nomes em .env
grep -E "^[A-Z_]+=" backend/.env | cut -d= -f1 | sort > /tmp/env_names.txt

# Nomes em .env.example
grep -E "^[A-Z_]+=" backend/.env.example | cut -d= -f1 | sort > /tmp/example_names.txt

# Diff
diff /tmp/env_names.txt /tmp/example_names.txt
```

**Esperado:** sem drift (excecao: secrets que cada dev precisa setar
individualmente — nao deve haver hoje).

---

## 10. CI requirements (futuro, quando GitHub Actions entrar)

Tests dependem de `JWT_SECRET_KEY` presente (3 callsites em `tests/`
chamam `settings.JWT_SECRET_KEY.get_secret_value()`).

Em CI:

| Variavel | Origem | Notas |
|---|---|---|
| `JWT_SECRET_KEY` | GitHub repo secret (valor de teste fixo) | **NUNCA** o valor de producao |
| `SECRET_KEY` | GitHub repo secret (valor de teste fixo) | Idem |
| `DATABASE_URL` | Postgres service do GH Actions (`services:`) | Ephemeral, regenerada cada job |
| `REDIS_URL` | Redis service do GH Actions | Ephemeral |
| `APP_ENV` | Hardcoded no workflow (`local`) | — |
| Demais | Defaults dos Settings cobrem | — |

**Mascaramento automatico:** GitHub Actions mascara `secrets.*` em logs
por default. Auditar 1ª execucao pra confirmar.

**Sync entre cofres:** valores de teste em CI sao **independentes** dos
de Railway (prod). Zero acoplamento.

---

## 11. Detecao de leak — `gitleaks` pre-commit hook

### Status

Instalado no mini-CP MEDIUM #1 (este). Catch-all preventivo apos lesson
learned do incidente outubro 2025.

### Funcionamento

- Hook em `.git/hooks/pre-commit` roda `gitleaks protect --staged` antes
  de cada commit
- Bloqueia se detectar pattern de secret conhecido (JWT_SECRET, AWS keys,
  GitHub tokens, API keys com pattern reconhecivel, etc.)
- Configuracao em `.gitleaks.toml` na raiz do repo
- Allowlist mantida minima (`.env.example`, `docs/SECRETS.md`,
  `.gitleaks.toml` proprio)

### Instalacao do binario gitleaks

Necessario uma vez por maquina dev. Hook tem fallback gracioso (avisa e
passa) se gitleaks nao estiver no PATH.

| OS | Comando |
|---|---|
| Windows | `scoop install gitleaks` OU `winget install gitleaks` |
| Mac | `brew install gitleaks` |
| Linux | `apt install gitleaks` (se distro recente) OU binario direto: https://github.com/gitleaks/gitleaks/releases |

Verificar: `gitleaks version`

### Bypass excepcional

Se gerar falso-positivo legitimo:

1. **Primeira opcao:** ajustar regra em `.gitleaks.toml` em commit
   dedicado (descreve por que falso-positivo eh aceitavel)
2. **Ultimo recurso:** `git commit --no-verify` — APENAS se urgencia
   justificar e fix da config vir em commit subsequente. Nunca como
   pratica recorrente.

---

## 12. Lessons learned

### Outubro 2025 — Service Account Google Play exposta

Service Account JSON commitada acidentalmente em commit publico. Conta
desabilitada apos descoberta. Sem dano operacional confirmado mas chave
considerada comprometida.

**Lessons aplicadas neste documento:**

1. **"Uma vez exposto, considere comprometido"** — base do principio
   "rotacionar pos-incidente"
2. **"Valor de secret so vive em 3 lugares"** — regra de ouro do topo
   deste doc
3. **`.gitignore` defensivo pre-uso** — entries pra Service Account
   adicionadas mesmo antes de uso real
4. **Chat com IA conta como exposicao** — politica formal de NUNCA
   trazer valores reais pra conversa, mesmo se solicitado explicitamente

### Abril 2026 — drift `.env` vs `.env.example`

Mini-CP MEDIUM #1 detectou 5 vars em `.env.example` ausentes em `.env`.
Funcionou via defaults mas confunde devs futuros. **Lesson:** processo
explicito de sincronia documentado (secao 9).

---

**Ultima revisao:** 2026-04-27 (mini-CP MEDIUM #1, ADR-028).

**Quando atualizar:**
- Cada secret novo declarado (atualizar tabela secao 1)
- Cada incidente de exposicao (lessons learned secao 12)
- Cada mudanca de tooling ou trigger de migracao (atualizar secao 2)
- Cada onboarding/offboarding registrado (atualizar secao 6 se padrao
  mudar)
