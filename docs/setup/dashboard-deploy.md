# 🎯 Dashboard v2 - Guia de Deploy

## Status

O novo dashboard foi redesenhado com:
- ✅ Componentes modernos (UI, Cards, Badges)
- ✅ KPIs (8 cards)
- ✅ Jogos ao vivo com phases
- ✅ Sinais recentes
- ✅ Ligas monitoradas
- ✅ Status do sistema
- ✅ Logs em estilo terminal
- ✅ Atualização automática (10s)
- ✅ Design Cyan/Blue com gradientes
- ✅ Responsivo

---

## 🚀 Deploy Localhost (Docker)

### 1. Rebuild & Restart

```bash
cd /home/daniel/cornerpressureelite
chmod +x rebuild_dashboard_safe.sh
./rebuild_dashboard_safe.sh
```

Ou manualmente:

```bash
sudo docker compose down
sudo docker compose build dashboard
sudo docker compose up -d
```

### 2. Verificar Status

```bash
sudo docker compose ps
sudo docker compose logs -f dashboard
```

### 3. Acessar

```
http://localhost:3001
```

---

## 🌐 Deploy Cloudflare (odontoschultz.online)

### Pré-requisitos

- ✅ Cloudflare account com odontoschultz.online
- ✅ Wrangler CLI (`npm install -g wrangler`)
- ✅ Cloudflare API Token

### 1. Autenticar

```bash
cd dashboard
wrangler login
```

### 2. Build para Cloudflare

```bash
npm run build
```

### 3. Deploy

```bash
npm run deploy
```

### 4. Configurar Domínio

No Cloudflare Dashboard:
1. Vá para **Workers & Pages** → **corner-pressure-dashboard**
2. **Settings** → **Domains & Routes**
3. Adicione:
   - `odontoschultz.online`
   - `www.odontoschultz.online`

### 5. Configurar Variáveis de Ambiente

No Cloudflare Dashboard:
1. **Settings** → **Environment variables**
2. Adicione:
   - `NEXTJS_ENV` = `production`
   - `CPES_API_URL` = `https://api.odontoschultz.online` (ou onde sua API estiver)

> **Nota:** A API precisa estar acessível de fora (Railway, Render, etc.) ou via Cloudflare Tunnel.

### 6. Acessar

```
https://odontoschultz.online
https://www.odontoschultz.online
```

---

## 🔧 Configurações Ajustadas

✅ **Dockerfile**: Atualizado para produção (build + start)
✅ **.env.production**: Variáveis para produção
✅ **.dev.vars**: Variáveis para desenvolvimento
✅ **next.config.ts**: Rewrites para API com detecção de ambiente
✅ **wrangler.jsonc**: Configurações Cloudflare atualizadas

---

## 🐛 Troubleshooting

### Porta 3001 já em uso

```bash
sudo lsof -i :3001
sudo kill -9 <PID>
```

### API não conecta

Verifique `CPES_API_URL`:
- Docker: `http://api:8000`
- Localhost: `http://localhost:8000`
- Produção: URL externa da API

### Rebuild não funciona

```bash
# Limpar cache e rebuild
sudo docker-compose down
sudo docker system prune -a
sudo docker-compose build --no-cache dashboard
sudo docker-compose up -d
```

---

## 📝 Próximos Passos

1. **Testar Localhost**: http://localhost:3001
2. **Verificar dados em tempo real**: Jogos, sinais, status
3. **Deploy Cloudflare**: Seguir seção acima
4. **Pedir testes em produção**: https://odontoschultz.online

---

## 📞 Contato

Para dúvidas, verifique:
- Logs Docker: `sudo docker-compose logs -f dashboard`
- API: `http://localhost:8000/docs` (FastAPI docs)
- Error console browser: F12
