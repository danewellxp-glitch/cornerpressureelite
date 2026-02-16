"use client";

import { cn } from "@/lib/utils";

type BadgeVariant = "green" | "red" | "pending" | "premium" | "normal" | "online" | "offline";

const variantClasses: Record<BadgeVariant, string> = {
  green: "bg-green-500/20 text-green-400 border border-green-500/30",
  red: "bg-red-500/20 text-red-400 border border-red-500/30",
  pending: "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
  premium: "bg-fuchsia-500/20 text-fuchsia-400 border border-fuchsia-500/30",
  normal: "bg-zinc-500/20 text-zinc-300 border border-zinc-500/30",
  online: "bg-green-500/20 text-green-400 border border-green-500/30",
  offline: "bg-red-500/20 text-red-400 border border-red-500/30",
};

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant, children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
