"""
Unit tests for adaptive signal generation functionality.

Tests the enhanced AdaptiveSignal class and signal generation methods
including ML confidence adjustment, regime-based filtering, and
signal strength amplification/dampening.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from bot.adaptive.adaptive_strategy_engine import AdaptiveStrategyEngine
from bot.adaptive.data_models import MarketRegime, AdaptiveSignal, StrategyAllocation
from bot.adaptive.enums import RegimeType, SignalStrength
from bot.strategy import TradingSignal, SignalType


class TestAdaptiveSignalGeneration(unittest.TestCase):
    """Test cases for adaptive signal generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'hysteresis_threshold': 0.15,
            'min_strategies_for_ensemble': 2,
            'confidence_decay_factor': 0.95,
            'min_consensus_threshold': 0.6
        }
        self.engine = AdaptiveStrategyEngine(self.config)
        
        # Create test market data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(100) * 0.01)
        
        self.market_data = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': prices * (1 + np.abs(np.random.randn(100) * 0.005)),
            'low': prices * (1 - np.abs(np.random.randn(100) * 0.005)),
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        })
        
        # Create test regime
        self.test_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.3,
            trend_strength=0.6,
            momentum=0.4,
            detected_at=datetime.now()
        )
        
        # Create test ML predictions
        self.ml_predictions = {
            'signal_confidence': 0.75,
            'trade_success_probability': 0.68,
            'expected_return': 0.02
        }
    
    def test_adaptive_signal_creation(self):
        """Test creation of AdaptiveSignal with enhanced metadata."""
        base_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.7,
            strategy="test_strategy",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Test signal"
        )
        
        strategy_weights = {"test_strategy": 1.0}
        
        adaptive_signal = self.engine._create_adaptive_signal(
            base_signal, strategy_weights, "BTCUSD", self.market_data,
            self.test_regime, self.ml_predictions
        )
        
        # Verify basic properties
        self.assertEqual(adaptive_signal.pair, "BTCUSD")
        self.assertEqual(adaptive_signal.signal_type, "buy")
        self.assertEqual(adaptive_signal.price, 100.0)
        self.assertIsInstance(adaptive_signal.strength, SignalStrength)
        
        # Verify regime context
        self.assertEqual(adaptive_signal.regime_context.regime_type, RegimeType.TRENDING_BULL)
        self.assertEqual(adaptive_signal.regime_context.confidence, 0.8)
        
        # Verify ML confidence
        self.assertEqual(adaptive_signal.ml_confidence, 0.75)
        
        # Verify strategy weights
        self.assertEqual(adaptive_signal.strategy_weights, strategy_weights)
        
        # Verify metadata
        self.assertIn('regime_type', adaptive_signal.adaptation_metadata)
        self.assertIn('ml_predictions', adaptive_signal.adaptation_metadata)
        self.assertIn('market_volatility', adaptive_signal.adaptation_metadata)
        
        # Verify risk parameters are calculated
        self.assertIsNotNone(adaptive_signal.suggested_position_size)
        self.assertIsNotNone(adaptive_signal.stop_loss)
        self.assertIsNotNone(adaptive_signal.take_profit)
    
    def test_signal_strength_calculation(self):
        """Test signal strength calculation based on confidence and consensus."""
        # The engine has 3 strategies by default, so consensus factor calculations:
        # consensus_factor = len(strategy_weights) / max(len(self.strategies), 1)
        
        # Test very strong signal - 2 strategies out of 3
        # consensus_factor = 2/3 ≈ 0.67, adjusted = 0.9 * (0.7 + 0.67*0.3) = 0.9 * 0.9 = 0.81
        strength = self.engine._calculate_signal_strength(0.9, {"s1": 0.5, "s2": 0.5})
        self.assertEqual(strength, SignalStrength.VERY_STRONG)
        
        # Test strong signal - need higher base confidence
        # consensus_factor = 2/3, adjusted = 0.8 * (0.7 + 0.67*0.3) = 0.8 * 0.9 = 0.72
        strength = self.engine._calculate_signal_strength(0.8, {"s1": 0.6, "s2": 0.4})
        self.assertEqual(strength, SignalStrength.STRONG)
        
        # Test moderate signal - single strategy
        # consensus_factor = 1/3 ≈ 0.33, adjusted = 0.6 * (0.7 + 0.33*0.3) = 0.6 * 0.8 = 0.48
        strength = self.engine._calculate_signal_strength(0.6, {"s1": 1.0})
        self.assertEqual(strength, SignalStrength.MODERATE)
        
        # Test weak signal
        # consensus_factor = 1/3, adjusted = 0.4 * (0.7 + 0.33*0.3) = 0.4 * 0.8 = 0.32
        strength = self.engine._calculate_signal_strength(0.4, {"s1": 1.0})
        self.assertEqual(strength, SignalStrength.WEAK)
        
        # Test very weak signal
        # consensus_factor = 1/3, adjusted = 0.2 * (0.7 + 0.33*0.3) = 0.2 * 0.8 = 0.16
        strength = self.engine._calculate_signal_strength(0.2, {"s1": 1.0})
        self.assertEqual(strength, SignalStrength.VERY_WEAK)
    
    def test_ml_confidence_adjustment(self):
        """Test ML confidence adjustment functionality."""
        # Create test signal
        base_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.6,
            strategy="test_strategy",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Test signal"
        )
        
        adaptive_signal = self.engine._create_adaptive_signal(
            base_signal, {"test_strategy": 1.0}, "BTCUSD", self.market_data
        )
        
        original_confidence = adaptive_signal.confidence
        
        # Apply ML adjustment
        adjusted_signal = self.engine._adjust_signal_confidence(
            adaptive_signal, self.ml_predictions, "BTCUSD"
        )
        
        # Verify confidence was adjusted
        self.assertNotEqual(adjusted_signal.confidence, original_confidence)
        self.assertEqual(adjusted_signal.ml_confidence, 0.75)
        
        # Verify metadata was updated
        self.assertIn('ml_adjustment', adjusted_signal.adaptation_metadata)
        self.assertIn('original_confidence', adjusted_signal.adaptation_metadata)
        self.assertIn('confidence_change', adjusted_signal.adaptation_metadata)
    
    def test_signal_strength_amplification(self):
        """Test signal strength amplification based on recent performance."""
        # Create test signal
        base_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.6,
            strategy="test_strategy",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Test signal"
        )
        
        adaptive_signal = self.engine._create_adaptive_signal(
            base_signal, {"test_strategy": 1.0}, "BTCUSD", self.market_data
        )
        
        original_confidence = adaptive_signal.confidence
        original_strength = adaptive_signal.strength
        
        # Mock good recent performance
        with patch.object(self.engine, '_calculate_recent_performance_score', return_value=0.2):
            amplified_signal = self.engine._amplify_signal_strength(adaptive_signal, "BTCUSD")
            
            # Verify amplification occurred
            self.assertGreater(amplified_signal.confidence, original_confidence)
            self.assertIn('performance_amplification', amplified_signal.adaptation_metadata)
            self.assertIn('performance_score', amplified_signal.adaptation_metadata)
        
        # Mock poor recent performance
        with patch.object(self.engine, '_calculate_recent_performance_score', return_value=-0.2):
            dampened_signal = self.engine._amplify_signal_strength(adaptive_signal, "BTCUSD")
            
            # Verify dampening occurred
            self.assertLess(dampened_signal.confidence, original_confidence)
    
    def test_regime_based_filtering(self):
        """Test signal filtering based on market regime."""
        # Create test signals
        signals = {
            "momentum_strategy": TradingSignal(
                action=SignalType.BUY,
                confidence=0.7,
                strategy="momentum_strategy",
                timestamp=datetime.now(),
                price=100.0,
                reasoning="Momentum signal"
            ),
            "mean_reversion_strategy": TradingSignal(
                action=SignalType.SELL,
                confidence=0.6,
                strategy="mean_reversion_strategy",
                timestamp=datetime.now(),
                price=100.0,
                reasoning="Mean reversion signal"
            )
        }
        
        # Set up strategy allocations with regime preferences
        self.engine.strategy_allocations["momentum_strategy"] = StrategyAllocation(
            strategy_name="momentum_strategy",
            allocation_percentage=0.5,
            current_weight=0.5,
            base_weight=0.5,
            recent_performance=0.1,
            performance_trend=0.05,
            confidence_level=0.7
        )
        self.engine.strategy_allocations["momentum_strategy"].regime_preferences = [
            RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR
        ]
        
        self.engine.strategy_allocations["mean_reversion_strategy"] = StrategyAllocation(
            strategy_name="mean_reversion_strategy",
            allocation_percentage=0.5,
            current_weight=0.5,
            base_weight=0.5,
            recent_performance=0.05,
            performance_trend=0.02,
            confidence_level=0.6
        )
        self.engine.strategy_allocations["mean_reversion_strategy"].regime_preferences = [
            RegimeType.RANGING, RegimeType.LOW_VOLATILITY
        ]
        
        # Test filtering with trending bull regime
        trending_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.3,
            trend_strength=0.6,
            momentum=0.4,
            detected_at=datetime.now()
        )
        
        filtered_signals = self.engine._filter_signals_by_regime(signals, trending_regime)
        
        # Momentum strategy should be included (preferred regime)
        self.assertIn("momentum_strategy", filtered_signals)
        
        # Mean reversion strategy might be excluded or included based on confidence
        # Since the signal confidence (0.6) is not > 0.7, it should be excluded
        self.assertNotIn("mean_reversion_strategy", filtered_signals)
    
    def test_parameter_adjustments(self):
        """Test dynamic parameter adjustments based on market conditions."""
        base_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.7,
            strategy="test_strategy",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Test signal"
        )
        
        # Test high volatility regime
        high_vol_regime = MarketRegime(
            regime_type=RegimeType.HIGH_VOLATILITY,
            confidence=0.8,
            volatility_level=0.8,
            trend_strength=0.2,
            momentum=0.1,
            detected_at=datetime.now()
        )
        
        adjustments = self.engine._calculate_parameter_adjustments(
            base_signal, high_vol_regime, self.market_data
        )
        
        # Verify volatility-based adjustments
        self.assertIn('stop_loss_multiplier', adjustments)
        self.assertIn('take_profit_multiplier', adjustments)
        self.assertGreater(adjustments['stop_loss_multiplier'], 1.0)
        
        # Verify regime-specific adjustments
        self.assertIn('position_size_multiplier', adjustments)
        self.assertEqual(adjustments['position_size_multiplier'], 0.7)  # Reduced for high vol
        
        # Test trending regime
        trending_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.3,
            trend_strength=0.7,
            momentum=0.5,
            detected_at=datetime.now()
        )
        
        trending_adjustments = self.engine._calculate_parameter_adjustments(
            base_signal, trending_regime, self.market_data
        )
        
        # Verify trend-based adjustments
        self.assertIn('trend_following_bias', trending_adjustments)
        self.assertIn('take_profit_multiplier', trending_adjustments)
        self.assertEqual(trending_adjustments['take_profit_multiplier'], 1.3)
    
    def test_position_size_calculation(self):
        """Test position size calculation based on signal and conditions."""
        base_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.8,
            strategy="test_strategy",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Test signal"
        )
        
        position_size = self.engine._calculate_position_size(
            base_signal, self.test_regime, 0.75
        )
        
        # Verify position size is within bounds
        self.assertGreaterEqual(position_size, 0.01)
        self.assertLessEqual(position_size, 0.15)
        
        # Verify it's influenced by confidence
        self.assertGreater(position_size, 0.05)  # Should be > 5% for high confidence
    
    def test_risk_levels_calculation(self):
        """Test stop-loss and take-profit calculation."""
        base_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.7,
            strategy="test_strategy",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Test signal"
        )
        
        stop_loss, take_profit = self.engine._calculate_risk_levels(
            base_signal, self.market_data, self.test_regime
        )
        
        # Verify levels are calculated
        self.assertIsNotNone(stop_loss)
        self.assertIsNotNone(take_profit)
        
        # Verify levels make sense for BUY signal
        self.assertLess(stop_loss, 100.0)  # Stop loss below entry
        self.assertGreater(take_profit, 100.0)  # Take profit above entry
        
        # Test SELL signal
        sell_signal = TradingSignal(
            action=SignalType.SELL,
            confidence=0.7,
            strategy="test_strategy",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Test sell signal"
        )
        
        sell_stop, sell_target = self.engine._calculate_risk_levels(
            sell_signal, self.market_data, self.test_regime
        )
        
        # Verify levels make sense for SELL signal
        self.assertGreater(sell_stop, 100.0)  # Stop loss above entry
        self.assertLess(sell_target, 100.0)  # Take profit below entry
    
    def test_ensemble_signal_generation(self):
        """Test ensemble signal generation from multiple strategies."""
        # Create mock strategies
        strategy1 = Mock()
        strategy1.calculate_signals.return_value = TradingSignal(
            action=SignalType.BUY,
            confidence=0.7,
            strategy="strategy1",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Strategy 1 buy signal"
        )
        
        strategy2 = Mock()
        strategy2.calculate_signals.return_value = TradingSignal(
            action=SignalType.BUY,
            confidence=0.6,
            strategy="strategy2",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Strategy 2 buy signal"
        )
        
        # Add strategies to engine
        self.engine.strategies = {"strategy1": strategy1, "strategy2": strategy2}
        self.engine.strategy_allocations = {
            "strategy1": StrategyAllocation(
                strategy_name="strategy1",
                allocation_percentage=0.6,
                current_weight=0.6,
                base_weight=0.6,
                recent_performance=0.1,
                performance_trend=0.05,
                confidence_level=0.7,
                is_active=True
            ),
            "strategy2": StrategyAllocation(
                strategy_name="strategy2",
                allocation_percentage=0.4,
                current_weight=0.4,
                base_weight=0.4,
                recent_performance=0.05,
                performance_trend=0.02,
                confidence_level=0.6,
                is_active=True
            )
        }
        
        # Generate ensemble signal
        ensemble_signal = self.engine.execute_adaptive_signal(
            "BTCUSD", self.market_data, self.test_regime, self.ml_predictions
        )
        
        # Verify ensemble signal was created
        self.assertIsNotNone(ensemble_signal)
        self.assertEqual(ensemble_signal.signal_type, "buy")
        self.assertGreater(ensemble_signal.confidence, 0.0)
        
        # Verify strategy weights are included
        self.assertEqual(len(ensemble_signal.strategy_weights), 2)
        self.assertIn("strategy1", ensemble_signal.strategy_weights)
        self.assertIn("strategy2", ensemble_signal.strategy_weights)
        
        # Verify metadata includes ensemble information
        self.assertEqual(ensemble_signal.adaptation_metadata['ensemble_size'], 2)
    
    def test_conflicting_signals_handling(self):
        """Test handling of conflicting signals from different strategies."""
        # Create conflicting signals
        strategy1 = Mock()
        strategy1.calculate_signals.return_value = TradingSignal(
            action=SignalType.BUY,
            confidence=0.6,
            strategy="strategy1",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Buy signal"
        )
        
        strategy2 = Mock()
        strategy2.calculate_signals.return_value = TradingSignal(
            action=SignalType.SELL,
            confidence=0.5,
            strategy="strategy2",
            timestamp=datetime.now(),
            price=100.0,
            reasoning="Sell signal"
        )
        
        # Add strategies with equal weights
        self.engine.strategies = {"strategy1": strategy1, "strategy2": strategy2}
        self.engine.strategy_allocations = {
            "strategy1": StrategyAllocation(
                strategy_name="strategy1",
                allocation_percentage=0.5,
                current_weight=0.5,
                base_weight=0.5,
                recent_performance=0.05,
                performance_trend=0.02,
                confidence_level=0.6,
                is_active=True
            ),
            "strategy2": StrategyAllocation(
                strategy_name="strategy2",
                allocation_percentage=0.5,
                current_weight=0.5,
                base_weight=0.5,
                recent_performance=0.05,
                performance_trend=0.02,
                confidence_level=0.6,
                is_active=True
            )
        }
        
        # Generate signal with conflicting inputs
        ensemble_signal = self.engine.execute_adaptive_signal(
            "BTCUSD", self.market_data, self.test_regime, self.ml_predictions
        )
        
        # With equal weights and similar confidence, should favor BUY (higher confidence)
        # But if consensus threshold is not met, might return None
        if ensemble_signal:
            self.assertEqual(ensemble_signal.signal_type, "buy")
        # If no consensus, no signal should be generated
    
    def test_signal_filtering_edge_cases(self):
        """Test edge cases in signal filtering."""
        # Test with no active strategies
        self.engine.strategy_allocations = {}
        
        result = self.engine.execute_adaptive_signal(
            "BTCUSD", self.market_data, self.test_regime, self.ml_predictions
        )
        
        self.assertIsNone(result)
        
        # Test with empty market data
        empty_data = pd.DataFrame()
        
        result = self.engine.execute_adaptive_signal(
            "BTCUSD", empty_data, self.test_regime, self.ml_predictions
        )
        
        self.assertIsNone(result)
    
    def test_recent_performance_score_calculation(self):
        """Test recent performance score calculation."""
        # Set up strategy allocations with different performance
        self.engine.strategy_allocations = {
            "good_strategy": StrategyAllocation(
                strategy_name="good_strategy",
                allocation_percentage=0.5,
                current_weight=0.5,
                base_weight=0.5,
                recent_performance=0.15,
                performance_trend=0.05,
                confidence_level=0.7,
                is_active=True
            ),
            "poor_strategy": StrategyAllocation(
                strategy_name="poor_strategy",
                allocation_percentage=0.5,
                current_weight=0.5,
                base_weight=0.5,
                recent_performance=-0.1,
                performance_trend=-0.03,
                confidence_level=0.4,
                is_active=True
            )
        }
        
        score = self.engine._calculate_recent_performance_score("BTCUSD")
        
        # Should be average of the two performances
        expected_score = (0.15 + (-0.1)) / 2
        self.assertAlmostEqual(score, expected_score, places=3)
        
        # Test with no active strategies
        self.engine.strategy_allocations = {}
        score = self.engine._calculate_recent_performance_score("BTCUSD")
        self.assertEqual(score, 0.0)


if __name__ == '__main__':
    unittest.main()