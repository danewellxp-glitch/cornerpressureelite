# ROADMAP

Fases planejadas + estado atual. Atualizado quando fase fecha ou nova é planejada.

> **Escopo:** visão geral (1 linha por fase). Detalhes operacionais por sprint vão em `docs/sprints/`.

## Concluído

- **Fase 1** — Bridge inicial (HTTP /quote, /health)
- **Fase 2a** — Catálogo completo /markets, política central 1.50-1.70
- **Fase 2a.1** — Otimização latência (24s → 8.5s)
- **Fase 3** — Refactor Protocol OddsProvider
- **Fase 2bc** — Composite wired no pipeline real
- **Fase D.0** — Telemetria full coverage com catálogo + contexto rico
- **Bridge Pool** — Pool distribuído (odin local + danewell LAN)
- **Fase D.1** — Bridge `/events/live` via Brave do pool danewell (renewer + danae API)
- **Fase D.2** — Worker `BetanoFixtureDiscovery` no cpes-main (matcher fuzzy + UPSERT auto). BETANO_EVENT_MAP virou override opcional.
- **Fase D.2 PARTE A** — Catálogo de teams 1×/dia: danewell `/danae/teams` (agrega live + upcoming) → bridge `/teams` (cache 24h) → worker refresh popula `betano_team_map` proativamente
- **Proxy residencial** — Brave do pool sai por IP RJ (ML Telecom) pra diversificar fingerprint
- **Systemd units** — Bridge resilient a crash + reboot
- **Fase E.0** — Investigação técnica stats Betano (mapeamento `/danae-webapi/api/live/events/<id>/latest`, gotchas `X-Operator/X-Language`) — commit `5553934` 2026-05-16
- **Fase E.1** — Stats Betano via bridge + Composite cascade Betano→AF. `USE_BETANO_STATS=true` em produção, smoke real validado (6 capturas bridge_betano + 12 AF fallback, version polling 4133→4222, latência 7-7.5s, decision_engine consumindo Score=7) — commit `1e3efca` 2026-05-17

## Em progresso

- **Smoke real D.0 + D.2** — Validar telemetria + matches em jogo de liga monitorada ao vivo (pendente overlap real)

## Próximas fases (Caminho A soft restante)

### Fase E.2 — WebSocket push stats (opcional, ~6-10h)
- `wss://www.betano.bet.br/sbpitches/statsstream/matchhub` (SignalR)
- Substitui polling 15s por push real-time
- **Não bloqueia caminho A** — só se polling ficar lento pra decisões críticas

### Fase F — Eventos Betano (~8-12h)
- `event.incidents[]` da Betano (GOAL/YELL/CRNR/RCRD/OFFS/SUBS/PENL/StoppageTime)
- Substituir `api_client.get_events()`
- Persistir `events_history` (timing exato de gols/cartões)
- Habilita análise pós-jogo + reconstrução de janelas via timeline (vs estimativa atual via rate)

### Fase G — Lineups Betano (~6-10h)
- Investigar endpoint (provável: `/api/statsstream/<id>/info/aggregated/`)
- Substituir `api_client.get_lineups()`
- Persistir `lineups_history`

### Fase H — Refactor remover `api_client.*` de runtime (~4-6h)
- Quando E.1 + F + G prontos, AF vira só residual (discovery + resultado FT)

### Fase I — Otimização + cache + testes integração (~8-15h)

TODOs registrados durante fases anteriores (consolidar em sprint dedicado):

- **Cache compartilhado `/event/<id>/state`** entre `BetanoStatsWorker`
  (Fase E.1) e `BetanoEventsWorker` (Fase F) via store in-memory
  (TTL ≈ 10s, key=event_id). Reduz ~50% chamadas ao renewer. Volume
  atual sustentável (~5.4 MB/min ao danewell, infra local). Implementar
  quando volume escalar (> 15 jogos simultâneos).
- **Cache 304 do bridge dead-code em produção** — bridge TTL=3s <<
  worker poll=15s. Reavaliar TTL ou frequência de poll.
- **AF unmapped types**: review semanal dos logs `events_adapter.af.unmapped_type`
  + `unmapped_var` pra detectar tipos novos AF não cobertos (`_AF_TYPE_MAP`
  em `data/providers/apifootball/events_adapter.py`).

**Total Caminho A soft restante:** ~30-50h em 5-8 sessões.

## Fases Caminho A hard (eliminar AF completamente)

### Fase J — Descontinuar API-Football (~2h)
Quando F+G+H entregues e estáveis, remove `APIFootballClient` do orquestrador.

## Fases Quant (longo prazo)

### Fase H1 — Telemetria refinada (4-6 semanas após Fase D.0 ligada)
Dataset acumulado, schema enriquecido se faltar.

### Fase H2 — Modelo de pricing
Treinar com dataset. LightGBM/XGBoost. Prevê odd futura baseado em stats.

### Fase H3 — Modelo de projeção
Projeta evento futuro (escanteios/cartões/gols) com intervalos de confiança.

### Fase H4 — Backtest engine
Roda estratégia hipotética sobre dataset histórico. Calibra parâmetros.
