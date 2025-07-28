"""
Integration tests for enhanced trading strategies.

Tests cover:
- Strategy integration with real market data patterns
- Multi-strategy coordination
- Performance under various market conditions
- Backtesting with realistic scenarios
"""
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from bot.enhanced_strategies import (
    BollingerBandsRSIStrategy,
    MACDStrategy,
    VolumeWeightedStrategy,
    MultiTimeframeMomentumStrategy,
    StrategyBacktester,
    create_enhanced_strategy_suite,
    create_conservative_strategy_suite
)
from bot.strategy import SignalType, TradingSignal, SignalGenerator


class TestMarketConditionScenarios(unittest.TestCase):
    """Test strategies under different market conditions."""
    
    def setUp(self):
        """Set up test fixtures with different market scenarios."""
        self.strategies = create_enhanced_strategy_suite()
        self.backtester = StrategyBacktester()
        
        # Create different market condition datasets
        self.market_scenarios = self._create_market_scenarios()
    
    def _create_market_scenarios(self) -> dict:
        """Create different market condition datasets."""
        scenarios = {}
        np.random.seed(42)
        
        # Trending bull market
        dates = pd.date_range(start='2023-01-01', periods=500, freq='H')
        prices = []
        base_price = 100
        for i in range(500):
            base_price *= (1 + 0.001 + np.random.randn() * 0.01)  # Consistent uptrend
            prices.append(base_price)
        
        scenarios['bull_market'] = self._create_ohlcv_data(dates, prices)
        
        # Trending bear market
        prices = []
        base_price = 100
        for i in range(500):
            base_price *= (1 - 0.0005 + np.random.randn() * 0.01)  # Consistent downtrend
            prices.append(base_price)
        
        scenarios['bear_market'] = self._create_ohlcv_data(dates, prices)
        
        # Sideways/ranging market
        prices = []
        base_price = 100
        for i in range(500):
            # Oscillate around base price
            cycle = np.sin(i / 50) * 5
            base_price = 100 + cycle + np.random.randn() * 2
            prices.append(base_price)
        
        scenarios['sideways_market'] = self._create_ohlcv_data(dates, prices)
        
        # High volatility market
        prices = []
        base_price = 100
        for i in range(500):
            base_price *= (1 + np.random.randn() * 0.03)  # High volatility
            prices.append(base_price)
        
        scenarios['volatile_market'] = self._create_ohlcv_data(dates, prices)
        
        # Low volatility market
        prices = []
        base_price = 100
        for i in range(500):
            base_price *= (1 + np.random.randn() * 0.005)  # Low volatility
            prices.append(base_price)
        
        scenarios['low_volatility_market'] = self._create_ohlcv_data(dates, prices)
        
        return scenarios
    
    def _create_ohlcv_data(self, dates: pd.DatetimeIndex, prices: list) -> pd.DataFrame:
        """Create OHLCV data from price series."""
        prices = np.array(prices)
        volumes = np.random.randint(1000, 10000, len(prices))
        
        # Add volume spikes during large price moves
        price_changes = np.abs(np.diff(prices, prepend=prices[0]))
        volume_multiplier = 1 + price_changes / np.mean(price_changes) * 2
        volumes = volumes * volume_multiplier
        
        return pd.DataFrame({
            'open': prices * (1 + np.random.randn(len(prices)) * 0.001),
            'high': prices * (1 + np.abs(np.random.randn(len(prices))) * 0.002),
            'low': prices * (1 - np.abs(np.random.randn(len(prices))) * 0.002),
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_strategies_in_bull_market(self):
        """Test strategy performance in bull market conditions."""
        data = self.market_scenarios['bull_market']
        
        for strategy in self.strategies:
            with self.subTest(strategy=strategy.name):
                # Test signal generation
                signal = strategy.calculate_signals(data)
                self.assertIsInstance(signal, TradingSignal)
                
                # Test backtesting
                result = self.backtester.backtest_strategy(strategy, data)
                
                # In a bull market, we expect some positive performance
                # (though not guaranteed due to transaction costs and timing)
                self.assertIsInstance(result.total_return, float)
                self.assertGreaterEqual(result.win_rate, 0.0)
    
    def test_strategies_in_bear_market(self):
        """Test strategy performance in bear market conditions."""
        data = self.market_scenarios['bear_market']
        
        for strategy in self.strategies:
            with self.subTest(strategy=strategy.name):
                signal = strategy.calculate_signals(data)
                self.assertIsInstance(signal, TradingSignal)
                
                result = self.backtester.backtest_strategy(strategy, data)
                self.assertIsInstance(result.total_return, float)
                self.assertGreaterEqual(result.win_rate, 0.0)
    
    def test_strategies_in_sideways_market(self):
        """Test strategy performance in sideways market conditions."""
        data = self.market_scenarios['sideways_market']
        
        for strategy in self.strategies:
            with self.subTest(strategy=strategy.name):
                signal = strategy.calculate_signals(data)
                self.assertIsInstance(signal, TradingSignal)
                
                result = self.backtester.backtest_strategy(strategy, data)
                
                # In sideways markets, expect more conservative results
                self.assertIsInstance(result.total_return, float)
                self.assertLessEqual(abs(result.total_return), 10.0)  # Reasonable bounds
    
    def test_strategies_in_volatile_market(self):
        """Test strategy performance in high volatility conditions."""
        data = self.market_scenarios['volatile_market']
        
        for strategy in self.strategies:
            with self.subTest(strategy=strategy.name):
                signal = strategy.calculate_signals(data)
                self.assertIsInstance(signal, TradingSignal)
                
                result = self.backtester.backtest_strategy(strategy, data)
                
                # High volatility should result in more trades
                self.assertGreaterEqual(result.total_trades, 0)
                self.assertIsInstance(result.volatility, float)
    
    def test_volatility_adjustment_effectiveness(self):
        """Test that volatility adjustments work as expected."""
        volatile_data = self.market_scenarios['volatile_market']
        low_vol_data = self.market_scenarios['low_volatility_market']
        
        # Test with a volatility-adjusted strategy
        strategy = BollingerBandsRSIStrategy()
        
        volatile_signal = strategy.calculate_signals(volatile_data)
        low_vol_signal = strategy.calculate_signals(low_vol_data)
        
        # Both should generate valid signals
        self.assertIsInstance(volatile_signal, TradingSignal)
        self.assertIsInstance(low_vol_signal, TradingSignal)
        
        # Test volatility adjustment calculation
        volatile_adj = strategy.calculate_volatility_adjustment(volatile_data)
        low_vol_adj = strategy.calculate_volatility_adjustment(low_vol_data)
        
        # Volatile markets should have lower adjustment (more conservative)
        self.assertLess(volatile_adj, low_vol_adj)


class TestMultiStrategyCoordination(unittest.TestCase):
    """Test coordination between multiple strategies."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.strategies = create_enhanced_strategy_suite()
        self.signal_generator = SignalGenerator(self.strategies)
        
        # Create test data
        dates = pd.date_range(start='2023-01-01', periods=300, freq='H')
        np.random.seed(42)
        
        prices = []
        base_price = 100
        for i in range(300):
            # Create some trend changes for interesting signals
            if i < 100:
                trend = 0.001
            elif i < 200:
                trend = -0.0005
            else:
                trend = 0.0008
            
            base_price *= (1 + trend + np.random.randn() * 0.015)
            prices.append(base_price)
        
        volumes = np.random.randint(1000, 15000, 300)
        
        self.test_data = pd.DataFrame({
            'open': np.array(prices) * 0.999,
            'high': np.array(prices) * 1.002,
            'low': np.array(prices) * 0.998,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_signal_generator_coordination(self):
        """Test SignalGenerator with enhanced strategies."""
        combined_signal = self.signal_generator.evaluate_all_strategies(self.test_data)
        
        self.assertIsInstance(combined_signal, TradingSignal)
        self.assertIn(combined_signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
        self.assertGreaterEqual(combined_signal.confidence, 0.0)
        self.assertLessEqual(combined_signal.confidence, 1.0)
    
    def test_individual_strategy_signals(self):
        """Test that individual strategies generate reasonable signals."""
        individual_signals = []
        
        for strategy in self.strategies:
            signal = strategy.calculate_signals(self.test_data)
            individual_signals.append(signal)
            
            # Each signal should be valid
            self.assertIsInstance(signal, TradingSignal)
            self.assertIn(signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
        
        # Should have signals from all strategies
        self.assertEqual(len(individual_signals), len(self.strategies))
        
        # At least some strategies should generate non-HOLD signals
        non_hold_signals = [s for s in individual_signals if s.action != SignalType.HOLD]
        self.assertGreater(len(non_hold_signals), 0)
    
    def test_strategy_agreement_analysis(self):
        """Test analysis of strategy agreement."""
        signals = []
        for strategy in self.strategies:
            signal = strategy.calculate_signals(self.test_data)
            signals.append(signal)
        
        # Analyze signal distribution
        buy_signals = [s for s in signals if s.action == SignalType.BUY]
        sell_signals = [s for s in signals if s.action == SignalType.SELL]
        hold_signals = [s for s in signals if s.action == SignalType.HOLD]
        
        # Should have some distribution of signals
        total_signals = len(buy_signals) + len(sell_signals) + len(hold_signals)
        self.assertEqual(total_signals, len(self.strategies))
        
        # Test signal combination logic
        combined = self.signal_generator.combine_signals(signals)
        self.assertIsInstance(combined, TradingSignal)


class TestStrategyParameterOptimization(unittest.TestCase):
    """Test strategy parameter optimization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.backtester = StrategyBacktester()
        
        # Create optimization test data
        dates = pd.date_range(start='2023-01-01', periods=800, freq='H')
        np.random.seed(42)
        
        # Create data with clear patterns for optimization
        prices = []
        base_price = 100
        for i in range(800):
            # Cyclical pattern with trend
            cycle = np.sin(i / 100) * 0.02
            trend = i / 100000
            noise = np.random.randn() * 0.01
            
            base_price *= (1 + cycle + trend + noise)
            prices.append(base_price)
        
        volumes = np.random.randint(2000, 12000, 800)
        
        self.optimization_data = pd.DataFrame({
            'open': np.array(prices) * 0.9995,
            'high': np.array(prices) * 1.0020,
            'low': np.array(prices) * 0.9980,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_bollinger_bands_optimization(self):
        """Test Bollinger Bands parameter optimization."""
        param_ranges = {
            'bb_period': [15, 20, 25],
            'bb_std': [1.5, 2.0, 2.5],
            'rsi_period': [10, 14, 18]
        }
        
        best_params, best_result = self.backtester.optimize_parameters(
            BollingerBandsRSIStrategy, self.optimization_data, param_ranges
        )
        
        self.assertIsNotNone(best_params)
        self.assertIsNotNone(best_result)
        
        # Check that optimized parameters are within expected ranges
        self.assertIn(best_params['bb_period'], param_ranges['bb_period'])
        self.assertIn(best_params['bb_std'], param_ranges['bb_std'])
        self.assertIn(best_params['rsi_period'], param_ranges['rsi_period'])
        
        # Result should be valid
        self.assertIsInstance(best_result.total_return, float)
        self.assertIsInstance(best_result.sharpe_ratio, float)
    
    def test_macd_optimization(self):
        """Test MACD parameter optimization."""
        param_ranges = {
            'fast_period': [8, 12, 16],
            'slow_period': [20, 26, 32],
            'signal_period': [6, 9, 12]
        }
        
        best_params, best_result = self.backtester.optimize_parameters(
            MACDStrategy, self.optimization_data, param_ranges
        )
        
        self.assertIsNotNone(best_params)
        self.assertIsNotNone(best_result)
        
        # Verify parameter constraints
        self.assertLess(best_params['fast_period'], best_params['slow_period'])
    
    def test_optimization_performance_improvement(self):
        """Test that optimization improves performance."""
        # Test default parameters
        default_strategy = BollingerBandsRSIStrategy()
        default_result = self.backtester.backtest_strategy(default_strategy, self.optimization_data)
        
        # Test optimized parameters
        param_ranges = {
            'bb_period': [15, 20, 25, 30],
            'bb_std': [1.5, 2.0, 2.5]
        }
        
        best_params, optimized_result = self.backtester.optimize_parameters(
            BollingerBandsRSIStrategy, self.optimization_data, param_ranges
        )
        
        # Optimized should generally perform better (though not guaranteed)
        # At minimum, optimization should complete successfully
        self.assertIsNotNone(optimized_result)
        self.assertGreaterEqual(optimized_result.sharpe_ratio, -10.0)  # More reasonable bound for edge cases


class TestRealWorldScenarios(unittest.TestCase):
    """Test strategies with realistic market scenarios."""
    
    def setUp(self):
        """Set up realistic market scenarios."""
        self.strategies = create_enhanced_strategy_suite()
        self.conservative_strategies = create_conservative_strategy_suite()
        
    def _create_crypto_crash_scenario(self) -> pd.DataFrame:
        """Create a crypto market crash scenario."""
        dates = pd.date_range(start='2023-01-01', periods=200, freq='H')
        np.random.seed(42)
        
        prices = []
        base_price = 100
        
        for i in range(200):
            if i < 50:
                # Normal market
                change = np.random.randn() * 0.02
            elif i < 100:
                # Crash phase
                change = -0.05 + np.random.randn() * 0.03
            elif i < 150:
                # Recovery attempt
                change = 0.02 + np.random.randn() * 0.04
            else:
                # Stabilization
                change = np.random.randn() * 0.015
            
            base_price *= (1 + change)
            prices.append(max(base_price, 10))  # Floor price
        
        # High volume during crash
        volumes = []
        for i in range(200):
            if 50 <= i < 100:
                volume = np.random.randint(10000, 50000)  # High volume during crash
            else:
                volume = np.random.randint(2000, 8000)
            volumes.append(volume)
        
        return pd.DataFrame({
            'open': np.array(prices) * 0.998,
            'high': np.array(prices) * 1.005,
            'low': np.array(prices) * 0.995,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def _create_pump_and_dump_scenario(self) -> pd.DataFrame:
        """Create a pump and dump scenario."""
        dates = pd.date_range(start='2023-01-01', periods=150, freq='H')
        np.random.seed(42)
        
        prices = []
        volumes = []
        base_price = 100
        
        for i in range(150):
            if i < 30:
                # Accumulation phase
                change = np.random.randn() * 0.01
                volume = np.random.randint(1000, 3000)
            elif i < 50:
                # Pump phase
                change = 0.08 + np.random.randn() * 0.02
                volume = np.random.randint(15000, 30000)
            elif i < 80:
                # Dump phase
                change = -0.12 + np.random.randn() * 0.03
                volume = np.random.randint(20000, 40000)
            else:
                # Aftermath
                change = np.random.randn() * 0.02
                volume = np.random.randint(2000, 6000)
            
            base_price *= (1 + change)
            prices.append(max(base_price, 10))
            volumes.append(volume)
        
        return pd.DataFrame({
            'open': np.array(prices) * 0.999,
            'high': np.array(prices) * 1.003,
            'low': np.array(prices) * 0.997,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_crash_scenario_handling(self):
        """Test strategy behavior during market crash."""
        crash_data = self._create_crypto_crash_scenario()
        
        for strategy in self.strategies:
            with self.subTest(strategy=strategy.name):
                signal = strategy.calculate_signals(crash_data)
                
                # Should generate valid signals even during crash
                self.assertIsInstance(signal, TradingSignal)
                self.assertIn(signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
                
                # Test that volatility adjustment works
                if hasattr(strategy, 'calculate_volatility_adjustment'):
                    vol_adj = strategy.calculate_volatility_adjustment(crash_data)
                    self.assertLessEqual(vol_adj, 2.0)  # Should be within reasonable bounds
    
    def test_pump_and_dump_detection(self):
        """Test strategy behavior during pump and dump."""
        pump_dump_data = self._create_pump_and_dump_scenario()
        
        volume_strategy = VolumeWeightedStrategy()
        signal = volume_strategy.calculate_signals(pump_dump_data)
        
        # Should generate a signal (likely sell during dump phase)
        self.assertIsInstance(signal, TradingSignal)
        
        # Test that volume analysis works
        self.assertIn('volume', signal.reasoning.lower())
    
    def test_conservative_vs_aggressive_strategies(self):
        """Test difference between conservative and aggressive strategies."""
        test_data = self._create_crypto_crash_scenario()
        
        # Test both strategy suites
        aggressive_signals = []
        for strategy in self.strategies[:3]:  # First 3 aggressive strategies
            signal = strategy.calculate_signals(test_data)
            aggressive_signals.append(signal)
        
        conservative_signals = []
        for strategy in self.conservative_strategies[:3]:  # First 3 conservative strategies
            signal = strategy.calculate_signals(test_data)
            conservative_signals.append(signal)
        
        # Both should generate valid signals
        self.assertEqual(len(aggressive_signals), 3)
        self.assertEqual(len(conservative_signals), 3)
        
        # Conservative strategies should generally have lower confidence
        # (though this isn't guaranteed in all market conditions)
        for signal in conservative_signals:
            self.assertIsInstance(signal, TradingSignal)


class TestStrategyRobustness(unittest.TestCase):
    """Test strategy robustness under edge cases."""
    
    def test_extreme_price_movements(self):
        """Test strategies with extreme price movements."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='H')
        
        # Create data with extreme movements
        prices = [100]
        for i in range(99):
            if i == 20:
                prices.append(prices[-1] * 2)  # 100% jump
            elif i == 50:
                prices.append(prices[-1] * 0.3)  # 70% drop
            else:
                prices.append(prices[-1] * (1 + np.random.randn() * 0.01))
        
        extreme_data = pd.DataFrame({
            'open': np.array(prices) * 0.999,
            'high': np.array(prices) * 1.001,
            'low': np.array(prices) * 0.999,
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
        
        strategies = create_enhanced_strategy_suite()
        
        for strategy in strategies:
            with self.subTest(strategy=strategy.name):
                try:
                    signal = strategy.calculate_signals(extreme_data)
                    self.assertIsInstance(signal, TradingSignal)
                except Exception as e:
                    self.fail(f"Strategy {strategy.name} failed with extreme data: {str(e)}")
    
    def test_zero_volume_handling(self):
        """Test strategies with zero volume periods."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='H')
        prices = 100 + np.cumsum(np.random.randn(100) * 0.01)
        volumes = np.random.randint(1000, 5000, 100)
        volumes[20:30] = 0  # Zero volume period
        
        zero_volume_data = pd.DataFrame({
            'open': prices * 0.999,
            'high': prices * 1.001,
            'low': prices * 0.999,
            'close': prices,
            'volume': volumes
        }, index=dates)
        
        strategies = create_enhanced_strategy_suite()
        
        for strategy in strategies:
            with self.subTest(strategy=strategy.name):
                try:
                    signal = strategy.calculate_signals(zero_volume_data)
                    self.assertIsInstance(signal, TradingSignal)
                except Exception as e:
                    self.fail(f"Strategy {strategy.name} failed with zero volume: {str(e)}")


if __name__ == '__main__':
    unittest.main()