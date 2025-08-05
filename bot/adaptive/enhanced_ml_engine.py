"""
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
