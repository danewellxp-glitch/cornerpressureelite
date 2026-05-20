"""SofaScore live feed via WebSocket NATS (Sprint N — descoberto em 2026-05-20).

O SofaScore expõe um broker NATS-over-WebSocket em `wss://ws.sofascore.com:9222/`
(sem auth — `user:none`). O browser faz:

    CONNECT {...}\r\n  PING\r\n
    SUB sport.football <sid>\r\n      # firehose: deltas de TODOS os jogos
    SUB event.<sofa_id> <sid>\r\n     # por-evento

e recebe `MSG <subject> <sid> <nbytes>\r\n<payload>\r\n`, onde o payload é um
delta achatado com dot-paths + `id`, ex:

    {"homeScore.current":2,"homeScore.period1":2,"id":15832136}
    {"status.type":"finished","statusDescription":"FT","id":15551983}
    {"cardsCode":"00","id":16146899}

**O que isto NÃO é:** não traz contagem de escanteios/posse — só placar, status,
tempo e cardsCode. É um *notificador de mudança* + feed de placar/status, não
fonte de stats completa. Uso pretendido (próximo sprint, atrás de flag):
  - FT em tempo real → cold-check instantâneo (substitui o poll de 2h via AF).
  - Smart-polling → re-buscar `/event/{id}/statistics` SÓ quando o WS sinaliza
    mudança (placar/cartão), em vez de pollar cego a cada 30s.

curl_cffi (impersonate chrome) é necessário — o host está atrás de Cloudflare e
clientes HTTP normais tomam 403, igual ao REST (ver SofaScoreClient).

Conexão é bloqueante (curl_cffi WebSocket é sync) → roda em thread daemon e
empurra deltas pra uma asyncio.Queue thread-safe. Consome com `async for`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("cpes.providers.sofascore.ws")

_WS_URL = "wss://ws.sofascore.com:9222/"
_ORIGIN = "https://www.sofascore.com"
# Réplica do handshake do browser (capturado 2026-05-20).
_CONNECT = (
    '{"protocol":1,"version":"3.1.0","lang":"nats.ws","verbose":false,'
    '"pedantic":false,"user":"none","pass":"none","headers":true,'
    '"no_responders":true}'
)


@dataclass(frozen=True)
class LiveDelta:
    """Um delta empurrado pelo NATS. `fields` tem dot-paths achatados."""
    subject: str
    sofa_event_id: Optional[int]
    fields: dict

    @property
    def is_finished(self) -> bool:
        return self.fields.get("status.type") == "finished"

    @property
    def has_card_change(self) -> bool:
        return "cardsCode" in self.fields

    @property
    def has_score_change(self) -> bool:
        return any(k.startswith("homeScore") or k.startswith("awayScore")
                   for k in self.fields)


def parse_nats(buffer: str) -> tuple[list[object], str, bool]:
    """Parseia frames NATS completos de `buffer`.

    Retorna `(eventos, resto_buffer, server_ping)`:
      - `eventos`: lista de `LiveDelta` (de frames MSG com payload JSON válido).
      - `resto_buffer`: bytes/texto de um frame incompleto (preservado pro próximo).
      - `server_ping`: True se o servidor mandou PING (caller deve responder PONG).

    Framing NATS: linhas terminadas em `\\r\\n`. `MSG <subject> <sid> [reply] <nbytes>`
    é seguido de exatamente `nbytes` de payload + `\\r\\n`.
    """
    events: list[object] = []
    server_ping = False
    while True:
        nl = buffer.find("\r\n")
        if nl == -1:
            break
        line = buffer[:nl]
        verb = line.split(" ", 1)[0].upper()

        if verb == "MSG":
            parts = line.split()
            # MSG <subject> <sid> [reply] <nbytes>
            try:
                subject = parts[1]
                nbytes = int(parts[-1])
            except (IndexError, ValueError):
                buffer = buffer[nl + 2:]  # linha malformada — descarta
                continue
            payload_start = nl + 2
            payload_end = payload_start + nbytes
            if len(buffer) < payload_end + 2:
                break  # payload incompleto — espera mais dados
            payload = buffer[payload_start:payload_end]
            buffer = buffer[payload_end + 2:]
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                ev_id = data.get("id")
                events.append(LiveDelta(
                    subject=subject,
                    sofa_event_id=ev_id if isinstance(ev_id, int) else None,
                    fields=data,
                ))
        else:
            if verb == "PING":
                server_ping = True
            # INFO / PONG / +OK / -ERR / PING: consome a linha e segue.
            buffer = buffer[nl + 2:]
    return events, buffer, server_ping


class SofaScoreLiveFeed:
    """Consome o firehose NATS do SofaScore. Roda em thread, expõe asyncio.Queue.

        feed = SofaScoreLiveFeed(subjects=["sport.football"])
        await feed.start()
        async for delta in feed:
            if delta.is_finished: ...
        await feed.stop()
    """

    def __init__(
        self,
        subjects: Optional[list[str]] = None,
        impersonate: str = "chrome120",
        queue_maxsize: int = 10000,
    ):
        self._subjects = subjects or ["sport.football"]
        self._impersonate = impersonate
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_maxsize)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ws = None
        self._stop = threading.Event()

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sofa-ws", daemon=True)
        self._thread.start()

    def _emit(self, delta: LiveDelta) -> None:
        if self._loop is None:
            return
        def _put():
            if not self._queue.full():
                self._queue.put_nowait(delta)
        self._loop.call_soon_threadsafe(_put)

    def _run(self) -> None:
        from curl_cffi import requests as cr
        try:
            self._ws = cr.WebSocket()
            self._ws.connect(
                _WS_URL, impersonate=self._impersonate,
                headers={"Origin": _ORIGIN},
            )
            self._ws.send(("CONNECT " + _CONNECT + "\r\n").encode())
            self._ws.send(b"PING\r\n")
            for i, subj in enumerate(self._subjects, start=1):
                self._ws.send(f"SUB {subj} {i}\r\n".encode())
            log.info("sofa_ws.connected subjects=%s", self._subjects)

            buffer = ""
            while not self._stop.is_set():
                try:
                    raw = self._ws.recv()[0]
                except Exception as e:
                    if not self._stop.is_set():
                        log.warning("sofa_ws.recv_error err=%s", e)
                    break
                buffer += raw.decode("utf-8", "replace")
                events, buffer, server_ping = parse_nats(buffer)
                if server_ping:
                    try:
                        self._ws.send(b"PONG\r\n")
                    except Exception:
                        break
                for ev in events:
                    self._emit(ev)
        except Exception as e:
            log.warning("sofa_ws.connect_error err=%s", e)
        finally:
            self._safe_close()

    def _safe_close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass

    async def get(self, timeout: Optional[float] = None) -> Optional[LiveDelta]:
        try:
            if timeout is None:
                return await self._queue.get()
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def __aiter__(self):
        return self

    async def __anext__(self) -> LiveDelta:
        return await self._queue.get()

    async def stop(self) -> None:
        self._stop.set()
        self._safe_close()
        if self._thread is not None:
            await asyncio.get_running_loop().run_in_executor(None, self._thread.join, 3.0)
