type Signal = {
  teams: string;
  meta: string;
  market: string;
  line: string;
  oldOdd: string;
  newOdd: string;
  delta: string;
};

const SIGNALS: Signal[] = [
  {
    teams: "Man City × Arsenal",
    meta: "Premier League · 67'",
    market: "Escanteios",
    line: "Over 9.5",
    oldOdd: "1.92",
    newOdd: "1.74",
    delta: "+6.3%",
  },
  {
    teams: "Real Madrid × Barça",
    meta: "La Liga · 73'",
    market: "Cartões",
    line: "Over 4.5",
    oldOdd: "2.10",
    newOdd: "1.88",
    delta: "+5.8%",
  },
  {
    teams: "PSG × Marseille",
    meta: "Ligue 1 · 58'",
    market: "Esc. 2º Tempo",
    line: "Over 5.5",
    oldOdd: "2.05",
    newOdd: "1.92",
    delta: "+3.4%",
  },
  {
    teams: "Flamengo × Palmeiras",
    meta: "Brasileirão · 82'",
    market: "Cartões",
    line: "Over 6.5",
    oldOdd: "2.30",
    newOdd: "1.96",
    delta: "+8.1%",
  },
];

export function TerminalCard() {
  return (
    <div
      className="relative overflow-hidden rounded-xl border border-[var(--border-bright)] bg-[var(--bg-card)]"
      style={{
        boxShadow:
          "0 0 0 1px rgba(16, 185, 129, 0.04), 0 24px 64px -16px rgba(0, 0, 0, 0.8)",
      }}
    >
      <span
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at top right, rgba(16, 185, 129, 0.08), transparent 60%)",
        }}
        aria-hidden="true"
      />

      <div className="flex items-center gap-2 border-b border-[var(--border)] bg-black/30 px-4 py-3.5 font-mono">
        <div className="mr-3 flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--red)] opacity-60" />
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--yellow)] opacity-60" />
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--green)] opacity-60" />
        </div>
        <span className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">
          live · sinais em tempo real
        </span>
        <span className="ml-auto flex items-center gap-1.5 text-[10px] text-[var(--green)]">
          <span
            className="h-1.5 w-1.5 rounded-full bg-[var(--green)]"
            style={{
              boxShadow: "0 0 8px var(--green)",
              animation: "pulse-dot 2s infinite",
            }}
          />
          CONECTADO
        </span>
      </div>

      <div className="py-2 font-mono">
        {SIGNALS.map((s, i) => (
          <SignalRow key={i} signal={s} last={i === SIGNALS.length - 1} />
        ))}
      </div>

      <div className="flex items-center justify-between border-t border-[var(--border)] bg-black/30 px-5 py-3 font-mono text-[10px] uppercase tracking-widest text-[var(--text-dim)]">
        <span>último update · há 12s</span>
        <span>·</span>
        <span>4 sinais ativos</span>
      </div>
    </div>
  );
}

function SignalRow({ signal: s, last }: { signal: Signal; last: boolean }) {
  return (
    <div
      className={`group relative grid grid-cols-[auto_1fr_auto] items-center gap-4 px-5 py-3.5 transition-colors hover:bg-[rgba(16,185,129,0.03)] ${
        last ? "" : "border-b border-[rgba(26,26,26,0.5)]"
      }`}
    >
      <span
        className="absolute bottom-0 left-0 top-0 w-0.5 bg-[var(--green)] opacity-0 transition-opacity group-hover:opacity-100"
        aria-hidden="true"
      />
      <div className="flex flex-col gap-0.5">
        <span className="text-[13px] font-semibold tracking-tight text-[var(--text)]">
          {s.teams}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
          {s.meta}
        </span>
      </div>
      <div className="pl-2 text-left text-[12px] text-[var(--text-muted)]">
        <span className="block text-[11px] text-[var(--text-muted)]">{s.market}</span>
        <span className="font-medium text-[var(--text)]">{s.line}</span>
      </div>
      <div className="flex items-center gap-2 text-[13px]">
        <span className="text-[11px] text-[var(--text-dim)] line-through">{s.oldOdd}</span>
        <span className="text-[10px] text-[var(--text-dim)]">→</span>
        <span className="text-[14px] font-bold text-[var(--text)]">{s.newOdd}</span>
        <span className="rounded bg-[rgba(16,185,129,0.1)] px-1.5 py-0.5 text-[11px] font-semibold text-[var(--green)]">
          {s.delta}
        </span>
      </div>
    </div>
  );
}
