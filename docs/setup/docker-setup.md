# CPES - Docker e scripts Linux

Sistema completo com Docker e equivalentes Linux dos scripts Windows.

**WAHA Plus:** O projeto usa `devlikeapro/waha-plus`. É necessária autenticação:
```bash
docker login -u devlikeapro -p SEU_TOKEN
# Token obtido em https://portal.devlike.pro/
```

## Opção 1: Docker Compose (tudo em containers)

```bash
# Subir todos os serviços
docker compose up -d

# Ver logs
docker compose logs -f

# Parar
docker compose down
```

**Serviços:**
- **waha** (porta 3000) – WAHA Plus (WhatsApp API)
- **api** (porta 8000) – FastAPI backend
- **dashboard** (porta 3001) – Next.js frontend
- **main** – Robô (analisa jogos e envia alertas)

**URLs:**
- Dashboard: http://localhost:3001
- API: http://localhost:8000
- WAHA: http://localhost:3000

## Opção 2: Scripts shell (modo nativo)

### Iniciar

```bash
./start_all.sh
```

- Inicia WAHA via Docker (se disponível)
- Inicia FastAPI (uvicorn)
- Inicia Dashboard (npm run dev)
- Opcional: Monitor no terminal

### Parar

```bash
./kill_all.sh
```

## Variáveis de ambiente

1. Copie o exemplo:
   ```bash
   cp corner-pressure-elite/.env.example corner-pressure-elite/.env
   ```

2. Edite `corner-pressure-elite/.env` com suas chaves:
   - `API_FOOTBALL_KEY` – obrigatório para o robô
   - `WHATSAPP_GROUP_ID`, `WHATSAPP_ADMIN` – WhatsApp
   - `WAHA_API_KEY` – se o WAHA exigir autenticação

## Usar tudo via Docker Compose no start_all.sh

```bash
CPES_USE_DOCKER=1 ./start_all.sh
```

Isso inicia todos os serviços via `docker compose up -d`.
