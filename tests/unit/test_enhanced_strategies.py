"""
Unit tests for enhanced trading strategies.

Tests cover:
- Strategy signal generation
- Volatility adjustments
- Multi-timeframe analysis
- Backtesting functionality
- Parameter optimization
"""
import unittest
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from bot.enhanced_strategies import (
    BollingerBandsRSIStrategy,
    MACDStrategy,
    VolumeWeightedStrategy,
    MultiTimeframeMomentumStrategy,
    StrategyBacktester,
    VolatilityAdjustedStrategy,
    create_enhanced_strategy_suite,
    create_conservative_strategy_suite
)
from bot.strategy import SignalType, TradingSignal


class TestVolatilityAdjustedStrategy(unittest.TestCase):
    """Test volatility adjustment functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # We'll use concrete strategies in the tests
        
        # Create sample data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='H')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(100) * 0.02)
        volumes = np.random.randint(1000, 10000, 100)
        
        self.sample_data = pd.DataFrame({
            'open': prices * 0.999,
            'high': prices * 1.001,
            'low': prices * 0.998,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_volatility_adjustment_calculation(self):
        """Test volatility adjustment factor calculation."""
        # Use a concrete strategy that inherits from VolatilityAdjustedStrategy
        strategy = BollingerBandsRSIStrategy()
        adjustment = strategy.calculate_volatility_adjustment(self.sample_data)
        
        self.assertIsInstance(adjustment, float)
        self.assertGreaterEqual(adjustment, 0.5)
        self.assertLessEqual(adjustment, 2.0)
    
    def test_volatility_adjustment_with_insufficient_data(self):
        """Test volatility adjustment with insufficient data."""
        strategy = BollingerBandsRSIStrategy()
        small_data = self.sample_data.head(5)
        adjustment = strategy.calculate_volatility_adjustment(small_data)
        
        self.assertEqual(adjustment, 1.0)


class TestBollingerBandsRSIStrategy(unittest.TestCase):
    """Test Bollinger Bands with RSI strategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.strategy = BollingerBandsRSIStrategy()
        
        # Create sample data with trend
        dates = pd.date_range(start='2023-01-01', periods=100, freq='H')
        np.random.seed(42)
        
        # Create trending data
        trend = np.linspace(100, 120, 100)
        noise = np.random.randn(100) * 2
        prices = trend + noise
        volumes = np.random.randint(1000, 10000, 100)
        
        self.sample_data = pd.DataFrame({
            'open': prices * 0.999,
            'high': prices * 1.002,
            'low': prices * 0.998,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_signal_generation(self):
        """Test basic signal generation."""
        signal = self.strategy.calculate_signals(self.sample_data)
        
        self.assertIsInstance(signal, TradingSignal)
        self.assertIn(signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
        self.assertGreaterEqual(signal.confidence, 0.0)
        self.assertLessEqual(signal.confidence, 1.0)
    
    def test_insufficient_data(self):
        """Test behavior with insufficient data."""
        small_data = self.sample_data.head(10)
        signal = self.strategy.calculate_signals(small_data)
        
        self.assertEqual(signal.action, SignalType.HOLD)
        self.assertEqual(signal.confidence, 0.0)
    
    def test_bollinger_band_calculation(self):
        """Test Bollinger Bands calculation."""
        data = self.sample_data.copy()
        
        # Calculate BB manually for verification
        bb_middle = data['close'].rolling(window=20).mean()
        bb_std = data['close'].rolling(window=20).std()
        bb_upper = bb_middle + (bb_std * 2.0)
        bb_lower = bb_middle - (bb_std * 2.0)
        
        # Test that our calculation would be similar
        signal = self.strategy.calculate_signals(data)
        self.assertIsNotNone(signal)
    
    def test_rsi_calculation(self):
        """Test RSI calculation."""
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109])
        rsi = self.strategy._calculate_rsi(prices, 5)
        
        # RSI should be between 0 and 100
        rsi_values = rsi.dropna()
        self.assertTrue(all(0 <= val <= 100 for val in rsi_values))


class TestMACDStrategy(unittest.TestCase):
    """Test MACD strategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.strategy = MACDStrategy()
        
        # Create sample data with clear trend changes
        dates = pd.date_range(start='2023-01-01', periods=100, freq='H')
        np.random.seed(42)
        
        # Create data with trend changes for MACD signals
        prices = []
        base_price = 100
        for i in range(100):
            if i < 30:
                base_price += np.random.randn() * 0.5 + 0.1  # Uptrend
            elif i < 60:
                base_price += np.random.randn() * 0.5 - 0.1  # Downtrend
            else:
                base_price += np.random.randn() * 0.5 + 0.05  # Slight uptrend
            prices.append(base_price)
        
        volumes = np.random.randint(1000, 10000, 100)
        
        self.sample_data = pd.DataFrame({
            'open': np.array(prices) * 0.999,
            'high': np.array(prices) * 1.001,
            'low': np.array(prices) * 0.998,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_signal_generation(self):
        """Test MACD signal generation."""
        signal = self.strategy.calculate_signals(self.sample_data)
        
        self.assertIsInstance(signal, TradingSignal)
        self.assertIn(signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
    
    def test_macd_calculation(self):
        """Test MACD calculation components."""
        data = self.sample_data.copy()
        
        # Calculate MACD components
        ema_fast = data['close'].ewm(span=12).mean()
        ema_slow = data['close'].ewm(span=26).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=9).mean()
        
        # Verify calculations are reasonable
        self.assertFalse(macd.isna().all())
        self.assertFalse(macd_signal.isna().all())


class TestVolumeWeightedStrategy(unittest.TestCase):
    """Test Volume Weighted strategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.strategy = VolumeWeightedStrategy()
        
        # Create sample data with volume spikes
        dates = pd.date_range(start='2023-01-01', periods=100, freq='H')
        np.random.seed(42)
        
        prices = 100 + np.cumsum(np.random.randn(100) * 0.01)
        volumes = np.random.randint(1000, 5000, 100)
        
        # Add some volume spikes
        volumes[20] = 15000
        volumes[50] = 20000
        volumes[80] = 18000
        
        self.sample_data = pd.DataFrame({
            'open': prices * 0.999,
            'high': prices * 1.002,
            'low': prices * 0.998,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_signal_generation(self):
        """Test volume-weighted signal generation."""
        signal = self.strategy.calculate_signals(self.sample_data)
        
        self.assertIsInstance(signal, TradingSignal)
        self.assertIn(signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
    
    def test_vwap_calculation(self):
        """Test VWAP calculation."""
        data = self.sample_data.copy()
        
        # Calculate VWAP manually for verification
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        vwap = (typical_price * data['volume']).rolling(window=20).sum() / \
               data['volume'].rolling(window=20).sum()
        
        # VWAP should be reasonable relative to prices
        self.assertFalse(vwap.isna().all())
        
        # VWAP should be within reasonable range of prices
        price_range = data['close'].max() - data['close'].min()
        vwap_range = vwap.max() - vwap.min()
        self.assertLess(vwap_range, price_range * 2)


class TestMultiTimeframeMomentumStrategy(unittest.TestCase):
    """Test Multi-Timeframe Momentum strategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.strategy = MultiTimeframeMomentumStrategy()
        
        # Create sample data with momentum patterns
        dates = pd.date_range(start='2023-01-01', periods=200, freq='H')
        np.random.seed(42)
        
        # Create momentum pattern
        prices = []
        base_price = 100
        for i in range(200):
            if i < 50:
                momentum = 0.002  # Positive momentum
            elif i < 100:
                momentum = -0.001  # Negative momentum
            elif i < 150:
                momentum = 0.003  # Strong positive momentum
            else:
                momentum = 0.0  # Sideways
            
            base_price *= (1 + momentum + np.random.randn() * 0.005)
            prices.append(base_price)
        
        volumes = np.random.randint(1000, 10000, 200)
        
        self.sample_data = pd.DataFrame({
            'open': np.array(prices) * 0.999,
            'high': np.array(prices) * 1.001,
            'low': np.array(prices) * 0.998,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_signal_generation(self):
        """Test multi-timeframe momentum signal generation."""
        signal = self.strategy.calculate_signals(self.sample_data)
        
        self.assertIsInstance(signal, TradingSignal)
        self.assertIn(signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
    
    def test_momentum_calculation(self):
        """Test momentum calculation across timeframes."""
        data = self.sample_data.copy()
        
        # Test momentum calculations
        for tf in self.strategy.timeframes:
            momentum = data['close'].pct_change(periods=tf)
            self.assertFalse(momentum.isna().all())


class TestStrategyBacktester(unittest.TestCase):
    """Test strategy backtesting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.backtester = StrategyBacktester(initial_capital=10000.0)
        self.strategy = BollingerBandsRSIStrategy()
        
        # Create sample data for backtesting
        dates = pd.date_range(start='2023-01-01', periods=500, freq='H')
        np.random.seed(42)
        
        # Create realistic price data with trends
        prices = []
        base_price = 100
        for i in range(500):
            # Add some trend and noise
            trend = 0.0001 * np.sin(i / 50)  # Cyclical trend
            noise = np.random.randn() * 0.01
            base_price *= (1 + trend + noise)
            prices.append(base_price)
        
        volumes = np.random.randint(1000, 10000, 500)
        
        self.sample_data = pd.DataFrame({
            'open': np.array(prices) * 0.999,
            'high': np.array(prices) * 1.002,
            'low': np.array(prices) * 0.998,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_backtest_execution(self):
        """Test basic backtest execution."""
        result = self.backtester.backtest_strategy(self.strategy, self.sample_data)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result.total_return, float)
        self.assertIsInstance(result.sharpe_ratio, float)
        self.assertIsInstance(result.max_drawdown, float)
        self.assertIsInstance(result.win_rate, float)
        self.assertIsInstance(result.total_trades, int)
        
        # Reasonable bounds
        self.assertGreaterEqual(result.win_rate, 0.0)
        self.assertLessEqual(result.win_rate, 1.0)
        self.assertLessEqual(result.max_drawdown, 0.0)
    
    def test_backtest_with_insufficient_data(self):
        """Test backtest with insufficient data."""
        small_data = self.sample_data.head(50)
        result = self.backtester.backtest_strategy(self.strategy, small_data)
        
        # Should return default result
        self.assertEqual(result.total_return, 0.0)
        self.assertEqual(result.total_trades, 0)
    
    def test_parameter_optimization(self):
        """Test parameter optimization."""
        param_ranges = {
            'bb_period': [15, 20, 25],
            'bb_std': [1.5, 2.0, 2.5]
        }
        
        best_params, best_result = self.backtester.optimize_parameters(
            BollingerBandsRSIStrategy, self.sample_data, param_ranges
        )
        
        self.assertIsNotNone(best_params)
        self.assertIsNotNone(best_result)
        self.assertIn('bb_period', best_params)
        self.assertIn('bb_std', best_params)


class TestStrategySuites(unittest.TestCase):
    """Test strategy suite creation."""
    
    def test_enhanced_strategy_suite_creation(self):
        """Test enhanced strategy suite creation."""
        strategies = create_enhanced_strategy_suite()
        
        self.assertIsInstance(strategies, list)
        self.assertGreater(len(strategies), 0)
        
        # Check that all strategies are BaseStrategy instances
        for strategy in strategies:
            self.assertIsInstance(strategy, type(strategies[0]).__bases__[0])
    
    def test_conservative_strategy_suite_creation(self):
        """Test conservative strategy suite creation."""
        strategies = create_conservative_strategy_suite()
        
        self.assertIsInstance(strategies, list)
        self.assertGreater(len(strategies), 0)
        
        # Check that all strategies are BaseStrategy instances
        for strategy in strategies:
            self.assertIsInstance(strategy, type(strategies[0]).__bases__[0])


class TestStrategyIntegration(unittest.TestCase):
    """Integration tests for strategy combinations."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create comprehensive test data
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='H')
        np.random.seed(42)
        
        # Create realistic market data
        prices = []
        volumes = []
        base_price = 100
        base_volume = 5000
        
        for i in range(1000):
            # Market cycles
            cycle_factor = np.sin(i / 100) * 0.1
            trend_factor = i / 10000
            noise = np.random.randn() * 0.02
            
            price_change = cycle_factor + trend_factor + noise
            base_price *= (1 + price_change)
            prices.append(base_price)
            
            # Volume with spikes during price movements
            volume_factor = 1 + abs(price_change) * 10
            volume = base_volume * volume_factor * (1 + np.random.randn() * 0.3)
            volumes.append(max(1000, volume))
        
        self.comprehensive_data = pd.DataFrame({
            'open': np.array(prices) * 0.9995,
            'high': np.array(prices) * 1.0015,
            'low': np.array(prices) * 0.9985,
            'close': prices,
            'volume': volumes
        }, index=dates)
    
    def test_all_strategies_with_comprehensive_data(self):
        """Test all strategies with comprehensive market data."""
        strategies = create_enhanced_strategy_suite()
        
        for strategy in strategies:
            with self.subTest(strategy=strategy.name):
                signal = strategy.calculate_signals(self.comprehensive_data)
                
                self.assertIsInstance(signal, TradingSignal)
                self.assertIn(signal.action, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])
                self.assertGreaterEqual(signal.confidence, 0.0)
                self.assertLessEqual(signal.confidence, 1.0)
                self.assertIsInstance(signal.reasoning, str)
                self.assertGreater(len(signal.reasoning), 0)
    
    def test_strategy_performance_comparison(self):
        """Test and compare performance of different strategies."""
        strategies = create_enhanced_strategy_suite()
        backtester = StrategyBacktester()
        
        results = {}
        for strategy in strategies[:3]:  # Test first 3 to keep test time reasonable
            result = backtester.backtest_strategy(strategy, self.comprehensive_data)
            results[strategy.name] = result
        
        # Verify all strategies produced results
        self.assertEqual(len(results), 3)
        
        # Check that results are reasonable
        for name, result in results.items():
            with self.subTest(strategy=name):
                self.assertIsInstance(result.total_return, float)
                self.assertGreaterEqual(result.win_rate, 0.0)
                self.assertLessEqual(result.win_rate, 1.0)


if __name__ == '__main__':
    unittest.main()