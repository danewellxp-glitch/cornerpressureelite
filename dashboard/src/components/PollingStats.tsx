"use client";

import { BarChart3 } from "lucide-react";

interface PollingStatsProps {
  jogosMonitorados?: number;
  jogosAnalisando?: number;
  economiaPct?: number;
}

export function PollingStats({
  jogosMonitorados = 0,
  jogosAnalisando = 0,
  economiaPct = 0,
}: PollingStatsProps) {
  return (
    <section className="animate-fade-in">
      <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-cyan-400">
        <BarChart3 className="h-5 w-5" />
        Estatísticas de polling
      </h2>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-4">
          <p className="text-xs uppercase text-zinc-500">Jogos monitorados</p>
          <p className="mt-2 text-2xl font-bold text-white">
            {jogosMonitorados.toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-4">
          <p className="text-xs uppercase text-zinc-500">Economia</p>
          <p className="mt-2 text-2xl font-bold text-emerald-400">
            {economiaPct}%
          </p>
          <p className="text-xs text-zinc-500">Requisições economizadas</p>
        </div>
        <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-4">
          <p className="text-xs uppercase text-zinc-500">Analisando agora</p>
          <p className="mt-2 text-2xl font-bold text-cyan-400">
            {jogosAnalisando}
          </p>
        </div>
      </div>
    </section>
  );
}
