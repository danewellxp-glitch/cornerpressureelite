"""
CPES Data Reader - Funções puras para leitura de dados.
Usado pela API web. Agora busca os estados JSON da tabela app_state.
"""

import json
import os
import asyncio
from datetime import datetime

from storage.database import Database
from config import API_DAILY_LIMIT


# Inicializa a conexão DB_READER para ser usada de forma assíncrona
db_reader = Database()


def get_log_file():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    today = datetime.now().strftime("%Y%m%d")
    return os.path.join(log_dir, f"cpes_{today}.log")


def read_last_lines(filepath: str, n: int = 20) -> list:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return lines[-n:] if len(lines) > n else lines
    except FileNotFoundError:
        return ["[Log nao encontrado]\n"]


async def get_db_stats(tipo_analise: str = None) -> dict:
    return await db_reader.get_estatisticas(tipo_analise)


async def get_recent_signals(limit: int = 5, tipo_analise: str = None) -> list:
    """Retorna sinais recentes."""
    try:
        await db_reader.connect()
        async with db_reader.pool.acquire() as conn:
            query = """
                SELECT timestamp, jogo_descricao, tipo_sinal, pressure_score, 
                projecao, edge, linha, odd, resultado, escanteios_final, tipo_analise 
                FROM sinais 
                WHERE id IN (
                    SELECT MAX(id) FROM sinais
            """
            params = []
            
            if tipo_analise:
                query += " WHERE tipo_analise = $1"
                params.append(tipo_analise)
                
            query += " GROUP BY jogo_id) ORDER BY id DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    except Exception as e:
        return []


def parse_log_for_status(lines: list) -> dict:
    """Extrai informações de status das linhas de log."""
    info = {
        "ciclo": "?",
        "jogos_ao_vivo": 0,
        "jogos_na_janela": 0,
        "api_usado": "?",
        "api_limite": str(API_DAILY_LIMIT),
        "ultimo_update": "?",
        "status_msg": "",
    }

    for line in reversed(lines):
        line = line.strip()

        if "Ciclo #" in line and info["ciclo"] == "?":
            try:
                info["ciclo"] = line.split("Ciclo #")[1].split(" ")[0].strip("-").strip()
            except (IndexError, ValueError):
                pass

        if "Encontrados" in line and "jogos ao vivo" in line and info["jogos_ao_vivo"] == 0:
            try:
                info["jogos_ao_vivo"] = int(line.split("Encontrados")[1].split("jogos")[0].strip())
            except (IndexError, ValueError):
                pass

        if "jogos na janela" in line and info["jogos_na_janela"] == 0:
            try:
                n = line.split("jogos na janela")[0].strip().split("|")[-1].strip()
                info["jogos_na_janela"] = int(n.split()[-1]) if n else 0
            except (IndexError, ValueError):
                pass

        if "API Status" in line and info["api_usado"] == "?":
            try:
                parts = line.split("Usado:")[1].strip()
                usado, limite = parts.split("/")
                info["api_usado"] = usado.strip()
                info["api_limite"] = limite.strip()
            except (IndexError, ValueError):
                pass

        if "Nenhum jogo na janela" in line and info["status_msg"] == "":
            info["status_msg"] = "Aguardando jogos na janela..."

        if "Nenhum jogo ao vivo" in line and info["status_msg"] == "":
            info["status_msg"] = "Sem jogos ao vivo"

        if info["ultimo_update"] == "?" and "|" in line:
            try:
                info["ultimo_update"] = line.split("|")[0].strip()
            except (IndexError, ValueError):
                pass

    return info


async def get_live_state() -> dict:
    """Retorna estado dos jogos ao vivo lendo do PostgreSQL."""
    try:
        state = await db_reader.get_state("live_state")
        if state: return state
    except Exception:
        pass
    return {
        "atualizado": None,
        "ciclo": 0,
        "pre_janela": [],
        "na_janela": [],
        "pos_janela": [],
        "ids_observados": [],
    }

async def get_upcoming_games() -> dict:
    """Retorna próximos jogos programados lendo do PostgreSQL."""
    try:
        data = await db_reader.get_state("upcoming_games")
        import time
        if data:
            now = time.time()
            proximos = []
            for game in data.get("proximos", []):
                ts = game.get("timestamp", 0)
                if not ts: continue
                if ts + 6300 < now: continue
                game["minutos_ate"] = max(0, int((ts - now) / 60))
                proximos.append(game)
            return {
                "atualizado": datetime.now().isoformat(),
                "proximos": proximos,
            }
    except Exception:
        pass
    return {
        "atualizado": None,
        "proximos": [],
    }


async def get_audit_state() -> dict:
    """Retorna dados de auditoria do último ciclo de análise."""
    try:
        state = await db_reader.get_state("audit_state")
        if state: return state
    except Exception:
        pass
    return {
        "atualizado": None,
        "ciclo": 0,
        "funil": {
            "total_analisados": 0,
            "passou_filtros": 0,
            "score_ok": 0, "edge_ok": 0,
            "sinais_emitidos": 0, "premium": 0, "normal": 0,
        },
        "filtros_breakdown": {},
        "jogos": [],
        "taxas": {
            "elegibilidade": 0, "conversao_score": 0,
            "conversao_edge": 0, "hit_rate": 0,
        },
    }

async def get_signals_history(days: int = 7, tipo_analise: str = None) -> list:
    """Retorna contagem de sinais por dia nos últimos N dias."""
    try:
        await db_reader.connect()
        async with db_reader.pool.acquire() as conn:
            where_clause = "WHERE timestamp >= NOW() - INTERVAL '" + str(days) + " days'"
            params = []
            
            if tipo_analise:
                where_clause += " AND tipo_analise = $1"
                params.append(tipo_analise)
                
            query = f"""
                SELECT
                    DATE(timestamp) as dia,
                    COUNT(*) as total,
                    SUM(CASE WHEN tipo_sinal = 'PREMIUM' THEN 1 ELSE 0 END) as premium,
                    SUM(CASE WHEN tipo_sinal = 'NORMAL' THEN 1 ELSE 0 END) as normal,
                    SUM(CASE WHEN resultado = 'GREEN' THEN 1 ELSE 0 END) as greens,
                    SUM(CASE WHEN resultado = 'RED' THEN 1 ELSE 0 END) as reds,
                    COALESCE(SUM(roi), 0) as roi
                FROM sinais
                {where_clause}
                GROUP BY DATE(timestamp)
                ORDER BY dia DESC
            """
            
            rows = await conn.fetch(query, *params)
            return [
                {
                    "dia": str(r["dia"]),
                    "total": r["total"],
                    "premium": r["premium"],
                    "normal": r["normal"],
                    "greens": r["greens"],
                    "reds": r["reds"],
                    "roi": round(r["roi"], 2),
                }
                for r in rows
            ]
    except Exception:
        return []
