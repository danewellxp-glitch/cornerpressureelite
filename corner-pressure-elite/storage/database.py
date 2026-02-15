import aiosqlite
import logging
from typing import Optional, List
from datetime import datetime

from data.models import Sinal, RegistroSinal
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
        """Retorna sinais sem resultado (para atualizacao posterior)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sinais WHERE resultado IS NULL"
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
            )
            for row in rows
        ]

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
