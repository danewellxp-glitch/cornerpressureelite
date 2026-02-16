"use client";

import { Globe } from "lucide-react";

interface Liga {
  id: number;
  nome: string;
  pais: string;
  media_esperada: number;
}

interface MonitoredLeaguesProps {
  ligas: Liga[];
}

const countryFlags: Record<string, string> = {
  England: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  Germany: "🇩🇪",
  Brazil: "🇧🇷",
  Argentina: "🇦🇷",
  Chile: "🇨🇱",
};

export function MonitoredLeagues({ ligas }: MonitoredLeaguesProps) {
  return (
    <section className="animate-fade-in">
      <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-cyan-400">
        <Globe className="h-5 w-5" />
        Ligas monitoradas
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {ligas.map((l) => (
          <div
            key={l.id}
            className="rounded-xl border border-white/5 bg-zinc-900/30 p-4 transition-all hover:border-cyan-500/20"
          >
            <div className="flex items-center gap-2">
              <span className="text-lg">
                {countryFlags[l.pais] ?? "🌍"}
              </span>
              <div>
                <p className="font-medium text-zinc-200">{l.nome}</p>
                <p className="text-xs text-zinc-500">{l.pais}</p>
              </div>
            </div>
            <p className="mt-2 text-xs text-zinc-400">
              📊 Média: {l.media_esperada} escanteios
            </p>
            <span className="mt-2 inline-block text-[10px] text-emerald-500">
              ✅ Ativa
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
