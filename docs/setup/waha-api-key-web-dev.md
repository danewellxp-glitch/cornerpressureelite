# WAHA Plus — Criar Nova API Key "web_dev"

Guia para gerar uma nova API Key no nome "web_dev" para acesso a http://localhost:3000/

---

## 📋 Pré-requisitos

- Conta no portal DevLike: https://portal.devlike.pro/
- Permissões de administrador na conta

---

## 🔑 Passos para Criar a Chave "web_dev"

### 1️⃣ Acessar o Portal DevLike

```
https://portal.devlike.pro/
```

### 2️⃣ Fazer Login

- Email e senha da sua conta
- Se não tem conta, criar em: https://portal.devlike.pro/signup

### 3️⃣ Navegar para API Keys/Credentials

No painel lateral, procure por:
- **API Keys**
- **Tokens**
- **Credentials**  
- **Integrations**

### 4️⃣ Criar Nova Chave

Clique em **"+ New API Key"** ou **"Generate Key"**

### 5️⃣ Configurar a Chave

Preencha os campos:

**Nome:** 
```
web_dev
```

**Descrição (opcional):**
```
API Key para ambiente de desenvolvimento - localhost:3000
```

**Permissões (marcar):**
- ✅ Read Sessions
- ✅ Write Sessions
- ✅ Send Messages
- ✅ Receive Webhooks
- ✅ Access Dashboard

**Tipo:** 
- Selecionar: **WAHA Plus** (não Free)

**Domínios permitidos (opcional):**
```
localhost:3000
127.0.0.1:3000
```

### 6️⃣ Gerar e Copiar

Clique em **"Generate"** ou **"Create"**

A chave aparecerá assim:
```
wha_dev_****_****_****_****_****_****
```

⚠️ **COPIE AGORA!** — Você receberá apenas uma vez.

---

## 💾 Salvar a Chave

### Opção A: Adicionar ao `.env`

Edite `/home/daniel/cornerpressureelite/.env`:

```bash
# WAHA (WhatsApp HTTP API)
WAHA_URL=http://localhost:3000
WAHA_SESSION_NAME=default
WAHA_API_KEY=<COLE_AQUI_WHA_DEV_KEY>
```

Substitua `<COLE_AQUI_WHA_DEV_KEY>` pela chave web_dev gerada.

### Opção B: Documentar em Credenciais

Edite `/home/daniel/cornerpressureelite/docs/credenciais/users.txt`:

```bash
# WAHA Plus API Keys
# ==================

# API Key web_dev (localhost:3000 - dev)
WAHA_API_KEY_WEB_DEV=<COLE_AQUI_WHA_DEV_KEY>

# Endpoints autorizados
# - localhost:3000
# - 127.0.0.1:3000

WAHA_URL=http://localhost:3000
WAHA_SESSION_NAME=default
```

---

## 🔐 Usar a Chave

### No Docker Compose

O `.env` já é carregado automaticamente. Após atualizar, reinicie:

```bash
docker compose down
docker compose up -d
```

### Em Requisições HTTP

```bash
# Usando como header Authorization
curl -H "Authorization: Bearer WHA_DEV_KEY" \
  http://localhost:3000/api/sessions

# Ou usando X-Api-Key
curl -H "X-Api-Key: WHA_DEV_KEY" \
  http://localhost:3000/api/sessions
```

### Em Python (notifier/whatsapp_client.py)

A chave é carregada automaticamente do `.env`:

```python
from config import WAHA_API_KEY
from notifier.whatsapp_client import WhatsAppClient, WAHAConfig

config = WAHAConfig(
    base_url="http://localhost:3000",
    session_name="default",
    api_key=WAHA_API_KEY  # Usará web_dev key
)

client = WhatsAppClient(config)
```

---

## ✅ Validar a Nova Chave

### 1. Testar Conexão

```bash
curl -H "X-Api-Key: YOUR_WEB_DEV_KEY" \
  http://localhost:3000/api/sessions
```

Resposta esperada:
```json
{
  "sessions": []
}
```

### 2. Ver Dashboard

Abra no navegador:
```
http://localhost:3000/
```

Devem aparecer as sessões do WAHA.

### 3. Ver Logs

```bash
docker compose logs -f waha
```

Procure por:
- `✅ API Key validated`
- Sem erros de autenticação

---

## 🔄 Gerenciar Múltiplas Chaves

Se precisar de múltiplas chaves (dev, prod, staging):

### No Portal

Crie chaves separadas:
- `web_dev` → localhost (desenvolvimento)
- `web_prod` → seu-dominio.com (produção)
- `api_client` → para scripts Python

### No Projeto

Use variáveis diferentes:

```bash
# .env
WAHA_API_KEY_DEV=wha_dev_...
WAHA_API_KEY_PROD=wha_prod_...
WAHA_API_KEY_CURRENT=${WAHA_API_KEY_DEV}  # Usar dev
```

---

## 🚨 Segurança

✅ **Checklist:**
- [ ] Mantenha `.env` fora do git (já está em `.gitignore`)
- [ ] Não compartilhe a chave em públicos
- [ ] Rotacione chaves a cada 90 dias
- [ ] Use chaves diferentes para each environment
- [ ] Revogar chaves antigas no portal

---

## ❌ Troubleshooting

### Erro: "Invalid API Key"

```bash
# Verifique se foi copiada corretamente
echo $WAHA_API_KEY

# Deve mostrar algo como:
# wha_dev_1234567890...
```

### Erro: "Unauthorized"

- A chave expirou no portal?
- Cofre/cache do Docker? Tente:
  ```bash
  docker compose down
  docker system prune -a
  docker compose up -d
  ```

### Chave não carrega do `.env`

```bash
# Verificar se .env foi recarregado
docker compose ps

# Reiniciar container WAHA
docker compose restart waha

# Ver logs
docker compose logs waha
```

---

## 📊 Monitorar Uso da Chave

No portal DevLike, você pode ver:
- ✅ Requisições feitas com a chave
- ✅ Últimos acessos
- ✅ IP de origem
- ✅ Taxa de requisições

---

## 🔗 Links Úteis

| Link | Descrição |
|------|-----------|
| https://portal.devlike.pro/ | Portal gerenciar chaves |
| https://waha.devlike.pro/ | Documentação oficial WAHA |
| http://localhost:3000/ | WAHA Dashboard local |
| http://localhost:3000/swagger | Swagger API docs |

---

## 📝 Resumo

| Item | Valor |
|------|-------|
| Nome da chave | `web_dev` |
| Tipo | WAHA Plus API Key |
| Alcance | localhost:3000 |
| URL Portall | https://portal.devlike.pro/ |
| Arquivo config | `.env` (WAHA_API_KEY) |

---

**Última atualização:** 15/02/2026 | WAHA Plus
