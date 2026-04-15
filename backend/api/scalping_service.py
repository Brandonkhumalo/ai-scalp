import logging
import traceback
from datetime import datetime
from decimal import Decimal

import pytz
from django.utils import timezone
from django.db import transaction as db_transaction

from api.models import Trade, Transaction
from api.services import alpaca_service, market_data_service

logger = logging.getLogger(__name__)


def check_scalping_targets(user, alpaca_headers):
    """Check and auto-close positions at scalping targets (1.5% profit / 2% stop-loss)"""
    try:
        with db_transaction.atomic():
            # Get user with lock
            user_model = type(user)
            user = user_model.objects.select_for_update().get(id=user.id)

            # Get all open STOCK trades only (equities-only platform)
            open_trades = Trade.objects.select_for_update().filter(user=user, status='open', instrument_type='stock')

            if not open_trades.exists():
                return {'action': 'none', 'message': 'No open trades'}

            # SCALPING PARAMETERS — 1:2 risk/reward ratio (risk $1 to make $2)
            # With 40% win rate this is profitable: (0.40 × 2%) - (0.60 × 1%) = +0.2% per trade
            PROFIT_TARGET = Decimal('0.02')   # 2% take-profit
            STOP_LOSS = Decimal('0.01')       # 1% stop-loss

            trades_to_close = []

            # Get Alpaca positions for fallback pricing when snapshots fail (rate limiting protection)
            alpaca_positions = alpaca_service.get_positions(user=user) or []
            alpaca_price_map = {pos['symbol']: float(pos.get('current_price', 0)) for pos in alpaca_positions}

            for trade in open_trades:
                # USER PREFERENCE: Scalping strategy enabled - same-day closes allowed
                # NOTE: Alpaca may reject same-day closes due to PDT restrictions (21 day trades)
                # User accepts this risk and prefers immediate profit-taking control

                # Get current market price with fallback logic
                current_price = None

                # Try #1: Market data snapshot (most accurate)
                snapshot = market_data_service.get_realtime_snapshot(trade.symbol)
                if snapshot:
                    latest_quote = snapshot.get('latestQuote', {})
                    current_price = latest_quote.get('ap', latest_quote.get('bp'))

                # Try #2: Alpaca position price (fallback during rate limiting)
                if not current_price and trade.symbol in alpaca_price_map:
                    current_price = alpaca_price_map[trade.symbol]
                    logger.info(f'   Using Alpaca position price for {trade.symbol}: ${current_price}')

                if current_price:
                    # Calculate current P&L and % change
                    if trade.side.lower() == 'buy':
                        pnl = (float(current_price) - float(trade.entry_price)) * float(trade.quantity)
                        pct_change = (Decimal(str(current_price)) - Decimal(str(trade.entry_price))) / Decimal(str(trade.entry_price))
                    else:
                        pnl = (float(trade.entry_price) - float(current_price)) * float(trade.quantity)
                        pct_change = (Decimal(str(trade.entry_price)) - Decimal(str(current_price))) / Decimal(str(trade.entry_price))

                    # SCALPING LOGIC: Close if profit target hit OR stop-loss triggered
                    reason = None
                    if pct_change >= PROFIT_TARGET:
                        reason = f'Profit Target ({float(pct_change)*100:.2f}%)'
                        trades_to_close.append({
                            'trade': trade,
                            'current_price': current_price,
                            'pnl': pnl,
                            'pct_change': pct_change,
                            'reason': reason
                        })
                    elif pct_change <= -STOP_LOSS:
                        reason = f'Stop Loss ({float(pct_change)*100:.2f}%)'
                        trades_to_close.append({
                            'trade': trade,
                            'current_price': current_price,
                            'pnl': pnl,
                            'pct_change': pct_change,
                            'reason': reason
                        })

            if trades_to_close:
                # Close all trades that hit targets
                closed_count = 0
                total_realized_profit = Decimal('0')
                close_details = []

                for item in trades_to_close:
                    trade = item['trade']
                    current_price = item['current_price']
                    pnl = item['pnl']
                    pct_change = item['pct_change']
                    reason = item['reason']

                    # *** PRODUCTION-GRADE POSITION CLOSE WITH VERIFICATION ***
                    try:
                        # USER PREFERENCE WARNING: Attempting same-day close (scalping mode)
                        us_eastern = pytz.timezone('US/Eastern')
                        trade_date_et = trade.created_at.astimezone(us_eastern).date()
                        current_date_et = timezone.now().astimezone(us_eastern).date()

                        if trade_date_et == current_date_et:
                            logger.warning(f'⚠️  SCALPING MODE: Attempting same-day close for {trade.symbol}')
                            logger.warning(f'   Trade opened: {trade.created_at.astimezone(us_eastern).strftime("%Y-%m-%d %H:%M:%S %Z")}')
                            logger.warning(f'   Alpaca may reject due to PDT restrictions (user accepts this risk)')

                        # Step 1: Submit close order to Alpaca
                        # NOTE: close_position() may return None if position already closed (404)
                        # This is OK - verification step is the source of truth!
                        logger.info(f'📤 Submitting close order for {trade.symbol} (qty={trade.quantity})...')
                        close_result = alpaca_service.close_position(trade.symbol, user=user)

                        if close_result:
                            logger.info(f'✅ Close order submitted for {trade.symbol}, order ID: {close_result.get("id", "unknown")}')
                        else:
                            logger.info(f'ℹ️  Close returned None (position may already be closed) - proceeding to verification...')

                        # Step 2: VERIFY position actually closed (ALWAYS RUN - this is the source of truth!)
                        # This handles ALL cases:
                        # - Position already closed (404) → Returns True
                        # - Position closed successfully → Returns True
                        # - Position still exists → Returns False
                        # - API errors / PDT rejections → Returns False
                        logger.info(f'🔍 Verifying position {trade.symbol} is fully closed...')
                        is_closed = alpaca_service.verify_position_closed(
                            symbol=trade.symbol,
                            max_retries=3,
                            retry_delay=1.0,  # 1s, 2s, 4s exponential backoff
                            user=user,
                        )

                        if not is_closed:
                            # Check if this is likely a PDT rejection (same-day close)
                            if trade_date_et == current_date_et:
                                logger.warning(f'🚫 PDT RESTRICTION: Alpaca rejected same-day close for {trade.symbol}')
                                logger.warning(f'   Reason: Pattern Day Trader protection (21 day trades flagged)')
                                logger.warning(f'   Position remains open: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f} ({float(pct_change)*100:.2f}%)')
                                logger.warning(f'   Action: Position will attempt to close on next market day')
                            else:
                                logger.error(f'❌ CRITICAL: Position {trade.symbol} still exists after close attempt!')
                                if close_result:
                                    logger.error(f'   Close order ID: {close_result.get("id", "unknown")}')
                                    logger.error(f'   Close status: {close_result.get("status", "unknown")}')
                                logger.error(f'   Position: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f}')
                                logger.error(f'   ACTION REQUIRED: Check Alpaca dashboard immediately!')
                            continue  # Skip database update - position still open

                        # Step 3: Success - position verified closed on Alpaca
                        logger.info(f'✅ VERIFIED: Position {trade.symbol} successfully closed on Alpaca')
                        logger.info(f'🎯 Scalping: {trade.symbol} (qty={trade.quantity}) - {reason}')
                        logger.info(f'   Realized P&L: ${pnl:.2f} ({float(pct_change)*100:.2f}%)')

                    except Exception as e:
                        error_msg = str(e).lower()

                        # Check if error is PDT-related
                        if any(pdt_keyword in error_msg for pdt_keyword in ['day trading', 'pdt', 'pattern day', 'buying power']):
                            logger.warning(f'🚫 PDT RESTRICTION: Alpaca rejected close for {trade.symbol}')
                            logger.warning(f'   Error: {e}')
                            logger.warning(f'   Position remains open: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f}')
                            logger.warning(f'   Action: Will retry on next market day')
                        else:
                            logger.error(f'❌ EXCEPTION closing Alpaca position {trade.symbol}: {e}')
                            logger.error(f'   Position: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f}')
                            logger.error(f'   CRITICAL: Manual review required - position may be stuck!')
                            logger.error(f'   Stack trace: {traceback.format_exc()}')
                        continue  # Skip this trade if exception occurred

                    # Update database record
                    trade.exit_price = current_price
                    trade.profit_loss = pnl
                    trade.status = 'closed'
                    trade.closed_at = timezone.now()
                    trade.save()

                    # Track P&L for statistics
                    total_realized_profit += Decimal(str(pnl))

                    # Create transaction
                    Transaction.objects.create(
                        user=user,
                        type='trade_pnl',
                        amount=pnl,
                        currency='USD',
                        reference=f'Trade #{trade.id} Auto-Closed (Scalping: {reason})',
                        status='completed'
                    )

                    close_details.append({
                        'symbol': trade.symbol,
                        'pnl': float(pnl),
                        'reason': reason
                    })
                    closed_count += 1

                user.save()

                return {
                    'action': 'scalping_auto_close',
                    'closed_count': closed_count,
                    'total_realized_profit': float(total_realized_profit),
                    'close_details': close_details,
                    'closed_symbols': [detail['symbol'] for detail in close_details],
                    'message': f'Closed {closed_count} trades. Realized P&L: ${total_realized_profit:.2f}'
                }
            else:
                return {
                    'action': 'none',
                    'message': 'No trades hit scalping targets'
                }

    except Exception as e:
        logger.error(f'Error checking scalping targets: {str(e)}')
        return {'action': 'error', 'message': str(e)}
