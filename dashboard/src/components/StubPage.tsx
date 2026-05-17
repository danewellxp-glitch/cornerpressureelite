import type { LucideIcon } from "lucide-react";
import { Hammer } from "lucide-react";

export function StubPage({
    icon: Icon = Hammer,
    title,
    description,
}: {
    icon?: LucideIcon;
    title: string;
    description: string;
}) {
    return (
        <div className="max-w-2xl mx-auto mt-12 piq-in">
            <div className="rounded-2xl border border-border bg-card p-10 text-center relative overflow-hidden">
                <div className="absolute inset-0 grid-bg opacity-30" />
                <div className="relative">
                    <div className="mx-auto size-14 rounded-2xl border border-mint/40 bg-mint/10 grid place-items-center mb-5">
                        <Icon className="size-7 text-mint-bright" />
                    </div>
                    <h2 className="font-display text-2xl font-semibold">{title}</h2>
                    <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
                        {description}
                    </p>
                </div>
            </div>
        </div>
    );
}
