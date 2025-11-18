from django.contrib import admin
from .models import (
    Transaction, Trade, AuditLog, 
    KYCRecord, AMLAlert, ModelRegistry, TradableInstrument, 
    BrokerAccountSummary
)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['type', 'status', 'currency']
    search_fields = ['user__email', 'reference']


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['user', 'symbol', 'broker', 'instrument_type', 'side', 'quantity', 'entry_price', 'status', 'created_at']
    list_filter = ['broker', 'instrument_type', 'status', 'side']
    search_fields = ['user__email', 'symbol']


@admin.register(TradableInstrument)
class TradableInstrumentAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'market', 'exchange', 'currency', 'is_active']
    list_filter = ['market', 'exchange', 'is_active']
    search_fields = ['symbol', 'name']


@admin.register(BrokerAccountSummary)
class BrokerAccountSummaryAdmin(admin.ModelAdmin):
    list_display = ['user', 'broker', 'balance', 'available_funds', 'profit_loss', 'currency', 'last_updated']
    list_filter = ['broker', 'currency']
    search_fields = ['user__email']


admin.register(AuditLog)
admin.register(KYCRecord)
admin.register(AMLAlert)
admin.register(ModelRegistry)
