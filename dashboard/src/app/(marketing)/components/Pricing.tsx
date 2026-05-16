"use client";

import { motion } from "framer-motion";
import { fadeUpStagger, VIEWPORT_ONCE } from "../lib/motion-variants";
import { SectionHeading } from "./ui/SectionHeading";
import { PriceCard } from "./ui/PriceCard";

const PRO_FEATURES = [
  { bold: "Sinais de Escanteios", text: "ilimitados" },
  { text: "Alertas no WhatsApp em tempo real" },
  { bold: "Dashboard", text: "de performance completo" },
  { text: "Histórico de sinais e ROI" },
  { text: "Análise de pressão de jogo" },
  { bold: "9 ligas", text: "monitoradas" },
  { text: "Suporte por email" },
];

const MAX_FEATURES = [
  { bold: "Tudo do plano Pro", text: "" },
  { text: "Sinais de ", bold: "Cartões + Gols" },
  { text: "Grupo ", bold: "VIP no WhatsApp" },
  { bold: "Robô apostador", text: "automático" },
  { text: "Estratégia totalmente customizável" },
  { bold: "Gestão de banca", text: "integrada" },
  { text: "Suporte prioritário ", bold: "24/7" },
];

export function Pricing() {
  return (
    <section id="pricing" className="mx-auto max-w-[1280px] px-6 py-24 md:py-32">
      <SectionHeading
        eyebrow="PLANOS"
        title="Escolha seu"
        highlight="nível de vantagem."
        sub="Comece com Pro pra ter sinais qualificados. Migre pra Max quando quiser automação total e gestão de banca."
      />

      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        variants={fadeUpStagger}
        className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2"
      >
        <PriceCard
          name="Pro"
          tagline="Para quem quer vantagem real com dados profissionais."
          price="39,90"
          features={PRO_FEATURES}
          ctaHref="/register?plan=pro"
          ctaLabel="Assinar Pro"
        />
        <PriceCard
          name="Max"
          tagline="Para profissionais que querem automação total."
          price="89,90"
          features={MAX_FEATURES}
          ctaHref="/register?plan=max"
          ctaLabel="Assinar Max"
          featured
        />
      </motion.div>
    </section>
  );
}
