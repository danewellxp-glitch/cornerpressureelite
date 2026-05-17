"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Settings as SettingsIcon,
    Sparkles,
    Flag,
    Square,
    FlaskConical,
    Save,
    Shield,
    Target,
    Flame,
    Skull,
    Crown,
    CheckCircle2,
    Lock,
    Loader2,
    type LucideIcon,
} from "lucide-react";
import { STRATEGY_TIERS, TIER_BY_ID, type StrategyTier } from "@/lib/strategies";
import { useStrategyPreference } from "@/lib/useStrategyPreference";
import { useShellUser } from "@/components/shell/Shell";
import {
    fetchThresholds,
    updateThresholds,
    fetchDevModeConfig,
    updateDevModeConfig,
    fetchStrategyPerformance,
    type ThresholdsConfig,
    type DevModeConfig,
} from "@/lib/api";
import { cn } from "@/lib/format";

const TIER_ICONS: Record<StrategyTier, LucideIcon> = {
    conservative: Shield,
    moderate: Target,
    aggressive: Flame,
    brute: Skull,
};

type PerfMap = Record<StrategyTier, { n: number; hit: number; roi: number }>;

// Fallback: usado SOMENTE se o endpoint /stats/strategy-performance falhar ou
// se o dataset ainda não tiver volume suficiente. Marcamos `isDemo: true`
// no state pra UI mostrar pro user que é demonstração.
const PERF_FALLBACK: Record<"corners" | "cards", PerfMap> = {
    corners: {
        conservative: { n: 142, hit: 74.6, roi: 18.2 },
        moderate: { n: 318, hit: 64.1, roi: 12.4 },
        aggressive: { n: 612, hit: 56.3, roi: 6.8 },
        brute: { n: 1284, hit: 48.7, roi: -2.1 },
    },
    cards: {
        conservative: { n: 96, hit: 68.4, roi: 9.6 },
        moderate: { n: 254, hit: 58.2, roi: 5.1 },
        aggressive: { n: 488, hit: 52.4, roi: 1.3 },
        brute: { n: 920, hit: 46.8, roi: -3.4 },
    },
};

export default function SettingsPage() {
    const { preference, update } = useStrategyPreference();
    const { plan, isAdmin } = useShellUser();
    const cardsAllowed = isAdmin || plan === "max";

    const [strategyToast, setStrategyToast] = useState<string | null>(null);

    const [thresholds, setThresholds] = useState<ThresholdsConfig>({
        min_score_normal: 6,
        min_score_premium: 8,
        min_edge_normal: 0.8,
        min_edge_premium: 1.5,
    });
    const [thresholdsLoading, setThresholdsLoading] = useState(false);
    const [savedToast, setSavedToast] = useState<string | null>(null);

    const [dev, setDev] = useState<DevModeConfig>({
        enabled: false,
        max_games: 5,
        polling_interval: 180,
        status_check_interval: 1800,
        api_daily_limit: 1000,
        normal_polling_interval: 60,
        normal_status_check_interval: 60,
        normal_api_daily_limit: 7500,
    });
    const [devLoading, setDevLoading] = useState(false);
    const [devToast, setDevToast] = useState<string | null>(null);

    const [perf, setPerf] = useState<Record<"corners" | "cards", PerfMap>>(PERF_FALLBACK);
    const [perfIsDemo, setPerfIsDemo] = useState(true);

    useEffect(() => {
        let cancelled = false;
        async function loadPerf() {
            try {
                const [c, k] = await Promise.all([
                    fetchStrategyPerformance("corners", 30),
                    fetchStrategyPerformance("cards", 30),
                ]);
                if (cancelled) return;
                const empty = STRATEGY_TIERS.reduce((acc, t) => {
                    acc[t.id] = { n: 0, hit: 0, roi: 0 };
                    return acc;
                }, {} as PerfMap);
                const mapTiers = (tiers: Record<string, { n: number; hit_rate: number; roi_pct: number }>) => {
                    const out = { ...empty };
                    for (const t of STRATEGY_TIERS) {
                        const v = tiers[t.id];
                        if (v) {
                            out[t.id] = { n: v.n, hit: v.hit_rate * 100, roi: v.roi_pct };
                        }
                    }
                    return out;
                };
                const corners = mapTiers(c.tiers);
                const cards = mapTiers(k.tiers);
                // Considera demo se TODOS os tiers têm n=0 (sem volume real ainda)
                const hasVolume =
                    STRATEGY_TIERS.some((t) => corners[t.id].n > 0) ||
                    STRATEGY_TIERS.some((t) => cards[t.id].n > 0);
                setPerf({ corners, cards });
                setPerfIsDemo(!hasVolume);
            } catch {
                // mantém fallback mock + flag isDemo=true
            }
        }
        loadPerf();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (!isAdmin) return;
        setThresholdsLoading(true);
        fetchThresholds()
            .then((res) => setThresholds((prev) => ({ ...prev, ...res.thresholds })))
            .catch(() => { })
            .finally(() => setThresholdsLoading(false));

        setDevLoading(true);
        fetchDevModeConfig()
            .then((res) => setDev(res.config))
            .catch(() => { })
            .finally(() => setDevLoading(false));
    }, [isAdmin]);

    function saveStrategy(market: "corners" | "cards", tier: StrategyTier) {
        if (market === "cards" && !cardsAllowed) return;
        update({ [market]: tier });
        setStrategyToast(`Estratégia ${market === "cards" ? "cartões" : "escanteios"} salva: ${TIER_BY_ID[tier].label}`);
        setTimeout(() => setStrategyToast(null), 2400);
    }

    async function saveAdmin() {
        try {
            await updateThresholds(thresholds);
            setSavedToast("Thresholds salvos.");
        } catch (err) {
            setSavedToast(err instanceof Error ? `Erro: ${err.message}` : "Erro ao salvar.");
        }
        setTimeout(() => setSavedToast(null), 2400);
    }

    async function saveDev(patch: Partial<DevModeConfig>) {
        const next = { ...dev, ...patch };
        setDev(next);
        try {
            await updateDevModeConfig(next);
            setDevToast(
                patch.enabled === true
                    ? "DEV TEST MODE ativado — aplica em até 1 ciclo."
                    : patch.enabled === false
                        ? "DEV TEST MODE desativado — robô volta ao normal."
                        : "Config DEV salva.",
            );
        } catch (err) {
            setDevToast(err instanceof Error ? `Erro: ${err.message}` : "Erro ao salvar DEV.");
        }
        setTimeout(() => setDevToast(null), 3000);
    }

    return (
        <div className="space-y-8 max-w-[1400px] mx-auto pb-12">
            <header className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.22em] text-muted-foreground uppercase flex items-center gap-2">
                        <SettingsIcon className="size-3" /> Painel de controle
                    </div>
                    <h1 className="font-display text-3xl font-bold mt-1 text-gradient-mint">
                        Configurações
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-xl">
                        Estratégia por mercado, thresholds do engine e modo de teste para administradores.
                    </p>
                </div>
                <div className="flex items-center gap-2 font-mono text-[10px] tracking-wider text-muted-foreground">
                    <span>USUÁRIO</span>
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-mint/40 bg-mint/10 text-mint-bright">
                        {isAdmin ? "ADMIN" : "USER"} · {plan.toUpperCase()}
                    </span>
                </div>
            </header>

            <SectionHeader
                icon={Sparkles}
                title="Sua estratégia"
                sub="Escolha o perfil de risco para cada mercado. Aplica no dashboard, no histórico e no envio de sinais via WhatsApp."
            />
            <AnimatePresence>
                {strategyToast && <Toast key="s">{strategyToast}</Toast>}
            </AnimatePresence>
            <div className="grid lg:grid-cols-2 gap-4">
                <StrategyCard
                    icon={Flag}
                    title="Escanteios"
                    market="corners"
                    value={preference.corners}
                    onChange={(t) => saveStrategy("corners", t)}
                    perf={perf.corners}
                    isDemo={perfIsDemo}
                />
                <div className="relative">
                    <StrategyCard
                        icon={Square}
                        title="Cartões Amarelos"
                        market="cards"
                        value={preference.cards}
                        disabled={!cardsAllowed}
                        onChange={(t) => cardsAllowed && saveStrategy("cards", t)}
                        perf={perf.cards}
                        isDemo={perfIsDemo}
                    />
                    {!cardsAllowed && (
                        <div className="absolute inset-0 rounded-2xl bg-background/70 backdrop-blur-sm border border-dashed border-warning/40 flex flex-col items-center justify-center text-center p-6 gap-3">
                            <span className="inline-flex items-center gap-1.5 font-mono text-[10px] tracking-[0.2em] px-2 py-1 rounded-full bg-warning/15 text-warning border border-warning/30">
                                <Crown className="size-3" /> DISPONÍVEL NO PLANO MAX
                            </span>
                            <p className="text-xs text-muted-foreground max-w-xs">
                                Receba sinais de cartões e tudo do plano Pro — desbloqueie todos os tiers para este mercado.
                            </p>
                            <a
                                href="/login?step=plans"
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-xs bg-gradient-to-br from-warning to-warning/70 text-background hover:brightness-110 transition"
                            >
                                Fazer upgrade para Max →
                            </a>
                        </div>
                    )}
                </div>
            </div>

            {isAdmin && (
                <>
                    <div className="h-px bg-border" />
                    <SectionHeader
                        icon={SettingsIcon}
                        title="Configurações do sistema"
                        sub="Estas opções afetam o robô para TODOS os usuários. Mude com cuidado."
                        badge="GLOBAL"
                    />
                    <AnimatePresence>{savedToast && <Toast key="adm">{savedToast}</Toast>}</AnimatePresence>
                    <div className="grid lg:grid-cols-2 gap-4">
                        <Panel title="Escanteios — Thresholds" accent="mint">
                            {thresholdsLoading ? (
                                <Loader2 className="size-4 animate-spin text-muted-foreground" />
                            ) : (
                                <>
                                    <NumberField
                                        label="Min Score Normal"
                                        value={thresholds.min_score_normal ?? 0}
                                        onChange={(v) => setThresholds({ ...thresholds, min_score_normal: v })}
                                    />
                                    <NumberField
                                        label="Min Score Premium"
                                        value={thresholds.min_score_premium ?? 0}
                                        onChange={(v) => setThresholds({ ...thresholds, min_score_premium: v })}
                                    />
                                    <NumberField
                                        step={0.1}
                                        label="Min Edge Normal"
                                        value={thresholds.min_edge_normal ?? 0}
                                        onChange={(v) => setThresholds({ ...thresholds, min_edge_normal: v })}
                                    />
                                    <NumberField
                                        step={0.1}
                                        label="Min Edge Premium"
                                        value={thresholds.min_edge_premium ?? 0}
                                        onChange={(v) => setThresholds({ ...thresholds, min_edge_premium: v })}
                                    />
                                </>
                            )}
                        </Panel>

                        <Panel title="Info" accent="mint">
                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                                Os thresholds acima controlam quais sinais o engine emite:
                                <br />- <span className="text-foreground tabular">score ≥ Normal</span> + <span className="text-foreground tabular">edge ≥ Normal</span> → sinal padrão
                                <br />- <span className="text-foreground tabular">score ≥ Premium</span> + <span className="text-foreground tabular">edge ≥ Premium</span> → sinal premium
                                <br /><br />
                                Configurações de polling e API daily limit estão no DEV TEST MODE abaixo.
                            </p>
                        </Panel>
                    </div>
                    <div className="flex justify-end">
                        <button
                            onClick={saveAdmin}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-mint text-background hover:bg-mint-bright transition glow-mint"
                        >
                            <Save className="size-3.5" /> Salvar thresholds
                        </button>
                    </div>
                </>
            )}

            {isAdmin && (
                <>
                    <div className="h-px bg-border" />
                    <div className="flex items-end justify-between gap-3 flex-wrap">
                        <SectionHeader
                            icon={FlaskConical}
                            title="DEV TEST MODE"
                            sub="Quando ativo, o robô limita budget diário da API-Football, sobe polling, reduz status check e analisa só os jogos relevantes (janela 50-90'). Aplica em até 1 ciclo."
                            inline
                            badge={dev.enabled ? "ATIVO" : "DESATIVADO"}
                            badgeTone={dev.enabled ? "warning" : "muted"}
                        />
                    </div>
                    <AnimatePresence>{devToast && <Toast key="dev" tone="warning">{devToast}</Toast>}</AnimatePresence>

                    <Panel title="Parâmetros DEV" accent="warning">
                        {devLoading ? (
                            <Loader2 className="size-4 animate-spin text-muted-foreground" />
                        ) : (
                            <>
                                <label className="flex items-center justify-between gap-3 -mt-1 mb-2">
                                    <span className="text-sm font-medium">Ativar DEV TEST MODE</span>
                                    <Switch checked={dev.enabled} onChange={(v) => saveDev({ enabled: v })} tone="warning" />
                                </label>
                                <div className="h-px bg-border my-1" />
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <NumberField
                                        label="Max jogos por ciclo"
                                        hint="1–20. Prioriza jogos na janela 50-90'."
                                        value={dev.max_games}
                                        min={1}
                                        max={20}
                                        onChange={(v) => setDev({ ...dev, max_games: v })}
                                    />
                                    <NumberField
                                        label="Polling DEV (s)"
                                        hint="60–3600. Recomendado 180s."
                                        value={dev.polling_interval}
                                        min={60}
                                        max={3600}
                                        onChange={(v) => setDev({ ...dev, polling_interval: v })}
                                    />
                                    <NumberField
                                        label="Status check DEV (s)"
                                        hint="60–86400. Recomendado 1800s."
                                        value={dev.status_check_interval}
                                        min={60}
                                        max={86400}
                                        onChange={(v) => setDev({ ...dev, status_check_interval: v })}
                                    />
                                    <NumberField
                                        label="Limite diário DEV"
                                        hint="Cap diário DEV. Sugerido 1000 (plano pago)."
                                        value={dev.api_daily_limit}
                                        min={10}
                                        max={100000}
                                        onChange={(v) => setDev({ ...dev, api_daily_limit: v })}
                                    />
                                </div>
                                <div className="h-px bg-border my-1" />
                                <p className="text-[11px] text-muted-foreground font-mono leading-relaxed">
                                    Quando DESATIVADO, o robô volta para: polling{" "}
                                    <span className="text-foreground tabular">{dev.normal_polling_interval}s</span>, status{" "}
                                    <span className="text-foreground tabular">{dev.normal_status_check_interval}s</span>, budget{" "}
                                    <span className="text-foreground tabular">{dev.normal_api_daily_limit}/dia</span>.
                                </p>
                                <div className="flex justify-end pt-2">
                                    <button
                                        onClick={() => saveDev({})}
                                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-warning text-background hover:brightness-110 transition"
                                    >
                                        <Save className="size-3.5" /> Salvar DEV Config
                                    </button>
                                </div>
                            </>
                        )}
                    </Panel>
                </>
            )}
        </div>
    );
}

/* ---------- subcomponents ---------- */

function SectionHeader({
    icon: Icon,
    title,
    sub,
    badge,
    badgeTone = "mint",
    inline = false,
}: {
    icon: LucideIcon;
    title: string;
    sub?: string;
    badge?: string;
    badgeTone?: "mint" | "warning" | "muted";
    inline?: boolean;
}) {
    return (
        <div className={cn("space-y-1", inline && "flex-1 min-w-0")}>
            <div className="flex items-center gap-2">
                <Icon className="size-4 text-mint-bright" />
                <h2 className="font-display text-lg font-semibold">{title}</h2>
                {badge && (
                    <span
                        className={cn(
                            "font-mono text-[10px] tracking-[0.15em] px-1.5 py-0.5 rounded-full border",
                            badgeTone === "warning"
                                ? "bg-warning/15 text-warning border-warning/30"
                                : badgeTone === "muted"
                                    ? "bg-muted/40 text-muted-foreground border-border"
                                    : "bg-mint/15 text-mint-bright border-mint/30",
                        )}
                    >
                        {badge}
                    </span>
                )}
            </div>
            {sub && <p className="text-xs text-muted-foreground max-w-3xl">{sub}</p>}
        </div>
    );
}

function StrategyCard({
    icon: Icon,
    title,
    market,
    value,
    onChange,
    disabled,
    perf,
    isDemo,
}: {
    icon: LucideIcon;
    title: string;
    market: "corners" | "cards";
    value: StrategyTier;
    onChange: (t: StrategyTier) => void;
    disabled?: boolean;
    perf: Record<StrategyTier, { n: number; hit: number; roi: number }>;
    isDemo?: boolean;
}) {
    const meta = TIER_BY_ID[value];
    return (
        <div className="piq-in rounded-2xl border border-border bg-card p-5">
            <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                    <Icon className="size-4 text-mint-bright" />
                    <div className="font-display text-base font-semibold">{title}</div>
                </div>
                <div className="flex items-center gap-2">
                    {isDemo && (
                        <span className="font-mono text-[9px] tracking-wider px-1.5 py-0.5 rounded border border-warning/40 bg-warning/10 text-warning">
                            DEMO
                        </span>
                    )}
                    <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                        {market === "cards" ? "MERCADO / CARTÕES" : "MERCADO / ESCANTEIOS"}
                    </span>
                </div>
            </div>
            <p className="text-xs text-muted-foreground mb-4">
                {isDemo
                    ? "Dataset ainda sem volume — números abaixo são placeholders para visualização."
                    : "Quanto mais conservador, menos sinais e maior confiança. Quanto mais bruto, mais sinais e maior risco."}
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {STRATEGY_TIERS.map((t) => {
                    const TIcon = TIER_ICONS[t.id];
                    const p = perf[t.id];
                    const active = t.id === value;
                    return (
                        <motion.button
                            key={t.id}
                            whileHover={!disabled ? { y: -2 } : {}}
                            whileTap={!disabled ? { scale: 0.97 } : {}}
                            disabled={disabled}
                            onClick={() => onChange(t.id)}
                            className={cn(
                                "text-left rounded-xl border p-3 transition flex flex-col gap-1.5",
                                active
                                    ? "border-mint/50 bg-mint/5 glow-mint"
                                    : "border-border bg-background/40 hover:border-border/80",
                                disabled && "opacity-50 cursor-not-allowed hover:border-border",
                            )}
                        >
                            <div className="flex items-center justify-between">
                                <div className={cn("size-7 rounded-lg grid place-items-center border", t.chip)}>
                                    <TIcon className="size-3.5" />
                                </div>
                                {active && <CheckCircle2 className="size-3.5 text-mint-bright" />}
                            </div>
                            <div className="font-display text-sm font-semibold">{t.label}</div>
                            <div className="font-mono text-[10px] tabular">
                                <span className="text-foreground">{p.hit.toFixed(1)}%</span>
                                <span className="text-muted-foreground"> acerto</span>
                            </div>
                            <div
                                className={cn(
                                    "font-mono text-[10px] tabular",
                                    p.roi >= 0 ? "text-success" : "text-destructive",
                                )}
                            >
                                {p.roi >= 0 ? "+" : ""}
                                {p.roi.toFixed(1)}% ROI · n={p.n}
                            </div>
                        </motion.button>
                    );
                })}
            </div>

            <div className="mt-4 rounded-xl border border-border bg-background/40 p-3 flex items-start gap-3">
                <span className={cn("inline-flex font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border shrink-0", meta.chip)}>
                    {meta.label}
                </span>
                <p className="text-[11px] text-muted-foreground leading-snug">{meta.description}</p>
            </div>
        </div>
    );
}

function Panel({
    title,
    accent,
    children,
}: {
    title: string;
    accent: "mint" | "warning";
    children: React.ReactNode;
}) {
    return (
        <div className="piq-in rounded-2xl border border-border bg-card p-5">
            <div
                className={cn(
                    "font-display text-sm font-semibold mb-3 flex items-center gap-2",
                    accent === "warning" ? "text-warning" : "text-mint-bright",
                )}
            >
                <span className={cn("size-1.5 rounded-full", accent === "warning" ? "bg-warning" : "bg-mint")} />
                {title}
            </div>
            <div className="flex flex-col gap-3">{children}</div>
        </div>
    );
}

function NumberField({
    label,
    value,
    onChange,
    hint,
    step = 1,
    min,
    max,
}: {
    label: string;
    value: number;
    onChange: (v: number) => void;
    hint?: string;
    step?: number;
    min?: number;
    max?: number;
}) {
    return (
        <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                {label}
            </span>
            <input
                type="number"
                value={value}
                step={step}
                min={min}
                max={max}
                onChange={(e) => onChange(Number(e.target.value))}
                className="px-3 py-1.5 rounded-lg border border-border bg-background/60 text-sm font-mono tabular focus:outline-none focus:border-mint/50"
            />
            {hint && <span className="text-[10px] text-muted-foreground">{hint}</span>}
        </label>
    );
}

function Switch({
    checked,
    onChange,
    tone = "mint",
}: {
    checked: boolean;
    onChange: (v: boolean) => void;
    tone?: "mint" | "warning";
}) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            onClick={() => onChange(!checked)}
            className={cn(
                "relative inline-flex h-5 w-9 rounded-full border transition",
                checked
                    ? tone === "warning"
                        ? "bg-warning border-warning"
                        : "bg-mint border-mint"
                    : "bg-muted border-border",
            )}
        >
            <span
                className={cn(
                    "absolute top-0.5 size-3.5 rounded-full bg-background shadow transition-transform",
                    checked ? "translate-x-[18px]" : "translate-x-0.5",
                )}
            />
        </button>
    );
}

function Toast({
    children,
    tone = "success",
}: {
    children: React.ReactNode;
    tone?: "success" | "warning";
}) {
    return (
        <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className={cn(
                "rounded-xl border px-4 py-2.5 text-sm inline-flex items-center gap-2",
                tone === "warning"
                    ? "border-warning/40 bg-warning/10 text-warning"
                    : "border-mint/40 bg-mint/10 text-mint-bright",
            )}
        >
            {tone === "warning" ? <Lock className="size-3.5" /> : <CheckCircle2 className="size-3.5" />}
            {children}
        </motion.div>
    );
}
