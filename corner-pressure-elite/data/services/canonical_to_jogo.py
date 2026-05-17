"""Mapper CanonicalStats → JogoAoVivo (Fase E.1 PARTE F').

Enriquece um `JogoAoVivo` já criado (metadata + media_historica vindos de
`parse_fixture_to_jogo` + odds de `enrich_jogo_with_*`) com snapshot live
vindo do `StatsProvider` (composite com BridgeStatsAdapter primário).

# Política de mesclagem — EXPLÍCITA (refactor pós-review Daniel)

A versão anterior usava heurística "se canonical > 0 sobrescreve, senão
preserva". Armadilha: AF sem créditos OU jogo legitimamente zerado vira
indistinguível de "Betano não cobre" — preserva valor errado.

Versão atual: **lista de gaps Betano explícita** (`BETANO_GAPS`). Esses
campos **NUNCA são sobrescritos**, ponto. Os demais (cobertos
deterministicamente pelo `event.liveData.results`) sobrescrevem **sempre**,
mesmo se canonical=0 (zero significa "Betano cobre e valor é zero", não
"missing").

`BETANO_GAPS` mantida em sintonia com `docs/architecture/betano-stats-api.md
§3` (tabela "Cobertura comparativa vs API-Football Opta") + ADR
`docs/DECISIONS.md` §"CASO α" (2026-05-16). Teste de regressão
`test_mapper_documents_betano_gaps_explicitly` garante coerência.

# Campos cobertos por Betano /latest (livedata.results)
  - score.home/away                → placar_casa/fora
  - clock.secondsSinceStart        → minute (via // 60)
  - results.corners.home/away      → escanteios_total/casa/fora
  - results.yellow.home/away       → cartoes_amarelos_total/casa/fora
  - results.xGoals.home/away       → x_goals_* (não mapeado pra jogo_base)
  - **shots NÃO mapeado pra finalizacoes_recentes** (semântica difere —
    Betano `shots` é all-shots, finalizacoes_recentes do AF é
    `Shots on Goal`. Daniel sinalizou semantic gap → tratado como GAP).
  - Janelas (`*_last_5/10min`)     → calculadas pelo StatsWindowCalculator
                                      (PARTE E' — None=preserva jogo_base)

# Campos da BETANO_GAPS (Betano não cobre confiavelmente)
  - cartoes_vermelhos_*  (Betano traz só em event.incidents — futuro RCRD parser)
  - posse_ultimos_10min  (não está em liveData.results)
  - faltas_*             (não está em liveData.results)
  - ataques_perigosos_ultimos_10min  (não está)
  - finalizacoes_recentes  (semantic mismatch Betano shots vs AF Shots on Goal)

# Sempre preservados do jogo_base
  - id, liga_id, liga_nome, time_casa, time_fora, kickoff_at (metadata)
  - media_historica_combinada, media_historica_cartoes (pre-game)
  - linha_*, odd_*, odds_source*, bookmaker_usado (OddsProvider injects)
"""
from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

from data.models import JogoAoVivo
from data.stats_provider import CanonicalStats


# Campos JogoAoVivo onde o BridgeStatsAdapter (Betano /latest) NÃO traz
# informação confiável. Mapper NUNCA sobrescreve esses — preserva valor
# do jogo_base (que veio do enrich_jogo_with_* via AF, ou ficou zero/None).
#
# IMPORTANTE: manter em sintonia com docs/architecture/betano-stats-api.md §3
# "Cobertura comparativa vs API-Football Opta". Teste de regressão
# `test_mapper_documents_betano_gaps_explicitly` ancora essa relação.
BETANO_GAPS: frozenset[str] = frozenset({
    "cartoes_vermelhos_total",
    "cartoes_vermelhos_casa",
    "cartoes_vermelhos_fora",
    "posse_ultimos_10min",
    "faltas_total",
    "faltas_casa",
    "faltas_fora",
    "ataques_perigosos_ultimos_10min",
    "finalizacoes_recentes",
})


def canonical_to_jogo(jogo_base: JogoAoVivo, stats: CanonicalStats) -> JogoAoVivo:
    """Retorna JogoAoVivo enriquecido com `stats` live. Não muta `jogo_base`.

    Política:
    - **Campos cobertos**: sobrescreve com canonical (até zero — zero é dado
      válido, não missing).
    - **Campos em `BETANO_GAPS`**: NUNCA sobrescreve — preserva jogo_base.
    - **Janelas (corners_last_5/10min, yellow_last_5/10min)**: sobrescreve só
      se canonical tem valor (None preserva — calculator pode não ter dado
      ainda no 1º poll).

    `is_cached` no canonical NÃO afeta o mapper — caller deve ter chamado
    `recalc_minute_if_cached` antes pra projetar minute via captured_at_ts.
    """
    updates: dict[str, Any] = {
        # ----- Campos cobertos por Betano /latest (sempre sobrescreve) -----
        "minuto": stats.minute or jogo_base.minuto,
        "placar_casa": stats.score_home,
        "placar_fora": stats.score_away,
        "escanteios_total": stats.corners_home + stats.corners_away,
        "escanteios_casa": stats.corners_home,
        "escanteios_fora": stats.corners_away,
        "cartoes_amarelos_total": stats.yellow_cards_home + stats.yellow_cards_away,
        "cartoes_amarelos_casa": stats.yellow_cards_home,
        "cartoes_amarelos_fora": stats.yellow_cards_away,
    }

    # Janelas — None = calculator ainda não calculou; preserva jogo_base.
    if stats.corners_last_5min is not None:
        updates["escanteios_ultimos_5min"] = stats.corners_last_5min
    if stats.corners_last_10min is not None:
        updates["escanteios_ultimos_10min"] = stats.corners_last_10min
    if stats.yellow_last_5min is not None:
        updates["cartoes_ultimos_5min"] = stats.yellow_last_5min
    if stats.yellow_last_10min is not None:
        updates["cartoes_ultimos_10min"] = stats.yellow_last_10min

    # Defesa em runtime: nenhum campo de BETANO_GAPS pode ter sido incluído
    # acima. Asserção barata, falha rápido em refactor errado.
    assert BETANO_GAPS.isdisjoint(updates.keys()), (
        f"canonical_to_jogo tentou sobrescrever campo de BETANO_GAPS: "
        f"{BETANO_GAPS & updates.keys()}"
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


def _validate_betano_gaps_against_jogo_schema() -> None:
    """Sanity: todo nome em BETANO_GAPS é campo existente em JogoAoVivo.

    Chamado em test_mapper_documents_betano_gaps_explicitly.
    """
    valid = {f.name for f in fields(JogoAoVivo)}
    invalid = BETANO_GAPS - valid
    if invalid:
        raise AssertionError(
            f"BETANO_GAPS contém campos que não existem em JogoAoVivo: {invalid}"
        )
