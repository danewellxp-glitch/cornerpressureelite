# QUANT_VISION.md — Caminho A soft (eliminar dependência API-Football no runtime)

Visão técnica/quant complementar ao [`CLIENT_VISION.md`](CLIENT_VISION.md).
Foco: independência operacional + dataset auditável proprietário.

**Última atualização:** 2026-05-17 (pós Fase G.1 entregue)
**Owner:** Daniel

---

## Visão

Reduzir e eventualmente eliminar dependência da API-Football no caminho
quente de decisão (live stats + odds + events + lineups). API-Football
fica residual pra discovery agenda + cross-check resultado FT.

Justificativa:
1. **Custo recorrente** — plano Pro AF $50/mês.
2. **Risco operacional** — chave vencida = pipeline cego (já aconteceu).
3. **Latência** — AF response varia 2-8s; Betano via bridge é 5-10s mas
   payload é >10× mais rico (xG, version, incidents timeline).
4. **Dataset proprietário** — capturas Betano em `odds_history` +
   `stats_history` viram dataset diferenciado vs concorrência.

## Caminhos

### Caminho A soft (em andamento)

Substitui runtime stats/events/lineups por Betano via bridge.
**Mantém** AF pra:
- Discovery agenda (`get_today_schedule` — fixture_id canônico).
- Resultado FT (cross-check com Betano + persistir GREEN/RED).

Eliminação parcial — AF vira ~5-10% das requests (vs 100% hoje).

### Caminho A hard (futuro)

Remove AF completamente. Discovery e resultado vêm do Betano também.
Requer:
- `event.startTime` da Betano coerente com fixture_id próprio.
- Resultado FT confiável via `event.liveData.score` pós-`isFinished`.

Não-objetivo agora — Caminho A soft é prioridade.

## Já entregue (atualizado 2026-05-17)

| Fase | Entrega | Commit |
|---|---|---|
| 1-3, 2bc | Bridge + Composite + Betano primary (odds) | múltiplos |
| D.0 | Telemetria full coverage (`odds_history`) | `417c367` |
| D.1 | `/events/live` via Brave + Danae | `f0abc0c` |
| D.2 | Worker discovery + fuzzy match + `betano_team_map` | `90d7675` |
| D.2 PARTE A | Bridge `/teams` + cache 24h | `89b7ca4` |
| **E.0** | **Investigação técnica stats Betano** | **`5553934`** |
| **E.1** | **Stats Betano via bridge + Composite cascade Betano→AF** | **`1e3efca`** |
| **F** | **Events Betano via `event.incidents[]` (dataset puro)** | **`a65bfe6`** |
| **G.0** | **Investigação técnica lineups Betano + saúde renewer** | **`508147b`** |
| **G.1** | **Lineups Betano via `event.roster` (CASO α puro)** | **`63cfd3a`** |

**Caminho A soft: ~75% completo** (de ~40-65h roadmap, ~37-43h entregue).

## Pendente (Caminho A soft)

| Fase | Escopo | Esforço |
|---|---|---|
| E.2 | WebSocket push stats (`statsstream/matchhub`) — opcional | ~6-10h |
| F.2 | Substituir `api_client.get_events` interno (post-FT) | ~1-2h |
| H | Remover `api_client.*` de runtime quente | ~4-6h |
| I | Otimização + cache compartilhado + testes integração | ~8-15h |

**Total restante:** ~13-25h em 3-5 sessões.

## Fases Quant (longo prazo)

Pós Caminho A soft completo + dataset Betano acumulado 4-6 semanas:

- **H1** — Telemetria refinada (schema enriquecido se faltar)
- **H2** — Modelo de pricing (LightGBM/XGBoost prevê odd futura)
- **H3** — Modelo de projeção (escanteios/cartões/gols + intervalos confiança)
- **H4** — Backtest engine (calibra estratégia sobre dataset histórico)

Caminho independente do Caminho A — só requer dataset acumulado.

## Princípios

1. **Cascata defensiva** — toda fonte primária Betano tem fallback AF via
   Composite. Falha temporária do bridge não para pipeline.
2. **Persistência granular** — toda captura vira linha em `*_history` com
   contexto temporal (minute, version, freshness). Auditável + alimenta H1-H4.
3. **Gaps explícitos** — campos não cobertos por Betano (`BETANO_GAPS`
   no `canonical_to_jogo`) preservados do AF/zero. Política frozenset
   evita inferência heurística.
4. **Foot-gun warnings** — combinações de flags inseguras (ex.
   `USE_NEW_PROVIDERS=true` sem stats) emitem WARNING explícito.
5. **Smoke real obrigatório** — toda fase fecha com captura ao vivo
   validada (não só testes unit).
