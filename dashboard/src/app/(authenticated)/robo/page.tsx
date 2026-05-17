import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import RoboPanel from "@/components/robo/RoboPanel";

const API_BASE = process.env.CPES_API_URL || "http://api:8000";

type UsersMeResponse = {
    user?: { id?: number; role?: string; full_name?: string; email?: string };
    subscription?: { valid?: boolean; plan?: string };
};

type BotConfig = {
    enabled: boolean;
    mode: string;
    bet_house: string | null;
    banca_inicial_cents: number;
    banca_atual_cents: number;
    max_loss_per_day_cents: number;
    max_bets_per_day: number;
    unit_pct: number;
    allowed_leagues: number[];
    allowed_markets: string[];
    kill_switch: boolean;
    real_mode_unlocked: boolean;
    accepted_tos_at: string | null;
};

export default async function RoboPage() {
    const cookieStore = await cookies();
    const token = cookieStore.get("cpes-auth")?.value;
    if (!token) redirect("/login");

    // Buscar user/me — server gate
    let me: UsersMeResponse | null = null;
    try {
        const res = await fetch(`${API_BASE}/api/users/me`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
        });
        if (!res.ok) redirect("/login");
        me = await res.json();
    } catch {
        redirect("/login");
    }

    const isAdmin = me?.user?.role === "admin";
    const plan = me?.subscription?.plan ?? "free";
    if (!isAdmin && plan !== "max") {
        redirect("/settings?upsell=robo");
    }

    // Carrega bot_config server-side pra evitar flash de empty state
    let config: BotConfig | null = null;
    try {
        const res = await fetch(`${API_BASE}/api/bot/config`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
        });
        if (res.ok) {
            config = await res.json();
        }
    } catch {
        // ignora — client fará fallback fetch
    }

    return (
        <RoboPanel
            initialConfig={config}
            userName={me?.user?.full_name || me?.user?.email || ""}
        />
    );
}
