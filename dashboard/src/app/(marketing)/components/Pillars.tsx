"use client";

import { motion } from "framer-motion";
import {
  Cpu,
  MessageCircle,
  LayoutDashboard,
  Bot,
  SlidersHorizontal,
  TrendingUp,
} from "lucide-react";
import { fadeUpStagger, VIEWPORT_ONCE } from "../lib/motion-variants";
import { SectionHeading } from "./ui/SectionHeading";
import { PillarCard, type PillarColor } from "./ui/PillarCard";

const PILLARS: Array<{
  badge: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  color: PillarColor;
}> = [
  {
    badge: "CORE",
    title: "Previsões com IA",
    description:
      "Algoritmos proprietários analisam pressão de jogo, ataques perigosos, ritmo de escanteios e cartões em centenas de partidas simultâneas. Dados que as casas de apostas não mostram.",
    icon: <Cpu size={24} strokeWidth={2} />,
    color: { hex: "#10b981", rgb: "16, 185, 129" },
  },
  {
    badge: "TEMPO REAL",
    title: "Alertas no WhatsApp",
    description:
      "Sinais chegam em menos de 30 segundos após identificação. Você recebe o alerta com a odd recomendada, a casa de apostas e o raciocínio do algoritmo. Nunca mais perde uma oportunidade.",
    icon: <MessageCircle size={24} strokeWidth={2} />,
    color: { hex: "#22d3ee", rgb: "34, 211, 238" },
  },
  {
    badge: "DASHBOARD",
    title: "Dashboard Completo",
    description:
      "Painel profissional com histórico de sinais, ROI acumulado, gráficos de desempenho e acompanhamento dos jogos ao vivo. O Bloomberg Terminal do apostador esportivo.",
    icon: <LayoutDashboard size={24} strokeWidth={2} />,
    color: { hex: "#60a5fa", rgb: "96, 165, 250" },
  },
  {
    badge: "MAX",
    title: "Robô Apostador",
    description:
      "Conecte sua conta nas principais casas de apostas e deixe o robô executar as apostas automaticamente. Sem emoção, sem erros humanos. Trabalha 24h por dia enquanto você vive.",
    icon: <Bot size={24} strokeWidth={2} />,
    color: { hex: "#c084fc", rgb: "192, 132, 252" },
  },
  {
    badge: "MAX",
    title: "Estratégia Customizável",
    description:
      "Configure risco máximo por aposta, mercados favoritos (escanteios, cartões, gols), bankroll management e filtros de odds. Você controla a estratégia, o algoritmo executa.",
    icon: <SlidersHorizontal size={24} strokeWidth={2} />,
    color: { hex: "#f472b6", rgb: "244, 114, 182" },
  },
  {
    badge: "TODOS",
    title: "ROI Rastreado",
    description:
      "Cada sinal é registrado com resultado real. Veja seu desempenho histórico, taxa de acerto por mercado e evolução do bankroll. Transparência total, nenhuma manipulação.",
    icon: <TrendingUp size={24} strokeWidth={2} />,
    color: { hex: "#34d399", rgb: "52, 211, 153" },
  },
];

export function Pillars() {
  return (
    <section id="pilares" className="mx-auto max-w-[1280px] px-6 py-24 md:py-32">
      <SectionHeading
        eyebrow="TUDO QUE VOCÊ PRECISA"
        title="Uma Plataforma."
        highlight="Vantagem Completa."
        sub="Do sinal ao dinheiro na conta. PressureIQ cobre todo o processo de análise e execução pra você."
      />

      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        variants={fadeUpStagger}
        className="grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-3"
      >
        {PILLARS.map((p) => (
          <PillarCard key={p.title} {...p} />
        ))}
      </motion.div>
    </section>
  );
}
