from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
#from api.models import Trade
from api.alpaca_account_service import AlpacaAccountService
import logging
from ...models import Trade

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Close all ghost positions (on Alpaca but not tracked in database)'

    def handle(self, *args, **options):
        User = get_user_model()
        alpaca = AlpacaAccountService()
        
        self.stdout.write(self.style.SUCCESS('\n🔍 GHOST POSITION CLEANUP'))
        self.stdout.write('=' * 70)
        
        # Get all Alpaca positions
        all_positions = alpaca.get_positions()
        
        if not all_positions:
            self.stdout.write(self.style.WARNING('No positions found on Alpaca'))
            return
        
        self.stdout.write(f'\n📊 Found {len(all_positions)} total positions on Alpaca\n')
        
        # Get all tracked symbols from database
        tracked_symbols = set(
            Trade.objects.filter(status='open', broker='alpaca_sim')
            .values_list('symbol', flat=True)
        )
        
        self.stdout.write(f'📁 Tracked in database: {sorted(tracked_symbols)}\n')
        
        # Identify ghost positions
        ghost_positions = []
        for pos in all_positions:
            symbol = pos.get('symbol')
            if symbol not in tracked_symbols:
                ghost_positions.append(pos)
        
        if not ghost_positions:
            self.stdout.write(self.style.SUCCESS('✅ No ghost positions found - database is in sync!'))
            return
        
        self.stdout.write(self.style.WARNING(f'👻 Found {len(ghost_positions)} GHOST POSITIONS (not tracked in DB):'))
        for pos in ghost_positions:
            symbol = pos.get('symbol')
            qty = float(pos.get('qty', 0))
            side = pos.get('side')
            unrealized_pl = float(pos.get('unrealized_pl', 0))
            current_price = float(pos.get('current_price', 0))
            self.stdout.write(f'   - {symbol}: {side} {qty:.2f} @ ${current_price:.2f} (P&L: ${unrealized_pl:.2f})')
        
        # Ask for confirmation
        self.stdout.write(self.style.WARNING('\n⚠️  This will CLOSE all ghost positions on Alpaca'))
        confirm = input('Continue? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('❌ Operation cancelled'))
            return
        
        # Close each ghost position
        closed_count = 0
        failed_count = 0
        total_realized_pl = 0
        
        self.stdout.write('\n📤 Closing ghost positions...\n')
        
        for pos in ghost_positions:
            symbol = pos.get('symbol')
            unrealized_pl = float(pos.get('unrealized_pl', 0))
            
            try:
                # Close position via Alpaca API
                result = alpaca.close_position(symbol)
                
                if result:
                    closed_count += 1
                    total_realized_pl += unrealized_pl
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Closed {symbol} (P&L: ${unrealized_pl:.2f})'))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f'   ❌ Failed to close {symbol}'))
                    
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'   ❌ Error closing {symbol}: {e}'))
        
        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f'✅ CLEANUP COMPLETE'))
        self.stdout.write(f'   Closed: {closed_count} positions')
        self.stdout.write(f'   Failed: {failed_count} positions')
        self.stdout.write(f'   Total Realized P&L: ${total_realized_pl:.2f}')
        self.stdout.write('=' * 70 + '\n')
