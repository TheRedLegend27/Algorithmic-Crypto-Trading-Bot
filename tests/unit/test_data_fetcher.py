"""
Unit tests for the DataFetcher class.
"""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from alpaca.data.models import Bar

from bot.data_fetcher import DataFetcher
from bot.config import AlpacaCredentials


class TestDataFetcher(unittest.TestCase):
    """Test cases for the DataFetcher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        
        # Create a mock for the CryptoHistoricalDataClient
        self.client_patcher = patch('bot.data_fetcher.CryptoHistoricalDataClient')
        self.mock_client_class = self.client_patcher.start()
        self.mock_client = self.mock_client_class.return_value
        
        # Create the DataFetcher instance with mocked client
        self.data_fetcher = DataFetcher(self.credentials)
        self.data_fetcher.client = self.mock_client
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.client_patcher.stop()
    
    def test_init(self):
        """Test initialization of DataFetcher."""
        self.assertEqual(self.data_fetcher.credentials, self.credentials)
        self.assertEqual(self.data_fetcher.rate_limit_wait, 0.2)
        self.mock_client_class.assert_called_once_with(
            api_key="test_key",
            secret_key="test_secret"
        )
    
    def test_respect_rate_limit(self):
        """Test rate limiting functionality."""
        with patch('time.sleep') as mock_sleep, patch('time.time') as mock_time:
            # First call, no delay needed
            mock_time.return_value = 100.0
            self.data_fetcher.last_request_time = 0
            self.data_fetcher._respect_rate_limit()
            mock_sleep.assert_not_called()
            self.assertEqual(self.data_fetcher.last_request_time, 100.0)
            
            # Second call, delay needed
            mock_time.return_value = 100.1  # 100ms elapsed
            self.data_fetcher._respect_rate_limit()
            mock_sleep.assert_called_once_with(0.1)  # Should sleep for 100ms
    
    def test_calculate_start_time(self):
        """Test start time calculation for different timeframes."""
        end_time = datetime(2023, 1, 1, 12, 0, 0)
        
        # Test 1Min timeframe
        start_time = self.data_fetcher._calculate_start_time(end_time, "1Min", 10)
        expected = end_time - timedelta(minutes=10)
        self.assertEqual(start_time, expected)
        
        # Test 5Min timeframe
        start_time = self.data_fetcher._calculate_start_time(end_time, "5Min", 10)
        expected = end_time - timedelta(minutes=50)
        self.assertEqual(start_time, expected)
        
        # Test 1H timeframe
        start_time = self.data_fetcher._calculate_start_time(end_time, "1H", 10)
        expected = end_time - timedelta(hours=10)
        self.assertEqual(start_time, expected)
        
        # Test 1D timeframe
        start_time = self.data_fetcher._calculate_start_time(end_time, "1D", 10)
        expected = end_time - timedelta(days=10)
        self.assertEqual(start_time, expected)
        
        # Test invalid timeframe (should default to 1 day)
        start_time = self.data_fetcher._calculate_start_time(end_time, "invalid", 10)
        expected = end_time - timedelta(days=1)
        self.assertEqual(start_time, expected)
    
    def test_bars_to_dataframe(self):
        """Test conversion of Bar objects to DataFrame."""
        # Create sample Bar objects
        bars = [
            MagicMock(
                timestamp=datetime(2023, 1, 1, 12, 0),
                open=100.0,
                high=105.0,
                low=99.0,
                close=102.0,
                volume=1000.0
            ),
            MagicMock(
                timestamp=datetime(2023, 1, 1, 12, 5),
                open=102.0,
                high=106.0,
                low=101.0,
                close=105.0,
                volume=1200.0
            )
        ]
        
        df = self.data_fetcher._bars_to_dataframe(bars)
        
        # Check DataFrame structure
        self.assertEqual(len(df), 2)
        self.assertTrue('open' in df.columns)
        self.assertTrue('high' in df.columns)
        self.assertTrue('low' in df.columns)
        self.assertTrue('close' in df.columns)
        self.assertTrue('volume' in df.columns)
        
        # Check values
        self.assertEqual(df.iloc[0]['open'], 100.0)
        self.assertEqual(df.iloc[0]['high'], 105.0)
        self.assertEqual(df.iloc[0]['low'], 99.0)
        self.assertEqual(df.iloc[0]['close'], 102.0)
        self.assertEqual(df.iloc[0]['volume'], 1000.0)
        
        # Check index
        self.assertEqual(df.index[0], datetime(2023, 1, 1, 12, 0))
    
    def test_fetch_crypto_data_success(self):
        """Test successful data fetching."""
        # Create mock bars
        mock_bars = {
            "BTC/USD": [
                MagicMock(
                    timestamp=datetime(2023, 1, 1, 12, 0),
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=102.0,
                    volume=1000.0
                ),
                MagicMock(
                    timestamp=datetime(2023, 1, 1, 12, 5),
                    open=102.0,
                    high=106.0,
                    low=101.0,
                    close=105.0,
                    volume=1200.0
                )
            ]
        }
        
        # Configure mock
        self.mock_client.get_crypto_bars.return_value = mock_bars
        
        # Call the method
        with patch('bot.data_fetcher.log_info') as mock_log:
            df = self.data_fetcher.fetch_crypto_data("BTC/USD", "5Min", 2)
        
        # Verify results
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['close'], 102.0)
        self.assertEqual(df.iloc[1]['close'], 105.0)
        
        # Verify API call
        self.mock_client.get_crypto_bars.assert_called_once()
        args, kwargs = self.mock_client.get_crypto_bars.call_args
        request_params = args[0]
        self.assertEqual(request_params.symbol_or_symbols, "BTC/USD")
    
    def test_fetch_crypto_data_invalid_timeframe(self):
        """Test fetching with invalid timeframe."""
        with self.assertRaises(ValueError) as context:
            self.data_fetcher.fetch_crypto_data("BTC/USD", "invalid", 50)
        
        self.assertIn("Invalid timeframe", str(context.exception))
    
    def test_fetch_crypto_data_empty_response(self):
        """Test handling of empty API response."""
        # Configure mock to return empty response
        self.mock_client.get_crypto_bars.return_value = {}
        
        # Call the method and expect exception
        with self.assertRaises(ValueError) as context:
            self.data_fetcher.fetch_crypto_data("BTC/USD", "5Min", 50)
        
        self.assertIn("No data returned", str(context.exception))
    
    def test_validate_data(self):
        """Test data validation."""
        # Valid data
        valid_data = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [105.0, 106.0],
            'low': [99.0, 100.0],
            'close': [102.0, 103.0],
            'volume': [1000.0, 1100.0]
        }, index=[datetime(2023, 1, 1, 12, 0), datetime(2023, 1, 1, 12, 5)])
        
        self.assertTrue(self.data_fetcher.validate_data(valid_data))
        
        # Empty data
        empty_data = pd.DataFrame()
        self.assertFalse(self.data_fetcher.validate_data(empty_data))
        
        # Missing columns
        missing_columns = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [105.0, 106.0],
            'low': [99.0, 100.0],
            # Missing 'close'
            'volume': [1000.0, 1100.0]
        })
        self.assertFalse(self.data_fetcher.validate_data(missing_columns))
        
        # NaN values
        nan_data = pd.DataFrame({
            'open': [100.0, np.nan],
            'high': [105.0, 106.0],
            'low': [99.0, 100.0],
            'close': [102.0, 103.0],
            'volume': [1000.0, 1100.0]
        })
        self.assertFalse(self.data_fetcher.validate_data(nan_data))
        
        # Invalid OHLC relationships
        invalid_ohlc = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [95.0, 106.0],  # High < Open
            'low': [99.0, 100.0],
            'close': [102.0, 103.0],
            'volume': [1000.0, 1100.0]
        })
        self.assertFalse(self.data_fetcher.validate_data(invalid_ohlc))
        
        # Negative prices
        negative_prices = pd.DataFrame({
            'open': [100.0, -101.0],
            'high': [105.0, 106.0],
            'low': [99.0, 100.0],
            'close': [102.0, 103.0],
            'volume': [1000.0, 1100.0]
        })
        self.assertFalse(self.data_fetcher.validate_data(negative_prices))
        
        # Negative volume
        negative_volume = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [105.0, 106.0],
            'low': [99.0, 100.0],
            'close': [102.0, 103.0],
            'volume': [1000.0, -1100.0]
        })
        self.assertFalse(self.data_fetcher.validate_data(negative_volume))
    
    def test_get_latest_price(self):
        """Test getting the latest price."""
        # Mock fetch_crypto_data to return a DataFrame with one row
        mock_df = pd.DataFrame({
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [102.0],
            'volume': [1000.0]
        }, index=[datetime.now()])
        
        with patch.object(self.data_fetcher, 'fetch_crypto_data', return_value=mock_df):
            price = self.data_fetcher.get_latest_price("BTC/USD")
            self.assertEqual(price, 102.0)
    
    def test_get_latest_price_empty_data(self):
        """Test getting latest price with empty data."""
        # Mock fetch_crypto_data to return empty DataFrame
        with patch.object(self.data_fetcher, 'fetch_crypto_data', return_value=pd.DataFrame()):
            with self.assertRaises(ValueError) as context:
                self.data_fetcher.get_latest_price("BTC/USD")
            
            self.assertIn("No recent price data available", str(context.exception))
    
    def test_handle_api_errors(self):
        """Test API error handling."""
        # Rate limit error
        rate_limit_error = Exception("Rate limit exceeded")
        with patch('time.sleep') as mock_sleep, patch('bot.data_fetcher.log_warning') as mock_log:
            result = self.data_fetcher.handle_api_errors(rate_limit_error)
            self.assertTrue(result)
            mock_sleep.assert_called_once_with(5)
        
        # Authentication error
        auth_error = Exception("Authentication failed")
        with patch('bot.data_fetcher.log_error') as mock_log:
            result = self.data_fetcher.handle_api_errors(auth_error)
            self.assertFalse(result)
        
        # Network error
        network_error = requests.exceptions.ConnectionError("Connection failed")
        with patch('bot.data_fetcher.log_warning') as mock_log:
            result = self.data_fetcher.handle_api_errors(network_error)
            self.assertTrue(result)
        
        # Timeout error
        timeout_error = requests.exceptions.Timeout("Request timed out")
        with patch('bot.data_fetcher.log_warning') as mock_log:
            result = self.data_fetcher.handle_api_errors(timeout_error)
            self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()