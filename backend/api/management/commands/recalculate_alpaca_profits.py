from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Trade
from decimal import Decimal

class Command(BaseCommand):
    help = 'Recalculate profit/loss for all Alpaca trades'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔄 Recalculating Alpaca trade profits...'))
        
        alpaca_trades = Trade.objects.filter(broker='alpaca_sim', status='closed')
        total_trades = alpaca_trades.count()
        
        if total_trades == 0:
            self.stdout.write(self.style.WARNING('⚠️  No closed Alpaca trades found'))
            return
        
        self.stdout.write(f'📊 Found {total_trades} closed Alpaca trades')
        
        updated_count = 0
        total_old_pl = Decimal('0')
        total_new_pl = Decimal('0')
        
        for trade in alpaca_trades:
            if trade.exit_price is None:
                self.stdout.write(self.style.WARNING(f'⚠️  Trade {trade.id} has no exit price, skipping'))
                continue
            
            old_pl = trade.profit_loss or Decimal('0')
            
            if trade.side == 'buy':
                new_pl = (trade.exit_price - trade.entry_price) * trade.quantity
            else:
                new_pl = (trade.entry_price - trade.exit_price) * trade.quantity
            
            new_pl = new_pl.quantize(Decimal('0.01'))
            
            if old_pl != new_pl:
                trade.profit_loss = new_pl
                trade.save(update_fields=['profit_loss'])
                
                total_old_pl += old_pl
                total_new_pl += new_pl
                updated_count += 1
                
                self.stdout.write(f'✅ Trade {trade.id} ({trade.symbol}): ${old_pl:.2f} → ${new_pl:.2f}')
        
        self.stdout.write(self.style.SUCCESS(f'\n📈 Recalculation Complete:'))
        self.stdout.write(f'   Total trades processed: {total_trades}')
        self.stdout.write(f'   Trades updated: {updated_count}')
        self.stdout.write(f'   Old total P/L: ${total_old_pl:.2f}')
        self.stdout.write(f'   New total P/L: ${total_new_pl:.2f}')
        self.stdout.write(f'   Difference: ${(total_new_pl - total_old_pl):.2f}')
