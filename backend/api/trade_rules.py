"""Explicit rule engine that replaces the ML model for trade quality gating.

These rules encode what the RandomForest's feature importance analysis discovered:
  1. Recent_Loss_Streak (23% importance) — don't trade during losing streaks
  2. BB_Width / volatility (7.7% importance) — don't trade in extreme volatility
  3. Is_High_Loss_Condition (7.9% importance) — cool off after consecutive losses
  4. VIX regime filter — reduce/halt trading in high-fear markets

A rule engine is more transparent, doesn't overfit, needs zero training data,
and executes instantly vs loading a pickled model.
"""
import logging
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

# VIX cache key and TTL (fetch at most once per 5 minutes)
_VIX_CACHE_KEY = 'trade_rules:vix'
_VIX_CACHE_TTL = 300


def _get_vix():
    """Fetch the current VIX level via the market data service (cached 5 min)."""
    vix = cache.get(_VIX_CACHE_KEY)
    if vix is not None:
        return vix

    try:
        from api.services import market_data_service
        # VIX is available as VIXY ETF snapshot on Alpaca, or direct ^VIX via yfinance
        snapshot = market_data_service.get_realtime_snapshot('VIXY')
        if snapshot:
            quote = snapshot.get('latestQuote', {})
            vix_price = quote.get('ap') or quote.get('bp')
            if vix_price:
                vix = float(vix_price)
                cache.set(_VIX_CACHE_KEY, vix, _VIX_CACHE_TTL)
                return vix
    except Exception as e:
        logger.debug(f'Could not fetch VIX proxy: {e}')

    return None  # Unknown — don't block trading


def check_trade_rules(user, symbol, bb_width, analysis=None):
    """Run pre-trade quality checks. Returns (allowed, reason, position_scale).

    Args:
        user: The User placing the trade.
        symbol: Stock symbol being traded.
        bb_width: Current Bollinger Band width (volatility proxy).
        analysis: Optional dict from analyze_market_sentiment with indicator data.

    Returns:
        (True, None) if trade is allowed at full size.
        (False, reason_string) if trade should be skipped.
    """
    from api.models import Trade

    # ── Rule 1: Loss streak cooldown ─────────────────────────────────────
    # If 3+ consecutive losses, skip this trade and wait for conditions to change.
    recent_trades = (
        Trade.objects.filter(user=user, status='closed', profit_loss__isnull=False)
        .order_by('-closed_at')[:5]
    )
    consecutive_losses = 0
    for trade in recent_trades:
        if trade.profit_loss < 0:
            consecutive_losses += 1
        else:
            break

    if consecutive_losses >= 3:
        logger.info(f'Rule Engine: SKIP {symbol} — {consecutive_losses} consecutive losses (cooling off)')
        return False, f'{consecutive_losses} consecutive losses — cooling off'

    # ── Rule 2: High volatility gate ─────────────────────────────────────
    # BB_Width > 0.04 means extreme volatility — indicators become unreliable.
    if bb_width > 0.04:
        logger.info(f'Rule Engine: SKIP {symbol} — BB width {bb_width:.4f} > 0.04 (volatility too high)')
        return False, f'Volatility too high (BB width {bb_width:.4f})'

    # ── Rule 3: VIX regime filter ────────────────────────────────────────
    # VIX (fear index) determines whether the market is safe for scalping.
    # Uses VIXY ETF as proxy (available on Alpaca).
    # > 25: indicators fail, halt trading entirely
    # > 20: reduce confidence, tighter rules
    vix = _get_vix()
    if vix is not None and vix > 25:
        logger.info(f'Rule Engine: SKIP {symbol} — VIX proxy {vix:.1f} > 25 (extreme fear, halting)')
        return False, f'Market fear too high (VIX proxy {vix:.1f} > 25)'

    # ── Rule 4: Daily loss limit proximity ───────────────────────────────
    # Soft gate before the 8% hard limit in execute_ai_trade.
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_pnl = (
        Trade.objects.filter(
            user=user, status='closed', closed_at__gte=today_start,
            profit_loss__isnull=False,
        )
        .aggregate(total=Sum('profit_loss'))['total']
    ) or Decimal('0')

    if today_pnl < Decimal('-500'):
        logger.info(f'Rule Engine: SKIP {symbol} — daily P&L ${today_pnl:.2f} approaching loss limit')
        return False, f'Daily P&L ${today_pnl:.2f} approaching limit'

    # All rules passed
    return True, None
