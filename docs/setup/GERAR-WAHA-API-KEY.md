# 🔑 Gerar WAHA API Key no Portal DevLike

Passo a passo para gerar a chave correta no portal.

---

## 📋 Acesse o Portal

Abra: **https://portal.devlike.pro/**

(Use o Docker Token para login se necessário)

---

## 🚀 Passos para Gerar a API Key

### 1️⃣ Faça Login

- Email e Senha
- Se pedir verificação de 2FA, confirme

### 2️⃣ Procure por "API Keys"

No painel lateral ou menu, procure por:
- **API Keys**
- **Credentials** 
- **Tokens**
- **Keys**

### 3️⃣ Clique em "Generate" ou "+ New Key"

Você verá algo assim:
- **Generate New API Key**
- **Create New Credential**
- **+ Add Key**

### 4️⃣ Preencha os Campos

**Nome da Chave:**
```
web_dev
```

**Descrição (opcional):**
```
WAHA Plus API Key para localhost:3000
```

**Tipo/Scope (marque):**
- ✅ Sessions Management
- ✅ Send Messages  
- ✅ Webhooks
- ✅ API Access

**Permissões:**
- ✅ Read
- ✅ Write

### 5️⃣ Clique em "Generate" ou "Create"

A chave aparecerá assim:
```
wha_XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

❗ **COPIE AGORA!** Só aparece uma vez!

---

## 📝 Cole a Chave aqui

Depois de copiar, responda com a chave novinha:

```
Chave: wha_XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Vou atualizar tudo automaticamente! ✅

---

## 📊 O que você vai receber

| Item | Valor |
|------|-------|
| **Tipo** | WAHA Plus API Key |
| **Formato** | Começa com `wha_` |
| **Tamanho** | ~32-40 caracteres |
| **Onde usar** | `.env` como `WAHA_API_KEY` |

---

## ⚠️ Importante

- ✅ A chave só aparece **UMA VEZ**
- ✅ Se não copiar, precisa gerar novamente
- ✅ Nunca compartilhe em repositórios públicos
- ✅ Está no `.gitignore` (seguro)

---

Estou esperando! 🎯
