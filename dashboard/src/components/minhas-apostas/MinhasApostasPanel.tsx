"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
    Loader2,
    Inbox,
    Settings,
    Check,
    X,
    Flag,
    Square,
    Gift,
    Trophy,
    Goal,
    Target,
    Plus,
} from "lucide-react";
import {
    fetchUserSignals,
    fetchUserStats,
    fetchBancaSummary,
    decideSignal,
    confirmSignalResult,
    confirmManualBet,
    type BancaSummary,
    type UserSignalDetail,
    type UserStats,
    type DecisionLeg,
    type LegMercado,
} from "@/lib/api";
import { cn, fmtTime } from "@/lib/format";
import { DecisionModal } from "./DecisionModal";
import { AddBetModal } from "./AddBetModal";

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

const MERCADO_LABEL: Record<LegMercado, string> = {
    escanteios: "Escanteios",
    cartoes: "Cartões",
    gols: "Gols / Marcador",
    "1x2": "1X2 / Resultado",
    ambas_marcam: "Ambas Marcam",
    custom: "Outro",
};

const MERCADO_ICON: Record<LegMercado, typeof Flag> = {
    escanteios: Flag,
    cartoes: Square,
    gols: Goal,
    "1x2": Trophy,
    ambas_marcam: Target,
    custom: Target,
};

export default function MinhasApostasPanel() {
    const [tab, setTab] = useState<TabId>("pending");
    const [signals, setSignals] = useState<UserSignalDetail[]>([]);
    const [stats, setStats] = useState<UserStats | null>(null);
    const [banca, setBanca] = useState<BancaSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [decideTarget, setDecideTarget] = useState<UserSignalDetail | null>(null);
    const [addBetOpen, setAddBetOpen] = useState(false);
    const [confirmTarget, setConfirmTarget] = useState<UserSignalDetail | null>(null);

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

    // Numero de apostas que precisam de confirmacao manual (signal terminou + decision is_multi)
    const aguardandoConfirmacao = useMemo(
        () =>
            signals.filter(
                (s) =>
                    s.decision.decision === "entered" &&
                    !s.decision.resultado &&
                    s.decision.requires_manual_confirmation &&
                    s.signal_resultado !== "PENDENTE",
            ).length,
        [signals],
    );

    return (
        <div className="space-y-6 max-w-[1200px] mx-auto">
            <header className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                        Registro manual de apostas
                    </div>
                    <h1 className="font-display text-2xl font-bold mt-1">Minhas Apostas</h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                        Independente do Robô. Sinal CPES é só ponto de partida — você
                        pode compor multi com outros mercados (gols, 1X2, cartões etc).
                        Só o que você confirma conta pro ROI e debita da banca.
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

            {aguardandoConfirmacao > 0 && (
                <div className="rounded-2xl border border-info/40 bg-info/10 p-4 flex items-center gap-3 text-sm">
                    <Trophy className="size-5 text-info shrink-0" />
                    <span className="text-info-foreground">
                        <strong>{aguardandoConfirmacao}</strong>{" "}
                        {aguardandoConfirmacao === 1 ? "aposta múltipla aguarda" : "apostas múltiplas aguardam"}{" "}
                        sua confirmação de resultado. Veja a aba <strong>Em andamento</strong>.
                    </span>
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
                    label="Bonus total"
                    value={brl(stats?.bonus_total_cents ?? 0)}
                    sub={`odd média ${(stats?.avg_odd ?? 0).toFixed(2)}`}
                    tone="mint"
                />
            </section>

            {/* Tabs + Adicionar Aposta */}
            <div className="flex items-center justify-between gap-3 flex-wrap">
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
                <button
                    onClick={() => setAddBetOpen(true)}
                    className="inline-flex items-center gap-1.5 px-3 py-2 border border-mint bg-mint/10 text-mint-bright font-mono text-xs tracking-wider hover:bg-mint/20 transition rounded-lg"
                >
                    <Plus className="size-3.5" />
                    ADICIONAR APOSTA
                </button>
            </div>

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
                        <BetCard
                            key={s.signal_id}
                            signal={s}
                            unitValueCents={banca?.unit_value_cents ?? 0}
                            onEnter={() => setDecideTarget(s)}
                            onSkip={() => handleSkip(s)}
                            onConfirm={() => setConfirmTarget(s)}
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

            {confirmTarget && (
                <ConfirmResultModal
                    signal={confirmTarget}
                    onClose={() => setConfirmTarget(null)}
                    onConfirmed={async () => {
                        setConfirmTarget(null);
                        await loadAll();
                    }}
                />
            )}

            {addBetOpen && (
                <AddBetModal
                    banca={banca}
                    onClose={() => setAddBetOpen(false)}
                    onCreated={async () => {
                        setAddBetOpen(false);
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

/* ────────────────────────────────────────────────────────────── */
/* BetCard — estilo Betano: legs + apostado + premios + bonus + total */

function BetCard({
    signal,
    unitValueCents,
    onEnter,
    onSkip,
    onConfirm,
}: {
    signal: UserSignalDetail;
    unitValueCents: number;
    onEnter: () => void;
    onSkip: () => void;
    onConfirm: () => void;
}) {
    const d = signal.decision;
    const isEscanteios = signal.tipo_analise === "ESCANTEIOS";
    const stake = d.valor_apostado_cents ?? 0;
    const odd = d.odd_entrada ?? 0;
    const stakeUnits = unitValueCents > 0 ? stake / unitValueCents : 0;

    // Premios brutos = stake * odd (retorno total se ganhar, sem bonus)
    const premiosBrutos = Math.round(stake * odd);
    // Bonus aplica sobre lucro liquido
    const bonus = Math.round((premiosBrutos - stake) * d.bonus_pct);
    const totalRetorno = premiosBrutos + bonus;

    // Estado visual
    const result = d.resultado ?? null;
    const needsConfirm =
        d.decision === "entered" &&
        !d.resultado &&
        d.requires_manual_confirmation &&
        signal.signal_resultado !== "PENDENTE";

    return (
        <article
            className={cn(
                "piq-in rounded-2xl border border-border bg-card overflow-hidden",
                d.decision === "skipped" && "opacity-50",
                result === "GREEN" && "border-success/40",
                result === "RED" && "border-destructive/40",
                needsConfirm && "border-info/40 ring-1 ring-info/30",
            )}
        >
            {/* Header */}
            <div className="p-4 border-b border-border/50 flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">
                            {d.decision === "entered" ? (d.is_multi ? "MÚLTIPLA" : "SIMPLES") : signal.tipo_sinal}
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">·</span>
                        <span className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">
                            {isEscanteios ? "ESCANTEIOS" : "CARTÕES"}
                        </span>
                        {signal.minuto != null && (
                            <>
                                <span className="font-mono text-[10px] text-muted-foreground">·</span>
                                <span className="font-mono text-[10px] tabular text-muted-foreground">
                                    {signal.minuto}&apos;
                                </span>
                            </>
                        )}
                    </div>
                    <h3 className="font-display text-base font-semibold leading-tight truncate">
                        {signal.jogo_descricao || "—"}
                    </h3>
                </div>
                {d.decision === "entered" && stake > 0 && (
                    <div className="text-right shrink-0">
                        <div className="font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
                            Aposta
                        </div>
                        <div className="font-display font-bold tabular text-sm">{brl(stake)}</div>
                    </div>
                )}
                {d.decision !== "entered" && (
                    <ResultPill r={result ?? signal.signal_resultado ?? "PENDENTE"} />
                )}
                {d.decision === "entered" && (
                    <div className="shrink-0 flex items-center gap-2">
                        <div className="bg-muted/60 px-2 py-1 rounded-md">
                            <span className="font-mono text-sm font-bold tabular">{odd.toFixed(2)}</span>
                        </div>
                        <ResultPill
                            r={
                                needsConfirm
                                    ? "CONFIRM"
                                    : result ?? (d.decision === "entered" ? "ABERTA" : "PENDENTE")
                            }
                        />
                    </div>
                )}
            </div>

            {/* Legs (entered only) */}
            {d.decision === "entered" && (
                <div className="p-4 space-y-2 border-b border-border/50">
                    {d.legs.length === 0 ? (
                        // single sem legs registradas — usa o sinal CPES como leg implicita
                        <SingleLegRow
                            mercado={isEscanteios ? "escanteios" : "cartoes"}
                            descricao={`${signal.tipo_sinal} ${isEscanteios ? "Escanteios" : "Cartões"} Mais de ${signal.linha}`}
                            linha={signal.linha}
                            odd={odd}
                            resultado={result}
                        />
                    ) : (
                        d.legs.map((leg) => (
                            <SingleLegRow
                                key={leg.id ?? `${leg.ordem}-${leg.descricao}`}
                                mercado={leg.mercado}
                                descricao={leg.descricao}
                                linha={leg.linha}
                                odd={leg.odd_leg}
                                resultado={leg.resultado}
                            />
                        ))
                    )}
                </div>
            )}

            {/* Sinal info (pending/skipped only) */}
            {d.decision !== "entered" && (
                <div className="p-4 border-b border-border/50">
                    <div className="font-mono text-[10px] text-muted-foreground tabular">
                        Linha {signal.linha} @ odd {signal.odd?.toFixed(2)} · score{" "}
                        {signal.pressure_score} · edge {signal.edge}
                    </div>
                </div>
            )}

            {/* Footer com Aposta / Premios / Bonus / Total */}
            {d.decision === "entered" && stake > 0 && (
                <div className="p-4 space-y-1.5 bg-muted/20">
                    <div className="flex items-center justify-between font-mono text-xs tabular">
                        <span className="text-muted-foreground">
                            Aposta
                            {stakeUnits > 0 && (
                                <span className="text-info ml-1">({stakeUnits.toFixed(1)}u)</span>
                            )}
                        </span>
                        <span>{brl(stake)}</span>
                    </div>
                    <div className="flex items-center justify-between font-mono text-xs tabular">
                        <span className="text-muted-foreground">
                            Prêmios{" "}
                            <span className="text-[10px] text-muted-foreground/60">
                                ({odd.toFixed(2)}×)
                            </span>
                        </span>
                        <span>{brl(premiosBrutos)}</span>
                    </div>
                    {d.bonus_pct > 0 && (
                        <div className="flex items-center justify-between font-mono text-xs tabular text-mint-bright">
                            <span className="flex items-center gap-1.5">
                                <Gift className="size-3" />
                                Bonus turbinada +{(d.bonus_pct * 100).toFixed(0)}%
                            </span>
                            <span>+{brl(bonus)}</span>
                        </div>
                    )}
                    <div className="flex items-center justify-between font-mono text-sm tabular border-t border-border/50 pt-1.5 mt-1.5">
                        <span className="font-semibold">
                            {result === "GREEN" ? "Recebido" : result === "RED" ? "Perdido" : "Retorno se GREEN"}
                        </span>
                        <span
                            className={cn(
                                "font-bold",
                                result === "GREEN" && "text-success",
                                result === "RED" && "text-destructive line-through",
                            )}
                        >
                            {result === "RED" ? brl(stake) : brl(totalRetorno)}
                        </span>
                    </div>
                    {result && d.payout_cents != null && (
                        <div className="flex items-center justify-between font-mono text-[10px] tabular text-muted-foreground pt-1">
                            <span>P&L líquido:</span>
                            <span
                                className={cn(
                                    d.payout_cents >= 0 ? "text-success" : "text-destructive",
                                )}
                            >
                                {d.payout_cents >= 0 ? "+" : ""}
                                {brl(d.payout_cents)}
                            </span>
                        </div>
                    )}
                    {d.decided_at && (
                        <div className="font-mono text-[10px] text-muted-foreground text-right pt-1">
                            registrada {fmtTime(d.decided_at)}
                            {d.manually_confirmed_at && ` · confirmada ${fmtTime(d.manually_confirmed_at)}`}
                        </div>
                    )}
                </div>
            )}

            {/* Actions */}
            {d.decision === "pending" && (
                <div className="p-4 flex gap-2">
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

            {needsConfirm && (
                <div className="p-4 border-t border-info/30 bg-info/5 space-y-2">
                    <div className="font-mono text-[10px] tracking-wider text-info uppercase">
                        Jogo terminou — confirme o resultado
                    </div>
                    <button
                        onClick={onConfirm}
                        className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 font-mono text-xs tracking-wider text-info border border-info/40 hover:bg-info hover:text-background transition rounded-lg"
                    >
                        <Trophy className="size-3.5" />
                        CONFIRMAR RESULTADO
                    </button>
                </div>
            )}

            {d.decision === "skipped" && (
                <div className="p-4 font-mono text-[10px] tracking-wider text-muted-foreground text-center">
                    PULADO
                </div>
            )}
        </article>
    );
}

function SingleLegRow({
    mercado,
    descricao,
    linha,
    odd,
    resultado,
}: {
    mercado: LegMercado;
    descricao: string;
    linha: number | null;
    odd: number;
    resultado: "GREEN" | "RED" | "PUSH" | "VOID" | null;
}) {
    const Icon = MERCADO_ICON[mercado] ?? Target;
    return (
        <div className="flex items-start gap-2.5 text-sm">
            <div
                className={cn(
                    "size-5 rounded-full border-2 grid place-items-center shrink-0 mt-0.5",
                    resultado === "GREEN" && "border-success bg-success/20",
                    resultado === "RED" && "border-destructive bg-destructive/20",
                    !resultado && "border-mint/50",
                )}
            >
                {resultado === "GREEN" && <Check className="size-3 text-success" />}
                {resultado === "RED" && <X className="size-3 text-destructive" />}
                {!resultado && <Icon className="size-2.5 text-mint" />}
            </div>
            <div className="flex-1 min-w-0">
                <div className="font-medium leading-tight truncate">{descricao}</div>
                <div className="font-mono text-[10px] text-muted-foreground mt-0.5">
                    {MERCADO_LABEL[mercado]}
                    {linha != null && ` · linha ${linha}`}
                    {" · "}
                    <span className="tabular">@ {odd.toFixed(2)}</span>
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
        CONFIRM: "text-info border-info/40 bg-info/10 animate-pulse",
        ABERTA: "text-mint border-mint/40 bg-mint/10",
    };
    const label =
        r === "PENDENTE"
            ? "PEND"
            : r === "GREEN"
              ? "GANHOU"
              : r === "RED"
                ? "PERDEU"
                : r === "CONFIRM"
                  ? "CONFIRMAR"
                  : r;
    return (
        <span
            className={cn(
                "shrink-0 inline-flex font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border self-start",
                map[r] ?? "border-border bg-muted/40 text-muted-foreground",
            )}
        >
            {label}
        </span>
    );
}

function EmptyState({ tab }: { tab: TabId }) {
    const copy: Record<TabId, { title: string; desc: string }> = {
        pending: {
            title: "Nenhum sinal aguardando decisão",
            desc: "Quando o sistema emitir um sinal, ele aparece aqui pra você confirmar se entrou (single ou multi) ou pular.",
        },
        open: {
            title: "Nenhuma aposta em andamento",
            desc: "Apostas confirmadas aparecem aqui enquanto o jogo ainda não terminou. Múltiplas vão precisar de confirmação manual quando o jogo encerrar.",
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
/* ConfirmResultModal — confirma manualmente resultado pos-jogo   */

function ConfirmResultModal({
    signal,
    onClose,
    onConfirmed,
}: {
    signal: UserSignalDetail;
    onClose: () => void;
    onConfirmed: () => void;
}) {
    const [busy, setBusy] = useState<"GREEN" | "RED" | "PUSH" | "VOID" | null>(null);
    const [err, setErr] = useState<string | null>(null);

    const confirm = async (resultado: "GREEN" | "RED" | "PUSH" | "VOID") => {
        setBusy(resultado);
        setErr(null);
        try {
            if (signal.is_manual && signal.decision.id != null) {
                await confirmManualBet(signal.decision.id, resultado);
            } else {
                await confirmSignalResult(signal.signal_id, resultado);
            }
            onConfirmed();
        } catch (e) {
            setErr(e instanceof Error ? e.message : "Erro ao confirmar");
            setBusy(null);
        }
    };

    const d = signal.decision;
    const stake = d.valor_apostado_cents ?? 0;
    const odd = d.odd_entrada ?? 0;
    const premiosBrutos = Math.round(stake * odd);
    const bonus = Math.round((premiosBrutos - stake) * d.bonus_pct);
    const totalRetorno = premiosBrutos + bonus;

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
                    <div className="font-mono text-[10px] tracking-[0.22em] uppercase text-info mb-2">
                        confirmar resultado
                    </div>
                    <h3 className="font-display text-xl font-bold leading-tight">
                        {signal.jogo_descricao}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1.5">
                        Sua aposta foi múltipla com {d.legs.length} legs. CPES não consegue
                        verificar todos os mercados — confirme você como saiu.
                    </p>
                </div>

                <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-1.5 font-mono text-xs tabular">
                    <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Aposta:</span>
                        <span>{brl(stake)} @ {odd.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Se GREEN recebe:</span>
                        <span className="text-mint-bright font-bold">{brl(totalRetorno)}</span>
                    </div>
                    {d.bonus_pct > 0 && (
                        <div className="flex items-center justify-between text-mint-bright text-[10px]">
                            <span>(inclui bonus +{(d.bonus_pct * 100).toFixed(0)}%)</span>
                            <span>+{brl(bonus)}</span>
                        </div>
                    )}
                </div>

                <div className="grid grid-cols-2 gap-2">
                    <button
                        onClick={() => confirm("GREEN")}
                        disabled={!!busy}
                        className="px-4 py-3 border-2 border-success bg-success/10 hover:bg-success hover:text-background text-success font-mono text-sm tracking-wider transition disabled:opacity-50 rounded-lg flex items-center justify-center gap-2"
                    >
                        <Check className="size-4" />
                        {busy === "GREEN" ? "…" : "GANHOU"}
                    </button>
                    <button
                        onClick={() => confirm("RED")}
                        disabled={!!busy}
                        className="px-4 py-3 border-2 border-destructive bg-destructive/10 hover:bg-destructive hover:text-background text-destructive font-mono text-sm tracking-wider transition disabled:opacity-50 rounded-lg flex items-center justify-center gap-2"
                    >
                        <X className="size-4" />
                        {busy === "RED" ? "…" : "PERDEU"}
                    </button>
                </div>

                <div className="grid grid-cols-2 gap-2">
                    <button
                        onClick={() => confirm("PUSH")}
                        disabled={!!busy}
                        className="px-3 py-2 border border-border hover:border-foreground/40 text-muted-foreground hover:text-foreground font-mono text-xs tracking-wider transition disabled:opacity-50 rounded-lg"
                    >
                        {busy === "PUSH" ? "…" : "PUSH (devolveu)"}
                    </button>
                    <button
                        onClick={() => confirm("VOID")}
                        disabled={!!busy}
                        className="px-3 py-2 border border-border hover:border-foreground/40 text-muted-foreground hover:text-foreground font-mono text-xs tracking-wider transition disabled:opacity-50 rounded-lg"
                    >
                        {busy === "VOID" ? "…" : "VOID (anulada)"}
                    </button>
                </div>

                {err && (
                    <div className="text-xs text-destructive border border-destructive/40 bg-destructive/10 p-2 rounded font-mono">
                        {err}
                    </div>
                )}

                <button
                    onClick={onClose}
                    disabled={!!busy}
                    className="w-full px-4 py-2 border border-border font-mono text-xs tracking-wider hover:text-foreground text-muted-foreground transition rounded-lg"
                >
                    CANCELAR
                </button>
            </div>
        </div>
    );
}
