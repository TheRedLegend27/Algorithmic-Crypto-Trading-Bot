"""
Integration tests for the enhanced data management system.
Tests real API interactions, caching behavior, and system integration.
"""
import unittest
from unittest.mock import patch, Mock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import shutil
import time
import threading

from bot.enhanced_data_manager import (
    EnhancedDataManager, CacheConfig, MarketData
)
from bot.config import Config


class TestEnhancedDataManagerIntegration(unittest.TestCase):
    """Integration tests for EnhancedDataManager with real-world scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pairs = ['XBTUSD', 'ETHUSD']  # Kraken format
        self.temp_dir = tempfile.mkdtemp()
        
        self.cache_config = CacheConfig(
            enabled=True,
            max_memory_mb=50,
            retention_hours=2,
            persist_to_disk=True,
            cache_directory=self.temp_dir,
            cleanup_interval_minutes=1
        )
        
        # Create data manager
        self.data_manager = EnhancedDataManager(self.pairs, self.cache_config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.data_manager.cleanup()
        shutil.rmtree(self.temp_dir)
    
    @patch('bot.data_fetcher.requests.get')
    def test_real_data_fetch_and_cache(self, mock_get):
        """Test fetching real data and caching behavior."""
        # Mock Kraken API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'error': [],
            'result': {
                'XXBTZUSD': [
                    [1640995200, '50000.0', '50100.0', '49900.0', '50050.0', '50025.0', '100.5', 50],
                    [1640995500, '50050.0', '50150.0', '49950.0', '50100.0', '50075.0', '120.3', 60],
                    [1640995800, '50100.0', '50200.0', '50000.0', '50150.0', '50125.0', '110.8', 55]
                ],
                'last': 1640995800
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # First fetch - should hit API
        start_time = time.time()
        data1 = self.data_manager.get_latest_data('XBTUSD', periods=50)
        fetch_time1 = time.time() - start_time
        
        self.assertFalse(data1.empty)
        self.assertEqual(len(data1), 3)
        self.assertIn('close', data1.columns)
        
        # Second fetch - should use cache
        start_time = time.time()
        data2 = self.data_manager.get_latest_data('XBTUSD', periods=50)
        fetch_time2 = time.time() - start_time
        
        # Cache should be faster
        self.assertLess(fetch_time2, fetch_time1)
        pd.testing.assert_frame_equal(data1, data2)
        
        # Verify cache hit rate improved
        metrics = self.data_manager.calculate_performance_metrics()
        self.assertGreater(metrics.cache_hit_rate, 0)
    
    def test_multi_pair_synchronization(self):
        """Test synchronizing data for multiple trading pairs."""
        with patch.object(self.data_manager.data_fetcher, 'fetch_crypto_data') as mock_fetch:
            # Create different data for each pair
            btc_data = self._create_sample_data(50000, 100)
            eth_data = self._create_sample_data(3000, 100)
            
            def side_effect(pair, **kwargs):
                if 'XBT' in pair:
                    return btc_data
                elif 'ETH' in pair:
                    return eth_data
                else:
                    return pd.DataFrame()
            
            mock_fetch.side_effect = side_effect
            
            # Sync all pairs
            results = self.data_manager.sync_all_pairs()
            
            # Verify all pairs were synced
            self.assertEqual(len(results), len(self.pairs))
            for pair in self.pairs:
                self.assertTrue(results[pair])
            
            # Verify data was stored
            for pair in self.pairs:
                summary = self.data_manager.get_pair_summary(pair)
                self.assertGreater(summary['latest_data_points'], 0)
                self.assertIsNotNone(summary['last_price'])
    
    def test_indicator_calculation_performance(self):
        """Test performance of indicator calculations with large datasets."""
        with patch.object(self.data_manager.data_fetcher, 'fetch_crypto_data') as mock_fetch:
            # Create large dataset
            large_data = self._create_sample_data(50000, 1000)  # 1000 data points
            mock_fetch.return_value = large_data
            
            indicators = ['sma', 'ema', 'rsi', 'macd', 'bollinger_bands', 'atr']
            
            start_time = time.time()
            results = self.data_manager.calculate_indicators('XBTUSD', indicators)
            calc_time = time.time() - start_time
            
            # Verify all indicators were calculated
            self.assertEqual(len(results), len(indicators))
            for indicator in indicators:
                self.assertIn(indicator, results)
                self.assertIsNotNone(results[indicator])
            
            # Performance should be reasonable (less than 5 seconds for 1000 points)
            self.assertLess(calc_time, 5.0)
            
            # Check performance metrics
            metrics = self.data_manager.calculate_performance_metrics()
            self.assertGreater(metrics.indicator_calculation_time_ms, 0)
    
    def test_data_quality_validation_scenarios(self):
        """Test data quality validation with various data scenarios."""
        test_scenarios = [
            # Valid data
            {
                'name': 'valid_data',
                'data': self._create_sample_data(50000, 100),
                'expected_valid': True
            },
            # Data with missing values
            {
                'name': 'missing_values',
                'data': self._create_data_with_missing_values(),
                'expected_valid': False
            },
            # Data with invalid OHLC relationships
            {
                'name': 'invalid_ohlc',
                'data': self._create_data_with_invalid_ohlc(),
                'expected_valid': False
            },
            # Data with negative values
            {
                'name': 'negative_values',
                'data': self._create_data_with_negative_values(),
                'expected_valid': False
            }
        ]
        
        for scenario in test_scenarios:
            with self.subTest(scenario=scenario['name']):
                quality_report = self.data_manager.validate_data_quality(scenario['data'])
                
                self.assertEqual(quality_report.is_valid, scenario['expected_valid'])
                if not scenario['expected_valid']:
                    self.assertGreater(len(quality_report.issues), 0)
                    self.assertLess(quality_report.quality_score, 0.95)
    
    def test_concurrent_data_access(self):
        """Test concurrent access to data manager from multiple threads."""
        with patch.object(self.data_manager.data_fetcher, 'fetch_crypto_data') as mock_fetch:
            mock_fetch.return_value = self._create_sample_data(50000, 100)
            
            results = []
            errors = []
            
            def worker_thread(pair, thread_id):
                try:
                    # Each thread performs multiple operations
                    for i in range(5):
                        data = self.data_manager.get_latest_data(pair, periods=50)
                        indicators = self.data_manager.calculate_indicators(pair, ['sma', 'rsi'])
                        quality = self.data_manager.validate_data_quality(data)
                        
                        results.append({
                            'thread_id': thread_id,
                            'iteration': i,
                            'data_points': len(data),
                            'indicators': len(indicators),
                            'quality_score': quality.quality_score
                        })
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {str(e)}")
            
            # Start multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=worker_thread, args=('XBTUSD', i))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=10)
            
            # Verify no errors occurred
            self.assertEqual(len(errors), 0, f"Errors in concurrent access: {errors}")
            
            # Verify all threads completed successfully
            self.assertEqual(len(results), 25)  # 5 threads * 5 iterations
            
            # Verify data consistency
            for result in results:
                self.assertGreater(result['data_points'], 0)
                self.assertGreaterEqual(result['indicators'], 0)
                self.assertGreaterEqual(result['quality_score'], 0)
    
    def test_memory_management_under_load(self):
        """Test memory management with high data volume."""
        with patch.object(self.data_manager.data_fetcher, 'fetch_crypto_data') as mock_fetch:
            # Simulate high-frequency data updates
            for i in range(100):
                # Create new data for each iteration
                data = self._create_sample_data(50000 + i * 10, 200)
                mock_fetch.return_value = data
                
                # Fetch data for multiple pairs
                for pair in self.pairs:
                    self.data_manager.get_latest_data(pair, periods=200)
                    
                    # Add market data
                    market_data = MarketData(
                        pair=pair,
                        timestamp=datetime.now(),
                        price=50000 + i * 10,
                        volume=1000,
                        bid=50000 + i * 10 - 5,
                        ask=50000 + i * 10 + 5,
                        spread=10
                    )
                    self.data_manager.add_market_data(pair, market_data)
            
            # Check memory usage
            metrics = self.data_manager.calculate_performance_metrics()
            
            # Memory usage should be reasonable (less than cache limit)
            self.assertLess(metrics.memory_usage_mb, self.cache_config.max_memory_mb * 2)
            
            # System should still be responsive
            status = self.data_manager.get_system_status()
            self.assertIsInstance(status, dict)
            self.assertEqual(status['active_pairs'], len(self.pairs))
    
    def test_cache_persistence_and_recovery(self):
        """Test cache persistence to disk and recovery."""
        if not self.cache_config.persist_to_disk:
            self.skipTest("Disk persistence disabled")
        
        with patch.object(self.data_manager.data_fetcher, 'fetch_crypto_data') as mock_fetch:
            test_data = self._create_sample_data(50000, 100)
            mock_fetch.return_value = test_data
            
            # Fetch data to populate cache
            original_data = self.data_manager.get_latest_data('XBTUSD', periods=100)
            
            # Verify cache files were created
            from pathlib import Path
            cache_files = list(Path(self.temp_dir).glob('*.json'))
            self.assertGreater(len(cache_files), 0)
            
            # Create new data manager with same cache directory
            new_data_manager = EnhancedDataManager(self.pairs, self.cache_config)
            
            # Should be able to retrieve cached data
            cached_data = new_data_manager.cache.get('XBTUSD', 'latest_data_100')
            if cached_data is not None:
                pd.testing.assert_frame_equal(cached_data, original_data)
            
            new_data_manager.cleanup()
    
    def test_error_recovery_and_fallback(self):
        """Test error recovery and fallback mechanisms."""
        with patch.object(self.data_manager.data_fetcher, 'fetch_crypto_data') as mock_fetch:
            # First call succeeds
            good_data = self._create_sample_data(50000, 100)
            mock_fetch.return_value = good_data
            
            data1 = self.data_manager.get_latest_data('XBTUSD', periods=100)
            self.assertFalse(data1.empty)
            
            # Second call fails
            mock_fetch.side_effect = Exception("API Error")
            
            data2 = self.data_manager.get_latest_data('XBTUSD', periods=100)
            
            # Should return empty DataFrame on error
            self.assertTrue(data2.empty)
            
            # System should still be functional
            status = self.data_manager.get_system_status()
            self.assertIsInstance(status, dict)
    
    def _create_sample_data(self, base_price: float, num_points: int) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(start='2024-01-01', periods=num_points, freq='5min')
        
        # Generate realistic price movements
        np.random.seed(42)
        price_changes = np.random.normal(0, base_price * 0.001, num_points)
        prices = base_price + np.cumsum(price_changes)
        
        # Create OHLCV data
        data = pd.DataFrame({
            'open': prices + np.random.normal(0, base_price * 0.0005, num_points),
            'high': prices + np.abs(np.random.normal(0, base_price * 0.001, num_points)),
            'low': prices - np.abs(np.random.normal(0, base_price * 0.001, num_points)),
            'close': prices,
            'volume': np.random.randint(100, 1000, num_points)
        }, index=dates)
        
        # Ensure OHLC relationships are valid
        data['high'] = np.maximum.reduce([
            data['open'], data['high'], data['low'], data['close']
        ])
        data['low'] = np.minimum.reduce([
            data['open'], data['high'], data['low'], data['close']
        ])
        
        return data
    
    def _create_data_with_missing_values(self) -> pd.DataFrame:
        """Create data with missing values for testing."""
        data = self._create_sample_data(50000, 50)
        
        # Introduce missing values
        data.loc[data.index[5:10], 'close'] = np.nan
        data.loc[data.index[15:20], 'volume'] = np.nan
        
        return data
    
    def _create_data_with_invalid_ohlc(self) -> pd.DataFrame:
        """Create data with invalid OHLC relationships for testing."""
        data = self._create_sample_data(50000, 50)
        
        # Make some high values lower than low values
        data.loc[data.index[5], 'high'] = data.loc[data.index[5], 'low'] - 100
        data.loc[data.index[10], 'low'] = data.loc[data.index[10], 'high'] + 100
        
        return data
    
    def _create_data_with_negative_values(self) -> pd.DataFrame:
        """Create data with negative values for testing."""
        data = self._create_sample_data(50000, 50)
        
        # Introduce negative values
        data.loc[data.index[5], 'close'] = -1000
        data.loc[data.index[10], 'volume'] = -500
        
        return data


if __name__ == '__main__':
    unittest.main()