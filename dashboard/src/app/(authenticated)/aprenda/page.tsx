"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
    BookOpen,
    TrendingUp,
    Activity,
    Target,
    Lightbulb,
    ArrowRight,
    Loader2,
} from "lucide-react";
import { fetchSignalsList, type SignalDetail } from "@/lib/api";

type Insight = { title: string; body: string };

export default function AprendaPage() {
    const [signals, setSignals] = useState<SignalDetail[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        fetchSignalsList("all", 2000)
            .then((l) => !cancelled && setSignals(l))
            .catch(() => {})
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, []);

    const insights: Insight[] = useMemo(() => buildInsights(signals), [signals]);

    return (
        <div className="space-y-8 max-w-[1100px] mx-auto">
            <header>
                <div className="font-mono text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
                    Conhecimento de mercado
                </div>
                <h1 className="font-display text-2xl font-bold mt-1">Aprenda</h1>
                <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                    Como o sistema pensa, o que cada métrica significa, e padrões reais do
                    histórico dos seus sinais.
                </p>
            </header>

            {/* Insights computados do dataset real */}
            <section>
                <div className="flex items-center gap-2 mb-4">
                    <Lightbulb className="size-4 text-mint-bright" />
                    <h2 className="font-display text-lg font-semibold">Padrões do seu histórico</h2>
                </div>
                {loading ? (
                    <div className="rounded-2xl border border-border bg-card p-8 text-center text-muted-foreground">
                        <Loader2 className="size-5 animate-spin mx-auto" />
                        <span className="font-mono text-xs tracking-wider mt-2 block">CARREGANDO PADRÕES…</span>
                    </div>
                ) : insights.length === 0 ? (
                    <div className="rounded-2xl border border-border bg-card p-8 text-center">
                        <p className="text-sm text-muted-foreground">
                            Ainda não há sinais decididos suficientes pra extrair padrões.
                            <br />
                            Os primeiros insights aparecem quando o sistema acumula ~20 GREEN/RED.
                        </p>
                    </div>
                ) : (
                    <div className="grid gap-3 md:grid-cols-2">
                        {insights.map((i, idx) => (
                            <div key={idx} className="rounded-xl border border-mint/30 bg-mint/5 p-4">
                                <h3 className="font-display text-sm font-semibold text-mint-bright mb-1">
                                    {i.title}
                                </h3>
                                <p className="text-sm text-foreground/90">{i.body}</p>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            {/* Glossário */}
            <section>
                <div className="flex items-center gap-2 mb-4">
                    <BookOpen className="size-4 text-mint-bright" />
                    <h2 className="font-display text-lg font-semibold">Glossário</h2>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                    <Card
                        icon={Activity}
                        title="Pressure Score"
                        body="Pontuação 0–100 do quanto o jogo está 'pressionando' por mais escanteios. Combina escanteios recentes, ataques perigosos, posse no campo ofensivo e finalizações. Acima de 6 = sinal Normal; acima de 8 = Premium."
                    />
                    <Card
                        icon={Activity}
                        title="Tension Score"
                        body="Pontuação equivalente pra cartões amarelos: tensão do jogo somada a faltas recentes, ritmo de cartões e contexto do placar. Acima de 5 = Normal; acima de 8 = Premium."
                    />
                    <Card
                        icon={TrendingUp}
                        title="Edge"
                        body="Diferença entre a projeção do sistema e a linha da casa de apostas. Edge ≥ 1.2 significa: o sistema espera ao menos 1.2 escanteios a mais do que a linha. Quanto maior, maior o valor esperado."
                    />
                    <Card
                        icon={Target}
                        title="Linha asiática"
                        body="A linha que a casa oferece (ex: +6.5 escanteios). 'Mais' (over) ganha se o total final for maior que a linha. Linhas com .5 não admitem empate."
                    />
                    <Card
                        icon={TrendingUp}
                        title="ROI (%)"
                        body="Retorno sobre investimento: lucro líquido / total apostado × 100. ROI +10% em 100 apostas de R$ 10 = R$ 100 de lucro. Resultados passados não garantem resultados futuros."
                    />
                    <Card
                        icon={Target}
                        title="Win rate"
                        body="% de apostas decididas que viraram GREEN. Win rate alto não significa lucro: depende da odd média. 55% de win rate com odds 1.80 já é lucrativo no longo prazo."
                    />
                </div>
            </section>

            {/* Como o sistema decide */}
            <section className="rounded-2xl border border-border bg-card p-6">
                <h2 className="font-display text-lg font-semibold mb-3">Como o sistema decide um sinal</h2>
                <ol className="space-y-3 text-sm">
                    <Step n={1} title="Janela de análise">
                        Cada jogo entra na janela aos minutos 50–90 (escanteios) ou 40+ (cartões),
                        ou antes se já estiver acelerado.
                    </Step>
                    <Step n={2} title="Coleta de stats">
                        O sistema busca estatísticas do jogo (escanteios, ataques, posse, cartões,
                        faltas) na API-Football a cada ciclo de ~60s.
                    </Step>
                    <Step n={3} title="Pré-avaliação">
                        Calcula um score preliminar. Se passa nos filtros mínimos, busca odds da
                        casa (Betano/Bet365) — economia de requisições.
                    </Step>
                    <Step n={4} title="Avaliação completa">
                        Combina score + projeção + edge. Se ultrapassa thresholds (score ≥ 6 normal
                        ou ≥ 8 premium; edge ≥ 1.2), emite sinal.
                    </Step>
                    <Step n={5} title="Notificação">
                        WhatsApp e dashboard. Pra clientes Max em modo manual: vira card pendente
                        em <Link href="/minhas-apostas" className="text-mint hover:text-mint-bright underline underline-offset-2">Minhas Apostas</Link>.
                    </Step>
                    <Step n={6} title="Resultado">
                        ~2h depois do jogo, o sistema busca o resultado final e marca o sinal como
                        GREEN ou RED, atualizando ROI e banca.
                    </Step>
                </ol>
            </section>

            <div className="grid gap-3 md:grid-cols-3">
                <CTA href="/jogos-ao-vivo" icon={Activity} label="Ver jogos ao vivo" />
                <CTA href="/performance" icon={TrendingUp} label="Analisar performance" />
                <CTA href="/sinais-historico" icon={BookOpen} label="Ver histórico de sinais" />
            </div>
        </div>
    );
}

function Card({
    icon: Icon,
    title,
    body,
}: {
    icon: React.ComponentType<{ className?: string }>;
    title: string;
    body: string;
}) {
    return (
        <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
                <Icon className="size-4 text-mint" />
                <h3 className="font-display text-sm font-semibold">{title}</h3>
            </div>
            <p className="text-sm text-foreground/85">{body}</p>
        </div>
    );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
    return (
        <li className="flex gap-3">
            <span className="shrink-0 size-7 rounded-full bg-mint/15 border border-mint/40 grid place-items-center font-mono text-xs tabular text-mint-bright font-bold">
                {n}
            </span>
            <div>
                <h4 className="font-display text-sm font-semibold">{title}</h4>
                <p className="text-sm text-muted-foreground mt-0.5">{children}</p>
            </div>
        </li>
    );
}

function CTA({
    href,
    icon: Icon,
    label,
}: {
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
}) {
    return (
        <Link
            href={href}
            className="rounded-xl border border-border bg-card hover:border-mint/40 hover:bg-mint/5 transition p-4 flex items-center justify-between text-sm font-medium"
        >
            <span className="flex items-center gap-2">
                <Icon className="size-4 text-mint-bright" />
                {label}
            </span>
            <ArrowRight className="size-4 text-muted-foreground" />
        </Link>
    );
}

function buildInsights(signals: SignalDetail[]): Insight[] {
    const decided = signals.filter((s) => s.resultado === "GREEN" || s.resultado === "RED");
    if (decided.length < 20) return [];

    const insights: Insight[] = [];

    // Insight 1: PREMIUM vs NORMAL
    const premium = decided.filter((s) => s.tipo_sinal === "PREMIUM");
    const normal = decided.filter((s) => s.tipo_sinal === "NORMAL");
    if (premium.length >= 5 && normal.length >= 5) {
        const premiumWr = (premium.filter((s) => s.resultado === "GREEN").length / premium.length) * 100;
        const normalWr = (normal.filter((s) => s.resultado === "GREEN").length / normal.length) * 100;
        const diff = premiumWr - normalWr;
        if (Math.abs(diff) >= 5) {
            insights.push({
                title: `Sinais PREMIUM ${diff > 0 ? "vencem" : "perdem"} ${Math.abs(diff).toFixed(0)}% mais que NORMAL`,
                body: `Em ${premium.length} PREMIUM (${premiumWr.toFixed(0)}% win) vs ${normal.length} NORMAL (${normalWr.toFixed(0)}% win). ${diff > 0 ? "Tier mais conservador = melhor taxa." : "Tier menos restritivo está performando comparável."}`,
            });
        }
    }

    // Insight 2: melhor liga
    const perLiga = new Map<string, { total: number; g: number }>();
    decided.forEach((s) => {
        const k = s.liga_nome || "—";
        if (!perLiga.has(k)) perLiga.set(k, { total: 0, g: 0 });
        const e = perLiga.get(k)!;
        e.total += 1;
        if (s.resultado === "GREEN") e.g += 1;
    });
    const ligaRanked = Array.from(perLiga.entries())
        .map(([liga, e]) => ({ liga, ...e, wr: (e.g / e.total) * 100 }))
        .filter((e) => e.total >= 5)
        .sort((a, b) => b.wr - a.wr);
    if (ligaRanked.length > 0 && ligaRanked[0].wr >= 55) {
        const top = ligaRanked[0];
        insights.push({
            title: `Melhor liga: ${top.liga}`,
            body: `${top.wr.toFixed(0)}% de win rate em ${top.total} sinais decididos. Foi onde o sistema mais acertou no seu histórico.`,
        });
    }

    // Insight 3: corners vs cards
    const corners = decided.filter((s) => (s.tipo_analise || "ESCANTEIOS").toUpperCase() === "ESCANTEIOS");
    const cards = decided.filter((s) => (s.tipo_analise || "").toUpperCase() === "CARTOES");
    if (corners.length >= 10 && cards.length >= 10) {
        const cornersWr = (corners.filter((s) => s.resultado === "GREEN").length / corners.length) * 100;
        const cardsWr = (cards.filter((s) => s.resultado === "GREEN").length / cards.length) * 100;
        insights.push({
            title: "Escanteios vs Cartões",
            body: `Escanteios: ${cornersWr.toFixed(0)}% wr em ${corners.length}. Cartões: ${cardsWr.toFixed(0)}% wr em ${cards.length}. ${cornersWr > cardsWr ? "Escanteios performa melhor" : "Cartões performa melhor"} no seu dataset.`,
        });
    }

    // Insight 4: ROI total real
    const totalRoi = decided.reduce((acc, s) => {
        if (s.resultado === "GREEN") return acc + ((s.odd ?? 1) - 1);
        return acc - 1;
    }, 0);
    const roiPct = (totalRoi / decided.length) * 100;
    insights.push({
        title: `ROI histórico: ${roiPct >= 0 ? "+" : ""}${roiPct.toFixed(1)}%`,
        body: `Em ${decided.length} apostas decididas (1u cada), o sistema acumulou ${totalRoi >= 0 ? "+" : ""}${totalRoi.toFixed(2)}u. Use isso como benchmark — não é garantia de futuro.`,
    });

    return insights;
}
