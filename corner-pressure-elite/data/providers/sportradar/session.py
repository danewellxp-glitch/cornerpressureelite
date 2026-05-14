"""Holder do token Sportradar com refresh sob demanda e lock async.

Formato do token (master §3.2):
    T=exp=<unix>~acl=/*~data=<base64_json>~hmac=<sha256>

TTL observado ~2h. Caller injeta o token via `set_token` (em testes) ou
via `token_refresher` callback (em produção, vindo do `BetanoSession`
da Fase B — ainda não disponível, fallback é env var
`SPORTRADAR_TOKEN`).
"""
import asyncio
import logging
import re
import time
from typing import Awaitable, Callable, Optional

log = logging.getLogger("cpes.sportradar.session")

TOKEN_EXP_RE = re.compile(r"T=exp=(\d+)~")
TOKEN_REFRESH_MARGIN_S = 300


class SportradarSession:
    """Mantém o token em memória, detecta expiração e serializa refresh."""

    def __init__(
        self,
        token_refresher: Optional[Callable[[], Awaitable[str]]] = None,
    ):
        self._token: Optional[str] = None
        self._exp: int = 0
        self._refresh_lock = asyncio.Lock()
        self._token_refresher = token_refresher

    def set_token(self, token_query: str) -> None:
        """Recebe o token completo (`T=exp=...~hmac=...`) e parseia `exp`.

        Levanta `ValueError` em formato inválido — é fronteira de input,
        try/except permitido (CLAUDE.md §7).
        """
        m = TOKEN_EXP_RE.search(token_query)
        if not m:
            raise ValueError(
                f"Token Sportradar sem exp= reconhecível: "
                f"{token_query[:60]}..."
            )
        self._token = token_query
        self._exp = int(m.group(1))
        log.info(
            "sportradar.session.token_set ttl_s=%d prefix=%s",
            max(0, self._exp - int(time.time())),
            token_query[:15],
        )

    @property
    def token(self) -> Optional[str]:
        return self._token

    @property
    def exp(self) -> int:
        return self._exp

    def is_expired(self) -> bool:
        """True se está dentro da margem de refresh (5min antes do exp)."""
        return time.time() >= self._exp - TOKEN_REFRESH_MARGIN_S

    def ttl_remaining(self) -> int:
        """Segundos até `exp`. Negativo se já expirou."""
        return self._exp - int(time.time())

    async def get_or_refresh(self) -> str:
        """Retorna token válido. Se expirado, chama o refresher (1x por
        contenção via lock async)."""
        if not self.is_expired() and self._token:
            return self._token
        async with self._refresh_lock:
            if not self.is_expired() and self._token:
                return self._token
            if not self._token_refresher:
                raise RuntimeError(
                    "Token Sportradar expirado e nenhum token_refresher "
                    "configurado — configure SPORTRADAR_TOKEN ou injete um "
                    "refresher callback"
                )
            log.info("sportradar.session.refresh.start")
            new = await self._token_refresher()
            self.set_token(new)
            log.info("sportradar.session.refresh.done")
            assert self._token is not None
            return self._token
