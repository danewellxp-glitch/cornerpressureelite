# ROBÔ DE APOSTAS ESPORTIVAS - DOCUMENTAÇÃO TÉCNICA COMPLETA
## Corner Pressure Elite System

---

## 📋 SUMÁRIO EXECUTIVO

**Nome do Projeto:** Corner Pressure Elite System (CPES)  
**Objetivo:** Sistema de análise e sinais para apostas em escanteios (corners) ao vivo  
**Tipo:** Motor de decisão estatístico semi-quantitativo  
**Abordagem:** Não automatizado - Sistema de alertas inteligentes  
**Filosofia:** Edge matemático através de projeção híbrida vs. linha de mercado

---

## 🎯 CONCEITO GERAL DO PROJETO

### Ideia Original
Criar um sistema que:
1. Monitore jogos de futebol ao vivo em ligas específicas
2. Analise estatísticas em tempo real (especialmente escanteios)
3. Calcule projeções matemáticas de escanteios totais
4. Compare essas projeções com as linhas oferecidas pelas casas de apostas
5. Detecte quando há **valor estatístico** (edge)
6. Envie alertas estruturados para o usuário decidir se aposta

### O Que NÃO É
- ❌ Sistema que acessa conta da casa de apostas
- ❌ Bot que faz apostas automaticamente
- ❌ Sistema que viola termos de uso
- ❌ Garantia de lucro
- ❌ Sistema baseado em intuição ou "dicas"

### O Que É
- ✅ Motor de análise estatística em tempo real
- ✅ Sistema de projeção matemática de escanteios
- ✅ Detector de discrepâncias entre projeção e mercado
- ✅ Ferramenta de alertas inteligentes
- ✅ Sistema profissional de análise quantitativa

---

## 🏗️ ARQUITETURA DO SISTEMA

### Stack Tecnológico

```
LINGUAGEM: Python 3.11+

FRAMEWORK WEB (OPCIONAL): FastAPI ou Flask
SCHEDULER: APScheduler ou asyncio loop
API DE DADOS: API-Football v3 (api-sports.io)
BANCO DE DADOS: 
  - Inicial: SQLite
  - Produção: PostgreSQL
NOTIFICAÇÕES: Webhook para WhatsApp
LOGGING: Sistema customizado em arquivo/banco
```

### Estrutura de Diretórios

```
corner-pressure-elite/
│
├── config.py                 # Configurações gerais
├── main.py                   # Entry point principal
│
├── data/
│   ├── __init__.py
│   ├── api_client.py         # Cliente da API-Football
│   └── models.py             # Modelos de dados (Pydantic/Dataclass)
│
├── engine/
│   ├── __init__.py
│   ├── score_engine.py       # Cálculo do Pressure Score
│   ├── projection_engine.py  # Modelo de projeção híbrida
│   ├── decision_engine.py    # Lógica de decisão de entrada
│   └── state_manager.py      # Gerenciamento de estado dos jogos
│
├── notifier/
│   ├── __init__.py
│   └── webhook_sender.py     # Envio de alertas via webhook
│
├── storage/
│   ├── __init__.py
│   ├── logger.py             # Sistema de logging
│   └── database.py           # Gerenciamento de banco de dados
│
├── utils/
│   ├── __init__.py
│   ├── rate_limiter.py       # Controle de rate limit da API
│   └── helpers.py            # Funções auxiliares
│
└── tests/
    ├── __init__.py
    ├── test_projection.py
    ├── test_score.py
    └── test_decision.py
```

---

## 🔑 API-FOOTBALL - CONFIGURAÇÃO E USO

### Autenticação

```python
# Todas as requisições precisam incluir:
Headers: {
    'x-apisports-key': 'SUA_API_KEY_AQUI'
}
```

### Endpoints Principais

#### 1. Status da Conta
```
GET https://v3.football.api-sports.io/status
```
**Uso:** Verificar requisições restantes (NÃO conta como requisição)

**Resposta:**
```json
{
  "response": {
    "subscription": {
      "plan": "Pro",
      "end": "2026-02-XX"
    },
    "requests": {
      "current": 350,
      "limit_day": 7500
    }
  }
}
```

#### 2. Jogos ao Vivo
```
GET https://v3.football.api-sports.io/fixtures?live=all
```
**Uso:** Listar todos os jogos ao vivo

**Filtros úteis:**
```
?live=all&league=39        # Premier League ao vivo
?live=all&league=71        # Brasileirão ao vivo
```

#### 3. Estatísticas do Jogo
```
GET https://v3.football.api-sports.io/fixtures/statistics?fixture=ID_DO_JOGO
```
**Uso:** Obter estatísticas detalhadas incluindo escanteios

**Dados retornados:**
```json
{
  "statistics": [
    {
      "type": "Corner Kicks",
      "value": 8
    },
    {
      "type": "Shots on Goal", 
      "value": 12
    },
    {
      "type": "Dangerous Attacks",
      "value": 45
    },
    {
      "type": "Ball Possession",
      "value": "58%"
    }
  ]
}
```

#### 4. Eventos do Jogo
```
GET https://v3.football.api-sports.io/fixtures/events?fixture=ID_DO_JOGO
```
**Uso:** Obter eventos como gols, cartões, escanteios com timestamp

#### 5. Odds
```
GET https://v3.football.api-sports.io/odds?fixture=ID_DO_JOGO
```
**Uso:** Obter odds em tempo real (se disponível)

### Limites e Consumo

**Plano Pro:** 7.500 requisições/dia

**Cálculo de Consumo:**
```
Cenário: Monitorar 10 jogos simultâneos

Por ciclo (60 segundos):
- 1 requisição: Lista de jogos ao vivo
- 10 requisições: Estatísticas (1 por jogo)
- 10 requisições: Eventos (1 por jogo)
- 10 requisições: Odds (1 por jogo)
TOTAL: 31 requisições/ciclo

Duração média: 90 minutos = 90 ciclos
Consumo total: 31 × 90 = 2.790 requisições

Jogos por dia: 7.500 / 2.790 ≈ 2.7 "blocos" de 10 jogos
OU
Aproximadamente 25-30 jogos ao longo do dia
```

**Otimizações:**
1. Atualizar odds a cada 60s (não 30s)
2. Atualizar eventos a cada 60s
3. Estatísticas detalhadas só quando necessário
4. Usar cache para dados históricos
5. Backtest em horários de baixo uso

---

## 📊 ESTRATÉGIA - MODELO HÍBRIDO SEMI-QUANTITATIVO

### Filosofia Central

**Objetivo:** Detectar quando o jogo está produzindo mais escanteios do que o mercado está precificando

**Conceito de Edge:**
```
Edge = Projeção_do_Modelo - Linha_da_Casa

Se Edge ≥ Threshold → Há valor estatístico
```

### Janela de Monitoramento

**Minuto de Início:** 55  
**Minuto de Fim:** 78  
**Razão:** Equilíbrio entre:
- Dados suficientes acumulados
- Odds ainda razoáveis
- Tempo suficiente para materializar

---

## 🚦 FILTROS ESTRUTURAIS (Pré-requisitos)

Antes de calcular score, o jogo DEVE atender:

```python
FILTROS_OBRIGATORIOS = {
    "minuto": >= 55 AND <= 78,
    "diferenca_gols": <= 2,
    "escanteios_totais": >= 5,
    "escanteio_ultimos_5min": >= 1,
    
    # Filtro especial para jogo morno:
    "se_0x0_no_minuto_60": escanteios >= 7,
    
    # Bloqueio de jogo morto:
    "time_sem_escanteio_1tempo": BLOQUEIA
}
```

**Exemplo de bloqueio:**
- Jogo 0x0 no minuto 65
- Apenas 4 escanteios totais
- ❌ BLOQUEADO - Jogo muito morno

---

## 🔥 PRESSURE SCORE (Motor Principal)

### Conceito
Medir a **intensidade ofensiva atual** do jogo através de múltiplos indicadores

### Sistema de Pontuação

| Condição | Pontos |
|----------|--------|
| 2+ escanteios nos últimos 10 minutos | +3 |
| 1 escanteio nos últimos 5 minutos | +1 |
| 6+ ataques perigosos últimos 10 min | +2 |
| Time perdendo por 1 gol | +2 |
| Posse > 60% últimos 10 min | +1 |
| Finalizações recentes | +1 |

**Máximo Teórico:** ~10 pontos  
**Mínimo para Entrada:** 8 pontos  
**Sinal Premium:** 9+ pontos

### Lógica de Implementação

```python
def calcular_pressure_score(dados_jogo):
    score = 0
    
    # Escanteios recentes (peso alto)
    if dados_jogo.escanteios_ultimos_10min >= 2:
        score += 3
    
    if dados_jogo.escanteios_ultimos_5min >= 1:
        score += 1
    
    # Ataques perigosos
    if dados_jogo.ataques_perigosos_ultimos_10min >= 6:
        score += 2
    
    # Contexto do placar
    if dados_jogo.time_perdendo_por_1():
        score += 2
    
    # Domínio de posse
    if dados_jogo.posse_ultimos_10min > 60:
        score += 1
    
    # Finalizações
    if dados_jogo.finalizacoes_recentes >= 3:
        score += 1
    
    return score
```

**Exemplo Real:**
```
Minuto 63
Internacional 1 x 1 Palmeiras

Últimos 10 min:
- 2 escanteios (+3)
- 7 ataques perigosos (+2)
- Jogo empatado (sem bônus)
- Posse 62% (+1)

SCORE = 6 pontos
```

---

## 📈 MODELO DE PROJEÇÃO HÍBRIDA

### Componentes da Projeção

A projeção final combina 3 elementos ponderados:

#### 1. **Ritmo Atual** (Base Matemática)

```python
def calcular_ritmo_base(escanteios_atuais, minuto_atual):
    ritmo_por_minuto = escanteios_atuais / minuto_atual
    projecao_95min = ritmo_por_minuto * 95
    return projecao_95min
```

**Exemplo:**
- Minuto 60
- 8 escanteios
- Ritmo: 8/60 = 0.133 por minuto
- Projeção: 0.133 × 95 = 12.67 escanteios

#### 2. **Ajuste de Pressão** (Contexto Atual)

```python
def ajuste_pressao(pressure_score):
    # Score de 0-10 vira ajuste de 0 a +2.5
    ajuste = pressure_score * 0.25
    return ajuste
```

**Exemplo:**
- Pressure Score = 8
- Ajuste = 8 × 0.25 = +2.0

#### 3. **Ajuste Histórico** (Baseline dos Times)

```python
def ajuste_historico(media_ultimos_10_jogos):
    if media_ultimos_10_jogos > 10.5:
        return +0.5
    return 0
```

### Fórmula Final

```python
def projecao_hibrida(escanteios, minuto, pressure_score, media_historica):
    # Base
    ritmo = (escanteios / minuto) * 95
    
    # Ajustes
    ajuste_press = pressure_score * 0.25
    ajuste_hist = 0.5 if media_historica > 10.5 else 0
    
    # Projeção final
    projecao = ritmo + ajuste_press + ajuste_hist
    
    return round(projecao, 2)
```

### Exemplo Completo

```
JOGO: Minuto 58
Escanteios atuais: 7
Pressure Score: 8
Média histórica combinada: 11.2

CÁLCULO:
1. Ritmo = (7/58) * 95 = 11.47
2. Ajuste Pressão = 8 * 0.25 = 2.0
3. Ajuste Histórico = +0.5

PROJEÇÃO FINAL = 11.47 + 2.0 + 0.5 = 13.97
```

---

## ⚡ MOTOR DE DECISÃO

### Conceito de Edge

```
Edge = Projeção - Linha_Atual_da_Casa

Exemplos:
- Projeção: 13.5, Linha: 11.5 → Edge = +2.0 ✅
- Projeção: 12.0, Linha: 11.5 → Edge = +0.5 ❌
```

### Níveis de Sinal

#### SINAL NORMAL
```python
CONDICOES = {
    "pressure_score": >= 8,
    "edge": >= 1.3,
    "minuto": >= 55 and <= 78
}
```

#### SINAL PREMIUM
```python
CONDICOES = {
    "pressure_score": >= 9,
    "edge": >= 2.0,
    "minuto": >= 55 and <= 78
}
```

### Lógica de Implementação

```python
def avaliar_entrada(jogo):
    # 1. Verificar filtros estruturais
    if not passou_filtros_estruturais(jogo):
        return None
    
    # 2. Calcular pressure score
    score = calcular_pressure_score(jogo)
    if score < 8:
        return None
    
    # 3. Calcular projeção
    projecao = projecao_hibrida(
        jogo.escanteios,
        jogo.minuto,
        score,
        jogo.media_historica
    )
    
    # 4. Calcular edge
    edge = projecao - jogo.linha_atual
    
    # 5. Decidir sinal
    if score >= 9 and edge >= 2.0:
        return {
            "tipo": "PREMIUM",
            "score": score,
            "projecao": projecao,
            "edge": edge,
            "linha": jogo.linha_atual,
            "odd": jogo.odd_atual
        }
    
    elif score >= 8 and edge >= 1.3:
        return {
            "tipo": "NORMAL",
            "score": score,
            "projecao": projecao,
            "edge": edge,
            "linha": jogo.linha_atual,
            "odd": jogo.odd_atual
        }
    
    return None
```

---

## 🔄 SISTEMA DE RE-AVALIAÇÃO

### Conceito
Após enviar o primeiro alerta, o sistema continua monitorando. Se as condições melhorarem significativamente, envia nova mensagem **informativa**.

### Condições para Re-avaliação

```python
REAVALIACAO_SE = {
    "linha_mudou": True,
    OR
    "edge_aumentou": >= 0.7,
    OR  
    "score_aumentou": >= 1,
    
    AND
    "tempo_desde_ultimo_alerta": >= 3  # minutos
}
```

### Diferença Crítica

```
PRIMEIRO ALERTA:
"🟡 OVER ESCANTEIOS - NORMAL"
Stake sugerida: 1u

RE-AVALIAÇÃO:
"🔄 RE-EVALUATION - SCENARIO IMPROVED"
[SEM sugestão de stake adicional]
```

**Razão:** Evitar stacking (empilhar apostas no mesmo jogo)

---

## 💰 GESTÃO DE RISCO E STAKE

### Princípios Fundamentais

1. **Stake Fixa:** Sempre 1 unidade
2. **Sem Martingale:** Nunca dobrar após perda
3. **Sem Stacking:** Nunca adicionar stake no mesmo jogo
4. **Sem Limite Diário:** Sistema pode gerar múltiplos sinais/dia
5. **Execução Manual:** Humano decide se entra ou não

### Por Que Stake Fixa?

```
VANTAGENS:
✅ Controle de risco simples
✅ Baixa variância
✅ Mede ROI real da estratégia
✅ Não mascara erros do modelo
✅ Psicologicamente mais fácil
✅ Ideal para validação inicial

DESVANTAGENS:
❌ Não maximiza sinais muito fortes
❌ Trata todos os sinais igualmente
```

### Evolução Futura (Após Validação)

Após 200-500 entradas validadas, pode-se considerar:

```python
STAKE_PROGRESSIVA = {
    "score_8_edge_1.3": 1.0,   # Normal
    "score_9_edge_2.0": 1.5,   # Premium
    "score_10_edge_2.5": 2.0   # Excepcional
}
```

---

## 🎯 LIGAS MONITORADAS

### Ligas Principais (IDs da API-Football)

| Liga | ID | Razão |
|------|----|----|
| Premier League | 39 | Alta intensidade, dados confiáveis |
| Bundesliga | 78 | Jogos abertos, muitos escanteios |
| Brasileirão Série A | 71 | Mercado local, familiaridade |
| Brasileirão Série B | 72 | Menos eficiente, mais oportunidades |

### Configuração no Sistema

```python
LIGAS_MONITORADAS = [
    {
        "id": 39,
        "nome": "Premier League",
        "pais": "England",
        "media_esperada": 10.8
    },
    {
        "id": 78,
        "nome": "Bundesliga",
        "pais": "Germany",
        "media_esperada": 11.2
    },
    {
        "id": 71,
        "nome": "Brasileirão A",
        "pais": "Brazil",
        "media_esperada": 9.8
    },
    {
        "id": 72,
        "nome": "Brasileirão B",
        "pais": "Brazil",
        "media_esperada": 9.5
    }
]
```

---

## 📱 SISTEMA DE ALERTAS

### Formato de Mensagem - SINAL NORMAL

```
🟡 OVER ESCANTEIOS – NORMAL

🏆 Liga: Premier League
⚽ Jogo: Manchester City vs Arsenal
⏱️ Minuto: 63
📊 Placar: 1-1

📈 ANÁLISE:
Escanteios atuais: 8
Linha: 11.5
Projeção: 13.2
Edge: +1.7

🔥 Pressure Score: 8/10

💰 MERCADO:
Odd: 1.78
Stake sugerida: 1u

⚠️ Tipo: ENTRADA NORMAL
```

### Formato de Mensagem - SINAL PREMIUM

```
🔥 OVER ESCANTEIOS – PREMIUM

🏆 Liga: Bundesliga  
⚽ Jogo: Bayern vs Dortmund
⏱️ Minuto: 58
📊 Placar: 2-1

📈 ANÁLISE:
Escanteios atuais: 9
Linha: 12.5
Projeção: 15.1
Edge: +2.6

🔥 Pressure Score: 9/10

💰 MERCADO:
Odd: 1.95
Stake sugerida: 1u

🚀 Tipo: ENTRADA PREMIUM
```

### Formato - RE-AVALIAÇÃO

```
🔄 RE-EVALUATION – SCENARIO IMPROVED

🏆 Liga: Premier League
⚽ Jogo: Manchester City vs Arsenal
⏱️ Minuto: 68 (Alerta inicial: 63)

📈 MUDANÇAS:
Escanteios: 8 → 10
Linha: 11.5 → 12.5
Projeção: 13.2 → 14.8
Edge: +1.7 → +2.3
Score: 8 → 9

💡 Cenário melhorou significativamente
⚠️ Re-avaliação informativa apenas
   (Sem sugestão de stake adicional)
```

### Webhook - Implementação Técnica

```python
import requests
import json

def enviar_alerta_webhook(dados_sinal):
    """
    Envia alerta via webhook para WhatsApp ou Telegram
    """
    webhook_url = "https://seu-webhook.com/endpoint"
    
    payload = {
        "tipo": dados_sinal["tipo"],
        "liga": dados_sinal["liga"],
        "jogo": dados_sinal["jogo"],
        "minuto": dados_sinal["minuto"],
        "placar": dados_sinal["placar"],
        "escanteios": dados_sinal["escanteios"],
        "linha": dados_sinal["linha"],
        "projecao": dados_sinal["projecao"],
        "edge": dados_sinal["edge"],
        "score": dados_sinal["score"],
        "odd": dados_sinal["odd"]
    }
    
    mensagem_formatada = formatar_mensagem(payload)
    
    response = requests.post(
        webhook_url,
        json={"message": mensagem_formatada},
        headers={"Content-Type": "application/json"}
    )
    
    return response.status_code == 200
```

---

## 🗄️ SISTEMA DE LOGGING E ARMAZENAMENTO

### Dados a Registrar

**Registro APENAS de entradas** (não monitora todos os jogos)

```sql
CREATE TABLE sinais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    
    -- Identificação
    liga_id INTEGER NOT NULL,
    liga_nome VARCHAR(100),
    jogo_id INTEGER NOT NULL,
    jogo_descricao VARCHAR(200),
    
    -- Estado do jogo
    minuto INTEGER NOT NULL,
    placar VARCHAR(10),
    escanteios_total INTEGER NOT NULL,
    
    -- Mercado
    linha DECIMAL(3,1) NOT NULL,
    odd DECIMAL(4,2) NOT NULL,
    
    -- Modelo
    projecao DECIMAL(4,2) NOT NULL,
    edge DECIMAL(3,2) NOT NULL,
    pressure_score INTEGER NOT NULL,
    
    -- Sinal
    tipo_sinal VARCHAR(20) NOT NULL, -- 'NORMAL' ou 'PREMIUM'
    reavalicao BOOLEAN DEFAULT FALSE,
    
    -- Resultado (preenchido posteriormente)
    resultado VARCHAR(10), -- 'GREEN', 'RED', NULL
    escanteios_final INTEGER,
    roi DECIMAL(5,2)
);
```

### Campos Adicionais Opcionais

```sql
-- Tabela de detalhes do jogo (para análise posterior)
CREATE TABLE detalhes_jogo (
    sinal_id INTEGER,
    ataques_perigosos INTEGER,
    finalizacoes INTEGER,
    posse_time_casa INTEGER,
    posse_time_fora INTEGER,
    escanteios_time_casa INTEGER,
    escanteios_time_fora INTEGER,
    media_historica DECIMAL(4,2),
    
    FOREIGN KEY (sinal_id) REFERENCES sinais(id)
);
```

### Logging em Arquivo

```python
import logging
from datetime import datetime

# Configuração
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/cpes_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('CPES')

# Uso
logger.info(f"Sinal NORMAL gerado: {jogo} - Edge: {edge}")
logger.warning(f"API rate limit próximo: {requests_remaining}")
logger.error(f"Erro ao buscar dados do jogo {jogo_id}: {erro}")
```

---

## 🔄 POLLING E ATUALIZAÇÃO

### Frequência de Atualização

```python
INTERVALO_POLLING = {
    "lista_jogos_vivos": 60,      # segundos
    "estatisticas_jogo": 60,       # segundos  
    "eventos_jogo": 60,            # segundos
    "odds_jogo": 60,               # segundos
    "status_api": 300              # 5 minutos
}
```

### Loop Principal

```python
import asyncio

async def main_loop():
    """
    Loop principal de monitoramento
    """
    while True:
        try:
            # 1. Buscar jogos ao vivo das ligas monitoradas
            jogos_vivos = await buscar_jogos_vivos()
            
            # 2. Filtrar jogos na janela de monitoramento (min 55-78)
            jogos_monitoraveis = filtrar_janela_monitoramento(jogos_vivos)
            
            # 3. Para cada jogo, buscar dados e avaliar
            for jogo in jogos_monitoraveis:
                # Buscar dados
                stats = await buscar_estatisticas(jogo.id)
                eventos = await buscar_eventos(jogo.id)
                odds = await buscar_odds(jogo.id)
                
                # Avaliar entrada
                sinal = avaliar_entrada(jogo, stats, eventos, odds)
                
                if sinal:
                    # Verificar se já alertou antes
                    if not ja_alertou(jogo.id):
                        enviar_alerta(sinal)
                        registrar_sinal(sinal)
                        marcar_como_alertado(jogo.id)
                    
                    # Verificar re-avaliação
                    elif deve_reavaliar(jogo.id, sinal):
                        enviar_reavaliacao(sinal)
                        atualizar_registro(jogo.id, sinal)
            
            # 4. Aguardar próximo ciclo
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
            await asyncio.sleep(60)

# Executar
if __name__ == "__main__":
    asyncio.run(main_loop())
```

---

## 🧪 BACKTEST - VALIDAÇÃO HISTÓRICA

### Conceito
Testar a estratégia em dados históricos para validar se há edge real antes de usar dinheiro real.

### Por Que é Crítico?

```
SEM BACKTEST:
- Você está apostando no escuro
- Não sabe taxa de acerto real
- Não sabe ROI esperado
- Não sabe drawdown máximo

COM BACKTEST:
- Valida edge matemático
- Descobre pontos fracos
- Ajusta thresholds
- Mede expectativa real
```

### Processo de Backtest

#### 1. Coletar Dados Históricos

```python
async def coletar_dados_historicos(liga_id, temporada):
    """
    Coleta todos os jogos de uma liga em uma temporada
    """
    jogos = await api.get_fixtures(
        league=liga_id,
        season=temporada
    )
    
    dados_completos = []
    
    for jogo in jogos:
        stats = await api.get_statistics(jogo.id)
        eventos = await api.get_events(jogo.id)
        
        # Reconstruir timeline minuto a minuto
        timeline = reconstruir_timeline(stats, eventos)
        
        dados_completos.append({
            "jogo_id": jogo.id,
            "jogo": jogo.descricao,
            "timeline": timeline,
            "resultado_final": jogo.escanteios_total
        })
    
    return dados_completos
```

#### 2. Simular Estratégia

```python
def simular_estrategia(dados_historicos):
    """
    Aplica a estratégia em cada minuto de cada jogo
    """
    resultados = []
    
    for jogo in dados_historicos:
        for minuto in range(55, 79):
            # Estado do jogo naquele minuto
            estado = jogo.timeline[minuto]
            
            # Aplicar lógica da estratégia
            sinal = avaliar_entrada_backtest(estado)
            
            if sinal:
                # Verificar resultado
                escanteios_final = jogo.resultado_final
                linha = sinal["linha"]
                
                if escanteios_final > linha:
                    resultado = "GREEN"
                    roi = (sinal["odd"] - 1) * 100
                else:
                    resultado = "RED"
                    roi = -100
                
                resultados.append({
                    "jogo": jogo.jogo,
                    "minuto_entrada": minuto,
                    "linha": linha,
                    "odd": sinal["odd"],
                    "edge": sinal["edge"],
                    "score": sinal["score"],
                    "resultado": resultado,
                    "roi": roi
                })
                
                break  # Primeira entrada apenas
    
    return resultados
```

#### 3. Analisar Resultados

```python
def analisar_backtest(resultados):
    """
    Calcula métricas do backtest
    """
    total_entradas = len(resultados)
    greens = sum(1 for r in resultados if r["resultado"] == "GREEN")
    reds = total_entradas - greens
    
    winrate = (greens / total_entradas) * 100
    
    roi_total = sum(r["roi"] for r in resultados)
    roi_medio = roi_total / total_entradas
    
    odd_media = sum(r["odd"] for r in resultados) / total_entradas
    
    # Drawdown
    bankroll = 100
    historico_bankroll = [bankroll]
    
    for r in resultados:
        if r["resultado"] == "GREEN":
            bankroll += (r["odd"] - 1)
        else:
            bankroll -= 1
        historico_bankroll.append(bankroll)
    
    max_drawdown = max(
        (max(historico_bankroll[:i]) - v) / max(historico_bankroll[:i]) * 100
        for i, v in enumerate(historico_bankroll) if i > 0
    )
    
    return {
        "total_entradas": total_entradas,
        "greens": greens,
        "reds": reds,
        "winrate": winrate,
        "roi_total": roi_total,
        "roi_medio": roi_medio,
        "odd_media": odd_media,
        "max_drawdown": max_drawdown,
        "bankroll_final": bankroll
    }
```

### Métricas de Sucesso

```
BACKTEST BOM:
✅ Winrate > 55% (para odds ~1.75)
✅ ROI médio > 5%
✅ Drawdown máximo < 20%
✅ Consistência entre ligas
✅ Consistência entre temporadas

BACKTEST RUIM:
❌ Winrate < 50%
❌ ROI negativo ou próximo de 0
❌ Drawdown > 30%
❌ Funciona só em 1 liga
❌ Funcionou só em 1 temporada específica
```

---

## 🛠️ IMPLEMENTAÇÃO - CÓDIGO BASE

### 1. Models (data/models.py)

```python
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class JogoAoVivo:
    id: int
    liga_id: int
    liga_nome: str
    time_casa: str
    time_fora: str
    placar_casa: int
    placar_fora: int
    minuto: int
    escanteios_total: int
    escanteios_casa: int
    escanteios_fora: int
    linha_atual: float
    odd_atual: float
    
    # Estatísticas últimos 10 minutos
    escanteios_ultimos_10min: int = 0
    escanteios_ultimos_5min: int = 0
    ataques_perigosos_ultimos_10min: int = 0
    posse_ultimos_10min: float = 0
    finalizacoes_recentes: int = 0
    
    # Dados históricos
    media_historica_combinada: float = 0

@dataclass
class Sinal:
    tipo: str  # 'NORMAL' ou 'PREMIUM'
    jogo: JogoAoVivo
    pressure_score: int
    projecao: float
    edge: float
    timestamp: datetime
    reavalicao: bool = False
```

### 2. Score Engine (engine/score_engine.py)

```python
class PressureScoreEngine:
    """
    Calcula o Pressure Score baseado em múltiplos indicadores
    """
    
    def calcular(self, jogo: JogoAoVivo) -> int:
        score = 0
        
        # Escanteios recentes (maior peso)
        if jogo.escanteios_ultimos_10min >= 2:
            score += 3
        
        if jogo.escanteios_ultimos_5min >= 1:
            score += 1
        
        # Ataques perigosos
        if jogo.ataques_perigosos_ultimos_10min >= 6:
            score += 2
        
        # Contexto do placar
        if self._time_perdendo_por_1(jogo):
            score += 2
        
        # Posse de bola
        if jogo.posse_ultimos_10min > 60:
            score += 1
        
        # Finalizações
        if jogo.finalizacoes_recentes >= 3:
            score += 1
        
        return score
    
    def _time_perdendo_por_1(self, jogo: JogoAoVivo) -> bool:
        diferenca = abs(jogo.placar_casa - jogo.placar_fora)
        return diferenca == 1
```

### 3. Projection Engine (engine/projection_engine.py)

```python
class ProjectionEngine:
    """
    Modelo híbrido de projeção de escanteios
    """
    
    def calcular_projecao(
        self,
        jogo: JogoAoVivo,
        pressure_score: int
    ) -> float:
        # 1. Ritmo base
        ritmo = self._calcular_ritmo_base(
            jogo.escanteios_total,
            jogo.minuto
        )
        
        # 2. Ajuste de pressão
        ajuste_pressao = pressure_score * 0.25
        
        # 3. Ajuste histórico
        ajuste_historico = self._calcular_ajuste_historico(
            jogo.media_historica_combinada
        )
        
        # 4. Projeção final
        projecao = ritmo + ajuste_pressao + ajuste_historico
        
        return round(projecao, 2)
    
    def _calcular_ritmo_base(
        self,
        escanteios: int,
        minuto: int
    ) -> float:
        if minuto == 0:
            return 0
        
        ritmo_por_minuto = escanteios / minuto
        projecao_95 = ritmo_por_minuto * 95
        
        return projecao_95
    
    def _calcular_ajuste_historico(
        self,
        media_historica: float
    ) -> float:
        if media_historica > 10.5:
            return 0.5
        return 0
```

### 4. Decision Engine (engine/decision_engine.py)

```python
from typing import Optional
from .score_engine import PressureScoreEngine
from .projection_engine import ProjectionEngine
from data.models import JogoAoVivo, Sinal
from datetime import datetime

class DecisionEngine:
    """
    Motor de decisão - Avalia se deve emitir sinal
    """
    
    def __init__(self):
        self.score_engine = PressureScoreEngine()
        self.projection_engine = ProjectionEngine()
    
    def avaliar(self, jogo: JogoAoVivo) -> Optional[Sinal]:
        # 1. Filtros estruturais
        if not self._passou_filtros(jogo):
            return None
        
        # 2. Calcular pressure score
        score = self.score_engine.calcular(jogo)
        
        if score < 8:
            return None
        
        # 3. Calcular projeção
        projecao = self.projection_engine.calcular_projecao(jogo, score)
        
        # 4. Calcular edge
        edge = projecao - jogo.linha_atual
        
        # 5. Verificar condições de entrada
        if score >= 9 and edge >= 2.0:
            return Sinal(
                tipo="PREMIUM",
                jogo=jogo,
                pressure_score=score,
                projecao=projecao,
                edge=edge,
                timestamp=datetime.now()
            )
        
        elif score >= 8 and edge >= 1.3:
            return Sinal(
                tipo="NORMAL",
                jogo=jogo,
                pressure_score=score,
                projecao=projecao,
                edge=edge,
                timestamp=datetime.now()
            )
        
        return None
    
    def _passou_filtros(self, jogo: JogoAoVivo) -> bool:
        # Janela de minutos
        if not (55 <= jogo.minuto <= 78):
            return False
        
        # Diferença de gols
        dif_gols = abs(jogo.placar_casa - jogo.placar_fora)
        if dif_gols > 2:
            return False
        
        # Mínimo de escanteios
        if jogo.escanteios_total < 5:
            return False
        
        # Escanteio recente
        if jogo.escanteios_ultimos_5min < 1:
            return False
        
        # Jogo morno
        if (jogo.placar_casa == 0 and 
            jogo.placar_fora == 0 and 
            jogo.minuto >= 60 and
            jogo.escanteios_total < 7):
            return False
        
        # Bloqueio jogo morto
        if jogo.escanteios_casa == 0 or jogo.escanteios_fora == 0:
            # Se algum time teve 0 escanteios no 1º tempo
            if jogo.minuto > 45:
                return False
        
        return True
```

### 5. API Client (data/api_client.py)

```python
import aiohttp
import asyncio
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class APIFootballClient:
    """
    Cliente para API-Football v3
    """
    
    BASE_URL = "https://v3.football.api-sports.io"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.requests_today = 0
        self.limit_daily = 7500
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    'x-apisports-key': self.api_key
                }
            )
        return self.session
    
    async def _request(self, endpoint: str, params: Dict = None) -> Dict:
        session = await self._get_session()
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            async with session.get(url, params=params) as response:
                data = await response.json()
                self.requests_today += 1
                
                logger.info(
                    f"API Request: {endpoint} | "
                    f"Requests today: {self.requests_today}/{self.limit_daily}"
                )
                
                return data
        
        except Exception as e:
            logger.error(f"API Error: {endpoint} - {e}")
            raise
    
    async def get_live_fixtures(self, league_ids: List[int]) -> List[Dict]:
        """
        Busca jogos ao vivo de ligas específicas
        """
        all_fixtures = []
        
        for league_id in league_ids:
            data = await self._request(
                "fixtures",
                params={"live": "all", "league": league_id}
            )
            all_fixtures.extend(data.get("response", []))
        
        return all_fixtures
    
    async def get_statistics(self, fixture_id: int) -> Dict:
        """
        Busca estatísticas detalhadas de um jogo
        """
        data = await self._request(
            "fixtures/statistics",
            params={"fixture": fixture_id}
        )
        return data.get("response", [])
    
    async def get_events(self, fixture_id: int) -> List[Dict]:
        """
        Busca eventos de um jogo
        """
        data = await self._request(
            "fixtures/events",
            params={"fixture": fixture_id}
        )
        return data.get("response", [])
    
    async def get_odds(self, fixture_id: int) -> Dict:
        """
        Busca odds de um jogo
        """
        data = await self._request(
            "odds",
            params={"fixture": fixture_id}
        )
        return data.get("response", [])
    
    async def check_status(self) -> Dict:
        """
        Verifica status da conta (NÃO conta como requisição)
        """
        data = await self._request("status")
        
        account_info = data.get("response", {})
        self.requests_today = account_info.get("requests", {}).get("current", 0)
        
        return account_info
    
    async def close(self):
        if self.session:
            await self.session.close()
```

---

## 📊 MÉTRICAS E KPIs

### Métricas de Performance

```python
class MetricsCalculator:
    """
    Calcula métricas de performance da estratégia
    """
    
    @staticmethod
    def calcular_metricas(sinais: List[Dict]) -> Dict:
        total = len(sinais)
        
        if total == 0:
            return {}
        
        greens = sum(1 for s in sinais if s["resultado"] == "GREEN")
        reds = total - greens
        
        winrate = (greens / total) * 100
        
        roi_list = [s["roi"] for s in sinais]
        roi_total = sum(roi_list)
        roi_medio = roi_total / total
        
        # Odd média
        odd_media = sum(s["odd"] for s in sinais) / total
        
        # Métricas por tipo de sinal
        normais = [s for s in sinais if s["tipo"] == "NORMAL"]
        premiums = [s for s in sinais if s["tipo"] == "PREMIUM"]
        
        winrate_normal = (
            sum(1 for s in normais if s["resultado"] == "GREEN") / len(normais) * 100
            if normais else 0
        )
        
        winrate_premium = (
            sum(1 for s in premiums if s["resultado"] == "GREEN") / len(premiums) * 100
            if premiums else 0
        )
        
        # Por liga
        metricas_liga = {}
        for liga in set(s["liga"] for s in sinais):
            sinais_liga = [s for s in sinais if s["liga"] == liga]
            greens_liga = sum(1 for s in sinais_liga if s["resultado"] == "GREEN")
            
            metricas_liga[liga] = {
                "total": len(sinais_liga),
                "greens": greens_liga,
                "winrate": greens_liga / len(sinais_liga) * 100,
                "roi": sum(s["roi"] for s in sinais_liga) / len(sinais_liga)
            }
        
        return {
            "total_sinais": total,
            "greens": greens,
            "reds": reds,
            "winrate": winrate,
            "roi_total": roi_total,
            "roi_medio": roi_medio,
            "odd_media": odd_media,
            "winrate_normal": winrate_normal,
            "winrate_premium": winrate_premium,
            "por_liga": metricas_liga
        }
```

---

## 🚀 PROMPT COMPLETO PARA CLAUDE CLI NO CURSOR

```markdown
You are a senior Python quantitative systems engineer.

We are building a production-grade football live betting signal engine called:
**CORNER PRESSURE ELITE SYSTEM**

This is NOT a toy project.
This is a structured semi-quantitative edge detection engine focused on Over Corners live betting.

Your job:
Design and start implementing a modular, scalable, production-ready Python system.

## 🎯 SYSTEM OBJECTIVE

Build a fully mechanical live monitoring engine that:
- Monitors selected leagues
- Calculates pressure score
- Calculates hybrid projection
- Detects statistical edge
- Sends structured webhook alerts (WhatsApp integration ready)
- Logs only entry signals
- Allows re-evaluation alerts without additional stake suggestion

NO automated betting execution.
Human executes manually.

## 🏆 TARGET LEAGUES

- Premier League (ID: 39)
- Bundesliga (ID: 78)
- Brazilian Serie A (ID: 71)
- Brazilian Serie B (ID: 72)

System must allow league ID configuration.

## 🧠 STRATEGIC MODEL

**Monitoring Window:**
Minute 55–78 only.

**Structural Filters:**
- Goal difference ≤ 2
- Minimum 5 total corners
- At least 1 corner in last 5 minutes
- If score 0–0 and minute ≥ 60 → must have ≥ 7 corners
- Block match if any team had 0 corners in first half

## 📊 PRESSURE SCORE

Minimum required: ≥ 8

**Scoring:**
- +3 → 2+ corners in last 10 minutes
- +2 → 6+ dangerous attacks last 10 minutes
- +2 → Team losing by 1 goal
- +1 → Possession > 60%
- +1 → Recent shots on target

**Premium Signal:**
Score ≥ 9

## 📈 PROJECTION MODEL (HYBRID)

**Base Rhythm:**
```
(current_corners / current_minute) × 95
```

**Pressure Adjustment:**
```
score × 0.25
```

**Historical Adjustment:**
```
+0.5 if combined last 10 match average > 10.5
```

**Final Projection:**
```
rhythm + pressure_adjustment + historical_adjustment
```

## 🎯 ENTRY CONDITIONS

**Normal Signal:**
- Projection ≥ Line + 1.3
- Score ≥ 8

**Premium Signal:**
- Projection ≥ Line + 2.0
- Score ≥ 9

## 🔄 RE-EVALUATION RULE

System continues monitoring after first alert.

Re-evaluation allowed if:
- Line changes
- OR Edge increases ≥ 0.7
- OR Score increases ≥ 1

Minimum 3 minutes between alerts.
Re-evaluation does NOT suggest additional stake.

## 💰 RISK MANAGEMENT

- Fixed stake: 1 unit (informational only)
- No stacking
- No martingale
- No daily cap

## 🧱 ARCHITECTURE REQUIREMENTS

Python 3.11+

**Modular structure:**
```
project/
│
├── config.py
├── main.py
├── data/
│   └── api_client.py
├── engine/
│   ├── score_engine.py
│   ├── projection_engine.py
│   ├── decision_engine.py
│   └── state_manager.py
├── notifier/
│   └── webhook_sender.py
├── storage/
│   └── logger.py
└── utils/
```

**Use:**
- Async architecture (asyncio)
- Clear typing
- Dataclasses or Pydantic models
- Separation of concerns
- Clean dependency injection

## 🔔 ALERT FORMAT

**Normal:**
```
🟡 OVER ESCANTEIOS – NORMAL

League: [name]
Match: [teams]
Minute: [min]
Score: [score]

Corners: [current]
Line: [line]
Projection: [proj]
Edge: [edge]

Pressure Score: [score]/10
Odd: [odd]
Stake: 1u
```

**Premium:**
```
🔥 OVER ESCANTEIOS – PREMIUM
[same structure]
```

**Re-evaluation:**
```
🔄 RE-EVALUATION – SCENARIO IMPROVED
[no stake suggestion]
```

## 🗄 LOGGING

Store only entries.

**Fields:**
- timestamp
- league
- match_id
- minute
- score
- total_corners
- line
- odd
- projection
- edge
- pressure_score
- signal_type

Use SQLite initially.

## 🔌 API INTEGRATION

Design abstraction layer for API-Football v3.
System must be easily replaceable with other data providers.
Implement rate limit control.
Polling interval: 60 seconds.

## 🎯 DELIVERABLE

Start by:
1. Designing the project structure
2. Creating core data models
3. Building projection engine
4. Building pressure score engine
5. Building decision engine
6. Creating main event loop

Write production-quality code.
No pseudo-code.
No placeholders.
Professional logging.
```

---

## 📚 REFERÊNCIAS E RECURSOS

### APIs Utilizadas
- **API-Football v3:** https://www.api-football.com/documentation-v3
- **API-Sports Account:** Gerenciamento de chave e limites

### Conceitos Estatísticos
- **Distribuição de Poisson:** Modelagem de eventos raros (escanteios)
- **Probabilidade Implícita:** Conversão de odds em probabilidade
- **Expected Value (EV):** Cálculo de valor esperado
- **Edge:** Vantagem estatística sobre o mercado

### Frameworks e Bibliotecas Python
- **asyncio:** Programação assíncrona
- **aiohttp:** Cliente HTTP assíncrono
- **Pydantic:** Validação de dados
- **SQLAlchemy:** ORM para banco de dados
- **APScheduler:** Agendamento de tarefas
- **python-telegram-bot:** Integração com Telegram (alternativa WhatsApp)

---

## ⚠️ AVISOS IMPORTANTES

### Legalidade e Ética
1. Sistema é para **análise estatística** apenas
2. Não automatiza apostas
3. Não viola termos de uso de casas de apostas
4. Não garante lucro
5. Usuário é responsável por suas decisões

### Riscos
1. **Perda de capital:** Apostas sempre envolvem risco
2. **API dependência:** Sistema depende da API-Football
3. **Mudanças de mercado:** Casas podem ajustar linhas rapidamente
4. **Overfitting:** Backtest pode não refletir futuro

### Recomendações
1. Sempre começar com stake baixo
2. Validar com backtest extensivo (200+ jogos)
3. Nunca apostar mais do que pode perder
4. Manter disciplina emocional
5. Revisar e ajustar constantemente

---

## 🔮 ROADMAP DE EVOLUÇÃO

### Fase 1: MVP (2-3 semanas)
- [x] Estrutura base do projeto
- [x] Integração com API-Football
- [x] Pressure Score Engine
- [x] Projection Engine
- [x] Decision Engine
- [x] Sistema de alertas básico
- [x] Logging de sinais

### Fase 2: Validação (1-2 meses)
- [ ] Coleta de 200+ sinais reais
- [ ] Análise de ROI
- [ ] Identificar pontos fracos
- [ ] Ajuste de thresholds
- [ ] Otimização de consumo de API

### Fase 3: Refinamento (Contínuo)
- [ ] Machine Learning para peso de pressão
- [ ] Modelo de regressão para projeção
- [ ] Análise por árbitro
- [ ] Análise por estádio
- [ ] Dashboard web para visualização

### Fase 4: Expansão (Futuro)
- [ ] Mais ligas
- [ ] Outros mercados (gols, cartões)
- [ ] API própria para venda de sinais
- [ ] Integração com mais casas de apostas
- [ ] Mobile app

---

## 📞 SUPORTE E CONTATO

**Documentação gerada em:** 14/02/2026  
**Versão do Sistema:** 1.0.0  
**Status:** Em desenvolvimento

---

*Este documento é um guia técnico completo. Use-o como referência para implementação no Claude CLI do Cursor. Boa sorte!* 🚀
