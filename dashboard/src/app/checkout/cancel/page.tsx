"use client";

import { Box, Card, CardContent, Typography, Button, ThemeProvider, CssBaseline } from "@mui/material";
import { ErrorOutline } from "@mui/icons-material";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import theme from "@/lib/theme";

export default function CheckoutCancelPage() {
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
                <Card sx={{ maxWidth: 500, mx: 2, textAlign: "center", border: "1px solid rgba(244, 67, 54, 0.3)" }}>
                    <CardContent sx={{ p: 4 }}>
                        <ErrorOutline sx={{ fontSize: 64, color: "#F44336", mb: 2 }} />
                        <Typography variant="h4" gutterBottom fontWeight="bold" color="error">
                            Pagamento Cancelado
                        </Typography>
                        <Typography variant="body1" color="text.secondary" paragraph>
                            O processo de pagamento foi cancelado ou ocorreu um erro. Nenhuma cobrança foi realizada.
                        </Typography>
                        <Button
                            variant="outlined"
                            color="primary"
                            size="large"
                            onClick={() => router.push("/login")}
                            sx={{ mt: 2 }}
                        >
                            Tentar Novamente
                        </Button>
                    </CardContent>
                </Card>
            </Box>
        </ThemeProvider>
    );
}
