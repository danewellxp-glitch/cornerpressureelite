"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { fadeUp, fadeUpStagger, fadeUpChild, VIEWPORT_ONCE } from "../../lib/motion-variants";

export function SectionHeading({
  eyebrow,
  title,
  highlight,
  sub,
}: {
  eyebrow: string;
  title: ReactNode;
  highlight?: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={VIEWPORT_ONCE}
      variants={fadeUpStagger}
      className="mb-16"
    >
      <motion.div
        variants={fadeUpChild}
        className="mb-5 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--green)]"
      >
        <span className="h-px w-8 bg-[var(--green)]" />
        {eyebrow}
      </motion.div>
      <motion.h2
        variants={fadeUpChild}
        className="mb-6 max-w-[800px] text-[clamp(36px,5vw,64px)] font-bold leading-[1.05] tracking-[-0.03em]"
      >
        {title}
        {highlight && (
          <>
            <br />
            <em
              className="inline-block bg-clip-text font-[family-name:var(--font-bricolage)] font-bold not-italic tracking-[-0.025em] text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(135deg, var(--green) 0%, var(--cyan) 100%)",
                WebkitBackgroundClip: "text",
              }}
            >
              {highlight}
            </em>
          </>
        )}
      </motion.h2>
      {sub && (
        <motion.p
          variants={fadeUp}
          className="max-w-[600px] text-[18px] leading-relaxed text-[var(--text-muted)]"
        >
          {sub}
        </motion.p>
      )}
    </motion.div>
  );
}
