# Fase A — Betano StatsStream Provider

> **Mestre:** [`2026-05-12-betano-discovery-master.md`](2026-05-12-betano-discovery-master.md)
>
> **Pré-requisitos:** Spike mitmproxy concluído. `.mitm` golden em
> `docs/sprints/captures/2026-05-12-betano-flow.mitm`.
>
> **Duração estimada:** ~10h

---

## 1. Objetivo

Construir `data/providers/betano/statsstream.py` — REST client que consome os
endpoints `/api/statsstream/{eventId}/*` da Betano (provider real: Opta), com
schemas tipados e parsers testáveis.

**Não toca em `main.py`** — isso é Fase C. Aqui é módulo isolado + testes +
smoke script.

A Fase A **depende da Fase B** apenas para `BetanoSession` (warmup + cookies +
HTTP wrapper). Recomendação: criar `BetanoSession` stub mínimo no início da
Fase A (apenas o suficiente pra fazer GET autenticado por cookies) e
expandir na Fase B.

---

## 2. Pré-requisitos

- [ ] Spike concluído com `.mitm` disponível
- [ ] `curl_cffi` instalável: `pip install curl-cffi`
- [ ] Cookies congelados de uma sessão real (do `.mitm` ou exportados do Chrome).
      Necessários: `cf_clearance`, `__cflb`, `_cfuvid`, `datadome`, `sticky_sb`
- [ ] Pelo menos um `eventId` de jogo ao vivo conhecido para testes
      (do `.mitm`: 84586925 = Cruzeiro × Goiás; 85539522 = Argentinos × Huracán)

---

## 3. Capabilities entregues

1. **`BetanoSession` mínimo** — carrega cookies de arquivo JSON
   (`config/betano_cookies.json`), monta headers padrão, expõe `async get(path,
   referer=None)` via `curl_cffi.requests.AsyncSession` com
   `impersonate="chrome131"`.

2. **Cliente StatsStream** — `BetanoStatsStream` com método para cada
   endpoint:
   - `get_info_aggregated(event_id, lang="pt_BR")`
   - `get_config(event_id)`
   - `get_stats_detailed(event_id)`
   - `get_stats_players(event_id)`
   - `get_momentum(event_id)`
   - `get_lineups(event_id)`
   - `get_h2h(event_id)`

3. **Schemas tipados** — dataclasses frozen em `schemas.py`:
   - `MatchInfo`, `MatchLineups`, `MatchConfig`
   - `TeamStats`, `TeamStatsPerHalf`, `DetailedStats`
   - `MomentumPoint`, `Momentum`
   - `LineupPlayer`, `TeamLineup`, `Lineups`
   - `H2HSummary`, `H2HMatch`, `H2H`

4. **Parsers puros** — `parsers.py` com `parse_*(raw_dict) -> Schema`.
   Defensivos: campos faltantes viram `None`, não exception.

5. **Retry e backoff** — em 5xx ou timeout: 3 tentativas com
   `2^attempt + random()` segundos. Em 403: levanta `BetanoBlockedError`
   imediatamente (sinal para warmup na Fase B). Em 401 com login: idem.

6. **Logs estruturados** — chave=valor: `endpoint, event_id, status,
   duration_ms, retries`.

7. **Healthcheck** — `BetanoStatsStream.healthcheck()` chama `get_config`
   para evento fixo conhecido. Retorna bool.

8. **Smoke script** — `scripts/betano_statsstream_smoke.py` que recebe
   `--event-id` e imprime resumo de todos os endpoints.

9. **Testes unit** — pelo menos um por parser, fixtures extraídas do `.mitm`.

10. **Teste de integração** — chama os 4 endpoints principais
    (`info/aggregated`, `stats/detailed`, `momentum`, `lineups`) com cookies
    congelados contra a Betano real, validando status 200 e schema mínimo.

---

## 4. Decisões críticas

### 4.1 Cookies em arquivo JSON, não em código

Cookies expiram. Manter em `config/betano_cookies.json` (gitignored):

```json
{
  "cookies": {
    "cf_clearance": "EXAcnEzOJvoe9zn6D8ibtCU8M...",
    "__cflb": "...",
    "_cfuvid": "...",
    "datadome": "...",
    "sticky_sb": "..."
  },
  "kbversion": "3.41.0",
  "captured_at": "2026-05-12T22:00:00Z"
}
```

`BetanoSession.from_file(path)` carrega. Fase B substitui esse mecanismo por
warmup automatizado.

### 4.2 Headers obrigatórios

```python
HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                  "Version/18.5 Mobile/15E148 Safari/604.1",
    "Sec-Ch-Ua": '"Google Chrome";v="147","Not.A/Brand";v="8","Chromium";v="147"',
    "Sec-Ch-Ua-Mobile": "?1",
    "Sec-Ch-Ua-Platform": '"iOS"',
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}
# x-kbversion adicionado dinamicamente, default "3.41.0"
# Referer: contextual (page do evento ou home)
```

### 4.3 Schema do `stats/detailed` — 35 campos por time × half

Lista completa confirmada na captura:

```python
@dataclass(frozen=True)
class TeamStats:
    goals: int
    total_shots: int
    shots_on_target: int
    shots_off_target: int
    shots_blocked: int
    shots_inside_box: int
    shots_outside_box: int
    throw_ins: int
    corners: int
    offsides: int
    big_chances: int
    big_chances_missed: int
    woodwork: int
    x_goals_live: float
    attacks: int
    dangerous_attacks: int
    fouls: int
    yellow_cards: int
    red_cards: int
    goalkeeper_saves: int
    tackles: int
    interceptions: int
    clearances: int
    aerials_won: int
    duels_won: int
    possession_lost: int
    dribbles: int
    possession: int
    passing_accuracy: int
    passes_attempted: int
    passes_completed: int
    acc_long_balls: int
    acc_crosses: int
```

### 4.4 Schema do `momentum` — pressure score Opta

```python
@dataclass(frozen=True)
class MomentumPoint:
    minute: int
    period: str         # "periodFirstHalf" | "periodSecondHalf" | ...
    pressure: int       # -100 a +100; positivo = casa, negativo = visitante
    home_incidents: list[dict]    # geralmente vazio
    away_incidents: list[dict]
```

### 4.5 `MatchInfo` traz o `kaizen_match_id` (Opta)

```python
@dataclass(frozen=True)
class MatchInfo:
    opta_match_id: str        # "55n9jqpc9lsi0nxt4zpw29ez8"
    sportsbook_id: int        # 84586925 (Betano eventId)
    home_team: str
    home_team_id: str         # ID Opta
    home_team_code: str       # "CRU"
    away_team: str
    away_team_id: str
    away_team_code: str
    coverage_level: str
    date_utc: datetime
    current_period: int
    league_name: str
    kaizen_match_name: str
    started: bool
    supports_pass_coordinates: bool
```

### 4.6 Parsers idempotentes

Cada `parse_*` recebe JSON cru (`dict`), retorna schema. Falha graciosa:
campos opcionais ausentes viram `None`. Apenas campo obrigatório ausente
(ex. `data.match.id`) levanta `BetanoParseError` (custom).

### 4.7 Cliente HTTP reutilizado

Uma `AsyncSession` por instância de `BetanoSession`. Conexões TCP/TLS
reusadas. Fechamento explícito em `close()` async.

### 4.8 Sem cache no provider

Cache fica no caller (Composite na Fase C) ou em `BetanoStatsStreamCached`
decorator separado, **não** dentro deste módulo. Mantém testabilidade.

---

## 5. Componentes novos

### 5.1 `data/providers/betano/__init__.py`

```python
from .session import BetanoSession, BetanoBlockedError, BetanoParseError
from .statsstream import BetanoStatsStream
from .schemas import (
    MatchInfo, MatchConfig, DetailedStats, TeamStats,
    Momentum, MomentumPoint,
    Lineups, TeamLineup, LineupPlayer,
    H2H,
)
__all__ = [...]
```

### 5.2 `data/providers/betano/session.py` (versão mínima — expande na Fase B)

```python
import asyncio
import json
import logging
from pathlib import Path
from curl_cffi.requests import AsyncSession

log = logging.getLogger("cpes.betano.session")


class BetanoBlockedError(Exception):
    """403 ou DataDome bloqueou. Sinaliza necessidade de warmup."""


class BetanoParseError(ValueError):
    """JSON inesperado / campo obrigatório ausente."""


HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                  "Version/18.5 Mobile/15E148 Safari/604.1",
    "Sec-Ch-Ua": '"Google Chrome";v="147","Not.A/Brand";v="8","Chromium";v="147"',
    "Sec-Ch-Ua-Mobile": "?1",
    "Sec-Ch-Ua-Platform": '"iOS"',
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}


class BetanoSession:
    def __init__(
        self,
        cookies: dict[str, str],
        kbversion: str = "3.41.0",
        proxy: str | None = None,
    ):
        self._cookies = cookies
        self._kbversion = kbversion
        self._http = AsyncSession(
            impersonate="chrome131",
            cookies=cookies,
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=15,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "BetanoSession":
        data = json.loads(Path(path).read_text())
        return cls(
            cookies=data["cookies"],
            kbversion=data.get("kbversion", "3.41.0"),
        )

    def _headers(self, referer: str) -> dict:
        return {**HEADERS_BASE, "Referer": referer,
                "x-kbversion": self._kbversion}

    async def get_json(
        self, path: str, referer: str | None = None
    ) -> dict | None:
        """Retorna dict do JSON ou None em falha não-fatal."""
        url = f"https://www.betano.bet.br{path}"
        referer = referer or "https://www.betano.bet.br/"
        for attempt in range(3):
            try:
                r = await self._http.get(url, headers=self._headers(referer))
                log.info("betano.get path=%s status=%d attempt=%d",
                         path, r.status_code, attempt)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (403, 451):
                    raise BetanoBlockedError(
                        f"Blocked {r.status_code} at {path}"
                    )
                if r.status_code in (404, 410):
                    return None
                # 5xx: retry
            except BetanoBlockedError:
                raise
            except Exception as e:
                log.warning("betano.error path=%s err=%s", path, e)
            await asyncio.sleep((2 ** attempt) + 0.3)
        return None

    async def close(self) -> None:
        await self._http.close()
```

### 5.3 `data/providers/betano/statsstream.py`

```python
import logging
from .session import BetanoSession
from .schemas import (
    MatchInfo, MatchConfig, DetailedStats,
    Momentum, Lineups, H2H, PlayerStats,
)
from . import parsers

log = logging.getLogger("cpes.betano.statsstream")


class BetanoStatsStream:
    def __init__(self, session: BetanoSession):
        self._s = session

    def _referer(self, event_id: int) -> str:
        # Path completo seria ".../live/<slug>/<eventId>/"
        # mas a Betano aceita prefixo curto que conhecemos
        return f"https://www.betano.bet.br/live/_/{event_id}/"

    async def get_info_aggregated(
        self, event_id: int, lang: str = "pt_BR"
    ) -> MatchInfo | None:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/info/aggregated/?lang={lang}",
            referer=self._referer(event_id),
        )
        return parsers.parse_info_aggregated(raw) if raw else None

    async def get_config(self, event_id: int) -> MatchConfig | None:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/config/",
            referer=self._referer(event_id),
        )
        return parsers.parse_config(raw) if raw else None

    async def get_stats_detailed(self, event_id: int) -> DetailedStats | None:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/stats/detailed/",
            referer=self._referer(event_id),
        )
        return parsers.parse_stats_detailed(raw) if raw else None

    async def get_stats_players(self, event_id: int) -> PlayerStats | None:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/stats/players/",
            referer=self._referer(event_id),
        )
        return parsers.parse_stats_players(raw) if raw else None

    async def get_momentum(self, event_id: int) -> Momentum | None:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/momentum/",
            referer=self._referer(event_id),
        )
        return parsers.parse_momentum(raw) if raw else None

    async def get_lineups(self, event_id: int) -> Lineups | None:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/lineups/",
            referer=self._referer(event_id),
        )
        return parsers.parse_lineups(raw) if raw else None

    async def get_h2h(self, event_id: int) -> H2H | None:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/h2h/",
            referer=self._referer(event_id),
        )
        return parsers.parse_h2h(raw) if raw else None

    async def healthcheck(self) -> bool:
        # event_id encerrado ou estável de teste
        return await self.get_config(84586925) is not None
```

### 5.4 `data/providers/betano/schemas.py`

Dataclasses frozen, todas com `to_dict()` para serialização. Esqueleto
denso (Claude CLI implementa completo):

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TeamStats:
    goals: int
    total_shots: int
    shots_on_target: int
    shots_off_target: int
    shots_blocked: int
    shots_inside_box: int
    shots_outside_box: int
    throw_ins: int
    corners: int
    offsides: int
    big_chances: int
    big_chances_missed: int
    woodwork: int
    x_goals_live: float
    attacks: int
    dangerous_attacks: int
    fouls: int
    yellow_cards: int
    red_cards: int
    goalkeeper_saves: int
    tackles: int
    interceptions: int
    clearances: int
    aerials_won: int
    duels_won: int
    possession_lost: int
    dribbles: int
    possession: int
    passing_accuracy: int
    passes_attempted: int
    passes_completed: int
    acc_long_balls: int
    acc_crosses: int


@dataclass(frozen=True)
class TeamStatsPerHalf:
    first_half: Optional[TeamStats]
    second_half: Optional[TeamStats]
    extra_time: Optional[TeamStats]
    total: TeamStats


@dataclass(frozen=True)
class DetailedStats:
    event_id: int
    home: TeamStatsPerHalf
    away: TeamStatsPerHalf


@dataclass(frozen=True)
class MatchInfo:
    opta_match_id: str
    sportsbook_id: int
    home_team: str
    home_team_id: str
    home_team_code: str
    home_team_color: Optional[str]
    away_team: str
    away_team_id: str
    away_team_code: str
    away_team_color: Optional[str]
    coverage_level: str
    date_utc: datetime
    current_period: int
    league_name: str
    kaizen_match_name: str
    started: bool
    supports_pass_coordinates: bool


@dataclass(frozen=True)
class MatchConfig:
    provider_type: str   # "Opta"
    momentum_enabled: bool
    disabled_tabs: list[int]
    home_team_color: Optional[str]
    away_team_color: Optional[str]


@dataclass(frozen=True)
class MomentumPoint:
    minute: int
    period: str
    pressure: int
    home_incidents: list[dict] = field(default_factory=list)
    away_incidents: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Momentum:
    event_id: int
    points: list[MomentumPoint]


@dataclass(frozen=True)
class LineupPlayer:
    id: str
    name: str
    number: int
    has_yellow_card: bool
    has_second_yellow_card: bool
    has_red_card: bool
    goals: int
    own_goals: int
    is_substituted: bool
    position: Optional[str] = None


@dataclass(frozen=True)
class TeamLineup:
    id: str
    name: str
    formation: str
    captain_id: str
    coach_name: Optional[str]
    on_pitch: list[list[LineupPlayer]]   # linhas táticas
    substitutes: list[LineupPlayer]


@dataclass(frozen=True)
class Lineups:
    event_id: int
    home: TeamLineup
    away: TeamLineup


@dataclass(frozen=True)
class H2HMatch:
    league_id: int
    league_name: str
    date_utc: datetime
    home_team: str
    away_team: str
    home_score: int
    away_score: int


@dataclass(frozen=True)
class H2HSummary:
    home_wins: int
    home_wins_perc: float
    away_wins: int
    away_wins_perc: float
    draws: int
    draws_perc: float


@dataclass(frozen=True)
class H2H:
    event_id: int
    summary: H2HSummary
    previous_meetings: list[H2HMatch]


@dataclass(frozen=True)
class PlayerStats:
    event_id: int
    raw: dict   # schema completo a refinar conforme uso
```

### 5.5 `data/providers/betano/parsers.py`

```python
import logging
from datetime import datetime, timezone
from .schemas import (
    MatchInfo, MatchConfig, DetailedStats, TeamStats, TeamStatsPerHalf,
    Momentum, MomentumPoint, Lineups, TeamLineup, LineupPlayer,
    H2H, H2HSummary, H2HMatch, PlayerStats,
)
from .session import BetanoParseError

log = logging.getLogger("cpes.betano.parser")


def _safe(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


def parse_info_aggregated(raw: dict) -> MatchInfo:
    m = _safe(raw, "data", "match", default={})
    if not m or "id" not in m:
        raise BetanoParseError("info/aggregated sem data.match.id")
    return MatchInfo(
        opta_match_id=m["id"],
        sportsbook_id=int(m["sportsbook_id"]),
        home_team=m.get("home_team", "?"),
        home_team_id=m.get("home_team_id", ""),
        home_team_code=m.get("home_team_code", ""),
        home_team_color=m.get("home_team_color"),
        away_team=m.get("away_team", "?"),
        away_team_id=m.get("away_team_id", ""),
        away_team_code=m.get("away_team_code", ""),
        away_team_color=m.get("away_team_color"),
        coverage_level=str(m.get("coverage_level", "")),
        date_utc=datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
            if m.get("date") else datetime.now(timezone.utc),
        current_period=int(m.get("current_period", 0)),
        league_name=m.get("league_name", ""),
        kaizen_match_name=m.get("kaizen_match_name", ""),
        started=bool(m.get("started", False)),
        supports_pass_coordinates=bool(m.get("supports_pass_coordinates", False)),
    )


def _parse_team_stats(d: dict) -> TeamStats:
    return TeamStats(
        goals=int(d.get("goals", 0)),
        total_shots=int(d.get("total_shots", 0)),
        shots_on_target=int(d.get("shots_on_target", 0)),
        shots_off_target=int(d.get("shots_off_target", 0)),
        shots_blocked=int(d.get("shots_blocked", 0)),
        shots_inside_box=int(d.get("shots_inside_box", 0)),
        shots_outside_box=int(d.get("shots_outside_box", 0)),
        throw_ins=int(d.get("throw_ins", 0)),
        corners=int(d.get("corners", 0)),
        offsides=int(d.get("offsides", 0)),
        big_chances=int(d.get("big_chances", 0)),
        big_chances_missed=int(d.get("big_chances_missed", 0)),
        woodwork=int(d.get("woodwork", 0)),
        x_goals_live=float(d.get("x_goals_live", 0)),
        attacks=int(d.get("attacks", 0)),
        dangerous_attacks=int(d.get("dangerous_attacks", 0)),
        fouls=int(d.get("fouls", 0)),
        yellow_cards=int(d.get("yellow_cards", 0)),
        red_cards=int(d.get("red_cards", 0)),
        goalkeeper_saves=int(d.get("goalkeeper_saves", 0)),
        tackles=int(d.get("tackles", 0)),
        interceptions=int(d.get("interceptions", 0)),
        clearances=int(d.get("clearances", 0)),
        aerials_won=int(d.get("aerials_won", 0)),
        duels_won=int(d.get("duels_won", 0)),
        possession_lost=int(d.get("possession_lost", 0)),
        dribbles=int(d.get("dribbles", 0)),
        possession=int(d.get("possession", 0)),
        passing_accuracy=int(d.get("passing_accuracy", 0)),
        passes_attempted=int(d.get("passes_attempted", 0)),
        passes_completed=int(d.get("passes_completed", 0)),
        acc_long_balls=int(d.get("acc_long_balls", 0)),
        acc_crosses=int(d.get("acc_crosses", 0)),
    )


def _parse_per_half(d: dict) -> TeamStatsPerHalf:
    return TeamStatsPerHalf(
        first_half=_parse_team_stats(d["first_half"]) if d.get("first_half") else None,
        second_half=_parse_team_stats(d["second_half"]) if d.get("second_half") else None,
        extra_time=_parse_team_stats(d["extra_time"]) if d.get("extra_time") else None,
        total=_parse_team_stats(d["total"]),
    )


def parse_stats_detailed(raw: dict, event_id: int = 0) -> DetailedStats:
    data = raw.get("data", {})
    if "home" not in data or "away" not in data:
        raise BetanoParseError("stats/detailed sem data.home/away")
    return DetailedStats(
        event_id=event_id,
        home=_parse_per_half(data["home"]),
        away=_parse_per_half(data["away"]),
    )


def parse_momentum(raw: dict, event_id: int = 0) -> Momentum:
    points_raw = _safe(raw, "data", "momentum", default=[]) or []
    points = [
        MomentumPoint(
            minute=int(p.get("minute", 0)),
            period=p.get("period", ""),
            pressure=int(p.get("pressure", 0)),
            home_incidents=p.get("homeIncidents", []) or [],
            away_incidents=p.get("awayIncidents", []) or [],
        )
        for p in points_raw
    ]
    return Momentum(event_id=event_id, points=points)


def parse_config(raw: dict) -> MatchConfig:
    data = raw.get("data", {})
    return MatchConfig(
        provider_type=data.get("provider_type", "?"),
        momentum_enabled=bool(data.get("momentum_enabled", False)),
        disabled_tabs=[t.get("id") for t in data.get("disabled_tabs", [])
                        if isinstance(t, dict) and "id" in t],
        home_team_color=_safe(data, "teams", "home_team", "color"),
        away_team_color=_safe(data, "teams", "away_team", "color"),
    )


def parse_lineups(raw: dict, event_id: int = 0) -> Lineups:
    data = raw.get("data", {})
    return Lineups(
        event_id=event_id,
        home=_parse_team_lineup(data.get("home", {})),
        away=_parse_team_lineup(data.get("away", {})),
    )


def _parse_team_lineup(d: dict) -> TeamLineup:
    on_pitch_raw = d.get("on_pitch", [])
    on_pitch = []
    if isinstance(on_pitch_raw, list):
        for row in on_pitch_raw:
            if isinstance(row, list):
                on_pitch.append([_parse_lineup_player(p) for p in row
                                 if isinstance(p, dict)])
            elif isinstance(row, dict):
                # alguns providers retornam flat list
                on_pitch.append([_parse_lineup_player(row)])
    subs = [_parse_lineup_player(p) for p in d.get("substitutes", [])
            if isinstance(p, dict)]
    return TeamLineup(
        id=str(d.get("id", "")),
        name=d.get("name", "?"),
        formation=d.get("formation", ""),
        captain_id=str(d.get("captain_id", "")),
        coach_name=d.get("coach_name"),
        on_pitch=on_pitch,
        substitutes=subs,
    )


def _parse_lineup_player(d: dict) -> LineupPlayer:
    return LineupPlayer(
        id=str(d.get("id", "")),
        name=d.get("name", "?"),
        number=int(d.get("number", 0)),
        has_yellow_card=bool(d.get("has_yellow_card", False)),
        has_second_yellow_card=bool(d.get("has_second_yellow_card", False)),
        has_red_card=bool(d.get("has_red_card", False)),
        goals=int(d.get("goals", 0)),
        own_goals=int(d.get("own_goals", 0)),
        is_substituted=bool(d.get("is_substituted", False)),
        position=d.get("position"),
    )


def parse_h2h(raw: dict, event_id: int = 0) -> H2H:
    data = raw.get("data", {})
    s = data.get("previous_meetings_summary", {})
    matches = []
    for m in data.get("previous_meetings", []) or []:
        try:
            matches.append(H2HMatch(
                league_id=int(m.get("league_id", 0)),
                league_name=m.get("league_name", ""),
                date_utc=datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
                    if m.get("date") else datetime.now(timezone.utc),
                home_team=m.get("home_team", ""),
                away_team=m.get("away_team", ""),
                home_score=int(m.get("home_score", 0)),
                away_score=int(m.get("away_score", 0)),
            ))
        except Exception:
            continue  # skip mal-formado
    return H2H(
        event_id=event_id,
        summary=H2HSummary(
            home_wins=int(s.get("home_wins", 0)),
            home_wins_perc=float(s.get("home_wins_perc", 0)),
            away_wins=int(s.get("away_wins", 0)),
            away_wins_perc=float(s.get("away_wins_perc", 0)),
            draws=int(s.get("draws", 0)),
            draws_perc=float(s.get("draws_perc", 0)),
        ),
        previous_meetings=matches,
    )


def parse_stats_players(raw: dict, event_id: int = 0) -> PlayerStats:
    return PlayerStats(event_id=event_id, raw=raw.get("data", {}))
```

### 5.6 `scripts/betano_statsstream_smoke.py`

```python
"""Smoke fim-a-fim do BetanoStatsStream.

Uso:
    python scripts/betano_statsstream_smoke.py --event-id 84586925 \\
        --cookies config/betano_cookies.json
"""
import argparse
import asyncio
from data.providers.betano import BetanoSession, BetanoStatsStream


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event-id", type=int, required=True)
    ap.add_argument("--cookies", default="config/betano_cookies.json")
    args = ap.parse_args()

    session = BetanoSession.from_file(args.cookies)
    client = BetanoStatsStream(session)

    try:
        info = await client.get_info_aggregated(args.event_id)
        print(f"\n=== info ===")
        if info:
            print(f"  {info.home_team} ({info.home_team_code}) "
                  f"x {info.away_team} ({info.away_team_code})")
            print(f"  Liga: {info.league_name}")
            print(f"  Opta match_id: {info.opta_match_id}")

        cfg = await client.get_config(args.event_id)
        print(f"\n=== config ===")
        if cfg:
            print(f"  Provider: {cfg.provider_type}")
            print(f"  Momentum enabled: {cfg.momentum_enabled}")

        det = await client.get_stats_detailed(args.event_id)
        print(f"\n=== stats detailed (total) ===")
        if det:
            h, a = det.home.total, det.away.total
            print(f"  Corners:   {h.corners} x {a.corners}")
            print(f"  Yellow:    {h.yellow_cards} x {a.yellow_cards}")
            print(f"  Red:       {h.red_cards} x {a.red_cards}")
            print(f"  Shots OnT: {h.shots_on_target} x {a.shots_on_target}")
            print(f"  Dang.Att:  {h.dangerous_attacks} x {a.dangerous_attacks}")
            print(f"  Posse:     {h.possession}% x {a.possession}%")
            print(f"  xG:        {h.x_goals_live:.2f} x {a.x_goals_live:.2f}")

        mom = await client.get_momentum(args.event_id)
        print(f"\n=== momentum ===")
        if mom:
            print(f"  Pontos: {len(mom.points)}")
            for p in mom.points[-5:]:
                print(f"  [{p.minute:3d}'] {p.period:18s} pressure={p.pressure:+4d}")

        lin = await client.get_lineups(args.event_id)
        print(f"\n=== lineups ===")
        if lin:
            print(f"  {lin.home.name} formação {lin.home.formation}")
            print(f"  {lin.away.name} formação {lin.away.formation}")

        h2h = await client.get_h2h(args.event_id)
        print(f"\n=== h2h ===")
        if h2h:
            s = h2h.summary
            print(f"  V {s.home_wins} | E {s.draws} | D {s.away_wins} "
                  f"({len(h2h.previous_meetings)} jogos)")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### 5.7 Extração de fixtures

`scripts/extract_betano_fixtures.py`:

```python
"""Extrai responses do .mitm golden para JSON em
tests/providers/betano/fixtures/."""
from mitmproxy import io
import json
import re
from pathlib import Path

FIXTURES_DIR = Path("tests/providers/betano/fixtures")
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

WANTED = {
    "info/aggregated": "info_aggregated",
    "config/": "config",
    "stats/detailed": "stats_detailed",
    "stats/players": "stats_players",
    "momentum/": "momentum",
    "lineups/": "lineups",
    "h2h/": "h2h",
    "/danae-webapi/api/live/events": "live_event_latest",
    "/danae-webapi/api/live/overview/latest": "live_overview_latest",
}

with open("docs/sprints/captures/2026-05-12-betano-flow.mitm", "rb") as f:
    for flow in io.FlowReader(f).stream():
        if not hasattr(flow, "response") or not flow.response:
            continue
        path = flow.request.path
        for sub, name in WANTED.items():
            if sub not in path:
                continue
            # extrai eventId quando possível
            m = re.search(r"/(\d{6,12})/?", path)
            evid = m.group(1) if m else "unknown"
            fname = FIXTURES_DIR / f"{name}_{evid}.json"
            if fname.exists():
                break
            try:
                data = flow.response.json()
            except Exception:
                break
            with open(fname, "w") as out:
                json.dump(data, out, indent=2, ensure_ascii=False)
            print(f"Wrote {fname}")
            break
```

### 5.8 Testes

`tests/providers/betano/test_parsers.py`:

```python
import json
import pytest
from pathlib import Path
from data.providers.betano import parsers, BetanoParseError

FIXTURES = Path("tests/providers/betano/fixtures")


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_parse_info_aggregated_happy():
    raw = load("info_aggregated_84586925.json")
    info = parsers.parse_info_aggregated(raw)
    assert info.opta_match_id
    assert info.sportsbook_id == 84586925
    assert info.home_team and info.away_team


def test_parse_info_aggregated_missing_id():
    with pytest.raises(BetanoParseError):
        parsers.parse_info_aggregated({"data": {"match": {}}})


def test_parse_stats_detailed_aggregates_corners():
    raw = load("stats_detailed_85539522.json")
    stats = parsers.parse_stats_detailed(raw, event_id=85539522)
    assert stats.home.total.corners >= 0
    assert stats.away.total.corners >= 0


def test_parse_momentum_points_have_pressure():
    raw = load("momentum_85539522.json")
    mom = parsers.parse_momentum(raw)
    assert len(mom.points) > 0
    assert all(isinstance(p.pressure, int) for p in mom.points)


def test_parse_config_extracts_provider_type():
    raw = load("config_85539522.json")
    cfg = parsers.parse_config(raw)
    assert cfg.provider_type == "Opta"
    assert isinstance(cfg.momentum_enabled, bool)


def test_parse_lineups_has_two_teams():
    raw = load("lineups_85539522.json")
    lin = parsers.parse_lineups(raw)
    assert lin.home.name and lin.away.name
    assert lin.home.formation  # ex. "4-3-3"


def test_parse_h2h_summary_sums_to_100():
    raw = load("h2h_85539522.json")
    h2h = parsers.parse_h2h(raw)
    s = h2h.summary
    total = s.home_wins_perc + s.away_wins_perc + s.draws_perc
    assert 99.0 <= total <= 101.0  # tolerância de arredondamento
```

`tests/providers/betano/test_integration.py`:

```python
import os
import pytest
import asyncio
from pathlib import Path
from data.providers.betano import BetanoSession, BetanoStatsStream

pytestmark = pytest.mark.skipif(
    not Path("config/betano_cookies.json").exists(),
    reason="config/betano_cookies.json não encontrado — integração pulada",
)

# Use evento ao vivo conhecido ao rodar; aqui só de Cruzeiro x Goiás
KNOWN_EVENT = int(os.environ.get("BETANO_TEST_EVENT", "84586925"))


@pytest.mark.asyncio
async def test_get_config_real_call():
    s = BetanoSession.from_file("config/betano_cookies.json")
    c = BetanoStatsStream(s)
    try:
        cfg = await c.get_config(KNOWN_EVENT)
        assert cfg is not None
        assert cfg.provider_type in ("Opta", "Sportradar", "?")
    finally:
        await s.close()
```

---

## 6. Edge cases

| Caso | Comportamento |
|---|---|
| Cookies expiraram (403) | `BetanoBlockedError` levantado; caller decide warmup (Fase B) |
| Evento já finalizado | `get_config` retorna 200 com `data: null` ou `momentum` vazio. Parser não quebra |
| Campos opcionais faltando | `None` no schema; parser não quebra |
| JSON inválido (corruption) | `BetanoParseError` ou `json.JSONDecodeError`; log error; retorna None |
| Resposta 404 (evento não existe) | Retorna `None`; log info |
| Rate limit transitório (429) | Retry com backoff (não documentado mas plausível) |
| `momentum_enabled: false` no config | `get_momentum` ainda funciona retornando lista vazia |
| Lineup `on_pitch` plat (não nested) | Parser detecta e wrappa numa lista de uma linha |
| Acentuação (UTF-8) | `ensure_ascii=False` nos fixtures; respostas devem decodificar normalmente |

---

## 7. Acceptance

- [ ] Estrutura de diretórios criada
- [ ] `BetanoSession` carrega cookies de JSON e faz GET autenticado
- [ ] `BetanoStatsStream` com 7 métodos implementados
- [ ] Schemas dataclasses frozen completos (sem `Any` salvo `raw` de
      `PlayerStats`)
- [ ] Parsers cobrem todos os 7 endpoints
- [ ] Retry/backoff: 3 tentativas com `2^attempt + jitter`
- [ ] 403/451 levantam `BetanoBlockedError` (não tentam de novo)
- [ ] Logs estruturados (chave=valor)
- [ ] Fixtures extraídas do `.mitm` em `tests/providers/betano/fixtures/`
- [ ] Suite de testes unit roda verde (`pytest tests/providers/betano/test_parsers.py`)
- [ ] Suite de testes integração roda verde com cookies reais
- [ ] Smoke script imprime resumo de todos os endpoints sem erro
- [ ] `data/providers/betano/` não importa nada de `data/api_client.py`
- [ ] Documentação inline + atualização `sistema-completo.md` §22

---

## 8. Pilares cobertos

| Pilar | Contribuição |
|---|---|
| **Multi-fonte** | Opta entra como primary; API-Football fallback |
| **Determinismo** | Parsers puros; schemas frozen; fixtures golden |
| **Observabilidade** | Logs por chamada; healthcheck endpoint |
| **Custo** | Endpoints leves (~5KB) vs 281KB do markets/latest |
| **Latência** | Stats em ~50-200ms na captura |

---

## 9. Esforço estimado

| Sub-task | Horas |
|---|---|
| Setup do diretório + `__init__.py` + extract_fixtures.py | 0.5 |
| `session.py` mínimo (cookies, GET, retry) | 1.0 |
| `schemas.py` (10 dataclasses) | 1.0 |
| `parsers.py` (7 funções) | 2.0 |
| `statsstream.py` (7 wrappers) | 1.0 |
| Testes unit (8 testes) | 1.5 |
| Testes integração (3 testes) | 0.5 |
| Smoke script | 0.5 |
| Healthcheck + logs | 0.5 |
| Buffer (ajustes parsers vs JSON real) | 1.5 |
| **Total** | **10h** |

---

## 10. Bloqueios potenciais

| Bloqueio | Resolução |
|---|---|
| Cookies do `.mitm` expiraram quando rodar testes integração | Re-capturar via Fase B (warmup) ou pedir Daniel pra exportar novos do Chrome |
| Schema do JSON real diferente em campo específico | Inspecionar fixture; ajustar parser; cobertura defensiva já mitiga |
| `curl_cffi` não instala (libcurl mismatch) | Fallback `httpx` (Betano REST é menos rígido em JA3) |

---

## 11. Out of scope

- ❌ Mapping `fixture_id → event_id` (Fase B)
- ❌ Markets/odds (Fase B)
- ❌ WebSocket (Fase B)
- ❌ Integração no `main.py:796` (Fase C)
- ❌ Persistência de stats em DB (Fase D)
- ❌ Warmup browser (Fase B; aqui só cookies congelados)
