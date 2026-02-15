"""
CPES Monitor - Dashboard em tempo real no terminal.
Mostra status do sistema, jogos ao vivo, sinais e performance.

Uso: python monitor.py
"""

import asyncio
import os
import sys
import time
from datetime import datetime

# Forcar UTF-8 no Windows
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    API_DAILY_LIMIT,
    LIGA_IDS,
    LIGAS_MONITORADAS,
    MINUTO_INICIO,
    MINUTO_FIM,
    JANELA_ANTECIPADA_INICIO,
    POLLING_INTERVAL,
    DB_PATH,
    WHATSAPP_GROUP_ID,
    WHATSAPP_ADMIN,
    WAHA_URL,
    WAHA_SESSION_NAME,
    WAHA_API_KEY,
)
from data_reader import (
    get_db_stats,
    get_recent_signals,
    parse_log_for_status,
    read_last_lines,
    get_log_file,
    get_live_state,
)

# Cores ANSI
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def colorize_log_line(line):
    """Adiciona cores a linha de log."""
    line = line.rstrip()
    if "ERROR" in line:
        return f"{RED}{line}{RESET}"
    if "WARNING" in line:
        return f"{YELLOW}{line}{RESET}"
    if "Sinal" in line and "enviado" in line:
        return f"{GREEN}{BOLD}{line}{RESET}"
    if "Ciclo #" in line:
        return f"{CYAN}{line}{RESET}"
    if "Encontrados" in line:
        return f"{MAGENTA}{line}{RESET}"
    if "Analisando" in line:
        return f"{GREEN}{line}{RESET}"
    return f"{DIM}{line}{RESET}"


def render_dashboard():
    """Renderiza o dashboard completo."""
    clear_screen()

    log_file = get_log_file()
    log_lines = read_last_lines(log_file, 50)
    status = parse_log_for_status(log_lines)
    stats = get_db_stats()
    recent = get_recent_signals(5)

    now = datetime.now().strftime("%H:%M:%S")
    ligas = ", ".join([l["nome"] for l in LIGAS_MONITORADAS])

    # Header
    print(f"{BG_BLUE}{BOLD}{WHITE}")
    print(f"{'':=<80}")
    print(f"  CORNER PRESSURE ELITE SYSTEM - MONITOR v1.0")
    print(f"  {now}  |  Ciclo #{status['ciclo']}  |  Polling: {POLLING_INTERVAL}s")
    print(f"{'':=<80}")
    print(f"{RESET}")

    # Status principal
    print(f"\n{BOLD}{CYAN}  SISTEMA{RESET}")
    print(f"  {'-'*70}")

    # API status
    api_pct = 0
    try:
        api_pct = int(status["api_usado"]) / int(status["api_limite"]) * 100
    except (ValueError, ZeroDivisionError):
        pass

    api_color = GREEN if api_pct < 50 else (YELLOW if api_pct < 80 else RED)
    print(f"  API Football   : {api_color}{status['api_usado']}/{status['api_limite']} requisicoes ({api_pct:.1f}%){RESET}")
    print(f"  Janela         : 0-30:5m | 31-50:3m (7+esc=1m) | 50-90:1m | 90+:30s")
    print(f"  Jogos ao vivo  : {BOLD}{status['jogos_ao_vivo']}{RESET}")
    print(f"  Na janela      : {BOLD}{status['jogos_na_janela']}{RESET}")
    print(f"  Ultimo update  : {status['ultimo_update']}")

    if status["status_msg"]:
        print(f"  Status         : {YELLOW}{status['status_msg']}{RESET}")

    # Economia de API (polling adaptativo)
    try:
        live = get_live_state()
        ps = live.get("polling_stats", {})
        if ps:
            econ = ps.get("economia_pct", 0)
            mon = ps.get("jogos_monitorados", 0)
            ana = ps.get("jogos_analisando", 0)
            print(f"  Economia API   : {ana}/{mon} processados ({econ:.0f}% economizado)")
    except Exception:
        pass

    # Ligas
    print(f"\n{BOLD}{CYAN}  LIGAS MONITORADAS{RESET}")
    print(f"  {'-'*70}")
    for liga in LIGAS_MONITORADAS:
        print(f"  {DIM}[{liga['id']}]{RESET} {liga['nome']} ({liga['pais']}) - Media: {liga['media_esperada']}")

    # Performance
    print(f"\n{BOLD}{CYAN}  PERFORMANCE{RESET}")
    print(f"  {'-'*70}")

    if stats["total"] > 0:
        wr_color = GREEN if stats["winrate"] >= 60 else (YELLOW if stats["winrate"] >= 50 else RED)
        roi_color = GREEN if stats["roi_total"] > 0 else RED

        print(f"  Total sinais   : {BOLD}{stats['total']}{RESET}")
        print(f"  Greens         : {GREEN}{stats['greens']}{RESET}")
        print(f"  Reds           : {RED}{stats['reds']}{RESET}")
        print(f"  Pendentes      : {YELLOW}{stats['pendentes']}{RESET}")
        print(f"  Winrate        : {wr_color}{BOLD}{stats['winrate']}%{RESET}")
        print(f"  ROI Total      : {roi_color}{stats['roi_total']}u{RESET}")
    else:
        print(f"  {DIM}Nenhum sinal registrado ainda{RESET}")

    # Sinais recentes
    if recent:
        print(f"\n{BOLD}{CYAN}  SINAIS RECENTES{RESET}")
        print(f"  {'-'*70}")
        print(f"  {'Hora':<12} {'Jogo':<30} {'Tipo':<9} {'Score':>5} {'Edge':>6} {'Res':>5}")
        print(f"  {'-'*70}")

        for row in recent:
            ts, desc, tipo, score, proj, edge, linha, resultado = row
            ts_short = ts[11:19] if len(ts) > 19 else ts

            if resultado == "GREEN":
                res_str = f"{GREEN}GREEN{RESET}"
            elif resultado == "RED":
                res_str = f"{RED}RED{RESET}"
            else:
                res_str = f"{YELLOW}  -  {RESET}"

            tipo_color = MAGENTA if tipo == "PREMIUM" else WHITE
            print(f"  {ts_short:<12} {desc[:28]:<30} {tipo_color}{tipo:<9}{RESET} {score:>5} {edge:>+5.2f} {res_str}")

    # Log recente
    print(f"\n{BOLD}{CYAN}  LOG (ULTIMAS LINHAS){RESET}")
    print(f"  {'-'*70}")

    display_lines = log_lines[-12:]
    for line in display_lines:
        # Comprimir a linha para caber no terminal
        clean = line.strip()
        if len(clean) > 78:
            # Remover o timestamp date parte para economizar espaco
            if "|" in clean:
                parts = clean.split("|", 1)
                time_part = parts[0].strip()
                if " " in time_part:
                    time_part = time_part.split(" ", 1)[1]  # so a hora
                rest = parts[1] if len(parts) > 1 else ""
                clean = f"{time_part} |{rest}"
            if len(clean) > 78:
                clean = clean[:75] + "..."
        print(f"  {colorize_log_line(clean)}")

    # Footer
    print(f"\n{DIM}  [R] Refresh  [S] Enviar status via WhatsApp  [Q] Sair  [Auto: 10s]{RESET}")
    print()


async def send_whatsapp_status():
    """Envia status atual via WhatsApp para admin e updates."""
    from notifier.whatsapp_client import WhatsAppClient, WAHAConfig

    try:
        config = WAHAConfig(
            base_url=WAHA_URL,
            session_name=WAHA_SESSION_NAME,
            api_key=WAHA_API_KEY or None,
        )

        stats = get_db_stats()
        log_lines = read_last_lines(get_log_file(), 50)
        status = parse_log_for_status(log_lines)
        now = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"\U0001f4ca *CPES MONITOR - STATUS*\n"
            f"\n"
            f"\u23f0 {now}\n"
            f"\U0001f504 Ciclo: #{status['ciclo']}\n"
            f"\U0001f4e1 API: {status['api_usado']}/{status['api_limite']}\n"
            f"\u26bd Jogos ao vivo: {status['jogos_ao_vivo']}\n"
            f"\U0001f3af Na janela ({MINUTO_INICIO}'-{MINUTO_FIM}'): {status['jogos_na_janela']}\n"
            f"\n"
            f"\U0001f4c8 *SINAIS:*\n"
            f"Total: {stats['total']} | "
            f"\u2705 {stats['greens']} | "
            f"\u274c {stats['reds']} | "
            f"WR: {stats['winrate']}%\n"
            f"\U0001f4b0 ROI: {stats['roi_total']}u"
        )

        async with WhatsAppClient(config) as client:
            # Enviar para admin
            if WHATSAPP_ADMIN:
                admin_id = WhatsAppClient.format_chat_id(WHATSAPP_ADMIN)
                await client.send_text(admin_id, msg)
                print(f"  {GREEN}Status enviado para admin{RESET}")

            # Enviar para updates
            updates_num = os.getenv("WHATSAPP_UPDATES", "")
            if updates_num:
                updates_id = WhatsAppClient.format_chat_id(updates_num)
                await client.send_text(updates_id, msg)
                print(f"  {GREEN}Status enviado para updates ({updates_num}){RESET}")

    except Exception as e:
        print(f"  {RED}Erro ao enviar status: {e}{RESET}")


async def main():
    # Ativar cores ANSI no Windows
    if os.name == "nt":
        os.system("color")

    print(f"{BOLD}CPES Monitor iniciando...{RESET}")

    try:
        import msvcrt  # Windows

        while True:
            render_dashboard()

            # Esperar 10 segundos ou ate tecla pressionada
            start = time.time()
            while time.time() - start < 10:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8", errors="ignore").lower()

                    if key == "q":
                        clear_screen()
                        print(f"{BOLD}Monitor encerrado.{RESET}")
                        return

                    if key == "r":
                        break  # Refresh imediato

                    if key == "s":
                        print(f"\n  {YELLOW}Enviando status via WhatsApp...{RESET}")
                        await send_whatsapp_status()
                        await asyncio.sleep(2)
                        break

                await asyncio.sleep(0.1)

    except ImportError:
        # Linux/Mac fallback (sem msvcrt)
        while True:
            render_dashboard()
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
