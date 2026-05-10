import asyncpg
import logging
from typing import Optional, List, Dict
from datetime import datetime
import json

from data.models import Sinal, SinalCartoes, RegistroSinal, JogoAoVivo, User, Subscription, UserStrategyPreference
from config import DATABASE_URL

logger = logging.getLogger("CPES.Database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sinais (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
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
    roi DECIMAL(5,2),
    tipo_analise TEXT DEFAULT 'ESCANTEIOS',
    matching_tiers TEXT[] DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS detalhes_jogo (
    sinal_id INTEGER REFERENCES sinais(id),
    ataques_perigosos INTEGER,
    finalizacoes INTEGER,
    posse_time_casa INTEGER,
    posse_time_fora INTEGER,
    escanteios_time_casa INTEGER,
    escanteios_time_fora INTEGER,
    media_historica DECIMAL(4,2)
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
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
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
    resultado_final TEXT,
    cartoes_amarelos INTEGER DEFAULT 0,
    cartoes_vermelhos INTEGER DEFAULT 0,
    faltas INTEGER DEFAULT 0,
    linha_cartoes REAL DEFAULT 0,
    odd_cartoes REAL DEFAULT 0,
    cartoes_final INTEGER
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150),
    whatsapp VARCHAR(20),
    cpf VARCHAR(14),
    role VARCHAR(20) DEFAULT 'user',
    is_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(6),
    verification_expires_at TIMESTAMP,
    verification_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'sent',
    provider_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    plan VARCHAR(50) DEFAULT 'basic',
    asaas_id VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    starts_at TIMESTAMP,
    expires_at TIMESTAMP,
    next_due_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_strategy_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL UNIQUE,
    corners_strategy VARCHAR(20) NOT NULL DEFAULT 'moderate',
    cards_strategy VARCHAR(20) NOT NULL DEFAULT 'moderate',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_state (
    key VARCHAR(50) PRIMARY KEY,
    data JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """Gerenciamento de banco de dados PostgreSQL."""

    def __init__(self, db_url: Optional[str] = None):
        # Convert dialect for asyncpg if necessary
        url = db_url or DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        self.db_url = url
        self.pool = None

    async def connect(self):
        """Inicializa o pool de conexões."""
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(self.db_url)
                logger.info("Connected to PostgreSQL pool.")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise

    async def init(self):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA)
        logger.info(f"Banco de dados inicializado: {self.db_url}")

    async def init_ligas_config(self, all_liga_ids: List[int]):
        """Inicializa config de ligas e remove ligas que não estão mais no config."""
        await self.connect()
        async with self.pool.acquire() as conn:
            for liga_id in all_liga_ids:
                await conn.execute(
                    """
                    INSERT INTO ligas_config (liga_id, ativa)
                    VALUES ($1, $2)
                    ON CONFLICT (liga_id) DO NOTHING
                    """,
                    liga_id, True
                )
            if all_liga_ids:
                status = await conn.execute(
                    "DELETE FROM ligas_config WHERE liga_id != ALL($1::int[])",
                    all_liga_ids
                )
                logger.info(f"Cleaned stale leagues: {status}")
        logger.info(f"Initialized config for {len(all_liga_ids)} leagues")

    async def init_thresholds_config(self):
        """Inicializa thresholds padrão se não existir."""
        from config import (
            MIN_SCORE_NORMAL, MIN_SCORE_PREMIUM, MIN_EDGE_NORMAL, MIN_EDGE_PREMIUM,
        )
        defaults = {
            "min_score_normal": (float(MIN_SCORE_NORMAL), "Pressure score mínimo para sinal NORMAL"),
            "min_score_premium": (float(MIN_SCORE_PREMIUM), "Pressure score mínimo para sinal PREMIUM"),
            "min_edge_normal": (float(MIN_EDGE_NORMAL), "Edge mínimo para sinal NORMAL"),
            "min_edge_premium": (float(MIN_EDGE_PREMIUM), "Edge mínimo para sinal PREMIUM"),
        }
        await self.connect()
        async with self.pool.acquire() as conn:
            for chave, (valor, descricao) in defaults.items():
                await conn.execute(
                    """
                    INSERT INTO thresholds_config (chave, valor, descricao)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (chave) DO NOTHING
                    """,
                    chave, valor, descricao,
                )
        logger.info("Initialized thresholds config with defaults")

    async def registrar_sinal(self, sinal: Sinal) -> int:
        jogo = sinal.jogo
        await self.connect()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                sinal_id = await conn.fetchval(
                    """
                    INSERT INTO sinais (
                        timestamp, liga_id, liga_nome, jogo_id, jogo_descricao,
                        minuto, placar, escanteios_total, linha, odd,
                        projecao, edge, pressure_score, tipo_sinal, reavaliacao,
                        matching_tiers
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                    RETURNING id
                    """,
                    datetime.now(), jogo.liga_id, jogo.liga_nome, jogo.id, jogo.descricao,
                    jogo.minuto, jogo.placar, jogo.escanteios_total, jogo.linha_atual,
                    jogo.odd_atual, sinal.projecao, sinal.edge, sinal.pressure_score,
                    sinal.tipo, sinal.reavaliacao, sinal.matching_tiers
                )
                await conn.execute(
                    """
                    INSERT INTO detalhes_jogo (
                        sinal_id, ataques_perigosos, finalizacoes,
                        escanteios_time_casa, escanteios_time_fora, media_historica
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    sinal_id, jogo.ataques_perigosos_ultimos_10min, jogo.finalizacoes_recentes,
                    jogo.escanteios_casa, jogo.escanteios_fora, jogo.media_historica_combinada
                )

        logger.info(f"Sinal #{sinal_id} registrado no banco")
        return sinal_id

    async def registrar_sinal_cartoes(self, sinal: SinalCartoes) -> int:
        jogo = sinal.jogo
        await self.connect()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                sinal_id = await conn.fetchval(
                    """
                    INSERT INTO sinais (
                        timestamp, liga_id, liga_nome, jogo_id, jogo_descricao,
                        minuto, placar, escanteios_total, linha, odd,
                        projecao, edge, pressure_score, tipo_sinal, reavaliacao,
                        tipo_analise, matching_tiers
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    RETURNING id
                    """,
                    datetime.now(), jogo.liga_id, jogo.liga_nome, jogo.id, jogo.descricao,
                    jogo.minuto, jogo.placar, jogo.cartoes_amarelos_total, jogo.linha_cartoes,
                    jogo.odd_cartoes, sinal.projecao_cartoes, sinal.edge, sinal.tension_score,
                    sinal.tipo, sinal.reavaliacao, 'CARTOES', sinal.matching_tiers
                )
                await conn.execute(
                    """
                    INSERT INTO detalhes_jogo (
                        sinal_id, ataques_perigosos, finalizacoes,
                        escanteios_time_casa, escanteios_time_fora, media_historica
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    sinal_id, jogo.faltas_total, jogo.finalizacoes_recentes,
                    jogo.cartoes_amarelos_casa, jogo.cartoes_amarelos_fora, jogo.media_historica_cartoes
                )

        logger.info(f"Sinal CARTOES #{sinal_id} registrado no banco")
        return sinal_id

    async def atualizar_resultado(
        self, jogo_id: int, resultado: str, escanteios_final: int, roi: float,
        tipo_analise: str = None
    ):
        await self.connect()
        async with self.pool.acquire() as conn:
            if tipo_analise:
                await conn.execute(
                    """
                    UPDATE sinais
                    SET resultado = $1, escanteios_final = $2, roi = $3
                    WHERE jogo_id = $4 AND resultado IS NULL AND tipo_analise = $5
                    """,
                    resultado, escanteios_final, roi, jogo_id, tipo_analise,
                )
            else:
                await conn.execute(
                    """
                    UPDATE sinais
                    SET resultado = $1, escanteios_final = $2, roi = $3
                    WHERE jogo_id = $4 AND resultado IS NULL
                    """,
                    resultado, escanteios_final, roi, jogo_id,
                )
        tipo_str = f" ({tipo_analise})" if tipo_analise else ""
        logger.info(f"Resultado atualizado: jogo {jogo_id}{tipo_str} = {resultado}")

    async def get_sinais_pendentes(self) -> List[RegistroSinal]:
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM sinais
                WHERE resultado IS NULL
                AND timestamp > NOW() - INTERVAL '24 hours'"""
            )
        return [
            RegistroSinal(
                id=row["id"], jogo_id=row["jogo_id"], jogo_descricao=row["jogo_descricao"],
                linha=float(row["linha"]), odd=float(row["odd"]), tipo_sinal=row["tipo_sinal"],
                timestamp=row["timestamp"].isoformat(),
                tipo_analise=row.get("tipo_analise", "ESCANTEIOS") or "ESCANTEIOS",
            )
            for row in rows
        ]

    async def expirar_sinais_antigos(self):
        await self.connect()
        async with self.pool.acquire() as conn:
            status = await conn.execute(
                """UPDATE sinais
                SET resultado = 'EXPIRADO'
                WHERE resultado IS NULL
                AND timestamp <= NOW() - INTERVAL '24 hours'"""
            )
        logger.info(f"Sinais expirados (>24h sem resultado): {status}")

    async def get_estatisticas(self, tipo_analise: str = None) -> dict:
        filtro = ""
        params = []
        if tipo_analise:
            filtro = " WHERE tipo_analise = $1"
            params = [tipo_analise]

        await self.connect()
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(f"SELECT COUNT(DISTINCT jogo_id) FROM sinais{filtro}", *params)
            
            filtro_r = (" AND tipo_analise = $1" if tipo_analise else "")
            params_r = [tipo_analise] if tipo_analise else []

            greens = await conn.fetchval(f"SELECT COUNT(DISTINCT jogo_id) FROM sinais WHERE resultado = 'GREEN'{filtro_r}", *params_r)
            reds = await conn.fetchval(f"SELECT COUNT(DISTINCT jogo_id) FROM sinais WHERE resultado = 'RED'{filtro_r}", *params_r)
            
            roi_total = await conn.fetchval(
                f"""SELECT COALESCE(SUM(roi), 0) FROM sinais 
                WHERE roi IS NOT NULL 
                AND id IN (
                    SELECT MIN(id) FROM sinais 
                    WHERE resultado IS NOT NULL{filtro_r}
                    GROUP BY jogo_id
                ){filtro_r}""",
                *(params_r + params_r)
            )

        pendentes = total - greens - reds
        winrate = (greens / (greens + reds) * 100) if (greens + reds) > 0 else 0

        return {
            "total": total,
            "greens": greens,
            "reds": reds,
            "pendentes": pendentes,
            "winrate": round(winrate, 1),
            "roi_total": round(float(roi_total), 2),
        }

    async def get_ligas_ativas(self) -> List[int]:
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT liga_id FROM ligas_config WHERE ativa = TRUE")
        return [row["liga_id"] for row in rows]

    async def set_ligas_ativas(self, liga_ids: List[int]):
        await self.connect()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("UPDATE ligas_config SET ativa = FALSE")
                for liga_id in liga_ids:
                    await conn.execute(
                        """
                        INSERT INTO ligas_config (liga_id, ativa) VALUES ($1, $2)
                        ON CONFLICT (liga_id) DO UPDATE SET ativa=TRUE
                        """,
                        liga_id, True,
                    )
        logger.info(f"Ligas ativas atualizadas: {liga_ids}")

    async def get_thresholds(self) -> dict:
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT chave, valor, descricao FROM thresholds_config")
        return {
            row["chave"]: {
                "valor": float(row["valor"]),
                "descricao": row["descricao"]
            }
            for row in rows
        }

    async def set_thresholds(self, updates: Dict[str, float]):
        await self.connect()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for chave, valor in updates.items():
                    await conn.execute(
                        """
                        INSERT INTO thresholds_config (chave, valor) VALUES ($1, $2)
                        ON CONFLICT (chave) DO UPDATE SET valor=EXCLUDED.valor
                        """,
                        chave, valor,
                    )
        logger.info(f"Thresholds atualizados: {updates}")

    async def upsert_state(self, key: str, data: dict):
        """Salva um documento JSON na tabela app_state."""
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO app_state (key, data, updated_at) 
                VALUES ($1, $2, NOW())
                ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """,
                key, json.dumps(data)
            )

    async def get_state(self, key: str) -> Optional[dict]:
        """Recupera um documento JSON da tabela app_state."""
        await self.connect()
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT data FROM app_state WHERE key = $1", key)
            if val is not None:
                return json.loads(val)
            return None

    # --- User & Auth Methods ---
    async def create_user(self, user: User) -> Optional[int]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                user_id = await conn.fetchval(
                    """
                    INSERT INTO users (email, password_hash, full_name, whatsapp, cpf, role)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    user.email, user.password_hash, user.full_name, user.whatsapp, user.cpf, user.role,
                )
                return user_id
        except Exception as e:
            logger.error(f"Erro ao criar usuario {user.email}: {e}")
            return None

    def _map_user(self, row) -> User:
        return User(
            id=row["id"], email=row["email"], password_hash=row["password_hash"],
            full_name=row["full_name"] or "", whatsapp=row["whatsapp"] or "",
            cpf=row["cpf"] or "", role=row["role"],
            is_verified=bool(row["is_verified"]), verification_code=row["verification_code"],
            verification_expires_at=row["verification_expires_at"],
            verification_attempts=row["verification_attempts"], created_at=row["created_at"],
        )

    async def get_user_by_email(self, email: str) -> Optional[User]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
                if row: return self._map_user(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar usuario {email}: {e}")
            return None
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
                if row: return self._map_user(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar usuario ID {user_id}: {e}")
            return None

    async def update_user_verification(self, email: str, code: str, expires_at: datetime) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE users
                    SET verification_code = $1, verification_expires_at = $2,
                        verification_attempts = 0, updated_at = NOW()
                    WHERE email = $3
                    """, code, expires_at, email
                )
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar código de verificação para {email}: {e}")
            return False

    async def verify_email_code(self, email: str, code: str) -> tuple[bool, str]:
        user = await self.get_user_by_email(email)
        if not user: return False, "Usuário não encontrado"
        if user.is_verified: return True, "Email já verificado"
        if user.verification_attempts >= 5: return False, "Muitas tentativas. Solicite um novo código."
        if not user.verification_code or user.verification_code != code:
            await self.increment_verification_attempts(email)
            return False, "Código inválido"
        if user.verification_expires_at and datetime.now() > user.verification_expires_at:
            return False, "Código expirado. Solicite um novo."
        
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE users
                    SET is_verified = TRUE, verification_code = NULL, verification_expires_at = NULL,
                        verification_attempts = 0, updated_at = NOW()
                    WHERE email = $1
                    """, email
                )
            return True, "Email verificado com sucesso"
        except Exception as e:
            logger.error(f"Erro ao verificar email {email}: {e}")
            return False, "Erro interno"

    async def increment_verification_attempts(self, email: str) -> None:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("UPDATE users SET verification_attempts = verification_attempts + 1 WHERE email = $1", email)
        except Exception as e:
            logger.error(f"Erro ao incrementar tentativas para {email}: {e}")

    async def log_email(self, user_id: Optional[int], email_type: str, status: str, response: str = "") -> None:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO email_logs (user_id, type, status, provider_response) VALUES ($1, $2, $3, $4)",
                    user_id, email_type, status, response,
                )
        except Exception as e:
            logger.error(f"Erro ao registrar email log: {e}")

    async def upsert_subscription(self, sub: Subscription) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO subscriptions (user_id, plan, asaas_id, status, starts_at, expires_at, next_due_date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET 
                        plan=EXCLUDED.plan, asaas_id=EXCLUDED.asaas_id, status=EXCLUDED.status,
                        starts_at=EXCLUDED.starts_at, expires_at=EXCLUDED.expires_at, next_due_date=EXCLUDED.next_due_date
                    """,
                    sub.user_id, sub.plan, sub.asaas_id, sub.status, sub.starts_at, sub.expires_at, sub.next_due_date
                ) # TODO: the conflict logic assumes an id but id is SERIAL, might need a constraint on user_id
                return True
        except Exception as e:
            logger.error(f"Erro ao salvar assinatura user {sub.user_id}: {e}")
            return False

    async def get_subscription_by_user_id(self, user_id: int) -> Optional[Subscription]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM subscriptions WHERE user_id = $1 ORDER BY id DESC LIMIT 1", user_id)
                if row:
                    return Subscription(
                        id=row["id"], user_id=row["user_id"], plan=row["plan"],
                        asaas_id=row["asaas_id"], status=row["status"],
                        starts_at=row["starts_at"], expires_at=row["expires_at"],
                        next_due_date=row["next_due_date"], created_at=row["created_at"],
                    )
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar assinatura user {user_id}: {e}")
            return None

    # --- User Strategy Preferences ---
    async def get_user_strategy_preference(self, user_id: int) -> Optional[UserStrategyPreference]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM user_strategy_preferences WHERE user_id = $1", user_id
                )
                if row:
                    return UserStrategyPreference(
                        id=row["id"],
                        user_id=row["user_id"],
                        corners_strategy=row["corners_strategy"],
                        cards_strategy=row["cards_strategy"],
                        updated_at=row["updated_at"],
                    )
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar preferencia de estrategia user {user_id}: {e}")
            return None

    async def upsert_user_strategy_preference(
        self, user_id: int, corners_strategy: str, cards_strategy: str
    ) -> Optional[UserStrategyPreference]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO user_strategy_preferences (user_id, corners_strategy, cards_strategy, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        corners_strategy = EXCLUDED.corners_strategy,
                        cards_strategy = EXCLUDED.cards_strategy,
                        updated_at = NOW()
                    RETURNING *
                    """,
                    user_id, corners_strategy, cards_strategy,
                )
                if row:
                    return UserStrategyPreference(
                        id=row["id"],
                        user_id=row["user_id"],
                        corners_strategy=row["corners_strategy"],
                        cards_strategy=row["cards_strategy"],
                        updated_at=row["updated_at"],
                    )
            return None
        except Exception as e:
            logger.error(f"Erro ao salvar preferencia de estrategia user {user_id}: {e}")
            return None

    # --- Snapshots (Backtest - Sprint 3) ---
    async def salvar_snapshot(self, jogo: JogoAoVivo):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO snapshots (
                    timestamp, fixture_id, liga_id, liga_nome, time_casa, time_fora, minuto,
                    placar_casa, placar_fora, escanteios_total, escanteios_casa, escanteios_fora,
                    escanteios_ultimos_10min, escanteios_ultimos_5min,
                    ataques_perigosos, posse_dominante, finalizacoes, media_historica,
                    linha_atual, odd_atual, cartoes_amarelos, cartoes_vermelhos,
                    faltas, linha_cartoes, odd_cartoes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)""",
                datetime.now(), jogo.id, jogo.liga_id, jogo.liga_nome, jogo.time_casa, jogo.time_fora, jogo.minuto,
                jogo.placar_casa, jogo.placar_fora, jogo.escanteios_total, jogo.escanteios_casa, jogo.escanteios_fora,
                jogo.escanteios_ultimos_10min, jogo.escanteios_ultimos_5min,
                jogo.ataques_perigosos_ultimos_10min, jogo.posse_ultimos_10min, jogo.finalizacoes_recentes,
                jogo.media_historica_combinada, jogo.linha_atual, jogo.odd_atual,
                jogo.cartoes_amarelos_total, jogo.cartoes_vermelhos_total,
                jogo.faltas_total, jogo.linha_cartoes, jogo.odd_cartoes,
            )

    async def atualizar_snapshot_resultado(self, fixture_id: int, corners_final: int):
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, linha_atual FROM snapshots WHERE fixture_id = $1 AND corners_final IS NULL", fixture_id)
            for row in rows:
                snap_id, linha = row["id"], row["linha_atual"]
                resultado = "GREEN" if corners_final > linha else "RED" if linha > 0 else None
                await conn.execute("UPDATE snapshots SET corners_final = $1, resultado_final = $2 WHERE id = $3", corners_final, resultado, snap_id)

    async def get_snapshots(
        self, liga_id: Optional[int] = None, date_from: Optional[str] = None,
        date_to: Optional[str] = None, apenas_com_resultado: bool = False,
    ) -> List[Dict]:
        query = "SELECT * FROM snapshots WHERE 1=1"
        params = []

        if liga_id is not None:
            params.append(liga_id)
            query += f" AND liga_id = ${len(params)}"
        if date_from:
            params.append(datetime.fromisoformat(date_from))
            query += f" AND timestamp >= ${len(params)}"
        if date_to:
            params.append(datetime.fromisoformat(date_to))
            query += f" AND timestamp <= ${len(params)}"
        if apenas_com_resultado:
            query += " AND corners_final IS NOT NULL"
        query += " ORDER BY timestamp ASC"

        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    async def get_snapshot_stats(self) -> Dict:
        await self.connect()
        async with self.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM snapshots")
            com_resultado = await conn.fetchval("SELECT COUNT(*) FROM snapshots WHERE corners_final IS NOT NULL")
            jogos_unicos = await conn.fetchval("SELECT COUNT(DISTINCT fixture_id) FROM snapshots")
            por_liga = await conn.fetch("SELECT liga_nome, COUNT(*) as cnt FROM snapshots GROUP BY liga_nome ORDER BY cnt DESC")

        return {
            "total_snapshots": total,
            "com_resultado": com_resultado,
            "sem_resultado": total - com_resultado,
            "jogos_unicos": jogos_unicos,
            "por_liga": [(row["liga_nome"], row["cnt"]) for row in por_liga],
        }

