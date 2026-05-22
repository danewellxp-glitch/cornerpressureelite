"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
    History,
    Search,
    Filter,
    CheckCircle2,
    XCircle,
    Coins,
    Activity,
    Loader2,
} from "lucide-react";
import {
    TIER_BY_ID,
    isValidTier,
    highestMatchingTier,
    signalMatchesUserTier,
    type Market,
    type StrategyTier,
} from "@/lib/strategies";
import { useStrategyPreference } from "@/lib/useStrategyPreference";
import { fetchSignalsList, type SignalDetail } from "@/lib/api";
import { fmtDateTime, fmtUnits, cn } from "@/lib/format";

type ResultFilter = "all" | "GREEN" | "RED";
type MarketFilter = "all" | "ESCANTEIOS" | "CARTOES";

// Histórico = acertividade do sistema. Só conta sinais com veredito definitivo
// (GREEN/RED). Pendente, vazio e EXPIRADO não têm acertividade → ficam de fora.
const isResolved = (r: string | null | undefined): r is "GREEN" | "RED" =>
    r === "GREEN" || r === "RED";

export default function SinaisHistoricoPage() {
    const { preference } = useStrategyPreference();
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
                setSignals(all);
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : "Erro ao carregar sinais");
            })
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, []);

    const [result, setResult] = useState<ResultFilter>("all");
    const [marketF, setMarketF] = useState<MarketFilter>("all");
    const [q, setQ] = useState("");
    const [onlyMyStrategy, setOnlyMyStrategy] = useState(true);

    // Sinais ainda sem veredito (aguardando FT / EXPIRADO / vazio) — não entram
    // no histórico de acertividade, só mostramos a contagem pra transparência.
    const pendingCount = useMemo(
        () => signals.filter((s) => !isResolved(s.resultado)).length,
        [signals],
    );

    const all = useMemo(
        () =>
            signals
                .filter((s) => isResolved(s.resultado))
                .map((s) => {
                    const market: Market = (s.tipo_analise || "").toUpperCase() === "CARTOES" ? "cards" : "corners";
                    const userTier = market === "cards" ? preference.cards : preference.corners;
                    const matched = ((s.matching_tiers || []).filter(isValidTier)) as StrategyTier[];
                    return { signal: s, market, userTier, matched };
                }),
        [signals, preference],
    );

    const filtered = useMemo(
        () =>
            all.filter(({ signal, market, userTier, matched }) => {
                if (onlyMyStrategy && !signalMatchesUserTier(matched, userTier)) return false;
                if (marketF !== "all") {
                    if (marketF === "ESCANTEIOS" && market !== "corners") return false;
                    if (marketF === "CARTOES" && market !== "cards") return false;
                }
                if (result === "GREEN" && signal.resultado !== "GREEN") return false;
                if (result === "RED" && signal.resultado !== "RED") return false;
                if (q && !(signal.jogo_descricao || "").toLowerCase().includes(q.toLowerCase())) return false;
                return true;
            }),
        [all, result, marketF, q, onlyMyStrategy],
    );

    const stats = useMemo(() => {
        const total = filtered.length;
        const greens = filtered.filter((x) => x.signal.resultado === "GREEN").length;
        const reds = filtered.filter((x) => x.signal.resultado === "RED").length;
        const dec = greens + reds || 1;
        const roi = filtered.reduce((a, { signal: s }) => {
            if (s.resultado === "GREEN") return a + ((s.odd ?? 1) - 1);
            if (s.resultado === "RED") return a - 1;
            return a;
        }, 0);
        return {
            total,
            greens,
            reds,
            winrate: Number(((greens / dec) * 100).toFixed(1)),
            roi: Number(roi.toFixed(2)),
        };
    }, [filtered]);

    const hidden = useMemo(
        () => (onlyMyStrategy ? all.filter((x) => !signalMatchesUserTier(x.matched, x.userTier)).length : 0),
        [all, onlyMyStrategy],
    );

    return (
        <div className="space-y-6 max-w-[1600px] mx-auto">
            <header className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.22em] text-muted-foreground uppercase flex items-center gap-2">
                        <History className="size-3" /> Histórico consolidado
                    </div>
                    <h1 className="font-display text-3xl font-bold mt-1 text-gradient-mint">
                        Sinais
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-xl">
                        Acertividade do sistema: todo sinal já resolvido (GREEN/RED), independente de
                        você ter entrado ou não.
                        {pendingCount > 0 && (
                            <span className="block font-mono text-[11px] text-muted-foreground/70 mt-1">
                                {pendingCount} sinal{pendingCount > 1 ? "s" : ""} ainda aguardando
                                resultado — não conta na acertividade.
                            </span>
                        )}
                    </p>
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono tracking-wider text-muted-foreground">
                    <TierChip label="ESC" tier={preference.corners} />
                    <TierChip label="CRT" tier={preference.cards} />
                </div>
            </header>

            <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Kpi label="Sinais resolvidos" value={stats.total} icon={Activity} tone="mint" />
                <Kpi label="Greens" value={stats.greens} sub={`${stats.reds} reds`} icon={CheckCircle2} tone="success" />
                <Kpi
                    label="Winrate"
                    value={`${stats.winrate}%`}
                    icon={XCircle}
                    tone={stats.winrate >= 60 ? "success" : stats.winrate >= 45 ? "warning" : "danger"}
                />
                <Kpi
                    label="ROI total"
                    value={fmtUnits(stats.roi)}
                    icon={Coins}
                    tone={stats.roi >= 0 ? "success" : "danger"}
                />
            </section>

            <section className="piq-in rounded-2xl border border-border bg-card overflow-hidden">
                <div className="p-5 border-b border-border flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3 flex-wrap">
                        <div className="font-display text-base font-semibold">Linha do tempo</div>
                        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={onlyMyStrategy}
                                onChange={(e) => setOnlyMyStrategy(e.target.checked)}
                                className="accent-[var(--color-mint)] size-3.5"
                            />
                            Apenas minha estratégia
                            {onlyMyStrategy && hidden > 0 && (
                                <span className="font-mono text-[10px] tabular">({hidden} ocultos)</span>
                            )}
                        </label>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <div className="relative">
                            <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                            <input
                                value={q}
                                onChange={(e) => setQ(e.target.value)}
                                placeholder="Buscar jogo…"
                                className="pl-7 pr-3 py-1.5 rounded-lg border border-border bg-background/60 text-xs w-44 focus:outline-none focus:border-mint/50"
                            />
                        </div>
                        <Segmented
                            value={marketF}
                            onChange={setMarketF}
                            opts={[
                                { v: "all", label: "Todos" },
                                { v: "ESCANTEIOS", label: "Esc." },
                                { v: "CARTOES", label: "Crt." },
                            ]}
                        />
                        <Segmented
                            value={result}
                            onChange={setResult}
                            opts={[
                                { v: "all", label: "—" },
                                { v: "GREEN", label: "Green", cls: "data-[on=true]:text-success" },
                                { v: "RED", label: "Red", cls: "data-[on=true]:text-destructive" },
                            ]}
                        />
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
                            Nenhum sinal corresponde aos filtros.
                        </p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="border-b border-border bg-background/30">
                                <tr className="font-mono text-[10px] tracking-wider text-muted-foreground">
                                    <Th>HORA</Th>
                                    <Th>JOGO</Th>
                                    <Th>MERC.</Th>
                                    <Th>SINAL</Th>
                                    <Th>ESTRAT.</Th>
                                    <Th align="right">SCORE</Th>
                                    <Th align="right">PROJ.</Th>
                                    <Th align="right">EDGE</Th>
                                    <Th align="right">LINHA</Th>
                                    <Th align="right">ODD</Th>
                                    <Th align="right">FINAL</Th>
                                    <Th align="center">RES</Th>
                                </tr>
                            </thead>
                            <motion.tbody initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.01 } } }}>
                                {filtered.slice(0, 80).map(({ signal: s, matched, market }, i) => {
                                    const top = highestMatchingTier(matched);
                                    const tierMeta = top ? TIER_BY_ID[top] : null;
                                    return (
                                        <motion.tr
                                            key={s.id ?? i}
                                            variants={{ hidden: { opacity: 0, y: 4 }, visible: { opacity: 1, y: 0 } }}
                                            className="border-b border-border/40 hover:bg-mint/5 transition"
                                        >
                                            <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground whitespace-nowrap tabular">
                                                {fmtDateTime(s.timestamp)}
                                            </td>
                                            <td className="px-4 py-3 font-medium truncate max-w-[220px]">
                                                {s.jogo_descricao || "—"}
                                            </td>
                                            <td className="px-4 py-3">
                                                <span
                                                    className={cn(
                                                        "inline-flex font-mono text-[10px] tracking-wider px-1.5 py-0.5 rounded border",
                                                        market === "cards"
                                                            ? "text-warning border-warning/30 bg-warning/10"
                                                            : "text-mint-bright border-mint/30 bg-mint/10",
                                                    )}
                                                >
                                                    {market === "cards" ? "CRT" : "ESC"}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-xs text-muted-foreground">{s.tipo_sinal}</td>
                                            <td className="px-4 py-3">
                                                {tierMeta ? (
                                                    <span className={cn("inline-flex font-mono text-[10px] tracking-wider px-1.5 py-0.5 rounded border", tierMeta.chip)}>
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
                                        </motion.tr>
                                    );
                                })}
                            </motion.tbody>
                        </table>
                        {filtered.length > 80 && (
                            <div className="p-4 text-center font-mono text-[10px] tracking-wider text-muted-foreground border-t border-border">
                                EXIBINDO 80 / {filtered.length} SINAIS
                            </div>
                        )}
                    </div>
                )}
            </section>
        </div>
    );
}

function TierChip({ label, tier }: { label: string; tier: StrategyTier }) {
    const m = TIER_BY_ID[tier];
    return (
        <span className="inline-flex items-center gap-1.5">
            <span className="text-muted-foreground">{label}</span>
            <span className={cn("inline-flex font-mono text-[10px] px-2 py-0.5 rounded-full border", m.chip)}>
                {m.label}
            </span>
        </span>
    );
}

function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" | "center" }) {
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

function Num({ v, digits = 1, signed = false }: { v: number | null | undefined; digits?: number; signed?: boolean }) {
    if (v == null)
        return <td className="px-4 py-3 text-right font-mono text-xs text-muted-foreground tabular">—</td>;
    const s = signed && v >= 0 ? `+${v.toFixed(digits)}` : v.toFixed(digits);
    return <td className="px-4 py-3 text-right font-mono text-xs tabular">{s}</td>;
}

function ResultPill({ r }: { r: string }) {
    const map: Record<string, string> = {
        GREEN: "text-success border-success/40 bg-success/10",
        RED: "text-destructive border-destructive/40 bg-destructive/10",
        PENDENTE: "text-warning border-warning/40 bg-warning/10",
    };
    return (
        <span className={cn("inline-flex font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border", map[r] ?? "border-border bg-muted/40 text-muted-foreground")}>
            {r === "PENDENTE" ? "PEND" : r}
        </span>
    );
}

function Segmented<T extends string>({
    value,
    onChange,
    opts,
}: {
    value: T;
    onChange: (v: T) => void;
    opts: { v: T; label: string; cls?: string }[];
}) {
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
                            on ? "bg-mint/10 text-mint-bright" : "text-muted-foreground hover:text-foreground",
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

function Kpi({
    label,
    value,
    sub,
    icon: Icon,
    tone,
}: {
    label: string;
    value: number | string;
    sub?: string;
    icon: React.ComponentType<{ className?: string }>;
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
        <div className="piq-in rounded-2xl border border-border bg-card p-4">
            <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">{label}</span>
                <Icon className={cn("size-4", accent)} />
            </div>
            <div className={cn("font-mono font-bold text-3xl mt-2 tabular", accent)}>{value}</div>
            {sub && <div className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">{sub}</div>}
        </div>
    );
}
