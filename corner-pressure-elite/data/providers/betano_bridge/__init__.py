"""Bridge HTTP local para captura de odds Betano via Chrome+Playwright.

Provider primário do `CompositeOddsProvider` quando `USE_BETANO_BRIDGE=true`,
com fallback automático pro APIFootball via cascata padrão do composite.

Componentes:
- `BetanoBridgeClient`: HTTPX async para o bridge FastAPI em :8080
- `BetanoBridgeOddsAdapter`: implementa `OddsProvider` Protocol
- Exceções (`BridgeUnavailable`, `BridgeTimeout`, `BridgeMarketNotFound`):
  levantadas pelo client; o adapter captura no boundary e devolve None.
"""
from data.providers.betano_bridge.client import BetanoBridgeClient
from data.providers.betano_bridge.exceptions import (
    BridgeError,
    BridgeMarketNotFound,
    BridgeTimeout,
    BridgeUnavailable,
)
from data.providers.betano_bridge.odds_adapter import BetanoBridgeOddsAdapter

__all__ = [
    "BetanoBridgeClient",
    "BetanoBridgeOddsAdapter",
    "BridgeError",
    "BridgeUnavailable",
    "BridgeTimeout",
    "BridgeMarketNotFound",
]
