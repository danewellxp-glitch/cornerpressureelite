"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
    Loader2,
    Inbox,
    Settings,
    TrendingUp,
    Check,
    X,
    Flag,
    Square,
    Clock,
} from "lucide-react";
import {
    fetchUserSignals,
    fetchUserStats,
    fetchBancaSummary,
    decideSignal,
    type BancaSummary,
    type UserSignalDetail,
    type UserStats,
} from "@/lib/api";
import { cn, fmtTime } from "@/lib/format";

/**
 * Minhas Apostas — pagina dedicada ao log de decisoes manuais do user.
 *
 * Desacoplada do Robo (que e auto-bet). Aqui o user decide signal-by-signal:
 *  - Aguardando decisao (pending)
 *  - Em andamento (entered, sem resultado ainda)
 *  - Encerradas (entered com resultado GREEN/RED/PUSH/VOID)
 *
 * Stats derivados de user_signal_decisions. Banca debita stake otimisticamente
 * no momento da entrada via movement bet_loss negativo (ver BancaRepo).
 */

type TabId = "pending" | "open" | "closed";
const TABS: { id: TabId; label: string }[] = [
    { id: "pending", label: "Aguardando" },
    { id: "open", label: "Em andamento" },
    { id: "closed", label: "Encerradas" },
];

const REFRESH_MS = 20_000;

function tabOf(s: UserSignalDetail): TabId | null {
    const d = s.decision;
    if (d.decision === "pending") return "pending";
    if (d.decision === "skipped") return "closed";
    // entered
    if (d.resultado) return "closed";
    return "open";
}

const brl = (cents: number) =>
    (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function MinhasApostasPanel() {
    const [tab, setTab] = useState<TabId>("pending");
    const [signals, setSignals] = useState<UserSignalDetail[]>([]);
    const [stats, setStats] = useState<UserStats | null>(null);
    const [banca, setBanca] = useState<BancaSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [decideTarget, setDecideTarget] = useState<UserSignalDetail | null>(null);

    const loadAll = useCallback(async () => {
        try {
            setLoading(true);
            const [sigs, st, b] = await Promise.all([
                fetchUserSignals(500),
                fetchUserStats().catch(() => null),
                fetchBancaSummary().catch(() => null),
            ]);
            setSignals(sigs);
            setStats(st);
            setBanca(b);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadAll();
        const id = setInterval(loadAll, REFRESH_MS);
        return () => clearInterval(id);
    }, [loadAll]);

    const grouped = useMemo(() => {
        const out: Record<TabId, UserSignalDetail[]> = { pending: [], open: [], closed: [] };
        for (const s of signals) {
            const t = tabOf(s);
            if (t) out[t].push(s);
        }
        // Mais recente primeiro
        for (const k of Object.keys(out) as TabId[]) {
            out[k].sort((a, b) => {
                const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
                const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
                return tb - ta;
            });
        }
        return out;
    }, [signals]);

    const visible = grouped[tab];
    const totals: Record<TabId, number> = {
        pending: grouped.pending.length,
        open: grouped.open.length,
        closed: grouped.closed.length,
    };

    const handleSkip = async (s: UserSignalDetail) => {
        try {
            await decideSignal(s.signal_id, { decision: "skipped" });
            await loadAll();
        } catch (e) {
            console.error("skip failed", e);
        }
    };

    return (
        <div className="space-y-6 max-w-[1200px] mx-auto">
            <header className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                        Registro manual de apostas
                    </div>
                    <h1 className="font-display text-2xl font-bold mt-1">Minhas Apostas</h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                        Independente do Robô. Cada sinal emitido aparece aqui pra você
                        confirmar (entrou com odd X / valor Y) ou pular. Só o que você
                        confirma conta pro ROI e debita da banca.
                    </p>
                </div>
                {banca?.configured && (
                    <div className="rounded-xl border border-border bg-card p-3 text-right">
                        <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Banca atual
                        </div>
                        <div className="font-display text-xl font-bold text-mint-bright tabular">
                            {brl(banca.banca_atual_cents)}
                        </div>
                    </div>
                )}
            </header>

            {!banca?.configured && (
                <div className="rounded-2xl border border-warning/40 bg-warning/10 p-5 flex items-start gap-3">
                    <Settings className="size-5 text-warning shrink-0 mt-0.5" />
                    <div className="flex-1">
                        <h3 className="font-display text-sm font-semibold text-warning">
                            Configure sua banca primeiro
                        </h3>
                        <p className="text-xs text-warning/80 mt-1">
                            Você pode registrar apostas mesmo sem banca, mas pra ROI fiel
                            e debito automático do stake, defina sua banca inicial.
                        </p>
                        <Link
                            href="/banca"
                            className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 rounded-lg border border-warning/40 bg-warning/10 hover:bg-warning/20 text-warning text-xs font-medium transition"
                        >
                            Configurar banca →
                        </Link>
                    </div>
                </div>
            )}

            {/* Stats agregados */}
            <section className="grid gap-3 grid-cols-2 md:grid-cols-4">
                <StatBox
                    label="Apostas"
                    value={String(stats?.total ?? 0)}
                    sub={stats?.aguardando_decisao ? `${stats.aguardando_decisao} aguardam` : "—"}
                />
                <StatBox
                    label="Winrate"
                    value={`${(stats?.winrate ?? 0).toFixed(1)}%`}
                    sub={`${(stats?.greens ?? 0)}G / ${(stats?.reds ?? 0)}R`}
                    tone={(stats?.winrate ?? 0) >= 50 ? "mint" : "danger"}
                />
                <StatBox
                    label="ROI"
                    value={`${(stats?.roi_pct ?? 0) >= 0 ? "+" : ""}${(stats?.roi_pct ?? 0).toFixed(2)}%`}
                    sub={`${brl(stats?.pnl_cents ?? 0)} P&L`}
                    tone={(stats?.pnl_cents ?? 0) >= 0 ? "mint" : "danger"}
                />
                <StatBox
                    label="Odd média"
                    value={(stats?.avg_odd ?? 0).toFixed(2)}
                    sub={`${brl(stats?.staked_cents ?? 0)} apostado`}
                />
            </section>

            {/* Tabs */}
            <nav className="inline-flex rounded-lg border border-border bg-card/60 p-0.5">
                {TABS.map((t) => {
                    const active = tab === t.id;
                    const count = totals[t.id];
                    return (
                        <button
                            key={t.id}
                            onClick={() => setTab(t.id)}
                            className={cn(
                                "px-4 py-2 text-xs font-mono tracking-wider rounded-md transition flex items-center gap-2",
                                active
                                    ? "bg-mint/10 text-mint-bright shadow-[inset_0_0_0_1px_oklch(0.62_0.22_255/0.35)]"
                                    : "text-muted-foreground hover:text-foreground",
                            )}
                        >
                            {t.label.toUpperCase()}
                            {count > 0 && (
                                <span
                                    className={cn(
                                        "px-1.5 py-0.5 rounded-full text-[9px] tabular",
                                        active
                                            ? "bg-mint-bright/20 text-mint-bright"
                                            : "bg-muted/40 text-muted-foreground",
                                    )}
                                >
                                    {count}
                                </span>
                            )}
                        </button>
                    );
                })}
            </nav>

            {/* Lista */}
            {loading && visible.length === 0 ? (
                <div className="flex items-center justify-center min-h-[40vh] text-muted-foreground">
                    <Loader2 className="size-6 animate-spin" />
                    <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO…</span>
                </div>
            ) : visible.length === 0 ? (
                <EmptyState tab={tab} />
            ) : (
                <div className="grid gap-3 lg:grid-cols-2">
                    {visible.map((s) => (
                        <SignalCard
                            key={s.signal_id}
                            signal={s}
                            onEnter={() => setDecideTarget(s)}
                            onSkip={() => handleSkip(s)}
                        />
                    ))}
                </div>
            )}

            {decideTarget && (
                <DecisionModal
                    signal={decideTarget}
                    banca={banca}
                    onClose={() => setDecideTarget(null)}
                    onConfirmed={async () => {
                        setDecideTarget(null);
                        await loadAll();
                    }}
                />
            )}
        </div>
    );
}

/* ────────────────────────────────────────────────────────────── */

function StatBox({
    label,
    value,
    sub,
    tone,
}: {
    label: string;
    value: string;
    sub?: string;
    tone?: "mint" | "danger";
}) {
    return (
        <div className="rounded-xl border border-border bg-card px-4 py-3">
            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                {label}
            </div>
            <div
                className={cn(
                    "font-display text-xl font-bold tabular mt-1",
                    tone === "mint" && "text-mint-bright",
                    tone === "danger" && "text-destructive",
                )}
            >
                {value}
            </div>
            {sub && (
                <div className="font-mono text-[10px] text-muted-foreground mt-1">{sub}</div>
            )}
        </div>
    );
}

function SignalCard({
    signal,
    onEnter,
    onSkip,
}: {
    signal: UserSignalDetail;
    onEnter: () => void;
    onSkip: () => void;
}) {
    const d = signal.decision;
    const isEscanteios = signal.tipo_analise === "ESCANTEIOS";
    const Icon = isEscanteios ? Flag : Square;

    return (
        <article
            className={cn(
                "piq-in rounded-2xl border border-border bg-card p-5 space-y-3",
                d.decision === "skipped" && "opacity-50",
                d.decision === "entered" && "border-mint/40",
            )}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <Icon
                            className={cn(
                                "size-3",
                                isEscanteios ? "text-mint" : "text-warning",
                            )}
                        />
                        <span className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">
                            {signal.tipo_sinal} · {isEscanteios ? "ESC" : "CRD"}
                        </span>
                        {signal.minuto != null && (
                            <span className="font-mono text-[10px] tabular text-muted-foreground">
                                · {signal.minuto}'
                            </span>
                        )}
                    </div>
                    <h3 className="font-display text-base font-semibold leading-tight truncate">
                        {signal.jogo_descricao || "—"}
                    </h3>
                    <div className="font-mono text-[10px] text-muted-foreground mt-1 tabular">
                        Linha {signal.linha} @ odd {signal.odd?.toFixed(2)} · score{" "}
                        {signal.pressure_score} · edge {signal.edge}
                    </div>
                </div>
                <ResultPill r={d.resultado ?? signal.signal_resultado ?? "PENDENTE"} />
            </div>

            {d.decision === "entered" && (
                <div className="rounded-lg border border-mint/30 bg-mint/5 p-3 space-y-1">
                    <div className="flex items-center justify-between font-mono text-xs tabular">
                        <span className="text-muted-foreground">Entrada:</span>
                        <span className="text-mint-bright">
                            {brl(d.valor_apostado_cents ?? 0)} @ {d.odd_entrada?.toFixed(2)}
                        </span>
                    </div>
                    {d.resultado && d.payout_cents != null && (
                        <div className="flex items-center justify-between font-mono text-xs tabular">
                            <span className="text-muted-foreground">P&L:</span>
                            <span
                                className={cn(
                                    d.payout_cents >= 0 ? "text-mint-bright" : "text-destructive",
                                )}
                            >
                                {d.payout_cents >= 0 ? "+" : ""}
                                {brl(d.payout_cents)}
                            </span>
                        </div>
                    )}
                    {d.decided_at && (
                        <div className="flex items-center justify-between font-mono text-[10px] text-muted-foreground">
                            <span>decidido:</span>
                            <span>{fmtTime(d.decided_at)}</span>
                        </div>
                    )}
                </div>
            )}

            {d.decision === "pending" && (
                <div className="flex gap-2">
                    <button
                        onClick={onEnter}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 font-mono text-xs tracking-wider text-mint border border-mint/40 hover:bg-mint hover:text-background transition rounded-lg"
                    >
                        <Check className="size-3.5" />
                        ENTREI
                    </button>
                    <button
                        onClick={onSkip}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 font-mono text-xs tracking-wider text-muted-foreground border border-border hover:text-foreground hover:border-foreground/40 transition rounded-lg"
                    >
                        <X className="size-3.5" />
                        PULEI
                    </button>
                </div>
            )}

            {d.decision === "skipped" && (
                <div className="font-mono text-[10px] tracking-wider text-muted-foreground text-center">
                    PULADO
                </div>
            )}
        </article>
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
                "shrink-0 inline-flex font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border self-start",
                map[r] ?? "border-border bg-muted/40 text-muted-foreground",
            )}
        >
            {r === "PENDENTE" ? "PEND" : r}
        </span>
    );
}

function EmptyState({ tab }: { tab: TabId }) {
    const copy: Record<TabId, { title: string; desc: string }> = {
        pending: {
            title: "Nenhum sinal aguardando decisão",
            desc: "Quando o sistema emitir um sinal, ele aparece aqui pra você confirmar se entrou ou pular.",
        },
        open: {
            title: "Nenhuma aposta em andamento",
            desc: "Apostas que você confirmou (Entrei) aparecem aqui enquanto o jogo ainda não terminou.",
        },
        closed: {
            title: "Sem histórico ainda",
            desc: "Apostas encerradas (GREEN, RED) e pulos ficam guardados aqui.",
        },
    };
    const { title, desc } = copy[tab];
    return (
        <div className="rounded-2xl border border-border bg-card p-12 text-center">
            <div className="mx-auto size-12 rounded-2xl border border-border bg-muted/40 grid place-items-center mb-4">
                <Inbox className="size-6 text-muted-foreground" />
            </div>
            <h3 className="font-display text-base font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">{desc}</p>
        </div>
    );
}

/* ────────────────────────────────────────────────────────────── */

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
        const h = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !busy) onClose();
        };
        document.addEventListener("keydown", h);
        return () => document.removeEventListener("keydown", h);
    }, [busy, onClose]);

    const confirm = async () => {
        const odd = parseFloat(oddStr);
        const val = Math.round(parseFloat(valStr) * 100);
        if (!odd || odd <= 1.0) {
            setErr("Odd precisa ser > 1.00");
            return;
        }
        if (!val || val <= 0) {
            setErr("Valor precisa ser > 0");
            return;
        }
        if (banca?.configured && val > banca.banca_atual_cents) {
            setErr(`Valor maior que saldo (${brl(banca.banca_atual_cents)})`);
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
                className="w-full max-w-md border border-border bg-card p-6 space-y-5 rounded-2xl"
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
                        {signal.tipo_sinal} · linha {signal.linha} · score {signal.pressure_score} ·
                        edge {signal.edge}
                    </p>
                </div>

                {!banca?.configured && (
                    <div className="text-xs text-warning border border-warning/40 bg-warning/10 p-2 rounded">
                        Banca não configurada — entrada vai contar pro ROI mas o saldo não
                        vai debitar.
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
                            className="mt-1 w-full bg-input border border-border px-3 py-2 font-mono text-sm tabular focus:outline-none focus:border-mint rounded-lg"
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
                            className="mt-1 w-full bg-input border border-border px-3 py-2 font-mono text-sm tabular focus:outline-none focus:border-mint rounded-lg"
                            disabled={busy}
                        />
                        {banca?.configured && (
                            <span className="font-mono text-[10px] text-muted-foreground mt-1 block">
                                saldo: {brl(banca.banca_atual_cents)}
                                {banca.unit_pct &&
                                    ` · sugestão ${banca.unit_pct}% = ${brl(sugestao)}`}
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
                        className="px-4 py-2 border border-border font-mono text-xs tracking-wider hover:text-foreground text-muted-foreground transition rounded-lg"
                    >
                        CANCELAR
                    </button>
                    <button
                        onClick={confirm}
                        disabled={busy}
                        className="px-4 py-2 border border-mint bg-mint text-background font-mono text-xs tracking-wider hover:bg-mint-bright transition disabled:opacity-50 rounded-lg"
                    >
                        {busy ? "REGISTRANDO…" : "CONFIRMAR ENTRADA"}
                    </button>
                </div>
            </div>
        </div>
    );
}
