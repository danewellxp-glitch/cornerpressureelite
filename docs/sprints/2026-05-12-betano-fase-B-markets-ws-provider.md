# Fase B — Betano Markets & WebSocket Provider

> **Mestre:** [`2026-05-12-betano-discovery-master.md`](2026-05-12-betano-discovery-master.md)
>
> **Pré-requisitos:** [Fase A](2026-05-12-betano-fase-A-statsstream-provider.md) concluída.
>
> **Duração estimada:** ~16h

---

## 1. Objetivo

Completar o provider Betano com 3 componentes:

1. **`BetanoMarkets`** — REST `/danae-webapi/api/live/events/{id}/latest` com
   parser de 279 mercados + filtro por codes (CNOU, TCOU, etc).
2. **`BetanoCatalog`** — REST `/danae-webapi/api/live/overview/latest` para
   listar eventos do dia e fuzzy match `fixture_id → event_id`.
3. **`BetanoWSClient`** — SignalR Core client para `/contenthub` (gatilho de
   updates) e `/sbpitches/statsstream/matchhub` (push de eventos Opta com X/Y).

E expandir o **`BetanoSession`** (criado mínimo na Fase A) com:

4. **Warmup browser via Playwright** — sequência completa de cookies
   (Cloudflare + DataDome + sticky_sb) em headless Chromium.
5. **Refresh on-demand** — quando algum endpoint retorna 403/451, refaz warmup
   e re-tenta.

---

## 2. Pré-requisitos

- [x] Fase A concluída — `BetanoSession`, `BetanoStatsStream`, schemas, parsers
- [ ] `playwright` instalado: `pip install playwright && playwright install chromium`
- [ ] Proxies BR disponíveis (Webshare 50 IPs SP — `.env` `WEBSHARE_PROXIES`)
- [ ] Pelo menos 1 evento ao vivo conhecido pra testes (qualquer Brasileirão
      ou liga top)

---

## 3. Capabilities entregues

1. **Warmup automatizado** — `BetanoSession.warmup()` abre Chromium headless,
   navega na home + um evento ao vivo, espera Cloudflare + DataDome
   resolverem, extrai cookies + kbversion.
2. **Detecção e refresh** — endpoint que retorna 403/451 dispara
   `_relogin_if_needed()` automaticamente.
3. **`BetanoMarkets.get_event_latest(event_id)`** — retorna `EventSnapshot`
   completo (event + markets + selections).
4. **`BetanoMarkets.fetch_corners(event_id, linha=None)`** — wrapper
   conveniente que filtra `CNOU` na linha desejada (ou principal).
5. **`BetanoMarkets.fetch_cards(event_id, linha=None)`** — análogo com `TCOU`.
6. **`BetanoCatalog.list_live_events()`** — retorna `list[BetanoLiveEvent]`
   com nome, kickoff, league, sport.
7. **`BetanoCatalog.find_event_by_fixture(fixture_id, team_home, team_away,
   kickoff_at, league_id_hint=None)`** — fuzzy match.
8. **`BetanoCatalog.resolve_event_full(event_id)`** — busca `statsplayer` e
   complementa com matchIds Opta + Sportradar (usa o que vier).
9. **`BetanoWSClient.start()`** — abre WS `/contenthub`, assina
   `joinLiveOverviewGroupWithOptions`. Expõe `on_diff(callback)` para sinais
   de mudança (gatilho).
10. **`BetanoWSClient.subscribe_match(event_id, callback)`** — abre WS
    `/sbpitches/statsstream/matchhub`, assina o evento. Callback recebe
    `MatchEvent` parseado (X/Y, player, attack flags).
11. **Reconnect com backoff** — perda de conexão WS → 1s, 2s, 5s, 10s, 30s,
    teto 60s. Re-assina automaticamente.
12. **Proxy rotation** — `BetanoSession` aceita `proxies: list[str]`. Marca
    proxy como "burned" por 30min em 403; pula. Se todos burned, espera
    1min e tenta o menos recente.
13. **Smoke script** — `scripts/betano_markets_smoke.py` que recebe
    `--event-id` e imprime CNOU e TCOU encontrados.

---

## 4. Decisões críticas

### 4.1 Warmup via Playwright + captura passiva

```python
async def warmup(self):
    async with self._warmup_lock:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; ...) ...",
                viewport={"width": 393, "height": 852},
                is_mobile=True, has_touch=True,
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            page = await context.new_page()

            # navega na home
            await page.goto("https://www.betano.bet.br/",
                            wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            # toca em "Ao Vivo" pra disparar mais cookies
            try:
                await page.click('a[href*="/live"]', timeout=5000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass

            # extrai cookies
            for c in await context.cookies():
                self._cookies[c["name"]] = c["value"]

            # busca kbversion via fetch interno (evita parsing HTML)
            kb = await page.evaluate(
                "async()=>(await fetch('/api/kb-config/').then(r=>r.json()))"
                ".releaseConfig"
            )
            if kb:
                self._kbversion = kb.get("latestVersion", "3.41.0")

            await browser.close()

    # reconstroi http client com novos cookies
    if self._http:
        await self._http.close()
    self._http = AsyncSession(
        impersonate="chrome131", cookies=self._cookies,
        proxies=self._proxy_dict(), timeout=15,
    )
```

### 4.2 Detecção 403 → warmup → retry uma vez

```python
async def get_json(self, path, referer=None):
    for outer in range(2):  # 0 = primeira tentativa; 1 = pós-warmup
        try:
            r = await self._http.get(url, headers=...)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (403, 451):
                if outer == 0:
                    log.warning("betano.403 — warmup e retry")
                    await self.warmup()
                    continue
                raise BetanoBlockedError(...)
            ...
        except ...
    return None
```

### 4.3 Filtro de mercados: por type, depois por handicap

```python
def _filter_market(markets: dict, type_code: str, linha: float | None):
    """Filtra dict de markets por type, opcionalmente por handicap.

    Retorna: lista de markets matching, ordenada por handicap se aplicável.
    """
    matching = []
    for mid, m in markets.items():
        if m.get("type") != type_code:
            continue
        if linha is not None and m.get("handicap") != linha:
            continue
        matching.append(m)
    return sorted(matching, key=lambda m: m.get("handicap", 0))
```

### 4.4 "Linha principal" quando o caller não pede uma específica

```python
def _pick_main_line(markets_filtered, selections):
    """Escolhe linha cuja odd Over esteja mais próxima de 1.95.

    Lê selections[selection_id_list[0]].price.
    """
    best = None
    best_dist = float("inf")
    for m in markets_filtered:
        if len(m.get("selectionIdList", [])) < 2:
            continue
        over_id = str(m["selectionIdList"][0])  # "Mais" geralmente vem antes
        over_sel = selections.get(over_id)
        if not over_sel:
            continue
        odd = over_sel.get("price", 0)
        dist = abs(odd - 1.95)
        if dist < best_dist:
            best_dist = dist
            best = m
    return best
```

### 4.5 Identificação de Over/Under dentro de selections

A captura mostra que **`name == "Mais"`** indica Over e **`name == "Menos"`**
indica Under. Mas a ordem em `selectionIdList` parece ser sempre [over, under]
no `CNOU` e `TCOU`. Para segurança, ler o `name`:

```python
def _split_over_under(market, selections):
    over = under = None
    for sel_id in market.get("selectionIdList", []):
        sel = selections.get(str(sel_id))
        if not sel:
            continue
        name_norm = sel.get("name", "").lower()
        if name_norm in ("mais", "over", "+"):
            over = sel
        elif name_norm in ("menos", "under", "-"):
            under = sel
    return over, under
```

### 4.6 SignalR Core — protocolo nativo, sem biblioteca

Usar `websockets` (`pip install websockets`) e implementar handshake manual.
SignalR Core JSON é simples:

```python
INIT_MSG = '{"protocol":"json","version":1}\x1e'

# Tipos de mensagem (campo `type`)
TYPE_INVOCATION = 1       # cliente invoca método ou servidor envia push
TYPE_STREAM_ITEM = 2
TYPE_COMPLETION = 3
TYPE_STREAM_INVOCATION = 4
TYPE_CANCEL_INVOCATION = 5
TYPE_PING = 6             # keepalive
TYPE_CLOSE = 7

async def connect_contenthub(session):
    ws = await websockets.connect(
        f"wss://www.betano.bet.br/contenthub?platformType=1",
        extra_headers={
            "Origin": "https://www.betano.bet.br",
            "Cookie": session.cookie_header(),
            "User-Agent": session.user_agent(),
        }
    )
    # handshake
    await ws.send(INIT_MSG)
    # primeira resposta deve ser {}
    first = await ws.recv()
    assert first.startswith("{}"), f"handshake falhou: {first}"

    # subscribe
    subscribe = {
        "arguments": [{"language": 5, "platformType": 1,
                       "includeVirtuals": True}],
        "invocationId": "0",
        "target": "joinLiveOverviewGroupWithOptions",
        "type": 1,
    }
    await ws.send(json.dumps(subscribe) + "\x1e")

    return ws
```

### 4.7 Não parsear `NewLiveOverviewDiffs` payload — usar como gatilho

Payload binário+JSON intercalado é proprietário. Em vez de implementar
parser custom, o callback do `contenthub` apenas extrai o `eventId`
referenciado e dispara re-fetch REST:

```python
def _extract_event_id_from_diff(payload: str) -> int | None:
    """O payload é base64. Decoded, contém JSON UTF-8 com 'eventId':XXX.
    Procuramos por regex simples; suficiente como gatilho."""
    try:
        decoded = base64.b64decode(payload).decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r'"eventId":(\d+)', decoded)
    return int(m.group(1)) if m else None
```

### 4.8 `matchhub` parser — JSON puro, sem mistério

```python
def parse_match_event(arg_str: str) -> MatchEvent:
    """Recebe a string interna do MatchEvent (vem escaped em JSON)."""
    data = json.loads(arg_str)
    ed = data.get("event_data", {})
    bp = ed.get("ball_position", {})
    bpe = ed.get("ball_position_end", {})
    return MatchEvent(
        opta_match_id=data.get("event_match_id", ""),
        sportsbook_match_id=int(data.get("sportsbook_match_id", 0)),
        event_type=int(data.get("event_type", -1)),
        period_id=int(data.get("event_period_id", 0)),
        minute=int(data.get("event_match_minute", 0)),
        seconds=int(data.get("event_match_second", 0)),
        team_id=ed.get("team_id"),
        player_id=ed.get("player_id"),
        x=bp.get("x"), y=bp.get("y"),
        x_end=bpe.get("x"), y_end=bpe.get("y"),
        is_attack=ed.get("is_attack", False),
        is_dangerous_attack=ed.get("is_dangerous_attack", False),
        is_possession=ed.get("is_possession", False),
        is_dangerous=ed.get("is_dangerous", False),
        provider_type=data.get("event_provider_type", "?"),
        raw=data,
    )
```

### 4.9 Sem login em produção

Operar sempre **anônimo**. Warmup navega na home + /live, **não** loga.
Reduz vetor `kz_trusted_device_*` e `pocaauth`. Cookies suficientes para
leitura.

### 4.10 Não compartilhar warmup entre instâncias

Cada `BetanoSession` faz seu próprio warmup. Em produção real (Fase C), uma
instância global da sessão é injetada no orquestrador. Lock async garante
warmup serial.

---

## 5. Componentes novos

### 5.1 `data/providers/betano/session.py` (expansão pós-Fase A)

```python
# adiciona ao session.py da Fase A
import asyncio
from playwright.async_api import async_playwright


class BetanoSession:
    # ... __init__, from_file, get_json da Fase A ...

    def __init__(self, ..., proxies: list[str] | None = None):
        # ... resto ...
        self._proxies = proxies or []
        self._proxy_idx = 0
        self._proxy_burned: dict[str, float] = {}
        self._warmup_lock = asyncio.Lock()

    def _next_proxy(self) -> str | None:
        if not self._proxies:
            return None
        now = time.time()
        # cleanup burned
        self._proxy_burned = {
            p: until for p, until in self._proxy_burned.items()
            if until > now
        }
        candidates = [p for p in self._proxies
                      if p not in self._proxy_burned]
        if not candidates:
            log.warning("betano.proxy.all_burned — usando o de menor TTL")
            return min(self._proxy_burned, key=self._proxy_burned.get)
        p = candidates[self._proxy_idx % len(candidates)]
        self._proxy_idx += 1
        return p

    def _proxy_dict(self) -> dict | None:
        p = self._next_proxy()
        return {"http": p, "https": p} if p else None

    async def warmup(self) -> None:
        # ... implementação da decisão 4.1 ...
        pass

    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    def user_agent(self) -> str:
        return HEADERS_BASE["User-Agent"]
```

### 5.2 `data/providers/betano/markets.py`

```python
import logging
from .session import BetanoSession
from .schemas import (
    EventSnapshot, BetanoMarket, BetanoSelection,
    BetanoLiveData, BetanoIncident, BetanoOverUnder,
)
from . import parsers
from .codes import MARKET_CODES_CORNERS_MAIN, MARKET_CODES_CARDS_MAIN

log = logging.getLogger("cpes.betano.markets")


class BetanoMarkets:
    def __init__(self, session: BetanoSession):
        self._s = session

    def _referer(self, event_id: int) -> str:
        return f"https://www.betano.bet.br/live/_/{event_id}/"

    async def get_event_latest(
        self, event_id: int
    ) -> EventSnapshot | None:
        raw = await self._s.get_json(
            f"/danae-webapi/api/live/events/{event_id}/latest",
            referer=self._referer(event_id),
        )
        return parsers.parse_event_snapshot(raw) if raw else None

    async def fetch_corners(
        self, event_id: int, linha: float | None = None
    ) -> BetanoOverUnder | None:
        snap = await self.get_event_latest(event_id)
        if not snap:
            return None
        return parsers.extract_over_under(
            snap, type_code="CNOU", linha=linha
        )

    async def fetch_cards(
        self, event_id: int, linha: float | None = None
    ) -> BetanoOverUnder | None:
        snap = await self.get_event_latest(event_id)
        if not snap:
            return None
        return parsers.extract_over_under(
            snap, type_code="TCOU", linha=linha
        )

    async def fetch_market_by_code(
        self, event_id: int, type_code: str, linha: float | None = None
    ) -> BetanoOverUnder | None:
        """Generic accessor — útil para RCOU, HRED, etc."""
        snap = await self.get_event_latest(event_id)
        if not snap:
            return None
        return parsers.extract_over_under(
            snap, type_code=type_code, linha=linha
        )
```

### 5.3 `data/providers/betano/catalog.py`

```python
import logging
import unicodedata
from datetime import datetime, timezone
from .session import BetanoSession
from .schemas import BetanoLiveEvent, BetanoStatsPlayerMapping
from . import parsers

log = logging.getLogger("cpes.betano.catalog")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


class BetanoCatalog:
    def __init__(self, session: BetanoSession):
        self._s = session
        self._events_cache: list[BetanoLiveEvent] = []
        self._fixture_map: dict[int, int] = {}  # fixture_id → event_id

    async def list_live_events(self) -> list[BetanoLiveEvent]:
        raw = await self._s.get_json(
            "/danae-webapi/api/live/overview/latest",
            referer="https://www.betano.bet.br/live/futebol/",
        )
        if not raw:
            return []
        self._events_cache = parsers.parse_live_overview_events(raw)
        return self._events_cache

    async def find_event_by_fixture(
        self,
        fixture_id: int,
        team_home: str,
        team_away: str,
        kickoff_at: datetime,
        league_id_hint: int | None = None,
    ) -> int | None:
        if fixture_id in self._fixture_map:
            return self._fixture_map[fixture_id]
        if not self._events_cache:
            await self.list_live_events()

        nh = _norm(team_home)
        na = _norm(team_away)
        candidates = []

        for ev in self._events_cache:
            if ev.sport_id != "FOOT":
                continue
            participants = [_norm(p.name) for p in ev.participants]
            home_match = any(nh in p or p in nh for p in participants)
            away_match = any(na in p or p in na for p in participants)
            if not (home_match and away_match):
                continue
            delta_min = abs((ev.start_time - kickoff_at).total_seconds() / 60)
            if delta_min > 15:
                continue
            score = 100 - delta_min  # quanto menor delta, melhor
            candidates.append((score, ev))

        if not candidates:
            log.info("betano.catalog.no_match fixture=%d %s vs %s",
                     fixture_id, team_home, team_away)
            return None

        candidates.sort(key=lambda x: -x[0])
        best = candidates[0][1]
        self._fixture_map[fixture_id] = best.event_id
        log.info("betano.catalog.matched fixture=%d → event=%d",
                 fixture_id, best.event_id)
        return best.event_id

    async def resolve_event_full(
        self, event_id: int
    ) -> BetanoStatsPlayerMapping | None:
        """Busca matchIds Opta + Sportradar via /api/liveevent/statsplayer."""
        raw = await self._s.get_json(
            f"/api/liveevent/statsplayer?id={event_id}",
            referer=f"https://www.betano.bet.br/live/_/{event_id}/",
        )
        return parsers.parse_statsplayer(raw, event_id) if raw else None
```

### 5.4 `data/providers/betano/wsclient.py`

```python
import asyncio
import json
import logging
import random
import re
import base64
import websockets
from typing import Callable, Awaitable
from .session import BetanoSession
from .schemas import MatchEvent
from . import parsers

log = logging.getLogger("cpes.betano.ws")

SEP = "\x1e"
INIT = '{"protocol":"json","version":1}' + SEP

EVENT_ID_RE = re.compile(rb'"eventId":(\d+)')


class BetanoWSClient:
    def __init__(self, session: BetanoSession):
        self._s = session
        self._contenthub_task: asyncio.Task | None = None
        self._match_tasks: dict[int, asyncio.Task] = {}
        self._stop = asyncio.Event()
        self._on_diff_callback: Callable | None = None

    async def start(
        self,
        on_diff: Callable[[int], Awaitable[None]] | None = None,
    ) -> None:
        """Abre contenthub e mantém persistente."""
        self._on_diff_callback = on_diff
        self._contenthub_task = asyncio.create_task(
            self._run_contenthub_forever()
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._contenthub_task:
            self._contenthub_task.cancel()
        for t in self._match_tasks.values():
            t.cancel()

    async def subscribe_match(
        self,
        event_id: int,
        on_event: Callable[[MatchEvent], Awaitable[None]],
    ) -> None:
        if event_id in self._match_tasks:
            return  # já assinado
        self._match_tasks[event_id] = asyncio.create_task(
            self._run_matchhub_forever(event_id, on_event)
        )

    async def unsubscribe_match(self, event_id: int) -> None:
        t = self._match_tasks.pop(event_id, None)
        if t:
            t.cancel()

    # ---- internals ----

    async def _ws_connect(self, url: str):
        return await websockets.connect(
            url,
            extra_headers={
                "Origin": "https://www.betano.bet.br",
                "Cookie": self._s.cookie_header(),
                "User-Agent": self._s.user_agent(),
            },
        )

    async def _run_contenthub_forever(self):
        backoff = 1.0
        while not self._stop.is_set():
            try:
                ws = await self._ws_connect(
                    "wss://www.betano.bet.br/contenthub?platformType=1"
                )
                log.info("ws.contenthub.connected")
                await ws.send(INIT)
                # consume handshake response
                first = await asyncio.wait_for(ws.recv(), timeout=10)
                if not first.startswith("{}"):
                    raise RuntimeError(f"handshake invalid: {first[:80]}")

                # subscribe
                msg = {
                    "arguments": [{"language": 5, "platformType": 1,
                                   "includeVirtuals": True}],
                    "invocationId": "0",
                    "target": "joinLiveOverviewGroupWithOptions",
                    "type": 1,
                }
                await ws.send(json.dumps(msg) + SEP)

                backoff = 1.0  # reset

                async for raw in ws:
                    for chunk in raw.split(SEP):
                        if not chunk:
                            continue
                        try:
                            parsed = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        if parsed.get("type") == 6:
                            # ping → responde pong
                            await ws.send(json.dumps({"type": 6}) + SEP)
                            continue
                        if parsed.get("target") == "NewLiveOverviewDiffs":
                            args = parsed.get("arguments", [])
                            if args and self._on_diff_callback:
                                event_id = self._extract_event_id(args[0])
                                if event_id:
                                    try:
                                        await self._on_diff_callback(event_id)
                                    except Exception:
                                        log.exception("contenthub.callback.error")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("ws.contenthub.error: %s — reconnecting in %.1fs",
                            e, backoff)
                await asyncio.sleep(backoff + random.random())
                backoff = min(backoff * 2, 60)

    def _extract_event_id(self, payload_b64: str) -> int | None:
        try:
            decoded = base64.b64decode(payload_b64)
        except Exception:
            return None
        m = EVENT_ID_RE.search(decoded)
        return int(m.group(1)) if m else None

    async def _run_matchhub_forever(
        self,
        event_id: int,
        on_event: Callable[[MatchEvent], Awaitable[None]],
    ):
        backoff = 1.0
        while not self._stop.is_set():
            try:
                ws = await self._ws_connect(
                    "wss://www.betano.bet.br/sbpitches/statsstream/matchhub"
                )
                log.info("ws.matchhub.connected event_id=%d", event_id)
                await ws.send(INIT)
                first = await asyncio.wait_for(ws.recv(), timeout=10)
                if not first.startswith("{}"):
                    raise RuntimeError(f"matchhub handshake invalid")

                msg = {
                    "arguments": [str(event_id)],
                    "invocationId": "0",
                    "target": "Subscribe",
                    "type": 1,
                }
                await ws.send(json.dumps(msg) + SEP)
                backoff = 1.0

                async for raw in ws:
                    for chunk in raw.split(SEP):
                        if not chunk:
                            continue
                        try:
                            parsed = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        if parsed.get("type") == 6:
                            await ws.send(json.dumps({"type": 6}) + SEP)
                            continue
                        # primeira resposta vem com type=3 (completion), valor inicial
                        # depois MatchEvent é target=...
                        if parsed.get("type") == 3:
                            result = parsed.get("result", {})
                            if isinstance(result, dict) and "data" in result:
                                try:
                                    me = parsers.parse_match_event_initial(
                                        result["data"]
                                    )
                                    if me:
                                        await on_event(me)
                                except Exception:
                                    log.exception("matchhub.initial.parse")
                        elif parsed.get("target") == "MatchEvent":
                            args = parsed.get("arguments", [])
                            if not args:
                                continue
                            try:
                                me = parsers.parse_match_event(args[0])
                                await on_event(me)
                            except Exception:
                                log.exception("matchhub.event.parse")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("ws.matchhub.error event=%d: %s — reconnect %.1fs",
                            event_id, e, backoff)
                await asyncio.sleep(backoff + random.random())
                backoff = min(backoff * 2, 60)
```

### 5.5 Adições a `schemas.py`

```python
# adiciona ao schemas.py da Fase A
@dataclass(frozen=True)
class BetanoLiveData:
    score_home: int
    score_away: int
    clock_seconds: int


@dataclass(frozen=True)
class BetanoParticipant:
    name: str
    is_home: bool
    team_id: int
    color: Optional[str] = None


@dataclass(frozen=True)
class BetanoIncident:
    type: str
    description: str
    props: dict


@dataclass(frozen=True)
class BetanoMarket:
    id: int
    type_code: str          # "CNOU", "TCOU", ...
    type_id: int
    name: str
    handicap: Optional[float]
    selection_ids: list[int]
    display_order: int
    rendering_layout: int
    market_close_time_millis: int


@dataclass(frozen=True)
class BetanoSelection:
    id: int
    name: str               # "Mais", "Menos", "1", "X", "2", ...
    full_name: str
    price: float            # ODD
    type_id: int
    column_index: int
    display_order: int


@dataclass(frozen=True)
class BetanoOverUnder:
    event_id: int
    market_code: str        # "CNOU", "TCOU"
    handicap: float
    odd_over: float
    odd_under: float


@dataclass(frozen=True)
class EventSnapshot:
    event_id: int
    sport_id: str           # "FOOT"
    league_id: int
    zone_id: int
    is_live: bool
    start_time: datetime
    participants: list[BetanoParticipant]
    live_data: BetanoLiveData
    total_markets_available: int
    betradar_match_id: Optional[int]
    incidents: list[BetanoIncident]
    url: str
    markets: dict[int, BetanoMarket]
    selections: dict[int, BetanoSelection]


@dataclass(frozen=True)
class BetanoLiveEvent:
    event_id: int
    sport_id: str
    league_id: int
    zone_id: int
    participants: list[BetanoParticipant]
    start_time: datetime
    is_live: bool
    will_go_live: bool
    total_markets_available: int
    betradar_match_id: Optional[int]
    url: str


@dataclass(frozen=True)
class BetanoStatsPlayerMapping:
    event_id: int
    sr_match_id: Optional[str]
    opta_match_id: Optional[str]
    available_stat_types: list[int]


@dataclass(frozen=True)
class MatchEvent:
    opta_match_id: str
    sportsbook_match_id: int
    event_type: int             # 0, 3, ...
    period_id: int
    minute: int
    seconds: int
    team_id: Optional[str]
    player_id: Optional[str]
    x: Optional[float]
    y: Optional[float]
    x_end: Optional[float]
    y_end: Optional[float]
    is_attack: bool
    is_dangerous_attack: bool
    is_possession: bool
    is_dangerous: bool
    provider_type: str
    raw: dict
```

### 5.6 Adições a `parsers.py`

```python
# adiciona ao parsers.py da Fase A
from .schemas import (
    EventSnapshot, BetanoMarket, BetanoSelection,
    BetanoLiveData, BetanoParticipant, BetanoIncident,
    BetanoLiveEvent, BetanoStatsPlayerMapping,
    BetanoOverUnder, MatchEvent,
)


def parse_event_snapshot(raw: dict) -> EventSnapshot:
    ev = raw.get("event", {})
    if not ev or "id" not in ev:
        raise BetanoParseError("event_latest sem event.id")
    markets_raw = raw.get("markets", {})
    selections_raw = raw.get("selections", {})

    return EventSnapshot(
        event_id=int(ev["id"]),
        sport_id=ev.get("sportId", ""),
        league_id=int(ev.get("leagueId", 0)),
        zone_id=int(ev.get("zoneId", 0)),
        is_live=bool(ev.get("isLive", False)),
        start_time=datetime.fromtimestamp(
            ev.get("startTime", 0) / 1000, tz=timezone.utc
        ),
        participants=[
            BetanoParticipant(
                name=p.get("name", ""),
                is_home=bool(p.get("isHome", False)),
                team_id=int(p.get("teamId", 0)),
                color=p.get("color"),
            ) for p in ev.get("participants", [])
        ],
        live_data=BetanoLiveData(
            score_home=int(_safe(ev, "liveData", "score", "home", default=0)),
            score_away=int(_safe(ev, "liveData", "score", "away", default=0)),
            clock_seconds=int(_safe(ev, "liveData", "clock",
                                    "secondsSinceStart", default=0)),
        ),
        total_markets_available=int(ev.get("totalMarketsAvailable", 0)),
        betradar_match_id=ev.get("betradarMatchId"),
        incidents=[
            BetanoIncident(
                type=i.get("type", ""),
                description=i.get("description", ""),
                props=i.get("props", {}),
            ) for i in ev.get("incidents", [])
        ],
        url=ev.get("url", ""),
        markets={
            int(mid): _parse_market(m) for mid, m in markets_raw.items()
        },
        selections={
            int(sid): _parse_selection(s) for sid, s in selections_raw.items()
        },
    )


def _parse_market(m: dict) -> BetanoMarket:
    return BetanoMarket(
        id=int(m.get("id", 0)),
        type_code=m.get("type", ""),
        type_id=int(m.get("typeId", 0)),
        name=m.get("name", ""),
        handicap=m.get("handicap"),
        selection_ids=[int(s) for s in m.get("selectionIdList", [])],
        display_order=int(m.get("displayOrder", 0)),
        rendering_layout=int(m.get("renderingLayout", 0)),
        market_close_time_millis=int(m.get("marketCloseTimeMillis", 0)),
    )


def _parse_selection(s: dict) -> BetanoSelection:
    return BetanoSelection(
        id=int(s.get("id", 0)),
        name=s.get("name", ""),
        full_name=s.get("fullName", ""),
        price=float(s.get("price", 0)),
        type_id=int(s.get("typeId", 0)),
        column_index=int(s.get("columnIndex", 0)),
        display_order=int(s.get("displayOrder", 0)),
    )


def extract_over_under(
    snap: EventSnapshot, type_code: str, linha: float | None = None
) -> BetanoOverUnder | None:
    # filtra markets do tipo
    matching = [m for m in snap.markets.values() if m.type_code == type_code]
    if linha is not None:
        matching = [m for m in matching if m.handicap == linha]
    if not matching:
        return None

    # se pediu específica, usa primeira; senão escolhe a "principal" (odd_over ~1.95)
    if linha is not None:
        market = matching[0]
    else:
        market = _pick_main_line(matching, snap.selections)
        if not market:
            return None

    over, under = _split_over_under(market, snap.selections)
    if not over or not under:
        return None
    return BetanoOverUnder(
        event_id=snap.event_id,
        market_code=type_code,
        handicap=market.handicap or 0,
        odd_over=over.price,
        odd_under=under.price,
    )


def _pick_main_line(matching, selections):
    best = None
    best_dist = float("inf")
    for m in matching:
        if not m.selection_ids:
            continue
        sel = selections.get(m.selection_ids[0])
        if not sel:
            continue
        d = abs(sel.price - 1.95)
        if d < best_dist:
            best_dist = d
            best = m
    return best


def _split_over_under(market, selections):
    over = under = None
    for sid in market.selection_ids:
        sel = selections.get(sid)
        if not sel:
            continue
        name = sel.name.lower().strip()
        if name in ("mais", "over", "+"):
            over = sel
        elif name in ("menos", "under", "-"):
            under = sel
    return over, under


def parse_live_overview_events(raw: dict) -> list[BetanoLiveEvent]:
    events_raw = raw.get("events", {}) or {}
    out = []
    for eid, ev in events_raw.items():
        try:
            out.append(BetanoLiveEvent(
                event_id=int(ev.get("id", eid)),
                sport_id=ev.get("sportId", ""),
                league_id=int(ev.get("leagueId", 0)),
                zone_id=int(ev.get("zoneId", 0)),
                participants=[
                    BetanoParticipant(
                        name=p.get("name", ""),
                        is_home=bool(p.get("isHome", False)),
                        team_id=int(p.get("teamId", 0)),
                        color=p.get("color"),
                    ) for p in ev.get("participants", [])
                ],
                start_time=datetime.fromtimestamp(
                    ev.get("startTime", 0) / 1000, tz=timezone.utc
                ),
                is_live=bool(ev.get("isLive", False)),
                will_go_live=bool(ev.get("willGoLive", False)),
                total_markets_available=int(ev.get("totalMarketsAvailable", 0)),
                betradar_match_id=ev.get("betradarMatchId"),
                url=ev.get("url", ""),
            ))
        except Exception:
            continue
    return out


def parse_statsplayer(
    raw: dict, event_id: int
) -> BetanoStatsPlayerMapping:
    models = _safe(raw, "data", "statPlayerModels", default=[]) or []
    sr_id = opta_id = None
    types = []
    for m in models:
        t = m.get("statType")
        if t is not None:
            types.append(int(t))
        mid = str(m.get("matchId", ""))
        if t == 4 and mid.isdigit():
            sr_id = mid
        elif t == 6 and mid:
            opta_id = mid
    return BetanoStatsPlayerMapping(
        event_id=event_id,
        sr_match_id=sr_id,
        opta_match_id=opta_id,
        available_stat_types=types,
    )


def parse_match_event(arg_str: str) -> MatchEvent:
    data = json.loads(arg_str)
    return _build_match_event(data)


def parse_match_event_initial(data: dict) -> MatchEvent | None:
    """Para o caso da primeira resposta do Subscribe (type=3 completion)."""
    if "event_data" not in data:
        return None
    return _build_match_event(data)


def _build_match_event(data: dict) -> MatchEvent:
    ed = data.get("event_data", {})
    bp = ed.get("ball_position", {})
    bpe = ed.get("ball_position_end", {})
    return MatchEvent(
        opta_match_id=data.get("event_match_id", ""),
        sportsbook_match_id=int(data.get("sportsbook_match_id", 0)),
        event_type=int(data.get("event_type", -1)),
        period_id=int(data.get("event_period_id", 0)),
        minute=int(data.get("event_match_minute", 0)),
        seconds=int(data.get("event_match_second", 0)),
        team_id=ed.get("team_id"),
        player_id=ed.get("player_id"),
        x=bp.get("x"), y=bp.get("y"),
        x_end=bpe.get("x"), y_end=bpe.get("y"),
        is_attack=bool(ed.get("is_attack", False)),
        is_dangerous_attack=bool(ed.get("is_dangerous_attack", False)),
        is_possession=bool(ed.get("is_possession", False)),
        is_dangerous=bool(ed.get("is_dangerous", False)),
        provider_type=data.get("event_provider_type", "?"),
        raw=data,
    )
```

### 5.7 `data/providers/betano/codes.py`

```python
"""Catálogo de codes de markets — mantém legibilidade no código."""

# Escanteios — código primário e variações
MARKET_CODES_CORNERS_MAIN = "CNOU"           # Escanteios Mais/Menos
MARKET_CODES_CORNERS_NEXT_TEAM = "NCNT"       # Próxima equipe a cobrar

# Cartões — código primário e variações
MARKET_CODES_CARDS_MAIN = "TCOU"             # Total de Cartões Mais/Menos
MARKET_CODES_CARDS_RED = "RCOU"               # Total de Vermelhos
MARKET_CODES_CARDS_HOME_RED = "HRED"          # Casa Vermelho
MARKET_CODES_CARDS_AWAY_RED = "ARED"          # Fora Vermelho
MARKET_CODES_CARDS_FIRST_HALF_RED = "1RED"    # Vermelho 1°T
MARKET_CODES_CARDS_PLAYER_GETS = "PTRC"       # Jogador receber cartão

# Resultado
MARKET_CODES_RESULT_FINAL = "MRES"           # Resultado Final
MARKET_CODES_RESULT_DOUBLE = "DBLC"           # Chance Dupla
MARKET_CODES_RESULT_DRAW_NO_BET = "DNOB"      # Empate Anula

# Total de Gols
MARKET_CODES_GOALS_TOTAL = "HCTG"            # Total de Gols Mais/Menos
MARKET_CODES_GOALS_BTTS = "BTSC"              # Ambas Marcam
```

### 5.8 `scripts/betano_markets_smoke.py`

```python
"""Smoke fim-a-fim de markets + WS.

Uso:
    python scripts/betano_markets_smoke.py --event-id 84586925
"""
import argparse
import asyncio
from data.providers.betano import BetanoSession, BetanoMarkets, BetanoCatalog


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event-id", type=int, required=True)
    ap.add_argument("--cookies", default="config/betano_cookies.json")
    args = ap.parse_args()

    s = BetanoSession.from_file(args.cookies)
    markets = BetanoMarkets(s)
    cat = BetanoCatalog(s)

    try:
        snap = await markets.get_event_latest(args.event_id)
        print(f"\n=== event {args.event_id} ===")
        if snap:
            print(f"  {snap.participants[0].name} {snap.live_data.score_home} x "
                  f"{snap.live_data.score_away} {snap.participants[1].name}")
            print(f"  Markets disponíveis: {snap.total_markets_available}")
            print(f"  betradarMatchId: {snap.betradar_match_id}")
            print(f"  Liga: {snap.league_id}, Zone: {snap.zone_id}")

        c = await markets.fetch_corners(args.event_id)
        print(f"\n=== CNOU (principal) ===")
        if c:
            print(f"  Linha {c.handicap}: Over {c.odd_over} | Under {c.odd_under}")

        ca = await markets.fetch_cards(args.event_id)
        print(f"\n=== TCOU (principal) ===")
        if ca:
            print(f"  Linha {ca.handicap}: Over {ca.odd_over} | Under {ca.odd_under}")

        mapping = await cat.resolve_event_full(args.event_id)
        print(f"\n=== statsplayer mapping ===")
        if mapping:
            print(f"  Sportradar matchId: {mapping.sr_match_id}")
            print(f"  Opta match_id: {mapping.opta_match_id}")

    finally:
        await s.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. Edge cases

| Caso | Comportamento |
|---|---|
| Snap retorna 281KB mas alguns markets sem selections | Selections faltando viram None no Over/Under; market é pulado |
| Linha pedida (8.5) não existe | Retorna `None`; caller pode fallback pra linha principal |
| Evento finalizado mid-fetch | Snap pode vir com `isLive: false`; provider retorna mesmo assim |
| `CNOU` está suspenso temporariamente | Não aparece em `markets`; fetch retorna `None` |
| WS perde conexão durante jogo | Reconnect com backoff; ao reconectar, re-assina o mesmo event_id |
| WS recebe mensagem com `type=7` (close) | Sai do loop, deixa reconnect tratar |
| Ping `type=6` não chega há 30s | Server provavelmente desconectou; reconnect (sem ping próprio do client por enquanto) |
| Múltiplos subscribes no mesmo event_id | Ignora segundo `subscribe_match` (já tem task) |
| Warmup falha 3x | `BetanoBlockedError` propaga; caller (Composite) cai pro API-Football |
| Cookies do warmup expiram durante WS aberto | WS continua funcionando (cookies validados no handshake); REST ao lado vai falhar e disparar warmup novo |

---

## 7. Testes

### 7.1 Unit

- [ ] `test_parse_event_snapshot_extracts_betradarMatchId`
- [ ] `test_parse_event_snapshot_parses_markets_dict`
- [ ] `test_extract_over_under_picks_requested_handicap`
- [ ] `test_extract_over_under_picks_main_when_no_handicap`
- [ ] `test_extract_over_under_handles_missing_selection`
- [ ] `test_parse_live_overview_filters_foot_events`
- [ ] `test_parse_statsplayer_picks_numeric_sr_id`
- [ ] `test_parse_match_event_extracts_xy`
- [ ] `test_parse_match_event_handles_no_ball_position_end`
- [ ] `test_catalog_find_by_fixture_normalizes_team_names`
- [ ] `test_catalog_find_by_fixture_respects_kickoff_window`
- [ ] `test_catalog_find_by_fixture_returns_none_for_no_match`

### 7.2 Integração (cookies reais)

- [ ] `test_get_event_latest_returns_snapshot_for_live_event`
- [ ] `test_fetch_corners_returns_cnou_for_live_brazilian_game`
- [ ] `test_fetch_cards_returns_tcou`
- [ ] `test_list_live_events_returns_at_least_one_foot`
- [ ] `test_resolve_event_full_returns_mappings`

### 7.3 WS (real)

- [ ] `test_contenthub_connects_and_receives_diff_within_30s`
- [ ] `test_matchhub_subscribe_receives_match_event_within_60s`
- [ ] `test_matchhub_reconnect_after_drop`

### 7.4 Warmup (real)

- [ ] `test_warmup_populates_cf_clearance_and_datadome`
- [ ] `test_warmup_extracts_kbversion_from_kb_config`
- [ ] `test_warmup_session_can_get_event_after_warmup`

---

## 8. Acceptance

- [ ] `BetanoSession.warmup()` opera com Chromium headless mobile
- [ ] Cookies necessários (1-5 da master §5) populados pós-warmup
- [ ] `kbversion` extraído dinamicamente
- [ ] `BetanoMarkets` cobre os 3 métodos públicos (get_event_latest,
      fetch_corners, fetch_cards) + generic `fetch_market_by_code`
- [ ] `BetanoCatalog` lista eventos do dia e faz fuzzy match
- [ ] `BetanoWSClient` mantém 1 conexão `/contenthub` persistente +
      N conexões `/matchhub` (uma por evento monitorado)
- [ ] Reconnect com backoff exponencial funcional
- [ ] Logs estruturados para WS connect/disconnect/error
- [ ] Schemas em `schemas.py` expandidos (8 dataclasses novos)
- [ ] Parsers em `parsers.py` expandidos (6 funções novas)
- [ ] `codes.py` com market codes documentados
- [ ] Smoke `betano_markets_smoke.py` imprime CNOU + TCOU sem erro
- [ ] Suite de testes verde (unit + integração + WS + warmup)
- [ ] 0 chamadas de login (operação 100% anônima)
- [ ] `_relogin_if_needed` testado com 403 simulado
- [ ] Documentação: `sistema-completo.md` §20 atualizado

---

## 9. Pilares cobertos

| Pilar | Contribuição |
|---|---|
| **Multi-fonte** | Betano REST + WS como primary; AF fallback |
| **Conformidade** | Operação anônima — zero risco de conta banida |
| **Resiliência** | Warmup on-demand; reconnect WS; proxy rotation; fallback APIs |
| **Determinismo** | Cookies + cookies congelados → testes reproduzíveis |
| **Observabilidade** | Logs estruturados WS + REST; healthcheck |
| **Camuflagem** | Warmup mobile + headers nativos + jitter |
| **Custo** | On-demand REST + WS persistente; <200 reqs/dia esperado |

---

## 10. Esforço estimado

| Sub-task | Horas |
|---|---|
| `session.warmup()` Playwright + cookies | 2.0 |
| `session._relogin_if_needed` + retry | 0.5 |
| `markets.py` (get_event_latest + filters) | 1.5 |
| `catalog.py` (list + fuzzy match) | 1.5 |
| `wsclient.py` contenthub | 2.0 |
| `wsclient.py` matchhub + reconnect | 2.0 |
| Schemas + parsers novos | 2.0 |
| Testes unit (12 testes) | 1.5 |
| Testes integração + WS + warmup (10 testes) | 1.5 |
| Smoke script | 0.5 |
| Buffer (ajustes WS, anti-bot) | 1.5 |
| **Total** | **16h** |

---

## 11. Bloqueios potenciais

| Bloqueio | Resolução |
|---|---|
| Playwright detectado por CF Bot Management | `playwright-extra` + `puppeteer-extra-plugin-stealth` (porta Python: `playwright-stealth`) |
| WS desconecta toda hora | Verificar `Origin` header; verificar cookies frescos; tentar com IP diferente |
| Fuzzy match falha em times de nomes traduzidos | Manter `data/static/team_aliases_betano.json` com aliases (ex. "Internacional" ↔ "SC Internacional") |
| Markets vêm sem `handicap` em alguns codes | Para esses, usar `selection.fullName` para extrair linha (parser fallback) |
| `betradarMatchId` ausente em alguns eventos | Aceitar `None`; aviso em log; provider segue normal |

---

## 12. Out of scope

- ❌ Decoder do `NewLiveOverviewDiffs` (usar como gatilho apenas)
- ❌ SignalR Classic (`/signalr/connect`) — só widget de quadra, ignorar
- ❌ Login da conta (anônimo é suficiente)
- ❌ Integração no `main.py:796` (Fase C)
- ❌ Persistência em DB (Fase D)
- ❌ Suporte a outros esportes (só futebol)
- ❌ Cache leve do snapshot (caller decide na Fase C)
