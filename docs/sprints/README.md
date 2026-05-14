# Pivot Betano — pacote de documentação

> **Versão pós-spike (2026-05-13)** — reflete a realidade descoberta na
> captura `.mitm` de 2026-05-12. Substitui versão anterior baseada em
> hipóteses.

---

## Ordem de leitura recomendada

| # | Documento | Quando ler |
|---|---|---|
| 1 | `2026-05-12-betano-discovery-master.md` | **Comece aqui.** Visão consolidada da realidade descoberta e da arquitetura final. |
| 2 | `2026-05-12-betano-spike-mitmproxy.md` | (Opcional) Como a captura foi feita e seção 16 com achados detalhados. |
| 3 | `2026-05-12-betano-fase-A-statsstream-provider.md` | Quando for implementar a Fase A. |
| 4 | `2026-05-12-betano-fase-B-markets-ws-provider.md` | Quando for implementar a Fase B. |
| 5 | `2026-05-12-betano-fase-C-pipeline-refactor.md` | Quando for implementar a Fase C. |
| 6 | `2026-05-12-betano-fase-D-persistencia-historica.md` | Quando for implementar a Fase D. |

---

## TL;DR do pivot

**Antes (premissa):** Sportradar gismo é a fonte de stats; tinha que capturar
token assinado e implementar provider Sportradar separado.

**Depois (realidade descoberta no .mitm):** A Betano BR usa **Opta**, não
Sportradar. Tudo é REST + WebSocket SignalR Core próprios. Provider único
Betano resolve o caso.

### Endpoints Betano descobertos

- **Stats:** `/api/statsstream/{eventId}/...` (info, config, stats/detailed,
  stats/players, momentum, lineups, h2h) — Opta-backed
- **Mercados:** `/danae-webapi/api/live/events/{eventId}/latest` — 281KB com
  279 mercados + 1153 selections
- **Catálogo:** `/danae-webapi/api/live/overview/latest` — 96 eventos do dia
- **WebSockets:** `/contenthub` (push de odds), `/sbpitches/statsstream/matchhub`
  (push de eventos Opta)

### Implicações

- ✅ Não precisamos do token Sportradar
- ✅ Tudo cookies-authenticated (sem JA3 fingerprint complexo)
- ✅ `betradarMatchId` vem inline no payload (mapping grátis)
- ✅ Pressure score da Opta vem pronto via `/momentum/`
- ✅ Operação 100% anônima funcional (sem login)

---

## Como rodar cada fase com Claude Code

Para cada fase, prompt-base:

```
Trabalhe na Fase X do pivot Betano.

Documento harness: docs/sprints/2026-05-12-betano-fase-X-*.md

Antes de começar, leia também:
- docs/sprints/2026-05-12-betano-discovery-master.md (contexto geral)
- CLAUDE.md (princípios de coding: PT-BR, citação arquivo:linha,
  try/except só em fronteiras)

Complete TODOS os itens da seção "Acceptance" do harness, na ordem da
seção "Componentes novos". Não improvise fora do harness sem pedir
confirmação antes.

Ao finalizar, rode os smoke scripts da seção de testes e reporte status.
```

Cada doc é **auto-suficiente** — Claude CLI consegue implementar sem precisar
de contexto adicional além do harness + master + CLAUDE.md.

### Cronologia de execução sugerida

1. **Aplicar migrations da Fase D primeiro** (independente, e o cache do
   fixture_map ajuda na Fase B)
2. **Fase A** (Betano StatsStream — 10h)
3. **Fase B** (Markets + WS + warmup — 16h)
4. **Fase C** (Pipeline refactor — 10h) com flag OFF
5. **Plugar workers de persistência** (parte da Fase D restante)
6. Em staging: `USE_NEW_PROVIDERS=true` + `DRIFT_CHECK_PROVIDERS=true` por 24h
7. Análise dos drift logs em `logs/provider_drift.jsonl`
8. Rollout gradual em produção (whitelist de leagues primeiro)

**Total estimado:** ~46h (vs ~52h da estimativa original do plano antigo).

---

## Decisões pendentes do Daniel

Estão listadas na §13 do master, mas resumindo:

1. **Playwright só pra refresh (1x a cada 12h)** — recomendado, e implementado
   na Fase B
2. **WS: 1 contenthub global + 1 matchhub por evento monitorado (até 20)** —
   recomendado, implementado na Fase B
3. **NewLiveOverviewDiffs: não parsear, usar como gatilho** — recomendado, ver
   §4.7 da Fase B
4. **Sem login em produção** — recomendado, ver §4.9 da Fase B
5. **Sportradar gismo no futuro?** — opcional, não bloqueia nada; pode entrar
   como "Fase E" se quisermos enrichment cruzado

---

## Mudanças desta versão vs a anterior

- ❌ Removida fase "Sportradar Provider" (capturar token + curl_cffi JA3)
- ✅ Nova Fase A focada em Betano StatsStream REST (provider Opta)
- ✅ Fase B expandida com warmup Playwright + WebSocket SignalR Core
- ✅ Fase C simplificada (Composite com provider único Betano + AF fallback)
- ✅ Fase D inclui `incidents_history` granular (eventos Opta com X/Y)
- ✅ Spike marcado como concluído + seção 16 com achados detalhados

---

## Arquivos neste diretório

```
.
├── README.md                                                   ← você está aqui
├── 2026-05-12-betano-discovery-master.md                        ← começar por aqui
├── 2026-05-12-betano-spike-mitmproxy.md                         ← concluído; seção 16 = achados
├── 2026-05-12-betano-fase-A-statsstream-provider.md
├── 2026-05-12-betano-fase-B-markets-ws-provider.md
├── 2026-05-12-betano-fase-C-pipeline-refactor.md
└── 2026-05-12-betano-fase-D-persistencia-historica.md
```

---

## Onde colocar no projeto

```
~/cornerpressureelite/
└── docs/
    └── sprints/
        ├── 2026-05-12-betano-discovery-master.md
        ├── 2026-05-12-betano-spike-mitmproxy.md
        ├── 2026-05-12-betano-fase-A-statsstream-provider.md
        ├── 2026-05-12-betano-fase-B-markets-ws-provider.md
        ├── 2026-05-12-betano-fase-C-pipeline-refactor.md
        ├── 2026-05-12-betano-fase-D-persistencia-historica.md
        └── captures/
            └── 2026-05-12-betano-flow.mitm    ← guardar para regression test
```
