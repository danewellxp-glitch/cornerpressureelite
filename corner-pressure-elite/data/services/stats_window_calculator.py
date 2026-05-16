"""StatsWindowCalculator — janelas temporais de corners/yellow por fixture.

Mantém um deque por fixture com tuplas (`captured_at`, `corners_total`,
`yellow_total`). API estilo "stateless por chamada": cada `add_snapshot` é
push idempotente; `compute_windows` deriva os 4 deltas (corners_last_5/10min,
yellow_last_5/10min) inspecionando o deque atual.

**Por que deque + cache interno** (Daniel disse "stateless" no spec mas
também "deque por fixture"):
- *Stateless API* = não depende de DB call a cada `compute_windows`. Tudo
  in-memory, custo O(N) onde N <= history_size por fixture.
- *Deque por fixture* = isolamento entre fixtures (race condition free no
  asyncio single-thread; cada fixture toca a sua deque).
- *Bootstrap explícito* = quando worker reinicia, chama `bootstrap_from_history`
  pra hidratar deques a partir do `stats_history` repo. Sem isso, janelas
  ficam None até acumular ~5min de polls.

Semântica de borda (cobertura completa em tests/services/test_stats_window_calculator.py):

| Cenário | Janela retornada |
|---|---|
| Sem snapshots no deque (`empty_history`) | `None` em todas as 4 |
| Só 1 snapshot (o atual) (`only_one_snapshot`) | `None` (sem base de comparação) |
| Snapshot anterior dentro da janela mas valor decresce (`corners_decreased`) | `0` (defesa contra reset/bug — janela nunca negativa) |
| Snapshot anterior fora da janela (≥ window+threshold) | janela calculada vs snapshot mais antigo *dentro* da janela; se nenhum, fallback `0` |
| Fixture visto pela 1ª vez já com valor alto (`first_seen_mid_match`) | `None` (não há base "antes do jogo começar") |
| Maior que `history_size` snapshots (`maxlen_eviction`) | janela usa o que sobrou; corners_last_10min pode ficar None se evicção comeu o snapshot referência |
| `reset_fixture` chamado | deque zera; próximas janelas voltam a `None` até acumular 2 snapshots |
| Múltiplos fixtures (`concurrent_fixtures_isolated`) | cada fixture tem sua deque, sem cross-contamination |
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("cpes.services.stats_window")


@dataclass(frozen=True)
class _Snapshot:
    captured_at: datetime
    corners_total: int
    yellow_total: int


class StatsWindowCalculator:
    """Calculadora de janelas 5/10min de corners e yellow cards."""

    def __init__(self, history_size: int = 120):
        if history_size < 2:
            raise ValueError("history_size deve ser >= 2 (precisa de base + atual)")
        self._history_size = history_size
        self._windows: dict[int, deque[_Snapshot]] = {}

    def add_snapshot(
        self,
        fixture_id: int,
        captured_at: datetime,
        corners_total: int,
        yellow_total: int,
    ) -> None:
        """Push snapshot no deque do fixture (maxlen=history_size).

        Idempotência: se o último snapshot tem o mesmo `captured_at`, vira no-op
        (defesa contra dupla chamada da mesma versão).
        """
        captured_at = _ensure_aware(captured_at)
        dq = self._windows.get(fixture_id)
        if dq is None:
            dq = deque(maxlen=self._history_size)
            self._windows[fixture_id] = dq
        if dq and dq[-1].captured_at == captured_at:
            return
        dq.append(
            _Snapshot(
                captured_at=captured_at,
                corners_total=int(corners_total),
                yellow_total=int(yellow_total),
            )
        )

    def bootstrap_from_history(self, fixture_id: int, rows: list[dict]) -> None:
        """Hidrata deque a partir de query ao stats_history (mais recente DESC).

        `rows` espera-se vir de `StatsHistoryRepo.list_recent_for_fixture` que
        retorna DESC; aqui inverte pra ordem cronológica e popula.
        """
        # Reset + repopulate na ordem cronológica (mais antigo primeiro).
        dq: deque[_Snapshot] = deque(maxlen=self._history_size)
        for r in reversed(rows):
            ts = r.get("captured_at")
            if ts is None:
                continue
            corners = (r.get("corners_home") or 0) + (r.get("corners_away") or 0)
            yellows = (r.get("yellow_cards_home") or 0) + (r.get("yellow_cards_away") or 0)
            dq.append(
                _Snapshot(
                    captured_at=_ensure_aware(ts),
                    corners_total=int(corners),
                    yellow_total=int(yellows),
                )
            )
        self._windows[fixture_id] = dq

    def reset_fixture(self, fixture_id: int) -> None:
        """Limpa o deque de 1 fixture (jogo terminou, bug, etc)."""
        self._windows.pop(fixture_id, None)

    def compute_windows(
        self, fixture_id: int, now: Optional[datetime] = None
    ) -> dict[str, Optional[int]]:
        """Calcula as 4 janelas a partir do estado atual do deque.

        Retorna dict com keys `corners_last_5min`, `corners_last_10min`,
        `yellow_last_5min`, `yellow_last_10min`. Valores `None` quando não
        é possível calcular (sem snapshots, só 1 snapshot, snapshot
        referência fora do deque por evicção, etc).
        """
        dq = self._windows.get(fixture_id)
        empty = {
            "corners_last_5min": None,
            "corners_last_10min": None,
            "yellow_last_5min": None,
            "yellow_last_10min": None,
        }
        if not dq or len(dq) < 2:
            return empty

        now = _ensure_aware(now) if now is not None else dq[-1].captured_at
        latest = dq[-1]

        return {
            "corners_last_5min": _delta_or_none(dq, latest, now, 5, "corners_total"),
            "corners_last_10min": _delta_or_none(dq, latest, now, 10, "corners_total"),
            "yellow_last_5min": _delta_or_none(dq, latest, now, 5, "yellow_total"),
            "yellow_last_10min": _delta_or_none(dq, latest, now, 10, "yellow_total"),
        }


def _delta_or_none(
    dq: deque[_Snapshot],
    latest: _Snapshot,
    now: datetime,
    minutes: int,
    attr: str,
) -> Optional[int]:
    """Delta da métrica `attr` entre o snapshot mais antigo dentro da janela
    `[now - Nmin, now]` e o `latest`.

    Política: SEMPRE prefere o snapshot mais antigo **dentro** da janela como
    base. Snapshots ANTES do cutoff são ignorados (eles representam um período
    fora da janela e contariam mudanças que não pertencem aos "últimos N min").

    Retorna `None` quando não há base de comparação dentro da janela (só o
    `latest` está dentro, ou o snapshot referência foi evictado por maxlen).
    Retorna `0` quando delta seria negativo (defesa contra reset/bug — janela
    nunca é negativa).

    Aceito-trade-off: se a cobertura temporal do deque é menor que `minutes`,
    a janela retorna o delta do intervalo que realmente cobrimos (subestima
    em vez de superestimar). Documentado em `betano-stats-api.md §5.2`.
    """
    cutoff = now - timedelta(minutes=minutes)
    base: Optional[_Snapshot] = None
    for snap in dq:
        if snap.captured_at >= cutoff:
            base = snap
            break

    if base is None or base is latest:
        # Só `latest` dentro da janela (ou nenhum) → sem base.
        return None

    delta = getattr(latest, attr) - getattr(base, attr)
    if delta < 0:
        # Defesa contra reset/bug — janela nunca é negativa.
        return 0
    return int(delta)


def _ensure_aware(dt: datetime) -> datetime:
    """Garante datetime tz-aware (UTC se naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
