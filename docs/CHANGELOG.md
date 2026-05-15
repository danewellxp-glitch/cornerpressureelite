# CHANGELOG

Resumo narrativo do que mudou por sessão. Não substitui git log — contextualiza decisões e dores. Última coisa que sessão escreve antes de fechar.

> **Escopo:** sessões inteiras (1 entrada por sessão). Changelogs de entregas individuais antigas estão em `docs/changelog/YYYY-MM-DD-*.md` (leitura histórica — convenção descontinuada após 2026-05-15).

**Formato:**
```
YYYY-MM-DD — Título curto da sessão
Contexto: o que motivou a sessão
O que foi feito: lista alto nível
Bugs encontrados: (se houver, linkar BUGS.md)
Decisões: (se houver, linkar DECISIONS.md)
Estado final: o que ficou rodando, o que ficou pendente
Próximos passos: (opcional)
```

---

## 2026-05-15 — Fase D.0 + Bridge Pool + PC danewell

**Contexto:** Pós-Fase 2bc fechada. Telemetria de odds implementada mas desligada. Necessidade de captura full coverage pra modelagem quant. Necessidade de redundância no bridge.

**O que foi feito:**
- Fase D.0 implementada e commitada (6 commits): worker telemetria ligado, catálogo completo persistido, contexto rico (minute + scores), gate desacoplado de pre_avaliar
- PC danewell (Pop!_OS) configurado com Chrome :9223 acessível na LAN
- Bridge refatorado pra pool distribuído (pool.py novo, server.py modificado, health check + failover)
- Bridge commitado e pushed pro GitHub (github.com/danewellxp-glitch/bridgecpe)
- Smoke E2E mockado validou Fase D.0 (25 linhas persistidas)
- Sistema de documentação ativa criado (`docs/DECISIONS.md`, `docs/BUGS.md`, `docs/CHANGELOG.md`, `docs/OPERATIONS.md`, `docs/ROADMAP.md` + regras no CLAUDE.md)

**Bugs encontrados:** [odds_persistence_worker=None silencioso](BUGS.md#2026-05-15--odds_persistence_workernone-silencioso)

**Decisões:** [Telemetria full coverage desacoplada](DECISIONS.md#2026-05-15--telemetria-full-coverage-desacoplada-fase-d0), [Pool distribuído de Chromes](DECISIONS.md#2026-05-15--pool-distribuído-de-chromes-fase-bridge-pool)

**Estado final:**
- ✅ Bridge rodando com pool 2/2 healthy (odin localhost + danewell LAN)
- ✅ Container cpes-main rodando código Fase D.0
- ✅ Repos protegidos no GitHub (cpes-main + cpes-bridge)
- ⏳ Smoke real Fase D.0 pendente (aguardando jogo de liga monitorada)
- ⏳ Systemd units pendentes (bridge ainda nohup)

**Próximos passos:**
- Systemd units pro bridge + Xvfb + Chrome local
- Smoke real Fase D.0 quando jogo monitorado aparecer
- Fase D principal (descoberta automática /events/today + /events/live)
