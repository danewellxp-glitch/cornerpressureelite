"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { motion, AnimatePresence, useReducedMotion, type Variants } from "framer-motion";
import {
    Zap, ArrowRight, Lock, Eye, EyeOff,
    TrendingUp, Shield, Brain, MessageCircle,
    LayoutDashboard, Bot, Sliders, Bell,
    Check, Star, X, ChevronDown, Menu
} from "lucide-react";
import { login, register, checkout, verifyEmail, resendVerification } from "@/lib/api";

// Stagger fade-in: logo (400ms) → title (delay 150ms) → fields (delay 300ms) → button (delay 450ms)
const STAGGER_DELAYS = { logo: 0, title: 0.15, fields: 0.3, button: 0.45 };
const FADE_DURATION = 0.4;

// ─── Live Stat Counter ───────────────────────────────────────────────────────
function LiveStat({ label, value, color }: { label: string; value: string; color: string }) {
    const [displayed, setDisplayed] = useState("0");
    useEffect(() => {
        const target = parseFloat(value.replace(/[^0-9.]/g, ""));
        const suffix = value.match(/[^0-9.]+$/)?.[0] || "";
        let current = 0;
        const step = target / 60;
        const timer = setInterval(() => {
            current = Math.min(current + step, target);
            setDisplayed(Math.round(current).toLocaleString("pt-BR") + suffix);
            if (current >= target) clearInterval(timer);
        }, 30);
        return () => clearInterval(timer);
    }, [value]);
    return (
        <div className="piq-glass piq-rounded-xl p-4 flex flex-col gap-1 min-w-[130px]">
            <div className={`text-2xl font-bold font-mono ${color}`}>{displayed}</div>
            <div className="text-xs piq-text-muted uppercase tracking-widest">{label}</div>
        </div>
    );
}

// ─── Features Data ────────────────────────────────────────────────────────────
const features = [
    { icon: Brain, color: "#00e676", title: "Previsões com IA", tag: "CORE", description: "Algoritmos proprietários analisam pressão de jogo, ataques perigosos, ritmo de escanteios e cartões em centenas de partidas simultâneas." },
    { icon: MessageCircle, color: "#4ade80", title: "Alertas no WhatsApp", tag: "TEMPO REAL", description: "Sinais chegam em menos de 30 segundos após identificação, com a odd recomendada e o raciocínio do algoritmo." },
    { icon: LayoutDashboard, color: "#60a5fa", title: "Dashboard Completo", tag: "DASHBOARD", description: "Painel profissional com histórico de sinais, ROI acumulado, gráficos de desempenho e jogos ao vivo." },
    { icon: Bot, color: "#facc15", title: "Robô Apostador", tag: "MAX", description: "Conecte sua conta nas principais casas e deixe o robô executar automaticamente. Sem emoção, 24h por dia." },
    { icon: Sliders, color: "#c084fc", title: "Estratégia Customizável", tag: "MAX", description: "Configure risco por aposta, mercados favoritos, bankroll management e filtros de odds. Você controla." },
    { icon: TrendingUp, color: "#f472b6", title: "ROI Rastreado", tag: "TODOS", description: "Cada sinal é registrado com resultado real. Transparência total, nenhuma manipulação." },
];

// ─── Plans Data ───────────────────────────────────────────────────────────────
const plans = [
    {
        name: "Pro", price: "39,90", planKey: "pro",
        description: "Para apostadores que querem vantagem real com dados profissionais.",
        tag: null, isPopular: false,
        features: ["Sinais de Escanteios ilimitados", "Alertas no WhatsApp em tempo real", "Dashboard de performance completo", "Histórico de sinais e ROI", "Análise de pressão de jogo", "Acesso a 9 ligas monitoradas", "Suporte por email"],
    },
    {
        name: "Max", price: "89,90", planKey: "max",
        description: "Para profissionais que querem automação total e acesso VIP.",
        tag: "MAIS POPULAR", isPopular: true,
        features: ["Tudo do plano Pro", "Sinais de Cartões + Gols", "Grupo VIP no WhatsApp", "Robô Apostador automático", "Estratégia totalmente customizável", "Integração multi-casa de apostas", "Suporte prioritário 24/7"],
    },
];

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function LoginPage() {
    const router = useRouter();
    const reduceMotion = useReducedMotion() ?? false;
    const fade = (delay = 0): Variants => reduceMotion
        ? {
            hidden: { opacity: 0 },
            visible: { opacity: 1, transition: { duration: 0.15, ease: "linear" } },
        }
        : {
            hidden: { opacity: 0, y: 6 },
            visible: { opacity: 1, y: 0, transition: { duration: FADE_DURATION, delay, ease: [0.22, 1, 0.36, 1] } },
        };
    const [showLoginModal, setShowLoginModal] = useState(false);
    const [tab, setTab] = useState<"login" | "register" | "plans" | "verify">("login");
    const [showPass, setShowPass] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [fullName, setFullName] = useState("");
    const [whatsapp, setWhatsapp] = useState("");
    const [cpf, setCpf] = useState("");
    const [verifyCode, setVerifyCode] = useState("");
    const [pendingEmail, setPendingEmail] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const data = await login(email, password);
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data.user));
            document.cookie = `cpes-auth=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
            router.push("/dashboard");
        } catch (err: any) {
            setError(err.message || "Erro ao fazer login. Verifique suas credenciais.");
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const data = await register({
                email,
                password,
                full_name: fullName,
                whatsapp: whatsapp.replace(/\D/g, ""),
                cpf: cpf.replace(/\D/g, ""),
            });
            // Backend agora retorna requires_verification=true
            setPendingEmail(email);
            setTab("verify");
            setError("");
        } catch (err: any) {
            setError(err.message || "Erro ao criar conta.");
        } finally {
            setLoading(false);
        }
    };

    const handleVerifyEmail = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const data = await verifyEmail(pendingEmail || email, verifyCode);
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data.user));
            document.cookie = `cpes-auth=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
            setTab("plans");
        } catch (err: any) {
            setError(err.message || "Código inválido.");
        } finally {
            setLoading(false);
        }
    };

    const handleResendCode = async () => {
        setError("");
        setLoading(true);
        try {
            await resendVerification(pendingEmail || email);
            setError(""); // Clear any previous error
        } catch (err: any) {
            setError(err.message || "Erro ao reenviar código.");
        } finally {
            setLoading(false);
        }
    };

    const handleCheckout = async (plan: string) => {
        setLoading(true);
        setError("");
        try {
            const currentToken = localStorage.getItem("token");
            if (!currentToken) throw new Error("Usuário não autenticado");
            const data = await checkout(plan, currentToken);
            if (data.checkoutUrl) {
                window.location.href = data.checkoutUrl;
            } else {
                throw new Error("Erro ao gerar link de pagamento");
            }
        } catch (err: any) {
            setError(err.message || "Erro no checkout");
            setLoading(false);
        }
    };

    const openLogin = (defaultTab: "login" | "register" = "login") => {
        setTab(defaultTab);
        setError("");
        setShowLoginModal(true);
    };

    return (
        <>
            {/* ─── Global Styles ─── */}
            <style>{`
                @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
                .piq-root { font-family: 'Space Grotesk', sans-serif; background: hsl(222, 47%, 4%); color: hsl(210, 40%, 96%); min-height: 100vh; overflow-x: hidden; }
                .piq-glass { background: rgba(7,14,30,0.7); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(0,230,118,0.12); }
                .piq-glass-strong { background: rgba(7,14,30,0.92); backdrop-filter: blur(30px); -webkit-backdrop-filter: blur(30px); border: 1px solid rgba(0,230,118,0.22); }
                .piq-rounded-xl { border-radius: 0.75rem; }
                .piq-rounded-2xl { border-radius: 1rem; }
                .piq-text-muted { color: hsl(215, 20%, 55%); }
                .piq-text-primary { color: #00e676; }
                .piq-glow-green { box-shadow: 0 0 20px rgba(0,230,118,0.3), 0 0 60px rgba(0,230,118,0.1); }
                .piq-gradient-text { background: linear-gradient(135deg, #00e676 0%, #00b0ff 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
                .piq-gradient-text-gold { background: linear-gradient(135deg, #ffd700 0%, #ff8c00 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
                .piq-pulse { animation: piq-pulse 2s infinite; }
                @keyframes piq-pulse { 0%,100%{box-shadow:0 0 0 0 rgba(0,230,118,0.7)} 70%{box-shadow:0 0 0 8px rgba(0,230,118,0)} }
                .piq-btn-primary { background: #00e676; color: hsl(222,47%,4%); font-weight: 700; border: none; cursor: pointer; transition: all 0.2s; }
                .piq-btn-primary:hover { background: #00c853; box-shadow: 0 0 20px rgba(0,230,118,0.4); }
                .piq-btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
                .piq-btn-outline { background: transparent; color: #00e676; border: 1px solid rgba(0,230,118,0.4); font-weight: 600; cursor: pointer; transition: all 0.2s; }
                .piq-btn-outline:hover { background: rgba(0,230,118,0.1); }
                .piq-input { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: hsl(210,40%,96%); border-radius: 0.75rem; padding: 0.75rem 1rem; width: 100%; font-family: inherit; font-size: 0.95rem; transition: border-color 0.2s; outline: none; }
                .piq-input:focus { border-color: #00e676; box-shadow: 0 0 0 3px rgba(0,230,118,0.1); }
                .piq-input::placeholder { color: hsl(215,20%,40%); }
                .piq-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: hsl(215,20%,55%); display: block; margin-bottom: 0.5rem; }
                .piq-border-glow { border: 1px solid transparent; background: linear-gradient(hsl(220,40%,7%), hsl(220,40%,7%)) padding-box, linear-gradient(135deg, #00e676, #00b0ff) border-box; }
                .piq-border-glow-gold { border: 1px solid transparent; background: linear-gradient(hsl(220,40%,7%), hsl(220,40%,7%)) padding-box, linear-gradient(135deg, #ffd700, #ff8c00) border-box; }
                .piq-feature-card { transition: all 0.3s; }
                .piq-feature-card:hover { transform: translateY(-4px); border-color: rgba(0,230,118,0.3) !important; }
                .piq-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 50; }
                .piq-modal-overlay { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 1rem; background: rgba(7,14,30,0.85); backdrop-filter: blur(8px); }
                .piq-scrollbar::-webkit-scrollbar { width: 4px; }
                .piq-scrollbar::-webkit-scrollbar-thumb { background: rgba(0,230,118,0.3); border-radius: 2px; }
            `}</style>

            <div className="piq-root">
                {/* ─── Navbar ─── */}
                <nav className="piq-nav piq-glass" style={{ borderBottom: "1px solid rgba(0,230,118,0.1)" }}>
                    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "0 1.5rem", display: "flex", alignItems: "center", justifyContent: "space-between", height: "64px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "rgba(0,230,118,0.15)", border: "1px solid rgba(0,230,118,0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                                <Zap size={16} color="#00e676" />
                            </div>
                            <span style={{ fontWeight: 700, fontSize: "1.1rem" }}>Pressure<span className="piq-gradient-text">IQ</span></span>
                        </div>
                        <div style={{ display: "flex", gap: "2rem" }} className="hidden md:flex">
                            <a href="#features" style={{ color: "hsl(215,20%,65%)", textDecoration: "none", fontSize: "0.9rem", transition: "color 0.2s" }} onMouseEnter={e => (e.currentTarget.style.color = "#00e676")} onMouseLeave={e => (e.currentTarget.style.color = "hsl(215,20%,65%)")}>Funcionalidades</a>
                            <a href="#pricing" style={{ color: "hsl(215,20%,65%)", textDecoration: "none", fontSize: "0.9rem", transition: "color 0.2s" }} onMouseEnter={e => (e.currentTarget.style.color = "#00e676")} onMouseLeave={e => (e.currentTarget.style.color = "hsl(215,20%,65%)")}>Planos</a>
                        </div>
                        <div style={{ display: "flex", gap: "0.75rem" }}>
                            <button onClick={() => openLogin("login")} className="piq-btn-outline" style={{ padding: "0.5rem 1.25rem", borderRadius: "0.5rem", fontSize: "0.875rem" }}>Entrar</button>
                            <button onClick={() => openLogin("register")} className="piq-btn-primary piq-glow-green" style={{ padding: "0.5rem 1.25rem", borderRadius: "0.5rem", fontSize: "0.875rem" }}>Começar</button>
                        </div>
                    </div>
                </nav>

                {/* ─── Hero Section ─── */}
                <section style={{
                    position: "relative",
                    minHeight: "100vh",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    overflow: "hidden",
                    paddingTop: "64px",
                    backgroundImage: "url('/hero-bg.jpg')",
                    backgroundSize: "cover",
                    backgroundPosition: "center",
                }}>
                    {/* Overlay dark gradient */}
                    <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to bottom, rgba(5, 10, 20, 0.7), rgba(5, 10, 20, 0.9))" }} />

                    <div style={{ position: "relative", zIndex: 10, maxWidth: "1024px", margin: "0 auto", padding: "0 1.5rem", textAlign: "center" }}>


                        {/* Headline */}
                        <h1 style={{ fontSize: "clamp(2.5rem, 7vw, 5rem)", fontWeight: 800, lineHeight: 1.1, marginBottom: "1.5rem", letterSpacing: "-0.02em" }}>
                            A Ciência por Trás<br />do <span className="piq-gradient-text" style={{ textShadow: "0 0 40px rgba(0,230,118,0.3)" }}>Green.</span>
                        </h1>

                        <p style={{ fontSize: "clamp(1rem, 2.5vw, 1.25rem)", color: "hsl(215,20%,65%)", maxWidth: "700px", margin: "0 auto 2.5rem", lineHeight: 1.7 }}>
                            Algoritmos proprietários analisam <strong style={{ color: "hsl(210,40%,96%)" }}>pressão de jogo em tempo real</strong> e entregam sinais de alta probabilidade direto no seu WhatsApp.
                        </p>

                        {/* CTAs */}
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", justifyContent: "center", marginBottom: "4rem" }}>
                            <button onClick={() => openLogin("register")} className="piq-btn-primary piq-glow-green" style={{ padding: "1rem 2rem", borderRadius: "0.75rem", fontSize: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                Começar Agora <ArrowRight size={18} />
                            </button>
                            <a href="#features">
                                <button className="piq-btn-outline" style={{ padding: "1rem 2rem", borderRadius: "0.75rem", fontSize: "1rem" }}>
                                    Ver Como Funciona
                                </button>
                            </a>
                        </div>



                        {/* Trust badges */}
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "1.5rem", justifyContent: "center", color: "hsl(215,20%,55%)", fontSize: "0.875rem" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><Shield size={16} color="#00e676" /><span>Dados reais e auditáveis</span></div>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><Zap size={16} color="#facc15" /><span>Alertas em &lt; 30 segundos</span></div>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><TrendingUp size={16} color="#60a5fa" /><span>ROI rastreado em tempo real</span></div>
                        </div>
                    </div>

                    {/* Scroll indicator */}
                    <div style={{ position: "absolute", bottom: "2rem", left: "50%", transform: "translateX(-50%)", animation: "bounce 2s infinite" }}>
                        <ChevronDown size={24} color="rgba(0,230,118,0.5)" />
                    </div>
                </section>

                {/* ─── Features Section ─── */}
                <section id="features" style={{ padding: "8rem 1.5rem", position: "relative" }}>
                    <div style={{ position: "absolute", top: "50%", left: 0, width: "400px", height: "400px", background: "rgba(0,230,118,0.04)", borderRadius: "50%", filter: "blur(100px)", pointerEvents: "none" }} />
                    <div style={{ maxWidth: "1280px", margin: "0 auto" }}>
                        <div style={{ textAlign: "center", marginBottom: "5rem" }}>
                            <div className="piq-glass" style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 1rem", borderRadius: "9999px", marginBottom: "1.5rem", border: "1px solid rgba(0,230,118,0.2)" }}>
                                <Bell size={12} color="#00e676" />
                                <span style={{ fontSize: "0.7rem", color: "#00e676", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>Tudo que você precisa</span>
                            </div>
                            <h2 style={{ fontSize: "clamp(2rem, 5vw, 3rem)", fontWeight: 800, marginBottom: "1rem" }}>
                                Uma Plataforma.<br /><span className="piq-gradient-text">Vantagem Completa.</span>
                            </h2>
                            <p style={{ color: "hsl(215,20%,55%)", fontSize: "1.1rem", maxWidth: "600px", margin: "0 auto" }}>
                                Do sinal ao dinheiro na conta. O PressureIQ cobre todo o processo de análise e execução.
                            </p>
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.5rem" }}>
                            {features.map((f) => {
                                const Icon = f.icon;
                                return (
                                    <div key={f.title} className="piq-glass piq-rounded-2xl piq-feature-card" style={{ padding: "1.5rem", cursor: "default" }}>
                                        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1rem" }}>
                                            <div style={{ width: "48px", height: "48px", borderRadius: "12px", background: `${f.color}18`, border: `1px solid ${f.color}30`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                                <Icon size={22} color={f.color} />
                                            </div>
                                            <span style={{ fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.1em", padding: "0.25rem 0.5rem", borderRadius: "9999px", background: `${f.color}18`, color: f.color, border: `1px solid ${f.color}30` }}>{f.tag}</span>
                                        </div>
                                        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "0.5rem" }}>{f.title}</h3>
                                        <p style={{ color: "hsl(215,20%,55%)", fontSize: "0.875rem", lineHeight: 1.6 }}>{f.description}</p>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </section>

                {/* ─── Pricing Section ─── */}
                <section id="pricing" style={{ padding: "8rem 1.5rem", position: "relative" }}>
                    <div style={{ position: "absolute", bottom: 0, left: "50%", transform: "translateX(-50%)", width: "600px", height: "200px", background: "rgba(0,230,118,0.04)", borderRadius: "50%", filter: "blur(80px)", pointerEvents: "none" }} />
                    <div style={{ maxWidth: "900px", margin: "0 auto" }}>
                        <div style={{ textAlign: "center", marginBottom: "4rem" }}>
                            <div className="piq-glass" style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 1rem", borderRadius: "9999px", marginBottom: "1.5rem", border: "1px solid rgba(0,230,118,0.2)" }}>
                                <Bot size={12} color="#00e676" />
                                <span style={{ fontSize: "0.7rem", color: "#00e676", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>Planos e Preços</span>
                            </div>
                            <h2 style={{ fontSize: "clamp(2rem, 5vw, 3rem)", fontWeight: 800, marginBottom: "1rem" }}>
                                Escolha Seu<br /><span className="piq-gradient-text">Nível de Vantagem</span>
                            </h2>
                            <p style={{ color: "hsl(215,20%,55%)", fontSize: "1.1rem" }}>Sem taxa de setup. Cancele quando quiser. Comece a ter resultados hoje.</p>
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "2rem", alignItems: "stretch" }}>
                            {plans.map((plan) => (
                                <div key={plan.name} className={plan.isPopular ? "piq-border-glow-gold" : "piq-border-glow"} style={{ borderRadius: "1rem", padding: "2rem", display: "flex", flexDirection: "column", position: "relative", background: "hsl(220,40%,7%)" }}>
                                    {plan.tag && (
                                        <div style={{ position: "absolute", top: "-12px", left: "50%", transform: "translateX(-50%)" }}>
                                            <span style={{ background: "#ffd700", color: "hsl(222,47%,4%)", fontSize: "0.65rem", fontWeight: 900, letterSpacing: "0.1em", padding: "0.25rem 1rem", borderRadius: "9999px" }}>{plan.tag}</span>
                                        </div>
                                    )}
                                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
                                        <div style={{ width: "48px", height: "48px", borderRadius: "12px", background: plan.isPopular ? "rgba(255,215,0,0.1)" : "rgba(0,230,118,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                                            {plan.isPopular ? <Star size={22} color="#ffd700" /> : <Zap size={22} color="#00e676" />}
                                        </div>
                                        <div>
                                            <div style={{ fontSize: "0.7rem", color: "hsl(215,20%,55%)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Plano</div>
                                            <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>{plan.name}</div>
                                        </div>
                                    </div>
                                    <div style={{ marginBottom: "1rem" }}>
                                        <div style={{ display: "flex", alignItems: "baseline", gap: "0.25rem" }}>
                                            <span style={{ fontSize: "0.875rem", color: "hsl(215,20%,55%)" }}>R$</span>
                                            <span style={{ fontSize: "3rem", fontWeight: 900 }}>{plan.price}</span>
                                            <span style={{ color: "hsl(215,20%,55%)", fontSize: "0.875rem" }}>/mês</span>
                                        </div>
                                        <p style={{ fontSize: "0.875rem", color: "hsl(215,20%,55%)", marginTop: "0.5rem", lineHeight: 1.5 }}>{plan.description}</p>
                                    </div>
                                    <button
                                        onClick={() => openLogin("register")}
                                        className={plan.isPopular ? "" : "piq-btn-primary"}
                                        style={{
                                            width: "100%", padding: "0.875rem", borderRadius: "0.75rem", fontSize: "1rem", fontWeight: 700,
                                            marginBottom: "2rem", cursor: "pointer", border: "none", transition: "all 0.2s",
                                            background: plan.isPopular ? "#ffd700" : "#00e676",
                                            color: "hsl(222,47%,4%)",
                                            boxShadow: plan.isPopular ? "0 0 20px rgba(255,215,0,0.3)" : "0 0 20px rgba(0,230,118,0.3)"
                                        }}
                                    >
                                        Assinar {plan.name}
                                    </button>
                                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", flex: 1 }}>
                                        {plan.features.map((feat) => (
                                            <div key={feat} style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                                                <div style={{ width: "20px", height: "20px", borderRadius: "50%", background: "rgba(0,230,118,0.15)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                                                    <Check size={12} color="#00e676" />
                                                </div>
                                                <span style={{ fontSize: "0.875rem", color: "hsl(210,40%,80%)" }}>{feat}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div style={{ textAlign: "center", marginTop: "2.5rem", fontSize: "0.875rem", color: "hsl(215,20%,55%)" }}>
                            <span style={{ color: "#00e676", fontWeight: 600 }}>7 dias de garantia</span> — Se não ficar satisfeito, devolvemos 100% do valor.
                        </div>
                    </div>
                </section>

                {/* ─── Footer ─── */}
                <footer style={{ padding: "2rem 1.5rem", borderTop: "1px solid rgba(255,255,255,0.06)", textAlign: "center" }}>
                    <p style={{ color: "hsl(215,20%,40%)", fontSize: "0.875rem" }}>
                        © 2025 PressureIQ — Todos os direitos reservados. Aposte com responsabilidade.
                    </p>
                </footer>

                {/* ─── Login Modal ─── */}
                <AnimatePresence>
                {showLoginModal && (
                    <motion.div
                        className="piq-modal-overlay"
                        onClick={(e) => e.target === e.currentTarget && setShowLoginModal(false)}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: reduceMotion ? 0.15 : 0.2 }}
                    >
                        <motion.div
                            style={{ position: "relative", width: "100%", maxWidth: tab === "plans" ? "780px" : "440px" }}
                            initial={{ maxWidth: tab === "plans" ? "780px" : "440px" }}
                            animate={{ maxWidth: tab === "plans" ? "780px" : "440px" }}
                            transition={{ duration: 0.3 }}
                        >
                            {/* Close button */}
                            <button
                                onClick={() => setShowLoginModal(false)}
                                style={{ position: "absolute", top: "-2.5rem", right: 0, background: "none", border: "none", color: "hsl(215,20%,55%)", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.25rem", fontSize: "0.875rem" }}
                            >
                                <X size={16} /> Fechar
                            </button>

                            <div className="piq-glass-strong piq-rounded-2xl" style={{ padding: "2rem", position: "relative", overflow: "hidden" }}>
                                {/* Corner glow */}
                                <div style={{ position: "absolute", top: 0, right: 0, width: "128px", height: "128px", background: "rgba(0,230,118,0.08)", borderRadius: "50%", filter: "blur(40px)", pointerEvents: "none" }} />

                                {/* Logo (stagger fade-in) */}
                                <motion.div
                                    initial="hidden"
                                    animate="visible"
                                    variants={fade(STAGGER_DELAYS.logo)}
                                    style={{ textAlign: "center", marginBottom: "1.5rem" }}
                                >
                                    <motion.div
                                        initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.92 }}
                                        animate={reduceMotion ? { opacity: 1 } : { opacity: 1, scale: 1 }}
                                        transition={reduceMotion ? { duration: 0.15 } : { duration: 0.4, ease: [0.34, 1.56, 0.64, 1] }}
                                        style={{ position: "relative", width: 72, height: 72, margin: "0 auto 0.75rem" }}
                                    >
                                        <Image
                                            src="/brand/logo-mark.png"
                                            alt="PressureIQ"
                                            fill
                                            priority
                                            sizes="72px"
                                            style={{ objectFit: "contain" }}
                                        />
                                    </motion.div>
                                </motion.div>

                                {/* Title (stagger fade-in) */}
                                <motion.div
                                    initial="hidden"
                                    animate="visible"
                                    variants={fade(STAGGER_DELAYS.title)}
                                    style={{ textAlign: "center", marginBottom: "2rem" }}
                                >
                                    <h2 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Pressure<span className="piq-gradient-text">IQ</span></h2>
                                    <p style={{ fontSize: "0.7rem", color: "hsl(215,20%,55%)", marginTop: "0.25rem", textTransform: "uppercase", letterSpacing: "0.15em" }}>Corner & Card Pressure Elite</p>
                                </motion.div>

                                {/* Error */}
                                {error && (
                                    <div style={{ background: "rgba(255,82,82,0.1)", border: "1px solid rgba(255,82,82,0.3)", borderRadius: "0.75rem", padding: "0.75rem 1rem", marginBottom: "1.5rem", fontSize: "0.875rem", color: "#ff5252" }}>
                                        {error}
                                    </div>
                                )}

                                {/* ─── Auth Tabs ─── */}
                                {tab !== "plans" && tab !== "verify" && (
                                    <>
                                        <motion.div
                                            initial="hidden"
                                            animate="visible"
                                            variants={fade(STAGGER_DELAYS.fields)}
                                            style={{ display: "flex", borderRadius: "0.75rem", overflow: "hidden", border: "1px solid rgba(255,255,255,0.08)", marginBottom: "2rem", background: "rgba(255,255,255,0.03)" }}
                                        >
                                            {(["login", "register"] as const).map((t) => (
                                                <button key={t} onClick={() => { setTab(t); setError(""); }} style={{ flex: 1, padding: "0.75rem", fontSize: "0.875rem", fontWeight: 600, border: "none", cursor: "pointer", transition: "all 0.2s", background: tab === t ? "#00e676" : "transparent", color: tab === t ? "hsl(222,47%,4%)" : "hsl(215,20%,55%)", fontFamily: "inherit" }}>
                                                    {t === "login" ? "Entrar" : "Criar Conta"}
                                                </button>
                                            ))}
                                        </motion.div>

                                        <motion.form
                                            onSubmit={tab === "login" ? handleLogin : handleRegister}
                                            style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
                                            initial="hidden"
                                            animate="visible"
                                            variants={fade(STAGGER_DELAYS.fields)}
                                        >
                                            {tab === "register" && (
                                                <>
                                                    <div>
                                                        <label className="piq-label">Nome completo</label>
                                                        <input className="piq-input" type="text" placeholder="Seu nome" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
                                                    </div>
                                                    <div>
                                                        <label className="piq-label">CPF</label>
                                                        <input className="piq-input" type="text" placeholder="000.000.000-00" value={cpf} onChange={(e) => {
                                                            const v = e.target.value.replace(/\D/g, "").slice(0, 11);
                                                            setCpf(v.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4").replace(/(\d{3})(\d{3})(\d{1,3})/, "$1.$2.$3").replace(/(\d{3})(\d{1,3})/, "$1.$2"));
                                                        }} required />
                                                    </div>
                                                    <div>
                                                        <label className="piq-label">WhatsApp (com DDD)</label>
                                                        <input className="piq-input" type="tel" placeholder="5511999999999" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} required />
                                                    </div>
                                                </>
                                            )}
                                            <div>
                                                <label className="piq-label">Email</label>
                                                <input className="piq-input" type="email" placeholder="seu@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
                                            </div>
                                            <div>
                                                <label className="piq-label">Senha</label>
                                                <div style={{ position: "relative" }}>
                                                    <input className="piq-input" type={showPass ? "text" : "password"} placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={tab === "register" ? 8 : undefined} style={{ paddingRight: "3rem" }} />
                                                    <button type="button" onClick={() => setShowPass(!showPass)} style={{ position: "absolute", right: "0.75rem", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "hsl(215,20%,55%)" }}>
                                                        {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                                                    </button>
                                                </div>
                                            </div>
                                            {tab === "login" && (
                                                <div style={{ textAlign: "right" }}>
                                                    <button type="button" style={{ background: "none", border: "none", color: "#00e676", fontSize: "0.75rem", cursor: "pointer" }}>Esqueci minha senha</button>
                                                </div>
                                            )}
                                            <motion.button
                                                type="submit"
                                                className="piq-btn-primary piq-glow-green"
                                                disabled={loading}
                                                style={{ padding: "0.875rem", borderRadius: "0.75rem", fontSize: "1rem", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", marginTop: "0.5rem" }}
                                                initial="hidden"
                                                animate="visible"
                                                variants={fade(STAGGER_DELAYS.button)}
                                                whileHover={reduceMotion || loading ? undefined : { scale: 1.02 }}
                                                whileTap={reduceMotion || loading ? undefined : { scale: 0.98 }}
                                            >
                                                <AnimatePresence mode="wait" initial={false}>
                                                    {loading ? (
                                                        <motion.span
                                                            key="spinner"
                                                            initial={{ opacity: 0 }}
                                                            animate={{ opacity: 1 }}
                                                            exit={{ opacity: 0 }}
                                                            transition={{ duration: 0.15 }}
                                                            style={{ display: "inline-block", width: "20px", height: "20px", border: "2px solid rgba(0,0,0,0.3)", borderTopColor: "hsl(222,47%,4%)", borderRadius: "50%", animation: "spin 0.7s linear infinite" }}
                                                        />
                                                    ) : (
                                                        <motion.span
                                                            key="label"
                                                            initial={{ opacity: 0 }}
                                                            animate={{ opacity: 1 }}
                                                            exit={{ opacity: 0 }}
                                                            transition={{ duration: 0.15 }}
                                                            style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
                                                        >
                                                            {tab === "login" ? "Acessar Plataforma" : "Criar Conta Grátis"} <ArrowRight size={16} />
                                                        </motion.span>
                                                    )}
                                                </AnimatePresence>
                                            </motion.button>
                                        </motion.form>

                                        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", marginTop: "1.5rem", fontSize: "0.75rem", color: "hsl(215,20%,45%)" }}>
                                            <Lock size={12} />
                                            <span>Conexão segura com criptografia SSL 256-bit</span>
                                        </div>
                                    </>
                                )}

                                {/* ─── Verify Email Tab ─── */}
                                {tab === "verify" && (
                                    <form onSubmit={handleVerifyEmail} style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                                        <div style={{ textAlign: "center" }}>
                                            <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>📧</div>
                                            <h3 style={{ margin: "0 0 8px", fontSize: "1.2rem", fontWeight: 700, color: "#fff" }}>Verifique seu email</h3>
                                            <p style={{ margin: 0, fontSize: "0.875rem", color: "hsl(215,20%,55%)", lineHeight: 1.5 }}>
                                                Enviamos um código de 6 dígitos para<br />
                                                <strong style={{ color: "#00e676" }}>{pendingEmail || email}</strong>
                                            </p>
                                        </div>
                                        <div>
                                            <label className="piq-label">Código de verificação</label>
                                            <input
                                                className="piq-input"
                                                type="text"
                                                placeholder="000000"
                                                value={verifyCode}
                                                onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                                                maxLength={6}
                                                required
                                                style={{ textAlign: "center", fontSize: "1.5rem", letterSpacing: "0.5rem", fontFamily: "monospace" }}
                                            />
                                        </div>
                                        <button type="submit" className="piq-btn-primary piq-glow-green" disabled={loading || verifyCode.length < 6} style={{ padding: "0.875rem", borderRadius: "0.75rem", fontSize: "1rem", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}>
                                            {loading ? <span style={{ display: "inline-block", width: "20px", height: "20px", border: "2px solid rgba(0,0,0,0.3)", borderTopColor: "hsl(222,47%,4%)", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} /> : <>Verificar Email <ArrowRight size={16} /></>}
                                        </button>
                                        <div style={{ textAlign: "center" }}>
                                            <button type="button" onClick={handleResendCode} disabled={loading} style={{ background: "none", border: "none", color: "#00e676", fontSize: "0.8rem", cursor: "pointer", textDecoration: "underline" }}>
                                                Não recebeu? Reenviar código
                                            </button>
                                        </div>
                                        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", fontSize: "0.75rem", color: "hsl(215,20%,45%)" }}>
                                            <Lock size={12} />
                                            <span>Código válido por 15 minutos</span>
                                        </div>
                                    </form>
                                )}

                                {/* ─── Plans Tab ─── */}
                                {tab === "plans" && (
                                    <div>
                                        <h3 style={{ textAlign: "center", fontSize: "1.25rem", fontWeight: 700, marginBottom: "0.5rem" }}>Escolha seu Plano</h3>
                                        <p style={{ textAlign: "center", color: "hsl(215,20%,55%)", fontSize: "0.875rem", marginBottom: "2rem" }}>Conta criada! Agora escolha como quer apostar.</p>
                                        {error && (
                                            <div style={{ background: "rgba(255,82,82,0.1)", border: "1px solid rgba(255,82,82,0.3)", borderRadius: "0.75rem", padding: "0.75rem 1rem", marginBottom: "1.5rem", fontSize: "0.875rem", color: "#ff5252" }}>{error}</div>
                                        )}
                                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1.5rem" }}>
                                            {plans.map((plan) => (
                                                <div key={plan.name} className={plan.isPopular ? "piq-border-glow-gold" : "piq-border-glow"} style={{ borderRadius: "1rem", padding: "1.5rem", position: "relative", background: "hsl(220,40%,7%)" }}>
                                                    {plan.tag && (
                                                        <div style={{ position: "absolute", top: "-12px", left: "50%", transform: "translateX(-50%)" }}>
                                                            <span style={{ background: "#ffd700", color: "hsl(222,47%,4%)", fontSize: "0.6rem", fontWeight: 900, letterSpacing: "0.1em", padding: "0.2rem 0.75rem", borderRadius: "9999px" }}>{plan.tag}</span>
                                                        </div>
                                                    )}
                                                    <div style={{ textAlign: "center", marginBottom: "1.25rem" }}>
                                                        <div style={{ fontSize: "0.7rem", color: "hsl(215,20%,55%)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Plano</div>
                                                        <div style={{ fontSize: "1.5rem", fontWeight: 800 }}>{plan.name}</div>
                                                        <div style={{ display: "flex", alignItems: "baseline", gap: "0.25rem", justifyContent: "center", marginTop: "0.5rem" }}>
                                                            <span style={{ fontSize: "0.8rem", color: "hsl(215,20%,55%)" }}>R$</span>
                                                            <span style={{ fontSize: "2.5rem", fontWeight: 900 }}>{plan.price}</span>
                                                            <span style={{ color: "hsl(215,20%,55%)", fontSize: "0.8rem" }}>/mês</span>
                                                        </div>
                                                    </div>
                                                    <button
                                                        onClick={() => handleCheckout(plan.planKey)}
                                                        disabled={loading}
                                                        style={{ width: "100%", padding: "0.75rem", borderRadius: "0.75rem", fontSize: "0.95rem", fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", border: "none", marginBottom: "1.25rem", background: plan.isPopular ? "#ffd700" : "#00e676", color: "hsl(222,47%,4%)", opacity: loading ? 0.7 : 1 }}
                                                    >
                                                        {loading ? "Aguarde..." : `Assinar ${plan.name}`}
                                                    </button>
                                                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                                        {plan.features.slice(0, 4).map((feat) => (
                                                            <div key={feat} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                                                <Check size={12} color="#00e676" />
                                                                <span style={{ fontSize: "0.8rem", color: "hsl(210,40%,75%)" }}>{feat}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                        <div style={{ textAlign: "center", marginTop: "1.5rem" }}>
                                            <button onClick={() => router.push("/dashboard")} style={{ background: "none", border: "none", color: "hsl(215,20%,55%)", fontSize: "0.8rem", cursor: "pointer", textDecoration: "underline" }}>
                                                Pular por agora e acessar o dashboard
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </motion.div>
                )}
                </AnimatePresence>

                <style>{`
                    @keyframes spin { to { transform: rotate(360deg); } }
                    @keyframes bounce { 0%,100%{transform:translateX(-50%) translateY(0)} 50%{transform:translateX(-50%) translateY(-8px)} }
                `}</style>
            </div>
        </>
    );
}
