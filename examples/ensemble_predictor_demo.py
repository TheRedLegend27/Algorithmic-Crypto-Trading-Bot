"""
Demo script for the Enhanced Ensemble Prediction System.

This script demonstrates the key features of the ensemble predictor:
- Multiple ensemble methods
- Confidence scoring and uncertainty quantification
- Model weight optimization based on performance
- Fallback mechanisms when models fail
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock

from bot.adaptive.ensemble_predictor import EnsemblePredictor, EnsemblePrediction
from bot.adaptive.data_models import AdaptiveSignal, MarketRegime
from bot.adaptive.enums import ModelType, RegimeType, SignalStrength

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mock_ml_engine():
    """Create a mock ML engine with different model behaviors."""
    mock_engine = Mock()
    
    # Create mock models with different prediction patterns
    models = {}
    
    # Random Forest: Generally optimistic
    rf_model = Mock()
    rf_model.predict_proba.return_value = np.array([[0.3, 0.7]])
    models[ModelType.RANDOM_FOREST] = rf_model
    
    # Gradient Boosting: More conservative
    gb_model = Mock()
    gb_model.predict_proba.return_value = np.array([[0.4, 0.6]])
    models[ModelType.GRADIENT_BOOSTING] = gb_model
    
    # Linear Regression: Moderate
    lr_model = Mock()
    lr_model.predict_proba.return_value = np.array([[0.35, 0.65]])
    models[ModelType.LINEAR_REGRESSION] = lr_model
    
    mock_engine.models = models
    
    # Mock the predict_trade_outcome method to simulate different model behaviors
    prediction_counter = 0
    def mock_predict(signal, conditions):
        nonlocal prediction_counter
        # Simulate different models giving different predictions
        predictions = {
            ModelType.RANDOM_FOREST: 0.75,
            ModelType.GRADIENT_BOOSTING: 0.65,
            ModelType.LINEAR_REGRESSION: 0.70
        }
        
        # Add some randomness to simulate real model behavior
        model_types = list(predictions.keys())
        selected_model = model_types[prediction_counter % len(model_types)]
        prediction_counter += 1
        
        base_pred = predictions[selected_model]
        # Add small random variation
        variation = np.random.normal(0, 0.05)
        return max(0.0, min(1.0, base_pred + variation))
    
    mock_engine.predict_trade_outcome = mock_predict
    
    return mock_engine


def create_test_signal(signal_type="buy", regime_type=RegimeType.TRENDING_BULL):
    """Create a test adaptive signal."""
    regime = MarketRegime(
        regime_type=regime_type,
        confidence=0.8,
        volatility_level=0.3,
        trend_strength=0.7,
        momentum=0.5,
        detected_at=datetime.now()
    )
    
    return AdaptiveSignal(
        pair="BTCUSD",
        signal_type=signal_type,
        strength=SignalStrength.STRONG,
        confidence=0.8,
        price=50000.0,
        timestamp=datetime.now(),
        regime_context=regime,
        ml_confidence=0.7
    )


def demo_basic_ensemble_prediction():
    """Demonstrate basic ensemble prediction functionality."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Ensemble Prediction")
    print("="*60)
    
    # Create ensemble predictor
    mock_engine = create_mock_ml_engine()
    predictor = EnsemblePredictor(mock_engine)
    
    # Create test signal and market conditions
    signal = create_test_signal()
    market_conditions = {
        'rsi': 45.0,
        'volatility': 0.02,
        'volume_ratio': 1.2
    }
    
    # Make ensemble prediction
    result = predictor.predict_with_ensemble(signal, market_conditions)
    
    print(f"Signal: {signal.signal_type.upper()} {signal.pair}")
    print(f"Market Regime: {signal.regime_context.regime_type.value}")
    print(f"Signal Confidence: {signal.confidence:.3f}")
    print()
    print("ENSEMBLE PREDICTION RESULTS:")
    print(f"  Prediction: {result.prediction:.3f}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Uncertainty: {result.uncertainty:.3f}")
    print(f"  Consensus Level: {result.consensus_level:.3f}")
    print(f"  Prediction Quality: {result.prediction_quality:.3f}")
    print(f"  Fallback Used: {result.fallback_used}")
    print(f"  Ensemble Method: {result.ensemble_method}")
    
    if result.model_predictions:
        print("\nINDIVIDUAL MODEL PREDICTIONS:")
        for model_type, prediction in result.model_predictions.items():
            weight = result.model_weights.get(model_type, 0.0)
            print(f"  {model_type.value}: {prediction:.3f} (weight: {weight:.3f})")
    
    # Calculate prediction interval
    lower, upper = result.get_prediction_interval(0.95)
    print(f"\n95% Prediction Interval: [{lower:.3f}, {upper:.3f}]")


def demo_ensemble_methods():
    """Demonstrate different ensemble methods."""
    print("\n" + "="*60)
    print("DEMO 2: Different Ensemble Methods")
    print("="*60)
    
    mock_engine = create_mock_ml_engine()
    predictor = EnsemblePredictor(mock_engine)
    
    signal = create_test_signal()
    market_conditions = {'rsi': 55.0, 'volatility': 0.025}
    
    # Test different ensemble methods
    methods = ['weighted_average', 'confidence_weighted', 'stacking', 'bayesian_model_averaging']
    
    for method in methods:
        result = predictor.predict_with_ensemble(signal, market_conditions, method)
        print(f"{method.upper()}:")
        print(f"  Prediction: {result.prediction:.3f}")
        print(f"  Confidence: {result.confidence:.3f}")
        print(f"  Uncertainty: {result.uncertainty:.3f}")
        print()


def demo_performance_tracking():
    """Demonstrate model performance tracking and dynamic weighting."""
    print("\n" + "="*60)
    print("DEMO 3: Performance Tracking and Dynamic Weighting")
    print("="*60)
    
    mock_engine = create_mock_ml_engine()
    predictor = EnsemblePredictor(mock_engine)
    
    signal = create_test_signal()
    market_conditions = {'rsi': 50.0, 'volatility': 0.02}
    
    print("Initial model performance (all models start equal):")
    summary = predictor.get_model_performance_summary()
    for model_type, stats in summary.items():
        if model_type != ModelType.ENSEMBLE:
            print(f"  {model_type.value}: accuracy={stats['recent_accuracy']:.3f}, weight={stats['dynamic_weight']:.3f}")
    
    print("\nSimulating trading outcomes...")
    
    # Simulate different performance for different models
    np.random.seed(42)  # For reproducible results
    
    for i in range(50):
        result = predictor.predict_with_ensemble(signal, market_conditions)
        
        # Simulate outcomes with different success rates for different models
        for model_type, prediction in result.model_predictions.items():
            if model_type == ModelType.RANDOM_FOREST:
                # Random Forest performs well
                outcome = np.random.random() < 0.8  # 80% success rate
            elif model_type == ModelType.GRADIENT_BOOSTING:
                # Gradient Boosting performs moderately
                outcome = np.random.random() < 0.6  # 60% success rate
            else:
                # Linear Regression performs poorly
                outcome = np.random.random() < 0.4  # 40% success rate
            
            predictor.update_model_performance(
                model_type, prediction, outcome, signal.regime_context.regime_type
            )
    
    print("\nAfter 50 simulated trades:")
    summary = predictor.get_model_performance_summary()
    for model_type, stats in summary.items():
        if model_type != ModelType.ENSEMBLE:
            print(f"  {model_type.value}:")
            print(f"    Recent Accuracy: {stats['recent_accuracy']:.3f}")
            print(f"    Long-term Accuracy: {stats['long_term_accuracy']:.3f}")
            print(f"    Dynamic Weight: {stats['dynamic_weight']:.3f}")
            print(f"    Performance Trend: {stats['performance_trend']:+.3f}")
            print(f"    Predictions Made: {stats['prediction_count']}")
            print()
    
    # Make a new prediction to see updated weights
    print("New prediction with updated weights:")
    result = predictor.predict_with_ensemble(signal, market_conditions)
    print(f"  Ensemble Prediction: {result.prediction:.3f}")
    print(f"  Confidence: {result.confidence:.3f}")
    print("  Model Weights:")
    for model_type, weight in result.model_weights.items():
        print(f"    {model_type.value}: {weight:.3f}")


def demo_fallback_mechanisms():
    """Demonstrate fallback mechanisms when ensemble fails."""
    print("\n" + "="*60)
    print("DEMO 4: Fallback Mechanisms")
    print("="*60)
    
    # Create a mock engine with insufficient models
    mock_engine = Mock()
    mock_engine.models = {ModelType.RANDOM_FOREST: Mock()}  # Only one model
    mock_engine.predict_trade_outcome = lambda s, c: 0.6
    
    predictor = EnsemblePredictor(mock_engine)
    
    signal = create_test_signal()
    market_conditions = {'rsi': 30.0, 'volatility': 0.05}  # Oversold, high volatility
    
    print("Testing with insufficient models (< 2):")
    result = predictor.predict_with_ensemble(signal, market_conditions)
    
    print(f"  Fallback Used: {result.fallback_used}")
    print(f"  Fallback Reason: {result.fallback_reason}")
    print(f"  Prediction: {result.prediction:.3f}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Ensemble Method: {result.ensemble_method}")
    
    # Test different market conditions for different fallback strategies
    print("\nTesting fallback with different market conditions:")
    
    test_conditions = [
        ({'rsi': 75.0, 'volatility': 0.01}, "Overbought, low volatility"),
        ({'rsi': 25.0, 'volatility': 0.01}, "Oversold, low volatility"),
        ({'rsi': 50.0, 'volatility': 0.08}, "Neutral RSI, high volatility"),
    ]
    
    for conditions, description in test_conditions:
        result = predictor.predict_with_ensemble(signal, conditions)
        print(f"  {description}: {result.prediction:.3f}")


def demo_regime_specific_performance():
    """Demonstrate regime-specific performance tracking."""
    print("\n" + "="*60)
    print("DEMO 5: Regime-Specific Performance")
    print("="*60)
    
    mock_engine = create_mock_ml_engine()
    predictor = EnsemblePredictor(mock_engine)
    
    # Test different market regimes
    regimes = [
        RegimeType.TRENDING_BULL,
        RegimeType.TRENDING_BEAR,
        RegimeType.RANGING,
        RegimeType.HIGH_VOLATILITY
    ]
    
    print("Simulating performance in different market regimes...")
    
    for regime in regimes:
        signal = create_test_signal(regime_type=regime)
        market_conditions = {'rsi': 50.0, 'volatility': 0.02}
        
        # Simulate 20 trades in this regime
        for _ in range(20):
            result = predictor.predict_with_ensemble(signal, market_conditions)
            
            # Simulate regime-specific model performance
            for model_type, prediction in result.model_predictions.items():
                if regime == RegimeType.TRENDING_BULL:
                    # Random Forest does well in bull markets
                    success_rate = 0.8 if model_type == ModelType.RANDOM_FOREST else 0.5
                elif regime == RegimeType.RANGING:
                    # Linear Regression does well in ranging markets
                    success_rate = 0.8 if model_type == ModelType.LINEAR_REGRESSION else 0.5
                else:
                    # Default performance
                    success_rate = 0.6
                
                outcome = np.random.random() < success_rate
                predictor.update_model_performance(model_type, prediction, outcome, regime)
    
    print("\nRegime-specific performance summary:")
    summary = predictor.get_model_performance_summary()
    
    for model_type, stats in summary.items():
        if model_type != ModelType.ENSEMBLE and stats['regime_performance']:
            print(f"\n{model_type.value}:")
            for regime, performance in stats['regime_performance'].items():
                print(f"  {regime.value}: {performance:.3f}")


def main():
    """Run all ensemble predictor demos."""
    print("Enhanced Ensemble Prediction System Demo")
    print("========================================")
    
    try:
        demo_basic_ensemble_prediction()
        demo_ensemble_methods()
        demo_performance_tracking()
        demo_fallback_mechanisms()
        demo_regime_specific_performance()
        
        print("\n" + "="*60)
        print("DEMO COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nKey Features Demonstrated:")
        print("✓ Multiple ensemble methods (weighted average, confidence-weighted, etc.)")
        print("✓ Confidence scoring and uncertainty quantification")
        print("✓ Dynamic model weight optimization based on performance")
        print("✓ Comprehensive fallback mechanisms")
        print("✓ Regime-specific performance tracking")
        print("✓ Prediction intervals and quality metrics")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {str(e)}")
        raise


if __name__ == "__main__":
    main()