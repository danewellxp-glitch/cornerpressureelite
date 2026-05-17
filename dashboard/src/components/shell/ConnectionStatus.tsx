"use client";

import { useEffect, useState } from "react";
import { Wifi, WifiOff, RefreshCw, RotateCw } from "lucide-react";
import { cn } from "@/lib/format";
import type { ConnectionStatus as ConnState } from "@/lib/useDashboardStream";

export function ConnectionStatus({
    status = "connected",
    lastUpdate,
    onReconnect,
}: {
    status?: ConnState;
    lastUpdate?: Date | null;
    onReconnect?: () => void;
}) {
    const [, force] = useState(0);
    useEffect(() => {
        const i = setInterval(() => force((t) => t + 1), 5_000);
        return () => clearInterval(i);
    }, []);

    const ago = lastUpdate ? Math.floor((Date.now() - lastUpdate.getTime()) / 1000) : null;

    const conf =
        status === "connected"
            ? { icon: Wifi, text: "Live", dot: "bg-success", ring: "shadow-[0_0_0_3px_oklch(0.78_0.18_155/0.18)]" }
            : status === "connecting" || status === "reconnecting"
                ? { icon: RefreshCw, text: status === "reconnecting" ? "Reconectando" : "Conectando", dot: "bg-warning animate-pulse", ring: "" }
                : { icon: WifiOff, text: "Offline", dot: "bg-destructive", ring: "" };

    const Icon = conf.icon;
    return (
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-2.5 py-1 text-xs">
            <span className={cn("relative size-1.5 rounded-full", conf.dot, conf.ring)} />
            <Icon className="size-3 text-muted-foreground" />
            <span className="font-mono text-[10px] tracking-wider text-muted-foreground">
                {conf.text}{ago != null ? ` · ${ago}s` : ""}
            </span>
            {status !== "connected" && onReconnect && (
                <button
                    onClick={onReconnect}
                    className="ml-1 text-mint hover:text-mint-bright"
                    title="Reconectar"
                >
                    <RotateCw className="size-3" />
                </button>
            )}
        </div>
    );
}
