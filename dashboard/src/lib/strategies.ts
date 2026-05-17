export type StrategyTier = "conservative" | "moderate" | "aggressive" | "brute";

export type Market = "corners" | "cards";

export interface StrategyTierMeta {
    id: StrategyTier;
    label: string;
    short: string;
    description: string;
    /** Hex legado (MUI/Recharts inline). */
    color: string;
    bg: string;
    /** Classes Tailwind pro design novo PressureIQ (chip/pill). */
    chip: string;
    /** Classes Tailwind pra cor de texto (accent). */
    accent: string;
    riskOrder: number;
}

export const STRATEGY_TIERS: StrategyTierMeta[] = [
    {
        id: "conservative",
        label: "Conservador",
        short: "Cons.",
        description: "Menos sinais, maior confiança. Edge ≥ 1.5, Score ≥ 8.",
        color: "#4CAF50",
        bg: "rgba(76,175,80,0.15)",
        chip: "bg-success/15 text-success border-success/30",
        accent: "text-success",
        riskOrder: 0,
    },
    {
        id: "moderate",
        label: "Moderado",
        short: "Mod.",
        description: "Equilíbrio entre volume e qualidade (padrão).",
        color: "#00E5FF",
        bg: "rgba(0,229,255,0.12)",
        chip: "bg-mint/15 text-mint-bright border-mint/30",
        accent: "text-mint-bright",
        riskOrder: 1,
    },
    {
        id: "aggressive",
        label: "Agressivo",
        short: "Agr.",
        description: "Mais sinais, threshold menor.",
        color: "#FFC107",
        bg: "rgba(255,193,7,0.15)",
        chip: "bg-warning/15 text-warning border-warning/30",
        accent: "text-warning",
        riskOrder: 2,
    },
    {
        id: "brute",
        label: "Bruto",
        short: "Bru.",
        description: "Cobertura máxima, menor confiança por sinal.",
        color: "#FF5252",
        bg: "rgba(255,82,82,0.15)",
        chip: "bg-destructive/15 text-destructive border-destructive/30",
        accent: "text-destructive",
        riskOrder: 3,
    },
];

export const TIER_BY_ID: Record<StrategyTier, StrategyTierMeta> = STRATEGY_TIERS.reduce(
    (acc, t) => {
        acc[t.id] = t;
        return acc;
    },
    {} as Record<StrategyTier, StrategyTierMeta>
);

export const VALID_TIERS: StrategyTier[] = STRATEGY_TIERS.map((t) => t.id);

export function isValidTier(value: string | undefined | null): value is StrategyTier {
    return !!value && (VALID_TIERS as string[]).includes(value);
}

interface Threshold {
    min_score: number;
    min_edge: number;
}

// Mirror of corner-pressure-elite/engine/strategy_config.py thresholds.
// Keep in sync if the backend changes.
const CORNER_THRESHOLDS: Record<StrategyTier, Threshold> = {
    conservative: { min_score: 8, min_edge: 1.5 },
    moderate: { min_score: 6, min_edge: 1.2 },
    aggressive: { min_score: 5, min_edge: 0.8 },
    brute: { min_score: 4, min_edge: 0.5 },
};

const CARD_THRESHOLDS: Record<StrategyTier, Threshold> = {
    conservative: { min_score: 7, min_edge: 1.2 },
    moderate: { min_score: 5, min_edge: 0.5 },
    aggressive: { min_score: 4, min_edge: 0.3 },
    brute: { min_score: 3, min_edge: 0.0 },
};

export function thresholdsFor(market: Market): Record<StrategyTier, Threshold> {
    return market === "cards" ? CARD_THRESHOLDS : CORNER_THRESHOLDS;
}

export function computeMatchingTiers(
    score: number | null | undefined,
    edge: number | null | undefined,
    market: Market
): StrategyTier[] {
    if (score == null || edge == null) return [];
    const t = thresholdsFor(market);
    return VALID_TIERS.filter((tier) => score >= t[tier].min_score && edge >= t[tier].min_edge);
}

// The strictest tier the signal still satisfies (conservative > brute).
export function highestMatchingTier(matched: StrategyTier[]): StrategyTier | null {
    for (const tier of VALID_TIERS) {
        if (matched.includes(tier)) return tier;
    }
    return null;
}

export function signalMatchesUserTier(
    matched: StrategyTier[],
    userTier: StrategyTier
): boolean {
    return matched.includes(userTier);
}

export function marketFromTipoAnalise(tipo: string | undefined | null): Market {
    return (tipo || "").toUpperCase() === "CARTOES" ? "cards" : "corners";
}
