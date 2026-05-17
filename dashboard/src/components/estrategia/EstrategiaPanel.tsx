"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Save, CheckCircle2, AlertTriangle, Target } from "lucide-react";
import {
    fetchBotConfig,
    patchBotConfig,
    fetchStrategyPreference,
    updateStrategyPreference,
    type BotConfig,
    type StrategyPreference,
} from "@/lib/api";
import { STRATEGY_TIERS, type StrategyTier } from "@/lib/strategies";
import { cn } from "@/lib/format";

const KNOWN_MARKETS = [
    { value: "corners", label: "Escanteios" },
    { value: "cards", label: "Cartões amarelos" },
];

export default function EstrategiaPanel() {
    const [config, setConfig] = useState<BotConfig | null>(null);
    const [strategy, setStrategy] = useState<StrategyPreference | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [savedAt, setSavedAt] = useState<Date | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Local edit state
    const [cornersTier, setCornersTier] = useState<StrategyTier>("moderate");
    const [cardsTier, setCardsTier] = useState<StrategyTier>("moderate");
    const [unitPct, setUnitPct] = useState("2");
    const [maxBets, setMaxBets] = useState("");
    const [maxLossReais, setMaxLossReais] = useState("");
    const [markets, setMarkets] = useState<string[]>(["corners", "cards"]);

    const loadAll = useCallback(async () => {
        setLoading(true);
        try {
            const [cfg, pref] = await Promise.all([
                fetchBotConfig().catch(() => null),
                fetchStrategyPreference().catch(() => null),
            ]);
            setConfig(cfg);
            setStrategy(pref);
            if (cfg) {
                setUnitPct(((cfg.unit_pct ?? 0.02) * 100).toString());
                setMaxBets(cfg.max_bets_per_day > 0 ? String(cfg.max_bets_per_day) : "");
                setMaxLossReais(
                    cfg.max_loss_per_day_cents > 0
                        ? (cfg.max_loss_per_day_cents / 100).toFixed(2)
                        : "",
                );
                setMarkets(cfg.allowed_markets && cfg.allowed_markets.length > 0 ? cfg.allowed_markets : ["corners", "cards"]);
            }
            if (pref) {
                if (pref.corners_strategy) setCornersTier(pref.corners_strategy as StrategyTier);
                if (pref.cards_strategy) setCardsTier(pref.cards_strategy as StrategyTier);
            }
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadAll();
    }, [loadAll]);

    async function handleSave() {
        setSaving(true);
        setError(null);
        try {
            const upN = parseFloat(unitPct.replace(",", ".")) / 100;
            const maxLossCents = Math.round((parseFloat(maxLossReais.replace(",", ".")) || 0) * 100);
            const maxBetsN = parseInt(maxBets, 10) || 0;

            if (!(upN >= 0.001 && upN <= 0.1)) {
                throw new Error("Stake % deve estar entre 0.1% e 10%");
            }
            if (markets.length === 0) {
                throw new Error("Selecione ao menos um mercado");
            }

            await Promise.all([
                patchBotConfig({
                    unit_pct: upN,
                    max_bets_per_day: maxBetsN,
                    max_loss_per_day_cents: maxLossCents,
                    allowed_markets: markets,
                }),
                updateStrategyPreference({
                    corners_strategy: cornersTier,
                    cards_strategy: cardsTier,
                }),
            ]);
            setSavedAt(new Date());
            await loadAll();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao salvar");
        } finally {
            setSaving(false);
        }
    }

    if (loading && !config) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
                <Loader2 className="size-6 animate-spin" />
                <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO ESTRATÉGIA…</span>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-[1100px] mx-auto">
            <header>
                <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                    Suas preferências
                </div>
                <h1 className="font-display text-2xl font-bold mt-1">Estratégia</h1>
                <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                    Quais sinais você quer receber, qual % da banca apostar, e limites diários.
                    Mudanças valem pra todos os sinais futuros — não retroage.
                </p>
            </header>

            {!config && (
                <div className="rounded-2xl border border-warning/40 bg-warning/10 p-5 flex items-start gap-3">
                    <AlertTriangle className="size-5 text-warning shrink-0 mt-0.5" />
                    <div>
                        <h3 className="font-display text-sm font-semibold text-warning">
                            Configure sua banca primeiro
                        </h3>
                        <p className="text-xs text-warning/80 mt-1">
                            A estratégia depende de uma banca configurada. Vá em Banca pra começar.
                        </p>
                    </div>
                </div>
            )}

            {/* Tier por mercado */}
            <section className="piq-in rounded-2xl border border-border bg-card p-6">
                <div className="flex items-center gap-2 mb-1">
                    <Target className="size-4 text-mint-bright" />
                    <h2 className="font-display text-lg font-semibold">Tier de filtros</h2>
                </div>
                <p className="text-sm text-muted-foreground mb-5">
                    O tier define a rigidez dos filtros. Mais conservador = menos sinais, mais
                    confiança. Mais agressivo = mais sinais, menor confiança individual.
                </p>

                <div className="space-y-5">
                    <TierSelector
                        market="Escanteios"
                        value={cornersTier}
                        onChange={setCornersTier}
                    />
                    <TierSelector
                        market="Cartões amarelos"
                        value={cardsTier}
                        onChange={setCardsTier}
                    />
                </div>
            </section>

            {/* Mercados ativos */}
            <section className="piq-in rounded-2xl border border-border bg-card p-6">
                <h2 className="font-display text-lg font-semibold mb-1">Mercados ativos</h2>
                <p className="text-sm text-muted-foreground mb-4">
                    Quais mercados o sistema considera quando emite sinais pra você.
                </p>
                <div className="flex flex-wrap gap-2">
                    {KNOWN_MARKETS.map((m) => {
                        const on = markets.includes(m.value);
                        return (
                            <button
                                key={m.value}
                                onClick={() =>
                                    setMarkets((prev) =>
                                        prev.includes(m.value)
                                            ? prev.filter((x) => x !== m.value)
                                            : [...prev, m.value],
                                    )
                                }
                                className={cn(
                                    "px-4 py-2 rounded-lg border text-sm font-medium transition",
                                    on
                                        ? "border-mint/60 bg-mint/10 text-mint-bright"
                                        : "border-border bg-background text-muted-foreground hover:border-mint/40",
                                )}
                            >
                                {m.label}
                            </button>
                        );
                    })}
                </div>
            </section>

            {/* Stake e limites */}
            <section className="piq-in rounded-2xl border border-border bg-card p-6 space-y-4">
                <h2 className="font-display text-lg font-semibold">Stake e limites</h2>

                <div className="grid gap-4 md:grid-cols-3">
                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                            Stake padrão (%)
                        </span>
                        <input
                            type="text"
                            inputMode="decimal"
                            value={unitPct}
                            onChange={(e) => setUnitPct(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                        />
                        <span className="text-xs text-muted-foreground mt-1 block">
                            % da banca por aposta
                        </span>
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
                            placeholder="0 = ilimitado"
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                        />
                        <span className="text-xs text-muted-foreground mt-1 block">
                            Circuit breaker diário
                        </span>
                    </label>

                    <label className="block">
                        <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase block mb-1">
                            Limite perda diária (R$)
                        </span>
                        <input
                            type="text"
                            inputMode="decimal"
                            value={maxLossReais}
                            onChange={(e) => setMaxLossReais(e.target.value)}
                            placeholder="0 = ilimitado"
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background font-mono tabular text-sm focus:outline-none focus:border-mint/60"
                        />
                        <span className="text-xs text-muted-foreground mt-1 block">
                            Pausa o dia ao atingir
                        </span>
                    </label>
                </div>
            </section>

            {error && (
                <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
                    <AlertTriangle className="size-4" /> {error}
                </div>
            )}

            <div className="flex items-center justify-between pt-2">
                {savedAt && (
                    <div className="flex items-center gap-1.5 text-xs text-mint">
                        <CheckCircle2 className="size-3.5" />
                        Salvo às {savedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                    </div>
                )}
                <button
                    onClick={handleSave}
                    disabled={saving || !config}
                    className="ml-auto flex items-center gap-2 px-5 py-2.5 rounded-lg bg-mint/20 border border-mint/40 text-mint-bright hover:bg-mint/30 text-sm font-medium transition disabled:opacity-50"
                >
                    {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                    Salvar mudanças
                </button>
            </div>
        </div>
    );
}

function TierSelector({
    market,
    value,
    onChange,
}: {
    market: string;
    value: StrategyTier;
    onChange: (t: StrategyTier) => void;
}) {
    return (
        <div>
            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mb-2">
                {market}
            </div>
            <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
                {STRATEGY_TIERS.map((t) => {
                    const on = value === t.id;
                    return (
                        <button
                            key={t.id}
                            onClick={() => onChange(t.id)}
                            className={cn(
                                "text-left p-3 rounded-xl border transition",
                                on
                                    ? `${t.chip} ring-1 ring-current/40`
                                    : "border-border bg-background hover:border-mint/40",
                            )}
                        >
                            <div className={cn("font-display text-sm font-semibold", on && t.accent)}>
                                {t.label}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                                {t.description}
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
