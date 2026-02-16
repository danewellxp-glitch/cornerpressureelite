"use client";

import { LiveGame } from "@/lib/api";
import { Badge } from "../ui/Badge";

interface GameCardProps {
  game: LiveGame;
  isObserved?: boolean;
  showLiveBadge?: boolean;
}

export function GameCard({
  game,
  isObserved = false,
  showLiveBadge = false,
}: GameCardProps) {
  return (
    <div
      className={`rounded-xl border p-4 transition-all ${
        isObserved
          ? "border-emerald-500/30 bg-emerald-950/20"
          : "border-white/5 bg-zinc-900/50 hover:border-white/10"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-zinc-100">
            {game.home} vs {game.away}
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <span>⏱️ {game.minuto}&apos;</span>
            <span>|</span>
            <span>📊 {game.placar}</span>
            {typeof game.escanteios === "number" && (
              <>
                <span>|</span>
                <span className="text-cyan-400">⛳ {game.escanteios} esc.</span>
              </>
            )}
          </p>
          {isObserved && (
            <p className="mt-2 text-[10px] text-emerald-400">
              Em observação (sinal enviado)
            </p>
          )}
        </div>
        {showLiveBadge && (
          <span className="flex-shrink-0 animate-pulse rounded bg-red-500/20 px-2 py-0.5 text-[10px] font-medium text-red-400">
            LIVE
          </span>
        )}
      </div>
    </div>
  );
}
