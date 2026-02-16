# 2026-02-15 Fix: WhatsApp Webhook e Comandos /status /jogos

## Problema Relatado

Usuário reportou:
- Comandos `/status` e `/jogos` no WhatsApp não funcionam
- Agenda do dia pode estar com dados incorretos
- Jogos ao vivo podem não entrar na janela de análise corretamente
- Robô do WhatsApp pode não estar enviando sinais para o grupo "Escanteios"

## Causas Identificadas

### 1. **Session Name Conflict (CRÍTICO)**
- `config.py` usava sessão `"cpes-alerts"` (padrão)
- WAHA Core (versão gratuita) suporta apenas sessão `"default"`
- Resultado: Sessão nunca era iniciada, webhook não recebia mensagens

### 2. **API Key Mismatch**
- `.env` tinha `WAHA_API_KEY=90a3f3b7963a43cd964395d2bd33ba81`
- `docker-compose.yml` tinha `WHATSAPP_API_KEY=cdb85694296a453eb291317d2ac1f660`
- WAHA usa a chave do docker-compose, não do .env

### 3. **Webhook não Registrado**
- WAHA não sabia para onde enviar mensagens recebidas
- Endpoint `/api/webhook/whatsapp` existia, mas WAHA não estava configurado para chamar

## Solução Implementada

### 1. Atualizar configuração de session name

**Arquivo: `corner-pressure-elite/config.py`**
```python
# De:
WAHA_SESSION_NAME = os.getenv("WAHA_SESSION_NAME", "cpes-alerts")

# Para:
WAHA_SESSION_NAME = os.getenv("WAHA_SESSION_NAME", "default")
```

**Arquivo: `corner-pressure-elite/.env`**
```bash
# De:
WAHA_SESSION_NAME=default
WAHA_API_KEY=90a3f3b7963a43cd964395d2bd33ba81

# Para:
WAHA_SESSION_NAME=default
WAHA_API_KEY=cdb85694296a453eb291317d2ac1f660  # Mesma chave do docker-compose
```

### 2. Registrar Webhook no WAHA

**Arquivo: `docker-compose.yml`**
```yaml
waha:
  environment:
    # ... outros valores ...
    # NOVO: Webhook configuration
    - WAHA_WEBHOOK_URL=http://cpes-api:8000/api/webhook/whatsapp
    - WAHA_WEBHOOK_API_KEY=cdb85694296a453eb291317d2ac1f660
```

Esta configuração instrui WAHA a:
- Enviar webhooks para `http://cpes-api:8000/api/webhook/whatsapp`
- Usar a API key `cdb85694296...` para autenticação

### 3. Criar Script de Diagnóstico

**Arquivo novo: `corner-pressure-elite/diagnose_whatsapp.py`**

Script que valida:
1. ✓ Conexão WAHA (sessão está WORKING)
2. ✓ Endpoint webhook respondendo
3. ✓ Formatadores de mensagens funcionando
4. ✓ Acesso aos dados do banco
5. ✓ Janela de análise configurada
6. ✓ Grupo WhatsApp configurado

## Validação

### Teste Manual via Webhook

```bash
curl -X POST "http://localhost:8000/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "payload": {
      "from": "554195089104@c.us",
      "body": "/status"
    }
  }'

# Resposta esperada:
# { "status": "ok", "command": "status" }
```

### Teste via Script de Diagnóstico

```bash
cd /home/daniel/cornerpressureelite
docker cp corner-pressure-elite/diagnose_whatsapp.py cpes-api:/app/
docker exec cpes-api python3 /app/diagnose_whatsapp.py
```

**Resultado esperado:**
```
✅ SISTEMA PRONTO! Comandos /status e /jogos devem funcionar no WhatsApp.
Resultado: 6/6 testes passaram
```

## Confirma Funcionando

Todos os testes passaram em 2026-02-15 14:37 UTC:

| Teste | Status | Detalhe |
|-------|--------|---------|
| WAHA Connection | ✓ | Status: WORKING, Conectado: True |
| Webhook Endpoint | ✓ | Responde corretamente a /status |
| Message Formatters | ✓ | Status, Jogos, Stats, Help OK |
| Database Access | ✓ | 20 jogos próximos disponíveis |
| Game Window | ✓ | 50-90 min configurado |
| Group Config | ✓ | Group, Admin, Updates configurados |

## Fluxo Agora Funcionando

```
Usuário envia /status no WhatsApp
    ↓
WAHA recebe via SDK WhatsApp
    ↓
WAHA envia webhook para http://cpes-api:8000/api/webhook/whatsapp
    ↓
FastAPI processa em /api/webhook/whatsapp:
  - Parse comando: "status"
  - Chama _handle_admin_command("status")
  - Gera resposta via MessageFormatter.format_health_response()
    ↓
API responde via WhatsAppClient.send_text()
    ↓
Mensagem vai para admin via WAHA
```

## Fluxo de Sinais (Grupo Escanteios)

```
CornerPressureElite detecta sinal
    ↓
decision_engine retorna Sinal
    ↓
NotificationManager.send_signal()
    ↓
MessageFormatter.format_signal()
    ↓
WhatsAppClient.send_text(group_id, message)
    ↓
WAHA envia para grupo 120363424218619609@g.us (Escanteios)
```

## Verificações Importantes

### 1. Confirmar que o Webhook está sendo chamado

Monitore os logs enquanto envia `/status`:

```bash
docker logs cpes-api --follow | grep -i "webhook\|whatsapp"
```

Você deve ver:
```
INFO: POST /api/webhook/whatsapp
```

### 2. Confirmar que Jogos ao Vivo entram na Janela

```bash
curl http://localhost:8000/api/live-games | python3 -m json.tool

# Procure por:
# - "jogos_na_janela": numero > 0 quando há jogos no intervalo 50-90 min
# - "jogos": [ { "minuto": numero entre 50-90 } ]
```

### 3. Confirmar que Sinais são Enviados

```bash
curl http://localhost:8000/api/signals/recent | python3 -m json.tool

# Veja últimos sinais enviados
```

## Proximas Melhorias

1. **Dashboard WebHook Status**: Adicionar indicador visual se WAHA está conectado
2. **Webhook Logging**: Adicionar logs de cada comando processado
3. **Backup Webhook**: Se WAHA falhar, mencionar em /admin status
4. **Test Broadcast**: Comando `/test-group` para enviar mensagem teste ao grupo

## Rollback (se necessário)

Se precisar reverter:

```bash
# Reverter .env
git checkout corner-pressure-elite/.env

# Reverter config.py
git checkout corner-pressure-elite/config.py

# Reverter docker-compose.yml
git checkout docker-compose.yml

# Reiniciar
docker compose down && docker compose up -d
```

---

**Testado em**: 2026-02-15 T14:37:00 UTC
**Status**: ✅ Resolvido - Aguardando confirmação de outro usuário
