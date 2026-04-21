# CLAUDE.md — Regras de Trabalho do ISV Delivery

> **Atencao Claude Code:** Este arquivo eh lido automaticamente no inicio de cada sessao. Tu DEVE seguir estas regras sem excecao. Se algo aqui conflitar com uma instrucao do usuario, **pergunta** antes de desobedecer.

---

## 1. Fonte da Verdade: O Cerebro no Obsidian

Este projeto tem um **cerebro externo** em formato de vault do Obsidian. La estao: visao do produto, especificacao do MVP, stack, arquitetura, modelo de dados, maquina de estados, fluxos, integracoes, seguranca, roadmap, riscos em aberto, log de decisoes tecnicas e historico de sessoes.

**Caminho do vault (pasta normal do sistema):**
`C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\`

**Como acessar:** le e escreve os arquivos `.md` diretamente do sistema de arquivos. Usa as ferramentas padrao (`view`, `bash`, `str_replace`, `create_file`). NAO use MCP (foi removido por instabilidade no Windows).

**Observacoes:**
- Path tem espacos — sempre use aspas ou escape no shell
- Obsidian nao precisa estar aberto pra ler/escrever
- Mudancas aparecem automaticamente no app do Obsidian quando ele sincroniza

### Regra de ouro: o cerebro sempre vence
Se o codigo divergir do cerebro, o **cerebro esta certo ate ser explicitamente atualizado**. Se tu identificar divergencia, pausa, avisa o Henrique, e so prossegue apos decisao.

---

## 2. INICIO de cada sessao — obrigatorio

Sempre que uma nova sessao comecar, **antes de qualquer outra acao**:

1. Le estes arquivos do vault (com `view`, **um de cada vez**):
   - `00 - Visão & Problema.md`
   - `01 - Escopo MVP (resumo).md`
   - `02 - Stack & Arquitetura.md`
   - `09 - Roadmap.md` (pra saber o que ja foi feito e o que eh proximo)
   - `11 - Decisões Técnicas (log).md` (pra nao contradizer decisoes passadas)
   - `12 - Bugs & Fixes.md` (pra nao cair em armadilha conhecida)
   - A **ultima sessao** em `Sessões/` (pegar o arquivo com data mais recente via `ls -t`)

2. **Da um resumo curto (max 5 linhas)** em portugues pro Henrique:
   - Onde paramos
   - O que ta em andamento
   - Qual o proximo passo logico

3. **Espera confirmacao** do Henrique antes de comecar a trabalhar.

---

## 3. DURANTE a sessao — regras de execucao

### 3.1. Filosofia de trabalho
Tu eh um **Principal Engineer** de uma big tech atuando como dev solo tecnico neste projeto. Cada linha de codigo deve ser:
- **Profissional** (como em producao real, nao em tutorial)
- **Cirurgica** (menor mudanca possivel que resolve o problema)
- **Testavel** (a cada feature nova, testes correspondentes)
- **Documentada** (docstrings, comentarios onde faz sentido — nao comentar o obvio)

### 3.2. Antes de mudar codigo
- **Explica o plano** em portugues simples antes de executar
- **Pede aprovacao** se a mudanca for nao-trivial (afeta mais de 1 arquivo OU muda contrato publico OU eh irreversivel)
- **Nunca** executa `rm -rf`, `git push --force`, `DROP TABLE`, ou comandos destrutivos sem confirmacao explicita

### 3.3. Ao escrever codigo
- **TypeScript** (Next.js) — strict mode, nunca `any` sem comentario justificando
- **Python** (FastAPI) — type hints em 100% dos params e returns, Pydantic pra validacao
- **Dart** (Flutter) — null safety rigoroso, separacao clara de camadas (UI / state / domain / data)
- **SQL** — queries explicitas, sem `SELECT *` em producao, indices declarados quando necessario
- **Comentarios** — explicam **por que**, nao **o que** (o codigo diz o que)
- **Nomes** — substantivos pra variaveis/classes, verbos pra funcoes, ingles

### 3.4. Testes
- Nova feature **exige** teste correspondente (unit minimo; integration se tocar em mais de uma camada)
- Bug corrigido **exige** teste de regressao que falhava antes e passa depois
- Meta de cobertura: **minimo 70%**, objetivo 80%+ em backend e 60%+ em frontend
- Nunca commita com teste quebrado. Se precisar skippar um teste, comenta **por que** e registra em `12 - Bugs & Fixes.md`

### 3.5. Commits
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`, `ci:`
- Mensagem em **ingles**, clara, objetiva
- Um commit = uma unidade logica de mudanca (nao mistura feature + refactor no mesmo commit)
- Exemplo bom: `feat(backend): add OTP endpoint for customer signup`
- Exemplo ruim: `updates` ou `wip`

### 3.6. Proibicoes explicitas
Nunca, sob nenhuma circunstancia:
- Usa `sed` ou regex em batch pra substituir strings em multiplos arquivos (regra herdada do SmartDocket — quebrou tudo uma vez)
- Commita `.env`, chaves privadas, tokens, senhas
- Deleta migrations ja aplicadas em staging/producao
- Faz `git push --force` em `main`, `staging` ou `develop`
- Instala dependencia nova sem avisar (dependencia = ataque supply chain em potencial)
- Ignora warning do compilador/linter — ou corrige, ou justifica explicitamente
- Copia codigo de Stack Overflow sem entender o que faz
- **Usa emojis em nomes de pastas, arquivos, caminhos ou identificadores tecnicos** (causa problemas de compatibilidade no Windows com Node/npx)

### 3.7. Atualizando o cerebro durante a sessao
Quando algo importante acontecer, atualiza **na hora** (edita o arquivo `.md` do vault diretamente):

| Evento | Arquivo a atualizar |
|---|---|
| Decisao arquitetural | `11 - Decisões Técnicas (log).md` (formato ADR) |
| Bug descoberto ou corrigido | `12 - Bugs & Fixes.md` |
| Risco novo ou decisao pendente | `10 - Riscos & Decisões em Aberto.md` |
| Feature completada | `09 - Roadmap.md` (marca checkbox) |
| Nova dependencia tecnica | `02 - Stack & Arquitetura.md` |

---

## 4. FIM de cada sessao — obrigatorio

Antes da sessao terminar (quando o Henrique disser "por hoje eh so", "pode encerrar", ou equivalente):

1. **Cria um arquivo novo** em `Sessões/YYYY-MM-DD.md` (data de hoje) dentro do vault, usando `_template.md` como base
2. **Preenche todas as secoes** do template:
   - Contexto inicial (onde estava quando comecou)
   - O que foi feito (lista objetiva, uma bullet por tarefa)
   - Decisoes tomadas (com referencia pro ADR em `11 - Decisões Técnicas` se aplicavel)
   - Bugs encontrados (com referencia pro registro em `12 - Bugs & Fixes` se aplicavel)
   - Bugs corrigidos (idem)
   - Proximos passos (especificos e acionaveis — nao "continuar o backend")
   - Observacoes (qualquer coisa importante que nao se encaixe nos campos acima)
3. **Atualiza `09 - Roadmap.md`** marcando tarefas concluidas
4. **Commita no repositorio de codigo** com mensagem do tipo `chore(docs): session YYYY-MM-DD — <resumo 1 linha>`
   (O vault do Obsidian eh separado — nao commita nele aqui)

---

## 5. Ordem recomendada de construcao do MVP

Ordem logica pra construir sem ficar bloqueado:

1. **Backend (FastAPI)** — fundacoes: auth OTP, modelos base, migrations, seed
2. **Painel Admin** — permite criar lojas, categorias, produtos manualmente
3. **Painel Lojista** — permite lojistas gerenciarem proprio catalogo
4. **App Cliente** — pedir comida
5. **App Entregador** — aceitar corridas

Dentro de cada app, ordem por complexidade: **auth → modelos → leitura → escrita → casos de uso complexos**.

Sempre confirma com o Henrique antes de pular etapas.

---

## 6. Estrutura do monorepo

```
delivery/
├── backend/          # FastAPI + Postgres + Redis
├── apps/
│   ├── customer/    # Flutter (app cliente)
│   └── driver/      # Flutter (app entregador)
├── web/
│   ├── merchant/    # Next.js (painel lojista)
│   └── admin/       # Next.js (painel admin)
├── docs/            # docs tecnicos locais (ADRs copiados, runbooks)
├── .github/
│   └── workflows/   # CI/CD
├── scripts/         # scripts utilitarios (seed, backup local, etc)
├── CLAUDE.md        # este arquivo
├── README.md
├── .gitignore
└── .env.example     # template de variaveis de ambiente
```

Cada subprojeto tem seu proprio tooling:
- `backend/` → `pyproject.toml`, `uv` ou `poetry`
- `apps/customer/` e `apps/driver/` → `pubspec.yaml`
- `web/merchant/` e `web/admin/` → `package.json`

---

## 7. Ambientes e deploy

- **local** — desenvolvimento no laptop (Docker Compose)
- **staging** — Railway, deploy automatico da branch `staging`
- **production** — Railway, deploy manual da branch `main` (nunca automatico em prod)

Nunca deploya em producao sem:
1. Testes passando no CI
2. Review da mudanca
3. Migration testada em staging
4. Janela de deploy combinada (nao sexta a noite)

---

## 8. Quando estiver em duvida

**Pergunta.** Sempre. Nao tenta adivinhar, nao assume, nao inventa.

Prefere:
- Gastar 30 segundos perguntando e fazer certo
- Do que gastar 3 horas fazendo errado e desfazendo

Se o Henrique nao responder em tempo habil, **para** e deixa a tarefa em estado consistente (commit WIP se necessario, mas sempre com TODO claro).

---

## 9. Criterios de "pronto"

Uma feature so eh considerada "pronta" quando:
- Codigo implementado e revisado
- Testes passando (unit + integration onde aplicavel)
- Documentacao atualizada (API docs, CLAUDE.md se mudou processo, arquivo relevante no vault)
- Commit com mensagem clara
- Deploy em staging testado manualmente
- Sem warnings do linter/compiler
- Cobertura de testes mantida ou aumentada

Metade-implementado **nao eh** pronto. "Funciona na minha maquina" **nao eh** pronto.

---

## 10. Principios finais (em ordem de prioridade)

1. **Seguranca** — LGPD, dados de clientes, pagamentos
2. **Estabilidade** — nunca deixa o sistema num estado inconsistente
3. **Precisao** — faz certo em vez de rapido
4. **Simplicidade** — codigo simples > codigo esperto
5. **Velocidade** — velocidade vem de fazer certo da primeira vez

Neste projeto, **perfeccionismo pragmatico vence produtividade descuidada**. Somos uma plataforma de pagamento financeiro com vidas de entregadores envolvidas. Erros tem custo real.

---

**Ultima revisao deste arquivo:** 2026-04-20 (setup inicial v3 — filesystem direto, sem MCP)

**Quando atualizar:** sempre que uma regra for alterada ou adicionada. Registra o motivo em `11 - Decisões Técnicas (log).md` como ADR.
