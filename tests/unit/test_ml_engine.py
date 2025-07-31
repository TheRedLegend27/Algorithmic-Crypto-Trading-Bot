"""
Unit tests for the ML Engine components.
"""
import unittest
import tempfile
import shutil
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from bot.adaptive.ml_engine import MLEngine, FeatureEngineer
from bot.adaptive.data_models import AdaptiveSignal, MarketRegime, MLModelMetadata
from bot.adaptive.enums import ModelType, RegimeType, SignalStrength


class TestFeatureEngineer(unittest.TestCase):
    """Test cases for the FeatureEngineer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.feature_engineer = FeatureEngineer()
        
        # Create sample market data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        np.random.seed(42)
        
        self.market_data = pd.DataFrame({
            'open': 100 + np.random.randn(100).cumsum() * 0.5,
            'high': 100 + np.random.randn(100).cumsum() * 0.5 + np.random.rand(100) * 2,
            'low': 100 + np.random.randn(100).cumsum() * 0.5 - np.random.rand(100) * 2,
            'close': 100 + np.random.randn(100).cumsum() * 0.5,
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
        
        # Ensure high >= low and high/low contain open/close
        self.market_data['high'] = self.market_data[['open', 'high', 'close']].max(axis=1)
        self.market_data['low'] = self.market_data[['open', 'low', 'close']].min(axis=1)
    
    def test_create_technical_features(self):
        """Test technical feature creation."""
        features = self.feature_engineer.create_technical_features(self.market_data)
        
        # Check that basic features are created
        expected_features = [
            'returns', 'log_returns', 'price_change', 'price_range',
            'sma_5', 'sma_10', 'sma_20', 'sma_50',
            'ema_5', 'ema_10', 'ema_20', 'ema_50',
            'volatility_5', 'volatility_20', 'atr_14',
            'rsi_14', 'rsi_7', 'momentum_10', 'momentum_5',
            'macd', 'macd_signal', 'macd_histogram',
            'bb_upper', 'bb_lower', 'bb_middle', 'bb_position', 'bb_width'
        ]
        
        for feature in expected_features:
            self.assertIn(feature, features.columns, f"Feature {feature} not found")
        
        # Check that features have reasonable values
        self.assertFalse(features['returns'].isnull().all())
        # Check RSI values (excluding NaN)
        rsi_valid = features['rsi_14'].dropna()
        self.assertTrue((rsi_valid >= 0).all() and (rsi_valid <= 100).all())
        # Check Bollinger Band position (excluding NaN) - can go outside 0-1 range
        bb_pos_valid = features['bb_position'].dropna()
        self.assertFalse(bb_pos_valid.isnull().all())  # Just check it's not all NaN
    
    def test_create_market_structure_features(self):
        """Test market structure feature creation."""
        # First create technical features, then market structure features
        tech_features = self.feature_engineer.create_technical_features(self.market_data)
        features = self.feature_engineer.create_market_structure_features(tech_features)
        
        expected_features = [
            'resistance_20', 'support_20', 'distance_to_resistance', 'distance_to_support',
            'trend_strength', 'volatility_regime', 'trend_regime'
        ]
        
        for feature in expected_features:
            self.assertIn(feature, features.columns, f"Feature {feature} not found")
        
        # Check regime classifications
        self.assertTrue(features['volatility_regime'].isin([0, 1, 2]).all())
        self.assertTrue(features['trend_regime'].isin([0, 1, 2]).all())
    
    def test_create_cross_asset_features(self):
        """Test cross-asset feature creation."""
        # Create multiple asset data
        market_data_multi = {
            'BTCUSD': self.market_data,
            'ETHUSD': self.market_data * 0.1 + np.random.randn(len(self.market_data), 5) * 0.01
        }
        
        features = self.feature_engineer.create_cross_asset_features(market_data_multi)
        
        # Should have correlation features
        self.assertIn('corr_BTCUSD_ETHUSD', features.columns)
        
        # Test with single asset (should return empty DataFrame)
        single_asset = {'BTCUSD': self.market_data}
        features_single = self.feature_engineer.create_cross_asset_features(single_asset)
        self.assertTrue(features_single.empty)
    
    def test_prepare_features_for_training(self):
        """Test feature preparation for training."""
        # Create sample trade outcomes
        trade_outcomes = [
            {'timestamp': self.market_data.index[10], 'profit': 100},
            {'timestamp': self.market_data.index[20], 'profit': -50},
            {'timestamp': self.market_data.index[30], 'profit': 75},
        ]
        
        X, y = self.feature_engineer.prepare_features_for_training(
            self.market_data, trade_outcomes
        )
        
        # Check that we get features and labels
        self.assertIsInstance(X, pd.DataFrame)
        self.assertIsInstance(y, pd.Series)
        self.assertEqual(len(X), len(y))
        
        # Check that labels are binary
        self.assertTrue(y.isin([0, 1]).all())
        
        # Check that features are scaled
        self.assertTrue(abs(X.mean().mean()) < 1.0)  # Should be roughly centered
    
    def test_rsi_calculation(self):
        """Test RSI calculation."""
        prices = pd.Series([44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.85, 46.08, 45.89])
        rsi = self.feature_engineer._calculate_rsi(prices, period=5)
        
        # RSI should be between 0 and 100 (excluding NaN values)
        rsi_valid = rsi.dropna()
        self.assertTrue((rsi_valid >= 0).all() and (rsi_valid <= 100).all())
        
        # Should have NaN values at the beginning due to rolling window
        self.assertTrue(rsi.iloc[:4].isnull().all())
    
    def test_atr_calculation(self):
        """Test ATR calculation."""
        df = self.market_data.copy()
        atr = self.feature_engineer._calculate_atr(df, period=14)
        
        # ATR should be positive (excluding NaN values)
        atr_valid = atr.dropna()
        self.assertTrue((atr_valid >= 0).all())
        
        # Should have NaN values at the beginning
        self.assertTrue(atr.iloc[:13].isnull().all())
    
    def test_macd_calculation(self):
        """Test MACD calculation."""
        prices = self.market_data['close']
        macd_data = self.feature_engineer._calculate_macd(prices)
        
        # Should return all three components
        self.assertIn('macd', macd_data)
        self.assertIn('signal', macd_data)
        self.assertIn('histogram', macd_data)
        
        # Histogram should be MACD - Signal
        expected_histogram = macd_data['macd'] - macd_data['signal']
        pd.testing.assert_series_equal(macd_data['histogram'], expected_histogram)
    
    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation."""
        prices = self.market_data['close']
        bb_data = self.feature_engineer._calculate_bollinger_bands(prices)
        
        # Should return all three bands
        self.assertIn('upper', bb_data)
        self.assertIn('middle', bb_data)
        self.assertIn('lower', bb_data)
        
        # Upper should be >= Middle >= Lower (excluding NaN values)
        valid_idx = ~(bb_data['upper'].isnull() | bb_data['middle'].isnull() | bb_data['lower'].isnull())
        upper_valid = bb_data['upper'][valid_idx]
        middle_valid = bb_data['middle'][valid_idx]
        lower_valid = bb_data['lower'][valid_idx]
        
        self.assertTrue((upper_valid >= middle_valid).all())
        self.assertTrue((middle_valid >= lower_valid).all())


class TestMLEngine(unittest.TestCase):
    """Test cases for the MLEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for model storage
        self.temp_dir = tempfile.mkdtemp()
        self.ml_engine = MLEngine(model_storage_path=self.temp_dir)
        
        # Create sample data
        dates = pd.date_range(start='2023-01-01', periods=200, freq='1H')
        np.random.seed(42)
        
        self.historical_data = pd.DataFrame({
            'open': 100 + np.random.randn(200).cumsum() * 0.5,
            'high': 100 + np.random.randn(200).cumsum() * 0.5 + np.random.rand(200) * 2,
            'low': 100 + np.random.randn(200).cumsum() * 0.5 - np.random.rand(200) * 2,
            'close': 100 + np.random.randn(200).cumsum() * 0.5,
            'volume': np.random.randint(1000, 10000, 200)
        }, index=dates)
        
        # Ensure high >= low and high/low contain open/close
        self.historical_data['high'] = self.historical_data[['open', 'high', 'close']].max(axis=1)
        self.historical_data['low'] = self.historical_data[['open', 'low', 'close']].min(axis=1)
        
        # Create sample trade outcomes
        self.trade_outcomes = []
        for i in range(0, 200, 10):
            self.trade_outcomes.append({
                'timestamp': dates[i],
                'profit': np.random.randn() * 100,
                'signal_type': 'buy' if np.random.rand() > 0.5 else 'sell'
            })
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test ML engine initialization."""
        self.assertIsInstance(self.ml_engine.feature_engineer, FeatureEngineer)
        self.assertEqual(self.ml_engine.model_storage_path, self.temp_dir)
        self.assertTrue(os.path.exists(self.temp_dir))
    
    def test_train_models(self):
        """Test model training."""
        # Train models
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        # Check that models were created
        expected_models = [ModelType.RANDOM_FOREST, ModelType.GRADIENT_BOOSTING, ModelType.LINEAR_REGRESSION]
        for model_type in expected_models:
            self.assertIn(model_type, self.ml_engine.models)
            self.assertIn(model_type, self.ml_engine.model_metadata)
        
        # Check that ensemble model was created if enough base models
        if len(self.ml_engine.models) >= 2:
            self.assertIn(ModelType.ENSEMBLE, self.ml_engine.models)
        
        # Check that models were saved to disk
        for model_type in expected_models:
            model_path = os.path.join(self.temp_dir, f"{model_type.value}_model.pkl")
            metadata_path = os.path.join(self.temp_dir, f"{model_type.value}_metadata.json")
            self.assertTrue(os.path.exists(model_path))
            self.assertTrue(os.path.exists(metadata_path))
    
    def test_train_models_insufficient_data(self):
        """Test model training with insufficient data."""
        # Create very small dataset
        small_data = self.historical_data.iloc[:10]
        small_outcomes = self.trade_outcomes[:2]
        
        # Should not raise exception but should log warning
        with patch.object(self.ml_engine.logger, 'warning') as mock_warning:
            self.ml_engine.train_models(small_data, small_outcomes)
            mock_warning.assert_called()
    
    def test_predict_trade_outcome(self):
        """Test trade outcome prediction."""
        # First train models
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        # Create sample signal
        regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.5,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now()
        )
        
        signal = AdaptiveSignal(
            pair='BTCUSD',
            signal_type='buy',
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=100.0,
            timestamp=datetime.now(),
            regime_context=regime,
            ml_confidence=0.7
        )
        
        market_conditions = {
            'rsi': 65.0,
            'volatility': 0.02,
            'volume': 5000
        }
        
        # Get prediction
        prediction = self.ml_engine.predict_trade_outcome(signal, market_conditions)
        
        # Should return a probability between 0 and 1
        self.assertIsInstance(prediction, float)
        self.assertTrue(0.0 <= prediction <= 1.0)
    
    def test_predict_trade_outcome_no_models(self):
        """Test prediction when no models are available."""
        signal = Mock()
        market_conditions = {}
        
        prediction = self.ml_engine.predict_trade_outcome(signal, market_conditions)
        
        # Should return neutral prediction
        self.assertEqual(prediction, 0.5)
    
    def test_update_online(self):
        """Test online learning update."""
        # First train models
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        initial_count = self.ml_engine.model_metadata[ModelType.RANDOM_FOREST].prediction_count
        
        # Update with new trade result
        trade_result = {
            'profit': 50.0,
            'signal_type': 'buy',
            'timestamp': datetime.now()
        }
        
        self.ml_engine.update_online(trade_result)
        
        # Check that prediction count was updated
        new_count = self.ml_engine.model_metadata[ModelType.RANDOM_FOREST].prediction_count
        self.assertEqual(new_count, initial_count + 1)
    
    def test_get_model_confidence(self):
        """Test model confidence calculation."""
        # Train models first
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        confidence = self.ml_engine.get_model_confidence(ModelType.RANDOM_FOREST)
        
        # Should return a value between 0 and 1
        self.assertIsInstance(confidence, float)
        self.assertTrue(0.0 <= confidence <= 1.0)
        
        # Test with non-existent model
        confidence_none = self.ml_engine.get_model_confidence(ModelType.NEURAL_NETWORK)
        self.assertEqual(confidence_none, 0.0)
    
    def test_get_feature_importance(self):
        """Test feature importance retrieval."""
        # Train models first
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        importance = self.ml_engine.get_feature_importance(ModelType.RANDOM_FOREST)
        
        # Should return a dictionary
        self.assertIsInstance(importance, dict)
        
        # Test with non-existent model
        importance_none = self.ml_engine.get_feature_importance(ModelType.NEURAL_NETWORK)
        self.assertEqual(importance_none, {})
    
    def test_get_model_metadata(self):
        """Test model metadata retrieval."""
        # Train models first
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        metadata = self.ml_engine.get_model_metadata(ModelType.RANDOM_FOREST)
        
        # Should return MLModelMetadata object
        self.assertIsInstance(metadata, MLModelMetadata)
        self.assertEqual(metadata.model_type, ModelType.RANDOM_FOREST)
        
        # Test with non-existent model
        with self.assertRaises(ValueError):
            self.ml_engine.get_model_metadata(ModelType.NEURAL_NETWORK)
    
    def test_save_and_load_models(self):
        """Test model persistence."""
        # Train models
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        # Create new ML engine instance (should load existing models)
        new_ml_engine = MLEngine(model_storage_path=self.temp_dir)
        
        # Check that models were loaded
        for model_type in [ModelType.RANDOM_FOREST, ModelType.GRADIENT_BOOSTING, ModelType.LINEAR_REGRESSION]:
            self.assertIn(model_type, new_ml_engine.models)
            self.assertIn(model_type, new_ml_engine.model_metadata)
    
    def test_prepare_prediction_features(self):
        """Test prediction feature preparation."""
        # Create sample signal
        regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.5,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now()
        )
        
        signal = AdaptiveSignal(
            pair='BTCUSD',
            signal_type='buy',
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=100.0,
            timestamp=datetime.now(),
            regime_context=regime,
            ml_confidence=0.7
        )
        
        market_conditions = {
            'rsi': 65.0,
            'volatility': 0.02
        }
        
        features = self.ml_engine._prepare_prediction_features(signal, market_conditions)
        
        # Should return a list of floats
        self.assertIsInstance(features, list)
        self.assertTrue(all(isinstance(f, (int, float)) for f in features))
    
    def test_get_best_model_type(self):
        """Test best model type selection."""
        # Train models first
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        best_model = self.ml_engine._get_best_model_type()
        
        # Should return a ModelType
        self.assertIsInstance(best_model, ModelType)
        
        # Test with no models
        empty_engine = MLEngine(model_storage_path=tempfile.mkdtemp())
        best_model_none = empty_engine._get_best_model_type()
        self.assertIsNone(best_model_none)
    
    def test_train_ensemble_model(self):
        """Test ensemble model training."""
        # First train base models
        self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
        
        # Check that ensemble model was created
        if len(self.ml_engine.models) >= 2:
            self.assertIn(ModelType.ENSEMBLE, self.ml_engine.models)
            self.assertIn(ModelType.ENSEMBLE, self.ml_engine.model_metadata)
    
    @patch('bot.adaptive.ml_engine.joblib.dump')
    def test_save_model_error_handling(self, mock_dump):
        """Test error handling in model saving."""
        mock_dump.side_effect = Exception("Save error")
        
        # Train models (should handle save errors gracefully)
        with patch.object(self.ml_engine.logger, 'error') as mock_error:
            self.ml_engine.train_models(self.historical_data, self.trade_outcomes)
            mock_error.assert_called()
    
    def test_prediction_error_handling(self):
        """Test error handling in prediction."""
        # Create invalid signal that will cause prediction error
        signal = Mock()
        signal.confidence = "invalid"  # Should be float
        
        prediction = self.ml_engine.predict_trade_outcome(signal, {})
        
        # Should return neutral prediction on error
        self.assertEqual(prediction, 0.5)


if __name__ == '__main__':
    unittest.main()