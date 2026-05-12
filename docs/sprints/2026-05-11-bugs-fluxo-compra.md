# Bugs pendentes — Fluxo de compra (Asaas → Dashboard)

> Criado em 2026-05-11 após validação end-to-end no sandbox Asaas (pagamento user 3 → status active confirmado).
> Estes itens NÃO bloqueiam a operação básica, mas devem ser resolvidos antes do go-live em produção.
>
> **Status (2026-05-11):** #1, #4, #5, #6 resolvidos —
> ver [`changelog/2026-05-11-fluxo-compra-pre-golive.md`](../changelog/2026-05-11-fluxo-compra-pre-golive.md).
> #2, #3, #7 seguem pendentes.
>
> **Nota de domínio (2026-05-11):** referências a `odontoschultz.online` neste doc refletem o estado anterior à migração para `iqpressure.online` no mesmo dia. Variáveis correntes: `EMAIL_FROM=PressureIQ <no-reply@iqpressure.online>`, `APP_URL=https://membros.iqpressure.online`, API em `api.iqpressure.online`.

---

## Contexto

O fluxo principal está funcionando:

1. ✅ Registro com verificação por e-mail (Resend + domínio verificado)
2. ✅ Criação de checkout no Asaas com `callback.successUrl`
3. ✅ Webhook `/api/webhook/asaas` validado por `asaas-access-token`
4. ✅ Subscription idempotente (`ON CONFLICT (user_id)`)
5. ✅ Gate de assinatura no dashboard (`(authenticated)/layout.tsx` server component)
6. ✅ E-mails transacionais (welcome / payment / renewal / cancellation)
7. ✅ Polling em `/checkout/success` com auto-redirect para `/dashboard`

Os bugs abaixo foram detectados durante o teste end-to-end e ficam em backlog.

---

## 🟡 Bug #1 — E-mails de "renovação" duplicados no primeiro pagamento

**Onde:** `corner-pressure-elite/api_server.py:991-1027` (handler do webhook PAYMENT_CONFIRMED/RECEIVED).

**O que acontece:**
Asaas envia **dois webhooks consecutivos** para pagamentos via cartão:
- `PAYMENT_CONFIRMED` (transação aprovada)
- `PAYMENT_RECEIVED` (dinheiro creditado, segundos depois)

O código atual detecta "renewal" se `prev_sub.status == "active"`. No 1º webhook a sub está `pending` → publica `EVENT_PAYMENT_CONFIRMED` ("Pagamento confirmado"). Em seguida o upsert vira `active`. No 2º webhook a sub já está `active` → publica `EVENT_SUBSCRIPTION_RENEWED` ("Assinatura renovada").

**Sintoma observado (user 3):** 1× e-mail `payment` + 2× e-mail `renewal` no mesmo minuto. Sub correta no DB, só os e-mails ficaram poluídos.

**Fix sugerido:**
Detectar renovação por **id do pagamento Asaas**, não pelo status local. Manter uma tabela `processed_payments` (asaas_payment_id PK) ou verificar se o `asaas_id` da sub mudou (renovação real = novo ciclo = novo `subscription.id` no Asaas).

```python
# pseudo:
already_processed = await db.payment_already_processed(payment.get("id"))
if already_processed:
    return {"status": "ignored", "reason": "duplicate"}
await db.mark_payment_processed(payment.get("id"))

is_renewal = prev_sub and prev_sub.asaas_id == sub_asaas_id and prev_sub.status == "active"
```

**Esforço:** ~30 min (precisa criar tabela `processed_payments` + migração).

---

## 🟡 Bug #2 — `WHATSAPP_GROUP_ID` aponta pra grupo inexistente

**Onde:** `corner-pressure-elite/api_server.py:1048` (`client.add_participant(WHATSAPP_GROUP_ID, ...)`).

**Sintoma:**
```
WAHA 404 - Cannot POST /api/groups/120363424218619609@g.us/participants
```

O ID `120363424218619609@g.us` está em `.env` (`WHATSAPP_GROUP_ID`) mas a sessão WAHA atual não tem esse grupo. Provável que o grupo foi recriado ou houve typo. Ativação do user **não é bloqueada**, mas o user fica fora do grupo.

**Fix sugerido:**
1. Listar grupos atuais da sessão: `GET /api/sessions/default/groups` no WAHA.
2. Pegar o ID correto e atualizar `.env`.
3. Considerar logar com `logger.warning` ao invés de tratar como erro, e seguir adiante (já segue, só polui o log).

**Esforço:** 5 min (sem código novo, só descobrir o ID certo).

---

## 🟡 Bug #3 — Boas-vindas WhatsApp falha para números fora do WhatsApp

**Onde:** `corner-pressure-elite/api_server.py:1066` (`client.send_text(participant_id, welcome_msg)`).

**Sintoma:**
```
WAHA 500 - No LID for user (chatId: 5541995089104@c.us)
```

O número de cadastro do user 3 não está no WhatsApp. WAHA tenta enviar e dá 500. O erro é **repetido a cada webhook** (3× para o user 3 porque CONFIRMED + RECEIVED + outro).

**Fix sugerido:**
Antes de `send_text`, validar com `client.check_number_exists()` (se WAHA expõe esse endpoint) ou tratar o 500 como WARN e seguir sem retentar.

**Esforço:** 10 min.

---

## 🟡 Bug #4 — Checkout não é idempotente (cobrança duplicada se user clicar 2x)

**Onde:** `corner-pressure-elite/api_server.py:894-946` (`create_checkout`).

**O que acontece:**
Cada `POST /api/subscriptions/checkout` cria uma nova subscription no Asaas. Se o user clicar "Assinar" 2 vezes seguidas, vira 2 subscriptions no Asaas (a `create_customer` é idempotente via lookup por email, mas a subscription não).

**Sintoma observado:** user 3 tem 3 subscriptions no painel sandbox Asaas (cliquei 3x), mas só 1 ficou ativa no DB (graças ao fix #2 que apliquei: `ON CONFLICT (user_id)`).

**Fix sugerido:**
Antes de chamar `asaas.create_subscription`, verificar se já existe sub local `status in ('pending','active')` para o user. Se `active`: retornar erro 409 "Já tem assinatura ativa". Se `pending`: tentar reutilizar o `invoiceUrl` da sub anterior (cancelar a antiga primeiro se quiser garantir limpeza).

**Esforço:** 20 min.

---

## 🟡 Bug #5 — `PAYMENT_REFUNDED` não tratado

**Onde:** `corner-pressure-elite/api_server.py:990` (lista de eventos tratados).

**O que acontece:**
Se o cliente pedir estorno via Asaas, o sistema **não revoga o acesso**. O status no DB continua `active` e o user continua usando o dashboard com o dinheiro de volta no bolso.

**Fix sugerido:**
Adicionar branch:
```python
elif event in ["PAYMENT_REFUNDED", "PAYMENT_REFUND_IN_PROGRESS"]:
    current_sub = await db.get_subscription_by_user_id(user_id)
    if current_sub:
        current_sub.status = "refunded"
        await db.upsert_subscription(current_sub)
```

E ajustar `require_paid_subscription` para rejeitar `status="refunded"` (já rejeita qualquer coisa != "active", então não precisa mudar nada).

**Esforço:** 5 min.

---

## 🟡 Bug #6 — `verify-email` já loga o usuário (estado "logado, sem pagar")

**Onde:** `corner-pressure-elite/api_server.py:728-743`.

**O que acontece:**
Após `/api/auth/verify-email`, o backend devolve JWT válido (30 dias) e o frontend salva no cookie + localStorage. O user tem `is_verified=TRUE` mas `subscription.valid=False`. Quando tenta acessar `/dashboard`, o gate redireciona pra `/login?step=plans` — loop circular.

**Sintoma observado:** "tentei entrar com o email e senha e ele volta pra pagina de assinatura" (relatado pelo user). É o comportamento correto do gate, mas a UX é estranha — o user pensou que perdeu o login.

**Fix sugerido — opções:**
1. Após verify-email, em vez de redirecionar pra `/dashboard`, redirecionar pra `/checkout/select-plan` (página dedicada de seleção).
2. Marcar o JWT com claim `unpaid=true` e renderizar UI específica "Finalize seu pagamento" quando o gate detectar isso.
3. Mostrar mensagem mais clara no `/login?step=plans` tipo "Sua conta foi criada! Falta apenas finalizar a assinatura."

**Esforço:** 15-30 min dependendo da opção.

---

## 🟡 Bug #7 — `externalReference` parsing frágil

**Onde:** `corner-pressure-elite/api_server.py:925,982-987`.

**O que acontece:**
Formato `cmp-{user_id}-{plan}-{timestamp}`, parse via `split("-")[2]`. Se algum dia plan tiver `-` (ex: `pro-mensal`), quebra. Hoje funciona porque plan ∈ {"pro","max"}.

**Fix sugerido:** trocar separador por algo improvável (`|`) ou fazer lookup reverso pelo `asaas_id` na nossa tabela `subscriptions`.

**Esforço:** 10 min.

---

## Prioridade sugerida quando voltar

1. **#5 (refund)** — proteção financeira, 5 min. Aplicar **antes** de produção.
2. **#1 (duplicate emails)** — polui caixa do user, parece amador. ~30 min.
3. **#6 (UX pós-verify)** — primeira impressão ruim, vale resolver antes do go-live.
4. **#4 (checkout idempotente)** — evita cobrança duplicada, importante.
5. **#2 (group ID)** — operacional, 5 min.
6. **#3 (boas-vindas WhatsApp)** — só ajuste de log, 10 min.
7. **#7 (parsing frágil)** — preventivo, não urgente.

---

## Estado de referência no dia em que foi escrito

- `subscriptions` table: 2 linhas (user 2 `canceled`, user 3 `active`).
- Asaas: rodando em sandbox (`https://sandbox.asaas.com/api/v3`), webhooks ativos para Cobranças + Assinaturas com token `UPq3NGkaPiRMrvVoF0SAQR_P91o2FvMnM20GzkjaFU8`.
- `EMAIL_FROM=PressureIQ <no-reply@odontoschultz.online>`, domínio verificado no Resend.
- `APP_URL=https://membros.odontoschultz.online`.
- DNS `api.odontoschultz.online` ativo via Cloudflare Tunnel (`ssh-tunnel`).
