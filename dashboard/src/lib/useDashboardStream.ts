"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DashboardData } from "./api";

// Rota proxy local que entrega o SSE com Cache-Control: no-transform
// (impede CF de comprimir e quebrar o stream). Ver
// dashboard/src/app/api/sse/dashboard/route.ts.
const SSE_URL = "/api/sse/dashboard";
const RECONNECT_BACKOFF_MS = [1_000, 2_000, 4_000, 8_000, 16_000, 30_000];
const HIDDEN_DISCONNECT_AFTER_MS = 5 * 60_000; // 5 min em background -> desconecta

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "offline";

export type StreamState = {
    data: DashboardData | null;
    status: ConnectionStatus;
    lastUpdate: Date | null;
    /** Re-trigger manual da conexao (botao "Reconectar agora"). */
    reconnect: () => void;
};

/**
 * Conecta no SSE `/api/sse/dashboard` (proxy local) e mantem estado live.
 *
 * - Auth via `?token=` (EventSource nao envia header).
 * - Backoff exponencial em desconexoes: 1s, 2s, 4s, 8s, 16s, 30s.
 * - Page Visibility API: aba em background > 5min desconecta; voltar ao foco reconecta.
 */
export function useDashboardStream(): StreamState {
    const [data, setData] = useState<DashboardData | null>(null);
    const [status, setStatus] = useState<ConnectionStatus>("connecting");
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

    const esRef = useRef<EventSource | null>(null);
    const attemptRef = useRef(0);
    const reconnectTimerRef = useRef<number | null>(null);
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

        const url = `${SSE_URL}?token=${encodeURIComponent(token)}`;
        setStatus(attemptRef.current === 0 ? "connecting" : "reconnecting");

        const es = new EventSource(url);
        esRef.current = es;

        es.onopen = () => {
            attemptRef.current = 0;
            setStatus("connected");
            console.debug("[SSE] open");
        };

        const handleMessage = (ev: MessageEvent) => {
            try {
                const payload = JSON.parse(ev.data) as DashboardData;
                setData(payload);
                setLastUpdate(new Date());
                console.debug("[SSE] frame", {
                    signals: payload?.signals?.length ?? 0,
                    live_na: payload?.live_games?.na_janela?.length ?? 0,
                });
            } catch (err) {
                console.error("[SSE] parse failed", err, "data:", ev.data?.slice?.(0, 200));
            }
        };
        es.onmessage = handleMessage;
        es.addEventListener("message", handleMessage);

        es.onerror = (ev) => {
            console.warn("[SSE] error/close", { readyState: es.readyState, ev });
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
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [cleanup]);

    const reconnect = useCallback(() => {
        attemptRef.current = 0;
        connect();
    }, [connect]);

    // Conecta no mount; desconecta no unmount
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
                if (!esRef.current) {
                    attemptRef.current = 0;
                    connect();
                }
            }
        };
        document.addEventListener("visibilitychange", handler);
        return () => document.removeEventListener("visibilitychange", handler);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return { data, status, lastUpdate, reconnect };
}
