"""
Module-level singleton service instances.

Import these instead of creating new instances per request so that
all views and the autonomous agent share the same in-memory caches
and rate-limit state.

Usage:
    from api.services import alpaca_service, market_data_service
"""
from api.alpaca_account_service import AlpacaAccountService
from api.market_data_service import MarketDataService

# Shared singletons — every caller gets the same cache and counters
alpaca_service = AlpacaAccountService()
market_data_service = MarketDataService()
