# Spike — Captura sistemática via mitmproxy

> **Status:** ✅ **CONCLUÍDO em 2026-05-12**. Captura de 46MB salva em
> `docs/sprints/captures/2026-05-12-betano-flow.mitm`.
>
> **Resultado:** premissa central do plano (Sportradar gismo como fonte) foi
> **invalidada** pela captura. Achados consolidados na §16 abaixo.
> **Doc mestre atualizado** com a realidade descoberta.
>
> **Mestre:** [`2026-05-12-betano-discovery-master.md`](2026-05-12-betano-discovery-master.md)
>
> **Duração realizada:** ~6h (setup + execução + 5 scripts de análise)
>
> **Objetivo:** parar de caçar requests no DevTools um por um. Capturar **um
> fluxo completo** de sessão Betano + tráfego Sportradar via mitmproxy em
> ~10min, depois extrair tudo de uma vez com filtros e scripts.

---

## 0. TL;DR para o Claude CLI

Este documento é **executável por agente**. Os passos numerados produzem
artefatos concretos. Não improvisar fora dos passos sem motivo registrado.

**Saídas esperadas ao final:**

```
docs/sprints/captures/
├── 2026-05-12-betano-flow.mitm                  # raw flow (binary)
├── 2026-05-12-betano-flow-analysis.md           # achados consolidados
├── 2026-05-12-betano-flow-token-sources.txt     # onde apareceu T=exp=
├── 2026-05-12-betano-flow-websockets.txt        # se houve WS, quais
└── 2026-05-12-betano-flow-endpoints-summary.csv # request/response inventory
```

Critério mínimo de "spike concluído com sucesso":

- Endpoint de origem do token Sportradar identificado **ou** documentado como
  embedded no HTML (com referência)
- Hipótese SignalR para mercados de odds **confirmada** (sim/não, com
  evidência: presença/ausência de conexão WS no flow)
- TTL real do token Sportradar medido (em horas, observado entre 2+ tokens)
- Response de `markets-offers/{eventId}` não-vazia capturada **ou** documentado
  que sempre vem `{}` em sessão isolada

---

## 1. Pré-requisitos

- [ ] Python 3.11+ disponível
- [ ] Chrome ou Chromium instalado
- [ ] Acesso à internet residencial BR (ou hotspot móvel se DataDome estiver
      banindo o IP residencial)
- [ ] Conta laboratório na Betano (com login funcional)
- [ ] Permissões para criar `/tmp/chrome-mitm/` e `~/.mitmproxy/`

---

## 2. Setup do ambiente

### 2.1 Criar venv isolada

```bash
python3 -m venv ~/.venvs/mitm
source ~/.venvs/mitm/bin/activate
pip install --upgrade pip
pip install mitmproxy
```

Verificar instalação:

```bash
mitmdump --version
# esperado: Mitmproxy: 11.x.x
```

### 2.2 Gerar CA cert (uma vez)

```bash
mitmweb --listen-port 8080 &
sleep 3
kill %1
```

Confere que cert foi gerado:

```bash
ls -la ~/.mitmproxy/
# esperado: mitmproxy-ca-cert.pem, mitmproxy-ca.pem, mitmproxy-ca-cert.cer, etc.
```

### 2.3 Pasta de saída

```bash
mkdir -p docs/sprints/captures
```

---

## 3. Captura — execução

### 3.1 Roda `mitmdump` em modo gravação

Em **terminal 1**, deixa rodando o tempo todo:

```bash
source ~/.venvs/mitm/bin/activate
cd /home/daniel/cornerpressureelite

OUT="docs/sprints/captures/2026-05-12-betano-flow.mitm"

mitmdump \
  --listen-port 8080 \
  --set save_stream_file="$OUT" \
  --set save_stream_filter="~d betano.bet.br | ~d sportradar.com | ~d gmlinteractive.com | ~d kaizengaming.com | ~d cloudfront.net" \
  --quiet
```

Filtros:

- `~d <dominio>` = match por domínio (request URL)
- `|` = OR
- Inclui `cloudfront.net` porque a CDN da Sportradar usa CloudFront

Pode aparecer ruído em outras CDNs (StaticG.com etc.) — está OK, ignorar.

### 3.2 Abre Chrome com proxy em terminal 2

**Não usar Chrome principal.** Janela isolada via `--user-data-dir`:

```bash
# Linux
google-chrome \
  --proxy-server=http://127.0.0.1:8080 \
  --user-data-dir=/tmp/chrome-mitm \
  --ignore-certificate-errors \
  --no-first-run \
  --no-default-browser-check \
  https://www.betano.bet.br

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --proxy-server=http://127.0.0.1:8080 \
  --user-data-dir=/tmp/chrome-mitm \
  --ignore-certificate-errors

# Windows (cmd)
start chrome.exe ^
  --proxy-server=http://127.0.0.1:8080 ^
  --user-data-dir=%TEMP%\chrome-mitm ^
  --ignore-certificate-errors
```

A flag `--ignore-certificate-errors` aceita o cert do mitmproxy só nessa
janela isolada — **não toca** o trust system.

**Atenção:** se a Betano detectar `--ignore-certificate-errors` via JS, pode
ser flag adicional. Alternativa "limpa": instalar o cert do mitmproxy no trust
system do user (não system-wide):

```bash
# Linux (NSS DB do Chrome — limpo, não afeta nada além do user)
certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n mitmproxy \
  -i ~/.mitmproxy/mitmproxy-ca-cert.pem
```

Depois pode rodar Chrome sem `--ignore-certificate-errors`.

### 3.3 Roteiro de navegação (10-15 min)

Faz **na sequência, sem pressa, com 5-30s de espera em cada passo** (sentir
como humano). Cada passo está numerado para o relatório de análise registrar
qual passo gerou qual capture.

```
1.  Aterrissa em https://www.betano.bet.br — espera 15s pra render
2.  Aceita cookies (banner OneTrust) — espera 5s
3.  Clica em "Entrar" — abre tela de login
4.  Loga com conta laboratório — espera 10s pra autenticar
5.  Volta para home — espera 15s
6.  Clica em "Promoções" no menu principal — espera 15s
       (esse passo é especialmente relevante para disparar availabletokens)
7.  Volta para home
8.  Clica em "Ao Vivo" no menu — espera 10s (lista /live)
9.  Escolhe um jogo de futebol ao vivo (qualquer Brasileirão se houver, ou
    qualquer liga top como Premier League, La Liga, Champions)
10. Dentro do evento, clica nas tabs nesta ordem, esperando 20s em cada:
       - Principais
       - Escanteios
       - Cartões
       - Estatísticas
       - Todos
       - Intervalo (se houver)
11. Volta para /live (lista)
12. Repete passos 9-10 com OUTRO jogo de futebol (ideal: liga top diferente)
13. Volta para home
14. Faz logout — espera 5s
15. Em janela anônima do MESMO Chrome (Ctrl+Shift+N), navega para
    https://www.betano.bet.br/ (sessão sem login) e repete:
       - Home
       - /live
       - Entra em um jogo ao vivo
       - Clica nas 3 tabs (Principais, Escanteios, Cartões)
       - Sai do jogo
       (Isso captura o flow SEM login — comparação com flow LOGADO)
16. Fecha Chrome (janelas todas)
```

### 3.4 Para a captura

No terminal 1, `Ctrl+C` no `mitmdump`. Verifica o arquivo:

```bash
ls -lh docs/sprints/captures/2026-05-12-betano-flow.mitm
# esperado: alguns MB (entre 5 e 50 MB típico)
```

---

## 4. Análise do flow capturado

Cria scripts auxiliares em `scripts/` (uso único, não precisam virar produção):

### 4.1 Script `find_token.py` — onde apareceu o token Sportradar

```python
# scripts/mitm_find_token.py
"""Encontra todos os responses que contêm 'T=exp=' (token Sportradar)."""
from mitmproxy import io
import sys

PATTERN = "T=exp="
flow_path = sys.argv[1] if len(sys.argv) > 1 else \
    "docs/sprints/captures/2026-05-12-betano-flow.mitm"

with open(flow_path, "rb") as f:
    reader = io.FlowReader(f)
    for flow in reader.stream():
        if not hasattr(flow, "response") or not flow.response:
            continue
        try:
            text = flow.response.get_text(strict=False) or ""
        except Exception:
            continue
        if PATTERN not in text:
            continue
        idx = text.find(PATTERN)
        ctx_before = text[max(0, idx - 80):idx]
        ctx_after = text[idx:idx + 200]
        print("=" * 80)
        print(f"URL:    {flow.request.pretty_url}")
        print(f"Method: {flow.request.method}")
        print(f"Status: {flow.response.status_code}")
        print(f"CT:     {flow.response.headers.get('Content-Type', '?')}")
        print(f"Size:   {len(text)} chars")
        print(f"Snippet:")
        print(f"  ...{ctx_before}[MATCH]{ctx_after}...")
        print()
```

Rodar:

```bash
python scripts/mitm_find_token.py \
  > docs/sprints/captures/2026-05-12-betano-flow-token-sources.txt
```

**Critério:** se o arquivo tem ≥1 entrada e a URL **não** é
`widgets.fn.sportradar.com` (esse seria o consumidor, não a fonte), a fonte
do token está identificada. Anotar na seção 5 deste doc.

### 4.2 Script `list_endpoints.py` — inventário de requests

```python
# scripts/mitm_list_endpoints.py
"""Lista cada request único (deduplicado por URL+método) com agregados."""
from mitmproxy import io
from collections import defaultdict
import csv
import sys

flow_path = sys.argv[1] if len(sys.argv) > 1 else \
    "docs/sprints/captures/2026-05-12-betano-flow.mitm"
out_path = sys.argv[2] if len(sys.argv) > 2 else \
    "docs/sprints/captures/2026-05-12-betano-flow-endpoints-summary.csv"

agg = defaultdict(lambda: {"count": 0, "statuses": defaultdict(int),
                           "sizes": [], "ctypes": defaultdict(int)})

with open(flow_path, "rb") as f:
    for flow in io.FlowReader(f).stream():
        if not hasattr(flow, "response") or not flow.response:
            continue
        host = flow.request.host
        path = flow.request.path.split("?")[0]
        method = flow.request.method
        key = f"{method} {host}{path}"
        agg[key]["count"] += 1
        agg[key]["statuses"][flow.response.status_code] += 1
        agg[key]["sizes"].append(len(flow.response.content or b""))
        agg[key]["ctypes"][flow.response.headers.get("Content-Type", "?")
                            .split(";")[0]] += 1

with open(out_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["endpoint", "count", "status_distribution",
                "avg_size_bytes", "max_size_bytes", "content_types"])
    for key, data in sorted(agg.items(), key=lambda x: -x[1]["count"]):
        sizes = data["sizes"]
        w.writerow([
            key,
            data["count"],
            "|".join(f"{s}:{c}" for s, c in sorted(data["statuses"].items())),
            sum(sizes) // len(sizes) if sizes else 0,
            max(sizes) if sizes else 0,
            "|".join(f"{ct}:{c}" for ct, c in
                     sorted(data["ctypes"].items(), key=lambda x: -x[1])),
        ])

print(f"Wrote {out_path}")
print(f"Top 10 by request count:")
for key, data in sorted(agg.items(), key=lambda x: -x[1]["count"])[:10]:
    print(f"  {data['count']:4d}× {key}")
```

Rodar:

```bash
python scripts/mitm_list_endpoints.py
```

Abrir o CSV em planilha (ou `column -t -s,`) para varredura visual.

### 4.3 Script `dump_websockets.py` — confirmar/refutar SignalR

```python
# scripts/mitm_dump_websockets.py
"""Lista WebSockets encontrados no flow."""
from mitmproxy import io
import sys

flow_path = sys.argv[1] if len(sys.argv) > 1 else \
    "docs/sprints/captures/2026-05-12-betano-flow.mitm"

ws_count = 0
with open(flow_path, "rb") as f:
    for flow in io.FlowReader(f).stream():
        if flow.type != "websocket":
            continue
        ws_count += 1
        print("=" * 80)
        print(f"WS URL:    {flow.request.pretty_url}")
        print(f"Messages:  {len(flow.websocket.messages)}")
        # Imprime as primeiras 5 mensagens
        for i, msg in enumerate(flow.websocket.messages[:5]):
            direction = "←client" if msg.from_client else "server→"
            content = msg.content if isinstance(msg.content, str) \
                      else msg.content.decode("utf-8", "replace")
            print(f"  [{i:2d}] {direction}: {content[:300]}")
        if len(flow.websocket.messages) > 5:
            print(f"  ... +{len(flow.websocket.messages) - 5} mensagens")
        print()

print(f"\nTotal WebSockets: {ws_count}")
```

Rodar:

```bash
python scripts/mitm_dump_websockets.py \
  > docs/sprints/captures/2026-05-12-betano-flow-websockets.txt
```

**Critério para hipótese SignalR:**

- Se `ws_count == 0`: hipótese SignalR **refutada** → odds vêm via REST.
  Próximo passo: investigar query params de `markets-offers`.
- Se existe WS em `signalr` ou `customerhub` ou `contenthub` com mensagens
  contendo nomes de mercados (`CNOU`, `TCOU`, `marketSort`): **confirmada**.
- Se existem WS mas sem dados relevantes: ambíguo — capturar de novo com
  mais tempo dentro do evento (passo 10 do roteiro, espera 60s em cada tab
  em vez de 20s).

### 4.4 Script `dump_markets_offers.py` — captura responses não-vazias

```python
# scripts/mitm_dump_markets_offers.py
"""Imprime cada response de markets-offers que não veio vazio."""
from mitmproxy import io
import sys
import json

flow_path = sys.argv[1] if len(sys.argv) > 1 else \
    "docs/sprints/captures/2026-05-12-betano-flow.mitm"

count_total = 0
count_nonempty = 0

with open(flow_path, "rb") as f:
    for flow in io.FlowReader(f).stream():
        if not hasattr(flow, "response") or not flow.response:
            continue
        if "markets-offers" not in flow.request.path:
            continue
        count_total += 1
        try:
            body = flow.response.get_text(strict=False) or ""
        except Exception:
            continue
        if len(body) <= 5:
            continue
        count_nonempty += 1
        print("=" * 80)
        print(f"URL:     {flow.request.pretty_url}")
        print(f"Status:  {flow.response.status_code}")
        print(f"Size:    {len(body)} bytes")
        try:
            data = json.loads(body)
            print(f"Top-level keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
            print(f"First 1000 chars:")
            print(json.dumps(data, indent=2)[:1000])
        except Exception:
            print(f"First 500 chars (not JSON):")
            print(body[:500])
        print()

print(f"\nTotal markets-offers: {count_total}, non-empty: {count_nonempty}")
```

### 4.5 Script `extract_cookies.py` — sequência de Set-Cookie

```python
# scripts/mitm_extract_cookies.py
"""Lista todos os Set-Cookie da Betano em ordem cronológica."""
from mitmproxy import io
import sys

flow_path = sys.argv[1] if len(sys.argv) > 1 else \
    "docs/sprints/captures/2026-05-12-betano-flow.mitm"

with open(flow_path, "rb") as f:
    for flow in io.FlowReader(f).stream():
        if not hasattr(flow, "response") or not flow.response:
            continue
        if "betano.bet.br" not in flow.request.host:
            continue
        for cookie_header in flow.response.headers.get_all("Set-Cookie"):
            name = cookie_header.split("=", 1)[0]
            print(f"{flow.request.timestamp_start:.0f} {flow.request.pretty_url}")
            print(f"  Set-Cookie: {name}")
```

Identifica em **qual request** cada cookie crítico é setado:
- `cf_clearance` — qual request gera (provavelmente challenge JS do Cloudflare)
- `datadome` — primeira chamada que recebe
- `GAUTH` — após autenticação
- `kz_trusted_device_*` — após login confirmado

Esse mapeamento é input para o **warmup do BetanoSession** (Fase B).

---

## 5. Relatório de análise — template

Criar `docs/sprints/captures/2026-05-12-betano-flow-analysis.md`:

```markdown
# Análise — Flow Betano capturado em 2026-05-12

## Captura
- Arquivo: `2026-05-12-betano-flow.mitm`
- Duração: <minutos>
- Total de flows: <do CSV>
- Tamanho do arquivo: <MB>
- Network usada: <residencial BR / 4G / Webshare proxy>
- Logada? <sim/não, em qual janela>

## Achados-chave

### 5.1 Token Sportradar
- Status: <encontrado em response / embedded em HTML / não encontrado>
- Endpoint de origem: <URL completa>
- Método: <GET/POST>
- Sessão: <anônima / requer login>
- Formato da resposta: <JSON path para o token, ex `data.token`>
- Refresh: <observou-se refresh? frequência?>
- TTL real: <horas entre tokens consecutivos>

### 5.2 Hipótese SignalR para mercados
- Status: <confirmada / refutada / ambígua>
- Evidência: <do dump_websockets.py>
- URL(s) WS: <wss://...>
- Mensagens de exemplo: <3-5 mensagens trocadas>

### 5.3 markets-offers — quando vem vazio vs cheio
- Tab que dispara response não-vazia: <Principais? Todos? Escanteios?>
- Query params relevantes: <listar>
- Exemplo de payload (truncado): <colar JSON>

### 5.4 Mapeamento de mercados (escanteios e cartões)
Confirmar/refutar adivinhações da seção 5 do master:
- `CNOU` é: <nome real do mercado vindo do response>
- `TCOU` é: <idem>
- ... (preencher para cada code que apareceu)

### 5.5 Sequência de cookies necessários
Em ordem cronológica do warmup:
1. `cf_clearance` setado por <request>
2. `datadome` setado por <request>
3. `_cfuvid` ...
4. ...

### 5.6 Headers obrigatórios confirmados
- `X-Operator: 8`
- `X-Language: 5`
- `x-kbversion: <versão capturada>` (extrair de kb-config)
- Outros: <listar>

### 5.7 Endpoints com resposta interessante (não documentada)
Olhar o CSV `endpoints-summary` e destacar endpoints com count alto que
ainda não estão no master:
- `<endpoint>`: <count> chamadas, <descrição do conteúdo>

## Decisões / próximas ações

- [ ] Token Sportradar — implementar captura via <endpoint> no `SportradarSession`
  (input para Fase A)
- [ ] Mercados — usar <REST | SignalR | ambos> (input para Fase B)
- [ ] Atualizar §3.3 do master com endpoint do token
- [ ] Atualizar §6 do master refletindo confirmação/refutação SignalR
- [ ] Outros: <listar>
```

---

## 6. Casos de problema durante captura

### 6.1 DataDome bloqueia o IP no meio da captura

Sintoma: requests retornam 403 com "O acesso está temporariamente restrito".

Ações:

1. Para o `mitmdump` (Ctrl+C)
2. Espera 30min-3h **ou** muda de rede (4G hotspot, VPN BR, proxy Webshare)
3. Reabre Chrome com novo `--user-data-dir=/tmp/chrome-mitm-2` (cookies novos)
4. Recomeça o roteiro do passo 1

### 6.2 Cloudflare challenge persistente

Sintoma: página fica em loop de "Verificando seu navegador..." e nunca passa.

Ações:

1. Verifica se `cf_clearance` aparece em algum response — se não, o JS
   challenge não passou (provavelmente headless detectado, mas estamos com
   Chrome visível, então improvável)
2. Tenta abrir uma janela **sem proxy** em paralelo, navega para a Betano,
   pega o `cf_clearance` ali, copia o cookie para a janela com proxy
3. Se persistir, troca de IP

### 6.3 Chrome reclama do cert mesmo com `--ignore-certificate-errors`

Algumas builds recentes do Chrome bloqueiam essa flag. Alternativas:

1. Instala cert no NSS DB (passo 2.3 do setup)
2. Usa Chromium em vez de Chrome
3. Usa Firefox com proxy manual (`about:preferences#network` → Proxy manual
   → HTTP 127.0.0.1:8080 + HTTPS idem) e importa o cert via
   `about:preferences#privacy` → Certificados → Importar

### 6.4 mitmproxy não captura algumas chamadas (HTTP/3, QUIC)

Chrome moderno tenta QUIC primeiro. Forçar HTTP/2:

```bash
google-chrome \
  --proxy-server=http://127.0.0.1:8080 \
  --user-data-dir=/tmp/chrome-mitm \
  --ignore-certificate-errors \
  --disable-quic
```

---

## 7. Limpeza pós-spike

```bash
# Manter o arquivo .mitm — vale ouro como fixture para testes
# Remover pasta temporária do Chrome
rm -rf /tmp/chrome-mitm /tmp/chrome-mitm-2

# Desativar venv
deactivate
```

Commit dos achados:

```bash
git add docs/sprints/captures/
git commit -m "chore(spike): captura mitmproxy 2026-05-12 — flow + análise"
```

**Manter o `.mitm` no repositório**: serve como golden fixture para testes
unitários de parsers (Fase A) e regression tests. Tamanho típico (~10-30 MB)
é aceitável.

---

## 8. Acceptance

- [ ] Setup do mitmproxy concluído (venv, CA cert, Chrome configurado)
- [ ] Captura executada seguindo o roteiro completo (passos 1-16)
- [ ] Arquivo `2026-05-12-betano-flow.mitm` salvo em
      `docs/sprints/captures/`
- [ ] Scripts `mitm_*.py` salvos em `scripts/`
- [ ] CSV `endpoints-summary.csv` gerado e revisado
- [ ] Token Sportradar — origem documentada **ou** documentado como não
      encontrado (com hipóteses alternativas)
- [ ] Hipótese SignalR resolvida (confirmada/refutada com evidência)
- [ ] Response não-vazia de `markets-offers` capturada **ou** documentado que
      todas vieram vazias (com explicação)
- [ ] Relatório `betano-flow-analysis.md` preenchido em todas as seções
- [ ] Master doc atualizado nas seções 3.3 e 6 (token + SignalR) com base nos
      achados
- [ ] Commit feito

---

## 9. Pilares cobertos

- **Observabilidade técnica:** captura sistemática do que o frontend faz —
  base para todas as decisões das fases seguintes
- **Determinismo:** golden fixture (`.mitm` no repo) permite reproduzir
  testes e parsers contra dados reais
- **Risco mitigado:** captura local com proxy isolado, sem alteração de
  estado em produção

---

## 10. Esforço estimado detalhado

| Sub-task | Horas |
|---|---|
| Setup do ambiente (venv, cert, scripts) | 0.5 |
| Captura — roteiro 1 (logado) | 0.5 |
| Captura — roteiro 2 (anônimo, comparação) | 0.5 |
| Análise pós-captura (rodar scripts, revisar CSV) | 1.0 |
| Preenchimento do relatório de análise | 1.0 |
| Atualização do master doc | 0.5 |
| Buffer para problemas (DataDome, CF challenge, retentativas) | 1.0 |
| **Total** | **5.0h** |

---

## 11. Output mínimo aceitável (caso de spike parcialmente sucedido)

Se por qualquer motivo o spike não conseguir resolver tudo, mas ao menos:

- O `.mitm` foi salvo com responses úteis
- Token Sportradar foi encontrado em **algum** response
- Pelo menos uma response não-vazia de `markets-offers` foi capturada

→ Fase A pode iniciar. Fase B pode iniciar com hipótese SignalR ainda aberta
(implementar REST primeiro, com TODO de investigar WS).

Se nem isso foi possível: revisar seção 6 (casos de problema), recapturar
com setup diferente (proxy externo, outra rede).

---

## 16. Achados consolidados (pós-execução, 2026-05-13)

> Adicionado após análise completa do `.mitm` capturado. **Mudanças na seção
> mestre são derivadas destes achados.**

### 16.1 Visão geral da captura

- **Tamanho:** 46MB
- **Flows totais:** 1.812 (HTTP) + 11 WebSockets (capturados, com mensagens)
- **Endpoints únicos:** 982
- **Domínios principais observados:**
  - `www.betano.bet.br` (REST + WS)
  - `obseu.tostarsbuilding.com` (DataDome telemetria)
  - `da.betano.bet.br` (Google Analytics)
  - `visuals.kaizengaming.com` (imagens otimizadas — Kaizen é o fornecedor)
  - `tracker.ads.sportradar.com` (ads tracking, **não** stats)

### 16.2 Premissa invalidada

❌ **Sportradar gismo NÃO está em uso na Betano BR.**

Evidências:
- `/api/sportsbook/tokens/availabletokens` (chamado 4×) retorna `{"data":[]}` (11B vazio)
- **Zero** chamadas para `widgets.fn.sportradar.com/.../gismo/...`
- As 8 chamadas a `*.sportradar.com` são todas ads/tracking, não stats
- Provider real no `/api/statsstream/{id}/config/`: `"provider_type": "Opta"`

### 16.3 Fonte real descoberta: Opta via REST proprietário

Endpoints Betano que servem stats Opta diretamente:

| Endpoint | Tamanho | Provider |
|---|---|---|
| `/api/statsstream/{id}/info/aggregated/` | 5.2KB | Opta |
| `/api/statsstream/{id}/config/` | 331B | Opta |
| `/api/statsstream/{id}/stats/detailed/` | 3.9KB | Opta |
| `/api/statsstream/{id}/stats/players/` | ~890B | Opta |
| `/api/statsstream/{id}/momentum/` | 5KB | Opta |
| `/api/statsstream/{id}/lineups/` | 10.5KB | Opta |
| `/api/statsstream/{id}/h2h/` | 16KB | Opta |

### 16.4 Endpoint dourado descoberto

`/danae-webapi/api/live/events/{id}/latest` — **281KB** com top-level keys:
`event` + `markets` (279 entries) + `selections` (1153 entries). Inclui
`event.betradarMatchId` inline (mapping Sportradar grátis). Uma única
chamada dá snapshot completo do jogo.

### 16.5 WebSockets confirmados — 3 hubs

| Hub | Função | Protocolo |
|---|---|---|
| `/contenthub?platformType=1` | Push de odds + score | SignalR Core (JSON+`\x1e`) |
| `/sbpitches/statsstream/matchhub` | Push de eventos Opta (X/Y, ataques) | SignalR Core |
| `/customerhub_2` | User state | SignalR Core |
| `/signalr/connect` | Widget de quadra (Classic) | SignalR Classic (ignorar) |

Mensagens reais decifradas. `matchhub` é JSON puro, parsing trivial.
`contenthub.NewLiveOverviewDiffs` é payload proprietário binário+JSON
intercalado — decisão: **não parsear**, usar apenas como gatilho de re-fetch
REST.

### 16.6 Cookies do warmup — sequência cronológica completa

Confirmados 12 cookies, ordem:

```
 1. _cfuvid                       (Cloudflare)
 2. sticky_sb                     (LB sticky)
 3. cf_clearance                  (Cloudflare challenge)
 4. datadome                      (DataDome)
 5. FPGSID                        (Google Analytics)
 6. _fbp                          (Facebook Pixel)
 7. kz_trusted_device_<accountId> (login completou — OPCIONAL)
 8. pocaauth                      (auth backend — OPCIONAL)
 9. PrefferedLoginType            (OPCIONAL)
10. GAUTH                         (OPCIONAL)
11. cntps_id                      (SignalR negotiate)
12. __cflb                        (SignalR negotiate)
```

**Decisão:** operar 100% anônimo em produção. Cookies 1-5 + 11-12 são
suficientes para leitura.

### 16.7 Catálogo de markets de odds — confirmado para escanteios e cartões

Para o jogo Cruzeiro × Goiás na captura, identificados:

**Escanteios:**
- `CNOU` (typeId 34) — "Escanteios Mais/Menos" — linhas 8.5, 9.5, 10.5, 11.5, 12.5
- `NCNT` (typeId 32) — "Próxima equipe a cobrar escanteio"

**Cartões:**
- `TCOU` (typeId 65) — "Total de Cartões Mais/Menos" — linha 5.5 capturada
- `RCOU` (typeId 49) — "Total de Vermelhos"
- `HRED` (typeId 51), `ARED` (typeId 52), `1RED` (typeId 53), `PTRC` (typeId 62)

Formato de selection: `{"price": 1.85, "name": "Mais", "fullName": "Mais de 9.5"}`.
Split Over/Under via `name` ("Mais" vs "Menos").

### 16.8 Pressure score da Opta — bônus descoberto

`/api/statsstream/{id}/momentum/` retorna array minuto-a-minuto:
```json
[{"minute": 0, "period": "periodFirstHalf", "pressure": -3, ...}, ...]
```

Valor de -100 a +100 (positivo = casa, negativo = visitante). É o output do
**modelo proprietário da Opta**. Pode ser usado como sanity check do
`pressure_score` do CPES + feature para o `quality_model.py` na Fase 4 do
robô auto.

### 16.9 Eventos via `/sbpitches/statsstream/matchhub`

Cada mensagem WS traz um `MatchEvent` em JSON puro:

```json
{
  "event_data": {
    "ball_position": {"x":67.2,"y":12.4},
    "ball_position_end": {"x":65.7,"y":39.1},
    "team_id": "...",
    "player_id": "...",
    "is_possession": false,
    "is_attack": true,
    "is_dangerous_attack": false
  },
  "event_match_id": "55n9jqpc9lsi0nxt4zpw29ez8",
  "sportsbook_match_id": "84586925",
  "event_type": 0,
  "event_period_id": 2,
  "event_match_minute": 24,
  "event_match_second": 29,
  "event_provider_type": "Opta"
}
```

Granularidade de scouting profissional. Esses eventos são a fonte ideal de
pressão em tempo real, com latência <2s. Persistir todos em
`incidents_history` (Fase D) habilita análises pré-incidente (X/Y dos
ataques que precederam o escanteio).

### 16.10 Mudanças não-óbvias confirmadas

1. **`api_client.py:574` (`get_live_odds_cards`) é hardcoded para
   `bookmaker="1"`**, apesar do nome "multi". Ganho potencial em **cartões**
   pelo BetanoOddsProvider é maior que em escanteios.

2. **`betradarMatchId` vem inline no payload** (`event.betradarMatchId`),
   eliminando necessidade de chamar `/api/liveevent/statsplayer` separado.

3. **Cadências oficiais documentadas no `kb-config`:**
   - liveOverview: 5000ms
   - liveEvent: 6000ms
   - pandora: 300000ms (5min)

   Nossas cadências propostas (15s stats, 30s momentum) são **mais conservadoras**
   que as do app oficial. Margem de segurança contra detecção.

### 16.11 Próximos passos derivados

| Ação | Doc afetado |
|---|---|
| Reescrever Fase A (Sportradar → Betano StatsStream) | ✅ `betano-fase-A-statsstream-provider.md` (criado) |
| Reescrever Fase B (Markets REST + WS SignalR) | ✅ `betano-fase-B-markets-ws-provider.md` (criado) |
| Atualizar Fase C (provider único Betano + AF fallback) | ✅ `betano-fase-C-pipeline-refactor.md` (criado) |
| Atualizar Fase D (campos Opta no schema; incidents_history) | ✅ `betano-fase-D-persistencia-historica.md` (criado) |
| Atualizar master | ✅ `betano-discovery-master.md` (criado) |

### 16.12 Scripts de análise produzidos

Salvos em `scripts/analyze_mitm/`:
- `analyze.py` — visão geral (top endpoints, contagens)
- `analyze_deep.py` — payloads críticos (statsstream, danae-webapi)
- `analyze_critical.py` — markets + selections + WebSocket upgrades
- `analyze_ws.py` — extração de mensagens WS por hub
- `analyze_final.py` — markets/selections detalhados + decodificação binária

Reutilizáveis para qualquer `.mitm` futuro com pequenas adaptações.
