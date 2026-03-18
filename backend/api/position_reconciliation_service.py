"""
Position Reconciliation Service

This service ensures the database stays in sync with Alpaca by:
1. Deleting ghost positions (database entries for closed Alpaca positions)
2. Keeping only one database record per symbol
3. Using Alpaca as the single source of truth

Ghost positions occur when:
- Alpaca closes a position (stop-loss, PDT, etc.) but database isn't updated
- Multiple database entries exist for the same symbol
"""

import logging
from api.models import Trade
logger = logging.getLogger(__name__)


class PositionReconciliationService:
    """Syncs database trades with Alpaca positions"""

    def __init__(self):
        from api.services import alpaca_service
        self.alpaca_service = alpaca_service
    
    def reconcile_user_positions(self, user, verbose=False):
        """
        Reconcile database open trades with Alpaca positions for a user.
        
        IMPORTANT: This preserves trade history by marking externally-closed positions 
        as "closed" instead of deleting them. This ensures ML training data is not lost.
        
        Returns:
            dict: {
                'ghosts_removed': int,
                'positions_closed': int,
                'positions_synced': int,
                'alpaca_positions': int,
                'database_positions': int
            }
        """
        try:
            from decimal import Decimal
            from django.utils import timezone
            
            # Get Alpaca positions (source of truth for OPEN positions)
            alpaca_positions = self.alpaca_service.get_positions(user)
            alpaca_symbols = {pos['symbol']: float(pos['qty']) for pos in alpaca_positions}
            
            # Get Alpaca CLOSED positions (last 30 days) to preserve trade history
            # Use 30 days to catch positions closed during market holidays, weekends, etc.
            try:
                alpaca_closed = self.alpaca_service.get_closed_positions_with_pnl(days_back=30)
                alpaca_closed_map = {pos['symbol']: pos for pos in alpaca_closed}
                logger.info(f"Fetched {len(alpaca_closed)} closed positions from Alpaca (30 day lookback)")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch Alpaca closed positions: {e}")
                logger.warning(f"   Reconciliation will NOT delete trades (preserving history safely)")
                alpaca_closed_map = None  # Signal that we don't have closed position data
            
            # Get database open trades
            db_open_trades = Trade.objects.filter(
                user=user, 
                status='open'
            ).order_by('symbol', '-created_at')
            
            initial_db_count = db_open_trades.count()
            ghosts_removed = 0
            positions_closed = 0
            seen_symbols = set()
            
            # Process each database trade
            for trade in db_open_trades:
                should_remove = False
                should_close = False
                reason = None
                
                # Check 1: Symbol no longer on Alpaca (may be externally closed)
                if trade.symbol not in alpaca_symbols:
                    # Try to find it in Alpaca's closed positions (if available)
                    if alpaca_closed_map is not None and trade.symbol in alpaca_closed_map:
                        should_close = True
                        reason = "closed by Alpaca (preserving history)"
                    elif alpaca_closed_map is None:
                        # No closed position data available - KEEP trade to avoid data loss!
                        logger.info(f"⚠️ Skipping {trade.symbol} - no Alpaca closed data (keeping for safety)")
                        continue
                    else:
                        should_remove = True
                        reason = "symbol not found on Alpaca (orphaned - not in last 30 days)"
                
                # Check 2: Duplicate entry for same symbol
                elif trade.symbol in seen_symbols:
                    should_remove = True
                    reason = "duplicate entry"
                
                if should_close:
                    # Mark as closed with Alpaca's P&L data (preserves trade history!)
                    alpaca_data = alpaca_closed_map[trade.symbol]
                    trade.status = 'closed'
                    trade.exit_price = Decimal(str(alpaca_data.get('exit_price', trade.entry_price)))
                    trade.pnl = Decimal(str(alpaca_data.get('realized_pnl', 0)))
                    trade.closed_at = timezone.now()
                    trade.save()
                    positions_closed += 1
                    
                    if verbose:
                        logger.info(
                            f"✅ Closed: {trade.symbol} "
                            f"{trade.side} {trade.quantity} @ ${trade.entry_price} "
                            f"P&L: ${trade.pnl} ({reason})"
                        )
                
                elif should_remove:
                    # Delete only true orphans (no history to preserve)
                    if verbose:
                        logger.info(
                            f"👻 Removing orphan: {trade.symbol} "
                            f"{trade.side} {trade.quantity} @ ${trade.entry_price} "
                            f"({reason})"
                        )
                    trade.delete()
                    ghosts_removed += 1
                
                else:
                    seen_symbols.add(trade.symbol)
            
            final_db_count = Trade.objects.filter(user=user, status='open').count()
            
            result = {
                'ghosts_removed': ghosts_removed,
                'positions_closed': positions_closed,
                'positions_synced': final_db_count,
                'alpaca_positions': len(alpaca_positions),
                'database_positions': final_db_count,
                'in_sync': final_db_count == len(alpaca_positions)
            }
            
            if verbose and (ghosts_removed > 0 or positions_closed > 0):
                logger.info(
                    f"✅ Reconciliation complete for {user.email}: "
                    f"Closed {positions_closed} positions, "
                    f"Removed {ghosts_removed} orphans, "
                    f"{final_db_count} positions in sync with Alpaca"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Reconciliation failed for {user.email}: {str(e)}")
            return {
                'ghosts_removed': 0,
                'positions_closed': 0,
                'positions_synced': 0,
                'alpaca_positions': 0,
                'database_positions': 0,
                'in_sync': False,
                'error': str(e)
            }
