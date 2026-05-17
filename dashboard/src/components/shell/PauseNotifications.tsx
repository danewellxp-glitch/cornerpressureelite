"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/format";
import { fetchNotificationSettings, updateNotificationSettings } from "@/lib/api";

const PRESETS = [
    { label: "30 min", minutes: 30 },
    { label: "1 hora", minutes: 60 },
    { label: "4 horas", minutes: 240 },
    { label: "Hoje", minutes: 720 },
];

function WhatsAppIcon({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden
        >
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.821 11.821 0 0 0 20.464 3.488" />
        </svg>
    );
}

export function PauseNotifications() {
    const [pausedUntil, setPausedUntil] = useState<Date | null>(null);
    const [open, setOpen] = useState(false);

    useEffect(() => {
        fetchNotificationSettings()
            .then((s) => setPausedUntil(s.paused_until ? new Date(s.paused_until) : null))
            .catch(() => { });
    }, []);

    const isPaused = pausedUntil && pausedUntil.getTime() > Date.now();

    async function pauseFor(minutes: number) {
        const until = new Date(Date.now() + minutes * 60_000);
        setPausedUntil(until);
        setOpen(false);
        try {
            await updateNotificationSettings(until.toISOString());
        } catch {
            setPausedUntil(null);
        }
    }

    async function resume() {
        setPausedUntil(null);
        setOpen(false);
        try {
            await updateNotificationSettings(null);
        } catch { }
    }

    return (
        <div className="relative">
            <button
                onClick={() => setOpen((o) => !o)}
                className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition",
                    isPaused
                        ? "border-warning/40 bg-warning/10 text-warning hover:bg-warning/15"
                        : "border-success/40 bg-success/10 text-success hover:bg-success/15",
                )}
            >
                <WhatsAppIcon className="size-3.5" />
                <span className="font-mono text-[10px] tracking-wider font-semibold">
                    {isPaused ? "PAUSADO" : "ATIVO"}
                </span>
            </button>

            {open && (
                <div className="absolute right-0 top-full mt-2 w-60 rounded-xl border border-border bg-popover p-2 shadow-lg z-30">
                    <div className="px-2 py-2 text-[10px] font-mono tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <WhatsAppIcon className="size-3 text-success" />
                        ALERTAS WHATSAPP
                    </div>
                    {!isPaused ? (
                        <>
                            <div className="px-2 pb-1 text-[10px] font-mono tracking-wider text-muted-foreground">
                                PAUSAR POR
                            </div>
                            <div className="space-y-1">
                                {PRESETS.map((p) => (
                                    <button
                                        key={p.minutes}
                                        onClick={() => pauseFor(p.minutes)}
                                        className="w-full text-left px-3 py-1.5 rounded-md text-sm text-foreground hover:bg-mint/10 hover:text-mint-bright transition"
                                    >
                                        {p.label}
                                    </button>
                                ))}
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="px-2 py-1.5 text-xs text-warning rounded-md bg-warning/5 mb-2">
                                Pausado até{" "}
                                <span className="font-mono tabular">
                                    {pausedUntil!.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                                </span>
                            </div>
                            <button
                                onClick={resume}
                                className="w-full text-left px-3 py-1.5 rounded-md text-sm text-success hover:bg-success/10 transition flex items-center gap-2"
                            >
                                <WhatsAppIcon className="size-3.5" />
                                Retomar agora
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
