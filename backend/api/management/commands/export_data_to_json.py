import json
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from accounts.models import User
from api.models import Trade, Transaction

class Command(BaseCommand):
    help = 'Export all data to JSON file for migration'

    def handle(self, *args, **options):
        self.stdout.write('📦 Exporting database to JSON...\n')
        
        data = {
            'users': [],
            'trades': [],
            'transactions': []
        }
        
        self.stdout.write('Exporting users...')
        for user in User.objects.all():
            data['users'].append({
                'id': user.id,
                'password': user.password,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'is_superuser': user.is_superuser,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'is_staff': user.is_staff,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat(),
                'phone': user.phone,
                'full_name': user.full_name,
                'usd_balance': str(user.usd_balance),
                'zwl_balance': str(user.zwl_balance),
                'ai_trading_enabled': user.ai_trading_enabled,
                'approval_status': user.approval_status,
                'approved_by_id': user.approved_by_id,
                'approved_at': user.approved_at.isoformat() if user.approved_at else None,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None,
            })
        self.stdout.write(f'  ✓ Exported {len(data["users"])} users')
        
        self.stdout.write('Exporting trades...')
        for trade in Trade.objects.all():
            data['trades'].append({
                'id': trade.id,
                'user_id': trade.user_id,
                'instrument_type': trade.instrument_type,
                'symbol': trade.symbol,
                'underlying_asset': trade.underlying_asset,
                'option_type': trade.option_type,
                'strike_price': str(trade.strike_price) if trade.strike_price else None,
                'expiration_date': trade.expiration_date.isoformat() if trade.expiration_date else None,
                'quantity': str(trade.quantity),
                'premium': str(trade.premium) if trade.premium else None,
                'entry_price': str(trade.entry_price),
                'exit_price': str(trade.exit_price) if trade.exit_price else None,
                'side': trade.side,
                'status': trade.status,
                'profit_loss': str(trade.profit_loss) if trade.profit_loss else None,
                'ai_confidence': trade.ai_confidence,
                'ai_signal_type': trade.ai_signal_type,
                'created_at': trade.created_at.isoformat(),
                'closed_at': trade.closed_at.isoformat() if trade.closed_at else None,
            })
        self.stdout.write(f'  ✓ Exported {len(data["trades"])} trades')
        
        self.stdout.write('Exporting transactions...')
        for txn in Transaction.objects.all():
            data['transactions'].append({
                'id': txn.id,
                'user_id': txn.user_id,
                'type': txn.type,
                'amount': str(txn.amount),
                'currency': txn.currency,
                'payment_method': txn.payment_method,
                'reference': txn.reference,
                'status': txn.status,
                'created_at': txn.created_at.isoformat(),
                'updated_at': txn.updated_at.isoformat(),
            })
        self.stdout.write(f'  ✓ Exported {len(data["transactions"])} transactions')
        
        output_file = 'production_data_export.json'
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, cls=DjangoJSONEncoder)
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Data exported to {output_file}'))
        self.stdout.write(f'\n📊 Summary:')
        self.stdout.write(f'  • Users: {len(data["users"])}')
        self.stdout.write(f'  • Trades: {len(data["trades"])}')
        self.stdout.write(f'  • Transactions: {len(data["transactions"])}')
        self.stdout.write(f'\n📥 Download this file and run import_data_from_json to load it into development')
