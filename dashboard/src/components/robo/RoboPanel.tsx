"use client";

import { useCallback, useEffect, useState } from "react";
import { Box, Tabs, Tab, Typography, Chip, Grid, Card, CardContent, Skeleton, Alert } from "@mui/material";
import {
    Dashboard as DashboardIcon,
    Tune,
    CheckCircleOutline,
    History,
    Science,
} from "@mui/icons-material";
import { motion } from "framer-motion";
import HeroEmpty from "./HeroEmpty";
import OverviewTab from "./OverviewTab";
import OpenBetsTab from "./OpenBetsTab";
import HistoryTab from "./HistoryTab";
import ConfigTab from "./ConfigTab";
import {
    fetchBotPnl,
    fetchBotOpenBets,
    fetchBotBets,
    type BotPnl,
    type OpenBet,
    type BetItem,
    type BotConfig,
} from "@/lib/api";

type Props = {
    initialConfig: BotConfig | null;
    userName: string;
};

const REFRESH_MS = 30_000;

export default function RoboPanel({ initialConfig, userName }: Props) {
    const [config, setConfig] = useState<BotConfig | null>(initialConfig);
    const [tab, setTab] = useState(0);
    const [pnl, setPnl] = useState<BotPnl | null>(null);
    const [openBets, setOpenBets] = useState<OpenBet[]>([]);
    const [bets, setBets] = useState<BetItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const needsSetup =
        !config ||
        !config.accepted_tos_at ||
        !config.bet_house ||
        (config.banca_inicial_cents ?? 0) < 5000;

    const loadAll = useCallback(async () => {
        if (needsSetup) return;
        try {
            const [pnlRes, openRes, betsRes] = await Promise.all([
                fetchBotPnl(30),
                fetchBotOpenBets(),
                fetchBotBets({ page: 1, page_size: 20 }),
            ]);
            setPnl(pnlRes);
            setOpenBets(openRes);
            setBets(betsRes.items);
            setError("");
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao carregar dados do robô");
        } finally {
            setLoading(false);
        }
    }, [needsSetup]);

    useEffect(() => {
        loadAll();
        if (needsSetup) return;
        const id = setInterval(loadAll, REFRESH_MS);
        return () => clearInterval(id);
    }, [loadAll, needsSetup]);

    if (needsSetup) {
        return <HeroEmpty userName={userName} initialConfig={config} />;
    }

    return (
        <Box>
            {/* Header */}
            <Box
                component={motion.div}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1.5,
                    mb: 2,
                    flexWrap: "wrap",
                    justifyContent: "space-between",
                }}
            >
                <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
                    <Typography variant="h5" fontWeight={700}>
                        Robô Auto-Aposta
                    </Typography>
                    <Chip
                        label={config!.mode === "real" ? "🟠 MODO REAL" : "🔵 MODO PAPER"}
                        size="small"
                        sx={{
                            fontWeight: 800,
                            letterSpacing: "0.05em",
                            bgcolor: config!.mode === "real" ? "rgba(255,107,0,0.18)" : "rgba(0,176,255,0.18)",
                            color: config!.mode === "real" ? "#FF6B00" : "#00B0FF",
                        }}
                    />
                    <Chip
                        label={config!.enabled ? "🟢 LIGADO" : "⚪ PAUSADO"}
                        size="small"
                        sx={{
                            fontWeight: 800,
                            bgcolor: config!.enabled ? "rgba(0,230,118,0.18)" : "rgba(148,163,184,0.18)",
                            color: config!.enabled ? "#00E676" : "#94A3B8",
                        }}
                    />
                </Box>
                <BancaBadge value={config!.banca_atual_cents} initial={config!.banca_inicial_cents} />
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            <Tabs
                value={tab}
                onChange={(_, v) => setTab(v)}
                sx={{ mb: 3, borderBottom: "1px solid rgba(255,255,255,0.05)" }}
                variant="scrollable"
                scrollButtons="auto"
            >
                <Tab icon={<DashboardIcon />} iconPosition="start" label="Visão geral" />
                <Tab icon={<Tune />} iconPosition="start" label="Configuração" />
                <Tab icon={<CheckCircleOutline />} iconPosition="start" label={`Abertas (${openBets.length})`} />
                <Tab icon={<History />} iconPosition="start" label="Histórico" />
                <Tab icon={<Science />} iconPosition="start" label="Simular" />
            </Tabs>

            <Box
                component={motion.div}
                key={tab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
            >
                {loading ? (
                    <SkeletonRow />
                ) : (
                    <>
                        {tab === 0 && <OverviewTab pnl={pnl} openBets={openBets} recentBets={bets.slice(0, 5)} />}
                        {tab === 1 && <ConfigTab config={config!} onConfigChange={setConfig} />}
                        {tab === 2 && <OpenBetsTab bets={openBets} />}
                        {tab === 3 && <HistoryTab bets={bets} />}
                        {tab === 4 && <PlaceholderTab title="Simular" hint="Backtester chega na Fase 4 do roadmap." />}
                    </>
                )}
            </Box>
        </Box>
    );
}

function BancaBadge({ value, initial }: { value: number; initial: number }) {
    const delta = value - initial;
    const positive = delta >= 0;
    return (
        <Box sx={{ textAlign: "right" }}>
            <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.65rem", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                Banca atual
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 800, fontFamily: "monospace", color: "#fff" }}>
                R$ {(value / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
            </Typography>
            <Typography variant="caption" sx={{ fontWeight: 700, color: positive ? "#00E676" : "#FF5252" }}>
                {positive ? "+" : ""}R$ {(delta / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
            </Typography>
        </Box>
    );
}

function SkeletonRow() {
    return (
        <Grid container spacing={2}>
            {[1, 2, 3].map((i) => (
                <Grid size={{ xs: 12, md: 4 }} key={i}>
                    <Skeleton variant="rounded" height={120} sx={{ bgcolor: "rgba(255,255,255,0.04)" }} />
                </Grid>
            ))}
        </Grid>
    );
}

function PlaceholderTab({ title, hint }: { title: string; hint: string }) {
    return (
        <Card>
            <CardContent sx={{ p: 4, textAlign: "center" }}>
                <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>
                    {title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                    {hint}
                </Typography>
            </CardContent>
        </Card>
    );
}
