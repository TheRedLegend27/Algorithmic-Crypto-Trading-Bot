"""
Unit tests for the enhanced data management system.
Tests data synchronization, caching, indicator calculations, and quality validation.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path

from bot.enhanced_data_manager import (
    EnhancedDataManager, IndicatorEngine, DataCache, CacheConfig,
    MarketData, DataQualityReport, PerformanceMetrics
)


class TestIndicatorEngine(unittest.TestCase):
    """Test cases for the IndicatorEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = IndicatorEngine()
        
        # Create sample OHLCV data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
        np.random.seed(42)  # For reproducible tests
        
        prices = 50000 + np.cumsum(np.random.randn(100) * 100)
        
        self.sample_data = pd.DataFrame({
            'open': prices + np.random.randn(100) * 50,
            'high': prices + np.abs(np.random.randn(100) * 100),
            'low': prices - np.abs(np.random.randn(100) * 100),
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
        
        # Ensure OHLC relationships are valid
        self.sample_data['high'] = np.maximum.reduce([
            self.sample_data['open'], self.sample_data['high'], 
            self.sample_data['low'], self.sample_data['close']
        ])
        self.sample_data['low'] = np.minimum.reduce([
            self.sample_data['open'], self.sample_data['high'], 
            self.sample_data['low'], self.sample_data['close']
        ])
    
    def test_calculate_sma(self):
        """Test Simple Moving Average calculation."""
        sma = self.engine._calculate_sma(self.sample_data, period=20)
        
        self.assertIsInstance(sma, pd.Series)
        self.assertEqual(len(sma), len(self.sample_data))
        
        # First 19 values should be NaN
        self.assertTrue(sma.iloc[:19].isna().all())
        
        # 20th value should be the mean of first 20 close prices
        expected_sma_20 = self.sample_data['close'].iloc[:20].mean()
        self.assertAlmostEqual(sma.iloc[19], expected_sma_20, places=2)
    
    def test_calculate_ema(self):
        """Test Exponential Moving Average calculation."""
        ema = self.engine._calculate_ema(self.sample_data, period=20)
        
        self.assertIsInstance(ema, pd.Series)
        self.assertEqual(len(ema), len(self.sample_data))
        
        # EMA should not have NaN values (except possibly the first)
        self.assertFalse(ema.iloc[1:].isna().any())
    
    def test_calculate_rsi(self):
        """Test Relative Strength Index calculation."""
        rsi = self.engine._calculate_rsi(self.sample_data, period=14)
        
        self.assertIsInstance(rsi, pd.Series)
        self.assertEqual(len(rsi), len(self.sample_data))
        
        # RSI values should be between 0 and 100
        valid_rsi = rsi.dropna()
        self.assertTrue((valid_rsi >= 0).all())
        self.assertTrue((valid_rsi <= 100).all())
    
    def test_calculate_macd(self):
        """Test MACD calculation."""
        macd_result = self.engine._calculate_macd(self.sample_data)
        
        self.assertIsInstance(macd_result, dict)
        self.assertIn('macd', macd_result)
        self.assertIn('signal', macd_result)
        self.assertIn('histogram', macd_result)
        
        for key, series in macd_result.items():
            self.assertIsInstance(series, pd.Series)
            self.assertEqual(len(series), len(self.sample_data))
    
    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation."""
        bb_result = self.engine._calculate_bollinger_bands(self.sample_data)
        
        self.assertIsInstance(bb_result, dict)
        self.assertIn('upper', bb_result)
        self.assertIn('middle', bb_result)
        self.assertIn('lower', bb_result)
        
        # Upper band should be above middle, middle above lower
        valid_data = ~bb_result['upper'].isna()
        self.assertTrue((bb_result['upper'][valid_data] >= bb_result['middle'][valid_data]).all())
        self.assertTrue((bb_result['middle'][valid_data] >= bb_result['lower'][valid_data]).all())
    
    def test_calculate_atr(self):
        """Test Average True Range calculation."""
        atr = self.engine._calculate_atr(self.sample_data, period=14)
        
        self.assertIsInstance(atr, pd.Series)
        self.assertEqual(len(atr), len(self.sample_data))
        
        # ATR should be positive
        valid_atr = atr.dropna()
        self.assertTrue((valid_atr >= 0).all())
    
    def test_calculate_indicators_multiple(self):
        """Test calculating multiple indicators at once."""
        indicators = ['sma', 'ema', 'rsi', 'macd']
        results = self.engine.calculate_indicators(self.sample_data, indicators)
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), len(indicators))
        
        for indicator in indicators:
            self.assertIn(indicator, results)
            self.assertIsNotNone(results[indicator])
    
    def test_calculate_indicators_unknown(self):
        """Test handling of unknown indicators."""
        indicators = ['unknown_indicator', 'sma']
        results = self.engine.calculate_indicators(self.sample_data, indicators)
        
        self.assertIn('sma', results)
        self.assertIsNotNone(results['sma'])
        # Unknown indicator should not be in results
        self.assertNotIn('unknown_indicator', results)


class TestDataCache(unittest.TestCase):
    """Test cases for the DataCache class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            enabled=True,
            max_memory_mb=1,  # Small limit for testing
            retention_hours=1,
            persist_to_disk=True,
            cache_directory=self.temp_dir,
            cleanup_interval_minutes=1
        )
        self.cache = DataCache(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_cache_set_get(self):
        """Test basic cache set and get operations."""
        test_data = {'price': 50000, 'volume': 1000}
        
        # Set data
        result = self.cache.set('BTC/USD', 'test_data', test_data)
        self.assertTrue(result)
        
        # Get data
        retrieved_data = self.cache.get('BTC/USD', 'test_data')
        self.assertEqual(retrieved_data, test_data)
    
    def test_cache_miss(self):
        """Test cache miss scenario."""
        result = self.cache.get('BTC/USD', 'nonexistent_key')
        self.assertIsNone(result)
    
    def test_cache_dataframe(self):
        """Test caching DataFrame objects."""
        df = pd.DataFrame({
            'price': [50000, 51000, 49000],
            'volume': [1000, 1100, 900]
        })
        
        # Set DataFrame
        result = self.cache.set('BTC/USD', 'price_data_df', df)
        self.assertTrue(result)
        
        # Get DataFrame
        retrieved_df = self.cache.get('BTC/USD', 'price_data_df')
        pd.testing.assert_frame_equal(retrieved_df, df)
    
    def test_cache_stats(self):
        """Test cache statistics."""
        # Add some data
        self.cache.set('BTC/USD', 'data1', {'value': 1})
        self.cache.set('ETH/USD', 'data2', {'value': 2})
        
        stats = self.cache.get_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_entries', stats)
        self.assertIn('memory_usage_mb', stats)
        self.assertEqual(stats['total_entries'], 2)
        self.assertGreater(stats['memory_usage_mb'], 0)


class TestEnhancedDataManager(unittest.TestCase):
    """Test cases for the EnhancedDataManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pairs = ['BTC/USD', 'ETH/USD']
        self.temp_dir = tempfile.mkdtemp()
        
        self.cache_config = CacheConfig(
            enabled=True,
            max_memory_mb=10,
            retention_hours=1,
            persist_to_disk=False,  # Disable disk persistence for tests
            cache_directory=self.temp_dir
        )
        
        # Mock the data fetcher
        self.mock_data_fetcher = Mock()
        
        # Create sample DataFrame
        dates = pd.date_range(start='2024-01-01', periods=50, freq='5min')
        self.sample_df = pd.DataFrame({
            'open': np.random.uniform(49000, 51000, 50),
            'high': np.random.uniform(50000, 52000, 50),
            'low': np.random.uniform(48000, 50000, 50),
            'close': np.random.uniform(49000, 51000, 50),
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)
        
        # Ensure OHLC relationships are valid
        self.sample_df['high'] = np.maximum.reduce([
            self.sample_df['open'], self.sample_df['high'], 
            self.sample_df['low'], self.sample_df['close']
        ])
        self.sample_df['low'] = np.minimum.reduce([
            self.sample_df['open'], self.sample_df['high'], 
            self.sample_df['low'], self.sample_df['close']
        ])
        
        self.mock_data_fetcher.fetch_crypto_data.return_value = self.sample_df
        
        # Create data manager with mocked fetcher
        with patch('bot.enhanced_data_manager.DataFetcher', return_value=self.mock_data_fetcher):
            self.data_manager = EnhancedDataManager(self.pairs, self.cache_config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.data_manager.cleanup()
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test data manager initialization."""
        self.assertEqual(self.data_manager.pairs, self.pairs)
        self.assertIsNotNone(self.data_manager.cache)
        self.assertIsNotNone(self.data_manager.indicator_engine)
        self.assertEqual(len(self.data_manager._market_data), len(self.pairs))
    
    def test_add_market_data(self):
        """Test adding market data."""
        market_data = MarketData(
            pair='BTC/USD',
            timestamp=datetime.now(),
            price=50000.0,
            volume=1000.0,
            bid=49950.0,
            ask=50050.0,
            spread=100.0
        )
        
        self.data_manager.add_market_data('BTC/USD', market_data)
        
        # Check that data was added
        self.assertEqual(len(self.data_manager._market_data['BTC/USD']), 1)
        self.assertEqual(self.data_manager._market_data['BTC/USD'][0], market_data)
    
    def test_get_latest_data(self):
        """Test getting latest market data."""
        result = self.data_manager.get_latest_data('BTC/USD', periods=50)
        
        # Verify data fetcher was called
        self.mock_data_fetcher.fetch_crypto_data.assert_called_with('BTC/USD', timeframe="5Min", limit=50)
        
        # Verify result
        pd.testing.assert_frame_equal(result, self.sample_df)
    
    def test_get_latest_data_cached(self):
        """Test getting cached latest data."""
        # First call
        result1 = self.data_manager.get_latest_data('BTC/USD', periods=50)
        
        # Second call should use cache
        result2 = self.data_manager.get_latest_data('BTC/USD', periods=50)
        
        # Data fetcher should only be called once
        self.assertEqual(self.mock_data_fetcher.fetch_crypto_data.call_count, 1)
        
        # Results should be the same
        pd.testing.assert_frame_equal(result1, result2)
    
    def test_get_historical_data(self):
        """Test getting historical market data."""
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 2)
        
        result = self.data_manager.get_historical_data('BTC/USD', start_time, end_time)
        
        # Verify data fetcher was called
        self.mock_data_fetcher.fetch_crypto_data.assert_called()
        
        # Result should be a DataFrame
        self.assertIsInstance(result, pd.DataFrame)
    
    def test_calculate_indicators(self):
        """Test calculating technical indicators."""
        indicators = ['sma', 'ema', 'rsi']
        
        result = self.data_manager.calculate_indicators('BTC/USD', indicators)
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        for indicator in indicators:
            self.assertIn(indicator, result)
    
    def test_validate_data_quality_valid(self):
        """Test data quality validation with valid data."""
        quality_report = self.data_manager.validate_data_quality(self.sample_df)
        
        self.assertIsInstance(quality_report, DataQualityReport)
        self.assertTrue(quality_report.is_valid)
        self.assertGreater(quality_report.quality_score, 0.9)
        self.assertEqual(quality_report.total_points, len(self.sample_df))
        self.assertEqual(quality_report.invalid_ohlc_points, 0)
        self.assertEqual(quality_report.negative_values, 0)
    
    def test_validate_data_quality_invalid(self):
        """Test data quality validation with invalid data."""
        # Create invalid data
        invalid_df = self.sample_df.copy()
        invalid_df.loc[invalid_df.index[0], 'high'] = -1000  # Negative price
        invalid_df.loc[invalid_df.index[1], 'low'] = invalid_df.loc[invalid_df.index[1], 'high'] + 100  # Low > High
        
        quality_report = self.data_manager.validate_data_quality(invalid_df)
        
        self.assertIsInstance(quality_report, DataQualityReport)
        self.assertFalse(quality_report.is_valid)
        self.assertLess(quality_report.quality_score, 0.9)
        self.assertGreater(len(quality_report.issues), 0)
        self.assertGreater(quality_report.negative_values, 0)
        self.assertGreater(quality_report.invalid_ohlc_points, 0)
    
    def test_validate_data_quality_empty(self):
        """Test data quality validation with empty data."""
        empty_df = pd.DataFrame()
        quality_report = self.data_manager.validate_data_quality(empty_df)
        
        self.assertFalse(quality_report.is_valid)
        self.assertEqual(quality_report.quality_score, 0.0)
        self.assertIn("Empty dataset", quality_report.issues)
    
    def test_calculate_performance_metrics(self):
        """Test performance metrics calculation."""
        # Add some data first
        self.data_manager.get_latest_data('BTC/USD', periods=50)
        
        metrics = self.data_manager.calculate_performance_metrics()
        
        self.assertIsInstance(metrics, PerformanceMetrics)
        self.assertGreaterEqual(metrics.memory_usage_mb, 0)
        self.assertEqual(metrics.active_pairs, len(self.pairs))
        self.assertIsInstance(metrics.last_updated, datetime)
    
    def test_get_pair_summary(self):
        """Test getting pair summary information."""
        # Add some data first
        self.data_manager.get_latest_data('BTC/USD', periods=50)
        
        summary = self.data_manager.get_pair_summary('BTC/USD')
        
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary['pair'], 'BTC/USD')
        self.assertIn('latest_data_points', summary)
        self.assertIn('last_price', summary)
        self.assertIn('data_quality', summary)
    
    def test_get_system_status(self):
        """Test getting system status."""
        status = self.data_manager.get_system_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('active_pairs', status)
        self.assertIn('performance_metrics', status)
        self.assertIn('pair_summaries', status)
        self.assertEqual(status['active_pairs'], len(self.pairs))
    
    def test_add_trading_pair(self):
        """Test adding a new trading pair."""
        new_pair = 'SOL/USD'
        result = self.data_manager.add_trading_pair(new_pair)
        
        self.assertTrue(result)
        self.assertIn(new_pair, self.data_manager.pairs)
        self.assertIn(new_pair, self.data_manager._market_data)
    
    def test_add_existing_trading_pair(self):
        """Test adding an existing trading pair."""
        result = self.data_manager.add_trading_pair('BTC/USD')
        
        self.assertFalse(result)  # Should return False for existing pair
    
    def test_remove_trading_pair(self):
        """Test removing a trading pair."""
        result = self.data_manager.remove_trading_pair('BTC/USD')
        
        self.assertTrue(result)
        self.assertNotIn('BTC/USD', self.data_manager.pairs)
        self.assertNotIn('BTC/USD', self.data_manager._market_data)
    
    def test_remove_nonexistent_trading_pair(self):
        """Test removing a non-existent trading pair."""
        result = self.data_manager.remove_trading_pair('NONEXISTENT/USD')
        
        self.assertFalse(result)  # Should return False for non-existent pair
    
    def test_sync_all_pairs(self):
        """Test synchronizing all trading pairs."""
        results = self.data_manager.sync_all_pairs()
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), len(self.pairs))
        
        for pair in self.pairs:
            self.assertIn(pair, results)
            self.assertTrue(results[pair])  # Should be True since mock returns valid data
    
    def test_error_handling_fetch_failure(self):
        """Test error handling when data fetch fails."""
        # Make data fetcher raise an exception
        self.mock_data_fetcher.fetch_crypto_data.side_effect = Exception("API Error")
        
        result = self.data_manager.get_latest_data('BTC/USD', periods=50)
        
        # Should return empty DataFrame on error
        self.assertTrue(result.empty)
        self.assertListEqual(list(result.columns), ['open', 'high', 'low', 'close', 'volume'])


if __name__ == '__main__':
    unittest.main()