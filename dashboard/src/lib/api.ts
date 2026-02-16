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
    odd: number | null;
    resultado: string;
    escanteios_final: number | null;
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
    status?: string;
    proximo_jogo_min?: number;
    pre_janela: LiveGame[];
    na_janela: LiveGame[];
    pos_janela: LiveGame[];
    ids_observados: number[];
    polling_stats?: {
      jogos_monitorados: number;
      jogos_analisando: number;
      economia_pct: number;
    };
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

// --- Audit Types ---
export interface AuditGameDetail {
  descricao: string;
  liga: string;
  minuto: number;
  placar: string;
  escanteios_total: number;
  escanteios_casa: number;
  escanteios_fora: number;
  corner_rate: number;
  est_5min: number;
  est_10min: number;
  ataques: number;
  posse: number;
  finalizacoes: number;
  linha: number;
  odd: number;
  pressure_score: number | null;
  projecao: number | null;
  edge: number | null;
  status: string;
  motivo: string | null;
}

export interface AuditData {
  atualizado: string | null;
  ciclo: number;
  funil: {
    total_analisados: number;
    passou_filtros: number;
    score_ok: number;
    edge_ok: number;
    sinais_emitidos: number;
    premium: number;
    normal: number;
  };
  filtros_breakdown: Record<string, number>;
  jogos: AuditGameDetail[];
  taxas: {
    elegibilidade: number;
    conversao_score: number;
    conversao_edge: number;
    hit_rate: number;
  };
  sinais_hoje: {
    total: number;
    greens: number;
    reds: number;
    pendentes: number;
    winrate: number;
    roi_total: number;
  };
  historico_7d: Array<{
    dia: string;
    total: number;
    premium: number;
    normal: number;
    greens: number;
    reds: number;
    roi: number;
  }>;
  config: {
    min_score_normal: number;
    min_score_premium: number;
    min_edge_normal: number;
    min_edge_premium: number;
  };
}

export async function fetchAudit(): Promise<AuditData> {
  const url = `${API_BASE}/audit`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error: ${res.status} ${res.statusText} - ${text}`);
  }
  return res.json();
}

export async function fetchDashboard(): Promise<DashboardData> {
  // Constrói URL corretamente:
  // - Em desenvolvimento: /api/cpes/dashboard → reescrita para http://localhost:8000/api/dashboard
  // - Em produção: /api/cpes/dashboard → reescrita para a API do backend
  const url = `${API_BASE}/dashboard`;
  
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API error: ${res.status} ${res.statusText} - ${text}`);
    }
    const data = await res.json();
    
    // Debug: verificar dados recebidos
    if (!data || !data.stats) {
      console.error("Resposta inválida da API:", data);
      throw new Error("Resposta da API sem campos esperados (stats)");
    }
    
    return data;
  } catch (error) {
    console.error("Erro ao buscar dashboard:", error);
    throw error;
  }
}
