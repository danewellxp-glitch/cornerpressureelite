"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
    Activity,
    CheckCircle2,
    XCircle,
    Clock,
    TrendingUp,
    Loader2,
    Wallet,
    Check,
    X,
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
import { OnboardingBanner } from "@/components/shell/OnboardingBanner";
import { useDashboard } from "@/components/shell/Shell";
import {
    fetchUserSignals,
    fetchBancaSummary,
    decideSignal,
    type UserSignalDetail,
    type SignalDetail,
    type SignalResult,
    type BancaSummary,
} from "@/lib/api";
import { fmtTime, fmtUnits, cn } from "@/lib/format";

type PeriodId = "today" | "7d" | "30d" | "all";

const PERIOD_OPTS: { v: PeriodId; label: string; ms: number | null }[] = [
    { v: "today", label: "Hoje", ms: null },
    { v: "7d", label: "7D", ms: 7 * 86_400_000 },
    { v: "30d", label: "30D", ms: 30 * 86_400_000 },
    { v: "all", label: "Tudo", ms: Number.POSITIVE_INFINITY },
];

function filterByPeriod(signals: UserSignalDetail[], period: PeriodId): UserSignalDetail[] {
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

/**
 * Stats user-scoped: conta SO decisions com decision='entered'. Pending/skipped
 * sao ignorados. ROI vem de payout_cents (sum) / staked.
 */
function computeUserStats(signals: UserSignalDetail[]) {
    const entered = signals.filter((s) => s.decision.decision === "entered");
    const greens = entered.filter((s) => s.decision.resultado === "GREEN").length;
    const reds = entered.filter((s) => s.decision.resultado === "RED").length;
    const pendentes = entered.filter((s) => !s.decision.resultado).length;
    const aguardando = signals.filter((s) => s.decision.decision === "pending").length;
    const decididos = greens + reds;
    const winrate = decididos > 0 ? (greens / decididos) * 100 : 0;
    const staked = entered.reduce((a, s) => a + (s.decision.valor_apostado_cents ?? 0), 0);
    const pnl = entered.reduce(
        (a, s) =>
            s.decision.resultado && s.decision.payout_cents != null
                ? a + s.decision.payout_cents
                : a,
        0,
    );
    const roi = staked > 0 ? (pnl / staked) * 100 : 0;
    return {
        total: entered.length,
        greens,
        reds,
        pendentes,
        aguardando,
        winrate: Number(winrate.toFixed(1)),
        roi: Number((pnl / 100).toFixed(2)), // reais
        roi_pct: Number(roi.toFixed(2)),
        staked_cents: staked,
        pnl_cents: pnl,
    };
}

// Compat shim p/ SignalsDrawer e ResultPill que esperam o shape antigo.
function toLegacySignal(s: UserSignalDetail): SignalDetail {
    return {
        id: s.signal_id,
        timestamp: s.timestamp,
        liga_nome: null,
        jogo_descricao: s.jogo_descricao,
        tipo_sinal: s.tipo_sinal,
        pressure_score: s.pressure_score,
        projecao: s.projecao,
        edge: s.edge,
        linha: s.linha,
        odd: s.odd,
        resultado: s.decision.resultado ?? s.signal_resultado ?? "PENDENTE",
        escanteios_final: s.escanteios_final,
        tipo_analise: s.tipo_analise,
        matching_tiers: s.matching_tiers,
        minuto: s.minuto,
        placar: s.placar,
        roi: null,
    };
}

export default function DashboardPage() {
    const { data: streamData } = useDashboard();
    const [drawer, setDrawer] = useState<SignalResult | null>(null);
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);

    const [period, setPeriod] = useState<PeriodId>("7d");
    const [allSignals, setAllSignals] = useState<UserSignalDetail[]>([]);
    const [banca, setBanca] = useState<BancaSummary | null>(null);
    const [loadingSignals, setLoadingSignals] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [decideModal, setDecideModal] = useState<UserSignalDetail | null>(null);

    const reload = useCallback(async () => {
        try {
            setLoadingSignals(true);
            setLoadError(null);
            const [list, b] = await Promise.all([
                fetchUserSignals(500),
                fetchBancaSummary().catch(() => null),
            ]);
            setAllSignals(list);
            setBanca(b);
        } catch (e) {
            const msg = e instanceof Error ? e.message : "Erro ao carregar sinais";
            console.error("[Dashboard] reload:", msg);
            setLoadError(msg);
        } finally {
            setLoadingSignals(false);
        }
    }, []);

    useEffect(() => {
        reload();
    }, [reload]);

    const filteredSignals = useMemo(
        () => filterByPeriod(allSignals, period),
        [allSignals, period],
    );
    const stats = useMemo(() => computeUserStats(filteredSignals), [filteredSignals]);

    const chart = useMemo(() => {
        let cum = 0;
        return [...filteredSignals]
            .filter((s) => s.decision.decision === "entered" && s.decision.resultado)
            .sort((a, b) => {
                const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
                const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
                return ta - tb;
            })
            .slice(-30)
            .map((s, i) => {
                cum += (s.decision.payout_cents ?? 0) / 100;
                return { name: `#${i + 1}`, roi: Number(cum.toFixed(2)) };
            });
    }, [filteredSignals]);

    const cumLatest = chart.length ? chart[chart.length - 1].roi : 0;
    const periodLabel = PERIOD_OPTS.find((p) => p.v === period)?.label ?? "";

    const drawerSignals = useMemo(() => filteredSignals.map(toLegacySignal), [filteredSignals]);

    if (loadingSignals && allSignals.length === 0) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
                <Loader2 className="size-6 animate-spin" />
                <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO SINAIS…</span>
            </div>
        );
    }

    const bancaConfigured = banca?.configured === true;

    return (
        <div className="space-y-6 max-w-[1600px] mx-auto">
            <OnboardingBanner />

            {!bancaConfigured && (
                <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 flex items-start gap-3">
                    <Wallet className="size-5 text-warning shrink-0 mt-0.5" />
                    <div className="flex-1">
                        <div className="font-display text-sm font-semibold mb-1">
                            Configure sua banca pra começar a contar ROI
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Enquanto a banca não estiver setada, os sinais aparecem como pendentes de
                            decisão mas o ROI não é calculado. Vá em{" "}
                            <Link href="/banca" className="text-warning underline">
                                Banca
                            </Link>{" "}
                            e defina seu saldo inicial.
                        </p>
                    </div>
                </div>
            )}

            {loadError && (
                <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive flex items-start gap-2">
                    <span className="font-mono tracking-wider uppercase shrink-0">ERRO:</span>
                    <span>Não foi possível carregar os sinais ({loadError}). Recarregue a página.</span>
                </div>
            )}

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

            {/* KPIs user-scoped: contam SO decisions entered */}
            <section className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                <KpiCard
                    label="Apostas entradas"
                    value={stats.total}
                    sub={
                        stats.aguardando > 0
                            ? `${stats.aguardando} aguardam decisão`
                            : periodLabel
                    }
                    icon={Activity}
                    tone="mint"
                    onClick={() => setDrawer("all")}
                />
                <KpiCard
                    label="Greens"
                    value={stats.greens}
                    sub={`${stats.winrate.toFixed(0)}% winrate`}
                    icon={CheckCircle2}
                    tone="success"
                    onClick={() => setDrawer("GREEN")}
                />
                <KpiCard
                    label="Reds"
                    value={stats.reds}
                    sub={`${stats.greens + stats.reds} decididos`}
                    icon={XCircle}
                    tone="danger"
                    onClick={() => setDrawer("RED")}
                />
                <KpiCard
                    label="Pendentes"
                    value={stats.pendentes}
                    sub={stats.pendentes > 0 ? "aguardando FT" : "—"}
                    icon={Clock}
                    tone="warning"
                    onClick={() => setDrawer("PENDENTE")}
                />
            </section>

            <MarketIntelligencePanel />

            <section className="grid gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2 piq-in rounded-2xl border border-border bg-card p-5">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                                P&L Acumulado (apostas entradas)
                            </div>
                            <div className="font-display text-lg font-semibold mt-0.5">
                                {chart.length} apostas — {periodLabel}
                            </div>
                        </div>
                        <span
                            className={cn(
                                "font-mono text-base font-bold tabular",
                                cumLatest >= 0 ? "text-mint-bright" : "text-destructive",
                            )}
                        >
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
                            <div className="flex items-center justify-center h-full text-xs text-muted-foreground text-center px-6">
                                {bancaConfigured
                                    ? "Sem apostas registradas no período. Use a coluna 'Decisão' nos sinais abaixo pra começar."
                                    : "Configure sua banca primeiro pra começar a registrar apostas."}
                            </div>
                        )}
                    </div>
                </div>

                <GamesPanel live_games={streamData?.live_games} />
            </section>

            {/* Sinais recentes — agora interativos (decisão pending/entered/skipped) */}
            <section className="piq-in rounded-2xl border border-border bg-card overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-border">
                    <div>
                        <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                            Sinais recentes
                        </div>
                        <div className="font-display text-lg font-semibold mt-0.5">
                            Últimos {Math.min(10, filteredSignals.length)} — {periodLabel}
                            {stats.aguardando > 0 && (
                                <span className="ml-2 text-xs text-warning font-mono">
                                    · {stats.aguardando} aguardam decisão
                                </span>
                            )}
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
                                <th className="text-center font-medium px-4 py-2.5">DECISÃO</th>
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
                                .map((s) => (
                                    <SignalRow
                                        key={s.signal_id}
                                        signal={s}
                                        onEnter={() => setDecideModal(s)}
                                        onSkip={async () => {
                                            try {
                                                await decideSignal(s.signal_id, { decision: "skipped" });
                                                await reload();
                                            } catch (e) {
                                                console.error("skip failed", e);
                                            }
                                        }}
                                    />
                                ))}
                            {filteredSignals.length === 0 && (
                                <tr>
                                    <td colSpan={6} className="px-4 py-8 text-center text-xs text-muted-foreground">
                                        Sem sinais no período.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {decideModal && (
                <DecisionModal
                    signal={decideModal}
                    banca={banca}
                    onClose={() => setDecideModal(null)}
                    onConfirmed={async () => {
                        setDecideModal(null);
                        await reload();
                    }}
                />
            )}

            <SignalsDrawer
                open={drawer !== null}
                onClose={() => setDrawer(null)}
                filter={drawer ?? "all"}
                signals={drawerSignals}
                periodLabel={periodLabel}
            />
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────────
 *  SignalRow — linha com decision UI
 * ────────────────────────────────────────────────────────────────── */

function SignalRow({
    signal,
    onEnter,
    onSkip,
}: {
    signal: UserSignalDetail;
    onEnter: () => void;
    onSkip: () => void;
}) {
    const d = signal.decision;
    return (
        <tr
            className={cn(
                "border-b border-border/40 hover:bg-mint/5 transition",
                d.decision === "skipped" && "opacity-50",
            )}
        >
            <td className="px-4 py-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
                {fmtTime(signal.timestamp ?? null)}
            </td>
            <td className="px-4 py-3 font-medium truncate max-w-[260px]">
                {signal.jogo_descricao || "—"}
            </td>
            <td className="px-4 py-3 text-xs text-muted-foreground">{signal.tipo_sinal}</td>
            <td className="px-4 py-3 text-right font-mono text-xs">
                {signal.odd?.toFixed(2) ?? "—"}
            </td>
            <td className="px-4 py-3 text-center">
                {d.decision === "pending" ? (
                    <div className="inline-flex gap-1.5">
                        <button
                            onClick={onEnter}
                            className="inline-flex items-center gap-1 px-2 py-1 font-mono text-[10px] tracking-wider text-mint border border-mint/40 hover:bg-mint hover:text-background transition rounded-md"
                        >
                            <Check className="size-3" />
                            ENTREI
                        </button>
                        <button
                            onClick={onSkip}
                            className="inline-flex items-center gap-1 px-2 py-1 font-mono text-[10px] tracking-wider text-muted-foreground border border-border hover:text-foreground hover:border-foreground/40 transition rounded-md"
                        >
                            <X className="size-3" />
                            PULEI
                        </button>
                    </div>
                ) : d.decision === "entered" ? (
                    <div className="inline-flex flex-col items-center gap-0.5">
                        <span className="font-mono text-[10px] tracking-wider text-mint">
                            R$ {((d.valor_apostado_cents ?? 0) / 100).toFixed(2)}
                        </span>
                        <span className="font-mono text-[9px] tracking-wider text-muted-foreground">
                            @ {d.odd_entrada?.toFixed(2)}
                        </span>
                    </div>
                ) : (
                    <span className="font-mono text-[10px] tracking-wider text-muted-foreground">
                        PULADO
                    </span>
                )}
            </td>
            <td className="px-4 py-3 text-center">
                <ResultPill r={d.resultado ?? signal.signal_resultado ?? "PENDENTE"} />
            </td>
        </tr>
    );
}

/* ──────────────────────────────────────────────────────────────────
 *  DecisionModal — entrar com odd + valor
 * ────────────────────────────────────────────────────────────────── */

function DecisionModal({
    signal,
    banca,
    onClose,
    onConfirmed,
}: {
    signal: UserSignalDetail;
    banca: BancaSummary | null;
    onClose: () => void;
    onConfirmed: () => void;
}) {
    const sugestao =
        banca?.configured && banca.unit_pct
            ? Math.round((banca.banca_atual_cents * banca.unit_pct) / 100)
            : 0;
    const [oddStr, setOddStr] = useState((signal.odd ?? 0).toFixed(2));
    const [valStr, setValStr] = useState((sugestao / 100).toFixed(2));
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState<string | null>(null);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !busy) onClose();
        };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, [busy, onClose]);

    const confirm = async () => {
        const odd = parseFloat(oddStr);
        const val = Math.round(parseFloat(valStr) * 100);
        if (!odd || odd <= 1.0) {
            setErr("Odd precisa ser > 1.00");
            return;
        }
        if (!val || val <= 0) {
            setErr("Valor apostado precisa ser > 0");
            return;
        }
        if (banca?.configured && val > banca.banca_atual_cents) {
            setErr(
                `Valor maior que saldo (R$ ${(banca.banca_atual_cents / 100).toFixed(2)})`,
            );
            return;
        }
        setBusy(true);
        setErr(null);
        try {
            await decideSignal(signal.signal_id, {
                decision: "entered",
                odd_entrada: odd,
                valor_apostado_cents: val,
            });
            onConfirmed();
        } catch (e) {
            setErr(e instanceof Error ? e.message : "Erro ao registrar");
            setBusy(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 grid place-items-center bg-background/80 backdrop-blur-sm p-4"
            onClick={() => !busy && onClose()}
        >
            <div
                className="w-full max-w-md border border-border bg-card p-6 space-y-5"
                onClick={(e) => e.stopPropagation()}
            >
                <div>
                    <div className="font-mono text-[10px] tracking-[0.22em] uppercase text-mint mb-2">
                        registrar entrada
                    </div>
                    <h3 className="font-display text-xl font-bold leading-tight">
                        {signal.jogo_descricao}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1.5 font-mono">
                        {signal.tipo_sinal} · linha {signal.linha} · score{" "}
                        {signal.pressure_score} · edge {signal.edge}
                    </p>
                </div>

                {!banca?.configured && (
                    <div className="text-xs text-warning border border-warning/40 bg-warning/10 p-2 rounded">
                        Banca não configurada — entrada vai contar pro ROI mas o saldo da banca não vai debitar.
                    </div>
                )}

                <div className="space-y-3">
                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Odd pega
                        </span>
                        <input
                            type="number"
                            step="0.01"
                            min="1.01"
                            value={oddStr}
                            onChange={(e) => setOddStr(e.target.value)}
                            className="mt-1 w-full bg-input border border-border px-3 py-2 font-mono text-sm tabular focus:outline-none focus:border-mint"
                            disabled={busy}
                        />
                    </label>
                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Valor (R$)
                        </span>
                        <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            value={valStr}
                            onChange={(e) => setValStr(e.target.value)}
                            className="mt-1 w-full bg-input border border-border px-3 py-2 font-mono text-sm tabular focus:outline-none focus:border-mint"
                            disabled={busy}
                        />
                        {banca?.configured && (
                            <span className="font-mono text-[10px] text-muted-foreground mt-1 block">
                                saldo: R$ {(banca.banca_atual_cents / 100).toFixed(2)}
                                {banca.unit_pct &&
                                    ` · sugestão ${banca.unit_pct}% = R$ ${(sugestao / 100).toFixed(2)}`}
                            </span>
                        )}
                    </label>
                </div>

                {err && (
                    <div className="text-xs text-destructive border border-destructive/40 bg-destructive/10 p-2 rounded font-mono">
                        {err}
                    </div>
                )}

                <div className="flex gap-2 justify-end">
                    <button
                        onClick={onClose}
                        disabled={busy}
                        className="px-4 py-2 border border-border font-mono text-xs tracking-wider hover:text-foreground text-muted-foreground transition"
                    >
                        CANCELAR
                    </button>
                    <button
                        onClick={confirm}
                        disabled={busy}
                        className="px-4 py-2 border border-mint bg-mint text-background font-mono text-xs tracking-wider hover:bg-mint-bright transition disabled:opacity-50"
                    >
                        {busy ? "REGISTRANDO…" : "CONFIRMAR ENTRADA"}
                    </button>
                </div>
            </div>
        </div>
    );
}

function ResultPill({ r }: { r: string }) {
    const map: Record<string, string> = {
        GREEN: "text-success border-success/40 bg-success/10",
        RED: "text-destructive border-destructive/40 bg-destructive/10",
        PENDENTE: "text-warning border-warning/40 bg-warning/10",
        PUSH: "text-muted-foreground border-border bg-muted/40",
        VOID: "text-muted-foreground border-border bg-muted/40",
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
