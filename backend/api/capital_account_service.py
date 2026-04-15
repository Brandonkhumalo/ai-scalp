import os
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List, Any

import requests

logger = logging.getLogger(__name__)


class CapitalAccountCache:
    def __init__(self):
        self._cache = {}
        self._ttls = {
            'account': 45,
            'positions': 10,
            'orders': 8,
            'quotes': 5,
            'snapshot': 5,
        }

    def get(self, key: str, category: str = 'account') -> Optional[Any]:
        if key not in self._cache:
            return None
        data, timestamp = self._cache[key]
        if datetime.now() - timestamp < timedelta(seconds=self._ttls.get(category, 15)):
            return data
        del self._cache[key]
        return None

    def set(self, key: str, data: Any, category: str = 'account'):
        self._cache[key] = (data, datetime.now())

    def clear(self, pattern: Optional[str] = None):
        if not pattern:
            self._cache.clear()
            return
        for key in list(self._cache.keys()):
            if pattern in key:
                del self._cache[key]


class CapitalAccountService:
    """
    Capital.com broker service with an Alpaca-compatible method surface.
    This allows existing scalping/AI/reconciliation code paths to reuse the
    same singleton object with minimal call-site changes.
    """

    PRIORITY_CRITICAL = 1
    PRIORITY_NORMAL = 2
    PRIORITY_LOW = 3

    def __init__(self):
        self.capital_trading_mode = os.getenv('CAPITAL_TRADING_MODE', 'demo').strip().lower()
        if self.capital_trading_mode not in ('demo', 'live'):
            self.capital_trading_mode = 'demo'

        self.capital_api_key, self.capital_identifier, self.capital_password, self.capital_base_url = self._resolve_capital_credentials()
        self.capital_epic_suffix = os.getenv('CAPITAL_EPIC_SUFFIX', '.US')

        self.cache = CapitalAccountCache()

        self._cst = None
        self._security_token = None
        self._session_expiry = None

        self._last_request_time = {}
        self._min_request_interval = {
            self.PRIORITY_CRITICAL: 0.12,
            self.PRIORITY_NORMAL: 0.4,
            self.PRIORITY_LOW: 1.2,
        }

    def _resolve_user_mode(self, user: Optional[Any]) -> str:
        if user is not None and hasattr(user, 'capital_use_demo'):
            return 'demo' if bool(getattr(user, 'capital_use_demo', True)) else 'live'
        return self.capital_trading_mode

    def _resolve_capital_credentials(self, trading_mode: Optional[str] = None):
        """
        Resolve credentials with mode-aware precedence:
        1) CAPITAL_{MODE}_* (DEMO/LIVE)
        2) generic CAPITAL_*
        """
        mode = (trading_mode or self.capital_trading_mode).strip().lower()
        if mode not in ('demo', 'live'):
            mode = 'demo'

        if mode == 'live':
            mode_api_key = os.getenv('CAPITAL_LIVE_API_KEY')
            mode_identifier = os.getenv('CAPITAL_LIVE_IDENTIFIER')
            mode_password = os.getenv('CAPITAL_LIVE_PASSWORD')
            mode_base_url = os.getenv('CAPITAL_LIVE_BASE_URL', 'https://api-capital.backend-capital.com')
        else:
            mode_api_key = os.getenv('CAPITAL_DEMO_API_KEY')
            mode_identifier = os.getenv('CAPITAL_DEMO_IDENTIFIER')
            mode_password = os.getenv('CAPITAL_DEMO_PASSWORD')
            mode_base_url = os.getenv('CAPITAL_DEMO_BASE_URL', 'https://demo-api-capital.backend-capital.com')

        api_key = mode_api_key or os.getenv('CAPITAL_API_KEY')
        identifier = mode_identifier or os.getenv('CAPITAL_IDENTIFIER')
        password = mode_password or os.getenv('CAPITAL_PASSWORD')
        base_url = (os.getenv('CAPITAL_BASE_URL') or mode_base_url).rstrip('/')
        return api_key, identifier, password, base_url

    def _apply_user_context(self, user: Optional[Any] = None):
        mode = self._resolve_user_mode(user)
        api_key, identifier, password, base_url = self._resolve_capital_credentials(mode)
        if (
            api_key != self.capital_api_key
            or identifier != self.capital_identifier
            or password != self.capital_password
            or base_url != self.capital_base_url
            or mode != self.capital_trading_mode
        ):
            # Reset session when credentials or target environment change.
            self._cst = None
            self._security_token = None
            self._session_expiry = None
        self.capital_trading_mode = mode
        self.capital_api_key = api_key
        self.capital_identifier = identifier
        self.capital_password = password
        self.capital_base_url = base_url

    def _throttle_request(self, priority: int = PRIORITY_NORMAL):
        now = time.time()
        if priority in self._last_request_time:
            elapsed = now - self._last_request_time[priority]
            min_interval = self._min_request_interval.get(priority, 0.4)
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        self._last_request_time[priority] = time.time()

    def _session_valid(self) -> bool:
        if not self._cst or not self._security_token:
            return False
        if not self._session_expiry:
            return True
        return datetime.now() < self._session_expiry

    def _authenticate(self) -> bool:
        if self._session_valid():
            return True

        if not (self.capital_api_key and self.capital_identifier and self.capital_password):
            logger.error(
                'Capital.com credentials not configured for mode=%s '
                '(expected CAPITAL_%s_API_KEY / CAPITAL_%s_IDENTIFIER / CAPITAL_%s_PASSWORD or generic CAPITAL_API_KEY / CAPITAL_IDENTIFIER / CAPITAL_PASSWORD)',
                self.capital_trading_mode,
                self.capital_trading_mode.upper(),
                self.capital_trading_mode.upper(),
                self.capital_trading_mode.upper(),
            )
            return False

        url = f"{self.capital_base_url}/api/v1/session"
        headers = {
            'X-CAP-API-KEY': self.capital_api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {
            'identifier': self.capital_identifier,
            'password': self.capital_password,
            'encryptedPassword': False,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code not in (200, 201):
                logger.error(f'Capital session creation failed: {response.status_code} {response.text}')
                return False

            self._cst = response.headers.get('CST')
            self._security_token = response.headers.get('X-SECURITY-TOKEN')
            # Default 50 minutes; Capital session length can vary.
            self._session_expiry = datetime.now() + timedelta(minutes=50)

            if not self._cst or not self._security_token:
                logger.error('Capital session created but missing CST/X-SECURITY-TOKEN headers')
                return False

            logger.info('Capital.com session established (mode=%s, base_url=%s)', self.capital_trading_mode, self.capital_base_url)
            return True
        except Exception as exc:
            logger.error(f'Capital authentication failed: {exc}')
            return False

    def _headers(self) -> Dict[str, str]:
        headers = {
            'X-CAP-API-KEY': self.capital_api_key or '',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self._cst:
            headers['CST'] = self._cst
        if self._security_token:
            headers['X-SECURITY-TOKEN'] = self._security_token
        return headers

    def _make_request(
        self,
        method: str,
        path: str,
        priority: int = PRIORITY_NORMAL,
        cache_key: Optional[str] = None,
        cache_category: str = 'account',
        user: Optional[Any] = None,
        **kwargs,
    ) -> Optional[Any]:
        self._apply_user_context(user=user)

        if cache_key and method.upper() == 'GET':
            cached = self.cache.get(cache_key, cache_category)
            if cached is not None:
                return cached

        if not self._authenticate():
            return None

        self._throttle_request(priority)
        url = f"{self.capital_base_url}{path}"

        try:
            response = requests.request(method, url, headers=self._headers(), timeout=20, **kwargs)

            if response.status_code == 401:
                self._cst = None
                self._security_token = None
                self._session_expiry = None
                if self._authenticate():
                    response = requests.request(method, url, headers=self._headers(), timeout=20, **kwargs)

            if response.status_code < 200 or response.status_code >= 300:
                logger.error(f'Capital API error {response.status_code} for {path}: {response.text}')
                return None

            data = response.json() if response.content else {}
            if cache_key and method.upper() == 'GET':
                self.cache.set(cache_key, data, cache_category)
            return data
        except Exception as exc:
            logger.error(f'Capital request failed ({method} {path}): {exc}')
            return None

    def _symbol_to_epic(self, symbol: str) -> str:
        if '.' in symbol:
            return symbol
        return f'{symbol}{self.capital_epic_suffix}'

    @staticmethod
    def _epic_to_symbol(epic: str) -> str:
        if not epic:
            return ''
        return epic.split('.')[0]

    def get_account_info(self, force_refresh: bool = False, user: Optional[Any] = None) -> Optional[Dict]:
        if force_refresh:
            self.cache.clear('account_info')

        data = self._make_request(
            'GET',
            '/api/v1/accounts',
            priority=self.PRIORITY_CRITICAL,
            cache_key='account_info',
            cache_category='account',
            user=user,
        )
        if not data:
            return None

        accounts = data.get('accounts') if isinstance(data, dict) else None
        if not accounts:
            return None

        account = next((a for a in accounts if a.get('preferred')), accounts[0])
        balance = account.get('balance', {})

        available = Decimal(str(balance.get('available') or balance.get('availableToDeal') or 0))
        equity = Decimal(str(balance.get('balance') or balance.get('equity') or 0))
        cash = Decimal(str(balance.get('deposit') or balance.get('cash') or available))

        return {
            'buying_power': str(available),
            'equity': str(equity),
            'cash': str(cash),
            'currency': account.get('currency', 'USD'),
            'account_id': account.get('accountId'),
            'provider': 'capital',
            'raw': account,
        }

    def get_buying_power(self, force_refresh: bool = False, user: Optional[Any] = None) -> Decimal:
        account = self.get_account_info(force_refresh=force_refresh, user=user)
        if account:
            return Decimal(str(account.get('buying_power', '0')))
        return Decimal('0')

    def get_cash_balance(self, force_refresh: bool = False, user: Optional[Any] = None) -> Decimal:
        account = self.get_account_info(force_refresh=force_refresh, user=user)
        if account:
            return Decimal(str(account.get('cash', '0')))
        return Decimal('0')

    def get_equity(self, force_refresh: bool = False, user: Optional[Any] = None) -> Decimal:
        account = self.get_account_info(force_refresh=force_refresh, user=user)
        if account:
            return Decimal(str(account.get('equity', '0')))
        return Decimal('0')

    def get_positions(self, force_refresh: bool = False, *_, **kwargs) -> List[Dict]:
        user = kwargs.get('user')
        if hasattr(force_refresh, 'id'):
            user = force_refresh
            force_refresh = False
        if force_refresh:
            self.cache.clear('positions')

        data = self._make_request(
            'GET',
            '/api/v1/positions',
            priority=self.PRIORITY_CRITICAL,
            cache_key='positions',
            cache_category='positions',
            user=user,
        )
        positions = data.get('positions', []) if isinstance(data, dict) else []

        normalized = []
        for item in positions:
            pos = item.get('position', {})
            market = item.get('market', {})
            epic = market.get('epic', '')
            symbol = self._epic_to_symbol(epic)
            bid = market.get('bid')
            offer = market.get('offer')
            current_price = offer if pos.get('direction', '').upper() == 'BUY' else bid
            size = pos.get('size', 0)
            normalized.append({
                'symbol': symbol,
                'epic': epic,
                'qty': str(size),
                'size': size,
                'side': 'long' if pos.get('direction', '').upper() == 'BUY' else 'short',
                'direction': pos.get('direction', 'BUY'),
                'current_price': current_price or bid or offer or 0,
                'market_value': pos.get('marketValue') or 0,
                'unrealized_pl': pos.get('upl') or pos.get('profit') or 0,
                'dealId': pos.get('dealId'),
                'raw': item,
            })
        return normalized

    def get_position(self, symbol: str, force_refresh: bool = False, user: Optional[Any] = None) -> Optional[Dict]:
        symbol = symbol.upper().strip()
        positions = self.get_positions(force_refresh=force_refresh, user=user)
        for pos in positions:
            if pos.get('symbol') == symbol:
                return pos
        return None

    def get_orders(self, status: str = 'all', limit: int = 50, force_refresh: bool = False, user: Optional[Any] = None) -> List[Dict]:
        if force_refresh:
            self.cache.clear('orders')

        data = self._make_request(
            'GET',
            '/api/v1/workingorders',
            priority=self.PRIORITY_NORMAL,
            cache_key=f'orders_{status}_{limit}',
            cache_category='orders',
            user=user,
        )
        orders = data.get('workingOrders', []) if isinstance(data, dict) else []

        normalized = []
        for item in orders[:limit]:
            wo = item.get('workingOrderData', {})
            market = item.get('marketData', {})
            normalized.append({
                'id': wo.get('dealId'),
                'status': status,
                'symbol': self._epic_to_symbol(market.get('epic', '')),
                'epic': market.get('epic'),
                'side': (wo.get('direction') or '').lower(),
                'qty': wo.get('size'),
                'raw': item,
            })
        return normalized

    def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = 'limit',
        time_in_force: str = 'day',
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        limit_price: Optional[float] = None,
        user: Optional[Any] = None,
    ) -> Optional[Dict]:
        direction = 'BUY' if side.lower() == 'buy' else 'SELL'
        order_type_cap = 'LIMIT' if order_type.lower() == 'limit' else 'MARKET'
        epic = self._symbol_to_epic(symbol)

        payload = {
            'epic': epic,
            'direction': direction,
            'size': float(qty),
            'orderType': order_type_cap,
            'currencyCode': 'USD',
            'forceOpen': True,
            'timeInForce': 'GOOD_TILL_CANCELLED' if time_in_force.lower() in ('gtc', 'good_till_cancelled') else 'FILL_OR_KILL',
        }

        if order_type_cap == 'LIMIT' and limit_price is not None:
            payload['level'] = float(limit_price)
        if stop_loss is not None:
            payload['stopLevel'] = float(stop_loss)
        if take_profit is not None:
            payload['profitLevel'] = float(take_profit)

        result = self._make_request(
            'POST',
            '/api/v1/positions',
            priority=self.PRIORITY_CRITICAL,
            user=user,
            json=payload,
        )
        if not result:
            return None

        deal_reference = result.get('dealReference')
        order_id = result.get('dealId') or deal_reference

        # Try to confirm for a richer status response.
        confirm = None
        if deal_reference:
            confirm = self._make_request(
                'GET',
                f'/api/v1/confirms/{deal_reference}',
                priority=self.PRIORITY_NORMAL,
                user=user,
            )

        return {
            'id': order_id,
            'dealReference': deal_reference,
            'status': (confirm or {}).get('status', 'submitted'),
            'filled_avg_price': (confirm or {}).get('level'),
            'raw': {'submit': result, 'confirm': confirm},
        }

    def close_position(self, symbol: str, user: Optional[Any] = None) -> Optional[Dict]:
        symbol = symbol.upper().strip()
        positions = self.get_positions(force_refresh=True, user=user)

        matching = [p for p in positions if p.get('symbol') == symbol]
        if not matching:
            return None

        # Close the first matching leg; repeated calls can close multiple legs.
        pos = matching[0]
        deal_id = pos.get('dealId')
        if not deal_id:
            logger.error(f'Cannot close {symbol}: missing dealId in Capital position payload')
            return None

        close_direction = 'SELL' if str(pos.get('direction', 'BUY')).upper() == 'BUY' else 'BUY'
        payload = {
            'direction': close_direction,
            'size': float(pos.get('size') or pos.get('qty') or 0),
            'orderType': 'MARKET',
            'timeInForce': 'FILL_OR_KILL',
        }

        result = self._make_request(
            'DELETE',
            f'/api/v1/positions/{deal_id}',
            priority=self.PRIORITY_CRITICAL,
            user=user,
            json=payload,
        )
        return result

    def verify_position_closed(self, symbol: str, max_retries: int = 3, retry_delay: float = 1.0, user: Optional[Any] = None) -> bool:
        symbol = symbol.upper().strip()
        for attempt in range(max_retries):
            positions = self.get_positions(force_refresh=True, user=user)
            exists = any((p.get('symbol') == symbol) for p in positions)
            if not exists:
                return True
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))
        return False

    def reconcile_positions(self, db_positions: list, user: Optional[Any] = None) -> dict:
        try:
            broker_positions = self.get_positions(force_refresh=True, user=user)
            broker_symbols = {p.get('symbol') for p in broker_positions if p.get('symbol')}
            db_symbols = {pos['symbol'] for pos in db_positions if pos.get('symbol')}

            orphaned = list(db_symbols - broker_symbols)
            ghosts = list(broker_symbols - db_symbols)
            matched = list(db_symbols & broker_symbols)

            position_map = {p.get('symbol'): p for p in broker_positions if p.get('symbol')}
            status = 'matched' if (not orphaned and not ghosts) else 'mismatch'

            return {
                'status': status,
                'orphaned_positions': orphaned,
                'ghost_positions': ghosts,
                'matched_positions': matched,
                'alpaca_positions': position_map,
                'message': f'Reconciliation: {len(matched)} matched, {len(orphaned)} orphaned, {len(ghosts)} ghosts',
            }
        except Exception as exc:
            logger.error(f'Position reconciliation failed: {exc}')
            return {
                'status': 'error',
                'orphaned_positions': [],
                'ghost_positions': [],
                'matched_positions': [],
                'alpaca_positions': {},
                'message': f'Reconciliation failed: {exc}',
            }

    def cancel_all_orders(self, user: Optional[Any] = None) -> Optional[Dict]:
        orders = self.get_orders(status='open', limit=500, force_refresh=True, user=user)
        cancelled = 0
        for order in orders:
            order_id = order.get('id')
            if not order_id:
                continue
            if self.cancel_order(order_id, user=user):
                cancelled += 1
        return {'cancelled': cancelled}

    def cancel_order(self, order_id: str, user: Optional[Any] = None) -> Optional[Dict]:
        return self._make_request(
            'DELETE',
            f'/api/v1/workingorders/{order_id}',
            priority=self.PRIORITY_CRITICAL,
            user=user,
        )

    def get_order_status(self, order_id: str, user: Optional[Any] = None) -> Optional[Dict]:
        orders = self.get_orders(status='open', limit=500, force_refresh=True, user=user)
        for order in orders:
            if str(order.get('id')) == str(order_id):
                return order
        return {'id': order_id, 'status': 'unknown'}

    def get_quote(self, symbol: str, force_refresh: bool = False, user: Optional[Any] = None) -> Optional[Dict]:
        snapshot = self.get_snapshot(symbol, force_refresh=force_refresh, user=user)
        if not snapshot:
            return None
        return {
            'quote': {
                'bp': snapshot.get('latestQuote', {}).get('bp'),
                'ap': snapshot.get('latestQuote', {}).get('ap'),
            }
        }

    def get_snapshot(self, symbol: str, force_refresh: bool = False, user: Optional[Any] = None) -> Optional[Dict]:
        symbol = symbol.upper().strip()
        epic = self._symbol_to_epic(symbol)
        cache_key = f'snapshot_{epic}'
        if force_refresh:
            self.cache.clear(cache_key)

        data = self._make_request(
            'GET',
            f'/api/v1/prices/{epic}?resolution=MINUTE&max=1',
            priority=self.PRIORITY_NORMAL,
            cache_key=cache_key,
            cache_category='snapshot',
            user=user,
        )
        if not data:
            return None

        prices = data.get('prices', []) if isinstance(data, dict) else []
        if not prices:
            return None

        latest = prices[-1]
        close_bid = ((latest.get('closePrice') or {}).get('bid'))
        close_ask = ((latest.get('closePrice') or {}).get('ask'))
        if close_bid is None and close_ask is None:
            return None

        return {
            'latestQuote': {
                'bp': close_bid if close_bid is not None else close_ask,
                'ap': close_ask if close_ask is not None else close_bid,
            },
            'source': 'capital',
        }

    def get_bars(self, symbol: str, timeframe: str = '1MINUTE', start: Optional[str] = None, end: Optional[str] = None, user: Optional[Any] = None) -> Optional[Dict]:
        symbol = symbol.upper().strip()
        epic = self._symbol_to_epic(symbol)

        params = [f'resolution={timeframe}', 'max=200']
        if start:
            params.append(f'from={start}')
        if end:
            params.append(f'to={end}')

        path = f"/api/v1/prices/{epic}?{'&'.join(params)}"
        data = self._make_request('GET', path, priority=self.PRIORITY_LOW, user=user)
        return data

    def get_closed_positions_with_pnl(self, days_back: int = 30) -> List[Dict]:
        # Capital historical close/PnL normalization is account-config dependent.
        # Raise to force safe fallback path in reconciliation service (preserve history).
        raise RuntimeError('Capital closed-position PnL fetch not implemented yet')

    def get_account_activities(self, activity_types: str = 'FILL', page_size: int = 100, direction: str = 'desc', after: Optional[str] = None, until: Optional[str] = None, **kwargs) -> List[Dict]:
        _ = (activity_types, page_size, direction, after, until, kwargs)
        # Not yet normalized for Capital; callers already handle empty lists.
        return []
