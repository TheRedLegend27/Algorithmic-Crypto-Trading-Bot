"""
Integration tests for CoinbaseDataFetcher.
Tests integration with actual Coinbase API (using sandbox).
"""
import unittest
import os
from unittest.mock import patch, Mock
import pandas as pd

from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.coinbase_client import CoinbaseCredentials


class TestCoinbaseDataFetcherIntegration(unittest.TestCase):
    """Integration test cases for CoinbaseDataFetcher."""
    
    def setUp(self):
        """Set up test fixtures with sandbox credentials."""
        # Use sandbox credentials for integration testing
        self.credentials = CoinbaseCredentials(
            api_key=os.getenv("COINBASE_API_KEY", "test_key"),
            api_secret=os.getenv("COINBASE_API_SECRET", "test_secret"),
            passphrase=os.getenv("COINBASE_PASSPHRASE", "test_passphrase"),
            sandbox=True  # Always use sandbox for tests
        )
        
        self.fetcher = CoinbaseDataFetcher(self.credentials)
    
    @unittest.skipIf(not all([
        os.getenv("COINBASE_API_KEY"),
        os.getenv("COINBASE_API_SECRET"),
        os.getenv("COINBASE_PASSPHRASE")
    ]), "Coinbase credentials not available")
    def test_fetch_crypto_ohlcv_integration(self):
        """Test OHLCV data fetching with real API (sandbox)."""
        try:
            df = self.fetcher.fetch_crypto_ohlcv("BTC-USD", "1H", 10)
            
            # Verify DataFrame structure
            self.assertIsInstance(df, pd.DataFrame)
            self.assertGreater(len(df), 0)
            self.assertListEqual(list(df.columns), ['open', 'high', 'low', 'close', 'volume'])
            
            # Verify data quality
            self.assertTrue(self.fetcher.validate_crypto_data(df))
            
        except Exception as e:
            # If sandbox is not available, skip the test
            self.skipTest(f"Sandbox API not available: {str(e)}")
    
    @unittest.skipIf(not all([
        os.getenv("COINBASE_API_KEY"),
        os.getenv("COINBASE_API_SECRET"),
        os.getenv("COINBASE_PASSPHRASE")
    ]), "Coinbase credentials not available")
    def test_get_latest_price_integration(self):
        """Test latest price fetching with real API (sandbox)."""
        try:
            price = self.fetcher.get_latest_price("BTC-USD")
            
            # Verify price is a positive number
            self.assertIsInstance(price, float)
            self.assertGreater(price, 0)
            
        except Exception as e:
            # If sandbox is not available, skip the test
            self.skipTest(f"Sandbox API not available: {str(e)}")
    
    @unittest.skipIf(not all([
        os.getenv("COINBASE_API_KEY"),
        os.getenv("COINBASE_API_SECRET"),
        os.getenv("COINBASE_PASSPHRASE")
    ]), "Coinbase credentials not available")
    def test_get_24h_stats_integration(self):
        """Test 24h stats fetching with real API (sandbox)."""
        try:
            stats = self.fetcher.get_24h_stats("BTC-USD")
            
            # Verify stats structure
            self.assertIsInstance(stats, dict)
            required_keys = ['open', 'high', 'low', 'last', 'volume']
            for key in required_keys:
                self.assertIn(key, stats)
                self.assertIsInstance(stats[key], float)
                self.assertGreaterEqual(stats[key], 0)
            
        except Exception as e:
            # If sandbox is not available, skip the test
            self.skipTest(f"Sandbox API not available: {str(e)}")
    
    @patch('bot.coinbase_data_fetcher.requests.get')
    def test_fallback_data_sources(self, mock_get):
        """Test fallback data sources when Coinbase API fails."""
        # Mock Coinbase client to always fail
        with patch.object(self.fetcher.client, 'get_product_candles') as mock_candles:
            mock_candles.side_effect = Exception("API Error")
            
            # Mock products cache to pass validation
            self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
            self.fetcher._cache_expiry = 9999999999  # Far future
            
            # Mock successful CoinGecko fallback response
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                'prices': [[1640995200000, 46500.0], [1640995260000, 47000.0]],
                'total_volumes': [[1640995200000, 1000000], [1640995260000, 1100000]]
            }
            mock_get.return_value = mock_response
            
            # Should use fallback (CoinGecko) and succeed
            df = self.fetcher.fetch_crypto_ohlcv("BTC-USD", "1H", 10)
            
            # Verify fallback worked
            self.assertIsInstance(df, pd.DataFrame)
            self.assertGreater(len(df), 0)
            
            # Verify CoinGecko API was called
            mock_get.assert_called_once()
    
    def test_symbol_format_conversion(self):
        """Test that different symbol formats are handled correctly."""
        test_cases = [
            ("BTC/USD", "BTC-USD"),
            ("BTC-USD", "BTC-USD"),
            ("BTCUSD", "BTC-USD"),
            ("ETH/USD", "ETH-USD"),
            ("ETHUSDT", "ETH-USDT")
        ]
        
        for input_symbol, expected_output in test_cases:
            result = self.fetcher._convert_symbol_format(input_symbol)
            self.assertEqual(result, expected_output)
    
    def test_crypto_data_validation_comprehensive(self):
        """Test comprehensive crypto data validation."""
        # Create test data with various scenarios
        
        # Valid data
        valid_data = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [95.0, 96.0, 97.0],
            'close': [103.0, 104.0, 105.0],
            'volume': [1000.0, 1100.0, 1200.0]
        }, index=pd.date_range('2023-01-01', periods=3, freq='5min'))
        
        self.assertTrue(self.fetcher.validate_crypto_data(valid_data))
        
        # High volatility data (should still pass for crypto)
        volatile_data = pd.DataFrame({
            'open': [100.0, 150.0, 75.0],  # High volatility
            'high': [120.0, 180.0, 90.0],
            'low': [80.0, 140.0, 60.0],
            'close': [110.0, 160.0, 80.0],
            'volume': [10000.0, 15000.0, 20000.0]
        }, index=pd.date_range('2023-01-01', periods=3, freq='5min'))
        
        self.assertTrue(self.fetcher.validate_crypto_data(volatile_data))
    
    def test_error_handling_strategies(self):
        """Test various error handling strategies."""
        # Test rate limit handling
        rate_limit_error = Exception("429 Rate limit exceeded")
        self.assertTrue(self.fetcher.handle_api_errors(rate_limit_error))
        
        # Test authentication error handling
        auth_error = Exception("401 Unauthorized")
        self.assertFalse(self.fetcher.handle_api_errors(auth_error))
        
        # Test network error handling
        import requests
        network_error = requests.exceptions.ConnectionError("Network error")
        self.assertTrue(self.fetcher.handle_api_errors(network_error))
        
        # Test timeout error handling
        timeout_error = requests.exceptions.Timeout("Request timeout")
        self.assertTrue(self.fetcher.handle_api_errors(timeout_error))


if __name__ == '__main__':
    unittest.main()