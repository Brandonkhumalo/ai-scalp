"""
Module-level singleton service instances.

Import these instead of creating new instances per request so that
all views and the autonomous agent share the same in-memory caches
and rate-limit state.

Usage:
    from api.services import alpaca_service, market_data_service
"""
import os

from api.alpaca_account_service import AlpacaAccountService
from api.capital_account_service import CapitalAccountService
from api.market_data_service import MarketDataService

# Shared singletons — every caller gets the same cache and counters.
# Keep variable name for backwards compatibility across the codebase.
if os.getenv('BROKER_PROVIDER', 'capital').lower() == 'alpaca':
    alpaca_service = AlpacaAccountService()
else:
    alpaca_service = CapitalAccountService()
market_data_service = MarketDataService()
