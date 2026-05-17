import { Activity, AlertTriangle } from "lucide-react";

export function Footer() {
    return (
        <footer className="border-t border-border">
            <div className="mx-auto max-w-7xl px-6 py-12 grid gap-10 md:grid-cols-3 items-start">
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-md bg-mint/15 border border-mint/40 grid place-items-center">
                            <Activity className="w-3.5 h-3.5 text-mint" strokeWidth={2.5} />
                        </div>
                        <span className="font-display font-bold text-foreground">PressureIQ</span>
                        <span className="font-mono text-[10px] text-muted-foreground">CPES</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                        Ferramenta de análise quantitativa para mercados de Escanteios,
                        Cartões e Gols. Vendemos o que o sistema faz hoje — não promessa futura.
                    </p>
                </div>

                <div className="space-y-3">
                    <h4 className="font-mono text-[10px] tracking-wider text-mint uppercase">
                        // Compliance
                    </h4>
                    <ul className="text-xs text-muted-foreground space-y-1.5 leading-relaxed">
                        <li>Permitido apenas para maiores de 18 anos.</li>
                        <li>Apostas envolvem risco. Aposte com responsabilidade.</li>
                        <li>Resultados passados não garantem resultados futuros.</li>
                        <li>PressureIQ é ferramenta de análise — decisão e responsabilidade são suas.</li>
                    </ul>
                </div>

                <div className="space-y-3">
                    <h4 className="font-mono text-[10px] tracking-wider text-mint uppercase">
                        // Ajuda
                    </h4>
                    <div className="flex items-start gap-2 text-xs text-muted-foreground leading-relaxed">
                        <AlertTriangle className="w-3.5 h-3.5 text-warning shrink-0 mt-0.5" />
                        <p>
                            Tem problema com jogo? Procure ajuda no{" "}
                            <a
                                href="https://www.jogadoresanonimos.com.br/"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-mint-bright hover:underline"
                            >
                                Jogadores Anônimos
                            </a>{" "}
                            ou ligue 188 (CVV).
                        </p>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                        Cancelamento a qualquer momento. Reembolso em 7 dias.
                        Dados privados conforme LGPD.
                    </p>
                </div>
            </div>

            <div className="border-t border-border">
                <div className="mx-auto max-w-7xl px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-muted-foreground font-mono">
                    <span>© {new Date().getFullYear()} PressureIQ · CPES</span>
                    <span>iqpressure.online</span>
                </div>
            </div>
        </footer>
    );
}
