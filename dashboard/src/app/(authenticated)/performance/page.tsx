"use client";

import { useEffect, useMemo, useState } from "react";
import {
    TrendingUp,
    Loader2,
    Trophy,
    Target,
    BarChart3,
    Activity,
} from "lucide-react";
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip as RTooltip,
    CartesianGrid,
    AreaChart,
    Area,
} from "recharts";
import { fetchSignalsList, type SignalDetail } from "@/lib/api";
import { cn, fmtUnits } from "@/lib/format";

type Period = "7d" | "30d" | "90d" | "all";
const PERIODS: { v: Period; label: string; ms: number }[] = [
    { v: "7d", label: "7D", ms: 7 * 86_400_000 },
    { v: "30d", label: "30D", ms: 30 * 86_400_000 },
    { v: "90d", label: "90D", ms: 90 * 86_400_000 },
    { v: "all", label: "Tudo", ms: Number.POSITIVE_INFINITY },
];

type Market = "all" | "ESCANTEIOS" | "CARTOES";

function inPeriod(s: SignalDetail, p: Period): boolean {
    if (p === "all") return true;
    if (!s.timestamp) return false;
    const opt = PERIODS.find((x) => x.v === p)!;
    return Date.now() - new Date(s.timestamp).getTime() <= opt.ms;
}

function inMarket(s: SignalDetail, m: Market): boolean {
    if (m === "all") return true;
    return (s.tipo_analise || "ESCANTEIOS").toUpperCase() === m;
}

export default function PerformancePage() {
    const [signals, setSignals] = useState<SignalDetail[]>([]);
    const [loading, setLoading] = useState(true);
    const [period, setPeriod] = useState<Period>("30d");
    const [market, setMarket] = useState<Market>("all");

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        fetchSignalsList("all", 500)
            .then((list) => !cancelled && setSignals(list))
            .catch(() => {})
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, []);

    const filtered = useMemo(
        () => signals.filter((s) => inPeriod(s, period) && inMarket(s, market)),
        [signals, period, market],
    );

    const summary = useMemo(() => {
        const total = filtered.length;
        const greens = filtered.filter((s) => s.resultado === "GREEN").length;
        const reds = filtered.filter((s) => s.resultado === "RED").length;
        const decided = greens + reds;
        const winrate = decided > 0 ? (greens / decided) * 100 : 0;
        const roi = filtered.reduce((acc, s) => {
            if (s.resultado === "GREEN") return acc + ((s.odd ?? 1) - 1);
            if (s.resultado === "RED") return acc - 1;
            return acc;
        }, 0);
        const stakedUnits = decided; // 1u por sinal
        const roiPct = stakedUnits > 0 ? (roi / stakedUnits) * 100 : 0;
        return { total, greens, reds, decided, winrate, roi, roiPct };
    }, [filtered]);

    const perLiga = useMemo(() => {
        const map = new Map<string, { liga: string; total: number; g: number; r: number; roi: number }>();
        filtered.forEach((s) => {
            const k = s.liga_nome || "—";
            if (!map.has(k)) map.set(k, { liga: k, total: 0, g: 0, r: 0, roi: 0 });
            const e = map.get(k)!;
            e.total += 1;
            if (s.resultado === "GREEN") {
                e.g += 1;
                e.roi += (s.odd ?? 1) - 1;
            } else if (s.resultado === "RED") {
                e.r += 1;
                e.roi -= 1;
            }
        });
        return Array.from(map.values())
            .filter((e) => e.g + e.r >= 1)
            .map((e) => ({
                ...e,
                winrate: e.g + e.r > 0 ? Math.round((e.g / (e.g + e.r)) * 100) : 0,
                roi: Number(e.roi.toFixed(2)),
            }))
            .sort((a, b) => b.total - a.total)
            .slice(0, 12);
    }, [filtered]);

    const perMercado = useMemo(() => {
        const map: Record<string, { mercado: string; total: number; g: number; r: number; roi: number }> = {};
        filtered.forEach((s) => {
            const k = (s.tipo_analise || "ESCANTEIOS").toUpperCase();
            if (!map[k]) map[k] = { mercado: k, total: 0, g: 0, r: 0, roi: 0 };
            map[k].total += 1;
            if (s.resultado === "GREEN") {
                map[k].g += 1;
                map[k].roi += (s.odd ?? 1) - 1;
            } else if (s.resultado === "RED") {
                map[k].r += 1;
                map[k].roi -= 1;
            }
        });
        return Object.values(map).map((e) => ({
            ...e,
            winrate: e.g + e.r > 0 ? Math.round((e.g / (e.g + e.r)) * 100) : 0,
            roi: Number(e.roi.toFixed(2)),
        }));
    }, [filtered]);

    const roiChart = useMemo(() => {
        let cum = 0;
        return [...filtered]
            .filter((s) => s.timestamp && (s.resultado === "GREEN" || s.resultado === "RED"))
            .sort((a, b) => new Date(a.timestamp!).getTime() - new Date(b.timestamp!).getTime())
            .map((s, i) => {
                cum += s.resultado === "GREEN" ? (s.odd ?? 1) - 1 : -1;
                return { n: i + 1, roi: Number(cum.toFixed(2)) };
            });
    }, [filtered]);

    const hourHeatmap = useMemo(() => {
        const acc = Array.from({ length: 24 }, (_, h) => ({ hora: h, total: 0, g: 0, r: 0 }));
        filtered.forEach((s) => {
            if (!s.timestamp) return;
            const h = new Date(s.timestamp).getHours();
            acc[h].total += 1;
            if (s.resultado === "GREEN") acc[h].g += 1;
            else if (s.resultado === "RED") acc[h].r += 1;
        });
        return acc.map((row) => ({
            ...row,
            winrate: row.g + row.r > 0 ? Math.round((row.g / (row.g + row.r)) * 100) : null,
        }));
    }, [filtered]);

    if (loading && signals.length === 0) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
                <Loader2 className="size-6 animate-spin" />
                <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO PERFORMANCE…</span>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-[1400px] mx-auto">
            <header>
                <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                    Análise agregada
                </div>
                <h1 className="font-display text-2xl font-bold mt-1">Performance</h1>
                <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                    ROI, win rate e padrões dos sinais emitidos. Todas as métricas baseadas nos
                    sinais reais do sistema, com resultado verificado.
                </p>
            </header>

            <div className="flex flex-wrap items-center gap-2">
                <div className="inline-flex rounded-lg border border-border bg-card/60 p-0.5">
                    {PERIODS.map((p) => (
                        <button
                            key={p.v}
                            onClick={() => setPeriod(p.v)}
                            className={cn(
                                "px-3 py-1.5 text-[11px] font-mono tracking-wider rounded-md transition",
                                period === p.v
                                    ? "bg-mint/10 text-mint-bright shadow-[inset_0_0_0_1px_oklch(0.62_0.22_255/0.35)]"
                                    : "text-muted-foreground hover:text-foreground",
                            )}
                        >
                            {p.label.toUpperCase()}
                        </button>
                    ))}
                </div>
                <div className="inline-flex rounded-lg border border-border bg-card/60 p-0.5">
                    {[
                        { v: "all" as Market, label: "TODOS" },
                        { v: "ESCANTEIOS" as Market, label: "ESCANTEIOS" },
                        { v: "CARTOES" as Market, label: "CARTÕES" },
                    ].map((m) => (
                        <button
                            key={m.v}
                            onClick={() => setMarket(m.v)}
                            className={cn(
                                "px-3 py-1.5 text-[11px] font-mono tracking-wider rounded-md transition",
                                market === m.v
                                    ? "bg-mint/10 text-mint-bright shadow-[inset_0_0_0_1px_oklch(0.62_0.22_255/0.35)]"
                                    : "text-muted-foreground hover:text-foreground",
                            )}
                        >
                            {m.label}
                        </button>
                    ))}
                </div>
            </div>

            <section className="grid gap-3 grid-cols-2 lg:grid-cols-4">
                <Kpi icon={TrendingUp} label="ROI" value={`${summary.roiPct >= 0 ? "+" : ""}${summary.roiPct.toFixed(1)}%`} sub={fmtUnits(summary.roi)} tone={summary.roiPct >= 0 ? "mint" : "danger"} />
                <Kpi icon={Trophy} label="Win Rate" value={`${summary.winrate.toFixed(0)}%`} sub={`${summary.greens}G / ${summary.reds}R`} />
                <Kpi icon={Target} label="Decididos" value={summary.decided.toString()} sub={`de ${summary.total} sinais`} />
                <Kpi icon={Activity} label="Sinais período" value={summary.total.toString()} sub={PERIODS.find((p) => p.v === period)?.label ?? ""} />
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
                <div className="piq-in rounded-2xl border border-border bg-card p-5">
                    <div className="flex items-center justify-between mb-3">
                        <div>
                            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                                ROI Acumulado
                            </div>
                            <div className="font-display text-base font-semibold mt-0.5">
                                {roiChart.length} apostas decididas
                            </div>
                        </div>
                        <span className={cn("font-mono text-base font-bold tabular", summary.roi >= 0 ? "text-mint-bright" : "text-destructive")}>
                            {fmtUnits(summary.roi)}
                        </span>
                    </div>
                    <div style={{ width: "100%", height: 220 }}>
                        {roiChart.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={roiChart} margin={{ left: -10, right: 8, top: 5, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="perfGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="#34d399" stopOpacity={0.4} />
                                            <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                                    <XAxis dataKey="n" stroke="#8b93a3" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                                    <YAxis stroke="#8b93a3" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                                    <RTooltip
                                        contentStyle={{
                                            background: "#2a2a2a",
                                            border: "1px solid rgba(52,211,153,0.35)",
                                            borderRadius: 12,
                                            fontSize: 12,
                                            fontFamily: "JetBrains Mono",
                                            color: "#e5e7eb",
                                            boxShadow: "0 6px 20px rgba(0,0,0,0.5)",
                                        }}
                                    />
                                    <Area type="monotone" dataKey="roi" stroke="#34d399" strokeWidth={2} fill="url(#perfGrad)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                                Sem decisões no período selecionado.
                            </div>
                        )}
                    </div>
                </div>

                <div className="piq-in rounded-2xl border border-border bg-card p-5">
                    <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mb-1">
                        Win rate por liga
                    </div>
                    <div className="font-display text-base font-semibold mb-3">Top {perLiga.length}</div>
                    <div style={{ width: "100%", height: 220 }}>
                        {perLiga.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={perLiga} margin={{ left: -10, right: 8, top: 5, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                                    <XAxis dataKey="liga" stroke="#8b93a3" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} angle={-30} textAnchor="end" interval={0} height={70} />
                                    <YAxis stroke="#8b93a3" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} domain={[0, 100]} />
                                    <RTooltip
                                        contentStyle={{
                                            background: "#2a2a2a",
                                            border: "1px solid rgba(52,211,153,0.35)",
                                            borderRadius: 12,
                                            fontSize: 12,
                                            fontFamily: "JetBrains Mono",
                                            color: "#e5e7eb",
                                            boxShadow: "0 6px 20px rgba(0,0,0,0.5)",
                                        }}
                                        formatter={(v) => [`${v}%`, "Win Rate"]}
                                    />
                                    <Bar dataKey="winrate" fill="#34d399" radius={[6, 6, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                                Sem ligas com resultado.
                            </div>
                        )}
                    </div>
                </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
                <div className="piq-in rounded-2xl border border-border bg-card p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <BarChart3 className="size-4 text-mint-bright" />
                        <h3 className="font-display text-base font-semibold">Por mercado</h3>
                    </div>
                    <div className="space-y-2">
                        {perMercado.map((m) => (
                            <div key={m.mercado} className="flex items-center justify-between text-sm rounded-lg border border-border p-3">
                                <div>
                                    <div className="font-medium">{m.mercado === "CARTOES" ? "Cartões" : "Escanteios"}</div>
                                    <div className="text-xs text-muted-foreground">
                                        {m.g}G / {m.r}R · {m.total} sinais
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className={cn("font-mono tabular text-base font-semibold", m.roi >= 0 ? "text-mint-bright" : "text-destructive")}>
                                        {fmtUnits(m.roi)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">{m.winrate}% wr</div>
                                </div>
                            </div>
                        ))}
                        {perMercado.length === 0 && (
                            <p className="text-xs text-muted-foreground text-center py-6">
                                Sem dados.
                            </p>
                        )}
                    </div>
                </div>

                <div className="piq-in rounded-2xl border border-border bg-card p-5">
                    <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mb-1">
                        Heatmap por hora
                    </div>
                    <div className="font-display text-base font-semibold mb-3">Win rate por horário</div>
                    <div className="grid grid-cols-12 gap-1">
                        {hourHeatmap.map((h) => {
                            const wr = h.winrate;
                            const bg =
                                wr == null
                                    ? "bg-muted/20"
                                    : wr >= 60
                                      ? "bg-mint-bright/70"
                                      : wr >= 50
                                        ? "bg-mint-bright/40"
                                        : wr >= 40
                                          ? "bg-warning/40"
                                          : "bg-destructive/40";
                            return (
                                <div
                                    key={h.hora}
                                    className={cn("aspect-square rounded text-center grid place-items-center", bg)}
                                    title={`${h.hora}h — ${h.total} sinais, ${wr ?? "—"}% wr`}
                                >
                                    <span className="font-mono text-[9px] tabular text-foreground/80">
                                        {h.hora}h
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                    <div className="text-xs text-muted-foreground mt-3 flex items-center gap-3 flex-wrap">
                        <span className="inline-flex items-center gap-1">
                            <span className="size-2 rounded bg-destructive/40" /> &lt; 40%
                        </span>
                        <span className="inline-flex items-center gap-1">
                            <span className="size-2 rounded bg-warning/40" /> 40-49%
                        </span>
                        <span className="inline-flex items-center gap-1">
                            <span className="size-2 rounded bg-mint-bright/40" /> 50-59%
                        </span>
                        <span className="inline-flex items-center gap-1">
                            <span className="size-2 rounded bg-mint-bright/70" /> ≥ 60%
                        </span>
                    </div>
                </div>
            </section>
        </div>
    );
}

function Kpi({
    icon: Icon,
    label,
    value,
    sub,
    tone,
}: {
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    value: string;
    sub?: string;
    tone?: "mint" | "danger";
}) {
    return (
        <div className="piq-in rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-1.5 mb-1">
                <Icon className="size-3.5 text-muted-foreground" />
                <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                    {label}
                </span>
            </div>
            <div
                className={cn(
                    "font-display text-2xl font-bold tabular",
                    tone === "mint" && "text-mint-bright",
                    tone === "danger" && "text-destructive",
                )}
            >
                {value}
            </div>
            {sub && <div className="font-mono text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
        </div>
    );
}
