from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from api.models import Trade
from api.alpaca_account_service import AlpacaAccountService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reconcile database ghost positions - closes trades that exist in DB but not on Alpaca'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='Limit to specific user ID (default: all users)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_id = options['user_id']

        self.stdout.write(self.style.WARNING('\n' + '='*80))
        self.stdout.write(self.style.WARNING('DATABASE GHOST POSITION RECONCILIATION'))
        self.stdout.write(self.style.WARNING('='*80 + '\n'))

        if dry_run:
            self.stdout.write(self.style.NOTICE('[DRY RUN MODE - No changes will be made]\n'))

        alpaca_service = AlpacaAccountService()

        open_trades_query = Trade.objects.filter(status='open')
        if user_id:
            open_trades_query = open_trades_query.filter(user_id=user_id)

        db_open_trades = list(open_trades_query.order_by('symbol', 'created_at'))

        alpaca_positions = alpaca_service.get_positions()
        alpaca_symbols = {pos['symbol'] for pos in alpaca_positions}

        self.stdout.write(f'📊 Database open positions: {len(db_open_trades)}')
        self.stdout.write(f'📊 Alpaca actual positions: {len(alpaca_positions)}\n')

        ghost_positions = []
        for trade in db_open_trades:
            if trade.symbol not in alpaca_symbols:
                ghost_positions.append(trade)

        if not ghost_positions:
            self.stdout.write(self.style.SUCCESS('✅ No ghost positions found - database is in sync!\n'))
            return

        self.stdout.write(self.style.ERROR(f'⚠️  Found {len(ghost_positions)} GHOST POSITIONS in database:\n'))

        for trade in ghost_positions:
            self.stdout.write(
                f'   {trade.symbol:8s} | {trade.quantity:8.2f} shares | '
                f'Entry: ${trade.entry_price:8.2f} | Created: {trade.created_at.strftime("%Y-%m-%d %H:%M")}'
            )

        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] Would close these ghost positions with:'))
            self.stdout.write('  - exit_price = entry_price (neutral close)')
            self.stdout.write('  - profit_loss = 0')
            self.stdout.write('  - status = "closed"')
            self.stdout.write('  - closed_at = now()\n')
            return

        self.stdout.write(self.style.WARNING('\nClosing ghost positions...\n'))

        closed_count = 0
        for trade in ghost_positions:
            try:
                trade.exit_price = trade.entry_price
                trade.profit_loss = 0.0
                trade.status = 'closed'
                trade.closed_at = timezone.now()
                trade.save()

                self.stdout.write(
                    self.style.SUCCESS(f'✅ Closed ghost position: {trade.symbol} (neutral exit)')
                )
                closed_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to close {trade.symbol}: {str(e)}')
                )
                logger.error(f'Error closing ghost position {trade.symbol}: {str(e)}', exc_info=True)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Successfully closed {closed_count}/{len(ghost_positions)} ghost positions'))
        self.stdout.write(self.style.WARNING('\n' + '='*80 + '\n'))
