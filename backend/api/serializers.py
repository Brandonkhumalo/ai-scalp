from rest_framework import serializers
from .models import (
    Transaction, Trade, AuditLog, KYCRecord, AMLAlert,
    ModelRegistry, TradableInstrument, BrokerAccountSummary,
    AlpacaEquitySnapshot, AgentState,
)


class FloatDecimalField(serializers.DecimalField):
    """Outputs Decimal values as float in JSON for frontend compatibility.

    DRF's default DecimalField serializes to strings. The React frontend
    expects numeric JSON values, so this field converts to float on output
    while keeping Decimal precision for all server-side arithmetic.
    """

    def to_representation(self, value):
        if value is None:
            return None
        return float(value)


class TransactionSerializer(serializers.ModelSerializer):
    amount = FloatDecimalField(max_digits=15, decimal_places=2)

    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'amount', 'currency', 'payment_method',
            'reference', 'status', 'created_at',
        ]


class TradeReadSerializer(serializers.ModelSerializer):
    """Serializer for reading Trade objects (list / detail responses)."""
    quantity = FloatDecimalField(max_digits=20, decimal_places=8)
    entry_price = FloatDecimalField(max_digits=15, decimal_places=2)
    exit_price = FloatDecimalField(max_digits=15, decimal_places=2, allow_null=True)
    stop_loss = FloatDecimalField(max_digits=15, decimal_places=2, allow_null=True)
    take_profit = FloatDecimalField(max_digits=15, decimal_places=2, allow_null=True)
    profit_loss = FloatDecimalField(max_digits=15, decimal_places=2, allow_null=True)
    pnl = serializers.SerializerMethodField()

    class Meta:
        model = Trade
        fields = [
            'id', 'instrument_type', 'symbol', 'broker', 'quantity',
            'entry_price', 'exit_price', 'stop_loss', 'take_profit',
            'side', 'status', 'profit_loss', 'pnl', 'ai_confidence',
            'ai_signal_type', 'broker_deal_id', 'created_at', 'closed_at',
        ]

    def get_pnl(self, obj):
        if obj.profit_loss is not None:
            return float(obj.profit_loss)
        return None


class TradeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new Trade objects with input validation."""

    class Meta:
        model = Trade
        fields = [
            'instrument_type', 'symbol', 'quantity', 'entry_price',
            'side', 'ai_confidence', 'ai_signal_type',
        ]
        extra_kwargs = {
            'symbol': {'required': True},
            'quantity': {'required': True},
            'entry_price': {'required': True},
        }


class AuditLogSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', allow_null=True, read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user_id', 'action', 'resource_type', 'resource_id',
            'details', 'timestamp', 'ip_address',
        ]


class KYCRecordSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = KYCRecord
        fields = ['id', 'user_id', 'full_name', 'status', 'created_at']


class AMLAlertSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = AMLAlert
        fields = [
            'id', 'user_id', 'alert_type', 'severity', 'description',
            'status', 'created_at', 'resolved_at',
        ]


class ModelRegistrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelRegistry
        fields = [
            'id', 'name', 'version', 'model_type',
            'performance_metrics', 'validation_results',
            'deployed_at', 'is_active',
        ]


class TradableInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradableInstrument
        fields = [
            'id', 'symbol', 'name', 'market', 'exchange',
            'currency', 'isin', 'is_active',
        ]


class BrokerAccountSummarySerializer(serializers.ModelSerializer):
    balance = FloatDecimalField(max_digits=15, decimal_places=2)
    available_funds = FloatDecimalField(max_digits=15, decimal_places=2)
    total_deposit = FloatDecimalField(max_digits=15, decimal_places=2)
    profit_loss = FloatDecimalField(max_digits=15, decimal_places=2)

    class Meta:
        model = BrokerAccountSummary
        fields = [
            'id', 'broker', 'balance', 'available_funds',
            'total_deposit', 'profit_loss', 'currency', 'last_updated',
        ]


class AlpacaEquitySnapshotSerializer(serializers.ModelSerializer):
    equity = FloatDecimalField(max_digits=15, decimal_places=2)
    cash = FloatDecimalField(max_digits=15, decimal_places=2)
    unrealized_pl = FloatDecimalField(max_digits=15, decimal_places=2)
    daily_pl = FloatDecimalField(max_digits=15, decimal_places=2)

    class Meta:
        model = AlpacaEquitySnapshot
        fields = ['timestamp', 'equity', 'cash', 'unrealized_pl', 'daily_pl']
