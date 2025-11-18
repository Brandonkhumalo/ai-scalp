import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
import logging
import time
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Dual-source market data service:
    - Primary: Alpaca Market Data API v2 (realtime IEX/SIP data)
    - Fallback: Yahoo Finance (historical training data)
    - Includes thread-safe caching to prevent API rate limiting
    - Optimized with multi-symbol batch endpoints to reduce from 1200/min to <65/min
    """
    
    # Class-level counters for instrumentation
    _api_call_count = 0
    _batch_call_count = 0
    _symbols_fetched = 0
    _last_api_call_time = 0
    _rate_limit_cooldown_until = 0  # Timestamp when rate limit cooldown expires
    _consecutive_429_count = 0  # Track consecutive 429 errors globally
    
    def __init__(self):
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
        self.alpaca_data_url = 'https://data.alpaca.markets'
        self._cache_ttl = 60  # Cache for 60 seconds - optimized for scalping (need fresh prices)
    
    @classmethod
    def log_api_metrics(cls):
        """Log API call efficiency metrics every 50 calls"""
        if cls._batch_call_count > 0 and cls._batch_call_count % 10 == 0:
            efficiency = cls._symbols_fetched / cls._api_call_count if cls._api_call_count > 0 else 0
            logger.info(f"📊 Alpaca API Metrics: {cls._api_call_count} API calls, {cls._batch_call_count} batches, "
                       f"{cls._symbols_fetched} symbols fetched (efficiency: {efficiency:.1f} symbols/call)")
    
    @classmethod
    def increment_api_call(cls, symbols_count=1):
        """Track an API call"""
        cls._api_call_count += 1
        cls._batch_call_count += 1
        cls._symbols_fetched += symbols_count
        cls.log_api_metrics()
    
    @classmethod
    def check_rate_limit_cooldown(cls):
        """Check if we're in a rate limit cooldown period. Returns True if we should skip API calls."""
        current_time = time.time()
        if current_time < cls._rate_limit_cooldown_until:
            remaining = int(cls._rate_limit_cooldown_until - current_time)
            logger.warning(f'⏸️  In rate limit cooldown - {remaining}s remaining. Using cached data only.')
            return True
        return False
    
    @classmethod
    def handle_rate_limit_backoff(cls, attempt):
        """Immediate cooldown on 429 to avoid worker timeout"""
        cls._consecutive_429_count += 1
        
        # Enter 15-second cooldown (reduced from 60s for faster scalping price updates)
        cls._rate_limit_cooldown_until = time.time() + 15
        logger.error(f'🚫 Rate limited (429 #{cls._consecutive_429_count}) - entering 15s cooldown. Will use cached data only.')
        cls._consecutive_429_count = 0  # Reset counter after entering cooldown
    
    @classmethod
    def reset_429_counter(cls):
        """Reset consecutive 429 counter on successful API call"""
        if cls._consecutive_429_count > 0:
            logger.info(f'✅ API call succeeded - resetting 429 counter (was {cls._consecutive_429_count})')
            cls._consecutive_429_count = 0
        
    def get_alpaca_headers(self):
        return {
            'APCA-API-KEY-ID': self.alpaca_api_key,
            'APCA-API-SECRET-KEY': self.alpaca_api_secret,
            'Content-Type': 'application/json',
        }
    
    def _get_cache_key(self, prefix, symbol):
        """Generate cache key for a symbol"""
        return f"market_data:{prefix}:{symbol}"
    
    def _get_cached(self, key):
        """Get cached data using Django's thread-safe cache"""
        return cache.get(key)
    
    def _set_cache(self, key, data):
        """Cache data using Django's thread-safe cache with TTL"""
        cache.set(key, data, self._cache_ttl)
    
    def get_snapshots(self, symbols, feed='iex', use_cache=True):
        """
        Get snapshots for multiple symbols using multi-symbol batch endpoint.
        Snapshots include: latest quote, latest trade, minute bar, daily bar, and previous daily bar.
        
        Args:
            symbols: List of symbols or single symbol string
            feed: 'iex' (real-time incomplete) or 'sip' (15-min delayed complete)
            use_cache: Whether to use cached data (default True)
        
        Returns:
            Dict mapping symbol -> snapshot data
        """
        try:
            if not symbols:
                return {}
            
            # Normalize to list
            symbol_list = symbols if isinstance(symbols, list) else [symbols]
            
            # Filter out forex symbols
            stock_symbols = [s for s in symbol_list if '/' not in s and s not in ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'NZDUSD', 'EURJPY', 'GBPJPY', 'XAUUSD']]
            
            if not stock_symbols:
                logger.debug('No stock symbols to fetch snapshots for')
                return {}
            
            results = {}
            uncached_symbols = []
            
            # Check cache first if enabled
            if use_cache:
                for symbol in stock_symbols:
                    cache_key = self._get_cache_key('snapshot', symbol)
                    cached = self._get_cached(cache_key)
                    if cached:
                        results[symbol] = cached
                    else:
                        uncached_symbols.append(symbol)
            else:
                uncached_symbols = stock_symbols
            
            if not uncached_symbols:
                logger.debug(f'All {len(stock_symbols)} snapshots retrieved from cache')
                return results
            
            # Check if we're in a rate limit cooldown period
            if self.check_rate_limit_cooldown():
                if results:
                    logger.info(f'📦 Returning {len(results)} CACHED snapshots (in rate limit cooldown)')
                else:
                    logger.warning(f'🚫 NO CACHED DATA AVAILABLE - In rate limit cooldown with empty cache. Wait for cooldown to expire.')
                return results  # Return whatever we have cached
            
            # Fetch uncached symbols in batches (max 3500 per Alpaca docs)
            headers = self.get_alpaca_headers()
            chunk_size = 3500
            max_retries = 3
            
            for i in range(0, len(uncached_symbols), chunk_size):
                chunk = uncached_symbols[i:i + chunk_size]
                symbol_str = ','.join(chunk)
                endpoint = f"{self.alpaca_data_url}/v2/stocks/snapshots?symbols={symbol_str}&feed={feed}"
                
                # Single attempt - no retries to avoid worker timeout
                response = requests.get(endpoint, headers=headers, timeout=15)
                
                # Track API call for metrics
                self.increment_api_call(symbols_count=len(chunk))
                
                if response.status_code == 200:
                    # Reset consecutive 429 counter on success
                    self.reset_429_counter()
                    
                    data = response.json()
                    # Alpaca returns {"snapshots": {"AAPL": {...}, "MSFT": {...}}}
                    snapshots = data.get('snapshots', {}) if isinstance(data, dict) else {}
                    
                    # Cache each symbol's snapshot
                    for symbol, snapshot in snapshots.items():
                        results[symbol] = snapshot
                        if use_cache:
                            cache_key = self._get_cache_key('snapshot', symbol)
                            self._set_cache(cache_key, snapshot)
                    
                    logger.info(f'✅ Fetched {len(chunk)} snapshots in 1 batch call (feed={feed})')
                
                elif response.status_code == 429:
                    # Rate limited - enter immediate cooldown, no retries
                    self.handle_rate_limit_backoff(0)
                    logger.warning(f'⚠️ Rate limit hit - returning partial/cached data to avoid timeout')
                else:
                    logger.error(f'Alpaca snapshots batch error: {response.status_code}')
            
            # Return whatever we successfully fetched (partial results better than nothing)
            return results
            
        except Exception as e:
            logger.error(f'Error fetching batch snapshots: {str(e)}')
            return {}
    
    def get_realtime_quotes(self, symbols):
        """
        DEPRECATED: Use get_snapshots() instead - quote data is included in snapshots.
        Kept for backward compatibility.
        """
        logger.warning('get_realtime_quotes() is deprecated - use get_snapshots() instead')
        snapshots = self.get_snapshots(symbols, feed='iex', use_cache=True)
        
        # Convert snapshot format to quotes format for backward compatibility
        quotes_data = {'quotes': {}}
        for symbol, snapshot in snapshots.items():
            latest_quote = snapshot.get('latestQuote', {})
            prev_close = snapshot.get('prevDailyBar', {}).get('c')
            if latest_quote:
                latest_quote['pc'] = prev_close
                quotes_data['quotes'][symbol] = latest_quote
        
        return quotes_data if quotes_data['quotes'] else None
    
    def get_realtime_snapshot(self, symbol):
        """
        Get combined quote/trade/bar snapshot from Alpaca with caching.
        Now uses the optimized batch endpoint under the hood.
        """
        try:
            # Skip forex symbols
            if '/' in symbol or symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'NZDUSD', 'EURJPY', 'GBPJPY', 'XAUUSD']:
                logger.debug(f'Skipping Alpaca snapshot for forex symbol: {symbol}')
                return None
            
            # Use batch method for single symbol (leverages caching)
            snapshots = self.get_snapshots([symbol], feed='iex', use_cache=True)
            return snapshots.get(symbol)
            
        except Exception as e:
            logger.error(f'Error fetching Alpaca snapshot: {str(e)}')
            return None
    
    def get_batch_snapshots(self, symbols):
        """
        DEPRECATED: Use get_snapshots() instead.
        Kept for backward compatibility.
        """
        logger.warning('get_batch_snapshots() is deprecated - use get_snapshots() instead')
        return self.get_snapshots(symbols, feed='iex', use_cache=True)
    
    def get_multi_bars(self, symbols, timeframe='5Min', num_bars=50, feed='iex', start=None, end=None):
        """
        Get historical bars for multiple symbols using multi-symbol batch endpoint.
        Optimized to reduce API calls from 1000 individual calls to ~5 batch calls.
        
        Args:
            symbols: List of symbols or single symbol string
            timeframe: Bar timeframe ('1Min', '5Min', '15Min', '1Hour', '1Day')
            num_bars: Number of bars to return (system fetches up to 10,000 and filters)
            feed: 'iex' (real-time incomplete) or 'sip' (15-min delayed complete)
            start: Start datetime (ISO format) - if None, auto-calculated from num_bars
            end: End datetime (ISO format) - if None, defaults to most recent data
        
        Returns:
            Dict mapping symbol -> list of bars
        """
        try:
            if not symbols:
                return {}
            
            # Normalize to list
            symbol_list = symbols if isinstance(symbols, list) else [symbols]
            
            # Filter out forex symbols
            stock_symbols = [s for s in symbol_list if '/' not in s and s not in ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'NZDUSD', 'EURJPY', 'GBPJPY', 'XAUUSD']]
            
            if not stock_symbols:
                return {}
            
            # Calculate start time if not provided (estimate based on num_bars and timeframe)
            if not start:
                timeframe_minutes = {
                    '1Min': 1, '5Min': 5, '15Min': 15, '30Min': 30, 
                    '1Hour': 60, '1Day': 1440
                }
                minutes = timeframe_minutes.get(timeframe, 5)
                lookback_minutes = num_bars * minutes * 2  # 2x buffer for market hours
                # Use RFC3339 format with UTC timezone (required by Alpaca)
                from datetime import timezone
                start_dt = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
                start = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Check if we're in a rate limit cooldown period
            if self.check_rate_limit_cooldown():
                logger.warning(f'🚫 Skipping bars fetch - In rate limit cooldown with empty cache. Wait for cooldown to expire.')
                return {}  # Return empty dict during cooldown
            
            results = {}
            headers = self.get_alpaca_headers()
            max_retries = 3
            
            # Alpaca allows ~50-100 symbols per bars request (10,000 bar limit total)
            # For 50 bars per symbol: 10,000 / 50 = 200 symbols max, use 50 for safety
            chunk_size = 50
            
            for i in range(0, len(stock_symbols), chunk_size):
                chunk = stock_symbols[i:i + chunk_size]
                symbol_str = ','.join(chunk)
                
                # Build endpoint with Alpaca best practices
                endpoint = f"{self.alpaca_data_url}/v2/stocks/bars?symbols={symbol_str}&timeframe={timeframe}&limit=10000&feed={feed}"
                if start:
                    endpoint += f"&start={start}"
                if end:
                    endpoint += f"&end={end}"
                
                # Single attempt - no retries to avoid worker timeout
                response = requests.get(endpoint, headers=headers, timeout=20)
                
                # Track API call for metrics
                self.increment_api_call(symbols_count=len(chunk))
                
                if response.status_code == 200:
                    # Reset consecutive 429 counter on success
                    self.reset_429_counter()
                    
                    data = response.json()
                    bars_dict = data.get('bars', {})
                    
                    # Limit each symbol to requested num_bars
                    for symbol, bars in bars_dict.items():
                        if bars:
                            # Take only the most recent num_bars
                            results[symbol] = bars[-num_bars:] if len(bars) > num_bars else bars
                    
                    logger.info(f'✅ Fetched bars for {len(chunk)} symbols in 1 batch call (timeframe={timeframe}, feed={feed})')
                
                elif response.status_code == 429:
                    # Rate limited - enter immediate cooldown, no retries
                    self.handle_rate_limit_backoff(0)
                    logger.warning(f'⚠️ Rate limit hit - returning partial/cached data to avoid timeout')
                else:
                    # Log full error details for debugging
                    error_body = response.text
                    logger.error(f'Alpaca multi-bars error: {response.status_code}')
                    logger.error(f'   URL: {endpoint}')
                    logger.error(f'   Response: {error_body[:500]}')
            
            # Return whatever we successfully fetched (partial results better than nothing)
            return results
            
        except Exception as e:
            logger.error(f'Error fetching multi-symbol bars: {str(e)}')
            return {}
    
    def get_bars(self, symbol, timeframe='1Min', limit=100, use_fallback=True):
        """
        Get OHLCV bars with multiple timeframe support (1Min to 1Day).
        Now uses the optimized batch endpoint under the hood.
        Primary: Alpaca realtime data
        Fallback: Yahoo Finance historical data
        """
        try:
            # Use batch method for single symbol
            bars_dict = self.get_multi_bars([symbol], timeframe=timeframe, num_bars=limit, feed='iex')
            bars = bars_dict.get(symbol, [])
            
            if bars and len(bars) > 0:
                logger.info(f'Fetched {len(bars)} bars from Alpaca for {symbol}')
                return bars
            
            # Fallback to Yahoo Finance for historical data
            if use_fallback:
                logger.info(f'Falling back to Yahoo Finance for {symbol}')
                return self.get_yahoo_bars(symbol, timeframe, limit)
            
            return []
            
        except Exception as e:
            logger.error(f'Error fetching bars: {str(e)}')
            
            # Try fallback on exception
            if use_fallback:
                return self.get_yahoo_bars(symbol, timeframe, limit)
            
            return []
    
    def get_yahoo_bars(self, symbol, timeframe='1Min', limit=100):
        """Fallback to Yahoo Finance for historical training data"""
        try:
            # Convert symbols to Yahoo Finance format
            yahoo_symbol = symbol
            if '/' in symbol:
                # Forex pair format: EUR/USD -> EURUSD=X
                yahoo_symbol = symbol.replace('/', '') + '=X'
                logger.info(f'Converting forex symbol {symbol} to Yahoo format: {yahoo_symbol}')
            elif symbol in ['SAP', 'SIE', 'ALV', 'DBK', 'DTE', 'RHM', 'ENR']:
                # German stocks need .DE suffix
                yahoo_symbol = symbol + '.DE'
                logger.info(f'Adding German exchange suffix: {yahoo_symbol}')
            elif symbol in ['SHEL', 'BP', 'AZN', 'HSBA', 'ULVR', 'FRES']:
                # UK stocks need .L suffix (London Stock Exchange)
                yahoo_symbol = symbol + '.L'
                logger.info(f'Adding London exchange suffix: {yahoo_symbol}')
            elif symbol in ['TTE', 'AIR']:
                # French stocks need .PA suffix (Paris)
                yahoo_symbol = symbol + '.PA'
                logger.info(f'Adding Paris exchange suffix: {yahoo_symbol}')
            
            # Map Alpaca timeframes to Yahoo Finance intervals
            interval_map = {
                '1Min': '1m',
                '5Min': '5m',
                '15Min': '15m',
                '30Min': '30m',
                '1Hour': '1h',
                '1Day': '1d'
            }
            
            interval = interval_map.get(timeframe, '5m')
            
            # Calculate period based on timeframe and limit
            if 'Min' in timeframe or 'Hour' in timeframe:
                period = '7d'  # Last 7 days for intraday
            else:
                period = '1y'  # Last year for daily
            
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f'No Yahoo Finance data for {symbol}')
                return []
            
            # Convert to Alpaca format
            bars = []
            for index, row in df.tail(limit).iterrows():
                bars.append({
                    't': index.isoformat(),
                    'o': float(row['Open']),
                    'h': float(row['High']),
                    'l': float(row['Low']),
                    'c': float(row['Close']),
                    'v': float(row['Volume']),
                    'source': 'yahoo'
                })
            
            logger.info(f'Fetched {len(bars)} bars from Yahoo Finance for {symbol}')
            return bars
            
        except Exception as e:
            logger.error(f'Yahoo Finance error for {symbol}: {str(e)}')
            return []
    
    def get_training_data(self, symbol, days=30):
        """Get historical data for AI model training (always uses fallback for more data)"""
        try:
            # For stocks, prefer Yahoo Finance for training (more historical data)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f'{days}d', interval='1h')
            
            bars = []
            for index, row in df.iterrows():
                bars.append({
                    't': index.isoformat(),
                    'o': float(row['Open']),
                    'h': float(row['High']),
                    'l': float(row['Low']),
                    'c': float(row['Close']),
                    'v': float(row['Volume']),
                    'source': 'yahoo_training'
                })
            
            logger.info(f'Fetched {len(bars)} training bars for {symbol}')
            return bars
                
        except Exception as e:
            logger.error(f'Error fetching training data: {str(e)}')
            return []
