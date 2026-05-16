import Link from "next/link";

const COLS = [
  {
    title: "PRODUTO",
    links: [
      { href: "#pilares", label: "Diferenciais" },
      { href: "#how", label: "Como funciona" },
      { href: "#pricing", label: "Planos" },
      { href: "#faq", label: "FAQ" },
    ],
  },
  {
    title: "EMPRESA",
    links: [
      { href: "/sobre", label: "Sobre" },
      { href: "/blog", label: "Blog" },
      { href: "/contato", label: "Contato" },
      { href: "/carreiras", label: "Carreiras" },
    ],
  },
  {
    title: "LEGAL",
    links: [
      { href: "/legal/termos", label: "Termos de uso" },
      { href: "/legal/privacidade", label: "Privacidade" },
      { href: "/legal/lgpd", label: "LGPD" },
      { href: "/legal/jogo-responsavel", label: "Jogo responsável" },
    ],
  },
] as const;

export function Footer() {
  return (
    <footer className="mx-auto max-w-[1280px] px-8 pb-10 pt-15">
      <div className="grid grid-cols-1 gap-12 border-b border-[var(--border)] pb-12 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr]">
        <div>
          <Link href="/" className="flex items-center gap-2.5 font-mono text-[15px] font-bold">
            <span className="relative flex h-7 w-7 items-center justify-center rounded-md bg-[var(--green)] text-[var(--bg)] font-extrabold">
              ⚡
              <span
                className="absolute inset-0 -z-10 rounded-md bg-[var(--green)] opacity-50 blur-[12px]"
                aria-hidden="true"
              />
            </span>
            <span className="text-[var(--text)]">PressureIQ</span>
          </Link>
          <p className="mt-4 max-w-[280px] text-[13px] leading-relaxed text-[var(--text-muted)]">
            A ciência por trás do green. Análise quantitativa de mercado esportivo
            em tempo real.
          </p>
        </div>

        {COLS.map((col) => (
          <div key={col.title}>
            <h5 className="mb-4 font-mono text-[10px] uppercase tracking-widest text-[var(--text-dim)]">
              {col.title}
            </h5>
            {col.links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="block py-1.5 text-[13px] text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
              >
                {link.label}
              </Link>
            ))}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-start justify-between gap-6 pt-8">
        <div className="text-[12px] text-[var(--text-dim)]">
          © 2026 PressureIQ. Todos os direitos reservados.
        </div>
        <p className="max-w-[600px] font-mono text-[11px] leading-relaxed text-[var(--text-dim)]">
          Apostas envolvem risco. Permitido apenas maiores de 18 anos. Resultados
          passados não garantem resultados futuros. PressureIQ é ferramenta de análise
          — decisões e responsabilidades de aposta são suas. Se você ou alguém
          próximo tem problema com jogo, procure ajuda.
        </p>
      </div>
    </footer>
  );
}
