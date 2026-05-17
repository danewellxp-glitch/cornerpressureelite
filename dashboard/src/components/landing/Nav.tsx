"use client";

import { motion } from "framer-motion";
import { Activity } from "lucide-react";

type Props = {
    onOpenAuth: (tab: "login" | "register") => void;
};

export function Nav({ onOpenAuth }: Props) {
    return (
        <header className="fixed top-0 inset-x-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
            <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
                <a href="#top" className="flex items-center gap-2 group">
                    <div className="w-8 h-8 rounded-md bg-mint/15 border border-mint/40 grid place-items-center group-hover:bg-mint/25 transition">
                        <Activity className="w-4 h-4 text-mint" strokeWidth={2.5} />
                    </div>
                    <span className="font-display font-bold tracking-tight text-foreground">
                        PressureIQ
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground px-1.5 py-0.5 border border-border rounded">
                        CPES
                    </span>
                </a>

                <nav className="hidden md:flex items-center gap-8 text-sm text-muted-foreground">
                    <a href="#features" className="hover:text-foreground transition">Features</a>
                    <a href="#vision" className="hover:text-foreground transition">Visão</a>
                    <a href="#pricing" className="hover:text-foreground transition">Pricing</a>
                </nav>

                <div className="flex items-center gap-2">
                    <button
                        onClick={() => onOpenAuth("login")}
                        className="text-sm text-muted-foreground hover:text-foreground transition px-3 py-2"
                    >
                        Entrar
                    </button>
                    <motion.button
                        whileHover={{ y: -1 }}
                        whileTap={{ y: 0 }}
                        onClick={() => onOpenAuth("register")}
                        className="text-sm font-medium bg-mint text-primary-foreground px-4 py-2 rounded-md hover:bg-mint-bright transition"
                    >
                        Começar
                    </motion.button>
                </div>
            </div>
        </header>
    );
}
