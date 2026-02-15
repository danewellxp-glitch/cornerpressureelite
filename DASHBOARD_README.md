# CPES Dashboard Web

Dashboard web em tempo real para o Corner Pressure Elite System, usando **FastAPI** (backend Python) e **Next.js** (frontend React).

## Portas do sistema (resolucao de conflito)

| Servico | Porta | URL |
|---------|-------|-----|
| **WAHA** (WhatsApp API) | 3000 | http://localhost:3000 |
| **Dashboard** (Next.js) | 3001 | http://localhost:3001 |
| **FastAPI** (Backend) | 8000 | http://localhost:8000 |

O Dashboard roda na porta **3001** para evitar conflito com o WAHA (porta 3000).

## Arquitetura

- **Backend (FastAPI)**: API REST em `corner-pressure-elite/api_server.py`
- **Frontend (Next.js)**: Dashboard em `dashboard/`
- **WAHA**: WhatsApp HTTP API (porta 3000)

## Como rodar

### Opcao 1: Script automatizado

```powershell
cd "C:\Users\danew\Documents\CORNER PRESSURE ELITE"
.\start_all.ps1
```

### Opcao 2: Manual

**Terminal 1 - WAHA** (Docker):
```powershell
docker run -d --name waha -p 3000:3000 -v ~/.waha:/app/.sessions devlikeapro/waha:latest
```

**Terminal 2 - Backend** (porta 8000):
```powershell
cd corner-pressure-elite
uvicorn api_server:app --host 127.0.0.1 --port 8000
```

**Terminal 3 - Frontend** (porta 3001):
```powershell
cd dashboard
npm run dev
```

**Terminal 4 - Monitor/Main**:
```powershell
cd corner-pressure-elite
python monitor.py
# ou
python main.py
```

### 3. Acessar

Abra **http://localhost:3001** no navegador (Dashboard na porta 3001).

O Next.js faz proxy de `/api/cpes/*` para `http://localhost:8000/api/*`, então o frontend busca os dados no backend automaticamente.

## Endpoints da API

| Endpoint | Descrição |
|----------|-----------|
| `GET /api/health` | Health check |
| `GET /api/dashboard` | Todos os dados (stats, status, sinais, logs, ligas) |
| `GET /api/stats` | Estatísticas de performance |
| `GET /api/signals/recent?limit=10` | Sinais recentes |
| `GET /api/status` | Status do sistema (ciclo, jogos ao vivo, API) |
| `GET /api/logs?lines=50` | Últimas linhas do log |
| `GET /api/config` | Configuração (ligas, janela) |

## Variaveis de ambiente (dashboard)

- `PORT`: Porta do Next.js (padrao 3001 via script dev)
- `NEXT_PUBLIC_CPES_API`: URL completa do backend (ex: `http://servidor:8000`) se o dashboard e a API estiverem em hosts diferentes. Caso contrario, usa o proxy local.
