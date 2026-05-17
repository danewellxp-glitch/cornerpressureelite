"use client";

import { useEffect, useState } from "react";
import { Clock, Loader2 } from "lucide-react";
import { fetchUpcomingGames, type LiveGame, type UpcomingGame } from "@/lib/api";
import { cn } from "@/lib/format";

type LiveGamesState = {
    na_janela: LiveGame[];
    pre_janela: LiveGame[];
    pos_janela: LiveGame[];
} | undefined;

export function GamesPanel({ live_games }: { live_games: LiveGamesState }) {
    const [tab, setTab] = useState<"live" | "upcoming">("live");
    const [upcoming, setUpcoming] = useState<UpcomingGame[]>([]);
    const [upcomingLoading, setUpcomingLoading] = useState(false);
    const [upcomingLoaded, setUpcomingLoaded] = useState(false);

    useEffect(() => {
        if (tab !== "upcoming" || upcomingLoaded) return;
        setUpcomingLoading(true);
        fetchUpcomingGames()
            .then((res) => {
                setUpcoming(res.proximos || []);
                setUpcomingLoaded(true);
            })
            .catch(() => {
                setUpcoming([]);
            })
            .finally(() => setUpcomingLoading(false));
    }, [tab, upcomingLoaded]);

    const liveCount =
        (live_games?.na_janela.length ?? 0) +
        (live_games?.pre_janela.length ?? 0) +
        (live_games?.pos_janela.length ?? 0);

    return (
        <div className="lg:col-span-1 piq-in rounded-2xl border border-border bg-card overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-border">
                <div className="flex gap-1">
                    <button
                        onClick={() => setTab("live")}
                        className={cn(
                            "px-3 py-1.5 rounded-md text-xs font-mono tracking-wider transition flex items-center gap-1.5",
                            tab === "live"
                                ? "bg-mint/10 text-mint-bright border border-mint/30"
                                : "text-muted-foreground hover:text-foreground border border-transparent",
                        )}
                    >
                        <span className="size-1.5 rounded-full bg-success animate-pulse" />
                        LIVE
                        <span className="tabular text-foreground/60">{liveCount}</span>
                    </button>
                    <button
                        onClick={() => setTab("upcoming")}
                        className={cn(
                            "px-3 py-1.5 rounded-md text-xs font-mono tracking-wider transition flex items-center gap-1.5",
                            tab === "upcoming"
                                ? "bg-mint/10 text-mint-bright border border-mint/30"
                                : "text-muted-foreground hover:text-foreground border border-transparent",
                        )}
                    >
                        <Clock className="size-3" />
                        PRÓXIMOS
                        {upcomingLoaded && (
                            <span className="tabular text-foreground/60">{upcoming.length}</span>
                        )}
                    </button>
                </div>
                {tab === "live" && (
                    <div className="text-right">
                        <div className="font-mono text-xl text-mint-bright tabular">
                            {live_games?.na_janela.length ?? 0}
                        </div>
                        <div className="font-mono text-[9px] tracking-wider text-muted-foreground">
                            NA JANELA
                        </div>
                    </div>
                )}
            </div>
            <div className="divide-y divide-border max-h-[440px] overflow-auto">
                {tab === "live" ? (
                    <>
                        {live_games?.na_janela.map((g) => (
                            <LiveGameRow key={`na-${g.id}`} g={g} window="na" />
                        ))}
                        {live_games?.pre_janela.map((g) => (
                            <LiveGameRow key={`pre-${g.id}`} g={g} window="pre" />
                        ))}
                        {liveCount === 0 && (
                            <div className="p-6 text-center text-xs text-muted-foreground">
                                Nenhum jogo monitorado no momento.
                            </div>
                        )}
                    </>
                ) : upcomingLoading ? (
                    <div className="p-8 flex items-center justify-center text-muted-foreground">
                        <Loader2 className="size-4 animate-spin" />
                    </div>
                ) : upcoming.length === 0 ? (
                    <div className="p-6 text-center text-xs text-muted-foreground">
                        Nenhum jogo agendado.
                    </div>
                ) : (
                    upcoming.slice(0, 20).map((g) => <UpcomingRow key={g.id} g={g} />)
                )}
            </div>
        </div>
    );
}

function LiveGameRow({
    g,
    window,
}: {
    g: LiveGame;
    window: "na" | "pre" | "pos";
}) {
    const tone =
        window === "na"
            ? "border-l-success bg-success/5"
            : window === "pre"
                ? "border-l-mint/50"
                : "border-l-muted-foreground/30";
    return (
        <div className={cn("p-4 border-l-2 hover:bg-mint/5 transition", tone)}>
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">
                        {g.home} <span className="text-muted-foreground mx-1">vs</span> {g.away}
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">{g.liga}</div>
                </div>
                <span
                    className={cn(
                        "font-mono text-[10px] tracking-wider px-1.5 py-0.5 rounded border tabular",
                        window === "na"
                            ? "text-success border-success/40 bg-success/10"
                            : "text-muted-foreground border-border bg-muted/40",
                    )}
                >
                    {g.minuto}'
                </span>
            </div>
            <div className="flex items-center justify-between mt-2 font-mono text-xs">
                <span className="text-foreground tabular">{g.placar}</span>
                <span className="flex gap-3 text-muted-foreground">
                    {g.escanteios != null && <span>esc {g.escanteios}</span>}
                    {g.cartoes != null && <span>crt {g.cartoes}</span>}
                </span>
            </div>
        </div>
    );
}

function UpcomingRow({ g }: { g: UpcomingGame }) {
    const minutosAte = g.minutos_ate;
    const ago =
        minutosAte < 60
            ? `${minutosAte}min`
            : minutosAte < 1440
                ? `${Math.floor(minutosAte / 60)}h${minutosAte % 60 ? ` ${minutosAte % 60}min` : ""}`
                : `${Math.floor(minutosAte / 1440)}d`;
    const tone =
        minutosAte < 60
            ? "text-mint-bright border-mint/40 bg-mint/10"
            : minutosAte < 240
                ? "text-mint border-mint/30 bg-mint/5"
                : "text-muted-foreground border-border bg-muted/40";
    return (
        <div className="p-4 hover:bg-mint/5 transition">
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">
                        {g.home} <span className="text-muted-foreground mx-1">vs</span> {g.away}
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">{g.liga}</div>
                </div>
                <span className={cn("font-mono text-[10px] tracking-wider px-1.5 py-0.5 rounded border tabular", tone)}>
                    {ago}
                </span>
            </div>
            <div className="flex items-center justify-between mt-2 font-mono text-xs">
                <span className="text-muted-foreground tabular">{g.hora_inicio}</span>
                <span className="text-foreground/50 uppercase text-[10px] tracking-wider">{g.status}</span>
            </div>
        </div>
    );
}
