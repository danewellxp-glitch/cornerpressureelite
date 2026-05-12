# Landing page pública do apex `iqpressure.online`

> **Data:** 2026-05-12
> **Status:** plano de execução (harness)
> **Owner:** Daniel
> **Pré-requisito:** migração de domínio iqpressure.online concluída (ver `docs/changelog/2026-05-11-migracao-dominio-iqpressure.md`)
> **Esforço estimado:** 2–4 h de implementação + 1–2 h de copy/design

---

## 0. Contexto

Depois da migração de domínio, `iqpressure.online/` aponta para o **dashboard Next.js** (`localhost:3001`). Mas o **middleware do dashboard** considera tudo, exceto `/login` e `/api/auth/*`, como rota protegida e redireciona pra `/login`. Resultado prático: hoje um visitante anônimo que digita `iqpressure.online` cai numa **tela de login**, não numa landing de marketing.

Para uma marca pública (PressureIQ), isso é ruim:
- **Zero conversão fria** — não há proposta de valor, nem prova social, nem CTA antes do login
- **SEO ferrado** — Google indexa `/login` como conteúdo do domínio raiz
- **Sem rede social funcional** — share de `iqpressure.online` no WhatsApp/Twitter mostra preview do `/login`
- **`metadataBase`** do `layout.tsx` aponta para `iqpressure.online` mas a página real não casa com a expectativa de quem chega

---

## 1. Goal & escopo

### O que vamos fazer

1. **`iqpressure.online/`** (apex e `www.`) passa a servir uma **landing page pública** de marketing: hero, features, planos, prova, CTA.
2. **`/login` continua igual** (já é público).
3. **`/dashboard`, `/escanteios`, `/cartoes-amarelos`, etc. continuam protegidos** pelo middleware (sem mudança de comportamento).
4. **`membros.iqpressure.online/`** decide o roteamento por host:
   - Visitante autenticado → `/dashboard`
   - Anônimo → `/login`
   - Não exibe a landing (a landing é só do apex).

### O que NÃO vamos fazer agora

- Página de blog, /sobre, /termos — pode vir depois
- A/B test em copy
- Captura de e-mail/waitlist sem login (CTA principal continua sendo "Criar conta" → `/login`)
- Tema independente da landing (vai usar mesmo MUI + globals.css do dashboard, com ajustes pontuais)
- Mudança de design system

---

## 2. Decisão de arquitetura

### Opções consideradas

| Opção | Como funciona | Trade-off |
|---|---|---|
| **A. Mesma app Next.js, `/` virou landing pública** | `app/page.tsx` deixa de redirecionar; middleware libera `/`. Membros é tratado por host na middleware. | ✅ Sem duplicação de stack, sem deploy novo. ❌ App fica com 2 personalidades (marketing + autenticado). |
| B. Subdomínio `landing.iqpressure.online` separado | App Next.js dedicada só pra marketing | ❌ Outro container, outra rota cloudflared, mais infra. Não compensa pra 1 página. |
| C. Site estático no apex (Cloudflare Pages) | Apex aponta direto pro CF Pages; dashboard fica em `membros.` | ❌ Reverte parte da migração que acabou de ser feita. Complicação no túnel. |

**Escolha: A.** Menor blast radius, alinhado com a topologia atual do tunnel.

### Como o middleware decide

```
URL                                | Comportamento
-----------------------------------|--------------------------------------------------
iqpressure.online/                 | mostra landing (público)
iqpressure.online/login            | mostra /login (público — já é)
iqpressure.online/checkout/success | mostra success (público — já é)
iqpressure.online/dashboard        | exige auth (igual a hoje)

www.iqpressure.online/             | mostra landing (igual ao apex)

membros.iqpressure.online/         | redireciona: anônimo → /login; autenticado → /dashboard
membros.iqpressure.online/login    | mostra /login
membros.iqpressure.online/dashboard| exige auth
```

> **Por que membros redireciona em vez de mostrar a landing?** O subdomínio `membros.` foi escolhido como "área de membros". Mostrar marketing lá seria contraditório. Quem digita `membros.` quer logar.

---

## 3. Implementação passo a passo

### 3.1 Substituir `dashboard/src/app/page.tsx`

Hoje:
```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard");
}
```

Vira (esqueleto da landing):
```tsx
import LandingHero from "@/components/landing/LandingHero";
import LandingFeatures from "@/components/landing/LandingFeatures";
import LandingPricing from "@/components/landing/LandingPricing";
import LandingProof from "@/components/landing/LandingProof";
import LandingCTA from "@/components/landing/LandingCTA";
import LandingFooter from "@/components/landing/LandingFooter";

export default function Home() {
  return (
    <>
      <LandingHero />
      <LandingFeatures />
      <LandingProof />
      <LandingPricing />
      <LandingCTA />
      <LandingFooter />
    </>
  );
}
```

> O comportamento "redirecionar pro dashboard se já logado" passa pra middleware (próximo passo) usando o host.

### 3.2 Ajustar `dashboard/src/middleware.ts`

Hoje (resumido):
```ts
const PUBLIC_PATHS = ["/login", "/api/auth"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p)) || ...) return NextResponse.next();
  const token = req.cookies.get("cpes-auth")?.value;
  if (!token) return NextResponse.redirect(new URL("/login", req.url));
  // ...
}
```

Mudanças:
1. Adicionar `/` e `/checkout` a `PUBLIC_PATHS`.
2. Adicionar lógica de host: se host é `membros.*` e path é exatamente `/`, redirecionar pra `/login` ou `/dashboard` conforme cookie.

```ts
const PUBLIC_PATHS = ["/login", "/api/auth", "/checkout"];
const PUBLIC_EXACT = new Set(["/"]);  // path exato — só o root

const MEMBROS_HOSTS = new Set([
  "membros.iqpressure.online",
  "membros.odontoschultz.online", // remover quando §11 do sprint de migração for executado
]);

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const host = req.headers.get("host") ?? "";

  // membros.* na home: força login ou dashboard
  if (MEMBROS_HOSTS.has(host) && pathname === "/") {
    const token = req.cookies.get("cpes-auth")?.value;
    return NextResponse.redirect(new URL(token ? "/dashboard" : "/login", req.url));
  }

  // Públicas: landing (/), login, api/auth, checkout, assets
  if (
    PUBLIC_EXACT.has(pathname) ||
    PUBLIC_PATHS.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/cpes") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  // Resto: precisa de token (igual a hoje)
  const token = req.cookies.get("cpes-auth")?.value;
  if (!token) return NextResponse.redirect(new URL("/login", req.url));

  try {
    await jwtVerify(token, JWT_SECRET);
    return NextResponse.next();
  } catch {
    return NextResponse.redirect(new URL("/login", req.url));
  }
}
```

> **Detalhe importante:** `req.headers.get("host")` quando o app está atrás do Cloudflare Tunnel deve refletir o host original (ex: `membros.iqpressure.online`). Validar isso no smoke test (§6).

### 3.3 Criar diretório de componentes da landing

Criar:
```
dashboard/src/components/landing/
├── LandingHero.tsx        # hero + value prop + CTA primário
├── LandingFeatures.tsx    # 3-4 cards: Pressure Score, Tension Score, WhatsApp instantâneo, IA
├── LandingProof.tsx       # KPIs (ex: "X sinais/dia", "Y% green em backtest") + depoimentos
├── LandingPricing.tsx     # Pro (R$ 39,90) vs Max (R$ 89,90), tabela comparativa, CTAs
├── LandingCTA.tsx         # bloco final: "Crie sua conta grátis" → /login
└── LandingFooter.tsx      # links: login, termos, contato (whatsapp), redes
```

Cada componente é um **Server Component** simples — sem `"use client"` salvo quando precisar (botão CTA com tracking, animações). Usa MUI Box/Container/Typography pra herdar tema do dashboard. Pode usar Tailwind utilitário onde já existir (em `globals.css`).

### 3.4 Copy do hero (proposta inicial — refinar com você)

**H1:** Sinais de escanteios e cartões com IA, direto no WhatsApp
**Sub:** Análise ao vivo de Pressure Score e Tension Score em jogos de ligas selecionadas. Receba alertas antes do mercado reagir.
**CTA primário:** Começar grátis → `/login` (cadastro)
**CTA secundário:** Ver planos → `#pricing`

### 3.5 Features (4 cards)

1. **Pressure Score em tempo real** — análise híbrida de stats da partida pra prever pressão de escanteios.
2. **Tension Score (cartões)** — sinal complementar pra Over Cartões Amarelos.
3. **WhatsApp instantâneo** — mensagem direta no grupo, antes do mercado reagir.
4. **Filtros estruturais** — só sinais com `score ≥ X` e `edge ≥ Y`. Sem ruído.

### 3.6 Prova social

- "X sinais enviados nos últimos 30 dias" (puxar do `/api/stats` se exposto público; senão hard-code com data)
- 2-3 depoimentos (cite-os por primeiro nome + cidade)
- Logos de ligas cobertas (Brasileirão, La Liga, Serie A, Premier League, etc.) — usar SVGs/imagens.

### 3.7 Pricing

Manter na landing a mesma estrutura que existe hoje na tela de checkout: Pro R$ 39,90/mês e Max R$ 89,90/mês. CTA de cada plano leva pra `/login?plan=pro` ou `/login?plan=max` (login page já entende `?plan=` ou pode ser ajustada pra fluir direto pro checkout pós-cadastro).

### 3.8 Layout root (`app/layout.tsx`)

Hoje ele já injeta MUI + ThemeProvider + globals. Não precisa mudar nada. A landing herda o tema.

### 3.9 Metadata específica da landing

Em `app/page.tsx` exportar `metadata` específica (sobrescreve o default do layout):

```tsx
export const metadata = {
  title: "PressureIQ — Sinais de escanteios e cartões com IA",
  description: "Análise ao vivo de Pressure Score e Tension Score com alertas no WhatsApp. Crie sua conta grátis.",
  openGraph: {
    title: "PressureIQ — Inteligência de pressão de jogo",
    description: "Sinais de Over Escanteios e Over Cartões Amarelos em tempo real, com IA, direto no WhatsApp.",
    images: ["/brand/og-image.png"],
    type: "website",
    url: "https://iqpressure.online",
  },
};
```

Confirmar que `/brand/og-image.png` existe em `dashboard/public/brand/` — se não, criar (1200×630, fundo da marca + logo + headline).

---

## 4. Tarefas (TODO list executável)

```
□ branch: feat/landing-page-apex
□ src/app/page.tsx → landing real (esqueleto + componentes)
□ src/middleware.ts → liberar "/" e adicionar host-aware redirect
□ src/components/landing/LandingHero.tsx
□ src/components/landing/LandingFeatures.tsx
□ src/components/landing/LandingProof.tsx
□ src/components/landing/LandingPricing.tsx
□ src/components/landing/LandingCTA.tsx
□ src/components/landing/LandingFooter.tsx
□ public/brand/og-image.png (se não existir)
□ Smoke local: npm run dev → testar:
  □ http://localhost:3001/                       → landing
  □ http://localhost:3001/login                  → login
  □ http://localhost:3001/dashboard sem cookie   → redirect /login
  □ Header Host: membros.iqpressure.online + /   → redirect /login
□ Build: npm run build → sem erro
□ Deploy: docker compose up -d --build cpes-dashboard
□ Smoke produção:
  □ https://iqpressure.online/                  → landing
  □ https://www.iqpressure.online/              → landing
  □ https://iqpressure.online/dashboard         → redirect /login
  □ https://membros.iqpressure.online/          → redirect /login
  □ https://membros.iqpressure.online/login     → login OK
  □ View source: og:image, og:url, title certos
□ SEO sanity:
  □ curl -s iqpressure.online | grep -i "<title>"   → tem "PressureIQ"
  □ curl -s iqpressure.online | grep -i "og:image"  → preenchido
□ Commit + PR
□ Atualizar docs/changelog/ com 2026-05-12-landing-page-apex.md
```

---

## 5. Validação esperada (§6)

| Teste | Esperado |
|---|---|
| `curl -sI https://iqpressure.online/` | 200 OK (não 307) |
| `curl -s https://iqpressure.online/ \| head -50` | HTML contendo "PressureIQ" e CTAs |
| `curl -sI https://iqpressure.online/dashboard` | 307 → `/login` |
| `curl -sI -H "Host: membros.iqpressure.online" https://membros.iqpressure.online/` | 307 → `/login` |
| Abrir landing no celular | Hero, features, pricing visíveis sem zoom horizontal |
| Compartilhar `https://iqpressure.online` no WhatsApp | Preview com og:image, título e descrição |

---

## 6. Rollback

Caso a landing cause regressão no fluxo de membros:

1. `git revert <commit-landing>` na branch `feat/landing-page-apex` ou na main após merge
2. `docker compose up -d --build cpes-dashboard`
3. O comportamento volta a ser `iqpressure.online/ → /login` (igual ao estado atual pós-migração)

Risco baixo: a landing é **adição** (página nova + flex no middleware); a única mudança em fluxo existente é o host-aware redirect pro `membros.*`, que tem que ser testado com cuidado mas não derruba o dashboard se quebrar (no pior caso, `membros.iqpressure.online/` mostra a landing — não-ideal mas não bloqueante).

---

## 7. Pendências relacionadas (fora deste sprint)

- **Captura de e-mail / waitlist** sem login (lead magnet pra remarketing) — se o CTA principal não converter, pode valer testar isso depois
- **A/B test** em copy do hero e CTAs
- **Páginas extras**: /sobre, /termos, /politica-de-privacidade — necessárias antes do go-live legal/Asaas em produção (estritamente; sandbox tolera)
- **Blog** ou /artigos com SEO long-tail ("como usar pressure score em escanteios", etc.)
- **Tracking**: Google Analytics ou Plausible — definir antes de divulgar a landing
- **Loading skeleton** específico se a landing puxar dados do `/api/stats` em runtime; por padrão, dados estáticos.

---

## 8. Decisões pendentes (perguntar antes de codar)

1. **Copy final do hero** (H1 + sub + CTAs) — proposta na §3.4, precisa confirmação ou ajuste
2. **KPIs reais pra prova social** (§3.6) — quais números querer mostrar e se vêm de endpoint público ou hard-code
3. **Depoimentos** — usar reais (nomes/cidades) ou fictícios marcados como "Cliente Pro – SP"?
4. **CTA final** — "Começar grátis" leva pra `/login`, mas hoje o cadastro pede CPF/celular antes do checkout. Quer revisar esse fluxo agora ou deixar como está?
5. **`og-image`** — gerar arte nova específica pra PressureIQ ou reutilizar a existente em `public/brand/og-image.png`?

---

## 9. Referências

- Sprint de migração de domínio: [`2026-05-11-migracao-dominio-iqpressure.md`](2026-05-11-migracao-dominio-iqpressure.md)
- Changelog da migração: [`../changelog/2026-05-11-migracao-dominio-iqpressure.md`](../changelog/2026-05-11-migracao-dominio-iqpressure.md)
- Middleware atual: `dashboard/src/middleware.ts`
- Layout root: `dashboard/src/app/layout.tsx`
- Página atual: `dashboard/src/app/page.tsx`
