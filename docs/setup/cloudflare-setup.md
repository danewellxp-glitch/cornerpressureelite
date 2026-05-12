# Configuração Cloudflare – iqpressure.online

> **STATUS (2026-05-11):** este doc descreve o caminho **alternativo** de deploy via Cloudflare Workers. **O setup em produção usa Cloudflare Tunnel** (não Workers). Para a topologia real, ver `CLAUDE.md` §9 e `docs/changelog/2026-05-11-migracao-dominio-iqpressure.md`. Mantido como referência se for migrar de Tunnel pra Workers no futuro.

Guia para publicar o projeto no domínio **iqpressure.online** usando Cloudflare Workers.

## Arquitetura

| Domínio | Serviço | Descrição |
|---------|---------|-----------|
| **iqpressure.online** | Frontend (dashboard) | **Apenas** o dashboard Next.js – Cloudflare Workers |
| **www.iqpressure.online** | Frontend (dashboard) | Mesmo dashboard |
| **ssh.iqpressure.online** | SSH Tunnel | Acesso SSH via Cloudflare Tunnel |

O domínio principal **só serve o frontend**. A API Python fica em outro provedor (Railway, Render, etc.).

---

## SSH Tunnel (ssh.iqpressure.online)

O tunnel SSH está configurado e ativo. Para conectar:

1. Adicione ao `~/.ssh/config`:
   ```
   Host ssh.iqpressure.online
     ProxyCommand /usr/bin/cloudflared access ssh --hostname %h
   ```

2. Conecte:
   ```bash
   ssh seu-usuario@ssh.iqpressure.online
   ```

Para manter o tunnel rodando em segundo plano:
```bash
cloudflared tunnel run ssh-tunnel
```

---

## 1. Pré-requisitos

1. **Conta Cloudflare** – [dash.cloudflare.com](https://dash.cloudflare.com)
2. **Domínio iqpressure.online** – adicionado e gerenciado pela Cloudflare
3. **Node.js 18+**

---

## 2. Instalação das dependências

```bash
cd dashboard
npm install
```

---

## 3. Configurar a API (Backend Python)

A API precisa estar em um serviço acessível na internet. Exemplos:

### Opção A: Railway / Render / Fly.io

1. Faça deploy da pasta `corner-pressure-elite`
2. Obtenha a URL pública, por exemplo: `https://api-corner-pressure.railway.app`
3. Atualize o CORS em `api_server.py` para incluir o domínio:

```python
allow_origins=[
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:3001", "http://127.0.0.1:3001",
    "https://iqpressure.online", "https://www.iqpressure.online"
],
```

---

## 4. Variável de ambiente da API

`NEXT_PUBLIC_CPES_API` precisa existir **durante o build**. Crie um arquivo na pasta `dashboard`:

**dashboard/.env.production**
```
NEXT_PUBLIC_CPES_API=https://sua-api.railway.app
```

Substitua pela URL real da sua API (Railway, Render, etc.).

> Não comite `.env.production` se tiver dados sensíveis. Ele já está em `.gitignore`. Se usar CI/CD no Cloudflare (Git integration), defina essa variável em **Settings → Environment variables** no painel.

---

## 5. Login no Cloudflare (CLI)

```bash
cd dashboard
npx wrangler login
```

---

## 6. Deploy

```bash
cd dashboard
npm run deploy
```

Isso vai:

1. Fazer o build do Next.js
2. Converter para Cloudflare Workers
3. Publicar na sua conta

---

## 7. Configurar o domínio iqpressure.online (somente frontend)

> O domínio **iqpressure.online** e **www.iqpressure.online** servem **apenas** o dashboard (frontend). Nenhum backend ou API no domínio principal.

1. Acesse **Workers & Pages** no painel Cloudflare
2. Abra o Worker **corner-pressure-dashboard**
3. Vá em **Settings** → **Domains & Routes**
4. Clique em **Add** → **Custom Domain**
5. Informe: `iqpressure.online`
6. Opcionalmente, adicione também: `www.iqpressure.online`

### DNS no Cloudflare

Se o domínio já está na Cloudflare:

1. **Websites** → **iqpressure.online** → **DNS**
2. Não é necessário criar registros manualmente para o Worker; ao adicionar o Custom Domain, o Cloudflare configura automaticamente

Se o domínio está em outro provedor:

1. **Websites** → **Add a Site**
2. Siga o assistente e atualize os nameservers no seu provedor de domínio
3. Depois, configure o Custom Domain no Worker conforme acima

---

## 8. Resumo dos comandos

| Comando      | Descrição                                    |
|-------------|-----------------------------------------------|
| `npm run dev`   | Desenvolvimento local                         |
| `npm run preview` | Preview local como no Cloudflare Workers |
| `npm run deploy` | Deploy para Cloudflare                       |
| `npm run upload` | Apenas upload (deploy gradual)               |

---

## 9. Checklist

- [ ] Dependências instaladas (`npm install`)
- [ ] API Python em produção (Railway/Render/etc.)
- [ ] CORS atualizado com `iqpressure.online`
- [ ] Variável `NEXT_PUBLIC_CPES_API` definida no Cloudflare
- [ ] `npx wrangler login` executado
- [ ] `npm run deploy` executado com sucesso
- [ ] Custom Domain `iqpressure.online` adicionado ao Worker
