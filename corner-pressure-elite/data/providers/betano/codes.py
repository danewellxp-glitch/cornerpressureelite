"""Catálogo de market codes da Betano — mantém legibilidade no código.

Codes derivados da captura `.mitm` de 2026-05-12 (ver
`docs/sprints/2026-05-12-betano-discovery-master.md` §3).
"""

# ---------- Escanteios ----------
MARKET_CODES_CORNERS_MAIN = "CNOU"          # Escanteios Mais/Menos (principal)
MARKET_CODES_CORNERS_NEXT_TEAM = "NCNT"     # Próxima equipe a cobrar escanteio

# ---------- Cartões ----------
MARKET_CODES_CARDS_MAIN = "TCOU"            # Total de Cartões Mais/Menos
MARKET_CODES_CARDS_RED = "RCOU"             # Total de Cartões Vermelhos
MARKET_CODES_CARDS_HOME_RED = "HRED"        # Casa cartão vermelho
MARKET_CODES_CARDS_AWAY_RED = "ARED"        # Fora cartão vermelho
MARKET_CODES_CARDS_FIRST_HALF_RED = "1RED"  # Cartão vermelho 1º tempo
MARKET_CODES_CARDS_PLAYER_GETS = "PTRC"     # Jogador receber cartão

# ---------- Resultado ----------
MARKET_CODES_RESULT_FINAL = "MRES"          # Resultado Final
MARKET_CODES_RESULT_DOUBLE = "DBLC"         # Chance Dupla
MARKET_CODES_RESULT_DRAW_NO_BET = "DNOB"    # Empate Anula

# ---------- Gols ----------
MARKET_CODES_GOALS_TOTAL = "HCTG"           # Total de Gols Mais/Menos
MARKET_CODES_GOALS_BTTS = "BTSC"            # Ambas Marcam

# Conjuntos úteis
CORNERS_CODES = {
    MARKET_CODES_CORNERS_MAIN,
    MARKET_CODES_CORNERS_NEXT_TEAM,
}
CARDS_CODES = {
    MARKET_CODES_CARDS_MAIN,
    MARKET_CODES_CARDS_RED,
    MARKET_CODES_CARDS_HOME_RED,
    MARKET_CODES_CARDS_AWAY_RED,
    MARKET_CODES_CARDS_FIRST_HALF_RED,
}
