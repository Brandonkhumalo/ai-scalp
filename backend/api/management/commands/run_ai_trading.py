import os
import time
import random
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.ai_trading_engine import AITradingEngine
from api.ml_training_service import MLTradingModel
from api.position_reconciliation_service import PositionReconciliationService
from api.models import Trade

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Run AI trading scheduler in background (24/7)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🤖 AI Trading Scheduler Started'))
        self.stdout.write('Monitoring users with AI trading enabled...')
        
        alpaca_api_key = os.getenv('ALPACA_API_KEY')
        alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not alpaca_api_key or not alpaca_api_secret:
            self.stdout.write(self.style.ERROR('❌ Alpaca API credentials not configured'))
            return
        
        engine = AITradingEngine(alpaca_api_key, alpaca_api_secret)
        ml_model = MLTradingModel()
        reconciliation_service = PositionReconciliationService()
        last_retrain_check = {}
        
        # Trading symbols: Equities only (stocks during market hours)
        stock_symbols = ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'AMZN', 'NVDA', 'META', 'NFLX', 'AMD', 'INTC']
        
        while True:
            try:
                # Find all users with AI trading enabled
                # Note: Balance is tracked in Alpaca account, not in User model
                users = User.objects.filter(ai_trading_enabled=True)
                
                if not users.exists():
                    self.stdout.write('⏸️  No users with AI trading enabled (waiting 30s...)')
                    time.sleep(30)
                    continue
                
                for user in users:
                    try:
                        # 🔄 AUTO-RECONCILIATION: Sync database with Alpaca positions (removes ghosts)
                        reconcile_result = reconciliation_service.reconcile_user_positions(user, verbose=False)
                        if reconcile_result.get('ghosts_removed', 0) > 0:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'🔄 Reconciled {user.email}: Removed {reconcile_result["ghosts_removed"]} ghost positions'
                                )
                            )
                        
                        # 🧠 ML RETRAINING: Check if model should be retrained for this user
                        user_id = str(user.id)
                        last_training = last_retrain_check.get(user_id)
                        closed_trades_count = Trade.objects.filter(user=user, status='closed').count()
                        
                        if ml_model.should_retrain(last_training, closed_trades_count):
                            self.stdout.write(f'🧠 Retraining ML model for {user.email}...')
                            # Convert to list to avoid "Cannot filter after slice" error
                            # FIXED: Use ALL closed trades (not just newest 100) to include losing trades
                            user_trades = list(Trade.objects.filter(user=user, status='closed').order_by('-created_at'))
                            
                            if user_trades:
                                retrain_result = ml_model.train(user_trades)
                                if retrain_result.get('success'):
                                    last_retrain_check[user_id] = datetime.now()
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'✅ ML Model retrained for {user.email}: '
                                            f'Accuracy={retrain_result.get("test_accuracy", 0):.2%}, '
                                            f'Trades={retrain_result.get("trades_count", 0)} '
                                            f'(Next retrain in 24h)'
                                        )
                                    )
                                else:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f'⚠️  ML retraining skipped for {user.email}: {retrain_result.get("error", "Unknown error")}'
                                        )
                                    )
                        
                        # 🎯 SCALPING: Check and auto-close positions at profit/loss targets first
                        scalping_result = engine.check_scalping_targets(user)
                        if scalping_result.get('action') == 'scalping_auto_close':
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'💰 SCALPING: {user.email} - {scalping_result.get("message")}'
                                )
                            )
                        
                        # 🎯 SMART SYMBOL SELECTION: Prioritize NEW symbols for diversity
                        # Get symbols already in portfolio FROM ALPACA (source of truth - prevents duplicate buys!)
                        from api.alpaca_account_service import AlpacaAccountService
                        alpaca_service_temp = AlpacaAccountService()
                        alpaca_positions = alpaca_service_temp.get_positions(user)
                        existing_symbols = {pos['symbol'] for pos in alpaca_positions}
                        
                        # Prefer NEW symbols (not in portfolio) to build diversity first
                        new_symbols = [s for s in stock_symbols if s not in existing_symbols]
                        
                        if new_symbols:
                            # Prioritize new symbols to maximize portfolio diversity
                            symbol = random.choice(new_symbols)
                        else:
                            # All symbols held, pick any (will be subject to 40% concentration limit)
                            symbol = random.choice(stock_symbols)
                        
                        instrument_type = 'stock'
                        
                        self.stdout.write(f'📊 Analyzing {symbol} (stock) for {user.email}...')
                        
                        # Execute AI trade
                        result = engine.execute_ai_trade(user, symbol, instrument_type)
                        
                        # Show detailed analysis for debugging
                        if result.get('analysis'):
                            analysis = result['analysis']
                            self.stdout.write(
                                f'   📊 {symbol}: Signal={analysis.get("signal", "NONE")}, '
                                f'Confidence={analysis.get("confidence", 0)}%, '
                                f'RSI={analysis.get("rsi", 0):.1f}, '
                                f'MACD={analysis.get("macd_histogram", 0):.4f}'
                            )
                        
                        self.stdout.write(f'📈 Result: {result}')
                        
                        if result.get('success'):
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✅ {user.email}: {symbol} (stock) - {result.get("message", "Trade executed")}'
                                )
                            )
                        else:
                            message = result.get('message', 'Unknown error')
                            if 'No clear trading signal' not in message and 'Insufficient' not in message:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'⚠️  {user.email}: {symbol} - {message}'
                                    )
                                )
                    
                    except Exception as e:
                        logger.exception(f'Error executing trade for {user.email}')
                        self.stdout.write(
                            self.style.ERROR(f'❌ {user.email}: {str(e)}')
                        )
                
                # Wait 12 seconds before next trading cycle
                time.sleep(12)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n🛑 AI Trading Scheduler Stopped'))
                break
            except Exception as e:
                logger.error(f'Error in AI trading loop: {str(e)}')
                self.stdout.write(self.style.ERROR(f'❌ Loop error: {str(e)}'))
                time.sleep(30)
