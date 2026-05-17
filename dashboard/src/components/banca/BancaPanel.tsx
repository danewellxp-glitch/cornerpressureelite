"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    Wallet,
    TrendingUp,
    TrendingDown,
    Loader2,
    Plus,
    Minus,
    RotateCcw,
    Pencil,
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
import {
    fetchBancaSummary,
    fetchBancaMovements,
    fetchBancaSeries,
    setupBanca,
    addBancaMovement,
    resetBanca,
    type BancaSummary,
    type BancaMovement,
    type BancaSeriesPoint,
} from "@/lib/api";
import { cn } from "@/lib/format";

const REFRESH_MS = 30_000;

const MOVEMENT_LABEL: Record<string, string> = {
    initial: "Banca inicial",
    bet_reserve: "Reserva (aposta aberta)",
    bet_settle: "Liquidação",
    deposit: "Depósito",
    withdraw: "Saque",
    reset: "Reset",
    correction: "Correção",
};

function brl(cents: number | null | undefined): string {
    if (cents == null) return "—";
    return (cents / 100).toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
    });
}

type ModalKind = "deposit" | "withdraw" | "correction" | "reset" | "edit_initial" | null;

export default function BancaPanel() {
    const [summary, setSummary] = useState<BancaSummary | null>(null);
    const [movements, setMovements] = useState<BancaMovement[]>([]);
    const [series, setSeries] = useState<BancaSeriesPoint[]>([]);
    const [loading, setLoading] = useState(true);
    const [setupBusy, setSetupBusy] = useState(false);
    const [modal, setModal] = useState<ModalKind>(null);

    const loadAll = useCallback(async () => {
        const [s, m, ser] = await Promise.all([
            fetchBancaSummary().catch(() => null),
            fetchBancaMovements({ page_size: 100 }).catch(() => null),
            fetchBancaSeries(30).catch(() => null),
        ]);
        setSummary(s);
        setMovements(m?.items ?? []);
        setSeries(ser?.series ?? []);
        setLoading(false);
    }, []);

    useEffect(() => {
        loadAll();
        const id = setInterval(loadAll, REFRESH_MS);
        return () => clearInterval(id);
    }, [loadAll]);

    if (loading && !summary) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
                <Loader2 className="size-6 animate-spin" />
                <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO BANCA…</span>
            </div>
        );
    }

    if (!summary?.configured) {
        return (
            <SetupWizard
                busy={setupBusy}
                onSubmit={async (payload) => {
                    setSetupBusy(true);
                    try {
                        const next = await setupBanca(payload);
                        setSummary(next);
                        await loadAll();
                    } catch (e) {
                        alert(e instanceof Error ? e.message : "Erro ao configurar banca");
                    } finally {
                        setSetupBusy(false);
                    }
                }}
            />
        );
    }

    const delta = summary.delta_cents ?? 0;
    const deltaPct = summary.delta_pct ?? 0;
    const positive = delta >= 0;
    const stats = summary.stats;

    return (
        <div className="space-y-6 max-w-[1200px] mx-auto">
            <header>
                <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                    Gestão financeira
                </div>
                <h1 className="font-display text-2xl font-bold mt-1">Banca</h1>
                <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                    Saldo, movimentos e métricas reais — baseadas no que você de fato apostou,
                    não no que o sistema sugeriu.
                </p>
            </header>

            {/* Saldo + ações */}
            <section className="grid gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2 piq-in rounded-2xl border border-mint/30 bg-gradient-to-br from-mint/10 to-card p-6 relative overflow-hidden">
                    <div className="absolute inset-0 grid-bg opacity-30" />
                    <div className="relative">
                        <div className="flex items-center gap-2 mb-1">
                            <Wallet className="size-4 text-mint-bright" />
                            <span className="font-mono text-[10px] tracking-wider text-mint uppercase">
                                Saldo atual
                            </span>
                        </div>
                        <div className="font-display text-4xl font-bold tabular text-foreground">
                            {brl(summary.banca_atual_cents)}
                        </div>
                        <div
                            className={cn(
                                "mt-2 font-mono text-sm tabular flex items-center gap-1.5",
                                positive ? "text-mint-bright" : "text-destructive",
                            )}
                        >
                            {positive ? <TrendingUp className="size-3.5" /> : <TrendingDown className="size-3.5" />}
                            {positive ? "+" : ""}
                            {brl(delta)} ({deltaPct >= 0 ? "+" : ""}
                            {deltaPct.toFixed(2)}%) desde início
                        </div>
                        <div className="mt-4 text-xs text-muted-foreground">
                            Banca inicial: {brl(summary.banca_inicial_cents)} ·{" "}
                            Stake padrão: {((summary.unit_pct ?? 0) * 100).toFixed(1)}%
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-1 gap-3">
                    <button
                        onClick={() => setModal("deposit")}
                        className="flex items-center gap-2 rounded-xl border border-success/40 bg-success/10 hover:bg-success/20 text-success px-4 py-3 text-sm font-medium transition"
                    >
                        <Plus className="size-4" />
                        Adicionar saldo
                    </button>
                    <button
                        onClick={() => setModal("withdraw")}
                        className="flex items-center gap-2 rounded-xl border border-border hover:border-warning/40 hover:bg-warning/10 hover:text-warning text-muted-foreground px-4 py-3 text-sm font-medium transition"
                    >
                        <Minus className="size-4" />
                        Sacar
                    </button>
                    <button
                        onClick={() => setModal("correction")}
                        className="flex items-center gap-2 rounded-xl border border-border hover:border-mint/40 hover:bg-mint/10 text-muted-foreground hover:text-mint-bright px-4 py-3 text-sm font-medium transition"
                    >
                        <Pencil className="size-4" />
                        Correção
                    </button>
                    <button
                        onClick={() => setModal("reset")}
                        className="flex items-center gap-2 rounded-xl border border-border hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive text-muted-foreground px-4 py-3 text-sm font-medium transition"
                    >
                        <RotateCcw className="size-4" />
                        Resetar
                    </button>
                </div>
            </section>

            {/* Métricas */}
            {stats && (
                <section className="grid gap-3 grid-cols-2 lg:grid-cols-5">
                    <MetricBox label="ROI" value={`${stats.roi_pct >= 0 ? "+" : ""}${stats.roi_pct.toFixed(2)}%`} tone={stats.roi_pct >= 0 ? "mint" : "danger"} />
                    <MetricBox label="Win Rate" value={`${(stats.win_rate * 100).toFixed(0)}%`} />
                    <MetricBox label="Avg Odd" value={stats.avg_odd > 0 ? stats.avg_odd.toFixed(2) : "—"} />
                    <MetricBox label="Drawdown Máx" value={brl(stats.max_drawdown_cents)} tone="danger" />
                    <MetricBox
                        label="Apostas decididas"
                        value={`${stats.settled} (${stats.wins}W/${stats.losses}L)`}
                    />
                </section>
            )}

            {/* Gráfico */}
            <section className="piq-in rounded-2xl border border-border bg-card p-5">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                            Evolução da banca
                        </div>
                        <div className="font-display text-base font-semibold mt-0.5">
                            Últimos 30 dias
                        </div>
                    </div>
                </div>
                <div style={{ width: "100%", height: 220 }}>
                    {series.length > 1 ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={series.map((p) => ({ ...p, saldo: p.saldo_cents / 100 }))} margin={{ left: -10, right: 8, top: 5, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="bancaGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="oklch(0.62 0.22 255)" stopOpacity={0.4} />
                                        <stop offset="100%" stopColor="oklch(0.62 0.22 255)" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.30 0.03 220 / 0.3)" />
                                <XAxis
                                    dataKey="dia"
                                    stroke="oklch(0.70 0.02 200)"
                                    tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
                                    tickFormatter={(v: string) => v.slice(5)}
                                />
                                <YAxis
                                    stroke="oklch(0.70 0.02 200)"
                                    tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
                                    tickFormatter={(v: number) =>
                                        v.toLocaleString("pt-BR", { maximumFractionDigits: 0 })
                                    }
                                />
                                <RTooltip
                                    contentStyle={{
                                        background: "oklch(0.20 0.028 232)",
                                        border: "1px solid oklch(0.62 0.22 255 / 0.4)",
                                        borderRadius: 12,
                                        fontSize: 12,
                                        fontFamily: "JetBrains Mono",
                                    }}
                                    formatter={(v) => [
                                        typeof v === "number"
                                            ? v.toLocaleString("pt-BR", {
                                                  style: "currency",
                                                  currency: "BRL",
                                              })
                                            : String(v),
                                        "Saldo",
                                    ]}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="saldo"
                                    stroke="oklch(0.74 0.18 235)"
                                    strokeWidth={2}
                                    fill="url(#bancaGrad)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                            Sem movimentos suficientes pra gráfico ainda.
                        </div>
                    )}
                </div>
            </section>

            {/* Histórico */}
            <section className="piq-in rounded-2xl border border-border bg-card overflow-hidden">
                <div className="p-5 border-b border-border">
                    <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                        Histórico de movimentos
                    </div>
                    <div className="font-display text-base font-semibold mt-0.5">
                        Últimos {Math.min(100, movements.length)} registros
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="border-b border-border bg-card/40">
                            <tr className="font-mono text-[10px] tracking-wider text-muted-foreground">
                                <th className="text-left font-medium px-4 py-2.5">DATA</th>
                                <th className="text-left font-medium px-4 py-2.5">TIPO</th>
                                <th className="text-left font-medium px-4 py-2.5">DESCRIÇÃO</th>
                                <th className="text-right font-medium px-4 py-2.5">VALOR</th>
                                <th className="text-right font-medium px-4 py-2.5">SALDO</th>
                            </tr>
                        </thead>
                        <tbody>
                            {movements.map((m) => (
                                <tr key={m.id} className="border-b border-border/40 hover:bg-mint/5">
                                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground whitespace-nowrap">
                                        {m.created_at
                                            ? new Date(m.created_at).toLocaleString("pt-BR", {
                                                  day: "2-digit",
                                                  month: "2-digit",
                                                  hour: "2-digit",
                                                  minute: "2-digit",
                                              })
                                            : "—"}
                                    </td>
                                    <td className="px-4 py-2.5">
                                        <span className="font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border border-border bg-muted/40">
                                            {(MOVEMENT_LABEL[m.tipo] ?? m.tipo).toUpperCase()}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2.5 text-xs text-muted-foreground truncate max-w-[300px]">
                                        {m.descricao || "—"}
                                    </td>
                                    <td
                                        className={cn(
                                            "px-4 py-2.5 text-right font-mono tabular text-xs",
                                            m.valor_cents > 0
                                                ? "text-mint-bright"
                                                : m.valor_cents < 0
                                                  ? "text-destructive"
                                                  : "text-muted-foreground",
                                        )}
                                    >
                                        {m.valor_cents >= 0 ? "+" : ""}
                                        {brl(m.valor_cents)}
                                    </td>
                                    <td className="px-4 py-2.5 text-right font-mono tabular text-xs">
                                        {brl(m.saldo_apos_cents)}
                                    </td>
                                </tr>
                            ))}
                            {movements.length === 0 && (
                                <tr>
                                    <td colSpan={5} className="px-4 py-8 text-center text-xs text-muted-foreground">
                                        Sem movimentos.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {modal && (
                <MovementModal
                    kind={modal}
                    saldoCents={summary.banca_atual_cents}
                    onClose={() => setModal(null)}
                    onDone={async () => {
                        setModal(null);
                        await loadAll();
                    }}
                />
            )}
        </div>
    );
}

function MetricBox({
    label,
    value,
    tone,
}: {
    label: string;
    value: string;
    tone?: "mint" | "danger";
}) {
    return (
        <div className="rounded-xl border border-border bg-card p-4">
            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                {label}
            </div>
            <div
                className={cn(
                    "font-display text-lg font-bold tabular mt-1",
                    tone === "mint" && "text-mint-bright",
                    tone === "danger" && "text-destructive",
                )}
            >
                {value}
            </div>
        </div>
    );
}

function SetupWizard({
    busy,
    onSubmit,
}: {
    busy: boolean;
    onSubmit: (p: { initial_cents: number; unit_pct: number; max_loss_per_day_cents: number; max_bets_per_day: number }) => Promise<void>;
}) {
    const [initialReais, setInitialReais] = useState("500,00");
    const [unitPct, setUnitPct] = useState("2");
    const [maxLossReais, setMaxLossReais] = useState("");
    const [maxBets, setMaxBets] = useState("");

    const parsed = useMemo(() => {
        const ini = parseFloat(initialReais.replace(",", ".")) * 100;
        const up = parseFloat(unitPct.replace(",", ".")) / 100;
        const ml = (parseFloat(maxLossReais.replace(",", ".")) || 0) * 100;
        const mb = parseInt(maxBets, 10) || 0;
        return {
            initial_cents: Math.round(ini || 0),
            unit_pct: up || 0.02,
            max_loss_per_day_cents: Math.round(ml || 0),
            max_bets_per_day: mb,
            valid: ini >= 5000 && up >= 0.001 && up <= 0.1,
        };
    }, [initialReais, unitPct, maxLossReais, maxBets]);

    return (
        <div className="max-w-xl mx-auto piq-in">
            <div className="rounded-2xl border border-mint/30 bg-card p-8">
                <div className="flex items-center gap-3 mb-2">
                    <Wallet className="size-6 text-mint-bright" />
                    <h1 className="font-display text-xl font-bold">Configure sua banca</h1>
                </div>
                <p className="text-sm text-muted-foreground mb-6">
                    Essa é a banca virtual que o sistema vai gerenciar. Você define quanto investiu
                    nas casas e qual % apostar por sinal. Tudo é editável depois.
                </p>

                <div className="space-y-4">
                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                            Banca inicial (R$)
                        </span>
                        <input
                            type="text"
                            inputMode="decimal"
                            value={initialReais}
                            onChange={(e) => setInitialReais(e.target.value)}
                            placeholder="500,00"
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                        />
                        <span className="text-xs text-muted-foreground mt-1 block">
                            Mínimo R$ 50,00 — quanto você de fato vai usar pra apostar
                        </span>
                    </label>

                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                            Stake padrão (%)
                        </span>
                        <input
                            type="text"
                            inputMode="decimal"
                            value={unitPct}
                            onChange={(e) => setUnitPct(e.target.value)}
                            placeholder="2"
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                        />
                        <span className="text-xs text-muted-foreground mt-1 block">
                            Sugerido: 1-3% da banca atual por aposta
                        </span>
                    </label>

                    <div className="grid grid-cols-2 gap-3">
                        <label className="block">
                            <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                Limite perda diária (R$)
                            </span>
                            <input
                                type="text"
                                inputMode="decimal"
                                value={maxLossReais}
                                onChange={(e) => setMaxLossReais(e.target.value)}
                                placeholder="opcional"
                                className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                            />
                        </label>
                        <label className="block">
                            <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                Máx apostas/dia
                            </span>
                            <input
                                type="text"
                                inputMode="numeric"
                                value={maxBets}
                                onChange={(e) => setMaxBets(e.target.value)}
                                placeholder="opcional"
                                className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                            />
                        </label>
                    </div>

                    <button
                        onClick={() =>
                            onSubmit({
                                initial_cents: parsed.initial_cents,
                                unit_pct: parsed.unit_pct,
                                max_loss_per_day_cents: parsed.max_loss_per_day_cents,
                                max_bets_per_day: parsed.max_bets_per_day,
                            })
                        }
                        disabled={!parsed.valid || busy}
                        className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-mint/20 border border-mint/40 text-mint-bright hover:bg-mint/30 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {busy && <Loader2 className="size-4 animate-spin" />}
                        Iniciar banca
                    </button>
                </div>
            </div>
        </div>
    );
}

function MovementModal({
    kind,
    saldoCents,
    onClose,
    onDone,
}: {
    kind: Exclude<ModalKind, null>;
    saldoCents: number;
    onClose: () => void;
    onDone: () => void | Promise<void>;
}) {
    const [valor, setValor] = useState("");
    const [motivo, setMotivo] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = "";
        };
    }, []);

    const labels: Record<Exclude<ModalKind, null>, { title: string; cta: string; helper?: string }> = {
        deposit: { title: "Adicionar saldo", cta: "Confirmar depósito" },
        withdraw: { title: "Sacar saldo", cta: "Confirmar saque" },
        correction: { title: "Correção manual", cta: "Aplicar correção", helper: "Use sinal de menos pra subtrair (ex: -50,00)" },
        reset: { title: "Resetar banca", cta: "Resetar agora" },
        edit_initial: { title: "Editar banca inicial", cta: "Salvar" },
    };
    const m = labels[kind];

    async function submit() {
        setBusy(true);
        setError(null);
        try {
            if (kind === "reset") {
                await resetBanca(motivo.trim() || undefined);
            } else {
                const n = parseFloat(valor.replace(",", "."));
                if (Number.isNaN(n) || n === 0) {
                    setError("Informe um valor.");
                    setBusy(false);
                    return;
                }
                let cents = Math.round(Math.abs(n) * 100);
                if (kind === "withdraw") cents = -cents;
                else if (kind === "correction") cents = Math.round(n * 100); // pode ser negativo
                await addBancaMovement({
                    tipo: kind === "edit_initial" ? "correction" : kind as "deposit" | "withdraw" | "correction",
                    valor_cents: cents,
                    descricao: undefined,
                    motivo: motivo.trim() || undefined,
                });
            }
            await onDone();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao registrar");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm">
            <div className="w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl border border-border bg-card shadow-2xl">
                <div className="p-5 border-b border-border">
                    <h2 className="font-display text-lg font-semibold">{m.title}</h2>
                    <p className="text-xs text-muted-foreground mt-1">
                        Saldo atual: {brl(saldoCents)}
                    </p>
                </div>

                <div className="p-5 space-y-4">
                    {kind !== "reset" && (
                        <label className="block">
                            <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                                Valor (R$)
                            </span>
                            <input
                                type="text"
                                inputMode="decimal"
                                value={valor}
                                onChange={(e) => setValor(e.target.value)}
                                placeholder="0,00"
                                autoFocus
                                className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                            />
                            {m.helper && (
                                <span className="text-xs text-muted-foreground mt-1 block">
                                    {m.helper}
                                </span>
                            )}
                        </label>
                    )}

                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                            Motivo (opcional)
                        </span>
                        <textarea
                            rows={2}
                            value={motivo}
                            onChange={(e) => setMotivo(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:border-mint/60"
                        />
                    </label>

                    {error && (
                        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                            {error}
                        </div>
                    )}
                </div>

                <div className="flex items-center justify-end gap-2 p-5 border-t border-border bg-card/40">
                    <button
                        onClick={onClose}
                        disabled={busy}
                        className="px-4 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground transition disabled:opacity-50"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={submit}
                        disabled={busy}
                        className={cn(
                            "px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2",
                            kind === "reset"
                                ? "border border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20"
                                : "bg-mint/20 border border-mint/40 text-mint-bright hover:bg-mint/30",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                        )}
                    >
                        {busy && <Loader2 className="size-3.5 animate-spin" />}
                        {m.cta}
                    </button>
                </div>
            </div>
        </div>
    );
}
