from django.core.management.base import BaseCommand
from accounts.models import User
from api.models import Trade
from api.alpaca_account_service import AlpacaAccountService
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reconcile database trades with Alpaca positions'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Starting position reconciliation...\n')
        
        users = User.objects.all()
        
        for user in users:
            self.stdout.write(f'\n👤 User: {user.email}')
            
            alpaca = AlpacaAccountService()
            
            try:
                positions = alpaca.get_positions(user)
                alpaca_symbols = {pos['symbol']: float(pos['qty']) for pos in positions}
                
                self.stdout.write(f'   Alpaca positions: {len(alpaca_symbols)}')
                for symbol, qty in alpaca_symbols.items():
                    self.stdout.write(f'     - {symbol}: {qty} shares')
                
                db_open_trades = Trade.objects.filter(user=user, status='open').order_by('symbol', '-created_at')
                self.stdout.write(f'   Database open trades: {db_open_trades.count()}')
                
                reconciled_count = 0
                seen_symbols = set()
                
                for trade in db_open_trades:
                    if trade.symbol not in alpaca_symbols:
                        self.stdout.write(
                            self.style.WARNING(
                                f'   👻 GHOST (symbol not on Alpaca): {trade.symbol} {trade.side} {trade.quantity} @ ${trade.entry_price}'
                            )
                        )
                        self.stdout.write(f'        Created: {trade.created_at}')
                        self.stdout.write(f'        Deleting...')
                        
                        trade.delete()
                        reconciled_count += 1
                    
                    elif trade.symbol in seen_symbols:
                        self.stdout.write(
                            self.style.WARNING(
                                f'   👻 GHOST (duplicate): {trade.symbol} {trade.side} {trade.quantity} @ ${trade.entry_price}'
                            )
                        )
                        self.stdout.write(f'        Created: {trade.created_at}')
                        self.stdout.write(f'        Deleting duplicate...')
                        
                        trade.delete()
                        reconciled_count += 1
                    
                    else:
                        seen_symbols.add(trade.symbol)
                
                if reconciled_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(f'\n✅ Reconciled {reconciled_count} ghost positions for {user.email}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ All positions in sync for {user.email}')
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error reconciling {user.email}: {str(e)}')
                )
        
        self.stdout.write(self.style.SUCCESS('\n✅ Reconciliation complete!'))
