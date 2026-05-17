"use client";

import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Activity, Bot } from "lucide-react";

type Props = {
    onOpenAuth: (tab: "login" | "register") => void;
};

const ticks = [
    { match: "ARS vs BRA", market: "Over 9.5 corners", from: "1.92", to: "1.74", edge: "+4.2%" },
    { match: "MCI vs LIV", market: "BTTS", from: "1.65", to: "1.58", edge: "+2.1%" },
    { match: "RMA vs BAR", market: "Cards Over 4.5", from: "2.10", to: "1.88", edge: "+5.8%" },
    { match: "PSG vs OM", market: "Corner H2 Over 5.5", from: "2.05", to: "1.92", edge: "+3.4%" },
];

export function Hero({ onOpenAuth }: Props) {
    return (
        <section id="top" className="relative pt-32 pb-24 overflow-hidden">
            <div className="absolute inset-0 piq-grid-bg opacity-40" aria-hidden />
            <div
                className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full opacity-30 blur-3xl"
                style={{ background: "radial-gradient(circle, var(--piq-mint) 0%, transparent 70%)" }}
                aria-hidden
            />

            <div className="relative mx-auto max-w-7xl px-6 grid grid-cols-12 gap-8 items-center">
                <div className="col-span-12 lg:col-span-7">
                    <motion.div
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5 }}
                        className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-mint/30 bg-mint/10 text-mint text-xs font-mono mb-6"
                    >
                        <span className="w-1.5 h-1.5 rounded-full bg-mint animate-pulse" />
                        QUANT · MARKET MICROSTRUCTURE · LIVE
                    </motion.div>

                    <motion.h1
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className="font-display font-bold text-5xl md:text-7xl leading-[1.02] text-foreground"
                    >
                        Uma ferramenta <span className="piq-text-gradient-mint">quant</span>.
                        <br />
                        Não um bot de palpite.
                    </motion.h1>

                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.2 }}
                        className="mt-6 text-lg text-muted-foreground max-w-xl leading-relaxed"
                    >
                        PressureIQ captura a curva inteira do mercado em tempo real, modela o
                        pricing das linhas e identifica janelas onde a precificação está mal feita.
                        Dataset proprietário, anti-bot genuíno, histórico auditável.
                        <span className="block mt-2 text-foreground/80">Sistema entrega o sinal. Decisão é sua.</span>
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.3 }}
                        className="mt-8 flex flex-wrap gap-3"
                    >
                        <motion.button
                            whileHover={{ y: -2 }}
                            whileTap={{ y: 0 }}
                            onClick={() => onOpenAuth("register")}
                            className="group inline-flex items-center gap-2 bg-mint text-primary-foreground font-medium px-6 py-3 rounded-md hover:bg-mint-bright transition piq-glow-mint"
                        >
                            Criar conta
                            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition" />
                        </motion.button>
                        <button
                            onClick={() => onOpenAuth("login")}
                            className="inline-flex items-center gap-2 border border-border text-foreground font-medium px-6 py-3 rounded-md hover:bg-secondary transition"
                        >
                            Já tenho acesso
                        </button>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.6, delay: 0.5 }}
                        className="mt-10 flex flex-wrap gap-6 text-sm text-muted-foreground"
                    >
                        <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-mint" />
                            <span className="font-mono">9 ligas monitoradas</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Bot className="w-4 h-4 text-mint" />
                            <span className="font-mono">24/7 autônomo</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-mint" />
                            <span className="font-mono">histórico auditável</span>
                        </div>
                    </motion.div>
                </div>

                <motion.div
                    initial={{ opacity: 0, x: 30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.7, delay: 0.3 }}
                    className="col-span-12 lg:col-span-5 relative lg:-mr-12"
                >
                    <div className="relative rounded-xl border border-border bg-card/80 backdrop-blur p-5 shadow-2xl">
                        <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
                            <div className="flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-destructive/70" />
                                <span className="w-2.5 h-2.5 rounded-full bg-mint/50" />
                                <span className="w-2.5 h-2.5 rounded-full bg-mint" />
                            </div>
                            <span className="font-mono text-xs text-muted-foreground">live · mispricing detector</span>
                        </div>

                        <div className="space-y-2">
                            {ticks.map((t, i) => (
                                <motion.div
                                    key={t.match}
                                    initial={{ opacity: 0, x: 10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.6 + i * 0.1 }}
                                    className="flex items-center justify-between gap-3 p-2.5 rounded-md bg-secondary/50 hover:bg-secondary transition"
                                >
                                    <div className="min-w-0 flex-1">
                                        <div className="font-mono text-xs text-foreground truncate">{t.match}</div>
                                        <div className="text-[10px] text-muted-foreground truncate">{t.market}</div>
                                    </div>
                                    <div className="font-mono text-xs text-muted-foreground tabular-nums">
                                        <span className="line-through opacity-60">{t.from}</span>
                                        <span className="mx-1">→</span>
                                        <span className="text-foreground">{t.to}</span>
                                    </div>
                                    <div className="font-mono text-xs text-mint tabular-nums">{t.edge}</div>
                                </motion.div>
                            ))}
                        </div>

                        <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs">
                            <span className="font-mono text-muted-foreground">last update</span>
                            <span className="font-mono text-mint flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-mint animate-pulse" />
                                12s ago
                            </span>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
