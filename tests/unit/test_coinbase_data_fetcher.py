"""
Unit tests for CoinbaseDataFetcher class.
Tests data fetching, validation, and error handling functionality.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta
import requests
import time

from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.coinbase_client import CoinbaseCredentials


class TestCoinbaseDataFetcher(unittest.TestCase):
    """Test cases for CoinbaseDataFetcher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
        
        # Mock the CoinbaseClient
        with patch('bot.coinbase_data_fetcher.CoinbaseClient') as mock_client_class:
            self.mock_client = Mock()
            mock_client_class.return_value = self.mock_client
            self.fetcher = CoinbaseDataFetcher(self.credentials)
    
    def test_init(self):
        """Test CoinbaseDataFetcher initialization."""
        self.assertEqual(self.fetcher.credentials, self.credentials)
        self.assertIsNotNone(self.fetcher.client)
        self.assertEqual(self.fetcher.rate_limit_wait, 0.1)
        self.assertEqual(self.fetcher._cache_ttl, 300)
    
    def test_convert_symbol_format(self):
        """Test symbol format conversion."""
        # Test BTC/USD -> BTC-USD
        self.assertEqual(self.fetcher._convert_symbol_format("BTC/USD"), "BTC-USD")
        
        # Test BTC-USD (already correct)
        self.assertEqual(self.fetcher._convert_symbol_format("BTC-USD"), "BTC-USD")
        
        # Test BTCUSD -> BTC-USD
        self.assertEqual(self.fetcher._convert_symbol_format("BTCUSD"), "BTC-USD")
        
        # Test BTCUSDT -> BTC-USDT
        self.assertEqual(self.fetcher._convert_symbol_format("BTCUSDT"), "BTC-USDT")
        
        # Test ETH -> ETH-USD (default)
        self.assertEqual(self.fetcher._convert_symbol_format("ETH"), "ETH-USD")
    
    def test_granularity_to_seconds(self):
        """Test timeframe to granularity conversion."""
        self.assertEqual(self.fetcher._granularity_to_seconds("1Min"), 60)
        self.assertEqual(self.fetcher._granularity_to_seconds("5Min"), 300)
        self.assertEqual(self.fetcher._granularity_to_seconds("15Min"), 900)
        self.assertEqual(self.fetcher._granularity_to_seconds("1H"), 3600)
        self.assertEqual(self.fetcher._granularity_to_seconds("1D"), 86400)
        self.assertEqual(self.fetcher._granularity_to_seconds("invalid"), 300)  # Default
    
    def test_calculate_time_range(self):
        """Test time range calculation."""
        with patch('bot.coinbase_data_fetcher.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = mock_now
            
            start, end = self.fetcher._calculate_time_range("1H", 24)
            
            # Should calculate 24 hours back
            expected_start = mock_now - timedelta(hours=24)
            self.assertTrue(start.startswith(expected_start.isoformat()[:16]))  # Check first 16 chars
            self.assertTrue(end.startswith(mock_now.isoformat()[:16]))
    
    def test_validate_product_id_with_cache(self):
        """Test product ID validation with caching."""
        # Mock products cache
        self.fetcher._products_cache = {
            'BTC-USD': {'id': 'BTC-USD', 'base_currency': 'BTC'},
            'ETH-USD': {'id': 'ETH-USD', 'base_currency': 'ETH'}
        }
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300  # Valid cache
        
        # Test valid product
        self.assertTrue(self.fetcher._validate_product_id('BTC-USD'))
        
        # Test invalid product
        self.assertFalse(self.fetcher._validate_product_id('INVALID-USD'))
    
    def test_get_products_cache_refresh(self):
        """Test products cache refresh when expired."""
        # Set expired cache
        self.fetcher._cache_expiry = 0
        
        # Mock API response
        mock_products = [
            {'id': 'BTC-USD', 'base_currency': 'BTC'},
            {'id': 'ETH-USD', 'base_currency': 'ETH'}
        ]
        self.mock_client.get_products.return_value = mock_products
        
        # Get cache (should refresh)
        cache = self.fetcher._get_products_cache()
        
        # Verify API was called and cache was updated
        self.mock_client.get_products.assert_called_once()
        self.assertEqual(len(cache), 2)
        self.assertIn('BTC-USD', cache)
        self.assertIn('ETH-USD', cache)
    
    def test_candles_to_dataframe(self):
        """Test conversion of Coinbase candle data to DataFrame."""
        # Mock candle data: [timestamp, low, high, open, close, volume]
        mock_candles = [
            [1640995200, 46000.0, 47000.0, 46500.0, 46800.0, 1.5],
            [1640995260, 46800.0, 47200.0, 46800.0, 47000.0, 2.1]
        ]
        
        df = self.fetcher._candles_to_dataframe(mock_candles)
        
        # Verify DataFrame structure
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ['open', 'high', 'low', 'close', 'volume'])
        
        # Verify data values
        self.assertEqual(df.iloc[0]['open'], 46500.0)
        self.assertEqual(df.iloc[0]['high'], 47000.0)
        self.assertEqual(df.iloc[0]['low'], 46000.0)
        self.assertEqual(df.iloc[0]['close'], 46800.0)
        self.assertEqual(df.iloc[0]['volume'], 1.5)
    
    def test_fetch_crypto_ohlcv_success(self):
        """Test successful OHLCV data fetching."""
        # Mock products cache
        self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Mock candle data
        mock_candles = [
            [1640995200, 46000.0, 47000.0, 46500.0, 46800.0, 1.5],
            [1640995260, 46800.0, 47200.0, 46800.0, 47000.0, 2.1]
        ]
        self.mock_client.get_product_candles.return_value = mock_candles
        
        # Fetch data
        df = self.fetcher.fetch_crypto_ohlcv("BTC/USD", "5Min", 50)
        
        # Verify result
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ['open', 'high', 'low', 'close', 'volume'])
        
        # Verify API was called with correct parameters
        self.mock_client.get_product_candles.assert_called_once()
        call_args = self.mock_client.get_product_candles.call_args
        self.assertEqual(call_args[1]['product_id'], 'BTC-USD')
        self.assertEqual(call_args[1]['granularity'], 300)  # 5Min = 300 seconds
    
    def test_fetch_crypto_ohlcv_invalid_product(self):
        """Test OHLCV fetching with invalid product."""
        # Mock empty products cache
        self.fetcher._products_cache = {}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Should raise ValueError for invalid product
        with self.assertRaises(ValueError) as context:
            self.fetcher.fetch_crypto_ohlcv("INVALID/USD", "5Min", 50)
        
        self.assertIn("Invalid product ID", str(context.exception))
    
    @patch('bot.coinbase_data_fetcher.requests.get')
    def test_fetch_crypto_ohlcv_with_fallback(self, mock_get):
        """Test OHLCV fetching with fallback when Coinbase fails."""
        # Mock products cache
        self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Mock Coinbase API failure
        self.mock_client.get_product_candles.side_effect = Exception("API Error")
        
        # Mock CoinGecko fallback response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'prices': [[1640995200000, 46500.0], [1640995260000, 47000.0]],
            'total_volumes': [[1640995200000, 1000000], [1640995260000, 1100000]]
        }
        mock_get.return_value = mock_response
        
        # Fetch data (should use fallback)
        df = self.fetcher.fetch_crypto_ohlcv("BTC/USD", "5Min", 50)
        
        # Verify fallback was used
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)
        mock_get.assert_called_once()
    
    def test_get_latest_price_success(self):
        """Test successful latest price fetching."""
        # Mock products cache
        self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Mock ticker response
        mock_ticker = {'price': '46500.00', 'bid': '46450.00', 'ask': '46550.00'}
        self.mock_client.get_product_ticker.return_value = mock_ticker
        
        # Get latest price
        price = self.fetcher.get_latest_price("BTC/USD")
        
        # Verify result
        self.assertEqual(price, 46500.0)
        self.mock_client.get_product_ticker.assert_called_once_with('BTC-USD')
    
    @patch('bot.coinbase_data_fetcher.requests.get')
    def test_get_latest_price_no_price_data(self, mock_get):
        """Test latest price fetching when no price data in response."""
        # Mock products cache
        self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Mock ticker response without price
        mock_ticker = {'bid': '46450.00', 'ask': '46550.00'}
        self.mock_client.get_product_ticker.return_value = mock_ticker
        
        # Mock fallback to also fail
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("Fallback failed")
        mock_get.return_value = mock_response
        
        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.fetcher.get_latest_price("BTC/USD")
        
        self.assertIn("Failed to get latest price", str(context.exception))
    
    @patch('bot.coinbase_data_fetcher.requests.get')
    def test_get_latest_price_with_fallback(self, mock_get):
        """Test latest price fetching with fallback."""
        # Mock products cache
        self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Mock Coinbase API failure
        self.mock_client.get_product_ticker.side_effect = Exception("API Error")
        
        # Mock CoinGecko fallback response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'bitcoin': {'usd': 46500.0}}
        mock_get.return_value = mock_response
        
        # Get latest price (should use fallback)
        price = self.fetcher.get_latest_price("BTC/USD")
        
        # Verify fallback was used
        self.assertEqual(price, 46500.0)
        mock_get.assert_called_once()
    
    def test_get_24h_stats_success(self):
        """Test successful 24h stats fetching."""
        # Mock products cache
        self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Mock stats response
        mock_stats = {
            'open': '45000.00',
            'high': '47000.00',
            'low': '44000.00',
            'last': '46500.00',
            'volume': '1234.56',
            'volume_30day': '123456.78'
        }
        self.mock_client.get_product_stats.return_value = mock_stats
        
        # Get 24h stats
        stats = self.fetcher.get_24h_stats("BTC/USD")
        
        # Verify result
        expected_stats = {
            'open': 45000.0,
            'high': 47000.0,
            'low': 44000.0,
            'last': 46500.0,
            'volume': 1234.56,
            'volume_30day': 123456.78
        }
        self.assertEqual(stats, expected_stats)
        self.mock_client.get_product_stats.assert_called_once_with('BTC-USD')
    
    def test_get_order_book_success(self):
        """Test successful order book fetching."""
        # Mock products cache
        self.fetcher._products_cache = {'BTC-USD': {'id': 'BTC-USD'}}
        self.fetcher._cache_expiry = datetime.now().timestamp() + 300
        
        # Mock ticker response (simplified order book)
        mock_ticker = {
            'price': '46500.00',
            'bid': '46450.00',
            'ask': '46550.00',
            'bid_size': '1.5',
            'ask_size': '2.0',
            'trade_id': '12345'
        }
        self.mock_client.get_product_ticker.return_value = mock_ticker
        
        # Get order book
        order_book = self.fetcher.get_order_book("BTC/USD")
        
        # Verify result
        self.assertIn('sequence', order_book)
        self.assertIn('bids', order_book)
        self.assertIn('asks', order_book)
        self.assertEqual(order_book['sequence'], 12345)
        self.assertEqual(order_book['bids'], [['46450.00', '1.5']])
        self.assertEqual(order_book['asks'], [['46550.00', '2.0']])
    
    def test_validate_crypto_data_valid(self):
        """Test crypto data validation with valid data."""
        # Create valid test data
        data = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [95.0, 96.0, 97.0],
            'close': [103.0, 104.0, 105.0],
            'volume': [1000.0, 1100.0, 1200.0]
        }, index=pd.date_range('2023-01-01', periods=3, freq='5T'))
        
        # Should pass validation
        self.assertTrue(self.fetcher.validate_crypto_data(data))
    
    def test_validate_crypto_data_empty(self):
        """Test crypto data validation with empty DataFrame."""
        data = pd.DataFrame()
        self.assertFalse(self.fetcher.validate_crypto_data(data))
    
    def test_validate_crypto_data_missing_columns(self):
        """Test crypto data validation with missing columns."""
        data = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [105.0, 106.0],
            # Missing 'low', 'close', 'volume'
        })
        self.assertFalse(self.fetcher.validate_crypto_data(data))
    
    def test_validate_crypto_data_nan_values(self):
        """Test crypto data validation with NaN values."""
        data = pd.DataFrame({
            'open': [100.0, None],  # NaN value
            'high': [105.0, 106.0],
            'low': [95.0, 96.0],
            'close': [103.0, 104.0],
            'volume': [1000.0, 1100.0]
        })
        self.assertFalse(self.fetcher.validate_crypto_data(data))
    
    def test_validate_crypto_data_invalid_ohlc(self):
        """Test crypto data validation with invalid OHLC relationships."""
        data = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [90.0, 106.0],  # High < Open (invalid)
            'low': [95.0, 96.0],
            'close': [103.0, 104.0],
            'volume': [1000.0, 1100.0]
        })
        self.assertFalse(self.fetcher.validate_crypto_data(data))
    
    def test_validate_crypto_data_negative_prices(self):
        """Test crypto data validation with negative prices."""
        data = pd.DataFrame({
            'open': [100.0, -101.0],  # Negative price
            'high': [105.0, 106.0],
            'low': [95.0, 96.0],
            'close': [103.0, 104.0],
            'volume': [1000.0, 1100.0]
        })
        self.assertFalse(self.fetcher.validate_crypto_data(data))
    
    def test_validate_crypto_data_negative_volume(self):
        """Test crypto data validation with negative volume."""
        data = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [105.0, 106.0],
            'low': [95.0, 96.0],
            'close': [103.0, 104.0],
            'volume': [1000.0, -1100.0]  # Negative volume
        })
        self.assertFalse(self.fetcher.validate_crypto_data(data))
    
    def test_resample_dataframe(self):
        """Test DataFrame resampling functionality."""
        # Create test data with 1-minute intervals
        data = pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'high': [105.0, 106.0, 107.0, 108.0, 109.0],
            'low': [95.0, 96.0, 97.0, 98.0, 99.0],
            'close': [103.0, 104.0, 105.0, 106.0, 107.0],
            'volume': [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
        }, index=pd.date_range('2023-01-01', periods=5, freq='1T'))
        
        # Resample to 5-minute intervals
        resampled = self.fetcher._resample_dataframe(data, '5T')
        
        # Should have 1 row (5 minutes of 1-minute data)
        self.assertEqual(len(resampled), 1)
        
        # Verify aggregation
        self.assertEqual(resampled.iloc[0]['open'], 100.0)  # First open
        self.assertEqual(resampled.iloc[0]['high'], 109.0)  # Max high
        self.assertEqual(resampled.iloc[0]['low'], 95.0)   # Min low
        self.assertEqual(resampled.iloc[0]['close'], 107.0) # Last close
        self.assertEqual(resampled.iloc[0]['volume'], 6000.0) # Sum volume
    
    def test_handle_api_errors_rate_limit(self):
        """Test API error handling for rate limits."""
        error = Exception("Rate limit exceeded")
        
        with patch('time.sleep') as mock_sleep:
            result = self.fetcher.handle_api_errors(error)
            
            self.assertTrue(result)  # Should retry
            mock_sleep.assert_called_once_with(5)
    
    def test_handle_api_errors_auth(self):
        """Test API error handling for authentication errors."""
        error = Exception("401 Unauthorized")
        result = self.fetcher.handle_api_errors(error)
        
        self.assertFalse(result)  # Should not retry
    
    def test_handle_api_errors_network(self):
        """Test API error handling for network errors."""
        error = requests.exceptions.ConnectionError("Connection failed")
        result = self.fetcher.handle_api_errors(error)
        
        self.assertTrue(result)  # Should retry
    
    def test_handle_api_errors_timeout(self):
        """Test API error handling for timeout errors."""
        error = requests.exceptions.Timeout("Request timed out")
        result = self.fetcher.handle_api_errors(error)
        
        self.assertTrue(result)  # Should retry
    
    def test_handle_api_errors_invalid_product(self):
        """Test API error handling for invalid product errors."""
        error = Exception("Invalid product ID")
        result = self.fetcher.handle_api_errors(error)
        
        self.assertFalse(result)  # Should not retry
    
    def test_handle_api_errors_general(self):
        """Test API error handling for general errors."""
        error = Exception("Some API error")
        result = self.fetcher.handle_api_errors(error)
        
        self.assertTrue(result)  # Should retry
    
    @patch('time.sleep')
    def test_respect_rate_limit(self, mock_sleep):
        """Test rate limiting functionality."""
        # Set last request time to now
        self.fetcher.last_request_time = time.time()
        
        # Call rate limit check immediately (should sleep)
        self.fetcher._respect_rate_limit()
        
        # Should have slept for the remaining time
        mock_sleep.assert_called_once()
        
        # Verify last_request_time was updated
        self.assertGreater(self.fetcher.last_request_time, 0)


if __name__ == '__main__':
    unittest.main()