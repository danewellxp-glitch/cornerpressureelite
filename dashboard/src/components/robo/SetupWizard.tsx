"use client";

import { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogActions,
    Button,
    Box,
    Typography,
    Stepper,
    Step,
    StepLabel,
    Checkbox,
    FormControlLabel,
    TextField,
    Slider,
    Chip,
    Alert,
    useMediaQuery,
} from "@mui/material";
import {
    ArrowForward,
    ArrowBack,
    CheckCircle,
    Gavel,
    Casino,
    AttachMoney,
    Science,
} from "@mui/icons-material";
import { motion, AnimatePresence, useReducedMotion, type Variants } from "framer-motion";
import { acceptBotTos, patchBotConfig, upsertBotCredential } from "@/lib/api";
import theme from "@/lib/theme";

type BotConfig = {
    accepted_tos_at: string | null;
    bet_house: string | null;
    banca_inicial_cents: number;
} | null;

type Props = {
    open: boolean;
    onClose: () => void;
    initialConfig: BotConfig;
};

const BANCA_PRESETS = [
    { label: "R$ 200", cents: 20_000 },
    { label: "R$ 500", cents: 50_000 },
    { label: "R$ 1.000", cents: 100_000 },
    { label: "R$ 2.000", cents: 200_000 },
];

const HOUSES = [
    { id: "betano", label: "Betano", color: "#FF6B00" },
    { id: "bet365", label: "Bet365", color: "#0a6e0a" },
    { id: "kto", label: "KTO", color: "#FFD700" },
];

export default function SetupWizard({ open, onClose, initialConfig }: Props) {
    const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
    const reduceMotion = useReducedMotion() ?? false;

    const [step, setStep] = useState(0);
    const [direction, setDirection] = useState<1 | -1>(1);
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);

    // Step 1: ToS
    const [tosAccepted, setTosAccepted] = useState(Boolean(initialConfig?.accepted_tos_at));

    // Step 2: Casa + credenciais
    const [house, setHouse] = useState<string>(initialConfig?.bet_house ?? "betano");
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    // Step 3: Banca
    const [bancaCents, setBancaCents] = useState<number>(
        initialConfig?.banca_inicial_cents || 50_000,
    );

    const stepVariants: Variants = reduceMotion
        ? {
              enter: { opacity: 0 },
              center: { opacity: 1, transition: { duration: 0.15, ease: "linear" } },
              exit: { opacity: 0, transition: { duration: 0.1, ease: "linear" } },
          }
        : {
              enter: (dir: number) => ({ opacity: 0, x: dir * 40, scale: 0.97 }),
              center: { opacity: 1, x: 0, scale: 1, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
              exit: (dir: number) => ({ opacity: 0, x: dir * -40, scale: 0.97, transition: { duration: 0.2, ease: [0.4, 0, 1, 1] } }),
          };

    const close = () => {
        setStep(0);
        setDirection(1);
        setError("");
        onClose();
    };

    const next = () => {
        setDirection(1);
        setStep((s) => Math.min(s + 1, 3));
        setError("");
    };
    const back = () => {
        setDirection(-1);
        setStep((s) => Math.max(s - 1, 0));
        setError("");
    };

    const handleSubmitTos = async () => {
        if (!tosAccepted) {
            setError("Aceite os termos para prosseguir.");
            return;
        }
        setSubmitting(true);
        try {
            await acceptBotTos();
            next();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao aceitar termos.");
        } finally {
            setSubmitting(false);
        }
    };

    const handleSubmitCredentials = async () => {
        if (!username || password.length < 4) {
            setError("Preencha login e senha válidos.");
            return;
        }
        setSubmitting(true);
        try {
            await upsertBotCredential(house, username, password);
            await patchBotConfig({ bet_house: house });
            next();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao salvar credenciais.");
        } finally {
            setSubmitting(false);
        }
    };

    const handleSubmitBanca = async () => {
        if (bancaCents < 5000) {
            setError("Banca mínima: R$ 50,00.");
            return;
        }
        setSubmitting(true);
        try {
            await patchBotConfig({
                banca_inicial_cents: bancaCents,
                max_loss_per_day_cents: Math.floor(bancaCents * 0.15), // 15% banca/dia default
                max_bets_per_day: 10,
                unit_pct: 0.01,
                allowed_markets: ["corners", "cards"],
            });
            next();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao salvar banca.");
        } finally {
            setSubmitting(false);
        }
    };

    const handleFinish = async () => {
        setSubmitting(true);
        try {
            // Ativa o robô em modo paper
            await patchBotConfig({ enabled: true });
            close();
            // Refresh pra carregar a página com nova config
            if (typeof window !== "undefined") window.location.reload();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao ativar robô.");
            setSubmitting(false);
        }
    };

    const STEPS = [
        { label: "Termos", icon: <Gavel /> },
        { label: "Casa", icon: <Casino /> },
        { label: "Banca", icon: <AttachMoney /> },
        { label: "Pronto", icon: <Science /> },
    ];

    return (
        <Dialog
            open={open}
            onClose={submitting ? undefined : close}
            maxWidth="sm"
            fullWidth
            fullScreen={isMobile}
            slotProps={{
                paper: {
                    sx: {
                        background: "linear-gradient(180deg, #0d1b2a 0%, #0a1628 100%)",
                        border: "1px solid rgba(124,77,255,0.3)",
                        borderRadius: { xs: 0, sm: 3 },
                    },
                },
            }}
        >
            <DialogContent sx={{ p: { xs: 3, sm: 4 } }}>
                <Stepper activeStep={step} alternativeLabel sx={{ mb: 3 }}>
                    {STEPS.map((s) => (
                        <Step key={s.label}>
                            <StepLabel
                                slotProps={{
                                    label: { sx: { fontSize: "0.7rem", fontWeight: 600 } },
                                }}
                            >
                                {s.label}
                            </StepLabel>
                        </Step>
                    ))}
                </Stepper>

                <Box sx={{ position: "relative", minHeight: 360, overflow: "hidden" }}>
                    <AnimatePresence mode="wait" custom={direction} initial={false}>
                        <motion.div
                            key={step}
                            custom={direction}
                            variants={stepVariants}
                            initial="enter"
                            animate="center"
                            exit="exit"
                        >
                            {step === 0 && (
                                <StepContent
                                    title="Termos de uso do Robô"
                                    color="#FFC107"
                                    icon={<Gavel sx={{ fontSize: 40, color: "#FFC107" }} />}
                                >
                                    <Typography variant="body2" sx={{ color: "text.secondary", textAlign: "left", maxHeight: 200, overflowY: "auto", p: 2, background: "rgba(0,0,0,0.2)", borderRadius: 1, mb: 2 }}>
                                        <strong>Riscos:</strong> apostas envolvem perda financeira real. A casa de aposta pode proibir uso de automação em seus termos de serviço — o uso do Robô pode resultar em banimento da sua conta e retenção/refund forçado das apostas. Você assume integralmente esse risco.
                                        <br /><br />
                                        <strong>Responsabilidade:</strong> a PressureIQ não garante lucros, não controla as casas de aposta nem os resultados dos jogos. Nossas responsabilidade limita-se ao funcionamento técnico do software.
                                        <br /><br />
                                        <strong>Banca virtual:</strong> o valor que você define aqui é o que o robô vai usar para calcular stakes. O saldo real na casa é apenas validado — variações fora do controle do robô não afetam sua banca virtual.
                                        <br /><br />
                                        <strong>Você pode pausar o robô a qualquer momento.</strong>
                                    </Typography>
                                    <FormControlLabel
                                        control={
                                            <Checkbox
                                                checked={tosAccepted}
                                                onChange={(e) => setTosAccepted(e.target.checked)}
                                                sx={{ color: "#FFC107", "&.Mui-checked": { color: "#FFC107" } }}
                                            />
                                        }
                                        label={<Typography variant="body2">Li e concordo com os termos acima.</Typography>}
                                    />
                                </StepContent>
                            )}
                            {step === 1 && (
                                <StepContent
                                    title="Conecte sua casa de aposta"
                                    color="#00B0FF"
                                    icon={<Casino sx={{ fontSize: 40, color: "#00B0FF" }} />}
                                >
                                    <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mb: 2 }}>
                                        Suas credenciais são <strong>cifradas</strong> antes de gravadas. Nunca expostas pela API.
                                    </Typography>
                                    <Box sx={{ display: "flex", gap: 1, mb: 2, flexWrap: "wrap" }}>
                                        {HOUSES.map((h) => (
                                            <Chip
                                                key={h.id}
                                                label={h.label}
                                                onClick={() => setHouse(h.id)}
                                                clickable
                                                sx={{
                                                    fontWeight: 700,
                                                    borderColor: house === h.id ? h.color : "rgba(255,255,255,0.2)",
                                                    color: house === h.id ? h.color : "text.secondary",
                                                    border: "1px solid",
                                                    bgcolor: house === h.id ? `${h.color}20` : "transparent",
                                                }}
                                            />
                                        ))}
                                    </Box>
                                    <TextField
                                        fullWidth
                                        label="Login / E-mail"
                                        value={username}
                                        onChange={(e) => setUsername(e.target.value)}
                                        sx={{ mb: 2 }}
                                        autoComplete="off"
                                    />
                                    <TextField
                                        fullWidth
                                        type="password"
                                        label="Senha"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        autoComplete="new-password"
                                    />
                                </StepContent>
                            )}
                            {step === 2 && (
                                <StepContent
                                    title="Defina sua banca virtual"
                                    color="#00E676"
                                    icon={<AttachMoney sx={{ fontSize: 40, color: "#00E676" }} />}
                                >
                                    <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mb: 2 }}>
                                        Quanto o robô vai usar como referência de 100% da sua banca. Saldo real na casa pode ser maior — o robô ignora.
                                    </Typography>
                                    <Box sx={{ display: "flex", gap: 1, mb: 3, flexWrap: "wrap" }}>
                                        {BANCA_PRESETS.map((p) => (
                                            <Chip
                                                key={p.cents}
                                                label={p.label}
                                                clickable
                                                onClick={() => setBancaCents(p.cents)}
                                                sx={{
                                                    fontWeight: 700,
                                                    bgcolor: bancaCents === p.cents ? "rgba(0,230,118,0.2)" : "transparent",
                                                    color: bancaCents === p.cents ? "#00E676" : "text.secondary",
                                                    border: "1px solid",
                                                    borderColor: bancaCents === p.cents ? "#00E676" : "rgba(255,255,255,0.15)",
                                                }}
                                            />
                                        ))}
                                    </Box>
                                    <Slider
                                        value={bancaCents / 100}
                                        min={50}
                                        max={5000}
                                        step={50}
                                        marks={[{ value: 50, label: "R$50" }, { value: 1000, label: "R$1k" }, { value: 5000, label: "R$5k" }]}
                                        onChange={(_, v) => setBancaCents((v as number) * 100)}
                                        sx={{ color: "#00E676", mb: 2 }}
                                    />
                                    <Typography variant="h4" sx={{ textAlign: "center", color: "#00E676", fontWeight: 800 }}>
                                        R$ {(bancaCents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                                    </Typography>
                                </StepContent>
                            )}
                            {step === 3 && (
                                <StepContent
                                    title="Tudo pronto!"
                                    color="#00E676"
                                    icon={<CheckCircle sx={{ fontSize: 40, color: "#00E676" }} />}
                                >
                                    <Typography variant="body2" sx={{ color: "text.secondary", textAlign: "center", mb: 2 }}>
                                        O robô vai iniciar em <strong style={{ color: "#00B0FF" }}>modo paper trading</strong> — simulando apostas com base nos sinais reais. Nenhum centavo é gasto.
                                    </Typography>
                                    <Box sx={{ p: 2, background: "rgba(0,176,255,0.06)", border: "1px solid rgba(0,176,255,0.2)", borderRadius: 2, mb: 2 }}>
                                        <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mb: 1 }}>
                                            Resumo
                                        </Typography>
                                        <Typography variant="body2">Casa: <strong>{HOUSES.find(h => h.id === house)?.label}</strong></Typography>
                                        <Typography variant="body2">Banca virtual: <strong>R$ {(bancaCents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</strong></Typography>
                                        <Typography variant="body2">Modo: <strong>PAPER</strong> (simulação)</Typography>
                                        <Typography variant="body2">Apostas/dia (max): <strong>10</strong></Typography>
                                        <Typography variant="body2">Stake por aposta: <strong>1% da banca</strong></Typography>
                                    </Box>
                                    <Alert severity="info" sx={{ "& .MuiAlert-message": { fontSize: "0.8rem" } }}>
                                        Recomendamos rodar pelo menos <strong>7 dias em paper</strong> antes de ativar modo real. Você poderá comparar os resultados no painel.
                                    </Alert>
                                </StepContent>
                            )}
                        </motion.div>
                    </AnimatePresence>
                </Box>

                {error && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                        {error}
                    </Alert>
                )}
            </DialogContent>

            <DialogActions sx={{ px: { xs: 3, sm: 4 }, pb: 3, justifyContent: "space-between" }}>
                <Button onClick={close} disabled={submitting} sx={{ textTransform: "none", color: "text.secondary" }}>
                    Cancelar
                </Button>
                <Box sx={{ display: "flex", gap: 1 }}>
                    {step > 0 && step < 3 && (
                        <Button onClick={back} disabled={submitting} startIcon={<ArrowBack />} sx={{ textTransform: "none" }}>
                            Voltar
                        </Button>
                    )}
                    {step === 0 && (
                        <Button
                            onClick={handleSubmitTos}
                            disabled={!tosAccepted || submitting}
                            variant="contained"
                            endIcon={<ArrowForward />}
                            sx={{ textTransform: "none", fontWeight: 700, background: "linear-gradient(135deg, #FFC107, #FF8F00)", "&:hover": { background: "linear-gradient(135deg, #FFD54F, #FFC107)" } }}
                        >
                            Aceitar e continuar
                        </Button>
                    )}
                    {step === 1 && (
                        <Button
                            onClick={handleSubmitCredentials}
                            disabled={submitting}
                            variant="contained"
                            endIcon={<ArrowForward />}
                            sx={{ textTransform: "none", fontWeight: 700, background: "linear-gradient(135deg, #00B0FF, #0277BD)", "&:hover": { background: "linear-gradient(135deg, #40C4FF, #00B0FF)" } }}
                        >
                            Conectar
                        </Button>
                    )}
                    {step === 2 && (
                        <Button
                            onClick={handleSubmitBanca}
                            disabled={submitting}
                            variant="contained"
                            endIcon={<ArrowForward />}
                            sx={{ textTransform: "none", fontWeight: 700, background: "linear-gradient(135deg, #00E676, #00C853)", "&:hover": { background: "linear-gradient(135deg, #69F0AE, #00E676)" } }}
                        >
                            Salvar banca
                        </Button>
                    )}
                    {step === 3 && (
                        <Button
                            onClick={handleFinish}
                            disabled={submitting}
                            variant="contained"
                            startIcon={<CheckCircle />}
                            sx={{ textTransform: "none", fontWeight: 700, background: "linear-gradient(135deg, #00E676, #00C853)", "&:hover": { background: "linear-gradient(135deg, #69F0AE, #00E676)" } }}
                        >
                            {submitting ? "Ativando..." : "Iniciar paper trading"}
                        </Button>
                    )}
                </Box>
            </DialogActions>
        </Dialog>
    );
}

function StepContent({
    title,
    color,
    icon,
    children,
}: {
    title: string;
    color: string;
    icon: React.ReactNode;
    children: React.ReactNode;
}) {
    return (
        <Box sx={{ textAlign: "center" }}>
            <Box
                sx={{
                    display: "inline-flex",
                    width: 70, height: 70, borderRadius: "50%",
                    background: `${color}15`, border: `2px solid ${color}40`, boxShadow: `0 0 30px ${color}30`,
                    alignItems: "center", justifyContent: "center", mb: 2,
                }}
            >
                {icon}
            </Box>
            <Typography variant="h6" fontWeight={700} sx={{ color: "#fff", mb: 2 }}>
                {title}
            </Typography>
            {children}
        </Box>
    );
}
