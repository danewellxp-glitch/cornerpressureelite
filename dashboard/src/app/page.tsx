"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchDashboard, type DashboardData } from "@/lib/api";
import { Header } from "@/components/Header";
import { MetricCard } from "@/components/MetricCard";
import { LiveGamesSection } from "@/components/LiveGames/LiveGamesSection";
import { RecentSignals } from "@/components/RecentSignals";
import { MonitoredLeagues } from "@/components/MonitoredLeagues";
import { SystemStatus } from "@/components/SystemStatus";
import { SystemLogs } from "@/components/SystemLogs";
import { PollingStats } from "@/components/PollingStats";
import { AuditPanel } from "@/components/AuditPanel";
import { UpcomingGames } from "@/components/UpcomingGames";
import {
  BarChart3,
  CheckCircle2,
  XCircle,
  Clock,
  Target,
  TrendingUp,
  Flame,
  Zap,
} from "lucide-react";

function useDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    try {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else if (!data) setLoading(true);
      const d = await fetchDashboard();
      if (!d || !d.stats) {
        setError("Resposta inválida da API: sem dados de stats");
        setData(null);
      } else {
        setData(d);
      }
    } catch (e) {
      console.error("Erro ao carregar dashboard:", e);
      setError(e instanceof Error ? e.message : "Erro ao carregar dados");
      setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [data]);

  useEffect(() => {
    load();
    const id = setInterval(() => load(true), 10000);
    return () => clearInterval(id);
  }, [load]);

  return { data, error, loading, refreshing, refresh: load };
}

export default function DashboardPage() {
  const { data, error, loading, refreshing, refresh } = useDashboard();

  // Estado de carregamento
  if (loading && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
          <p className="text-zinc-400">Carregando CPES...</p>
        </div>
      </div>
    );
  }

  // Estado de erro
  if (error || !data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-[#0a0a0a] px-4">
        <p className="text-center text-red-400">
          {error || "Erro ao carregar dados"}
        </p>
        <p className="max-w-md text-center text-sm text-zinc-500">
          Verifique se o backend está rodando em localhost:8000 e a API está respondendo.
        </p>
        <button
          onClick={() => refresh(true)}
          className="rounded-lg bg-cyan-600 px-6 py-3 font-medium text-white transition-colors hover:bg-cyan-500"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  // Se chegou aqui, data é garantido não-null
  const stats = data.stats;
  const status = data.status;
  const liveGames = data.live_games;
  const pollingStats = liveGames?.polling_stats;

  const greensPct =
    stats.total > 0 ? ((stats.greens / stats.total) * 100).toFixed(1) : "0";
  const redsPct =
    stats.total > 0 ? ((stats.reds / stats.total) * 100).toFixed(1) : "0";
  const pendentesPct =
    stats.total > 0 ? ((stats.pendentes / stats.total) * 100).toFixed(1) : "0";

  const recentSignals = data.signals;
  const premiumRecent = recentSignals.filter((s) => s.tipo_sinal === "PREMIUM").length;
  const normalRecent = recentSignals.filter((s) => s.tipo_sinal === "NORMAL").length;
  const recentTotal = recentSignals.length;
  const tipoPremiumPct =
    recentTotal > 0 ? ((premiumRecent / recentTotal) * 100).toFixed(1) : "0";
  const tipoNormalPct =
    recentTotal > 0 ? ((normalRecent / recentTotal) * 100).toFixed(1) : "0";

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Header
        isOnline={!!data}
        ciclo={status.ciclo}
        statusMsg={status.status_msg || undefined}
        onRefresh={() => refresh(true)}
        isRefreshing={refreshing}
      />

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* KPI Cards */}
        <section className="mb-10">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              icon={BarChart3}
              label="Sinais total"
              value={stats.total}
              subValue="100%"
            />
            <MetricCard
              icon={CheckCircle2}
              label="Greens"
              value={stats.greens}
              subValue={`${greensPct}%`}
              variant="green"
            />
            <MetricCard
              icon={XCircle}
              label="Reds"
              value={stats.reds}
              subValue={`${redsPct}%`}
              variant="red"
            />
            <MetricCard
              icon={Clock}
              label="Pendentes"
              value={stats.pendentes}
              subValue={`${pendentesPct}%`}
              variant="amber"
            />
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              icon={Target}
              label="Winrate"
              value={`${stats.winrate}%`}
              variant={
                stats.winrate >= 60
                  ? "green"
                  : stats.winrate >= 50
                    ? "amber"
                    : "red"
              }
            />
            <MetricCard
              icon={TrendingUp}
              label="ROI total"
              value={`${stats.roi_total > 0 ? "+" : ""}${stats.roi_total}u`}
              variant={stats.roi_total > 0 ? "green" : "red"}
            />
            <MetricCard
              icon={Flame}
              label="Premium (últimos 10)"
              value={premiumRecent}
              subValue={`${tipoPremiumPct}%`}
              variant="cyan"
            />
            <MetricCard
              icon={Zap}
              label="Normal (últimos 10)"
              value={normalRecent}
              subValue={`${tipoNormalPct}%`}
            />
          </div>
        </section>

        {/* Jogos ao vivo */}
        {liveGames && (
          <section className="mb-10">
            <LiveGamesSection
              preJanela={liveGames.pre_janela}
              naJanela={liveGames.na_janela}
              posJanela={liveGames.pos_janela}
              idsObservados={liveGames.ids_observados}
            />
            {liveGames.atualizado && (
              <p className="mt-3 text-xs text-zinc-500">
                Última atualização: {liveGames.atualizado.slice(11, 19)}
              </p>
            )}
          </section>
        )}

        <div className="grid gap-10 lg:grid-cols-2">
          {/* Sinais recentes */}
          <RecentSignals signals={data!.signals} />

          {/* Ligas monitoradas */}
          <MonitoredLeagues ligas={data!.ligas} />
        </div>

        {/* Próximos jogos */}
        <section className="mt-10">
          <UpcomingGames />
        </section>

        {/* Status do sistema */}
        <section className="mt-10">
          <SystemStatus
            apiUsado={status.api_usado}
            apiLimite={status.api_limite}
            minutoInicio={status.minuto_inicio ?? 50}
            minutoFim={status.minuto_fim ?? 90}
            jogosAoVivo={status.jogos_ao_vivo}
            jogosNaJanela={status.jogos_na_janela}
            ultimoUpdate={
              status.ultimo_update !== "?" ? status.ultimo_update : undefined
            }
          />
        </section>

        {/* Polling stats */}
        <section className="mt-10">
          <PollingStats
            jogosMonitorados={pollingStats?.jogos_monitorados}
            jogosAnalisando={pollingStats?.jogos_analisando}
            economiaPct={pollingStats?.economia_pct}
          />
        </section>

        {/* Audit Panel */}
        <section className="mt-10">
          <AuditPanel />
        </section>

        {/* Logs */}
        <section className="mt-10">
          <SystemLogs lines={data!.logs} />
        </section>
      </main>
    </div>
  );
}
