"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { fadeUp, scaleIn } from "../lib/motion-variants";
import { TerminalCard } from "./TerminalCard";

const STATS = [
  { value: "+18.4", unit: "%", label: "ROI 30 DIAS" },
  { value: "63", unit: "%", label: "WIN RATE" },
  { value: "<30", unit: "s", label: "LATÊNCIA SINAL" },
  { value: "9", unit: "/9", label: "LIGAS ATIVAS" },
] as const;

export function Hero() {
  return (
    <section className="relative min-h-[calc(100vh-28px)] w-full overflow-hidden">
      {/* hero background image — edge-to-edge */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage: "url('/hero-bg.jpg')",
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
        }}
        aria-hidden="true"
      />
      {/* dark overlay para legibilidade do texto */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(10,10,10,0.85) 0%, rgba(10,10,10,0.75) 40%, rgba(10,10,10,0.92) 100%)",
        }}
        aria-hidden="true"
      />
      {/* scanlines */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(16, 185, 129, 0.015) 2px, rgba(16, 185, 129, 0.015) 4px)",
        }}
        aria-hidden="true"
      />
      {/* atmospheric glow */}
      <div className="pointer-events-none absolute inset-0 z-[1] overflow-hidden" aria-hidden="true">
        <div
          className="absolute -left-[10%] -top-[20%] h-[80%] w-[60%]"
          style={{
            background:
              "radial-gradient(circle, rgba(16, 185, 129, 0.10) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
        <div
          className="absolute -bottom-[20%] -right-[10%] h-[60%] w-[50%]"
          style={{
            background:
              "radial-gradient(circle, rgba(34, 211, 238, 0.06) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
      </div>

      <div className="relative z-[2] mx-auto grid max-w-[1280px] items-center gap-12 px-6 pb-28 pt-12 md:pt-20 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
        <div>
          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="mb-8 inline-flex items-center gap-2.5 rounded-full border border-[var(--border-bright)] bg-[rgba(16,185,129,0.04)] px-3.5 py-1.5 font-mono text-[11px] font-medium uppercase tracking-widest text-[var(--green)]"
          >
            <span
              className="h-1.5 w-1.5 rounded-full bg-[var(--green)]"
              style={{
                boxShadow: "0 0 12px var(--green)",
                animation: "pulse-dot 1.5s ease-in-out infinite",
              }}
            />
            <span>SISTEMA AO VIVO · 9 LIGAS · TEMPO REAL</span>
          </motion.div>

          <motion.h1
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            transition={{ delay: 0.1 }}
            className="mb-7 text-[clamp(48px,7vw,86px)] font-extrabold leading-[0.95] tracking-[-0.04em]"
          >
            A Ciência
            <br />
            por trás
            <br />
            <span
              className="inline-block bg-clip-text font-[family-name:var(--font-bricolage)] font-bold tracking-[-0.02em] text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(135deg, var(--green) 0%, var(--cyan) 100%)",
                WebkitBackgroundClip: "text",
              }}
            >
              do Green.
            </span>
          </motion.h1>

          <motion.p
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            transition={{ delay: 0.2 }}
            className="mb-10 max-w-[520px] text-[18px] leading-relaxed text-[var(--text-muted)]"
          >
            Algoritmos proprietários analisam pressão de jogo em tempo real e
            entregam{" "}
            <strong className="font-medium text-[var(--text)]">
              sinais de alta probabilidade
            </strong>{" "}
            direto no seu WhatsApp. Robô aposta enquanto você dorme.
          </motion.p>

          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            transition={{ delay: 0.3 }}
            className="mb-14 flex flex-wrap gap-3"
          >
            <Link
              href="/register"
              className="group relative inline-flex items-center gap-2 overflow-hidden rounded-md bg-[var(--green)] px-6 py-3.5 text-[14px] font-semibold text-[var(--bg)] transition-all hover:-translate-y-px"
              style={{ transitionProperty: "transform, box-shadow" }}
            >
              <span className="pointer-events-none absolute inset-0 bg-[var(--green-bright)] opacity-0 transition-opacity group-hover:opacity-100" />
              <span className="relative z-10">Quero Começar Agora</span>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                className="relative z-10"
                aria-hidden="true"
              >
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </Link>
            <a
              href="#how"
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border-bright)] bg-transparent px-6 py-3.5 text-[14px] font-semibold text-[var(--text)] transition-colors hover:border-[var(--text-dim)] hover:bg-[var(--bg-elevated)]"
            >
              Ver Como Funciona
            </a>
          </motion.div>

          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            transition={{ delay: 0.4 }}
            className="flex flex-wrap gap-10 border-t border-[var(--border)] pt-8"
          >
            {STATS.map((s) => (
              <div key={s.label}>
                <div className="flex items-baseline gap-1 font-mono text-[24px] font-bold tracking-tight text-[var(--text)]">
                  <span>{s.value}</span>
                  <span className="text-[12px] font-medium text-[var(--text-muted)]">
                    {s.unit}
                  </span>
                </div>
                <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-[var(--text-dim)]">
                  {s.label}
                </div>
              </div>
            ))}
          </motion.div>
        </div>

        <motion.div
          initial="hidden"
          animate="visible"
          variants={scaleIn}
          transition={{ delay: 0.3 }}
        >
          <TerminalCard />
        </motion.div>
      </div>
    </section>
  );
}
