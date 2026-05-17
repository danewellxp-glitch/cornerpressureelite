"use client";

import { Box, Card, CardContent, Typography, Grid } from "@mui/material";
import { motion } from "framer-motion";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import type { BotPnl, OpenBet, BetItem } from "@/lib/api";

function PeriodCard({
    title, n, wins, losses, delta, roi, color, delay,
}: {
    title: string; n: number; wins: number; losses: number;
    delta: number; roi: number; color: string; delay: number;
}) {
    const positive = delta >= 0;
    return (
        <Box
            component={motion.div}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay }}
        >
            <Card sx={{ borderTop: `3px solid ${color}` }}>
                <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="caption" sx={{ color: "text.secondary", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                        {title}
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 800, fontFamily: "monospace", color: positive ? "#00E676" : "#FF5252", mt: 0.5 }}>
                        {positive ? "+" : ""}R$ {(delta / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </Typography>
                    <Box sx={{ display: "flex", gap: 1.5, mt: 1.5, alignItems: "baseline" }}>
                        <Typography variant="caption" sx={{ fontWeight: 700, color: positive ? "#00E676" : "#FF5252" }}>
                            ROI {positive ? "+" : ""}{roi.toFixed(1)}%
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {wins}W {losses}L · {n} apostas
                        </Typography>
                    </Box>
                </CardContent>
            </Card>
        </Box>
    );
}

export default function OverviewTab({
    pnl, openBets, recentBets,
}: {
    pnl: BotPnl | null;
    openBets: OpenBet[];
    recentBets: BetItem[];
}) {
    if (!pnl) return null;

    return (
        <Box>
            <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid size={{ xs: 12, md: 4 }}>
                    <PeriodCard title="Hoje" {...pnl.today} delta={pnl.today.delta_cents} roi={pnl.today.roi_pct} color="#00B0FF" delay={0} />
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                    <PeriodCard title="Esta semana" {...pnl.week} delta={pnl.week.delta_cents} roi={pnl.week.roi_pct} color="#9C6DFF" delay={0.08} />
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                    <PeriodCard title={`${pnl.days} dias`} {...pnl.total} delta={pnl.total.delta_cents} roi={pnl.total.roi_pct} color="#00E676" delay={0.16} />
                </Grid>
            </Grid>

            <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
                        Evolução do P&L ({pnl.days} dias)
                    </Typography>
                    {pnl.series.length === 0 ? (
                        <Typography variant="body2" color="text.secondary" sx={{ textAlign: "center", py: 4 }}>
                            Sem dados suficientes ainda.
                        </Typography>
                    ) : (
                        <Box sx={{ height: 240 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={pnl.series.map((s) => ({ date: s.date.slice(5), delta: s.delta_cents / 100 }))}>
                                    <defs>
                                        <linearGradient id="pnlArea" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="#00E676" stopOpacity={0.6} />
                                            <stop offset="100%" stopColor="#00E676" stopOpacity={0.02} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid stroke="rgba(255,255,255,0.04)" />
                                    <XAxis dataKey="date" stroke="rgba(255,255,255,0.4)" fontSize={11} />
                                    <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                                    <Tooltip
                                        contentStyle={{ background: "#0d1b2a", border: "1px solid rgba(255,255,255,0.1)" }}
                                        formatter={(v) => `R$ ${Number(v ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`}
                                    />
                                    <Area type="monotone" dataKey="delta" stroke="#00E676" strokeWidth={2} fill="url(#pnlArea)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </Box>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
                        Apostas abertas ({openBets.length})
                    </Typography>
                    {openBets.length === 0 ? (
                        <Typography variant="body2" color="text.secondary" sx={{ textAlign: "center", py: 3 }}>
                            Nenhuma aposta aberta. Aguardando próximo sinal…
                        </Typography>
                    ) : (
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                            {openBets.slice(0, 5).map((b) => (
                                <Box key={b.id} sx={{ p: 1.5, background: "rgba(0,176,255,0.05)", border: "1px solid rgba(0,176,255,0.15)", borderRadius: 1 }}>
                                    <Typography variant="body2" fontWeight={600}>
                                        {b.jogo_descricao || `#${b.signal_id}`}
                                        <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                                            · {b.liga_nome} · {b.minuto ? `${b.minuto}'` : ""} {b.placar ? b.placar : ""}
                                        </Typography>
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {b.market === "cards" ? "Cartões" : "Escanteios"} {b.selecao} {b.linha} · R$ {(b.stake_cents / 100).toFixed(2)} @ {b.odd.toFixed(2)}
                                    </Typography>
                                </Box>
                            ))}
                        </Box>
                    )}
                </CardContent>
            </Card>
        </Box>
    );
}
