# Playwright + Cloudflare Bot Management — Checklist Defensivo

> Documento meta. Aprendizado consolidado do incidente 2026-05-15 (IP residencial flagueado em ~10 min de investigação D.1). Ler antes de qualquer sessão de scraping/investigação que envolva Playwright apontado pra Betano (ou qualquer site sob Cloudflare WAF).

## TL;DR

**Investigação ad-hoc em IP de produção é caminho de mão única.** Cloudflare flagga o IP, recuperação leva 12-24h, todo o sistema cai junto. Use **mitmproxy + navegador real do humano** pra explorar; use Playwright só pra **execução repetitiva já validada**, com throttling agressivo.

---

## 1. Sinais que disparam Cloudflare Bot Management

Em ordem de impacto observado (incidente 2026-05-15):

### 1.1 Burst de requests (alto impacto)

Cloudflare mantém baseline por IP. IP residencial que normalmente faz <10 req/h subindo pra 30 req/10min é estatisticamente bot. **A faixa segura observada é ≤2 req/min com jitter.**

### 1.2 URLs 404 / probing (alto impacto)

Bater múltiplas URLs inexistentes em sequência é **assinatura clássica de scraper recon**. No incidente, `investigate_betano_v3.py` testou 10 URLs candidatas e 7 não existiam (`/inplay/`, `/aovivo/`, `/sport/futebol/jogos-de-hoje/`, etc). **Cada 404 conta como sinal forte.**

### 1.3 Sem interação humana (médio-alto impacto)

Playwright `page.goto()` direto, sem mouse moves / scrolls / focus events / clicks reais entre navegações, deixa rastro óbvio. Bot Management procura pela ausência desses eventos.

### 1.4 Padrão de profile inconsistente (médio impacto)

Perfil de Chrome que historicamente só acessou `/odds/<id>/` (mercados de jogos específicos) e de repente começa a navegar `/`, `/live/`, `/sport/futebol/` é mudança de padrão estatístico — flag de "comportamento atípico".

### 1.5 Múltiplas pages/contexts paralelos (médio impacto)

Humano abre 1-3 tabs por vez. Script abrindo 10 pages em loop em <30s é claro bot. Contexto Playwright cria pages instantâneas sem latência humana.

### 1.6 Fingerprint do Playwright (médio impacto)

Chrome controlado via Playwright via CDP exibe:
- `window.__playwright__binding__` (vimos isso no nosso bridge)
- `navigator.webdriver === true` (em modo automation)
- Plugin list anormal
- Comportamento de canvas/WebGL ligeiramente diferente

Cloudflare Bot Management roda fingerprinting em runtime via JS injetado.

### 1.7 Mesmo IP pra múltiplos endpoints (estrutural)

Pool com odin localhost + danewell LAN — ambos saem com mesmo IP residencial NAT. **Quando o IP flagga, todo o pool cai junto.** Não há HA real sem diversificação de IP.

### 1.8 Headers/TLS minor mismatch (baixo-médio impacto)

User-Agent declarando Firefox mas TLS fingerprint de Chromium, Accept-Language inconsistente com geolocation IP, etc. Conectar via CDP a Chrome stable real **mitiga isso** (TLS = Chrome real).

### 1.9 Tempo entre requests muito regular (baixo impacto isolado, alto combinado)

`await asyncio.sleep(5)` consistente em loop é robotic. Humano tem variância natural.

---

## 2. Defesas técnicas (com código)

### 2.1 Throttling com jitter (sempre)

```python
import asyncio, random

async def navigate_with_jitter(page, url):
    await page.goto(url, wait_until="domcontentloaded")
    # Tempo na page: 8-15s aleatório (humano lê)
    await asyncio.sleep(random.uniform(8, 15))

# Entre URLs diferentes: 30-90s
async def session_loop(urls):
    for url in urls:
        await navigate_with_jitter(page, url)
        await asyncio.sleep(random.uniform(30, 90))
```

**Regra prática:** ≤2 navegações/min com jitter ≥30s entre elas.

### 2.2 Whitelist de URLs (nunca probing)

```python
# RUIM — chuta caminhos
URLS = [
    "https://www.betano.bet.br/live/",
    "https://www.betano.bet.br/inplay/",       # 404
    "https://www.betano.bet.br/aovivo/",       # 404
    "https://www.betano.bet.br/sport/futebol/jogos-de-hoje/",  # 404
]

# BOM — só URLs validadas previamente via mitmproxy/navegador humano
URLS = [
    "https://www.betano.bet.br/sport/futebol/",
    "https://www.betano.bet.br/live/",
]
```

Validar caminho com `HEAD` antes de bater `GET` em escala? **Não funciona** — Cloudflare bloqueia HEAD com mesmo critério. Validar **manualmente** uma vez via humano e armazenar.

### 2.3 Eventos humanos sintéticos

```python
# Antes de extrair dados, simula leitura humana
await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
await asyncio.sleep(random.uniform(0.5, 1.5))
await page.mouse.wheel(0, random.randint(200, 600))
await asyncio.sleep(random.uniform(1, 3))
await page.mouse.wheel(0, random.randint(200, 600))
await asyncio.sleep(random.uniform(2, 4))
```

Não é mágica — mas é melhor que nada. Cloudflare consegue detectar padrões mesmo de mouse synth, mas o sinal é menor que ZERO eventos.

### 2.4 Init script pra esconder Playwright

```python
await context.add_init_script("""
    // Hide webdriver
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

    // Fake plugin list
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin' },
            { name: 'Chrome PDF Viewer' },
            { name: 'Native Client' }
        ]
    });

    // Fake languages coerentes com pt-BR
    Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});

    // Permissions consistente
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) => (
        params.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(params)
    );
""")
```

**Atenção:** isso ajuda contra fingerprinting básico mas **não esconde `__playwright__binding__`** (que vimos no nosso Chrome). Pra esconder isso precisa Playwright ≥1.40 com `--disable-blink-features=AutomationControlled` no Chrome args, OU mudar pra biblioteca como `undetected-chromedriver` (Selenium-based) ou `playwright-stealth`.

### 2.5 Reusar pages (não criar 10)

```python
# RUIM — cria N pages
for url in urls:
    page = await ctx.new_page()
    await page.goto(url)
    await page.close()

# BOM — reusa mesma page
page = await ctx.new_page()
for url in urls:
    await page.goto(url)
    await asyncio.sleep(random.uniform(30, 90))
await page.close()
```

### 2.6 Detectar block em runtime e PARAR

```python
async def safe_navigate(page, url):
    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    title = await page.title()
    if "Splash Screen" in title or "restricted" in (await page.evaluate("document.body.innerText")).lower():
        # FLAGGED — para tudo, alerta
        raise BotFlagDetected(f"Cloudflare flag em {url}, parar imediatamente")
    return page
```

**Crítico:** quando ver Splash Screen, **NÃO continuar tentando outras URLs** — cada retry reforça o flag.

### 2.7 Warmup natural pra perfis novos

Antes de qualquer scraping, perfil novo deve "viver" como humano:
1. Abrir home, scroll, esperar 30s
2. Clicar (não `goto`) num link de esporte
3. Esperar 30s
4. Clicar num jogo
5. Voltar pra home
6. Total: ~5min de "uso natural"

Só DEPOIS desse warmup começar requests programáticas.

### 2.8 Cookie persistence + reuso

Em vez de Chrome iniciar do zero a cada start, **profile persistente em disco** (`--user-data-dir`). Cookies sobrevivem a restarts. Já fazemos isso em `~/chrome-betano-test-profile`.

**Mas atenção:** profile queimado fica queimado. Se Cloudflare flag o profile (não só o IP), recriar do zero é única saída. Backup periódico do profile aquecido (cookies válidos, fingerprint estável) é boa prática:

```bash
# Backup mensal
tar czf ~/chrome-betano-profile-backup-$(date +%Y%m).tar.gz ~/chrome-betano-test-profile/
```

---

## 3. Decisão arquitetural pré-investigação

Antes de iniciar qualquer sessão de investigação/exploração, escolher a ferramenta certa:

| Cenário | Ferramenta | Por quê |
|---|---|---|
| **Mapear endpoint novo / schema desconhecido** | mitmproxy no PC humano | Captura tudo (XHR + WS), zero risco de flag, vê auth real |
| **Validar URL nova** | Navegador real do humano | Visualiza splash screen, captcha, etc |
| **Extrair dados de URL conhecida + validada** | Playwright via bridge | Repetitivo, automatizável, com throttling |
| **Polling periódico de API descoberta** | `httpx` direto, Chrome só pra cookies | Mais leve, menos exposto |
| **Smoke test ad-hoc em produção** | NÃO FAZER | Sempre via mitmproxy primeiro |

### Regra de incerteza — peça mitmproxy ao usuário

**Se o agente não tem certeza de uma URL, schema, header ou fluxo — NÃO testar via Playwright pra "ver o que retorna".** Cada teste especulativo conta como sinal de bot (especialmente URLs 404). Em vez disso, **pedir ao usuário pra rodar mitmproxy no PC dele** e capturar o tráfego natural.

Casos típicos onde aplica:
- "Acho que existe `/api/<algo>/today/` mas não tenho certeza" → pedir mitmproxy
- "Não sei qual cookie é necessário pra autenticar" → pedir mitmproxy
- "Preciso ver o response de X mas nunca capturei" → pedir mitmproxy
- "Quero validar se o endpoint mudou de schema" → pedir mitmproxy
- "Não sei a URL exata da página de Y" → pedir usuário navegar com mitmproxy

Como pedir (template de mensagem):

```
Não tenho certeza de [URL/schema/header/fluxo] e testar via Playwright
no bridge pode disparar flag (custaria 12-24h de downtime). Você pode
rodar mitmproxy no seu PC, navegar [PASSO ESPECÍFICO], salvar .mitm e
me mandar? Setup completo em [link/comando]. Demora ~5min e elimina
a incerteza sem risco.
```

Critério prático: se a investigação envolve mais de **2 URLs novas** OU qualquer URL que não foi vista em capture anterior, **pedir mitmproxy é o default**. Playwright só pra reproduzir o que mitmproxy já validou.

---

## 4. Checklist pré-sessão de scraping

Antes de rodar QUALQUER script Playwright apontando pra Betano (ou outro alvo Cloudflare):

- [ ] As URLs estão **todas validadas** (não-404)?
- [ ] Throttling configurado (≥30s entre navegações com jitter)?
- [ ] Reusando mesma page (não criando múltiplas)?
- [ ] Init script de stealth carregado?
- [ ] Detecção de Splash Screen com `raise + stop`?
- [ ] Profile aquecido (não recém-criado)?
- [ ] Plano de fallback se IP flagueado (ex: cancelar sessão, esperar 24h)?
- [ ] Tem snapshot do profile antes (se algo der errado)?
- [ ] Estou em IP que pode ser sacrificado, ou é IP de produção crítico?

Se qualquer caixa marcada NÃO, **pause e ajuste**.

---

## 5. Recovery após flag

Se o IP foi flagueado:

1. **Parar TODAS as requests automatizadas imediatamente** — toda chamada adicional reforça o flag
2. **Não tentar URLs alternativas pra "validar se está mesmo bloqueado"** — isso piora
3. **Esperar 12-24h passivamente** — TTL típico Cloudflare WAF
4. **Investigar via mitmproxy + navegador humano** se urgente
5. **Documentar em BUGS.md** o que disparou (quais scripts, quantas URLs, qual janela de tempo)

Se IP **não desbloquear em 24h**:
1. Trocar IP (modem off 1h+, ou clone MAC, ou suporte ISP)
2. Recriar profile do zero (`mv ~/chrome-betano-test-profile ~/chrome-...-queimado`)
3. Aquecer profile via humano (5-10 min de uso natural)
4. Só depois retomar scripts (com checklist seção 4)

---

## 6. Referências internas

- Incidente: [BUGS.md — IP residencial flagueado pela Cloudflare Bot Management](../BUGS.md#2026-05-15--ip-residencial-flagueado-pela-cloudflare-bot-management)
- Decisão D.1 v2: [DECISIONS.md — D.1 vai usar API HTTP nativa](../DECISIONS.md#2026-05-15-sessão-3--d1-vai-usar-api-http-nativa-não-dom-scrape)
- Schema da API descoberta: [betano-danae-api.md](betano-danae-api.md)
- Sessão de investigação: [CHANGELOG.md — sessão 3](../CHANGELOG.md#2026-05-15-sessão-3--d1-investigação-descoberta-da-danae-api--ip-flagueado)
