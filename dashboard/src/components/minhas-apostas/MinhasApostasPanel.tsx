"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CheckCheck, Loader2, Inbox, Settings } from "lucide-react";
import {
    fetchMyBets,
    fetchBancaSummary,
    fetchBotConfig,
    approveBet,
    rejectBet,
    patchBotConfig,
    type MyBet,
    type BetStatus,
    type BancaSummary,
    type BotConfig,
    type ApprovePayload,
    type RejectPayload,
} from "@/lib/api";
import { cn } from "@/lib/format";
import { BetCard } from "./BetCard";
import { BetActionModal } from "./BetActionModal";

type TabId = "pending" | "open" | "closed";

const TABS: { id: TabId; label: string; statuses: BetStatus[] }[] = [
    { id: "pending", label: "Pendentes", statuses: ["pending_approval"] },
    { id: "open", label: "Em andamento", statuses: ["open"] },
    {
        id: "closed",
        label: "Encerradas",
        statuses: ["won", "lost", "rejected", "cashed_out", "canceled", "error"],
    },
];

type ModalState =
    | { kind: "approve_as_is"; bet: MyBet }
    | { kind: "approve_custom"; bet: MyBet }
    | { kind: "reject"; bet: MyBet }
    | null;

const REFRESH_MS = 20_000;

export default function MinhasApostasPanel() {
    const [tab, setTab] = useState<TabId>("pending");
    const [bets, setBets] = useState<Record<TabId, MyBet[]>>({
        pending: [],
        open: [],
        closed: [],
    });
    const [totals, setTotals] = useState<Record<TabId, number>>({
        pending: 0,
        open: 0,
        closed: 0,
    });
    const [loading, setLoading] = useState(true);
    const [banca, setBanca] = useState<BancaSummary | null>(null);
    const [botConfig, setBotConfig] = useState<BotConfig | null>(null);
    const [modal, setModal] = useState<ModalState>(null);
    const [modalBusy, setModalBusy] = useState(false);
    const [modalError, setModalError] = useState<string | null>(null);
    const [modeBusy, setModeBusy] = useState(false);

    const loadTab = useCallback(async (which: TabId) => {
        const def = TABS.find((t) => t.id === which)!;
        // backend filtra por um status só; iteramos os statuses do tab.
        const results = await Promise.all(
            def.statuses.map((s) =>
                fetchMyBets({ status: s, page_size: 50 }).catch(() => null),
            ),
        );
        const items: MyBet[] = [];
        let total = 0;
        for (const r of results) {
            if (!r) continue;
            items.push(...r.items);
            total += r.total;
        }
        items.sort((a, b) => {
            const ta = a.placed_at ? new Date(a.placed_at).getTime() : 0;
            const tb = b.placed_at ? new Date(b.placed_at).getTime() : 0;
            return tb - ta;
        });
        setBets((prev) => ({ ...prev, [which]: items }));
        setTotals((prev) => ({ ...prev, [which]: total }));
    }, []);

    const loadAll = useCallback(async () => {
        setLoading(true);
        try {
            await Promise.all([
                loadTab("pending"),
                loadTab("open"),
                loadTab("closed"),
                fetchBancaSummary().then(setBanca).catch(() => setBanca(null)),
                fetchBotConfig().then(setBotConfig).catch(() => setBotConfig(null)),
            ]);
        } finally {
            setLoading(false);
        }
    }, [loadTab]);

    useEffect(() => {
        loadAll();
        const id = setInterval(loadAll, REFRESH_MS);
        return () => clearInterval(id);
    }, [loadAll]);

    const visibleBets = bets[tab];

    const inManualMode = botConfig?.mode === "manual";
    const botEnabled = botConfig?.enabled === true;

    async function handleEnableManual() {
        setModeBusy(true);
        try {
            const updated = await patchBotConfig({ mode: "manual" });
            setBotConfig(updated);
            // se ainda não estava enabled, tentar enable também
            if (!updated.enabled) {
                if (!updated.accepted_tos_at) {
                    // sem ToS — manda pro robô pra configurar
                    window.location.href = "/robo";
                    return;
                }
                if ((updated.banca_inicial_cents ?? 0) < 5000) {
                    window.location.href = "/banca";
                    return;
                }
                const en = await patchBotConfig({ enabled: true });
                setBotConfig(en);
            }
            await loadAll();
        } catch (e) {
            alert(
                "Não foi possível ativar o modo manual. Verifique se a banca está configurada (página Banca) e o Termo de Uso foi aceito (página Robô).",
            );
            console.error(e);
        } finally {
            setModeBusy(false);
        }
    }

    function openApproveAsIs(bet: MyBet) {
        setModal({ kind: "approve_as_is", bet });
        setModalError(null);
    }
    function openApproveCustom(bet: MyBet) {
        setModal({ kind: "approve_custom", bet });
        setModalError(null);
    }
    function openReject(bet: MyBet) {
        setModal({ kind: "reject", bet });
        setModalError(null);
    }

    async function handleApprove(payload: ApprovePayload) {
        if (!modal || modal.kind === "reject") return;
        setModalBusy(true);
        setModalError(null);
        try {
            await approveBet(modal.bet.id, payload);
            setModal(null);
            await Promise.all([loadTab("pending"), loadTab("open"), fetchBancaSummary().then(setBanca)]);
        } catch (e) {
            setModalError(e instanceof Error ? e.message : "Erro ao aprovar aposta");
        } finally {
            setModalBusy(false);
        }
    }

    async function handleReject(payload: RejectPayload) {
        if (!modal || modal.kind !== "reject") return;
        setModalBusy(true);
        setModalError(null);
        try {
            await rejectBet(modal.bet.id, payload);
            setModal(null);
            await Promise.all([loadTab("pending"), loadTab("closed")]);
        } catch (e) {
            setModalError(e instanceof Error ? e.message : "Erro ao recusar aposta");
        } finally {
            setModalBusy(false);
        }
    }

    const bancaAtualCents = banca?.banca_atual_cents ?? 0;
    const unitPct = banca?.unit_pct ?? botConfig?.unit_pct ?? 0.02;

    return (
        <div className="space-y-6 max-w-[1200px] mx-auto">
            <header className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                        Co-piloto manual
                    </div>
                    <h1 className="font-display text-2xl font-bold mt-1">Minhas Apostas</h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                        Sinais que chegam viram cards aqui. Você decide se apostou conforme,
                        diferente, ou não apostou. Sua banca atualiza só com o que confirmar.
                    </p>
                </div>
                {banca?.configured && (
                    <div className="rounded-xl border border-border bg-card p-3 text-right">
                        <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Banca atual
                        </div>
                        <div className="font-display text-xl font-bold text-mint-bright tabular">
                            {(bancaAtualCents / 100).toLocaleString("pt-BR", {
                                style: "currency",
                                currency: "BRL",
                            })}
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
                            Pra registrar apostas e ver ROI real, você precisa definir sua banca inicial.
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

            {banca?.configured && (!inManualMode || !botEnabled) && (
                <div className="rounded-2xl border border-mint/30 bg-mint/5 p-5 flex items-start gap-3">
                    <CheckCheck className="size-5 text-mint-bright shrink-0 mt-0.5" />
                    <div className="flex-1">
                        <h3 className="font-display text-sm font-semibold">
                            Ativar modo manual
                        </h3>
                        <p className="text-xs text-muted-foreground mt-1">
                            Pra que cada sinal vire um card aqui (em vez de virar aposta automática),
                            ative o modo manual.{" "}
                            {botConfig?.mode === "real" || botConfig?.mode === "paper"
                                ? `Modo atual: ${botConfig.mode}.`
                                : ""}
                        </p>
                        <button
                            onClick={handleEnableManual}
                            disabled={modeBusy}
                            className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 rounded-lg border border-mint/40 bg-mint/10 hover:bg-mint/20 text-mint-bright text-xs font-medium transition disabled:opacity-50"
                        >
                            {modeBusy ? (
                                <Loader2 className="size-3.5 animate-spin" />
                            ) : (
                                <CheckCheck className="size-3.5" />
                            )}
                            Ativar modo manual
                        </button>
                    </div>
                </div>
            )}

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

            {loading && visibleBets.length === 0 ? (
                <div className="flex items-center justify-center min-h-[40vh] text-muted-foreground">
                    <Loader2 className="size-6 animate-spin" />
                    <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO…</span>
                </div>
            ) : visibleBets.length === 0 ? (
                <EmptyState tab={tab} hasManualMode={inManualMode && botEnabled} />
            ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                    {visibleBets.map((b) => (
                        <BetCard
                            key={b.id}
                            bet={b}
                            onApproveAsIs={openApproveAsIs}
                            onApproveCustom={openApproveCustom}
                            onReject={openReject}
                        />
                    ))}
                </div>
            )}

            {modal && (
                <BetActionModal
                    bet={modal.bet}
                    mode={modal.kind}
                    bancaAtualCents={bancaAtualCents}
                    unitPct={unitPct}
                    onClose={() => setModal(null)}
                    onSubmitApprove={handleApprove}
                    onSubmitReject={handleReject}
                    busy={modalBusy}
                    error={modalError}
                />
            )}
        </div>
    );
}

function EmptyState({ tab, hasManualMode }: { tab: TabId; hasManualMode: boolean }) {
    const copy: Record<TabId, { title: string; desc: string }> = {
        pending: {
            title: hasManualMode
                ? "Nenhum sinal aguardando aprovação"
                : "Nada por aqui ainda",
            desc: hasManualMode
                ? "Quando o sistema emitir um sinal, ele aparece aqui pra você aprovar ou recusar."
                : "Ative o modo manual acima pra começar a receber sinais pra aprovação.",
        },
        open: {
            title: "Nenhuma aposta em andamento",
            desc: "Apostas que você aprovou aparecem aqui enquanto o jogo está rolando.",
        },
        closed: {
            title: "Sem histórico ainda",
            desc: "Apostas encerradas (GREEN, RED, recusadas) ficam guardadas aqui.",
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
