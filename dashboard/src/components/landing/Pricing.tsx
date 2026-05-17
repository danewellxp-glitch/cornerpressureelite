"use client";

import { motion } from "framer-motion";
import { Check, ArrowRight } from "lucide-react";

type Plan = {
    name: string;
    price: string;
    planKey: "pro" | "max";
    description: string;
    tag: string | null;
    isPopular: boolean;
    features: string[];
};

const plans: Plan[] = [
    {
        name: "Pro",
        price: "39,90",
        planKey: "pro",
        description: "Sinais sólidos chegam no seu WhatsApp. Você decide. Sem distração, sem ruído.",
        tag: null,
        isPopular: false,
        features: [
            "Sinais de Escanteios ilimitados (9 ligas)",
            "Alertas no WhatsApp em segundos",
            "Pressure Score com racional técnico",
            "Histórico completo de sinais e ROI",
            "Dashboard de performance + página Aprenda",
            "Política de linha 1.50–1.70 (odd realista)",
            "Suporte por email",
        ],
    },
    {
        name: "Max",
        price: "89,90",
        planKey: "max",
        description: "Co-piloto, não autopiloto. Dados profissionais, banca rastreada, controle total.",
        tag: "PROFISSIONAL",
        isPopular: true,
        features: [
            "Tudo do Pro + Sinais de Cartões e Gols",
            "Minhas Apostas: aprove, customize ou recuse",
            "Banca integrada com ROI individual real",
            "Robô apostador automático (delegação opcional)",
            "Estratégia customizável (filtros próprios)",
            "Captura de catálogo completo + dataset temporal",
            "Suporte prioritário 24/7",
        ],
    },
];

type Props = {
    onChoosePlan: (planKey: "pro" | "max") => void;
};

export function Pricing({ onChoosePlan }: Props) {
    return (
        <section id="pricing" className="relative py-24 border-t border-border">
            <div className="mx-auto max-w-5xl px-6">
                <div className="text-center mb-14">
                    <div className="font-mono text-xs text-mint mb-3">// PRICING</div>
                    <h2 className="font-display text-4xl md:text-5xl font-bold text-foreground">
                        Sem upsell, sem letra miúda.
                    </h2>
                    <p className="mt-4 text-muted-foreground text-lg max-w-xl mx-auto">
                        Dois planos. Mensal. Cancele quando quiser direto pelo painel.
                        Reembolso nos primeiros 7 dias se decidir não usar.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 gap-6">
                    {plans.map((p, i) => (
                        <motion.div
                            key={p.planKey}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.4, delay: i * 0.1 }}
                            className={`relative rounded-2xl border p-8 flex flex-col ${
                                p.isPopular
                                    ? "border-mint bg-card piq-glow-mint"
                                    : "border-border bg-card"
                            }`}
                        >
                            {p.tag && (
                                <div className="absolute -top-3 left-8 px-3 py-1 bg-mint text-primary-foreground text-[10px] font-mono font-semibold rounded-full">
                                    {p.tag}
                                </div>
                            )}

                            <div className="mb-6">
                                <h3 className="font-display text-2xl font-bold text-foreground">{p.name}</h3>
                                <p className="text-sm text-muted-foreground mt-1">{p.description}</p>
                            </div>

                            <div className="mb-6 flex items-baseline gap-1">
                                <span className="font-mono text-muted-foreground text-sm">R$</span>
                                <span className="font-display text-5xl font-bold text-foreground tabular-nums">
                                    {p.price}
                                </span>
                                <span className="text-muted-foreground text-sm ml-1">/mês</span>
                            </div>

                            <ul className="space-y-3 mb-8 flex-1">
                                {p.features.map((f) => (
                                    <li key={f} className="flex items-start gap-2.5 text-sm text-foreground">
                                        <Check className="w-4 h-4 text-mint mt-0.5 shrink-0" strokeWidth={2.5} />
                                        <span>{f}</span>
                                    </li>
                                ))}
                            </ul>

                            <motion.button
                                whileHover={{ y: -1 }}
                                whileTap={{ y: 0 }}
                                onClick={() => onChoosePlan(p.planKey)}
                                className={`group inline-flex items-center justify-center gap-2 w-full font-medium px-5 py-3 rounded-md transition ${
                                    p.isPopular
                                        ? "bg-mint text-primary-foreground hover:bg-mint-bright"
                                        : "border border-border text-foreground hover:bg-secondary"
                                }`}
                            >
                                Assinar {p.name}
                                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition" />
                            </motion.button>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
