"""
Unit tests for the Adaptive Strategy Engine.

Tests cover:
- Strategy selection and weighting system
- Dynamic weight calculation based on performance
- Strategy switching logic with hysteresis
- Ensemble signal generation from multiple strategies
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from collections import deque
import pandas as pd
import numpy as np

from bot.adaptive.adaptive_strategy_engine import AdaptiveStrategyEngine
from bot.adaptive.data_models import MarketRegime, PerformanceMetrics, StrategyAllocation
from bot.adaptive.enums import RegimeType, SignalStrength
from bot.strategy import TradingSignal, SignalType, BaseStrategy


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""
    
    def __init__(self, name: str, signal_type: SignalType = SignalType.HOLD, 
                 confidence: float = 0.5):
        super().__init__(name)
        self.signal_type = signal_type
        self.confidence = confidence
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        return TradingSignal(
            action=self.signal_type,
            confidence=self.confidence,
            strategy=self.name,
            timestamp=datetime.now(),
            price=100.0,
            reasoning=f"Mock signal from {self.name}"
        )


class TestAdaptiveStrategyEngine(unittest.TestCase):
    """Test cases for AdaptiveStrategyEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'hysteresis_threshold': 0.15,
            'min_switch_interval_minutes': 30,
            'min_strategies_for_ensemble': 2,
            'confidence_decay_factor': 0.95,
            'min_performance_threshold': -0.1,
            'disable_threshold': -0.2,
            'reenable_threshold': 0.05
        }
        
        # Mock the strategy imports to avoid dependency issues
        with patch.multiple(
            'bot.adaptive.adaptive_strategy_engine',
            EnhancedMomentumStrategy=Mock,
            PriceActionStrategy=Mock,
            MultiTimeframeStrategy=Mock,
            VolatilityAdjustedStrategy=Mock
        ):
            self.engine = AdaptiveStrategyEngine(self.config)
        
        # Clear default strategies and add test strategies
        self.engine.strategies.clear()
        self.engine.strategy_allocations.clear()
        
        # Add test strategies
        self.strategy1 = MockStrategy("test_strategy_1", SignalType.BUY, 0.7)
        self.strategy2 = MockStrategy("test_strategy_2", SignalType.SELL, 0.6)
        self.strategy3 = MockStrategy("test_strategy_3", SignalType.HOLD, 0.3)
        
        self.engine.add_strategy("test_strategy_1", self.strategy1, {'base_weight': 0.4})
        self.engine.add_strategy("test_strategy_2", self.strategy2, {'base_weight': 0.3})
        self.engine.add_strategy("test_strategy_3", self.strategy3, {'base_weight': 0.3})
    
    def test_initialization(self):
        """Test engine initialization."""
        self.assertIsInstance(self.engine.strategies, dict)
        self.assertIsInstance(self.engine.strategy_allocations, dict)
        self.assertEqual(self.engine.hysteresis_threshold, 0.15)
        self.assertEqual(self.engine.min_strategies_for_ensemble, 2)
    
    def test_add_strategy(self):
        """Test adding a new strategy."""
        new_strategy = MockStrategy("new_strategy", SignalType.BUY, 0.8)
        self.engine.add_strategy("new_strategy", new_strategy, {'base_weight': 0.2})
        
        self.assertIn("new_strategy", self.engine.strategies)
        self.assertIn("new_strategy", self.engine.strategy_allocations)
        
        allocation = self.engine.strategy_allocations["new_strategy"]
        self.assertEqual(allocation.strategy_name, "new_strategy")
        self.assertEqual(allocation.base_weight, 0.2)
        self.assertTrue(allocation.is_active)
    
    def test_remove_strategy(self):
        """Test removing a strategy."""
        self.assertIn("test_strategy_1", self.engine.strategies)
        
        self.engine.remove_strategy("test_strategy_1")
        
        self.assertNotIn("test_strategy_1", self.engine.strategies)
        self.assertNotIn("test_strategy_1", self.engine.strategy_allocations)
    
    def test_strategy_allocation_rebalancing(self):
        """Test that strategy allocations are properly rebalanced."""
        # Get initial allocations
        allocations = self.engine.get_strategy_allocation()
        total_allocation = sum(alloc.allocation_percentage for alloc in allocations.values())
        
        # Should sum to approximately 1.0
        self.assertAlmostEqual(total_allocation, 1.0, places=2)
    
    def test_select_optimal_strategy_basic(self):
        """Test basic strategy selection."""
        regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.5,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now()
        )
        
        selected_strategy = self.engine.select_optimal_strategy("BTCUSD", regime)
        
        self.assertIsNotNone(selected_strategy)
        self.assertIn(selected_strategy, self.engine.strategies)
    
    def test_select_optimal_strategy_with_performance(self):
        """Test strategy selection with performance data."""
        # Update strategy performance
        performance_data = {
            "test_strategy_1": PerformanceMetrics(
                total_return=0.15,
                annualized_return=0.20,
                excess_return=0.10,
                sharpe_ratio=1.5,
                sortino_ratio=1.8,
                calmar_ratio=1.2,
                max_drawdown=0.05,
                volatility=0.15,
                downside_deviation=0.10,
                win_rate=0.65,
                profit_factor=1.8,
                avg_trade_duration=timedelta(hours=4),
                trades_count=50,
                avg_win=0.03,
                avg_loss=-0.02
            ),
            "test_strategy_2": PerformanceMetrics(
                total_return=0.05,
                annualized_return=0.08,
                excess_return=0.02,
                sharpe_ratio=0.8,
                sortino_ratio=0.9,
                calmar_ratio=0.6,
                max_drawdown=0.08,
                volatility=0.20,
                downside_deviation=0.15,
                win_rate=0.55,
                profit_factor=1.2,
                avg_trade_duration=timedelta(hours=6),
                trades_count=30,
                avg_win=0.025,
                avg_loss=-0.025
            )
        }
        
        self.engine.update_strategy_weights(performance_data)
        
        regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.5,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now()
        )
        
        selected_strategy = self.engine.select_optimal_strategy("BTCUSD", regime)
        
        # Strategy 1 should be selected due to better performance
        self.assertEqual(selected_strategy, "test_strategy_1")
    
    def test_hysteresis_prevents_rapid_switching(self):
        """Test that hysteresis prevents rapid strategy switching."""
        regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.5,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now()
        )
        
        # First selection
        first_strategy = self.engine.select_optimal_strategy("BTCUSD", regime)
        
        # Slightly modify strategy weights (not enough to overcome hysteresis)
        for allocation in self.engine.strategy_allocations.values():
            allocation.current_weight *= 1.05  # Small increase
        
        # Second selection should be the same due to hysteresis
        second_strategy = self.engine.select_optimal_strategy("BTCUSD", regime)
        
        self.assertEqual(first_strategy, second_strategy)
    
    def test_execute_adaptive_signal_single_strategy(self):
        """Test adaptive signal execution with single active strategy."""
        # Disable two strategies to test single strategy case
        self.engine.strategy_allocations["test_strategy_2"].is_active = False
        self.engine.strategy_allocations["test_strategy_3"].is_active = False
        
        market_data = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101],
            'close': [100.5, 101.5, 102.5],
            'volume': [1000, 1100, 1200]
        })
        
        signal = self.engine.execute_adaptive_signal("BTCUSD", market_data)
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.pair, "BTCUSD")
        self.assertEqual(signal.signal_type, "buy")  # From strategy1
        self.assertIn("test_strategy_1", signal.strategy_weights)
    
    def test_execute_adaptive_signal_ensemble(self):
        """Test adaptive signal execution with ensemble of strategies."""
        market_data = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101],
            'close': [100.5, 101.5, 102.5],
            'volume': [1000, 1100, 1200]
        })
        
        signal = self.engine.execute_adaptive_signal("BTCUSD", market_data)
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.pair, "BTCUSD")
        # Should have multiple strategies in weights (ensemble)
        self.assertGreater(len(signal.strategy_weights), 1)
    
    def test_update_strategy_weights(self):
        """Test strategy weight updates based on performance."""
        performance_data = {
            "test_strategy_1": PerformanceMetrics(
                total_return=0.20,
                annualized_return=0.25,
                excess_return=0.15,
                sharpe_ratio=2.0,
                sortino_ratio=2.2,
                calmar_ratio=1.5,
                max_drawdown=0.03,
                volatility=0.12,
                downside_deviation=0.08,
                win_rate=0.70,
                profit_factor=2.5,
                avg_trade_duration=timedelta(hours=3),
                trades_count=60,
                avg_win=0.035,
                avg_loss=-0.015
            ),
            "test_strategy_2": PerformanceMetrics(
                total_return=-0.05,
                annualized_return=-0.08,
                excess_return=-0.12,
                sharpe_ratio=-0.5,
                sortino_ratio=-0.6,
                calmar_ratio=-0.3,
                max_drawdown=0.15,
                volatility=0.25,
                downside_deviation=0.20,
                win_rate=0.40,
                profit_factor=0.8,
                avg_trade_duration=timedelta(hours=8),
                trades_count=25,
                avg_win=0.02,
                avg_loss=-0.03
            )
        }
        
        # Store initial weights
        initial_weight_1 = self.engine.strategy_allocations["test_strategy_1"].current_weight
        initial_weight_2 = self.engine.strategy_allocations["test_strategy_2"].current_weight
        
        self.engine.update_strategy_weights(performance_data)
        
        # Strategy 1 should have increased weight due to good performance
        new_weight_1 = self.engine.strategy_allocations["test_strategy_1"].current_weight
        self.assertGreater(new_weight_1, initial_weight_1)
        
        # Strategy 2 should have decreased weight due to poor performance
        new_weight_2 = self.engine.strategy_allocations["test_strategy_2"].current_weight
        self.assertLess(new_weight_2, initial_weight_2)
    
    def test_strategy_disabling_and_reenabling(self):
        """Test automatic strategy disabling and re-enabling."""
        # Test disabling due to poor performance
        poor_performance = {
            "test_strategy_1": PerformanceMetrics(
                total_return=-0.25,  # Below disable threshold
                annualized_return=-0.30,
                excess_return=-0.35,
                sharpe_ratio=-1.0,
                sortino_ratio=-1.2,
                calmar_ratio=-0.8,
                max_drawdown=0.30,
                volatility=0.35,
                downside_deviation=0.30,
                win_rate=0.30,
                profit_factor=0.5,
                avg_trade_duration=timedelta(hours=10),
                trades_count=20,
                avg_win=0.015,
                avg_loss=-0.04
            )
        }
        
        self.engine.update_strategy_weights(poor_performance)
        
        # Strategy should be disabled
        self.assertFalse(self.engine.strategy_allocations["test_strategy_1"].is_active)
        
        # Test re-enabling due to improved performance
        good_performance = {
            "test_strategy_1": PerformanceMetrics(
                total_return=0.08,  # Above re-enable threshold
                annualized_return=0.12,
                excess_return=0.05,
                sharpe_ratio=1.2,
                sortino_ratio=1.4,
                calmar_ratio=0.8,
                max_drawdown=0.05,
                volatility=0.15,
                downside_deviation=0.10,
                win_rate=0.60,
                profit_factor=1.5,
                avg_trade_duration=timedelta(hours=4),
                trades_count=40,
                avg_win=0.025,
                avg_loss=-0.02
            )
        }
        
        self.engine.update_strategy_weights(good_performance)
        
        # Strategy should be re-enabled
        self.assertTrue(self.engine.strategy_allocations["test_strategy_1"].is_active)
    
    def test_performance_trend_calculation(self):
        """Test performance trend calculation."""
        strategy_name = "test_strategy_1"
        
        # Add some performance history
        history = self.engine.strategy_performance_history[strategy_name]
        for i in range(10):
            history.append({
                'timestamp': datetime.now() - timedelta(hours=i),
                'return': 0.01 * i,  # Increasing returns
                'sharpe': 1.0 + 0.1 * i,
                'drawdown': 0.05 - 0.001 * i
            })
        
        trend = self.engine._calculate_performance_trend(strategy_name)
        
        # Should be positive due to increasing returns
        self.assertGreater(trend, 0)
    
    def test_strategy_confidence_calculation(self):
        """Test strategy confidence calculation."""
        good_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.20,
            excess_return=0.10,
            sharpe_ratio=1.8,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            max_drawdown=0.03,
            volatility=0.12,
            downside_deviation=0.08,
            win_rate=0.70,
            profit_factor=2.0,
            avg_trade_duration=timedelta(hours=3),
            trades_count=50,
            avg_win=0.03,
            avg_loss=-0.02
        )
        
        confidence = self.engine._calculate_strategy_confidence("test_strategy_1", good_metrics)
        
        # Should be high confidence due to good metrics
        self.assertGreater(confidence, 0.7)
        self.assertLessEqual(confidence, 1.0)
    
    def test_dynamic_weight_calculation(self):
        """Test dynamic weight calculation."""
        excellent_metrics = PerformanceMetrics(
            total_return=0.25,  # Excellent return
            annualized_return=0.30,
            excess_return=0.20,
            sharpe_ratio=2.5,  # Excellent Sharpe
            sortino_ratio=2.8,
            calmar_ratio=2.0,
            max_drawdown=0.02,
            volatility=0.10,
            downside_deviation=0.06,
            win_rate=0.75,
            profit_factor=3.0,
            avg_trade_duration=timedelta(hours=2),
            trades_count=80,
            avg_win=0.04,
            avg_loss=-0.015
        )
        
        # Set positive trend
        self.engine.strategy_allocations["test_strategy_1"].performance_trend = 0.5
        
        new_weight = self.engine._calculate_dynamic_weight("test_strategy_1", excellent_metrics)
        base_weight = self.engine.strategy_allocations["test_strategy_1"].base_weight
        
        # New weight should be higher than base weight
        self.assertGreater(new_weight, base_weight)
    
    def test_get_strategy_allocation(self):
        """Test getting strategy allocation."""
        allocations = self.engine.get_strategy_allocation()
        
        self.assertIsInstance(allocations, dict)
        self.assertEqual(len(allocations), 3)  # Three test strategies
        
        for name, allocation in allocations.items():
            self.assertIsInstance(allocation, StrategyAllocation)
            self.assertEqual(allocation.strategy_name, name)
    
    def test_get_strategy_performance_summary(self):
        """Test getting strategy performance summary."""
        summary = self.engine.get_strategy_performance_summary()
        
        self.assertIn('total_strategies', summary)
        self.assertIn('active_strategies', summary)
        self.assertIn('strategy_details', summary)
        
        self.assertEqual(summary['total_strategies'], 3)
        self.assertEqual(len(summary['strategy_details']), 3)
    
    def test_reset_strategy_weights(self):
        """Test resetting strategy weights."""
        # Modify weights
        for allocation in self.engine.strategy_allocations.values():
            allocation.current_weight *= 1.5
            allocation.is_active = False
        
        self.engine.reset_strategy_weights()
        
        # Weights should be reset to base values
        for allocation in self.engine.strategy_allocations.values():
            self.assertEqual(allocation.current_weight, allocation.base_weight)
            self.assertTrue(allocation.is_active)
    
    def test_ensemble_signal_history(self):
        """Test getting ensemble signal history."""
        # Execute some signals to create history
        market_data = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101],
            'close': [100.5, 101.5, 102.5],
            'volume': [1000, 1100, 1200]
        })
        
        self.engine.execute_adaptive_signal("BTCUSD", market_data)
        self.engine.execute_adaptive_signal("ETHUSD", market_data)
        
        history = self.engine.get_ensemble_signal_history(hours_back=1)
        
        self.assertIsInstance(history, list)
        # Should have some signals in history
        self.assertGreater(len(history), 0)
    
    def test_empty_market_data_handling(self):
        """Test handling of empty market data."""
        empty_data = pd.DataFrame()
        
        signal = self.engine.execute_adaptive_signal("BTCUSD", empty_data)
        
        self.assertIsNone(signal)
    
    def test_no_active_strategies(self):
        """Test behavior when no strategies are active."""
        # Disable all strategies
        for allocation in self.engine.strategy_allocations.values():
            allocation.is_active = False
        
        regime = MarketRegime(
            regime_type=RegimeType.UNCERTAIN,
            confidence=0.5,
            volatility_level=0.5,
            trend_strength=0.0,
            momentum=0.0,
            detected_at=datetime.now()
        )
        
        selected_strategy = self.engine.select_optimal_strategy("BTCUSD", regime)
        
        # Should return first available strategy as fallback
        self.assertIsNotNone(selected_strategy)
    
    def test_real_time_performance_metrics(self):
        """Test getting real-time performance metrics for a strategy."""
        strategy_name = "test_strategy_1"
        
        # Add some performance history
        history = self.engine.strategy_performance_history[strategy_name]
        for i in range(5):
            history.append({
                'timestamp': datetime.now() - timedelta(hours=i),
                'return': 0.02 * (i + 1),
                'sharpe': 1.0 + 0.1 * i,
                'drawdown': 0.05 - 0.001 * i,
                'win_rate': 0.6 + 0.01 * i
            })
        
        metrics = self.engine.get_real_time_performance_metrics(strategy_name)
        
        self.assertIsInstance(metrics, dict)
        self.assertEqual(metrics['strategy_name'], strategy_name)
        self.assertIn('is_active', metrics)
        self.assertIn('current_weight', metrics)
        self.assertIn('recent_performance', metrics)
        self.assertIn('performance_trend', metrics)
        self.assertIn('confidence_level', metrics)
        self.assertIn('performance_history_length', metrics)
        self.assertEqual(metrics['performance_history_length'], 5)
    
    def test_monitor_strategy_performance_degradation(self):
        """Test monitoring strategies for performance degradation."""
        # Set up different performance scenarios
        self.engine.strategy_allocations["test_strategy_1"].recent_performance = 0.15  # Good
        self.engine.strategy_allocations["test_strategy_2"].recent_performance = -0.05  # Poor
        self.engine.strategy_allocations["test_strategy_3"].is_active = False  # Disabled
        
        report = self.engine.monitor_strategy_performance_degradation(24)
        
        self.assertIsInstance(report, dict)
        self.assertIn('timestamp', report)
        self.assertIn('strategies_analyzed', report)
        self.assertIn('degrading_strategies', report)
        self.assertIn('stable_strategies', report)
        self.assertIn('improving_strategies', report)
        self.assertIn('disabled_strategies', report)
        
        self.assertEqual(report['strategies_analyzed'], 3)
        self.assertEqual(len(report['disabled_strategies']), 1)
        self.assertEqual(report['disabled_strategies'][0]['strategy_name'], "test_strategy_3")
    
    def test_adjust_strategy_allocations_based_on_performance(self):
        """Test adjusting strategy allocations based on performance."""
        # Set up performance scenarios
        self.engine.strategy_allocations["test_strategy_1"].recent_performance = 0.20  # Excellent
        self.engine.strategy_allocations["test_strategy_2"].recent_performance = -0.15  # Poor
        
        initial_weight_1 = self.engine.strategy_allocations["test_strategy_1"].current_weight
        initial_weight_2 = self.engine.strategy_allocations["test_strategy_2"].current_weight
        
        report = self.engine.adjust_strategy_allocations_based_on_performance(24)
        
        self.assertIsInstance(report, dict)
        self.assertIn('timestamp', report)
        self.assertIn('adjustments_made', report)
        self.assertIn('strategies_disabled', report)
        self.assertIn('strategies_enabled', report)
        
        # Check that weights were adjusted
        new_weight_1 = self.engine.strategy_allocations["test_strategy_1"].current_weight
        new_weight_2 = self.engine.strategy_allocations["test_strategy_2"].current_weight
        
        # Strategy 1 should have increased weight due to good performance
        self.assertGreaterEqual(new_weight_1, initial_weight_1)
        
        # Strategy 2 might be disabled or have reduced weight due to poor performance
        if self.engine.strategy_allocations["test_strategy_2"].is_active:
            self.assertLessEqual(new_weight_2, initial_weight_2)
    
    def test_get_strategy_performance_comparison(self):
        """Test getting strategy performance comparison."""
        # Add performance history for comparison
        for strategy_name in ["test_strategy_1", "test_strategy_2", "test_strategy_3"]:
            history = self.engine.strategy_performance_history[strategy_name]
            base_return = 0.05 if strategy_name == "test_strategy_1" else -0.02
            
            for i in range(10):
                history.append({
                    'timestamp': datetime.now() - timedelta(hours=i),
                    'return': base_return + 0.01 * np.random.randn(),
                    'sharpe': 1.0 + 0.1 * np.random.randn(),
                    'drawdown': 0.05 + 0.01 * np.random.randn(),
                    'win_rate': 0.6 + 0.05 * np.random.randn()
                })
        
        comparison = self.engine.get_strategy_performance_comparison(24)
        
        self.assertIsInstance(comparison, dict)
        self.assertIn('timestamp', comparison)
        self.assertIn('strategy_rankings', comparison)
        self.assertIn('performance_summary', comparison)
        
        self.assertEqual(len(comparison['strategy_rankings']), 3)
        
        # Check that rankings are sorted by risk-adjusted score
        rankings = comparison['strategy_rankings']
        for i in range(len(rankings) - 1):
            self.assertGreaterEqual(
                rankings[i]['risk_adjusted_score'],
                rankings[i + 1]['risk_adjusted_score']
            )
        
        # Check performance summary
        summary = comparison['performance_summary']
        self.assertIn('best_performer', summary)
        self.assertIn('worst_performer', summary)
    
    def test_create_performance_alert(self):
        """Test creating performance alerts."""
        strategy_name = "test_strategy_1"
        alert_type = "degradation"
        alert_data = {
            'reason': 'consistent_decline',
            'severity': 0.15,
            'metrics': {
                'return': -0.08,
                'sharpe': -0.5,
                'drawdown': 0.12,
                'win_rate': 0.35
            }
        }
        
        alert = self.engine.create_performance_alert(strategy_name, alert_type, alert_data)
        
        self.assertIsInstance(alert, dict)
        self.assertIn('alert_id', alert)
        self.assertIn('timestamp', alert)
        self.assertEqual(alert['strategy_name'], strategy_name)
        self.assertEqual(alert['alert_type'], alert_type)
        self.assertIn('message', alert)
        self.assertTrue(alert['requires_action'])
        
        # Check that alert was stored
        alerts = self.engine.get_performance_alerts(1)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['alert_id'], alert['alert_id'])
    
    def test_get_performance_alerts(self):
        """Test getting performance alerts with filtering."""
        # Create multiple alerts
        self.engine.create_performance_alert("test_strategy_1", "degradation", {'severity': 0.1})
        self.engine.create_performance_alert("test_strategy_2", "improvement", {'magnitude': 0.05})
        self.engine.create_performance_alert("test_strategy_1", "disabled", {'reason': 'poor_performance'})
        
        # Get all alerts
        all_alerts = self.engine.get_performance_alerts(24)
        self.assertEqual(len(all_alerts), 3)
        
        # Get alerts for specific strategy
        strategy_alerts = self.engine.get_performance_alerts(24, "test_strategy_1")
        self.assertEqual(len(strategy_alerts), 2)
        
        for alert in strategy_alerts:
            self.assertEqual(alert['strategy_name'], "test_strategy_1")
    
    def test_performance_degradation_detection_integration(self):
        """Test integration of performance degradation detection with tracking."""
        strategy_name = "test_strategy_1"
        
        # Add declining performance history
        history = self.engine.strategy_performance_history[strategy_name]
        for i in range(10):
            history.append({
                'timestamp': datetime.now() - timedelta(hours=i),
                'return': 0.05 - 0.02 * i,  # Declining returns
                'sharpe': 1.5 - 0.2 * i,
                'drawdown': 0.02 + 0.01 * i,
                'win_rate': 0.7 - 0.05 * i
            })
        
        # Create poor performance metrics
        poor_metrics = PerformanceMetrics(
            total_return=-0.15,  # Poor return
            annualized_return=-0.20,
            excess_return=-0.25,
            sharpe_ratio=-0.8,  # Poor Sharpe
            sortino_ratio=-1.0,
            calmar_ratio=-0.5,
            max_drawdown=0.20,  # High drawdown
            volatility=0.30,
            downside_deviation=0.25,
            win_rate=0.30,  # Low win rate
            profit_factor=0.6,
            avg_trade_duration=timedelta(hours=8),
            trades_count=25,
            avg_win=0.02,
            avg_loss=-0.04
        )
        
        # Track performance (should detect degradation and create alert)
        self.engine._track_strategy_performance(strategy_name, poor_metrics)
        
        # Check that alert was created
        alerts = self.engine.get_performance_alerts(1, strategy_name)
        degradation_alerts = [a for a in alerts if a['alert_type'] == 'degradation']
        self.assertGreater(len(degradation_alerts), 0)
    
    def test_strategy_enabling_disabling_integration(self):
        """Test integration of strategy enabling/disabling with alerts."""
        strategy_name = "test_strategy_1"
        
        # Test disabling
        poor_metrics = PerformanceMetrics(
            total_return=-0.25,  # Below disable threshold
            annualized_return=-0.30,
            excess_return=-0.35,
            sharpe_ratio=-1.2,
            sortino_ratio=-1.5,
            calmar_ratio=-0.8,
            max_drawdown=0.30,
            volatility=0.35,
            downside_deviation=0.30,
            win_rate=0.25,
            profit_factor=0.4,
            avg_trade_duration=timedelta(hours=12),
            trades_count=20,
            avg_win=0.015,
            avg_loss=-0.05
        )
        
        self.engine._adapt_strategy_allocation(strategy_name, poor_metrics)
        
        # Strategy should be disabled
        self.assertFalse(self.engine.strategy_allocations[strategy_name].is_active)
        
        # Check that disable alert was created
        alerts = self.engine.get_performance_alerts(1, strategy_name)
        disable_alerts = [a for a in alerts if a['alert_type'] == 'disabled']
        self.assertGreater(len(disable_alerts), 0)
        
        # Test re-enabling
        good_metrics = PerformanceMetrics(
            total_return=0.08,  # Above re-enable threshold
            annualized_return=0.12,
            excess_return=0.05,
            sharpe_ratio=1.2,
            sortino_ratio=1.4,
            calmar_ratio=0.8,
            max_drawdown=0.04,
            volatility=0.15,
            downside_deviation=0.10,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=40,
            avg_win=0.025,
            avg_loss=-0.018
        )
        
        self.engine._adapt_strategy_allocation(strategy_name, good_metrics)
        
        # Strategy should be re-enabled
        self.assertTrue(self.engine.strategy_allocations[strategy_name].is_active)
        
        # Check that enable alert was created
        alerts = self.engine.get_performance_alerts(1, strategy_name)
        enable_alerts = [a for a in alerts if a['alert_type'] == 'enabled']
        self.assertGreater(len(enable_alerts), 0)


if __name__ == '__main__':
    unittest.main()