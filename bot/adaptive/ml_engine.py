"""
Machine Learning Engine for the adaptive trading bot system.

This module implements the ML infrastructure including:
- Feature engineering pipeline
- Model training and validation
- Online learning capabilities
- Ensemble prediction system
- Model persistence and versioning
"""
import os
import pickle
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib

from .interfaces import MLEngineInterface
from .data_models import AdaptiveSignal, MLModelMetadata, PerformanceMetrics
from .enums import ModelType, RegimeType
from .ensemble_predictor import EnsemblePredictor, EnsemblePrediction


class FeatureEngineer:
    """Feature engineering pipeline for market data and trading signals."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scalers = {}
        
    def create_technical_features(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Create technical indicator features from market data."""
        df = market_data.copy()
        
        # Price-based features
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['price_change'] = df['close'] - df['open']
        df['price_range'] = df['high'] - df['low']
        df['body_size'] = abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        
        # Moving averages
        for period in [5, 10, 20, 50]:
            df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
            df[f'ema_{period}'] = df['close'].ewm(span=period).mean()
            df[f'price_to_sma_{period}'] = df['close'] / df[f'sma_{period}']
            df[f'sma_{period}_slope'] = df[f'sma_{period}'].diff(5)
        
        # Volatility features
        df['volatility_5'] = df['returns'].rolling(window=5).std()
        df['volatility_20'] = df['returns'].rolling(window=20).std()
        df['atr_14'] = self._calculate_atr(df, 14)
        df['volatility_ratio'] = df['volatility_5'] / df['volatility_20']
        
        # Momentum indicators
        df['rsi_14'] = self._calculate_rsi(df['close'], 14)
        df['rsi_7'] = self._calculate_rsi(df['close'], 7)
        df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
        
        # MACD
        macd_data = self._calculate_macd(df['close'])
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        df['macd_histogram'] = macd_data['histogram']
        
        # Bollinger Bands
        bb_data = self._calculate_bollinger_bands(df['close'], 20, 2)
        df['bb_upper'] = bb_data['upper']
        df['bb_lower'] = bb_data['lower']
        df['bb_middle'] = bb_data['middle']
        df['bb_position'] = (df['close'] - bb_data['lower']) / (bb_data['upper'] - bb_data['lower'])
        df['bb_width'] = (bb_data['upper'] - bb_data['lower']) / bb_data['middle']
        
        # Volume features (if available)
        if 'volume' in df.columns:
            df['volume_sma_10'] = df['volume'].rolling(window=10).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma_10']
            df['price_volume'] = df['close'] * df['volume']
            df['vwap'] = (df['price_volume'].rolling(window=20).sum() / 
                         df['volume'].rolling(window=20).sum())
        
        # Time-based features
        df['hour'] = pd.to_datetime(df.index).hour
        df['day_of_week'] = pd.to_datetime(df.index).dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        return df
    
    def create_market_structure_features(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Create market microstructure features."""
        df = market_data.copy()
        
        # Support and resistance levels
        df['resistance_20'] = df['high'].rolling(window=20).max()
        df['support_20'] = df['low'].rolling(window=20).min()
        df['distance_to_resistance'] = (df['resistance_20'] - df['close']) / df['close']
        df['distance_to_support'] = (df['close'] - df['support_20']) / df['close']
        
        # Trend strength
        df['trend_strength'] = self._calculate_trend_strength(df)
        
        # Market regime features
        df['volatility_regime'] = self._classify_volatility_regime(df)
        df['trend_regime'] = self._classify_trend_regime(df)
        
        return df
    
    def create_cross_asset_features(self, market_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Create features based on cross-asset correlations."""
        if len(market_data) < 2:
            return pd.DataFrame()
        
        # Calculate correlations between assets
        returns_data = {}
        for pair, data in market_data.items():
            returns_data[pair] = data['close'].pct_change()
        
        returns_df = pd.DataFrame(returns_data)
        
        # Rolling correlations
        correlation_features = pd.DataFrame(index=returns_df.index)
        pairs = list(returns_data.keys())
        
        for i, pair1 in enumerate(pairs):
            for pair2 in pairs[i+1:]:
                corr_name = f'corr_{pair1}_{pair2}'
                correlation_features[corr_name] = (
                    returns_df[pair1].rolling(window=20).corr(returns_df[pair2])
                )
        
        return correlation_features
    
    def prepare_features_for_training(
        self, 
        market_data: pd.DataFrame, 
        trade_outcomes: List[Dict],
        feature_columns: Optional[List[str]] = None
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features and labels for model training."""
        # Create all features
        features_df = self.create_technical_features(market_data)
        # Pass the features_df (which includes technical features) to market structure features
        market_structure_features = self.create_market_structure_features(features_df)
        
        # Only add new columns from market structure features to avoid duplicates
        new_columns = [col for col in market_structure_features.columns if col not in features_df.columns]
        if new_columns:
            features_df = pd.concat([
                features_df, 
                market_structure_features[new_columns]
            ], axis=1)
        
        # Create labels from trade outcomes
        labels = self._create_labels_from_trades(trade_outcomes, features_df.index)
        
        # Select feature columns
        if feature_columns is None:
            feature_columns = self._select_important_features(features_df)
        
        # Clean and prepare data
        X = features_df[feature_columns].copy()
        y = labels.copy()
        
        # Remove rows with NaN values
        valid_idx = ~(X.isnull().any(axis=1) | y.isnull())
        X = X[valid_idx]
        y = y[valid_idx]
        
        # Scale features
        scaler_key = 'default'
        if scaler_key not in self.scalers:
            self.scalers[scaler_key] = RobustScaler()
            X_scaled = pd.DataFrame(
                self.scalers[scaler_key].fit_transform(X),
                columns=X.columns,
                index=X.index
            )
        else:
            X_scaled = pd.DataFrame(
                self.scalers[scaler_key].transform(X),
                columns=X.columns,
                index=X.index
            )
        
        return X_scaled, y
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Calculate MACD indicator."""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        
        return {
            'macd': macd,
            'signal': macd_signal,
            'histogram': macd_histogram
        }
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands."""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    
    def _calculate_trend_strength(self, df: pd.DataFrame) -> pd.Series:
        """Calculate trend strength indicator."""
        # Use ADX-like calculation
        high_diff = df['high'].diff()
        low_diff = df['low'].diff().abs()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        atr = self._calculate_atr(df, 14)
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=14).mean()
        
        return adx
    
    def _classify_volatility_regime(self, df: pd.DataFrame) -> pd.Series:
        """Classify volatility regime (0=low, 1=medium, 2=high)."""
        volatility = df['returns'].rolling(window=20).std()
        vol_33 = volatility.rolling(window=100).quantile(0.33)
        vol_67 = volatility.rolling(window=100).quantile(0.67)
        
        regime = pd.Series(1, index=df.index)  # Default to medium
        regime[volatility <= vol_33] = 0  # Low volatility
        regime[volatility >= vol_67] = 2  # High volatility
        
        return regime
    
    def _classify_trend_regime(self, df: pd.DataFrame) -> pd.Series:
        """Classify trend regime (0=bear, 1=sideways, 2=bull)."""
        sma_20 = df['close'].rolling(window=20).mean()
        sma_50 = df['close'].rolling(window=50).mean()
        
        regime = pd.Series(1, index=df.index)  # Default to sideways
        regime[sma_20 > sma_50] = 2  # Bull trend
        regime[sma_20 < sma_50] = 0  # Bear trend
        
        return regime
    
    def _create_labels_from_trades(self, trade_outcomes: List[Dict], index: pd.Index) -> pd.Series:
        """Create binary labels from trade outcomes (1=profitable, 0=unprofitable)."""
        labels = pd.Series(0, index=index)
        
        for trade in trade_outcomes:
            if 'timestamp' in trade and 'profit' in trade:
                timestamp = pd.to_datetime(trade['timestamp'])
                if timestamp in labels.index:
                    labels[timestamp] = 1 if trade['profit'] > 0 else 0
        
        return labels
    
    def _select_important_features(self, features_df: pd.DataFrame) -> List[str]:
        """Select important features for training."""
        # Remove features with too many NaN values
        nan_threshold = 0.5
        valid_features = []
        
        for col in features_df.columns:
            nan_ratio = features_df[col].isnull().sum() / len(features_df)
            if nan_ratio < nan_threshold:
                valid_features.append(col)
        
        # Remove highly correlated features
        if len(valid_features) > 1:
            corr_matrix = features_df[valid_features].corr().abs()
            upper_triangle = corr_matrix.where(
                np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
            )
            
            to_drop = [column for column in upper_triangle.columns 
                      if any(upper_triangle[column] > 0.95)]
            valid_features = [f for f in valid_features if f not in to_drop]
        
        return valid_features


class MLEngine(MLEngineInterface):
    """Main ML engine for the adaptive trading system."""
    
    def __init__(self, model_storage_path: str = "models/adaptive"):
        self.logger = logging.getLogger(__name__)
        self.model_storage_path = model_storage_path
        self.feature_engineer = FeatureEngineer()
        self.models = {}
        self.model_metadata = {}
        self.feature_columns = {}
        
        # Online learning components
        self.trade_results_buffer = []  # Buffer for recent trade results
        self.performance_history = {}  # Track model performance over time
        self.drift_detector = ModelDriftDetector()
        self.model_backup = {}  # Backup models for rollback
        self.online_learning_config = {
            'buffer_size': 1000,
            'min_samples_for_update': 50,
            'drift_threshold': 0.1,
            'performance_window': 100,
            'rollback_threshold': 0.05
        }
        
        # Ensure model storage directory exists
        os.makedirs(model_storage_path, exist_ok=True)
        
        # Initialize ensemble predictor
        self.ensemble_predictor = EnsemblePredictor(self)
        
        # Load existing models
        self._load_existing_models()
    
    def train_models(self, historical_data: pd.DataFrame, trade_outcomes: List[Dict]) -> None:
        """Train ML models on historical data and trade outcomes."""
        try:
            self.logger.info("Starting model training process")
            
            # Prepare features and labels
            X, y = self.feature_engineer.prepare_features_for_training(
                historical_data, trade_outcomes
            )
            
            if len(X) < 100:
                self.logger.warning(f"Insufficient data for training: {len(X)} samples")
                return
            
            # Store feature columns for future use
            self.feature_columns['default'] = list(X.columns)
            
            # Split data for training and validation
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Train different model types
            models_to_train = {
                ModelType.RANDOM_FOREST: RandomForestClassifier(
                    n_estimators=100, max_depth=10, random_state=42
                ),
                ModelType.GRADIENT_BOOSTING: GradientBoostingClassifier(
                    n_estimators=100, max_depth=6, random_state=42
                ),
                ModelType.LINEAR_REGRESSION: LogisticRegression(
                    random_state=42, max_iter=1000
                )
            }
            
            for model_type, model in models_to_train.items():
                self.logger.info(f"Training {model_type.value} model")
                
                # Train model
                model.fit(X_train, y_train)
                
                # Validate model
                train_pred = model.predict(X_train)
                val_pred = model.predict(X_val)
                
                train_accuracy = accuracy_score(y_train, train_pred)
                val_accuracy = accuracy_score(y_val, val_pred)
                
                # Store model and metadata
                model_id = f"{model_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.models[model_type] = model
                
                # Create metadata
                metadata = MLModelMetadata(
                    model_id=model_id,
                    model_type=model_type,
                    version="1.0",
                    trained_at=datetime.now(),
                    training_data_size=len(X_train),
                    training_period=timedelta(days=30),  # Approximate
                    training_accuracy=train_accuracy,
                    validation_accuracy=val_accuracy,
                    features_used=list(X.columns),
                    hyperparameters=model.get_params(),
                    is_active=True
                )
                
                # Add feature importance if available
                if hasattr(model, 'feature_importances_'):
                    metadata.feature_importance = dict(zip(
                        X.columns, model.feature_importances_
                    ))
                
                self.model_metadata[model_type] = metadata
                
                # Save model to disk
                self._save_model(model_type, model, metadata)
                
                self.logger.info(
                    f"Model {model_type.value} trained - "
                    f"Train accuracy: {train_accuracy:.3f}, "
                    f"Val accuracy: {val_accuracy:.3f}"
                )
            
            # Train ensemble model
            self._train_ensemble_model(X_train, X_val, y_train, y_val)
            
            self.logger.info("Model training completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during model training: {str(e)}")
            raise
    
    def predict_trade_outcome(self, signal: AdaptiveSignal, market_conditions: Dict[str, Any]) -> float:
        """Predict the probability of a successful trade using ensemble methods."""
        try:
            # Use the enhanced ensemble predictor
            ensemble_result = self.ensemble_predictor.predict_with_ensemble(
                signal, market_conditions, ensemble_method='confidence_weighted'
            )
            
            # Store prediction context for potential online learning
            features = self._prepare_prediction_features(signal, market_conditions)
            self._store_prediction_context(signal, market_conditions, features, ensemble_result.prediction)
            
            # Store the full ensemble result for later analysis
            if not hasattr(self, 'recent_ensemble_predictions'):
                self.recent_ensemble_predictions = []
            
            self.recent_ensemble_predictions.append(ensemble_result)
            
            # Keep only recent predictions (last 100)
            if len(self.recent_ensemble_predictions) > 100:
                self.recent_ensemble_predictions = self.recent_ensemble_predictions[-100:]
            
            self.logger.debug(
                f"Ensemble prediction: {ensemble_result.prediction:.3f} "
                f"(confidence: {ensemble_result.confidence:.3f}, "
                f"uncertainty: {ensemble_result.uncertainty:.3f}, "
                f"fallback: {ensemble_result.fallback_used})"
            )
            
            return ensemble_result.prediction
            
        except Exception as e:
            self.logger.error(f"Error during ensemble prediction: {str(e)}")
            return 0.5  # Return neutral prediction on error
    
    def update_online(self, trade_result: Dict[str, Any]) -> None:
        """Update models with new trade result using incremental learning."""
        try:
            self.logger.info(f"Processing trade result for online learning: {trade_result}")
            
            # Store trade result for batch retraining and analysis
            self._store_trade_result(trade_result)
            
            # Update model performance tracking
            self._update_model_performance_tracking(trade_result)
            
            # Perform incremental learning if supported
            if self._should_perform_incremental_update(trade_result):
                self._perform_incremental_learning(trade_result)
            
            # Check for model drift and trigger retraining if needed
            self._check_model_drift()
            
            # Update model metadata
            for model_type in self.model_metadata:
                self.model_metadata[model_type].prediction_count += 1
                self.model_metadata[model_type].last_updated = datetime.now()
            
            # Update ensemble performance tracking if we have the necessary data
            if ('prediction' in trade_result and 'actual_outcome' in trade_result and 
                'model_predictions' in trade_result):
                
                model_predictions = trade_result.get('model_predictions', {})
                actual_outcome = trade_result['actual_outcome'] > 0  # Convert to boolean
                regime = trade_result.get('regime')
                
                for model_type, prediction in model_predictions.items():
                    self.update_ensemble_model_performance(
                        model_type, prediction, actual_outcome, regime
                    )
            
            self.logger.debug("Online learning update completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during online update: {str(e)}")
            raise
    
    def get_model_confidence(self, model_type: ModelType) -> float:
        """Get confidence level for a specific model."""
        if model_type not in self.model_metadata:
            return 0.0
        
        metadata = self.model_metadata[model_type]
        
        # Base confidence on validation accuracy
        base_confidence = metadata.validation_accuracy
        
        # Adjust for model age (newer models might be more relevant)
        age_days = (datetime.now() - metadata.trained_at).days
        age_penalty = max(0, min(0.2, age_days / 30 * 0.2))  # Up to 20% penalty after 30 days
        
        # Adjust for prediction count (more predictions = more confidence)
        prediction_bonus = min(0.1, metadata.prediction_count / 1000 * 0.1)  # Up to 10% bonus
        
        confidence = base_confidence - age_penalty + prediction_bonus
        return max(0.0, min(1.0, confidence))
    
    def get_feature_importance(self, model_type: ModelType) -> Dict[str, float]:
        """Get feature importance for a model."""
        if model_type not in self.model_metadata:
            return {}
        
        return self.model_metadata[model_type].feature_importance
    
    def get_model_metadata(self, model_type: ModelType) -> MLModelMetadata:
        """Get metadata for a specific model."""
        if model_type not in self.model_metadata:
            raise ValueError(f"Model type {model_type} not found")
        
        return self.model_metadata[model_type]
    
    def predict_with_full_ensemble_details(
        self, 
        signal: AdaptiveSignal, 
        market_conditions: Dict[str, Any],
        ensemble_method: str = 'confidence_weighted'
    ) -> EnsemblePrediction:
        """Get full ensemble prediction with detailed confidence and uncertainty metrics."""
        return self.ensemble_predictor.predict_with_ensemble(
            signal, market_conditions, ensemble_method
        )
    
    def get_ensemble_performance_summary(self) -> Dict[ModelType, Dict[str, Any]]:
        """Get performance summary for all models in the ensemble."""
        return self.ensemble_predictor.get_model_performance_summary()
    
    def update_ensemble_model_performance(
        self, 
        model_type: ModelType, 
        prediction: float, 
        actual_outcome: bool,
        regime: Optional[RegimeType] = None
    ) -> None:
        """Update performance tracking for ensemble models."""
        self.ensemble_predictor.update_model_performance(
            model_type, prediction, actual_outcome, regime
        )
    
    def _prepare_prediction_features(self, signal: AdaptiveSignal, market_conditions: Dict[str, Any]) -> List[float]:
        """Prepare features for prediction from signal and market conditions."""
        features = []
        
        # Signal features
        features.extend([
            signal.confidence,
            signal.ml_confidence,
            signal.strength.value,
            signal.regime_context.confidence,
            signal.regime_context.volatility_level,
            signal.regime_context.trend_strength,
            signal.regime_context.momentum
        ])
        
        # Market condition features
        if 'rsi' in market_conditions:
            features.append(market_conditions['rsi'])
        else:
            features.append(50.0)  # Neutral RSI
        
        if 'volatility' in market_conditions:
            features.append(market_conditions['volatility'])
        else:
            features.append(0.02)  # Default volatility
        
        # Pad or truncate to match expected feature count
        expected_features = len(self.feature_columns.get('default', []))
        if expected_features > 0:
            while len(features) < expected_features:
                features.append(0.0)
            features = features[:expected_features]
        
        return features
    
    def _train_ensemble_model(self, X_train: pd.DataFrame, X_val: pd.DataFrame, 
                            y_train: pd.Series, y_val: pd.Series) -> None:
        """Train an ensemble model combining multiple base models."""
        if len(self.models) < 2:
            self.logger.warning("Not enough base models for ensemble training")
            return
        
        # Get predictions from base models
        train_predictions = []
        val_predictions = []
        
        for model_type, model in self.models.items():
            if model_type != ModelType.ENSEMBLE:
                if hasattr(model, 'predict_proba'):
                    train_pred = model.predict_proba(X_train)[:, 1]
                    val_pred = model.predict_proba(X_val)[:, 1]
                else:
                    train_pred = model.predict(X_train)
                    val_pred = model.predict(X_val)
                
                train_predictions.append(train_pred)
                val_predictions.append(val_pred)
        
        # Create ensemble features
        X_ensemble_train = np.column_stack(train_predictions)
        X_ensemble_val = np.column_stack(val_predictions)
        
        # Train ensemble model (simple logistic regression on base model predictions)
        ensemble_model = LogisticRegression(random_state=42)
        ensemble_model.fit(X_ensemble_train, y_train)
        
        # Validate ensemble
        ensemble_val_pred = ensemble_model.predict(X_ensemble_val)
        ensemble_accuracy = accuracy_score(y_val, ensemble_val_pred)
        
        # Store ensemble model
        self.models[ModelType.ENSEMBLE] = ensemble_model
        
        # Create ensemble metadata
        ensemble_metadata = MLModelMetadata(
            model_id=f"ensemble_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            model_type=ModelType.ENSEMBLE,
            version="1.0",
            trained_at=datetime.now(),
            training_data_size=len(X_train),
            training_period=timedelta(days=30),
            training_accuracy=accuracy_score(y_train, ensemble_model.predict(X_ensemble_train)),
            validation_accuracy=ensemble_accuracy,
            features_used=[f"model_{i}" for i in range(len(train_predictions))],
            hyperparameters=ensemble_model.get_params(),
            is_active=True
        )
        
        self.model_metadata[ModelType.ENSEMBLE] = ensemble_metadata
        self._save_model(ModelType.ENSEMBLE, ensemble_model, ensemble_metadata)
        
        self.logger.info(f"Ensemble model trained - Validation accuracy: {ensemble_accuracy:.3f}")
    
    def rollback_model(self, model_type: ModelType, backup_id: str = "latest") -> bool:
        """Rollback a model to a previous version."""
        try:
            backup_key = f"{model_type.value}_{backup_id}"
            if backup_key not in self.model_backup:
                self.logger.error(f"No backup found for {backup_key}")
                return False
            
            # Restore model and metadata from backup
            backup_data = self.model_backup[backup_key]
            self.models[model_type] = backup_data['model']
            self.model_metadata[model_type] = backup_data['metadata']
            
            # Save restored model to disk
            self._save_model(model_type, backup_data['model'], backup_data['metadata'])
            
            self.logger.info(f"Successfully rolled back model {model_type.value} to backup {backup_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error rolling back model {model_type.value}: {str(e)}")
            return False
    
    def get_model_performance_history(self, model_type: ModelType) -> List[Dict[str, Any]]:
        """Get performance history for a model."""
        if model_type.value not in self.performance_history:
            return []
        return self.performance_history[model_type.value]
    
    def detect_model_drift(self, model_type: ModelType) -> Dict[str, Any]:
        """Detect if a model has drifted from its training distribution."""
        if model_type not in self.models:
            return {'drift_detected': False, 'reason': 'Model not found'}
        
        return self.drift_detector.detect_drift(
            model_type, 
            self.performance_history.get(model_type.value, [])
        )
    
    def _store_prediction_context(self, signal: AdaptiveSignal, market_conditions: Dict[str, Any], 
                                features: List[float], prediction: float) -> None:
        """Store prediction context for later use in online learning."""
        # Store prediction context that can be matched with trade results later
        prediction_context = {
            'timestamp': datetime.now(),
            'pair': signal.pair,
            'signal_type': signal.signal_type,
            'features': features,
            'prediction': prediction,
            'signal_confidence': signal.confidence,
            'ml_confidence': signal.ml_confidence,
            'market_conditions': market_conditions.copy()
        }
        
        # Store in a separate buffer for prediction contexts
        if not hasattr(self, 'prediction_contexts'):
            self.prediction_contexts = []
        
        self.prediction_contexts.append(prediction_context)
        
        # Maintain buffer size
        if len(self.prediction_contexts) > self.online_learning_config['buffer_size']:
            self.prediction_contexts.pop(0)
    
    def _store_trade_result(self, trade_result: Dict[str, Any]) -> None:
        """Store trade result in buffer for online learning."""
        # Add timestamp if not present
        if 'timestamp' not in trade_result:
            trade_result['timestamp'] = datetime.now()
        
        # Try to match with prediction context
        matched_context = self._match_prediction_context(trade_result)
        if matched_context:
            trade_result['features'] = matched_context['features']
            trade_result['prediction'] = matched_context['prediction']
        
        # Add to buffer
        self.trade_results_buffer.append(trade_result)
        
        # Maintain buffer size
        if len(self.trade_results_buffer) > self.online_learning_config['buffer_size']:
            self.trade_results_buffer.pop(0)
    
    def _match_prediction_context(self, trade_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Match trade result with its prediction context."""
        if not hasattr(self, 'prediction_contexts'):
            return None
        
        trade_timestamp = trade_result.get('timestamp', datetime.now())
        trade_pair = trade_result.get('pair', '')
        
        # Look for matching prediction context within a reasonable time window
        time_window = timedelta(minutes=30)  # 30 minute window
        
        for context in reversed(self.prediction_contexts):  # Search most recent first
            context_timestamp = context['timestamp']
            
            # Check if within time window and same pair
            if (abs((trade_timestamp - context_timestamp).total_seconds()) <= time_window.total_seconds() and
                context['pair'] == trade_pair):
                return context
        
        return None
    
    def _update_model_performance_tracking(self, trade_result: Dict[str, Any]) -> None:
        """Update performance tracking for all models."""
        if 'prediction' not in trade_result or 'actual_outcome' not in trade_result:
            return
        
        prediction = trade_result['prediction']
        actual = trade_result['actual_outcome']
        timestamp = trade_result.get('timestamp', datetime.now())
        
        # Calculate prediction accuracy
        accuracy = 1.0 if (prediction > 0.5 and actual > 0) or (prediction <= 0.5 and actual <= 0) else 0.0
        
        # Update performance history for each model
        for model_type in self.models:
            if model_type.value not in self.performance_history:
                self.performance_history[model_type.value] = []
            
            performance_entry = {
                'timestamp': timestamp,
                'prediction': prediction,
                'actual': actual,
                'accuracy': accuracy,
                'trade_id': trade_result.get('trade_id', 'unknown')
            }
            
            self.performance_history[model_type.value].append(performance_entry)
            
            # Maintain performance history size
            window_size = self.online_learning_config['performance_window']
            if len(self.performance_history[model_type.value]) > window_size:
                self.performance_history[model_type.value].pop(0)
            
            # Update model metadata with recent accuracy
            if len(self.performance_history[model_type.value]) >= 10:
                recent_accuracies = [
                    entry['accuracy'] for entry in 
                    self.performance_history[model_type.value][-10:]
                ]
                self.model_metadata[model_type].recent_accuracy = np.mean(recent_accuracies)
    
    def _should_perform_incremental_update(self, trade_result: Dict[str, Any]) -> bool:
        """Determine if incremental learning should be performed."""
        # Check if we have enough samples
        min_samples = self.online_learning_config['min_samples_for_update']
        if len(self.trade_results_buffer) < min_samples:
            return False
        
        # Check if enough time has passed since last update
        for model_type in self.model_metadata:
            last_updated = self.model_metadata[model_type].last_updated
            if (datetime.now() - last_updated).total_seconds() < 3600:  # 1 hour minimum
                return False
        
        return True
    
    def _perform_incremental_learning(self, trade_result: Dict[str, Any]) -> None:
        """Perform incremental learning on supported models."""
        try:
            # Create backup before updating
            self._create_model_backup()
            
            # Prepare recent data for incremental learning
            recent_results = self.trade_results_buffer[-self.online_learning_config['min_samples_for_update']:]
            
            # For now, we'll use a simple approach: retrain on recent data
            # In a full implementation, this would use true online learning algorithms
            self._retrain_on_recent_data(recent_results)
            
            self.logger.info("Incremental learning completed")
            
        except Exception as e:
            self.logger.error(f"Error during incremental learning: {str(e)}")
            # Rollback on error
            self._rollback_from_backup()
    
    def _retrain_on_recent_data(self, recent_results: List[Dict[str, Any]]) -> None:
        """Retrain models on recent data."""
        if not recent_results:
            return
        
        # Convert trade results to training format
        features_list = []
        labels_list = []
        
        for result in recent_results:
            if 'features' in result and 'actual_outcome' in result:
                features_list.append(result['features'])
                labels_list.append(1 if result['actual_outcome'] > 0 else 0)
        
        if not features_list:
            return
        
        X_new = np.array(features_list)
        y_new = np.array(labels_list)
        
        # Update models that support incremental learning
        for model_type, model in self.models.items():
            if hasattr(model, 'partial_fit'):
                # For models that support partial_fit (like SGD-based models)
                model.partial_fit(X_new, y_new)
                self.logger.info(f"Incrementally updated {model_type.value} model")
            else:
                # For other models, we could implement a sliding window approach
                # or use ensemble methods to incorporate new data
                self.logger.debug(f"Model {model_type.value} does not support incremental learning")
    
    def _check_model_drift(self) -> None:
        """Check for model drift and trigger retraining if needed."""
        for model_type in self.models:
            drift_result = self.detect_model_drift(model_type)
            
            if drift_result.get('drift_detected', False):
                self.logger.warning(
                    f"Drift detected in {model_type.value} model: {drift_result.get('reason', 'Unknown')}"
                )
                
                # Update drift score in metadata
                self.model_metadata[model_type].drift_score = drift_result.get('drift_score', 0.0)
                
                # Trigger retraining if drift is significant
                if drift_result.get('drift_score', 0.0) > self.online_learning_config['drift_threshold']:
                    self.logger.info(f"Triggering retraining for {model_type.value} due to drift")
                    # In a full implementation, this would trigger a background retraining job
    
    def _create_model_backup(self) -> None:
        """Create backup of current models before updating."""
        backup_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for model_type, model in self.models.items():
            backup_key = f"{model_type.value}_{backup_id}"
            
            try:
                # Try to create deep copy using pickle
                model_copy = pickle.loads(pickle.dumps(model))
                metadata_copy = pickle.loads(pickle.dumps(self.model_metadata[model_type]))
            except (pickle.PicklingError, TypeError):
                # Fallback for objects that can't be pickled (like mocks in tests)
                self.logger.warning(f"Could not pickle model {model_type.value}, using reference copy")
                model_copy = model
                metadata_copy = self.model_metadata[model_type]
            
            self.model_backup[backup_key] = {
                'model': model_copy,
                'metadata': metadata_copy
            }
            
            # Also create a "latest" backup
            latest_key = f"{model_type.value}_latest"
            self.model_backup[latest_key] = self.model_backup[backup_key]
        
        # Limit backup storage
        self._cleanup_old_backups()
    
    def _rollback_from_backup(self) -> None:
        """Rollback all models from latest backup."""
        for model_type in self.models:
            self.rollback_model(model_type, "latest")
    
    def _cleanup_old_backups(self) -> None:
        """Clean up old model backups to save memory."""
        max_backups_per_model = 5
        
        # Group backups by model type
        backup_groups = {}
        for backup_key in list(self.model_backup.keys()):
            if '_latest' in backup_key:
                continue  # Skip latest backups
            
            model_type = backup_key.split('_')[0]
            if model_type not in backup_groups:
                backup_groups[model_type] = []
            backup_groups[model_type].append(backup_key)
        
        # Keep only the most recent backups for each model
        for model_type, backup_keys in backup_groups.items():
            backup_keys.sort(reverse=True)  # Most recent first
            
            for old_backup in backup_keys[max_backups_per_model:]:
                del self.model_backup[old_backup]

    def _get_best_model_type(self) -> Optional[ModelType]:
        """Get the model type with the highest confidence."""
        if not self.model_metadata:
            return None
        
        best_model = None
        best_confidence = 0.0
        
        for model_type in self.model_metadata:
            confidence = self.get_model_confidence(model_type)
            if confidence > best_confidence:
                best_confidence = confidence
                best_model = model_type
        
        return best_model
    
    def _save_model(self, model_type: ModelType, model: Any, metadata: MLModelMetadata) -> None:
        """Save model and metadata to disk."""
        try:
            # Save model
            model_path = os.path.join(self.model_storage_path, f"{model_type.value}_model.pkl")
            joblib.dump(model, model_path)
            
            # Save metadata
            metadata_path = os.path.join(self.model_storage_path, f"{model_type.value}_metadata.json")
            with open(metadata_path, 'w') as f:
                # Convert metadata to dict for JSON serialization
                metadata_dict = {
                    'model_id': metadata.model_id,
                    'model_type': metadata.model_type.value,
                    'version': metadata.version,
                    'trained_at': metadata.trained_at.isoformat(),
                    'training_data_size': metadata.training_data_size,
                    'training_period_days': metadata.training_period.days,
                    'training_accuracy': metadata.training_accuracy,
                    'validation_accuracy': metadata.validation_accuracy,
                    'features_used': metadata.features_used,
                    'hyperparameters': metadata.hyperparameters,
                    'feature_importance': metadata.feature_importance,
                    'is_active': metadata.is_active,
                    'prediction_count': metadata.prediction_count
                }
                json.dump(metadata_dict, f, indent=2)
            
            self.logger.info(f"Model {model_type.value} saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving model {model_type.value}: {str(e)}")
    
    def _load_existing_models(self) -> None:
        """Load existing models from disk."""
        try:
            for model_type in ModelType:
                model_path = os.path.join(self.model_storage_path, f"{model_type.value}_model.pkl")
                metadata_path = os.path.join(self.model_storage_path, f"{model_type.value}_metadata.json")
                
                if os.path.exists(model_path) and os.path.exists(metadata_path):
                    # Load model
                    model = joblib.load(model_path)
                    self.models[model_type] = model
                    
                    # Load metadata
                    with open(metadata_path, 'r') as f:
                        metadata_dict = json.load(f)
                    
                    # Reconstruct metadata object
                    metadata = MLModelMetadata(
                        model_id=metadata_dict['model_id'],
                        model_type=ModelType(metadata_dict['model_type']),
                        version=metadata_dict['version'],
                        trained_at=datetime.fromisoformat(metadata_dict['trained_at']),
                        training_data_size=metadata_dict['training_data_size'],
                        training_period=timedelta(days=metadata_dict['training_period_days']),
                        training_accuracy=metadata_dict['training_accuracy'],
                        validation_accuracy=metadata_dict['validation_accuracy'],
                        features_used=metadata_dict['features_used'],
                        hyperparameters=metadata_dict['hyperparameters'],
                        feature_importance=metadata_dict['feature_importance'],
                        is_active=metadata_dict['is_active'],
                        prediction_count=metadata_dict['prediction_count']
                    )
                    
                    self.model_metadata[model_type] = metadata
                    
                    self.logger.info(f"Loaded existing model: {model_type.value}")
        
        except Exception as e:
            self.logger.error(f"Error loading existing models: {str(e)}")

class ModelDriftDetector:
    """Detects model drift based on performance degradation and prediction distribution changes."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_drift(self, model_type: ModelType, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect model drift using multiple methods.
        
        Args:
            model_type: Type of model to check
            performance_history: Historical performance data
            
        Returns:
            Dictionary with drift detection results
        """
        if len(performance_history) < 20:
            return {
                'drift_detected': False,
                'reason': 'Insufficient data for drift detection',
                'drift_score': 0.0
            }
        
        # Performance-based drift detection
        performance_drift = self._detect_performance_drift(performance_history)
        
        # Distribution-based drift detection
        distribution_drift = self._detect_distribution_drift(performance_history)
        
        # Combine drift signals
        overall_drift_score = max(performance_drift['drift_score'], distribution_drift['drift_score'])
        drift_detected = overall_drift_score > 0.1  # Threshold for drift detection
        
        reasons = []
        if performance_drift['drift_detected']:
            reasons.append(performance_drift['reason'])
        if distribution_drift['drift_detected']:
            reasons.append(distribution_drift['reason'])
        
        return {
            'drift_detected': drift_detected,
            'drift_score': overall_drift_score,
            'reason': '; '.join(reasons) if reasons else 'No drift detected',
            'performance_drift': performance_drift,
            'distribution_drift': distribution_drift
        }
    
    def _detect_performance_drift(self, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect drift based on performance degradation."""
        try:
            # Split history into recent and historical periods
            split_point = len(performance_history) // 2
            historical_performance = performance_history[:split_point]
            recent_performance = performance_history[split_point:]
            
            # Calculate average accuracy for each period
            historical_accuracy = np.mean([entry['accuracy'] for entry in historical_performance])
            recent_accuracy = np.mean([entry['accuracy'] for entry in recent_performance])
            
            # Calculate performance degradation
            performance_change = historical_accuracy - recent_accuracy
            drift_score = max(0.0, performance_change)  # Only consider degradation as drift
            
            # Statistical significance test (simple t-test approximation)
            historical_std = np.std([entry['accuracy'] for entry in historical_performance])
            recent_std = np.std([entry['accuracy'] for entry in recent_performance])
            
            # Avoid division by zero
            pooled_std = np.sqrt((historical_std**2 + recent_std**2) / 2)
            if pooled_std > 0:
                t_stat = performance_change / (pooled_std * np.sqrt(2 / len(performance_history)))
                significant = abs(t_stat) > 1.96  # 95% confidence
            else:
                significant = False
            
            drift_detected = drift_score > 0.05 and significant
            
            return {
                'drift_detected': drift_detected,
                'drift_score': drift_score,
                'reason': f'Performance degraded by {performance_change:.3f}' if drift_detected else 'No performance drift',
                'historical_accuracy': historical_accuracy,
                'recent_accuracy': recent_accuracy,
                'statistical_significance': significant
            }
            
        except Exception as e:
            self.logger.error(f"Error in performance drift detection: {str(e)}")
            return {
                'drift_detected': False,
                'drift_score': 0.0,
                'reason': f'Error in drift detection: {str(e)}'
            }
    
    def _detect_distribution_drift(self, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect drift based on prediction distribution changes."""
        try:
            # Split history into recent and historical periods
            split_point = len(performance_history) // 2
            historical_predictions = [entry['prediction'] for entry in performance_history[:split_point]]
            recent_predictions = [entry['prediction'] for entry in performance_history[split_point:]]
            
            # Calculate distribution statistics
            historical_mean = np.mean(historical_predictions)
            recent_mean = np.mean(recent_predictions)
            historical_std = np.std(historical_predictions)
            recent_std = np.std(recent_predictions)
            
            # Calculate distribution drift metrics
            mean_shift = abs(historical_mean - recent_mean)
            std_change = abs(historical_std - recent_std)
            
            # Normalize by historical values to get relative changes
            mean_drift_score = mean_shift / (historical_mean + 1e-8)
            std_drift_score = std_change / (historical_std + 1e-8)
            
            # Combined drift score
            drift_score = max(mean_drift_score, std_drift_score)
            drift_detected = drift_score > 0.2  # 20% change threshold
            
            return {
                'drift_detected': drift_detected,
                'drift_score': drift_score,
                'reason': f'Prediction distribution changed (mean: {mean_drift_score:.3f}, std: {std_drift_score:.3f})' if drift_detected else 'No distribution drift',
                'mean_shift': mean_shift,
                'std_change': std_change,
                'historical_stats': {'mean': historical_mean, 'std': historical_std},
                'recent_stats': {'mean': recent_mean, 'std': recent_std}
            }
            
        except Exception as e:
            self.logger.error(f"Error in distribution drift detection: {str(e)}")
            return {
                'drift_detected': False,
                'drift_score': 0.0,
                'reason': f'Error in distribution drift detection: {str(e)}'
            }