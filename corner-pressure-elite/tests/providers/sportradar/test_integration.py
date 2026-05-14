"""Testes de integração contra a CDN real da Sportradar.

Skipped por default — habilitam-se quando `SPORTRADAR_TOKEN` está no
ambiente. O token tem TTL ~2h (master §3.2); ver Fase A §2 do harness
para o fluxo de captura manual via DevTools.

Harness Fase A §8.2.
"""
import os

import pytest

from data.providers.sportradar import SportradarClient, SportradarSession

# matchId estável (jogo encerrado, payload imutável). Origem: master §4.
KNOWN_MATCH = "70401284"

pytestmark = pytest.mark.skipif(
    not os.environ.get("SPORTRADAR_TOKEN"),
    reason="SPORTRADAR_TOKEN env var não definida — integração pulada",
)


@pytest.fixture
async def client():
    session = SportradarSession()
    session.set_token(os.environ["SPORTRADAR_TOKEN"])
    c = SportradarClient(session)
    try:
        yield c
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_match_info_real_call(client):
    info = await client.match_info(KNOWN_MATCH)
    assert info is not None
    assert info.match_id == KNOWN_MATCH
    assert info.home_team_name != "?"
    assert info.away_team_name != "?"


@pytest.mark.asyncio
async def test_timeline_delta_real_call_returns_events(client):
    delta = await client.get_timeline_delta(KNOWN_MATCH)
    assert delta is not None
    assert delta.match_id == KNOWN_MATCH
    # Jogo encerrado deve ter eventos (corners, cards, goals)
    assert len(delta.events) > 0


@pytest.mark.asyncio
async def test_situation_real_call(client):
    sit = await client.stats_match_situation(KNOWN_MATCH)
    assert sit is not None
    assert sit.match_id == KNOWN_MATCH


@pytest.mark.asyncio
async def test_details_extended_real_call_has_corners(client):
    ext = await client.match_details_extended(KNOWN_MATCH)
    assert ext is not None
    # Jogo encerrado: pelo menos 1 escanteio na soma
    assert (ext.corners_home + ext.corners_away) >= 1


@pytest.mark.asyncio
async def test_healthcheck_real_call():
    session = SportradarSession()
    session.set_token(os.environ["SPORTRADAR_TOKEN"])
    async with SportradarClient(session) as c:
        assert await c.healthcheck() is True
