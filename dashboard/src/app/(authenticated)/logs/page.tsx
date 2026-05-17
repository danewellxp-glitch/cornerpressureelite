"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
    Terminal,
    RefreshCw,
    ArrowDownToLine,
    Pause,
    Play,
    Search,
    Loader2,
} from "lucide-react";
import { useDashboard } from "@/components/shell/Shell";
import { cn } from "@/lib/format";

type Level = "ALL" | "INFO" | "CYCLE" | "SIGNAL" | "PREMIUM" | "GREEN" | "WARNING" | "ERROR";
const LEVELS: Level[] = ["ALL", "CYCLE", "SIGNAL", "PREMIUM", "GREEN", "WARNING", "ERROR"];

function tokenize(line: string): { ts: string; level: Level; body: string } {
    const m = line.match(/^\[(\d{2}:\d{2}:\d{2})\]\s+(\w+)\s+(.*)$/);
    if (!m) return { ts: "", level: "INFO", body: line };
    return { ts: m[1], level: m[2] as Level, body: m[3] };
}

function levelClass(level: Level): string {
    switch (level) {
        case "ERROR":
            return "text-destructive";
        case "WARNING":
            return "text-warning";
        case "GREEN":
            return "text-success";
        case "PREMIUM":
            return "text-mint-bright";
        case "SIGNAL":
            return "text-mint";
        case "CYCLE":
            return "text-foreground/70";
        default:
            return "text-muted-foreground";
    }
}

export default function LogsPage() {
    const { data, reconnect } = useDashboard();
    const [autoScroll, setAutoScroll] = useState(true);
    const [level, setLevel] = useState<Level>("ALL");
    const [q, setQ] = useState("");
    const containerRef = useRef<HTMLDivElement>(null);

    const logs = data?.logs ?? [];

    const filtered = useMemo(() => {
        return logs
            .map((raw, i) => ({ raw, i, ...tokenize(raw) }))
            .filter((x) => {
                if (level !== "ALL" && x.level !== level) return false;
                if (q && !x.body.toLowerCase().includes(q.toLowerCase())) return false;
                return true;
            });
    }, [logs, level, q]);

    useEffect(() => {
        if (autoScroll && containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [filtered.length, autoScroll]);

    const counts = useMemo(() => {
        const c: Record<Level, number> = {
            ALL: logs.length,
            INFO: 0,
            CYCLE: 0,
            SIGNAL: 0,
            PREMIUM: 0,
            GREEN: 0,
            WARNING: 0,
            ERROR: 0,
        };
        for (const raw of logs) {
            const t = tokenize(raw);
            c[t.level] = (c[t.level] ?? 0) + 1;
        }
        return c;
    }, [logs]);

    return (
        <div className="space-y-4 max-w-[1600px] mx-auto h-[calc(100vh-7rem)] flex flex-col">
            <header className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="font-mono text-[10px] tracking-[0.22em] text-muted-foreground uppercase flex items-center gap-2">
                        <Terminal className="size-3" /> /var/log/pressureiq
                    </div>
                    <h1 className="font-display text-3xl font-bold mt-1 text-gradient-mint">
                        Logs do robô
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-xl">
                        Stream em tempo real do ciclo de análise — emissão de sinais, cache, polling e erros.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] tracking-wider text-muted-foreground tabular">
                        {filtered.length.toLocaleString("pt-BR")} / {logs.length.toLocaleString("pt-BR")} linhas
                    </span>
                    <button
                        onClick={reconnect}
                        className="size-8 grid place-items-center rounded-lg border border-border bg-card hover:border-mint/50 text-muted-foreground hover:text-mint-bright transition"
                        title="Reconectar stream"
                    >
                        <RefreshCw className="size-3.5" />
                    </button>
                    <button
                        onClick={() => setAutoScroll((s) => !s)}
                        className={cn(
                            "h-8 px-2.5 inline-flex items-center gap-1.5 rounded-lg border text-[11px] font-mono tracking-wider transition",
                            autoScroll
                                ? "border-mint/50 bg-mint/10 text-mint-bright glow-mint"
                                : "border-border bg-card text-muted-foreground hover:text-foreground",
                        )}
                        title={autoScroll ? "Pausar auto-scroll" : "Retomar auto-scroll"}
                    >
                        {autoScroll ? <Pause className="size-3" /> : <Play className="size-3" />}
                        {autoScroll ? "AUTOSCROLL" : "PAUSED"}
                    </button>
                    <button
                        onClick={() => {
                            if (containerRef.current)
                                containerRef.current.scrollTop = containerRef.current.scrollHeight;
                        }}
                        className="size-8 grid place-items-center rounded-lg border border-border bg-card hover:border-mint/50 text-muted-foreground hover:text-mint-bright transition"
                        title="Ir para o fim"
                    >
                        <ArrowDownToLine className="size-3.5" />
                    </button>
                </div>
            </header>

            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-1 flex-wrap">
                    {LEVELS.map((l) => {
                        const on = level === l;
                        return (
                            <button
                                key={l}
                                onClick={() => setLevel(l)}
                                className={cn(
                                    "px-2 py-1 text-[10px] font-mono tracking-wider rounded-md border transition inline-flex items-center gap-1.5",
                                    on
                                        ? "border-mint/50 bg-mint/10 text-mint-bright"
                                        : "border-border bg-card text-muted-foreground hover:text-foreground",
                                )}
                            >
                                <span className={cn("size-1.5 rounded-full", on ? "bg-mint-bright" : "bg-muted-foreground/40")} />
                                {l}
                                <span className="tabular text-foreground/40">{counts[l]}</span>
                            </button>
                        );
                    })}
                </div>
                <div className="relative">
                    <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder="grep…"
                        className="pl-7 pr-3 py-1.5 rounded-lg border border-border bg-background/60 text-xs w-56 focus:outline-none focus:border-mint/50 font-mono"
                    />
                </div>
            </div>

            <div className="flex-1 min-h-0 rounded-2xl border border-border bg-[oklch(0.13_0.02_232)] overflow-hidden grid-bg">
                <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background/40">
                    <div className="flex items-center gap-1.5">
                        <span className="size-2 rounded-full bg-destructive/60" />
                        <span className="size-2 rounded-full bg-warning/60" />
                        <span className="size-2 rounded-full bg-success/60" />
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground tracking-wider">
                        piq-engine — stream/dashboard
                    </span>
                    <span className="font-mono text-[10px] text-mint-bright tracking-wider flex items-center gap-1.5">
                        <span className="size-1.5 rounded-full bg-mint-bright animate-pulse" />
                        STREAMING
                    </span>
                </div>
                <div
                    ref={containerRef}
                    className="h-[calc(100%-2.25rem)] overflow-auto p-3 font-mono text-[12px] leading-[1.7]"
                >
                    {!data ? (
                        <div className="flex items-center justify-center h-full text-muted-foreground">
                            <Loader2 className="size-4 animate-spin mr-2" />
                            <span className="text-xs">Aguardando stream…</span>
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="text-muted-foreground text-xs p-4">
                            Nenhuma linha encontrada com os filtros atuais.
                        </div>
                    ) : (
                        filtered.map(({ raw, i, ts, level: lv, body }) => (
                            <div
                                key={i}
                                className="grid grid-cols-[3rem_4.5rem_5rem_1fr] gap-3 px-2 py-0.5 rounded hover:bg-mint/5 transition"
                            >
                                <span className="text-foreground/25 text-right select-none tabular">
                                    {String(i + 1).padStart(4, " ")}
                                </span>
                                <span className="text-foreground/50 tabular">{ts || ""}</span>
                                <span className={cn("font-semibold tracking-wider", levelClass(lv))}>
                                    {lv}
                                </span>
                                <span className={cn("break-all whitespace-pre-wrap", levelClass(lv))}>
                                    {body || raw}
                                </span>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
