import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.CPES_API_URL ?? "http://api:8000";

/**
 * SSE proxy do dashboard.
 *
 * Por que existe: Cloudflare comprime `text/event-stream` com gzip no
 * edge, e gzip bufferiza ate ter dados suficientes — frames SSE de ~1KB
 * nunca chegam ao cliente. EventSource API nao permite header
 * `Accept-Encoding: identity` (forbidden header). Fetch tambem nao
 * (Chrome ignora silenciosamente).
 *
 * Solucao: route handler server-side faz fetch ao backend com
 * `Accept-Encoding: identity` (server-side fetch nao tem essa
 * restricao), e devolve a resposta com `Cache-Control: no-transform`
 * + `Content-Encoding: identity` — CF respeita e nao comprime.
 *
 * Cliente conecta aqui via EventSource normal (`/api/sse/dashboard?token=...`).
 */
export async function GET(req: NextRequest) {
    const token = req.nextUrl.searchParams.get("token") ?? "";
    if (!token) {
        return new Response("missing token", { status: 401 });
    }

    const upstream = await fetch(
        `${BACKEND}/api/stream/dashboard?token=${encodeURIComponent(token)}`,
        {
            headers: {
                Accept: "text/event-stream",
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
            },
        },
    );

    if (!upstream.ok || !upstream.body) {
        return new Response(`backend ${upstream.status}`, { status: upstream.status });
    }

    return new Response(upstream.body, {
        status: 200,
        headers: {
            "Content-Type": "text/event-stream; charset=utf-8",
            // no-transform = CDN nao pode comprimir nem modificar payload.
            // no-store + no-cache pra impedir cache de SSE.
            "Cache-Control": "no-cache, no-store, no-transform",
            // identity = "ja entreguei sem compressao, nao re-encode".
            "Content-Encoding": "identity",
            "Connection": "keep-alive",
            // nginx/uvicorn/CF: desabilita buffering em proxies intermedios.
            "X-Accel-Buffering": "no",
        },
    });
}
