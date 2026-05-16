"""Mapper CanonicalStats → JogoAoVivo (Fase E.1 PARTE F').

Enriquece um `JogoAoVivo` já criado (metadata + media_historica vindos de
`parse_fixture_to_jogo` + odds de `enrich_jogo_with_*`) com snapshot live
vindo do `StatsProvider` (composite com BridgeStatsAdapter primário).

**Política de mesclagem** (campos consumidos pelos decision/score engines —
levantamento via grep em PARTE F'.1):

| Campo JogoAoVivo                       | Origem canonical                                | Comportamento |
|---|---|---|
| `minuto`                               | `stats.minute` (fallback `jogo_base.minuto`)    | sempre sobrescreve |
| `placar_casa/fora`                     | `stats.score_home/away`                          | sempre sobrescreve |
| `escanteios_total/casa/fora`           | `stats.corners_*`                                | sempre sobrescreve |
| `escanteios_ultimos_5/10min`           | `stats.corners_last_5/10min` (None = preserva)   | só se canonical tem |
| `cartoes_amarelos_total/casa/fora`     | `stats.yellow_cards_*`                           | sempre sobrescreve |
| `cartoes_ultimos_5/10min`              | `stats.yellow_last_5/10min` (None = preserva)    | só se canonical tem |
| `finalizacoes_recentes`                | `stats.shots_on_target_home + _away`             | sempre sobrescreve |
| `cartoes_vermelhos_total/casa/fora`    | `stats.red_cards_*` (Betano /latest = 0)         | só se canonical > 0 |
| `ataques_perigosos_ultimos_10min`      | `stats.dangerous_attacks_*` (Betano = 0)         | só se canonical > 0 |
| `posse_ultimos_10min`                  | `max(stats.possession_home, possession_away)` (Betano = 0) | só se canonical > 0 |
| `faltas_total/casa/fora`               | **gap canonical** — preserva jogo_base sempre    | nunca toca |
| `id, liga_*, time_*, kickoff_at`       | preserva jogo_base (metadata fixa)               | nunca toca |
| `media_historica_combinada/cartoes`    | preserva jogo_base (pre-game data)               | nunca toca |
| `linha_*, odd_*, odds_source*`         | preserva jogo_base (vem do OddsProvider)         | nunca toca |

**Gaps Betano vs AF** (DECISIONS.md §"CASO α", 2026-05-16):
- `posse_ultimos_10min` (Betano não expõe) → score_engine perde sinal de "POSSE_DOMINANT"
- `faltas_total` (não expõe) → cards_decision_engine perde `foul_rate`
- `cartoes_vermelhos_*` (Betano `liveData.results` = 0; via `event.incidents` futuramente) → cards_score_engine perde penalidade

Quando USE_BETANO_STATS=true + AF sem cota, esses campos ficam zero. Aceitável pro MVP — score thresholds calibrados pra esse gap.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from data.models import JogoAoVivo
from data.stats_provider import CanonicalStats


def canonical_to_jogo(jogo_base: JogoAoVivo, stats: CanonicalStats) -> JogoAoVivo:
    """Retorna JogoAoVivo enriquecido com `stats` live. Não muta `jogo_base`."""
    updates: dict[str, Any] = {
        "minuto": stats.minute or jogo_base.minuto,
        "placar_casa": stats.score_home,
        "placar_fora": stats.score_away,
        "escanteios_total": stats.corners_home + stats.corners_away,
        "escanteios_casa": stats.corners_home,
        "escanteios_fora": stats.corners_away,
        "cartoes_amarelos_total": stats.yellow_cards_home + stats.yellow_cards_away,
        "cartoes_amarelos_casa": stats.yellow_cards_home,
        "cartoes_amarelos_fora": stats.yellow_cards_away,
        "finalizacoes_recentes": stats.shots_on_target_home + stats.shots_on_target_away,
    }

    if stats.corners_last_5min is not None:
        updates["escanteios_ultimos_5min"] = stats.corners_last_5min
    if stats.corners_last_10min is not None:
        updates["escanteios_ultimos_10min"] = stats.corners_last_10min
    if stats.yellow_last_5min is not None:
        updates["cartoes_ultimos_5min"] = stats.yellow_last_5min
    if stats.yellow_last_10min is not None:
        updates["cartoes_ultimos_10min"] = stats.yellow_last_10min

    if stats.red_cards_home or stats.red_cards_away:
        updates["cartoes_vermelhos_total"] = stats.red_cards_home + stats.red_cards_away
        updates["cartoes_vermelhos_casa"] = stats.red_cards_home
        updates["cartoes_vermelhos_fora"] = stats.red_cards_away
    if stats.dangerous_attacks_home or stats.dangerous_attacks_away:
        updates["ataques_perigosos_ultimos_10min"] = (
            stats.dangerous_attacks_home + stats.dangerous_attacks_away
        )
    if stats.possession_home or stats.possession_away:
        updates["posse_ultimos_10min"] = float(
            max(stats.possession_home, stats.possession_away)
        )

    return replace(jogo_base, **updates)


def recalc_minute_if_cached(stats: CanonicalStats, now_ts: float) -> CanonicalStats:
    """Se snapshot é cached, projeta `minute` adicionando `(now - captured_at_ts) / 60`.

    Snapshot cached tem `minute` "congelado" no momento do último 200 do
    bridge. Sem essa correção, decision engines decidiriam baseados em
    minuto desatualizado (até ~30s defasado dada a TTL do bridge cache).

    Retorna novo `CanonicalStats` (frozen). Se não cached OU sem
    `captured_at_ts`, retorna inalterado.
    """
    if not stats.is_cached or stats.captured_at_ts is None:
        return stats
    age_sec = max(0, int(now_ts - stats.captured_at_ts))
    new_minute = (stats.minute or 0) + (age_sec // 60)
    return replace(stats, minute=new_minute)
