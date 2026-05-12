# Migração de domínio: `odontoschultz.online` → `iqpressure.online`

**Data:** 2026-05-11
**Tipo:** Mudança de infra pública (DNS, CORS, e-mail, webhook de pagamento)
**Plano de execução:** [`docs/sprints/2026-05-11-migracao-dominio-iqpressure.md`](../sprints/2026-05-11-migracao-dominio-iqpressure.md)

## Resumo

Domínio público da PressureIQ trocado para alinhar com a marca. `odontoschultz.online` era herança do consultório do dono e estava confundindo a identidade do produto.

## Mapeamento final (tunnel `ssh-tunnel`, mesmo de antes)

| Hostname | Origem | Função |
|---|---|---|
| `iqpressure.online` / `www.` | `localhost:3001` | Dashboard Next.js — site principal |
| `membros.iqpressure.online` | `localhost:3001` | Dashboard — área de membros |
| `api.iqpressure.online` | `localhost:8000` | API FastAPI |
| `wa.iqpressure.online` | `localhost:3000` | WAHA Plus (antes ficava no apex) |
| `ssh.iqpressure.online` | `ssh://localhost:22` | SSH via Cloudflare Access |

Diferença vs setup antigo: **apex agora serve o dashboard** (era WAHA antes); WAHA virou `wa.iqpressure.online`.

## Sistemas externos reconfigurados

- **Cloudflare:** zona `iqpressure.online` criada; 6 rotas DNS criadas pelo `cloudflared` (após `cloudflared tunnel login` re-autorizando o `cert.pem` pra cobrir as 2 zonas).
- **Resend:** domínio `iqpressure.online` verificado (region `sa-east-1`). 3 records DNS (`MX send`, `TXT send` SPF, `TXT resend._domainkey` DKIM) na zona iqpressure como **DNS only**.
- **Asaas:** webhook URL trocada para `https://api.iqpressure.online/api/webhook/asaas` (mesmo `asaas-access-token`). Adicionado `https://iqpressure.online` em **Minha Conta → Dados Comerciais → Site** (sem isso a criação de subscription falha com 400).
- **`.env` de produção:** `EMAIL_FROM=PressureIQ <no-reply@iqpressure.online>`, `APP_URL=https://membros.iqpressure.online`.
- **CORS (`api_server.py`):** novos origins adicionados (apex/www/membros iqpressure); legados `odontoschultz` mantidos por 72h.
- **Frontend (`dashboard/src/app/layout.tsx`):** `metadataBase` apontando para `https://iqpressure.online`.

## Commits da migração

Branch `feat/migrate-domain-iqpressure`:

1. `4825c8f` — chore: snapshot trabalho acumulado pré-migração (isolado pra commit limpo)
2. `bec5a28` — feat: migração de domínio (CORS, .env.example, metadataBase, scripts, settings.local.json)
3. (próximo commit) — docs: atualização de CLAUDE.md e referências em `docs/`

## Validação end-to-end (executada após deploy)

- ✅ DNS: todos os 5 hostnames resolvem via Cloudflare proxy
- ✅ Tunnel: cloudflared reiniciado com 4 conexões QUIC ativas
- ✅ Dashboard: `https://membros.iqpressure.online/` → 307 `/login`
- ✅ API: `https://api.iqpressure.online/api/health` → `{"status":"ok"}`
- ✅ WAHA: `https://wa.iqpressure.online/` → 401 Basic (Express)
- ✅ CORS: preflight com `Origin: https://membros.iqpressure.online` → `access-control-allow-origin` ecoado
- ✅ E-mail: signup real → welcome e-mail chegou de `no-reply@iqpressure.online` (DKIM/SPF passando)
- ✅ Checkout Asaas: customer + subscription criados; `/api/subscriptions/checkout` 200
- ✅ Webhook Asaas: `POST /api/webhook/asaas` 200 (Asaas disparou evento real)

## Pendências pós-migração

1. **Apex sem landing page pública.** `iqpressure.online/` cai em `/login` (middleware do dashboard). Se quiser página de marketing aberta no apex, vai precisar de sprint no Next.js (rota pública + dividir layouts).
2. **Cleanup do legado (§11 do sprint).** Esperar 72h verde (até ~2026-05-14) e então remover do `config.yml` os hostnames `*.odontoschultz.online`, do CORS os 3 origins antigos, e desabilitar (não deletar) os recursos `odontoschultz` em Asaas/Resend.
3. **CPF inválido travando checkout.** Pré-existente, separado da migração. Sistema deveria validar checksum CPF no front antes de mandar pro Asaas (que retorna 500 genérico).

## Referências durante a migração

- Sprint executável: [`docs/sprints/2026-05-11-migracao-dominio-iqpressure.md`](../sprints/2026-05-11-migracao-dominio-iqpressure.md)
- Backup do `cert.pem` antigo: `~/.cloudflared/cert.pem.bak.2026-05-11`
- Backup do `config.yml` antigo: `~/.cloudflared/config.yml.bak.2026-05-11`
- Backup do `.env` antigo: `corner-pressure-elite/.env.bak.2026-05-11`
