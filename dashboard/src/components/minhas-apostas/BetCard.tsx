"use client";

import { CheckCircle2, XCircle, Clock, Pencil, Ban, Loader2, AlertTriangle } from "lucide-react";
import type { MyBet } from "@/lib/api";
import { cn, fmtDateTime } from "@/lib/format";

const STATUS_META: Record<
    string,
    { label: string; cls: string; icon: typeof CheckCircle2 }
> = {
    pending_approval: {
        label: "PENDENTE",
        cls: "text-warning border-warning/40 bg-warning/10",
        icon: Clock,
    },
    open: {
        label: "EM ANDAMENTO",
        cls: "text-sky-300 border-sky-300/40 bg-sky-300/10",
        icon: Loader2,
    },
    won: {
        label: "GREEN",
        cls: "text-success border-success/40 bg-success/10",
        icon: CheckCircle2,
    },
    lost: {
        label: "RED",
        cls: "text-destructive border-destructive/40 bg-destructive/10",
        icon: XCircle,
    },
    rejected: {
        label: "RECUSADA",
        cls: "text-muted-foreground border-border bg-muted/40",
        icon: Ban,
    },
    cashed_out: {
        label: "CASH OUT",
        cls: "text-mint border-mint/40 bg-mint/10",
        icon: CheckCircle2,
    },
    canceled: {
        label: "ANULADA",
        cls: "text-muted-foreground border-border bg-muted/40",
        icon: AlertTriangle,
    },
    error: {
        label: "ERRO",
        cls: "text-destructive border-destructive/40 bg-destructive/10",
        icon: AlertTriangle,
    },
};

const MARKET_LABEL: Record<string, string> = {
    corners: "escanteios",
    cards: "cartões amarelos",
};

function formatCents(cents: number | null | undefined): string {
    if (cents == null) return "—";
    return (cents / 100).toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
    });
}

function suggestedLineLabel(bet: MyBet): string {
    const market = MARKET_LABEL[bet.market] || bet.market;
    const sel = bet.selecao === "over" ? "Mais" : "Menos";
    const linha = bet.linha != null ? bet.linha.toFixed(1) : "—";
    const odd = bet.odd != null ? bet.odd.toFixed(2) : "—";
    return `${sel} ${linha} ${market} @ ${odd}`;
}

function customLineLabel(bet: MyBet): string | null {
    if (
        bet.actual_linha == null &&
        bet.actual_odd == null &&
        bet.actual_stake_cents == null
    ) {
        return null;
    }
    const linha =
        bet.actual_linha != null ? bet.actual_linha.toFixed(1) : (bet.linha?.toFixed(1) ?? "—");
    const odd =
        bet.actual_odd != null ? bet.actual_odd.toFixed(2) : (bet.odd?.toFixed(2) ?? "—");
    const stake = formatCents(bet.actual_stake_cents ?? bet.stake_cents);
    return `${linha} @ ${odd} — ${stake}`;
}

function potentialGain(bet: MyBet): number | null {
    const stake = bet.actual_stake_cents ?? bet.stake_cents;
    const odd = bet.actual_odd ?? bet.odd;
    if (!stake || !odd) return null;
    return Math.round(stake * (odd - 1));
}

export function BetCard({
    bet,
    onApproveAsIs,
    onApproveCustom,
    onReject,
    busy,
}: {
    bet: MyBet;
    onApproveAsIs?: (bet: MyBet) => void;
    onApproveCustom?: (bet: MyBet) => void;
    onReject?: (bet: MyBet) => void;
    busy?: boolean;
}) {
    const meta = STATUS_META[bet.status] ?? STATUS_META.error;
    const StatusIcon = meta.icon;
    const isPending = bet.status === "pending_approval";
    const isOpen = bet.status === "open";
    const isClosed = ["won", "lost", "cashed_out", "canceled", "error"].includes(
        bet.status,
    );
    const isRejected = bet.status === "rejected";

    return (
        <div className="piq-in rounded-2xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-base">⚽</span>
                        <h3 className="font-display text-base font-semibold truncate">
                            {bet.jogo_descricao || "—"}
                        </h3>
                    </div>
                    <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                        {bet.liga_nome || "—"}
                        {bet.minuto != null && bet.placar && (
                            <> · min {bet.minuto} · {bet.placar}</>
                        )}
                    </div>
                </div>
                <span
                    className={cn(
                        "inline-flex items-center gap-1 font-mono text-[10px] tracking-wider px-2 py-1 rounded-full border",
                        meta.cls,
                    )}
                >
                    <StatusIcon className={cn("size-3", isOpen && "animate-spin")} />
                    {meta.label}
                </span>
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                <div>
                    <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block">
                        Sinal sugerido
                    </span>
                    <span className="font-medium">{suggestedLineLabel(bet)}</span>
                </div>
                {bet.pressure_score != null && (
                    <div>
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block">
                            Confiança
                        </span>
                        <span className="font-mono tabular text-mint-bright">
                            {bet.pressure_score}
                            {bet.tipo_sinal === "PREMIUM" && " · PRM"}
                        </span>
                    </div>
                )}
                {bet.edge != null && (
                    <div>
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block">
                            Edge
                        </span>
                        <span className="font-mono tabular">{bet.edge.toFixed(2)}</span>
                    </div>
                )}
            </div>

            {(isOpen || isClosed) && customLineLabel(bet) && (
                <div className="rounded-lg border border-mint/30 bg-mint/5 p-3 text-sm">
                    <div className="font-mono text-[10px] tracking-wider text-mint uppercase mb-1">
                        Sua execução
                    </div>
                    <div className="font-medium">{customLineLabel(bet)}</div>
                    {bet.actual_bet_house && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                            Casa: {bet.actual_bet_house}
                        </div>
                    )}
                </div>
            )}

            {isOpen && potentialGain(bet) != null && (
                <div className="flex items-center justify-between text-sm pt-1 border-t border-border/40">
                    <span className="text-muted-foreground">Ganho potencial</span>
                    <span className="font-mono tabular text-mint-bright font-semibold">
                        +{formatCents(potentialGain(bet))}
                    </span>
                </div>
            )}

            {bet.status === "won" && (
                <div className="flex items-center justify-between text-sm pt-1 border-t border-border/40">
                    <span className="text-muted-foreground">Lucro</span>
                    <span className="font-mono tabular text-success font-semibold">
                        +{formatCents(bet.payout_cents - (bet.actual_stake_cents ?? bet.stake_cents))}
                    </span>
                </div>
            )}

            {bet.status === "lost" && (
                <div className="flex items-center justify-between text-sm pt-1 border-t border-border/40">
                    <span className="text-muted-foreground">Prejuízo</span>
                    <span className="font-mono tabular text-destructive font-semibold">
                        -{formatCents(bet.actual_stake_cents ?? bet.stake_cents)}
                    </span>
                </div>
            )}

            {isRejected && bet.rejection_reason && (
                <div className="text-xs text-muted-foreground italic pt-1 border-t border-border/40">
                    Motivo: {bet.rejection_reason}
                </div>
            )}

            {bet.escanteios_final != null && (bet.status === "won" || bet.status === "lost") && (
                <div className="text-xs text-muted-foreground">
                    Total final: {bet.escanteios_final} {MARKET_LABEL[bet.market]}
                </div>
            )}

            <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
                <span>{fmtDateTime(bet.placed_at)}</span>
                {bet.placement_mode === "manual" && (
                    <span className="font-mono text-[9px] tracking-wider px-1.5 py-0.5 rounded border border-border bg-muted/40">
                        MANUAL
                    </span>
                )}
            </div>

            {isPending && (
                <div className="grid grid-cols-3 gap-2 pt-2">
                    <button
                        onClick={() => onApproveAsIs?.(bet)}
                        disabled={busy}
                        className="flex items-center justify-center gap-1.5 rounded-lg border border-success/40 bg-success/10 hover:bg-success/20 text-success px-3 py-2 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <CheckCircle2 className="size-3.5" />
                        Apostei conforme
                    </button>
                    <button
                        onClick={() => onApproveCustom?.(bet)}
                        disabled={busy}
                        className="flex items-center justify-center gap-1.5 rounded-lg border border-mint/40 bg-mint/10 hover:bg-mint/20 text-mint-bright px-3 py-2 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Pencil className="size-3.5" />
                        Apostei diferente
                    </button>
                    <button
                        onClick={() => onReject?.(bet)}
                        disabled={busy}
                        className="flex items-center justify-center gap-1.5 rounded-lg border border-border hover:bg-destructive/10 hover:border-destructive/40 hover:text-destructive text-muted-foreground px-3 py-2 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <XCircle className="size-3.5" />
                        Não apostei
                    </button>
                </div>
            )}
        </div>
    );
}
