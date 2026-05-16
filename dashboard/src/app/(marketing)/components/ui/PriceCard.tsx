"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { fadeUpChild } from "../../lib/motion-variants";

type Feature = { text: string; bold?: string };

export function PriceCard({
  name,
  tagline,
  price,
  features,
  ctaHref,
  ctaLabel,
  featured,
}: {
  name: string;
  tagline: string;
  price: string;
  features: Feature[];
  ctaHref: string;
  ctaLabel: string;
  featured?: boolean;
}) {
  return (
    <motion.div
      variants={fadeUpChild}
      className={`relative flex flex-col rounded-2xl border p-10 ${
        featured
          ? "border-[var(--green)] bg-[var(--bg-elevated)]"
          : "border-[var(--border-bright)] bg-[var(--bg-card)]"
      }`}
      style={
        featured
          ? {
              boxShadow:
                "0 0 0 1px rgba(16, 185, 129, 0.2), 0 24px 64px -16px rgba(16, 185, 129, 0.15)",
            }
          : undefined
      }
    >
      {featured && (
        <span className="absolute -top-px right-6 rounded-b-md bg-[var(--green)] px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-widest text-[var(--bg)]">
          MAIS POPULAR
        </span>
      )}

      <div
        className={`mb-2 text-[14px] font-semibold uppercase tracking-wider ${
          featured ? "text-[var(--green)]" : "text-[var(--text-muted)]"
        }`}
      >
        {name}
      </div>
      <div className="mb-6 min-h-[40px] text-[13px] text-[var(--text-dim)]">
        {tagline}
      </div>
      <div className="mb-8 flex items-baseline gap-1.5 font-mono text-[48px] font-extrabold tracking-tight">
        <span className="text-[18px] text-[var(--text-muted)]">R$</span>
        <span>{price}</span>
        <span className="font-[family-name:var(--font-geist)] text-[14px] font-medium text-[var(--text-muted)]">
          /mês
        </span>
      </div>

      <ul className="mb-8 flex-1 list-none">
        {features.map((f, i) => (
          <li
            key={i}
            className="flex items-start gap-3 border-b border-[var(--border)] py-2.5 text-[14px] text-[var(--text-muted)] last:border-b-0"
          >
            <Check
              size={16}
              strokeWidth={3}
              className="mt-0.5 shrink-0 text-[var(--green)]"
            />
            <span>
              {f.bold && (
                <strong className="font-medium text-[var(--text)]">{f.bold}</strong>
              )}
              {f.bold && " "}
              {f.text}
            </span>
          </li>
        ))}
      </ul>

      <Link
        href={ctaHref}
        className={`group relative inline-flex w-full items-center justify-center gap-2 overflow-hidden rounded-md px-4 py-3.5 text-[14px] font-semibold transition-all hover:-translate-y-px ${
          featured
            ? "bg-[var(--green)] text-[var(--bg)]"
            : "border border-[var(--border-bright)] bg-transparent text-[var(--text)] hover:border-[var(--text-dim)] hover:bg-[var(--bg-elevated)]"
        }`}
      >
        {featured && (
          <span className="pointer-events-none absolute inset-0 bg-[var(--green-bright)] opacity-0 transition-opacity group-hover:opacity-100" />
        )}
        <span className="relative z-10">{ctaLabel}</span>
      </Link>
    </motion.div>
  );
}
