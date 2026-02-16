"use client";

import { LucideIcon } from "lucide-react";
import { Card } from "./ui/Card";

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  subValue?: string;
  variant?: "default" | "green" | "red" | "amber" | "cyan";
}

const variantClasses = {
  default: "text-white",
  green: "text-emerald-400",
  red: "text-red-400",
  amber: "text-amber-400",
  cyan: "text-cyan-400",
};

export function MetricCard({
  icon: Icon,
  label,
  value,
  subValue,
  variant = "default",
}: MetricCardProps) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            {label}
          </p>
          <p className={`mt-2 text-3xl font-bold md:text-4xl ${variantClasses[variant]}`}>
            {value}
          </p>
          {subValue && (
            <p className="mt-1 text-sm text-zinc-500">{subValue}</p>
          )}
        </div>
        <div className="rounded-lg bg-white/5 p-2.5">
          <Icon className="h-6 w-6 text-zinc-400" />
        </div>
      </div>
    </Card>
  );
}
