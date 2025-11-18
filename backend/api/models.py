from django.db import models
from django.conf import settings


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('trade_pnl', 'Trade P&L'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'USD'),
        ('ZWL', 'ZWL'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    payment_method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.type} - {self.amount} {self.currency}"


class Trade(models.Model):
    INSTRUMENT_CHOICES = [
        ('stock', 'Stock'),
        ('forex', 'Forex'),
    ]
    
    SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    
    BROKER_CHOICES = [
        ('alpaca_sim', 'Alpaca (Simulated)'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trades')
    instrument_type = models.CharField(max_length=20, choices=INSTRUMENT_CHOICES)
    symbol = models.CharField(max_length=50)
    broker = models.CharField(max_length=20, choices=BROKER_CHOICES, default='alpaca_sim')
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=15, decimal_places=2)
    exit_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    stop_loss = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    take_profit = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    side = models.CharField(max_length=10, choices=SIDE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    profit_loss = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    ai_confidence = models.FloatField(blank=True, null=True)
    ai_signal_type = models.JSONField(blank=True, null=True)
    broker_deal_id = models.CharField(max_length=255, blank=True, null=True)  # Capital.com deal ID for forex/stock trades
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        """
        Override save to enforce exit_price validation and prevent $0.00 bug.
        BLOCKS trades from closing without a valid exit price.
        """
        import logging
        import traceback
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        
        logger = logging.getLogger(__name__)
        
        # Check if this is a closure operation
        if self.status == 'closed':
            # Get the old state if this is an update
            is_update = self.pk is not None
            old_status = None
            
            if is_update:
                try:
                    old_trade = Trade.objects.get(pk=self.pk)
                    old_status = old_trade.status
                except Trade.DoesNotExist:
                    pass
            
            # Detect if we're transitioning to closed
            is_closing = old_status != 'closed' if old_status else True
            
            if is_closing:
                # CRITICAL: ENFORCE exit_price validation - BLOCK the save if invalid
                if not self.exit_price or self.exit_price == Decimal('0'):
                    logger.error('🚨 CRITICAL: Attempted to close trade WITHOUT valid exit_price - BLOCKING!')
                    logger.error(f'   Trade ID: {self.pk}')
                    logger.error(f'   Symbol: {self.symbol}')
                    logger.error(f'   User: {self.user.email}')
                    logger.error(f'   Entry Price: ${self.entry_price}')
                    logger.error(f'   Exit Price: ${self.exit_price or 0}')
                    logger.error('   CALL STACK:')
                    for line in traceback.format_stack():
                        logger.error(f'     {line.strip()}')
                    
                    # PREVENT the save - raise exception
                    raise ValidationError(
                        f'Cannot close trade {self.symbol} without a valid exit_price. '
                        f'Current exit_price: ${self.exit_price or 0}. '
                        'This prevents data corruption.'
                    )
                
                # Log successful closures for debugging
                logger.info(f'✅ Trade Closing: {self.symbol} for {self.user.email}')
                logger.info(f'   Entry: ${self.entry_price}, Exit: ${self.exit_price}, P&L: ${self.profit_loss or 0}')
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.symbol} ({self.broker}) - {self.side}"


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=255)
    details = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email if self.user else 'System'} - {self.action}"


class KYCRecord(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_record')
    full_name = models.CharField(max_length=255)
    id_number = models.CharField(max_length=100)
    id_document = models.TextField(blank=True)
    proof_of_address = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - KYC {self.status}"


class AMLAlert(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='aml_alerts')
    alert_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} - {self.alert_type} - {self.severity}"


class ModelRegistry(models.Model):
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=50)
    model_type = models.CharField(max_length=100)
    performance_metrics = models.JSONField(blank=True, null=True)
    validation_results = models.JSONField(blank=True, null=True)
    deployed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} v{self.version}"


class TradableInstrument(models.Model):
    """
    Allowlist of stocks/instruments tradable via Capital.com
    """
    MARKET_CHOICES = [
        ('US', 'United States'),
        ('EU', 'European Union'),
        ('JP', 'Japan'),
        ('HK', 'Hong Kong'),
        ('SG', 'Singapore'),
        ('IN', 'India'),
        ('AU', 'Australia'),
        ('ZA', 'South Africa'),
    ]
    
    EXCHANGE_CHOICES = [
        ('NYSE', 'New York Stock Exchange'),
        ('NASDAQ', 'NASDAQ'),
        ('XETRA', 'Deutsche Börse XETRA (Germany)'),
        ('LSE', 'London Stock Exchange'),
        ('EURONEXT', 'Euronext (France)'),
        ('TSE', 'Tokyo Stock Exchange'),
        ('HKEX', 'Hong Kong Stock Exchange'),
        ('SGX', 'Singapore Exchange'),
        ('NSE', 'National Stock Exchange of India'),
        ('BSE', 'Bombay Stock Exchange'),
        ('ASX', 'Australian Securities Exchange'),
        ('JSE', 'Johannesburg Stock Exchange'),
        ('OTHER', 'Other Exchange'),
    ]
    
    symbol = models.CharField(max_length=50, unique=True)  # Capital.com symbol/epic
    name = models.CharField(max_length=255)
    market = models.CharField(max_length=10, choices=MARKET_CHOICES)
    exchange = models.CharField(max_length=20, choices=EXCHANGE_CHOICES, default='OTHER')
    currency = models.CharField(max_length=3, default='USD')
    isin = models.CharField(max_length=12, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['market', 'symbol']
    
    def __str__(self):
        return f"{self.symbol} ({self.market}) - {self.name}"


class BrokerAccountSummary(models.Model):
    """
    Per-user, per-broker account balance snapshots
    """
    BROKER_CHOICES = [
        ('alpaca_sim', 'Alpaca (Simulated)'),
        ('capital_stock', 'Capital.com (Stock)'),
        ('capital_forex', 'Capital.com (Forex)'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='broker_summaries')
    broker = models.CharField(max_length=20, choices=BROKER_CHOICES)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    available_funds = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_deposit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    profit_loss = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['user', 'broker']]
        ordering = ['-last_updated']
    
    def __str__(self):
        return f"{self.user.email} - {self.broker}: {self.balance} {self.currency}"


class AlpacaEquitySnapshot(models.Model):
    """
    Stores periodic Alpaca equity snapshots for P&L charting
    Automatically created when Alpaca account data is fetched
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alpaca_snapshots')
    timestamp = models.DateTimeField(auto_now_add=True)
    equity = models.DecimalField(max_digits=15, decimal_places=2)  # Total equity
    cash = models.DecimalField(max_digits=15, decimal_places=2)  # Cash balance
    unrealized_pl = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Unrealized P&L
    daily_pl = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Daily P&L (today's equity - yesterday's closing)
    
    class Meta:
        db_table = 'alpaca_equity_snapshots'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.timestamp.strftime('%Y-%m-%d %H:%M')} - ${self.equity}"
