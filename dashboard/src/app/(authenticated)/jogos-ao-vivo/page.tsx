"use client";

import { Radio, Loader2, Flag, Square } from "lucide-react";
import { useDashboard } from "@/components/shell/Shell";
import type { LiveGame } from "@/lib/api";
import { cn, fmtTime } from "@/lib/format";

const PHASE_LABEL = {
    pre_janela: { label: "AGUARDANDO", cls: "text-muted-foreground border-border bg-muted/40" },
    na_janela: { label: "NA JANELA", cls: "text-mint-bright border-mint-bright/40 bg-mint-bright/10" },
    pos_janela: { label: "FIM", cls: "text-muted-foreground border-border bg-muted/40" },
} as const;

export default function JogosAoVivoPage() {
    const { data, status, lastUpdate } = useDashboard();

    const live = data?.live_games;

    if (!live) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
                {status === "connected" ? (
                    <>
                        <Loader2 className="size-6 animate-spin" />
                        <span className="ml-2 font-mono text-xs tracking-wider">CARREGANDO…</span>
                    </>
                ) : (
                    <span className="font-mono text-xs tracking-wider">CONEXÃO {status.toUpperCase()}</span>
                )}
            </div>
        );
    }

    const naJanela = live.na_janela ?? [];
    const preJanela = live.pre_janela ?? [];
    const posJanela = live.pos_janela ?? [];
    const total = naJanela.length + preJanela.length + posJanela.length;

    return (
        <div className="space-y-6 max-w-[1400px] mx-auto">
            <header className="flex items-end justify-between flex-wrap gap-3">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                        Monitoramento em tempo real
                    </div>
                    <h1 className="font-display text-2xl font-bold mt-1">Jogos ao vivo</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Partidas que o sistema está observando agora. Atualização a cada 2s.
                    </p>
                </div>
                <div className="flex items-center gap-3 font-mono text-[10px] tracking-wider text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                        <span
                            className={cn(
                                "size-1.5 rounded-full",
                                status === "connected" ? "bg-success animate-pulse" : "bg-warning",
                            )}
                        />
                        {status.toUpperCase()}
                    </span>
                    {lastUpdate && <span>· {fmtTime(lastUpdate.toISOString())}</span>}
                </div>
            </header>

            {total === 0 && (
                <div className="rounded-2xl border border-border bg-card p-12 text-center">
                    <div className="mx-auto size-12 rounded-2xl border border-border bg-muted/40 grid place-items-center mb-4">
                        <Radio className="size-6 text-muted-foreground" />
                    </div>
                    <h3 className="font-display text-base font-semibold">Nenhum jogo ao vivo agora</h3>
                    <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
                        Quando partidas das ligas monitoradas começarem, elas aparecem aqui automaticamente.
                    </p>
                    {live.proximo_jogo_min != null && live.proximo_jogo_min > 0 && (
                        <p className="text-xs text-mint mt-3 font-mono tracking-wider">
                            PRÓXIMO JOGO EM {live.proximo_jogo_min} MIN
                        </p>
                    )}
                </div>
            )}

            {naJanela.length > 0 && (
                <GameSection
                    title="Na janela de análise"
                    desc="Sistema avaliando ativamente"
                    games={naJanela}
                    phaseKey="na_janela"
                />
            )}

            {preJanela.length > 0 && (
                <GameSection
                    title="Aguardando janela"
                    desc="Polling reduzido"
                    games={preJanela}
                    phaseKey="pre_janela"
                />
            )}

            {posJanela.length > 0 && (
                <GameSection
                    title="Pós-janela"
                    desc="Aguardando resultado"
                    games={posJanela}
                    phaseKey="pos_janela"
                />
            )}
        </div>
    );
}

function GameSection({
    title,
    desc,
    games,
    phaseKey,
}: {
    title: string;
    desc: string;
    games: LiveGame[];
    phaseKey: keyof typeof PHASE_LABEL;
}) {
    return (
        <section>
            <div className="flex items-baseline justify-between mb-3">
                <div>
                    <h2 className="font-display text-lg font-semibold">{title}</h2>
                    <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
                <span className="font-mono text-[10px] tracking-wider text-muted-foreground">
                    {games.length} {games.length === 1 ? "JOGO" : "JOGOS"}
                </span>
            </div>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {games.map((g) => (
                    <GameCard key={g.id} game={g} phaseKey={phaseKey} />
                ))}
            </div>
        </section>
    );
}

function GameCard({
    game,
    phaseKey,
}: {
    game: LiveGame;
    phaseKey: keyof typeof PHASE_LABEL;
}) {
    const phase = PHASE_LABEL[phaseKey];
    return (
        <div className="piq-in rounded-2xl border border-border bg-card p-4 hover:border-mint/40 transition">
            <div className="flex items-center justify-between mb-3">
                <span
                    className={cn(
                        "font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border",
                        phase.cls,
                    )}
                >
                    {phase.label}
                </span>
                <span className="font-mono text-xs text-muted-foreground tabular">
                    {game.minuto}'
                </span>
            </div>
            <div className="font-display text-sm font-semibold leading-tight">{game.home}</div>
            <div className="font-display text-2xl font-bold tabular text-mint-bright text-center my-2">
                {game.placar}
            </div>
            <div className="font-display text-sm font-semibold leading-tight">{game.away}</div>
            <div className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase mt-3 truncate">
                {game.liga}
            </div>
            <div className="flex items-center justify-around mt-3 pt-3 border-t border-border/40">
                <div className="text-center">
                    <Flag className="size-3.5 mx-auto text-muted-foreground" />
                    <div className="font-mono text-xs tabular mt-0.5">{game.escanteios ?? 0}</div>
                </div>
                <div className="text-center">
                    <Square className="size-3.5 mx-auto text-warning" />
                    <div className="font-mono text-xs tabular mt-0.5">{game.cartoes ?? 0}</div>
                </div>
            </div>
        </div>
    );
}
