"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DashboardData } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_CPES_API || "/api/cpes";
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
 * Stream SSE do dashboard via fetch + ReadableStream.
 *
 * IMPORTANTE: nao usa EventSource API porque Cloudflare comprime
 * `text/event-stream` com gzip no edge, e gzip bufferiza ate ter dados
 * suficientes pra emitir — o cliente fica "connected" eternamente sem
 * receber frame nenhum. Fetch permite `Accept-Encoding: identity` que
 * forca CF a entregar uncompressed. EventSource nao aceita headers
 * customizados.
 *
 * - Auth via `?token=` (mantem compatibilidade com backend que valida
 *   o mesmo param tanto via header quanto query).
 * - Backoff exponencial em desconexoes: 1s, 2s, 4s, 8s, 16s, 30s.
 * - Page Visibility API: aba em background > 5min desconecta;
 *   voltar ao foco reconecta.
 */
export function useDashboardStream(): StreamState {
    const [data, setData] = useState<DashboardData | null>(null);
    const [status, setStatus] = useState<ConnectionStatus>("connecting");
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

    const abortRef = useRef<AbortController | null>(null);
    const attemptRef = useRef(0);
    const reconnectTimerRef = useRef<number | null>(null);
    const hiddenTimerRef = useRef<number | null>(null);

    const cleanup = useCallback(() => {
        if (abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
        }
        if (reconnectTimerRef.current != null) {
            window.clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
    }, []);

    const scheduleReconnect = useCallback(() => {
        const idx = Math.min(attemptRef.current, RECONNECT_BACKOFF_MS.length - 1);
        const delay = RECONNECT_BACKOFF_MS[idx];
        attemptRef.current += 1;
        setStatus("reconnecting");
        reconnectTimerRef.current = window.setTimeout(() => {
            connect();
        }, delay);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const connect = useCallback(async () => {
        if (typeof window === "undefined") return;
        cleanup();

        const token = localStorage.getItem("token");
        if (!token) {
            setStatus("offline");
            return;
        }

        const url = `${API_BASE}/stream/dashboard?token=${encodeURIComponent(token)}`;
        setStatus(attemptRef.current === 0 ? "connecting" : "reconnecting");

        const controller = new AbortController();
        abortRef.current = controller;

        let response: Response;
        try {
            response = await fetch(url, {
                signal: controller.signal,
                headers: {
                    Accept: "text/event-stream",
                    "Cache-Control": "no-cache",
                    // KEY: força CF/proxies a NAO comprimir o stream. gzip
                    // bufferiza e quebra SSE (frames ficam presos ate o buffer
                    // encher). EventSource nao permite esse header customizado.
                    "Accept-Encoding": "identity",
                },
            });
        } catch (err) {
            if (controller.signal.aborted) return;
            console.warn("[SSE] fetch failed", err);
            scheduleReconnect();
            return;
        }

        if (!response.ok || !response.body) {
            console.warn("[SSE] non-ok response", response.status);
            if (response.status === 401) {
                setStatus("offline");
                return;
            }
            scheduleReconnect();
            return;
        }

        attemptRef.current = 0;
        setStatus("connected");
        console.debug("[SSE] open", url.split("?")[0]);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        try {
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                // SSE event delimiter = double newline
                let idx: number;
                while ((idx = buffer.indexOf("\n\n")) >= 0) {
                    const block = buffer.slice(0, idx);
                    buffer = buffer.slice(idx + 2);
                    const dataLines = block
                        .split("\n")
                        .filter((l) => l.startsWith("data:"))
                        .map((l) => l.slice(l.startsWith("data: ") ? 6 : 5));
                    if (dataLines.length === 0) continue;
                    const raw = dataLines.join("\n");
                    try {
                        const payload = JSON.parse(raw) as DashboardData;
                        setData(payload);
                        setLastUpdate(new Date());
                        console.debug("[SSE] frame", {
                            signals: payload?.signals?.length ?? 0,
                            live_na: payload?.live_games?.na_janela?.length ?? 0,
                        });
                    } catch (err) {
                        console.error("[SSE] parse failed", err, "raw:", raw.slice(0, 200));
                    }
                }
            }
        } catch (err) {
            if (controller.signal.aborted) return;
            console.warn("[SSE] read loop error", err);
        }

        // Stream encerrou (servidor fechou ou rede caiu).
        if (controller.signal.aborted) return;
        scheduleReconnect();
    }, [cleanup, scheduleReconnect]);

    const reconnect = useCallback(() => {
        attemptRef.current = 0;
        connect();
    }, [connect]);

    // Conecta no mount; desconecta no unmount. Deps vazias intencionalmente —
    // connect/cleanup sao estaveis o suficiente; loop reconnect e gerenciado
    // internamente via refs e timers.
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
                if (!abortRef.current) {
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
