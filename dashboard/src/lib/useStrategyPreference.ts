"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchStrategyPreference, updateStrategyPreference } from "@/lib/api";
import { isValidTier, type StrategyTier } from "@/lib/strategies";

export interface UserStrategyPreference {
    corners: StrategyTier;
    cards: StrategyTier;
}

const DEFAULT_PREF: UserStrategyPreference = {
    corners: "moderate",
    cards: "moderate",
};

export function useStrategyPreference() {
    const [preference, setPreference] = useState<UserStrategyPreference>(DEFAULT_PREF);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string>("");
    // Seq counter: ignora respostas de updates antigos quando o user dispara
    // varios em sequencia (ex: troca corners e cards rapido). So o ultimo
    // dispatch + reverte em caso de erro.
    const updateSeqRef = useRef(0);

    const load = useCallback(async () => {
        try {
            setLoading(true);
            const pref = await fetchStrategyPreference();
            setPreference({
                corners: isValidTier(pref.corners_strategy) ? pref.corners_strategy : "moderate",
                cards: isValidTier(pref.cards_strategy) ? pref.cards_strategy : "moderate",
            });
            setError("");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Erro ao carregar preferência");
        } finally {
            setLoading(false);
        }
    }, []);

    const update = useCallback(async (patch: Partial<UserStrategyPreference>) => {
        setPreference((prev) => ({ ...prev, ...patch }));
        const mySeq = ++updateSeqRef.current;
        try {
            await updateStrategyPreference({
                ...(patch.corners ? { corners_strategy: patch.corners } : {}),
                ...(patch.cards ? { cards_strategy: patch.cards } : {}),
            });
            if (updateSeqRef.current === mySeq) {
                window.dispatchEvent(new Event("strategy-pref-updated"));
            }
        } catch (err) {
            if (updateSeqRef.current !== mySeq) return; // call mais recente cuida
            setError(err instanceof Error ? err.message : "Erro ao salvar preferência");
            load();
        }
    }, [load]);

    useEffect(() => {
        load();
        const handler = () => load();
        window.addEventListener("strategy-pref-updated", handler);
        return () => window.removeEventListener("strategy-pref-updated", handler);
    }, [load]);

    return { preference, loading, error, reload: load, update };
}
