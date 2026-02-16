"use client";

import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-white/5 bg-gradient-to-br from-[#1a1a1a] to-[#0f0f0f] p-6",
        "shadow-xl shadow-black/50 transition-all duration-300 hover:border-cyan-500/20",
        className
      )}
    >
      {children}
    </div>
  );
}
