import json
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from accounts.models import User
from api.models import Trade, Transaction

class Command(BaseCommand):
    help = 'Import data from JSON file exported from production'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='production_data_export.json',
            help='JSON file to import (default: production_data_export.json)'
        )

    def handle(self, *args, **options):
        filename = options['file']
        
        self.stdout.write(self.style.WARNING('⚠️  This will REPLACE all data in your development database!'))
        
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            self.stdout.write(f'\n📦 Loaded data from {filename}')
            self.stdout.write(f'  • Users: {len(data["users"])}')
            self.stdout.write(f'  • Trades: {len(data["trades"])}')
            self.stdout.write(f'  • Transactions: {len(data["transactions"])}')
            
            with transaction.atomic():
                self.stdout.write('\nClearing development database...')
                with connection.cursor() as cursor:
                    cursor.execute('DELETE FROM api_transaction')
                    cursor.execute('DELETE FROM api_trade')
                    cursor.execute('DELETE FROM accounts_user')
                
                self.stdout.write(self.style.SUCCESS('✓ Database cleared'))
                
                self.stdout.write('\n=== Importing Users ===')
                for user_data in data['users']:
                    User.objects.create(
                        id=user_data['id'],
                        password=user_data['password'],
                        last_login=datetime.fromisoformat(user_data['last_login']) if user_data['last_login'] else None,
                        is_superuser=user_data['is_superuser'],
                        username=user_data['username'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name'],
                        email=user_data['email'],
                        is_staff=user_data['is_staff'],
                        is_active=user_data['is_active'],
                        date_joined=datetime.fromisoformat(user_data['date_joined']),
                        phone=user_data['phone'],
                        full_name=user_data['full_name'],
                        usd_balance=Decimal(user_data['usd_balance']),
                        zwl_balance=Decimal(user_data['zwl_balance']),
                        ai_trading_enabled=user_data['ai_trading_enabled'],
                        approval_status=user_data['approval_status'],
                        approved_by_id=user_data['approved_by_id'],
                        approved_at=datetime.fromisoformat(user_data['approved_at']) if user_data['approved_at'] else None,
                        created_at=datetime.fromisoformat(user_data['created_at']) if user_data['created_at'] else None,
                        updated_at=datetime.fromisoformat(user_data['updated_at']) if user_data['updated_at'] else None,
                    )
                    self.stdout.write(f'  ✓ Imported user: {user_data["email"]} (Balance: ${user_data["usd_balance"]})')
                
                self.stdout.write(self.style.SUCCESS(f'✓ Imported {len(data["users"])} users'))
                
                self.stdout.write('\n=== Importing Trades ===')
                for trade_data in data['trades']:
                    Trade.objects.create(
                        id=trade_data['id'],
                        user_id=trade_data['user_id'],
                        instrument_type=trade_data['instrument_type'],
                        symbol=trade_data['symbol'],
                        underlying_asset=trade_data['underlying_asset'],
                        option_type=trade_data['option_type'],
                        strike_price=Decimal(trade_data['strike_price']) if trade_data['strike_price'] else None,
                        expiration_date=datetime.fromisoformat(trade_data['expiration_date']).date() if trade_data['expiration_date'] else None,
                        quantity=Decimal(trade_data['quantity']),
                        premium=Decimal(trade_data['premium']) if trade_data['premium'] else None,
                        entry_price=Decimal(trade_data['entry_price']),
                        exit_price=Decimal(trade_data['exit_price']) if trade_data['exit_price'] else None,
                        side=trade_data['side'],
                        status=trade_data['status'],
                        profit_loss=Decimal(trade_data['profit_loss']) if trade_data['profit_loss'] else None,
                        ai_confidence=trade_data['ai_confidence'],
                        ai_signal_type=trade_data['ai_signal_type'],
                        created_at=datetime.fromisoformat(trade_data['created_at']),
                        closed_at=datetime.fromisoformat(trade_data['closed_at']) if trade_data['closed_at'] else None,
                    )
                
                self.stdout.write(self.style.SUCCESS(f'✓ Imported {len(data["trades"])} trades'))
                
                self.stdout.write('\n=== Importing Transactions ===')
                for txn_data in data['transactions']:
                    Transaction.objects.create(
                        id=txn_data['id'],
                        user_id=txn_data['user_id'],
                        type=txn_data['type'],
                        amount=Decimal(txn_data['amount']),
                        currency=txn_data['currency'],
                        payment_method=txn_data['payment_method'],
                        reference=txn_data['reference'],
                        status=txn_data['status'],
                        created_at=datetime.fromisoformat(txn_data['created_at']),
                        updated_at=datetime.fromisoformat(txn_data['updated_at']),
                    )
                
                self.stdout.write(self.style.SUCCESS(f'✓ Imported {len(data["transactions"])} transactions'))
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('✅ IMPORT COMPLETE!'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(f'\n📊 Final Summary:')
            self.stdout.write(f'  • Users: {len(data["users"])}')
            self.stdout.write(f'  • Trades: {len(data["trades"])}')
            self.stdout.write(f'  • Transactions: {len(data["transactions"])}')
            self.stdout.write(f'\n✅ Your production data is now in db.sqlite3')
            self.stdout.write(f'✅ You can download the workspace and analyze it locally!')
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'\n❌ File not found: {filename}'))
            self.stdout.write('Please make sure the JSON export file is in the backend/ directory')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Import failed: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise
