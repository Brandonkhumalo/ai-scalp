"""
Emergency command to close ALL positions immediately
Closes both database-tracked positions and ghost positions on Alpaca
"""
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Trade
from accounts.models import User
from api.alpaca_account_service import AlpacaAccountService
from decimal import Decimal


class Command(BaseCommand):
    help = 'EMERGENCY: Close all open positions immediately to stop losses'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('🚨 EMERGENCY POSITION CLOSURE INITIATED'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        # Get Alpaca service
        alpaca_service = AlpacaAccountService()
        
        # Get ALL users (regardless of AI trading status)
        users = User.objects.all()
        
        total_closed = 0
        total_errors = 0
        
        for user in users:
            self.stdout.write(f'\n📊 Processing user: {user.email}')
            
            # STEP 1: Get ALL positions from Alpaca (includes ghosts)
            try:
                alpaca_positions = alpaca_service.get_positions()
                self.stdout.write(f'   Found {len(alpaca_positions)} positions on Alpaca')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Failed to get Alpaca positions: {e}'))
                continue
            
            # STEP 2: Close ALL Alpaca positions (including ghosts)
            for position in alpaca_positions:
                symbol = position['symbol']
                qty = abs(float(position['qty']))
                side = position['side']
                
                try:
                    self.stdout.write(f'   🔄 Closing {symbol}: {qty} shares ({side})')
                    
                    # Close position on Alpaca
                    result = alpaca_service.close_position(symbol)
                    
                    if result.get('success'):
                        self.stdout.write(self.style.SUCCESS(f'      ✅ Closed {symbol} on Alpaca'))
                        total_closed += 1
                        
                        # Update database if it exists
                        db_trades = Trade.objects.filter(
                            user=user,
                            broker='alpaca_sim',
                            symbol=symbol,
                            status='open'
                        )
                        
                        if db_trades.exists():
                            for trade in db_trades:
                                trade.status = 'closed'
                                trade.exit_price = trade.entry_price  # Neutral exit
                                trade.profit_loss = Decimal('0.00')
                                trade.closed_at = timezone.now()
                                trade.save()
                            self.stdout.write(f'      ✅ Updated {db_trades.count()} database record(s)')
                        else:
                            self.stdout.write(f'      ⚠️  Ghost position (not in database)')
                    else:
                        self.stdout.write(self.style.ERROR(f'      ❌ Failed to close {symbol}: {result.get("message")}'))
                        total_errors += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'      ❌ Error closing {symbol}: {e}'))
                    total_errors += 1
            
            # STEP 3: Close any remaining database positions that weren't on Alpaca
            db_only_trades = Trade.objects.filter(
                user=user,
                broker='alpaca_sim',
                status='open'
            )
            
            if db_only_trades.exists():
                self.stdout.write(f'\n   📋 Found {db_only_trades.count()} orphaned database positions')
                for trade in db_only_trades:
                    trade.status = 'closed'
                    trade.exit_price = trade.entry_price
                    trade.profit_loss = Decimal('0.00')
                    trade.closed_at = timezone.now()
                    trade.save()
                    self.stdout.write(self.style.SUCCESS(f'      ✅ Closed orphan: {trade.symbol}'))
        
        # FINAL SUMMARY
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS(f'✅ EMERGENCY CLOSURE COMPLETE'))
        self.stdout.write(self.style.SUCCESS(f'   Total positions closed: {total_closed}'))
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'   Errors encountered: {total_errors}'))
        self.stdout.write('=' * 80)
        
        # Verify all closed
        remaining = Trade.objects.filter(broker='alpaca_sim', status='open').count()
        if remaining == 0:
            self.stdout.write(self.style.SUCCESS('\n🎉 SUCCESS: All database positions are now closed!'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠️  WARNING: {remaining} positions still open in database'))
