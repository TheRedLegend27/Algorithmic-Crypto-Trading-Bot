"""
Unit tests for ML Engine online learning capabilities.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil
import os

from bot.adaptive.ml_engine import MLEngine, ModelDriftDetector
from bot.adaptive.data_models import AdaptiveSignal, MarketRegime, MLModelMetadata
from bot.adaptive.enums import ModelType, RegimeType, SignalStrength


class TestMLEngineOnlineLearning(unittest.TestCase):
    """Test cases for ML Engine online learning functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ml_engine = MLEngine(model_storage_path=self.temp_dir)
        
        # Create mock market regime
        self.mock_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.3,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now()
        )
        
        # Create mock adaptive signal
        self.mock_signal = AdaptiveSignal(
            pair="BTCUSD",
            signal_type="buy",
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=50000.0,
            timestamp=datetime.now(),
            regime_context=self.mock_regime,
            ml_confidence=0.7
        )
        
        # Mock market conditions
        self.mock_market_conditions = {
            'rsi': 65.0,
            'volatility': 0.02,
            'volume': 1000000,
            'trend': 'bullish'
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_store_prediction_context(self):
        """Test storing prediction context for online learning."""
        features = [0.1, 0.2, 0.3, 0.4, 0.5]
        prediction = 0.75
        
        # Store prediction context
        self.ml_engine._store_prediction_context(
            self.mock_signal, self.mock_market_conditions, features, prediction
        )
        
        # Check that context was stored
        self.assertTrue(hasattr(self.ml_engine, 'prediction_contexts'))
        self.assertEqual(len(self.ml_engine.prediction_contexts), 1)
        
        context = self.ml_engine.prediction_contexts[0]
        self.assertEqual(context['pair'], 'BTCUSD')
        self.assertEqual(context['signal_type'], 'buy')
        self.assertEqual(context['features'], features)
        self.assertEqual(context['prediction'], prediction)
        self.assertEqual(context['signal_confidence'], 0.8)
        self.assertEqual(context['ml_confidence'], 0.7)
    
    def test_match_prediction_context(self):
        """Test matching trade results with prediction contexts."""
        # Store a prediction context
        features = [0.1, 0.2, 0.3, 0.4, 0.5]
        prediction = 0.75
        self.ml_engine._store_prediction_context(
            self.mock_signal, self.mock_market_conditions, features, prediction
        )
        
        # Create matching trade result
        trade_result = {
            'pair': 'BTCUSD',
            'timestamp': datetime.now(),
            'profit': 100.0,
            'actual_outcome': 1
        }
        
        # Test matching
        matched_context = self.ml_engine._match_prediction_context(trade_result)
        
        self.assertIsNotNone(matched_context)
        self.assertEqual(matched_context['pair'], 'BTCUSD')
        self.assertEqual(matched_context['features'], features)
        self.assertEqual(matched_context['prediction'], prediction)
    
    def test_match_prediction_context_no_match(self):
        """Test prediction context matching when no match exists."""
        # Store a prediction context for different pair
        self.ml_engine._store_prediction_context(
            self.mock_signal, self.mock_market_conditions, [0.1, 0.2], 0.75
        )
        
        # Create non-matching trade result
        trade_result = {
            'pair': 'ETHUSD',  # Different pair
            'timestamp': datetime.now(),
            'profit': 100.0,
            'actual_outcome': 1
        }
        
        # Test matching
        matched_context = self.ml_engine._match_prediction_context(trade_result)
        
        self.assertIsNone(matched_context)
    
    def test_store_trade_result(self):
        """Test storing trade results for online learning."""
        trade_result = {
            'pair': 'BTCUSD',
            'profit': 100.0,
            'actual_outcome': 1,
            'trade_id': 'test_trade_1'
        }
        
        # Store trade result
        self.ml_engine._store_trade_result(trade_result)
        
        # Check that result was stored
        self.assertEqual(len(self.ml_engine.trade_results_buffer), 1)
        stored_result = self.ml_engine.trade_results_buffer[0]
        
        self.assertEqual(stored_result['pair'], 'BTCUSD')
        self.assertEqual(stored_result['profit'], 100.0)
        self.assertEqual(stored_result['actual_outcome'], 1)
        self.assertIn('timestamp', stored_result)
    
    def test_update_model_performance_tracking(self):
        """Test updating model performance tracking."""
        # Create mock models and metadata
        self.ml_engine.models[ModelType.RANDOM_FOREST] = Mock()
        self.ml_engine.model_metadata[ModelType.RANDOM_FOREST] = MLModelMetadata(
            model_id='test_rf',
            model_type=ModelType.RANDOM_FOREST,
            version='1.0',
            trained_at=datetime.now(),
            training_data_size=1000,
            training_period=timedelta(days=30),
            training_accuracy=0.8,
            validation_accuracy=0.75
        )
        
        # Create trade result with prediction
        trade_result = {
            'prediction': 0.8,
            'actual_outcome': 1,
            'timestamp': datetime.now(),
            'trade_id': 'test_trade_1'
        }
        
        # Update performance tracking
        self.ml_engine._update_model_performance_tracking(trade_result)
        
        # Check that performance history was updated
        self.assertIn('random_forest', self.ml_engine.performance_history)
        history = self.ml_engine.performance_history['random_forest']
        
        self.assertEqual(len(history), 1)
        entry = history[0]
        
        self.assertEqual(entry['prediction'], 0.8)
        self.assertEqual(entry['actual'], 1)
        self.assertEqual(entry['accuracy'], 1.0)  # Correct prediction
        self.assertEqual(entry['trade_id'], 'test_trade_1')
    
    def test_should_perform_incremental_update(self):
        """Test logic for determining when to perform incremental updates."""
        # Initially should not update (not enough samples)
        self.assertFalse(self.ml_engine._should_perform_incremental_update({}))
        
        # Add enough samples to buffer
        for i in range(60):  # More than min_samples_for_update (50)
            self.ml_engine.trade_results_buffer.append({
                'trade_id': f'trade_{i}',
                'timestamp': datetime.now()
            })
        
        # Create mock model metadata with old timestamp
        old_timestamp = datetime.now() - timedelta(hours=2)
        self.ml_engine.model_metadata[ModelType.RANDOM_FOREST] = MLModelMetadata(
            model_id='test_rf',
            model_type=ModelType.RANDOM_FOREST,
            version='1.0',
            trained_at=old_timestamp,
            training_data_size=1000,
            training_period=timedelta(days=30),
            training_accuracy=0.8,
            validation_accuracy=0.75,
            last_updated=old_timestamp
        )
        
        # Now should update
        self.assertTrue(self.ml_engine._should_perform_incremental_update({}))
    
    @patch('bot.adaptive.ml_engine.MLEngine._create_model_backup')
    @patch('bot.adaptive.ml_engine.MLEngine._retrain_on_recent_data')
    def test_perform_incremental_learning(self, mock_retrain, mock_backup):
        """Test performing incremental learning."""
        # Add some trade results
        for i in range(10):
            self.ml_engine.trade_results_buffer.append({
                'trade_id': f'trade_{i}',
                'features': [0.1 * i, 0.2 * i],
                'actual_outcome': i % 2
            })
        
        # Perform incremental learning
        self.ml_engine._perform_incremental_learning({})
        
        # Check that backup was created and retraining was called
        mock_backup.assert_called_once()
        mock_retrain.assert_called_once()
    
    def test_retrain_on_recent_data(self):
        """Test retraining models on recent data."""
        # Create mock model with partial_fit capability
        mock_model = Mock()
        mock_model.partial_fit = Mock()
        self.ml_engine.models[ModelType.LINEAR_REGRESSION] = mock_model
        
        # Create recent results with features
        recent_results = [
            {'features': [0.1, 0.2], 'actual_outcome': 1},
            {'features': [0.3, 0.4], 'actual_outcome': 0},
            {'features': [0.5, 0.6], 'actual_outcome': 1}
        ]
        
        # Retrain on recent data
        self.ml_engine._retrain_on_recent_data(recent_results)
        
        # Check that partial_fit was called
        mock_model.partial_fit.assert_called_once()
        
        # Check the arguments passed to partial_fit
        args, kwargs = mock_model.partial_fit.call_args
        X_new, y_new = args
        
        np.testing.assert_array_equal(X_new, [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        np.testing.assert_array_equal(y_new, [1, 0, 1])
    
    def test_create_model_backup(self):
        """Test creating model backups."""
        # Create mock model and metadata
        mock_model = Mock()
        self.ml_engine.models[ModelType.RANDOM_FOREST] = mock_model
        self.ml_engine.model_metadata[ModelType.RANDOM_FOREST] = MLModelMetadata(
            model_id='test_rf',
            model_type=ModelType.RANDOM_FOREST,
            version='1.0',
            trained_at=datetime.now(),
            training_data_size=1000,
            training_period=timedelta(days=30),
            training_accuracy=0.8,
            validation_accuracy=0.75
        )
        
        # Create backup
        self.ml_engine._create_model_backup()
        
        # Check that backup was created
        self.assertTrue(len(self.ml_engine.model_backup) >= 2)  # At least timestamped and latest
        
        # Check that latest backup exists
        latest_key = 'random_forest_latest'
        self.assertIn(latest_key, self.ml_engine.model_backup)
        
        backup = self.ml_engine.model_backup[latest_key]
        self.assertIn('model', backup)
        self.assertIn('metadata', backup)
    
    def test_rollback_model(self):
        """Test rolling back a model to previous version."""
        # Create mock model and backup
        original_model = Mock()
        backup_model = Mock()
        
        self.ml_engine.models[ModelType.RANDOM_FOREST] = original_model
        self.ml_engine.model_backup['random_forest_latest'] = {
            'model': backup_model,
            'metadata': MLModelMetadata(
                model_id='backup_rf',
                model_type=ModelType.RANDOM_FOREST,
                version='1.0',
                trained_at=datetime.now(),
                training_data_size=1000,
                training_period=timedelta(days=30),
                training_accuracy=0.8,
                validation_accuracy=0.75
            )
        }
        
        # Mock the save method
        with patch.object(self.ml_engine, '_save_model') as mock_save:
            # Rollback model
            result = self.ml_engine.rollback_model(ModelType.RANDOM_FOREST, 'latest')
            
            # Check that rollback was successful
            self.assertTrue(result)
            self.assertEqual(self.ml_engine.models[ModelType.RANDOM_FOREST], backup_model)
            mock_save.assert_called_once()
    
    def test_update_online_integration(self):
        """Test the complete online learning update process."""
        # Create mock models
        self.ml_engine.models[ModelType.RANDOM_FOREST] = Mock()
        self.ml_engine.model_metadata[ModelType.RANDOM_FOREST] = MLModelMetadata(
            model_id='test_rf',
            model_type=ModelType.RANDOM_FOREST,
            version='1.0',
            trained_at=datetime.now(),
            training_data_size=1000,
            training_period=timedelta(days=30),
            training_accuracy=0.8,
            validation_accuracy=0.75
        )
        
        # Mock the drift detector
        with patch.object(self.ml_engine.drift_detector, 'detect_drift') as mock_drift:
            mock_drift.return_value = {'drift_detected': False, 'drift_score': 0.05}
            
            # Create trade result
            trade_result = {
                'pair': 'BTCUSD',
                'profit': 100.0,
                'actual_outcome': 1,
                'prediction': 0.8,
                'trade_id': 'test_trade_1'
            }
            
            # Update online
            self.ml_engine.update_online(trade_result)
            
            # Check that trade result was stored
            self.assertEqual(len(self.ml_engine.trade_results_buffer), 1)
            
            # Check that performance tracking was updated
            self.assertIn('random_forest', self.ml_engine.performance_history)
            
            # Check that drift detection was called
            mock_drift.assert_called_once()


class TestModelDriftDetector(unittest.TestCase):
    """Test cases for model drift detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.drift_detector = ModelDriftDetector()
    
    def test_detect_drift_insufficient_data(self):
        """Test drift detection with insufficient data."""
        performance_history = [
            {'accuracy': 0.8, 'prediction': 0.7} for _ in range(10)
        ]
        
        result = self.drift_detector.detect_drift(ModelType.RANDOM_FOREST, performance_history)
        
        self.assertFalse(result['drift_detected'])
        self.assertEqual(result['reason'], 'Insufficient data for drift detection')
        self.assertEqual(result['drift_score'], 0.0)
    
    def test_detect_performance_drift(self):
        """Test detection of performance-based drift."""
        # Create performance history with degradation
        performance_history = []
        
        # Historical period with good performance
        for i in range(15):
            performance_history.append({
                'accuracy': 0.8 + np.random.normal(0, 0.05),  # Good performance
                'prediction': 0.7 + np.random.normal(0, 0.1)
            })
        
        # Recent period with poor performance
        for i in range(15):
            performance_history.append({
                'accuracy': 0.6 + np.random.normal(0, 0.05),  # Poor performance
                'prediction': 0.7 + np.random.normal(0, 0.1)
            })
        
        result = self.drift_detector._detect_performance_drift(performance_history)
        
        self.assertTrue(result['drift_detected'])
        self.assertGreater(result['drift_score'], 0.05)
        self.assertIn('Performance degraded', result['reason'])
    
    def test_detect_distribution_drift(self):
        """Test detection of distribution-based drift."""
        # Create performance history with distribution change
        performance_history = []
        
        # Historical period with one distribution
        for i in range(15):
            performance_history.append({
                'accuracy': 0.8,
                'prediction': 0.5 + np.random.normal(0, 0.1)  # Centered around 0.5
            })
        
        # Recent period with different distribution
        for i in range(15):
            performance_history.append({
                'accuracy': 0.8,
                'prediction': 0.8 + np.random.normal(0, 0.1)  # Centered around 0.8
            })
        
        result = self.drift_detector._detect_distribution_drift(performance_history)
        
        self.assertTrue(result['drift_detected'])
        self.assertGreater(result['drift_score'], 0.2)
        self.assertIn('Prediction distribution changed', result['reason'])
    
    def test_detect_drift_combined(self):
        """Test combined drift detection."""
        # Create performance history with both types of drift
        performance_history = []
        
        # Historical period
        for i in range(15):
            performance_history.append({
                'accuracy': 0.8,
                'prediction': 0.5 + np.random.normal(0, 0.05)
            })
        
        # Recent period with both performance and distribution drift
        for i in range(15):
            performance_history.append({
                'accuracy': 0.6,  # Performance drift
                'prediction': 0.8 + np.random.normal(0, 0.05)  # Distribution drift
            })
        
        result = self.drift_detector.detect_drift(ModelType.RANDOM_FOREST, performance_history)
        
        self.assertTrue(result['drift_detected'])
        self.assertGreater(result['drift_score'], 0.1)
        self.assertTrue(result['performance_drift']['drift_detected'])
        self.assertTrue(result['distribution_drift']['drift_detected'])


if __name__ == '__main__':
    unittest.main()