"use client";

import { Box, Card, CardContent, Typography, Chip } from "@mui/material";
import { motion } from "framer-motion";
import type { OpenBet } from "@/lib/api";

export default function OpenBetsTab({ bets }: { bets: OpenBet[] }) {
    if (bets.length === 0) {
        return (
            <Card>
                <CardContent sx={{ p: 6, textAlign: "center" }}>
                    <Typography variant="h6" sx={{ mb: 1, color: "text.secondary" }}>
                        Sem apostas abertas no momento 💤
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Aguardando o próximo sinal CPES chegar e bater com a sua estratégia.
                    </Typography>
                </CardContent>
            </Card>
        );
    }

    return (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {bets.map((b, idx) => (
                <Box
                    key={b.id}
                    component={motion.div}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: idx * 0.04 }}
                >
                    <Card sx={{ borderLeft: `4px solid ${b.mode === "real" ? "#D9560A" : "#0277BD"}` }}>
                        <CardContent sx={{ p: 2.5 }}>
                            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1, flexWrap: "wrap", gap: 1 }}>
                                <Box>
                                    <Typography variant="subtitle1" fontWeight={700}>
                                        {b.jogo_descricao || `Sinal #${b.signal_id}`}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {b.liga_nome} {b.minuto ? `· ${b.minuto}'` : ""} {b.placar ? `· ${b.placar}` : ""}
                                    </Typography>
                                </Box>
                                <Chip
                                    label={b.mode === "real" ? "REAL" : "PAPER"}
                                    size="small"
                                    sx={{
                                        fontWeight: 700,
                                        bgcolor: b.mode === "real" ? "rgba(255,107,0,0.16)" : "rgba(2,119,189,0.14)",
                                        color: b.mode === "real" ? "#D9560A" : "#0277BD",
                                    }}
                                />
                            </Box>
                            <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", mt: 1 }}>
                                <Stat label="Mercado" value={b.market === "cards" ? "Cartões" : "Escanteios"} />
                                <Stat label="Linha" value={`${b.selecao} ${b.linha}`} />
                                <Stat label="Odd" value={b.odd.toFixed(2)} />
                                <Stat label="Stake" value={`R$ ${(b.stake_cents / 100).toFixed(2)}`} />
                                <Stat label="Payout estimado" value={`R$ ${((b.stake_cents * b.odd) / 100).toFixed(2)}`} />
                            </Box>
                        </CardContent>
                    </Card>
                </Box>
            ))}
        </Box>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", fontSize: "0.65rem", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                {label}
            </Typography>
            <Typography variant="body2" fontWeight={700}>
                {value}
            </Typography>
        </Box>
    );
}
