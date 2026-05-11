"use client";

import { Box, Card, CardContent, Typography, Button, ThemeProvider, CssBaseline } from "@mui/material";
import { CheckCircle } from "@mui/icons-material";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import theme from "@/lib/theme";

export default function CheckoutSuccessPage() {
    const router = useRouter();
    const reduceMotion = useReducedMotion() ?? false;

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
                <Card sx={{ maxWidth: 500, mx: 2, textAlign: "center", border: "1px solid rgba(76, 175, 80, 0.3)" }}>
                    <CardContent sx={{ p: 4 }}>
                        <CheckCircle sx={{ fontSize: 64, color: "#4CAF50", mb: 2 }} />
                        <Typography variant="h4" gutterBottom fontWeight="bold">
                            Pagamento em processamento!
                        </Typography>
                        <Typography variant="body1" color="text.secondary" paragraph>
                            Seu pagamento foi recebido e está sendo processado. Assim que confirmado, seu acesso será liberado automaticamente e você receberá o link dos grupos no WhatsApp.
                        </Typography>
                        <Button
                            variant="contained"
                            color="primary"
                            size="large"
                            onClick={() => router.push("/dashboard")}
                            sx={{ mt: 2 }}
                        >
                            Ir para o Dashboard
                        </Button>
                    </CardContent>
                </Card>
            </Box>
        </ThemeProvider>
    );
}
