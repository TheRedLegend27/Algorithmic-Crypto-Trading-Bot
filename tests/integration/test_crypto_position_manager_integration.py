"""
Integration tests for the CryptoPositionManager class.
Tests the integration with Coinbase API for position and balance management.
"""
import unittest
from unittest.mock import patch
import os
import json
from datetime import datetime, timedelta

from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials
from bot.crypto_position_manager import CryptoPositionManager


class TestCryptoPositionManagerIntegration(unittest.TestCase):
    """Integration tests for CryptoPositionManager with Coinbase API."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are reused across tests."""
        # Check if we're in CI environment or if we should use sandbox
        cls.use_sandbox = os.environ.get('CI') == 'true' or os.environ.get('USE_SANDBOX') == 'true'
        
        # Skip tests if API credentials are not available
        cls.api_key = os.environ.get('COINBASE_API_KEY')
        cls.api_secret = os.environ.get('COINBASE_API_SECRET')
        cls.passphrase = os.environ.get('COINBASE_PASSPHRASE')
        
        if not cls.api_key or not cls.api_secret or not cls.passphrase:
            cls.skip_tests = True
            print("Skipping integration tests: Coinbase API credentials not available")
        else:
            cls.skip_tests = False
            
            # Create credentials and client
            cls.credentials = CoinbaseCredentials(
                api_key=cls.api_key,
                api_secret=cls.api_secret,
                passphrase=cls.passphrase,
                sandbox=cls.use_sandbox
            )
            cls.client = CoinbaseClient(cls.credentials)
            
            # Test authentication
            try:
                auth_success = cls.client.test_authentication()
                if not auth_success:
                    cls.skip_tests = True
                    print("Skipping integration tests: Coinbase authentication failed")
            except Exception as e:
                cls.skip_tests = True
                print(f"Skipping integration tests: Coinbase authentication error: {str(e)}")
    
    def setUp(self):
        """Set up test fixtures before each test."""
        if self.skip_tests:
            self.skipTest("Coinbase API credentials not available or authentication failed")
        
        # Create position manager
        self.position_manager = CryptoPositionManager(self.client)
        
        # Get current market prices for testing
        self.market_prices = self._get_test_market_prices()
    
    def _get_test_market_prices(self):
        """Get current market prices for testing."""
        try:
            # Get prices for common cryptocurrencies
            prices = {}
            for product_id in ['BTC-USD', 'ETH-USD', 'LTC-USD']:
                ticker = self.client.get_product_ticker(product_id)
                currency = product_id.split('-')[0]
                prices[currency] = float(ticker.get('price', 0.0))
            
            # Add USD price
            prices['USD'] = 1.0
            
            return prices
        except Exception as e:
            print(f"Error getting market prices: {str(e)}")
            # Return some default prices for testing
            return {
                'BTC': 40000.0,
                'ETH': 2000.0,
                'LTC': 100.0,
                'USD': 1.0
            }
    
    def test_get_balances(self):
        """Test getting balances from Coinbase API."""
        # Get all balances
        balances = self.position_manager.get_all_balances()
        
        # Verify we got some balances
        self.assertGreater(len(balances), 0)
        
        # Print balances for debugging
        print(f"Found {len(balances)} balances:")
        for currency, balance in balances.items():
            if balance.balance > 0:
                print(f"  {currency}: {balance.balance} (Available: {balance.available}, Hold: {balance.hold})")
    
    def test_portfolio_summary(self):
        """Test getting portfolio summary with real market prices."""
        # Get portfolio summary
        summary = self.position_manager.get_portfolio_summary(self.market_prices)
        
        # Verify summary structure
        self.assertIn('total_market_value_usd', summary)
        self.assertIn('positions', summary)
        
        # Print summary for debugging
        print(f"Portfolio value: ${summary['total_market_value_usd']:,.2f}")
        print(f"Position count: {summary['position_count']}")
    
    @patch('bot.crypto_position_manager.CryptoPositionManager._refresh_balances')
    def test_track_position_simulation(self, mock_refresh):
        """Test position tracking simulation."""
        # Mock _refresh_balances to avoid API calls during simulation
        mock_refresh.return_value = True
        
        # Simulate tracking a BTC position
        self.position_manager.track_crypto_position('BTC', 0.1, self.market_prices['BTC'] * 0.9, 
                                                 datetime.now() - timedelta(days=1), 5.0)
        
        # Simulate a partial sell
        self.position_manager.track_crypto_position('BTC', -0.05, self.market_prices['BTC'], 
                                                  datetime.now(), 3.0)
        
        # Get position summary
        summary = self.position_manager.get_position_summary('BTC', self.market_prices['BTC'])
        
        # Verify position tracking
        self.assertEqual(len(self.position_manager.position_entries['BTC']), 1)
        self.assertEqual(self.position_manager.position_entries['BTC'][0].quantity, 0.05)
        
        # Verify trade history
        self.assertEqual(len(self.position_manager.trade_history), 1)
        self.assertEqual(self.position_manager.trade_history[0].currency, 'BTC')
        self.assertEqual(self.position_manager.trade_history[0].quantity, 0.05)
        
        # Print position summary for debugging
        print(f"BTC Position Summary:")
        print(f"  Quantity: {summary['balance']}")
        print(f"  Avg Entry: ${summary['avg_entry_price']:,.2f}")
        print(f"  Current Price: ${self.market_prices['BTC']:,.2f}")
        print(f"  Unrealized P&L: ${summary['unrealized_pnl']:,.2f}")
        print(f"  P&L %: {summary['pnl_percentage']:.2f}%")
    
    def test_export_import_data(self):
        """Test exporting and importing position data."""
        # Skip if we're in CI environment
        if os.environ.get('CI') == 'true':
            self.skipTest("Skipping file operations in CI environment")
        
        # Create a temporary file path
        temp_path = 'temp_position_data.json'
        
        try:
            # Track a simulated position
            self.position_manager.track_crypto_position('BTC', 0.1, self.market_prices['BTC'], 
                                                     datetime.now(), 5.0)
            
            # Export data
            export_success = self.position_manager.export_position_data(temp_path)
            self.assertTrue(export_success)
            
            # Create a new position manager
            new_position_manager = CryptoPositionManager(self.client)
            
            # Import data
            import_success = new_position_manager.import_position_data(temp_path)
            self.assertTrue(import_success)
            
            # Verify imported data
            self.assertEqual(
                len(new_position_manager.position_entries['BTC']),
                len(self.position_manager.position_entries['BTC'])
            )
            
            # Verify entry details
            btc_entry = new_position_manager.position_entries['BTC'][0]
            self.assertEqual(btc_entry.quantity, 0.1)
            self.assertAlmostEqual(btc_entry.price, self.market_prices['BTC'], delta=0.01)
            self.assertEqual(btc_entry.fees, 5.0)
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()