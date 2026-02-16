"""
CPES Data Reader - Funções puras para leitura de dados.
Usado por monitor.py (terminal) e api_server.py (API web).
"""

import json
import os
import sqlite3
import time
from datetime import datetime

from config import API_DAILY_LIMIT, DB_PATH


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


def get_db_stats() -> dict:
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return {"total": 0, "greens": 0, "reds": 0, "pendentes": 0, "winrate": 0.0, "roi_total": 0.0}

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM sinais")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sinais WHERE resultado = 'GREEN'")
        greens = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sinais WHERE resultado = 'RED'")
        reds = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(roi), 0) FROM sinais WHERE roi IS NOT NULL")
        roi_total = cur.fetchone()[0]

        conn.close()

        pendentes = total - greens - reds
        winrate = (greens / (greens + reds) * 100) if (greens + reds) > 0 else 0

        return {
            "total": total,
            "greens": greens,
            "reds": reds,
            "pendentes": pendentes,
            "winrate": round(winrate, 1),
            "roi_total": round(roi_total, 2),
        }
    except Exception:
        return {"total": 0, "greens": 0, "reds": 0, "pendentes": 0, "winrate": 0.0, "roi_total": 0.0}


def get_recent_signals(limit: int = 5) -> list:
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return []

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT timestamp, jogo_descricao, tipo_sinal, pressure_score, "
            "projecao, edge, linha, odd, resultado, escanteios_final FROM sinais "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
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


LIVE_STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "live_state.json")
UPCOMING_GAMES_PATH = os.path.join(os.path.dirname(__file__), "data", "upcoming_games.json")
AUDIT_STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "audit_state.json")


def get_live_state() -> dict:
    """Retorna estado dos jogos ao vivo (por fase, analisados, observados)."""
    try:
        if os.path.exists(LIVE_STATE_PATH):
            with open(LIVE_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
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


def get_upcoming_games() -> dict:
    """Retorna próximos jogos programados com minutos_ate recalculado em tempo real."""
    try:
        if os.path.exists(UPCOMING_GAMES_PATH):
            with open(UPCOMING_GAMES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            now = time.time()
            proximos = []
            for game in data.get("proximos", []):
                ts = game.get("timestamp", 0)
                if not ts:
                    continue
                # Pula jogos ja terminados (estimativa 105 min = 6300 seg)
                if ts + 6300 < now:
                    continue
                # Recalcula minutos_ate em tempo real
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


def get_audit_state() -> dict:
    """Retorna dados de auditoria do último ciclo de análise."""
    try:
        if os.path.exists(AUDIT_STATE_PATH):
            with open(AUDIT_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "atualizado": None,
        "ciclo": 0,
        "funil": {
            "total_analisados": 0,
            "passou_filtros": 0,
            "score_ok": 0,
            "edge_ok": 0,
            "sinais_emitidos": 0,
            "premium": 0,
            "normal": 0,
        },
        "filtros_breakdown": {},
        "jogos": [],
        "taxas": {
            "elegibilidade": 0,
            "conversao_score": 0,
            "conversao_edge": 0,
            "hit_rate": 0,
        },
    }


def get_signals_history(days: int = 7) -> list:
    """Retorna contagem de sinais por dia nos últimos N dias."""
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return []

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                date(timestamp) as dia,
                COUNT(*) as total,
                SUM(CASE WHEN tipo_sinal = 'PREMIUM' THEN 1 ELSE 0 END) as premium,
                SUM(CASE WHEN tipo_sinal = 'NORMAL' THEN 1 ELSE 0 END) as normal,
                SUM(CASE WHEN resultado = 'GREEN' THEN 1 ELSE 0 END) as greens,
                SUM(CASE WHEN resultado = 'RED' THEN 1 ELSE 0 END) as reds,
                COALESCE(SUM(roi), 0) as roi
            FROM sinais
            WHERE timestamp >= date('now', ?)
            GROUP BY date(timestamp)
            ORDER BY dia DESC
            """,
            (f"-{days} days",),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "dia": r[0],
                "total": r[1],
                "premium": r[2],
                "normal": r[3],
                "greens": r[4],
                "reds": r[5],
                "roi": round(r[6], 2),
            }
            for r in rows
        ]
    except Exception:
        return []
