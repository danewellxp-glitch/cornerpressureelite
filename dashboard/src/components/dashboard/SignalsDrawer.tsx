"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Filter, Loader2 } from "lucide-react";
import { fetchSignalsList, type SignalDetail, type SignalResult } from "@/lib/api";
import { fmtDateTime, cn } from "@/lib/format";

const TITLES: Record<SignalResult, string> = {
    all: "Todos os sinais",
    GREEN: "Sinais GREEN",
    RED: "Sinais RED",
    PENDENTE: "Sinais pendentes",
};

const RESULT_STYLE: Record<string, string> = {
    GREEN: "text-success border-success/40 bg-success/10",
    RED: "text-destructive border-destructive/40 bg-destructive/10",
    PENDENTE: "text-warning border-warning/40 bg-warning/10",
};

export function SignalsDrawer({
    open,
    onClose,
    filter,
    signals: signalsProp,
    periodLabel,
}: {
    open: boolean;
    onClose: () => void;
    filter: SignalResult;
    /** Sinais já filtrados por período (passados do dashboard). Se vier, ignora fetch. */
    signals?: SignalDetail[];
    /** Label do período pro header do drawer ("Últimos 7 dias", etc). */
    periodLabel?: string;
}) {
    const [fetched, setFetched] = useState<SignalDetail[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Se signals foi passado por prop, usa eles (filtra por resultado client-side).
    // Senão, fetch do backend.
    const usesProp = signalsProp !== undefined;

    useEffect(() => {
        if (!open || usesProp) return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        fetchSignalsList(filter, 500)
            .then((list) => {
                if (cancelled) return;
                setFetched(list);
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : "Erro ao carregar sinais");
            })
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, [open, filter, usesProp]);

    const items = useMemo(() => {
        const source = usesProp ? signalsProp ?? [] : fetched;
        if (filter === "all") return source;
        return source.filter((s) => s.resultado === filter || (filter === "PENDENTE" && !s.resultado));
    }, [usesProp, signalsProp, fetched, filter]);

    return (
        <AnimatePresence>
            {open && (
                <>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="fixed inset-0 bg-background/70 backdrop-blur-sm z-40"
                        onClick={onClose}
                    />
                    <motion.aside
                        initial={{ x: "100%" }}
                        animate={{ x: 0 }}
                        exit={{ x: "100%" }}
                        transition={{ type: "spring", damping: 30, stiffness: 280 }}
                        className="fixed top-0 right-0 bottom-0 w-full sm:w-[760px] z-50 bg-card border-l border-mint/30 flex flex-col"
                    >
                        <div className="flex items-center justify-between p-5 border-b border-border">
                            <div className="flex items-center gap-3">
                                <div className="rounded-lg border border-mint/40 bg-mint/10 p-2">
                                    <Filter className="size-4 text-mint-bright" />
                                </div>
                                <div>
                                    <h2 className="font-display text-lg font-semibold">{TITLES[filter]}</h2>
                                    <span className="font-mono text-[10px] tracking-wider text-muted-foreground">
                                        {loading
                                            ? "CARREGANDO…"
                                            : `${items.length} REGISTROS${periodLabel ? ` · ${periodLabel.toUpperCase()}` : ""}`}
                                    </span>
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/40"
                            >
                                <X className="size-4" />
                            </button>
                        </div>

                        <div className="flex-1 overflow-auto">
                            {loading ? (
                                <div className="flex items-center justify-center py-16 text-muted-foreground">
                                    <Loader2 className="size-5 animate-spin" />
                                </div>
                            ) : error ? (
                                <div className="text-center py-16 text-sm text-destructive">{error}</div>
                            ) : items.length === 0 ? (
                                <div className="text-center py-16 text-sm text-muted-foreground">
                                    Nenhum sinal encontrado.
                                </div>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="sticky top-0 bg-card z-10 border-b border-border">
                                        <tr className="font-mono text-[10px] tracking-wider text-muted-foreground">
                                            <th className="text-left font-medium px-4 py-3">DATA</th>
                                            <th className="text-left font-medium px-4 py-3">JOGO</th>
                                            <th className="text-left font-medium px-4 py-3">TIPO</th>
                                            <th className="text-right font-medium px-4 py-3">LINHA</th>
                                            <th className="text-right font-medium px-4 py-3">ODD</th>
                                            <th className="text-center font-medium px-4 py-3">STATUS</th>
                                            <th className="text-right font-medium px-4 py-3">ROI</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {items.map((s) => (
                                            <tr
                                                key={s.id}
                                                className="border-b border-border/40 hover:bg-mint/5 transition-colors"
                                            >
                                                <td className="px-4 py-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
                                                    {fmtDateTime(s.timestamp)}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="font-medium text-foreground">
                                                        {s.jogo_descricao || "—"}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">{s.liga_nome}</div>
                                                </td>
                                                <td className="px-4 py-3 text-xs">
                                                    <span className="text-mint mr-1">
                                                        {s.tipo_analise === "CARTOES" ? "▮" : "◤"}
                                                    </span>
                                                    {s.tipo_sinal}
                                                </td>
                                                <td className="px-4 py-3 text-right font-mono text-xs">
                                                    {s.linha ?? "—"}
                                                </td>
                                                <td className="px-4 py-3 text-right font-mono text-xs">
                                                    {s.odd?.toFixed(2) ?? "—"}
                                                </td>
                                                <td className="px-4 py-3 text-center">
                                                    <span
                                                        className={cn(
                                                            "inline-flex items-center justify-center font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-full border",
                                                            RESULT_STYLE[s.resultado] ?? "border-border bg-muted/40 text-muted-foreground",
                                                        )}
                                                    >
                                                        {s.resultado}
                                                    </span>
                                                </td>
                                                <td
                                                    className={cn(
                                                        "px-4 py-3 text-right font-mono text-xs font-semibold",
                                                        s.roi == null
                                                            ? "text-muted-foreground"
                                                            : s.roi >= 0
                                                                ? "text-success"
                                                                : "text-destructive",
                                                    )}
                                                >
                                                    {s.roi == null
                                                        ? "—"
                                                        : `${s.roi >= 0 ? "+" : ""}${s.roi.toFixed(2)}u`}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </motion.aside>
                </>
            )}
        </AnimatePresence>
    );
}
