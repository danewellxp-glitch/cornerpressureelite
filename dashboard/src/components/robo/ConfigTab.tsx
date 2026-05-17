"use client";

import { useState } from "react";
import { Box, Card, CardContent, Typography, Switch, FormControlLabel, TextField, Chip, Button, Alert, Divider } from "@mui/material";
import { Save } from "@mui/icons-material";
import { patchBotConfig, type BotConfig } from "@/lib/api";

const MARKETS = [
    { id: "corners", label: "Escanteios" },
    { id: "cards", label: "Cartões" },
];

export default function ConfigTab({
    config, onConfigChange,
}: {
    config: BotConfig;
    onConfigChange: (c: BotConfig) => void;
}) {
    const [enabled, setEnabled] = useState(config.enabled);
    const [killSwitch, setKillSwitch] = useState(config.kill_switch);
    const [bancaR, setBancaR] = useState((config.banca_inicial_cents / 100).toFixed(2));
    const [maxLossR, setMaxLossR] = useState((config.max_loss_per_day_cents / 100).toFixed(2));
    const [maxBets, setMaxBets] = useState(config.max_bets_per_day);
    const [unitPct, setUnitPct] = useState(config.unit_pct * 100);
    const [allowedMarkets, setAllowedMarkets] = useState<string[]>(config.allowed_markets || []);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    const save = async () => {
        setSaving(true);
        setError("");
        setMessage("");
        try {
            const patch = {
                enabled,
                kill_switch: killSwitch,
                banca_inicial_cents: Math.round(parseFloat(bancaR) * 100),
                max_loss_per_day_cents: Math.round(parseFloat(maxLossR) * 100),
                max_bets_per_day: Number(maxBets) || 0,
                unit_pct: Math.max(0.001, Math.min(0.05, unitPct / 100)),
                allowed_markets: allowedMarkets,
            };
            const updated = await patchBotConfig(patch);
            onConfigChange(updated);
            setMessage("Configuração salva.");
            setTimeout(() => setMessage(""), 2500);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao salvar.");
        } finally {
            setSaving(false);
        }
    };

    const toggleMarket = (m: string) => {
        setAllowedMarkets((prev) =>
            prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m],
        );
    };

    return (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Card>
                <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2, color: "#9C6DFF" }}>
                        Estado do robô
                    </Typography>
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                        <FormControlLabel
                            control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} color="success" />}
                            label={<Typography fontWeight={600}>Robô {enabled ? "ligado" : "pausado"}</Typography>}
                        />
                        <FormControlLabel
                            control={<Switch checked={killSwitch} onChange={(e) => setKillSwitch(e.target.checked)} color="warning" />}
                            label={
                                <Box>
                                    <Typography fontWeight={600}>Kill switch</Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        Pausa de emergência — robô ignora todos os sinais quando ativo.
                                    </Typography>
                                </Box>
                            }
                        />
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2, color: "#00E676" }}>
                        Banca & Risco
                    </Typography>
                    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)" }, gap: 2 }}>
                        <TextField
                            label="Banca virtual (R$)"
                            type="number"
                            size="small"
                            value={bancaR}
                            onChange={(e) => setBancaR(e.target.value)}
                            helperText="Valor de referência (100% da banca para cálculo de stake)"
                        />
                        <TextField
                            label="Stake por aposta (% da banca)"
                            type="number"
                            size="small"
                            value={unitPct}
                            onChange={(e) => setUnitPct(Number(e.target.value))}
                            slotProps={{ htmlInput: { step: 0.1, min: 0.1, max: 5 } }}
                            helperText="0.1% – 5%. Default: 1%"
                        />
                        <TextField
                            label="Max apostas / dia"
                            type="number"
                            size="small"
                            value={maxBets}
                            onChange={(e) => setMaxBets(Number(e.target.value))}
                        />
                        <TextField
                            label="Max perda / dia (R$)"
                            type="number"
                            size="small"
                            value={maxLossR}
                            onChange={(e) => setMaxLossR(e.target.value)}
                            helperText="Robô pausa após atingir esse limite"
                        />
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2, color: "#00B0FF" }}>
                        Mercados permitidos
                    </Typography>
                    <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                        {MARKETS.map((m) => (
                            <Chip
                                key={m.id}
                                label={m.label}
                                clickable
                                onClick={() => toggleMarket(m.id)}
                                sx={{
                                    fontWeight: 700,
                                    border: "1px solid",
                                    borderColor: allowedMarkets.includes(m.id) ? "#00B0FF" : "rgba(255,255,255,0.15)",
                                    bgcolor: allowedMarkets.includes(m.id) ? "rgba(0,176,255,0.2)" : "transparent",
                                    color: allowedMarkets.includes(m.id) ? "#00B0FF" : "text.secondary",
                                }}
                            />
                        ))}
                    </Box>
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                        O robô só aposta nos mercados marcados acima.
                    </Typography>
                </CardContent>
            </Card>

            <Divider />

            {error && <Alert severity="error">{error}</Alert>}
            {message && <Alert severity="success">{message}</Alert>}

            <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
                <Button
                    variant="contained"
                    startIcon={<Save />}
                    onClick={save}
                    disabled={saving}
                    sx={{
                        px: 4,
                        background: "linear-gradient(135deg, #7C4DFF, #5C2DC9)",
                        "&:hover": { background: "linear-gradient(135deg, #9C6DFF, #7C4DFF)" },
                    }}
                >
                    {saving ? "Salvando..." : "Salvar configuração"}
                </Button>
            </Box>
        </Box>
    );
}
