# WAHA Plus — Gerar Nova API Key

Guia para criar uma nova API Key para o WAHA Plus (devlikeapro).

---

## 📋 Pré-requisitos

- Conta no DevLike: https://portal.devlike.pro/
- Acesso ao portal de credenciais

---

## 🔑 Passos para Gerar Nova Chave

### 1. Acessar o Portal

Abra: **https://portal.devlike.pro/**

### 2. Fazer Login

- Se já tem conta: login com email e senha
- Se não tem: criar conta (sign up)

### 3. Navegar para API Keys

- No menu, procure por:
  - **"API Keys"**
  - **"Credentials"**
  - **"Tokens"**
  - **"Chaves de Acesso"**

### 4. Gerar Nova Chave

- Clique em **"Generate New Key"** ou **"Create New Key"**
- Ou botão **"+"** perto de API Keys
- Copie a chave gerada (aparece em destaque)

### 5. Guardar a Chave com Segurança

⚠️ **IMPORTANTE:** 
- A chave só aparece **UMA VEZ**
- Se não copiar, precisará gerar outra
- **Nunca** compartilhe a chave em repositórios públicos
- Está no `.gitignore` automaticamente

---

## 🔄 Atualizar no Projeto

### Arquivo `.env`

Edite `/home/daniel/cornerpressureelite/.env`:

```bash
WAHA_API_KEY=SUA_NOVA_CHAVE_AQUI
```

Substitua `SUA_NOVA_CHAVE_AQUI` pela chave gerada no portal.

### Arquivo de Credenciais (Backup Seguro)

Edite `/home/daniel/cornerpressureelite/docs/credenciais/users.txt`:

```bash
WAHA_API_KEY=SUA_NOVA_CHAVE_AQUI
```

---

## ✅ Testar a Nova Chave

### 1. Atualizar Docker

```bash
# Parar o WAHA atual
docker compose down

# Remover container antigo
docker rm waha 2>/dev/null || true

# Reconstruir com nova chave
docker compose up -d
```

### 2. Verificar Logs

```bash
docker compose logs -f waha
```

Procure por mensagens de erro de autenticação.

### 3. Testar Health Check

```bash
curl http://localhost:3000/health
```

Resposta esperada:
```json
{ "status": "ok" }
```

---

## 🚀 Uso da Chave

A `WAHA_API_KEY` é usada para:

1. **Autenticação na API**
   ```bash
   curl -H "Authorization: Bearer $WAHA_API_KEY" http://localhost:3000/api/sessions
   ```

2. **Header X-Api-Key (alguns endpoints)**
   ```bash
   curl -H "X-Api-Key: $WAHA_API_KEY" http://localhost:3000/api/sessions
   ```

3. **Autenticação Docker** (para pull da imagem)
   ```bash
   docker login -u devlikeapro -p $WAHA_API_KEY
   docker pull devlikeapro/waha-plus:latest
   ```

---

## 🔐 Segurança

✅ **Boas práticas:**
- Nunca comite `.env` no git
- Arquivo já está em `.gitignore`
- Rotacione chaves periodicamente
- Use chaves diferentes para dev/prod

---

## ❌ Troubleshooting

### Erro: "Invalid API Key"

- Verifique se copiou **toda** a chave
- Sem espaços no final
- Regenere a chave no portal se necessário

### Erro: "Unauthorized"

- Confirme formato da chave (deve ser string longa)
- Verifique se `.env` foi recarregado
- Reinicie os containers: `docker compose restart waha`

### Porta 3000 em Conflito

Se WAHA não iniciar:
```bash
# Encontrar processo na porta 3000
sudo lsof -i :3000

# Matar processo
sudo kill -9 <PID>

# Restartar
docker compose up -d
```

---

## 📞 Suporte

- **Documentação oficial**: https://waha.devlike.pro/
- **GitHub**: https://github.com/devlikeapro/waha
- **Portal DevLike**: https://portal.devlike.pro/

---

**Última atualização:** 15/02/2026
