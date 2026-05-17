import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import EstrategiaPanel from "@/components/estrategia/EstrategiaPanel";

const API_BASE = process.env.CPES_API_URL || "http://api:8000";

type UsersMeResponse = {
    user?: { id?: number; role?: string };
    subscription?: { plan?: string };
};

export default async function EstrategiaPage() {
    const cookieStore = await cookies();
    const token = cookieStore.get("cpes-auth")?.value;
    if (!token) redirect("/login");

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
        redirect("/settings?upsell=estrategia");
    }

    return <EstrategiaPanel />;
}
