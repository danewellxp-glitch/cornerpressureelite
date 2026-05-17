"use client";

import { motion } from "framer-motion";
import { X, Check } from "lucide-react";

const notIs = [
    "Bot de signals guiado por feeling",
    "Cópia de tipsters do Telegram",
    "Reação a stats Opta sem contexto temporal",
    "Caixa-preta com promessa de ROI",
];

const is = [
    "Captura e análise de movimentação de mercado em tempo real",
    "Modelagem matemática de pricing: como a linha se move, por que, quando",
    "Detector de mispricing temporal — janelas onde existe valor real",
    "Dataset histórico de qualidade alimentando estratégias backtested",
];

export function Vision() {
    return (
        <section id="vision" className="relative py-28 border-t border-border overflow-hidden">
            <div
                className="absolute inset-0 opacity-[0.04]"
                style={{
                    backgroundImage: "radial-gradient(var(--piq-mint) 1px, transparent 1px)",
                    backgroundSize: "24px 24px",
                }}
                aria-hidden
            />

            <div className="relative mx-auto max-w-6xl px-6">
                <div className="text-center mb-16">
                    <div className="font-mono text-xs text-mint mb-3">// VISÃO</div>
                    <motion.h2
                        initial={{ opacity: 0, y: 16 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="font-display text-4xl md:text-6xl font-bold text-foreground max-w-3xl mx-auto leading-tight"
                    >
                        Uma ferramenta <span className="piq-text-gradient-mint">quant</span>.
                        <br />
                        Não um bot de palpite.
                    </motion.h2>
                    <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
                        O ativo principal é o dataset proprietário que cresce a cada dia.
                        Os sinais no WhatsApp são produto derivado — não o produto.
                    </p>
                    <p className="mt-3 text-sm text-mint-bright font-mono max-w-2xl mx-auto">
                        // Mostramos o que o sistema FAZ, não o que vai fazer.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 gap-px bg-border rounded-xl overflow-hidden max-w-5xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="bg-card p-8"
                    >
                        <div className="flex items-center gap-2 mb-6">
                            <div className="w-7 h-7 rounded-md bg-destructive/15 border border-destructive/30 grid place-items-center">
                                <X className="w-4 h-4 text-destructive" strokeWidth={2.5} />
                            </div>
                            <h3 className="font-display font-semibold text-foreground">O que NÃO é</h3>
                        </div>
                        <ul className="space-y-3">
                            {notIs.map((item) => (
                                <li key={item} className="flex items-start gap-3 text-sm text-muted-foreground leading-relaxed">
                                    <span className="font-mono text-destructive/70 mt-0.5">—</span>
                                    <span>{item}</span>
                                </li>
                            ))}
                        </ul>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="bg-card p-8 relative"
                    >
                        <div className="absolute inset-0 bg-mint/[0.03]" aria-hidden />
                        <div className="relative">
                            <div className="flex items-center gap-2 mb-6">
                                <div className="w-7 h-7 rounded-md bg-mint/15 border border-mint/40 grid place-items-center">
                                    <Check className="w-4 h-4 text-mint" strokeWidth={2.5} />
                                </div>
                                <h3 className="font-display font-semibold text-foreground">O que É</h3>
                            </div>
                            <ul className="space-y-3">
                                {is.map((item) => (
                                    <li key={item} className="flex items-start gap-3 text-sm text-foreground leading-relaxed">
                                        <span className="font-mono text-mint mt-0.5">+</span>
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
