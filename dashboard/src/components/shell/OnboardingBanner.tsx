"use client";

import { useEffect, useState } from "react";
import { Sparkles, X } from "lucide-react";

const STORAGE_KEY = "piq-onboarding-dismissed";

export function OnboardingBanner() {
    const [closed, setClosed] = useState(true);
    useEffect(() => {
        if (typeof window === "undefined") return;
        setClosed(localStorage.getItem(STORAGE_KEY) === "1");
    }, []);
    if (closed) return null;
    return (
        <div className="relative overflow-hidden rounded-2xl border border-mint/30 bg-gradient-to-r from-mint/10 via-mint/5 to-transparent p-4 piq-in">
            <div className="absolute inset-0 grid-bg opacity-30" />
            <div className="relative flex items-center gap-4">
                <div className="rounded-xl border border-mint/40 bg-mint/10 p-2.5">
                    <Sparkles className="size-5 text-mint-bright" />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="font-display text-sm font-semibold">Bem-vindo ao PressureIQ</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                        Configure suas preferências de estratégia em{" "}
                        <span className="text-mint">Configurações</span> e ative o robô para operar 24/7.
                    </div>
                </div>
                <button
                    onClick={() => {
                        localStorage.setItem(STORAGE_KEY, "1");
                        setClosed(true);
                    }}
                    className="text-muted-foreground hover:text-foreground p-1.5"
                    aria-label="Fechar"
                >
                    <X className="size-4" />
                </button>
            </div>
        </div>
    );
}
