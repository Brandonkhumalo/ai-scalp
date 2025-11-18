from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import Trade
from api.ml_training_service import MLTradingModel
import numpy as np
from collections import Counter

User = get_user_model()

class Command(BaseCommand):
    help = 'Run ML diagnostic to identify SELL signal bias'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🔬 Running ML Diagnostic...'))
        self.stdout.write('=' * 70)
        
        # Get all users
        users = User.objects.all()
        
        for user in users:
            self.stdout.write(f'\n📊 Analyzing ML model for: {user.email}')
            self.stdout.write('-' * 70)
            
            # Get closed trades for this user
            closed_trades = Trade.objects.filter(user=user, status='closed').order_by('-created_at')
            
            if not closed_trades.exists():
                self.stdout.write(self.style.WARNING('   ⚠️  No closed trades - ML model not trained yet'))
                continue
            
            # Analyze trade distribution
            total_trades = closed_trades.count()
            buy_trades = closed_trades.filter(side='BUY').count()
            sell_trades = closed_trades.filter(side='SELL').count()
            
            self.stdout.write(f'\n   📈 TRADE DISTRIBUTION:')
            self.stdout.write(f'      Total Trades: {total_trades}')
            self.stdout.write(f'      BUY Trades:   {buy_trades} ({buy_trades/total_trades*100:.1f}%)')
            self.stdout.write(f'      SELL Trades:  {sell_trades} ({sell_trades/total_trades*100:.1f}%)')
            
            # Analyze profitability by side
            buy_profitable = closed_trades.filter(side='BUY', profit_loss__gt=0).count()
            sell_profitable = closed_trades.filter(side='SELL', profit_loss__gt=0).count()
            buy_losses = closed_trades.filter(side='BUY', profit_loss__lte=0).count()
            sell_losses = closed_trades.filter(side='SELL', profit_loss__lte=0).count()
            
            self.stdout.write(f'\n   💰 PROFITABILITY BY SIDE:')
            if buy_trades > 0:
                self.stdout.write(f'      BUY:  {buy_profitable} wins, {buy_losses} losses ({buy_profitable/buy_trades*100:.1f}% win rate)')
            if sell_trades > 0:
                self.stdout.write(f'      SELL: {sell_profitable} wins, {sell_losses} losses ({sell_profitable/sell_trades*100:.1f}% win rate)')
            
            # Analyze ML training labels
            profitable_count = closed_trades.filter(profit_loss__gt=0).count()
            loss_count = closed_trades.filter(profit_loss__lte=0).count()
            
            self.stdout.write(f'\n   🎯 ML TRAINING LABELS:')
            self.stdout.write(f'      Profitable (label=1): {profitable_count} ({profitable_count/total_trades*100:.1f}%)')
            self.stdout.write(f'      Loss (label=0):       {loss_count} ({loss_count/total_trades*100:.1f}%)')
            
            # Check if model is available
            ml_model = MLTradingModel()
            
            # Analyze recent trades for pattern
            recent_trades = closed_trades[:10]
            self.stdout.write(f'\n   🔍 RECENT 10 TRADES ANALYSIS:')
            
            buy_count = 0
            sell_count = 0
            for trade in recent_trades:
                if trade.side == 'BUY':
                    buy_count += 1
                else:
                    sell_count += 1
                    
                pnl_status = '✅ WIN' if trade.profit_loss and trade.profit_loss > 0 else '❌ LOSS'
                self.stdout.write(f'      {trade.side:4s} {trade.symbol:6s} @ ${trade.entry_price:.2f} → {pnl_status} ${trade.profit_loss or 0:.2f}')
            
            self.stdout.write(f'\n   📊 Recent Trade Bias: {buy_count} BUY vs {sell_count} SELL')
            
            # Diagnosis
            self.stdout.write(f'\n   🩺 DIAGNOSIS:')
            
            if sell_trades > buy_trades * 2:
                self.stdout.write(self.style.ERROR('      ❌ CRITICAL: Severe SELL bias detected!'))
                self.stdout.write(f'         → SELL trades ({sell_trades}) are {sell_trades/buy_trades:.1f}x more than BUY trades ({buy_trades})')
            elif sell_trades > buy_trades:
                self.stdout.write(self.style.WARNING('      ⚠️  Moderate SELL bias detected'))
                self.stdout.write(f'         → More SELL trades ({sell_trades}) than BUY trades ({buy_trades})')
            else:
                self.stdout.write(self.style.SUCCESS('      ✅ Trade distribution appears balanced'))
            
            if sell_losses == sell_trades and sell_trades > 0:
                self.stdout.write(self.style.ERROR('      ❌ CRITICAL: ALL SELL trades resulted in losses!'))
                self.stdout.write('         → Algorithm is executing SELL signals incorrectly')
            
            if loss_count > profitable_count:
                self.stdout.write(self.style.WARNING('      ⚠️  ML model trained on more losses than wins'))
                self.stdout.write('         → Model may be learning to predict losses instead of profits')
            
            self.stdout.write(f'\n   💡 RECOMMENDATIONS:')
            if sell_trades > buy_trades * 1.5:
                self.stdout.write('      1. Review indicator weighting - likely biased toward SELL signals')
                self.stdout.write('      2. Check if market conditions favor BUY but algorithm produces SELL')
                self.stdout.write('      3. Consider rebalancing training data with synthetic BUY examples')
            
            if loss_count > profitable_count * 1.5:
                self.stdout.write('      4. ML model is learning from too many losses')
                self.stdout.write('      5. Need more profitable trades to improve model accuracy')
                self.stdout.write('      6. Consider raising confidence threshold to filter bad trades')
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('✅ ML Diagnostic Complete\n'))
