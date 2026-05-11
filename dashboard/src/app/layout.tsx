import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PressureIQ - Inteligência de Pressão de Jogo",
  description: "Sistema avançado de análise de escanteios e cartões com IA",
  metadataBase: new URL("https://odontoschultz.online"),
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/brand/logo-mark.png", type: "image/png" },
    ],
    apple: [
      { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
  openGraph: {
    title: "PressureIQ — Corner & Card Pressure Elite",
    description: "Sinais ao vivo de escanteios e cartões com IA, direto no WhatsApp.",
    images: [
      { url: "/brand/og-image.png", width: 1200, height: 630, alt: "PressureIQ" },
    ],
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
