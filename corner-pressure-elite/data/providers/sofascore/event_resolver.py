"""SofaScoreEventResolver — resolve fixture_id (AF) → sofa_event_id (B.5).

Estratégia híbrida:

1. **Cache in-memory** com TTL por outcome:
   - Hit positivo (sofa_event_id resolvido): 5 min.
   - Hit negativo (não encontrado): 60s (não martela em retry imediato).

2. **`betano_fixture_map` (D.2) como hint primeiro**:
   - Se fixture_id já mapeado pra Betano, usa `home_team`/`away_team` do
     map (confidence 1.00 em produção D.2) — names canônicos pra fuzzy.
   - Se não, usa `fixture.home_team`/`away_team` direto.

3. **Fuzzy match em `/sport/football/events/live`**:
   - rapidfuzz.fuzz.ratio em ambos `home_name` + `away_name`.
   - Tie-breaker temporal ±30min (compara `startTimestamp` SofaScore com
     `fixture.starts_at_utc`).
   - Threshold combined score ≥ 85 (mesmo da D.2).
   - WARNING quando top-2 candidates < 5 pontos de diferença.

4. **TODO PARTE C futura**: tabela `sofascore_event_map` persistente +
   worker discovery dedicado, igual D.2 PARTE A.

Design notes:
- Resolver é stateless por construção — fixture_repo/betano_team_map_repo
  são opcionais; default funciona só com `/events/live`.
- Live API tem latência ~30ms cached, ~300ms fresh — cache evita repetir.
- Cache negative TTL 60s evita retry burst quando jogo não está em /live
  (pré-jogo / pós-jogo).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from rapidfuzz import fuzz

from data.odds_provider import CanonicalFixture

from .client import SofaScoreClient

log = logging.getLogger("cpes.providers.sofascore.event_resolver")


_FUZZ_THRESHOLD = 85
_KICKOFF_WINDOW_MIN = 30
_AMBIGUITY_DELTA = 5
_TTL_POS_SEC = 300
_TTL_NEG_SEC = 60


class SofaScoreEventResolver:
    """Resolve `CanonicalFixture` → `sofa_event_id` via cache + live search.

    Pra resolver:
        resolver = SofaScoreEventResolver(client, fixture_map_repo=...)
        sofa_id = await resolver.resolve(canonical_fixture)
        if sofa_id is None:
            ...  # composite cai pro próximo provider
    """

    def __init__(
        self,
        client: SofaScoreClient,
        fixture_map_repo: Any = None,
    ):
        self._client = client
        self._fixture_map_repo = fixture_map_repo
        # cache: {fixture_id: (sofa_event_id_or_None, expiry_ts)}
        self._cache: dict[int, tuple[Optional[int], float]] = {}

    async def resolve(
        self, fixture: CanonicalFixture
    ) -> Optional[int]:
        # 1. Cache.
        now = time.monotonic()
        cached = self._cache.get(fixture.fixture_id)
        if cached is not None:
            sofa_id, expiry = cached
            if now < expiry:
                return sofa_id

        # 2. Names canônicos via betano_fixture_map (se disponível).
        home_name, away_name = await self._resolve_names(fixture)

        # 3. Fuzzy match em /events/live.
        sofa_id = await self._search_live(
            home_name, away_name, fixture.starts_at_utc,
        )

        # 4. Cacheia outcome.
        ttl = _TTL_POS_SEC if sofa_id is not None else _TTL_NEG_SEC
        self._cache[fixture.fixture_id] = (sofa_id, now + ttl)
        return sofa_id

    async def _resolve_names(
        self, fixture: CanonicalFixture
    ) -> tuple[str, str]:
        """Preferir names canônicos do betano_fixture_map (D.2 confidence 1.00)."""
        home = fixture.home_team
        away = fixture.away_team
        if self._fixture_map_repo is None:
            return (home, away)
        try:
            row = await self._fixture_map_repo.get_by_fixture_id(fixture.fixture_id)
        except Exception as e:
            log.debug(
                "event_resolver.fixture_map.lookup_error fixture=%d err=%s",
                fixture.fixture_id, e,
            )
            return (home, away)
        if row is None:
            return (home, away)
        # row deve ter home_team/away_team (schema D.2).
        h = row.get("home_team") if isinstance(row, dict) else getattr(row, "home_team", None)
        a = row.get("away_team") if isinstance(row, dict) else getattr(row, "away_team", None)
        return (h or home, a or away)

    async def _search_live(
        self,
        home_name: str,
        away_name: str,
        kickoff_at: Optional[datetime],
    ) -> Optional[int]:
        try:
            events = await self._client.get_live_events()
        except Exception as e:
            log.warning("event_resolver.live_events.error err=%s", e)
            return None
        if not events:
            return None
        return _fuzzy_match(events, home_name, away_name, kickoff_at)

    def invalidate(self, fixture_id: int) -> None:
        """Remove cache pra um fixture (debug / após erro persistente)."""
        self._cache.pop(fixture_id, None)


def _fuzzy_match(
    events: list[dict],
    home_name: str,
    away_name: str,
    kickoff_at: Optional[datetime],
) -> Optional[int]:
    """Fuzzy match com tie-breaker temporal. Aceita ≥85 combined score.

    Quando 2+ candidates com delta < `_AMBIGUITY_DELTA`, escolhe maior
    (provavelmente correto) mas loga WARNING pra investigação.
    """
    candidates: list[tuple[float, int]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ev_id = ev.get("id")
        if not isinstance(ev_id, int):
            continue
        ht = (ev.get("homeTeam") or {})
        at = (ev.get("awayTeam") or {})
        ev_home = ht.get("name") if isinstance(ht, dict) else None
        ev_away = at.get("name") if isinstance(at, dict) else None
        if not ev_home or not ev_away:
            continue

        score_home = fuzz.ratio(home_name, ev_home)
        score_away = fuzz.ratio(away_name, ev_away)
        combined = (score_home + score_away) / 2

        # Tie-breaker temporal: se ambos kickoff disponíveis, exigir ±30min.
        if kickoff_at is not None:
            ts = ev.get("startTimestamp")
            if isinstance(ts, int):
                sofa_kickoff = datetime.fromtimestamp(ts, tz=timezone.utc)
                # kickoff_at pode estar naive — assumir UTC nesse caso.
                if kickoff_at.tzinfo is None:
                    kickoff_at_aware = kickoff_at.replace(tzinfo=timezone.utc)
                else:
                    kickoff_at_aware = kickoff_at
                delta_min = abs(
                    (sofa_kickoff - kickoff_at_aware).total_seconds() / 60
                )
                if delta_min > _KICKOFF_WINDOW_MIN:
                    log.debug(
                        "event_resolver.skipped_by_kickoff "
                        "sofa_event=%s home=%r away=%r delta_min=%.1f",
                        ev_id, ev_home, ev_away, delta_min,
                    )
                    continue

        if combined >= _FUZZ_THRESHOLD:
            candidates.append((combined, ev_id))

    if not candidates:
        return None

    candidates.sort(key=lambda x: -x[0])
    top_score, top_id = candidates[0]
    if len(candidates) >= 2:
        delta = top_score - candidates[1][0]
        if delta < _AMBIGUITY_DELTA:
            log.warning(
                "event_resolver.ambiguous home=%r away=%r top_score=%.1f "
                "second=%.1f delta=%.1f — accepting top (sofa_id=%d)",
                home_name, away_name, top_score, candidates[1][0],
                delta, top_id,
            )
    return top_id
