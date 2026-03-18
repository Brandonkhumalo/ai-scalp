import logging
from decimal import Decimal
from api.services import alpaca_service
from api.models import Trade

logger = logging.getLogger(__name__)


def calculate_position_size(account_balance, risk_per_trade=0.02):
    """Calculate position size based on account balance and risk tolerance"""
    return account_balance * risk_per_trade


def calculate_portfolio_concentration(user):
    """
    Calculate portfolio concentration metrics for diversity analysis

    PRODUCTION-GRADE: Uses LIVE Alpaca positions (30s cache) to prevent ghost positions
    from blocking trades. Falls back to DB on API failure with degraded-mode logging.

    Returns dict with concentration per symbol and diversity metrics
    """
    # *** PRIMARY: Use Alpaca's LIVE positions (already cached 30s TTL) ***
    # This prevents ghost positions from inflating portfolio value
    alpaca_positions = alpaca_service.get_positions()

    # *** FALLBACK: Use DB if Alpaca API fails ***
    if alpaca_positions is None or (isinstance(alpaca_positions, list) and len(alpaca_positions) == 0):
        # Check if we have DB positions (distinguishes "no positions" from "API failure")
        open_trades = Trade.objects.filter(user=user, status='open', instrument_type='stock')

        if not open_trades.exists():
            # No positions anywhere - legitimate empty portfolio
            return {
                'total_positions': 0,
                'concentration': {},
                'max_concentration': 0,
                'diversity_score': 1.0,
                'unique_symbols': 0,
                'portfolio_value': 0
            }

        # API might be down - use DB as fallback
        if alpaca_positions is None:
            logger.warning('DEGRADED MODE: Alpaca API unavailable. Using DB for concentration calculation.')

        # Fallback to DB calculation
        portfolio_value = Decimal('0')
        symbol_exposure = {}

        for trade in open_trades:
            position_value = Decimal(str(trade.quantity)) * Decimal(str(trade.entry_price))
            portfolio_value += position_value

            if trade.symbol not in symbol_exposure:
                symbol_exposure[trade.symbol] = Decimal('0')
            symbol_exposure[trade.symbol] += position_value
    else:
        # *** PRIMARY PATH: Use Alpaca's live market values ***
        portfolio_value = Decimal('0')
        symbol_exposure = {}

        for position in alpaca_positions:
            # Use current market value (more accurate than entry price)
            position_value = Decimal(str(abs(float(position.get('market_value', 0)))))
            portfolio_value += position_value

            symbol = position.get('symbol')
            if symbol not in symbol_exposure:
                symbol_exposure[symbol] = Decimal('0')
            symbol_exposure[symbol] += position_value

    # Calculate concentration percentages
    concentration = {}
    max_concentration = 0

    for symbol, value in symbol_exposure.items():
        if portfolio_value > 0:
            pct = float(value / portfolio_value * 100)
            concentration[symbol] = round(pct, 2)
            max_concentration = max(max_concentration, pct)

    # Calculate diversity score (Herfindahl index inverted)
    hhi = sum((pct ** 2) for pct in concentration.values())
    diversity_score = round(1 - (hhi / 10000), 3)

    return {
        'total_positions': len(symbol_exposure),
        'concentration': concentration,
        'max_concentration': round(max_concentration, 2),
        'diversity_score': diversity_score,
        'unique_symbols': len(symbol_exposure),
        'portfolio_value': float(portfolio_value)
    }


def check_position_concentration(user, symbol, proposed_trade_value, max_concentration_pct=15):
    """
    Check if adding a new position would violate concentration limits

    CRITICAL FIX: Concentration is measured against ACCOUNT EQUITY, not sum of positions.
    This allows proper portfolio growth while maintaining risk controls.

    Args:
        user: User object
        symbol: Stock symbol for the proposed trade
        proposed_trade_value: Dollar value of the proposed trade
        max_concentration_pct: Maximum allowed concentration in a single stock (default 15%)

    Returns:
        dict with 'allowed': bool and 'reason': str
    """
    # Get current portfolio state
    portfolio = calculate_portfolio_concentration(user)

    # *** CRITICAL FIX: Use ACCOUNT EQUITY, not sum of positions ***
    # Get total account equity from Alpaca
    account_info = alpaca_service.get_account_info()
    if not account_info:
        logger.warning('Cannot get account info for concentration check. Denying trade for safety.')
        return {
            'allowed': False,
            'reason': 'Cannot verify concentration (API unavailable)',
            'current_concentration': 0,
            'new_concentration': 0,
            'diversity_score': 0
        }

    account_equity = Decimal(str(account_info.get('equity', 0)))

    # Calculate proposed position's value (existing + new)
    current_portfolio_value = Decimal(str(portfolio.get('portfolio_value', 0)))
    current_symbol_exposure = Decimal(str(portfolio['concentration'].get(symbol, 0))) * current_portfolio_value / 100
    new_symbol_exposure = current_symbol_exposure + Decimal(str(proposed_trade_value))

    # Calculate new concentration percentage AGAINST ACCOUNT EQUITY
    if account_equity > 0:
        new_concentration_pct = float(new_symbol_exposure / account_equity * 100)
    else:
        new_concentration_pct = 100.0  # First trade is 100% concentrated

    # Allow first 2 positions to build initial portfolio diversity (bypass concentration check)
    # This prevents blocking when the second position would naturally be >40% in a small portfolio
    total_positions = portfolio.get('total_positions', 0)
    # Only check OPEN trades when determining if symbol is new (ignore historical closed trades)
    is_new_symbol = not Trade.objects.filter(user=user, symbol=symbol, status='open', instrument_type='stock').exists()

    # Debug logging to troubleshoot bypass logic
    logger.info(f"Concentration check for {symbol}: total_positions={total_positions}, is_new_symbol={is_new_symbol}, bypass_allowed={total_positions < 2 and is_new_symbol}")

    if total_positions < 2 and is_new_symbol:
        return {
            'allowed': True,
            'reason': f'Building initial portfolio diversity ({total_positions + 1}/2 positions)',
            'current_concentration': portfolio['concentration'].get(symbol, 0),
            'new_concentration': round(new_concentration_pct, 2),
            'diversity_score': portfolio['diversity_score']
        }

    # Check if it violates the concentration limit
    if new_concentration_pct > max_concentration_pct:
        return {
            'allowed': False,
            'reason': f'Position concentration limit exceeded: {symbol} would be {new_concentration_pct:.1f}% (max {max_concentration_pct}%)',
            'current_concentration': portfolio['concentration'].get(symbol, 0),
            'new_concentration': round(new_concentration_pct, 2),
            'diversity_score': portfolio['diversity_score']
        }

    return {
        'allowed': True,
        'reason': 'Within concentration limits',
        'current_concentration': portfolio['concentration'].get(symbol, 0),
        'new_concentration': round(new_concentration_pct, 2),
        'diversity_score': portfolio['diversity_score']
    }
