"use client";

import { cn } from "@/lib/utils";

interface StatusIndicatorProps {
  online: boolean;
  className?: string;
}

export function StatusIndicator({ online, className }: StatusIndicatorProps) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        online ? "bg-green-500 animate-pulse" : "bg-red-500",
        className
      )}
      aria-label={online ? "Online" : "Offline"}
    />
  );
}
