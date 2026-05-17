"""Extrai linhas Over/Under de markets do payload /event/<id>/state.

Substitui o DOM scraping da rota legada /live/_/<id>/ (nuked por anti-bot
Cloudflare em 2026-05-17). O endpoint /event/<id>/state proxia o JSON
nativo /danae-webapi/api/live/events/<id>/latest, que contém TODOS os
markets de corners + cards em jogos com cobertura completa.

Descoberta: captura HAR 2026-05-17 (Real Sociedad x Valencia, La Liga)
mostrou 41 markets de escanteios + 28 de cartões num mesmo payload.

Schema source:
    {
      "data": {
        "markets": {
          "2761961170": {
            "id": 2761961170,
            "type": "CNOU",
            "name": "Escanteios Mais/Menos",
            "handicap": 6.5,
            "selectionIdList": [9611174726, 9611174727],
            ...
          },
          ...
        },
        "selections": {
          "9611174726": {
            "id": 9611174726, "price": 1.78, "name": "Mais de 6.5", ...
          },
          ...
        },
        "event": {...}, "version": ..., ...
      },
      "version": ..., "captured_at": ..., ...
    }

Output: lista compatível com `BetanoBridgeClient.markets()` legado:
    [{"line": 6.5, "over_price": 1.78, "under_price": 1.93}, ...]
"""
from __future__ import annotations

from typing import Any, Optional

# Type codes Danae → categoria. Mantém só Over/Under tradicionais (2 selections,
# 1 handicap). COF3 (3 selections — Under/Exact/Over) e Asian (1000617/618)
# ficam de fora — schema diferente, baixo valor pro CPES atual.
CORNER_TYPES = {
    "CNOU",  # Corners Over/Under (linha .5)
    "COU1",  # Corners Over/Under 1° Tempo
    "COU2",  # Corners Over/Under 2° Tempo (especulativo, espelho do COU1)
}
CARD_TYPES = {
    "TCOU",  # Total Cards Over/Under
    "1COU",  # Total Cards Over/Under 1° Tempo
    "2COU",  # Total Cards Over/Under 2° Tempo (especulativo)
}


def _select_types(market_kind: str) -> set[str]:
    if market_kind == "corners" or market_kind == "corners_over_under":
        return CORNER_TYPES
    if market_kind == "cards" or market_kind == "cards_over_under":
        return CARD_TYPES
    return set()


def _payload_root(state_response: dict) -> dict:
    """Aceita resposta do bridge (com wrapper {data: ...}) ou payload Danae cru."""
    if isinstance(state_response.get("data"), dict) and "markets" in state_response["data"]:
        return state_response["data"]
    return state_response


def _is_over_selection(sel: dict) -> bool:
    """Detecta qual selection é 'Mais de' (over) — Danae não garante ordem."""
    name = (sel.get("name") or "").lower()
    return "mais" in name or "over" in name


def extract_lines(state_response: dict, market_kind: str) -> list[dict]:
    """Filtra markets do payload por categoria + extrai (line, over, under).

    Retorna lista ordenada por linha ASC. Markets com schema fora do esperado
    (sem handicap, selections ausentes, prices inválidos) são silenciosamente
    pulados — convenção do parser legado.
    """
    types = _select_types(market_kind)
    if not types:
        return []

    root = _payload_root(state_response)
    markets = root.get("markets") or {}
    selections = root.get("selections") or {}

    lines: list[dict] = []
    seen_handicaps: set[float] = set()

    for market in markets.values():
        if not isinstance(market, dict) or market.get("type") not in types:
            continue
        handicap = market.get("handicap")
        sel_ids = market.get("selectionIdList") or []
        if handicap is None or len(sel_ids) != 2:
            continue
        sel_a = selections.get(str(sel_ids[0])) or selections.get(sel_ids[0])
        sel_b = selections.get(str(sel_ids[1])) or selections.get(sel_ids[1])
        if not (isinstance(sel_a, dict) and isinstance(sel_b, dict)):
            continue

        s_over, s_under = (sel_a, sel_b) if _is_over_selection(sel_a) else (sel_b, sel_a)

        try:
            line = float(handicap)
            over_price = float(s_over["price"])
            under_price = float(s_under["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if line <= 0 or over_price <= 0 or under_price <= 0:
            continue

        # Dedup por handicap (mesma linha pode aparecer 2x com type diferente).
        # Mantém primeiro visto.
        if line in seen_handicaps:
            continue
        seen_handicaps.add(line)

        lines.append({
            "line": line,
            "over_price": over_price,
            "under_price": under_price,
        })

    lines.sort(key=lambda l: l["line"])
    return lines


def has_coverage(state_response: dict, market_kind: str) -> bool:
    """True se há ≥1 market do tipo no payload (cobertura existe pra essa liga)."""
    return len(extract_lines(state_response, market_kind)) > 0
