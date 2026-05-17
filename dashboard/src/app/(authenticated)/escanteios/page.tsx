import type { Metadata } from "next";
import { MarketPage } from "@/components/markets/MarketPage";

export const metadata: Metadata = { title: "Escanteios — PressureIQ" };

export default function EscanteiosPage() {
    return (
        <MarketPage
            market="corners"
            title="Escanteios"
            subtitle="Sinais de pressão para Over de escanteios, segmentados por tier de risco. Auditoria por jogo, edge esperado e linha de mercado."
        />
    );
}
