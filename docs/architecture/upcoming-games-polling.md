# Próximos Jogos com Polling Inteligente

## Visão Geral

Implementação de sistema inteligente para atualizar próximos jogos programados no dashboard com requisições otimizadas que se auto-ajustam conforme o tempo passa.

## Arquitetura

### Backend (Python)

#### 1. **main.py** - Salvamento de próximos jogos
- Nova função `_save_upcoming_games()` que:
  - Calcula tempo até cada jogo
  - Filtra jogos que já terminaram
  - Salva em `data/upcoming_games.json`
  - Chamada automaticamente após `_fetch_today_schedule()`

```python
# Exemplo de saída em upcoming_games.json
{
  "atualizado": "2026-02-15T14:30:45.123456",
  "proximos": [
    {
      "id": 1234567,
      "timestamp": 1708028400,
      "hora_inicio": "15:30",
      "minutos_ate": 60,
      "home": "Manchester United",
      "away": "Liverpool",
      "liga": "Premier League",
      "placar": "0-0",
      "status": "NS"
    },
    ...
  ]
}
```

#### 2. **api_server.py** - Novo endpoint
- `GET /api/upcoming-games`
- Retorna próximos jogos com tempo até início
- Chamado em tempo real pelo dashboard

#### 3. **data_reader.py** - Função de leitura
- `get_upcoming_games()` - lê `upcoming_games.json`
- `UPCOMING_GAMES_PATH` - caminho do arquivo

### Frontend (TypeScript/React)

#### 1. **UpcomingGames.tsx** - Componente com polling adaptativo

**Lógica de Polling Adaptativo:**

| Tempo até jogo | Intervalo | Caso de uso |
|---|---|---|
| > 90 min | 10 min (600s) | Economia - jogo distante |
| 30-90 min | 2 min (120s) | Preparação - próximo jogo se aproximando |
| 0-30 min | 30 seg (30s) | Crítico - pré-jogo, preparação final |
| < 0 min | 10 seg (10s) | Em andamento - monitoramento durante jogo |

**Features:**
- ✅ Cores dinâmicas baseado no tempo (azul → amarelo → vermelho)
- ✅ Ícone de alerta piscante quando < 30 min
- ✅ Exibe intervalo de polling atual
- ✅ Última atualização com timestamp
- ✅ Auto-ajuste conforme tempo passa
- ✅ Carregamento inicial
- ✅ Tratamento de erros

**Estados visuais:**
```
Normal (>90min):     Azul       → pollling 10min
Preparação (30-90):  Amarelo    → polling 2min  
Crítico (<30min):    Vermelho   → polling 30seg (com ícone ⚠️)
Em andamento (<0):   Amarelo    → polling 10seg
```

## Fluxo de Dados

```
main.py (_fetch_today_schedule)
    ↓
_save_upcoming_games()
    ↓
upcoming_games.json
    ↓
api_server.py (/api/upcoming-games)
    ↓
data_reader.py (get_upcoming_games)
    ↓
Dashboard (UpcomingGames.tsx)
    ↓
Polling inteligente auto-ajustável
```

## Requisições e Economia

### Custo por dia

**Sem jogos:**
- 1 requisição `/api/upcoming-games` a cada 10 min = 144 reqs/dia

**Com 10 jogos ao longo do dia:**

| Fase | Duração | Intervalo | Reqs |
|---|---|---|---|
| Primeiros 90 min | 90 min | 10 min | 9 reqs |
| Preparação (30-90 min antes) | 60 min | 2 min | 30 reqs |
| Crítico (0-30 min antes) | 30 min | 30 seg | 60 reqs |
| Durante jogo (~105 min) | 105 min | 10 seg | 630 reqs |
| **Total por jogo** | | | **~730 reqs** |
| **Total 10 jogos** | | | **~7,300 reqs** |
| **Margem restante** | | | **+200 reqs** |

✅ **Totalmente dentro do orçamento de 7,500 reqs/dia**

## Como Usar

### 1. Verificar endpoint funciona

```bash
# Terminal 1: iniciar backend
cd corner-pressure-elite
python main.py

# Terminal 2: testar endpoint
curl http://localhost:8000/api/upcoming-games
```

### 2. Dashboard mostra próximos jogos

- Acesse http://localhost:3001
- Vá para seção "Próximos jogos programados"
- Veja polling inteligente funcionar em tempo real

### 3. Monitorar ajuste de polling

- Abra DevTools (F12) → Console
- Veja mensagem "Polling: XXs" no canto superior
- Máximo de 10 min entre atualizações quando sem urgência
- Mínimo de 10 seg durante jogo em andamento

## Integração com Sistema Existente

✅ **Não quebra nada existente:**
- Reutiliza `_today_schedule` já populada
- Nova função `_save_upcoming_games()` adicional
- Novo arquivo JSON não afeta outros componentes
- Novo endpoint não interfere com endpoints existentes

✅ **Compatível com Sprint 4:**
- Usa `get_ligas_ativas()` para ligas dinâmicas
- Respeita configuração de ligas do dashboard
- Não requer mudanças no banco de dados

## Próximas Melhorias

- [ ] Notificação push 10 min antes do jogo
- [ ] Webhook para sistemas de trading (webhooks)
- [ ] Histórico de jogos já analisados
- [ ] Filtro por liga na seção de próximos jogos
- [ ] Contagem regressiva animada nos últimos 5 min

## Debug

Se não está vendo próximos jogos:

1. **Verifique se arquivo existe:**
   ```bash
   cat corner-pressure-elite/data/upcoming_games.json
   ```

2. **Verifique se main.py está salvando:**
   ```bash
   grep "_save_upcoming_games" corner-pressure-elite/main.py
   ```

3. **Teste endpoint:**
   ```bash
   curl -s http://localhost:8000/api/upcoming-games | jq .
   ```

4. **Verifique logs do dashboard:**
   ```bash
   # DevTools Console deve mostrar requisições a /api/cpes/upcoming-games
   ```
