"use client";

import { motion } from "framer-motion";
import { fadeUp, fadeUpStagger, fadeUpChild, VIEWPORT_ONCE } from "../lib/motion-variants";

export function Manifesto() {
  return (
    <section className="relative mx-auto max-w-[1280px] overflow-hidden px-6 py-32 text-center md:py-44">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <div
          className="absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2"
          style={{
            background:
              "radial-gradient(circle, rgba(16, 185, 129, 0.06) 0%, transparent 60%)",
            filter: "blur(40px)",
          }}
        />
      </div>

      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        variants={fadeUpStagger}
      >
        <motion.div
          variants={fadeUpChild}
          className="mb-12 inline-flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--green)]"
        >
          <span className="h-px w-8 bg-[var(--green-dim)]" />
          <span>MARKET MICROSTRUCTURE</span>
          <span className="h-px w-8 bg-[var(--green-dim)]" />
        </motion.div>

        <motion.h2
          variants={fadeUpChild}
          className="mx-auto max-w-[1100px] text-[clamp(40px,6.5vw,96px)] font-bold leading-[1.0] tracking-[-0.04em]"
        >
          Uma ferramenta{" "}
          <span
            className="inline-block bg-clip-text font-[family-name:var(--font-bricolage)] font-bold tracking-[-0.025em] text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(135deg, var(--green) 0%, var(--cyan) 100%)",
              WebkitBackgroundClip: "text",
            }}
          >
            quant.
          </span>
          <br />
          Não um{" "}
          <span
            className="text-[var(--text-dim)]"
            style={{
              textDecoration: "line-through",
              textDecorationColor: "var(--red)",
              textDecorationThickness: "3px",
            }}
          >
            bot de palpite.
          </span>
        </motion.h2>

        <motion.div
          variants={fadeUp}
          className="mt-16 flex flex-wrap items-center justify-center gap-6 font-mono text-[11px] uppercase tracking-widest text-[var(--text-dim)]"
        >
          <span>DADOS REAIS</span>
          <span
            className="inline-block h-1 w-1 rounded-full bg-[var(--green)]"
            style={{ boxShadow: "0 0 8px var(--green)" }}
            aria-hidden="true"
          />
          <span>ALGORITMOS PROPRIETÁRIOS</span>
          <span
            className="inline-block h-1 w-1 rounded-full bg-[var(--green)]"
            style={{ boxShadow: "0 0 8px var(--green)" }}
            aria-hidden="true"
          />
          <span>HISTÓRICO AUDITÁVEL</span>
        </motion.div>
      </motion.div>
    </section>
  );
}
