// Proxy Next.js: /api/cpes -> localhost:8000 (ver next.config.ts)
const API_BASE = process.env.NEXT_PUBLIC_CPES_API || "/api/cpes";

export interface DashboardData {
  stats: {
    total: number;
    greens: number;
    reds: number;
    pendentes: number;
    winrate: number;
    roi_total: number;
  };
  status: {
    ciclo: string;
    jogos_ao_vivo: number;
    jogos_na_janela: number;
    api_usado: string;
    api_limite: string;
    ultimo_update: string;
    status_msg: string;
    minuto_inicio?: number;
    minuto_fim?: number;
  };
  signals: Array<{
    timestamp: string;
    jogo_descricao: string;
    tipo_sinal: string;
    pressure_score: number;
    projecao: number | null;
    edge: number | null;
    linha: number | null;
    resultado: string;
  }>;
  logs: string[];
  ligas: Array<{
    id: number;
    nome: string;
    pais: string;
    media_esperada: number;
  }>;
  live_games?: {
    atualizado: string | null;
    ciclo: number;
    pre_janela: LiveGame[];
    na_janela: LiveGame[];
    pos_janela: LiveGame[];
    ids_observados: number[];
  };
}

export interface LiveGame {
  id: number;
  home: string;
  away: string;
  liga: string;
  minuto: number;
  placar: string;
  fase: string;
  escanteios?: number | null;
}

export async function fetchDashboard(): Promise<DashboardData> {
  const url = API_BASE.startsWith("http") ? `${API_BASE}/api/dashboard` : `${API_BASE}/dashboard`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
