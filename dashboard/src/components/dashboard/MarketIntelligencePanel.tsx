"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
    Activity,
    Flame,
    Trophy,
    Clock,
    ArrowRight,
    Loader2,
    ChevronDown,
    ChevronRight,
    Cpu,
} from "lucide-react";
import {
    fetchAudit,
    fetchStrategyPerformance,
    fetchUpcomingGames,
    fetchPollingStats,
    type AuditData,
    type AuditGameDetail,
    type StrategyPerformance,
    type TierPerformance,
    type UpcomingGame,
    type PollingStatsResponse,
} from "@/lib/api";
import { STRATEGY_TIERS, TIER_BY_ID, type StrategyTier } from "@/lib/strategies";
import { cn, fmtTime } from "@/lib/format";
import { useShellUser } from "@/components/shell/Shell";

const REFRESH_MS = 30_000;

// ─── Helpers ───────────────────────────────────────────────────

function friendlyMotivo(m: string | null | undefined): string | null {
    if (!m) return null;
    const map: Record<string, string> = {
        score_baixo: "Score abaixo do tier",
        edge_baixo: "Edge abaixo do tier",
        fora_janela: "Fora da janela",
        sem_odds: "Sem odds disponíveis",
        sem_linha: "Sem linha disponível",
        linha_alta: "Linha muito alta",
    };
    // tenta normalizar — backend devolve free-text
    const low = m.toLowerCase();
    for (const [k, v] of Object.entries(map)) {
        if (low.includes(k)) return v;
    }
    return m;
}

function countdownLabel(min: number): string {
    if (min <= 0) return "agora";
    if (min < 60) return `em ${min} min`;
    const h = Math.floor(min / 60);
    const rest = min % 60;
    if (rest === 0) return `em ${h}h`;
    return `em ${h}h ${rest}min`;
}

function rankTierByROI(tiers: Record<string, TierPerformance>): TierPerformance[] {
    return Object.values(tiers)
        .filter((t) => t.n >= 3)
        .sort((a, b) => b.roi_pct - a.roi_pct);
}

function areTiersIdentical(rows: TierPerformance[]): boolean {
    if (rows.length < 2) return false;
    const ref = rows[0];
    return rows.every(
        (r) => r.n === ref.n && r.greens === ref.greens && r.reds === ref.reds,
    );
}

// ─── Panel ─────────────────────────────────────────────────────

export function MarketIntelligencePanel() {
    const { isAdmin } = useShellUser();

    const [audit, setAudit] = useState<AuditData | null>(null);
    const [perfCorners, setPerfCorners] = useState<StrategyPerformance | null>(null);
    const [perfCards, setPerfCards] = useState<StrategyPerformance | null>(null);
    const [upcoming, setUpcoming] = useState<UpcomingGame[]>([]);
    const [polling, setPolling] = useState<PollingStatsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [marketTab, setMarketTab] = useState<"corners" | "cards">("corners");
    const [adminOpen, setAdminOpen] = useState(false);

    useEffect(() => {
        let cancelled = false;
        async function load() {
            try {
                const [a, pc, pk, up, ps] = await Promise.allSettled([
                    fetchAudit(),
                    fetchStrategyPerformance("corners", 30),
                    fetchStrategyPerformance("cards", 30),
                    fetchUpcomingGames(),
                    isAdmin ? fetchPollingStats() : Promise.resolve(null),
                ]);
                if (cancelled) return;
                if (a.status === "fulfilled") setAudit(a.value);
                if (pc.status === "fulfilled") setPerfCorners(pc.value);
                if (pk.status === "fulfilled") setPerfCards(pk.value);
                if (up.status === "fulfilled") setUpcoming(up.value.proximos ?? []);
                if (ps.status === "fulfilled") setPolling(ps.value);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        load();
        const id = setInterval(load, REFRESH_MS);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, [isAdmin]);

    // Top jogos com pressão crescente (ordena por edge desc, fallback pressure_score).
    const hotGames = useMemo<AuditGameDetail[]>(() => {
        const jogos = audit?.jogos ?? [];
        return [...jogos]
            .filter((g) => (g.pressure_score ?? 0) > 0 || (g.edge ?? 0) > 0)
            .sort((a, b) => {
                const ea = a.edge ?? -999;
                const eb = b.edge ?? -999;
                if (ea !== eb) return eb - ea;
                return (b.pressure_score ?? 0) - (a.pressure_score ?? 0);
            })
            .slice(0, 3);
    }, [audit]);

    const tierRanked = useMemo(() => {
        const perf = marketTab === "corners" ? perfCorners : perfCards;
        return perf ? rankTierByROI(perf.tiers) : [];
    }, [marketTab, perfCorners, perfCards]);

    const nextGames = upcoming.slice(0, 3);

    if (loading && !audit && !perfCorners) {
        return (
            <div className="piq-in rounded-2xl border border-border bg-card p-8 flex flex-col items-center justify-center min-h-[200px]">
                <Loader2 className="size-5 text-muted-foreground animate-spin" />
                <span className="font-mono text-[10px] tracking-wider text-muted-foreground mt-2">
                    CARREGANDO INTELIGÊNCIA…
                </span>
            </div>
        );
    }

    return (
        <div className="piq-in rounded-2xl border border-border bg-card overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase flex items-center gap-1.5">
                        <Flame className="size-3" /> Inteligência ao vivo
                    </div>
                    <div className="font-display text-lg font-semibold mt-0.5">
                        O que o sistema está vendo agora
                    </div>
                </div>
                {audit?.atualizado && (
                    <span className="font-mono text-[10px] tabular text-muted-foreground tracking-wider">
                        {fmtTime(audit.atualizado)}
                    </span>
                )}
            </div>

            <div className="grid lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-border">
                {/* Jogos sob pressão */}
                <section className="p-5">
                    <div className="flex items-baseline justify-between mb-3">
                        <div>
                            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                                Jogos sob pressão
                            </div>
                            <div className="text-[10px] text-muted-foreground/70 mt-0.5">
                                Top 3 com maior edge ou score agora
                            </div>
                        </div>
                        <Link
                            href="/jogos-ao-vivo"
                            className="font-mono text-[10px] tracking-wider text-mint hover:text-mint-bright"
                        >
                            VER TODOS →
                        </Link>
                    </div>
                    {hotGames.length === 0 ? (
                        <div className="py-8 text-center text-xs text-muted-foreground">
                            Nenhum jogo na janela de análise.
                        </div>
                    ) : (
                        <ul className="space-y-2">
                            {hotGames.map((g, i) => (
                                <HotGameRow key={i} game={g} />
                            ))}
                        </ul>
                    )}
                </section>

                {/* Tier campeão */}
                <section className="p-5">
                    <div className="flex items-baseline justify-between mb-3">
                        <div>
                            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase flex items-center gap-1.5">
                                <Trophy className="size-3" /> Tier campeão · 30d
                            </div>
                            <div className="text-[10px] text-muted-foreground/70 mt-0.5">
                                Qual filtro está dando mais ROI
                            </div>
                        </div>
                        <div className="inline-flex rounded-md border border-border bg-card/60 p-0.5">
                            {(["corners", "cards"] as const).map((m) => (
                                <button
                                    key={m}
                                    onClick={() => setMarketTab(m)}
                                    className={cn(
                                        "px-2 py-0.5 text-[10px] font-mono tracking-wider rounded transition",
                                        marketTab === m
                                            ? "bg-mint/10 text-mint-bright"
                                            : "text-muted-foreground hover:text-foreground",
                                    )}
                                >
                                    {m === "corners" ? "ESCN" : "CARD"}
                                </button>
                            ))}
                        </div>
                    </div>
                    {tierRanked.length === 0 ? (
                        <div className="py-8 text-center text-xs text-muted-foreground">
                            Dados insuficientes ainda.
                            <br />
                            Min: 3 sinais decididos por tier.
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {tierRanked.map((t, i) => (
                                <TierRow key={t.tier} t={t} highlight={i === 0} />
                            ))}
                            {tierRanked.length > 1 && areTiersIdentical(tierRanked) && (
                                <div className="text-[10px] text-muted-foreground/80 italic px-1 pt-1 leading-snug">
                                    Tiers são cumulativos: sinais que passam Moderado também
                                    passam Agressivo e Bruto. Quando todos têm os mesmos números,
                                    é porque ninguém ainda passou nos filtros mais estritos.
                                </div>
                            )}
                            <Link
                                href="/estrategia"
                                className="mt-3 flex items-center justify-between text-xs px-3 py-2 rounded-lg border border-mint/30 bg-mint/5 hover:bg-mint/10 text-mint-bright transition"
                            >
                                <span className="font-medium">Configurar meu tier</span>
                                <ArrowRight className="size-3.5" />
                            </Link>
                        </div>
                    )}
                </section>

                {/* Próximas oportunidades */}
                <section className="p-5">
                    <div className="flex items-baseline justify-between mb-3">
                        <div>
                            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase flex items-center gap-1.5">
                                <Clock className="size-3" /> Próximas oportunidades
                            </div>
                            <div className="text-[10px] text-muted-foreground/70 mt-0.5">
                                Janela de análise: minuto 50+
                            </div>
                        </div>
                    </div>
                    {nextGames.length === 0 ? (
                        <div className="py-8 text-center text-xs text-muted-foreground">
                            Sem jogos agendados nas próximas horas.
                        </div>
                    ) : (
                        <ul className="space-y-2">
                            {nextGames.map((g) => (
                                <UpcomingRow key={g.id} game={g} />
                            ))}
                        </ul>
                    )}
                </section>
            </div>

            {/* Admin: bloco técnico colapsável */}
            {isAdmin && (
                <div className="border-t border-border bg-background/40">
                    <button
                        onClick={() => setAdminOpen((v) => !v)}
                        className="w-full flex items-center justify-between px-5 py-2.5 text-[10px] font-mono tracking-wider text-muted-foreground hover:text-foreground transition"
                    >
                        <span className="flex items-center gap-1.5">
                            <Cpu className="size-3" /> DEV: FUNIL DO CICLO · ECONOMIA
                        </span>
                        {adminOpen ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                    </button>
                    {adminOpen && audit?.funil && (
                        <div className="px-5 py-4 border-t border-border grid lg:grid-cols-2 gap-5">
                            <FunnelAdmin funil={audit.funil} />
                            {polling && <EconomiaAdmin polling={polling} />}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── Sub-components ────────────────────────────────────────────

function HotGameRow({ game }: { game: AuditGameDetail }) {
    const motivo = friendlyMotivo(game.motivo);
    const projectedDelta =
        game.projecao != null && game.linha != null ? game.projecao - game.linha : null;
    const positive = (game.edge ?? 0) > 0;
    return (
        <li className="rounded-xl border border-border bg-background/40 p-3">
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <div className="font-medium text-sm truncate">{game.descricao}</div>
                    <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mt-0.5">
                        {game.liga} · min {game.minuto} · {game.placar}
                    </div>
                </div>
                <div className="text-right shrink-0">
                    <div
                        className={cn(
                            "font-mono tabular text-sm font-semibold",
                            positive ? "text-mint-bright" : "text-muted-foreground",
                        )}
                    >
                        {game.edge != null ? (game.edge >= 0 ? "+" : "") + game.edge.toFixed(2) : "—"}
                    </div>
                    <div className="font-mono text-[9px] text-muted-foreground tracking-wider">
                        EDGE
                    </div>
                </div>
            </div>
            <div className="flex items-center gap-3 mt-2 text-xs">
                <span className="font-mono text-muted-foreground tabular">
                    <Activity className="inline size-3 mr-1 text-mint" />
                    {game.pressure_score ?? "—"}
                </span>
                {projectedDelta != null && (
                    <span className="font-mono text-muted-foreground tabular">
                        Linha {game.linha?.toFixed(1)} · Proj{" "}
                        <span className={cn(projectedDelta > 0 ? "text-mint-bright" : "text-muted-foreground")}>
                            {projectedDelta >= 0 ? "+" : ""}
                            {projectedDelta.toFixed(1)}
                        </span>
                    </span>
                )}
                {motivo && (
                    <span className="ml-auto font-mono text-[10px] text-warning truncate max-w-[140px]">
                        {motivo}
                    </span>
                )}
            </div>
        </li>
    );
}

function TierRow({ t, highlight }: { t: TierPerformance; highlight: boolean }) {
    const meta = TIER_BY_ID[t.tier as StrategyTier] ?? STRATEGY_TIERS[1];
    const positive = t.roi_pct >= 0;
    return (
        <div
            className={cn(
                "flex items-center justify-between rounded-lg border p-2.5",
                highlight ? "border-mint/60 bg-mint/5" : "border-border bg-background/40",
            )}
        >
            <div className="min-w-0 flex items-center gap-2">
                {highlight && <Trophy className="size-3.5 text-mint-bright" />}
                <div>
                    <div className={cn("font-medium text-sm", highlight && "text-mint-bright")}>
                        {meta.label}
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                        {t.n} apostas · {t.greens}G/{t.reds}R
                    </div>
                </div>
            </div>
            <div className="text-right">
                <div
                    className={cn(
                        "font-mono tabular text-sm font-bold",
                        positive ? "text-mint-bright" : "text-destructive",
                    )}
                >
                    {positive ? "+" : ""}
                    {t.roi_pct.toFixed(1)}%
                </div>
                <div className="font-mono text-[10px] text-muted-foreground">
                    {(t.hit_rate * 100).toFixed(0)}% wr
                </div>
            </div>
        </div>
    );
}

function UpcomingRow({ game }: { game: UpcomingGame }) {
    return (
        <li className="rounded-xl border border-border bg-background/40 p-3">
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <div className="font-medium text-sm truncate">
                        {game.home} × {game.away}
                    </div>
                    <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mt-0.5 truncate">
                        {game.liga}
                    </div>
                </div>
                <div className="text-right shrink-0">
                    <div className="font-mono text-sm font-semibold text-mint-bright tabular">
                        {game.hora_inicio}
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground tracking-wider">
                        {countdownLabel(game.minutos_ate)}
                    </div>
                </div>
            </div>
        </li>
    );
}

function FunnelAdmin({ funil }: { funil: NonNullable<AuditData["funil"]> }) {
    const total = funil.total_analisados;
    const pct = (n: number) => (total > 0 ? Math.round((n / total) * 100) : 0);
    const rows = [
        { label: "Analisados", value: total, pct: 100 },
        { label: "Passou filtros", value: funil.passou_filtros, pct: pct(funil.passou_filtros) },
        { label: "Score OK", value: funil.score_ok, pct: pct(funil.score_ok) },
        { label: "Edge OK", value: funil.edge_ok, pct: pct(funil.edge_ok) },
        { label: "Emitidos", value: funil.sinais_emitidos, pct: pct(funil.sinais_emitidos) },
    ];
    return (
        <div>
            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mb-2">
                Funil do ciclo
            </div>
            <div className="space-y-1.5">
                {rows.map((r) => (
                    <div key={r.label}>
                        <div className="flex items-center justify-between text-xs mb-0.5">
                            <span className="text-muted-foreground">{r.label}</span>
                            <span className="font-mono tabular text-foreground">
                                {r.value} · {r.pct}%
                            </span>
                        </div>
                        <div className="h-1 rounded-full bg-muted overflow-hidden">
                            <div
                                className="h-full rounded-full bg-mint/60"
                                style={{ width: `${r.pct}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function EconomiaAdmin({ polling }: { polling: PollingStatsResponse }) {
    return (
        <div>
            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mb-2">
                Engine economia
            </div>
            <div className="flex items-baseline gap-2 mb-2">
                <span className="font-mono font-bold text-2xl text-mint-bright tabular">
                    {polling.economia_pct.toFixed(0)}%
                </span>
                <span className="font-mono text-[10px] text-muted-foreground tracking-wider">
                    ECONOMIZADO
                </span>
            </div>
            <div className="h-1 rounded-full bg-muted overflow-hidden mb-3">
                <div
                    className="h-full rounded-full bg-mint"
                    style={{ width: `${Math.min(100, polling.economia_pct)}%` }}
                />
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded border border-border bg-background/40 px-2 py-1.5">
                    <div className="font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
                        Monitorados
                    </div>
                    <div className="font-mono tabular font-semibold">{polling.jogos_monitorados}</div>
                </div>
                <div className="rounded border border-border bg-background/40 px-2 py-1.5">
                    <div className="font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
                        Analisando
                    </div>
                    <div className="font-mono tabular font-semibold">{polling.jogos_analisando}</div>
                </div>
            </div>
        </div>
    );
}
