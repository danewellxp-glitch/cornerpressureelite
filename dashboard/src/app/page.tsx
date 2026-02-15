"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchDashboard, type DashboardData } from "@/lib/api";

function useDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setError(null);
      const d = await fetchDashboard();
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  return { data, error, loading, refresh: load };
}

function LogLine({ line }: { line: string }) {
  const isError = line.includes("ERROR");
  const isWarning = line.includes("WARNING");
  const isSignal = line.includes("Sinal") && line.includes("enviado");
  const isCycle = line.includes("Ciclo #");

  let className = "font-mono text-xs text-zinc-500 truncate";
  if (isError) className = "font-mono text-xs text-red-400";
  else if (isWarning) className = "font-mono text-xs text-amber-400";
  else if (isSignal) className = "font-mono text-xs text-emerald-400 font-medium";
  else if (isCycle) className = "font-mono text-xs text-cyan-400";

  return (
    <div className={className}>
      {line.length > 100 ? line.slice(0, 97) + "..." : line}
    </div>
  );
}

function ResultBadge({ resultado }: { resultado: string }) {
  if (resultado === "GREEN")
    return (
      <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-xs font-medium text-emerald-400">
        GREEN
      </span>
    );
  if (resultado === "RED")
    return (
      <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs font-medium text-red-400">
        RED
      </span>
    );
  return (
    <span className="rounded bg-zinc-500/20 px-1.5 py-0.5 text-xs text-zinc-500">-</span>
  );
}

export default function DashboardPage() {
  const { data, error, loading, refresh } = useDashboard();

  if (loading && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-100">
        <div className="text-center">
          <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent mx-auto" />
          <p className="text-zinc-400">Carregando CPES...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-950 text-zinc-100">
        <p className="text-red-400">{error}</p>
        <p className="text-sm text-zinc-500">
          Verifique se o backend está rodando:{" "}
          <code className="rounded bg-zinc-800 px-2 py-1">
            cd corner-pressure-elite && uvicorn api_server:app --port 8000
          </code>
        </p>
        <button
          onClick={refresh}
          className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium hover:bg-cyan-500"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  const stats = data!.stats;
  const status = data!.status;
  const signals = data!.signals;
  const logs = data!.logs;
  const ligas = data!.ligas;

  const apiPct =
    status.api_usado !== "?"
      ? Math.round((parseInt(status.api_usado, 10) / parseInt(status.api_limite, 10)) * 100)
      : 0;
  const apiColor =
    apiPct < 50 ? "text-emerald-400" : apiPct < 80 ? "text-amber-400" : "text-red-400";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <h1 className="text-xl font-bold tracking-tight text-cyan-400">
            CORNER PRESSURE ELITE SYSTEM
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-500">
              Ciclo #{status.ciclo} · Polling 10s
            </span>
            <button
              onClick={refresh}
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-800"
            >
              Atualizar
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {/* Jogos ao vivo por fase */}
        {data!.live_games && (
          <section className="mb-8">
            <h2 className="mb-4 text-lg font-semibold text-cyan-400">
              Jogos ao vivo (por fase)
            </h2>
            <div className="grid gap-4 lg:grid-cols-3">
              {/* Pre-janela: 0-50 (ou < 7 esc) */}
              <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 p-4">
                <h3 className="mb-2 text-sm font-medium text-amber-400">
                  Aguardando janela (0-30: 5 min | 31-50: 3 min)
                </h3>
                <p className="mb-3 text-xs text-zinc-500">
                  {data!.live_games.pre_janela.length} jogo(s)
                </p>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {data!.live_games.pre_janela.length === 0 ? (
                    <p className="text-xs text-zinc-600">Nenhum</p>
                  ) : (
                    data!.live_games.pre_janela.map((j) => (
                      <div
                        key={j.id}
                        className="rounded border border-zinc-800 bg-zinc-900/50 px-3 py-2 text-xs"
                      >
                        <p className="font-medium text-zinc-200 truncate">
                          {j.home} vs {j.away}
                        </p>
                        <p className="text-zinc-500">
                          {j.liga} · {j.minuto}&apos; · {j.placar}
                          {typeof j.escanteios === "number" && (
                            <span className="text-cyan-400"> · {j.escanteios} esc.</span>
                          )}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Na janela: 50-90 ou 7+ esc (early trigger) */}
              <div className="rounded-lg border border-cyan-900/50 bg-cyan-950/20 p-4">
                <h3 className="mb-2 text-sm font-medium text-cyan-400">
                  Na janela (sendo analisados) · 1 min
                </h3>
                <p className="mb-3 text-xs text-zinc-500">
                  {data!.live_games.na_janela.length} jogo(s)
                </p>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {data!.live_games.na_janela.length === 0 ? (
                    <p className="text-xs text-zinc-600">Nenhum</p>
                  ) : (
                    data!.live_games.na_janela.map((j) => {
                      const observado = data!.live_games!.ids_observados.includes(j.id);
                      return (
                        <div
                          key={j.id}
                          className={`rounded border px-3 py-2 text-xs ${
                            observado
                              ? "border-emerald-800 bg-emerald-950/30"
                              : "border-zinc-800 bg-zinc-900/50"
                          }`}
                        >
                          <p className="font-medium text-zinc-200 truncate">
                            {j.home} vs {j.away}
                          </p>
                          <p className="text-zinc-500">
                            {j.liga} · {j.minuto}&apos; · {j.placar}
                            {typeof j.escanteios === "number" && (
                              <span className="text-cyan-400"> · {j.escanteios} esc.</span>
                            )}
                          </p>
                          {observado && (
                            <span className="text-[10px] text-emerald-400">
                              Em observação (sinal enviado)
                            </span>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Pos-janela: após min 90 (acréscimos) */}
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
                <h3 className="mb-2 text-sm font-medium text-zinc-400">
                  Após janela (após min 90)
                </h3>
                <p className="mb-3 text-xs text-zinc-500">
                  {data!.live_games.pos_janela.length} jogo(s)
                </p>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {data!.live_games.pos_janela.length === 0 ? (
                    <p className="text-xs text-zinc-600">Nenhum</p>
                  ) : (
                    data!.live_games.pos_janela.map((j) => (
                      <div
                        key={j.id}
                        className="rounded border border-zinc-800 bg-zinc-900/50 px-3 py-2 text-xs"
                      >
                        <p className="font-medium text-zinc-300 truncate">
                          {j.home} vs {j.away}
                        </p>
                        <p className="text-zinc-500">
                          {j.liga} · {j.minuto}&apos; · {j.placar}
                          {typeof j.escanteios === "number" && (
                            <span className="text-cyan-400"> · {j.escanteios} esc.</span>
                          )}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
            {data!.live_games.atualizado && (
              <p className="mt-2 text-xs text-zinc-500">
                Última atualização: {data!.live_games.atualizado.slice(11, 19)}
              </p>
            )}
          </section>
        )}

        {/* System status */}
        <section className="mb-8">
          <h2 className="mb-4 text-lg font-semibold text-cyan-400">Sistema</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">API Football</p>
              <p className={`font-mono font-medium ${apiColor}`}>
                {status.api_usado}/{status.api_limite} req ({apiPct}%)
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">Janela (min)</p>
              <p className="font-mono font-medium">
                {status.minuto_inicio}–{status.minuto_fim}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">Jogos ao vivo</p>
              <p className="font-mono text-lg font-bold text-cyan-400">
                {status.jogos_ao_vivo}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">Na janela</p>
              <p className="font-mono text-lg font-bold text-cyan-400">
                {status.jogos_na_janela}
              </p>
            </div>
          </div>
          {status.status_msg && (
            <p className="mt-3 text-sm text-amber-400">{status.status_msg}</p>
          )}
        </section>

        {/* Performance */}
        <section className="mb-8">
          <h2 className="mb-4 text-lg font-semibold text-cyan-400">Performance</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">Total sinais</p>
              <p className="text-xl font-bold">{stats.total}</p>
            </div>
            <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/30 p-4">
              <p className="text-xs text-zinc-500">Greens</p>
              <p className="text-xl font-bold text-emerald-400">{stats.greens}</p>
            </div>
            <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-4">
              <p className="text-xs text-zinc-500">Reds</p>
              <p className="text-xl font-bold text-red-400">{stats.reds}</p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">Pendentes</p>
              <p className="text-xl font-bold text-amber-400">{stats.pendentes}</p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">Winrate</p>
              <p
                className={`text-xl font-bold ${
                  stats.winrate >= 60
                    ? "text-emerald-400"
                    : stats.winrate >= 50
                      ? "text-amber-400"
                      : "text-red-400"
                }`}
              >
                {stats.winrate}%
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs text-zinc-500">ROI Total</p>
              <p
                className={`text-xl font-bold ${
                  stats.roi_total > 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {stats.roi_total}u
              </p>
            </div>
          </div>
        </section>

        <div className="grid gap-8 lg:grid-cols-2">
          {/* Recent signals */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-cyan-400">Sinais recentes</h2>
            <div className="overflow-hidden rounded-lg border border-zinc-800">
              {signals.length === 0 ? (
                <p className="p-6 text-center text-sm text-zinc-500">
                  Nenhum sinal registrado ainda
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800 bg-zinc-900/80">
                        <th className="px-3 py-2 text-left text-xs text-zinc-500">Hora</th>
                        <th className="px-3 py-2 text-left text-xs text-zinc-500">Jogo</th>
                        <th className="px-3 py-2 text-left text-xs text-zinc-500">Tipo</th>
                        <th className="px-3 py-2 text-right text-xs text-zinc-500">Score</th>
                        <th className="px-3 py-2 text-right text-xs text-zinc-500">Edge</th>
                        <th className="px-3 py-2 text-center text-xs text-zinc-500">Res</th>
                      </tr>
                    </thead>
                    <tbody>
                      {signals.map((s, i) => (
                        <tr
                          key={i}
                          className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800/30"
                        >
                          <td className="px-3 py-2 font-mono text-xs">
                            {s.timestamp.length > 19 ? s.timestamp.slice(11, 19) : s.timestamp}
                          </td>
                          <td className="max-w-[180px] truncate px-3 py-2" title={s.jogo_descricao}>
                            {s.jogo_descricao}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={
                                s.tipo_sinal === "PREMIUM" ? "text-fuchsia-400" : "text-zinc-300"
                              }
                            >
                              {s.tipo_sinal}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right font-mono">{s.pressure_score}</td>
                          <td className="px-3 py-2 text-right font-mono">
                            {s.edge != null ? (s.edge >= 0 ? `+${s.edge.toFixed(2)}` : s.edge.toFixed(2)) : "-"}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <ResultBadge resultado={s.resultado} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          {/* Leagues */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-cyan-400">Ligas monitoradas</h2>
            <div className="space-y-2 rounded-lg border border-zinc-800 p-4">
              {ligas.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center justify-between rounded border border-zinc-800/50 bg-zinc-900/30 px-3 py-2"
                >
                  <span className="text-zinc-300">{l.nome}</span>
                  <span className="text-xs text-zinc-500">
                    {l.pais} · média {l.media_esperada}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Log */}
        <section className="mt-8">
          <h2 className="mb-4 text-lg font-semibold text-cyan-400">Log (últimas linhas)</h2>
          <div className="max-h-48 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-900/30 p-3 font-mono">
            {logs.length === 0 ? (
              <p className="text-sm text-zinc-500">[Log vazio]</p>
            ) : (
              logs.map((line, i) => (
                <LogLine key={i} line={line} />
              ))
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
