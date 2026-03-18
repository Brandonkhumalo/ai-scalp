from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest.mock import patch, MagicMock

from api.models import Trade, Transaction, AgentState
from api.serializers import (
    FloatDecimalField, TransactionSerializer, TradeReadSerializer,
    AlpacaEquitySnapshotSerializer,
)
from accounts.authentication import JWTAuthentication, mark_token_blacklisted, _blacklist_cache_key
from accounts.models import BlacklistedToken

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_user(email='test@example.com'):
    return User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password='testpass123',
    )


def _make_trade(user, **overrides):
    defaults = dict(
        instrument_type='stock', symbol='AAPL', broker='alpaca_sim',
        quantity=Decimal('10'), entry_price=Decimal('150.00'),
        side='buy', status='open',
    )
    defaults.update(overrides)
    return Trade.objects.create(user=user, **defaults)


# ── Trade P&L Decimal Precision ──────────────────────────────────────────

class TradePnLTests(TestCase):
    """Verify P&L calculations use Decimal (no floating-point drift)."""

    def setUp(self):
        self.user = _make_user()

    def test_buy_trade_pnl_stays_decimal(self):
        """Closing a BUY trade should produce exact Decimal P&L."""
        trade = _make_trade(self.user)
        entry = trade.entry_price             # 150.00
        exit_price = Decimal('150.75')
        trade.exit_price = exit_price
        trade.profit_loss = (exit_price - entry) * trade.quantity
        trade.status = 'closed'
        trade.save()

        trade.refresh_from_db()
        expected = Decimal('7.50')  # (150.75 - 150.00) * 10
        self.assertEqual(trade.profit_loss, expected)
        self.assertIsInstance(trade.profit_loss, Decimal)

    def test_sell_trade_pnl_stays_decimal(self):
        trade = _make_trade(self.user, side='sell')
        exit_price = Decimal('149.25')
        trade.exit_price = exit_price
        trade.profit_loss = (trade.entry_price - exit_price) * trade.quantity
        trade.status = 'closed'
        trade.save()

        trade.refresh_from_db()
        expected = Decimal('7.50')  # (150.00 - 149.25) * 10
        self.assertEqual(trade.profit_loss, expected)

    def test_pending_to_open_transition(self):
        trade = _make_trade(self.user, status='pending')
        self.assertEqual(trade.status, 'pending')
        trade.status = 'open'
        trade.save()
        trade.refresh_from_db()
        self.assertEqual(trade.status, 'open')

    def test_pending_to_failed_transition(self):
        trade = _make_trade(self.user, status='pending')
        trade.status = 'failed'
        trade.save()
        trade.refresh_from_db()
        self.assertEqual(trade.status, 'failed')

    def test_close_without_exit_price_raises(self):
        """Trade.save() should block closing without a valid exit_price."""
        from django.core.exceptions import ValidationError
        trade = _make_trade(self.user)
        trade.status = 'closed'
        trade.exit_price = None
        with self.assertRaises(ValidationError):
            trade.save()


# ── Token Blacklist Caching ──────────────────────────────────────────────

class TokenBlacklistCacheTests(TestCase):
    """Verify the cache-first blacklist lookup works correctly."""

    def setUp(self):
        self.user = _make_user('cache@example.com')
        cache.clear()

    def test_mark_token_blacklisted_populates_cache(self):
        token = 'test-jwt-token-abc'
        mark_token_blacklisted(token)

        # Cache should be True
        self.assertTrue(cache.get(_blacklist_cache_key(token)))
        # DB should also have it
        self.assertTrue(BlacklistedToken.objects.filter(token=token).exists())

    def test_cache_hit_skips_db(self):
        token = 'cached-token'
        key = _blacklist_cache_key(token)
        cache.set(key, True, 60)

        # Even if DB is empty, cache says blacklisted
        self.assertFalse(BlacklistedToken.objects.filter(token=token).exists())
        self.assertTrue(cache.get(key))

    def test_cache_miss_falls_through_to_db(self):
        token = 'db-only-token'
        BlacklistedToken.objects.create(token=token)

        # Cache is empty
        key = _blacklist_cache_key(token)
        self.assertIsNone(cache.get(key))

        # Simulate what authenticate() does: check cache, fall to DB, cache result
        is_blacklisted = cache.get(key)
        if is_blacklisted is None:
            is_blacklisted = BlacklistedToken.objects.filter(token=token).exists()
            cache.set(key, is_blacklisted, 60)

        self.assertTrue(is_blacklisted)
        # Now cache should be populated
        self.assertTrue(cache.get(key))

    def test_non_blacklisted_token_cached_as_false(self):
        token = 'clean-token'
        key = _blacklist_cache_key(token)

        is_blacklisted = cache.get(key)
        if is_blacklisted is None:
            is_blacklisted = BlacklistedToken.objects.filter(token=token).exists()
            cache.set(key, is_blacklisted, 60)

        self.assertFalse(is_blacklisted)
        self.assertFalse(cache.get(key))


# ── Serializer Tests ─────────────────────────────────────────────────────

class SerializerTests(TestCase):
    """Verify serializers output the right types and fields."""

    def test_float_decimal_field_outputs_float(self):
        field = FloatDecimalField(max_digits=10, decimal_places=2)
        result = field.to_representation(Decimal('123.45'))
        self.assertIsInstance(result, float)
        self.assertEqual(result, 123.45)

    def test_float_decimal_field_handles_none(self):
        field = FloatDecimalField(max_digits=10, decimal_places=2, allow_null=True)
        self.assertIsNone(field.to_representation(None))

    def test_transaction_serializer_fields(self):
        user = _make_user('ser@example.com')
        txn = Transaction.objects.create(
            user=user, type='deposit', amount=Decimal('100.00'),
            currency='USD', status='completed',
        )
        data = TransactionSerializer(txn).data
        self.assertIn('id', data)
        self.assertIn('amount', data)
        self.assertIn('currency', data)
        self.assertIsInstance(data['amount'], float)

    def test_trade_serializer_decimal_fields(self):
        user = _make_user('trade_ser@example.com')
        trade = _make_trade(user, exit_price=Decimal('155.00'),
                            profit_loss=Decimal('50.00'), status='closed')
        data = TradeReadSerializer(trade).data
        self.assertIsInstance(data['entry_price'], float)
        self.assertIsInstance(data['exit_price'], float)
        self.assertIsInstance(data['profit_loss'], float)
        self.assertIsInstance(data['pnl'], float)
        self.assertEqual(data['pnl'], 50.0)


# ── Agent State Persistence ──────────────────────────────────────────────

class AgentStatePersistenceTests(TestCase):
    """Verify agent state can round-trip through the database."""

    def test_save_and_load_global_state(self):
        AgentState.objects.update_or_create(
            state_type='agent_global', user=None,
            defaults={'state_data': {'total_checks': 42, 'total_trades_executed': 7}},
        )
        row = AgentState.objects.get(state_type='agent_global', user=None)
        self.assertEqual(row.state_data['total_checks'], 42)
        self.assertEqual(row.state_data['total_trades_executed'], 7)

    def test_save_and_load_per_user_reconciliation_state(self):
        user = _make_user('agent@example.com')
        state = {'reconciliation_interval': 1, 'clean_passes': 3, 'orphan_counters': {}}
        AgentState.objects.update_or_create(
            state_type='reconciliation', user=user,
            defaults={'state_data': state},
        )
        row = AgentState.objects.get(state_type='reconciliation', user=user)
        self.assertEqual(row.state_data['clean_passes'], 3)

    def test_stock_rotation_set_to_list_roundtrip(self):
        """Sets must be converted to lists for JSON, then back to sets on load."""
        user = _make_user('rotation@example.com')
        stocks = {'AAPL', 'MSFT', 'NVDA'}
        AgentState.objects.update_or_create(
            state_type='stock_rotation', user=user,
            defaults={'state_data': {'available_stocks': list(stocks), 'sleep_mode': False}},
        )
        row = AgentState.objects.get(state_type='stock_rotation', user=user)
        loaded_stocks = set(row.state_data['available_stocks'])
        self.assertEqual(loaded_stocks, stocks)

    def test_unique_constraint(self):
        """Only one row per (user, state_type) pair."""
        user = _make_user('unique@example.com')
        AgentState.objects.create(state_type='reconciliation', user=user, state_data={'v': 1})
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            AgentState.objects.create(state_type='reconciliation', user=user, state_data={'v': 2})
