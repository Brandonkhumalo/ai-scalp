import os
import pickle
import logging
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class MLTradingModel:
    """Machine Learning model for trading predictions with automatic retraining"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.model_path = 'backend/ml_models/trading_model.pkl'
        self.scaler_path = 'backend/ml_models/scaler.pkl'
        self.metrics_path = 'backend/ml_models/metrics.json'
        self.version_path = 'backend/ml_models/model_version.txt'
        self.min_trades_for_training = 5  # Start learning with 5 trades, improve as more data comes in
        self.retrain_interval_hours = 24
        self.expected_features = 38  # Updated to 38 features (30 + 8 advanced loss pattern features)
        self.model_version = '4.0'  # Version 4.0 with 38 features (trend detection, drawdown, volatility spike, loss pattern learning)
        
        # Load training cutoff date from Django settings
        from django.conf import settings
        self.training_cutoff = getattr(settings, 'ML_TRAINING_CUTOFF_DATE', None)
        
        # Create models directory if it doesn't exist
        os.makedirs('backend/ml_models', exist_ok=True)
        
        # Load existing model if available and compatible
        self.load_model()
    
    def extract_features(self, trade_data):
        """
        Extract enhanced features from trade data for ML training
        Features include technical indicators, market conditions, and engineered features
        """
        features = []
        
        for trade in trade_data:
            rsi = trade.get('rsi', 50)
            macd = trade.get('macd', 0)
            macd_signal = trade.get('macd_signal', 0)
            bb_upper = trade.get('bb_upper', 0)
            bb_lower = trade.get('bb_lower', 0)
            bb_middle = trade.get('bb_middle', 0)
            volume = trade.get('volume', 0)
            price_change = trade.get('price_change', 0)
            volatility = trade.get('volatility', 0)
            side = 1 if trade.get('side') == 'BUY' else 0
            
            # Advanced engineered features for 90%+ win rate
            # RSI-based features
            rsi_oversold = 1 if rsi < 30 else 0  # Strong buy signal
            rsi_overbought = 1 if rsi > 70 else 0  # Strong sell signal
            rsi_neutral = 1 if 40 <= rsi <= 60 else 0  # Neutral zone
            
            # MACD strength
            macd_strength = abs(macd - macd_signal)  # Signal strength
            macd_bullish = 1 if macd > macd_signal else 0  # Bullish crossover
            
            # Bollinger Band position
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            bb_position = ((bb_middle - bb_lower) / (bb_upper - bb_lower)) if (bb_upper - bb_lower) > 0 else 0.5
            
            # Trend indicators
            trend_strength = abs(price_change)  # How strong is the trend
            trend_direction = 1 if price_change > 0 else -1  # Trend direction
            
            # Volatility-based risk
            high_volatility = 1 if volatility > 0.02 else 0  # High risk
            low_volatility = 1 if volatility < 0.01 else 0  # Low risk
            
            # Volume confirmation
            volume_normalized = volume / 1000000 if volume > 0 else 0  # Normalize volume
            
            # Interaction features (combinations that predict success)
            rsi_macd_alignment = 1 if (rsi < 30 and macd_bullish) or (rsi > 70 and not macd_bullish) else 0
            volatility_volume_ratio = volatility * volume_normalized if volume_normalized > 0 else 0
            
            # Portfolio diversity features (6 features)
            portfolio_diversity_score = trade.get('portfolio_diversity_score', 0.5)  # 0=concentrated, 1=diverse
            portfolio_max_concentration = trade.get('portfolio_max_concentration', 0) / 100  # Normalize to 0-1
            portfolio_unique_symbols = min(trade.get('portfolio_unique_symbols', 0) / 10, 1.0)  # Normalize (max 10)
            portfolio_total_positions = min(trade.get('portfolio_total_positions', 0) / 20, 1.0)  # Normalize (max 20)
            symbol_concentration_before = trade.get('symbol_concentration_before', 0) / 100  # Normalize to 0-1
            symbol_concentration_after = trade.get('symbol_concentration_after', 0) / 100  # Normalize to 0-1
            
            # Advanced loss pattern features (8 features) - Learn from drawdown, volatility spikes, and losing patterns
            # Drawdown zone detection (2 features)
            is_in_drawdown = 1 if trade.get('max_drawdown_pct', 0) > 5 else 0  # In significant drawdown (>5%)
            drawdown_severity = min(trade.get('max_drawdown_pct', 0) / 20, 1.0)  # Normalize drawdown (cap at 20%)
            
            # Volatility spike detection (2 features)
            is_volatility_spike = 1 if volatility > 0.03 else 0  # Extreme volatility (>3%)
            volatility_regime = 2 if volatility > 0.03 else (1 if volatility > 0.015 else 0)  # 0=low, 1=medium, 2=high
            
            # High-loss condition detection (2 features)
            recent_loss_streak = trade.get('recent_loss_streak', 0)  # Number of recent consecutive losses
            is_high_loss_condition = 1 if recent_loss_streak >= 2 else 0  # 2+ losses in a row = high risk
            
            # Past losing pattern similarity (2 features)
            similar_past_losses = trade.get('similar_past_losses', 0)  # Count of similar losing trades
            loss_pattern_score = min(similar_past_losses / 5, 1.0)  # Normalize (0-1, cap at 5 similar losses)
            
            feature_vector = [
                # Original features (10)
                rsi, macd, macd_signal, bb_upper, bb_lower, bb_middle, 
                volume, price_change, volatility, side,
                # Advanced features (14 = 24 total)
                rsi_oversold, rsi_overbought, rsi_neutral,
                macd_strength, macd_bullish,
                bb_width, bb_position,
                trend_strength, trend_direction,
                high_volatility, low_volatility,
                volume_normalized,
                rsi_macd_alignment, volatility_volume_ratio,
                # Diversity features (6 = 30 total)
                portfolio_diversity_score, portfolio_max_concentration,
                portfolio_unique_symbols, portfolio_total_positions,
                symbol_concentration_before, symbol_concentration_after,
                # Loss pattern learning features (8 = 38 total)
                is_in_drawdown, drawdown_severity,
                is_volatility_spike, volatility_regime,
                is_high_loss_condition, recent_loss_streak,
                similar_past_losses, loss_pattern_score
            ]
            features.append(feature_vector)
        
        return np.array(features)
    
    def extract_labels(self, trade_data):
        """
        Extract labels (profit/loss outcome) from trade data
        1 = profitable trade, 0 = losing trade
        """
        labels = []
        
        for trade in trade_data:
            profit_loss = trade.get('profit_loss', 0) or 0
            # Positive profit = 1 (good trade), otherwise 0
            labels.append(1 if profit_loss > 0 else 0)
        
        return np.array(labels)
    
    def _filter_trades_by_cutoff(self, trades):
        """
        Filter trades to exclude those created before the training cutoff date.
        This prevents corrupted historical trades from poisoning the ML model.
        
        Args:
            trades: QuerySet or list of Trade objects
            
        Returns:
            Filtered list of Trade objects
        """
        if not self.training_cutoff:
            logger.info('No ML training cutoff date set - using all trades')
            return list(trades) if hasattr(trades, '__iter__') else trades
        
        # Import here to avoid circular dependency
        from django.utils import timezone
        from django.db.models import QuerySet
        
        # Handle QuerySet vs list
        if isinstance(trades, QuerySet):
            # Efficient database filtering
            filtered = trades.filter(created_at__gte=self.training_cutoff)
            total_count = trades.count()
            filtered_count = filtered.count()
        else:
            # Python filtering for lists
            total_count = len(trades)
            filtered = []
            for trade in trades:
                if trade.created_at:
                    # Ensure timezone-aware datetime for comparison
                    trade_dt = trade.created_at if timezone.is_aware(trade.created_at) else timezone.make_aware(trade.created_at)
                    if trade_dt >= self.training_cutoff:
                        filtered.append(trade)
            filtered_count = len(filtered)
        
        excluded_count = total_count - filtered_count
        
        if excluded_count > 0:
            logger.info(
                f'ML Training: Excluded {excluded_count} trades created before {self.training_cutoff.date()} '
                f'(using {filtered_count}/{total_count} trades for training)'
            )
        else:
            logger.info(f'ML Training: Using all {filtered_count} trades (none excluded by cutoff date)')
        
        return list(filtered)
    
    def prepare_training_data(self, trades):
        """Prepare features and labels from Trade model instances with loss pattern analysis"""
        trade_data = []
        
        # Calculate drawdown and loss patterns for each trade
        cumulative_pnl = 0
        peak_equity = 0
        recent_losses = []  # Track recent loss streak
        
        for i, trade in enumerate(trades):
            # Only include closed trades with profit/loss calculated
            if trade.status == 'closed' and trade.profit_loss is not None:
                # Handle both dict (new format) and string (legacy format) ai_signal_type
                signal_data = {}
                if trade.ai_signal_type:
                    if isinstance(trade.ai_signal_type, dict):
                        signal_data = trade.ai_signal_type
                    elif isinstance(trade.ai_signal_type, str):
                        # Legacy format - skip or use defaults
                        logger.info(f'Skipping legacy trade {trade.id} with string ai_signal_type')
                        continue
                
                # Extract volume from signal_data if available
                volume = signal_data.get('volume', 0)
                
                # Calculate volatility from Bollinger Bands width if available
                bb_upper = signal_data.get('bb_upper', 0)
                bb_lower = signal_data.get('bb_lower', 0)
                bb_middle = signal_data.get('bb_middle', 1)
                volatility = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
                
                # Calculate loss pattern features
                profit_loss = float(trade.profit_loss or 0)
                cumulative_pnl += profit_loss
                peak_equity = max(peak_equity, cumulative_pnl)
                
                # Calculate drawdown
                drawdown = peak_equity - cumulative_pnl
                max_drawdown_pct = (drawdown / peak_equity * 100) if peak_equity > 0 else 0
                
                # Calculate recent loss streak
                if profit_loss <= 0:
                    recent_losses.append(1)
                else:
                    recent_losses = []  # Reset streak on winning trade
                
                recent_loss_streak = len(recent_losses)
                
                # Calculate similar past losses (trades with similar RSI/volatility that lost money)
                similar_past_losses = 0
                rsi = signal_data.get('rsi', 50)
                for past_idx in range(max(0, i - 20), i):  # Look at last 20 trades
                    past_trade = trades[past_idx]
                    if past_trade.status == 'closed' and past_trade.profit_loss is not None:
                        if past_trade.profit_loss <= 0 and past_trade.ai_signal_type:
                            past_signal = past_trade.ai_signal_type if isinstance(past_trade.ai_signal_type, dict) else {}
                            past_rsi = past_signal.get('rsi', 50)
                            past_vol = past_signal.get('volatility', 0)
                            
                            # Check if conditions are similar (RSI within 20 points, volatility within 50%)
                            if abs(past_rsi - rsi) < 20 and abs(past_vol - volatility) < volatility * 0.5:
                                similar_past_losses += 1
                
                trade_dict = {
                    'rsi': rsi,
                    'macd': signal_data.get('macd', 0),
                    'macd_signal': signal_data.get('macd_signal', 0),
                    'bb_upper': bb_upper,
                    'bb_lower': bb_lower,
                    'bb_middle': bb_middle,
                    'volume': volume,
                    'price_change': ((trade.exit_price or trade.entry_price) - trade.entry_price) / trade.entry_price if trade.entry_price else 0,
                    'volatility': volatility,
                    'side': trade.side,
                    'profit_loss': profit_loss,
                    # Extract diversity metrics from signal_data
                    'portfolio_diversity_score': signal_data.get('portfolio_diversity_score', 0.5),
                    'portfolio_max_concentration': signal_data.get('portfolio_max_concentration', 0),
                    'portfolio_unique_symbols': signal_data.get('portfolio_unique_symbols', 0),
                    'portfolio_total_positions': signal_data.get('portfolio_total_positions', 0),
                    'symbol_concentration_before': signal_data.get('symbol_concentration_before', 0),
                    'symbol_concentration_after': signal_data.get('symbol_concentration_after', 0),
                    # Loss pattern features
                    'max_drawdown_pct': max_drawdown_pct,
                    'recent_loss_streak': recent_loss_streak,
                    'similar_past_losses': similar_past_losses,
                }
                trade_data.append(trade_dict)
        
        if len(trade_data) < self.min_trades_for_training:
            logger.warning(f'Insufficient training data: {len(trade_data)} trades (minimum {self.min_trades_for_training})')
            return None, None
        
        X = self.extract_features(trade_data)
        y = self.extract_labels(trade_data)
        
        return X, y
    
    def train(self, trades):
        """Train the ML model on historical trades"""
        logger.info(f'Starting ML model training with {len(trades)} trades')
        
        # Filter trades by cutoff date to exclude corrupted historical data
        trades = self._filter_trades_by_cutoff(trades)
        
        X, y = self.prepare_training_data(trades)
        
        if X is None or len(X) < self.min_trades_for_training:
            logger.error('Cannot train: insufficient data')
            return {
                'success': False,
                'error': f'Need at least {self.min_trades_for_training} closed trades for training',
                'trades_count': len(trades) if trades else 0
            }
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train enhanced Random Forest model with optimized hyperparameters for 90%+ win rate
        self.model = RandomForestClassifier(
            n_estimators=200,  # Increased from 100 for better ensemble
            max_depth=15,  # Increased from 10 for more complex patterns
            min_samples_split=3,  # More strict splitting for quality
            min_samples_leaf=2,  # Prevent overfitting on single samples
            max_features='sqrt',  # Use sqrt of features for diversity
            bootstrap=True,
            oob_score=True,  # Out-of-bag score for validation
            class_weight='balanced',  # Handle imbalanced profitable/unprofitable trades
            random_state=42,
            n_jobs=-1
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        # Get feature importances (38 features total)
        feature_names = [
            'RSI', 'MACD', 'MACD_Signal', 'BB_Upper', 'BB_Lower', 'BB_Middle', 
            'Volume', 'Price_Change', 'Volatility', 'Side',
            'RSI_Oversold', 'RSI_Overbought', 'RSI_Neutral',
            'MACD_Strength', 'MACD_Bullish',
            'BB_Width', 'BB_Position',
            'Trend_Strength', 'Trend_Direction',
            'High_Volatility', 'Low_Volatility',
            'Volume_Normalized',
            'RSI_MACD_Alignment', 'Volatility_Volume_Ratio',
            'Portfolio_Diversity_Score', 'Portfolio_Max_Concentration',
            'Portfolio_Unique_Symbols', 'Portfolio_Total_Positions',
            'Symbol_Concentration_Before', 'Symbol_Concentration_After',
            'Is_In_Drawdown', 'Drawdown_Severity',
            'Is_Volatility_Spike', 'Volatility_Regime',
            'Is_High_Loss_Condition', 'Recent_Loss_Streak',
            'Similar_Past_Losses', 'Loss_Pattern_Score'
        ]
        importances = dict(zip(feature_names, self.model.feature_importances_.tolist()))
        
        # Save model
        self.save_model()
        
        metrics = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'trades_count': len(trades),
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'train_accuracy': float(train_score),
            'test_accuracy': float(test_score),
            'feature_importances': importances,
            'profitable_ratio': float(np.mean(y)) if y is not None and len(y) > 0 else 0.0
        }
        
        # Save metrics
        import json
        with open(self.metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2)
        
        # Write learning log
        self.write_learning_log(metrics, trades)
        
        logger.info(f'Model trained successfully: Train={train_score:.2%}, Test={test_score:.2%}')
        
        return metrics
    
    def predict(self, features):
        """Make prediction on new trade opportunity"""
        if self.model is None:
            logger.warning('No trained model available for prediction')
            return {
                'prediction': 0,
                'confidence': 0.5,
                'model_available': False
            }
        
        # Scale features
        features_scaled = self.scaler.transform([features])
        
        # Predict
        prediction = self.model.predict(features_scaled)[0]
        probabilities = self.model.predict_proba(features_scaled)[0]
        
        # Handle case where model only learned one class (all profitable or all losses)
        if len(probabilities) == 1:
            # Model only has one class
            confidence = float(probabilities[0])
            if prediction == 0:
                prob_dict = {'loss': float(probabilities[0]), 'profit': 0.0}
            else:
                prob_dict = {'loss': 0.0, 'profit': float(probabilities[0])}
        else:
            # Normal case with 2 classes
            confidence = float(probabilities[prediction])
            prob_dict = {
                'loss': float(probabilities[0]) if len(probabilities) > 0 else 0.0,
                'profit': float(probabilities[1]) if len(probabilities) > 1 else 0.0
            }
        
        return {
            'prediction': int(prediction),  # 1 = likely profitable, 0 = likely not profitable
            'confidence': confidence,
            'probabilities': prob_dict,
            'model_available': True
        }
    
    def save_model(self):
        """Save trained model, scaler, and version to disk"""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            with open(self.scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            # Save model version and feature count for compatibility checking
            with open(self.version_path, 'w', encoding='utf-8') as f:
                f.write(f"{self.model_version}\n{self.expected_features}")
            
            logger.info(f'Model v{self.model_version} saved successfully with {self.expected_features} features')
        except Exception as e:
            logger.error(f'Error saving model: {str(e)}')
    
    def load_model(self):
        """Load trained model and scaler from disk with version compatibility check"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                # Check version compatibility
                if os.path.exists(self.version_path):
                    with open(self.version_path, 'r') as f:
                        lines = f.read().strip().split('\n')
                        saved_version = lines[0] if len(lines) > 0 else '1.0'
                        saved_features = int(lines[1]) if len(lines) > 1 else 10
                    
                    # If feature count doesn't match, invalidate old model
                    if saved_features != self.expected_features:
                        logger.warning(f'Model feature mismatch: saved={saved_features}, expected={self.expected_features}. Invalidating old model.')
                        self._delete_old_model()
                        return False
                    
                    # Load compatible model
                    with open(self.model_path, 'rb') as f:
                        self.model = pickle.load(f)
                    
                    with open(self.scaler_path, 'rb') as f:
                        self.scaler = pickle.load(f)
                    
                    logger.info(f'Model v{saved_version} loaded successfully with {saved_features} features')
                    return True
                else:
                    # Old model without version - assume 10 features (v1.0)
                    logger.warning('Old model detected (no version file). Invalidating for new 24-feature model.')
                    self._delete_old_model()
                    return False
        except Exception as e:
            logger.error(f'Error loading model: {str(e)}')
            self._delete_old_model()
        
        return False
    
    def _delete_old_model(self):
        """Delete incompatible old model files"""
        try:
            if os.path.exists(self.model_path):
                os.remove(self.model_path)
            if os.path.exists(self.scaler_path):
                os.remove(self.scaler_path)
            if os.path.exists(self.version_path):
                os.remove(self.version_path)
            logger.info('Old model files deleted')
        except Exception as e:
            logger.error(f'Error deleting old model: {str(e)}')
    
    def get_metrics(self):
        """Get latest model performance metrics"""
        try:
            if os.path.exists(self.metrics_path):
                import json
                with open(self.metrics_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f'Error loading metrics: {str(e)}')
        
        return {
            'model_available': self.model is not None,
            'error': 'No metrics available'
        }
    
    def should_retrain(self, last_training_time, total_trades_count):
        """Determine if model should be retrained based on time and new data thresholds"""
        # If never trained for this user before (first time), train now
        if last_training_time is None:
            # But only if we have enough trades
            if total_trades_count >= self.min_trades_for_training:
                logger.info('Retraining: First training session for this user')
                return True
            else:
                logger.info(f'Skipping retrain: Only {total_trades_count} trades (need {self.min_trades_for_training})')
                return False
        
        # Check time interval: Retrain if it's been more than retrain_interval_hours
        hours_since_training = (datetime.now() - last_training_time).total_seconds() / 3600
        if hours_since_training > self.retrain_interval_hours:
            logger.info(f'Retraining due to time interval: {hours_since_training:.1f} hours (>{self.retrain_interval_hours}h threshold)')
            return True
        
        # Skip retraining - within 24h window
        return False
    
    def write_learning_log(self, metrics, trades):
        """Write detailed learning log to text file"""
        # Get user email from trades (all trades should be from same user)
        user_email = 'unknown'
        if trades and len(trades) > 0:
            user_email = trades[0].user.email if hasattr(trades[0], 'user') else 'unknown'
        
        # Create user-specific log directory
        log_dir = os.path.join('backend/ai_logs', user_email)
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'training_log_{timestamp}.txt')
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("AI TRADING MODEL - LEARNING LOG\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Training Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("TRAINING SUMMARY\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Trades Analyzed: {metrics['trades_count']}\n")
            f.write(f"Training Samples: {metrics['training_samples']}\n")
            f.write(f"Test Samples: {metrics['test_samples']}\n")
            f.write(f"Profitable Trade Ratio: {metrics['profitable_ratio']:.2%}\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("MODEL PERFORMANCE\n")
            f.write("-" * 80 + "\n")
            f.write(f"Training Accuracy: {metrics['train_accuracy']:.2%}\n")
            f.write(f"Testing Accuracy: {metrics['test_accuracy']:.2%}\n\n")
            
            # Check for improvement
            prev_accuracy = self.get_previous_accuracy()
            if prev_accuracy:
                improvement = metrics['test_accuracy'] - prev_accuracy
                f.write(f"Previous Test Accuracy: {prev_accuracy:.2%}\n")
                f.write(f"Improvement: {improvement:+.2%}\n")
                if improvement > 0:
                    f.write("✓ Model has IMPROVED!\n\n")
                elif improvement < 0:
                    f.write("✗ Model performance DECREASED\n\n")
                else:
                    f.write("= No change in performance\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("WHAT THE AI LEARNED - FEATURE IMPORTANCE\n")
            f.write("-" * 80 + "\n")
            f.write("(Higher values = more important for predicting profitable trades)\n\n")
            
            # Sort features by importance
            sorted_features = sorted(
                metrics['feature_importances'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            for i, (feature, importance) in enumerate(sorted_features, 1):
                bar_length = int(importance * 50)
                bar = "█" * bar_length
                f.write(f"{i}. {feature:15s} [{importance:.4f}] {bar}\n")
            
            f.write("\n" + "-" * 80 + "\n")
            f.write("KEY INSIGHTS\n")
            f.write("-" * 80 + "\n")
            
            # Identify most important feature
            most_important = sorted_features[0]
            f.write(f"• Most Critical Indicator: {most_important[0]} ({most_important[1]:.2%} importance)\n")
            
            # Profitability insight
            if metrics['profitable_ratio'] > 0.6:
                f.write(f"• High Success Rate: {metrics['profitable_ratio']:.0%} of trades were profitable\n")
            elif metrics['profitable_ratio'] < 0.4:
                f.write(f"• Low Success Rate: Only {metrics['profitable_ratio']:.0%} of trades were profitable\n")
            else:
                f.write(f"• Moderate Success Rate: {metrics['profitable_ratio']:.0%} of trades were profitable\n")
            
            # Model confidence
            if metrics['test_accuracy'] > 0.7:
                f.write(f"• Strong Predictive Power: {metrics['test_accuracy']:.0%} accuracy on test data\n")
            elif metrics['test_accuracy'] < 0.55:
                f.write(f"• Weak Predictive Power: {metrics['test_accuracy']:.0%} accuracy (needs more data)\n")
            else:
                f.write(f"• Moderate Predictive Power: {metrics['test_accuracy']:.0%} accuracy\n")
            
            f.write("\n" + "=" * 80 + "\n")
        
        logger.info(f'Learning log written to {log_file}')
        
        # Also write a comparison log for past 5 days
        self.write_trade_comparison_log(trades)
    
    def get_previous_accuracy(self):
        """Get the previous model's test accuracy for comparison"""
        try:
            if os.path.exists(self.metrics_path):
                import json
                with open(self.metrics_path, 'r') as f:
                    prev_metrics = json.load(f)
                    return prev_metrics.get('test_accuracy')
        except:
            pass
        return None
    
    def write_trade_comparison_log(self, all_trades):
        """Write trade comparison for past 5 days"""
        # Get user email from trades (all trades should be from same user)
        user_email = 'unknown'
        if all_trades and len(all_trades) > 0:
            user_email = all_trades[0].user.email if hasattr(all_trades[0], 'user') else 'unknown'
        
        # Create user-specific log directory
        log_dir = os.path.join('backend/ai_logs', user_email)
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'trade_comparison_{timestamp}.txt')
        
        # Group trades by day (past 5 days)
        cutoff_date = datetime.now() - timedelta(days=5)
        recent_trades = [t for t in all_trades if t.created_at.replace(tzinfo=None) >= cutoff_date]
        
        # Group by date
        trades_by_day = {}
        for trade in recent_trades:
            date_key = trade.created_at.strftime('%Y-%m-%d')
            if date_key not in trades_by_day:
                trades_by_day[date_key] = []
            trades_by_day[date_key].append(trade)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TRADE COMPARISON - PAST 5 DAYS\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if not recent_trades:
                f.write("No trades found in the past 5 days.\n")
                return
            
            # Daily summary
            for day in sorted(trades_by_day.keys(), reverse=True):
                day_trades = trades_by_day[day]
                closed_trades = [t for t in day_trades if t.status == 'closed']
                
                f.write("-" * 80 + "\n")
                f.write(f"DATE: {day}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Total Trades: {len(day_trades)}\n")
                f.write(f"Closed Trades: {len(closed_trades)}\n")
                
                if closed_trades:
                    total_profit = sum(t.profit_loss or 0 for t in closed_trades)
                    profitable = [t for t in closed_trades if (t.profit_loss or 0) > 0]
                    win_rate = len(profitable) / len(closed_trades) * 100
                    
                    f.write(f"Win Rate: {win_rate:.1f}%\n")
                    f.write(f"Total P&L: ${total_profit:.2f}\n")
                    f.write(f"Avg Profit per Trade: ${total_profit/len(closed_trades):.2f}\n\n")
                    
                    f.write("Trade Details:\n")
                    for i, trade in enumerate(closed_trades, 1):
                        profit_sign = "+" if (trade.profit_loss or 0) >= 0 else ""
                        f.write(f"  {i}. {trade.symbol:8s} {trade.side:4s} "
                               f"Entry: ${trade.entry_price:.2f} -> "
                               f"Exit: ${trade.exit_price or 0:.2f} | "
                               f"P&L: {profit_sign}${trade.profit_loss or 0:.2f}\n")
                else:
                    f.write("No closed trades for this day.\n")
                
                f.write("\n")
            
            # Overall summary
            f.write("=" * 80 + "\n")
            f.write("5-DAY SUMMARY\n")
            f.write("=" * 80 + "\n")
            
            all_closed = [t for t in recent_trades if t.status == 'closed']
            if all_closed:
                total_profit = sum(t.profit_loss or 0 for t in all_closed)
                profitable = [t for t in all_closed if (t.profit_loss or 0) > 0]
                overall_win_rate = len(profitable) / len(all_closed) * 100
                
                f.write(f"Total Trades: {len(all_closed)}\n")
                f.write(f"Profitable Trades: {len(profitable)}\n")
                f.write(f"Losing Trades: {len(all_closed) - len(profitable)}\n")
                f.write(f"Overall Win Rate: {overall_win_rate:.1f}%\n")
                f.write(f"Total Profit/Loss: ${total_profit:.2f}\n")
                f.write(f"Average per Trade: ${total_profit/len(all_closed):.2f}\n\n")
                
                # Performance trend
                if len(trades_by_day) >= 2:
                    days_sorted = sorted(trades_by_day.keys())
                    first_day_profit = sum(t.profit_loss or 0 for t in trades_by_day[days_sorted[0]] if t.status == 'closed')
                    last_day_profit = sum(t.profit_loss or 0 for t in trades_by_day[days_sorted[-1]] if t.status == 'closed')
                    
                    f.write("PERFORMANCE TREND:\n")
                    if last_day_profit > first_day_profit:
                        f.write("✓ IMPROVING - Recent performance is better than earlier days\n")
                    elif last_day_profit < first_day_profit:
                        f.write("✗ DECLINING - Recent performance is worse than earlier days\n")
                    else:
                        f.write("= STABLE - Performance is consistent\n")
            else:
                f.write("No closed trades in the past 5 days.\n")
            
            f.write("\n" + "=" * 80 + "\n")
        
        logger.info(f'Trade comparison log written to {log_file}')
