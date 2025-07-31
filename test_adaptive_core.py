#!/usr/bin/env python3
"""
Test script to verify the adaptive bot core data structures and interfaces.
"""
import sys
import os
from datetime import datetime, timedelta

# Add the bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

def test_enums():
    """Test that all enums are properly defined."""
    print("Testing enums...")
    
    from bot.adaptive.enums import (
        RegimeType, AdaptationType, SignalStrength, 
        OptimizationMethod, ModelType, PerformanceMetricType
    )
    
    # Test RegimeType
    assert RegimeType.TRENDING_BULL.value == "trending_bull"
    assert RegimeType.RANGING.value == "ranging"
    print("✓ RegimeType enum working")
    
    # Test AdaptationType
    assert AdaptationType.STRATEGY_WEIGHT_CHANGE.value == "strategy_weight_change"
    assert AdaptationType.PARAMETER_OPTIMIZATION.value == "parameter_optimization"
    print("✓ AdaptationType enum working")
    
    # Test SignalStrength
    assert SignalStrength.WEAK.value == 0.4
    assert SignalStrength.STRONG.value == 0.8
    print("✓ SignalStrength enum working")
    
    # Test OptimizationMethod
    assert OptimizationMethod.BAYESIAN.value == "bayesian"
    assert OptimizationMethod.GENETIC_ALGORITHM.value == "genetic_algorithm"
    print("✓ OptimizationMethod enum working")
    
    # Test ModelType
    assert ModelType.RANDOM_FOREST.value == "random_forest"
    assert ModelType.ENSEMBLE.value == "ensemble"
    print("✓ ModelType enum working")
    
    # Test PerformanceMetricType
    assert PerformanceMetricType.SHARPE_RATIO.value == "sharpe_ratio"
    assert PerformanceMetricType.MAX_DRAWDOWN.value == "max_drawdown"
    print("✓ PerformanceMetricType enum working")


def test_data_models():
    """Test that all data models can be instantiated and validated."""
    print("\nTesting data models...")
    
    from bot.adaptive.data_models import (
        MarketRegime, AdaptiveSignal, PerformanceMetrics,
        OptimizationResult, AdaptationEvent, MLModelMetadata, StrategyAllocation
    )
    from bot.adaptive.enums import (
        RegimeType, AdaptationType, SignalStrength, 
        OptimizationMethod, ModelType
    )
    
    # Test MarketRegime
    regime = MarketRegime(
        regime_type=RegimeType.TRENDING_BULL,
        confidence=0.8,
        volatility_level=0.6,
        trend_strength=0.7,
        momentum=0.5,
        detected_at=datetime.now(),
        supporting_indicators={"rsi": 65.0, "macd": 0.5}
    )
    assert regime.confidence == 0.8
    assert regime.regime_type == RegimeType.TRENDING_BULL
    print("✓ MarketRegime model working")
    
    # Test AdaptiveSignal
    signal = AdaptiveSignal(
        pair="BTCUSD",
        signal_type="buy",
        strength=SignalStrength.STRONG,
        confidence=0.85,
        price=50000.0,
        timestamp=datetime.now(),
        regime_context=regime,
        ml_confidence=0.75,
        strategy_weights={"momentum": 0.6, "mean_reversion": 0.4}
    )
    assert signal.pair == "BTCUSD"
    assert signal.strength == SignalStrength.STRONG
    print("✓ AdaptiveSignal model working")
    
    # Test PerformanceMetrics
    metrics = PerformanceMetrics(
        total_return=0.15,
        annualized_return=0.18,
        excess_return=0.08,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.8,
        max_drawdown=-0.05,
        volatility=0.12,
        downside_deviation=0.08,
        win_rate=0.65,
        profit_factor=1.8,
        avg_trade_duration=timedelta(hours=4),
        trades_count=150,
        avg_win=0.02,
        avg_loss=-0.015
    )
    assert metrics.total_return == 0.15
    assert metrics.win_rate == 0.65
    assert metrics.recovery_factor is not None  # Should be calculated in __post_init__
    print("✓ PerformanceMetrics model working")
    
    # Test OptimizationResult
    opt_result = OptimizationResult(
        strategy_name="momentum_strategy",
        optimization_method=OptimizationMethod.BAYESIAN,
        old_parameters={"rsi_period": 14, "threshold": 70},
        new_parameters={"rsi_period": 16, "threshold": 75},
        performance_improvement=0.05,
        confidence_score=0.8,
        validation_score=0.75
    )
    changes = opt_result.get_parameter_changes()
    assert changes["rsi_period"] == 2
    assert changes["threshold"] == 5
    print("✓ OptimizationResult model working")
    
    # Test AdaptationEvent
    event = AdaptationEvent(
        event_id="adapt_001",
        event_type=AdaptationType.PARAMETER_OPTIMIZATION,
        trigger_reason="Performance degradation detected",
        changes_made={"rsi_threshold": 75},
        expected_impact=0.03
    )
    assert event.event_id == "adapt_001"
    assert event.rollback_available == True
    print("✓ AdaptationEvent model working")
    
    # Test MLModelMetadata
    model_meta = MLModelMetadata(
        model_id="rf_001",
        model_type=ModelType.RANDOM_FOREST,
        version="1.0",
        trained_at=datetime.now(),
        training_data_size=10000,
        training_period=timedelta(days=30),
        training_accuracy=0.85,
        validation_accuracy=0.82
    )
    assert model_meta.model_type == ModelType.RANDOM_FOREST
    assert model_meta.training_accuracy == 0.85
    print("✓ MLModelMetadata model working")
    
    # Test StrategyAllocation
    allocation = StrategyAllocation(
        strategy_name="momentum_strategy",
        allocation_percentage=0.3,
        current_weight=0.35,
        base_weight=0.3,
        recent_performance=0.12,
        performance_trend=0.02,
        confidence_level=0.8
    )
    assert allocation.allocation_percentage == 0.3
    assert allocation.is_active == True
    print("✓ StrategyAllocation model working")


def test_interfaces():
    """Test that all interfaces are properly defined."""
    print("\nTesting interfaces...")
    
    from bot.adaptive.interfaces import (
        MarketRegimeDetectorInterface,
        AdaptiveStrategyEngineInterface,
        MLEngineInterface,
        ParameterOptimizerInterface,
        PerformanceAnalyzerInterface,
        AdaptationControllerInterface,
        DataManagerInterface,
        RiskManagerInterface,
        MonitoringInterface
    )
    
    # Check that interfaces have the expected abstract methods
    assert hasattr(MarketRegimeDetectorInterface, 'detect_regime')
    assert hasattr(AdaptiveStrategyEngineInterface, 'execute_adaptive_signal')
    assert hasattr(MLEngineInterface, 'predict_trade_outcome')
    assert hasattr(ParameterOptimizerInterface, 'optimize_parameters')
    assert hasattr(PerformanceAnalyzerInterface, 'analyze_strategy_performance')
    assert hasattr(AdaptationControllerInterface, 'should_adapt')
    assert hasattr(DataManagerInterface, 'store_regime_data')
    assert hasattr(RiskManagerInterface, 'validate_adaptive_signal')
    assert hasattr(MonitoringInterface, 'monitor_system_health')
    
    print("✓ All interfaces properly defined")


def test_imports():
    """Test that all components can be imported from the main module."""
    print("\nTesting imports...")
    
    from bot.adaptive import (
        # Enums
        RegimeType, AdaptationType, SignalStrength,
        OptimizationMethod, ModelType, PerformanceMetricType,
        
        # Data Models
        MarketRegime, AdaptiveSignal, PerformanceMetrics,
        OptimizationResult, AdaptationEvent, MLModelMetadata, StrategyAllocation,
        
        # Interfaces
        MarketRegimeDetectorInterface, AdaptiveStrategyEngineInterface,
        MLEngineInterface, ParameterOptimizerInterface,
        PerformanceAnalyzerInterface, AdaptationControllerInterface,
        DataManagerInterface, RiskManagerInterface, MonitoringInterface
    )
    
    print("✓ All components can be imported from main module")


def main():
    """Run all tests."""
    print("Testing Adaptive Bot Core Components")
    print("=" * 40)
    
    try:
        test_enums()
        test_data_models()
        test_interfaces()
        test_imports()
        
        print("\n" + "=" * 40)
        print("✅ All tests passed! Core data structures and interfaces are working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())