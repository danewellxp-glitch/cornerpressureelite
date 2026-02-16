"use client";

import { Zap } from "lucide-react";
import { Badge } from "./ui/Badge";

interface Signal {
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
}

interface RecentSignalsProps {
  signals: Signal[];
}

function ResultBadge({ resultado, escanteios_final }: { resultado: string; escanteios_final: number | null }) {
  if (resultado === "GREEN")
    return <Badge variant="green">✅ GREEN | {escanteios_final}esc</Badge>;
  if (resultado === "RED")
    return <Badge variant="red">❌ RED | {escanteios_final}esc</Badge>;
  return <Badge variant="pending">⏳ Pendente</Badge>;
}

export function RecentSignals({ signals }: RecentSignalsProps) {
  return (
    <section className="animate-fade-in">
      <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-cyan-400">
        <Zap className="h-5 w-5" />
        Sinais recentes
      </h2>
      <div className="space-y-3">
        {signals.length === 0 ? (
          <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-8 text-center">
            <p className="text-sm text-zinc-500">
              Nenhum sinal registrado ainda
            </p>
          </div>
        ) : (
          signals.map((s, i) => (
            <div
              key={i}
              className="rounded-xl border border-white/5 bg-zinc-900/30 p-4 transition-all hover:border-cyan-500/20"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span
                  className={
                    s.tipo_sinal === "PREMIUM"
                      ? "text-fuchsia-400"
                      : "text-cyan-400"
                  }
                >
                  {s.tipo_sinal === "PREMIUM" ? "🔥 PREMIUM" : "⚡ NORMAL"}
                </span>
                <span className="text-xs text-zinc-500">
                  {s.timestamp.length > 19 ? s.timestamp.slice(11, 19) : s.timestamp}
                </span>
              </div>
              <p className="mt-2 truncate font-medium text-zinc-200">
                {s.jogo_descricao}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-zinc-400">
                <span>Score: {s.pressure_score}</span>
                <span>Proj: {s.projecao ?? "-"}</span>
                <span>Linha: {s.linha ?? "-"}</span>
                <span>Odd: {s.odd ? `${s.odd.toFixed(2)}x` : "-"}</span>
                <span>
                  Edge:{" "}
                  {s.edge != null
                    ? (s.edge >= 0 ? `+${s.edge.toFixed(2)}` : s.edge.toFixed(2))
                    : "-"}
                </span>
              </div>
              <div className="mt-3">
                <ResultBadge resultado={s.resultado} escanteios_final={s.escanteios_final} />
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
