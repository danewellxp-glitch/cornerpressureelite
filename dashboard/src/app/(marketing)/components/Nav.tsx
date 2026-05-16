"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

const LINKS = [
  { href: "#pilares", label: "Diferenciais" },
  { href: "#how", label: "Como Funciona" },
  { href: "#pricing", label: "Planos" },
  { href: "#faq", label: "FAQ" },
] as const;

export function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/70 py-4 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1280px] items-center justify-between px-8">
        <Link href="/" className="flex items-center gap-2.5 font-mono text-[15px] font-bold tracking-tight">
          <span
            className="relative flex h-7 w-7 items-center justify-center rounded-md bg-[var(--green)] text-[var(--bg)] font-extrabold"
            aria-hidden="true"
          >
            ⚡
            <span
              className="absolute inset-0 -z-10 rounded-md bg-[var(--green)] opacity-50 blur-[12px]"
              aria-hidden="true"
            />
          </span>
          <span className="text-[var(--text)]">PressureIQ</span>
          <span className="rounded bg-[var(--border)] px-1.5 py-0.5 text-[10px] font-medium tracking-wider text-[var(--text-muted)]">
            CPES
          </span>
        </Link>

        <div className="hidden gap-8 text-[13px] font-medium md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <Link
            href="/login"
            className="rounded-md px-4 py-2 text-[13px] font-semibold text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
          >
            Entrar
          </Link>
          <Link
            href="/register"
            className="group relative inline-flex items-center gap-2 overflow-hidden rounded-md bg-[var(--green)] px-4 py-2 text-[13px] font-semibold text-[var(--bg)] transition-all hover:-translate-y-px"
            style={{ boxShadow: "0 0 0 transparent" }}
          >
            <span className="pointer-events-none absolute inset-0 bg-[var(--green-bright)] opacity-0 transition-opacity group-hover:opacity-100" />
            <span className="relative z-10">Começar</span>
          </Link>
        </div>

        <button
          aria-label={open ? "Fechar menu" : "Abrir menu"}
          onClick={() => setOpen((v) => !v)}
          className="text-[var(--text)] md:hidden"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open && (
        <div className="border-t border-[var(--border)] bg-[var(--bg)] md:hidden">
          <div className="flex flex-col gap-1 px-8 py-4">
            {LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="py-2 text-[14px] text-[var(--text-muted)] hover:text-[var(--text)]"
              >
                {link.label}
              </a>
            ))}
            <div className="mt-2 flex gap-3 border-t border-[var(--border)] pt-4">
              <Link
                href="/login"
                className="flex-1 rounded-md border border-[var(--border-bright)] px-4 py-2 text-center text-[13px] font-semibold text-[var(--text)]"
              >
                Entrar
              </Link>
              <Link
                href="/register"
                className="flex-1 rounded-md bg-[var(--green)] px-4 py-2 text-center text-[13px] font-semibold text-[var(--bg)]"
              >
                Começar
              </Link>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
