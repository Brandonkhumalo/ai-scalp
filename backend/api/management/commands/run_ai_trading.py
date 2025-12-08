import os
import time
import random
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from api.ai_trading_engine import AITradingEngine
from api.ml_training_service import MLTradingModel
from api.position_reconciliation_service import PositionReconciliationService
from api.models import Trade, TradableInstrument
from api.market_hours_service import MarketHoursService

logger = logging.getLogger(__name__)
User = get_user_model()


class StockRotationManager:
    """Manages stock rotation and sleep mode for AI trading"""
    
    def __init__(self):
        self.user_states = {}
        self.market_hours = MarketHoursService()
        self.last_market_state = {}
    
    def _get_user_state(self, user_id: int) -> dict:
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                'available_stocks': set(),
                'sleep_mode': True,
                'last_wake_reason': None,
                'session_initialized': False,
            }
        return self.user_states[user_id]
    
    def initialize_available_stocks(self, user_id: int, stdout=None) -> set:
        state = self._get_user_state(user_id)
        
        BLACKLISTED_SYMBOLS = ['GEV']
        all_stocks = set(TradableInstrument.objects.filter(
            is_active=True,
            market='US'
        ).values_list('symbol', flat=True))
        
        if not all_stocks:
            all_stocks = {'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN', 'NFLX', 'AMD', 'INTC'}
        
        all_stocks = all_stocks - set(BLACKLISTED_SYMBOLS)
        
        open_position_symbols = set(Trade.objects.filter(
            user_id=user_id,
            status='open',
            instrument_type='stock'
        ).values_list('symbol', flat=True))
        
        available_stocks = all_stocks - open_position_symbols
        
        state['available_stocks'] = available_stocks
        state['session_initialized'] = True
        state['sleep_mode'] = len(available_stocks) == 0
        
        if stdout:
            stdout.write(f'   📋 Stock Rotation: Initialized {len(available_stocks)} available stocks')
            stdout.write(f'      Total pool: {len(all_stocks)}, Open positions: {len(open_position_symbols)}')
        
        return available_stocks
    
    def remove_stock_from_rotation(self, user_id: int, symbol: str, stdout=None):
        state = self._get_user_state(user_id)
        
        if symbol in state['available_stocks']:
            state['available_stocks'].discard(symbol)
            remaining = len(state['available_stocks'])
            
            if stdout:
                stdout.write(f'   🔄 Removed {symbol} from rotation ({remaining} remaining)')
            
            if remaining == 0:
                state['sleep_mode'] = True
                if stdout:
                    stdout.write('   💤 SLEEP MODE: No stocks left to trade')
    
    def add_stock_to_rotation(self, user_id: int, symbol: str, stdout=None):
        state = self._get_user_state(user_id)
        
        if state['session_initialized'] and symbol not in state['available_stocks']:
            state['available_stocks'].add(symbol)
            available_count = len(state['available_stocks'])
            
            if stdout:
                stdout.write(f'   🔄 Added {symbol} back to rotation ({available_count} available)')
            
            if state['sleep_mode']:
                state['sleep_mode'] = False
                state['last_wake_reason'] = f'Position closed: {symbol}'
                if stdout:
                    stdout.write(f'   🌅 WAKE UP: Position closed - AI resuming')
    
    def check_manually_closed_trades(self, user_id: int, stdout=None):
        """Check for any closed positions and add them back to rotation if not already present"""
        state = self._get_user_state(user_id)
        
        if not state['session_initialized']:
            return
        
        BLACKLISTED_SYMBOLS = ['GEV']
        all_stocks = set(TradableInstrument.objects.filter(
            is_active=True,
            market='US'
        ).values_list('symbol', flat=True))
        
        if not all_stocks:
            all_stocks = {'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN', 'NFLX', 'AMD', 'INTC'}
        
        all_stocks = all_stocks - set(BLACKLISTED_SYMBOLS)
        
        open_position_symbols = set(Trade.objects.filter(
            user_id=user_id,
            status='open',
            instrument_type='stock'
        ).values_list('symbol', flat=True))
        
        should_be_available = all_stocks - open_position_symbols
        
        for symbol in should_be_available:
            if symbol not in state['available_stocks']:
                self.add_stock_to_rotation(user_id, symbol, stdout)
    
    def reinitialize_if_sleep_but_stocks_available(self, user_id: int, stdout=None):
        """Reinitialize rotation if in sleep mode but stocks should be available"""
        state = self._get_user_state(user_id)
        
        if not state['sleep_mode']:
            return
        
        open_positions = Trade.objects.filter(
            user_id=user_id,
            status='open',
            instrument_type='stock'
        ).count()
        
        BLACKLISTED_SYMBOLS = ['GEV']
        all_stocks = set(TradableInstrument.objects.filter(
            is_active=True,
            market='US'
        ).values_list('symbol', flat=True))
        
        if not all_stocks:
            all_stocks = {'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN', 'NFLX', 'AMD', 'INTC'}
        
        all_stocks_count = len(all_stocks - set(BLACKLISTED_SYMBOLS))
        
        if open_positions < all_stocks_count:
            if stdout:
                stdout.write(f'   🔄 Sleep mode detected but stocks available - reinitializing')
            self.initialize_available_stocks(user_id, stdout)
            state['sleep_mode'] = False
            state['last_wake_reason'] = 'Stocks became available'
    
    def handle_market_session_change(self, user_id: int, market: str, is_now_open: bool, was_open: bool, stdout=None):
        state = self._get_user_state(user_id)
        
        if is_now_open and not was_open:
            if stdout:
                stdout.write(f'   🔔 SESSION OPEN: {market} market opened')
            self.initialize_available_stocks(user_id, stdout)
            state['sleep_mode'] = False
            state['last_wake_reason'] = f'{market} market session opened'
            if stdout:
                stdout.write(f'   🌅 WAKE UP: Market session started')
                
        elif not is_now_open and was_open:
            state['sleep_mode'] = True
            state['session_initialized'] = False
            state['available_stocks'].clear()
            if stdout:
                stdout.write(f'   🌙 SESSION CLOSED: {market} market closed - AI sleeping')
    
    def is_in_sleep_mode(self, user_id: int) -> bool:
        return self._get_user_state(user_id)['sleep_mode']
    
    def get_available_stocks(self, user_id: int) -> list:
        return list(self._get_user_state(user_id)['available_stocks'])
    
    def check_market_session_changes(self, stdout=None) -> dict:
        market_summary = self.market_hours.get_market_summary()
        current_market_state = {
            market_id: status['is_open'] 
            for market_id, status in market_summary['markets_status'].items()
        }
        
        market_changes = {}
        for market_id in current_market_state:
            is_now_open = current_market_state.get(market_id, False)
            was_open = self.last_market_state.get(market_id, False)
            if is_now_open != was_open:
                market_changes[market_id] = {'is_now_open': is_now_open, 'was_open': was_open}
        
        self.last_market_state = current_market_state
        return market_changes


class Command(BaseCommand):
    help = 'Run AI trading scheduler with stock rotation and sleep mode (24/7)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🤖 AI Trading Scheduler Started (Stock Rotation Mode)'))
        self.stdout.write('Monitoring users with AI trading enabled...')
        
        alpaca_api_key = os.getenv('ALPACA_API_KEY')
        alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not alpaca_api_key or not alpaca_api_secret:
            self.stdout.write(self.style.ERROR('❌ Alpaca API credentials not configured'))
            return
        
        engine = AITradingEngine(alpaca_api_key, alpaca_api_secret)
        ml_model = MLTradingModel()
        reconciliation_service = PositionReconciliationService()
        rotation_manager = StockRotationManager()
        last_retrain_check = {}
        market_hours = MarketHoursService()
        
        while True:
            try:
                market_summary = market_hours.get_market_summary()
                open_markets = market_summary['open_markets']
                
                market_changes = rotation_manager.check_market_session_changes(self.stdout)
                
                users = User.objects.filter(ai_trading_enabled=True)
                
                if not users.exists():
                    self.stdout.write('⏸️  No users with AI trading enabled (waiting 30s...)')
                    time.sleep(30)
                    continue
                
                for user in users:
                    try:
                        for market_id, change in market_changes.items():
                            rotation_manager.handle_market_session_change(
                                user.id, market_id, 
                                change['is_now_open'], change['was_open'],
                                self.stdout
                            )
                        
                        reconcile_result = reconciliation_service.reconcile_user_positions(user, verbose=False)
                        if reconcile_result.get('ghosts_removed', 0) > 0:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'🔄 Reconciled {user.email}: Removed {reconcile_result["ghosts_removed"]} ghost positions'
                                )
                            )
                        
                        user_id = str(user.id)
                        last_training = last_retrain_check.get(user_id)
                        closed_trades_count = Trade.objects.filter(user=user, status='closed').count()
                        
                        if ml_model.should_retrain(last_training, closed_trades_count):
                            self.stdout.write(f'🧠 Retraining ML model for {user.email}...')
                            user_trades = list(Trade.objects.filter(user=user, status='closed').order_by('-created_at'))
                            
                            if user_trades:
                                retrain_result = ml_model.train(user_trades)
                                if retrain_result.get('success'):
                                    last_retrain_check[user_id] = datetime.now()
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'✅ ML Model retrained for {user.email}: '
                                            f'Accuracy={retrain_result.get("test_accuracy", 0):.2%}, '
                                            f'Trades={retrain_result.get("trades_count", 0)}'
                                        )
                                    )
                        
                        scalping_result = engine.check_scalping_targets(user)
                        if scalping_result.get('action') == 'scalping_auto_close':
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'💰 SCALPING: {user.email} - {scalping_result.get("message")}'
                                )
                            )
                            for symbol in scalping_result.get('closed_symbols', []):
                                rotation_manager.add_stock_to_rotation(user.id, symbol, self.stdout)
                        
                        rotation_manager.check_manually_closed_trades(user.id, self.stdout)
                        
                        state = rotation_manager._get_user_state(user.id)
                        if not state['session_initialized']:
                            self.stdout.write(f'   📋 Initializing stock rotation for {user.email}')
                            rotation_manager.initialize_available_stocks(user.id, self.stdout)
                        
                        rotation_manager.reinitialize_if_sleep_but_stocks_available(user.id, self.stdout)
                        
                        if rotation_manager.is_in_sleep_mode(user.id):
                            self.stdout.write(f'💤 {user.email}: SLEEP MODE (0 stocks available)')
                            self.stdout.write(f'   Wake triggers: Position close or market session open')
                            continue
                        
                        available_stocks = rotation_manager.get_available_stocks(user.id)
                        
                        if not available_stocks:
                            state['sleep_mode'] = True
                            self.stdout.write(f'💤 {user.email}: No stocks left - entering sleep mode')
                            continue
                        
                        self.stdout.write(f'📋 {user.email}: {len(available_stocks)} stocks available for trading')
                        
                        symbol = random.choice(available_stocks)
                        
                        self.stdout.write(f'📊 Analyzing {symbol} (stock) for {user.email}...')
                        
                        result = engine.execute_ai_trade(user, symbol, instrument_type='stock')
                        
                        if result.get('analysis'):
                            analysis = result['analysis']
                            self.stdout.write(
                                f'   📊 {symbol}: Signal={analysis.get("signal", "NONE")}, '
                                f'Confidence={analysis.get("confidence", 0)}%, '
                                f'RSI={analysis.get("rsi", 0):.1f}'
                            )
                        
                        if result.get('success'):
                            rotation_manager.remove_stock_from_rotation(user.id, symbol, self.stdout)
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✅ {user.email}: {symbol} (stock) - Trade executed!'
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
                
                time.sleep(12)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n🛑 AI Trading Scheduler Stopped'))
                break
            except Exception as e:
                logger.error(f'Error in AI trading loop: {str(e)}')
                self.stdout.write(self.style.ERROR(f'❌ Loop error: {str(e)}'))
                time.sleep(30)
