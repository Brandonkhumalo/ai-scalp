import os
import requests
import random
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db import transaction as db_transaction
from django.contrib.auth import get_user_model
import pytz
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Trade
from .ml_training_service import MLTradingModel
from .trade_rules import check_trade_rules
from .technical_indicators import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_ema_trend, calculate_supertrend,
)
from .portfolio_service import (
    calculate_position_size, calculate_portfolio_concentration,
    check_position_concentration,
)
from .scalping_service import check_scalping_targets

logger = logging.getLogger(__name__)


class AITradingEngine:
    """AI Trading Engine for automated Alpaca stock trading"""
    
    def __init__(self, alpaca_api_key, alpaca_api_secret):
        self.alpaca_api_key = alpaca_api_key
        self.alpaca_api_secret = alpaca_api_secret
        self.alpaca_data_url = 'https://data.alpaca.markets'
        self.alpaca_trading_url = 'https://api.alpaca.markets'
        
        # Use shared singleton for caching and request prioritization
        from api.services import alpaca_service
        self.alpaca_account = alpaca_service
        
    def get_alpaca_headers(self):
        return {
            'APCA-API-KEY-ID': self.alpaca_api_key,
            'APCA-API-SECRET-KEY': self.alpaca_api_secret,
            'Content-Type': 'application/json',
        }

    def check_higher_timeframe_trend(self, symbol):
        """
        Check trend on higher timeframe (15 minutes) to confirm overall direction
        Returns: dict with trend info
        """
        try:
            from api.services import market_data_service as market_service
            
            # Get 15-minute bars for higher timeframe analysis (400 bars = ~4 days for better EMA calculation)
            bars_15m = market_service.get_bars(symbol, timeframe='15Min', limit=400, use_fallback=True)
            
            if not bars_15m or len(bars_15m) < 50:
                logger.warning(f'Insufficient 15M data for trend check: {symbol}')
                return {'trend': 'neutral', 'confidence': 0}
            
            # Extract prices from 15M timeframe
            prices_15m = [float(bar['c']) for bar in bars_15m]
            
            # Calculate trend on 15M timeframe
            ema_trend = calculate_ema_trend(prices_15m)
            supertrend, supertrend_value = calculate_supertrend(bars_15m)
            
            # Combine both indicators for confirmation
            if ema_trend == 'uptrend' and supertrend == 'uptrend':
                return {'trend': 'uptrend', 'confidence': 0.9, 'ema_trend': ema_trend, 'supertrend': supertrend}
            elif ema_trend == 'downtrend' and supertrend == 'downtrend':
                return {'trend': 'downtrend', 'confidence': 0.9, 'ema_trend': ema_trend, 'supertrend': supertrend}
            elif ema_trend == supertrend and ema_trend != 'neutral':
                return {'trend': ema_trend, 'confidence': 0.7, 'ema_trend': ema_trend, 'supertrend': supertrend}
            else:
                return {'trend': 'neutral', 'confidence': 0.5, 'ema_trend': ema_trend, 'supertrend': supertrend}
            
        except Exception as e:
            logger.error(f'Error checking higher timeframe trend: {str(e)}')
            return {'trend': 'neutral', 'confidence': 0}
    
    def analyze_market_sentiment(self, symbol, instrument_type='stock', use_training_data=False):
        """Analyze market sentiment using price action and volume with dual-source data"""
        try:
            # Use dual-source market data service
            from api.services import market_data_service as market_service
            
            if use_training_data:
                # For AI training, get more historical data
                bars = market_service.get_training_data(symbol, days=7)
            else:
                # For realtime analysis, get recent bars with fallback
                timeframe = '1Min'
                bars = market_service.get_bars(symbol, timeframe=timeframe, limit=100, use_fallback=True)
            
            # Ensure bars is a list and has enough data
            if not bars or not isinstance(bars, list) or len(bars) < 20:
                logger.warning(f'Insufficient bar data for {symbol}: got {len(bars) if bars else 0} bars (source: dual)')
                return None
            
            # Extract price and volume data
            prices = [float(bar['c']) for bar in bars]
            volumes = [float(bar['v']) for bar in bars]
            
            # Calculate technical indicators
            rsi = calculate_rsi(prices)
            macd_line, signal_line, histogram = calculate_macd(prices)
            upper_band, middle_band, lower_band = calculate_bollinger_bands(prices)
            
            # Calculate momentum
            momentum = (prices[-1] - prices[-5]) / prices[-5] * 100
            
            # Volume analysis
            avg_volume = sum(volumes[-10:]) / 10
            volume_surge = volumes[-1] > avg_volume * 1.5
            
            # Determine trading signal combining all three indicators + ML
            current_price = prices[-1]
            buy_signals = 0
            sell_signals = 0
            signal_strength = 0
            
            # RSI signals (oversold/overbought)
            if rsi < 30:
                buy_signals += 1
                signal_strength += 30
            elif rsi > 70:
                sell_signals += 1
                signal_strength += 30
            elif 40 < rsi < 60:
                # Neutral RSI contributes less but doesn't block
                signal_strength += 10
            
            # MACD signals (momentum and crossover)
            if histogram > 0:
                buy_signals += 1
                signal_strength += 25
            elif histogram < 0:
                sell_signals += 1
                signal_strength += 25
            
            # Bollinger Bands signals (price extremes)
            if current_price < lower_band:
                buy_signals += 1
                signal_strength += 25
            elif current_price > upper_band:
                sell_signals += 1
                signal_strength += 25
            elif lower_band < current_price < upper_band:
                # Price in middle band - weak signal
                signal_strength += 10
            
            # Calculate volatility from Bollinger Bands for ML prediction
            volatility = (upper_band - lower_band) / middle_band if middle_band > 0 else 0
            
            # ML Prediction with v5.0 15-feature model
            ml_model = MLTradingModel()
            price_change = (current_price - prices[-2]) / prices[-2] if len(prices) > 1 else 0
            side_value = 1 if buy_signals > sell_signals else 0

            # Derived features matching FEATURE_NAMES in ml_training_service.py
            bb_width = (upper_band - lower_band) / middle_band if middle_band > 0 else 0
            bb_position = ((middle_band - lower_band) / (upper_band - lower_band)) if (upper_band - lower_band) > 0 else 0.5
            volume_normalized = avg_volume / 1_000_000 if avg_volume > 0 else 0
            macd_bullish = 1 if macd_line > signal_line else 0
            rsi_macd_alignment = 1 if (rsi < 30 and macd_bullish) or (rsi > 70 and not macd_bullish) else 0
            volatility_volume = bb_width * volume_normalized

            # 15-feature vector (order must match FEATURE_NAMES)
            ml_features = [
                rsi, macd_line, signal_line,
                bb_width, bb_position,
                volume_normalized, price_change, side_value,
                rsi_macd_alignment,
                0.5,   # portfolio_diversity (neutral default for live prediction)
                0.0,   # portfolio_positions (neutral default)
                0,     # recent_loss_streak (neutral default)
                0,     # is_high_loss_condition (neutral default)
                0.0,   # drawdown_severity (neutral default)
                volatility_volume,
            ]
            
            ml_prediction = ml_model.predict(ml_features)
            
            # Add ML signal if model is available and confident (65%+ for quality trades)
            if ml_prediction['model_available'] and ml_prediction['confidence'] >= 0.65:
                if ml_prediction['prediction'] == 1:  # Profitable trade predicted
                    # ML suggests this is a good trade opportunity with high confidence
                    signal_strength += int(ml_prediction['confidence'] * 30)  # Up to 30 points for high confidence
                    logger.info(f"✅ ML model predicts PROFIT with {ml_prediction['confidence']:.2%} confidence (STRONG)")
                else:
                    # ML suggests avoiding this trade
                    signal_strength -= 20  # Strong penalty for predicted losses
                    logger.warning(f"⚠️ ML model predicts LOSS with {ml_prediction['confidence']:.2%} confidence (STRONG)")
            elif ml_prediction['model_available'] and ml_prediction['confidence'] >= 0.50:
                # Medium confidence (50-65%) - moderate trade support
                if ml_prediction['prediction'] == 1:
                    signal_strength += int(ml_prediction['confidence'] * 15)  # Moderate weight
                    logger.info(f"💡 ML model predicts PROFIT with {ml_prediction['confidence']:.2%} confidence (MEDIUM)")
                else:
                    signal_strength -= 10  # Moderate penalty
                    logger.warning(f"⚠️ ML model predicts LOSS with {ml_prediction['confidence']:.2%} confidence (MEDIUM)")
            
            # Volume confirmation
            if volume_surge:
                signal_strength += 20
            
            # *** TREND DETECTION FILTER - CHECK FIRST (MOVED BEFORE RSI OVERRIDE) ***
            # Check higher timeframe trend before allowing RSI override
            # This prevents synchronized buying of falling tech stocks during market selloffs
            trend_filter_blocked = False
            higher_tf_trend = {'trend': 'neutral', 'confidence': 0}
            
            if not use_training_data:  # Only apply in live trading, not during ML training
                higher_tf_trend = self.check_higher_timeframe_trend(symbol)
                ema_trend_1min = calculate_ema_trend(prices)
                supertrend_1min, _ = calculate_supertrend(bars)
                
                logger.info(f'{symbol} Trend Check - 15M: {higher_tf_trend["trend"]} (conf: {higher_tf_trend["confidence"]:.1%}), 1M EMA: {ema_trend_1min}, 1M SuperTrend: {supertrend_1min}')
            else:
                # For training data, store trend values for ML learning
                ema_trend_1min = 'neutral'
                supertrend_1min = 'neutral'
            
            # RSI contributes as one vote (lines 130-138 above) but does NOT override
            # other indicators. Extreme RSI alone is not a reliable signal — in a crash,
            # RSI stays below 30 for hours while price keeps falling.

            # Apply trend filter blocks
            if not use_training_data:
                # Block trades if higher timeframe shows strong opposite trend
                if higher_tf_trend['confidence'] >= 0.6:
                    if higher_tf_trend['trend'] == 'downtrend' and buy_signals > sell_signals:
                        logger.warning(f'⛔ Trend Filter: Blocking BUY signal - 15M timeframe shows strong downtrend')
                        trend_filter_blocked = True
                        return {
                            'signal': None,
                            'confidence': 0,
                            'momentum': momentum,
                            'rsi': rsi,
                            'macd': macd_line,
                            'macd_signal': signal_line,
                            'macd_histogram': histogram,
                            'bb_upper': upper_band,
                            'bb_middle': middle_band,
                            'bb_lower': lower_band,
                            'volume': avg_volume,
                            'volume_surge': volume_surge,
                            'volatility': volatility,
                            'current_price': current_price,
                            'ml_prediction': ml_prediction,
                            'trend_filter': 'BLOCKED: 15M downtrend blocks BUY'
                        }
                
                # Boost confidence for BUY trades aligned with uptrend
                # NOTE: SHORT SELLING DISABLED - No SELL signal boost
                if not trend_filter_blocked:
                    if higher_tf_trend['trend'] == 'uptrend' and buy_signals > sell_signals:
                        signal_strength += int(higher_tf_trend['confidence'] * 20)
                        logger.info(f'✅ Trend Filter: BUY aligned with 15M uptrend - boosting confidence')
            
            # Determine final signal based on majority vote
            signal = None
            confidence = 0
            
            logger.info(f'{symbol}: buy_signals={buy_signals}, sell_signals={sell_signals}, signal_strength={signal_strength}, ML={ml_prediction}')

            # Signal decision: require 2+ technical indicators to agree (majority vote).
            # ML prediction still contributes to signal_strength score but doesn't force trades.
            # NOTE: SHORT SELLING DISABLED — only BUY signals allowed.
            if buy_signals > sell_signals and buy_signals >= 2:
                signal = 'BUY'
                confidence = min(max(signal_strength, 0), 95)
            
            # *** FINAL GUARD: Block ALL BUY trades against strong higher timeframe downtrend ***
            # This catches ML-driven and technical-driven trades that bypassed earlier filters
            # CRITICAL: This prevents synchronized buying during market selloffs
            if signal and not use_training_data:
                if higher_tf_trend['confidence'] >= 0.6:
                    if signal == 'BUY' and higher_tf_trend['trend'] == 'downtrend':
                        logger.warning(f'⛔ FINAL GUARD: Blocking {signal} for {symbol} - 15M shows downtrend ({higher_tf_trend["confidence"]:.1%})')
                        signal = None
                        confidence = 0
            
            return {
                'signal': signal,
                'confidence': confidence,
                'momentum': momentum,
                'rsi': rsi,
                'macd': macd_line,
                'macd_signal': signal_line,
                'macd_histogram': histogram,
                'bb_upper': upper_band,
                'bb_middle': middle_band,
                'bb_lower': lower_band,
                'volume': avg_volume,
                'volume_surge': volume_surge,
                'volatility': volatility,
                'current_price': current_price,
                'ml_prediction': ml_prediction  # Include ML prediction data for quality checks
            }
            
        except Exception as e:
            logger.error(f'Error analyzing market sentiment: {str(e)}')
            return None

    def execute_ai_trade(self, user, symbol, instrument_type='stock'):
        """Execute an AI-driven trade based on market analysis"""
        try:
            # Check daily loss limit (8% of account balance - allows recovery trading)
            from django.db.models import Sum
            User = get_user_model()
            
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_trades = Trade.objects.filter(
                user=user,
                created_at__gte=today_start,
                status='closed',
                profit_loss__isnull=False
            )
            
            daily_pnl = today_trades.aggregate(total_pnl=Sum('profit_loss'))['total_pnl'] or Decimal('0')
            
            # Analyze market - analyze_market_sentiment already validates ML confidence and signal quality
            analysis = self.analyze_market_sentiment(symbol, instrument_type)
            if not analysis or not analysis['signal']:
                return {'success': False, 'message': 'No clear trading signal', 'analysis': analysis}
            
            # RULE ENGINE QUALITY GATE — replaces ML model for trade filtering.
            # Explicit rules based on what the ML model's feature importance revealed:
            # loss streaks, volatility, and daily P&L proximity to limits.
            bb_width = analysis.get('volatility', 0)
            rules_allowed, rules_reason = check_trade_rules(user, symbol, bb_width, analysis)
            if not rules_allowed:
                logger.info(f"Rule Engine blocked trade for {symbol}: {rules_reason}")
                return {'success': False, 'message': rules_reason, 'analysis': analysis}
            
            # *** ALPACA STOCK TRADING ONLY ***
            # Get Alpaca headers for placing orders (stocks only)
            headers = self.get_alpaca_headers()
            
            # *** USE LIVE ALPACA BALANCE (WITH CACHING) ***
            # Get real-time account data from Alpaca API (cached for 30s)
            account_info = self.alpaca_account.get_account_info()
            if not account_info:
                logger.error(f'Failed to fetch Alpaca account info for user {user.id}')
                return {
                    'success': False,
                    'message': 'Unable to fetch account balance from Alpaca. Please try again.'
                }
            
            # Use Alpaca buying power as user balance
            user_balance = float(account_info.get('buying_power', '0'))
            account_equity = float(account_info.get('equity', '0'))
            
            logger.info(f'Alpaca account: buying_power=${user_balance:.2f}, equity=${account_equity:.2f}')
            
            # Check if daily loss exceeds 8% limit (based on equity)
            daily_loss_limit = account_equity * 0.08
            if float(daily_pnl) < -daily_loss_limit:
                logger.warning(f'Daily loss limit exceeded for user {user.id}: {daily_pnl} < -{daily_loss_limit}')
                return {
                    'success': False, 
                    'message': f'Daily loss limit (8%) reached. Trading halted for today.',
                    'daily_pnl': float(daily_pnl),
                    'daily_loss_limit': daily_loss_limit
                }
            
            # Calculate position size using Alpaca buying power
            position_value = calculate_position_size(user_balance, risk_per_trade=0.05)
            
            # Get current price
            current_price = analysis['current_price']
            # Support fractional shares for small balances (round to 8 decimal places for precision)
            quantity = round(position_value / current_price, 8)
            
            # Minimum trade: 0.001 shares or $1, whichever is larger
            min_quantity = max(0.001, 1.0 / current_price)
            if quantity < min_quantity:
                logger.warning(f"💰 Insufficient funds: buying_power=${user_balance:.2f}, need ${min_quantity * current_price:.2f} minimum")
                return {'success': False, 'message': 'Insufficient buying power', 'insufficient_funds': True, 'buying_power': user_balance}
            
            # Calculate total trade cost
            trade_cost = Decimal(str(quantity)) * Decimal(str(current_price))
            
            # *** PORTFOLIO DIVERSITY CHECK WITH AUTO-ADJUSTMENT ***
            # Instead of blocking, reduce position size to fit within 25% limit
            max_concentration_pct = 25
            concentration_check = check_position_concentration(
                user=user,
                symbol=symbol,
                proposed_trade_value=float(trade_cost),
                max_concentration_pct=max_concentration_pct
            )
            
            if not concentration_check['allowed']:
                # Calculate maximum allowed position value to stay at 25% concentration
                portfolio = calculate_portfolio_concentration(user)
                current_symbol_exposure = Decimal(str(portfolio['concentration'].get(symbol, 0))) * Decimal(str(portfolio.get('portfolio_value', 0))) / 100
                
                # Max allowed total exposure = 25% of account equity
                max_allowed_exposure = Decimal(str(account_equity)) * Decimal(str(max_concentration_pct)) / 100
                
                # Max new trade value = max allowed - current exposure
                max_new_trade_value = max_allowed_exposure - current_symbol_exposure
                
                if max_new_trade_value <= 0:
                    logger.info(f'❌ Trade blocked for {user.email}: {symbol} already at or above {max_concentration_pct}% concentration')
                    return {
                        'success': False,
                        'message': f'{symbol} already at maximum concentration ({concentration_check["current_concentration"]:.1f}%)',
                        'diversity_info': {
                            'current_concentration': concentration_check['current_concentration'],
                            'would_be_concentration': concentration_check['new_concentration'],
                            'diversity_score': concentration_check['diversity_score']
                        }
                    }
                
                # Reduce quantity to fit within limit (support fractional shares)
                adjusted_quantity = round(float(max_new_trade_value) / current_price, 8)
                
                min_quantity = max(0.001, 1.0 / current_price)
                if adjusted_quantity < min_quantity:
                    logger.info(f'❌ Trade blocked for {user.email}: Adjusted quantity too small ({adjusted_quantity} shares)')
                    return {
                        'success': False,
                        'message': f'Cannot buy {symbol} - position too small after concentration limit adjustment',
                        'diversity_info': {
                            'current_concentration': concentration_check['current_concentration'],
                            'max_allowed': max_concentration_pct,
                            'diversity_score': concentration_check['diversity_score']
                        }
                    }
                
                # Update quantity and trade cost to adjusted values
                quantity = adjusted_quantity
                trade_cost = Decimal(str(quantity)) * Decimal(str(current_price))
                
                logger.info(f'📊 Position size adjusted for {symbol}: {int(position_value / current_price)} → {quantity} shares (staying within {max_concentration_pct}% limit)')
                
                # Re-check concentration with adjusted quantity
                concentration_check = check_position_concentration(
                    user=user,
                    symbol=symbol,
                    proposed_trade_value=float(trade_cost),
                    max_concentration_pct=max_concentration_pct
                )
            
            # *** CALCULATE STOP-LOSS AND TAKE-PROFIT ***
            # For BUY orders: stop_loss below entry, take_profit above
            # For SELL orders: stop_loss above entry, take_profit below
            # 1:2 risk/reward ratio — risk $1 to make $2
            stop_loss_pct = 0.01   # 1% stop-loss
            take_profit_pct = 0.02  # 2% take-profit
            
            if analysis['signal'].lower() == 'buy':
                stop_loss_price = round(current_price * (1 - stop_loss_pct), 2)
                take_profit_price = round(current_price * (1 + take_profit_pct), 2)
            else:  # sell
                stop_loss_price = round(current_price * (1 + stop_loss_pct), 2)
                take_profit_price = round(current_price * (1 - take_profit_pct), 2)
            
            logger.info(f'Setting bracket order for {symbol}: entry=${current_price:.2f}, stop_loss=${stop_loss_price:.2f}, take_profit=${take_profit_price:.2f}')
            
            # ── Step 1: Create a PENDING trade before placing the Alpaca order ──
            # This closes the divergence window — if the process crashes after the
            # Alpaca order but before the DB write, the pending row survives for
            # startup reconciliation.
            with db_transaction.atomic():
                locked_user = User.objects.select_for_update().get(id=user.id)

                # Get portfolio diversity metrics BEFORE this trade
                portfolio_before = calculate_portfolio_concentration(locked_user)

                # Enrich analysis with diversity metrics for ML training
                analysis_with_diversity = {
                    **analysis,
                    'portfolio_diversity_score': portfolio_before['diversity_score'],
                    'portfolio_max_concentration': portfolio_before['max_concentration'],
                    'portfolio_unique_symbols': portfolio_before['unique_symbols'],
                    'portfolio_total_positions': portfolio_before['total_positions'],
                    'symbol_concentration_before': portfolio_before['concentration'].get(symbol, 0),
                    'symbol_concentration_after': concentration_check['new_concentration']
                }

                trade = Trade.objects.create(
                    user=locked_user,
                    broker='alpaca_sim',
                    symbol=symbol,
                    side=analysis['signal'],
                    quantity=quantity,
                    entry_price=current_price,  # Estimated; updated after fill
                    stop_loss=stop_loss_price,
                    take_profit=take_profit_price,
                    instrument_type=instrument_type,
                    status='pending',
                    ai_confidence=analysis['confidence'],
                    ai_signal_type=analysis_with_diversity,
                )

            # ── Step 2: Place limit order at current price ──
            # Limit orders avoid slippage (~0.05-0.3% per trade on market orders).
            # Slight price cushion (+0.02% for buys, -0.02% for sells) ensures fill
            # while still controlling entry price.
            side_str = analysis['signal'].lower()
            if side_str == 'buy':
                limit_price = round(current_price * 1.0002, 2)  # Tiny cushion above ask
            else:
                limit_price = round(current_price * 0.9998, 2)  # Tiny cushion below bid

            alpaca_order = self.alpaca_account.place_order(
                symbol=symbol,
                qty=quantity,
                side=side_str,
                order_type='limit',
                time_in_force='day',
                stop_loss=stop_loss_price,
                take_profit=take_profit_price,
                limit_price=limit_price,
            )

            if not alpaca_order:
                # Order failed — mark the pending trade as failed
                trade.status = 'failed'
                trade.save(update_fields=['status'])
                logger.error(f'Failed to place Alpaca order for {symbol}')
                return {
                    'success': False,
                    'message': 'Failed to place order on Alpaca. Please try again.'
                }

            # ── Step 3: Promote pending → open with actual fill details ──
            order_id = alpaca_order.get('id')
            filled_price = alpaca_order.get('filled_avg_price', current_price)
            order_status = alpaca_order.get('status')

            logger.info(f'Alpaca order placed: {order_id}, status={order_status}, qty={quantity}, price=${filled_price}')

            trade.status = 'open'
            trade.entry_price = filled_price or current_price
            trade.broker_deal_id = order_id
            trade.save(update_fields=['status', 'entry_price', 'broker_deal_id'])

            return {
                'success': True,
                'trade_id': trade.id,
                'order_id': order_id,
                'alpaca_status': order_status,
                'symbol': symbol,
                'side': analysis['signal'],
                'quantity': quantity,
                'price': filled_price or current_price,
                'confidence': analysis['confidence'],
                'analysis': analysis,
                'broker': 'Alpaca (Live API)'
            }
            
        except Exception as e:
            logger.error(f'Error executing AI trade: {str(e)}')
            # If exception occurs, transaction automatically rolls back - balance is refunded
            return {'success': False, 'message': str(e)}


class AITradingView(APIView):
    """API endpoint for AI-driven trading"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            alpaca_api_key = os.getenv('ALPACA_API_KEY')
            alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
            
            if not alpaca_api_key or not alpaca_api_secret:
                return Response(
                    {'error': 'Alpaca API credentials not configured'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            engine = AITradingEngine(alpaca_api_key, alpaca_api_secret)
            
            action = request.data.get('action')
            
            if action == 'analyzeSentiment':
                symbol = request.data.get('symbol')
                instrument_type = request.data.get('instrument_type', 'stock')
                
                if not symbol:
                    return Response(
                        {'error': 'Symbol is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                analysis = engine.analyze_market_sentiment(symbol, instrument_type)
                if not analysis:
                    return Response(
                        {
                            'error': 'Insufficient market data',
                            'message': f'Unable to analyze {symbol}. The market may be closed or data is unavailable.',
                            'signal': 'NEUTRAL',
                            'confidence': 0,
                            'momentum': 0,
                            'rsi': 50,
                            'macd': 0,
                            'current_price': 0
                        },
                        status=status.HTTP_200_OK
                    )
                
                # Ensure confidence is always a valid number
                if 'confidence' not in analysis or analysis['confidence'] is None:
                    analysis['confidence'] = 0
                
                return Response(analysis, status=status.HTTP_200_OK)
            
            elif action == 'executeTrade':
                symbol = request.data.get('symbol')
                instrument_type = request.data.get('instrument_type', 'stock')
                
                result = engine.execute_ai_trade(request.user, symbol, instrument_type)
                
                if result['success']:
                    return Response(result, status=status.HTTP_200_OK)
                else:
                    return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
            elif action == 'autoTrade':
                # Auto-trade multiple symbols
                symbols = request.data.get('symbols', ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'])
                instrument_type = request.data.get('instrument_type', 'stock')
                
                results = []
                for symbol in symbols:
                    result = engine.execute_ai_trade(request.user, symbol, instrument_type)
                    results.append({
                        'symbol': symbol,
                        'result': result
                    })
                
                return Response({'trades': results}, status=status.HTTP_200_OK)
            
            else:
                return Response(
                    {'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f'Error in AI trading: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
