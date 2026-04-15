from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from api.models import Trade
from api.alpaca_account_service import AlpacaAccountService
from api.ml_training_service import MLTradingModel
from collections import defaultdict
from decimal import Decimal
from dateutil import parser
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import historical closed positions from Alpaca to bootstrap ML training'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-email',
            type=str,
            help='User email to import trades for',
            default='josias@tishanyq.co.zw'
        )
        parser.add_argument(
            '--max-trades',
            type=int,
            help='Maximum number of closed positions to import',
            default=50
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )

    def handle(self, *args, **options):
        user_email = options['user_email']
        max_trades = options['max_trades']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n📥 ALPACA HISTORICAL DATA IMPORT'))
        self.stdout.write('=' * 70)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN MODE - No data will be imported\n'))
        
        # Get user
        User = get_user_model()
        try:
            user = User.objects.get(email=user_email)
            self.stdout.write(f'User: {user.email}')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ User {user_email} not found'))
            return
        
        # Get ML cutoff date
        cutoff_date = getattr(settings, 'ML_TRAINING_CUTOFF_DATE', None)
        if cutoff_date:
            self.stdout.write(f'ML Training Cutoff: {cutoff_date}')
            self.stdout.write(f'Only importing trades after this date\n')
        
        # Initialize Alpaca service
        alpaca = AlpacaAccountService()
        
        # Fetch account activities (FILL events)
        self.stdout.write('🔍 Fetching Alpaca account activities...')
        activities = alpaca.get_account_activities(
            activity_types='FILL',
            page_size=100,
            direction='desc'
        )
        
        if not activities:
            self.stdout.write(self.style.WARNING('⚠️  No activities found in Alpaca account'))
            return
        
        self.stdout.write(f'✅ Found {len(activities)} FILL activities\n')
        
        # Group activities by symbol to match buy/sell pairs
        symbol_trades = defaultdict(list)
        for activity in activities:
            symbol = activity.get('symbol')
            transaction_time = activity.get('transaction_time')
            
            # Parse timestamp
            try:
                timestamp = parser.parse(transaction_time)
            except:
                continue
            
            # Filter by cutoff date if set
            if cutoff_date and timestamp < cutoff_date:
                continue
            
            if symbol:
                symbol_trades[symbol].append({
                    'side': activity.get('side'),  # 'buy' or 'sell'
                    'qty': float(activity.get('qty', 0)),
                    'price': float(activity.get('price', 0)),
                    'timestamp': timestamp,
                    'id': activity.get('id')
                })
        
        # Calculate closed positions
        closed_positions = []
        
        for symbol, trades in symbol_trades.items():
            # Sort by timestamp (oldest first)
            trades.sort(key=lambda x: x['timestamp'])
            
            # Track open position
            position_qty = 0
            position_cost = 0
            entry_time = None
            
            for trade in trades:
                if trade['side'] == 'buy':
                    # Add to position
                    position_cost += trade['qty'] * trade['price']
                    position_qty += trade['qty']
                    if entry_time is None:
                        entry_time = trade['timestamp']
                else:  # sell
                    # Close position (full or partial)
                    if position_qty > 0:
                        sell_qty = min(trade['qty'], position_qty)
                        avg_cost = position_cost / position_qty if position_qty > 0 else 0
                        
                        # Calculate P&L for this close
                        pl = sell_qty * (trade['price'] - avg_cost)
                        
                        # Calculate hold time
                        if entry_time and trade['timestamp']:
                            hold_time_hours = (trade['timestamp'] - entry_time).total_seconds() / 3600
                        else:
                            hold_time_hours = 0
                        
                        closed_positions.append({
                            'symbol': symbol,
                            'side': 'buy',  # Original entry side
                            'quantity': sell_qty,
                            'entry_price': avg_cost,
                            'exit_price': trade['price'],
                            'profit_loss': pl,
                            'created_at': entry_time,
                            'closed_at': trade['timestamp'],
                            'hold_time_hours': hold_time_hours,
                            'alpaca_id': trade['id']
                        })
                        
                        # Update remaining position
                        position_qty -= sell_qty
                        if position_qty > 0:
                            position_cost = position_qty * avg_cost
                        else:
                            position_cost = 0
                            entry_time = None
        
        # Limit to max_trades
        closed_positions = closed_positions[:max_trades]
        
        if not closed_positions:
            self.stdout.write(self.style.WARNING('⚠️  No closed positions found after cutoff date'))
            return
        
        self.stdout.write(f'\n📊 CLOSED POSITIONS TO IMPORT: {len(closed_positions)}')
        self.stdout.write('=' * 70)
        
        # Show statistics
        wins = sum(1 for p in closed_positions if p['profit_loss'] > 0)
        losses = sum(1 for p in closed_positions if p['profit_loss'] < 0)
        total_pnl = sum(p['profit_loss'] for p in closed_positions)
        
        self.stdout.write(f'✅ Wins: {wins}')
        self.stdout.write(f'❌ Losses: {losses}')
        self.stdout.write(f'💰 Total P&L: ${total_pnl:.2f}')
        if closed_positions:
            win_rate = (wins / len(closed_positions)) * 100
            self.stdout.write(f'📈 Win Rate: {win_rate:.2f}%')
        
        # Show sample
        self.stdout.write('\n📋 Sample positions (first 10):')
        for i, pos in enumerate(closed_positions[:10], 1):
            pnl = pos['profit_loss']
            icon = '✅' if pnl > 0 else '❌'
            self.stdout.write(
                f"  {i}. {icon} {pos['symbol']}: {pos['quantity']} shares @ "
                f"${pos['entry_price']:.2f} → ${pos['exit_price']:.2f} = ${pnl:.2f}"
            )
        
        if len(closed_positions) > 10:
            self.stdout.write(f'  ... and {len(closed_positions) - 10} more')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n🔍 DRY RUN: Would import {len(closed_positions)} trades'))
            self.stdout.write('   Run without --dry-run to actually import these trades')
            return
        
        # Import trades into database
        self.stdout.write('\n💾 Importing trades into database...')
        imported_count = 0
        skipped_count = 0
        
        for pos in closed_positions:
            # Check if already exists (by symbol and timestamp)
            existing = Trade.objects.filter(
                user=user,
                symbol=pos['symbol'],
                created_at=pos['created_at'],
                status='closed'
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # Create trade record
            trade = Trade.objects.create(
                user=user,
                symbol=pos['symbol'],
                side=pos['side'],
                quantity=Decimal(str(pos['quantity'])),
                entry_price=Decimal(str(pos['entry_price'])),
                exit_price=Decimal(str(pos['exit_price'])),
                profit_loss=Decimal(str(pos['profit_loss'])),
                status='closed',
                instrument_type='stock',
                created_at=pos['created_at'],
                closed_at=pos['closed_at']
            )
            imported_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ IMPORT COMPLETE'))
        self.stdout.write(f'   Imported: {imported_count} trades')
        self.stdout.write(f'   Skipped (duplicates): {skipped_count} trades')
        
        # Show final database state
        total_closed = Trade.objects.filter(user=user, status='closed').count()
        self.stdout.write(f'\n📊 Total closed trades in database: {total_closed}')

        min_required = MLTradingModel().min_trades_for_training
        if total_closed >= min_required:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Sufficient data for ML training ({total_closed} ≥ {min_required})'
            ))
            self.stdout.write('\n🤖 Next step: Run ML training to improve AI confidence')
        else:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Still need more trades for ML training ({total_closed} < {min_required})'
            ))
