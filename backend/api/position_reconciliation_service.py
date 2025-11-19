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
from api.alpaca_account_service import AlpacaAccountService

logger = logging.getLogger(__name__)


class PositionReconciliationService:
    """Syncs database trades with Alpaca positions"""
    
    def __init__(self):
        self.alpaca_service = AlpacaAccountService()
    
    def reconcile_user_positions(self, user, verbose=False):
        """
        Reconcile database open trades with Alpaca positions for a user.
        
        Returns:
            dict: {
                'ghosts_removed': int,
                'positions_synced': int,
                'alpaca_positions': int,
                'database_positions': int
            }
        """
        try:
            # Get Alpaca positions (source of truth)
            alpaca_positions = self.alpaca_service.get_positions(user)
            alpaca_symbols = {pos['symbol']: float(pos['qty']) for pos in alpaca_positions}
            
            # Get database open trades
            db_open_trades = Trade.objects.filter(
                user=user, 
                status='open'
            ).order_by('symbol', '-created_at')
            
            initial_db_count = db_open_trades.count()
            ghosts_removed = 0
            seen_symbols = set()
            
            # Process each database trade
            for trade in db_open_trades:
                should_delete = False
                reason = None
                
                # Check 1: Symbol no longer on Alpaca
                if trade.symbol not in alpaca_symbols:
                    should_delete = True
                    reason = "symbol not on Alpaca (closed externally)"
                
                # Check 2: Duplicate entry for same symbol
                elif trade.symbol in seen_symbols:
                    should_delete = True
                    reason = "duplicate entry"
                
                if should_delete:
                    if verbose:
                        logger.info(
                            f"👻 Removing ghost: {trade.symbol} "
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
                'positions_synced': final_db_count,
                'alpaca_positions': len(alpaca_positions),
                'database_positions': final_db_count,
                'in_sync': final_db_count == len(alpaca_positions)
            }
            
            if verbose and ghosts_removed > 0:
                logger.info(
                    f"✅ Reconciliation complete for {user.email}: "
                    f"Removed {ghosts_removed} ghosts, "
                    f"{final_db_count} positions in sync with Alpaca"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Reconciliation failed for {user.email}: {str(e)}")
            return {
                'ghosts_removed': 0,
                'positions_synced': 0,
                'alpaca_positions': 0,
                'database_positions': 0,
                'in_sync': False,
                'error': str(e)
            }
