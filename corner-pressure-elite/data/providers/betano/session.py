"""HTTP session da Betano — versão Fase B (warmup + relogin + proxies).

A Fase A só usava cookies congelados. A Fase B adiciona:
- `warmup()` — abre Chromium headless mobile via Playwright para coletar a
  sequência canônica de cookies (Cloudflare + DataDome + sticky_sb) e o
  `kbversion` corrente.
- `_relogin_if_needed` — em 403/451, refaz o warmup e re-tenta uma vez.
- Rotação de proxies — `proxies: list[str]` opcional; marca proxy como
  "burned" por 30min em 403.
- Helpers `cookie_header()` / `user_agent()` para o WebSocket client.

Operação 100% anônima (sem login). Vide §4.9 do harness Fase B.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from pathlib import Path
from typing import Optional

from curl_cffi.requests import AsyncSession

log = logging.getLogger("cpes.betano.session")


class BetanoBlockedError(Exception):
    """403/451/DataDome bloqueou e warmup também não resolveu."""


class BetanoParseError(ValueError):
    """JSON inesperado / campo obrigatório ausente."""


BETANO_BASE_URL = "https://www.betano.bet.br"

HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.5 Mobile/15E148 Safari/604.1"
    ),
    "Sec-Ch-Ua": '"Google Chrome";v="147","Not.A/Brand";v="8","Chromium";v="147"',
    "Sec-Ch-Ua-Mobile": "?1",
    "Sec-Ch-Ua-Platform": '"iOS"',
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

_PROXY_BURN_SECONDS = 1800  # 30 min


class BetanoSession:
    """Wrapper sobre `curl_cffi.AsyncSession` com warmup + proxies + 403 retry."""

    def __init__(
        self,
        cookies: Optional[dict[str, str]] = None,
        kbversion: str = "3.41.0",
        proxy: Optional[str] = None,
        proxies: Optional[list[str]] = None,
        timeout: float = 15.0,
    ):
        self._cookies: dict[str, str] = dict(cookies or {})
        self._kbversion = kbversion
        self._timeout = timeout
        self._proxies: list[str] = list(proxies or ([proxy] if proxy else []))
        self._proxy_idx = 0
        self._proxy_burned: dict[str, float] = {}
        self._warmup_lock = asyncio.Lock()
        self._http: Optional[AsyncSession] = None
        self._build_http()

    # ---------- construtores auxiliares ----------

    @classmethod
    def from_file(cls, path: str | Path) -> "BetanoSession":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            cookies=data.get("cookies") or {},
            kbversion=data.get("kbversion", "3.41.0"),
            proxies=data.get("proxies") or None,
        )

    # ---------- accessors ----------

    @property
    def kbversion(self) -> str:
        return self._kbversion

    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._cookies)

    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    def user_agent(self) -> str:
        return HEADERS_BASE["User-Agent"]

    # ---------- proxies ----------

    def _now(self) -> float:
        return time.time()

    def _next_proxy(self) -> Optional[str]:
        if not self._proxies:
            return None
        now = self._now()
        self._proxy_burned = {p: until for p, until in self._proxy_burned.items() if until > now}
        candidates = [p for p in self._proxies if p not in self._proxy_burned]
        if not candidates:
            log.warning("betano.proxy.all_burned — usando o de menor TTL")
            return min(self._proxy_burned, key=self._proxy_burned.get) if self._proxy_burned else None
        p = candidates[self._proxy_idx % len(candidates)]
        self._proxy_idx += 1
        return p

    def _proxy_dict(self) -> Optional[dict]:
        p = self._next_proxy()
        return {"http": p, "https": p} if p else None

    def _burn_current_proxy(self, proxy_dict: Optional[dict]) -> None:
        if not proxy_dict:
            return
        p = proxy_dict.get("https") or proxy_dict.get("http")
        if p:
            self._proxy_burned[p] = self._now() + _PROXY_BURN_SECONDS
            log.warning("betano.proxy.burned proxy=%s for %ds", p, _PROXY_BURN_SECONDS)

    # ---------- http ----------

    def _build_http(self) -> None:
        self._http = AsyncSession(
            # Match com UA iPhone Safari iOS 18.5 em HEADERS_BASE. curl_cffi não
            # expõe 18_5; 18_4 é o mais próximo. chrome131 anterior batia TLS de
            # desktop com UA mobile, o que ativava o gate do Cloudflare (403).
            impersonate="safari184_ios",
            cookies=self._cookies,
            proxies=self._proxy_dict(),
            timeout=self._timeout,
        )

    def _headers(self, referer: str) -> dict[str, str]:
        return {**HEADERS_BASE, "Referer": referer, "x-kbversion": self._kbversion}

    async def get_json(
        self,
        path: str,
        referer: Optional[str] = None,
        max_attempts: int = 3,
    ) -> Optional[dict]:
        """GET autenticado retornando dict do JSON.

        - 200: retorna `dict`.
        - 403/451: tenta `warmup()` UMA vez e re-tenta a chamada; se ainda 403,
          levanta `BetanoBlockedError`.
        - 404/410: retorna `None`.
        - 5xx/timeout: retry interno com backoff exponencial.
        """
        url = f"{BETANO_BASE_URL}{path}"
        referer = referer or f"{BETANO_BASE_URL}/"
        relogged = False

        for outer in range(2):  # 0 = inicial, 1 = pós-warmup
            last_status: Optional[int] = None
            for attempt in range(max_attempts):
                start = time.monotonic()
                try:
                    r = await self._http.get(url, headers=self._headers(referer))
                    duration_ms = int((time.monotonic() - start) * 1000)
                    last_status = r.status_code
                    log.info(
                        "betano.get path=%s status=%d attempt=%d duration_ms=%d",
                        path, r.status_code, attempt, duration_ms,
                    )
                    if r.status_code == 200:
                        return r.json()
                    if r.status_code in (403, 451):
                        break  # sai do loop interno para tentar warmup
                    if r.status_code in (404, 410):
                        return None
                except Exception as e:
                    duration_ms = int((time.monotonic() - start) * 1000)
                    log.warning(
                        "betano.error path=%s err=%s attempt=%d duration_ms=%d",
                        path, e, attempt, duration_ms,
                    )
                await asyncio.sleep((2 ** attempt) + random.random() * 0.3)

            if last_status in (403, 451) and not relogged:
                log.warning(
                    "betano.blocked path=%s status=%s — warmup e retry",
                    path, last_status,
                )
                try:
                    await self._relogin_if_needed()
                    relogged = True
                    continue
                except Exception as e:
                    log.error("betano.warmup.failed err=%s", e)
                    raise BetanoBlockedError(
                        f"betano.blocked status={last_status} path={path} (warmup falhou)"
                    ) from e
            if last_status in (403, 451) and relogged:
                raise BetanoBlockedError(
                    f"betano.blocked status={last_status} path={path} (após warmup)"
                )

        log.error("betano.exhausted path=%s", path)
        return None

    async def _relogin_if_needed(self) -> None:
        """Refaz warmup. Mantido como método separado para fácil mock em testes."""
        await self.warmup()

    # ---------- warmup (Playwright) ----------

    async def warmup(self) -> None:
        """Navega via Chromium headless mobile e captura cookies + kbversion.

        Não loga em nenhum momento — apenas home + página de live.
        Atualiza `self._cookies` e `self._kbversion` em sucesso, recria o HTTP
        client com os cookies novos.
        """
        async with self._warmup_lock:
            # Import tardio: playwright só é necessário em warmup real.
            try:
                from playwright.async_api import async_playwright
            except ImportError as e:
                raise RuntimeError(
                    "playwright não instalado. `pip install playwright && playwright install chromium`"
                ) from e

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(
                        user_agent=HEADERS_BASE["User-Agent"],
                        viewport={"width": 393, "height": 852},
                        is_mobile=True,
                        has_touch=True,
                        locale="pt-BR",
                        timezone_id="America/Sao_Paulo",
                    )
                    page = await context.new_page()

                    await page.goto(
                        f"{BETANO_BASE_URL}/",
                        wait_until="load",
                        timeout=30000,
                    )
                    # Betano nunca atinge networkidle (analytics/ws contínuo);
                    # damos folga pra Cloudflare/DataDome assentar cookies.
                    await page.wait_for_timeout(5000)

                    try:
                        await page.click('a[href*="/live"]', timeout=5000)
                        await page.wait_for_timeout(2000)
                    except Exception:
                        log.debug("warmup.click_live_failed — segue sem isso")

                    new_cookies: dict[str, str] = {}
                    for c in await context.cookies():
                        name = c.get("name")
                        value = c.get("value")
                        if name and value is not None:
                            new_cookies[name] = value
                    if new_cookies:
                        self._cookies = new_cookies
                        log.info("betano.warmup.cookies count=%d", len(new_cookies))

                    try:
                        kb = await page.evaluate(
                            "async()=>{"
                            "  const r = await fetch('/api/kb-config/');"
                            "  if (!r.ok) return null;"
                            "  const j = await r.json();"
                            "  return (j && j.releaseConfig) || j;"
                            "}"
                        )
                        if isinstance(kb, dict):
                            latest = kb.get("latestVersion") or kb.get("version")
                            if latest:
                                self._kbversion = str(latest)
                                log.info("betano.warmup.kbversion=%s", self._kbversion)
                    except Exception:
                        log.debug("warmup.kbversion.fetch_failed — mantém valor atual")
                finally:
                    await browser.close()

            if self._http is not None:
                try:
                    await self._http.close()
                except Exception:
                    pass
            self._build_http()

    # ---------- lifecycle ----------

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()
            self._http = None

    async def __aenter__(self) -> "BetanoSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
