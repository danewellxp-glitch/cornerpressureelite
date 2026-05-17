"use client";

import { useEffect, useState } from "react";
import { X, AlertTriangle, Loader2 } from "lucide-react";
import type { MyBet, ApprovePayload, RejectPayload } from "@/lib/api";
import { cn } from "@/lib/format";

const VALID_HOUSES = ["betano", "bet365", "kto"];

const REJECTION_TAGS: { value: string; label: string }[] = [
    { value: "banca_insuficiente", label: "Banca insuficiente" },
    { value: "linha_nao_disponivel", label: "Linha não tinha na minha casa" },
    { value: "odd_mudou", label: "Odd já tinha mudado" },
    { value: "sem_confianca", label: "Não confiei no sinal" },
];

type Mode = "approve_as_is" | "approve_custom" | "reject";

export function BetActionModal({
    bet,
    mode,
    bancaAtualCents,
    unitPct,
    onClose,
    onSubmitApprove,
    onSubmitReject,
    busy,
    error,
}: {
    bet: MyBet;
    mode: Mode;
    bancaAtualCents: number;
    unitPct: number;
    onClose: () => void;
    onSubmitApprove: (payload: ApprovePayload) => Promise<void> | void;
    onSubmitReject: (payload: RejectPayload) => Promise<void> | void;
    busy?: boolean;
    error?: string | null;
}) {
    const suggestedStake = Math.round(bancaAtualCents * (unitPct || 0.02));
    const suggestedStakeReais = suggestedStake / 100;

    const [stakeReais, setStakeReais] = useState<string>(
        (suggestedStakeReais > 0 ? suggestedStakeReais : 50).toFixed(2),
    );
    const [house, setHouse] = useState<string>("betano");
    const [linha, setLinha] = useState<string>(bet.linha != null ? bet.linha.toString() : "");
    const [odd, setOdd] = useState<string>(bet.odd != null ? bet.odd.toFixed(2) : "");
    const [notes, setNotes] = useState<string>("");

    const [reason, setReason] = useState<string>("");
    const [tags, setTags] = useState<string[]>([]);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", handler);
        document.body.style.overflow = "hidden";
        return () => {
            window.removeEventListener("keydown", handler);
            document.body.style.overflow = "";
        };
    }, [onClose]);

    function parseReais(v: string): number | null {
        const n = parseFloat(v.replace(",", "."));
        if (Number.isNaN(n) || n <= 0) return null;
        return Math.round(n * 100);
    }

    async function handleSubmit() {
        if (mode === "reject") {
            await onSubmitReject({
                reason: reason.trim() || undefined,
                tags: tags.length ? tags : undefined,
            });
            return;
        }
        if (mode === "approve_as_is") {
            const stakeCents = parseReais(stakeReais);
            if (stakeCents == null) return;
            await onSubmitApprove({
                actual_stake_cents: stakeCents,
                actual_bet_house: house,
            });
            return;
        }
        // approve_custom
        const stakeCents = parseReais(stakeReais);
        const linhaN = parseFloat(linha.replace(",", "."));
        const oddN = parseFloat(odd.replace(",", "."));
        if (stakeCents == null) return;
        await onSubmitApprove({
            actual_stake_cents: stakeCents,
            actual_bet_house: house,
            actual_linha: !Number.isNaN(linhaN) ? linhaN : undefined,
            actual_odd: !Number.isNaN(oddN) ? oddN : undefined,
            customer_notes: notes.trim() || undefined,
        });
    }

    const title =
        mode === "approve_as_is"
            ? "Confirme execução"
            : mode === "approve_custom"
              ? "Aposta customizada"
              : "Não apostou";

    const submitLabel =
        mode === "reject" ? "Registrar recusa" : "Confirmar aposta";

    const submitDisabled =
        busy ||
        (mode !== "reject" && (parseReais(stakeReais) == null || !house));

    const linhaChanged =
        mode === "approve_custom" &&
        linha &&
        bet.linha != null &&
        parseFloat(linha.replace(",", ".")) !== bet.linha;
    const oddChanged =
        mode === "approve_custom" &&
        odd &&
        bet.odd != null &&
        parseFloat(odd.replace(",", ".")) !== bet.odd;

    return (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm">
            <div className="w-full sm:max-w-md max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-border bg-card shadow-2xl">
                <div className="flex items-center justify-between p-5 border-b border-border">
                    <h2 className="font-display text-lg font-semibold">{title}</h2>
                    <button
                        onClick={onClose}
                        aria-label="Fechar"
                        className="p-1 rounded hover:bg-muted/40 text-muted-foreground hover:text-foreground transition"
                    >
                        <X className="size-4" />
                    </button>
                </div>

                <div className="p-5 space-y-4">
                    <div className="rounded-lg bg-muted/30 p-3 text-sm">
                        <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mb-1">
                            Sinal sugerido
                        </div>
                        <div className="font-medium">
                            {bet.jogo_descricao} ·{" "}
                            {bet.selecao === "over" ? "Mais" : "Menos"}{" "}
                            {bet.linha?.toFixed(1)} {bet.market === "cards" ? "cartões" : "escanteios"}{" "}
                            @ {bet.odd?.toFixed(2)}
                        </div>
                    </div>

                    {mode !== "reject" && (
                        <>
                            {mode === "approve_custom" && (
                                <div className="grid grid-cols-2 gap-3">
                                    <label className="block">
                                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                            Linha real
                                        </span>
                                        <input
                                            type="text"
                                            inputMode="decimal"
                                            value={linha}
                                            onChange={(e) => setLinha(e.target.value)}
                                            placeholder={bet.linha?.toFixed(1) ?? "0.0"}
                                            className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                                        />
                                    </label>
                                    <label className="block">
                                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                            Odd real
                                        </span>
                                        <input
                                            type="text"
                                            inputMode="decimal"
                                            value={odd}
                                            onChange={(e) => setOdd(e.target.value)}
                                            placeholder={bet.odd?.toFixed(2) ?? "0.00"}
                                            className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                                        />
                                    </label>
                                </div>
                            )}

                            <label className="block">
                                <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                    Stake (R$)
                                </span>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="text"
                                        inputMode="decimal"
                                        value={stakeReais}
                                        onChange={(e) => setStakeReais(e.target.value)}
                                        placeholder="0,00"
                                        className="flex-1 px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                                    />
                                    {suggestedStake > 0 && (
                                        <button
                                            type="button"
                                            onClick={() => setStakeReais(suggestedStakeReais.toFixed(2))}
                                            className="font-mono text-[10px] tracking-wider px-2 py-1.5 rounded-lg border border-mint/40 text-mint hover:bg-mint/10 transition"
                                        >
                                            {(unitPct * 100).toFixed(1)}% banca
                                        </button>
                                    )}
                                </div>
                            </label>

                            <label className="block">
                                <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                    Casa de apostas
                                </span>
                                <select
                                    value={house}
                                    onChange={(e) => setHouse(e.target.value)}
                                    className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:border-mint/60"
                                >
                                    {VALID_HOUSES.map((h) => (
                                        <option key={h} value={h}>
                                            {h.charAt(0).toUpperCase() + h.slice(1)}
                                        </option>
                                    ))}
                                </select>
                            </label>

                            {(linhaChanged || oddChanged) && (
                                <div className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs text-warning">
                                    <AlertTriangle className="size-4 shrink-0 mt-0.5" />
                                    <span>
                                        Você apostou {linhaChanged ? `${linha}` : bet.linha} @ {oddChanged ? odd : bet.odd?.toFixed(2)}
                                        {" "}— diferente do sinal sugerido ({bet.linha?.toFixed(1)} @ {bet.odd?.toFixed(2)}). Confirma?
                                    </span>
                                </div>
                            )}

                            {mode === "approve_custom" && (
                                <label className="block">
                                    <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                        Observações (opcional)
                                    </span>
                                    <textarea
                                        rows={2}
                                        value={notes}
                                        onChange={(e) => setNotes(e.target.value)}
                                        placeholder="Por que apostou diferente?"
                                        className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:border-mint/60"
                                    />
                                </label>
                            )}
                        </>
                    )}

                    {mode === "reject" && (
                        <>
                            <div>
                                <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-2">
                                    Motivos (opcional, ajuda a melhorar sinais)
                                </span>
                                <div className="grid grid-cols-2 gap-2">
                                    {REJECTION_TAGS.map((t) => {
                                        const on = tags.includes(t.value);
                                        return (
                                            <button
                                                key={t.value}
                                                type="button"
                                                onClick={() =>
                                                    setTags((prev) =>
                                                        prev.includes(t.value)
                                                            ? prev.filter((x) => x !== t.value)
                                                            : [...prev, t.value],
                                                    )
                                                }
                                                className={cn(
                                                    "px-3 py-2 rounded-lg border text-xs text-left transition",
                                                    on
                                                        ? "border-mint/60 bg-mint/10 text-mint-bright"
                                                        : "border-border bg-background text-muted-foreground hover:border-mint/40 hover:text-foreground",
                                                )}
                                            >
                                                {t.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                            <label className="block">
                                <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                    Outro motivo
                                </span>
                                <textarea
                                    rows={2}
                                    value={reason}
                                    onChange={(e) => setReason(e.target.value)}
                                    placeholder="(opcional)"
                                    className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:border-mint/60"
                                />
                            </label>
                        </>
                    )}

                    {error && (
                        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                            <AlertTriangle className="size-4 shrink-0 mt-0.5" />
                            <span>{error}</span>
                        </div>
                    )}
                </div>

                <div className="flex items-center justify-end gap-2 p-5 border-t border-border bg-card/40">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={busy}
                        className="px-4 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground transition disabled:opacity-50"
                    >
                        Cancelar
                    </button>
                    <button
                        type="button"
                        onClick={handleSubmit}
                        disabled={submitDisabled}
                        className={cn(
                            "px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2",
                            mode === "reject"
                                ? "border border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20"
                                : "bg-mint/20 border border-mint/40 text-mint-bright hover:bg-mint/30",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                        )}
                    >
                        {busy && <Loader2 className="size-3.5 animate-spin" />}
                        {submitLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
