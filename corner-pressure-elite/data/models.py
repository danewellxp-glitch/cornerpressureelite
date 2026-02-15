from dataclasses import dataclass, field
from typing import Optional
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

    # Estatisticas recentes (ultimos 10 min)
    escanteios_ultimos_10min: int = 0
    escanteios_ultimos_5min: int = 0
    ataques_perigosos_ultimos_10min: int = 0
    posse_ultimos_10min: float = 0.0
    finalizacoes_recentes: int = 0

    # Historico
    media_historica_combinada: float = 0.0

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

    # Dados do momento do primeiro alerta (para re-avaliacao)
    primeiro_minuto: Optional[int] = None
    primeiro_escanteios: Optional[int] = None
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
    tipo_sinal: str = ""
    reavaliacao: bool = False
    resultado: Optional[str] = None  # 'GREEN', 'RED', None
    escanteios_final: Optional[int] = None
    roi: Optional[float] = None
