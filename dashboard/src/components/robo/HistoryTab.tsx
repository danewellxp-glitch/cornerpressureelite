"use client";

import { Box, Card, CardContent, Typography, Table, TableHead, TableRow, TableCell, TableBody, Chip } from "@mui/material";
import type { BetItem } from "@/lib/api";

const STATUS_COLORS: Record<string, { label: string; color: string; bg: string }> = {
    won: { label: "GREEN", color: "#15A34A", bg: "rgba(21,163,74,0.14)" },
    lost: { label: "RED", color: "#DC2626", bg: "rgba(220,38,38,0.12)" },
    cashed_out: { label: "CASHOUT", color: "#B45309", bg: "rgba(180,83,9,0.14)" },
    open: { label: "OPEN", color: "#0277BD", bg: "rgba(2,119,189,0.14)" },
    error: { label: "ERROR", color: "#DC2626", bg: "rgba(220,38,38,0.12)" },
    canceled: { label: "CANCELED", color: "#64748B", bg: "rgba(100,116,139,0.16)" },
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
                                const s = STATUS_COLORS[b.status] ?? { label: b.status, color: "#64748B", bg: "rgba(100,116,139,0.16)" };
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
                                        <TableCell align="right" sx={{ fontFamily: "monospace", fontSize: "0.8rem", fontWeight: 700, color: !isResolved ? "text.secondary" : delta >= 0 ? "#15A34A" : "#DC2626" }}>
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
