#!/usr/bin/env python3
"""Debug: Testar seasons diferentes"""

import asyncio
import aiohttp
import os
import sys

sys.path.insert(0, "/home/daniel/cornerpressureelite/corner-pressure-elite")
from config import API_FOOTBALL_KEY

BASE_URL = "https://v3.football.api-sports.io"

async def test_seasons():
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    date = "2026-02-15"
    
    ligas = [
        (39, "Premier League"),
        (135, "Serie A"),
        (128, "Argentina"),
    ]
    
    async with aiohttp.ClientSession(headers=headers) as session:
        print("\n" + "=" * 80)
        print("TESTE: Seasons 2024 vs 2025 vs 2026")
        print("=" * 80)
        
        for liga_id, liga_nome in ligas:
            print(f"\n{liga_nome} (Liga {liga_id}):")
            print("-" * 40)
            
            for season in [2024, 2025, 2026]:
                async with session.get(f"{BASE_URL}/fixtures", params={"date": date, "league": liga_id, "season": season}) as resp:
                    data = await resp.json()
                    fixtures = len(data.get("response", []))
                    
                    print(f"  Season {season}: {fixtures} jogos")

if __name__ == "__main__":
    asyncio.run(test_seasons())
