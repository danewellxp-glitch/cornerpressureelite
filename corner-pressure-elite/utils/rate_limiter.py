import asyncio
import time
import logging

logger = logging.getLogger("CPES.RateLimiter")


class RateLimiter:
    """Controle de rate limit para a API-Football.
    
    DEBUG FASE 5: Instrumentado com logs detalhados.
    """

    def __init__(self, max_requests_per_day: int, max_requests_per_minute: int = 30):
        self.max_daily = max_requests_per_day
        self.max_per_minute = max_requests_per_minute
        self.requests_today = 0
        self.minute_requests: list[float] = []
        self._day_start = time.time()

    def _clean_minute_window(self):
        now = time.time()
        self.minute_requests = [t for t in self.minute_requests if now - t < 60]

    def can_request(self) -> bool:
        self._clean_minute_window()
        
        daily_remaining = self.max_daily - self.requests_today
        minute_count = len(self.minute_requests)
        
        # DEBUG: Log status
        logger.debug(f"[DEBUG FASE 5] Rate check: {self.requests_today}/{self.max_daily} daily | {minute_count}/{self.max_per_minute} min")
        
        if self.requests_today >= self.max_daily:
            logger.warning(
                f"[DEBUG FASE 5] ⚠ BLOQUEADO: Limite diario atingido ({self.requests_today}/{self.max_daily})"
            )
            return False
            
        if len(self.minute_requests) >= self.max_per_minute:
            logger.warning(
                f"[DEBUG FASE 5] ⚠ BLOQUEADO: Limite por minuto atingido ({minute_count}/{self.max_per_minute})"
            )
            return False
        
        return True

    def remaining_daily(self) -> int:
        return max(0, self.max_daily - self.requests_today)

    async def wait_if_needed(self):
        self._clean_minute_window()

        if self.requests_today >= self.max_daily:
            logger.critical(
                f"[DEBUG FASE 5] 🔴 ALERTA CRÍTICO: Limite diario total atingido ({self.requests_today}/{self.max_daily})"
            )
            raise RuntimeError("Limite diario de requisicoes atingido")

        if len(self.minute_requests) >= self.max_per_minute:
            wait_time = 60 - (time.time() - self.minute_requests[0])
            if wait_time > 0:
                logger.info(
                    f"[DEBUG FASE 5] Rate limit por minuto - aguardando {wait_time:.1f}s "
                    f"({len(self.minute_requests)}/{self.max_per_minute})"
                )
                await asyncio.sleep(wait_time)

    def record_request(self):
        self.requests_today += 1
        self.minute_requests.append(time.time())
        
        remaining = self.remaining_daily()
        logger.info(
            f"[DEBUG FASE 5] Requisição registrada: {self.requests_today}/{self.max_daily} |"
            f" {remaining} restantes"
        )

    def sync_from_api(self, current_requests: int, limit_day: int = 0):
        """Sincroniza contagem e limite diário com os valores reais da API."""
        old_count = self.requests_today
        self.requests_today = current_requests

        # Sincronizar limite diário se a API informou um valor válido
        if limit_day > 0 and limit_day != self.max_daily:
            old_limit = self.max_daily
            self.max_daily = limit_day
            logger.info(
                f"Rate limiter: limite diário atualizado {old_limit} → {limit_day}"
            )

        logger.info(
            f"Rate limiter sincronizado: {old_count} → {self.requests_today}/{self.max_daily}"
        )

        if current_requests >= self.max_daily:
            logger.critical(
                f"🔴 ALERTA: API informou limite atingido ({current_requests}/{self.max_daily})"
            )

