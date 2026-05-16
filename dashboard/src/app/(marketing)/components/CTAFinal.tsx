"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { fadeUpStagger, fadeUpChild, VIEWPORT_ONCE } from "../lib/motion-variants";

export function CTAFinal() {
  return (
    <section
      className="relative overflow-hidden border-y border-[var(--border)] px-6 py-24 text-center md:py-32"
      style={{
        background: "linear-gradient(180deg, var(--bg) 0%, #050505 100%)",
      }}
    >
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[800px] w-[800px] -translate-x-1/2 -translate-y-1/2"
        style={{
          background:
            "radial-gradient(circle, rgba(16, 185, 129, 0.06) 0%, transparent 60%)",
        }}
        aria-hidden="true"
      />
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        variants={fadeUpStagger}
        className="relative"
      >
        <motion.h2
          variants={fadeUpChild}
          className="mb-6 text-[clamp(40px,6vw,72px)] font-extrabold leading-none tracking-[-0.04em]"
        >
          Pronto pra apostar
          <br />
          com{" "}
          <em
            className="inline-block bg-clip-text font-[family-name:var(--font-bricolage)] font-bold not-italic tracking-[-0.025em] text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(135deg, var(--green) 0%, var(--cyan) 100%)",
              WebkitBackgroundClip: "text",
            }}
          >
            vantagem real?
          </em>
        </motion.h2>
        <motion.p
          variants={fadeUpChild}
          className="mx-auto mb-10 max-w-[540px] text-[18px] text-[var(--text-muted)]"
        >
          Comece hoje. Receba o primeiro sinal nos próximos minutos. Cancele a
          qualquer momento.
        </motion.p>
        <motion.div variants={fadeUpChild}>
          <Link
            href="/register"
            className="group relative mx-auto inline-flex items-center gap-2 overflow-hidden rounded-md bg-[var(--green)] px-6 py-3.5 text-[14px] font-semibold text-[var(--bg)] transition-all hover:-translate-y-px"
          >
            <span className="pointer-events-none absolute inset-0 bg-[var(--green-bright)] opacity-0 transition-opacity group-hover:opacity-100" />
            <span className="relative z-10">Quero Acesso Agora</span>
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
        </motion.div>
      </motion.div>
    </section>
  );
}
