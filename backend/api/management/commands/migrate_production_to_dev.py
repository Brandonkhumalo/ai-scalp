import psycopg2
from django.core.management.base import BaseCommand
from django.db import connection
from accounts.models import User
from api.models import Trade, Transaction

class Command(BaseCommand):
    help = 'Migrate production PostgreSQL data to development SQLite database'

    def handle(self, *args, **options):
        prod_db_params = {
            'host': 'ep-shy-boat-aeo1un3f.c-2.us-east-2.aws.neon.tech',
            'database': 'neondb',
            'user': 'neondb_owner',
            'password': 'npg_m7TDCFqk4xHE',
            'port': 5432,
            'sslmode': 'require',
            'connect_timeout': 30
        }
        
        self.stdout.write(self.style.WARNING('⚠️  Starting production to development migration...'))
        self.stdout.write(self.style.WARNING('⚠️  This will REPLACE all data in your development database!'))
        
        try:
            self.stdout.write('Connecting to production PostgreSQL database...')
            self.stdout.write(f'Host: {prod_db_params["host"]}')
            self.stdout.write(f'Database: {prod_db_params["database"]}')
            prod_conn = psycopg2.connect(**prod_db_params)
            prod_cursor = prod_conn.cursor()
            
            self.stdout.write(self.style.SUCCESS('✓ Connected to production database'))
            
            self.stdout.write('\nClearing development database...')
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM api_transaction')
                cursor.execute('DELETE FROM api_trade')
                cursor.execute('DELETE FROM accounts_user')
            
            self.stdout.write(self.style.SUCCESS('✓ Development database cleared'))
            
            self.stdout.write('\n=== Migrating Users ===')
            prod_cursor.execute('''
                SELECT id, password, last_login, is_superuser, username, first_name, 
                       last_name, email, is_staff, is_active, date_joined, phone, 
                       full_name, usd_balance, zwl_balance, ai_trading_enabled, 
                       approval_status, approved_by_id, approved_at, created_at, updated_at 
                FROM accounts_user ORDER BY id
            ''')
            users = prod_cursor.fetchall()
            
            user_count = 0
            for user_data in users:
                User.objects.create(
                    id=user_data[0],
                    password=user_data[1],
                    last_login=user_data[2],
                    is_superuser=user_data[3],
                    username=user_data[4],
                    first_name=user_data[5],
                    last_name=user_data[6],
                    email=user_data[7],
                    is_staff=user_data[8],
                    is_active=user_data[9],
                    date_joined=user_data[10],
                    phone=user_data[11],
                    full_name=user_data[12],
                    usd_balance=user_data[13],
                    zwl_balance=user_data[14],
                    ai_trading_enabled=user_data[15],
                    approval_status=user_data[16],
                    approved_by_id=user_data[17],
                    approved_at=user_data[18],
                    created_at=user_data[19],
                    updated_at=user_data[20]
                )
                user_count += 1
                self.stdout.write(f'  ✓ Migrated user: {user_data[7]} (Balance: ${user_data[13]})')
            
            self.stdout.write(self.style.SUCCESS(f'✓ Migrated {user_count} users'))
            
            self.stdout.write('\n=== Migrating Trades ===')
            prod_cursor.execute('''
                SELECT id, user_id, instrument_type, symbol, underlying_asset, option_type, 
                       strike_price, expiration_date, quantity, premium, entry_price, 
                       exit_price, side, status, profit_loss, ai_confidence, ai_signal_type, 
                       created_at, closed_at 
                FROM api_trade ORDER BY id
            ''')
            trades = prod_cursor.fetchall()
            
            trade_count = 0
            for trade_data in trades:
                Trade.objects.create(
                    id=trade_data[0],
                    user_id=trade_data[1],
                    instrument_type=trade_data[2],
                    symbol=trade_data[3],
                    underlying_asset=trade_data[4],
                    option_type=trade_data[5],
                    strike_price=trade_data[6],
                    expiration_date=trade_data[7],
                    quantity=trade_data[8],
                    premium=trade_data[9],
                    entry_price=trade_data[10],
                    exit_price=trade_data[11],
                    side=trade_data[12],
                    status=trade_data[13],
                    profit_loss=trade_data[14],
                    ai_confidence=trade_data[15],
                    ai_signal_type=trade_data[16],
                    created_at=trade_data[17],
                    closed_at=trade_data[18]
                )
                trade_count += 1
                if trade_count <= 5:
                    pnl_str = f"P&L: ${trade_data[14]}" if trade_data[14] else "Open"
                    self.stdout.write(f'  ✓ Migrated trade: {trade_data[3]} {trade_data[12]} @ ${trade_data[10]} ({pnl_str})')
            
            if trade_count > 5:
                self.stdout.write(f'  ... and {trade_count - 5} more trades')
            self.stdout.write(self.style.SUCCESS(f'✓ Migrated {trade_count} trades'))
            
            self.stdout.write('\n=== Migrating Transactions ===')
            prod_cursor.execute('''
                SELECT id, user_id, type, amount, currency, payment_method, reference, 
                       status, created_at, updated_at 
                FROM api_transaction ORDER BY id
            ''')
            transactions = prod_cursor.fetchall()
            
            txn_count = 0
            for txn_data in transactions:
                Transaction.objects.create(
                    id=txn_data[0],
                    user_id=txn_data[1],
                    type=txn_data[2],
                    amount=txn_data[3],
                    currency=txn_data[4],
                    payment_method=txn_data[5],
                    reference=txn_data[6],
                    status=txn_data[7],
                    created_at=txn_data[8],
                    updated_at=txn_data[9]
                )
                txn_count += 1
                if txn_count <= 3:
                    self.stdout.write(f'  ✓ Migrated transaction: {txn_data[2]} ${txn_data[3]} {txn_data[4]}')
            
            if txn_count > 3:
                self.stdout.write(f'  ... and {txn_count - 3} more transactions')
            self.stdout.write(self.style.SUCCESS(f'✓ Migrated {txn_count} transactions'))
            
            prod_cursor.close()
            prod_conn.close()
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('✅ MIGRATION COMPLETE!'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(f'\n📊 Summary:')
            self.stdout.write(f'  • Users: {user_count}')
            self.stdout.write(f'  • Trades: {trade_count}')
            self.stdout.write(f'  • Transactions: {txn_count}')
            self.stdout.write(f'\n✅ Your production data is now in backend/db.sqlite3')
            self.stdout.write(f'✅ You can download the workspace and analyze it locally!')
            self.stdout.write(self.style.WARNING('\n⚠️  SECURITY REMINDER: Rotate your production database password!'))
            self.stdout.write(self.style.WARNING('   Go to your Neon dashboard and reset the password.'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Migration failed: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise
