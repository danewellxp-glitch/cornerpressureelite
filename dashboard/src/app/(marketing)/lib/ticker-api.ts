export interface LiveGame {
  match: string;
  league: string;
  minute: number;
  score: string;
  pressure_score: number | null;
  tension_score: number | null;
}

export interface RecentSignal {
  emitted_at: string;
  match: string;
  league: string;
  market: string;
  odd: number | null;
  delta_pct: number | null;
  result: "GREEN" | "RED" | null;
}

export interface TickerResponse {
  generated_at: string;
  live: LiveGame[];
  recent_signals: RecentSignal[];
}

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production"
    ? "https://api.iqpressure.online"
    : "http://localhost:8000");

export async function getTicker(): Promise<TickerResponse | null> {
  try {
    const res = await fetch(`${API_URL}/api/v1/public/ticker`, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;
    return (await res.json()) as TickerResponse;
  } catch {
    return null;
  }
}
