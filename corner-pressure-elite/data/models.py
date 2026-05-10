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
    media_historica_cartoes: float = 0.0

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
    id: Optional[int] = None
    user_id: int = 0
    corners_strategy: str = "moderate"  # conservative, moderate, aggressive, brute
    cards_strategy: str = "moderate"
    updated_at: datetime = field(default_factory=datetime.now)

