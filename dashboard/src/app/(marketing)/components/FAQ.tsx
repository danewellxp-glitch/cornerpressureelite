"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fadeUpStagger, fadeUpChild, VIEWPORT_ONCE } from "../lib/motion-variants";
import { SectionHeading } from "./ui/SectionHeading";

const FAQS = [
  {
    q: "Quantos sinais por dia eu recebo?",
    a: "Não temos meta de volume. Sinal só sai quando confluência de fatores aparece — entre 4 e 15 sinais por dia, dependendo da agenda de jogos. Menos quantidade, mais qualidade.",
  },
  {
    q: "Como sei que não é mais um tipster?",
    a: "Todo sinal emitido fica registrado no seu dashboard com timestamp, jogo, mercado, odd e resultado. Tipsters deletam histórico ruim. PressureIQ persiste tudo — você revisa quando quiser, ROI calculado matematicamente.",
  },
  {
    q: "Em quais casas posso usar?",
    a: "Os sinais funcionam em qualquer casa que aceite os mercados (escanteios, cartões, gols). No plano Max, o robô apostador suporta integração com as principais casas brasileiras.",
  },
  {
    q: "Tem garantia de lucro?",
    a: "Não — e desconfie de quem garante. Apostas têm risco inerente. PressureIQ fornece vantagem informacional, dados melhores e disciplina via gestão de banca. ROI histórico mostra que com gestão disciplinada, vantagem se converte em lucro consistente. Resultados passados não garantem resultados futuros.",
  },
  {
    q: "Posso cancelar quando quiser?",
    a: "Sim. Sem fidelidade, sem multa. Cancela direto pelo dashboard. Acesso permanece até o fim do ciclo já pago.",
  },
  {
    q: "E se eu não entender de aposta esportiva?",
    a: 'O plano Pro foi desenhado pra ser simples: sinal chega no WhatsApp com instrução clara. Quem quiser aprofundar tem a página "Aprenda" com explicações de cada conceito. Plano Max adiciona automação pra quem prefere delegar tudo.',
  },
] as const;

export function FAQ() {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  return (
    <section id="faq" className="mx-auto max-w-[1280px] px-6 py-24 md:py-32">
      <SectionHeading
        eyebrow="DÚVIDAS FREQUENTES"
        title="Antes de você"
        highlight="perguntar."
      />

      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        variants={fadeUpStagger}
        className="mx-auto mt-14 max-w-[800px]"
      >
        {FAQS.map((f, i) => {
          const isOpen = openIdx === i;
          return (
            <motion.div
              key={f.q}
              variants={fadeUpChild}
              className="border-b border-[var(--border)]"
            >
              <button
                type="button"
                onClick={() => setOpenIdx(isOpen ? null : i)}
                aria-expanded={isOpen}
                className="flex w-full cursor-pointer items-center justify-between gap-4 py-7 text-left"
              >
                <span className="text-[18px] font-semibold tracking-tight text-[var(--text)]">
                  {f.q}
                </span>
                <span
                  className={`font-mono text-[22px] text-[var(--green)] transition-transform duration-300 ${
                    isOpen ? "rotate-45" : ""
                  }`}
                  aria-hidden="true"
                >
                  +
                </span>
              </button>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                    className="overflow-hidden"
                  >
                    <p className="pb-7 text-[15px] leading-relaxed text-[var(--text-muted)]">
                      {f.a}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
