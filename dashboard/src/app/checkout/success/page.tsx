"use client";

import { useEffect, useState } from "react";
import { Box, Card, CardContent, Typography, Button, ThemeProvider, CssBaseline, CircularProgress } from "@mui/material";
import { CheckCircle, HourglassEmpty } from "@mui/icons-material";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import theme from "@/lib/theme";

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 90_000;

type SubState = "waiting" | "active" | "timeout";

export default function CheckoutSuccessPage() {
    const router = useRouter();
    const reduceMotion = useReducedMotion() ?? false;
    const [state, setState] = useState<SubState>("waiting");

    useEffect(() => {
        const start = Date.now();
        let cancelled = false;

        const check = async (): Promise<boolean> => {
            try {
                const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
                if (!token) return false;
                const res = await fetch("/api/cpes/users/me", {
                    headers: { Authorization: `Bearer ${token}` },
                    cache: "no-store",
                });
                if (!res.ok) return false;
                const data = await res.json();
                return data?.subscription?.valid === true;
            } catch {
                return false;
            }
        };

        const poll = async () => {
            while (!cancelled) {
                if (await check()) {
                    if (!cancelled) {
                        setState("active");
                        setTimeout(() => router.replace("/dashboard"), 800);
                    }
                    return;
                }
                if (Date.now() - start > POLL_TIMEOUT_MS) {
                    if (!cancelled) setState("timeout");
                    return;
                }
                await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
            }
        };

        poll();
        return () => {
            cancelled = true;
        };
    }, [router]);

    const isActive = state === "active";
    const isTimeout = state === "timeout";

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Box
                component={motion.div}
                initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 8 }}
                animate={reduceMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
                transition={
                    reduceMotion
                        ? { duration: 0.15, ease: "linear" }
                        : { duration: 0.25, ease: [0.22, 1, 0.36, 1] }
                }
                sx={{
                    minHeight: "100vh",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "#0A0A1F",
                }}
            >
                <Card sx={{ maxWidth: 520, mx: 2, textAlign: "center", border: `1px solid ${isActive ? "rgba(76, 175, 80, 0.4)" : "rgba(255,193,7,0.3)"}` }}>
                    <CardContent sx={{ p: 4 }}>
                        {isActive ? (
                            <CheckCircle sx={{ fontSize: 64, color: "#4CAF50", mb: 2 }} />
                        ) : isTimeout ? (
                            <HourglassEmpty sx={{ fontSize: 64, color: "#FFC107", mb: 2 }} />
                        ) : (
                            <CircularProgress size={64} sx={{ color: "#4CAF50", mb: 2 }} />
                        )}

                        <Typography variant="h5" gutterBottom fontWeight="bold">
                            {isActive
                                ? "Pagamento confirmado!"
                                : isTimeout
                                    ? "Confirmação demorando..."
                                    : "Confirmando seu pagamento..."}
                        </Typography>

                        <Typography variant="body2" color="text.secondary" paragraph>
                            {isActive
                                ? "Redirecionando para o dashboard..."
                                : isTimeout
                                    ? "O pagamento pode levar alguns minutos para ser processado (especialmente PIX/Boleto). Você receberá um e-mail assim que for confirmado e poderá entrar normalmente."
                                    : "Aguardando o Asaas confirmar seu pagamento. Não feche esta página."}
                        </Typography>

                        {isTimeout && (
                            <Button
                                variant="contained"
                                color="primary"
                                size="large"
                                onClick={() => router.push("/dashboard")}
                                sx={{ mt: 2 }}
                            >
                                Tentar acessar o dashboard
                            </Button>
                        )}
                    </CardContent>
                </Card>
            </Box>
        </ThemeProvider>
    );
}
