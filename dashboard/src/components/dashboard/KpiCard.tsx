"use client";

import { type LucideIcon, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/format";

type Tone = "mint" | "success" | "danger" | "warning" | "neutral";

const TONE: Record<Tone, { ring: string; chip: string; value: string }> = {
    mint: {
        ring: "border-mint/30 hover:border-mint/60",
        chip: "bg-mint/10 text-mint-bright border-mint/30",
        value: "text-mint-bright",
    },
    success: {
        ring: "border-success/30 hover:border-success/60",
        chip: "bg-success/10 text-success border-success/30",
        value: "text-success",
    },
    danger: {
        ring: "border-destructive/30 hover:border-destructive/60",
        chip: "bg-destructive/10 text-destructive border-destructive/30",
        value: "text-destructive",
    },
    warning: {
        ring: "border-warning/30 hover:border-warning/60",
        chip: "bg-warning/10 text-warning border-warning/30",
        value: "text-warning",
    },
    neutral: {
        ring: "border-border hover:border-mint/40",
        chip: "bg-muted/40 text-muted-foreground border-border",
        value: "text-foreground",
    },
};

export function KpiCard({
    label,
    value,
    sub,
    icon: Icon,
    tone = "mint",
    onClick,
}: {
    label: string;
    value: string | number;
    sub?: string;
    icon: LucideIcon;
    tone?: Tone;
    onClick?: () => void;
}) {
    const t = TONE[tone];
    const clickable = !!onClick;
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={!clickable}
            className={cn(
                "piq-in group relative w-full text-left rounded-2xl border bg-card p-5 transition-all",
                t.ring,
                clickable && "hover:-translate-y-0.5 hover:shadow-[0_8px_30px_-12px_oklch(0.62_0.22_255/0.4)] cursor-pointer",
            )}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <span className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                            {label}
                        </span>
                    </div>
                    <div
                        className={cn(
                            "font-display font-bold text-3xl mt-2 tabular tracking-tight",
                            t.value,
                        )}
                    >
                        {value}
                    </div>
                    {sub && (
                        <div className="text-xs text-muted-foreground mt-1 font-mono">{sub}</div>
                    )}
                </div>
                <div
                    className={cn(
                        "shrink-0 grid place-items-center size-10 rounded-xl border",
                        t.chip,
                    )}
                >
                    <Icon className="size-5" />
                </div>
            </div>
            {clickable && (
                <div className="mt-3 flex items-center gap-1 text-[10px] font-mono tracking-wider text-mint/70 group-hover:text-mint transition">
                    DETALHAR <ArrowUpRight className="size-3" />
                </div>
            )}
        </button>
    );
}
