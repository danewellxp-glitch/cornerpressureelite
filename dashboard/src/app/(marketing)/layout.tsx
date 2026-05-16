import type { ReactNode } from "react";
import { Nav } from "./components/Nav";
import { Ticker } from "./components/Ticker";
import { Footer } from "./components/Footer";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      {/* Ticker é Server Component: revalida a cada 60s */}
      <Ticker />
      <Nav />
      <main>{children}</main>
      <Footer />
    </>
  );
}
