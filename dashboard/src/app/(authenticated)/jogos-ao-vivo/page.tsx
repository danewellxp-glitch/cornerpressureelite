"use client";

import { useState } from "react";
import {
    Radio,
    AlertOctagon,
    ChevronDown,
    RefreshCw,
    Flag,
    Square,
    WifiOff,
    Clock,
} from "lucide-react";
import { useDashboard } from "@/components/shell/Shell";
import type { LiveGame } from "@/lib/api";
import { cn, fmtTime } from "@/lib/format";

/* ──────────────────────────────────────────────────────────────────
 *  /jogos-ao-vivo — Live monitoring terminal
 *  Aesthetic: trading floor x scoreboard. Mono labels, sharp borders,
 *  zero rounded shells. 3 lanes (FOCUS / WATCH / DONE) com hierarquia
 *  visual decrescente. Estados completos: boot / empty / offline / live.
 * ────────────────────────────────────────────────────────────────── */

type Status = "connecting" | "connected" | "reconnecting" | "offline";

export default function JogosAoVivoPage() {
    const { data, status, lastUpdate, reconnect } = useDashboard();

    if (status === "offline") return <DeadStream reason="offline" onReconnect={reconnect} />;
    if (!data) {
        if (status === "reconnecting") return <DeadStream reason="reconnecting" onReconnect={reconnect} />;
        return <Booting status={status} />;
    }

    const live = data.live_games ?? {
        na_janela: [],
        pre_janela: [],
        pos_janela: [],
        proximo_jogo_min: null,
    };
    const naJanela = live.na_janela ?? [];
    const preJanela = live.pre_janela ?? [];
    const posJanela = live.pos_janela ?? [];
    const total = naJanela.length + preJanela.length + posJanela.length;

    return (
        <div className="-mx-6 -mt-6">
            <TerminalBar
                status={status}
                lastUpdate={lastUpdate}
                focusCount={naJanela.length}
                watchCount={preJanela.length}
                doneCount={posJanela.length}
            />
            <div className="px-6 py-8 space-y-12 max-w-[1480px] mx-auto">
                {total === 0 ? (
                    <SilentNight proximoJogoMin={live.proximo_jogo_min ?? undefined} />
                ) : (
                    <>
                        {naJanela.length > 0 && (
                            <Lane
                                index="01"
                                code="FOCUS"
                                title="Em analise"
                                desc="Janela ativa — pressure score recalculando a cada 60s. Sinais podem disparar aqui."
                                accent="mint"
                                count={naJanela.length}
                            >
                                <div className="space-y-2">
                                    {naJanela.map((g, i) => (
                                        <FocusRow key={g.id} game={g} index={i} />
                                    ))}
                                </div>
                            </Lane>
                        )}

                        {preJanela.length > 0 && (
                            <Lane
                                index="02"
                                code="WATCH"
                                title="Aguardando"
                                desc="Antes do minuto 50 — polling reduzido, fora da janela de decisao."
                                accent="warning"
                                count={preJanela.length}
                            >
                                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                                    {preJanela.map((g, i) => (
                                        <CompactRow key={g.id} game={g} index={i} />
                                    ))}
                                </div>
                            </Lane>
                        )}

                        {posJanela.length > 0 && (
                            <CollapsibleLane
                                index="03"
                                code="DONE"
                                title="Encerrado"
                                desc="Pos-janela — aguardando resultado final do FT pra marcar GREEN/RED."
                                games={posJanela}
                            />
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  Terminal bar — banner full-bleed no topo
 * ════════════════════════════════════════════════════════════════ */

function TerminalBar({
    status,
    lastUpdate,
    focusCount,
    watchCount,
    doneCount,
}: {
    status: Status;
    lastUpdate: Date | null;
    focusCount: number;
    watchCount: number;
    doneCount: number;
}) {
    const total = focusCount + watchCount + doneCount;
    return (
        <header className="border-b border-border bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/70">
            <div className="max-w-[1480px] mx-auto px-6 py-3 flex items-center gap-x-5 gap-y-2 flex-wrap font-mono text-[10px] tracking-[0.18em] uppercase">
                <div className="flex items-center gap-2">
                    <span
                        className={cn(
                            "size-2 rounded-full",
                            status === "connected" &&
                                "bg-mint shadow-[0_0_10px_oklch(0.62_0.22_255)] animate-pulse",
                            status === "connecting" && "bg-warning animate-pulse",
                            status === "reconnecting" && "bg-warning animate-pulse",
                            status === "offline" && "bg-destructive",
                        )}
                    />
                    <span className="text-foreground">stream / {status}</span>
                </div>

                <span className="text-border" aria-hidden>
                    ─
                </span>

                <div className="flex items-center gap-4 tabular">
                    <Counter label="focus" value={focusCount} accent="mint" />
                    <Counter label="watch" value={watchCount} accent="warning" />
                    <Counter label="done" value={doneCount} accent="muted" />
                    <span className="text-border" aria-hidden>
                        →
                    </span>
                    <Counter label="total" value={total} accent="foreground" />
                </div>

                <span className="text-border" aria-hidden>
                    ─
                </span>

                <div className="text-muted-foreground tabular">
                    {lastUpdate ? `synced ${fmtTime(lastUpdate.toISOString())}` : "awaiting first frame"}
                </div>

                <div className="ml-auto flex items-center gap-2 text-muted-foreground">
                    <Radio className="size-3" aria-hidden />
                    <span>jogos ao vivo / v2</span>
                </div>
            </div>
        </header>
    );
}

function Counter({
    label,
    value,
    accent,
}: {
    label: string;
    value: number;
    accent: "mint" | "warning" | "muted" | "foreground";
}) {
    return (
        <span className="tabular">
            <span className="text-muted-foreground">{label}:</span>{" "}
            <span
                className={cn(
                    "font-semibold",
                    accent === "mint" && "text-mint",
                    accent === "warning" && "text-warning",
                    accent === "muted" && "text-muted-foreground",
                    accent === "foreground" && "text-foreground",
                )}
            >
                {String(value).padStart(2, "0")}
            </span>
        </span>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  Lane — header de secao com left-rail acentuado
 * ════════════════════════════════════════════════════════════════ */

function Lane({
    index,
    code,
    title,
    desc,
    accent,
    count,
    children,
}: {
    index: string;
    code: string;
    title: string;
    desc: string;
    accent: "mint" | "warning";
    count: number;
    children: React.ReactNode;
}) {
    return (
        <section className="relative pl-5">
            <span
                className={cn(
                    "absolute left-0 top-1 bottom-1 w-[3px]",
                    accent === "mint" && "bg-mint shadow-[0_0_10px_oklch(0.62_0.22_255_/_0.6)]",
                    accent === "warning" && "bg-warning",
                )}
                aria-hidden
            />
            <header className="mb-5 flex items-end justify-between flex-wrap gap-3">
                <div>
                    <div
                        className={cn(
                            "font-mono text-[10px] tracking-[0.24em] uppercase mb-1.5 flex items-center gap-2",
                            accent === "mint" && "text-mint",
                            accent === "warning" && "text-warning",
                        )}
                    >
                        <span className="text-muted-foreground">{index}</span>
                        <span className="text-border" aria-hidden>
                            /
                        </span>
                        {code}
                        <span className="text-border" aria-hidden>
                            ·
                        </span>
                        <span className="tabular">{String(count).padStart(2, "0")}</span>
                    </div>
                    <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight leading-none">
                        {title}
                    </h2>
                    <p className="text-xs text-muted-foreground mt-2 max-w-lg font-mono">{desc}</p>
                </div>
            </header>
            {children}
        </section>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  FocusRow — partida em analise ativa (linha cheia, big numbers)
 * ════════════════════════════════════════════════════════════════ */

function FocusRow({ game, index }: { game: LiveGame; index: number }) {
    const minuto = Math.max(0, game.minuto ?? 0);
    const minutoCapped = Math.min(minuto, 90);
    const minutoPct = (minutoCapped / 90) * 100;
    const inJanela = minuto >= 50 && minuto <= 90;

    return (
        <article
            className="piq-in relative border border-border bg-card/80 hover:border-mint/50 hover:bg-card transition-colors"
            style={{ animationDelay: `${index * 40}ms` }}
        >
            {/* progress bar top */}
            <div className="absolute top-0 inset-x-0 h-[2px] bg-border/40 overflow-hidden">
                <div
                    className={cn(
                        "h-full transition-[width] duration-700 ease-out",
                        inJanela ? "bg-mint shadow-[0_0_8px_oklch(0.62_0.22_255)]" : "bg-warning",
                    )}
                    style={{ width: `${minutoPct}%` }}
                />
            </div>

            <div className="grid grid-cols-12 items-center gap-3 sm:gap-5 px-4 sm:px-5 py-4 sm:py-5">
                {/* minute + live tag */}
                <div className="col-span-4 sm:col-span-2">
                    <div className="flex items-center gap-1.5">
                        <span className="size-1.5 rounded-full bg-mint animate-pulse shadow-[0_0_6px_oklch(0.62_0.22_255)]" />
                        <span className="font-mono text-[9px] tracking-[0.22em] uppercase text-mint">
                            live
                        </span>
                    </div>
                    <div className="font-mono text-3xl sm:text-[2.5rem] font-bold tabular leading-none mt-1.5">
                        {minuto}
                        <span className="text-xs text-muted-foreground align-top ml-0.5">'</span>
                    </div>
                </div>

                {/* teams + score */}
                <div className="col-span-8 sm:col-span-7">
                    <div className="font-mono text-[9px] tracking-[0.22em] uppercase text-muted-foreground truncate mb-2">
                        {game.liga}
                    </div>
                    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-4">
                        <div className="font-display text-sm sm:text-lg font-semibold leading-tight truncate text-right">
                            {game.home}
                        </div>
                        <div className="font-display text-2xl sm:text-[1.75rem] font-bold tabular text-mint-bright text-center px-2 sm:px-4 border-x border-mint/25">
                            {game.placar}
                        </div>
                        <div className="font-display text-sm sm:text-lg font-semibold leading-tight truncate">
                            {game.away}
                        </div>
                    </div>
                </div>

                {/* stats */}
                <div className="col-span-12 sm:col-span-3 flex items-end justify-around sm:justify-end gap-5 sm:gap-6 sm:border-l sm:border-border sm:pl-5 pt-2 sm:pt-0 border-t sm:border-t-0 border-border/40 mt-1 sm:mt-0">
                    <StatBlock
                        icon={<Flag className="size-3" aria-hidden />}
                        label="esc"
                        value={game.escanteios ?? 0}
                        accent="mint"
                    />
                    <StatBlock
                        icon={<Square className="size-3" aria-hidden />}
                        label="crd"
                        value={game.cartoes ?? 0}
                        accent="warning"
                    />
                </div>
            </div>
        </article>
    );
}

function StatBlock({
    icon,
    label,
    value,
    accent,
}: {
    icon: React.ReactNode;
    label: string;
    value: number;
    accent: "mint" | "warning";
}) {
    return (
        <div className="flex flex-col items-center gap-1">
            <div
                className={cn(
                    "font-mono text-[9px] tracking-[0.22em] uppercase inline-flex items-center gap-1",
                    accent === "mint" && "text-mint",
                    accent === "warning" && "text-warning",
                )}
            >
                {icon} {label}
            </div>
            <div className="font-mono text-xl sm:text-2xl font-bold tabular leading-none">
                {String(value).padStart(2, "0")}
            </div>
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  CompactRow — pre_janela (grid 2-3 colunas, denso)
 * ════════════════════════════════════════════════════════════════ */

function CompactRow({ game, index }: { game: LiveGame; index: number }) {
    return (
        <article
            className="piq-in border border-border/60 bg-card/40 hover:bg-card/80 hover:border-warning/40 transition-colors p-4"
            style={{ animationDelay: `${index * 25}ms` }}
        >
            <div className="flex items-center justify-between mb-2 font-mono text-[9px] tracking-[0.2em] uppercase">
                <span className="inline-flex items-center gap-1.5 text-warning">
                    <span className="size-1 rounded-full bg-warning" />
                    wait
                </span>
                <span className="tabular text-muted-foreground">{game.minuto}'</span>
            </div>
            <div className="font-mono text-[9px] tracking-[0.2em] uppercase text-muted-foreground truncate mb-2">
                {game.liga}
            </div>

            <div className="space-y-1">
                <div className="text-sm font-medium leading-tight truncate">{game.home}</div>
                <div className="font-display text-xl font-bold tabular leading-none">
                    {game.placar}
                </div>
                <div className="text-sm font-medium leading-tight truncate">{game.away}</div>
            </div>

            <div className="flex items-center gap-4 mt-3 pt-3 border-t border-border/50 font-mono text-[10px] tabular text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                    <Flag className="size-3" aria-hidden />
                    {game.escanteios ?? 0}
                </span>
                <span className="inline-flex items-center gap-1">
                    <Square className="size-3" aria-hidden />
                    {game.cartoes ?? 0}
                </span>
            </div>
        </article>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  CollapsibleLane — pos_janela (colapsavel)
 * ════════════════════════════════════════════════════════════════ */

function CollapsibleLane({
    index,
    code,
    title,
    desc,
    games,
}: {
    index: string;
    code: string;
    title: string;
    desc: string;
    games: LiveGame[];
}) {
    const [open, setOpen] = useState(games.length <= 3);
    return (
        <section className="relative pl-5">
            <span
                className="absolute left-0 top-1 bottom-1 w-[3px] bg-border"
                aria-hidden
            />
            <button
                type="button"
                onClick={() => setOpen((o) => !o)}
                aria-expanded={open}
                className="w-full text-left mb-5 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
                <div className="font-mono text-[10px] tracking-[0.24em] uppercase mb-1.5 flex items-center gap-2 text-muted-foreground">
                    <span>{index}</span>
                    <span className="text-border" aria-hidden>
                        /
                    </span>
                    {code}
                    <span className="text-border" aria-hidden>
                        ·
                    </span>
                    <span className="tabular">{String(games.length).padStart(2, "0")}</span>
                </div>
                <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight leading-none text-muted-foreground group-hover:text-foreground transition-colors flex items-center gap-2">
                    {title}
                    <ChevronDown
                        className={cn(
                            "size-5 transition-transform duration-200",
                            open && "rotate-180",
                        )}
                        aria-hidden
                    />
                </h2>
                <p className="text-xs text-muted-foreground mt-2 max-w-lg font-mono">{desc}</p>
            </button>

            {open && (
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {games.map((g, i) => (
                        <FinishedRow key={g.id} game={g} index={i} />
                    ))}
                </div>
            )}
        </section>
    );
}

function FinishedRow({ game, index }: { game: LiveGame; index: number }) {
    return (
        <article
            className="piq-in border border-border/40 bg-card/20 px-4 py-3"
            style={{ animationDelay: `${index * 18}ms` }}
        >
            <div className="flex items-center justify-between mb-2 font-mono text-[9px] tracking-[0.2em] uppercase">
                <span className="text-muted-foreground">fim · {game.minuto}'</span>
                <span className="tabular text-muted-foreground inline-flex items-center gap-1.5">
                    <Flag className="size-3" aria-hidden /> {game.escanteios ?? 0}
                    <span className="text-border mx-1" aria-hidden>
                        ·
                    </span>
                    <Square className="size-3" aria-hidden /> {game.cartoes ?? 0}
                </span>
            </div>
            <div className="font-mono text-[9px] tracking-[0.2em] uppercase text-muted-foreground/80 truncate mb-1.5">
                {game.liga}
            </div>
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                <div className="text-sm font-medium truncate text-right text-muted-foreground">
                    {game.home}
                </div>
                <div className="font-display text-lg font-bold tabular text-foreground/80 text-center px-2">
                    {game.placar}
                </div>
                <div className="text-sm font-medium truncate text-muted-foreground">
                    {game.away}
                </div>
            </div>
        </article>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  Empty state — "Silent Night"
 * ════════════════════════════════════════════════════════════════ */

function SilentNight({ proximoJogoMin }: { proximoJogoMin?: number }) {
    return (
        <div className="relative border border-border bg-card/40 px-6 py-16 sm:py-24 text-center overflow-hidden grid-bg">
            <div
                className="absolute inset-x-0 top-1/2 h-px bg-gradient-to-r from-transparent via-mint/50 to-transparent"
                aria-hidden
            />

            <div className="relative inline-flex flex-col items-center gap-5 max-w-xl">
                <div className="font-mono text-[10px] tracking-[0.3em] uppercase text-mint flex items-center gap-2">
                    <span aria-hidden>▾</span>
                    stream silent
                    <span aria-hidden>▾</span>
                </div>

                <h3 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
                    Nenhuma partida ao vivo agora.
                </h3>

                <p className="text-sm text-muted-foreground font-mono max-w-md leading-relaxed">
                    Motor em modo sentinela. Assim que uma partida das ligas monitoradas comecar, ela aparece aqui automaticamente — sem refresh.
                </p>

                {proximoJogoMin != null && proximoJogoMin > 0 && (
                    <div className="inline-flex items-center gap-2 mt-2 px-4 py-2 border border-mint/40">
                        <Clock className="size-3.5 text-mint" aria-hidden />
                        <span className="font-mono text-[11px] tracking-[0.2em] uppercase text-mint tabular">
                            proximo kickoff em {proximoJogoMin}m
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  Booting state — primeira conexao
 * ════════════════════════════════════════════════════════════════ */

function Booting({ status }: { status: Status }) {
    const phaseLabel: Record<Status, string> = {
        connecting: "estabelecendo stream",
        connected: "aguardando primeiro frame",
        reconnecting: "reconectando",
        offline: "stream offline",
    };
    return (
        <div className="px-6 py-24 max-w-md mx-auto text-center">
            <div className="inline-flex flex-col items-center gap-5">
                <div className="relative size-16 grid place-items-center">
                    <span
                        className="absolute inset-0 rounded-full border border-mint/30 animate-ping"
                        aria-hidden
                    />
                    <span
                        className="absolute inset-2 rounded-full border border-mint/20"
                        aria-hidden
                    />
                    <Radio className="size-5 text-mint relative animate-pulse" aria-hidden />
                </div>
                <div className="font-mono text-[10px] tracking-[0.26em] uppercase text-mint">
                    {phaseLabel[status]}
                </div>
                <p className="text-xs text-muted-foreground font-mono max-w-xs leading-relaxed">
                    SSE handshake em curso. A primeira leitura inclui o snapshot completo das partidas ao vivo do momento.
                </p>
            </div>
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  Dead stream — offline ou reconnecting sem dados
 * ════════════════════════════════════════════════════════════════ */

function DeadStream({
    reason,
    onReconnect,
}: {
    reason: "offline" | "reconnecting";
    onReconnect: () => void;
}) {
    return (
        <div className="-mx-6 -mt-6">
            <div className="border-b border-destructive/50 bg-destructive/10">
                <div className="max-w-[1480px] mx-auto px-6 py-3 flex items-center gap-3 font-mono text-[10px] tracking-[0.2em] uppercase">
                    <AlertOctagon className="size-4 text-destructive" aria-hidden />
                    <span className="text-destructive">
                        stream / {reason === "offline" ? "disconnected" : "reconnecting"}
                    </span>
                    <button
                        type="button"
                        onClick={onReconnect}
                        className="ml-auto inline-flex items-center gap-1.5 text-destructive hover:text-foreground transition-colors px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    >
                        <RefreshCw className="size-3" aria-hidden />
                        retry now
                    </button>
                </div>
            </div>

            <div className="px-6 py-24 max-w-md mx-auto text-center">
                <div className="inline-flex flex-col items-center gap-5">
                    <WifiOff className="size-10 text-destructive" aria-hidden />
                    <h2 className="font-display text-2xl sm:text-3xl font-bold leading-tight tracking-tight">
                        {reason === "offline" ? "Stream caiu." : "Sem sinal ha alguns segundos."}
                    </h2>
                    <p className="text-sm text-muted-foreground max-w-sm font-mono leading-relaxed">
                        {reason === "offline"
                            ? "Possivel: aba em background > 5min, JWT expirou, ou a API do CPES esta fora. Reconecte ou recarregue a pagina."
                            : "Tentando re-handshake automaticamente. Backoff exponencial ate 30s. Se persistir, force o retry."}
                    </p>
                    <button
                        type="button"
                        onClick={onReconnect}
                        className="inline-flex items-center gap-2 px-5 py-2.5 border border-mint text-mint font-mono text-xs tracking-[0.2em] uppercase hover:bg-mint hover:text-background transition-colors mt-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    >
                        <RefreshCw className="size-3.5" aria-hidden />
                        reconectar agora
                    </button>
                </div>
            </div>
        </div>
    );
}
