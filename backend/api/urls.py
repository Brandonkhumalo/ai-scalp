from django.urls import path
from .views import (
    TransactionListView, TradeListView, TradeDetailView, CheckProfitTakingView, AuditLogListView, KYCListView,
    AMLAlertListView, ModelRegistryListView, ProfileView, BalanceHistoryView,
    UserListView, AssignRoleView, RemoveRoleView, CloseProfitableTradesView,
    ManualAITradingView, AgentStatusView, AlpacaAccountView, AlpacaEquityHistoryView, PerformanceAnalyticsView
)
from .alpaca_service import AlpacaMarketDataView
from .ai_trading_engine import AITradingView
#from .views_market import MarketDataView
from .views_ml import MLModelView
from .admin_views import (
    get_all_users, approve_user, reject_user,
    get_realtime_trading_stats, get_platform_overview
)
from .test_roles import TestRolesView

from .views import get_all_data, delete_old_trades_and_show_wins

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='transaction_list'),
    path('trades/', TradeListView.as_view(), name='trade_list'),
    path('trades/<int:trade_id>/', TradeDetailView.as_view(), name='trade_detail'),
    path('check-profit-taking/', CheckProfitTakingView.as_view(), name='check_profit_taking'),
    path('close-profitable-trades/', CloseProfitableTradesView.as_view(), name='close_profitable_trades'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit_log_list'),
    path('kyc-records/', KYCListView.as_view(), name='kyc_record_list'),
    path('aml-alerts/', AMLAlertListView.as_view(), name='aml_alert_list'),
    path('model-registry/', ModelRegistryListView.as_view(), name='model_registry_list'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('balance-history/', BalanceHistoryView.as_view(), name='balance_history'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('assign-role/', AssignRoleView.as_view(), name='assign_role'),
    path('remove-role/', RemoveRoleView.as_view(), name='remove_role'),
    path('alpaca-market-data/', AlpacaMarketDataView.as_view(), name='alpaca_market_data'),
    path('ai-trading/', AITradingView.as_view(), name='ai_trading'),
    #path('market-data/', MarketDataView.as_view(), name='market_data'),
    path('ml-model/', MLModelView.as_view(), name='ml_model'),
    path('admin/users/', get_all_users, name='admin_users'),
    path('admin/users/<int:user_id>/approve/', approve_user, name='admin_approve_user'),
    path('admin/users/<int:user_id>/reject/', reject_user, name='admin_reject_user'),
    path('admin/trading-stats/', get_realtime_trading_stats, name='admin_trading_stats'),
    path('admin/platform-overview/', get_platform_overview, name='admin_platform_overview'),
    path('admin/platform-stats/', get_platform_overview, name='admin_platform_stats'),
    path('test-roles/', TestRolesView.as_view(), name='test_roles'),
    path('autonomous-agent/status/', AgentStatusView.as_view(), name='autonomous_agent_status'),
    path('manual-ai-trading/', ManualAITradingView.as_view(), name='manual_ai_trading'),
    path('alpaca-account/', AlpacaAccountView.as_view(), name='alpaca_account'),
    path('alpaca-equity-history/', AlpacaEquityHistoryView.as_view(), name='alpaca_equity_history'),
    path('performance-analytics/', PerformanceAnalyticsView.as_view(), name='performance_analytics'),

    path('all_data/', get_all_data, name="get_user_data"),
    path("cleanup-trades/", delete_old_trades_and_show_wins),
]
