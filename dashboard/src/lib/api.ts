const API_BASE = process.env.NEXT_PUBLIC_CPES_API || "/api/cpes";

// ─── Types ──────────────────────────────────────────────────────

export interface DashboardStats {
  total: number;
  greens: number;
  reds: number;
  pendentes: number;
  winrate: number;
  roi_total: number;
}

export interface SystemStatus {
  ciclo: string;
  jogos_ao_vivo: number;
  jogos_na_janela: number;
  api_usado: string;
  api_limite: string;
  ultimo_update: string;
  status_msg: string;
  minuto_inicio?: number;
  minuto_fim?: number;
}

export interface Signal {
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
  tipo_analise?: string;
  matching_tiers?: string[];
}

export interface StrategyPreference {
  corners_strategy: string;
  cards_strategy: string;
  updated_at: string | null;
}

export interface Liga {
  id: number;
  nome: string;
  pais: string;
  media_esperada: number;
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
  cartoes?: number | null;
}

export interface PollingStats {
  jogos_monitorados: number;
  jogos_analisando: number;
  economia_pct: number;
}

export interface DashboardData {
  stats: DashboardStats;
  status: SystemStatus;
  signals: Signal[];
  logs: string[];
  ligas: Liga[];
  live_games?: {
    atualizado: string | null;
    ciclo: number;
    status?: string;
    proximo_jogo_min?: number;
    pre_janela: LiveGame[];
    na_janela: LiveGame[];
    pos_janela: LiveGame[];
    ids_observados: number[];
    polling_stats?: PollingStats;
  };
}

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

export interface UpcomingGame {
  id: number;
  timestamp: number;
  hora_inicio: string;
  minutos_ate: number;
  home: string;
  away: string;
  liga: string;
  placar: string;
  status: string;
}

export interface UpcomingGamesResponse {
  atualizado: string | null;
  proximos: UpcomingGame[];
}

// ─── Fetchers ───────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers,
  });
  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      // Redirecionar para login se token expirou
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      document.cookie = "cpes-auth=; path=/; max-age=0";
      window.location.href = "/login";
    }
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export const fetchDashboard = () => apiFetch<DashboardData>("/dashboard");

export const fetchAudit = () => apiFetch<AuditData>("/audit");

export const fetchStats = (type?: string) =>
  apiFetch<DashboardStats>(type ? `/stats?type=${type}` : "/stats");

export const fetchSignals = (type?: string, limit = 20) =>
  apiFetch<Signal[]>(
    `/signals/recent?limit=${limit}${type ? `&type=${type}` : ""}`
  );

export const fetchUpcomingGames = () =>
  apiFetch<UpcomingGamesResponse>("/upcoming-games");

export const fetchStrategyPreference = () =>
  apiFetch<StrategyPreference>("/user/strategy-preference");

export const updateStrategyPreference = (body: {
  corners_strategy?: string;
  cards_strategy?: string;
}) =>
  apiFetch<StrategyPreference>("/user/strategy-preference", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

// ─── Current User ──────────────────────────────────────────────

export interface CurrentUser {
  user: {
    id: number;
    email: string;
    full_name: string;
    whatsapp: string;
    role: string;
  };
  subscription: {
    valid: boolean;
    plan: string;
    status: string;
    starts_at: string | null;
    expires_at: string | null;
  } | null;
}

export const fetchCurrentUser = () =>
  apiFetch<CurrentUser>("/users/me");

// ─── Notification Settings ──────────────────────────────────────

export interface NotificationSettings {
  paused_until: string | null; // ISO timestamp ou null
}

export const fetchNotificationSettings = () =>
  apiFetch<NotificationSettings>("/user/notifications");

export const updateNotificationSettings = (paused_until: string | null) =>
  apiFetch<NotificationSettings>("/user/notifications", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paused_until }),
  });

// ─── Strategy Performance (hit rate / ROI por tier) ─────────────

export interface TierPerformance {
  tier: string;
  n: number;
  greens: number;
  reds: number;
  hit_rate: number; // 0–1
  roi_pct: number;  // %
}

export interface StrategyPerformance {
  market: "corners" | "cards";
  days: number;
  tiers: Record<string, TierPerformance>;
  cached_at: number;
}

export const fetchStrategyPerformance = (market: "corners" | "cards", days = 30) =>
  apiFetch<StrategyPerformance>(`/stats/strategy-performance?market=${market}&days=${days}`);

// ─── Robô Auto-Aposta ────────────────────────────────────────────

export interface BotConfig {
  enabled: boolean;
  mode: string;
  bet_house: string | null;
  banca_inicial_cents: number;
  banca_atual_cents: number;
  max_loss_per_day_cents: number;
  max_bets_per_day: number;
  unit_pct: number;
  allowed_leagues: number[];
  allowed_markets: string[];
  kill_switch: boolean;
  real_mode_unlocked: boolean;
  accepted_tos_at: string | null;
}

export interface BotCredentialItem {
  bet_house: string;
  status: "unverified" | "valid" | "invalid";
  last_validated_at: string | null;
}

export const fetchBotConfig = () => apiFetch<BotConfig>("/bot/config");

export const patchBotConfig = (patch: Partial<BotConfig>) =>
  apiFetch<BotConfig>("/bot/config", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });

export const acceptBotTos = () =>
  apiFetch<BotConfig>("/bot/tos/accept", { method: "POST" });

export const fetchBotCredentials = () =>
  apiFetch<BotCredentialItem[]>("/bot/credentials");

export const upsertBotCredential = (bet_house: string, username: string, password: string) =>
  apiFetch<{ status: string; bet_house: string }>("/bot/credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bet_house, username, password }),
  });

export const deleteBotCredential = (bet_house: string) =>
  apiFetch<{ status: string }>(`/bot/credentials/${bet_house}`, { method: "DELETE" });

// ─── Bets, PnL, Open ─────────────────────────────────────────────

export interface BetItem {
  id: number;
  signal_id: number | null;
  market: string;
  bet_house: string | null;
  mode: string;
  stake_cents: number;
  odd: number;
  linha: number;
  selecao: string;
  status: string;
  payout_cents: number;
  placed_at: string | null;
  settled_at: string | null;
  jogo_descricao: string | null;
  liga_nome: string | null;
}

export interface BetsPage {
  total: number;
  page: number;
  page_size: number;
  items: BetItem[];
}

export const fetchBotBets = (params: { status?: string; page?: number; page_size?: number } = {}) => {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return apiFetch<BetsPage>(`/bot/bets?${q.toString()}`);
};

export interface BetsPnlSlice {
  n: number;
  wins: number;
  losses: number;
  stake_cents: number;
  payout_cents: number;
  delta_cents: number;
  roi_pct: number;
}

export interface BotPnl {
  days: number;
  today: BetsPnlSlice;
  week: BetsPnlSlice;
  total: BetsPnlSlice;
  series: { date: string; delta_cents: number }[];
  open_count: number;
}

export const fetchBotPnl = (days = 30) =>
  apiFetch<BotPnl>(`/bot/pnl?days=${days}`);

export interface OpenBet {
  id: number;
  signal_id: number | null;
  market: string;
  mode: string;
  stake_cents: number;
  odd: number;
  linha: number;
  selecao: string;
  placed_at: string | null;
  jogo_descricao: string | null;
  liga_nome: string | null;
  minuto: number | null;
  placar: string | null;
}

export const fetchBotOpenBets = () =>
  apiFetch<OpenBet[]>("/bot/open-bets");

// ─── Signals filtered (drawer dos KPI cards) ─────────────────────

export type SignalResult = "all" | "GREEN" | "RED" | "PENDENTE";

export interface SignalDetail {
  id: number;
  timestamp: string | null;
  liga_nome: string | null;
  jogo_descricao: string | null;
  tipo_sinal: string | null;
  pressure_score: number | null;
  projecao: number | null;
  edge: number | null;
  linha: number | null;
  odd: number | null;
  resultado: string;
  escanteios_final: number | null;
  tipo_analise: string;
  matching_tiers: string[];
  minuto: number | null;
  placar: string | null;
  roi: number | null;
}

export const fetchSignalsList = (result: SignalResult = "all", limit = 100) =>
  apiFetch<SignalDetail[]>(`/signals/list?result=${result}&limit=${limit}`);

// ─── User-scoped: stats + signals com decision (Sprint M) ──────

export interface UserStats {
  total: number;
  greens: number;
  reds: number;
  pendentes: number;
  push_void: number;
  winrate: number;       // %
  staked_cents: number;
  pnl_cents: number;
  bonus_total_cents: number;
  roi_pct: number;       // %
  roi_total: number;     // reais (retro-compat)
  avg_odd: number;
  aguardando_decisao: number;
  aguardando_confirmacao: number;
}

export type UserDecisionState = "pending" | "entered" | "skipped";

export type LegMercado =
  | "escanteios"
  | "cartoes"
  | "gols"
  | "1x2"
  | "ambas_marcam"
  | "custom";

export interface DecisionLeg {
  id?: number;
  ordem: number;
  mercado: LegMercado;
  descricao: string;
  linha: number | null;
  odd_leg: number;
  resultado: "GREEN" | "RED" | "PUSH" | "VOID" | null;
}

export interface UserSignalDecision {
  id?: number;
  decision: UserDecisionState;
  odd_entrada: number | null;
  valor_apostado_cents: number | null;
  resultado: "GREEN" | "RED" | "PUSH" | "VOID" | null;
  payout_cents: number | null;
  bonus_pct: number;
  bonus_cents: number;
  is_multi: boolean;
  requires_manual_confirmation: boolean;
  decided_at: string | null;
  settled_at: string | null;
  manually_confirmed_at?: string | null;
  legs: DecisionLeg[];
}

export interface UserSignalDetail {
  signal_id: number;
  timestamp: string | null;
  jogo_descricao: string | null;
  tipo_sinal: string | null;
  pressure_score: number | null;
  projecao: number | null;
  edge: number | null;
  linha: number | null;
  odd: number | null;
  signal_resultado: SignalResult | "PENDENTE";
  escanteios_final: number | null;
  tipo_analise: "ESCANTEIOS" | "CARTOES" | string;
  matching_tiers: string[];
  minuto: number | null;
  placar: string | null;
  is_manual?: boolean;
  decision: UserSignalDecision;
}

export const fetchUserStats = () => apiFetch<UserStats>("/users/me/stats");

export const fetchUserSignals = (limit = 100) =>
  apiFetch<UserSignalDetail[]>(`/users/me/signals?limit=${limit}`);

export interface DecideEnteredBody {
  decision: "entered";
  odd_entrada: number;
  valor_apostado_cents: number;
  bonus_pct?: number;
  legs?: Array<{
    mercado: LegMercado;
    descricao: string;
    linha?: number | null;
    odd_leg: number;
  }>;
}

export const decideSignal = (
  signalId: number,
  body: DecideEnteredBody | { decision: "skipped" },
) =>
  apiFetch<UserSignalDecision & { id: number }>(`/signals/${signalId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

/* ─── Apostas manuais (migration 0017) ─────────────────────────── */

export interface LiveGamesState {
  atualizado: string | null;
  ciclo?: number;
  na_janela: LiveGame[];
  pre_janela: LiveGame[];
  pos_janela: LiveGame[];
}

export const fetchLiveGames = () => apiFetch<LiveGamesState>("/live-games");

export interface ManualBetLeg {
  mercado: "escanteios" | "cartoes";
  descricao: string;
  jogo_id: number;
  linha: number;
  side: "over" | "under";
  odd_leg: number;
}

export interface CreateManualBetBody {
  descricao: string;
  odd_entrada: number;
  valor_apostado_cents: number;
  bonus_pct?: number;
  legs: ManualBetLeg[];
}

export const createManualBet = (body: CreateManualBetBody) =>
  apiFetch<{ id: number; is_multi: boolean; requires_manual_confirmation: boolean }>(
    "/manual-bets",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );

export const confirmManualBet = (
  decisionId: number,
  resultado: "GREEN" | "RED" | "PUSH" | "VOID",
) =>
  apiFetch(`/manual-bets/${decisionId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resultado }),
  });

export const confirmSignalResult = (
  signalId: number,
  resultado: "GREEN" | "RED" | "PUSH" | "VOID",
) =>
  apiFetch<UserSignalDecision & { id: number; banca_credit: unknown }>(
    `/signals/${signalId}/decision/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resultado }),
    },
  );

export const updateSignalBonus = (signalId: number, bonus_pct: number) =>
  apiFetch<UserSignalDecision & { id: number }>(
    `/signals/${signalId}/decision/bonus`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bonus_pct }),
    },
  );

// ─── WhatsApp WAHA health (admin-only) ─────────────────────────

export interface WhatsappHealth {
    status: string;        // ex: "WORKING" | "FAILED" | "UNKNOWN"
    healthy: boolean;
    action_taken: string;  // ex: "never_checked" | "auto_recovered" | "manual_restart"
    details: Record<string, unknown>;
    checked_at?: string;
}

export const fetchWhatsappHealth = () =>
    apiFetch<WhatsappHealth>("/whatsapp/health");

// ─── Polling stats (engine economia) ───────────────────────────

export interface PollingStatsResponse {
    intervalos: Record<string, string>;
    jogos_monitorados: number;
    jogos_analisando: number;
    economia_pct: number;
    destaque: string;
}

export const fetchPollingStats = () =>
    apiFetch<PollingStatsResponse>("/polling-stats");

// ─── Admin Thresholds (admin-only) ─────────────────────────────

export interface ThresholdsConfig {
    min_score_normal?: number;
    min_score_premium?: number;
    min_edge_normal?: number;
    min_edge_premium?: number;
}

export interface ThresholdsResponse {
    thresholds: ThresholdsConfig;
}

export const fetchThresholds = () =>
    apiFetch<ThresholdsResponse>("/config/thresholds");

export const updateThresholds = (body: ThresholdsConfig) =>
    apiFetch<{ status: string; thresholds: ThresholdsConfig }>("/config/thresholds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });

// ─── Dev Test Mode (admin-only) ────────────────────────────────

export interface DevModeConfig {
  enabled: boolean;
  max_games: number;
  polling_interval: number;
  status_check_interval: number;
  api_daily_limit: number;
  normal_polling_interval: number;
  normal_status_check_interval: number;
  normal_api_daily_limit: number;
}

export const fetchDevModeConfig = () =>
  apiFetch<{ config: DevModeConfig }>("/config/dev-mode");

export const updateDevModeConfig = (body: Partial<DevModeConfig>) =>
  apiFetch<{ status: string; config: DevModeConfig }>("/config/dev-mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export async function register(userData: {
  email: string;
  password: string;
  full_name: string;
  whatsapp: string;
  cpf?: string;
}) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(userData),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Erro ao criar conta");
  }
  return res.json(); // { message, email, requires_verification }
}

export async function verifyEmail(email: string, code: string) {
  const res = await fetch(`${API_BASE}/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Código inválido");
  }
  return res.json(); // { access_token, token_type, user }
}

export async function resendVerification(email: string) {
  const res = await fetch(`${API_BASE}/auth/resend-verification`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Erro ao reenviar código");
  }
  return res.json();
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Credenciais inválidas");
  }
  return res.json();
}

export async function checkout(plan: string, token: string, upgrade_from?: string) {
  const res = await fetch(`${API_BASE}/subscriptions/checkout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(upgrade_from ? { plan, upgrade_from } : { plan }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Erro ao criar checkout");
  }
  return res.json();
}

export async function logout() {
  // Client-side logout only for JWT
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

// ─── V2 CLIENT_VISION — Minhas Apostas + Banca ─────────────────

export type BetStatus =
  | "pending_approval"
  | "open"
  | "won"
  | "lost"
  | "rejected"
  | "cashed_out"
  | "canceled"
  | "error";

export type PlacementMode = "manual" | "auto";

export interface MyBet {
  id: number;
  signal_id: number | null;
  market: string;            // 'corners'|'cards'
  bet_house: string | null;
  mode: string;              // 'paper'|'real'
  stake_cents: number;
  odd: number | null;
  linha: number | null;
  selecao: string;
  status: BetStatus;
  payout_cents: number;
  placed_at: string | null;
  settled_at: string | null;
  placement_mode: PlacementMode;
  actual_linha: number | null;
  actual_odd: number | null;
  actual_stake_cents: number | null;
  actual_bet_house: string | null;
  rejection_reason: string | null;
  rejection_tags: string[];
  approved_at: string | null;
  rejected_at: string | null;
  customer_notes: string | null;
  // Joined from signal:
  jogo_descricao: string | null;
  liga_nome: string | null;
  minuto: number | null;
  placar: string | null;
  pressure_score: number | null;
  edge: number | null;
  tipo_sinal: string | null;
  tipo_analise: string | null;
  escanteios_final: number | null;
  signal_resultado: string | null;
}

export interface MyBetsPage {
  total: number;
  page: number;
  page_size: number;
  items: MyBet[];
}

export const fetchMyBets = (params: {
  status?: BetStatus;
  placement_mode?: PlacementMode;
  page?: number;
  page_size?: number;
} = {}) => {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.placement_mode) q.set("placement_mode", params.placement_mode);
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return apiFetch<MyBetsPage>(`/bets?${q.toString()}`);
};

export const fetchMyBet = (id: number) => apiFetch<MyBet>(`/bets/${id}`);

export interface ApprovePayload {
  actual_linha?: number;
  actual_odd?: number;
  actual_stake_cents?: number;
  actual_bet_house?: string;
  customer_notes?: string;
}

export const approveBet = (id: number, body: ApprovePayload) =>
  apiFetch<MyBet>(`/bets/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export interface RejectPayload {
  reason?: string;
  tags?: string[];
}

export const rejectBet = (id: number, body: RejectPayload) =>
  apiFetch<MyBet>(`/bets/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

// ─── Banca ─────────────────────────────────────────────────────

export interface BancaStats {
  settled: number;
  wins: number;
  losses: number;
  opens: number;
  pendings: number;
  rejecteds: number;
  win_rate: number;          // 0..1
  avg_odd: number;
  total_staked_cents: number;
  total_payout_cents: number;
  pnl_cents: number;
  roi_pct: number;           // %
  max_drawdown_cents: number;
}

export interface BancaSummary {
  configured: boolean;
  banca_inicial_cents: number;
  banca_atual_cents: number;
  delta_cents?: number;
  delta_pct?: number;
  unit_pct?: number;
  total_unidades?: number;
  unit_value_cents?: number;
  unidades_disponiveis?: number;
  max_loss_per_day_cents?: number;
  max_bets_per_day?: number;
  stats?: BancaStats;
}

export const fetchBancaSummary = () => apiFetch<BancaSummary>("/banca");

export interface BancaSeriesPoint {
  dia: string;       // ISO date YYYY-MM-DD
  saldo_cents: number;
}

export const fetchBancaSeries = (days = 30) =>
  apiFetch<{ days: number; series: BancaSeriesPoint[] }>(
    `/banca/series?days=${days}`,
  );

export interface BancaMovement {
  id: number;
  tipo: string;
  valor_cents: number;
  saldo_apos_cents: number;
  bet_id: number | null;
  descricao: string | null;
  motivo: string | null;
  created_at: string | null;
}

export interface BancaMovementsPage {
  total: number;
  page: number;
  page_size: number;
  items: BancaMovement[];
}

export const fetchBancaMovements = (params: {
  tipo?: string;
  page?: number;
  page_size?: number;
} = {}) => {
  const q = new URLSearchParams();
  if (params.tipo) q.set("tipo", params.tipo);
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return apiFetch<BancaMovementsPage>(`/banca/movements?${q.toString()}`);
};

export interface SetupBancaPayload {
  initial_cents: number;
  unit_pct?: number;
  total_unidades?: number;
  max_loss_per_day_cents?: number;
  max_bets_per_day?: number;
}

export const setupBanca = (body: SetupBancaPayload) =>
  apiFetch<BancaSummary>("/banca/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const updateBancaUnits = (total_unidades: number) =>
  apiFetch<BancaSummary>("/banca/units", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ total_unidades }),
  });

export interface AddMovementPayload {
  tipo: "deposit" | "withdraw" | "correction";
  valor_cents: number;
  descricao?: string;
  motivo?: string;
}

export const addBancaMovement = (body: AddMovementPayload) =>
  apiFetch<{ movement_id: number; saldo_apos_cents: number }>(
    "/banca/movements",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );

export const resetBanca = (motivo?: string) =>
  apiFetch<BancaSummary>("/banca/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ motivo: motivo ?? null }),
  });

/**
 * Wipe completo: deleta banca + todos movements. Diferente de resetBanca
 * que só zera saldo pro inicial. Use quando user quer recomeçar do zero
 * (re-setup com valor diferente, sair da feature, etc.).
 */
export const deleteBanca = () =>
  apiFetch<{ deleted: boolean; configured: false }>("/banca", {
    method: "DELETE",
  });
