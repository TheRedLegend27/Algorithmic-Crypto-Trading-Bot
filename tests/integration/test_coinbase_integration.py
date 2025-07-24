"""
Integration tests for Coinbase client and configuration.
Tests the integration between CoinbaseClient and Config classes.
"""
import os
import unittest
from unittest.mock import patch, Mock

from bot.config import Config
from bot.coinbase_client import CoinbaseClient


class TestCoinbaseIntegration(unittest.TestCase):
    """Test integration between Coinbase client and configuration."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Reset singleton instance
        Config._instance = None
    
    def tearDown(self):
        """Clean up after tests."""
        # Reset singleton instance
        Config._instance = None
    
    @patch.dict(os.environ, {
        'ALPACA_API_KEY': 'alpaca_key',
        'ALPACA_SECRET_KEY': 'alpaca_secret',
        'ALPACA_BASE_URL': 'https://paper-api.alpaca.markets',
        'COINBASE_API_KEY': 'coinbase_key',
        'COINBASE_API_SECRET': 'Y29pbmJhc2Vfc2VjcmV0',  # base64 encoded "coinbase_secret"
        'COINBASE_PASSPHRASE': 'coinbase_passphrase',
        'COINBASE_SANDBOX': 'True'
    })
    def test_coinbase_client_from_config(self):
        """Test creating CoinbaseClient from configuration."""
        config = Config()
        config.load_env_variables()
        
        # Validate Coinbase config
        self.assertTrue(config.validate_coinbase_config())
        
        # Get credentials and create client
        credentials = config.get_coinbase_credentials()
        self.assertIsNotNone(credentials)
        
        client = CoinbaseClient(credentials)
        self.assertIsNotNone(client)
        self.assertEqual(client.credentials, credentials)
        self.assertTrue(client.credentials.sandbox)
    
    @patch.dict(os.environ, {
        'ALPACA_API_KEY': 'alpaca_key',
        'ALPACA_SECRET_KEY': 'alpaca_secret',
        'ALPACA_BASE_URL': 'https://paper-api.alpaca.markets',
        'COINBASE_API_KEY': 'coinbase_key',
        'COINBASE_API_SECRET': 'Y29pbmJhc2Vfc2VjcmV0',  # base64 encoded "coinbase_secret"
        'COINBASE_PASSPHRASE': 'coinbase_passphrase',
        'COINBASE_SANDBOX': 'False'
    })
    def test_coinbase_client_production_config(self):
        """Test creating CoinbaseClient for production from configuration."""
        config = Config()
        config.load_env_variables()
        
        credentials = config.get_coinbase_credentials()
        self.assertIsNotNone(credentials)
        self.assertFalse(credentials.sandbox)
        self.assertEqual(credentials.base_url, "https://api.exchange.coinbase.com")
        
        client = CoinbaseClient(credentials)
        self.assertIsNotNone(client)
        self.assertFalse(client.credentials.sandbox)
    
    @patch.dict(os.environ, {
        'ALPACA_API_KEY': 'alpaca_key',
        'ALPACA_SECRET_KEY': 'alpaca_secret',
        'ALPACA_BASE_URL': 'https://paper-api.alpaca.markets'
        # No Coinbase credentials
    })
    def test_no_coinbase_credentials(self):
        """Test behavior when no Coinbase credentials are provided."""
        config = Config()
        config.load_env_variables()
        
        credentials = config.get_coinbase_credentials()
        self.assertIsNone(credentials)
        
        # Should not be able to validate Coinbase config
        self.assertFalse(config.validate_coinbase_config())
    
    @patch.dict(os.environ, {
        'ALPACA_API_KEY': 'alpaca_key',
        'ALPACA_SECRET_KEY': 'alpaca_secret',
        'ALPACA_BASE_URL': 'https://paper-api.alpaca.markets',
        'COINBASE_API_KEY': 'coinbase_key',
        'COINBASE_API_SECRET': 'Y29pbmJhc2Vfc2VjcmV0',
        'COINBASE_PASSPHRASE': 'coinbase_passphrase',
        'COINBASE_SANDBOX': 'True'
    })
    @patch('requests.Session.request')
    def test_coinbase_client_authentication_test(self, mock_request):
        """Test authentication test with mocked response."""
        # Mock successful authentication response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": "account1", "currency": "USD"}]
        mock_request.return_value = mock_response
        
        config = Config()
        config.load_env_variables()
        
        credentials = config.get_coinbase_credentials()
        client = CoinbaseClient(credentials)
        
        # Test authentication
        auth_result = client.test_authentication()
        self.assertTrue(auth_result)
        
        # Verify the request was made with correct authentication headers
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        headers = call_args[1]['headers']
        
        # Check that authentication headers are present
        self.assertIn('CB-ACCESS-KEY', headers)
        self.assertIn('CB-ACCESS-SIGN', headers)
        self.assertIn('CB-ACCESS-TIMESTAMP', headers)
        self.assertIn('CB-ACCESS-PASSPHRASE', headers)
        self.assertIn('CB-ACCESS-NONCE', headers)
        
        # Check header values
        self.assertEqual(headers['CB-ACCESS-KEY'], 'coinbase_key')
        self.assertEqual(headers['CB-ACCESS-PASSPHRASE'], 'coinbase_passphrase')
    
    @patch.dict(os.environ, {
        'ALPACA_API_KEY': 'alpaca_key',
        'ALPACA_SECRET_KEY': 'alpaca_secret',
        'ALPACA_BASE_URL': 'https://paper-api.alpaca.markets',
        'COINBASE_API_KEY': 'coinbase_key',
        'COINBASE_API_SECRET': 'Y29pbmJhc2Vfc2VjcmV0',
        'COINBASE_PASSPHRASE': 'coinbase_passphrase',
        'COINBASE_SANDBOX': 'True'
    })
    def test_crypto_trading_settings_integration(self):
        """Test integration with crypto trading settings."""
        config = Config()
        config.load_env_variables()
        
        crypto_settings = config.get_crypto_trading_settings()
        self.assertIsNotNone(crypto_settings)
        self.assertEqual(crypto_settings.trading_pair, "BTC-USD")
        self.assertEqual(crypto_settings.base_currency, "BTC")
        self.assertEqual(crypto_settings.quote_currency, "USD")
        
        # Verify settings can be used with client
        credentials = config.get_coinbase_credentials()
        client = CoinbaseClient(credentials)
        
        # This should work without errors
        self.assertIsNotNone(client)
        self.assertEqual(client.credentials.api_key, 'coinbase_key')


if __name__ == '__main__':
    unittest.main()