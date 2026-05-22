"use client";

import { useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import { SmartToy, ArrowForward } from "@mui/icons-material";
import { motion, useReducedMotion } from "framer-motion";
import SetupWizard from "./SetupWizard";

type BotConfig = {
    accepted_tos_at: string | null;
    bet_house: string | null;
    banca_inicial_cents: number;
} | null;

type Props = {
    userName: string;
    initialConfig: BotConfig;
};

const STEPS = [
    { icon: "1️⃣", title: "Aceite os termos", body: "Disclaimer de risco e responsabilidade" },
    { icon: "2️⃣", title: "Conecte sua casa", body: "Betano, Bet365 ou KTO" },
    { icon: "3️⃣", title: "Defina sua banca", body: "Valor virtual que o robô vai gerenciar" },
    { icon: "4️⃣", title: "Modo simulação", body: "7 dias antes de ativar real" },
];

export default function HeroEmpty({ userName, initialConfig }: Props) {
    const [wizardOpen, setWizardOpen] = useState(false);
    const reduceMotion = useReducedMotion() ?? false;
    const firstName = (userName || "").split(" ")[0] || "Apostador";

    return (
        <Box
            sx={{
                minHeight: "70vh",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
                p: 4,
            }}
        >
            <Box
                component={motion.div}
                animate={
                    reduceMotion
                        ? undefined
                        : { y: [0, -8, 0] }
                }
                transition={
                    reduceMotion
                        ? undefined
                        : { duration: 3, repeat: Infinity, ease: "easeInOut" }
                }
                sx={{
                    width: 96, height: 96, borderRadius: "50%",
                    background: "rgba(124,77,255,0.15)",
                    border: "2px solid rgba(124,77,255,0.4)",
                    boxShadow: "0 0 60px rgba(124,77,255,0.3)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    mb: 3,
                }}
            >
                <SmartToy sx={{ fontSize: 56, color: "#7C4DFF" }} />
            </Box>

            <Typography
                component={motion.h4}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                variant="h4"
                fontWeight={800}
                sx={{ mb: 1, color: "#1F1B16" }}
            >
                Bem-vindo ao Robô, {firstName}!
            </Typography>

            <Typography
                component={motion.p}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.15 }}
                sx={{ color: "#5C594F", maxWidth: 520, mb: 4, lineHeight: 1.6 }}
            >
                Os sinais do PressureIQ chegam direto na casa de aposta. O robô executa,
                gerencia a banca e fecha apostas quando faz sentido matematicamente.
            </Typography>

            <Box
                sx={{
                    display: "grid",
                    gridTemplateColumns: { xs: "1fr", sm: "repeat(4, 1fr)" },
                    gap: 2,
                    maxWidth: 720,
                    mb: 4,
                }}
            >
                {STEPS.map((s, i) => (
                    <Box
                        key={s.title}
                        component={motion.div}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.35, delay: 0.2 + i * 0.08 }}
                        sx={{
                            p: 2,
                            background: "rgba(124,77,255,0.05)",
                            border: "1px solid rgba(124,77,255,0.18)",
                            borderRadius: 2,
                            textAlign: "left",
                        }}
                    >
                        <Box sx={{ fontSize: 24, mb: 0.5 }}>{s.icon}</Box>
                        <Typography variant="body2" fontWeight={700} sx={{ color: "#1F1B16", mb: 0.5 }}>
                            {s.title}
                        </Typography>
                        <Typography variant="caption" sx={{ color: "text.secondary" }}>
                            {s.body}
                        </Typography>
                    </Box>
                ))}
            </Box>

            <Button
                component={motion.button}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.55 }}
                whileHover={reduceMotion ? undefined : { scale: 1.03 }}
                whileTap={reduceMotion ? undefined : { scale: 0.97 }}
                onClick={() => setWizardOpen(true)}
                variant="contained"
                size="large"
                endIcon={<ArrowForward />}
                sx={{
                    px: 4,
                    py: 1.5,
                    fontSize: "1.05rem",
                    fontWeight: 700,
                    textTransform: "none",
                    background: "linear-gradient(135deg, #7C4DFF, #5C2DC9)",
                    boxShadow: "0 6px 30px rgba(124,77,255,0.4)",
                    "&:hover": { background: "linear-gradient(135deg, #9C6DFF, #7C4DFF)" },
                }}
            >
                Começar configuração
            </Button>

            <Typography variant="caption" sx={{ mt: 3, color: "#9A958A" }}>
                ⚠️ Apostas envolvem risco real. Leia os termos antes.
            </Typography>

            <SetupWizard
                open={wizardOpen}
                onClose={() => setWizardOpen(false)}
                initialConfig={initialConfig}
            />
        </Box>
    );
}
