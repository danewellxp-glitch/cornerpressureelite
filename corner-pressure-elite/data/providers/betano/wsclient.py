"""WebSocket client (SignalR Core JSON) para Betano.

Mantém:
- 1 conexão persistente em `/contenthub` (push de diffs — gatilho para REST).
- 1 conexão por evento monitorado em `/sbpitches/statsstream/matchhub` (push
  de eventos Opta com X/Y).

Reconexão com backoff exponencial 1→2→5→10→30→60s. Re-subscribe automático.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import random
import re
from typing import Awaitable, Callable, Optional

import websockets

from . import parsers
from .schemas import MatchEvent
from .session import BetanoSession

log = logging.getLogger("cpes.betano.ws")

SEP = "\x1e"
INIT_MSG = '{"protocol":"json","version":1}' + SEP

# Tipos SignalR Core JSON
TYPE_INVOCATION = 1
TYPE_STREAM_ITEM = 2
TYPE_COMPLETION = 3
TYPE_PING = 6
TYPE_CLOSE = 7

_EVENT_ID_RE = re.compile(rb'"eventId":(\d+)')

OnDiffCallback = Callable[[int], Awaitable[None]]
OnMatchEventCallback = Callable[[MatchEvent], Awaitable[None]]


class BetanoWSClient:
    def __init__(self, session: BetanoSession):
        self._s = session
        self._contenthub_task: Optional[asyncio.Task] = None
        self._match_tasks: dict[int, asyncio.Task] = {}
        self._stop = asyncio.Event()
        self._on_diff: Optional[OnDiffCallback] = None

    async def start(self, on_diff: Optional[OnDiffCallback] = None) -> None:
        self._on_diff = on_diff
        if self._contenthub_task is None or self._contenthub_task.done():
            self._contenthub_task = asyncio.create_task(self._run_contenthub_forever())

    async def stop(self) -> None:
        self._stop.set()
        if self._contenthub_task:
            self._contenthub_task.cancel()
        for t in list(self._match_tasks.values()):
            t.cancel()
        # aguarda cancellation propagar
        pending = [self._contenthub_task] + list(self._match_tasks.values())
        for t in pending:
            if t is None:
                continue
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    async def subscribe_match(
        self, event_id: int, on_event: OnMatchEventCallback
    ) -> None:
        if event_id in self._match_tasks and not self._match_tasks[event_id].done():
            log.debug("ws.matchhub.already_subscribed event=%d", event_id)
            return
        self._match_tasks[event_id] = asyncio.create_task(
            self._run_matchhub_forever(event_id, on_event)
        )

    async def unsubscribe_match(self, event_id: int) -> None:
        t = self._match_tasks.pop(event_id, None)
        if t:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    # ---- internals ----

    async def _ws_connect(self, url: str):
        headers = [
            ("Origin", "https://www.betano.bet.br"),
            ("Cookie", self._s.cookie_header()),
            ("User-Agent", self._s.user_agent()),
        ]
        return await websockets.connect(url, additional_headers=headers)

    @staticmethod
    def _extract_event_id_from_diff(payload_b64: str) -> Optional[int]:
        try:
            decoded = base64.b64decode(payload_b64, validate=False)
        except Exception:
            return None
        m = _EVENT_ID_RE.search(decoded)
        try:
            return int(m.group(1)) if m else None
        except (TypeError, ValueError):
            return None

    async def _handshake(self, ws) -> None:
        await ws.send(INIT_MSG)
        first = await asyncio.wait_for(ws.recv(), timeout=10)
        if not isinstance(first, str) or not first.startswith("{}"):
            raise RuntimeError(f"signalr handshake invalid: {str(first)[:80]}")

    async def _run_contenthub_forever(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                ws = await self._ws_connect(
                    "wss://www.betano.bet.br/contenthub?platformType=1"
                )
                log.info("ws.contenthub.connected")
                try:
                    await self._handshake(ws)
                    subscribe = {
                        "arguments": [{
                            "language": 5,
                            "platformType": 1,
                            "includeVirtuals": True,
                        }],
                        "invocationId": "0",
                        "target": "joinLiveOverviewGroupWithOptions",
                        "type": TYPE_INVOCATION,
                    }
                    await ws.send(json.dumps(subscribe) + SEP)
                    backoff = 1.0
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        for chunk in str(raw).split(SEP):
                            if not chunk:
                                continue
                            await self._handle_contenthub_chunk(ws, chunk)
                finally:
                    await ws.close()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning(
                    "ws.contenthub.error err=%s — reconnect in %.1fs",
                    e, backoff,
                )
                await asyncio.sleep(backoff + random.random())
                backoff = min(backoff * 2, 60)

    async def _handle_contenthub_chunk(self, ws, chunk: str) -> None:
        try:
            parsed = json.loads(chunk)
        except json.JSONDecodeError:
            return
        mtype = parsed.get("type")
        if mtype == TYPE_PING:
            try:
                await ws.send(json.dumps({"type": TYPE_PING}) + SEP)
            except Exception:
                pass
            return
        if mtype == TYPE_CLOSE:
            raise RuntimeError("server sent CLOSE")
        if parsed.get("target") == "NewLiveOverviewDiffs":
            args = parsed.get("arguments") or []
            if args and self._on_diff:
                eid = self._extract_event_id_from_diff(args[0])
                if eid is not None:
                    try:
                        await self._on_diff(eid)
                    except Exception:
                        log.exception("ws.contenthub.callback.error")

    async def _run_matchhub_forever(
        self, event_id: int, on_event: OnMatchEventCallback
    ) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                ws = await self._ws_connect(
                    "wss://www.betano.bet.br/sbpitches/statsstream/matchhub"
                )
                log.info("ws.matchhub.connected event=%d", event_id)
                try:
                    await self._handshake(ws)
                    subscribe = {
                        "arguments": [str(event_id)],
                        "invocationId": "0",
                        "target": "Subscribe",
                        "type": TYPE_INVOCATION,
                    }
                    await ws.send(json.dumps(subscribe) + SEP)
                    backoff = 1.0
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        for chunk in str(raw).split(SEP):
                            if not chunk:
                                continue
                            await self._handle_matchhub_chunk(ws, chunk, on_event)
                finally:
                    await ws.close()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning(
                    "ws.matchhub.error event=%d err=%s — reconnect in %.1fs",
                    event_id, e, backoff,
                )
                await asyncio.sleep(backoff + random.random())
                backoff = min(backoff * 2, 60)

    async def _handle_matchhub_chunk(
        self, ws, chunk: str, on_event: OnMatchEventCallback
    ) -> None:
        try:
            parsed = json.loads(chunk)
        except json.JSONDecodeError:
            return
        mtype = parsed.get("type")
        if mtype == TYPE_PING:
            try:
                await ws.send(json.dumps({"type": TYPE_PING}) + SEP)
            except Exception:
                pass
            return
        if mtype == TYPE_CLOSE:
            raise RuntimeError("server sent CLOSE")
        if mtype == TYPE_COMPLETION:
            result = parsed.get("result")
            if isinstance(result, dict):
                me = parsers.parse_match_event_initial(result.get("data") or result)
                if me:
                    try:
                        await on_event(me)
                    except Exception:
                        log.exception("ws.matchhub.initial.callback.error")
            return
        if parsed.get("target") == "MatchEvent":
            args = parsed.get("arguments") or []
            if not args:
                return
            try:
                arg0 = args[0]
                me = parsers.parse_match_event(arg0) if isinstance(arg0, str) else parsers._build_match_event(arg0)
                await on_event(me)
            except Exception:
                log.exception("ws.matchhub.event.parse_or_callback.error")
