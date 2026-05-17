"use client";

import { Box, Card, CardContent, Typography, Table, TableHead, TableRow, TableCell, TableBody, Chip } from "@mui/material";
import type { BetItem } from "@/lib/api";

const STATUS_COLORS: Record<string, { label: string; color: string; bg: string }> = {
    won: { label: "GREEN", color: "#00E676", bg: "rgba(0,230,118,0.15)" },
    lost: { label: "RED", color: "#FF5252", bg: "rgba(255,82,82,0.15)" },
    cashed_out: { label: "CASHOUT", color: "#FFC107", bg: "rgba(255,193,7,0.15)" },
    open: { label: "OPEN", color: "#00B0FF", bg: "rgba(0,176,255,0.15)" },
    error: { label: "ERROR", color: "#FF5252", bg: "rgba(255,82,82,0.15)" },
    canceled: { label: "CANCELED", color: "#94A3B8", bg: "rgba(148,163,184,0.15)" },
};

function fmtDateTime(iso: string | null) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export default function HistoryTab({ bets }: { bets: BetItem[] }) {
    if (bets.length === 0) {
        return (
            <Card>
                <CardContent sx={{ p: 6, textAlign: "center" }}>
                    <Typography variant="body2" color="text.secondary">
                        Nenhuma aposta no histórico ainda.
                    </Typography>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardContent sx={{ p: 0 }}>
                <Box sx={{ overflowX: "auto" }}>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Data</TableCell>
                                <TableCell>Jogo</TableCell>
                                <TableCell>Mercado</TableCell>
                                <TableCell align="right">Stake</TableCell>
                                <TableCell align="right">Odd</TableCell>
                                <TableCell align="center">Status</TableCell>
                                <TableCell align="right">Δ Banca</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {bets.map((b) => {
                                const s = STATUS_COLORS[b.status] ?? { label: b.status, color: "#94A3B8", bg: "rgba(148,163,184,0.15)" };
                                const delta = b.payout_cents - b.stake_cents;
                                const isResolved = b.status !== "open";
                                return (
                                    <TableRow key={b.id} hover>
                                        <TableCell sx={{ fontSize: "0.75rem", color: "text.secondary" }}>
                                            {fmtDateTime(b.placed_at)}
                                        </TableCell>
                                        <TableCell sx={{ fontSize: "0.8rem" }}>
                                            <Box sx={{ fontWeight: 600 }}>{b.jogo_descricao || `#${b.signal_id}`}</Box>
                                            <Box sx={{ fontSize: "0.7rem", color: "text.secondary" }}>{b.liga_nome}</Box>
                                        </TableCell>
                                        <TableCell sx={{ fontSize: "0.75rem" }}>
                                            {b.market === "cards" ? "Cartões" : "Escanteios"} {b.selecao} {b.linha}
                                        </TableCell>
                                        <TableCell align="right" sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                                            R$ {(b.stake_cents / 100).toFixed(2)}
                                        </TableCell>
                                        <TableCell align="right" sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                                            {b.odd.toFixed(2)}
                                        </TableCell>
                                        <TableCell align="center">
                                            <Chip size="small" label={s.label} sx={{ fontWeight: 700, bgcolor: s.bg, color: s.color, height: 20, fontSize: "0.65rem" }} />
                                        </TableCell>
                                        <TableCell align="right" sx={{ fontFamily: "monospace", fontSize: "0.8rem", fontWeight: 700, color: !isResolved ? "text.secondary" : delta >= 0 ? "#00E676" : "#FF5252" }}>
                                            {isResolved ? `${delta >= 0 ? "+" : ""}R$ ${(delta / 100).toFixed(2)}` : "—"}
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </Box>
            </CardContent>
        </Card>
    );
}
