"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DashboardData } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_CPES_API || "/api/cpes";
const RECONNECT_BACKOFF_MS = [1_000, 2_000, 4_000, 8_000, 16_000, 30_000];
const HIDDEN_DISCONNECT_AFTER_MS = 5 * 60_000; // 5 min em background → desconecta

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "offline";

export type StreamState = {
    data: DashboardData | null;
    status: ConnectionStatus;
    lastUpdate: Date | null;
    /** Re-trigger manual da conexão (botão "Reconectar agora"). */
    reconnect: () => void;
};

/**
 * Conecta no SSE `/api/cpes/stream/dashboard` e mantém um estado live do dashboard.
 *
 * - Auth via `?token=` (EventSource não envia header).
 * - Backoff exponencial em desconexões: 1s, 2s, 4s, 8s, 16s, 30s.
 * - Page Visibility API: aba em background > 5min desconecta; voltar ao foco reconecta.
 */
export function useDashboardStream(): StreamState {
    const [data, setData] = useState<DashboardData | null>(null);
    const [status, setStatus] = useState<ConnectionStatus>("connecting");
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

    const esRef = useRef<EventSource | null>(null);
    const attemptRef = useRef(0);
    const reconnectTimerRef = useRef<number | null>(null);
    const hiddenSinceRef = useRef<number | null>(null);
    const hiddenTimerRef = useRef<number | null>(null);

    const cleanup = useCallback(() => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }
        if (reconnectTimerRef.current != null) {
            window.clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
    }, []);

    const connect = useCallback(() => {
        if (typeof window === "undefined") return;
        cleanup();

        const token = localStorage.getItem("token");
        if (!token) {
            setStatus("offline");
            return;
        }

        const url = `${API_BASE}/stream/dashboard?token=${encodeURIComponent(token)}`;
        setStatus(attemptRef.current === 0 ? "connecting" : "reconnecting");

        const es = new EventSource(url);
        esRef.current = es;

        es.onopen = () => {
            attemptRef.current = 0;
            setStatus("connected");
        };

        es.onmessage = (ev) => {
            try {
                const payload = JSON.parse(ev.data) as DashboardData;
                setData(payload);
                setLastUpdate(new Date());
            } catch {
                // payload mal-formado: ignora
            }
        };

        es.onerror = () => {
            // EventSource auto-reconecta no nativo, mas queremos backoff customizado
            // pra evitar tight loop quando o servidor está fora.
            es.close();
            esRef.current = null;
            const idx = Math.min(attemptRef.current, RECONNECT_BACKOFF_MS.length - 1);
            const delay = RECONNECT_BACKOFF_MS[idx];
            attemptRef.current += 1;
            setStatus("reconnecting");
            reconnectTimerRef.current = window.setTimeout(() => {
                connect();
            }, delay);
        };
    }, [cleanup]);

    const reconnect = useCallback(() => {
        attemptRef.current = 0;
        connect();
    }, [connect]);

    // Conecta no mount; desconecta no unmount. Deps vazias intencionalmente —
    // `connect`/`cleanup` sao estaveis (useCallback com deps []), e qualquer
    // re-identificacao futura nao pode disparar reconect loop.
    useEffect(() => {
        connect();
        return () => {
            cleanup();
            if (hiddenTimerRef.current != null) {
                window.clearTimeout(hiddenTimerRef.current);
                hiddenTimerRef.current = null;
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Page Visibility: desconecta se em background > 5min, reconecta on focus
    useEffect(() => {
        if (typeof document === "undefined") return;
        const handler = () => {
            if (document.hidden) {
                hiddenSinceRef.current = Date.now();
                // Limpa timer anterior antes de re-agendar — evita leak quando
                // o user toggle a aba varias vezes em <5min.
                if (hiddenTimerRef.current != null) {
                    window.clearTimeout(hiddenTimerRef.current);
                }
                hiddenTimerRef.current = window.setTimeout(() => {
                    cleanup();
                    setStatus("offline");
                }, HIDDEN_DISCONNECT_AFTER_MS);
            } else {
                if (hiddenTimerRef.current != null) {
                    window.clearTimeout(hiddenTimerRef.current);
                    hiddenTimerRef.current = null;
                }
                // Se passou tempo no background sem ter sido desconectado, ainda OK.
                // Se foi desconectado (status=offline), reconecta agora.
                if (!esRef.current) {
                    attemptRef.current = 0;
                    connect();
                }
                hiddenSinceRef.current = null;
            }
        };
        document.addEventListener("visibilitychange", handler);
        return () => document.removeEventListener("visibilitychange", handler);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return { data, status, lastUpdate, reconnect };
}
