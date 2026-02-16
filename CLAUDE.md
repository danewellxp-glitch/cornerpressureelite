# CLAUDE.md — Instrucoes do Projeto para AI

## Projeto

Corner Pressure Elite System (CPES) — motor automatizado de analise de escanteios ao vivo para sinais de apostas esportivas.

- **Backend:** Python (FastAPI) em `corner-pressure-elite/`
- **Frontend:** Next.js + TypeScript em `dashboard/`
- **Infra:** Docker Compose, Cloudflare Workers/Tunnel
- **Notificacoes:** WAHA (WhatsApp HTTP API)

---

## Regras de Documentacao

Toda documentacao vive em `docs/`. **Nunca crie arquivos .md na raiz do projeto** (exceto este CLAUDE.md).

### Onde colocar novos documentos

| Categoria | Pasta | O que vai aqui |
|-----------|-------|----------------|
| Architecture | `docs/architecture/` | Specs tecnicas completas, codigo-fonte documentado |
| Analises | `docs/analises/` | Analises de componentes, modelos de decisao, estudos, avaliacoes |
| Resumo | `docs/resumo/` | Resumos executivos, relatorios de performance, snapshots |
| Sprints | `docs/sprints/` | Planejamento, roadmap, tarefas futuras, evolucao do sistema |
| Setup | `docs/setup/` | Guias de deploy, configuracao de ambiente, infra, como rodar |
| Changelog | `docs/changelog/` | Registros de mudancas. Nomear como `YYYY-MM-DD-slug.md` |

### Convencao de nomes

- Usar kebab-case em minusculo: `decision-model.md`, nao `DecisionModel.md`
- Changelogs sempre com data: `2026-02-15-strategy-tuning.md`
- Nomes descritivos: `cloudflare-workers-deploy.md`, nao `setup.md`

### Apos criar um documento

Atualizar `docs/README.md` para incluir o novo documento na tabela da categoria correspondente.

### O que NAO fazer

- Nao criar `.md` na raiz do projeto (exceto este arquivo)
- Nao misturar docs de setup/deploy com docs de architecture
- Nao misturar docs de design/analise com docs de setup

---

## Estrutura do Codigo

```
corner-pressure-elite/          # Backend Python
  api_server.py                 # API FastAPI (porta 8000)
  config.py                     # Todos os parametros tuneaveis
  main.py                       # Robo principal (loop de monitoramento)
  monitor.py                    # Monitor de status
  engine/                       # Logica de analise
    score_engine.py             # Calculo do Pressure Score
    projection_engine.py        # Projecao hibrida de escanteios
    decision_engine.py          # Motor de decisao (filtros + sinais)
    state_manager.py            # Gerenciamento de estado/re-avaliacao
  notifier/                     # Notificacoes WhatsApp
  storage/                      # Persistencia (SQLite)
  data/                         # Modelos de dados
  utils/                        # Utilitarios (polling adaptativo, etc)
  tests/                        # Testes

dashboard/                      # Frontend Next.js
  src/                          # Codigo fonte React/TypeScript
  public/                       # Assets estaticos

docs/                           # Documentacao (ver regras acima)
  architecture/                 # Specs tecnicas completas
  analises/                     # Analises, modelos de decisao, estudos
  resumo/                       # Resumos executivos, relatorios
  sprints/                      # Planejamento, roadmap, tarefas
  setup/                        # Deploy e config
  changelog/                    # Registros de mudancas
```

## Portas

| Servico | Porta |
|---------|-------|
| WAHA (WhatsApp) | 3000 |
| API (FastAPI) | 8000 |
| Dashboard (Next.js) | 3001 |

## Rodando o Sistema

```bash
# Docker (todos os servicos)
docker compose up -d

# Nativo
./start_all.sh

# Parar
./kill_all.sh
```

## Dominio

- **https://odontoschultz.online** — Dashboard (via Cloudflare Tunnel)
- **https://api.odontoschultz.online** — API
- **ssh.odontoschultz.online** — Acesso SSH via Cloudflare Tunnel
