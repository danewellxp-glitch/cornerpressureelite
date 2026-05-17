"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
    LayoutDashboard,
    Flag,
    Square,
    History,
    Bot,
    Settings,
    Terminal,
    LogOut,
    ChevronsLeft,
    ChevronsRight,
    Radio,
    TrendingUp,
    BookOpen,
    CheckCheck,
    Wallet,
    Target,
} from "lucide-react";
import { cn } from "@/lib/format";
import { logout } from "@/lib/api";

type Plan = "admin" | "max" | "pro" | "free";

type NavItem = {
    label: string;
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: "BETA" | "MAX";
    requiresMax?: boolean;
    adminOnly?: boolean;
};

const NAV: NavItem[] = [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "Jogos ao vivo", href: "/jogos-ao-vivo", icon: Radio },
    { label: "Escanteios", href: "/escanteios", icon: Flag },
    { label: "Cartões Amarelos", href: "/cartoes-amarelos", icon: Square },
    { label: "Histórico Sinais", href: "/sinais-historico", icon: History },
    { label: "Performance", href: "/performance", icon: TrendingUp },
    { label: "Aprenda", href: "/aprenda", icon: BookOpen },
    { label: "Minhas Apostas", href: "/minhas-apostas", icon: CheckCheck, badge: "MAX", requiresMax: true },
    { label: "Banca", href: "/banca", icon: Wallet, badge: "MAX", requiresMax: true },
    { label: "Robô", href: "/robo", icon: Bot, badge: "BETA", requiresMax: true },
    { label: "Estratégia", href: "/estrategia", icon: Target, badge: "MAX", requiresMax: true },
    { label: "Configurações", href: "/settings", icon: Settings },
    { label: "Logs", href: "/logs", icon: Terminal, adminOnly: true },
];

const PLAN_STYLES: Record<Plan, string> = {
    admin: "text-success border-success/40 bg-success/10",
    max: "text-mint-bright border-mint-bright/40 bg-mint-bright/10",
    pro: "text-sky-300 border-sky-300/40 bg-sky-300/10",
    free: "text-muted-foreground border-border bg-muted/40",
};

export function SideNav({
    open,
    onToggle,
    plan,
    userName,
}: {
    open: boolean;
    onToggle: () => void;
    plan: Plan;
    userName: string;
}) {
    const pathname = usePathname() || "";

    async function handleLogout() {
        await logout();
        document.cookie = "cpes-auth=; path=/; max-age=0";
        window.location.href = "/login";
    }

    return (
        <aside
            className={cn(
                "relative h-screen sticky top-0 flex flex-col border-r border-border bg-card/40 backdrop-blur-xl transition-[width] duration-300 shrink-0",
                open ? "w-[260px]" : "w-[72px]",
            )}
        >
            <div className="flex flex-col items-center gap-3 px-4 pt-5 pb-4">
                <div className="relative w-full flex items-center justify-between">
                    {open && (
                        <span className="font-display text-xs uppercase tracking-[0.18em] text-mint-bright/80">
                            PressureIQ
                        </span>
                    )}
                    <button
                        onClick={onToggle}
                        aria-label={open ? "Recolher" : "Expandir"}
                        className="ml-auto p-1.5 rounded-md text-muted-foreground hover:text-mint hover:bg-mint/10 transition"
                    >
                        {open ? <ChevronsLeft className="size-4" /> : <ChevronsRight className="size-4" />}
                    </button>
                </div>

                <div
                    className={cn(
                        "relative flex items-center justify-center rounded-2xl border border-mint/30 bg-gradient-to-br from-mint/15 to-transparent overflow-hidden",
                        open ? "w-full h-28" : "w-12 h-12",
                    )}
                >
                    <div className="absolute inset-0 grid-bg opacity-50" />
                    <div className="relative font-display font-bold text-mint-bright tabular text-2xl">
                        CPES
                    </div>
                    {open && (
                        <div className="absolute bottom-2 left-0 right-0 text-center font-mono text-[9px] tracking-[0.2em] text-mint/70">
                            CORNER · CARD · ELITE
                        </div>
                    )}
                </div>

                {open && (
                    <div className="flex flex-col items-center gap-1.5 w-full">
                        <span
                            className={cn(
                                "font-mono text-[10px] tracking-[0.18em] px-2 py-0.5 rounded-full border",
                                PLAN_STYLES[plan],
                            )}
                        >
                            {plan.toUpperCase()}
                        </span>
                        {userName && (
                            <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                                {userName}
                            </span>
                        )}
                    </div>
                )}
            </div>

            <div className="h-px bg-border mx-3" />

            <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
                {NAV.filter((item) => !item.adminOnly || plan === "admin").map((item) => {
                    const active = pathname === item.href;
                    const Icon = item.icon;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                                active
                                    ? "text-foreground"
                                    : "text-muted-foreground hover:text-foreground hover:bg-mint/5",
                                !open && "justify-center px-2",
                            )}
                            title={!open ? item.label : undefined}
                        >
                            {active && (
                                <motion.span
                                    layoutId="nav-pill"
                                    transition={{ type: "spring", stiffness: 500, damping: 36 }}
                                    className="absolute inset-0 rounded-xl bg-mint/10 border border-mint/40"
                                />
                            )}
                            <Icon
                                className={cn(
                                    "size-4 relative z-10 transition-colors",
                                    active ? "text-mint-bright" : "group-hover:text-mint",
                                )}
                            />
                            {open && (
                                <>
                                    <span
                                        className={cn(
                                            "relative z-10 flex-1 truncate",
                                            active ? "font-semibold text-foreground" : "",
                                        )}
                                    >
                                        {item.label}
                                    </span>
                                    {item.badge && (
                                        <span
                                            className={cn(
                                                "relative z-10 font-mono text-[9px] tracking-wider px-1.5 py-0.5 rounded-full border",
                                                item.badge === "MAX"
                                                    ? "border-mint-bright/40 text-mint-bright bg-mint-bright/10"
                                                    : "border-warning/40 text-warning bg-warning/10",
                                            )}
                                        >
                                            {item.badge}
                                        </span>
                                    )}
                                </>
                            )}
                        </Link>
                    );
                })}
            </nav>

            <div className="h-px bg-border mx-3" />

            <div className="p-2">
                <button
                    onClick={handleLogout}
                    className={cn(
                        "w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition",
                        !open && "justify-center px-2",
                    )}
                    title={!open ? "Sair" : undefined}
                >
                    <LogOut className="size-4" />
                    {open && <span>Sair</span>}
                </button>
            </div>
        </aside>
    );
}
