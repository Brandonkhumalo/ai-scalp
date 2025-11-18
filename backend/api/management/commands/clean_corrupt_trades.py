from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import Trade, Transaction
from django.db import transaction
from decimal import Decimal

class Command(BaseCommand):
    help = 'Clean up corrupt trade records (closed trades with exit_price=$0.00)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n🧹 CORRUPT TRADE DATA CLEANUP'))
        self.stdout.write('=' * 70)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN MODE - No data will be deleted\n'))
        
        # Find all corrupt trades (closed with exit_price = 0 or null)
        corrupt_trades = Trade.objects.filter(
            status='closed'
        ).filter(
            exit_price__isnull=True
        ) | Trade.objects.filter(
            status='closed',
            exit_price=Decimal('0')
        )
        
        total_corrupt = corrupt_trades.count()
        
        if total_corrupt == 0:
            self.stdout.write(self.style.SUCCESS('✅ No corrupt trades found - database is clean!'))
            return
        
        # Show statistics
        self.stdout.write(self.style.WARNING(f'🚨 Found {total_corrupt} CORRUPT TRADES:'))
        self.stdout.write(f'   (Closed trades with exit_price=$0.00 or NULL)\n')
        
        # Group by user
        User = get_user_model()
        for user in User.objects.all():
            user_corrupt = corrupt_trades.filter(user=user).count()
            if user_corrupt > 0:
                self.stdout.write(f'   📊 {user.email}: {user_corrupt} corrupt trades')
        
        # Show sample records
        self.stdout.write('\n📋 Sample corrupt trades:')
        for trade in corrupt_trades[:10]:
            self.stdout.write(f'   ID {trade.id}: {trade.symbol} - Entry: ${trade.entry_price}, Exit: ${trade.exit_price or 0}, P&L: ${trade.profit_loss or 0}')
        
        if total_corrupt > 10:
            self.stdout.write(f'   ... and {total_corrupt - 10} more')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n🔍 DRY RUN: Would delete {total_corrupt} corrupt trades'))
            self.stdout.write('   Run without --dry-run to actually delete these records')
            return
        
        # Ask for confirmation
        self.stdout.write(self.style.WARNING(f'\n⚠️  This will DELETE {total_corrupt} corrupt trade records'))
        self.stdout.write('   This will allow the ML model to retrain on clean data')
        confirm = input('Continue? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('❌ Operation cancelled'))
            return
        
        # Delete corrupt trades in a transaction
        with transaction.atomic():
            deleted_count = corrupt_trades.count()
            corrupt_trades.delete()
            
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write(self.style.SUCCESS(f'✅ CLEANUP COMPLETE'))
            self.stdout.write(f'   Deleted: {deleted_count} corrupt trade records')
            self.stdout.write('   ML model can now retrain on clean data')
            self.stdout.write('=' * 70 + '\n')
