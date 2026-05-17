import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Shell } from "@/components/shell/Shell";

const API_BASE = process.env.CPES_API_URL || "http://api:8000";

export default async function AuthenticatedLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const cookieStore = await cookies();
    const token = cookieStore.get("cpes-auth")?.value;

    if (!token) redirect("/login");

    let payload:
        | {
              user?: { id?: number; role?: string; full_name?: string; email?: string };
              subscription?: { valid?: boolean; plan?: string; starts_at?: string | null };
          }
        | null = null;
    try {
        const res = await fetch(`${API_BASE}/api/users/me`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
        });
        if (!res.ok) redirect("/login");
        payload = await res.json();
    } catch {
        redirect("/login");
    }

    const isAdmin = payload?.user?.role === "admin";
    const hasPaid = payload?.subscription?.valid === true;
    if (!isAdmin && !hasPaid) redirect("/login?step=plans&reason=unpaid");

    const rawPlan = isAdmin ? "admin" : (payload?.subscription?.plan ?? "free");
    const plan: "admin" | "max" | "pro" | "free" =
        rawPlan === "admin" || rawPlan === "max" || rawPlan === "pro" ? rawPlan : "free";

    return (
        <Shell
            plan={plan}
            userId={payload?.user?.id ?? null}
            userName={payload?.user?.full_name || payload?.user?.email || ""}
            isAdmin={isAdmin}
            subscriptionStartedAt={payload?.subscription?.starts_at ?? null}
            token={token}
        >
            {children}
        </Shell>
    );
}
