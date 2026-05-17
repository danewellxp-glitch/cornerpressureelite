"use client";

import { usePathname } from "next/navigation";
import { ConnectionStatus } from "./ConnectionStatus";
import { PauseNotifications } from "./PauseNotifications";
import type { ConnectionStatus as ConnState } from "@/lib/useDashboardStream";

const TITLES: Record<string, { title: string; sub?: string }> = {
    "/dashboard": { title: "Dashboard", sub: "Visão geral em tempo real" },
    "/escanteios": { title: "Escanteios", sub: "Estratégia de pressão de escanteios" },
    "/cartoes-amarelos": { title: "Cartões Amarelos", sub: "Pressão disciplinar por minuto" },
    "/sinais-historico": { title: "Histórico de Sinais", sub: "Auditoria completa" },
    "/robo": { title: "Robô Auto-Aposta", sub: "Operação automatizada" },
    "/settings": { title: "Configurações", sub: "Conta e preferências" },
    "/logs": { title: "Logs", sub: "Stream do motor em tempo real" },
};

export function Topbar({
    status,
    lastUpdate,
    onReconnect,
}: {
    status?: ConnState;
    lastUpdate?: Date | null;
    onReconnect?: () => void;
}) {
    const pathname = usePathname() || "";
    const t = TITLES[pathname] ?? { title: "PressureIQ" };
    return (
        <header className="sticky top-0 z-20 backdrop-blur-xl bg-background/70 border-b border-border">
            <div className="flex items-center justify-between px-6 py-4">
                <div>
                    <h1 className="font-display text-xl font-semibold tracking-tight">{t.title}</h1>
                    {t.sub && (
                        <p className="text-xs text-muted-foreground mt-0.5">{t.sub}</p>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    <ConnectionStatus status={status} lastUpdate={lastUpdate} onReconnect={onReconnect} />
                    <PauseNotifications />
                </div>
            </div>
        </header>
    );
}
