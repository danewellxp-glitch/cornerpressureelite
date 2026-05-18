"""Refetch just-before-send pra validar fidelidade de odds (Fase K, 2026-05-17).

Antes do `notifier.send_signal`, refazemos a chamada `composite_odds.get_<market>()`
pra capturar odds mais recentes. Bridge tem cache TTL 3s — se a captura
original ainda está fresh, refetch é instantâneo (cache hit).

Validações que ABORTAM emit:
1. Refetch retornou None (bridge falhou + cache vazio — P4-B silêncio)
2. Refetch retornou `is_stale=True` (cache entre TTL e 2×TTL)
3. Linha mudou (`fresh.linha != orig.linha`) — mercado fechou aquela linha
4. Odd drift > `max_drift_pct` (default 15%) — odd movimentou demais

Se passar, atualiza `jogo.odd_atual`/`jogo.odd_cartoes` com odd fresh
(captura mais nova). Decision_engine não recalcula edge/projeção — assume
que dentro de 15% drift, o sinal continua válido.

Pode ser desabilitado via `ODDS_REFETCH_BEFORE_EMIT=false`.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("cpes.refetch")


async def refetch_validate_corners(
    composite_odds,
    canonical_fixture,
    current_score: int,
    jogo,
    max_drift_pct: float = 0.15,
    *,
    blocked_repo=None,
    af_sofa_map=None,
) -> bool:
    """Retorna True se ok pra emitir, False se abort.

    Quando abort + `blocked_repo` informado, persiste em blocked_signals
    pra análise de qualidade do filtro.
    """
    return await _refetch_validate(
        composite_odds,
        method="get_corners",
        canonical_fixture=canonical_fixture,
        current_score=current_score,
        jogo=jogo,
        orig_linha=jogo.linha_atual,
        orig_odd=jogo.odd_atual,
        update_jogo_field="odd_atual",
        market_kind="corners",
        max_drift_pct=max_drift_pct,
        blocked_repo=blocked_repo,
        af_sofa_map=af_sofa_map,
    )


async def refetch_validate_cards(
    composite_odds,
    canonical_fixture,
    current_score: int,
    jogo,
    max_drift_pct: float = 0.15,
    *,
    blocked_repo=None,
    af_sofa_map=None,
) -> bool:
    return await _refetch_validate(
        composite_odds,
        method="get_cards",
        canonical_fixture=canonical_fixture,
        current_score=current_score,
        jogo=jogo,
        orig_linha=jogo.linha_cartoes,
        orig_odd=jogo.odd_cartoes,
        update_jogo_field="odd_cartoes",
        market_kind="cards",
        max_drift_pct=max_drift_pct,
        blocked_repo=blocked_repo,
        af_sofa_map=af_sofa_map,
    )


async def _refetch_validate(
    composite_odds,
    *,
    method: str,
    canonical_fixture,
    current_score: int,
    jogo,
    orig_linha: float,
    orig_odd: float,
    update_jogo_field: str,
    market_kind: str,
    max_drift_pct: float,
    blocked_repo=None,
    af_sofa_map=None,
) -> bool:
    fid = canonical_fixture.fixture_id
    # Fase H A1.3: resolve sofa_event_id pra dual-write em blocked_signals
    _sofa_id: Optional[int] = None
    if af_sofa_map is not None:
        try:
            _sofa_id = await af_sofa_map.get_sofa_id(fid)
        except Exception:
            _sofa_id = None
    try:
        fresh = await getattr(composite_odds, method)(
            canonical_fixture, current_score=current_score, line=None,
        )
    except Exception as e:
        log.warning(
            "refetch.exception fixture=%d market=%s err=%s",
            fid, market_kind, e,
        )
        await _record_block(blocked_repo, fid, market_kind, orig_linha,
                            "refetch_exception", orig_odd, None, None,
                            metadata={"err": str(e)[:200]},
                            sofa_event_id=_sofa_id)
        return False

    if fresh is None:
        log.warning(
            "refetch.none fixture=%d market=%s — bridge falhou + cache expirado, sinal bloqueado",
            fid, market_kind,
        )
        await _record_block(blocked_repo, fid, market_kind, orig_linha,
                            "refetch_none", orig_odd, None, None,
                            sofa_event_id=_sofa_id)
        return False

    if getattr(fresh, "is_stale", False):
        log.warning(
            "refetch.stale fixture=%d market=%s age=%ds — sinal bloqueado",
            fid, market_kind, getattr(fresh, "age_seconds", 0),
        )
        await _record_block(blocked_repo, fid, market_kind, orig_linha,
                            "refetch_stale", orig_odd, fresh.odd_over, None,
                            metadata={"age_seconds": getattr(fresh, "age_seconds", 0)},
                            sofa_event_id=_sofa_id)
        return False

    if abs(fresh.linha - orig_linha) > 0.01:
        log.warning(
            "refetch.line_changed fixture=%d market=%s orig=%.1f fresh=%.1f — sinal bloqueado",
            fid, market_kind, orig_linha, fresh.linha,
        )
        await _record_block(blocked_repo, fid, market_kind, orig_linha,
                            "line_changed", orig_odd, fresh.odd_over, None,
                            metadata={"fresh_linha": fresh.linha},
                            sofa_event_id=_sofa_id)
        return False

    if orig_odd <= 0:
        # sem odd original (caso degradado) — aceita refetch como fonte
        setattr(jogo, update_jogo_field, fresh.odd_over)
        return True

    drift = abs(fresh.odd_over - orig_odd) / orig_odd
    if drift > max_drift_pct:
        log.warning(
            "refetch.odd_drift fixture=%d market=%s orig=%.2f fresh=%.2f drift=%.1f%% > %.1f%% — sinal bloqueado",
            fid, market_kind, orig_odd, fresh.odd_over, drift * 100, max_drift_pct * 100,
        )
        await _record_block(blocked_repo, fid, market_kind, orig_linha,
                            "odd_drift", orig_odd, fresh.odd_over, drift * 100,
                            sofa_event_id=_sofa_id)
        return False

    if drift > 0.0:
        # Atualiza odd com valor fresh; mantém linha (já validada acima).
        log.info(
            "refetch.ok_drift fixture=%d market=%s orig=%.2f fresh=%.2f drift=%.1f%% — emit autorizado",
            fid, market_kind, orig_odd, fresh.odd_over, drift * 100,
        )
        setattr(jogo, update_jogo_field, fresh.odd_over)
    return True


async def _record_block(
    blocked_repo,
    fixture_id: int,
    market_kind: str,
    linha: float,
    reason: str,
    orig_odd: Optional[float],
    fresh_odd: Optional[float],
    drift_pct: Optional[float],
    metadata: Optional[dict] = None,
    sofa_event_id: Optional[int] = None,
) -> None:
    if blocked_repo is None:
        return
    try:
        await blocked_repo.insert(
            fixture_id=fixture_id, market_kind=market_kind, linha=linha,
            reason=reason, orig_odd=orig_odd, fresh_odd=fresh_odd,
            drift_pct=drift_pct, metadata=metadata,
            sofa_event_id=sofa_event_id,
        )
    except Exception as e:
        log.warning("refetch.record_block_failed fixture=%d err=%s", fixture_id, e)
