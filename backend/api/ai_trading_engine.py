import os
import requests
import random
from datetime import datetime, timedelta
from django.utils import timezone
import pytz
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Trade
from .market_data_service import MarketDataService
from .ml_training_service import MLTradingModel
from .alpaca_account_service import AlpacaAccountService
import logging

logger = logging.getLogger(__name__)


class AITradingEngine:
    """AI Trading Engine for automated Alpaca stock trading"""
    
    def __init__(self, alpaca_api_key, alpaca_api_secret):
        self.alpaca_api_key = alpaca_api_key
        self.alpaca_api_secret = alpaca_api_secret
        self.alpaca_data_url = 'https://data.alpaca.markets'
        self.alpaca_trading_url = 'https://paper-api.alpaca.markets'
        
        # Initialize Alpaca account service with caching and request prioritization
        self.alpaca_account = AlpacaAccountService()
        
    def get_alpaca_headers(self):
        return {
            'APCA-API-KEY-ID': self.alpaca_api_key,
            'APCA-API-SECRET-KEY': self.alpaca_api_secret,
            'Content-Type': 'application/json',
        }
    
    def calculate_rsi(self, prices, period=14):
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow + signal:
            return 0, 0, 0
        
        # Calculate EMAs
        def ema(data, period):
            if len(data) < period:
                return []
            multiplier = 2 / (period + 1)
            ema_values = [sum(data[:period]) / period]
            for price in data[period:]:
                ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
            return ema_values
        
        # Calculate fast and slow EMAs
        fast_ema_values = ema(prices, fast)
        slow_ema_values = ema(prices, slow)
        
        # Align by trimming fast EMA to match slow EMA length
        # slow EMA starts later, so we need to offset fast EMA
        offset = slow - fast
        aligned_fast_ema = fast_ema_values[offset:]
        
        # Calculate MACD line (fast - slow)
        macd_values = [aligned_fast_ema[i] - slow_ema_values[i] for i in range(len(slow_ema_values))]
        
        # Calculate signal line (EMA of MACD)
        signal_values = ema(macd_values, signal)
        
        if not signal_values:
            return 0, 0, 0
        
        macd_line = macd_values[-1]
        signal_line = signal_values[-1]
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return prices[-1], prices[-1], prices[-1]
        
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = variance ** 0.5
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return upper_band, sma, lower_band
    
    def calculate_ema(self, prices, period):
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema_values = [sum(prices[:period]) / period]
        
        for price in prices[period:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        
        return ema_values[-1]
    
    def calculate_ema_trend(self, prices):
        """
        Calculate EMA 50/200 trend filter
        Returns: 'uptrend', 'downtrend', or 'neutral'
        """
        if len(prices) < 200:
            return 'neutral'  # Not enough data for trend detection
        
        ema_50 = self.calculate_ema(prices, 50)
        ema_200 = self.calculate_ema(prices, 200)
        
        if ema_50 is None or ema_200 is None:
            return 'neutral'
        
        # Golden cross (EMA 50 above EMA 200) = uptrend
        if ema_50 > ema_200 * 1.01:  # 1% buffer to avoid whipsaws
            return 'uptrend'
        # Death cross (EMA 50 below EMA 200) = downtrend
        elif ema_50 < ema_200 * 0.99:
            return 'downtrend'
        else:
            return 'neutral'
    
    def calculate_supertrend(self, bars, period=10, multiplier=3):
        """
        Calculate SuperTrend indicator
        Returns: 'uptrend', 'downtrend', current supertrend value
        """
        if len(bars) < period:
            return 'neutral', None
        
        # Extract high, low, close prices
        highs = [float(bar['h']) for bar in bars]
        lows = [float(bar['l']) for bar in bars]
        closes = [float(bar['c']) for bar in bars]
        
        # Calculate ATR (Average True Range)
        true_ranges = []
        for i in range(1, len(bars)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < period:
            return 'neutral', None
        
        # Simple moving average of true range
        atr = sum(true_ranges[-period:]) / period
        
        # Calculate basic upper and lower bands
        hl_avg = (highs[-1] + lows[-1]) / 2
        basic_upper = hl_avg + (multiplier * atr)
        basic_lower = hl_avg - (multiplier * atr)
        
        # Determine trend based on close price vs bands
        current_price = closes[-1]
        
        if current_price > basic_upper:
            return 'uptrend', basic_upper
        elif current_price < basic_lower:
            return 'downtrend', basic_lower
        else:
            return 'neutral', hl_avg
    
    def check_higher_timeframe_trend(self, symbol):
        """
        Check trend on higher timeframe (1 hour) to confirm overall direction
        Returns: dict with trend info
        """
        try:
            market_service = MarketDataService()
            
            # Get 1-hour bars for higher timeframe analysis
            bars_1h = market_service.get_bars(symbol, timeframe='1Hour', limit=200, use_fallback=True)
            
            if not bars_1h or len(bars_1h) < 50:
                logger.warning(f'Insufficient 1H data for trend check: {symbol}')
                return {'trend': 'neutral', 'confidence': 0}
            
            # Extract prices from 1H timeframe
            prices_1h = [float(bar['c']) for bar in bars_1h]
            
            # Calculate trend on 1H timeframe
            ema_trend = self.calculate_ema_trend(prices_1h)
            supertrend, supertrend_value = self.calculate_supertrend(bars_1h)
            
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
            market_service = MarketDataService()
            
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
            rsi = self.calculate_rsi(prices)
            macd_line, signal_line, histogram = self.calculate_macd(prices)
            upper_band, middle_band, lower_band = self.calculate_bollinger_bands(prices)
            
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
            
            # ML Prediction signal with enhanced 24-feature model
            ml_model = MLTradingModel()
            price_change = (current_price - prices[-2]) / prices[-2] if len(prices) > 1 else 0
            
            # Calculate side based on current signals for ML
            side_value = 1 if buy_signals > sell_signals else 0
            
            # Build 24-feature vector matching enhanced ML model
            # Advanced engineered features
            rsi_oversold = 1 if rsi < 30 else 0
            rsi_overbought = 1 if rsi > 70 else 0
            rsi_neutral = 1 if 40 <= rsi <= 60 else 0
            macd_strength = abs(macd_line - signal_line)
            macd_bullish = 1 if macd_line > signal_line else 0
            bb_width = (upper_band - lower_band) / middle_band if middle_band > 0 else 0
            bb_position = ((middle_band - lower_band) / (upper_band - lower_band)) if (upper_band - lower_band) > 0 else 0.5
            trend_strength = abs(price_change)
            trend_direction = 1 if price_change > 0 else -1
            high_volatility = 1 if volatility > 0.02 else 0
            low_volatility = 1 if volatility < 0.01 else 0
            volume_normalized = avg_volume / 1000000 if avg_volume > 0 else 0
            rsi_macd_alignment = 1 if (rsi < 30 and macd_bullish) or (rsi > 70 and not macd_bullish) else 0
            volatility_volume_ratio = volatility * volume_normalized if volume_normalized > 0 else 0
            
            ml_features = [
                # Original 10 features
                rsi, macd_line, signal_line, upper_band, lower_band, middle_band,
                avg_volume, price_change, volatility, side_value,
                # Advanced 14 features
                rsi_oversold, rsi_overbought, rsi_neutral,
                macd_strength, macd_bullish,
                bb_width, bb_position,
                trend_strength, trend_direction,
                high_volatility, low_volatility,
                volume_normalized,
                rsi_macd_alignment, volatility_volume_ratio,
                # Diversity features (6 features = 30 total) - use neutral defaults for prediction
                0.5, 0.0, 0.0, 0.0, 0.0, 0.0,
                # Loss pattern features (8 features = 38 total) - use neutral defaults for prediction
                0, 0.0,  # is_in_drawdown, drawdown_severity
                0, 1,    # is_volatility_spike, volatility_regime (1=medium default)
                0, 0,    # is_high_loss_condition, recent_loss_streak
                0, 0.0   # similar_past_losses, loss_pattern_score
            ]
            
            ml_prediction = ml_model.predict(ml_features)
            
            # Add ML signal if model is available and confident (60%+ temporarily, was 70%)
            if ml_prediction['model_available'] and ml_prediction['confidence'] > 0.60:
                if ml_prediction['prediction'] == 1:  # Profitable trade predicted
                    # ML suggests this is a good trade opportunity with high confidence
                    signal_strength += int(ml_prediction['confidence'] * 30)  # Up to 30 points for high confidence
                    logger.info(f"ML model predicts profitable trade with {ml_prediction['confidence']:.2%} confidence")
                else:
                    # ML suggests avoiding this trade (reduced penalty to allow more trades)
                    signal_strength -= 10  # Reduced from -20 to allow more trades
                    logger.info(f"ML model predicts unprofitable trade with {ml_prediction['confidence']:.2%} confidence")
            elif ml_prediction['model_available'] and ml_prediction['confidence'] > 0.55:
                # Medium confidence (55-60%) - moderate trade support
                if ml_prediction['prediction'] == 1:
                    signal_strength += int(ml_prediction['confidence'] * 15)  # Moderate weight
                else:
                    signal_strength -= 5  # Reduced from -8
            
            # Volume confirmation
            if volume_surge:
                signal_strength += 20
            
            # *** TREND DETECTION FILTER ***
            # Check higher timeframe trend before allowing trades
            trend_filter_blocked = False
            if not use_training_data:  # Only apply in live trading, not during ML training
                higher_tf_trend = self.check_higher_timeframe_trend(symbol)
                ema_trend_1min = self.calculate_ema_trend(prices)
                supertrend_1min, _ = self.calculate_supertrend(bars)
                
                logger.info(f'{symbol} Trend Check - 1H: {higher_tf_trend["trend"]} (conf: {higher_tf_trend["confidence"]:.1%}), 1M EMA: {ema_trend_1min}, 1M SuperTrend: {supertrend_1min}')
                
                # Block trades if higher timeframe shows strong opposite trend
                # This prevents buying in a downtrend or selling in an uptrend
                if higher_tf_trend['confidence'] >= 0.7:
                    if higher_tf_trend['trend'] == 'downtrend' and buy_signals > sell_signals:
                        logger.warning(f'⛔ Trend Filter: Blocking BUY signal - 1H timeframe shows strong downtrend')
                        trend_filter_blocked = True
                        # Return no signal to hard-block the trade
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
                            'trend_filter': 'BLOCKED: 1H downtrend blocks BUY'
                        }
                    elif higher_tf_trend['trend'] == 'uptrend' and sell_signals > buy_signals:
                        logger.warning(f'⛔ Trend Filter: Blocking SELL signal - 1H timeframe shows strong uptrend')
                        trend_filter_blocked = True
                        # Return no signal to hard-block the trade
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
                            'trend_filter': 'BLOCKED: 1H uptrend blocks SELL'
                        }
                
                # Boost confidence for trades aligned with trend
                if not trend_filter_blocked:
                    if higher_tf_trend['trend'] == 'uptrend' and buy_signals > sell_signals:
                        signal_strength += int(higher_tf_trend['confidence'] * 20)
                        logger.info(f'✅ Trend Filter: BUY aligned with 1H uptrend - boosting confidence')
                    elif higher_tf_trend['trend'] == 'downtrend' and sell_signals > buy_signals:
                        signal_strength += int(higher_tf_trend['confidence'] * 20)
                        logger.info(f'✅ Trend Filter: SELL aligned with 1H downtrend - boosting confidence')
            else:
                # For training data, store trend values for ML learning
                higher_tf_trend = {'trend': 'neutral', 'confidence': 0}
                ema_trend_1min = 'neutral'
                supertrend_1min = 'neutral'
            
            # Determine final signal based on majority vote
            signal = None
            confidence = 0
            
            logger.info(f'{symbol}: buy_signals={buy_signals}, sell_signals={sell_signals}, signal_strength={signal_strength}, ML={ml_prediction}')
            
            # AI-FIRST TRADING: Allow trades based on strong ML confidence (≥60% temporarily, was ≥70%) even with weak technical signals
            # This enables pure ML-driven trading when technical indicators are insufficient
            if ml_prediction['model_available'] and ml_prediction['confidence'] >= 0.60:
                if ml_prediction['prediction'] == 1:  # ML predicts profitable trade
                    signal = 'BUY'
                    confidence = min(max(signal_strength, 50), 95)  # Minimum 50 confidence for ML-only trades
                    logger.info(f'✅ ML-driven trade signal: {signal} with {ml_prediction["confidence"]:.1%} ML confidence')
                # If ML predicts loss with ≥60% confidence, don't trade even if technical signals suggest it
                elif ml_prediction['prediction'] == 0:
                    signal = None
                    logger.info(f'⛔ ML model predicts loss with {ml_prediction["confidence"]:.1%} confidence - trade blocked')
            
            # TECHNICAL SIGNAL OVERRIDE: If we have strong technical agreement (≥2 indicators), use that
            # This allows technical analysis to override ML when signals are very clear
            if buy_signals > sell_signals and buy_signals >= 2:
                signal = 'BUY'
                confidence = min(max(signal_strength, 0), 95)
            elif sell_signals > buy_signals and sell_signals >= 2:
                signal = 'SELL'
                confidence = min(max(signal_strength, 0), 95)
            
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
    
    def calculate_position_size(self, account_balance, risk_per_trade=0.02):
        """Calculate position size based on account balance and risk tolerance"""
        return account_balance * risk_per_trade
    
    def calculate_portfolio_concentration(self, user):
        """
        Calculate portfolio concentration metrics for diversity analysis
        
        PRODUCTION-GRADE: Uses LIVE Alpaca positions (30s cache) to prevent ghost positions
        from blocking trades. Falls back to DB on API failure with degraded-mode logging.
        
        Returns dict with concentration per symbol and diversity metrics
        """
        from decimal import Decimal
        
        # *** PRIMARY: Use Alpaca's LIVE positions (already cached 30s TTL) ***
        # This prevents ghost positions from inflating portfolio value
        alpaca_positions = self.alpaca_account.get_positions()
        
        # *** FALLBACK: Use DB if Alpaca API fails ***
        if alpaca_positions is None or (isinstance(alpaca_positions, list) and len(alpaca_positions) == 0):
            # Check if we have DB positions (distinguishes "no positions" from "API failure")
            open_trades = Trade.objects.filter(user=user, status='open', instrument_type='stock')
            
            if not open_trades.exists():
                # No positions anywhere - legitimate empty portfolio
                return {
                    'total_positions': 0,
                    'concentration': {},
                    'max_concentration': 0,
                    'diversity_score': 1.0,
                    'unique_symbols': 0,
                    'portfolio_value': 0
                }
            
            # API might be down - use DB as fallback
            if alpaca_positions is None:
                logger.warning('⚠️  DEGRADED MODE: Alpaca API unavailable. Using DB for concentration calculation.')
            
            # Fallback to DB calculation
            portfolio_value = Decimal('0')
            symbol_exposure = {}
            
            for trade in open_trades:
                position_value = Decimal(str(trade.quantity)) * Decimal(str(trade.entry_price))
                portfolio_value += position_value
                
                if trade.symbol not in symbol_exposure:
                    symbol_exposure[trade.symbol] = Decimal('0')
                symbol_exposure[trade.symbol] += position_value
        else:
            # *** PRIMARY PATH: Use Alpaca's live market values ***
            portfolio_value = Decimal('0')
            symbol_exposure = {}
            
            for position in alpaca_positions:
                # Use current market value (more accurate than entry price)
                position_value = Decimal(str(abs(float(position.get('market_value', 0)))))
                portfolio_value += position_value
                
                symbol = position.get('symbol')
                if symbol not in symbol_exposure:
                    symbol_exposure[symbol] = Decimal('0')
                symbol_exposure[symbol] += position_value
        
        # Calculate concentration percentages
        concentration = {}
        max_concentration = 0
        
        for symbol, value in symbol_exposure.items():
            if portfolio_value > 0:
                pct = float(value / portfolio_value * 100)
                concentration[symbol] = round(pct, 2)
                max_concentration = max(max_concentration, pct)
        
        # Calculate diversity score (Herfindahl index inverted)
        hhi = sum((pct ** 2) for pct in concentration.values())
        diversity_score = round(1 - (hhi / 10000), 3)
        
        return {
            'total_positions': len(symbol_exposure),
            'concentration': concentration,
            'max_concentration': round(max_concentration, 2),
            'diversity_score': diversity_score,
            'unique_symbols': len(symbol_exposure),
            'portfolio_value': float(portfolio_value)
        }
    
    def check_position_concentration(self, user, symbol, proposed_trade_value, max_concentration_pct=25):
        """
        Check if adding a new position would violate concentration limits
        
        CRITICAL FIX: Concentration is measured against ACCOUNT EQUITY, not sum of positions.
        This allows proper portfolio growth while maintaining risk controls.
        
        TEMPORARY OVERRIDE (Nov 2025): Increased from 15% to 25% to allow diversity building
        with existing over-concentrated positions. Will reduce back to 15% once portfolio
        diversity improves.
        
        Args:
            user: User object
            symbol: Stock symbol for the proposed trade
            proposed_trade_value: Dollar value of the proposed trade
            max_concentration_pct: Maximum allowed concentration in a single stock (default 25%, temp override)
        
        Returns:
            dict with 'allowed': bool and 'reason': str
        """
        from decimal import Decimal
        
        # Get current portfolio state
        portfolio = self.calculate_portfolio_concentration(user)
        
        # *** CRITICAL FIX: Use ACCOUNT EQUITY, not sum of positions ***
        # Get total account equity from Alpaca
        account_info = self.alpaca_account.get_account_info()
        if not account_info:
            logger.warning('⚠️  Cannot get account info for concentration check. Denying trade for safety.')
            return {
                'allowed': False,
                'reason': 'Cannot verify concentration (API unavailable)',
                'current_concentration': 0,
                'new_concentration': 0,
                'diversity_score': 0
            }
        
        account_equity = Decimal(str(account_info.get('equity', 0)))
        
        # Calculate proposed position's value (existing + new)
        current_portfolio_value = Decimal(str(portfolio.get('portfolio_value', 0)))
        current_symbol_exposure = Decimal(str(portfolio['concentration'].get(symbol, 0))) * current_portfolio_value / 100
        new_symbol_exposure = current_symbol_exposure + Decimal(str(proposed_trade_value))
        
        # Calculate new concentration percentage AGAINST ACCOUNT EQUITY
        if account_equity > 0:
            new_concentration_pct = float(new_symbol_exposure / account_equity * 100)
        else:
            new_concentration_pct = 100.0  # First trade is 100% concentrated
        
        # Allow first 2 positions to build initial portfolio diversity (bypass concentration check)
        # This prevents blocking when the second position would naturally be >40% in a small portfolio
        total_positions = portfolio.get('total_positions', 0)
        # Only check OPEN trades when determining if symbol is new (ignore historical closed trades)
        is_new_symbol = not Trade.objects.filter(user=user, symbol=symbol, status='open', instrument_type='stock').exists()
        
        # Debug logging to troubleshoot bypass logic
        logger.info(f"🔍 Concentration check for {symbol}: total_positions={total_positions}, is_new_symbol={is_new_symbol}, bypass_allowed={total_positions < 2 and is_new_symbol}")
        
        if total_positions < 2 and is_new_symbol:
            return {
                'allowed': True,
                'reason': f'Building initial portfolio diversity ({total_positions + 1}/2 positions)',
                'current_concentration': portfolio['concentration'].get(symbol, 0),
                'new_concentration': round(new_concentration_pct, 2),
                'diversity_score': portfolio['diversity_score']
            }
        
        # Check if it violates the concentration limit
        if new_concentration_pct > max_concentration_pct:
            return {
                'allowed': False,
                'reason': f'Position concentration limit exceeded: {symbol} would be {new_concentration_pct:.1f}% (max {max_concentration_pct}%)',
                'current_concentration': portfolio['concentration'].get(symbol, 0),
                'new_concentration': round(new_concentration_pct, 2),
                'diversity_score': portfolio['diversity_score']
            }
        
        return {
            'allowed': True,
            'reason': 'Within concentration limits',
            'current_concentration': portfolio['concentration'].get(symbol, 0),
            'new_concentration': round(new_concentration_pct, 2),
            'diversity_score': portfolio['diversity_score']
        }
    
    def check_scalping_targets(self, user):
        """Check and auto-close positions at scalping targets (3% profit / 2% stop-loss)"""
        from django.db import transaction as db_transaction
        from django.utils import timezone
        from decimal import Decimal
        from .market_data_service import MarketDataService
        from .models import Transaction
        
        try:
            with db_transaction.atomic():
                # Get user with lock
                user_model = type(user)
                user = user_model.objects.select_for_update().get(id=user.id)
                
                # Get all open STOCK trades only (equities-only platform)
                open_trades = Trade.objects.select_for_update().filter(user=user, status='open', instrument_type='stock')
                
                if not open_trades.exists():
                    return {'action': 'none', 'message': 'No open trades'}
                
                # SCALPING PARAMETERS (Adjusted for better position visibility)
                PROFIT_TARGET = Decimal('0.03')  # 3% profit target per trade
                STOP_LOSS = Decimal('0.02')  # 2% stop-loss per trade
                
                market_service = MarketDataService()
                trades_to_close = []
                
                # Get Alpaca positions for fallback pricing when snapshots fail (rate limiting protection)
                alpaca_positions = self.alpaca_account.get_positions() or []
                alpaca_price_map = {pos['symbol']: float(pos.get('current_price', 0)) for pos in alpaca_positions}
                
                for trade in open_trades:
                    # USER PREFERENCE: Scalping strategy enabled - same-day closes allowed
                    # NOTE: Alpaca may reject same-day closes due to PDT restrictions (21 day trades)
                    # User accepts this risk and prefers immediate profit-taking control
                    
                    # Get current market price with fallback logic
                    current_price = None
                    
                    # Try #1: Market data snapshot (most accurate)
                    snapshot = market_service.get_realtime_snapshot(trade.symbol)
                    if snapshot:
                        latest_quote = snapshot.get('latestQuote', {})
                        current_price = latest_quote.get('ap', latest_quote.get('bp'))
                    
                    # Try #2: Alpaca position price (fallback during rate limiting)
                    if not current_price and trade.symbol in alpaca_price_map:
                        current_price = alpaca_price_map[trade.symbol]
                        logger.info(f'   Using Alpaca position price for {trade.symbol}: ${current_price}')
                    
                    if current_price:
                        # Calculate current P&L and % change
                        if trade.side.lower() == 'buy':
                            pnl = (float(current_price) - float(trade.entry_price)) * float(trade.quantity)
                            pct_change = (Decimal(str(current_price)) - Decimal(str(trade.entry_price))) / Decimal(str(trade.entry_price))
                        else:
                            pnl = (float(trade.entry_price) - float(current_price)) * float(trade.quantity)
                            pct_change = (Decimal(str(trade.entry_price)) - Decimal(str(current_price))) / Decimal(str(trade.entry_price))
                        
                        # SCALPING LOGIC: Close if profit target hit OR stop-loss triggered
                        reason = None
                        if pct_change >= PROFIT_TARGET:
                            reason = f'Profit Target ({float(pct_change)*100:.2f}%)'
                            trades_to_close.append({
                                'trade': trade,
                                'current_price': current_price,
                                'pnl': pnl,
                                'pct_change': pct_change,
                                'reason': reason
                            })
                        elif pct_change <= -STOP_LOSS:
                            reason = f'Stop Loss ({float(pct_change)*100:.2f}%)'
                            trades_to_close.append({
                                'trade': trade,
                                'current_price': current_price,
                                'pnl': pnl,
                                'pct_change': pct_change,
                                'reason': reason
                            })
                
                if trades_to_close:
                    # Close all trades that hit targets
                    closed_count = 0
                    total_realized_profit = Decimal('0')
                    close_details = []
                    
                    for item in trades_to_close:
                        trade = item['trade']
                        current_price = item['current_price']
                        pnl = item['pnl']
                        pct_change = item['pct_change']
                        reason = item['reason']
                        
                        # *** PRODUCTION-GRADE POSITION CLOSE WITH VERIFICATION ***
                        try:
                            # USER PREFERENCE WARNING: Attempting same-day close (scalping mode)
                            us_eastern = pytz.timezone('US/Eastern')
                            trade_date_et = trade.created_at.astimezone(us_eastern).date()
                            current_date_et = timezone.now().astimezone(us_eastern).date()
                            
                            if trade_date_et == current_date_et:
                                logger.warning(f'⚠️  SCALPING MODE: Attempting same-day close for {trade.symbol}')
                                logger.warning(f'   Trade opened: {trade.created_at.astimezone(us_eastern).strftime("%Y-%m-%d %H:%M:%S %Z")}')
                                logger.warning(f'   Alpaca may reject due to PDT restrictions (user accepts this risk)')
                            
                            # Step 1: Submit close order to Alpaca
                            # NOTE: close_position() may return None if position already closed (404)
                            # This is OK - verification step is the source of truth!
                            logger.info(f'📤 Submitting close order for {trade.symbol} (qty={trade.quantity})...')
                            close_result = self.alpaca_account.close_position(trade.symbol)
                            
                            if close_result:
                                logger.info(f'✅ Close order submitted for {trade.symbol}, order ID: {close_result.get("id", "unknown")}')
                            else:
                                logger.info(f'ℹ️  Close returned None (position may already be closed) - proceeding to verification...')
                            
                            # Step 2: VERIFY position actually closed (ALWAYS RUN - this is the source of truth!)
                            # This handles ALL cases:
                            # - Position already closed (404) → Returns True
                            # - Position closed successfully → Returns True
                            # - Position still exists → Returns False
                            # - API errors / PDT rejections → Returns False
                            logger.info(f'🔍 Verifying position {trade.symbol} is fully closed...')
                            is_closed = self.alpaca_account.verify_position_closed(
                                symbol=trade.symbol,
                                max_retries=3,
                                retry_delay=1.0  # 1s, 2s, 4s exponential backoff
                            )
                            
                            if not is_closed:
                                # Check if this is likely a PDT rejection (same-day close)
                                if trade_date_et == current_date_et:
                                    logger.warning(f'🚫 PDT RESTRICTION: Alpaca rejected same-day close for {trade.symbol}')
                                    logger.warning(f'   Reason: Pattern Day Trader protection (21 day trades flagged)')
                                    logger.warning(f'   Position remains open: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f} ({float(pct_change)*100:.2f}%)')
                                    logger.warning(f'   Action: Position will attempt to close on next market day')
                                else:
                                    logger.error(f'❌ CRITICAL: Position {trade.symbol} still exists after close attempt!')
                                    if close_result:
                                        logger.error(f'   Close order ID: {close_result.get("id", "unknown")}')
                                        logger.error(f'   Close status: {close_result.get("status", "unknown")}')
                                    logger.error(f'   Position: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f}')
                                    logger.error(f'   ACTION REQUIRED: Check Alpaca dashboard immediately!')
                                continue  # Skip database update - position still open
                            
                            # Step 3: Success - position verified closed on Alpaca
                            logger.info(f'✅ VERIFIED: Position {trade.symbol} successfully closed on Alpaca')
                            logger.info(f'🎯 Scalping: {trade.symbol} (qty={trade.quantity}) - {reason}')
                            logger.info(f'   Realized P&L: ${pnl:.2f} ({float(pct_change)*100:.2f}%)')
                            
                        except Exception as e:
                            error_msg = str(e).lower()
                            
                            # Check if error is PDT-related
                            if any(pdt_keyword in error_msg for pdt_keyword in ['day trading', 'pdt', 'pattern day', 'buying power']):
                                logger.warning(f'🚫 PDT RESTRICTION: Alpaca rejected close for {trade.symbol}')
                                logger.warning(f'   Error: {e}')
                                logger.warning(f'   Position remains open: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f}')
                                logger.warning(f'   Action: Will retry on next market day')
                            else:
                                logger.error(f'❌ EXCEPTION closing Alpaca position {trade.symbol}: {e}')
                                logger.error(f'   Position: {trade.symbol}, Qty: {trade.quantity}, P&L: ${pnl:.2f}')
                                logger.error(f'   CRITICAL: Manual review required - position may be stuck!')
                                import traceback
                                logger.error(f'   Stack trace: {traceback.format_exc()}')
                            continue  # Skip this trade if exception occurred
                        
                        # Update database record
                        trade.exit_price = current_price
                        trade.profit_loss = pnl
                        trade.status = 'closed'
                        trade.closed_at = timezone.now()
                        trade.save()
                        
                        # Track P&L for statistics
                        total_realized_profit += Decimal(str(pnl))
                        
                        # Create transaction
                        Transaction.objects.create(
                            user=user,
                            type='trade_pnl',
                            amount=pnl,
                            currency='USD',
                            reference=f'Trade #{trade.id} Auto-Closed (Scalping: {reason})',
                            status='completed'
                        )
                        
                        close_details.append({
                            'symbol': trade.symbol,
                            'pnl': float(pnl),
                            'reason': reason
                        })
                        closed_count += 1
                    
                    user.save()
                    
                    return {
                        'action': 'scalping_auto_close',
                        'closed_count': closed_count,
                        'total_realized_profit': float(total_realized_profit),
                        'new_balance': float(user.usd_balance),
                        'close_details': close_details,
                        'message': f'Closed {closed_count} trades. Realized P&L: ${total_realized_profit:.2f}'
                    }
                else:
                    return {
                        'action': 'none',
                        'message': 'No trades hit scalping targets'
                    }
                    
        except Exception as e:
            logger.error(f'Error checking scalping targets: {str(e)}')
            return {'action': 'error', 'message': str(e)}
    
    def execute_ai_trade(self, user, symbol, instrument_type='stock'):
        """Execute an AI-driven trade based on market analysis"""
        try:
            # Check daily loss limit (8% of account balance - allows recovery trading)
            from django.utils import timezone
            from django.db.models import Sum
            from decimal import Decimal
            from django.db import transaction as db_transaction
            from django.contrib.auth import get_user_model
            
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
            
            # ML QUALITY GATE: Minimum 60% ML confidence required (TEMPORARILY REDUCED from 70%)
            # Bootstrap Mode: Skip ML checks when user.ml_bootstrap_mode=True (allows trading with technical analysis only)
            # NOTE: Threshold temporarily at 60% to accumulate more training data with clean Alpaca history
            # Will be restored to 70% once model has ≥50 closed trades for robust training
            ml_data = analysis.get('ml_prediction', {})
            
            if not user.ml_bootstrap_mode:
                # NORMAL MODE: Enforce ML model requirements
                if not ml_data.get('model_available', False):
                    logger.info(f"⛔ Trade rejected: ML model not available for {symbol}")
                    return {'success': False, 'message': 'ML model not available', 'analysis': analysis}
                
                ml_conf = ml_data.get('confidence', 0)
                ml_pred = ml_data.get('prediction', 0)
                
                # Reject if ML predicts loss
                if ml_pred == 0:
                    logger.info(f"⛔ Trade rejected: ML predicts LOSS with {ml_conf:.1%} confidence for {symbol}")
                    return {'success': False, 'message': f'ML model predicts unprofitable trade ({ml_conf:.1%} confidence)', 'analysis': analysis}
                
                # Reject if ML confidence below 60% (TEMPORARY THRESHOLD - will return to 70% after more data)
                if ml_conf < 0.60:
                    logger.info(f"⛔ Trade rejected: ML confidence {ml_conf:.1%} below 60% threshold for {symbol}")
                    return {'success': False, 'message': f'ML confidence below 60% threshold ({ml_conf:.1%})', 'analysis': analysis}
            else:
                # BOOTSTRAP MODE: Trading with technical analysis only (≥2 agreeing indicators already enforced)
                logger.info(f"🚀 BOOTSTRAP MODE: Executing trade without ML model (technical analysis only) for {symbol}")
            
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
            position_value = self.calculate_position_size(user_balance, risk_per_trade=0.10)
            
            # Get current price
            current_price = analysis['current_price']
            # For equities (stocks and options), use whole numbers
            quantity = int(position_value / current_price)
            
            if quantity <= 0:
                return {'success': False, 'message': 'Insufficient buying power'}
            
            # Calculate total trade cost
            trade_cost = Decimal(str(quantity)) * Decimal(str(current_price))
            
            # *** PORTFOLIO DIVERSITY CHECK ***
            # Check if this trade would violate concentration limits (max 25% per symbol - TEMP OVERRIDE)
            concentration_check = self.check_position_concentration(
                user=user,
                symbol=symbol,
                proposed_trade_value=float(trade_cost),
                max_concentration_pct=25  # TEMPORARY: Increased to 25% to allow diversity building
            )
            
            if not concentration_check['allowed']:
                logger.info(f'Trade rejected for {user.email}: {concentration_check["reason"]}')
                return {
                    'success': False,
                    'message': concentration_check['reason'],
                    'diversity_info': {
                        'current_concentration': concentration_check['current_concentration'],
                        'would_be_concentration': concentration_check['new_concentration'],
                        'diversity_score': concentration_check['diversity_score']
                    }
                }
            
            # *** CALCULATE STOP-LOSS AND TAKE-PROFIT ***
            # For BUY orders: stop_loss below entry, take_profit above
            # For SELL orders: stop_loss above entry, take_profit below
            stop_loss_pct = 0.02  # 2% stop-loss
            take_profit_pct = 0.03  # 3% take-profit
            
            if analysis['signal'].lower() == 'buy':
                stop_loss_price = round(current_price * (1 - stop_loss_pct), 2)
                take_profit_price = round(current_price * (1 + take_profit_pct), 2)
            else:  # sell
                stop_loss_price = round(current_price * (1 + stop_loss_pct), 2)
                take_profit_price = round(current_price * (1 - take_profit_pct), 2)
            
            logger.info(f'Setting bracket order for {symbol}: entry=${current_price:.2f}, stop_loss=${stop_loss_price:.2f}, take_profit=${take_profit_price:.2f}')
            
            # *** EXECUTE LIVE ORDER ON ALPACA WITH BRACKET (STOP-LOSS & TAKE-PROFIT) ***
            # Place actual order on Alpaca paper trading account with risk management
            alpaca_order = self.alpaca_account.place_order(
                symbol=symbol,
                qty=quantity,
                side=analysis['signal'].lower(),  # 'buy' or 'sell'
                order_type='market',
                time_in_force='day',
                stop_loss=stop_loss_price,
                take_profit=take_profit_price
            )
            
            if not alpaca_order:
                logger.error(f'Failed to place Alpaca order for {symbol}')
                return {
                    'success': False,
                    'message': 'Failed to place order on Alpaca. Please try again.'
                }
            
            order_id = alpaca_order.get('id')
            filled_price = alpaca_order.get('filled_avg_price', current_price)
            order_status = alpaca_order.get('status')
            
            logger.info(f'Alpaca order placed: {order_id}, status={order_status}, qty={quantity}, price=${filled_price}')
            
            # *** SAVE TRADE TO DATABASE ***
            with db_transaction.atomic():
                User = get_user_model()
                locked_user = User.objects.select_for_update().get(id=user.id)
                
                # Get portfolio diversity metrics BEFORE this trade
                portfolio_before = self.calculate_portfolio_concentration(locked_user)
                
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
                
                # Save trade to database with actual Alpaca order details
                trade = Trade.objects.create(
                    user=locked_user,
                    broker='alpaca_sim',
                    symbol=symbol,
                    side=analysis['signal'],
                    quantity=quantity,
                    entry_price=filled_price or current_price,  # Use actual filled price
                    stop_loss=stop_loss_price,
                    take_profit=take_profit_price,
                    instrument_type=instrument_type,
                    status='open',
                    ai_confidence=analysis['confidence'],
                    ai_signal_type=analysis_with_diversity,
                    broker_deal_id=order_id  # Store Alpaca order ID
                )
                
                # Transaction commits here - trade saved with Alpaca order ID
            
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
