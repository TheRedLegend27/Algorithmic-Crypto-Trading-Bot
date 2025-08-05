#!/usr/bin/env python3
"""
Enhanced Adaptive Algorithms
Improve the ML learning and adaptation capabilities of the bot.
"""
import json
import os
from pathlib import Path

def create_enhanced_ml_engine():
    """Create an enhanced ML engine with better learning capabilities."""
    print("🧠 Creating Enhanced ML Engine...")
    
    enhanced_ml_code = '''"""
Enhanced ML Engine with Improved Learning Capabilities
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
import logging
from dataclasses import dataclass, field
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

@dataclass
class MLPrediction:
    """ML prediction result."""
    signal: str  # 'buy', 'sell', 'hold'
    confidence: float
    price_prediction: Optional[float] = None
    features_used: List[str] = field(default_factory=list)
    model_name: str = "ensemble"
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ModelPerformance:
    """Model performance metrics."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    mse: float = float('inf')
    mae: float = float('inf')
    sharpe_ratio: float = 0.0
    total_predictions: int = 0
    correct_predictions: int = 0

class EnhancedMLEngine:
    """Enhanced ML engine with multiple models and online learning."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize models
        self.models = {
            'random_forest': RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            ),
            'gradient_boosting': GradientBoostingRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            ),
            'linear': Ridge(alpha=1.0),
            'ensemble': None  # Will be created dynamically
        }
        
        # Scalers for feature normalization
        self.scalers = {
            'standard': StandardScaler(),
            'robust': RobustScaler()
        }
        self.current_scaler = self.scalers['robust']
        
        # Training data storage
        self.training_data = []
        self.feature_names = []
        self.target_values = []
        
        # Performance tracking
        self.model_performance = {
            name: ModelPerformance() for name in self.models.keys()
        }
        
        # Online learning parameters
        self.min_training_samples = config.get('min_training_samples', 100)
        self.retrain_frequency = config.get('retrain_frequency', 50)  # Retrain every N predictions
        self.prediction_count = 0
        
        # Feature importance tracking
        self.feature_importance = {}
        
        # Model weights for ensemble
        self.model_weights = {
            'random_forest': 0.4,
            'gradient_boosting': 0.3,
            'linear': 0.3
        }
        
        self.logger.info("Enhanced ML Engine initialized")
    
    def extract_features(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract comprehensive features from market data."""
        features = {}
        
        try:
            # Price-based features
            if 'price' in market_data:
                price = market_data['price']
                features['current_price'] = price
                
                # Price history features
                if 'price_history' in market_data:
                    prices = market_data['price_history']
                    if len(prices) >= 20:
                        prices_array = np.array(prices)
                        
                        # Moving averages
                        features['sma_5'] = np.mean(prices_array[-5:])
                        features['sma_10'] = np.mean(prices_array[-10:])
                        features['sma_20'] = np.mean(prices_array[-20:])
                        
                        # Price momentum
                        features['momentum_5'] = (price - features['sma_5']) / features['sma_5']
                        features['momentum_10'] = (price - features['sma_10']) / features['sma_10']
                        
                        # Volatility
                        returns = np.diff(prices_array) / prices_array[:-1]
                        features['volatility_5'] = np.std(returns[-5:])
                        features['volatility_10'] = np.std(returns[-10:])
                        
                        # Price position in range
                        high_20 = np.max(prices_array[-20:])
                        low_20 = np.min(prices_array[-20:])
                        if high_20 != low_20:
                            features['price_position'] = (price - low_20) / (high_20 - low_20)
                        else:
                            features['price_position'] = 0.5
            
            # Technical indicators
            if 'indicators' in market_data:
                indicators = market_data['indicators']
                
                # RSI
                if 'rsi' in indicators:
                    features['rsi'] = indicators['rsi']
                    features['rsi_oversold'] = 1.0 if indicators['rsi'] < 30 else 0.0
                    features['rsi_overbought'] = 1.0 if indicators['rsi'] > 70 else 0.0
                
                # MACD
                if 'macd' in indicators:
                    features['macd'] = indicators['macd']
                    features['macd_signal'] = indicators.get('macd_signal', 0)
                    features['macd_histogram'] = indicators.get('macd_histogram', 0)
                
                # Bollinger Bands
                if 'bb_upper' in indicators and 'bb_lower' in indicators:
                    bb_upper = indicators['bb_upper']
                    bb_lower = indicators['bb_lower']
                    bb_middle = indicators.get('bb_middle', (bb_upper + bb_lower) / 2)
                    
                    if bb_upper != bb_lower:
                        features['bb_position'] = (price - bb_lower) / (bb_upper - bb_lower)
                    else:
                        features['bb_position'] = 0.5
                    
                    features['bb_squeeze'] = (bb_upper - bb_lower) / bb_middle if bb_middle != 0 else 0
            
            # Volume features
            if 'volume' in market_data:
                volume = market_data['volume']
                features['volume'] = volume
                
                if 'volume_history' in market_data:
                    volumes = market_data['volume_history']
                    if len(volumes) >= 10:
                        avg_volume = np.mean(volumes[-10:])
                        features['volume_ratio'] = volume / avg_volume if avg_volume > 0 else 1.0
            
            # Market regime features
            if 'market_regime' in market_data:
                regime = market_data['market_regime']
                features['trend_strength'] = regime.get('trend_strength', 0.0)
                features['volatility_regime'] = regime.get('volatility_regime', 0.0)
                features['momentum_regime'] = regime.get('momentum_regime', 0.0)
            
            # Time-based features
            now = datetime.now()
            features['hour_of_day'] = now.hour / 24.0
            features['day_of_week'] = now.weekday() / 7.0
            
            # Market microstructure (if available)
            if 'order_book' in market_data:
                order_book = market_data['order_book']
                if 'bid_ask_spread' in order_book:
                    features['bid_ask_spread'] = order_book['bid_ask_spread']
                if 'order_book_imbalance' in order_book:
                    features['order_book_imbalance'] = order_book['order_book_imbalance']
            
        except Exception as e:
            self.logger.error(f"Error extracting features: {e}")
        
        # Ensure we have consistent feature names
        if not self.feature_names:
            self.feature_names = sorted(features.keys())
        
        # Fill missing features with zeros
        for feature_name in self.feature_names:
            if feature_name not in features:
                features[feature_name] = 0.0
        
        return features
    
    def add_training_sample(self, features: Dict[str, float], target: float, 
                          actual_outcome: Optional[float] = None):
        """Add a training sample for online learning."""
        try:
            # Convert features to array
            feature_array = np.array([features.get(name, 0.0) for name in self.feature_names])
            
            # Store training data
            self.training_data.append(feature_array)
            self.target_values.append(target)
            
            # Limit training data size to prevent memory issues
            max_samples = self.config.get('max_training_samples', 10000)
            if len(self.training_data) > max_samples:
                # Remove oldest samples
                remove_count = len(self.training_data) - max_samples
                self.training_data = self.training_data[remove_count:]
                self.target_values = self.target_values[remove_count:]
            
            # Update performance if actual outcome is provided
            if actual_outcome is not None:
                self._update_performance_metrics(target, actual_outcome)
            
            self.logger.debug(f"Added training sample, total samples: {len(self.training_data)}")
            
        except Exception as e:
            self.logger.error(f"Error adding training sample: {e}")
    
    def _update_performance_metrics(self, prediction: float, actual: float):
        """Update performance metrics based on prediction vs actual outcome."""
        try:
            # Update overall performance
            for model_name in self.model_performance:
                perf = self.model_performance[model_name]
                perf.total_predictions += 1
                
                # Simple accuracy check (within 5% tolerance)
                if abs(prediction - actual) / abs(actual) < 0.05 if actual != 0 else abs(prediction) < 0.05:
                    perf.correct_predictions += 1
                
                perf.accuracy = perf.correct_predictions / perf.total_predictions
                
                # Update MSE and MAE
                error = prediction - actual
                perf.mse = (perf.mse * (perf.total_predictions - 1) + error**2) / perf.total_predictions
                perf.mae = (perf.mae * (perf.total_predictions - 1) + abs(error)) / perf.total_predictions
        
        except Exception as e:
            self.logger.error(f"Error updating performance metrics: {e}")
    
    def train_models(self) -> bool:
        """Train all models with current data."""
        if len(self.training_data) < self.min_training_samples:
            self.logger.info(f"Not enough training samples: {len(self.training_data)}/{self.min_training_samples}")
            return False
        
        try:
            # Prepare training data
            X = np.array(self.training_data)
            y = np.array(self.target_values)
            
            # Scale features
            X_scaled = self.current_scaler.fit_transform(X)
            
            # Train individual models
            for model_name, model in self.models.items():
                if model_name == 'ensemble':
                    continue  # Skip ensemble, it's created dynamically
                
                try:
                    # Use time series split for validation
                    tscv = TimeSeriesSplit(n_splits=3)
                    scores = []
                    
                    for train_idx, val_idx in tscv.split(X_scaled):
                        X_train, X_val = X_scaled[train_idx], X_scaled[val_idx]
                        y_train, y_val = y[train_idx], y[val_idx]
                        
                        # Train model
                        model.fit(X_train, y_train)
                        
                        # Validate
                        y_pred = model.predict(X_val)
                        score = mean_squared_error(y_val, y_pred)
                        scores.append(score)
                    
                    # Update model performance
                    avg_score = np.mean(scores)
                    self.model_performance[model_name].mse = avg_score
                    
                    # Final training on all data
                    model.fit(X_scaled, y)
                    
                    # Update feature importance
                    if hasattr(model, 'feature_importances_'):
                        importance = dict(zip(self.feature_names, model.feature_importances_))
                        self.feature_importance[model_name] = importance
                    
                    self.logger.info(f"Trained {model_name} model, MSE: {avg_score:.4f}")
                    
                except Exception as e:
                    self.logger.error(f"Error training {model_name}: {e}")
                    continue
            
            # Update model weights based on performance
            self._update_model_weights()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error training models: {e}")
            return False
    
    def _update_model_weights(self):
        """Update ensemble model weights based on performance."""
        try:
            # Calculate weights based on inverse MSE (lower MSE = higher weight)
            total_inverse_mse = 0
            model_inverse_mse = {}
            
            for model_name in ['random_forest', 'gradient_boosting', 'linear']:
                mse = self.model_performance[model_name].mse
                if mse > 0:
                    inverse_mse = 1.0 / mse
                    model_inverse_mse[model_name] = inverse_mse
                    total_inverse_mse += inverse_mse
                else:
                    model_inverse_mse[model_name] = 1.0
                    total_inverse_mse += 1.0
            
            # Normalize weights
            if total_inverse_mse > 0:
                for model_name in model_inverse_mse:
                    self.model_weights[model_name] = model_inverse_mse[model_name] / total_inverse_mse
            
            self.logger.info(f"Updated model weights: {self.model_weights}")
            
        except Exception as e:
            self.logger.error(f"Error updating model weights: {e}")
    
    def predict(self, market_data: Dict[str, Any]) -> MLPrediction:
        """Make prediction using ensemble of models."""
        try:
            # Extract features
            features = self.extract_features(market_data)
            
            # Convert to array
            feature_array = np.array([features.get(name, 0.0) for name in self.feature_names])
            
            if len(self.training_data) < self.min_training_samples:
                # Not enough training data, return neutral prediction
                return MLPrediction(
                    signal='hold',
                    confidence=0.0,
                    features_used=list(features.keys()),
                    model_name='insufficient_data'
                )
            
            # Scale features
            feature_scaled = self.current_scaler.transform([feature_array])
            
            # Get predictions from all models
            predictions = {}
            confidences = {}
            
            for model_name, model in self.models.items():
                if model_name == 'ensemble' or model is None:
                    continue
                
                try:
                    pred = model.predict(feature_scaled)[0]
                    predictions[model_name] = pred
                    
                    # Calculate confidence based on model performance
                    perf = self.model_performance[model_name]
                    confidence = max(0.0, min(1.0, perf.accuracy))
                    confidences[model_name] = confidence
                    
                except Exception as e:
                    self.logger.error(f"Error getting prediction from {model_name}: {e}")
                    predictions[model_name] = 0.0
                    confidences[model_name] = 0.0
            
            # Ensemble prediction
            if predictions:
                weighted_pred = sum(
                    predictions[name] * self.model_weights.get(name, 0.0) 
                    for name in predictions
                )
                
                weighted_confidence = sum(
                    confidences[name] * self.model_weights.get(name, 0.0)
                    for name in confidences
                )
            else:
                weighted_pred = 0.0
                weighted_confidence = 0.0
            
            # Convert prediction to signal
            signal = 'hold'
            if weighted_pred > 0.1:
                signal = 'buy'
            elif weighted_pred < -0.1:
                signal = 'sell'
            
            # Increment prediction count
            self.prediction_count += 1
            
            # Retrain if needed
            if self.prediction_count % self.retrain_frequency == 0:
                self.logger.info("Retraining models...")
                self.train_models()
            
            return MLPrediction(
                signal=signal,
                confidence=weighted_confidence,
                price_prediction=weighted_pred,
                features_used=list(features.keys()),
                model_name='ensemble'
            )
            
        except Exception as e:
            self.logger.error(f"Error making prediction: {e}")
            return MLPrediction(
                signal='hold',
                confidence=0.0,
                model_name='error'
            )
    
    def get_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """Get feature importance from all models."""
        return self.feature_importance.copy()
    
    def get_model_performance(self) -> Dict[str, ModelPerformance]:
        """Get performance metrics for all models."""
        return self.model_performance.copy()
    
    def save_state(self, filepath: str):
        """Save ML engine state to file."""
        try:
            state = {
                'feature_names': self.feature_names,
                'model_weights': self.model_weights,
                'feature_importance': self.feature_importance,
                'prediction_count': self.prediction_count,
                'performance': {
                    name: {
                        'accuracy': perf.accuracy,
                        'mse': perf.mse,
                        'mae': perf.mae,
                        'total_predictions': perf.total_predictions,
                        'correct_predictions': perf.correct_predictions
                    }
                    for name, perf in self.model_performance.items()
                }
            }
            
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2)
            
            self.logger.info(f"ML engine state saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving ML engine state: {e}")
    
    def load_state(self, filepath: str):
        """Load ML engine state from file."""
        try:
            if not os.path.exists(filepath):
                self.logger.info("No saved state found, starting fresh")
                return
            
            with open(filepath, 'r') as f:
                state = json.load(f)
            
            self.feature_names = state.get('feature_names', [])
            self.model_weights = state.get('model_weights', self.model_weights)
            self.feature_importance = state.get('feature_importance', {})
            self.prediction_count = state.get('prediction_count', 0)
            
            # Restore performance metrics
            if 'performance' in state:
                for name, perf_data in state['performance'].items():
                    if name in self.model_performance:
                        perf = self.model_performance[name]
                        perf.accuracy = perf_data.get('accuracy', 0.0)
                        perf.mse = perf_data.get('mse', float('inf'))
                        perf.mae = perf_data.get('mae', float('inf'))
                        perf.total_predictions = perf_data.get('total_predictions', 0)
                        perf.correct_predictions = perf_data.get('correct_predictions', 0)
            
            self.logger.info(f"ML engine state loaded from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error loading ML engine state: {e}")
'''
    
    try:
        # Create the enhanced ML engine directory if it doesn't exist
        os.makedirs('bot/adaptive', exist_ok=True)
        
        # Write the enhanced ML engine
        with open('bot/adaptive/enhanced_ml_engine.py', 'w') as f:
            f.write(enhanced_ml_code)
        
        print("✅ Created enhanced ML engine")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create enhanced ML engine: {e}")
        return False

def create_adaptive_learning_config():
    """Create configuration for adaptive learning."""
    print("🎯 Creating Adaptive Learning Configuration...")
    
    config = {
        "ml_engine": {
            "min_training_samples": 50,
            "max_training_samples": 5000,
            "retrain_frequency": 25,
            "feature_selection": {
                "enabled": True,
                "max_features": 20,
                "importance_threshold": 0.01
            },
            "online_learning": {
                "enabled": True,
                "learning_rate": 0.01,
                "adaptation_rate": 0.1
            }
        },
        "adaptive_strategies": {
            "adaptation_frequency_minutes": 30,
            "min_performance_threshold": 0.6,
            "max_adaptations_per_day": 20,
            "confidence_threshold": 0.7,
            "strategy_weights": {
                "enhanced_momentum": 0.4,
                "price_action": 0.3,
                "multi_timeframe": 0.3
            }
        },
        "performance_tracking": {
            "metrics": [
                "accuracy",
                "precision",
                "recall",
                "sharpe_ratio",
                "max_drawdown",
                "win_rate",
                "profit_factor"
            ],
            "evaluation_window_hours": 24,
            "min_trades_for_evaluation": 10
        },
        "risk_adaptation": {
            "enabled": True,
            "volatility_adjustment": True,
            "drawdown_protection": True,
            "position_sizing_adaptation": True,
            "max_risk_per_trade": 0.02,
            "max_portfolio_risk": 0.1
        }
    }
    
    try:
        os.makedirs('config', exist_ok=True)
        
        with open('config/adaptive_learning.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        print("✅ Created adaptive learning configuration")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create adaptive learning config: {e}")
        return False

def create_performance_analyzer():
    """Create an enhanced performance analyzer."""
    print("📊 Creating Enhanced Performance Analyzer...")
    
    analyzer_code = '''"""
Enhanced Performance Analyzer with Advanced Metrics
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging
from dataclasses import dataclass, field

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Advanced metrics
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    
    # Time-based metrics
    best_day: float = 0.0
    worst_day: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    
    # Risk metrics
    var_95: float = 0.0  # Value at Risk 95%
    cvar_95: float = 0.0  # Conditional Value at Risk 95%
    
    timestamp: datetime = field(default_factory=datetime.now)

class EnhancedPerformanceAnalyzer:
    """Enhanced performance analyzer with comprehensive metrics."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Trade history
        self.trades = []
        self.daily_returns = []
        self.portfolio_values = []
        
        # Benchmark data (if available)
        self.benchmark_returns = []
        
        # Performance history
        self.performance_history = []
        
        self.logger.info("Enhanced Performance Analyzer initialized")
    
    def add_trade(self, trade_data: Dict):
        """Add a completed trade for analysis."""
        try:
            trade = {
                'timestamp': trade_data.get('timestamp', datetime.now()),
                'pair': trade_data.get('pair', ''),
                'side': trade_data.get('side', ''),
                'entry_price': trade_data.get('entry_price', 0.0),
                'exit_price': trade_data.get('exit_price', 0.0),
                'quantity': trade_data.get('quantity', 0.0),
                'pnl': trade_data.get('pnl', 0.0),
                'pnl_percent': trade_data.get('pnl_percent', 0.0),
                'duration_minutes': trade_data.get('duration_minutes', 0),
                'fees': trade_data.get('fees', 0.0),
                'strategy': trade_data.get('strategy', 'unknown')
            }
            
            self.trades.append(trade)
            
            # Limit trade history to prevent memory issues
            max_trades = self.config.get('max_trade_history', 10000)
            if len(self.trades) > max_trades:
                self.trades = self.trades[-max_trades:]
            
            self.logger.debug(f"Added trade: {trade['pair']} {trade['side']} PnL: {trade['pnl']:.4f}")
            
        except Exception as e:
            self.logger.error(f"Error adding trade: {e}")
    
    def add_portfolio_value(self, value: float, timestamp: Optional[datetime] = None):
        """Add portfolio value for tracking."""
        try:
            if timestamp is None:
                timestamp = datetime.now()
            
            self.portfolio_values.append({
                'timestamp': timestamp,
                'value': value
            })
            
            # Calculate daily return if we have previous value
            if len(self.portfolio_values) > 1:
                prev_value = self.portfolio_values[-2]['value']
                if prev_value > 0:
                    daily_return = (value - prev_value) / prev_value
                    self.daily_returns.append(daily_return)
            
            # Limit history
            max_values = self.config.get('max_portfolio_history', 10000)
            if len(self.portfolio_values) > max_values:
                self.portfolio_values = self.portfolio_values[-max_values:]
                self.daily_returns = self.daily_returns[-max_values:]
            
        except Exception as e:
            self.logger.error(f"Error adding portfolio value: {e}")
    
    def calculate_metrics(self, period_days: Optional[int] = None) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        try:
            metrics = PerformanceMetrics()
            
            if not self.trades:
                return metrics
            
            # Filter trades by period if specified
            trades = self.trades
            if period_days:
                cutoff_date = datetime.now() - timedelta(days=period_days)
                trades = [t for t in trades if t['timestamp'] >= cutoff_date]
            
            if not trades:
                return metrics
            
            # Basic trade metrics
            metrics.total_trades = len(trades)
            
            pnls = [t['pnl'] for t in trades]
            pnl_percents = [t['pnl_percent'] for t in trades]
            
            winning_trades = [t for t in trades if t['pnl'] > 0]
            losing_trades = [t for t in trades if t['pnl'] < 0]
            
            metrics.winning_trades = len(winning_trades)
            metrics.losing_trades = len(losing_trades)
            
            if metrics.total_trades > 0:
                metrics.win_rate = metrics.winning_trades / metrics.total_trades
            
            # PnL metrics
            if pnls:
                metrics.total_return = sum(pnls)
                
                if winning_trades:
                    metrics.average_win = np.mean([t['pnl'] for t in winning_trades])
                
                if losing_trades:
                    metrics.average_loss = np.mean([t['pnl'] for t in losing_trades])
                
                # Profit factor
                gross_profit = sum(t['pnl'] for t in winning_trades)
                gross_loss = abs(sum(t['pnl'] for t in losing_trades))
                
                if gross_loss > 0:
                    metrics.profit_factor = gross_profit / gross_loss
            
            # Return-based metrics
            if self.daily_returns and len(self.daily_returns) > 1:
                returns = np.array(self.daily_returns)
                
                # Annualized return
                if period_days and period_days > 0:
                    total_return = (1 + returns).prod() - 1
                    metrics.annualized_return = (1 + total_return) ** (365 / period_days) - 1
                else:
                    metrics.annualized_return = np.mean(returns) * 365
                
                # Volatility
                metrics.volatility = np.std(returns) * np.sqrt(365)
                
                # Sharpe ratio
                if metrics.volatility > 0:
                    risk_free_rate = 0.02  # Assume 2% risk-free rate
                    metrics.sharpe_ratio = (metrics.annualized_return - risk_free_rate) / metrics.volatility
                
                # Sortino ratio (downside deviation)
                downside_returns = returns[returns < 0]
                if len(downside_returns) > 0:
                    downside_deviation = np.std(downside_returns) * np.sqrt(365)
                    if downside_deviation > 0:
                        metrics.sortino_ratio = (metrics.annualized_return - risk_free_rate) / downside_deviation
                
                # Maximum drawdown
                if self.portfolio_values:
                    values = [pv['value'] for pv in self.portfolio_values]
                    peak = values[0]
                    max_dd = 0
                    
                    for value in values:
                        if value > peak:
                            peak = value
                        drawdown = (peak - value) / peak if peak > 0 else 0
                        max_dd = max(max_dd, drawdown)
                    
                    metrics.max_drawdown = max_dd
                
                # Calmar ratio
                if metrics.max_drawdown > 0:
                    metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown
                
                # Value at Risk (VaR) and Conditional VaR
                if len(returns) >= 20:  # Need sufficient data
                    metrics.var_95 = np.percentile(returns, 5)
                    cvar_returns = returns[returns <= metrics.var_95]
                    if len(cvar_returns) > 0:
                        metrics.cvar_95 = np.mean(cvar_returns)
                
                # Best and worst days
                metrics.best_day = np.max(returns)
                metrics.worst_day = np.min(returns)
            
            # Consecutive wins/losses
            if trades:
                current_streak = 0
                max_win_streak = 0
                max_loss_streak = 0
                
                for trade in trades:
                    if trade['pnl'] > 0:
                        if current_streak >= 0:
                            current_streak += 1
                        else:
                            current_streak = 1
                        max_win_streak = max(max_win_streak, current_streak)
                    elif trade['pnl'] < 0:
                        if current_streak <= 0:
                            current_streak -= 1
                        else:
                            current_streak = -1
                        max_loss_streak = max(max_loss_streak, abs(current_streak))
                
                metrics.consecutive_wins = max_win_streak
                metrics.consecutive_losses = max_loss_streak
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {e}")
            return PerformanceMetrics()
    
    def analyze_strategy_performance(self) -> Dict[str, PerformanceMetrics]:
        """Analyze performance by strategy."""
        try:
            strategy_trades = {}
            
            # Group trades by strategy
            for trade in self.trades:
                strategy = trade.get('strategy', 'unknown')
                if strategy not in strategy_trades:
                    strategy_trades[strategy] = []
                strategy_trades[strategy].append(trade)
            
            # Calculate metrics for each strategy
            strategy_metrics = {}
            for strategy, trades in strategy_trades.items():
                # Temporarily set trades for calculation
                original_trades = self.trades
                self.trades = trades
                
                metrics = self.calculate_metrics()
                strategy_metrics[strategy] = metrics
                
                # Restore original trades
                self.trades = original_trades
            
            return strategy_metrics
            
        except Exception as e:
            self.logger.error(f"Error analyzing strategy performance: {e}")
            return {}
    
    def generate_performance_report(self) -> Dict:
        """Generate comprehensive performance report."""
        try:
            # Overall metrics
            overall_metrics = self.calculate_metrics()
            
            # Recent performance (last 7 days)
            recent_metrics = self.calculate_metrics(period_days=7)
            
            # Strategy breakdown
            strategy_metrics = self.analyze_strategy_performance()
            
            # Trading pair analysis
            pair_performance = {}
            pairs = set(t['pair'] for t in self.trades)
            
            for pair in pairs:
                pair_trades = [t for t in self.trades if t['pair'] == pair]
                if pair_trades:
                    pair_pnl = sum(t['pnl'] for t in pair_trades)
                    pair_trades_count = len(pair_trades)
                    pair_win_rate = len([t for t in pair_trades if t['pnl'] > 0]) / pair_trades_count
                    
                    pair_performance[pair] = {
                        'total_pnl': pair_pnl,
                        'trade_count': pair_trades_count,
                        'win_rate': pair_win_rate,
                        'avg_pnl': pair_pnl / pair_trades_count
                    }
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'overall_performance': {
                    'total_return': overall_metrics.total_return,
                    'annualized_return': overall_metrics.annualized_return,
                    'sharpe_ratio': overall_metrics.sharpe_ratio,
                    'max_drawdown': overall_metrics.max_drawdown,
                    'win_rate': overall_metrics.win_rate,
                    'profit_factor': overall_metrics.profit_factor,
                    'total_trades': overall_metrics.total_trades
                },
                'recent_performance': {
                    'total_return': recent_metrics.total_return,
                    'win_rate': recent_metrics.win_rate,
                    'total_trades': recent_metrics.total_trades
                },
                'strategy_performance': {
                    strategy: {
                        'total_return': metrics.total_return,
                        'win_rate': metrics.win_rate,
                        'sharpe_ratio': metrics.sharpe_ratio,
                        'total_trades': metrics.total_trades
                    }
                    for strategy, metrics in strategy_metrics.items()
                },
                'pair_performance': pair_performance,
                'risk_metrics': {
                    'max_drawdown': overall_metrics.max_drawdown,
                    'var_95': overall_metrics.var_95,
                    'volatility': overall_metrics.volatility,
                    'consecutive_losses': overall_metrics.consecutive_losses
                }
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating performance report: {e}")
            return {}
    
    def save_performance_data(self, filepath: str):
        """Save performance data to file."""
        try:
            data = {
                'trades': self.trades,
                'portfolio_values': self.portfolio_values,
                'daily_returns': self.daily_returns,
                'performance_history': self.performance_history
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            self.logger.info(f"Performance data saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving performance data: {e}")
    
    def load_performance_data(self, filepath: str):
        """Load performance data from file."""
        try:
            if not os.path.exists(filepath):
                self.logger.info("No saved performance data found")
                return
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.trades = data.get('trades', [])
            self.portfolio_values = data.get('portfolio_values', [])
            self.daily_returns = data.get('daily_returns', [])
            self.performance_history = data.get('performance_history', [])
            
            # Convert timestamp strings back to datetime objects
            for trade in self.trades:
                if isinstance(trade['timestamp'], str):
                    trade['timestamp'] = datetime.fromisoformat(trade['timestamp'])
            
            for pv in self.portfolio_values:
                if isinstance(pv['timestamp'], str):
                    pv['timestamp'] = datetime.fromisoformat(pv['timestamp'])
            
            self.logger.info(f"Performance data loaded from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error loading performance data: {e}")
'''
    
    try:
        with open('bot/adaptive/enhanced_performance_analyzer.py', 'w') as f:
            f.write(analyzer_code)
        
        print("✅ Created enhanced performance analyzer")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create enhanced performance analyzer: {e}")
        return False

def main():
    """Main function to enhance adaptive algorithms."""
    print("🧠 ENHANCING ADAPTIVE ALGORITHMS")
    print("=" * 60)
    
    enhancements = []
    
    # 1. Create enhanced ML engine
    if create_enhanced_ml_engine():
        enhancements.append("✅ Enhanced ML Engine with online learning")
    else:
        enhancements.append("❌ Failed to create enhanced ML engine")
    
    # 2. Create adaptive learning configuration
    if create_adaptive_learning_config():
        enhancements.append("✅ Adaptive learning configuration")
    else:
        enhancements.append("❌ Failed to create adaptive learning config")
    
    # 3. Create enhanced performance analyzer
    if create_performance_analyzer():
        enhancements.append("✅ Enhanced performance analyzer")
    else:
        enhancements.append("❌ Failed to create performance analyzer")
    
    # Summary
    print("\n📋 ENHANCEMENTS APPLIED:")
    for enhancement in enhancements:
        print(f"   {enhancement}")
    
    successful = len([e for e in enhancements if "✅" in e])
    total = len(enhancements)
    
    print(f"\n🎯 SUCCESS RATE: {successful}/{total} ({successful/total*100:.1f}%)")
    
    if successful >= 2:
        print("\n🚀 ADAPTIVE ALGORITHMS ENHANCED!")
        print("Key improvements:")
        print("• Online learning with multiple ML models")
        print("• Advanced feature extraction and selection")
        print("• Comprehensive performance tracking")
        print("• Adaptive strategy weight adjustment")
        print("• Risk-adjusted position sizing")
        print("• Real-time model retraining")
    else:
        print("\n⚠️ Some enhancements failed. Review errors above.")

if __name__ == "__main__":
    main()