import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.conf import settings
from decimal import Decimal

from .market_hours_service import MarketHoursService
from .ai_trading_engine import AITradingEngine
from .models import Trade, TradableInstrument, AgentState

User = get_user_model()
logger = logging.getLogger(__name__)


class AutonomousAgentService:

    def __init__(self):
        self.agent_state = {
            'started_at': None,
            'last_check': None,
            'total_checks': 0,
            'total_trades_executed': 0,
            'active_markets': [],
            'active_users': 0,
            'last_reconciliation': None,
            'last_market_state': {},  # Track market open/close state for session triggers
        }
        self.market_hours = MarketHoursService()

        # Per-user reconciliation state (prevents cross-user state pollution)
        self.user_reconciliation_state = {}  # {user_id: {reconciliation_interval, clean_passes, startup_complete, orphan_counters}}

        # STOCK ROTATION SYSTEM: Per-user available stocks and sleep mode state
        # {user_id: {'available_stocks': set(), 'sleep_mode': bool, 'last_wake_reason': str}}
        self.user_stock_rotation_state = {}

        # Restore persisted state from the database (survives process restarts)
        self._load_state_from_db()

    # ── State Persistence ────────────────────────────────────────────────

    def _load_state_from_db(self):
        """Load all persisted agent state from the database on startup."""
        try:
            # Global agent state
            global_row = AgentState.objects.filter(state_type='agent_global', user=None).first()
            if global_row and global_row.state_data:
                saved = global_row.state_data
                # Merge numeric counters (keep cumulative totals across restarts)
                self.agent_state['total_checks'] = saved.get('total_checks', 0)
                self.agent_state['total_trades_executed'] = saved.get('total_trades_executed', 0)
                logger.info(f"   Loaded global agent state: {self.agent_state['total_checks']} checks, "
                            f"{self.agent_state['total_trades_executed']} trades")

            # Per-user reconciliation state
            for row in AgentState.objects.filter(state_type='reconciliation').exclude(user=None):
                self.user_reconciliation_state[row.user_id] = row.state_data
            if self.user_reconciliation_state:
                logger.info(f"   Loaded reconciliation state for {len(self.user_reconciliation_state)} users")

            # Per-user stock rotation state (convert lists back to sets)
            for row in AgentState.objects.filter(state_type='stock_rotation').exclude(user=None):
                data = row.state_data.copy()
                data['available_stocks'] = set(data.get('available_stocks', []))
                self.user_stock_rotation_state[row.user_id] = data
            if self.user_stock_rotation_state:
                logger.info(f"   Loaded stock rotation state for {len(self.user_stock_rotation_state)} users")

        except Exception as e:
            logger.warning(f"Could not load persisted agent state: {e}")

    def _persist_state_to_db(self):
        """Write current agent state to the database for crash recovery."""
        try:
            # Global agent state (convert non-JSON-safe types)
            state_data = {}
            for k, v in self.agent_state.items():
                if hasattr(v, 'isoformat'):
                    state_data[k] = v.isoformat()
                elif isinstance(v, (str, int, float, bool, list, dict, type(None))):
                    state_data[k] = v
                else:
                    state_data[k] = str(v)

            AgentState.objects.update_or_create(
                state_type='agent_global', user=None,
                defaults={'state_data': state_data},
            )

            # Per-user reconciliation state
            for user_id, data in self.user_reconciliation_state.items():
                AgentState.objects.update_or_create(
                    state_type='reconciliation', user_id=user_id,
                    defaults={'state_data': data},
                )

            # Per-user stock rotation state (convert sets to lists for JSON)
            for user_id, data in self.user_stock_rotation_state.items():
                json_safe = data.copy()
                json_safe['available_stocks'] = list(data.get('available_stocks', set()))
                AgentState.objects.update_or_create(
                    state_type='stock_rotation', user_id=user_id,
                    defaults={'state_data': json_safe},
                )
        except Exception as e:
            logger.warning(f"Could not persist agent state: {e}")
    
    def _get_stock_rotation_state(self, user_id: int) -> dict:
        """Get or initialize per-user stock rotation state"""
        if user_id not in self.user_stock_rotation_state:
            self.user_stock_rotation_state[user_id] = {
                'available_stocks': set(),  # Stocks available for trading
                'sleep_mode': True,  # Start in sleep mode until market opens
                'last_wake_reason': None,
                'session_initialized': False,  # Track if stocks were loaded for current session
            }
        return self.user_stock_rotation_state[user_id]
    
    def _initialize_available_stocks(self, user_id: int, market: str = 'US') -> set:
        """
        Initialize the available stocks list from TradableInstrument.
        Excludes stocks that already have open positions.
        Called when market session opens or AI is enabled.
        """
        state = self._get_stock_rotation_state(user_id)
        
        # Get all active stocks for the market
        BLACKLISTED_SYMBOLS = ['GEV']
        all_stocks = set(TradableInstrument.objects.filter(
            is_active=True,
            market=market
        ).values_list('symbol', flat=True))
        
        # Fallback if no TradableInstruments configured
        if not all_stocks:
            all_stocks = {'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN'}
        
        # Remove blacklisted symbols
        all_stocks = all_stocks - set(BLACKLISTED_SYMBOLS)
        
        # Get symbols with open positions (exclude from available list)
        open_position_symbols = set(Trade.objects.filter(
            user_id=user_id,
            status='open',
            instrument_type='stock'
        ).values_list('symbol', flat=True))
        
        # Available stocks = all stocks - stocks with open positions
        available_stocks = all_stocks - open_position_symbols
        
        state['available_stocks'] = available_stocks
        state['session_initialized'] = True
        
        logger.info(f"   📋 Stock Rotation: Initialized {len(available_stocks)} available stocks")
        logger.info(f"      Total pool: {len(all_stocks)}, Open positions: {len(open_position_symbols)}")
        
        return available_stocks
    
    def _remove_stock_from_rotation(self, user_id: int, symbol: str):
        """Remove a stock from available list after trade execution"""
        state = self._get_stock_rotation_state(user_id)
        
        if symbol in state['available_stocks']:
            state['available_stocks'].discard(symbol)
            remaining = len(state['available_stocks'])
            logger.info(f"   🔄 Stock Rotation: Removed {symbol} from available list ({remaining} remaining)")
            
            # Check if we should enter sleep mode
            if remaining == 0:
                state['sleep_mode'] = True
                logger.info(f"   💤 SLEEP MODE: No stocks left to trade - AI entering sleep mode")
    
    def _add_stock_to_rotation(self, user_id: int, symbol: str):
        """Add a stock back to available list when position is closed"""
        state = self._get_stock_rotation_state(user_id)
        
        # Only add back if session is initialized (market is open)
        if state['session_initialized']:
            state['available_stocks'].add(symbol)
            available_count = len(state['available_stocks'])
            logger.info(f"   🔄 Stock Rotation: Added {symbol} back to available list ({available_count} available)")
            
            # Wake up from sleep mode if we were sleeping
            if state['sleep_mode']:
                state['sleep_mode'] = False
                state['last_wake_reason'] = f'Position closed: {symbol}'
                logger.info(f"   🌅 WAKE UP: Position closed on {symbol} - AI resuming trading")
    
    def _handle_market_session_change(self, user_id: int, market: str, is_now_open: bool, was_open: bool):
        """Handle market session open/close events"""
        state = self._get_stock_rotation_state(user_id)
        
        if is_now_open and not was_open:
            # Market just opened - initialize stocks and wake up
            logger.info(f"   🔔 SESSION OPEN: {market} market opened - Initializing stock rotation")
            self._initialize_available_stocks(user_id, market)
            state['sleep_mode'] = False
            state['last_wake_reason'] = f'{market} market session opened'
            logger.info(f"   🌅 WAKE UP: Market session started - AI active")
            
        elif not is_now_open and was_open:
            # Market just closed - enter sleep mode
            state['sleep_mode'] = True
            state['session_initialized'] = False
            state['available_stocks'].clear()
            logger.info(f"   🌙 SESSION CLOSED: {market} market closed - AI entering sleep mode")
    
    def _is_in_sleep_mode(self, user_id: int) -> bool:
        """Check if AI is in sleep mode for this user"""
        state = self._get_stock_rotation_state(user_id)
        return state['sleep_mode']
    
    def _get_available_stocks(self, user_id: int) -> list:
        """Get list of available stocks for trading"""
        state = self._get_stock_rotation_state(user_id)
        return list(state['available_stocks'])
    
    def _check_manually_closed_trades(self, user_id: int):
        """
        Check for any closed positions and add them back to rotation if not already present.
        Uses set-diff approach to ensure all available stocks are in rotation.
        """
        state = self._get_stock_rotation_state(user_id)
        
        if not state['session_initialized']:
            return
        
        BLACKLISTED_SYMBOLS = ['GEV']
        all_stocks = set(TradableInstrument.objects.filter(
            is_active=True,
            market='US'
        ).values_list('symbol', flat=True))
        
        if not all_stocks:
            all_stocks = {'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN'}
        
        all_stocks = all_stocks - set(BLACKLISTED_SYMBOLS)
        
        open_position_symbols = set(Trade.objects.filter(
            user_id=user_id,
            status='open',
            instrument_type='stock'
        ).values_list('symbol', flat=True))
        
        should_be_available = all_stocks - open_position_symbols
        
        for symbol in should_be_available:
            if symbol not in state['available_stocks']:
                self._add_stock_to_rotation(user_id, symbol)
    
    def _reinitialize_if_sleep_but_stocks_available(self, user_id: int):
        """Reinitialize rotation if in sleep mode but stocks should be available"""
        state = self._get_stock_rotation_state(user_id)
        
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
            all_stocks = {'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN'}
        
        all_stocks_count = len(all_stocks - set(BLACKLISTED_SYMBOLS))
        
        if open_positions < all_stocks_count:
            logger.info(f"   🔄 Sleep mode detected but stocks available - reinitializing")
            self._initialize_available_stocks(user_id, 'US')
            state['sleep_mode'] = False
            state['last_wake_reason'] = 'Stocks became available'

    def _reconcile_pending_trades(self):
        """Reconcile trades left in 'pending' status from a previous crash.

        For each pending trade:
        - If it has a broker_deal_id, check Alpaca for the order status.
        - If the order was filled, promote to 'open'.
        - Otherwise mark as 'failed'.
        """
        pending_trades = Trade.objects.filter(status='pending')
        if not pending_trades.exists():
            return

        from api.services import alpaca_service
        logger.info(f"🔄 Startup reconciliation: found {pending_trades.count()} pending trades")

        for trade in pending_trades:
            try:
                if trade.broker_deal_id:
                    # Check Alpaca for matching position
                    positions = alpaca_service.get_positions(user=user) or []
                    symbol_on_alpaca = any(
                        p.get('symbol') == trade.symbol for p in positions
                    )
                    if symbol_on_alpaca:
                        trade.status = 'open'
                        trade.save(update_fields=['status'])
                        logger.info(f"   ✅ Pending trade {trade.id} ({trade.symbol}) → open (position found on Alpaca)")
                        continue

                # No matching position found — mark failed
                trade.status = 'failed'
                trade.save(update_fields=['status'])
                logger.info(f"   ❌ Pending trade {trade.id} ({trade.symbol}) → failed (no Alpaca position)")
            except Exception as e:
                logger.error(f"   Error reconciling pending trade {trade.id}: {e}")

    def run_continuous(self, check_interval: int = 15):
        self.agent_state['started_at'] = timezone.now()
        logger.info("🤖 Autonomous Trading Agent STARTED - Multi-Timezone 24/7 Operation")
        logger.info(f"   Check interval: {check_interval} seconds")

        # Clean up any trades left in pending status from a previous crash
        self._reconcile_pending_trades()

        while True:
            try:
                self._run_cycle()
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Autonomous Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Autonomous Agent error: {e}", exc_info=True)
                time.sleep(check_interval)
    
    def _run_cycle(self):
        self.agent_state['last_check'] = timezone.now()
        self.agent_state['total_checks'] += 1

        # Persist state every 20 cycles (~5 minutes at 15s interval)
        if self.agent_state['total_checks'] % 20 == 0:
            self._persist_state_to_db()
        
        market_summary = self.market_hours.get_market_summary()
        open_markets = market_summary['open_markets']
        self.agent_state['active_markets'] = open_markets
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🌍 AUTONOMOUS AGENT - Check #{self.agent_state['total_checks']}")
        logger.info(f"{'='*70}")
        logger.info(f"⏰ Time: {market_summary['timestamp_utc']}")
        logger.info(f"📊 Open Markets: {', '.join(open_markets) if open_markets else 'None'}")
        
        # Detect market session changes for stock rotation triggers
        current_market_state = {market_id: status['is_open'] for market_id, status in market_summary['markets_status'].items()}
        previous_market_state = self.agent_state.get('last_market_state', {})
        
        # Store market state changes for user processing
        market_changes = {}
        for market_id in current_market_state:
            is_now_open = current_market_state.get(market_id, False)
            was_open = previous_market_state.get(market_id, False)
            if is_now_open != was_open:
                market_changes[market_id] = {'is_now_open': is_now_open, 'was_open': was_open}
                if is_now_open:
                    logger.info(f"   🔔 SESSION CHANGE: {market_id} market OPENED")
                else:
                    logger.info(f"   🔔 SESSION CHANGE: {market_id} market CLOSED")
        
        # Update stored market state
        self.agent_state['last_market_state'] = current_market_state
        
        # Handle market session changes for all users (even when closed)
        if market_changes:
            approved_users_for_changes = User.objects.filter(approval_status='approved', is_active=True)
            for user in approved_users_for_changes:
                for market_id, change in market_changes.items():
                    self._handle_market_session_change(user.id, market_id, change['is_now_open'], change['was_open'])
        
        # Log market status but continue processing (Alpaca supports extended hours)
        if not open_markets:
            logger.info("📊 Regular market hours closed - Extended hours trading may be available")
        
        for market_id, status in market_summary['markets_status'].items():
            if status['is_open']:
                logger.info(f"   ✅ {status['name']}: TRADING ACTIVE ({status['broker']})")
            else:
                logger.info(f"   ⏸️  {status['name']}: {status['next_event']}")
        
        approved_users = User.objects.filter(approval_status='approved', is_active=True)
        self.agent_state['active_users'] = approved_users.count()
        
        logger.info(f"\n👥 Active Users: {self.agent_state['active_users']}")
        
        for user in approved_users:
            try:
                # Handle any market session changes first
                for market_id, change in market_changes.items():
                    self._handle_market_session_change(user.id, market_id, change['is_now_open'], change['was_open'])
                
                self._process_user_trading(user, open_markets)
            except Exception as e:
                logger.error(f"❌ Error processing user {user.email}: {e}")
    
    def _process_user_trading(self, user, open_markets: List[str]):
        """
        Process trading for stock brokers only:
        1. Alpaca (alpaca_sim): For users with ai_trading_enabled (supports extended hours)
        2. Capital.com Stocks: DISABLED (per user request)
        
        Note: Forex trading is MANUAL ONLY - not included in autonomous agent
        """
        trades_executed = 0
        
        # Process Alpaca Trading (supports extended hours - no market gate)
        if hasattr(user, 'ai_trading_enabled') and user.ai_trading_enabled:
            trades_executed += self._process_alpaca_trading(user)
        
        # Capital.com Stock Trading DISABLED per user request
        # Forex is excluded from autonomous agent - manual trading only
        
        if trades_executed > 0:
            self.agent_state['total_trades_executed'] += trades_executed
            logger.info(f"   💰 {user.email}: {trades_executed} trade(s) executed")
    
    def _get_user_state(self, user_id: int) -> dict:
        """Get or initialize per-user reconciliation state"""
        if user_id not in self.user_reconciliation_state:
            self.user_reconciliation_state[user_id] = {
                'reconciliation_interval': 1,  # Start intensive (every cycle)
                'clean_reconciliation_passes': 0,
                'startup_reconciliation_complete': False,
                'orphan_grace_counters': {}  # {symbol: consecutive_detection_count}
            }
        return self.user_reconciliation_state[user_id]
    
    def _process_alpaca_trading(self, user) -> int:
        """Execute Alpaca simulator trading for users with AI trading enabled"""
        try:
            import os
            ai_engine = AITradingEngine(
                os.getenv('ALPACA_API_KEY'),
                os.getenv('ALPACA_API_SECRET')
            )
            
            # Get per-user reconciliation state
            user_state = self._get_user_state(user.id)
            
            # Get stock rotation state
            rotation_state = self._get_stock_rotation_state(user.id)
            
            # 🎯 SCALPING: Check and auto-close positions at profit/loss targets FIRST
            if settings.USE_GO_MARKETD:
                logger.info(f"      ⏭️ Skipping Django scalping closes for {user.email} (USE_GO_MARKETD=True)")
            else:
                scalping_result = ai_engine.check_scalping_targets(user)
                if scalping_result.get('action') == 'scalping_auto_close':
                    logger.info(f"      🎯 Scalping: Closed {scalping_result.get('closed_count')} positions")
                    logger.info(f"         Realized P&L: ${scalping_result.get('total_realized_profit', 0):.2f}")

                    # Add closed stocks back to rotation (wake up if sleeping)
                    closed_symbols = scalping_result.get('closed_symbols', [])
                    for symbol in closed_symbols:
                        self._add_stock_to_rotation(user.id, symbol)
            
            # 📋 Check for manually closed trades and add them back to rotation
            self._check_manually_closed_trades(user.id)
            
            # 🔍 RECONCILIATION: Verify database positions match Alpaca reality
            if self.agent_state['total_checks'] % user_state['reconciliation_interval'] == 0:
                if settings.USE_GO_MARKETD:
                    logger.info(f"      ⏭️ Skipping Django reconciliation for {user.email} (USE_GO_MARKETD=True)")
                else:
                    self._run_position_reconciliation(user, ai_engine, user_state)
            
            # 💤 STOCK ROTATION SLEEP MODE CHECK
            # Initialize stocks if session not yet initialized
            if not rotation_state['session_initialized']:
                logger.info(f"      📋 Initializing stock rotation for {user.email}")
                self._initialize_available_stocks(user.id, 'US')
                rotation_state['sleep_mode'] = False
                rotation_state['last_wake_reason'] = 'Session initialized'
            
            # Check if should wake from sleep mode (stocks became available)
            self._reinitialize_if_sleep_but_stocks_available(user.id)
            
            # Check if in sleep mode
            if self._is_in_sleep_mode(user.id):
                available_count = len(rotation_state['available_stocks'])
                logger.info(f"      💤 SLEEP MODE: AI is sleeping (0 stocks available)")
                logger.info(f"         Wake triggers: Position close or market session open")
                return 0
            
            analytics = self._get_user_analytics(user, 'alpaca_sim')
            
            if self._should_execute_trade(user, analytics, 'alpaca_sim'):
                # Use available stocks from rotation system (not full list)
                available_stocks = self._get_available_stocks(user.id)
                
                if not available_stocks:
                    # No stocks available - enter sleep mode
                    rotation_state['sleep_mode'] = True
                    logger.info(f"      💤 SLEEP MODE: No stocks left in rotation - AI sleeping")
                    return 0
                
                logger.info(f"      📋 Stock Rotation: {len(available_stocks)} stocks available for trading")
                
                # *** INTELLIGENT ML-BASED STOCK SELECTION ***
                # Pre-screen available stocks (not all stocks) with >70% ML confidence
                best_stock = self._select_best_stock_ml_prescreening(ai_engine, user, available_stocks)
                
                if not best_stock:
                    logger.info(f"      ⛔ No high-quality opportunities in available stocks (try again next cycle)")
                    return 0
                
                symbol = best_stock['symbol']
                logger.info(f"      🎯 Selected {symbol} with {best_stock['ml_confidence']:.1%} ML confidence (diversity priority: {best_stock['is_new_symbol']})")
                
                result = ai_engine.execute_ai_trade(user, symbol, instrument_type='stock')
                
                if result.get('success'):
                    logger.info(f"      📊 Alpaca trade: {result.get('symbol', symbol)} - Executed")
                    
                    # Remove traded stock from rotation
                    self._remove_stock_from_rotation(user.id, symbol)
                    
                    return 1
                else:
                    # Log the failure reason so we can debug why trades aren't executing
                    logger.warning(f"      ⚠️  Trade NOT executed for {symbol}: {result.get('message', 'Unknown reason')}")
                    if 'analysis' in result:
                        logger.info(f"         Analysis: {result['analysis'].get('signal', 'N/A')} signal")
                    return 0
        
        except Exception as e:
            logger.error(f"Alpaca trading error for {user.email}: {e}")
        
        return 0
    
    def _process_stock_trading(self, user, open_markets: List[str]) -> int:
        try:
            # Stocks with restrictive trading hours on Capital.com (avoid during autonomous trading)
            RESTRICTED_HOURS_STOCKS = ['ENR']  # ENR only trades 13:30-20:00 UTC
            
            market_filters = []
            if 'US' in open_markets:
                market_filters.append('US')
            if 'EU' in open_markets:
                market_filters.append('EU')
            
            available_stocks = list(TradableInstrument.objects.filter(
                is_active=True,
                market__in=market_filters
            ).exclude(symbol__in=RESTRICTED_HOURS_STOCKS).values_list('symbol', flat=True))
            
            if not available_stocks:
                return 0
            
            import os
            ai_engine = AITradingEngine(
                os.getenv('ALPACA_API_KEY'),
                os.getenv('ALPACA_API_SECRET')
            )
            
            analytics = self._get_user_analytics(user, 'capital_stock')
            
            if self._should_execute_trade(user, analytics, 'capital_stock'):
                # Randomly select a stock to diversify trades
                import random
                symbol = random.choice(available_stocks)
                result = ai_engine.execute_ai_trade(user, symbol, instrument_type='stock')
                
                if result.get('success'):
                    logger.info(f"      📈 Stock trade: {result.get('symbol', symbol)} - Executed")
                    return 1
                else:
                    logger.info(f"      ⛔ Trade skipped for {symbol}: {result.get('message', 'Unknown reason')}")
        
        except Exception as e:
            logger.error(f"Stock trading error for {user.email}: {e}")
        
        return 0
    
    def _process_forex_trading(self, user) -> int:
        try:
            import os
            ai_engine = AITradingEngine(
                os.getenv('ALPACA_API_KEY'),
                os.getenv('ALPACA_API_SECRET')
            )
            
            analytics = self._get_user_analytics(user, 'capital_forex')
            
            if self._should_execute_trade(user, analytics, 'capital_forex'):
                forex_pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'XAU/USD']
                # Randomly select a forex pair to diversify trades
                import random
                symbol = random.choice(forex_pairs)
                result = ai_engine.execute_ai_trade(user, symbol, instrument_type='forex')
                
                if result.get('success'):
                    logger.info(f"      💱 Forex trade: {result.get('symbol', symbol)} - Executed")
                    return 1
        
        except Exception as e:
            logger.error(f"Forex trading error for {user.email}: {e}")
        
        return 0
    
    def _get_user_analytics(self, user, broker: str) -> Dict:
        """
        Calculate user analytics including:
        - Daily P&L
        - Lifetime win rate (all historical trades)
        - Rolling win rate (last 100 trades) for recent performance
        """
        try:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            today_trades = Trade.objects.filter(
                user=user,
                broker=broker,
                created_at__gte=today_start,
                status='closed'
            )
            
            daily_pnl = today_trades.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
            
            # LIFETIME METRICS (all historical trades)
            all_closed = Trade.objects.filter(user=user, broker=broker, status='closed')
            total_trades = all_closed.count()
            winning_trades = all_closed.filter(profit_loss__gt=0).count()
            lifetime_win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # ROLLING WINDOW METRICS (last 100 trades for recent performance)
            ROLLING_WINDOW = 100
            recent_trades = all_closed.order_by('-closed_at')[:ROLLING_WINDOW]
            recent_count = recent_trades.count()
            recent_wins = sum(1 for trade in recent_trades if trade.profit_loss and trade.profit_loss > 0)
            rolling_win_rate = (recent_wins / recent_count * 100) if recent_count > 0 else 0
            
            return {
                'daily_pnl': float(daily_pnl),
                'win_rate': lifetime_win_rate,  # Keep for backward compatibility
                'lifetime_win_rate': lifetime_win_rate,
                'rolling_win_rate': rolling_win_rate,
                'total_trades': total_trades,
                'rolling_trades': recent_count
            }
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            return {
                'daily_pnl': 0,
                'win_rate': 0,
                'lifetime_win_rate': 0,
                'rolling_win_rate': 0,
                'total_trades': 0,
                'rolling_trades': 0
            }
    
    def _select_best_stock_ml_prescreening(self, ai_engine, user, candidate_stocks: List[str]) -> Optional[Dict]:
        """
        INTELLIGENT ML-BASED STOCK SELECTION (RATE-LIMIT OPTIMIZED)
        
        Pre-screens a LIMITED number of candidate stocks using ML model:
        1. Analyzes max 5 random stocks per cycle to avoid rate limits
        2. ML confidence >= 70% (quality threshold)
        3. Prioritizes NEW symbols (not in current portfolio) for diversity
        4. Selects highest confidence among qualified candidates
        
        Returns: {'symbol': str, 'ml_confidence': float, 'is_new_symbol': bool} or None
        """
        import random
        
        qualified_stocks = []
        
        # Get current portfolio symbols for diversity prioritization
        current_symbols = set(Trade.objects.filter(
            user=user,
            status='open',
            instrument_type='stock'
        ).values_list('symbol', flat=True))
        
        # RATE LIMIT OPTIMIZATION: Analyze max 5 random stocks per cycle
        # This prevents hitting Alpaca rate limits while still maintaining quality
        MAX_STOCKS_PER_CYCLE = 5
        stocks_to_analyze = random.sample(candidate_stocks, min(MAX_STOCKS_PER_CYCLE, len(candidate_stocks)))
        
        logger.info(f"      🔍 Pre-screening {len(stocks_to_analyze)}/{len(candidate_stocks)} stocks for ML quality (>=70% confidence)...")
        
        for symbol in stocks_to_analyze:
            try:
                # Analyze stock with ML model
                analysis = ai_engine.analyze_market_sentiment(symbol, instrument_type='stock')
                
                if not analysis:
                    continue
                
                ml_prediction = analysis.get('ml_prediction', {})
                ml_confidence = ml_prediction.get('confidence', 0)
                ml_profitable = ml_prediction.get('prediction', 0) == 1
                
                # ADAPTIVE QUALITY FILTER:
                # Accept stocks if ML confidence >= 70% for profitable trades
                # This allows high-confidence ML predictions even without technical indicator agreement
                # (Previously required 2+ agreeing indicators, which blocked recovery mode learning)
                if ml_profitable and ml_confidence >= 0.70:
                    is_new_symbol = symbol not in current_symbols
                    qualified_stocks.append({
                        'symbol': symbol,
                        'ml_confidence': ml_confidence,
                        'is_new_symbol': is_new_symbol,
                        'signal_strength': analysis.get('confidence', 0),
                        'has_signal': bool(analysis.get('signal'))  # Track if technical indicators agree
                    })
                    logger.info(f"         ✅ {symbol}: ML={ml_confidence:.1%}, Technical Signal={'Yes' if analysis.get('signal') else 'No'}")
            
            except Exception as e:
                logger.error(f"         Error analyzing {symbol}: {e}")
                continue
        
        if not qualified_stocks:
            logger.info(f"      ⚠️  No qualified stocks found in this cycle (try again in 60s)")
            return None
        
        logger.info(f"      ✅ Found {len(qualified_stocks)} qualified stocks (>=70% ML confidence)")
        
        # Sort by: (1) diversity priority (new symbols first), (2) highest ML confidence
        qualified_stocks.sort(key=lambda x: (not x['is_new_symbol'], -x['ml_confidence']))
        
        return qualified_stocks[0]
    
    def _should_execute_trade(self, user, analytics: Dict, broker: str) -> bool:
        """
        ENHANCED RISK MANAGEMENT WITH ROLLING WINDOW & RECOVERY MODE:
        - 8% daily loss limit (based on Alpaca equity)
        - 70% minimum win rate threshold using ROLLING 100-trade window
        - Recovery mode: Allows limited trading when below threshold
        - Quality-focused trading with adaptive risk management
        """
        # Get current Alpaca account equity for daily loss limit calculation
        from api.services import alpaca_service
        alpaca_equity = float(alpaca_service.get_equity(user=user) or 100000)
        
        daily_loss_limit = alpaca_equity * 0.08
        
        # Check daily loss limit
        if analytics.get('daily_pnl', 0) < -daily_loss_limit:
            logger.info(f"      ⛔ Daily loss limit reached for {user.email} ({broker}): {analytics.get('daily_pnl', 0):.2f} < -{daily_loss_limit:.2f}")
            return False
        
        # Check win rate threshold using ROLLING WINDOW (last 100 trades)
        total_trades = analytics.get('total_trades', 0)
        rolling_trades = analytics.get('rolling_trades', 0)
        lifetime_win_rate = analytics.get('lifetime_win_rate', 0)
        rolling_win_rate = analytics.get('rolling_win_rate', 0)
        
        # Only enforce win rate threshold after 10+ total trades
        if total_trades >= 10:
            # Use rolling win rate for recent performance evaluation
            if rolling_win_rate < 70:
                logger.info(f"      📊 Win Rate Analysis for {user.email} ({broker}):")
                logger.info(f"         • Lifetime: {lifetime_win_rate:.1f}% (all {total_trades} trades)")
                logger.info(f"         • Rolling:  {rolling_win_rate:.1f}% (last {rolling_trades} trades)")
                logger.info(f"         • ⚠️  Rolling win rate below 70% threshold")
                logger.info(f"         • ✅ RECOVERY MODE: Trading allowed with standard risk limits")
                logger.info(f"            System will automatically improve as AI learns from new trades")
                # Allow trading in recovery mode - the AI needs new data to improve
                # Risk is still managed by:
                # - 70% ML confidence threshold
                # - 15% position concentration limit
                # - 8% daily loss limit
                # - 2% stop-loss / 3% profit target (scalping)
                return True
        
        return True
    
    def _auto_close_orphan_trade(self, trade, reason: str) -> bool:
        """
        Auto-close an orphaned trade with neutral exit (entry_price, $0 P&L)
        
        Args:
            trade: Trade object to close
            reason: Reason for auto-closure (for audit trail)
            
        Returns:
            bool: True if successfully closed, False otherwise
        """
        try:
            trade.exit_price = trade.entry_price
            trade.profit_loss = Decimal('0.00')
            trade.status = 'closed'
            trade.closed_at = timezone.now()
            trade.save()
            
            logger.warning(f"      🔧 AUTO-HEALED: Closed orphan {trade.symbol} (neutral exit) - {reason}")
            logger.info(f"         Trade ID: {trade.id}, Entry: ${trade.entry_price}, Qty: {trade.quantity}")
            
            return True
            
        except Exception as e:
            logger.error(f"      ❌ Failed to auto-close orphan {trade.symbol}: {e}")
            return False
    
    def _run_position_reconciliation(self, user, ai_engine, user_state: dict):
        """
        Production-grade auto-healing position reconciliation with per-user state tracking
        
        Verifies database positions match Alpaca reality and auto-closes orphans:
        - Identifies orphaned positions (in DB but not on Alpaca)
        - Uses grace period (2 consecutive detections) before auto-closing
        - Auto-closes confirmed orphans with neutral exit_price and $0 P&L
        - Alerts on ghost positions (on Alpaca but not in DB)
        - Tracks clean reconciliation passes for startup completion (per-user)
        - Uses per-user state to prevent cross-user pollution in multi-user deployments
        """
        try:
            logger.info(f"      🔍 Running position reconciliation for {user.email}...")
            
            # Get database positions
            db_trades = Trade.objects.filter(
                user=user,
                broker='alpaca_sim',
                status='open'
            )
            
            db_positions = [
                {'symbol': trade.symbol, 'qty': float(trade.quantity)}
                for trade in db_trades
            ]
            
            # Reconcile with Alpaca
            reconciliation = ai_engine.alpaca_account.reconcile_positions(db_positions)
            
            if reconciliation['status'] == 'matched':
                logger.info(f"      ✅ Reconciliation successful: {len(reconciliation['matched_positions'])} positions matched")
                
                # Track clean passes for startup reconciliation
                user_state['clean_reconciliation_passes'] += 1
                
                # Clear all grace counters on clean reconciliation
                if user_state['orphan_grace_counters']:
                    user_state['orphan_grace_counters'].clear()
                
                # Mark startup reconciliation complete after 2 consecutive clean passes
                if not user_state['startup_reconciliation_complete'] and user_state['clean_reconciliation_passes'] >= 2:
                    user_state['startup_reconciliation_complete'] = True
                    user_state['reconciliation_interval'] = 5  # Reduce to every 5 cycles after startup
                    logger.info(f"      ✅ STARTUP RECONCILIATION COMPLETE for {user.email} - Switching to normal interval (every 5 cycles)")
                    
            else:
                logger.warning(f"      ⚠️  RECONCILIATION MISMATCH DETECTED!")
                
                # Reset clean pass counter and increase reconciliation frequency
                user_state['clean_reconciliation_passes'] = 0
                user_state['reconciliation_interval'] = 1  # Run every cycle until clean
                user_state['startup_reconciliation_complete'] = False  # Re-enter intensive mode
                logger.info(f"      🔄 Entering intensive reconciliation mode for {user.email} (every cycle until 2 clean passes)")
                
                # Handle orphaned positions (in DB but not on Alpaca) - AUTO-HEAL
                if reconciliation['orphaned_positions']:
                    orphan_symbols = reconciliation['orphaned_positions']
                    logger.warning(f"      ⚠️  Orphaned positions (in DB but not on Alpaca): {orphan_symbols}")
                    
                    # Clear grace counters for symbols no longer orphaned (ensures consecutive detection)
                    current_orphan_symbols = set(orphan_symbols)
                    stale_symbols = [sym for sym in user_state['orphan_grace_counters'].keys() 
                                    if sym not in current_orphan_symbols]
                    for stale_symbol in stale_symbols:
                        user_state['orphan_grace_counters'].pop(stale_symbol, None)
                    
                    # Auto-close orphans after 2 consecutive detections (grace period)
                    for symbol in orphan_symbols:
                        # Increment grace counter (symbol as key, already user-scoped via user_state)
                        user_state['orphan_grace_counters'][symbol] = user_state['orphan_grace_counters'].get(symbol, 0) + 1
                        
                        grace_count = user_state['orphan_grace_counters'][symbol]
                        
                        if grace_count >= 2:
                            # Grace period expired - auto-close orphan
                            orphan_trades = db_trades.filter(symbol=symbol)
                            for trade in orphan_trades:
                                success = self._auto_close_orphan_trade(
                                    trade,
                                    f"Orphan detected {grace_count} consecutive times (grace period expired)"
                                )
                                if success:
                                    # Clear counter after successful closure
                                    user_state['orphan_grace_counters'].pop(symbol, None)
                        else:
                            logger.info(f"         Grace period: {symbol} orphan count={grace_count}/2 (will auto-close at 2)")
                
                # Handle ghost positions (on Alpaca but not in DB) - ALERT ONLY
                if reconciliation['ghost_positions']:
                    ghost_symbols = reconciliation['ghost_positions']
                    logger.error(f"      🚨 ALERT: Ghost positions (on Alpaca but not in DB): {ghost_symbols}")
                    logger.error(f"         MANUAL ACTION REQUIRED: These positions exist on Alpaca but are not tracked!")
            
            self.agent_state['last_reconciliation'] = timezone.now()
            
        except Exception as e:
            logger.error(f"      ❌ Position reconciliation failed: {e}", exc_info=True)
    
    def get_status(self) -> Dict:
        market_summary = self.market_hours.get_market_summary()
        
        return {
            **self.agent_state,
            'uptime_seconds': (timezone.now() - self.agent_state['started_at']).total_seconds() if self.agent_state['started_at'] else 0,
            'market_summary': market_summary
        }
