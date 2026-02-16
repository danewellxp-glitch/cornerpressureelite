"use client";

import Link from "next/link";
import { Target, RotateCw, Settings } from "lucide-react";
import { StatusIndicator } from "./ui/StatusIndicator";
import { Badge } from "./ui/Badge";

interface HeaderProps {
  isOnline: boolean;
  ciclo: string;
  statusMsg?: string;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export function Header({
  isOnline,
  ciclo,
  statusMsg,
  onRefresh,
  isRefreshing = false,
}: HeaderProps) {
  return (
    <header className="border-b border-white/5 bg-[#111]/90 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-500/10">
                <Target className="h-7 w-7 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
                  CORNER PRESSURE ELITE SYSTEM
                </h1>
                <p className="mt-1 text-sm text-zinc-400">
                  Sistema de análise automatizada de escanteios
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <StatusIndicator online={isOnline} />
                <span className="text-sm text-zinc-300">
                  {isOnline ? "Online" : "Offline"}
                </span>
              </div>
              <span className="text-zinc-600">|</span>
              <span className="text-sm text-zinc-400">Ciclo #{ciclo}</span>
              <span className="text-zinc-600">|</span>
              <span className="text-sm text-zinc-400">Polling: 10s</span>
            </div>
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-cyan-500/10 hover:border-cyan-500/30 disabled:opacity-50"
            >
              <RotateCw
                className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
              Atualizar
            </button>
            <Link
              href="/settings"
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-green-500/10 hover:border-green-500/30"
            >
              <Settings className="h-4 w-4" />
              Configurações
            </Link>
          </div>
        </div>

        {statusMsg && (
          <div className="mt-4">
            <Badge variant="pending">{statusMsg}</Badge>
          </div>
        )}
      </div>
    </header>
  );
}
