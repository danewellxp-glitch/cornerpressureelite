import asyncio
import asyncpg
import logging
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import json

from data.models import Sinal, SinalCartoes, RegistroSinal, JogoAoVivo, User, Subscription, UserStrategyPreference
from config import DATABASE_URL

logger = logging.getLogger("CPES.Database")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

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
    matching_tiers TEXT[] DEFAULT '{}',
    -- Rastreabilidade (2026-05-11): fonte e variantes da linha
    bookmaker_usado VARCHAR(20),         -- 'betano' | 'bet365' | 'consolidada'
    linha_betano DECIMAL(4,1),
    linha_bet365 DECIMAL(4,1)
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
    notifications_paused_until TIMESTAMP,
    recovery_email_sent_at TIMESTAMP,
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

CREATE TABLE IF NOT EXISTS user_strategy_preference (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    strategy TEXT NOT NULL CHECK (strategy IN ('conservative','moderate','aggressive','brute')),
    market TEXT NOT NULL CHECK (market IN ('corners','cards')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, market)
);

CREATE TABLE IF NOT EXISTS app_state (
    key VARCHAR(50) PRIMARY KEY,
    data JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processed_payments (
    asaas_payment_id VARCHAR(50) NOT NULL,
    event_group VARCHAR(20) NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asaas_payment_id, event_group)
);

-- ============= Robô Auto-Aposta =============

CREATE TABLE IF NOT EXISTS bot_config (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    enabled BOOLEAN DEFAULT FALSE,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper','real')),
    bet_house TEXT,
    banca_inicial_cents BIGINT NOT NULL DEFAULT 0,
    banca_atual_cents BIGINT NOT NULL DEFAULT 0,
    max_loss_per_day_cents BIGINT NOT NULL DEFAULT 0,
    max_bets_per_day INTEGER NOT NULL DEFAULT 0,
    unit_pct REAL NOT NULL DEFAULT 0.01,
    allowed_leagues INTEGER[] DEFAULT '{}',
    allowed_markets TEXT[] DEFAULT '{}',
    kill_switch BOOLEAN DEFAULT FALSE,
    real_mode_unlocked BOOLEAN DEFAULT FALSE,
    accepted_tos_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bet_house_credentials (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bet_house TEXT NOT NULL,
    username_ct BYTEA NOT NULL,
    password_ct BYTEA NOT NULL,
    nonce BYTEA NOT NULL,
    last_validated_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'unverified',
    PRIMARY KEY (user_id, bet_house)
);

CREATE TABLE IF NOT EXISTS bets (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal_id INTEGER REFERENCES sinais(id),
    market TEXT NOT NULL,
    bet_house TEXT,
    bet_house_bet_id TEXT,
    mode TEXT NOT NULL DEFAULT 'paper',
    stake_cents BIGINT NOT NULL,
    odd REAL NOT NULL,
    linha REAL NOT NULL,
    selecao TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    payout_cents BIGINT DEFAULT 0,
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP,
    UNIQUE (user_id, signal_id, market)
);

CREATE INDEX IF NOT EXISTS bets_user_status ON bets(user_id, status);

CREATE TABLE IF NOT EXISTS bot_audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    decision_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    context JSONB NOT NULL,
    result JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS bot_audit_user_time ON bot_audit_log(user_id, created_at DESC);

-- Mapping fixture_id (API-Football) -> betano_event_id (bridge Betano).
-- Fase 2bc: alimentado por seed manual via env BETANO_EVENT_MAP.
-- Coluna mantida como betano_event_id pra compatibilidade com FixtureMapRepo.
CREATE TABLE IF NOT EXISTS betano_fixture_map (
    fixture_id INTEGER PRIMARY KEY,
    betano_event_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """Gerenciamento de banco de dados PostgreSQL.

    O pool eh compartilhado entre todas as instancias do processo (class-level)
    para evitar TooManyConnectionsError: cada Database() criava um pool novo
    de ~10 conexoes; com 18 endpoints instanciando Database() por request,
    Postgres (max_connections=100) saturava.
    """

    _shared_pool: Optional[asyncpg.Pool] = None
    _pool_lock: Optional[asyncio.Lock] = None

    def __init__(self, db_url: Optional[str] = None):
        # Convert dialect for asyncpg if necessary
        url = db_url or DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        self.db_url = url

    @property
    def pool(self) -> Optional[asyncpg.Pool]:
        return Database._shared_pool

    async def connect(self):
        """Inicializa o pool compartilhado (apenas uma vez por processo)."""
        if Database._shared_pool is not None:
            return

        if Database._pool_lock is None:
            Database._pool_lock = asyncio.Lock()

        async with Database._pool_lock:
            if Database._shared_pool is not None:
                return
            try:
                Database._shared_pool = await asyncpg.create_pool(
                    self.db_url,
                    min_size=2,
                    max_size=15,
                    command_timeout=30,
                )
                logger.info("Connected to PostgreSQL pool (shared, max_size=15).")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise

    async def init(self):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA)
            await self._migrate_subscriptions_unique(conn)
            await self._migrate_users_columns(conn)
            await self._apply_sql_migrations(conn)
        logger.info(f"Banco de dados inicializado: {self.db_url}")

    async def seed_betano_fixture_map(self, mapping: Dict[int, str]) -> int:
        """UPSERT seed manual fixture_id -> betano_event_id (Fase 2bc).

        Idempotente: re-run sobrescreve. Retorna quantidade de linhas seedadas.
        """
        if not mapping:
            return 0
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO betano_fixture_map (fixture_id, betano_event_id)
                VALUES ($1, $2)
                ON CONFLICT (fixture_id) DO UPDATE
                  SET betano_event_id = EXCLUDED.betano_event_id,
                      created_at = CURRENT_TIMESTAMP
                """,
                [(fid, str(eid)) for fid, eid in mapping.items()],
            )
        return len(mapping)

    async def _apply_sql_migrations(self, conn) -> None:
        """Aplica arquivos .sql em migrations/ em ordem lexicográfica.

        Os arquivos devem ser idempotentes (IF NOT EXISTS). Sem tabela de
        controle por enquanto — Fase D só introduz tabelas novas com guard.
        """
        if not MIGRATIONS_DIR.is_dir():
            return
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for path in files:
            sql = path.read_text(encoding="utf-8")
            if not sql.strip():
                continue
            await conn.execute(sql)
            logger.info(f"[MIGRATION] aplicado: {path.name}")

    async def _migrate_users_columns(self, conn) -> None:
        """Adiciona colunas que não existiam em versões antigas do schema. Idempotente."""
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_paused_until TIMESTAMP"
        )
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_email_sent_at TIMESTAMP"
        )
        # sinais.matching_tiers (criado depois do schema inicial)
        await conn.execute(
            "ALTER TABLE sinais ADD COLUMN IF NOT EXISTS matching_tiers TEXT[] DEFAULT '{}'"
        )
        await conn.execute(
            "ALTER TABLE sinais ADD COLUMN IF NOT EXISTS tipo_analise TEXT DEFAULT 'ESCANTEIOS'"
        )
        # sinais — rastreabilidade da linha (2026-05-11)
        await conn.execute(
            "ALTER TABLE sinais ADD COLUMN IF NOT EXISTS bookmaker_usado VARCHAR(20)"
        )
        await conn.execute(
            "ALTER TABLE sinais ADD COLUMN IF NOT EXISTS linha_betano DECIMAL(4,1)"
        )
        await conn.execute(
            "ALTER TABLE sinais ADD COLUMN IF NOT EXISTS linha_bet365 DECIMAL(4,1)"
        )

    async def _migrate_subscriptions_unique(self, conn) -> None:
        """Garante 1 sub por user. Idempotente — roda em todo startup.

        1) deduplica linhas existentes (mantém a maior id por user_id)
        2) cria unique index em user_id (habilita ON CONFLICT (user_id))
        """
        deleted = await conn.fetchval(
            """
            WITH dups AS (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id DESC) AS rn
                FROM subscriptions
            )
            DELETE FROM subscriptions WHERE id IN (SELECT id FROM dups WHERE rn > 1)
            RETURNING id
            """
        )
        if deleted is not None:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM subscriptions"
            )
            logger.info(f"[MIGRATION] subscriptions: tabela com {count} linhas após dedupe")
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_user_id_uniq ON subscriptions(user_id)"
        )

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

    async def registrar_sinal(
        self,
        sinal: Sinal,
        sofa_event_id: Optional[int] = None,
    ) -> int:
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
                        matching_tiers, bookmaker_usado, linha_betano, linha_bet365,
                        sofa_event_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                    RETURNING id
                    """,
                    datetime.now(), jogo.liga_id, jogo.liga_nome, jogo.id, jogo.descricao,
                    jogo.minuto, jogo.placar, jogo.escanteios_total, jogo.linha_atual,
                    jogo.odd_atual, sinal.projecao, sinal.edge, sinal.pressure_score,
                    sinal.tipo, sinal.reavaliacao, sinal.matching_tiers,
                    jogo.bookmaker_usado or None,
                    jogo.linha_betano if jogo.linha_betano > 0 else None,
                    jogo.linha_bet365 if jogo.linha_bet365 > 0 else None,
                    sofa_event_id,
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

    async def registrar_sinal_cartoes(
        self,
        sinal: SinalCartoes,
        sofa_event_id: Optional[int] = None,
    ) -> int:
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
                        tipo_analise, matching_tiers, sofa_event_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                    RETURNING id
                    """,
                    datetime.now(), jogo.liga_id, jogo.liga_nome, jogo.id, jogo.descricao,
                    jogo.minuto, jogo.placar, jogo.cartoes_amarelos_total, jogo.linha_cartoes,
                    jogo.odd_cartoes, sinal.projecao_cartoes, sinal.edge, sinal.tension_score,
                    sinal.tipo, sinal.reavaliacao, 'CARTOES', sinal.matching_tiers,
                    sofa_event_id,
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
                *params_r
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

    async def init_dev_mode_config(self):
        """Seed dev_mode_config na app_state com defaults do .env se nao existir."""
        from config import (
            DEV_TEST_MODE,
            DEV_TEST_MAX_GAMES,
            DEV_TEST_POLLING_INTERVAL,
            DEV_TEST_STATUS_CHECK_INTERVAL,
            DEV_TEST_API_DAILY_LIMIT,
        )
        defaults = {
            "enabled": bool(DEV_TEST_MODE),
            "max_games": int(DEV_TEST_MAX_GAMES),
            "polling_interval": int(DEV_TEST_POLLING_INTERVAL),
            "status_check_interval": int(DEV_TEST_STATUS_CHECK_INTERVAL),
            "api_daily_limit": int(DEV_TEST_API_DAILY_LIMIT),
            "normal_polling_interval": 60,
            "normal_status_check_interval": 300,
            "normal_api_daily_limit": 7500,
        }
        await self.connect()
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT data FROM app_state WHERE key = $1", "dev_mode_config"
            )
            if existing is None:
                await conn.execute(
                    """
                    INSERT INTO app_state (key, data, updated_at)
                    VALUES ($1, $2, NOW())
                    """,
                    "dev_mode_config", json.dumps(defaults),
                )
                logger.info("Initialized dev_mode_config: %s", defaults)

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
    
    async def get_user_by_whatsapp(self, whatsapp: str) -> Optional[User]:
        """Look up a user by their WhatsApp number."""
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE whatsapp = $1", whatsapp)
                if row: return self._map_user(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar usuario por WhatsApp {whatsapp}: {e}")
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

    async def get_strategy_performance(self, market: str, days: int = 30) -> Dict[str, Dict]:
        """Performance histórica por tier no mercado dado (corners | cards).

        Retorna dict { tier: { n, greens, reds, hit_rate, roi_pct } } para os 4 tiers,
        agregado sobre sinais resolvidos (GREEN/RED) dos últimos `days` dias.
        Tiers sem sinais saem com n=0.
        """
        tipo = "ESCANTEIOS" if market == "corners" else "CARTOES"
        tiers = ("conservative", "moderate", "aggressive", "brute")
        result: Dict[str, Dict] = {
            t: {"tier": t, "n": 0, "greens": 0, "reds": 0, "hit_rate": 0.0, "roi_pct": 0.0}
            for t in tiers
        }
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        tier,
                        COUNT(*) AS n,
                        COUNT(*) FILTER (WHERE resultado = 'GREEN') AS greens,
                        COUNT(*) FILTER (WHERE resultado = 'RED') AS reds,
                        COALESCE(AVG(roi), 0) AS avg_roi
                    FROM sinais, UNNEST(matching_tiers) AS tier
                    WHERE tipo_analise = $1
                      AND resultado IN ('GREEN','RED')
                      AND timestamp > NOW() - ($2::int * INTERVAL '1 day')
                      AND tier = ANY($3::text[])
                    GROUP BY tier
                    """,
                    tipo, days, list(tiers),
                )
                for r in rows:
                    n = int(r["n"]) or 0
                    greens = int(r["greens"]) or 0
                    reds = int(r["reds"]) or 0
                    resolved = greens + reds
                    avg_roi = float(r["avg_roi"]) if r["avg_roi"] is not None else 0.0
                    result[r["tier"]] = {
                        "tier": r["tier"],
                        "n": n,
                        "greens": greens,
                        "reds": reds,
                        "hit_rate": (greens / resolved) if resolved > 0 else 0.0,
                        "roi_pct": avg_roi * 100.0,  # roi é fração (0.15 = +15%)
                    }
        except Exception as e:
            logger.error(f"Erro em get_strategy_performance({market}): {e}")
        return result

    # ============= Robô Auto-Aposta =============

    async def get_bot_config(self, user_id: int) -> Optional[Dict]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM bot_config WHERE user_id = $1", user_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Erro buscando bot_config user {user_id}: {e}")
            return None

    async def upsert_bot_config(self, user_id: int, fields: Dict) -> bool:
        """Upsert parcial — só atualiza campos passados. Cria row se não existir."""
        if not fields:
            return False
        allowed = {
            "enabled", "mode", "bet_house", "banca_inicial_cents", "banca_atual_cents",
            "max_loss_per_day_cents", "max_bets_per_day", "unit_pct", "allowed_leagues",
            "allowed_markets", "kill_switch", "real_mode_unlocked", "accepted_tos_at",
        }
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return False

        cols = list(clean.keys())
        values = [clean[c] for c in cols]
        placeholders = ", ".join(f"${i+2}" for i in range(len(cols)))
        set_clauses = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)

        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO bot_config (user_id, {', '.join(cols)}, updated_at)
                    VALUES ($1, {placeholders}, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        {set_clauses}, updated_at = NOW()
                    """,
                    user_id, *values,
                )
                return True
        except Exception as e:
            logger.error(f"Erro upsert bot_config user {user_id}: {e}")
            return False

    async def list_user_credentials(self, user_id: int) -> List[Dict]:
        """Lista casas configuradas para o user — SEM retornar username/password.

        Retorna apenas metadata: bet_house, status, last_validated_at.
        """
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT bet_house, status, last_validated_at FROM bet_house_credentials WHERE user_id = $1",
                    user_id,
                )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Erro listando credentials user {user_id}: {e}")
            return []

    async def upsert_credential(
        self, user_id: int, bet_house: str,
        username_ct: bytes, password_ct: bytes, nonce: bytes,
    ) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bet_house_credentials
                        (user_id, bet_house, username_ct, password_ct, nonce, status)
                    VALUES ($1, $2, $3, $4, $5, 'unverified')
                    ON CONFLICT (user_id, bet_house) DO UPDATE SET
                        username_ct = EXCLUDED.username_ct,
                        password_ct = EXCLUDED.password_ct,
                        nonce = EXCLUDED.nonce,
                        status = 'unverified',
                        last_validated_at = NULL
                    """,
                    user_id, bet_house, username_ct, password_ct, nonce,
                )
                return True
        except Exception as e:
            logger.error(f"Erro upsert credential user {user_id}/{bet_house}: {e}")
            return False

    async def delete_credential(self, user_id: int, bet_house: str) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM bet_house_credentials WHERE user_id = $1 AND bet_house = $2",
                    user_id, bet_house,
                )
                return result.startswith("DELETE")
        except Exception as e:
            logger.error(f"Erro delete credential user {user_id}/{bet_house}: {e}")
            return False

    async def get_bot_global_kill(self) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchval(
                    "SELECT data FROM app_state WHERE key = 'bot_global_kill'"
                )
                if row is None:
                    return False
                # asyncpg retorna JSONB como str por padrão (sem custom codec)
                if isinstance(row, str):
                    try:
                        row = json.loads(row)
                    except Exception:
                        return False
                if isinstance(row, dict):
                    return bool(row.get("enabled"))
                return bool(row)
        except Exception as e:
            logger.error(f"Erro lendo bot_global_kill: {e}")
            return False

    async def set_bot_global_kill(self, enabled: bool) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO app_state (key, data, updated_at)
                    VALUES ('bot_global_kill', $1::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                    """,
                    json.dumps({"enabled": enabled}),
                )
                return True
        except Exception as e:
            logger.error(f"Erro setando bot_global_kill: {e}")
            return False

    # --- Queries usadas pelo bot orchestrator (Fase 2) ---

    async def get_bot_checkpoint(self) -> int:
        """Último signal_id processado pelo bot. 0 se nunca rodou."""
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchval(
                    "SELECT data FROM app_state WHERE key = 'bot_checkpoint'"
                )
                if row is None:
                    return 0
                if isinstance(row, str):
                    try:
                        row = json.loads(row)
                    except Exception:
                        return 0
                if isinstance(row, dict):
                    return int(row.get("last_signal_id", 0))
                return 0
        except Exception as e:
            logger.error(f"Erro lendo bot_checkpoint: {e}")
            return 0

    async def set_bot_checkpoint(self, last_signal_id: int) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO app_state (key, data, updated_at)
                    VALUES ('bot_checkpoint', $1::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                    """,
                    json.dumps({"last_signal_id": last_signal_id}),
                )
                return True
        except Exception as e:
            logger.error(f"Erro salvando bot_checkpoint: {e}")
            return False

    async def signals_after(self, last_id: int, limit: int = 50) -> List[Dict]:
        """Retorna sinais com id > last_id, ordenados por id ASC.

        Inclui apenas sinais elegíveis (não reavaliação). Retorna campos chave
        usados pelo orchestrator pra tomar decisão.
        """
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, liga_id, jogo_id, jogo_descricao, minuto,
                           linha, odd, edge, pressure_score, tipo_sinal,
                           tipo_analise, matching_tiers, timestamp, resultado, roi
                    FROM sinais
                    WHERE id > $1 AND reavaliacao = FALSE
                    ORDER BY id ASC
                    LIMIT $2
                    """,
                    last_id, limit,
                )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Erro signals_after({last_id}): {e}")
            return []

    async def users_with_bot_enabled(self) -> List[Dict]:
        """Users com bot ativo e ToS aceito. Retorna tudo que orchestrator precisa."""
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT u.id AS user_id, u.role,
                           c.enabled, c.mode, c.bet_house,
                           c.banca_inicial_cents, c.banca_atual_cents,
                           c.max_loss_per_day_cents, c.max_bets_per_day,
                           c.unit_pct, c.allowed_leagues, c.allowed_markets,
                           c.kill_switch
                    FROM users u
                    JOIN bot_config c ON c.user_id = u.id
                    LEFT JOIN subscriptions s ON s.user_id = u.id
                    WHERE c.enabled = TRUE
                      AND c.kill_switch = FALSE
                      AND c.accepted_tos_at IS NOT NULL
                      AND (
                          u.role = 'admin'
                          OR (s.status = 'active' AND s.plan = 'max'
                              AND (s.expires_at IS NULL OR s.expires_at > NOW()))
                      )
                    """
                )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Erro users_with_bot_enabled: {e}")
            return []

    async def insert_bet(self, bet: Dict) -> Optional[int]:
        """Insere uma bet. Idempotência via UNIQUE (user_id, signal_id, market).
        Retorna id da bet, ou None se já existia (conflito) ou erro.
        """
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO bets (
                        user_id, signal_id, market, bet_house, bet_house_bet_id,
                        mode, stake_cents, odd, linha, selecao, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'open')
                    ON CONFLICT (user_id, signal_id, market) DO NOTHING
                    RETURNING id
                    """,
                    bet["user_id"], bet.get("signal_id"), bet["market"],
                    bet.get("bet_house"), bet.get("bet_house_bet_id"),
                    bet.get("mode", "paper"), bet["stake_cents"], bet["odd"],
                    bet["linha"], bet["selecao"],
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"Erro insert_bet user {bet.get('user_id')}: {e}")
            return None

    async def get_bet_by_user_signal(self, user_id: int, signal_id: int, market: str) -> Optional[Dict]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM bets WHERE user_id=$1 AND signal_id=$2 AND market=$3",
                    user_id, signal_id, market,
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Erro get_bet_by_user_signal: {e}")
            return None

    async def get_open_bets_for_signal(self, signal_id: int) -> List[Dict]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM bets WHERE signal_id=$1 AND status='open'",
                    signal_id,
                )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Erro get_open_bets_for_signal: {e}")
            return []

    async def settle_bet(
        self, bet_id: int, status: str, payout_cents: int,
    ) -> bool:
        """Marca bet como won/lost/cashed_out e seta payout."""
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bets
                    SET status=$2, payout_cents=$3, settled_at=NOW()
                    WHERE id=$1 AND status='open'
                    """,
                    bet_id, status, payout_cents,
                )
                return True
        except Exception as e:
            logger.error(f"Erro settle_bet {bet_id}: {e}")
            return False

    async def adjust_banca(self, user_id: int, delta_cents: int) -> bool:
        """Adiciona delta na banca_atual_cents. Pode ser negativo."""
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bot_config
                    SET banca_atual_cents = banca_atual_cents + $2, updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id, delta_cents,
                )
                return True
        except Exception as e:
            logger.error(f"Erro adjust_banca user {user_id}: {e}")
            return False

    async def count_bets_today(self, user_id: int) -> int:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM bets
                    WHERE user_id=$1 AND placed_at::date = CURRENT_DATE
                    """,
                    user_id,
                ) or 0
        except Exception as e:
            logger.error(f"Erro count_bets_today user {user_id}: {e}")
            return 0

    async def sum_losses_today_cents(self, user_id: int) -> int:
        """Soma perdas (stake - payout) das bets resolvidas hoje. Sempre >= 0."""
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                v = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(stake_cents - payout_cents), 0)
                    FROM bets
                    WHERE user_id=$1
                      AND settled_at::date = CURRENT_DATE
                      AND status IN ('lost', 'cashed_out')
                      AND payout_cents < stake_cents
                    """,
                    user_id,
                )
                return int(v or 0)
        except Exception as e:
            logger.error(f"Erro sum_losses_today user {user_id}: {e}")
            return 0

    async def insert_audit(
        self, user_id: Optional[int], decision_id: str, event_type: str,
        context: Dict, result: Optional[Dict] = None,
    ) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bot_audit_log (user_id, decision_id, event_type, context, result)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
                    """,
                    user_id, decision_id, event_type,
                    json.dumps(context), json.dumps(result) if result else None,
                )
                return True
        except Exception as e:
            logger.error(f"Erro insert_audit: {e}")
            return False

    async def list_abandoned_checkouts(self, min_age_hours: int = 1) -> List[Dict]:
        """Users com sub pending há mais de X horas e que ainda não receberam recovery.

        Retorna [{user_id, email, full_name, plan, asaas_id}]. O caller é responsável
        por (1) re-checar status antes de enviar e (2) marcar recovery_email_sent_at.
        """
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT u.id AS user_id, u.email, u.full_name,
                           s.plan, s.asaas_id, s.created_at AS sub_created_at
                    FROM users u
                    JOIN subscriptions s ON s.user_id = u.id
                    WHERE s.status = 'pending'
                      AND s.created_at < NOW() - ($1::int * INTERVAL '1 hour')
                      AND u.recovery_email_sent_at IS NULL
                      AND u.is_verified = TRUE
                      AND s.asaas_id IS NOT NULL
                      AND s.asaas_id NOT LIKE 'pending_%'
                    """,
                    min_age_hours,
                )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Erro listando abandoned checkouts: {e}")
            return []

    async def mark_recovery_sent(self, user_id: int) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET recovery_email_sent_at = NOW() WHERE id = $1",
                    user_id,
                )
            return True
        except Exception as e:
            logger.error(f"Erro marcando recovery_sent user {user_id}: {e}")
            return False

    async def get_notifications_paused_until(self, user_id: int) -> Optional[datetime]:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval(
                    "SELECT notifications_paused_until FROM users WHERE id = $1",
                    user_id,
                )
        except Exception as e:
            logger.error(f"Erro buscando paused_until user {user_id}: {e}")
            return None

    async def set_notifications_paused_until(
        self, user_id: int, paused_until: Optional[datetime]
    ) -> bool:
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET notifications_paused_until = $1, updated_at = NOW() WHERE id = $2",
                    paused_until, user_id,
                )
            return True
        except Exception as e:
            logger.error(f"Erro salvando paused_until user {user_id}: {e}")
            return False

    async def list_users_for_broadcast(self) -> List[Dict]:
        """Usuários elegíveis para receber sinais via WhatsApp.

        Critério: (admin OR subscription.status='active' não-expirada)
                  AND verified AND whatsapp não vazio.

        Dedup por whatsapp: se 2 contas compartilham o mesmo número (caso comum
        admin + conta de testes), retorna só UMA entrada — prioriza role=admin,
        depois plan=max, depois plan=pro, depois menor id.

        Retorna [{id, whatsapp, full_name, plan, role}] — o caller decide
        o que enviar com base no plano ('pro' = só corners, 'max' = ambos).
        """
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT u.id, u.whatsapp, u.full_name, u.role,
                           COALESCE(s.plan, 'free') AS plan
                    FROM users u
                    LEFT JOIN subscriptions s ON s.user_id = u.id
                    WHERE u.is_verified = TRUE
                      AND u.whatsapp IS NOT NULL AND u.whatsapp <> ''
                      AND (u.notifications_paused_until IS NULL
                           OR u.notifications_paused_until < NOW())
                      AND (
                          u.role = 'admin'
                          OR (
                              s.status = 'active'
                              AND (s.expires_at IS NULL OR s.expires_at > NOW())
                          )
                      )
                    ORDER BY u.id
                    """
                )
                users = [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Erro ao listar usuários para broadcast: {e}")
            return []

        plan_rank = {"max": 0, "pro": 1, "free": 2}

        def prio(u: Dict) -> tuple:
            return (
                0 if u.get("role") == "admin" else 1,
                plan_rank.get(u.get("plan"), 9),
                u.get("id", 0),
            )

        by_phone: Dict[str, Dict] = {}
        for u in users:
            phone = u.get("whatsapp", "")
            existing = by_phone.get(phone)
            if existing is None or prio(u) < prio(existing):
                by_phone[phone] = u
        return list(by_phone.values())

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
        """Upsert por user_id. Exige unique index em subscriptions(user_id) — criado em init()."""
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO subscriptions (user_id, plan, asaas_id, status, starts_at, expires_at, next_due_date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (user_id) DO UPDATE SET
                        plan=EXCLUDED.plan,
                        asaas_id=EXCLUDED.asaas_id,
                        status=EXCLUDED.status,
                        starts_at=COALESCE(EXCLUDED.starts_at, subscriptions.starts_at),
                        expires_at=COALESCE(EXCLUDED.expires_at, subscriptions.expires_at),
                        next_due_date=COALESCE(EXCLUDED.next_due_date, subscriptions.next_due_date)
                    """,
                    sub.user_id, sub.plan, sub.asaas_id, sub.status,
                    sub.starts_at, sub.expires_at, sub.next_due_date,
                )
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

    async def mark_payment_processed(self, asaas_payment_id: str, event_group: str) -> bool:
        """Marca um payment+grupo como processado. Retorna True se foi novo, False se já existia.

        Usado pelo webhook do Asaas para deduplicar PAYMENT_CONFIRMED + PAYMENT_RECEIVED
        (mesmo grupo 'confirmed') que chegam em sequência com o mesmo payment id e
        disparariam e-mails duplicados. Eventos diferentes para o mesmo payment
        (ex: refunded depois de confirmed) usam grupos distintos e não colidem.
        """
        if not asaas_payment_id:
            return True
        await self.connect()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO processed_payments (asaas_payment_id, event_group)
                    VALUES ($1, $2)
                    ON CONFLICT (asaas_payment_id, event_group) DO NOTHING
                    RETURNING asaas_payment_id
                    """,
                    asaas_payment_id, event_group,
                )
                return row is not None
        except Exception as e:
            logger.error(f"Erro ao marcar payment {asaas_payment_id}/{event_group}: {e}")
            return True

    # --- User Strategy Preferences ---
    VALID_MARKETS = ("corners", "cards")
    VALID_STRATEGIES = ("conservative", "moderate", "aggressive", "brute")
    DEFAULT_STRATEGY = "moderate"

    async def get_user_strategy(self, user_id: int, market: str) -> str:
        """Return the user's strategy tier for the given market.

        Falls back to 'moderate' when no row exists. Raises ValueError on
        unknown market.
        """
        if market not in self.VALID_MARKETS:
            raise ValueError(f"Invalid market: {market}. Must be one of {self.VALID_MARKETS}")
        await self.connect()
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                "SELECT strategy FROM user_strategy_preference WHERE user_id = $1 AND market = $2",
                user_id, market,
            )
        return value if value else self.DEFAULT_STRATEGY

    async def set_user_strategy(self, user_id: int, market: str, strategy: str) -> UserStrategyPreference:
        """Upsert the user's strategy tier for a given market. Returns the saved row."""
        if market not in self.VALID_MARKETS:
            raise ValueError(f"Invalid market: {market}. Must be one of {self.VALID_MARKETS}")
        if strategy not in self.VALID_STRATEGIES:
            raise ValueError(f"Invalid strategy: {strategy}. Must be one of {self.VALID_STRATEGIES}")
        await self.connect()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_strategy_preference (user_id, market, strategy, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id, market) DO UPDATE SET
                    strategy = EXCLUDED.strategy,
                    updated_at = NOW()
                RETURNING user_id, market, strategy, updated_at
                """,
                user_id, market, strategy,
            )
        return UserStrategyPreference(
            user_id=row["user_id"],
            market=row["market"],
            strategy=row["strategy"],
            updated_at=row["updated_at"],
        )

    async def get_user_strategies(self, user_id: int) -> Dict[str, str]:
        """Return a dict {market: strategy} for all markets, filling defaults."""
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT market, strategy FROM user_strategy_preference WHERE user_id = $1",
                user_id,
            )
        result = {market: self.DEFAULT_STRATEGY for market in self.VALID_MARKETS}
        for row in rows:
            result[row["market"]] = row["strategy"]
        return result

    async def get_user_strategy_preference_updated_at(self, user_id: int) -> Optional[datetime]:
        """Latest updated_at across the user's preference rows, or None."""
        await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT MAX(updated_at) FROM user_strategy_preference WHERE user_id = $1",
                user_id,
            )

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

