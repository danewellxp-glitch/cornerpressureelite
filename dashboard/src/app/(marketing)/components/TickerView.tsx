"use client";

import type { LiveGame, RecentSignal } from "../lib/ticker-api";

type TickerItem =
  | { kind: "live"; game: LiveGame }
  | { kind: "signal"; signal: RecentSignal }
  | { kind: "static"; label: string; value: string };

function fmtDeltaSignal(odd: number | null, delta: number | null): string {
  if (delta !== null) {
    const sign = delta >= 0 ? "+" : "";
    return `${sign}${delta.toFixed(1)}%`;
  }
  if (odd !== null) return `@${odd.toFixed(2)}`;
  return "";
}

function interleave(live: LiveGame[], signals: RecentSignal[]): TickerItem[] {
  const items: TickerItem[] = [];
  const max = Math.max(live.length, signals.length);
  for (let i = 0; i < max; i++) {
    if (live[i]) items.push({ kind: "live", game: live[i] });
    if (signals[i]) items.push({ kind: "signal", signal: signals[i] });
  }
  return items;
}

export function TickerView({
  live,
  signals,
}: {
  live: LiveGame[];
  signals: RecentSignal[];
}) {
  const items = interleave(live, signals);
  // Duplica para animação infinita sem gap visível
  const loop = [...items, ...items];

  return (
    <div className="relative z-50 hidden h-7 items-center overflow-hidden border-b border-[var(--border)] bg-[var(--bg)] font-mono text-[11px] font-medium tracking-wide sm:flex">
      <div
        className="flex shrink-0 gap-12 whitespace-nowrap pl-[100vw]"
        style={{ animation: "ticker-scroll 60s linear infinite" }}
      >
        {loop.map((item, i) => (
          <TickerItemView key={i} item={item} />
        ))}
      </div>
    </div>
  );
}

function TickerItemView({ item }: { item: TickerItem }) {
  if (item.kind === "live") {
    const g = item.game;
    const score =
      g.pressure_score ?? g.tension_score
        ? `+${(g.pressure_score ?? g.tension_score ?? 0).toString()}`
        : null;
    return (
      <span className="inline-flex items-center gap-2 text-[var(--text-muted)]">
        <span
          className="h-1 w-1 rounded-full bg-[var(--green)]"
          style={{
            boxShadow: "0 0 8px var(--green)",
            animation: "pulse-dot 2s ease-in-out infinite",
          }}
        />
        <span className="text-[10px] uppercase text-[var(--text-dim)]">LIVE</span>
        <span className="text-[var(--text)]">{g.match}</span>
        <span className="text-[var(--text-muted)]">{g.minute}'</span>
        {score && <span className="font-semibold text-[var(--green)]">{score}</span>}
      </span>
    );
  }

  if (item.kind === "signal") {
    const s = item.signal;
    return (
      <span className="inline-flex items-center gap-2 text-[var(--text-muted)]">
        <span className="text-[10px] uppercase text-[var(--text-dim)]">SINAL</span>
        <span className="text-[var(--text)]">{s.market}</span>
        <span className="font-semibold text-[var(--green)]">
          {fmtDeltaSignal(s.odd, s.delta_pct)}
        </span>
        {s.result && (
          <span
            className={
              s.result === "GREEN" ? "text-[var(--green)]" : "text-[var(--red)]"
            }
          >
            {s.result === "GREEN" ? "🟢" : "🔴"}
          </span>
        )}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-2 text-[var(--text-muted)]">
      <span className="text-[10px] uppercase text-[var(--text-dim)]">{item.label}</span>
      <span className="text-[var(--text)]">{item.value}</span>
    </span>
  );
}

export function TickerFallback() {
  return (
    <div className="relative z-50 hidden h-7 items-center overflow-hidden border-b border-[var(--border)] bg-[var(--bg)] px-8 font-mono text-[11px] font-medium tracking-wide text-[var(--text-muted)] sm:flex">
      <span className="inline-flex items-center gap-2">
        <span
          className="h-1 w-1 rounded-full bg-[var(--green)]"
          style={{
            boxShadow: "0 0 8px var(--green)",
            animation: "pulse-dot 2s ease-in-out infinite",
          }}
        />
        <span className="text-[10px] uppercase text-[var(--text-dim)]">SISTEMA</span>
        <span className="text-[var(--text)]">9 ligas monitoradas · dados em atualização</span>
      </span>
    </div>
  );
}
