"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { fadeUpChild } from "../../lib/motion-variants";

export type PillarColor = {
  hex: string;
  rgb: string; // "16, 185, 129"
};

export function PillarCard({
  badge,
  title,
  description,
  icon,
  color,
}: {
  badge: string;
  title: string;
  description: string;
  icon: ReactNode;
  color: PillarColor;
}) {
  const colorVars = {
    "--pillar-color": color.hex,
    "--pillar-rgb": color.rgb,
  } as React.CSSProperties;

  return (
    <motion.div
      variants={fadeUpChild}
      className="group relative flex min-h-[260px] flex-col bg-[var(--bg-card)] p-8 transition-colors hover:bg-[var(--bg-elevated)]"
      style={colorVars}
    >
      <span
        className="absolute left-0 right-0 top-0 h-px opacity-0 transition-opacity group-hover:opacity-50"
        style={{
          background:
            "linear-gradient(90deg, transparent, var(--pillar-color), transparent)",
        }}
        aria-hidden="true"
      />

      <span
        className="absolute right-8 top-8 rounded font-mono text-[10px] uppercase tracking-wider"
        style={{
          color: "var(--pillar-color)",
          border: "1px solid rgba(var(--pillar-rgb), 0.3)",
          background: "rgba(var(--pillar-rgb), 0.04)",
          padding: "3px 8px",
        }}
      >
        {badge}
      </span>

      <div
        className="relative mb-6 flex h-11 w-11 items-center justify-center rounded-[10px]"
        style={{
          color: "var(--pillar-color)",
          background: "rgba(var(--pillar-rgb), 0.08)",
          border: "1px solid rgba(var(--pillar-rgb), 0.15)",
        }}
      >
        {icon}
        <span
          className="absolute inset-0 -z-10 rounded-[10px] opacity-15"
          style={{
            background: "var(--pillar-color)",
            filter: "blur(20px)",
          }}
          aria-hidden="true"
        />
      </div>

      <h3 className="mb-3 text-[19px] font-bold tracking-tight text-[var(--text)]">
        {title}
      </h3>
      <p className="text-[14px] leading-relaxed text-[var(--text-muted)]">
        {description}
      </p>
    </motion.div>
  );
}
