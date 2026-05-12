# ✅ Dashboard v2 - Resumo de Instalação

## 🎯 O que foi feito

O novo dashboard redesenhado agora substitui completamente o antigo com:

- **8 KPI Cards**: Sinais, Greens, Reds, Pendentes, Winrate, ROI, Premium, Normal
- **Jogos ao Vivo**: 3 fases (Pré-janela, Na janela, Pós-janela) com badges LIVE
- **Sinais Recentes**: Cards com tipo, jogo, score, projeção, edge, resultado
- **Ligas Monitoradas**: Grid com bandeiras e média de escanteios
- **Status do Sistema**: API, janela, jogos, polling
- **Logs Terminal**: Estilo terminal com cores por nível
- **Design**: Cyan/Blue (#00d9ff) com gradientes, responsivo
- **Atualização**: Automática a cada 10 segundos

---

## 🚀 Como Deploy (3 passos)

### 1️⃣ Fazer Rebuild (em seu terminal)

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

### 2️⃣ Verificar se Está Rodando

```bash
# Ver containers
sudo docker compose ps

# Ver logs
sudo docker compose logs -f dashboard
```

### 3️⃣ Acessar

- **Localhost**: http://localhost:3001
- **Produção**: https://iqpressure.online (após deploy Cloudflare)

---

## 🌐 Deploy em Produção (Cloudflare)

### Para iqpressure.online

```bash
cd dashboard

# Fazer build
npm run build

# Deploy (requer cloudflare login)
npm run deploy

# OU fazer upload apenas
npm run upload
```

Depois, no [Cloudflare Dashboard](https://dash.cloudflare.com/):

1. **Workers & Pages** → **corner-pressure-dashboard**
2. **Settings** → **Domains & Routes**
3. Adicionar domínios:
   - `iqpressure.online`
   - `www.iqpressure.online`

4. **Settings** → **Environment variables**
5. Adicionar: `CPES_API_URL` = URL da API em produção

---

## 📝 Arquivos Alterados

✅ `dashboard/Dockerfile` - Produção (build + start)
✅ `dashboard/next.config.ts` - Rewrites da API
✅ `dashboard/.env.production` - Vars produção
✅ `dashboard/.dev.vars` - Vars desenvolvimento
✅ `dashboard/wrangler.jsonc` - Config Cloudflare
✅ `docker-compose.yml` - Sem mudanças (já estava correto)

---

## ⚡ TL;DR (Quick Start)

```bash
cd /home/daniel/cornerpressureelite
./rebuild_dashboard_safe.sh
```

Depois abra: **http://localhost:3001**

---

## 🐛 Se Algo der Errado

### Porta em uso
```bash
sudo lsof -i :3001
sudo kill -9 <PID>
```

### Limpar e rebuild
```bash
sudo docker system prune -a
sudo docker compose build --no-cache dashboard
```

### Ver erros
```bash
sudo docker compose logs -f dashboard
```

---

Pronto! Dashboard v2 substitui totalmente o antigo tanto em localhost quanto em produção. 🚀
