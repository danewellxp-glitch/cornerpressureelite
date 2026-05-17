"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { X, Eye, EyeOff, ArrowRight, Check, Mail, Loader2 } from "lucide-react";
import { login, register, verifyEmail, resendVerification, checkout } from "@/lib/api";

export type AuthTab = "login" | "register" | "verify" | "plans";

type Props = {
    open: boolean;
    tab: AuthTab;
    reason?: string | null;
    onClose: () => void;
    onTabChange: (tab: AuthTab) => void;
};

const maskCpf = (v: string) =>
    v
        .replace(/\D/g, "")
        .slice(0, 11)
        .replace(/(\d{3})(\d)/, "$1.$2")
        .replace(/(\d{3})(\d)/, "$1.$2")
        .replace(/(\d{3})(\d{1,2})$/, "$1-$2");

const onlyDigits = (v: string) => v.replace(/\D/g, "");

const persistSession = (access_token: string, user: unknown) => {
    document.cookie = `cpes-auth=${access_token}; path=/; max-age=2592000; SameSite=Lax`;
    localStorage.setItem("token", access_token);
    localStorage.setItem("user", JSON.stringify(user));
};

const plans = [
    { name: "Pro", price: "39,90", planKey: "pro" as const, perks: ["Sinais ilimitados", "WhatsApp em tempo real", "Dashboard completo"] },
    { name: "Max", price: "89,90", planKey: "max" as const, perks: ["Tudo do Pro", "Robô automático", "VIP + multi-casa"], popular: true },
];

export function AuthModal({ open, tab, reason, onClose, onTabChange }: Props) {
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPwd, setShowPwd] = useState(false);
    const [fullName, setFullName] = useState("");
    const [whatsapp, setWhatsapp] = useState("");
    const [cpf, setCpf] = useState("");
    const [code, setCode] = useState("");
    const [pendingEmail, setPendingEmail] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) {
            setError(null);
            setLoading(false);
        }
    }, [open]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            const data = await login(email, password);
            persistSession(data.access_token, data.user);
            router.push("/dashboard");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Credenciais inválidas.");
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        if (password.length < 8) {
            setError("A senha precisa ter no mínimo 8 caracteres.");
            return;
        }
        setLoading(true);
        try {
            await register({
                email,
                password,
                full_name: fullName,
                whatsapp: onlyDigits(whatsapp),
                cpf: onlyDigits(cpf),
            });
            setPendingEmail(email);
            onTabChange("verify");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Não foi possível criar a conta.");
        } finally {
            setLoading(false);
        }
    };

    const handleVerify = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        if (code.length !== 6) {
            setError("O código tem 6 dígitos.");
            return;
        }
        setLoading(true);
        try {
            const data = await verifyEmail(pendingEmail || email, code);
            persistSession(data.access_token, data.user);
            onTabChange("plans");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Código inválido.");
        } finally {
            setLoading(false);
        }
    };

    const handleResendCode = async () => {
        setError(null);
        setLoading(true);
        try {
            await resendVerification(pendingEmail || email);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Erro ao reenviar código.");
        } finally {
            setLoading(false);
        }
    };

    const handleCheckout = async (planKey: "pro" | "max") => {
        setError(null);
        setLoading(true);
        try {
            const token = localStorage.getItem("token");
            if (!token) throw new Error("Usuário não autenticado");
            const data = await checkout(planKey, token);
            if (data.checkoutUrl) {
                window.location.href = data.checkoutUrl;
            } else {
                throw new Error("Erro ao gerar link de pagamento");
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Falha ao iniciar checkout.");
            setLoading(false);
        }
    };

    return (
        <AnimatePresence>
            {open && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 grid place-items-center p-4 backdrop-blur-md"
                    style={{ background: "oklch(0.18 0.03 230 / 0.8)" }}
                    onClick={onClose}
                >
                    <motion.div
                        initial={{ opacity: 0, y: 20, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 10, scale: 0.98 }}
                        transition={{ duration: 0.2 }}
                        onClick={(e) => e.stopPropagation()}
                        className="relative w-full max-w-md bg-card border border-border rounded-2xl p-6 shadow-2xl max-h-[92vh] overflow-y-auto"
                        role="dialog"
                        aria-modal="true"
                        aria-label="Autenticação PressureIQ"
                    >
                        <button
                            onClick={onClose}
                            aria-label="Fechar"
                            className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition"
                        >
                            <X className="w-5 h-5" />
                        </button>

                        {tab === "plans" && reason === "unpaid" && (
                            <div className="mb-4 p-3 rounded-md bg-mint/10 border border-mint/30 text-sm text-foreground">
                                <strong className="font-display">Finalize sua assinatura</strong>
                                <p className="text-xs text-muted-foreground mt-1">
                                    Você precisa concluir o pagamento para acessar o painel.
                                </p>
                            </div>
                        )}

                        {(tab === "login" || tab === "register") && (
                            <div className="mb-6">
                                <div className="font-mono text-xs text-mint mb-2">// PressureIQ · CPES</div>
                                <div className="flex gap-1 p-1 bg-secondary rounded-lg">
                                    <button
                                        onClick={() => onTabChange("login")}
                                        className={`flex-1 text-sm font-medium py-2 rounded-md transition ${
                                            tab === "login" ? "bg-card text-foreground shadow" : "text-muted-foreground"
                                        }`}
                                    >
                                        Entrar
                                    </button>
                                    <button
                                        onClick={() => onTabChange("register")}
                                        className={`flex-1 text-sm font-medium py-2 rounded-md transition ${
                                            tab === "register" ? "bg-card text-foreground shadow" : "text-muted-foreground"
                                        }`}
                                    >
                                        Criar conta
                                    </button>
                                </div>
                            </div>
                        )}

                        {tab === "login" && (
                            <form onSubmit={handleLogin} className="space-y-4">
                                <Field label="Email">
                                    <input
                                        type="email"
                                        required
                                        autoComplete="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        className="piq-auth-input"
                                        placeholder="voce@exemplo.com"
                                    />
                                </Field>
                                <Field label="Senha">
                                    <div className="relative">
                                        <input
                                            type={showPwd ? "text" : "password"}
                                            required
                                            autoComplete="current-password"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            className="piq-auth-input pr-10"
                                            placeholder="••••••••"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPwd((v) => !v)}
                                            aria-label={showPwd ? "Ocultar senha" : "Mostrar senha"}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                        >
                                            {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                        </button>
                                    </div>
                                </Field>

                                {error && <ErrorMsg>{error}</ErrorMsg>}

                                <SubmitButton loading={loading}>Entrar</SubmitButton>
                            </form>
                        )}

                        {tab === "register" && (
                            <form onSubmit={handleRegister} className="space-y-4">
                                <Field label="Nome completo">
                                    <input
                                        type="text"
                                        required
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        className="piq-auth-input"
                                        autoComplete="name"
                                    />
                                </Field>
                                <Field label="Email">
                                    <input
                                        type="email"
                                        required
                                        autoComplete="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        className="piq-auth-input"
                                    />
                                </Field>
                                <div className="grid grid-cols-2 gap-3">
                                    <Field label="WhatsApp">
                                        <input
                                            type="tel"
                                            required
                                            inputMode="numeric"
                                            value={whatsapp}
                                            onChange={(e) => setWhatsapp(onlyDigits(e.target.value).slice(0, 13))}
                                            className="piq-auth-input"
                                            placeholder="11999999999"
                                            autoComplete="tel"
                                        />
                                    </Field>
                                    <Field label="CPF">
                                        <input
                                            type="text"
                                            required
                                            inputMode="numeric"
                                            value={cpf}
                                            onChange={(e) => setCpf(maskCpf(e.target.value))}
                                            className="piq-auth-input"
                                            placeholder="000.000.000-00"
                                        />
                                    </Field>
                                </div>
                                <Field label="Senha (mín. 8)">
                                    <input
                                        type="password"
                                        required
                                        minLength={8}
                                        autoComplete="new-password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="piq-auth-input"
                                    />
                                </Field>

                                {error && <ErrorMsg>{error}</ErrorMsg>}

                                <SubmitButton loading={loading}>Criar conta</SubmitButton>
                            </form>
                        )}

                        {tab === "verify" && (
                            <div>
                                <div className="text-center mb-6">
                                    <div className="w-12 h-12 mx-auto rounded-full bg-mint/15 border border-mint/40 grid place-items-center mb-3">
                                        <Mail className="w-5 h-5 text-mint" />
                                    </div>
                                    <h3 className="font-display text-xl font-bold text-foreground">Confirme seu email</h3>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        Enviamos um código de 6 dígitos para <strong>{pendingEmail || email || "seu email"}</strong>.
                                    </p>
                                </div>
                                <form onSubmit={handleVerify} className="space-y-4">
                                    <input
                                        type="text"
                                        required
                                        inputMode="numeric"
                                        maxLength={6}
                                        value={code}
                                        onChange={(e) => setCode(onlyDigits(e.target.value).slice(0, 6))}
                                        className="piq-auth-input text-center font-mono text-2xl tracking-[0.5em]"
                                        placeholder="••••••"
                                        autoComplete="one-time-code"
                                        autoFocus
                                    />

                                    {error && <ErrorMsg>{error}</ErrorMsg>}

                                    <SubmitButton loading={loading}>Confirmar</SubmitButton>

                                    <button
                                        type="button"
                                        onClick={handleResendCode}
                                        disabled={loading}
                                        className="w-full text-xs text-muted-foreground hover:text-foreground disabled:opacity-60"
                                    >
                                        Reenviar código
                                    </button>
                                </form>
                            </div>
                        )}

                        {tab === "plans" && (
                            <div>
                                <div className="mb-5">
                                    <div className="font-mono text-xs text-mint mb-2">// ESCOLHA SEU PLANO</div>
                                    <h3 className="font-display text-xl font-bold text-foreground">
                                        {reason === "unpaid" ? "Finalize sua assinatura" : "Pronto para começar"}
                                    </h3>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        Cancele quando quiser direto pelo painel.
                                    </p>
                                </div>

                                <div className="space-y-3">
                                    {plans.map((p) => (
                                        <button
                                            key={p.planKey}
                                            onClick={() => handleCheckout(p.planKey)}
                                            disabled={loading}
                                            className={`w-full text-left p-4 rounded-xl border transition disabled:opacity-60 ${
                                                p.popular
                                                    ? "border-mint bg-mint/5 hover:bg-mint/10"
                                                    : "border-border bg-secondary/40 hover:bg-secondary"
                                            }`}
                                        >
                                            <div className="flex items-baseline justify-between mb-2">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-display font-bold text-foreground">{p.name}</span>
                                                    {p.popular && (
                                                        <span className="text-[10px] font-mono text-mint border border-mint/40 px-1.5 py-0.5 rounded">
                                                            POPULAR
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="font-display font-bold text-foreground tabular-nums">
                                                    R$ {p.price}
                                                    <span className="text-xs text-muted-foreground font-sans">/mês</span>
                                                </div>
                                            </div>
                                            <ul className="space-y-1">
                                                {p.perks.map((perk) => (
                                                    <li key={perk} className="flex items-center gap-2 text-xs text-muted-foreground">
                                                        <Check className="w-3 h-3 text-mint" />
                                                        {perk}
                                                    </li>
                                                ))}
                                            </ul>
                                        </button>
                                    ))}
                                </div>

                                {error && <div className="mt-4"><ErrorMsg>{error}</ErrorMsg></div>}
                            </div>
                        )}
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <label className="block">
            <span className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wider">
                {label}
            </span>
            {children}
        </label>
    );
}

function ErrorMsg({ children }: { children: React.ReactNode }) {
    return (
        <div className="text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-md px-3 py-2">
            {children}
        </div>
    );
}

function SubmitButton({
    loading,
    children,
}: {
    loading: boolean;
    children: React.ReactNode;
}) {
    return (
        <button
            type="submit"
            disabled={loading}
            className="group w-full inline-flex items-center justify-center gap-2 bg-mint text-primary-foreground font-medium px-5 py-3 rounded-md hover:bg-mint-bright transition disabled:opacity-60"
        >
            {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
                <>
                    {children}
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition" />
                </>
            )}
        </button>
    );
}
