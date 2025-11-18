from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import Trade, Transaction, AuditLog
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Reset all user trading data while preserving accounts'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🔄 Starting user data reset...'))
        
        # Delete all trades (open and closed)
        trades_count = Trade.objects.all().count()
        Trade.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✅ Deleted {trades_count} trades'))
        
        # Delete ONLY trading-related transactions (trade P&L), preserve deposits/withdrawals
        trading_transactions_count = Transaction.objects.filter(type='trade_pnl').count()
        Transaction.objects.filter(type='trade_pnl').delete()
        self.stdout.write(self.style.SUCCESS(f'✅ Deleted {trading_transactions_count} trade P&L transactions'))
        
        # Preserve deposit/withdrawal history
        financial_transactions = Transaction.objects.filter(type__in=['deposit', 'withdrawal']).count()
        self.stdout.write(self.style.SUCCESS(f'✅ Preserved {financial_transactions} deposit/withdrawal records'))
        
        # Delete trading-related audit logs (optional - keep for security audit trail)
        # audit_count = AuditLog.objects.filter(action__in=['TRADE_OPEN', 'TRADE_CLOSE']).count()
        # AuditLog.objects.filter(action__in=['TRADE_OPEN', 'TRADE_CLOSE']).delete()
        # self.stdout.write(self.style.SUCCESS(f'✅ Deleted {audit_count} trading audit logs'))
        
        # Reset all user balances to initial amount (e.g., $10,000)
        initial_balance = Decimal('10000.00')
        users = User.objects.all()
        
        for user in users:
            user.usd_balance = initial_balance
            user.ai_trading_enabled = False  # Stop AI trading during reset
            user.save()
            self.stdout.write(f'   Reset {user.email}: balance=${initial_balance}, AI trading disabled')
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Reset complete! {users.count()} accounts preserved with ${initial_balance} balance'))
        self.stdout.write(self.style.WARNING('⚠️  Users can now re-enable AI trading and trade today'))
