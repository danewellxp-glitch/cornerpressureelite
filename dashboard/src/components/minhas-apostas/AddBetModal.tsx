"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2, Gift } from "lucide-react";
import {
    createManualBet,
    fetchLiveGames,
    fetchUpcomingGames,
    type BancaSummary,
    type CreateManualBetBody,
} from "@/lib/api";
import { cn } from "@/lib/format";

/** Jogo selecionável: ao vivo (in-play) ou agendado (hoje, antes do apito). */
interface SelGame {
    id: number;
    home: string;
    away: string;
    liga: string;
    kind: "live" | "upcoming";
    detail: string;
}

/* ──────────────────────────────────────────────────────────────────
 *  AddBetModal — registra aposta MANUAL (single/multi) em jogos ao vivo.
 *  Cada leg: jogo ao vivo + escanteio/cartão + over/under + linha + odd.
 *  Legs escanteio/cartão em jogo monitorado = auto-settle GREEN/RED. (0017)
 * ────────────────────────────────────────────────────────────────── */

const brl = (cents: number) =>
    (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

type Mercado = "escanteios" | "cartoes";

interface LegDraft {
    jogoId: number | null;
    mercado: Mercado;
    side: "over" | "under";
    linha: string;
    odd_leg: string;
}

const emptyLeg = (): LegDraft => ({
    jogoId: null,
    mercado: "escanteios",
    side: "over",
    linha: "",
    odd_leg: "",
});

function legLabel(leg: LegDraft, game?: SelGame): string {
    const merc = leg.mercado === "escanteios" ? "escanteios" : "cartões";
    const dir = leg.side === "over" ? "Mais de" : "Menos de";
    const linha = leg.linha || "?";
    const jogo = game ? `${game.home} vs ${game.away}` : "(jogo?)";
    return `${jogo} — ${dir} ${linha} ${merc}`;
}

export function AddBetModal({
    banca,
    onClose,
    onCreated,
}: {
    banca: BancaSummary | null;
    onClose: () => void;
    onCreated: () => void;
}) {
    const [games, setGames] = useState<SelGame[]>([]);
    const [loadingGames, setLoadingGames] = useState(true);
    const [legs, setLegs] = useState<LegDraft[]>([emptyLeg()]);
    const [bonusPctStr, setBonusPctStr] = useState("0");
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState<string | null>(null);

    const unitValue = banca?.unit_value_cents ?? 0;
    const seed =
        unitValue > 0
            ? unitValue
            : banca?.configured && banca.unit_pct
              ? Math.round((banca.banca_atual_cents * banca.unit_pct) / 100)
              : 0;
    const [valStr, setValStr] = useState((seed / 100).toFixed(2));

    useEffect(() => {
        let alive = true;
        Promise.all([
            fetchLiveGames().catch(() => null),
            fetchUpcomingGames().catch(() => null),
        ])
            .then(([live, up]) => {
                if (!alive) return;
                const seen = new Set<number>();
                const out: SelGame[] = [];
                // Ao vivo primeiro (in-play).
                const liveArr = live
                    ? [...(live.na_janela || []), ...(live.pre_janela || []), ...(live.pos_janela || [])]
                    : [];
                for (const g of liveArr) {
                    if (seen.has(g.id)) continue;
                    seen.add(g.id);
                    const extra =
                        (g.escanteios != null ? ` · ${g.escanteios} esc` : "") +
                        (g.cartoes != null ? ` · ${g.cartoes} cart` : "");
                    out.push({
                        id: g.id, home: g.home, away: g.away, liga: g.liga,
                        kind: "live", detail: `AO VIVO ${g.minuto}' · ${g.placar}${extra}`,
                    });
                }
                // Agendados de hoje (antes do apito).
                for (const g of up?.proximos || []) {
                    if (seen.has(g.id)) continue;
                    seen.add(g.id);
                    out.push({
                        id: g.id, home: g.home, away: g.away, liga: g.liga,
                        kind: "upcoming", detail: `${g.hora_inicio || "hoje"} · agendado`,
                    });
                }
                setGames(out);
            })
            .finally(() => alive && setLoadingGames(false));
        return () => {
            alive = false;
        };
    }, []);

    useEffect(() => {
        const h = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !busy) onClose();
        };
        document.addEventListener("keydown", h);
        return () => document.removeEventListener("keydown", h);
    }, [busy, onClose]);

    const gameById = useMemo(() => {
        const m = new Map<number, SelGame>();
        games.forEach((g) => m.set(g.id, g));
        return m;
    }, [games]);

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
    const isMulti = legs.length > 1;

    const setUnits = (u: number) => {
        if (unitValue > 0) setValStr(((unitValue * u) / 100).toFixed(2));
    };
    const addLeg = () => setLegs((p) => [...p, emptyLeg()]);
    const removeLeg = (idx: number) =>
        setLegs((p) => (p.length > 1 ? p.filter((_, i) => i !== idx) : p));
    const updateLeg = (idx: number, patch: Partial<LegDraft>) =>
        setLegs((p) => p.map((l, i) => (i === idx ? { ...l, ...patch } : l)));

    const confirm = async () => {
        if (combinedOdd <= 1.0) return setErr("Odd combinada precisa ser > 1.00");
        if (stakeCents <= 0) return setErr("Valor apostado precisa ser > 0");
        if (banca?.configured && stakeCents > banca.banca_atual_cents)
            return setErr(`Valor maior que saldo (${brl(banca.banca_atual_cents)})`);
        for (const l of legs) {
            if (!l.jogoId) return setErr("Cada seleção precisa de um jogo");
            if (!l.linha || !Number.isFinite(parseFloat(l.linha)))
                return setErr("Cada seleção precisa de uma linha");
            const o = parseFloat(l.odd_leg);
            if (!o || o <= 1.0) return setErr("Cada seleção precisa de odd > 1.00");
        }
        if (bonusPct < 0 || bonusPct > 5) return setErr("Bonus deve estar entre 0 e 500%");

        setBusy(true);
        setErr(null);
        try {
            const apiLegs: CreateManualBetBody["legs"] = legs.map((l) => ({
                mercado: l.mercado,
                descricao: legLabel(l, gameById.get(l.jogoId!)),
                jogo_id: l.jogoId!,
                linha: parseFloat(l.linha),
                side: l.side,
                odd_leg: parseFloat(l.odd_leg),
            }));
            const descricao = isMulti
                ? `Múltipla · ${legs.length} seleções`
                : apiLegs[0].descricao;
            await createManualBet({
                descricao,
                odd_entrada: combinedOdd,
                valor_apostado_cents: stakeCents,
                bonus_pct: bonusPct,
                legs: apiLegs,
            });
            onCreated();
        } catch (e) {
            setErr(e instanceof Error ? e.message : "Erro ao criar aposta");
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
                        adicionar aposta
                    </div>
                    <h3 className="font-display text-xl font-bold leading-tight">
                        {isMulti ? `Múltipla com ${legs.length} seleções` : "Aposta em jogo ao vivo"}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1.5 font-mono">
                        Escanteio/cartão em jogo monitorado fecha GREEN/RED automático.
                    </p>
                </div>

                {!banca?.configured && (
                    <div className="text-xs text-warning border border-warning/40 bg-warning/10 p-2 rounded">
                        Banca não configurada — a aposta conta pro ROI mas o saldo não debita.
                    </div>
                )}

                {!loadingGames && games.length === 0 && (
                    <div className="text-xs text-warning border border-warning/40 bg-warning/10 p-2 rounded">
                        Nenhum jogo ao vivo nem agendado pra hoje nas ligas monitoradas.
                    </div>
                )}

                {/* Seleções */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            Bilhete{isMulti ? ` (Múltipla — ${legs.length} jogos)` : " (Simples)"}
                        </span>
                        <button
                            type="button"
                            onClick={addLeg}
                            disabled={busy}
                            className="inline-flex items-center gap-1 px-2 py-1 font-mono text-[10px] tracking-wider text-mint border border-mint/40 hover:bg-mint/10 transition rounded-md"
                        >
                            <Plus className="size-3" />
                            ADD JOGO
                        </button>
                    </div>
                    <div className="space-y-2">
                        {legs.map((leg, idx) => (
                            <LegEditor
                                key={idx}
                                leg={leg}
                                games={games}
                                onChange={(p) => updateLeg(idx, p)}
                                onRemove={legs.length > 1 ? () => removeLeg(idx) : null}
                                disabled={busy || loadingGames}
                            />
                        ))}
                    </div>
                </div>

                {/* Stake em unidades */}
                {unitValue > 0 && (
                    <div className="rounded-lg border border-info/30 bg-info/5 p-3 space-y-2">
                        <span className="font-mono text-[10px] tracking-wider text-info uppercase">
                            Stake em unidades · 1u = {brl(unitValue)}
                        </span>
                        <div className="flex gap-1.5 flex-wrap">
                            {[1, 2, 3, 5, 10].map((u) => {
                                const active = Math.abs(stakeUnits - u) < 0.05;
                                return (
                                    <button
                                        key={u}
                                        type="button"
                                        onClick={() => setUnits(u)}
                                        disabled={busy}
                                        className={cn(
                                            "px-2.5 py-1 rounded-md border font-mono text-xs tracking-wider transition",
                                            active
                                                ? "border-info bg-info/20 text-info"
                                                : "border-border text-muted-foreground hover:text-foreground",
                                        )}
                                    >
                                        {u}u
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
                                {unitValue > 0 && stakeUnits > 0 && <> · {stakeUnits.toFixed(1)}u</>}
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
                        {busy ? "CRIANDO…" : "CRIAR APOSTA"}
                    </button>
                </div>
            </div>
        </div>
    );
}

function LegEditor({
    leg,
    games,
    onChange,
    onRemove,
    disabled,
}: {
    leg: LegDraft;
    games: SelGame[];
    onChange: (p: Partial<LegDraft>) => void;
    onRemove: (() => void) | null;
    disabled: boolean;
}) {
    return (
        <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
            <div className="flex gap-2">
                <select
                    value={leg.jogoId ?? ""}
                    onChange={(e) => onChange({ jogoId: e.target.value ? Number(e.target.value) : null })}
                    disabled={disabled}
                    className="flex-1 bg-input border border-border px-2 py-1.5 text-xs rounded focus:outline-none focus:border-mint"
                >
                    <option value="">— escolha o jogo —</option>
                    {games.map((g) => (
                        <option key={g.id} value={g.id}>
                            {g.home} vs {g.away} · {g.detail}
                        </option>
                    ))}
                </select>
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
                <select
                    value={leg.mercado}
                    onChange={(e) => onChange({ mercado: e.target.value as Mercado })}
                    disabled={disabled}
                    className="bg-input border border-border px-2 py-1.5 font-mono text-xs rounded focus:outline-none focus:border-mint"
                >
                    <option value="escanteios">Escanteios</option>
                    <option value="cartoes">Cartões</option>
                </select>
                <select
                    value={leg.side}
                    onChange={(e) => onChange({ side: e.target.value as "over" | "under" })}
                    disabled={disabled}
                    className="bg-input border border-border px-2 py-1.5 font-mono text-xs rounded focus:outline-none focus:border-mint"
                >
                    <option value="over">Mais de</option>
                    <option value="under">Menos de</option>
                </select>
                <input
                    type="number"
                    step="0.5"
                    value={leg.linha}
                    onChange={(e) => onChange({ linha: e.target.value })}
                    placeholder="Linha"
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
