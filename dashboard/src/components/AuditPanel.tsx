"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchAudit, type AuditData, type AuditGameDetail } from "@/lib/api";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import {
  Activity,
  Filter,
  TrendingUp,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Eye,
} from "lucide-react";

// --- Funnel Bar ---
function FunnelBar({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 text-right text-xs text-zinc-400">
        {label}
      </span>
      <div className="relative h-7 flex-1 overflow-hidden rounded-md bg-zinc-800/50">
        <div
          className={`absolute inset-y-0 left-0 rounded-md transition-all duration-700 ${color}`}
          style={{ width: `${Math.max(pct, 1)}%` }}
        />
        <span className="absolute inset-0 flex items-center justify-center text-xs font-semibold text-white drop-shadow">
          {value} ({pct.toFixed(0)}%)
        </span>
      </div>
    </div>
  );
}

// --- Decision Funnel ---
function DecisionFunnel({ funil }: { funil: AuditData["funil"] }) {
  const total = funil.total_analisados;
  return (
    <Card className="p-5">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-cyan-400">
        <Filter className="h-4 w-4" />
        Funil de decisao
      </h3>
      {total === 0 ? (
        <p className="text-sm text-zinc-500">Sem dados neste ciclo</p>
      ) : (
        <div className="space-y-2">
          <FunnelBar
            label="Analisados"
            value={total}
            total={total}
            color="bg-zinc-600"
          />
          <FunnelBar
            label="Filtros OK"
            value={funil.passou_filtros}
            total={total}
            color="bg-blue-500/70"
          />
          <FunnelBar
            label="Score OK"
            value={funil.score_ok}
            total={total}
            color="bg-amber-500/70"
          />
          <FunnelBar
            label="Edge OK"
            value={funil.edge_ok}
            total={total}
            color="bg-emerald-500/70"
          />
          <FunnelBar
            label="Sinais"
            value={funil.sinais_emitidos}
            total={total}
            color="bg-cyan-500/80"
          />
          {funil.sinais_emitidos > 0 && (
            <div className="mt-2 flex items-center justify-center gap-3 text-xs">
              <Badge variant="premium">
                PREMIUM: {funil.premium}
              </Badge>
              <Badge variant="normal">
                NORMAL: {funil.normal}
              </Badge>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// --- Conversion Rates ---
function ConversionRates({
  taxas,
  config,
}: {
  taxas: AuditData["taxas"];
  config: AuditData["config"];
}) {
  const rates = [
    {
      label: "Elegibilidade",
      value: taxas.elegibilidade,
      desc: "Jogos que passam filtros estruturais",
      color: "text-blue-400",
    },
    {
      label: "Score",
      value: taxas.conversao_score,
      desc: `Score >= ${config.min_score_normal}`,
      color: "text-amber-400",
    },
    {
      label: "Edge",
      value: taxas.conversao_edge,
      desc: `Edge >= ${config.min_edge_normal}`,
      color: "text-emerald-400",
    },
    {
      label: "Hit Rate",
      value: taxas.hit_rate,
      desc: "Analisados -> Sinais",
      color: "text-cyan-400",
    },
  ];

  return (
    <Card className="p-5">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-cyan-400">
        <TrendingUp className="h-4 w-4" />
        Taxas de conversao
      </h3>
      <div className="grid grid-cols-2 gap-4">
        {rates.map((r) => (
          <div key={r.label} className="text-center">
            <p className={`text-2xl font-bold ${r.color}`}>
              {r.value.toFixed(1)}%
            </p>
            <p className="mt-1 text-xs font-medium text-zinc-300">{r.label}</p>
            <p className="text-[10px] text-zinc-500">{r.desc}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

// --- Filter Breakdown ---
function FilterBreakdown({
  filtros,
}: {
  filtros: Record<string, number>;
}) {
  const entries = Object.entries(filtros);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  const colors = [
    "bg-red-500/70",
    "bg-orange-500/70",
    "bg-amber-500/70",
    "bg-yellow-500/70",
    "bg-lime-500/70",
    "bg-teal-500/70",
    "bg-blue-500/70",
    "bg-violet-500/70",
  ];

  return (
    <Card className="p-5">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-cyan-400">
        <AlertTriangle className="h-4 w-4" />
        Motivos de bloqueio
      </h3>
      {entries.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhum jogo bloqueado</p>
      ) : (
        <div className="space-y-2">
          {entries.map(([motivo, count], i) => {
            const pct = total > 0 ? (count / total) * 100 : 0;
            return (
              <div key={motivo} className="flex items-center gap-3">
                <div className="relative h-6 flex-1 overflow-hidden rounded bg-zinc-800/50">
                  <div
                    className={`absolute inset-y-0 left-0 rounded ${colors[i % colors.length]}`}
                    style={{ width: `${Math.max(pct, 2)}%` }}
                  />
                  <span className="absolute inset-0 flex items-center px-2 text-[11px] font-medium text-white drop-shadow">
                    {motivo}
                  </span>
                </div>
                <span className="w-12 shrink-0 text-right font-mono text-xs text-zinc-400">
                  {count} ({pct.toFixed(0)}%)
                </span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// --- Game Status Badge ---
function GameStatusBadge({ status }: { status: string }) {
  switch (status) {
    case "SINAL_PREMIUM":
      return <Badge variant="premium">PREMIUM</Badge>;
    case "SINAL_NORMAL":
      return <Badge variant="normal">SINAL</Badge>;
    case "SCORE_INSUFICIENTE":
      return <Badge variant="pending">SCORE</Badge>;
    case "EDGE_INSUFICIENTE":
      return <Badge variant="pending">EDGE</Badge>;
    case "SEM_ODDS":
      return <Badge variant="pending">S/ ODDS</Badge>;
    case "BLOQUEADO":
      return <Badge variant="red">BLOQ</Badge>;
    default:
      return <Badge variant="normal">{status}</Badge>;
  }
}

// --- Games Detail Table ---
function GamesDetail({ jogos }: { jogos: AuditGameDetail[] }) {
  const [expanded, setExpanded] = useState(false);
  const displayed = expanded ? jogos : jogos.slice(0, 5);

  return (
    <Card className="p-5">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-cyan-400">
        <Eye className="h-4 w-4" />
        Jogos analisados ({jogos.length})
      </h3>
      {jogos.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhum jogo no ciclo</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/5 text-left text-zinc-500">
                  <th className="pb-2 pr-3">Jogo</th>
                  <th className="pb-2 pr-3">Liga</th>
                  <th className="pb-2 pr-2 text-center">Min</th>
                  <th className="pb-2 pr-2 text-center">Esc</th>
                  <th className="pb-2 pr-2 text-center">Score</th>
                  <th className="pb-2 pr-2 text-center">Proj</th>
                  <th className="pb-2 pr-2 text-center">Linha</th>
                  <th className="pb-2 pr-2 text-center">Edge</th>
                  <th className="pb-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {displayed.map((g, i) => {
                  const isSignal =
                    g.status === "SINAL_PREMIUM" ||
                    g.status === "SINAL_NORMAL";
                  return (
                    <tr
                      key={i}
                      className={`border-b border-white/[0.03] transition-colors ${
                        isSignal
                          ? "bg-cyan-500/5"
                          : "hover:bg-white/[0.02]"
                      }`}
                    >
                      <td className="py-2 pr-3 font-medium text-zinc-200">
                        <div className="max-w-[180px] truncate">
                          {g.descricao}
                        </div>
                        {g.motivo && (
                          <div className="mt-0.5 max-w-[180px] truncate text-[10px] text-zinc-500">
                            {g.motivo}
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-zinc-400">
                        <div className="max-w-[100px] truncate">{g.liga}</div>
                      </td>
                      <td className="py-2 pr-2 text-center text-zinc-300">
                        {g.minuto}&apos;
                      </td>
                      <td className="py-2 pr-2 text-center text-zinc-300">
                        {g.escanteios_total}
                      </td>
                      <td className="py-2 pr-2 text-center">
                        <span
                          className={
                            g.pressure_score !== null && g.pressure_score >= 8
                              ? "font-bold text-fuchsia-400"
                              : g.pressure_score !== null &&
                                  g.pressure_score >= 5
                                ? "font-semibold text-cyan-400"
                                : "text-zinc-400"
                          }
                        >
                          {g.pressure_score ?? "-"}
                        </span>
                      </td>
                      <td className="py-2 pr-2 text-center text-zinc-300">
                        {g.projecao !== null ? g.projecao.toFixed(1) : "-"}
                      </td>
                      <td className="py-2 pr-2 text-center text-zinc-300">
                        {g.linha > 0 ? g.linha.toFixed(1) : "-"}
                      </td>
                      <td className="py-2 pr-2 text-center">
                        {g.edge !== null ? (
                          <span
                            className={
                              g.edge >= 1.5
                                ? "font-bold text-emerald-400"
                                : g.edge >= 0.7
                                  ? "font-semibold text-emerald-300"
                                  : g.edge > 0
                                    ? "text-amber-400"
                                    : "text-red-400"
                            }
                          >
                            {g.edge >= 0 ? "+" : ""}
                            {g.edge.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-zinc-500">-</span>
                        )}
                      </td>
                      <td className="py-2 text-center">
                        <GameStatusBadge status={g.status} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {jogos.length > 5 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-3 flex w-full items-center justify-center gap-1 rounded-lg border border-white/5 py-2 text-xs text-zinc-400 transition-colors hover:border-cyan-500/20 hover:text-cyan-400"
            >
              {expanded ? (
                <>
                  <ChevronUp className="h-3 w-3" />
                  Mostrar menos
                </>
              ) : (
                <>
                  <ChevronDown className="h-3 w-3" />
                  Ver todos ({jogos.length})
                </>
              )}
            </button>
          )}
        </>
      )}
    </Card>
  );
}

// --- 7-Day History ---
function HistoryChart({
  historico,
}: {
  historico: AuditData["historico_7d"];
}) {
  if (historico.length === 0) {
    return (
      <Card className="p-5">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-cyan-400">
          <Activity className="h-4 w-4" />
          Historico 7 dias
        </h3>
        <p className="text-sm text-zinc-500">Sem dados historicos</p>
      </Card>
    );
  }

  const maxTotal = Math.max(...historico.map((d) => d.total), 1);

  return (
    <Card className="p-5">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-cyan-400">
        <Activity className="h-4 w-4" />
        Historico 7 dias
      </h3>
      <div className="space-y-2">
        {historico.map((day) => {
          const greenPct = day.total > 0 ? (day.greens / day.total) * 100 : 0;
          const barWidth = (day.total / maxTotal) * 100;
          return (
            <div key={day.dia} className="flex items-center gap-3">
              <span className="w-16 shrink-0 text-right font-mono text-[11px] text-zinc-400">
                {day.dia.slice(5)}
              </span>
              <div className="relative h-6 flex-1 overflow-hidden rounded bg-zinc-800/50">
                {/* Green portion */}
                <div
                  className="absolute inset-y-0 left-0 rounded bg-emerald-500/60"
                  style={{
                    width: `${barWidth * (greenPct / 100)}%`,
                  }}
                />
                {/* Red portion (stacked after green) */}
                <div
                  className="absolute inset-y-0 rounded bg-red-500/50"
                  style={{
                    left: `${barWidth * (greenPct / 100)}%`,
                    width: `${barWidth * ((100 - greenPct) / 100)}%`,
                  }}
                />
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-white drop-shadow">
                  {day.total} sinais
                </span>
              </div>
              <div className="flex w-28 shrink-0 items-center gap-2 text-[10px]">
                <span className="text-emerald-400">{day.greens}G</span>
                <span className="text-red-400">{day.reds}R</span>
                <span
                  className={
                    day.roi >= 0 ? "text-emerald-300" : "text-red-300"
                  }
                >
                  {day.roi >= 0 ? "+" : ""}
                  {day.roi.toFixed(1)}u
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// --- Main Audit Panel ---
export function AuditPanel() {
  const [data, setData] = useState<AuditData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setError(null);
      const d = await fetchAudit();
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar auditoria");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && !data) {
    return (
      <section className="animate-fade-in">
        <h2 className="mb-6 flex items-center gap-2 text-xl font-semibold text-cyan-400">
          <Activity className="h-5 w-5" />
          Painel de auditoria
        </h2>
        <div className="flex items-center justify-center rounded-xl border border-white/5 bg-zinc-900/30 p-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
        </div>
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="animate-fade-in">
        <h2 className="mb-6 flex items-center gap-2 text-xl font-semibold text-cyan-400">
          <Activity className="h-5 w-5" />
          Painel de auditoria
        </h2>
        <Card className="p-6 text-center">
          <p className="text-sm text-zinc-500">
            {error || "Sem dados de auditoria"}
          </p>
          <p className="mt-1 text-xs text-zinc-600">
            O painel sera populado quando o motor iniciar a analise de jogos
          </p>
        </Card>
      </section>
    );
  }

  return (
    <section className="animate-fade-in">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xl font-semibold text-cyan-400">
          <Activity className="h-5 w-5" />
          Painel de auditoria
        </h2>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          <span>Ciclo #{data.ciclo}</span>
          {data.atualizado && (
            <>
              <span className="text-zinc-700">|</span>
              <span>{data.atualizado.slice(11, 19)}</span>
            </>
          )}
        </div>
      </div>

      {/* Row 1: Funnel + Rates + Filters */}
      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        <DecisionFunnel funil={data.funil} />
        <ConversionRates taxas={data.taxas} config={data.config} />
        <FilterBreakdown filtros={data.filtros_breakdown} />
      </div>

      {/* Row 2: Games Table */}
      <div className="mb-4">
        <GamesDetail jogos={data.jogos} />
      </div>

      {/* Row 3: History */}
      <HistoryChart historico={data.historico_7d} />
    </section>
  );
}
