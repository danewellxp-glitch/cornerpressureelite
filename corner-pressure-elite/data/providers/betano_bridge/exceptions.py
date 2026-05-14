"""Exceções do client do bridge Betano.

São levantadas apenas por `BetanoBridgeClient` (fronteira HTTP). O adapter
(`BetanoBridgeOddsAdapter`) captura essas exceções e devolve `None`, em
linha com a convenção do `OddsProvider` Protocol.
"""


class BridgeError(Exception):
    """Base: qualquer erro do bridge Betano."""


class BridgeUnavailable(BridgeError):
    """Bridge offline, rede inacessível ou HTTP 5xx."""


class BridgeTimeout(BridgeError):
    """Bridge respondeu além do timeout configurado."""


class BridgeMarketNotFound(BridgeError):
    """Bridge respondeu com 404 ou `found:false` (mercado/linha indisponível)."""
