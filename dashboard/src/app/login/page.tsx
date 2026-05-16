"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
} from "lucide-react";
import {
  login,
  register,
  checkout,
  verifyEmail,
  resendVerification,
} from "@/lib/api";

type Tab = "login" | "register" | "verify" | "plans";

const PLANS = [
  {
    key: "pro",
    name: "Pro",
    price: "39,90",
    tagline: "Sinais qualificados + dashboard + histórico.",
    features: [
      "Sinais de Escanteios ilimitados",
      "Alertas WhatsApp em tempo real",
      "Dashboard de performance",
      "9 ligas monitoradas",
    ],
    featured: false,
  },
  {
    key: "max",
    name: "Max",
    price: "89,90",
    tagline: "Automação total + cards/gols + banca integrada.",
    features: [
      "Tudo do plano Pro",
      "Sinais Cartões + Gols",
      "Robô apostador automático",
      "Gestão de banca integrada",
    ],
    featured: true,
  },
] as const;

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("login");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [cpf, setCpf] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [pendingEmail, setPendingEmail] = useState("");

  const persistSession = (token: string, user: unknown) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    document.cookie = `cpes-auth=${token}; path=/; max-age=86400; SameSite=Lax`;
  };

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(email, password);
      persistSession(data.access_token, data.user);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao fazer login.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({
        email,
        password,
        full_name: fullName,
        whatsapp: whatsapp.replace(/\D/g, ""),
        cpf: cpf.replace(/\D/g, ""),
      });
      setPendingEmail(email);
      setTab("verify");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar conta.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await verifyEmail(pendingEmail || email, verifyCode);
      persistSession(data.access_token, data.user);
      setTab("plans");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Código inválido.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setError("");
    setLoading(true);
    try {
      await resendVerification(pendingEmail || email);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao reenviar código.");
    } finally {
      setLoading(false);
    }
  };

  const handleCheckout = async (planKey: string) => {
    setError("");
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error("Sessão não encontrada.");
      const data = await checkout(planKey, token);
      if (data?.checkoutUrl) {
        window.location.href = data.checkoutUrl;
      } else {
        throw new Error("Link de pagamento indisponível.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no checkout.");
      setLoading(false);
    }
  };

  const cardWidth =
    tab === "plans"
      ? "max-w-[760px]"
      : tab === "register"
        ? "max-w-[460px]"
        : "max-w-[420px]";

  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--bg)] text-[var(--text)]">
      <BackgroundLayers />
      <TopBar />

      <main className="relative z-[2] mx-auto flex min-h-[calc(100vh-64px)] w-full items-center justify-center px-6 py-12">
        <motion.div
          layout
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className={`relative w-full ${cardWidth}`}
        >
          <div className="relative overflow-hidden rounded-2xl border border-[var(--border-bright)] bg-[var(--bg-card)] p-8 md:p-10">
            <span
              className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full"
              style={{
                background: "rgba(16, 185, 129, 0.1)",
                filter: "blur(60px)",
              }}
              aria-hidden="true"
            />

            <AnimatePresence mode="wait">
              {tab === "login" && (
                <PaneLogin
                  key="login"
                  email={email}
                  setEmail={setEmail}
                  password={password}
                  setPassword={setPassword}
                  showPass={showPass}
                  setShowPass={setShowPass}
                  loading={loading}
                  error={error}
                  onSubmit={handleLogin}
                  onSwitchTab={(t) => {
                    setError("");
                    setTab(t);
                  }}
                />
              )}
              {tab === "register" && (
                <PaneRegister
                  key="register"
                  email={email}
                  setEmail={setEmail}
                  password={password}
                  setPassword={setPassword}
                  fullName={fullName}
                  setFullName={setFullName}
                  whatsapp={whatsapp}
                  setWhatsapp={setWhatsapp}
                  cpf={cpf}
                  setCpf={setCpf}
                  showPass={showPass}
                  setShowPass={setShowPass}
                  loading={loading}
                  error={error}
                  onSubmit={handleRegister}
                  onSwitchTab={(t) => {
                    setError("");
                    setTab(t);
                  }}
                />
              )}
              {tab === "verify" && (
                <PaneVerify
                  key="verify"
                  emailShown={pendingEmail || email}
                  verifyCode={verifyCode}
                  setVerifyCode={setVerifyCode}
                  loading={loading}
                  error={error}
                  onSubmit={handleVerify}
                  onResend={handleResend}
                  onBack={() => {
                    setError("");
                    setTab("register");
                  }}
                />
              )}
              {tab === "plans" && (
                <PanePlans
                  key="plans"
                  loading={loading}
                  error={error}
                  onChoose={handleCheckout}
                  onSkip={() => router.push("/dashboard")}
                />
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </main>
    </div>
  );
}

/* ─────────── Layout pieces ─────────── */

function BackgroundLayers() {
  return (
    <>
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(16, 185, 129, 0.012) 2px, rgba(16, 185, 129, 0.012) 4px)",
        }}
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute inset-0 z-[1] overflow-hidden" aria-hidden="true">
        <div
          className="absolute -left-[15%] -top-[20%] h-[70%] w-[60%]"
          style={{
            background:
              "radial-gradient(circle, rgba(16, 185, 129, 0.10) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
        <div
          className="absolute -bottom-[30%] -right-[10%] h-[60%] w-[50%]"
          style={{
            background:
              "radial-gradient(circle, rgba(34, 211, 238, 0.06) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
      </div>
    </>
  );
}

function TopBar() {
  return (
    <header className="relative z-[3] border-b border-[var(--border)] bg-[var(--bg)]/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5 font-mono text-[15px] font-bold tracking-tight">
          <span
            className="relative flex h-7 w-7 items-center justify-center rounded-md bg-[var(--green)] font-extrabold text-[var(--bg)]"
            aria-hidden="true"
          >
            ⚡
            <span
              className="absolute inset-0 -z-10 rounded-md bg-[var(--green)] opacity-50 blur-[12px]"
              aria-hidden="true"
            />
          </span>
          <span className="text-[var(--text)]">PressureIQ</span>
          <span className="rounded bg-[var(--border)] px-1.5 py-0.5 text-[10px] font-medium tracking-wider text-[var(--text-muted)]">
            CPES
          </span>
        </Link>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-[13px] text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
        >
          <ChevronLeft size={14} />
          Voltar para o site
        </Link>
      </div>
    </header>
  );
}

/* ─────────── Reusable form bits ─────────── */

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--green)]">
      <span className="h-px w-6 bg-[var(--green)]" />
      {children}
    </div>
  );
}

function HeadingDisplay({ children, accent }: { children: React.ReactNode; accent?: string }) {
  return (
    <h1 className="mb-6 text-[clamp(28px,4vw,36px)] font-bold leading-tight tracking-[-0.03em]">
      {children}
      {accent && (
        <>
          {" "}
          <em
            className="inline-block bg-clip-text font-[family-name:var(--font-bricolage)] font-bold not-italic tracking-[-0.025em] text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(135deg, var(--green) 0%, var(--cyan) 100%)",
              WebkitBackgroundClip: "text",
            }}
          >
            {accent}
          </em>
        </>
      )}
    </h1>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">
      {children}
    </label>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-md border border-[var(--border-bright)] bg-black/30 px-4 py-3 text-[14px] text-[var(--text)] placeholder:text-[var(--text-dim)] outline-none transition-colors focus:border-[var(--green)] focus:ring-2 focus:ring-[rgba(16,185,129,0.15)] ${props.className || ""}`}
    />
  );
}

function PrimaryButton({
  loading,
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={loading || rest.disabled}
      className="group relative inline-flex w-full items-center justify-center gap-2 overflow-hidden rounded-md bg-[var(--green)] px-4 py-3.5 text-[14px] font-semibold text-[var(--bg)] transition-all hover:-translate-y-px disabled:opacity-60 disabled:hover:translate-y-0"
    >
      <span className="pointer-events-none absolute inset-0 bg-[var(--green-bright)] opacity-0 transition-opacity group-hover:opacity-100" />
      <span className="relative z-10 inline-flex items-center gap-2">
        {loading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <>
            {children}
            <ArrowRight size={14} />
          </>
        )}
      </span>
    </button>
  );
}

function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="mb-5 rounded-md border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] px-3 py-2.5 text-[13px] text-[var(--red)]"
    >
      {message}
    </div>
  );
}

function TabSwitch({
  tab,
  onSwitch,
}: {
  tab: "login" | "register";
  onSwitch: (t: "login" | "register") => void;
}) {
  return (
    <div className="mb-6 flex overflow-hidden rounded-md border border-[var(--border-bright)] bg-black/20">
      {(["login", "register"] as const).map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => onSwitch(t)}
          className={`flex-1 px-4 py-2.5 text-[13px] font-semibold transition-colors ${
            tab === t
              ? "bg-[var(--green)] text-[var(--bg)]"
              : "text-[var(--text-muted)] hover:text-[var(--text)]"
          }`}
        >
          {t === "login" ? "Entrar" : "Criar conta"}
        </button>
      ))}
    </div>
  );
}

function SslHint() {
  return (
    <div className="mt-6 flex items-center justify-center gap-2 text-[11px] text-[var(--text-dim)]">
      <Lock size={12} />
      <span>Conexão segura SSL 256-bit</span>
    </div>
  );
}

const paneAnim = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.25, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
};

/* ─────────── Panes ─────────── */

function PaneLogin({
  email,
  setEmail,
  password,
  setPassword,
  showPass,
  setShowPass,
  loading,
  error,
  onSubmit,
  onSwitchTab,
}: {
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  showPass: boolean;
  setShowPass: (v: boolean) => void;
  loading: boolean;
  error: string;
  onSubmit: (e: FormEvent) => void;
  onSwitchTab: (t: "login" | "register") => void;
}) {
  return (
    <motion.div {...paneAnim}>
      <Eyebrow>ACESSO</Eyebrow>
      <HeadingDisplay accent="conta.">Entre na sua</HeadingDisplay>
      <TabSwitch tab="login" onSwitch={onSwitchTab} />
      <ErrorBanner message={error} />

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div>
          <Label>Email</Label>
          <Input
            type="email"
            placeholder="seu@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <Label>Senha</Label>
          <div className="relative">
            <Input
              type={showPass ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="pr-12"
            />
            <button
              type="button"
              onClick={() => setShowPass(!showPass)}
              aria-label={showPass ? "Ocultar senha" : "Mostrar senha"}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
            >
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <div className="text-right">
          <button
            type="button"
            className="text-[12px] text-[var(--green)] transition-opacity hover:opacity-80"
          >
            Esqueci minha senha
          </button>
        </div>
        <PrimaryButton type="submit" loading={loading}>
          Acessar plataforma
        </PrimaryButton>
      </form>

      <SslHint />
    </motion.div>
  );
}

function PaneRegister({
  email,
  setEmail,
  password,
  setPassword,
  fullName,
  setFullName,
  whatsapp,
  setWhatsapp,
  cpf,
  setCpf,
  showPass,
  setShowPass,
  loading,
  error,
  onSubmit,
  onSwitchTab,
}: {
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  fullName: string;
  setFullName: (v: string) => void;
  whatsapp: string;
  setWhatsapp: (v: string) => void;
  cpf: string;
  setCpf: (v: string) => void;
  showPass: boolean;
  setShowPass: (v: boolean) => void;
  loading: boolean;
  error: string;
  onSubmit: (e: FormEvent) => void;
  onSwitchTab: (t: "login" | "register") => void;
}) {
  const formatCpf = (raw: string) =>
    raw
      .replace(/\D/g, "")
      .slice(0, 11)
      .replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4")
      .replace(/(\d{3})(\d{3})(\d{1,3})$/, "$1.$2.$3")
      .replace(/(\d{3})(\d{1,3})$/, "$1.$2");

  return (
    <motion.div {...paneAnim}>
      <Eyebrow>ABRIR CONTA</Eyebrow>
      <HeadingDisplay accent="vantagem.">Comece com</HeadingDisplay>
      <TabSwitch tab="register" onSwitch={onSwitchTab} />
      <ErrorBanner message={error} />

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div>
          <Label>Nome completo</Label>
          <Input
            type="text"
            placeholder="Seu nome"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            autoComplete="name"
          />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label>CPF</Label>
            <Input
              type="text"
              placeholder="000.000.000-00"
              value={cpf}
              onChange={(e) => setCpf(formatCpf(e.target.value))}
              required
              inputMode="numeric"
            />
          </div>
          <div>
            <Label>WhatsApp</Label>
            <Input
              type="tel"
              placeholder="5511999999999"
              value={whatsapp}
              onChange={(e) => setWhatsapp(e.target.value)}
              required
              inputMode="tel"
            />
          </div>
        </div>
        <div>
          <Label>Email</Label>
          <Input
            type="email"
            placeholder="seu@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <Label>Senha (mín. 8 caracteres)</Label>
          <div className="relative">
            <Input
              type={showPass ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="pr-12"
            />
            <button
              type="button"
              onClick={() => setShowPass(!showPass)}
              aria-label={showPass ? "Ocultar senha" : "Mostrar senha"}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
            >
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <PrimaryButton type="submit" loading={loading}>
          Criar conta
        </PrimaryButton>
      </form>

      <p className="mt-5 text-center text-[12px] leading-relaxed text-[var(--text-dim)]">
        Ao criar conta, você concorda com nossos{" "}
        <Link href="/legal/termos" className="text-[var(--text-muted)] underline hover:text-[var(--text)]">
          Termos
        </Link>{" "}
        e{" "}
        <Link href="/legal/privacidade" className="text-[var(--text-muted)] underline hover:text-[var(--text)]">
          Privacidade
        </Link>
        .
      </p>
    </motion.div>
  );
}

function PaneVerify({
  emailShown,
  verifyCode,
  setVerifyCode,
  loading,
  error,
  onSubmit,
  onResend,
  onBack,
}: {
  emailShown: string;
  verifyCode: string;
  setVerifyCode: (v: string) => void;
  loading: boolean;
  error: string;
  onSubmit: (e: FormEvent) => void;
  onResend: () => void;
  onBack: () => void;
}) {
  return (
    <motion.div {...paneAnim}>
      <Eyebrow>VERIFICAÇÃO</Eyebrow>
      <HeadingDisplay accent="email.">Confira seu</HeadingDisplay>

      <p className="mb-6 flex items-center gap-2 text-[14px] text-[var(--text-muted)]">
        <Mail size={16} className="text-[var(--green)]" />
        Enviamos um código de 6 dígitos para{" "}
        <strong className="text-[var(--text)]">{emailShown}</strong>
      </p>

      <ErrorBanner message={error} />

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div>
          <Label>Código de verificação</Label>
          <Input
            type="text"
            value={verifyCode}
            onChange={(e) =>
              setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))
            }
            placeholder="000000"
            maxLength={6}
            required
            inputMode="numeric"
            className="text-center font-mono text-[24px] tracking-[0.5em]"
          />
        </div>
        <PrimaryButton type="submit" loading={loading} disabled={verifyCode.length < 6}>
          Verificar
        </PrimaryButton>
      </form>

      <div className="mt-6 flex flex-col items-center gap-2 text-[12px]">
        <button
          type="button"
          onClick={onResend}
          disabled={loading}
          className="text-[var(--green)] underline transition-opacity hover:opacity-80 disabled:opacity-40"
        >
          Não recebeu? Reenviar código
        </button>
        <button
          type="button"
          onClick={onBack}
          className="text-[var(--text-dim)] transition-colors hover:text-[var(--text-muted)]"
        >
          ← Voltar
        </button>
      </div>
    </motion.div>
  );
}

function PanePlans({
  loading,
  error,
  onChoose,
  onSkip,
}: {
  loading: boolean;
  error: string;
  onChoose: (planKey: string) => void;
  onSkip: () => void;
}) {
  return (
    <motion.div {...paneAnim}>
      <Eyebrow>CONTA CRIADA</Eyebrow>
      <HeadingDisplay accent="plano.">Escolha seu</HeadingDisplay>
      <p className="mb-8 text-[14px] text-[var(--text-muted)]">
        Comece em qualquer plano. Cancele quando quiser, sem fidelidade.
      </p>

      <ErrorBanner message={error} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {PLANS.map((plan) => (
          <div
            key={plan.key}
            className={`relative flex flex-col rounded-xl border p-6 ${
              plan.featured
                ? "border-[var(--green)] bg-[var(--bg-elevated)]"
                : "border-[var(--border-bright)] bg-[var(--bg-card)]"
            }`}
            style={
              plan.featured
                ? {
                    boxShadow:
                      "0 0 0 1px rgba(16, 185, 129, 0.2), 0 16px 48px -16px rgba(16, 185, 129, 0.18)",
                  }
                : undefined
            }
          >
            {plan.featured && (
              <span className="absolute -top-px right-4 rounded-b-md bg-[var(--green)] px-2 py-1 font-mono text-[9px] font-bold uppercase tracking-widest text-[var(--bg)]">
                MAIS POPULAR
              </span>
            )}
            <div
              className={`mb-1 text-[12px] font-semibold uppercase tracking-wider ${
                plan.featured ? "text-[var(--green)]" : "text-[var(--text-muted)]"
              }`}
            >
              {plan.name}
            </div>
            <div className="mb-4 min-h-[36px] text-[12px] text-[var(--text-dim)]">
              {plan.tagline}
            </div>
            <div className="mb-5 flex items-baseline gap-1.5 font-mono text-[36px] font-extrabold tracking-tight">
              <span className="text-[14px] text-[var(--text-muted)]">R$</span>
              <span>{plan.price}</span>
              <span className="font-[family-name:var(--font-geist)] text-[12px] font-medium text-[var(--text-muted)]">
                /mês
              </span>
            </div>
            <ul className="mb-5 flex-1 list-none space-y-2">
              {plan.features.map((f) => (
                <li
                  key={f}
                  className="flex items-start gap-2 text-[13px] text-[var(--text-muted)]"
                >
                  <Check size={14} strokeWidth={3} className="mt-0.5 shrink-0 text-[var(--green)]" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => onChoose(plan.key)}
              disabled={loading}
              className={`group relative inline-flex w-full items-center justify-center gap-2 overflow-hidden rounded-md px-4 py-3 text-[14px] font-semibold transition-all hover:-translate-y-px disabled:opacity-60 disabled:hover:translate-y-0 ${
                plan.featured
                  ? "bg-[var(--green)] text-[var(--bg)]"
                  : "border border-[var(--border-bright)] bg-transparent text-[var(--text)] hover:border-[var(--text-dim)] hover:bg-[var(--bg-elevated)]"
              }`}
            >
              {plan.featured && (
                <span className="pointer-events-none absolute inset-0 bg-[var(--green-bright)] opacity-0 transition-opacity group-hover:opacity-100" />
              )}
              <span className="relative z-10">
                {loading ? "Aguarde..." : `Assinar ${plan.name}`}
              </span>
            </button>
          </div>
        ))}
      </div>

      <div className="mt-6 text-center">
        <button
          type="button"
          onClick={onSkip}
          className="text-[12px] text-[var(--text-dim)] underline transition-colors hover:text-[var(--text-muted)]"
        >
          Pular e ir pro dashboard
        </button>
      </div>
    </motion.div>
  );
}
