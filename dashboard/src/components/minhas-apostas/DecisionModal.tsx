"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2, Gift } from "lucide-react";
import {
    decideSignal,
    type BancaSummary,
    type UserSignalDetail,
    type LegMercado,
    type DecideEnteredBody,
} from "@/lib/api";
import { cn } from "@/lib/format";

/* ──────────────────────────────────────────────────────────────────
 *  DecisionModal — fonte ÚNICA de registro de entrada (simples OU multi).
 *  Usado tanto em "Minhas Apostas" quanto em "Sinais recentes" (dashboard)
 *  pra garantir que a odd_entrada gravada seja sempre a odd COMBINADA das
 *  legs — sem divergência de odd entre as duas telas.
 * ────────────────────────────────────────────────────────────────── */

const brl = (cents: number) =>
    (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Sugestão de stake em unidades baseada na força do sinal CPES. */
function suggestedUnits(signal: UserSignalDetail): number {
    const tier = (signal.tipo_sinal || "").toUpperCase();
    let u = tier === "PREMIUM" ? 2 : 1;
    if ((signal.edge ?? 0) >= 2.0) u += 1;
    return u;
}

const MERCADO_LABEL: Record<LegMercado, string> = {
    escanteios: "Escanteios",
    cartoes: "Cartões",
    gols: "Gols / Marcador",
    "1x2": "1X2 / Resultado",
    ambas_marcam: "Ambas Marcam",
    custom: "Outro",
};

const MERCADOS: LegMercado[] = ["escanteios", "cartoes", "gols", "1x2", "ambas_marcam", "custom"];

interface LegDraft {
    mercado: LegMercado;
    descricao: string;
    linha: string;
    odd_leg: string;
}

function legFromSignal(signal: UserSignalDetail): LegDraft {
    const isEsc = signal.tipo_analise === "ESCANTEIOS";
    return {
        mercado: isEsc ? "escanteios" : "cartoes",
        descricao: `Mais de ${signal.linha} ${isEsc ? "escanteios" : "cartões"}`,
        linha: signal.linha != null ? String(signal.linha) : "",
        odd_leg: signal.odd != null ? signal.odd.toFixed(2) : "1.50",
    };
}

export function DecisionModal({
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
    const [legs, setLegs] = useState<LegDraft[]>([legFromSignal(signal)]);
    const [bonusPctStr, setBonusPctStr] = useState("0");

    const unitValue = banca?.unit_value_cents ?? 0;
    const sugUnits = suggestedUnits(signal);
    const sugestaoCents =
        unitValue > 0
            ? unitValue * sugUnits
            : banca?.configured && banca.unit_pct
              ? Math.round((banca.banca_atual_cents * banca.unit_pct) / 100)
              : 0;
    const [valStr, setValStr] = useState((sugestaoCents / 100).toFixed(2));
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState<string | null>(null);

    const setUnits = (u: number) => {
        if (unitValue > 0) setValStr(((unitValue * u) / 100).toFixed(2));
    };

    // Odd combinada = produto das odds das legs
    const combinedOdd = useMemo(
        () =>
            legs.reduce((acc, l) => {
                const o = parseFloat(l.odd_leg);
                return Number.isFinite(o) && o > 1 ? acc * o : acc;
            }, 1),
        [legs],
    );

    const stakeCents = Math.round((parseFloat(valStr) || 0) * 100);
    const stakeUnits = unitValue > 0 ? stakeCents / unitValue : 0;
    const bonusPct = parseFloat(bonusPctStr) / 100 || 0;
    const premiosBrutos = Math.round(stakeCents * combinedOdd);
    const bonus = Math.round((premiosBrutos - stakeCents) * bonusPct);
    const totalRetorno = premiosBrutos + bonus;

    useEffect(() => {
        const h = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !busy) onClose();
        };
        document.addEventListener("keydown", h);
        return () => document.removeEventListener("keydown", h);
    }, [busy, onClose]);

    const addLeg = () =>
        setLegs((prev) => [
            ...prev,
            { mercado: "1x2", descricao: "", linha: "", odd_leg: "" },
        ]);

    const removeLeg = (idx: number) =>
        setLegs((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== idx) : prev));

    const updateLeg = (idx: number, patch: Partial<LegDraft>) =>
        setLegs((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));

    const confirm = async () => {
        if (combinedOdd <= 1.0) {
            setErr("Odd combinada precisa ser > 1.00");
            return;
        }
        if (stakeCents <= 0) {
            setErr("Valor apostado precisa ser > 0");
            return;
        }
        if (banca?.configured && stakeCents > banca.banca_atual_cents) {
            setErr(`Valor maior que saldo (${brl(banca.banca_atual_cents)})`);
            return;
        }
        for (const l of legs) {
            if (!l.descricao.trim()) {
                setErr("Cada leg precisa de descrição");
                return;
            }
            const o = parseFloat(l.odd_leg);
            if (!o || o <= 1.0) {
                setErr(`Leg "${l.descricao || "(sem nome)"}": odd > 1.00 obrigatória`);
                return;
            }
        }
        if (bonusPct < 0 || bonusPct > 5) {
            setErr("Bonus deve estar entre 0 e 500%");
            return;
        }

        setBusy(true);
        setErr(null);
        try {
            const body: DecideEnteredBody = {
                decision: "entered",
                odd_entrada: combinedOdd,
                valor_apostado_cents: stakeCents,
                bonus_pct: bonusPct,
                legs: legs.map((l) => ({
                    mercado: l.mercado,
                    descricao: l.descricao.trim(),
                    linha: l.linha ? parseFloat(l.linha) : null,
                    odd_leg: parseFloat(l.odd_leg),
                })),
            };
            await decideSignal(signal.signal_id, body);
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
                className="w-full max-w-2xl border border-border bg-card p-6 space-y-5 rounded-2xl max-h-[90vh] overflow-y-auto"
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
                        Sinal CPES: {signal.tipo_sinal} · linha {signal.linha} @{" "}
                        {signal.odd?.toFixed(2)}
                    </p>
                </div>

                {!banca?.configured && (
                    <div className="text-xs text-warning border border-warning/40 bg-warning/10 p-2 rounded">
                        Banca não configurada — entrada vai contar pro ROI mas o saldo não
                        vai debitar.
                    </div>
                )}

                {/* Legs */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Bilhete{legs.length > 1 ? ` (Multi com ${legs.length} legs)` : " (Simples)"}
                        </span>
                        <button
                            type="button"
                            onClick={addLeg}
                            disabled={busy}
                            className="inline-flex items-center gap-1 px-2 py-1 font-mono text-[10px] tracking-wider text-mint border border-mint/40 hover:bg-mint/10 transition rounded-md"
                        >
                            <Plus className="size-3" />
                            ADD MERCADO
                        </button>
                    </div>
                    <div className="space-y-2">
                        {legs.map((leg, idx) => (
                            <LegEditor
                                key={idx}
                                leg={leg}
                                onChange={(p) => updateLeg(idx, p)}
                                onRemove={legs.length > 1 ? () => removeLeg(idx) : null}
                                disabled={busy}
                            />
                        ))}
                    </div>
                </div>

                {/* Sugestão por unidades */}
                {unitValue > 0 && (
                    <div className="rounded-lg border border-info/30 bg-info/5 p-3 space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="font-mono text-[10px] tracking-wider text-info uppercase">
                                Stake em unidades · 1u = {brl(unitValue)}
                            </span>
                            <span className="font-mono text-[10px] text-info-foreground">
                                Sinal {(signal.tipo_sinal || "").toUpperCase()} → sugerido{" "}
                                <strong>{sugUnits}u</strong>
                            </span>
                        </div>
                        <div className="flex gap-1.5 flex-wrap">
                            {[1, 2, 3, 5, 10].map((u) => {
                                const active = Math.abs(stakeUnits - u) < 0.05;
                                const isSug = u === sugUnits;
                                return (
                                    <button
                                        key={u}
                                        type="button"
                                        onClick={() => setUnits(u)}
                                        disabled={busy}
                                        className={cn(
                                            "px-2.5 py-1 rounded-md border font-mono text-xs tracking-wider transition relative",
                                            active
                                                ? "border-info bg-info/20 text-info"
                                                : "border-border text-muted-foreground hover:text-foreground",
                                        )}
                                    >
                                        {u}u
                                        {isSug && (
                                            <span className="absolute -top-1 -right-1 size-2 rounded-full bg-info" />
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Valor apostado (R$)
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
                                {unitValue > 0 && stakeUnits > 0 && (
                                    <> · {stakeUnits.toFixed(1)}u</>
                                )}
                            </span>
                        )}
                    </label>
                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Bonus turbinada (%)
                        </span>
                        <input
                            type="number"
                            step="1"
                            min="0"
                            max="500"
                            value={bonusPctStr}
                            onChange={(e) => setBonusPctStr(e.target.value)}
                            placeholder="0"
                            className="mt-1 w-full bg-input border border-border px-3 py-2 font-mono text-sm tabular focus:outline-none focus:border-mint rounded-lg"
                            disabled={busy}
                        />
                        <span className="font-mono text-[10px] text-muted-foreground mt-1 block">
                            ex: 25 = +25% sobre lucro líquido (opcional, dá pra editar depois)
                        </span>
                    </label>
                </div>

                {/* Preview */}
                <div className="rounded-lg border border-mint/30 bg-mint/5 p-3 space-y-1 font-mono text-xs tabular">
                    <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Odd combinada</span>
                        <span className="text-mint-bright font-bold">{combinedOdd.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Aposta</span>
                        <span>{brl(stakeCents)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Prêmios brutos</span>
                        <span>{brl(premiosBrutos)}</span>
                    </div>
                    {bonusPct > 0 && (
                        <div className="flex items-center justify-between text-mint-bright">
                            <span>
                                <Gift className="inline size-3 -mt-0.5 mr-1" />
                                Bonus +{(bonusPct * 100).toFixed(0)}%
                            </span>
                            <span>+{brl(bonus)}</span>
                        </div>
                    )}
                    <div className="flex items-center justify-between border-t border-mint/20 pt-1 mt-1">
                        <span className="font-semibold">Total se GREEN</span>
                        <span className="font-bold text-mint-bright">{brl(totalRetorno)}</span>
                    </div>
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

function LegEditor({
    leg,
    onChange,
    onRemove,
    disabled,
}: {
    leg: LegDraft;
    onChange: (p: Partial<LegDraft>) => void;
    onRemove: (() => void) | null;
    disabled: boolean;
}) {
    return (
        <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
            <div className="flex gap-2">
                <select
                    value={leg.mercado}
                    onChange={(e) => onChange({ mercado: e.target.value as LegMercado })}
                    disabled={disabled}
                    className="bg-input border border-border px-2 py-1.5 font-mono text-xs rounded focus:outline-none focus:border-mint"
                >
                    {MERCADOS.map((m) => (
                        <option key={m} value={m}>
                            {MERCADO_LABEL[m]}
                        </option>
                    ))}
                </select>
                <input
                    type="text"
                    value={leg.descricao}
                    onChange={(e) => onChange({ descricao: e.target.value })}
                    placeholder="Descrição (ex: Empate, Mais de 8.5, ...)"
                    disabled={disabled}
                    className="flex-1 bg-input border border-border px-2 py-1.5 text-xs rounded focus:outline-none focus:border-mint"
                />
                {onRemove && (
                    <button
                        type="button"
                        onClick={onRemove}
                        disabled={disabled}
                        className="px-2 py-1.5 border border-destructive/40 text-destructive hover:bg-destructive/10 transition rounded"
                    >
                        <Trash2 className="size-3" />
                    </button>
                )}
            </div>
            <div className="flex gap-2">
                <input
                    type="number"
                    step="0.5"
                    value={leg.linha}
                    onChange={(e) => onChange({ linha: e.target.value })}
                    placeholder="Linha (opcional)"
                    disabled={disabled}
                    className="flex-1 bg-input border border-border px-2 py-1.5 font-mono text-xs tabular rounded focus:outline-none focus:border-mint"
                />
                <input
                    type="number"
                    step="0.01"
                    min="1.01"
                    value={leg.odd_leg}
                    onChange={(e) => onChange({ odd_leg: e.target.value })}
                    placeholder="Odd"
                    disabled={disabled}
                    className="flex-1 bg-input border border-border px-2 py-1.5 font-mono text-xs tabular rounded focus:outline-none focus:border-mint"
                />
            </div>
        </div>
    );
}
