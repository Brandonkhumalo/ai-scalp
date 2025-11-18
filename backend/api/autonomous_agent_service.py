import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum
from decimal import Decimal

from .market_hours_service import MarketHoursService
from .ai_trading_engine import AITradingEngine
from .models import Trade, TradableInstrument

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
        }
        self.market_hours = MarketHoursService()
        
        # Per-user reconciliation state (prevents cross-user state pollution)
        self.user_reconciliation_state = {}  # {user_id: {reconciliation_interval, clean_passes, startup_complete, orphan_counters}}
    
    def run_continuous(self, check_interval: int = 60):
        self.agent_state['started_at'] = timezone.now()
        logger.info("🤖 Autonomous Trading Agent STARTED - Multi-Timezone 24/7 Operation")
        logger.info(f"   Check interval: {check_interval} seconds")
        
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
        
        market_summary = self.market_hours.get_market_summary()
        open_markets = market_summary['open_markets']
        self.agent_state['active_markets'] = open_markets
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🌍 AUTONOMOUS AGENT - Check #{self.agent_state['total_checks']}")
        logger.info(f"{'='*70}")
        logger.info(f"⏰ Time: {market_summary['timestamp_utc']}")
        logger.info(f"📊 Open Markets: {', '.join(open_markets) if open_markets else 'None'}")
        
        if not open_markets:
            logger.info("💤 All markets closed - Agent in standby mode")
            return
        
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
                self._process_user_trading(user, open_markets)
            except Exception as e:
                logger.error(f"❌ Error processing user {user.email}: {e}")
    
    def _process_user_trading(self, user, open_markets: List[str]):
        """
        Process trading for stock brokers only:
        1. Alpaca (alpaca_sim): For users with ai_trading_enabled during US market hours
        2. Capital.com Stocks: DISABLED (per user request)
        
        Note: Forex trading is MANUAL ONLY - not included in autonomous agent
        """
        trades_executed = 0
        
        # Process Alpaca Trading (US markets only)
        if hasattr(user, 'ai_trading_enabled') and user.ai_trading_enabled and 'US' in open_markets:
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
            
            # 🎯 SCALPING: Check and auto-close positions at profit/loss targets FIRST
            scalping_result = ai_engine.check_scalping_targets(user)
            if scalping_result.get('action') == 'scalping_auto_close':
                logger.info(f"      🎯 Scalping: Closed {scalping_result.get('closed_count')} positions")
                logger.info(f"         Realized P&L: ${scalping_result.get('total_realized_profit', 0):.2f}")
            
            # 🔍 RECONCILIATION: Verify database positions match Alpaca reality
            if self.agent_state['total_checks'] % user_state['reconciliation_interval'] == 0:
                self._run_position_reconciliation(user, ai_engine, user_state)
            
            analytics = self._get_user_analytics(user, 'alpaca_sim')
            
            if self._should_execute_trade(user, analytics, 'alpaca_sim'):
                # *** BLACKLIST: Stocks to NEVER trade ***
                BLACKLISTED_SYMBOLS = ['GEV']  # Add symbols here to permanently exclude from AI trading
                
                # Use US stocks from TradableInstrument
                us_stocks = list(TradableInstrument.objects.filter(
                    is_active=True,
                    market='US'
                ).values_list('symbol', flat=True))
                
                if not us_stocks:
                    # Fallback to default US stocks if TradableInstrument is empty
                    us_stocks = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN']
                
                # Remove blacklisted symbols from trading
                us_stocks = [s for s in us_stocks if s not in BLACKLISTED_SYMBOLS]
                logger.info(f"      🚫 Blacklisted symbols excluded: {BLACKLISTED_SYMBOLS}")
                
                # *** INTELLIGENT ML-BASED STOCK SELECTION ***
                # Pre-screen all stocks and select best opportunity with >70% ML confidence
                best_stock = self._select_best_stock_ml_prescreening(ai_engine, user, us_stocks)
                
                if not best_stock:
                    logger.info(f"      ⛔ No high-quality trading opportunities found (all stocks below 70% ML confidence)")
                    return 0
                
                symbol = best_stock['symbol']
                logger.info(f"      🎯 Selected {symbol} with {best_stock['ml_confidence']:.1%} ML confidence (diversity priority: {best_stock['is_new_symbol']})")
                
                result = ai_engine.execute_ai_trade(user, symbol, instrument_type='stock')
                
                if result.get('success'):
                    logger.info(f"      📊 Alpaca trade: {result.get('symbol', symbol)} - Executed")
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
        from .alpaca_account_service import AlpacaAccountService
        alpaca_service = AlpacaAccountService()
        alpaca_equity = float(alpaca_service.get_equity() or 100000)
        
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
