import type { Metadata } from "next";
import { Geist, JetBrains_Mono, Bricolage_Grotesque } from "next/font/google";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
  display: "swap",
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
  weight: ["300", "400", "500", "600", "700", "800"],
});

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "PressureIQ — A Ciência por Trás do Green",
  description:
    "Algoritmos proprietários analisam pressão de jogo em tempo real e entregam sinais de alta probabilidade no WhatsApp. Análise quantitativa de escanteios, cartões e gols.",
  metadataBase: new URL("https://iqpressure.online"),
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/brand/logo-mark.png", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    title: "PressureIQ — A Ciência por Trás do Green",
    description:
      "Sinais ao vivo de escanteios, cartões e gols com a inteligência que o mercado profissional usa.",
    images: [
      { url: "/brand/og-image.png", width: 1200, height: 630, alt: "PressureIQ" },
    ],
    type: "website",
    locale: "pt_BR",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      className={`${geist.variable} ${jetbrainsMono.variable} ${bricolage.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
