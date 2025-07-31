"""
Unit tests for the ensemble prediction system.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from bot.adaptive.ensemble_predictor import (
    EnsemblePredictor, EnsemblePrediction, ModelPerformanceTracker
)
from bot.adaptive.data_models import AdaptiveSignal, MarketRegime
from bot.adaptive.enums import ModelType, RegimeType, SignalStrength


class TestModelPerformanceTracker(unittest.TestCase):
    """Test the ModelPerformanceTracker class."""
    
    def setUp(self):
        self.tracker = ModelPerformanceTracker(ModelType.RANDOM_FOREST)
    
    def test_initialization(self):
        """Test tracker initialization."""
        self.assertEqual(self.tracker.model_type, ModelType.RANDOM_FOREST)
        self.assertEqual(self.tracker.recent_accuracy, 0.5)
        self.assertEqual(self.tracker.long_term_accuracy, 0.5)
        self.assertEqual(self.tracker.prediction_count, 0)
        self.assertEqual(len(self.tracker.recent_predictions), 0)
    
    def test_update_performance_single_prediction(self):
        """Test updating performance with a single prediction."""
        self.tracker.update_performance(0.8, True)
        
        self.assertEqual(self.tracker.prediction_count, 1)
        self.assertEqual(len(self.tracker.recent_predictions), 1)
        self.assertEqual(self.tracker.recent_predictions[0], (0.8, True))
    
    def test_update_performance_multiple_predictions(self):
        """Test updating performance with multiple predictions."""
        # Add several predictions
        predictions = [(0.8, True), (0.3, False), (0.9, True), (0.2, False)]
        
        for pred, outcome in predictions:
            self.tracker.update_performance(pred, outcome)
        
        self.assertEqual(self.tracker.prediction_count, 4)
        self.assertEqual(len(self.tracker.recent_predictions), 4)
        
        # Check that accuracy is calculated correctly
        # All predictions were correct (0.8>0.5 and True, 0.3<0.5 and False, etc.)
        self.assertEqual(self.tracker.recent_accuracy, 1.0)
    
    def test_update_performance_buffer_limit(self):
        """Test that recent predictions buffer is limited."""
        # Add more than 100 predictions
        for i in range(150):
            self.tracker.update_performance(0.6, True)
        
        # Should only keep last 100
        self.assertEqual(len(self.tracker.recent_predictions), 100)
        self.assertEqual(self.tracker.prediction_count, 150)
    
    def test_dynamic_weight_calculation(self):
        """Test dynamic weight calculation."""
        # Add some good predictions
        for _ in range(20):
            self.tracker.update_performance(0.8, True)
        
        weight = self.tracker.get_dynamic_weight(1.0)
        self.assertGreater(weight, 0.5)  # Should be above average
        
        # Add some bad predictions
        for _ in range(20):
            self.tracker.update_performance(0.8, False)  # Wrong predictions
        
        new_weight = self.tracker.get_dynamic_weight(1.0)
        self.assertLess(new_weight, weight)  # Should decrease
    
    def test_performance_trend_calculation(self):
        """Test performance trend calculation."""
        # Add poor performance first
        for _ in range(10):
            self.tracker.update_performance(0.8, False)  # Wrong predictions (0.8 > 0.5 but outcome is False)
        
        # Then add good performance
        for _ in range(10):
            self.tracker.update_performance(0.8, True)   # Correct predictions (0.8 > 0.5 and outcome is True)
        
        # Should detect positive trend (improvement from bad to good)
        self.assertGreater(self.tracker.performance_trend, 0)


class TestEnsemblePrediction(unittest.TestCase):
    """Test the EnsemblePrediction class."""
    
    def test_initialization(self):
        """Test ensemble prediction initialization."""
        prediction = EnsemblePrediction(
            prediction=0.75,
            confidence=0.8,
            uncertainty=0.2
        )
        
        self.assertEqual(prediction.prediction, 0.75)
        self.assertEqual(prediction.confidence, 0.8)
        self.assertEqual(prediction.uncertainty, 0.2)
        self.assertFalse(prediction.fallback_used)
    
    def test_prediction_interval(self):
        """Test prediction interval calculation."""
        prediction = EnsemblePrediction(
            prediction=0.6,
            confidence=0.8,
            uncertainty=0.1
        )
        
        lower, upper = prediction.get_prediction_interval(0.95)
        
        # Should be symmetric around prediction
        self.assertLess(lower, 0.6)
        self.assertGreater(upper, 0.6)
        self.assertGreaterEqual(lower, 0.0)
        self.assertLessEqual(upper, 1.0)


class TestEnsemblePredictor(unittest.TestCase):
    """Test the EnsemblePredictor class."""
    
    def setUp(self):
        # Create mock ML engine
        self.mock_ml_engine = Mock()
        self.mock_ml_engine.models = {
            ModelType.RANDOM_FOREST: Mock(),
            ModelType.GRADIENT_BOOSTING: Mock(),
            ModelType.LINEAR_REGRESSION: Mock()
        }
        
        # Create ensemble predictor
        self.predictor = EnsemblePredictor(self.mock_ml_engine)
        
        # Create test signal
        self.test_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.3,
            trend_strength=0.7,
            momentum=0.5,
            detected_at=datetime.now()
        )
        
        self.test_signal = AdaptiveSignal(
            pair="BTCUSD",
            signal_type="buy",
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=50000.0,
            timestamp=datetime.now(),
            regime_context=self.test_regime,
            ml_confidence=0.7
        )
        
        self.test_market_conditions = {
            'rsi': 45.0,
            'volatility': 0.02,
            'volume_ratio': 1.2
        }
    
    def test_initialization(self):
        """Test ensemble predictor initialization."""
        self.assertIsNotNone(self.predictor.ml_engine)
        self.assertIsInstance(self.predictor.model_trackers, dict)
        self.assertIn('min_models_for_ensemble', self.predictor.ensemble_config)
        
        # Should have trackers for all model types except ensemble
        expected_trackers = [mt for mt in ModelType if mt != ModelType.ENSEMBLE]
        self.assertEqual(len(self.predictor.model_trackers), len(expected_trackers))
    
    @patch.object(EnsemblePredictor, '_get_individual_predictions')
    def test_predict_with_ensemble_insufficient_models(self, mock_get_predictions):
        """Test ensemble prediction with insufficient models."""
        # Mock insufficient models
        mock_get_predictions.return_value = {ModelType.RANDOM_FOREST: 0.7}
        
        result = self.predictor.predict_with_ensemble(
            self.test_signal, self.test_market_conditions
        )
        
        self.assertIsInstance(result, EnsemblePrediction)
        self.assertTrue(result.fallback_used)
        self.assertIn("insufficient_models", result.fallback_reason)
    
    @patch.object(EnsemblePredictor, '_get_individual_predictions')
    def test_predict_with_ensemble_success(self, mock_get_predictions):
        """Test successful ensemble prediction."""
        # Mock sufficient models with predictions
        mock_predictions = {
            ModelType.RANDOM_FOREST: 0.7,
            ModelType.GRADIENT_BOOSTING: 0.8,
            ModelType.LINEAR_REGRESSION: 0.6
        }
        mock_get_predictions.return_value = mock_predictions
        
        result = self.predictor.predict_with_ensemble(
            self.test_signal, self.test_market_conditions
        )
        
        self.assertIsInstance(result, EnsemblePrediction)
        self.assertFalse(result.fallback_used)
        self.assertGreater(result.confidence, 0.0)
        self.assertLess(result.uncertainty, 1.0)
        self.assertEqual(len(result.model_predictions), 3)
    
    def test_calculate_dynamic_weights(self):
        """Test dynamic weight calculation."""
        mock_predictions = {
            ModelType.RANDOM_FOREST: 0.7,
            ModelType.GRADIENT_BOOSTING: 0.8
        }
        
        # Add more significant performance history
        # Random Forest: good performance
        for _ in range(10):
            self.predictor.model_trackers[ModelType.RANDOM_FOREST].update_performance(0.8, True)
        
        # Gradient Boosting: poor performance
        for _ in range(10):
            self.predictor.model_trackers[ModelType.GRADIENT_BOOSTING].update_performance(0.8, False)
        
        weights = self.predictor._calculate_dynamic_weights(
            mock_predictions, RegimeType.TRENDING_BULL
        )
        
        self.assertEqual(len(weights), 2)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        
        # Random forest should have higher weight (better performance)
        self.assertGreater(
            weights[ModelType.RANDOM_FOREST], 
            weights[ModelType.GRADIENT_BOOSTING]
        )
    
    def test_weighted_average_ensemble(self):
        """Test weighted average ensemble method."""
        predictions = {
            ModelType.RANDOM_FOREST: 0.8,
            ModelType.GRADIENT_BOOSTING: 0.6
        }
        weights = {
            ModelType.RANDOM_FOREST: 0.7,
            ModelType.GRADIENT_BOOSTING: 0.3
        }
        
        result = self.predictor._weighted_average_ensemble(
            predictions, weights, self.test_signal, self.test_market_conditions
        )
        
        expected = 0.8 * 0.7 + 0.6 * 0.3
        self.assertAlmostEqual(result, expected, places=5)
    
    def test_confidence_weighted_ensemble(self):
        """Test confidence-weighted ensemble method."""
        predictions = {
            ModelType.RANDOM_FOREST: 0.8,
            ModelType.GRADIENT_BOOSTING: 0.6
        }
        weights = {
            ModelType.RANDOM_FOREST: 0.5,
            ModelType.GRADIENT_BOOSTING: 0.5
        }
        
        # Set different calibration scores
        self.predictor.model_trackers[ModelType.RANDOM_FOREST].calibration_score = 0.8
        self.predictor.model_trackers[ModelType.GRADIENT_BOOSTING].calibration_score = 0.4
        
        result = self.predictor._confidence_weighted_ensemble(
            predictions, weights, self.test_signal, self.test_market_conditions
        )
        
        # Should weight more towards the better calibrated model
        self.assertGreater(result, 0.7)  # Closer to 0.8 than 0.6
    
    def test_calculate_ensemble_confidence(self):
        """Test ensemble confidence calculation."""
        predictions = {
            ModelType.RANDOM_FOREST: 0.8,
            ModelType.GRADIENT_BOOSTING: 0.82,  # Close agreement
            ModelType.LINEAR_REGRESSION: 0.78
        }
        weights = {model: 1/3 for model in predictions.keys()}
        
        confidence = self.predictor._calculate_ensemble_confidence(
            predictions, weights, 0.8
        )
        
        self.assertGreater(confidence, 0.5)  # Should be confident with close agreement
        self.assertLessEqual(confidence, 1.0)
    
    def test_calculate_prediction_uncertainty(self):
        """Test prediction uncertainty calculation."""
        # High agreement case
        predictions_low_uncertainty = {
            ModelType.RANDOM_FOREST: 0.8,
            ModelType.GRADIENT_BOOSTING: 0.82
        }
        weights = {model: 0.5 for model in predictions_low_uncertainty.keys()}
        
        uncertainty_low = self.predictor._calculate_prediction_uncertainty(
            predictions_low_uncertainty, weights
        )
        
        # High disagreement case
        predictions_high_uncertainty = {
            ModelType.RANDOM_FOREST: 0.2,
            ModelType.GRADIENT_BOOSTING: 0.8
        }
        
        uncertainty_high = self.predictor._calculate_prediction_uncertainty(
            predictions_high_uncertainty, weights
        )
        
        self.assertLess(uncertainty_low, uncertainty_high)
    
    def test_calculate_consensus_level(self):
        """Test consensus level calculation."""
        # High consensus
        predictions_high_consensus = {
            ModelType.RANDOM_FOREST: 0.8,
            ModelType.GRADIENT_BOOSTING: 0.82,
            ModelType.LINEAR_REGRESSION: 0.78
        }
        
        consensus_high = self.predictor._calculate_consensus_level(predictions_high_consensus)
        
        # Low consensus
        predictions_low_consensus = {
            ModelType.RANDOM_FOREST: 0.2,
            ModelType.GRADIENT_BOOSTING: 0.8,
            ModelType.LINEAR_REGRESSION: 0.5
        }
        
        consensus_low = self.predictor._calculate_consensus_level(predictions_low_consensus)
        
        self.assertGreater(consensus_high, consensus_low)
    
    def test_fallback_mechanisms(self):
        """Test various fallback mechanisms."""
        # Test technical analysis fallback
        fallback_result = self.predictor._technical_analysis_fallback(
            self.test_signal, self.test_market_conditions
        )
        self.assertIsNotNone(fallback_result)
        self.assertGreaterEqual(fallback_result, 0.0)
        self.assertLessEqual(fallback_result, 1.0)
        
        # Test regime-based fallback
        fallback_result = self.predictor._regime_based_fallback(
            self.test_signal, self.test_market_conditions
        )
        self.assertIsNotNone(fallback_result)
        
        # Test conservative fallback
        fallback_result = self.predictor._conservative_fallback(
            self.test_signal, self.test_market_conditions
        )
        self.assertEqual(fallback_result, 0.5)
    
    def test_update_model_performance(self):
        """Test updating model performance."""
        initial_count = self.predictor.model_trackers[ModelType.RANDOM_FOREST].prediction_count
        
        self.predictor.update_model_performance(
            ModelType.RANDOM_FOREST, 0.8, True, RegimeType.TRENDING_BULL
        )
        
        tracker = self.predictor.model_trackers[ModelType.RANDOM_FOREST]
        self.assertEqual(tracker.prediction_count, initial_count + 1)
        self.assertIn(RegimeType.TRENDING_BULL, tracker.regime_performance)
    
    def test_get_model_performance_summary(self):
        """Test getting model performance summary."""
        # Add some performance data
        self.predictor.update_model_performance(ModelType.RANDOM_FOREST, 0.8, True)
        
        summary = self.predictor.get_model_performance_summary()
        
        self.assertIn(ModelType.RANDOM_FOREST, summary)
        self.assertIn('recent_accuracy', summary[ModelType.RANDOM_FOREST])
        self.assertIn('dynamic_weight', summary[ModelType.RANDOM_FOREST])
    
    @patch.object(EnsemblePredictor, '_get_individual_predictions')
    def test_low_quality_prediction_fallback(self, mock_get_predictions):
        """Test that low quality predictions trigger fallback."""
        # Mock predictions with high disagreement (low consensus)
        mock_predictions = {
            ModelType.RANDOM_FOREST: 0.1,
            ModelType.GRADIENT_BOOSTING: 0.9,
            ModelType.LINEAR_REGRESSION: 0.5
        }
        mock_get_predictions.return_value = mock_predictions
        
        result = self.predictor.predict_with_ensemble(
            self.test_signal, self.test_market_conditions
        )
        
        # Should use fallback due to low consensus
        self.assertTrue(result.fallback_used)
        self.assertIn("low_quality", result.fallback_reason)


class TestEnsembleIntegration(unittest.TestCase):
    """Integration tests for ensemble prediction system."""
    
    def setUp(self):
        # Create a more realistic mock ML engine
        self.mock_ml_engine = Mock()
        
        # Mock models with predict_proba methods
        mock_rf = Mock()
        mock_rf.predict_proba.return_value = np.array([[0.3, 0.7]])
        
        mock_gb = Mock()
        mock_gb.predict_proba.return_value = np.array([[0.2, 0.8]])
        
        mock_lr = Mock()
        mock_lr.predict_proba.return_value = np.array([[0.4, 0.6]])
        
        self.mock_ml_engine.models = {
            ModelType.RANDOM_FOREST: mock_rf,
            ModelType.GRADIENT_BOOSTING: mock_gb,
            ModelType.LINEAR_REGRESSION: mock_lr
        }
        
        # Mock the predict_trade_outcome method to return individual predictions
        def mock_predict(signal, conditions):
            # Return different predictions for different calls
            if not hasattr(mock_predict, 'call_count'):
                mock_predict.call_count = 0
            
            predictions = [0.7, 0.8, 0.6]
            result = predictions[mock_predict.call_count % len(predictions)]
            mock_predict.call_count += 1
            return result
        
        self.mock_ml_engine.predict_trade_outcome = mock_predict
        
        self.predictor = EnsemblePredictor(self.mock_ml_engine)
        
        # Create test data
        self.test_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.3,
            trend_strength=0.7,
            momentum=0.5,
            detected_at=datetime.now()
        )
        
        self.test_signal = AdaptiveSignal(
            pair="BTCUSD",
            signal_type="buy",
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=50000.0,
            timestamp=datetime.now(),
            regime_context=self.test_regime,
            ml_confidence=0.7
        )
        
        self.test_market_conditions = {
            'rsi': 45.0,
            'volatility': 0.02
        }
    
    def test_full_ensemble_prediction_workflow(self):
        """Test the complete ensemble prediction workflow."""
        # Make prediction
        result = self.predictor.predict_with_ensemble(
            self.test_signal, self.test_market_conditions
        )
        
        # Verify result structure
        self.assertIsInstance(result, EnsemblePrediction)
        self.assertGreaterEqual(result.prediction, 0.0)
        self.assertLessEqual(result.prediction, 1.0)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)
        self.assertGreaterEqual(result.uncertainty, 0.0)
        self.assertLessEqual(result.uncertainty, 1.0)
        
        # Update performance and make another prediction
        self.predictor.update_model_performance(
            ModelType.RANDOM_FOREST, 0.7, True, RegimeType.TRENDING_BULL
        )
        
        result2 = self.predictor.predict_with_ensemble(
            self.test_signal, self.test_market_conditions
        )
        
        # Should still work after performance update
        self.assertIsInstance(result2, EnsemblePrediction)
    
    def test_performance_tracking_over_time(self):
        """Test performance tracking over multiple predictions."""
        # Make several predictions and update performance
        for i in range(10):
            result = self.predictor.predict_with_ensemble(
                self.test_signal, self.test_market_conditions
            )
            
            # Simulate outcomes (some good, some bad)
            outcome = i % 3 == 0  # Every third prediction is correct
            
            for model_type in result.model_predictions.keys():
                self.predictor.update_model_performance(
                    model_type, result.model_predictions[model_type], outcome
                )
        
        # Check that performance summary is updated
        summary = self.predictor.get_model_performance_summary()
        
        for model_type in [ModelType.RANDOM_FOREST, ModelType.GRADIENT_BOOSTING, ModelType.LINEAR_REGRESSION]:
            self.assertIn(model_type, summary)
            self.assertGreater(summary[model_type]['prediction_count'], 0)


if __name__ == '__main__':
    unittest.main()