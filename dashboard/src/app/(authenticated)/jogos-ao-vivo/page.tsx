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
                                <div className="space-y-3">
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
                                <div className="space-y-3">
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

type RowVariant = "live" | "watch" | "done";

const ROW_VARIANT: Record<
    RowVariant,
    {
        label: string;
        dot: string;
        tag: string;
        bar: string;
        accent: string;
        score: string;
        minute: string;
        hover: string;
    }
> = {
    live: {
        label: "ao vivo",
        dot: "bg-mint animate-pulse shadow-[0_0_8px_oklch(0.62_0.22_255)]",
        tag: "text-mint",
        bar: "from-mint/0 via-mint to-mint/0",
        accent: "from-mint via-mint to-mint/20",
        score: "text-mint-bright",
        minute: "text-foreground",
        hover: "hover:border-mint/45 hover:ring-mint/20",
    },
    watch: {
        label: "aguarda",
        dot: "bg-warning shadow-[0_0_6px_oklch(0.8_0.16_75)]",
        tag: "text-warning",
        bar: "from-warning/0 via-warning/70 to-warning/0",
        accent: "from-warning via-warning/80 to-warning/15",
        score: "text-foreground/90",
        minute: "text-muted-foreground",
        hover: "hover:border-warning/40 hover:ring-warning/15",
    },
    done: {
        label: "encerrado",
        dot: "bg-muted-foreground",
        tag: "text-muted-foreground",
        bar: "from-transparent via-border to-transparent",
        accent: "from-border via-border to-transparent",
        score: "text-foreground/65",
        minute: "text-muted-foreground/60",
        hover: "hover:border-border hover:ring-white/10",
    },
};

function FocusRow({
    game,
    index,
    variant = "live",
}: {
    game: LiveGame;
    index: number;
    variant?: RowVariant;
}) {
    const minuto = Math.max(0, game.minuto ?? 0);
    const minutoPct = Math.min((minuto / 90) * 100, 100);
    const v = ROW_VARIANT[variant];

    return (
        <article
            className={cn(
                "piq-in group relative overflow-hidden rounded-xl border border-border/70",
                "bg-gradient-to-br from-card/95 via-card/70 to-card/45",
                "ring-1 ring-inset ring-white/[0.03]",
                "shadow-[inset_0_1px_0_oklch(1_0_0/0.05),0_12px_32px_-20px_oklch(0_0_0/0.8)]",
                "transition-all duration-300 hover:-translate-y-px",
                v.hover,
            )}
            style={{ animationDelay: `${index * 35}ms` }}
        >
            {/* left accent bar */}
            <span
                className={cn("absolute left-0 inset-y-0 w-[3px] bg-gradient-to-b", v.accent)}
                aria-hidden
            />
            {/* top progress */}
            {variant !== "done" && (
                <span className="absolute top-0 inset-x-0 h-px overflow-hidden" aria-hidden>
                    <span
                        className={cn("block h-full bg-gradient-to-r transition-[width] duration-700 ease-out", v.bar)}
                        style={{ width: `${minutoPct}%` }}
                    />
                </span>
            )}

            <div className="grid grid-cols-12 items-center gap-3 sm:gap-5 pl-5 pr-4 sm:pr-5 py-4">
                {/* status + minute */}
                <div className="col-span-4 sm:col-span-2">
                    <span
                        className={cn(
                            "inline-flex items-center gap-1.5 font-mono text-[9px] tracking-[0.22em] uppercase",
                            v.tag,
                        )}
                    >
                        <span className={cn("size-1.5 rounded-full", v.dot)} />
                        {v.label}
                    </span>
                    <div
                        className={cn(
                            "font-mono text-[2.1rem] sm:text-[2.6rem] font-bold tabular leading-none mt-1.5",
                            v.minute,
                        )}
                    >
                        {variant === "done" ? (
                            <span className="text-2xl sm:text-3xl">FT</span>
                        ) : (
                            <>
                                {minuto}
                                <span className="text-sm text-muted-foreground align-top ml-0.5">&apos;</span>
                            </>
                        )}
                    </div>
                </div>

                {/* league + teams + score */}
                <div className="col-span-8 sm:col-span-7 min-w-0">
                    <div className="font-mono text-[9px] tracking-[0.22em] uppercase text-muted-foreground/70 truncate mb-2.5">
                        {game.liga}
                    </div>
                    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-4">
                        <div className="font-display text-sm sm:text-lg font-semibold leading-tight truncate text-right">
                            {game.home}
                        </div>
                        <div
                            className={cn(
                                "font-mono text-xl sm:text-2xl font-bold tabular text-center rounded-lg px-3 sm:px-4 py-1",
                                "bg-background/50 border border-border/60 shadow-[inset_0_1px_2px_oklch(0_0_0/0.4)]",
                                v.score,
                            )}
                        >
                            {game.placar}
                        </div>
                        <div className="font-display text-sm sm:text-lg font-semibold leading-tight truncate">
                            {game.away}
                        </div>
                    </div>
                </div>

                {/* stats */}
                <div className="col-span-12 sm:col-span-3 flex items-center justify-around sm:justify-end gap-2.5 sm:gap-3 pt-3 sm:pt-0 mt-1 sm:mt-0 border-t sm:border-t-0 border-border/40">
                    <StatChip
                        icon={<Flag className="size-3" aria-hidden />}
                        label="esc"
                        value={game.escanteios ?? 0}
                        accent="mint"
                    />
                    <StatChip
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

function StatChip({
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
        <div className="flex flex-col items-center gap-1 rounded-lg border border-border/50 bg-background/30 px-3 py-1.5 min-w-[58px]">
            <span
                className={cn(
                    "font-mono text-[9px] tracking-[0.18em] uppercase inline-flex items-center gap-1",
                    accent === "mint" ? "text-mint" : "text-warning",
                )}
            >
                {icon} {label}
            </span>
            <span className="font-mono text-lg sm:text-xl font-bold tabular leading-none text-foreground">
                {String(value).padStart(2, "0")}
            </span>
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
 *  CompactRow — pre_janela (grid 2-3 colunas, denso)
 * ════════════════════════════════════════════════════════════════ */

function CompactRow({ game, index }: { game: LiveGame; index: number }) {
    return <FocusRow game={game} index={index} variant="watch" />;
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
                <div className="space-y-3">
                    {games.map((g, i) => (
                        <FinishedRow key={g.id} game={g} index={i} />
                    ))}
                </div>
            )}
        </section>
    );
}

function FinishedRow({ game, index }: { game: LiveGame; index: number }) {
    return <FocusRow game={game} index={index} variant="done" />;
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
