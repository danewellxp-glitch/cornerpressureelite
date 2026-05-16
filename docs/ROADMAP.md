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
- **Proxy residencial** — Brave do pool sai por IP RJ (ML Telecom) pra diversificar fingerprint
- **Systemd units** — Bridge resilient a crash + reboot

## Em progresso

- **PARTE A do D.2** — bridge `/teams` endpoint (depende de `/danae/teams` no renewer danewell)
- **Smoke real D.0 + D.2** — Validar telemetria + matches em jogo de liga monitorada ao vivo (pendente overlap real)

## Próximas fases (Caminho A — eliminar API-Football)

### D.2 PARTE A (pendente, ~1h) — bridge `/teams` + worker refresh catálogo 1×/dia

### Fase E — Adapter Stats (~10-14h)
- /api/statsstream/<id>/stats/detailed
- StatsProvider no Composite

### Fase F — Adapter Eventos (~8-12h)
### Fase G — Adapter Lineups (~6-10h)
### Fase H — Remover api_client de main.py (~6-10h)
### Fase I — Testes + rate limit + RAM management (~10-20h)
### Fase J — Descontinuar API-Football (~2h)

**Total Caminho A restante:** ~55-95h em 6-10 semanas.

## Fases Quant (longo prazo)

### Fase H1 — Telemetria refinada (4-6 semanas após Fase D.0 ligada)
Dataset acumulado, schema enriquecido se faltar.

### Fase H2 — Modelo de pricing
Treinar com dataset. LightGBM/XGBoost. Prevê odd futura baseado em stats.

### Fase H3 — Modelo de projeção
Projeta evento futuro (escanteios/cartões/gols) com intervalos de confiança.

### Fase H4 — Backtest engine
Roda estratégia hipotética sobre dataset histórico. Calibra parâmetros.
