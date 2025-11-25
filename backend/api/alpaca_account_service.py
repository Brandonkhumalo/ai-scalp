import os
import requests
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List
import time
import threading

logger = logging.getLogger(__name__)


class AlpacaAccountCache:
    """Intelligent caching system with different TTLs for different data types"""
    
    def __init__(self):
        self._cache = {}
        self._ttls = {
            'account': 60,      # Account balance data: 60 seconds (reduced API calls)
            'positions': 30,    # Open positions: 30 seconds (reduced API calls)
            'orders': 15,       # Recent orders: 15 seconds
            'quotes': 30,       # Market quotes: 30 seconds (reduced API calls)
            'snapshot': 30,     # Market snapshots: 30 seconds (reduced API calls)
        }
    
    def get(self, key: str, category: str = 'account') -> Optional[Dict]:
        """Get cached data if not expired"""
        if key not in self._cache:
            return None
        
        cached_data, timestamp = self._cache[key]
        ttl = self._ttls.get(category, 30)
        
        if datetime.now() - timestamp < timedelta(seconds=ttl):
            logger.debug(f"Cache HIT: {key} (age: {(datetime.now() - timestamp).seconds}s)")
            return cached_data
        
        logger.debug(f"Cache MISS: {key} (expired)")
        del self._cache[key]
        return None
    
    def set(self, key: str, data: Dict, category: str = 'account'):
        """Cache data with timestamp"""
        self._cache[key] = (data, datetime.now())
        logger.debug(f"Cache SET: {key} (TTL: {self._ttls.get(category, 30)}s)")
    
    def clear(self, pattern: Optional[str] = None):
        """Clear all cache or specific pattern"""
        if pattern:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for k in keys_to_delete:
                del self._cache[k]
        else:
            self._cache.clear()


class AlpacaAccountService:
    """
    Enhanced Alpaca service with live account data, intelligent caching, 
    and request prioritization to avoid rate limits
    """
    
    # Request priority levels
    PRIORITY_CRITICAL = 1    # Execute immediately (account balance, positions)
    PRIORITY_NORMAL = 2      # Can be batched (quotes for multiple symbols)
    PRIORITY_LOW = 3         # Can be delayed (historical data, non-critical queries)
    
    # Global request counter (class variable shared across all instances)
    _total_requests = 0
    _cache_hits = 0
    _request_start_time = None
    _counter_lock = threading.Lock()  # Thread-safe counter increments
    
    def __init__(self):
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
        self.alpaca_data_url = 'https://data.alpaca.markets'
        self.alpaca_trading_url = 'https://api.alpaca.markets'
        
        # Shared cache instance
        self.cache = AlpacaAccountCache()
        
        # Rate limiting
        self._last_request_time = {}
        self._min_request_interval = {
            self.PRIORITY_CRITICAL: 0.1,   # 100ms between critical requests
            self.PRIORITY_NORMAL: 0.5,     # 500ms between normal requests
            self.PRIORITY_LOW: 2.0,        # 2s between low priority requests
        }
        
        # Request deduplication - prevent parallel duplicate API calls
        self._request_locks = {}
        self._lock_manager = threading.Lock()
    
    def get_alpaca_headers(self):
        """Get Alpaca API headers"""
        return {
            'APCA-API-KEY-ID': self.alpaca_api_key,
            'APCA-API-SECRET-KEY': self.alpaca_api_secret,
            'Content-Type': 'application/json',
        }
    
    def _throttle_request(self, priority: int = PRIORITY_NORMAL):
        """Throttle requests based on priority to avoid rate limits"""
        current_time = time.time()
        
        if priority in self._last_request_time:
            time_since_last = current_time - self._last_request_time[priority]
            min_interval = self._min_request_interval.get(priority, 0.5)
            
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                logger.debug(f"Throttling {priority} priority request for {sleep_time:.3f}s")
                time.sleep(sleep_time)
        
        self._last_request_time[priority] = time.time()
    
    def _make_request(self, method: str, url: str, priority: int = PRIORITY_NORMAL, 
                     cache_key: Optional[str] = None, cache_category: str = 'account',
                     **kwargs) -> Optional[Dict]:
        """
        Make HTTP request with caching, throttling, and deduplication
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            priority: Request priority (CRITICAL, NORMAL, LOW)
            cache_key: Cache key for this request (if cacheable)
            cache_category: Cache category for TTL determination
            **kwargs: Additional arguments for requests
        """
        # Check cache first
        if cache_key and method.upper() == 'GET':
            cached = self.cache.get(cache_key, cache_category)
            if cached is not None:
                with AlpacaAccountService._counter_lock:
                    AlpacaAccountService._cache_hits += 1
                logger.debug(f"✅ Cache HIT: {cache_key} (Total hits: {AlpacaAccountService._cache_hits})")
                return cached
        
        # Request deduplication: Only one thread executes the same request
        # Others wait for the result
        request_key = f"{method}:{url}"
        
        with self._lock_manager:
            if request_key not in self._request_locks:
                self._request_locks[request_key] = threading.Lock()
            request_lock = self._request_locks[request_key]
        
        # Try to acquire the lock for this specific request
        with request_lock:
            # Double-check cache after acquiring lock (first caller may have completed)
            if cache_key and method.upper() == 'GET':
                cached = self.cache.get(cache_key, cache_category)
                if cached is not None:
                    with AlpacaAccountService._counter_lock:
                        AlpacaAccountService._cache_hits += 1
                    logger.debug(f"✅ Deduplication HIT: {cache_key} (Total hits: {AlpacaAccountService._cache_hits})")
                    return cached
            
            # Throttle request based on priority
            self._throttle_request(priority)
            
            try:
                # Increment global request counter (thread-safe)
                with AlpacaAccountService._counter_lock:
                    AlpacaAccountService._total_requests += 1
                    if AlpacaAccountService._request_start_time is None:
                        AlpacaAccountService._request_start_time = datetime.now()
                    current_count = AlpacaAccountService._total_requests
                
                # Log rate limit warning every 50 requests
                if current_count % 50 == 0:
                    elapsed = (datetime.now() - AlpacaAccountService._request_start_time).total_seconds()
                    rate = AlpacaAccountService._total_requests / elapsed if elapsed > 0 else 0
                    cache_hit_rate = (AlpacaAccountService._cache_hits / AlpacaAccountService._total_requests * 100) if AlpacaAccountService._total_requests > 0 else 0
                    logger.warning(f"⚠️  Alpaca API Usage: {AlpacaAccountService._total_requests} requests ({rate:.2f} req/sec), {AlpacaAccountService._cache_hits} cache hits ({cache_hit_rate:.1f}% hit rate)")
                
                headers = self.get_alpaca_headers()
                headers.update(kwargs.pop('headers', {}))
                
                response = requests.request(method, url, headers=headers, **kwargs)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Cache successful GET requests
                    if cache_key and method.upper() == 'GET':
                        self.cache.set(cache_key, data, cache_category)
                    
                    return data
                elif response.status_code == 429:
                    logger.error(f"🚨 RATE LIMIT EXCEEDED: Alpaca API returned 429. Total requests: {AlpacaAccountService._total_requests}, Cache hits: {AlpacaAccountService._cache_hits}")
                    return None
                else:
                    logger.error(f"Alpaca API error: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"Request failed: {str(e)}")
                return None
    
    def get_account_info(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get Alpaca account information with caching
        
        Returns dict with: buying_power, cash, portfolio_value, equity, etc.
        Cache TTL: 30 seconds
        Priority: CRITICAL
        """
        cache_key = "account_info"
        
        if force_refresh:
            self.cache.clear(cache_key)
        
        url = f"{self.alpaca_trading_url}/v2/account"
        return self._make_request(
            'GET', 
            url, 
            priority=self.PRIORITY_CRITICAL,
            cache_key=cache_key,
            cache_category='account'
        )
    
    def get_buying_power(self, force_refresh: bool = False) -> Decimal:
        """
        Get current buying power from Alpaca
        
        Returns: Decimal value of available buying power
        """
        account = self.get_account_info(force_refresh=force_refresh)
        if account:
            return Decimal(str(account.get('buying_power', '0')))
        return Decimal('0')
    
    def get_cash_balance(self, force_refresh: bool = False) -> Decimal:
        """
        Get current cash balance from Alpaca
        
        Returns: Decimal value of available cash
        """
        account = self.get_account_info(force_refresh=force_refresh)
        if account:
            return Decimal(str(account.get('cash', '0')))
        return Decimal('0')
    
    def get_equity(self, force_refresh: bool = False) -> Decimal:
        """
        Get total equity (cash + positions) from Alpaca
        
        Returns: Decimal value of total equity
        """
        account = self.get_account_info(force_refresh=force_refresh)
        if account:
            return Decimal(str(account.get('equity', '0')))
        return Decimal('0')
    
    def get_positions(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get all open positions with caching
        
        Cache TTL: 10 seconds
        Priority: CRITICAL
        """
        cache_key = "positions"
        
        if force_refresh:
            self.cache.clear(cache_key)
        
        url = f"{self.alpaca_trading_url}/v2/positions"
        result = self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_CRITICAL,
            cache_key=cache_key,
            cache_category='positions'
        )
        return result if result else []
    
    def get_position(self, symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get specific position by symbol
        
        Priority: CRITICAL
        """
        cache_key = f"position_{symbol}"
        
        if force_refresh:
            self.cache.clear(cache_key)
        
        url = f"{self.alpaca_trading_url}/v2/positions/{symbol}"
        return self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_CRITICAL,
            cache_key=cache_key,
            cache_category='positions'
        )
    
    def get_orders(self, status: str = 'all', limit: int = 50, force_refresh: bool = False) -> List[Dict]:
        """
        Get orders with caching
        
        Cache TTL: 5 seconds
        Priority: NORMAL
        """
        cache_key = f"orders_{status}_{limit}"
        
        if force_refresh:
            self.cache.clear(cache_key)
        
        url = f"{self.alpaca_trading_url}/v2/orders?status={status}&limit={limit}"
        result = self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_NORMAL,
            cache_key=cache_key,
            cache_category='orders'
        )
        return result if result else []
    
    def place_order(self, symbol: str, qty: float, side: str, 
                   order_type: str = 'market', time_in_force: str = 'day',
                   stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> Optional[Dict]:
        """
        Place an order on Alpaca with optional stop-loss and take-profit (bracket order)
        
        Priority: CRITICAL (no caching)
        
        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            time_in_force: 'day', 'gtc', etc.
            stop_loss: Stop-loss price (for bracket orders)
            take_profit: Take-profit price (for bracket orders)
        
        Note: Fractional orders MUST be simple orders (no bracket orders allowed by Alpaca)
        """
        url = f"{self.alpaca_trading_url}/v2/orders"
        payload = {
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'type': order_type,
            'time_in_force': time_in_force,
        }
        
        is_fractional = qty % 1 != 0
        
        if is_fractional:
            logger.info(f'🔸 Placing simple order for {qty} shares of {symbol} (fractional shares require simple orders)')
        elif stop_loss is not None or take_profit is not None:
            payload['order_class'] = 'bracket'
            
            if stop_loss is not None:
                payload['stop_loss'] = {
                    'stop_price': stop_loss
                }
            
            if take_profit is not None:
                payload['take_profit'] = {
                    'limit_price': take_profit
                }
            
            logger.info(f'🎯 Placing bracket order for {qty} shares of {symbol} (SL: {stop_loss}, TP: {take_profit})')
        
        return self._make_request(
            'POST',
            url,
            priority=self.PRIORITY_CRITICAL,
            json=payload
        )
    
    def close_position(self, symbol: str) -> Optional[Dict]:
        """
        Close a position on Alpaca
        
        Priority: CRITICAL (no caching)
        Returns: Order object with status (e.g., 'accepted', 'filled')
        """
        url = f"{self.alpaca_trading_url}/v2/positions/{symbol}"
        return self._make_request(
            'DELETE',
            url,
            priority=self.PRIORITY_CRITICAL
        )
    
    def verify_position_closed(self, symbol: str, max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        Verify that a position has been fully closed on Alpaca
        
        PRODUCTION-GRADE: This method MUST be 100% reliable for real money trading.
        - Returns True ONLY when position is confirmed gone (404)
        - Returns False for ANY other condition (API errors, timeouts, position exists)
        - Never assumes success - only explicit 404 means closed
        
        Critical safety rules:
        1. 404 status = position doesn't exist = SUCCESS
        2. 200 status = position exists = FAILURE
        3. 429/500 status = API error = FAILURE
        4. Network error = FAILURE
        
        NOTE: This method bypasses _make_request() to access raw status codes
        """
        import time
        import requests
        
        for attempt in range(max_retries):
            try:
                url = f"{self.alpaca_trading_url}/v2/positions/{symbol}"
                headers = self.get_alpaca_headers()
                
                # Make direct request to get status code
                response = requests.get(url, headers=headers)
                
                if response.status_code == 404:
                    # Position doesn't exist = successfully closed
                    logger.info(f'✅ Position {symbol} confirmed closed (404)')
                    return True
                    
                elif response.status_code == 200:
                    # Position still exists
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.info(f'Position {symbol} still open (200), retrying in {wait_time}s...')
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f'❌ Position {symbol} still exists after {max_retries} retries')
                        return False
                        
                elif response.status_code == 429:
                    # Rate limit
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(f'⚠️  Rate limit (429) verifying {symbol}, retrying in {wait_time}s...')
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f'❌ Rate limited after {max_retries} retries - cannot verify {symbol}')
                        return False
                        
                else:
                    # Other HTTP errors (500, 503, etc.)
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(f'⚠️  HTTP {response.status_code} verifying {symbol}, retrying in {wait_time}s...')
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f'❌ HTTP {response.status_code} after {max_retries} retries - cannot verify {symbol}')
                        return False
                    
            except Exception as e:
                # Network errors, timeouts, etc.
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f'⚠️  Exception verifying {symbol}: {e}, retrying in {wait_time}s...')
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f'❌ Exception after {max_retries} retries - cannot verify {symbol}: {e}')
                    return False
        
        # Should never reach here, but return False for safety
        logger.error(f'❌ verify_position_closed fell through - returning False for safety')
        return False
    
    def reconcile_positions(self, db_positions: list) -> dict:
        """
        Reconcile database positions with Alpaca reality
        
        Production-grade safety check:
        - Compares database positions with actual Alpaca positions
        - Identifies orphaned positions (in DB but not on Alpaca)
        - Identifies ghost positions (on Alpaca but not in DB)
        - Returns detailed reconciliation report
        
        Returns:
            {
                'status': 'matched' | 'mismatch',
                'orphaned_positions': [list of symbols in DB but not on Alpaca],
                'ghost_positions': [list of symbols on Alpaca but not in DB],
                'matched_positions': [list of symbols that match],
                'alpaca_positions': {dict of symbol: position data},
                'message': 'description'
            }
        """
        try:
            # Get all current positions from Alpaca
            alpaca_positions = self.get_positions(force_refresh=True)
            
            # Create lookup sets
            alpaca_symbols = set()
            alpaca_position_map = {}
            
            if alpaca_positions:
                for pos in alpaca_positions:
                    symbol = pos.get('symbol')
                    if symbol:
                        alpaca_symbols.add(symbol)
                        alpaca_position_map[symbol] = pos
            
            db_symbols = {pos['symbol'] for pos in db_positions if pos.get('symbol')}
            
            # Find mismatches
            orphaned = list(db_symbols - alpaca_symbols)  # In DB but not on Alpaca
            ghosts = list(alpaca_symbols - db_symbols)    # On Alpaca but not in DB
            matched = list(db_symbols & alpaca_symbols)   # In both
            
            status = 'matched' if (not orphaned and not ghosts) else 'mismatch'
            
            result = {
                'status': status,
                'orphaned_positions': orphaned,
                'ghost_positions': ghosts,
                'matched_positions': matched,
                'alpaca_positions': alpaca_position_map,
                'message': f'Reconciliation: {len(matched)} matched, {len(orphaned)} orphaned, {len(ghosts)} ghosts'
            }
            
            # Log any mismatches
            if orphaned:
                logger.warning(f'⚠️  Orphaned positions (in DB but not on Alpaca): {orphaned}')
            if ghosts:
                logger.warning(f'⚠️  Ghost positions (on Alpaca but not in DB): {ghosts}')
            if status == 'matched':
                logger.info(f'✅ Position reconciliation successful: {len(matched)} positions matched')
            
            return result
            
        except Exception as e:
            logger.error(f'❌ Error during position reconciliation: {e}')
            return {
                'status': 'error',
                'orphaned_positions': [],
                'ghost_positions': [],
                'matched_positions': [],
                'alpaca_positions': {},
                'message': f'Reconciliation failed: {str(e)}'
            }
    
    def cancel_all_orders(self) -> Optional[Dict]:
        """
        Cancel ALL pending orders on Alpaca
        
        Priority: CRITICAL (no caching)
        """
        url = f"{self.alpaca_trading_url}/v2/orders"
        return self._make_request(
            'DELETE',
            url,
            priority=self.PRIORITY_CRITICAL
        )
    
    def cancel_order(self, order_id: str) -> Optional[Dict]:
        """
        Cancel a specific order by ID
        
        Priority: CRITICAL (no caching)
        """
        url = f"{self.alpaca_trading_url}/v2/orders/{order_id}"
        return self._make_request(
            'DELETE',
            url,
            priority=self.PRIORITY_CRITICAL
        )
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get specific order by ID to check status (filled, partially_filled, etc.)
        
        Priority: CRITICAL (no caching)
        """
        url = f"{self.alpaca_trading_url}/v2/orders/{order_id}"
        return self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_CRITICAL
        )
    
    def get_quote(self, symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get latest quote for a symbol with caching
        
        Cache TTL: 5 seconds
        Priority: NORMAL
        """
        cache_key = f"quote_{symbol}"
        
        if force_refresh:
            self.cache.clear(cache_key)
        
        url = f"{self.alpaca_data_url}/v2/stocks/{symbol}/quotes/latest"
        return self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_NORMAL,
            cache_key=cache_key,
            cache_category='quotes'
        )
    
    def get_snapshot(self, symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get market snapshot with caching
        
        Cache TTL: 10 seconds
        Priority: NORMAL
        """
        cache_key = f"snapshot_{symbol}"
        
        if force_refresh:
            self.cache.clear(cache_key)
        
        url = f"{self.alpaca_data_url}/v2/stocks/{symbol}/snapshot"
        return self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_NORMAL,
            cache_key=cache_key,
            cache_category='snapshot'
        )
    
    def get_bars(self, symbol: str, timeframe: str = '1Min', 
                start: Optional[str] = None, end: Optional[str] = None) -> Optional[Dict]:
        """
        Get historical bars (low priority - can be delayed)
        
        Priority: LOW
        """
        url = f"{self.alpaca_data_url}/v2/stocks/{symbol}/bars?timeframe={timeframe}"
        if start:
            url += f"&start={start}"
        if end:
            url += f"&end={end}"
        
        return self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_LOW
        )
    
    def get_closed_positions_with_pnl(self, days_back: int = 30) -> List[Dict]:
        """
        Get closed positions with realized P&L from account activities
        
        This queries Alpaca's activity log for FILL activities (trade executions)
        and calculates realized P&L for closed positions
        
        Args:
            days_back: Number of days to look back (default 30)
        
        Returns:
            List of dicts with symbol, realized_pnl, close_time, etc.
        
        Priority: NORMAL
        """
        from datetime import datetime, timedelta
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        date_start = start_date.strftime('%Y-%m-%d')
        
        # Get all fill activities (trade executions)
        activities = self.get_account_activities(
            activity_types='FILL',
            after=date_start,
            page_size=100
        )
        
        if not activities:
            return []
        
        # Group fills by symbol to track positions
        symbol_fills = {}
        
        for activity in activities:
            symbol = activity.get('symbol')
            if not symbol:
                continue
            
            if symbol not in symbol_fills:
                symbol_fills[symbol] = []
            
            symbol_fills[symbol].append({
                'side': activity.get('side'),  # 'buy' or 'sell'
                'qty': abs(float(activity.get('qty', 0))),
                'price': float(activity.get('price', 0)),
                'transaction_time': activity.get('transaction_time'),
                'id': activity.get('id')
            })
        
        # Calculate realized P&L for each symbol
        closed_positions = []
        
        for symbol, fills in symbol_fills.items():
            # Sort by time
            fills.sort(key=lambda x: x['transaction_time'])
            
            # Track position
            position_qty = 0
            total_cost = 0
            closed_trades = []
            
            for fill in fills:
                if fill['side'] == 'buy':
                    # Opening or adding to position
                    position_qty += fill['qty']
                    total_cost += fill['qty'] * fill['price']
                elif fill['side'] == 'sell' and position_qty > 0:
                    # Closing or reducing position
                    sell_qty = min(fill['qty'], position_qty)
                    avg_cost = total_cost / position_qty if position_qty > 0 else 0
                    
                    # Calculate realized P&L for this close
                    realized_pnl = (fill['price'] - avg_cost) * sell_qty
                    
                    if sell_qty > 0:
                        closed_trades.append({
                            'symbol': symbol,
                            'qty': sell_qty,
                            'avg_entry_price': avg_cost,
                            'exit_price': fill['price'],
                            'realized_pnl': realized_pnl,
                            'close_time': fill['transaction_time'],
                            'side': 'buy'  # Original side of the trade
                        })
                    
                    # Update position
                    cost_reduction = (sell_qty / position_qty) * total_cost if position_qty > 0 else 0
                    position_qty -= sell_qty
                    total_cost -= cost_reduction
            
            closed_positions.extend(closed_trades)
        
        return closed_positions
    
    def get_account_activities(self, activity_types: str = 'FILL', 
                              page_size: int = 100, 
                              direction: str = 'desc',
                              after: Optional[str] = None,
                              until: Optional[str] = None) -> List[Dict]:
        """
        Get account activities (trade fills, closed positions, etc.)
        
        Args:
            activity_types: Activity type filter (default: 'FILL' for trade executions)
            page_size: Number of results per page (default: 100, Alpaca maximum)
            direction: Sort direction 'asc' or 'desc' (default: 'desc')
            after: Start date (YYYY-MM-DD)
            until: End date (YYYY-MM-DD)
        
        Returns: List of activity records with trade details
        Priority: NORMAL
        """
        url = f"{self.alpaca_trading_url}/v2/account/activities?activity_types={activity_types}&page_size={page_size}&direction={direction}"
        
        if after:
            url += f"&after={after}"
        if until:
            url += f"&until={until}"
        
        result = self._make_request(
            'GET',
            url,
            priority=self.PRIORITY_NORMAL
        )
        
        # Alpaca returns activities as a list, not a dict
        return result if isinstance(result, list) else []
