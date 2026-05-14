"""Worker que persiste `incidents_history` (eventos Opta do WS matchhub)."""
from __future__ import annotations

import logging
from typing import Optional

from data.repositories.incidents_history import (
    IncidentHistoryEntry,
    IncidentsHistoryRepo,
    event_uid,
)

from ._base import _BaseBatchWorker

log = logging.getLogger("cpes.persistence.incidents")


class IncidentsPersistenceWorker(_BaseBatchWorker[IncidentHistoryEntry]):
    def __init__(
        self,
        repo: IncidentsHistoryRepo,
        *,
        queue_size: int = 20000,
        batch_size: int = 25,
        batch_timeout_s: float = 3.0,
    ):
        super().__init__(
            name="incidents_worker",
            queue_size=queue_size,
            batch_size=batch_size,
            batch_timeout_s=batch_timeout_s,
        )
        self._repo = repo

    async def flush(self, batch: list[IncidentHistoryEntry]) -> None:
        await self._repo.bulk_insert(batch)

    # ---- callback para `BetanoWSClient.subscribe_match(... , on_event)` ----

    def make_ws_callback(self, *, fixture_id_for: Optional[callable] = None):
        """Retorna um callback async pronto para o WS.

        `fixture_id_for(opta_match_id)` permite ao caller injetar um lookup
        custom (ex. usar um mapa Opta→fixture). Default: None.
        """
        async def _on_event(match_event) -> None:
            opta = match_event.opta_match_id
            fixture_id = None
            if fixture_id_for is not None:
                try:
                    fixture_id = fixture_id_for(opta)
                except Exception:
                    fixture_id = None
            entry = IncidentHistoryEntry(
                fixture_id=fixture_id,
                opta_match_id=opta,
                event_uid=event_uid(
                    opta_match_id=opta,
                    team_id=match_event.team_id,
                    player_id=match_event.player_id,
                    minute=int(match_event.minute or 0),
                    seconds=int(match_event.seconds or 0),
                    event_type=int(match_event.event_type or 0),
                    x=match_event.x,
                    y=match_event.y,
                ),
                event_type=int(match_event.event_type or 0),
                period_id=int(match_event.period_id or 0),
                minute=int(match_event.minute or 0),
                seconds=int(match_event.seconds or 0),
                team_id=match_event.team_id,
                player_id=match_event.player_id,
                x=match_event.x, y=match_event.y,
                x_end=match_event.x_end, y_end=match_event.y_end,
                is_attack=match_event.is_attack,
                is_dangerous_attack=match_event.is_dangerous_attack,
                is_possession=match_event.is_possession,
                is_dangerous=match_event.is_dangerous,
                raw=match_event.raw,
            )
            self.enqueue(entry)
        return _on_event
