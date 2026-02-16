"use client";

import { Activity } from "lucide-react";
import { LiveGame } from "@/lib/api";
import { GameCard } from "./GameCard";

interface LiveGamesSectionProps {
  preJanela: LiveGame[];
  naJanela: LiveGame[];
  posJanela: LiveGame[];
  idsObservados: number[];
}

const phaseConfig = {
  pre_janela: {
    title: "Aguardando janela (0-50 min)",
    subtitle: "0-30: 5 min | 31-50: 3 min (ou 1 min se 7+ esc)",
    color: "border-amber-500/30 bg-amber-950/20",
    headerColor: "text-amber-400",
  },
  na_janela: {
    title: "Na janela (50-90 min)",
    subtitle: "Sendo analisados · 1 min",
    color: "border-emerald-500/30 bg-emerald-950/20",
    headerColor: "text-emerald-400",
  },
  pos_janela: {
    title: "Após janela (90+ min)",
    subtitle: "Reta final · 30 seg",
    color: "border-cyan-500/30 bg-cyan-950/20",
    headerColor: "text-cyan-400",
  },
} as const;

function PhaseBlock({
  phase,
  games,
  idsObservados,
  showLiveBadge,
}: {
  phase: keyof typeof phaseConfig;
  games: LiveGame[];
  idsObservados: number[];
  showLiveBadge: boolean;
}) {
  const config = phaseConfig[phase];

  return (
    <div className={`rounded-xl border p-5 ${config.color}`}>
      <h3 className={`mb-1 text-sm font-semibold ${config.headerColor}`}>
        {config.title}
      </h3>
      <p className="mb-4 text-xs text-zinc-500">{config.subtitle}</p>
      <div className="space-y-3 max-h-64 overflow-y-auto">
        {games.length === 0 ? (
          <p className="py-4 text-center text-sm text-zinc-600">
            Nenhum jogo nesta fase
          </p>
        ) : (
          games.map((j) => (
            <GameCard
              key={j.id}
              game={j}
              isObserved={idsObservados.includes(j.id)}
              showLiveBadge={showLiveBadge && phase === "na_janela"}
            />
          ))
        )}
      </div>
    </div>
  );
}

export function LiveGamesSection({
  preJanela,
  naJanela,
  posJanela,
  idsObservados,
}: LiveGamesSectionProps) {
  return (
    <section className="animate-fade-in">
      <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-cyan-400">
        <Activity className="h-5 w-5" />
        Jogos ao vivo (por fase)
      </h2>
      <div className="grid gap-6 lg:grid-cols-3">
        <PhaseBlock
          phase="pre_janela"
          games={preJanela}
          idsObservados={idsObservados}
          showLiveBadge={true}
        />
        <PhaseBlock
          phase="na_janela"
          games={naJanela}
          idsObservados={idsObservados}
          showLiveBadge={true}
        />
        <PhaseBlock
          phase="pos_janela"
          games={posJanela}
          idsObservados={idsObservados}
          showLiveBadge={true}
        />
      </div>
    </section>
  );
}
