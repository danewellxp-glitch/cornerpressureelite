from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class JogoAoVivo:
    id: int
    liga_id: int
    liga_nome: str
    time_casa: str
    time_fora: str
    placar_casa: int
    placar_fora: int
    minuto: int
    escanteios_total: int
    escanteios_casa: int
    escanteios_fora: int

    # Mercado
    linha_atual: float = 0.0
    odd_atual: float = 0.0
    odd_betano: float = 0.0   # Betano (bookmaker 46)
    odd_bet365: float = 0.0   # Bet365 (bookmaker 8)
    # Rastreabilidade (2026-05-11): de onde veio a linha + linhas alternativas
    bookmaker_usado: str = ""  # 'betano' | 'bet365' | 'consolidada' | ''
    linha_betano: float = 0.0
    linha_bet365: float = 0.0
    # Fonte única quando o CompositeOddsProvider é usado (USE_BETANO_BRIDGE):
    # 'betano_bridge' | 'apifootball'. None = caminho legado multi-bookmaker.
    odds_source: Optional[str] = None
    # P4-B (2026-05-17): flags de cache stale — bloqueia emit quando True
    # (decision_engine não envia WhatsApp com odds stale, só persiste telemetria)
    odds_is_stale: bool = False
    odds_age_seconds: int = 0
    odds_is_stale_cartoes: bool = False
    odds_age_seconds_cartoes: int = 0

    # Estatisticas recentes (ultimos 10 min)
    escanteios_ultimos_10min: int = 0
    escanteios_ultimos_5min: int = 0
    ataques_perigosos_ultimos_10min: int = 0
    posse_ultimos_10min: float = 0.0
    finalizacoes_recentes: int = 0

    # Historico
    media_historica_combinada: float = 0.0

    # --- Cartoes ---
    cartoes_amarelos_total: int = 0
    cartoes_amarelos_casa: int = 0
    cartoes_amarelos_fora: int = 0
    cartoes_vermelhos_total: int = 0
    cartoes_vermelhos_casa: int = 0
    cartoes_vermelhos_fora: int = 0
    cartoes_ultimos_5min: int = 0
    cartoes_ultimos_10min: int = 0
    faltas_total: int = 0
    faltas_casa: int = 0
    faltas_fora: int = 0
    linha_cartoes: float = 0.0
    odd_cartoes: float = 0.0
    # Fonte única das odds de cartões quando via CompositeOddsProvider.
    odds_source_cartoes: Optional[str] = None
    media_historica_cartoes: float = 0.0

    # Kickoff (origem API-Football fixture.date, ISO 8601). Usado pelos
    # providers Betano/Sportradar (Fase B/C) para mapear fixture→event_id por
    # janela de horário.
    kickoff_at: Optional[datetime] = None

    @property
    def descricao(self) -> str:
        return f"{self.time_casa} vs {self.time_fora}"

    @property
    def placar(self) -> str:
        return f"{self.placar_casa}-{self.placar_fora}"

    @property
    def diferenca_gols(self) -> int:
        return abs(self.placar_casa - self.placar_fora)


@dataclass
class Sinal:
    tipo: str  # 'NORMAL' ou 'PREMIUM'
    jogo: JogoAoVivo
    pressure_score: int
    projecao: float
    edge: float
    timestamp: datetime = field(default_factory=datetime.now)
    reavaliacao: bool = False
    matching_tiers: List[str] = field(default_factory=list)

    # Dados do momento do primeiro alerta (para re-avaliacao)
    primeiro_minuto: Optional[int] = None
    primeiro_escanteios: Optional[int] = None
    primeiro_linha: Optional[float] = None
    primeiro_projecao: Optional[float] = None
    primeiro_edge: Optional[float] = None
    primeiro_score: Optional[int] = None


@dataclass
class SinalCartoes:
    tipo: str  # 'NORMAL' ou 'PREMIUM'
    jogo: JogoAoVivo
    tension_score: int
    projecao_cartoes: float
    edge: float
    timestamp: datetime = field(default_factory=datetime.now)
    reavaliacao: bool = False
    matching_tiers: List[str] = field(default_factory=list)

    # Dados do momento do primeiro alerta
    primeiro_minuto: Optional[int] = None
    primeiro_cartoes: Optional[int] = None
    primeiro_linha: Optional[float] = None
    primeiro_projecao: Optional[float] = None
    primeiro_edge: Optional[float] = None
    primeiro_score: Optional[int] = None


@dataclass
class RegistroSinal:
    """Registro persistido no banco de dados."""
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    liga_id: int = 0
    liga_nome: str = ""
    jogo_id: int = 0
    jogo_descricao: str = ""
    minuto: int = 0
    placar: str = ""
    escanteios_total: int = 0
    linha: float = 0.0
    odd: float = 0.0
    projecao: float = 0.0
    edge: float = 0.0
    pressure_score: int = 0
    tipo_sinal: str = "NORMAL"
    resultado: Optional[str] = None
    escanteios_final: Optional[int] = None
    roi: Optional[float] = None
    tipo_analise: str = "ESCANTEIOS"


@dataclass
class OddsAoVivo:
    """Odds ao vivo para um jogo (escanteios)."""
    fixture_id: int
    linha: float
    odd_over: float
    odd_under: float
    bookmaker: str
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def implicito_under(self) -> float:
        """Probabilidade implícita do Under (1 / odd_under)."""
        return round(1 / self.odd_under * 100, 1) if self.odd_under > 0 else 0

    @property
    def implicito_over(self) -> float:
        """Probabilidade implícita do Over (1 / odd_over)."""
        return round(1 / self.odd_over * 100, 1) if self.odd_over > 0 else 0


@dataclass
class ResultadoJogo:
    """Resultado final de um jogo."""
    fixture_id: int
    escanteios_totais: int
    placar_final: dict  # {"home": 2, "away": 1}
    status: str  # "FT", "AET", "PEN"
    timestamp: datetime = field(default_factory=datetime.now)

    def resultado_signal(self, linha_apoio: float) -> str:
        """Retorna 'GREEN' se escanteios_totais > linha_apoio, 'RED' caso contrario."""
        return "GREEN" if self.escanteios_totais > linha_apoio else "RED"
    edge: float = 0.0
    pressure_score: int = 0
    tipo_sinal: str = ""
    reavaliacao: bool = False
    resultado: Optional[str] = None  # 'GREEN', 'RED', None
    escanteios_final: Optional[int] = None
    roi: Optional[float] = None


@dataclass
class User:
    id: Optional[int] = None
    email: str = ""
    password_hash: str = ""
    full_name: str = ""
    whatsapp: str = ""
    cpf: str = ""
    role: str = "user"  # 'user', 'admin'
    is_verified: bool = False
    verification_code: Optional[str] = None
    verification_expires_at: Optional[datetime] = None
    verification_attempts: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Subscription:
    id: Optional[int] = None
    user_id: int = 0
    plan: str = "basic"  # 'basic', 'max' (or 'pro')
    asaas_id: str = ""
    status: str = "pending"  # 'pending', 'active', 'overdue', 'canceled'
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    next_due_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class UserStrategyPreference:
    user_id: int = 0
    strategy: str = "moderate"  # conservative, moderate, aggressive, brute
    market: str = "corners"     # corners, cards
    updated_at: datetime = field(default_factory=datetime.now)


# ============= Robô Auto-Aposta =============

@dataclass
class BotConfig:
    user_id: int = 0
    enabled: bool = False
    mode: str = "paper"  # 'paper' | 'real'
    bet_house: Optional[str] = None  # 'betano' | 'bet365' | 'kto'
    banca_inicial_cents: int = 0
    banca_atual_cents: int = 0
    max_loss_per_day_cents: int = 0
    max_bets_per_day: int = 0
    unit_pct: float = 0.01
    allowed_leagues: list = field(default_factory=list)
    allowed_markets: list = field(default_factory=list)
    kill_switch: bool = False
    real_mode_unlocked: bool = False
    accepted_tos_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class BetHouseCredential:
    user_id: int = 0
    bet_house: str = ""
    username_ct: bytes = b""
    password_ct: bytes = b""
    nonce: bytes = b""
    last_validated_at: Optional[datetime] = None
    status: str = "unverified"  # 'unverified' | 'valid' | 'invalid'


@dataclass
class Bet:
    id: Optional[int] = None
    user_id: int = 0
    signal_id: Optional[int] = None
    market: str = ""  # 'corners' | 'cards'
    bet_house: Optional[str] = None  # None = paper
    bet_house_bet_id: Optional[str] = None
    mode: str = "paper"  # 'paper' | 'real'
    stake_cents: int = 0
    odd: float = 0.0
    linha: float = 0.0
    selecao: str = ""  # 'over' | 'under'
    status: str = "open"  # open | won | lost | cashed_out | error | canceled
    payout_cents: int = 0
    placed_at: datetime = field(default_factory=datetime.now)
    settled_at: Optional[datetime] = None

