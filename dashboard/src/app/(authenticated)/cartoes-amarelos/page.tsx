import type { Metadata } from "next";
import { MarketPage } from "@/components/markets/MarketPage";

export const metadata: Metadata = { title: "Cartões Amarelos — PressureIQ" };

export default function CartoesAmarelosPage() {
    return (
        <MarketPage
            market="cards"
            title="Cartões Amarelos"
            subtitle="Sinais de pressão para Over de cartões, com tiers calibrados para volume vs. confiança e jogos em campo."
        />
    );
}
