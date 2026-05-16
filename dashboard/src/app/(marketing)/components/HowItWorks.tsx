"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fadeUpStagger, fadeUpChild, VIEWPORT_ONCE } from "../lib/motion-variants";
import { SectionHeading } from "./ui/SectionHeading";

type StepId = 1 | 2 | 3 | 4 | 5;

const STEPS: ReadonlyArray<{ id: StepId; title: string; body: string }> = [
  {
    id: 1,
    title: "Sistema monitora 9 ligas",
    body: "Centenas de jogos ao vivo analisados simultaneamente — Premier, La Liga, Bundesliga, Serie A, Brasileirão, Argentina, Portugal, Holanda, Chile.",
  },
  {
    id: 2,
    title: "Algoritmo identifica pressão",
    body: "Pressure Score (escanteios) e Tension Score (cartões) calculam confluência de fatores: ritmo, momentum, contexto do placar.",
  },
  {
    id: 3,
    title: "Sinal chega no seu WhatsApp",
    body: "Em menos de 30 segundos. Linha sugerida, odd justa, justificativa técnica. Você não precisa estar no app.",
  },
  {
    id: 4,
    title: "Você decide. Aposta sua.",
    body: "No Pro, você aposta como preferir. No Max, robô executa automaticamente e atualiza sua banca dentro do sistema.",
  },
  {
    id: 5,
    title: "Resultado rastreado",
    body: "Sistema registra GREEN/RED, atualiza ROI, calcula desempenho por mercado. Histórico auditável sempre disponível.",
  },
];

export function HowItWorks() {
  const [active, setActive] = useState<StepId>(1);

  return (
    <section id="how" className="mx-auto max-w-[1280px] px-6 py-24 md:py-32">
      <SectionHeading
        eyebrow="EM 5 PASSOS"
        title="Do dado bruto"
        highlight="ao green confirmado."
        sub="O processo que separa apostador de trader esportivo."
      />

      <div className="grid items-start gap-12 lg:grid-cols-2 lg:gap-20">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={VIEWPORT_ONCE}
          variants={fadeUpStagger}
          className="flex flex-col"
        >
          {STEPS.map((step) => {
            const isActive = active === step.id;
            return (
              <motion.button
                key={step.id}
                variants={fadeUpChild}
                onClick={() => setActive(step.id)}
                onMouseEnter={() => setActive(step.id)}
                aria-pressed={isActive}
                className={`grid grid-cols-[56px_1fr] gap-6 border-b border-[var(--border)] py-8 text-left transition-opacity last:border-b-0 ${
                  isActive ? "opacity-100" : "opacity-40 hover:opacity-100"
                }`}
              >
                <span className="pt-1 font-mono text-[13px] font-bold tracking-wide text-[var(--green)]">
                  {String(step.id).padStart(2, "0")} {isActive && "↘"}
                </span>
                <span>
                  <h4 className="mb-2 text-[18px] font-bold tracking-tight">
                    {step.title}
                  </h4>
                  <p className="text-[14px] leading-relaxed text-[var(--text-muted)]">
                    {step.body}
                  </p>
                </span>
              </motion.button>
            );
          })}
        </motion.div>

        <div className="relative">
          <div className="sticky top-24">
            <div
              className="relative min-h-[460px] overflow-hidden rounded-xl border border-[var(--border-bright)] bg-[var(--bg-card)] p-8"
              style={{ minHeight: 460 }}
            >
              <span
                className="pointer-events-none absolute inset-0"
                style={{
                  background:
                    "radial-gradient(circle at 70% 30%, rgba(16, 185, 129, 0.08), transparent 60%)",
                }}
                aria-hidden="true"
              />
              <AnimatePresence mode="wait">
                <motion.div
                  key={active}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25 }}
                >
                  {active === 1 && <VisualOverview />}
                  {active === 2 && <VisualPressureBars />}
                  {active === 3 && <VisualWhatsApp />}
                  {active === 4 && <VisualMyBets />}
                  {active === 5 && <VisualPerformance />}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricBox({
  label,
  value,
  delta,
  greenValue,
}: {
  label: string;
  value: string;
  delta?: string;
  greenValue?: boolean;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-black/30 p-3.5">
      <div className="mb-1.5 font-mono text-[9px] uppercase tracking-wider text-[var(--text-dim)]">
        {label}
      </div>
      <div
        className={`text-[22px] font-bold tracking-tight ${
          greenValue ? "text-[var(--green)]" : "text-[var(--text)]"
        }`}
      >
        {value}
      </div>
      {delta && (
        <div className="mt-1 text-[10px] text-[var(--green)]">{delta}</div>
      )}
    </div>
  );
}

function ChartMock() {
  return (
    <svg viewBox="0 0 400 120" className="mt-4 h-[120px] w-full">
      <defs>
        <linearGradient id="howChart" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        fill="url(#howChart)"
        opacity="0.6"
        d="M 0,100 L 0,80 L 40,70 L 80,55 L 120,60 L 160,40 L 200,45 L 240,30 L 280,35 L 320,20 L 360,25 L 400,15 L 400,120 L 0,120 Z"
      />
      <path
        stroke="#10b981"
        strokeWidth="2"
        fill="none"
        d="M 0,80 L 40,70 L 80,55 L 120,60 L 160,40 L 200,45 L 240,30 L 280,35 L 320,20 L 360,25 L 400,15"
      />
    </svg>
  );
}

function VisualOverview() {
  return (
    <div className="relative font-mono">
      <div className="mb-6 flex gap-1 border-b border-[var(--border)] pb-4">
        {[
          { label: "Premier", active: true },
          { label: "La Liga" },
          { label: "Brasileirão" },
          { label: "+6" },
        ].map((t) => (
          <span
            key={t.label}
            className={`cursor-pointer rounded px-3 py-1.5 text-[11px] ${
              t.active
                ? "border border-[rgba(16,185,129,0.2)] bg-[rgba(16,185,129,0.08)] text-[var(--green)]"
                : "text-[var(--text-dim)]"
            }`}
          >
            {t.label}
          </span>
        ))}
      </div>
      <div className="mb-6 grid grid-cols-3 gap-3">
        <MetricBox label="JOGOS LIVE" value="27" />
        <MetricBox label="LIGAS" value="9/9" greenValue />
        <MetricBox label="UPTIME" value="99.7%" />
      </div>
      <ChartMock />
    </div>
  );
}

function VisualPressureBars() {
  const bars = [
    { label: "PRESSURE SCORE", value: "8/11", pct: 73, color: "var(--green)" },
    { label: "ATAQUES PERIGOSOS", value: "42", pct: 68, color: "var(--cyan)" },
    { label: "RITMO ESCANTEIOS", value: "+7 em 15'", pct: 85, color: "#c084fc" },
  ];
  return (
    <div className="relative font-mono">
      <div className="mb-6">
        <div className="mb-1 text-[13px] font-semibold text-[var(--text)]">
          Man City × Arsenal
        </div>
        <div className="text-[11px] text-[var(--text-dim)]">Premier League · 67'</div>
      </div>
      <div className="flex flex-col gap-3">
        {bars.map((b) => (
          <div key={b.label}>
            <div className="mb-1.5 flex justify-between text-[11px]">
              <span className="text-[var(--text-muted)]">{b.label}</span>
              <span className="font-bold" style={{ color: b.color }}>
                {b.value}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-[3px] bg-[var(--border)]">
              <div
                className="h-full"
                style={{
                  width: `${b.pct}%`,
                  background: b.color,
                  boxShadow: `0 0 12px ${b.color}`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-8 rounded-lg border border-[rgba(16,185,129,0.2)] bg-[rgba(16,185,129,0.08)] p-3.5">
        <div className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--green)]">
          SINAL GERADO
        </div>
        <div className="text-[14px] font-semibold">Over 9.5 corners @ 1.74</div>
      </div>
    </div>
  );
}

function VisualWhatsApp() {
  return (
    <div className="relative flex flex-col gap-3 font-mono">
      <div className="mb-2 flex items-center gap-3 border-b border-[var(--border)] pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--green)] text-[16px] font-bold text-[var(--bg)]">
          P
        </div>
        <div className="flex-1">
          <div className="text-[13px] font-semibold text-[var(--text)]">
            PressureIQ Signals
          </div>
          <div className="mt-0.5 text-[11px] text-[var(--green)]">● online</div>
        </div>
      </div>
      <div className="max-w-[90%] rounded-tl-lg rounded-tr-lg rounded-br-lg border border-[rgba(16,185,129,0.15)] bg-[rgba(16,185,129,0.08)] p-4 text-[12px] leading-relaxed text-[var(--text)]">
        <span className="mb-2 block font-bold uppercase tracking-widest text-[var(--green)]">
          ⚡ Sinal de Alta Probabilidade
        </span>
        <strong className="text-[var(--green-bright)]">
          Manchester City × Arsenal
        </strong>
        <br />
        Premier League · 67' · 1-1
        <br />
        <br />
        Mercado: <strong>Mais 9.5 escanteios</strong>
        <br />
        Odd recomendada: <strong>@1.74</strong>
        <br />
        Casa: Bet365
        <br />
        <br />
        <span className="text-[var(--text-muted)]">
          Pressão crescente do mandante. 7 escanteios nos últimos 15 min. Score: 8/11.
        </span>
        <div className="mt-1.5 text-right text-[10px] text-[var(--text-dim)]">17:42 ✓✓</div>
      </div>
    </div>
  );
}

function VisualMyBets() {
  return (
    <div className="relative font-mono">
      <div className="mb-4 text-[12px] uppercase tracking-wider text-[var(--text-muted)]">
        MINHAS APOSTAS · MAX
      </div>
      <div className="mb-4 rounded-xl border border-[var(--border)] bg-black/30 p-5">
        <div className="mb-1 text-[14px] font-semibold text-[var(--text)]">
          Man City × Arsenal
        </div>
        <div className="mb-4 text-[11px] text-[var(--text-dim)]">
          Premier League · Mais 9.5 corners @ 1.74
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="flex-1 rounded-md border border-[rgba(16,185,129,0.3)] bg-[rgba(16,185,129,0.1)] px-2 py-2.5 font-mono text-[11px] text-[var(--green)]"
          >
            ✓ APOSTAR R$ 50
          </button>
          <button
            type="button"
            className="flex-1 rounded-md border border-[var(--border-bright)] bg-transparent px-2 py-2.5 font-mono text-[11px] text-[var(--text-muted)]"
          >
            EDITAR
          </button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <MetricBox label="BANCA" value="R$ 1.247" delta="+R$ 247 (+24.7%)" />
        <MetricBox label="EXPOSIÇÃO" value="2.0%" delta="R$ 50 desta aposta" />
      </div>
    </div>
  );
}

function VisualPerformance() {
  return (
    <div className="relative font-mono">
      <div className="mb-4 text-[12px] uppercase tracking-wider text-[var(--text-muted)]">
        PERFORMANCE · 30 DIAS
      </div>
      <div className="mb-6 grid grid-cols-3 gap-3">
        <MetricBox label="ROI" value="+18.4%" delta="▲ 3.2pp" greenValue />
        <MetricBox label="WIN RATE" value="63%" />
        <MetricBox label="SINAIS" value="147" />
      </div>
      <svg viewBox="0 0 400 120" className="h-[120px] w-full">
        <defs>
          <linearGradient id="perfChart" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          fill="url(#perfChart)"
          opacity="0.6"
          d="M 0,100 L 0,90 L 40,85 L 80,75 L 120,80 L 160,60 L 200,55 L 240,45 L 280,30 L 320,35 L 360,20 L 400,10 L 400,120 L 0,120 Z"
        />
        <path
          stroke="#10b981"
          strokeWidth="2"
          fill="none"
          d="M 0,90 L 40,85 L 80,75 L 120,80 L 160,60 L 200,55 L 240,45 L 280,30 L 320,35 L 360,20 L 400,10"
        />
      </svg>
      <div className="mt-4 flex justify-between font-mono text-[10px] text-[var(--text-dim)]">
        <span>HÁ 30 DIAS</span>
        <span>HOJE</span>
      </div>
    </div>
  );
}
