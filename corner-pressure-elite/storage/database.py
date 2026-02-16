import aiosqlite
import logging
from typing import Optional, List, Dict
from datetime import datetime

from data.models import Sinal, RegistroSinal, JogoAoVivo
from config import DB_PATH

logger = logging.getLogger("CPES.Database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sinais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    liga_id INTEGER NOT NULL,
    liga_nome VARCHAR(100),
    jogo_id INTEGER NOT NULL,
    jogo_descricao VARCHAR(200),
    minuto INTEGER NOT NULL,
    placar VARCHAR(10),
    escanteios_total INTEGER NOT NULL,
    linha DECIMAL(3,1) NOT NULL,
    odd DECIMAL(4,2) NOT NULL,
    projecao DECIMAL(4,2) NOT NULL,
    edge DECIMAL(3,2) NOT NULL,
    pressure_score INTEGER NOT NULL,
    tipo_sinal VARCHAR(20) NOT NULL,
    reavaliacao BOOLEAN DEFAULT FALSE,
    resultado VARCHAR(10),
    escanteios_final INTEGER,
    roi DECIMAL(5,2)
);

CREATE TABLE IF NOT EXISTS detalhes_jogo (
    sinal_id INTEGER,
    ataques_perigosos INTEGER,
    finalizacoes INTEGER,
    posse_time_casa INTEGER,
    posse_time_fora INTEGER,
    escanteios_time_casa INTEGER,
    escanteios_time_fora INTEGER,
    media_historica DECIMAL(4,2),
    FOREIGN KEY (sinal_id) REFERENCES sinais(id)
);

CREATE TABLE IF NOT EXISTS ligas_config (
    liga_id INTEGER PRIMARY KEY,
    ativa BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS thresholds_config (
    chave VARCHAR(50) PRIMARY KEY,
    valor DECIMAL(10,2) NOT NULL,
    descricao VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    fixture_id INTEGER NOT NULL,
    liga_id INTEGER,
    liga_nome TEXT,
    time_casa TEXT,
    time_fora TEXT,
    minuto INTEGER,
    placar_casa INTEGER,
    placar_fora INTEGER,
    escanteios_total INTEGER,
    escanteios_casa INTEGER,
    escanteios_fora INTEGER,
    escanteios_ultimos_10min INTEGER DEFAULT 0,
    escanteios_ultimos_5min INTEGER DEFAULT 0,
    ataques_perigosos INTEGER DEFAULT 0,
    posse_dominante REAL DEFAULT 0,
    finalizacoes INTEGER DEFAULT 0,
    media_historica REAL DEFAULT 0,
    linha_atual REAL DEFAULT 0,
    odd_atual REAL DEFAULT 0,
    corners_final INTEGER,
    resultado_final TEXT
);
"""


class Database:
    """Gerenciamento de banco de dados SQLite para registro de sinais."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        logger.info(f"Banco de dados inicializado: {self.db_path}")

    async def init_ligas_config(self, all_liga_ids: List[int]):
        """Inicializa config de ligas e remove ligas que não estão mais no config."""
        async with aiosqlite.connect(self.db_path) as db:
            for liga_id in all_liga_ids:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO ligas_config (liga_id, ativa)
                    VALUES (?, ?)
                    """,
                    (liga_id, True),
                )
            # Remover ligas que foram retiradas de LIGAS_MONITORADAS
            if all_liga_ids:
                placeholders = ",".join("?" * len(all_liga_ids))
                result = await db.execute(
                    f"DELETE FROM ligas_config WHERE liga_id NOT IN ({placeholders})",
                    all_liga_ids,
                )
                if result.rowcount > 0:
                    logger.info(f"Removed {result.rowcount} stale leagues from ligas_config")
            await db.commit()
        logger.info(f"Initialized config for {len(all_liga_ids)} leagues")

    async def init_thresholds_config(self):
        """Inicializa thresholds padrão se não existir."""
        from config import (
            MIN_SCORE_NORMAL,
            MIN_SCORE_PREMIUM,
            MIN_EDGE_NORMAL,
            MIN_EDGE_PREMIUM,
        )
        
        defaults = {
            "min_score_normal": (float(MIN_SCORE_NORMAL), "Pressure score mínimo para sinal NORMAL"),
            "min_score_premium": (float(MIN_SCORE_PREMIUM), "Pressure score mínimo para sinal PREMIUM"),
            "min_edge_normal": (float(MIN_EDGE_NORMAL), "Edge mínimo para sinal NORMAL"),
            "min_edge_premium": (float(MIN_EDGE_PREMIUM), "Edge mínimo para sinal PREMIUM"),
        }
        
        async with aiosqlite.connect(self.db_path) as db:
            for chave, (valor, descricao) in defaults.items():
                await db.execute(
                    """
                    INSERT OR IGNORE INTO thresholds_config (chave, valor, descricao)
                    VALUES (?, ?, ?)
                    """,
                    (chave, valor, descricao),
                )
            await db.commit()
        logger.info("Initialized thresholds config with defaults")

    async def registrar_sinal(self, sinal: Sinal) -> int:
        jogo = sinal.jogo

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO sinais (
                    timestamp, liga_id, liga_nome, jogo_id, jogo_descricao,
                    minuto, placar, escanteios_total, linha, odd,
                    projecao, edge, pressure_score, tipo_sinal, reavaliacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    jogo.liga_id,
                    jogo.liga_nome,
                    jogo.id,
                    jogo.descricao,
                    jogo.minuto,
                    jogo.placar,
                    jogo.escanteios_total,
                    jogo.linha_atual,
                    jogo.odd_atual,
                    sinal.projecao,
                    sinal.edge,
                    sinal.pressure_score,
                    sinal.tipo,
                    sinal.reavaliacao,
                ),
            )
            await db.commit()
            sinal_id = cursor.lastrowid

            # Detalhes
            await db.execute(
                """
                INSERT INTO detalhes_jogo (
                    sinal_id, ataques_perigosos, finalizacoes,
                    escanteios_time_casa, escanteios_time_fora, media_historica
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sinal_id,
                    jogo.ataques_perigosos_ultimos_10min,
                    jogo.finalizacoes_recentes,
                    jogo.escanteios_casa,
                    jogo.escanteios_fora,
                    jogo.media_historica_combinada,
                ),
            )
            await db.commit()

        logger.info(f"Sinal #{sinal_id} registrado no banco")
        return sinal_id

    async def atualizar_resultado(
        self, jogo_id: int, resultado: str, escanteios_final: int, roi: float
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE sinais
                SET resultado = ?, escanteios_final = ?, roi = ?
                WHERE jogo_id = ? AND resultado IS NULL
                """,
                (resultado, escanteios_final, roi, jogo_id),
            )
            await db.commit()
        logger.info(f"Resultado atualizado: jogo {jogo_id} = {resultado}")

    async def get_sinais_pendentes(self) -> List[RegistroSinal]:
        """Retorna sinais sem resultado das ultimas 24h (para atualizacao posterior)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM sinais
                WHERE resultado IS NULL
                AND timestamp > datetime('now', '-24 hours')"""
            )
            rows = await cursor.fetchall()

        return [
            RegistroSinal(
                id=row["id"],
                jogo_id=row["jogo_id"],
                jogo_descricao=row["jogo_descricao"],
                linha=row["linha"],
                odd=row["odd"],
                tipo_sinal=row["tipo_sinal"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    async def expirar_sinais_antigos(self):
        """Marca sinais pendentes com mais de 24h como EXPIRADO."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """UPDATE sinais
                SET resultado = 'EXPIRADO'
                WHERE resultado IS NULL
                AND timestamp <= datetime('now', '-24 hours')"""
            )
            await db.commit()
            if cursor.rowcount > 0:
                logger.info(f"{cursor.rowcount} sinais expirados (>24h sem resultado)")

    async def get_estatisticas(self) -> dict:
        """Retorna estatisticas gerais dos sinais."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM sinais")
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM sinais WHERE resultado = 'GREEN'"
            )
            greens = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM sinais WHERE resultado = 'RED'"
            )
            reds = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COALESCE(SUM(roi), 0) FROM sinais WHERE roi IS NOT NULL"
            )
            roi_total = (await cursor.fetchone())[0]

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

    async def get_ligas_ativas(self) -> List[int]:
        """Retorna lista de liga_ids atualmente ativas.
        
        DEBUG FASE 2: Instrumentado para validar persistência.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT liga_id FROM ligas_config WHERE ativa = TRUE"
            )
            rows = await cursor.fetchall()
        
        liga_ids = [row[0] for row in rows]
        
        # LOG detalhado
        logger.info("=" * 80)
        logger.info("[DEBUG FASE 2] DATABASE - LIGAS ATIVAS")
        logger.info("=" * 80)
        logger.info(f"[DEBUG] Total de ligas ativas: {len(liga_ids)}")
        logger.info(f"[DEBUG] IDs de ligas: {sorted(liga_ids)}")
        
        # Log mapeado com nomes conhecidos
        from config import LIGAS_MONITORADAS
        liga_map = {liga["id"]: liga["nome"] for liga in LIGAS_MONITORADAS}
        for liga_id in sorted(liga_ids):
            liga_nome = liga_map.get(liga_id, "DESCONHECIDA")
            logger.info(f"[DEBUG]   - {liga_id}: {liga_nome}")
        
        logger.info("=" * 80)
        
        return liga_ids

    async def set_ligas_ativas(self, liga_ids: List[int]):
        """Atualiza quais ligas devem ser monitoradas."""
        async with aiosqlite.connect(self.db_path) as db:
            # Desativa todas
            await db.execute("UPDATE ligas_config SET ativa = FALSE")
            
            # Ativa apenas as especificadas
            for liga_id in liga_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO ligas_config (liga_id, ativa) VALUES (?, ?)",
                    (liga_id, True),
                )
                await db.execute(
                    "UPDATE ligas_config SET ativa = TRUE WHERE liga_id = ?",
                    (liga_id,),
                )
            await db.commit()
        logger.info(f"Ligas ativas atualizadas: {liga_ids}")

    async def get_thresholds(self) -> dict:
        """Retorna todos os thresholds configurados."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT chave, valor, descricao FROM thresholds_config")
            rows = await cursor.fetchall()
        
        return {
            row["chave"]: {
                "valor": float(row["valor"]),
                "descricao": row["descricao"]
            }
            for row in rows
        }

    async def set_thresholds(self, thresholds: dict):
        """Atualiza valores de thresholds."""
        async with aiosqlite.connect(self.db_path) as db:
            for chave, valor in thresholds.items():
                await db.execute(
                    """
                    UPDATE thresholds_config SET valor = ? WHERE chave = ?
                    """,
                    (float(valor), chave),
                )
            await db.commit()
        logger.info(f"Thresholds atualizados: {thresholds}")

    # --- Snapshots (Backtest - Sprint 3) ---

    async def salvar_snapshot(self, jogo: JogoAoVivo):
        """Salva snapshot completo do estado de um jogo para backtest."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO snapshots (
                    timestamp, fixture_id, liga_id, liga_nome,
                    time_casa, time_fora, minuto,
                    placar_casa, placar_fora,
                    escanteios_total, escanteios_casa, escanteios_fora,
                    escanteios_ultimos_10min, escanteios_ultimos_5min,
                    ataques_perigosos, posse_dominante, finalizacoes,
                    media_historica, linha_atual, odd_atual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    jogo.id, jogo.liga_id, jogo.liga_nome,
                    jogo.time_casa, jogo.time_fora, jogo.minuto,
                    jogo.placar_casa, jogo.placar_fora,
                    jogo.escanteios_total, jogo.escanteios_casa, jogo.escanteios_fora,
                    jogo.escanteios_ultimos_10min, jogo.escanteios_ultimos_5min,
                    jogo.ataques_perigosos_ultimos_10min,
                    jogo.posse_ultimos_10min, jogo.finalizacoes_recentes,
                    jogo.media_historica_combinada,
                    jogo.linha_atual, jogo.odd_atual,
                ),
            )
            await db.commit()

    async def atualizar_snapshot_resultado(self, fixture_id: int, corners_final: int):
        """Preenche corners_final e resultado nos snapshots de um jogo."""
        async with aiosqlite.connect(self.db_path) as db:
            # Buscar linha de cada snapshot para calcular resultado
            cursor = await db.execute(
                "SELECT id, linha_atual FROM snapshots WHERE fixture_id = ? AND corners_final IS NULL",
                (fixture_id,),
            )
            rows = await cursor.fetchall()
            for row in rows:
                snap_id, linha = row
                resultado = "GREEN" if corners_final > linha else "RED" if linha > 0 else None
                await db.execute(
                    "UPDATE snapshots SET corners_final = ?, resultado_final = ? WHERE id = ?",
                    (corners_final, resultado, snap_id),
                )
            await db.commit()
            if rows:
                logger.debug(f"Snapshots atualizados para fixture {fixture_id}: {corners_final} corners")

    async def get_snapshots(
        self,
        liga_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        apenas_com_resultado: bool = False,
    ) -> List[Dict]:
        """Busca snapshots para backtest, com filtros opcionais."""
        query = "SELECT * FROM snapshots WHERE 1=1"
        params = []

        if liga_id is not None:
            query += " AND liga_id = ?"
            params.append(liga_id)
        if date_from:
            query += " AND timestamp >= ?"
            params.append(date_from)
        if date_to:
            query += " AND timestamp <= ?"
            params.append(date_to)
        if apenas_com_resultado:
            query += " AND corners_final IS NOT NULL"

        query += " ORDER BY timestamp ASC"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_snapshot_stats(self) -> Dict:
        """Retorna estatisticas dos snapshots coletados."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM snapshots")
            total = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM snapshots WHERE corners_final IS NOT NULL")
            com_resultado = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(DISTINCT fixture_id) FROM snapshots")
            jogos_unicos = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT liga_nome, COUNT(*) as cnt FROM snapshots GROUP BY liga_nome ORDER BY cnt DESC"
            )
            por_liga = await cursor.fetchall()

        return {
            "total_snapshots": total,
            "com_resultado": com_resultado,
            "sem_resultado": total - com_resultado,
            "jogos_unicos": jogos_unicos,
            "por_liga": [(row[0], row[1]) for row in por_liga],
        }

