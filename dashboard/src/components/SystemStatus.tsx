"use client";

import { Radio, Database, Wifi, Clock } from "lucide-react";

interface SystemStatusProps {
  apiUsado: string;
  apiLimite: string;
  minutoInicio: number;
  minutoFim: number;
  jogosAoVivo: number;
  jogosNaJanela: number;
  ultimoUpdate?: string;
}

export function SystemStatus({
  apiUsado,
  apiLimite,
  minutoInicio,
  minutoFim,
  jogosAoVivo,
  jogosNaJanela,
  ultimoUpdate,
}: SystemStatusProps) {
  const apiPct =
    apiUsado !== "?" && apiLimite !== "?"
      ? Math.round((parseInt(apiUsado, 10) / parseInt(apiLimite, 10)) * 100)
      : 0;
  const apiColor =
    apiPct < 50 ? "text-emerald-400" : apiPct < 80 ? "text-amber-400" : "text-red-400";

  return (
    <section className="animate-fade-in">
      <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-cyan-400">
        <Radio className="h-5 w-5" />
        Status do sistema
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-4">
          <div className="flex items-center gap-2 text-zinc-500">
            <Wifi className="h-4 w-4" />
            <span className="text-xs uppercase">API Football</span>
          </div>
          <p className={`mt-2 font-mono font-medium ${apiColor}`}>
            {apiUsado}/{apiLimite} req
          </p>
          <p className="text-xs text-zinc-500">Uso: {apiPct}%</p>
        </div>

        <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-4">
          <div className="flex items-center gap-2 text-zinc-500">
            <Clock className="h-4 w-4" />
            <span className="text-xs uppercase">Janela (min)</span>
          </div>
          <p className="mt-2 font-mono font-medium text-white">
            {minutoInicio}–{minutoFim}
          </p>
        </div>

        <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-4">
          <div className="flex items-center gap-2 text-zinc-500">
            <Radio className="h-4 w-4" />
            <span className="text-xs uppercase">Jogos ao vivo</span>
          </div>
          <p className="mt-2 font-mono text-xl font-bold text-cyan-400">
            {jogosAoVivo}
          </p>
        </div>

        <div className="rounded-xl border border-white/5 bg-zinc-900/30 p-4">
          <div className="flex items-center gap-2 text-zinc-500">
            <Database className="h-4 w-4" />
            <span className="text-xs uppercase">Na janela</span>
          </div>
          <p className="mt-2 font-mono text-xl font-bold text-cyan-400">
            {jogosNaJanela}
          </p>
          {ultimoUpdate && (
            <p className="mt-1 text-xs text-zinc-500">Último: {ultimoUpdate}</p>
          )}
        </div>
      </div>
    </section>
  );
}
