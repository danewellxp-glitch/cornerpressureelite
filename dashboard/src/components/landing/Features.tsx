"use client";

import { motion } from "framer-motion";
import {
    Bot,
    LineChart,
    ShieldCheck,
    Activity,
    History,
    UserCog,
    type LucideIcon,
} from "lucide-react";

type Pillar = {
    icon: LucideIcon;
    tag: string;
    title: string;
    headline: string;
    description: string;
};

const pillars: Pillar[] = [
    {
        icon: Bot,
        tag: "PILAR 01",
        title: "Sistema autônomo 24/7",
        headline: "Funciona sem você. Trabalha enquanto você dorme.",
        description:
            "Descobre jogos sozinho, captura odds em tempo real, analisa pressão minuto a minuto. Pool distribuído de Chromes + failover automático. Você só recebe o sinal pronto no WhatsApp.",
    },
    {
        icon: LineChart,
        tag: "PILAR 02",
        title: "Captura quant de mercado",
        headline: "Não capturamos só odd. Capturamos a curva inteira do mercado.",
        description:
            "Catálogo COMPLETO de cada mercado (5–8 linhas por jogo), com timestamp, minuto, placar e score de pressão persistidos. Você vê a linha 9.5 cair pra 7.5 enquanto o ritmo do jogo muda.",
    },
    {
        icon: ShieldCheck,
        tag: "PILAR 03",
        title: "Anti-bot genuíno",
        headline: "Não tentamos enganar a casa. Somos um usuário real.",
        description:
            "Chrome stable real (não headless mascarado), em IP residencial brasileiro autêntico via proxy dedicado. Não dependemos de APIs piratas que param de funcionar — sobrevivemos a updates de anti-bot.",
    },
    {
        icon: Activity,
        tag: "PILAR 04",
        title: "Inteligência de pressão",
        headline: "Sinal só sai quando os dados mostram confluência — não quando \"parece bom\".",
        description:
            "Pressure Score (escanteios) + Tension Score (cartões) compostos de pressão ofensiva, ritmo de cartões, faltas, posse e contexto do placar. Política de linha 1.50–1.70 — odd realista, sem isca.",
    },
    {
        icon: History,
        tag: "PILAR 05",
        title: "Rastreabilidade total",
        headline: "Você vê POR QUE o sinal saiu. E ROI auditável.",
        description:
            "Cada sinal carrega o estado completo do jogo no momento (minuto, placar, score, evolução da linha). Histórico fica disponível pra sempre no dashboard — sem tipster sumindo com resultados ruins.",
    },
    {
        icon: UserCog,
        tag: "PILAR 06 · MAX",
        title: "Controle total do cliente",
        headline: "Co-piloto, não autopiloto. Você decide. Sistema entrega.",
        description:
            "Aprove, customize ou recuse cada sinal. Banca rastreada com ROI individual real baseado na SUA execução, não na sugestão. Robô apostador disponível quando quiser delegar.",
    },
];

export function Features() {
    return (
        <section id="features" className="relative py-24 border-t border-border">
            <div className="mx-auto max-w-7xl px-6">
                <div className="max-w-2xl mb-14">
                    <div className="font-mono text-xs text-mint mb-3">// OS 6 PILARES</div>
                    <h2 className="font-display text-4xl md:text-5xl font-bold text-foreground">
                        Infraestrutura quant. Cada claim verificável.
                    </h2>
                    <p className="mt-4 text-muted-foreground text-lg">
                        Vendemos o que o sistema FAZ hoje — não promessa futura.
                        Cada pilar abaixo tem base técnica em produção, documentada e auditável.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border rounded-xl overflow-hidden">
                    {pillars.map((p, i) => {
                        const Icon = p.icon;
                        return (
                            <motion.div
                                key={p.title}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-50px" }}
                                transition={{ duration: 0.4, delay: i * 0.05 }}
                                className="group bg-card p-7 hover:bg-secondary/50 transition relative"
                            >
                                <div className="flex items-start justify-between mb-5">
                                    <div className="w-11 h-11 rounded-lg bg-mint/10 border border-mint/30 grid place-items-center group-hover:bg-mint/20 transition">
                                        <Icon className="w-5 h-5 text-mint" strokeWidth={2} />
                                    </div>
                                    <span className="font-mono text-[10px] text-muted-foreground border border-border px-1.5 py-0.5 rounded">
                                        {p.tag}
                                    </span>
                                </div>
                                <h3 className="font-display font-semibold text-lg text-foreground mb-1.5">
                                    {p.title}
                                </h3>
                                <p className="text-xs text-mint-bright italic mb-3 leading-snug">
                                    &ldquo;{p.headline}&rdquo;
                                </p>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {p.description}
                                </p>
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
