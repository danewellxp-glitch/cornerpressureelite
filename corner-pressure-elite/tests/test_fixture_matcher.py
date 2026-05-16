"""Unit tests do FixtureMatcher.

Estratégia: mock do BetanoTeamMapRepo, fixtures candidate inline.
Sem rapidfuzz mocked — usa o real (lib pura, sem IO).
"""
from __future__ import annotations

from typing import Optional, Sequence

import pytest

from data.discovery.fixture_matcher import (
    FixtureMatcher,
    MatchResult,
    _normalize_team_name,
    _pick_home,
    _pick_away,
)
from data.repositories.betano_team_map import BetanoTeamEntry


# ============================================================
# Mock repo
# ============================================================


class _FakeTeamRepo:
    def __init__(self):
        self.by_betano: dict[int, BetanoTeamEntry] = {}
        self.upserts: list[BetanoTeamEntry] = []

    async def get_by_betano_id(self, betano_team_id: int) -> Optional[BetanoTeamEntry]:
        return self.by_betano.get(int(betano_team_id))

    async def get_by_api_football_id(self, af_id: int) -> Optional[BetanoTeamEntry]:
        for e in self.by_betano.values():
            if e.api_football_team_id == af_id:
                return e
        return None

    async def bulk_upsert(self, entries: Sequence[BetanoTeamEntry]) -> int:
        for e in entries:
            self.upserts.append(e)
            self.by_betano[e.betano_team_id] = e  # simula persistência
        return len(entries)

    async def find_by_fuzzy_name(self, name: str, threshold: float = 0.85, limit: int = 3):
        return []


# ============================================================
# Fixtures de exemplo
# ============================================================


def _make_betano_event(
    event_id: str = "84842530",
    home_team_id: int = 2050542,
    home_name: str = "Bay FC (F)",
    away_team_id: int = 2096271,
    away_name: str = "Boston Legacy (F)",
    start_time_ms: int = 1778896800000,
):
    return {
        "event_id": event_id,
        "name": f"{home_name} vs {away_name}",
        "participants": [
            {"name": home_name, "is_home": True, "team_id": home_team_id},
            {"name": away_name, "is_home": None, "team_id": away_team_id},
        ],
        "sport_id": "FOOT",
        "league_id": 18207,
        "league_name": "National Soccer League (F)",
        "zone_id": 11387,
        "zone_name": "EUA",
        "start_time_ms": start_time_ms,
        "url": "/live/bay-fc-f-boston-legacy-f/84842530/",
        "is_outright": False,
        "total_markets": 33,
    }


def _make_af_fixture(
    fixture_id: int,
    home_id: int,
    home_name: str,
    away_id: int,
    away_name: str,
    date_iso: str = "2026-05-16T02:00:00+00:00",
    league_id: int = 12345,
):
    return {
        "fixture": {"id": fixture_id, "date": date_iso},
        "teams": {
            "home": {"id": home_id, "name": home_name},
            "away": {"id": away_id, "name": away_name},
        },
        "league": {"id": league_id, "name": "NWSL"},
    }


# ============================================================
# match_event — caminho determinístico (team_id_lookup)
# ============================================================


@pytest.mark.asyncio
async def test_match_via_team_id_lookup_success():
    """Times já mapeados → match determinístico, confidence=1.0."""
    repo = _FakeTeamRepo()
    repo.by_betano[2050542] = BetanoTeamEntry(
        betano_team_id=2050542, betano_team_name="Bay FC (F)",
        api_football_team_id=4001, api_football_team_name="Bay FC",
        match_method="fuzzy", match_confidence=0.91,
    )
    repo.by_betano[2096271] = BetanoTeamEntry(
        betano_team_id=2096271, betano_team_name="Boston Legacy (F)",
        api_football_team_id=4002, api_football_team_name="Boston Legacy",
        match_method="fuzzy", match_confidence=0.93,
    )

    fixtures = [_make_af_fixture(
        fixture_id=999001, home_id=4001, home_name="Bay FC",
        away_id=4002, away_name="Boston Legacy",
    )]

    matcher = FixtureMatcher(repo, confidence_threshold=0.85)
    result = await matcher.match_event(_make_betano_event(), fixtures)

    assert result is not None
    assert result.fixture_id == 999001
    assert result.betano_event_id == 84842530
    assert result.confidence == 1.0
    assert result.method == "team_id_lookup"
    assert result.home_team == "Bay FC"
    assert result.away_team == "Boston Legacy"
    # Não fez upsert no path determinístico
    assert repo.upserts == []


# ============================================================
# match_event — fuzzy fallback
# ============================================================


@pytest.mark.asyncio
async def test_match_fallback_to_fuzzy_when_team_not_mapped():
    """Times sem map → fuzzy bate por nome, UPSERT cria entries."""
    repo = _FakeTeamRepo()  # vazio
    fixtures = [_make_af_fixture(
        fixture_id=999002, home_id=5001, home_name="Bay FC",
        away_id=5002, away_name="Boston Legacy",
    )]

    matcher = FixtureMatcher(repo, confidence_threshold=0.85)
    result = await matcher.match_event(_make_betano_event(), fixtures)

    assert result is not None
    assert result.fixture_id == 999002
    assert result.method == "fuzzy"
    assert result.confidence >= 0.85
    assert result.confidence <= 1.0

    # UPSERTou os 2 teams
    assert len(repo.upserts) == 2
    upsert_betano_ids = {e.betano_team_id for e in repo.upserts}
    assert upsert_betano_ids == {2050542, 2096271}
    for e in repo.upserts:
        assert e.match_method == "fuzzy"
        assert e.api_football_team_id in {5001, 5002}


# ============================================================
# match_event — abaixo do threshold
# ============================================================


@pytest.mark.asyncio
async def test_match_returns_none_below_threshold():
    """Nomes muito diferentes → None, não UPSERTa nada."""
    repo = _FakeTeamRepo()
    fixtures = [_make_af_fixture(
        fixture_id=999003,
        home_id=6001, home_name="Real Madrid",
        away_id=6002, away_name="Barcelona",
    )]
    matcher = FixtureMatcher(repo, confidence_threshold=0.85)
    result = await matcher.match_event(_make_betano_event(), fixtures)

    assert result is None
    assert repo.upserts == []


# ============================================================
# match_event — kickoff window
# ============================================================


@pytest.mark.asyncio
async def test_match_validates_kickoff_within_window():
    """Fixture com kickoff fora da janela ±30min é descartado."""
    repo = _FakeTeamRepo()
    repo.by_betano[2050542] = BetanoTeamEntry(
        betano_team_id=2050542, betano_team_name="Bay FC (F)",
        api_football_team_id=7001, api_football_team_name="Bay FC",
    )
    repo.by_betano[2096271] = BetanoTeamEntry(
        betano_team_id=2096271, betano_team_name="Boston Legacy (F)",
        api_football_team_id=7002, api_football_team_name="Boston Legacy",
    )

    # Fixture com kickoff 3h depois (fora da janela de 30min; Betano é 02:00 UTC)
    fixtures = [_make_af_fixture(
        fixture_id=999004, home_id=7001, home_name="Bay FC",
        away_id=7002, away_name="Boston Legacy",
        date_iso="2026-05-16T05:00:00+00:00",
    )]

    matcher = FixtureMatcher(repo, confidence_threshold=0.85)
    result = await matcher.match_event(_make_betano_event(), fixtures, tolerance_minutes=30)

    assert result is None


@pytest.mark.asyncio
async def test_match_accepts_kickoff_within_window():
    """Fixture com kickoff dentro da janela é aceito."""
    repo = _FakeTeamRepo()
    repo.by_betano[2050542] = BetanoTeamEntry(
        betano_team_id=2050542, betano_team_name="Bay FC (F)",
        api_football_team_id=7001, api_football_team_name="Bay FC",
    )
    repo.by_betano[2096271] = BetanoTeamEntry(
        betano_team_id=2096271, betano_team_name="Boston Legacy (F)",
        api_football_team_id=7002, api_football_team_name="Boston Legacy",
    )
    # 10min de diferença (Betano é 02:00 UTC)
    fixtures = [_make_af_fixture(
        fixture_id=999005, home_id=7001, home_name="Bay FC",
        away_id=7002, away_name="Boston Legacy",
        date_iso="2026-05-16T02:10:00+00:00",
    )]

    matcher = FixtureMatcher(repo, confidence_threshold=0.85)
    result = await matcher.match_event(_make_betano_event(), fixtures, tolerance_minutes=30)

    assert result is not None
    assert result.fixture_id == 999005


# ============================================================
# match_event — formato de input
# ============================================================


@pytest.mark.asyncio
async def test_match_handles_event_without_2_participants():
    """Outright/torneio (1 participant ou 3+) → None gracioso."""
    repo = _FakeTeamRepo()
    fixtures = [_make_af_fixture(999006, 1, "X", 2, "Y")]

    matcher = FixtureMatcher(repo)
    # Caso 1: lista vazia
    event = _make_betano_event()
    event["participants"] = []
    assert await matcher.match_event(event, fixtures) is None

    # Caso 2: só 1 participant
    event["participants"] = [{"name": "X", "is_home": True, "team_id": 1}]
    assert await matcher.match_event(event, fixtures) is None


# ============================================================
# helpers — testes de unidade
# ============================================================


def test_normalize_team_name_removes_noise():
    assert _normalize_team_name("Bay FC (F)") == "bay"
    assert _normalize_team_name("Real Madrid CF") == "real madrid"
    assert _normalize_team_name("São Paulo FC") == "sao paulo"
    assert _normalize_team_name("Liverpool (cl1vlind) (Esports)") == "liverpool (cl1vlind)"


def test_pick_home_prefers_is_home_true():
    parts = [
        {"name": "A", "is_home": None, "team_id": 1},
        {"name": "B", "is_home": True, "team_id": 2},
    ]
    assert _pick_home(parts)["name"] == "B"


def test_pick_home_falls_back_to_first_when_no_is_home():
    parts = [
        {"name": "A", "is_home": None, "team_id": 1},
        {"name": "B", "is_home": None, "team_id": 2},
    ]
    assert _pick_home(parts)["name"] == "A"


def test_pick_away_returns_other_participant():
    parts = [
        {"name": "A", "is_home": True, "team_id": 1},
        {"name": "B", "is_home": None, "team_id": 2},
    ]
    home = _pick_home(parts)
    assert _pick_away(parts, home)["name"] == "B"
