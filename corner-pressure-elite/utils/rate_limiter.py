import asyncio
import time
import logging

logger = logging.getLogger("CPES.RateLimiter")


class RateLimiter:
    """Controle de rate limit para a API-Football."""

    def __init__(self, max_requests_per_day: int, max_requests_per_minute: int = 10):
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
        if self.requests_today >= self.max_daily:
            return False
        if len(self.minute_requests) >= self.max_per_minute:
            return False
        return True

    def remaining_daily(self) -> int:
        return max(0, self.max_daily - self.requests_today)

    async def wait_if_needed(self):
        self._clean_minute_window()

        if self.requests_today >= self.max_daily:
            logger.warning(
                f"Limite diario atingido: {self.requests_today}/{self.max_daily}"
            )
            raise RuntimeError("Limite diario de requisicoes atingido")

        if len(self.minute_requests) >= self.max_per_minute:
            wait_time = 60 - (time.time() - self.minute_requests[0])
            if wait_time > 0:
                logger.info(f"Rate limit por minuto - aguardando {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

    def record_request(self):
        self.requests_today += 1
        self.minute_requests.append(time.time())

    def sync_from_api(self, current_requests: int):
        """Sincroniza contagem com o valor real da API."""
        self.requests_today = current_requests
        logger.info(
            f"Rate limiter sincronizado: {self.requests_today}/{self.max_daily}"
        )
