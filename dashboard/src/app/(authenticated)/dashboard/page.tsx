"use client";

import { useEffect, useMemo, useState } from "react";
import {
    Activity,
    CheckCircle2,
    XCircle,
    Clock,
    TrendingUp,
    Loader2,
} from "lucide-react";
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    Tooltip as RTooltip,
    CartesianGrid,
} from "recharts";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { SignalsDrawer } from "@/components/dashboard/SignalsDrawer";
import { MarketIntelligencePanel } from "@/components/dashboard/MarketIntelligencePanel";
import { GamesPanel } from "@/components/dashboard/GamesPanel";

type PeriodId = "today" | "7d" | "30d" | "all";
type PeriodStats = {
    total: number;
    greens: number;
    reds: number;
    pendentes: number;
    winrate: number;
    roi: number;
};
import { OnboardingBanner } from "@/components/shell/OnboardingBanner";
import { useDashboard } from "@/components/shell/Shell";
import { fetchSignalsList, type SignalDetail, type SignalResult } from "@/lib/api";
import { fmtTime, fmtUnits, cn } from "@/lib/format";

const PERIOD_OPTS: { v: PeriodId; label: string; ms: number | null }[] = [
    { v: "today", label: "Hoje", ms: null }, // ms=null = filtra "do início do dia local"
    { v: "7d", label: "7D", ms: 7 * 86_400_000 },
    { v: "30d", label: "30D", ms: 30 * 86_400_000 },
    { v: "all", label: "Tudo", ms: Number.POSITIVE_INFINITY },
];

function filterByPeriod(signals: SignalDetail[], period: PeriodId): SignalDetail[] {
    const opt = PERIOD_OPTS.find((p) => p.v === period)!;
    if (opt.v === "all") return signals;
    if (opt.v === "today") {
        const startOfDay = new Date();
        startOfDay.setHours(0, 0, 0, 0);
        const startMs = startOfDay.getTime();
        return signals.filter((s) => s.timestamp && new Date(s.timestamp).getTime() >= startMs);
    }
    const cutoff = Date.now() - (opt.ms ?? 0);
    return signals.filter((s) => s.timestamp && new Date(s.timestamp).getTime() >= cutoff);
}

function computeStats(signals: SignalDetail[]): PeriodStats {
    const total = signals.length;
    const greens = signals.filter((s) => s.resultado === "GREEN").length;
    const reds = signals.filter((s) => s.resultado === "RED").length;
    const pendentes = signals.filter((s) => s.resultado === "PENDENTE" || !s.resultado).length;
    const decididos = greens + reds;
    const winrate = decididos > 0 ? (greens / decididos) * 100 : 0;
    const roi = signals.reduce((a, s) => {
        if (s.resultado === "GREEN") return a + ((s.odd ?? 1) - 1);
        if (s.resultado === "RED") return a - 1;
        return a;
    }, 0);
    return {
        total,
        greens,
        reds,
        pendentes,
        winrate: Number(winrate.toFixed(1)),
        roi: Number(roi.toFixed(2)),
    };
}

export default function DashboardPage() {
    const { data: streamData } = useDashboard();
    const [drawer, setDrawer] = useState<SignalResult | null>(null);
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);

    const [period, setPeriod] = useState<PeriodId>("7d");
    const [allSignals, setAllSignals] = useState<SignalDetail[]>([]);
    const [loadingSignals, setLoadingSignals] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoadingSignals(true);
        setLoadError(null);
        fetchSignalsList("all", 2000)
            .then((list) => {
                if (cancelled) return;
                setAllSignals(list);
            })
            .catch((e: unknown) => {
                if (cancelled) return;
                const msg = e instanceof Error ? e.message : "Erro ao carregar sinais";
                console.error("[Dashboard] fetchSignalsList:", msg);
                setLoadError(msg);
            })
            .finally(() => !cancelled && setLoadingSignals(false));
        return () => {
            cancelled = true;
        };
    }, []);

    const filteredSignals = useMemo(() => filterByPeriod(allSignals, period), [allSignals, period]);
    const periodStats = useMemo(() => computeStats(filteredSignals), [filteredSignals]);

    const chart = useMemo(() => {
        let cum = 0;
        return [...filteredSignals]
            .sort((a, b) => {
                const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
                const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
                return ta - tb;
            })
            .slice(-30)
            .map((s, i) => {
                const r =
                    s.resultado === "GREEN" ? (s.odd ?? 1) - 1 : s.resultado === "RED" ? -1 : 0;
                cum += r;
                return { name: `#${i + 1}`, roi: Number(cum.toFixed(2)) };
            });
    }, [filteredSignals]);

    const cumLatest = chart.length ? chart[chart.length - 1].roi : 0;
    const periodLabel = PERIOD_OPTS.find((p) => p.v === period)?.label ?? "";

    if (loadingSignals && allSignals.length === 0) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
                <Loader2 className="size-6 animate-spin" />
                <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO SINAIS…</span>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-[1600px] mx-auto">
            <OnboardingBanner />

            {loadError && (
                <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive flex items-start gap-2">
                    <span className="font-mono tracking-wider uppercase shrink-0">ERRO:</span>
                    <span>Não foi possível carregar os sinais ({loadError}). Recarregue a página.</span>
                </div>
            )}

            {/* Filtro temporal */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="inline-flex rounded-lg border border-border bg-card/60 p-0.5">
                    {PERIOD_OPTS.map((o) => {
                        const on = period === o.v;
                        return (
                            <button
                                key={o.v}
                                onClick={() => setPeriod(o.v)}
                                className={cn(
                                    "px-3 py-1.5 text-[11px] font-mono tracking-wider rounded-md transition",
                                    on
                                        ? "bg-mint/10 text-mint-bright shadow-[inset_0_0_0_1px_oklch(0.62_0.22_255/0.35)]"
                                        : "text-muted-foreground hover:text-foreground",
                                )}
                            >
                                {o.label.toUpperCase()}
                            </button>
                        );
                    })}
                </div>
                {streamData?.status && (
                    <div className="flex items-center gap-3 font-mono text-[10px] tracking-wider text-muted-foreground">
                        <span className="inline-flex items-center gap-1.5">
                            <span className="size-1.5 rounded-full bg-success animate-pulse" />
                            {streamData.status.status_msg || "ativo"}
                        </span>
                        <span>·</span>
                        <span>último update: {fmtTime(streamData.status.ultimo_update)}</span>
                    </div>
                )}
            </div>

            {/* KPIs clicáveis (diferenciados por resultado) */}
            <section className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                <KpiCard
                    label="Sinais no período"
                    value={periodStats.total}
                    sub={periodLabel}
                    icon={Activity}
                    tone="mint"
                    onClick={() => setDrawer("all")}
                />
                <KpiCard
                    label="Greens"
                    value={periodStats.greens}
                    sub={`${periodStats.winrate.toFixed(0)}% winrate`}
                    icon={CheckCircle2}
                    tone="success"
                    onClick={() => setDrawer("GREEN")}
                />
                <KpiCard
                    label="Reds"
                    value={periodStats.reds}
                    sub={`${periodStats.greens + periodStats.reds} decididos`}
                    icon={XCircle}
                    tone="danger"
                    onClick={() => setDrawer("RED")}
                />
                <KpiCard
                    label="Pendentes"
                    value={periodStats.pendentes}
                    sub={periodStats.pendentes > 0 ? "ver detalhe" : "—"}
                    icon={Clock}
                    tone="warning"
                    onClick={() => setDrawer("PENDENTE")}
                />
            </section>

            {/* Inteligência ao vivo — substitui o antigo Quant Engine (dev-only) */}
            <MarketIntelligencePanel />

            {/* Chart + Games */}
            <section className="grid gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2 piq-in rounded-2xl border border-border bg-card p-5">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                                ROI Acumulado
                            </div>
                            <div className="font-display text-lg font-semibold mt-0.5">
                                {chart.length} sinais — {periodLabel}
                            </div>
                        </div>
                        <span className={cn("font-mono text-base font-bold tabular", cumLatest >= 0 ? "text-mint-bright" : "text-destructive")}>
                            {fmtUnits(cumLatest)}
                        </span>
                    </div>
                    <div style={{ width: "100%", height: 240 }}>
                        {mounted && chart.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={chart} margin={{ left: -10, right: 8, top: 5, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="mintGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="oklch(0.62 0.22 255)" stopOpacity={0.4} />
                                            <stop offset="100%" stopColor="oklch(0.62 0.22 255)" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.30 0.03 220 / 0.3)" />
                                    <XAxis
                                        dataKey="name"
                                        stroke="oklch(0.70 0.02 200)"
                                        tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
                                    />
                                    <YAxis
                                        stroke="oklch(0.70 0.02 200)"
                                        tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
                                    />
                                    <RTooltip
                                        contentStyle={{
                                            background: "oklch(0.20 0.028 232)",
                                            border: "1px solid oklch(0.62 0.22 255 / 0.4)",
                                            borderRadius: 12,
                                            fontSize: 12,
                                            fontFamily: "JetBrains Mono",
                                        }}
                                        labelStyle={{ color: "oklch(0.70 0.02 200)" }}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="roi"
                                        stroke="oklch(0.74 0.18 235)"
                                        strokeWidth={2}
                                        fill="url(#mintGrad)"
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                                Sem sinais no período selecionado.
                            </div>
                        )}
                    </div>
                </div>

                <GamesPanel live_games={streamData?.live_games} />
            </section>

            {/* Recent signals — full width */}
            <section className="piq-in rounded-2xl border border-border bg-card overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-border">
                    <div>
                        <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                            Sinais recentes
                        </div>
                        <div className="font-display text-lg font-semibold mt-0.5">
                            Últimos {Math.min(10, filteredSignals.length)} — {periodLabel}
                        </div>
                    </div>
                    <button
                        onClick={() => setDrawer("all")}
                        className="font-mono text-[10px] tracking-wider text-mint hover:text-mint-bright flex items-center gap-1.5"
                    >
                        <TrendingUp className="size-3" />
                        VER TODOS →
                    </button>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="border-b border-border">
                            <tr className="font-mono text-[10px] tracking-wider text-muted-foreground">
                                <th className="text-left font-medium px-4 py-2.5">DATA</th>
                                <th className="text-left font-medium px-4 py-2.5">JOGO</th>
                                <th className="text-left font-medium px-4 py-2.5">SINAL</th>
                                <th className="text-right font-medium px-4 py-2.5">ODD</th>
                                <th className="text-center font-medium px-4 py-2.5">RES</th>
                            </tr>
                        </thead>
                        <tbody>
                            {[...filteredSignals]
                                .sort((a, b) => {
                                    const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
                                    const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
                                    return tb - ta;
                                })
                                .slice(0, 10)
                                .map((s, i) => (
                                    <tr
                                        key={s.id ?? i}
                                        className="border-b border-border/40 hover:bg-mint/5 transition"
                                    >
                                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
                                            {fmtTime(s.timestamp)}
                                        </td>
                                        <td className="px-4 py-3 font-medium truncate max-w-[260px]">
                                            {s.jogo_descricao || "—"}
                                        </td>
                                        <td className="px-4 py-3 text-xs text-muted-foreground">
                                            {s.tipo_sinal}
                                        </td>
                                        <td className="px-4 py-3 text-right font-mono text-xs">
                                            {s.odd?.toFixed(2) ?? "—"}
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            <ResultPill r={s.resultado || "PENDENTE"} />
                                        </td>
                                    </tr>
                                ))}
                            {filteredSignals.length === 0 && (
                                <tr>
                                    <td colSpan={5} className="px-4 py-8 text-center text-xs text-muted-foreground">
                                        Sem sinais no período.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            <SignalsDrawer
                open={drawer !== null}
                onClose={() => setDrawer(null)}
                filter={drawer ?? "all"}
                signals={filteredSignals}
                periodLabel={periodLabel}
            />
        </div>
    );
}

function ResultPill({ r }: { r: string }) {
    const map: Record<string, string> = {
        GREEN: "text-success border-success/40 bg-success/10",
        RED: "text-destructive border-destructive/40 bg-destructive/10",
        PENDENTE: "text-warning border-warning/40 bg-warning/10",
    };
    return (
        <span
            className={cn(
                "inline-flex font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border",
                map[r] ?? "border-border bg-muted/40 text-muted-foreground",
            )}
        >
            {r === "PENDENTE" ? "PEND" : r}
        </span>
    );
}
