"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
    Activity,
    CheckCircle2,
    XCircle,
    Coins,
    Filter,
    Search,
    Shield,
    Target,
    Flame,
    Skull,
    Loader2,
    type LucideIcon,
} from "lucide-react";
import {
    STRATEGY_TIERS,
    TIER_BY_ID,
    highestMatchingTier,
    isValidTier,
    signalMatchesUserTier,
    type Market,
    type StrategyTier,
} from "@/lib/strategies";
import { useStrategyPreference } from "@/lib/useStrategyPreference";
import { fetchSignalsList, type SignalDetail } from "@/lib/api";
import { fmtDateTime, fmtUnits, cn } from "@/lib/format";

type ResultFilter = "all" | "GREEN" | "RED" | "PENDENTE";

const TIER_ICONS: Record<StrategyTier, LucideIcon> = {
    conservative: Shield,
    moderate: Target,
    aggressive: Flame,
    brute: Skull,
};

export function MarketPage({
    market,
    title,
    subtitle,
}: {
    market: Market;
    title: string;
    subtitle: string;
}) {
    const { preference, update } = useStrategyPreference();
    const userTier: StrategyTier = market === "cards" ? preference.cards : preference.corners;
    const userMeta = TIER_BY_ID[userTier];

    const [signals, setSignals] = useState<SignalDetail[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        fetchSignalsList("all", 500)
            .then((all) => {
                if (cancelled) return;
                const filtered = all.filter((s) => {
                    const isCards = (s.tipo_analise || "").toUpperCase() === "CARTOES";
                    return market === "cards" ? isCards : !isCards;
                });
                setSignals(filtered);
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : "Erro ao carregar sinais");
            })
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, [market]);

    const [onlyMyStrategy, setOnlyMyStrategy] = useState(true);
    const [result, setResult] = useState<ResultFilter>("all");
    const [q, setQ] = useState("");

    const annotated = useMemo(
        () =>
            signals.map((s) => ({
                signal: s,
                matched: ((s.matching_tiers || []).filter(isValidTier) as StrategyTier[]),
            })),
        [signals],
    );

    const filtered = useMemo(() => {
        return annotated.filter(({ signal, matched }) => {
            if (onlyMyStrategy && !signalMatchesUserTier(matched, userTier)) return false;
            if (result === "GREEN" && signal.resultado !== "GREEN") return false;
            if (result === "RED" && signal.resultado !== "RED") return false;
            if (result === "PENDENTE" && signal.resultado && signal.resultado !== "PENDENTE")
                return false;
            if (q && !(signal.jogo_descricao || "").toLowerCase().includes(q.toLowerCase())) return false;
            return true;
        });
    }, [annotated, onlyMyStrategy, userTier, result, q]);

    const hiddenByStrategy = useMemo(
        () =>
            onlyMyStrategy
                ? annotated.filter(({ matched }) => !signalMatchesUserTier(matched, userTier)).length
                : 0,
        [annotated, onlyMyStrategy, userTier],
    );

    const stats = useMemo(() => {
        const total = signals.length;
        const greens = signals.filter((s) => s.resultado === "GREEN").length;
        const reds = signals.filter((s) => s.resultado === "RED").length;
        const dec = greens + reds || 1;
        const roi = signals.reduce((a, s) => {
            if (s.resultado === "GREEN") return a + ((s.odd ?? 1) - 1);
            if (s.resultado === "RED") return a - 1;
            return a;
        }, 0);
        return {
            total,
            greens,
            reds,
            winrate: Number(((greens / dec) * 100).toFixed(1)),
            roi_total: Number(roi.toFixed(2)),
        };
    }, [signals]);

    const tierBreakdown = useMemo(() => {
        const breakdown: Record<StrategyTier, number> = {
            conservative: 0,
            moderate: 0,
            aggressive: 0,
            brute: 0,
        };
        for (const { matched } of annotated) {
            for (const t of matched) breakdown[t]++;
        }
        return breakdown;
    }, [annotated]);

    return (
        <div className="space-y-6 max-w-[1600px] mx-auto">
            <header className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.22em] text-muted-foreground uppercase">
                        Mercado {market === "cards" ? "/ Cartões" : "/ Escanteios"}
                    </div>
                    <h1 className="font-display text-3xl font-bold mt-1 text-gradient-mint">
                        {title}
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-xl">{subtitle}</p>
                </div>
                <div className="flex items-center gap-2 font-mono text-[10px] tracking-wider text-muted-foreground">
                    <span>SUA ESTRATÉGIA</span>
                    <span
                        className={cn(
                            "inline-flex items-center gap-1.5 px-2 py-1 rounded-full border tabular",
                            userMeta.chip,
                        )}
                    >
                        <span className="size-1.5 rounded-full bg-current" />
                        {userMeta.label}
                    </span>
                </div>
            </header>

            <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiTile label="Total sinais" value={stats.total} icon={Activity} tone="mint" />
                <KpiTile
                    label="Greens"
                    value={stats.greens}
                    sub={`${stats.reds} reds`}
                    icon={CheckCircle2}
                    tone="success"
                />
                <KpiTile
                    label="Winrate"
                    value={`${stats.winrate.toFixed(1)}%`}
                    icon={XCircle}
                    tone={stats.winrate >= 60 ? "success" : stats.winrate >= 45 ? "warning" : "danger"}
                />
                <KpiTile
                    label="ROI total"
                    value={fmtUnits(stats.roi_total)}
                    icon={Coins}
                    tone={stats.roi_total >= 0 ? "success" : "danger"}
                />
            </section>

            <section className="piq-in rounded-2xl border border-border bg-card p-5">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                    <div>
                        <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                            Selecione seu nível
                        </div>
                        <div className="font-display text-lg font-semibold mt-0.5">
                            Tiers de estratégia
                        </div>
                    </div>
                    <span className="font-mono text-[10px] tracking-wider text-muted-foreground">
                        DISTRIBUIÇÃO ATUAL ({signals.length} sinais)
                    </span>
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    {STRATEGY_TIERS.map((t) => {
                        const Icon = TIER_ICONS[t.id];
                        const active = t.id === userTier;
                        const count = tierBreakdown[t.id] ?? 0;
                        const pct = signals.length
                            ? Math.round((count / signals.length) * 100)
                            : 0;
                        return (
                            <motion.button
                                key={t.id}
                                onClick={() => update({ [market]: t.id })}
                                whileHover={{ y: -2 }}
                                whileTap={{ scale: 0.98 }}
                                className={cn(
                                    "text-left rounded-xl border p-3 transition relative overflow-hidden",
                                    active
                                        ? "border-mint/50 bg-mint/5 glow-mint"
                                        : "border-border bg-background/40 hover:border-border/80",
                                )}
                            >
                                <div className="flex items-center justify-between">
                                    <div
                                        className={cn(
                                            "size-7 rounded-lg grid place-items-center border",
                                            t.chip,
                                        )}
                                    >
                                        <Icon className="size-3.5" />
                                    </div>
                                    <span className="font-mono text-[10px] tabular text-muted-foreground">
                                        {count} · {pct}%
                                    </span>
                                </div>
                                <div className="mt-2 font-display text-sm font-semibold">
                                    {t.label}
                                </div>
                                <div className="text-[11px] text-muted-foreground leading-snug mt-0.5">
                                    {t.description}
                                </div>
                                <div className="mt-2 h-1 rounded-full bg-muted overflow-hidden">
                                    <div
                                        className={cn(
                                            "h-full",
                                            t.id === "conservative" && "bg-success",
                                            t.id === "moderate" && "bg-mint",
                                            t.id === "aggressive" && "bg-warning",
                                            t.id === "brute" && "bg-destructive",
                                        )}
                                        style={{ width: `${pct}%` }}
                                    />
                                </div>
                            </motion.button>
                        );
                    })}
                </div>
            </section>

            <section className="piq-in rounded-2xl border border-border bg-card overflow-hidden">
                <div className="p-5 border-b border-border flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3 flex-wrap">
                        <div className="font-display text-base font-semibold">
                            Histórico de sinais
                        </div>
                        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={onlyMyStrategy}
                                onChange={(e) => setOnlyMyStrategy(e.target.checked)}
                                className="accent-[var(--color-mint)] size-3.5"
                            />
                            Apenas <span className={userMeta.accent}>{userMeta.label}</span>
                            {onlyMyStrategy && hiddenByStrategy > 0 && (
                                <span className="font-mono text-[10px] tabular">
                                    ({hiddenByStrategy} ocultos)
                                </span>
                            )}
                        </label>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="relative">
                            <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                            <input
                                value={q}
                                onChange={(e) => setQ(e.target.value)}
                                placeholder="Buscar jogo…"
                                className="pl-7 pr-3 py-1.5 rounded-lg border border-border bg-background/60 text-xs w-44 focus:outline-none focus:border-mint/50"
                            />
                        </div>
                        <SegmentedFilter value={result} onChange={setResult} />
                    </div>
                </div>

                {loading ? (
                    <div className="flex items-center justify-center py-16 text-muted-foreground">
                        <Loader2 className="size-5 animate-spin" />
                    </div>
                ) : error ? (
                    <div className="p-10 text-center text-sm text-destructive">{error}</div>
                ) : filtered.length === 0 ? (
                    <div className="p-10 text-center">
                        <Filter className="size-5 text-muted-foreground mx-auto mb-2" />
                        <p className="text-sm text-muted-foreground">
                            {onlyMyStrategy && annotated.length > 0
                                ? `Nenhum sinal corresponde a "${userMeta.label}". Desligue o filtro para ver todos.`
                                : "Nenhum sinal encontrado."}
                        </p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="border-b border-border bg-background/30">
                                <tr className="font-mono text-[10px] tracking-wider text-muted-foreground">
                                    <Th>HORA</Th>
                                    <Th>JOGO</Th>
                                    <Th>SINAL</Th>
                                    <Th>ESTRATÉGIA</Th>
                                    <Th align="right">SCORE</Th>
                                    <Th align="right">PROJ.</Th>
                                    <Th align="right">EDGE</Th>
                                    <Th align="right">LINHA</Th>
                                    <Th align="right">ODD</Th>
                                    <Th align="right">FINAL</Th>
                                    <Th align="center">RES</Th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(({ signal: s, matched }, i) => {
                                    const top = highestMatchingTier(matched);
                                    const tierMeta = top ? TIER_BY_ID[top] : null;
                                    return (
                                        <tr
                                            key={s.id ?? i}
                                            className="border-b border-border/40 hover:bg-mint/5 transition"
                                        >
                                            <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground whitespace-nowrap tabular">
                                                {fmtDateTime(s.timestamp)}
                                            </td>
                                            <td className="px-4 py-3 font-medium truncate max-w-[220px]">
                                                {s.jogo_descricao || "—"}
                                            </td>
                                            <td className="px-4 py-3 text-xs text-muted-foreground">
                                                {s.tipo_sinal}
                                            </td>
                                            <td className="px-4 py-3">
                                                {tierMeta ? (
                                                    <span
                                                        className={cn(
                                                            "inline-flex font-mono text-[10px] tracking-wider px-1.5 py-0.5 rounded border",
                                                            tierMeta.chip,
                                                        )}
                                                    >
                                                        {tierMeta.short}
                                                    </span>
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </td>
                                            <Num v={s.pressure_score} digits={1} />
                                            <Num v={s.projecao} digits={1} />
                                            <Num v={s.edge} digits={2} signed />
                                            <Num v={s.linha} digits={1} />
                                            <Num v={s.odd} digits={2} />
                                            <Num v={s.escanteios_final} digits={0} />
                                            <td className="px-4 py-3 text-center">
                                                <ResultPill r={s.resultado || "PENDENTE"} />
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </div>
    );
}

function Th({
    children,
    align = "left",
}: {
    children: React.ReactNode;
    align?: "left" | "right" | "center";
}) {
    return (
        <th
            className={cn(
                "px-4 py-2.5 font-medium",
                align === "left" && "text-left",
                align === "right" && "text-right",
                align === "center" && "text-center",
            )}
        >
            {children}
        </th>
    );
}

function Num({
    v,
    digits = 1,
    signed = false,
}: {
    v: number | null | undefined;
    digits?: number;
    signed?: boolean;
}) {
    if (v == null)
        return (
            <td className="px-4 py-3 text-right font-mono text-xs text-muted-foreground tabular">
                —
            </td>
        );
    const s = signed && v >= 0 ? `+${v.toFixed(digits)}` : v.toFixed(digits);
    return (
        <td className="px-4 py-3 text-right font-mono text-xs tabular">{s}</td>
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

function SegmentedFilter({
    value,
    onChange,
}: {
    value: ResultFilter;
    onChange: (v: ResultFilter) => void;
}) {
    const opts: { v: ResultFilter; label: string; cls?: string }[] = [
        { v: "all", label: "Todos" },
        { v: "GREEN", label: "Green", cls: "data-[on=true]:text-success" },
        { v: "RED", label: "Red", cls: "data-[on=true]:text-destructive" },
        { v: "PENDENTE", label: "Pend.", cls: "data-[on=true]:text-warning" },
    ];
    return (
        <div className="inline-flex rounded-lg border border-border bg-background/60 p-0.5">
            {opts.map((o) => {
                const on = value === o.v;
                return (
                    <button
                        key={o.v}
                        data-on={on}
                        onClick={() => onChange(o.v)}
                        className={cn(
                            "px-2.5 py-1 text-[11px] font-mono tracking-wider rounded-md transition",
                            on
                                ? "bg-mint/10 text-mint-bright"
                                : "text-muted-foreground hover:text-foreground",
                            o.cls,
                        )}
                    >
                        {o.label.toUpperCase()}
                    </button>
                );
            })}
        </div>
    );
}

function KpiTile({
    label,
    value,
    sub,
    icon: Icon,
    tone,
}: {
    label: string;
    value: number | string;
    sub?: string;
    icon: LucideIcon;
    tone: "mint" | "success" | "warning" | "danger";
}) {
    const accent =
        tone === "success"
            ? "text-success"
            : tone === "warning"
                ? "text-warning"
                : tone === "danger"
                    ? "text-destructive"
                    : "text-mint-bright";
    return (
        <div className="piq-in relative rounded-2xl border border-border bg-card p-4 overflow-hidden">
            <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                    {label}
                </span>
                <Icon className={cn("size-4", accent)} />
            </div>
            <div className={cn("font-mono font-bold text-3xl mt-2 tabular", accent)}>
                {value}
            </div>
            {sub && (
                <div className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">
                    {sub}
                </div>
            )}
        </div>
    );
}
