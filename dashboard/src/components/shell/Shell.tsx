"use client";

import { useState, useEffect, createContext, useContext } from "react";
import { ThemeProvider, CssBaseline } from "@mui/material";
import theme from "@/lib/theme";
import { SideNav } from "./SideNav";
import { Topbar } from "./Topbar";
import { useDashboardStream, type ConnectionStatus } from "@/lib/useDashboardStream";
import type { DashboardData } from "@/lib/api";

type Plan = "admin" | "max" | "pro" | "free";

export interface ShellUser {
    plan: Plan;
    userId: number | null;
    userName: string;
    isAdmin: boolean;
    subscriptionStartedAt: string | null;
}

export interface DashboardStreamContextValue {
    data: DashboardData | null;
    status: ConnectionStatus;
    lastUpdate: Date | null;
    reconnect: () => void;
}

const ShellUserCtx = createContext<ShellUser | null>(null);
const DashboardStreamCtx = createContext<DashboardStreamContextValue | null>(null);

export function useShellUser(): ShellUser {
    const ctx = useContext(ShellUserCtx);
    if (!ctx) throw new Error("useShellUser must be used within <Shell>");
    return ctx;
}

export function useDashboard(): DashboardStreamContextValue {
    const ctx = useContext(DashboardStreamCtx);
    if (!ctx) throw new Error("useDashboard must be used within <Shell>");
    return ctx;
}

export function Shell({
    plan,
    userId,
    userName,
    isAdmin,
    subscriptionStartedAt,
    token,
    children,
}: ShellUser & { token: string | null; children: React.ReactNode }) {
    const [open, setOpen] = useState(true);

    // Sincroniza o JWT do cookie (lido server-side no layout) pro localStorage.
    // useDashboardStream le de localStorage. Fallback pra sessoes que entraram
    // via cookie antigo sem passar pelo login novo (que ja popula localStorage).
    useEffect(() => {
        if (token && typeof window !== "undefined" && !localStorage.getItem("token")) {
            localStorage.setItem("token", token);
        }
    }, [token]);

    const stream = useDashboardStream();

    return (
        // ThemeProvider preserva paleta MUI pras páginas que ainda usam MUI (Robo).
        // Páginas redesenhadas em Tailwind ignoram o tema MUI (usam classes diretas).
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <ShellUserCtx.Provider value={{ plan, userId, userName, isAdmin, subscriptionStartedAt }}>
                <DashboardStreamCtx.Provider value={stream}>
                    <div className="piq-dashboard flex min-h-screen bg-background text-foreground font-sans">
                        <SideNav
                            open={open}
                            onToggle={() => setOpen((o) => !o)}
                            plan={plan}
                            userName={userName}
                        />
                        <div className="flex-1 min-w-0 flex flex-col">
                            <Topbar
                                status={stream.status}
                                lastUpdate={stream.lastUpdate}
                                onReconnect={stream.reconnect}
                            />
                            <main className="flex-1 px-6 py-6">{children}</main>
                        </div>
                    </div>
                </DashboardStreamCtx.Provider>
            </ShellUserCtx.Provider>
        </ThemeProvider>
    );
}
