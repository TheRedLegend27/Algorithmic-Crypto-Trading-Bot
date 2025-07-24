"""
Unit tests for the CryptoPositionManager class.
"""
import unittest
from unittest.mock import MagicMock, patch
import json
import os
from datetime import datetime, timedelta
import tempfile

from bot.crypto_position_manager import (
    CryptoPositionManager, CryptoBalance, CryptoPositionEntry, CryptoTradeRecord
)


class TestCryptoPositionManager(unittest.TestCase):
    """Test cases for CryptoPositionManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        
        # Mock the get_accounts method to return test data
        self.mock_client.get_accounts.return_value = [
            {
                'currency': 'BTC',
                'balance': '1.5',
                'available': '1.2',
                'hold': '0.3',
                'profile_id': 'profile1',
                'trading_enabled': True
            },
            {
                'currency': 'ETH',
                'balance': '10.0',
                'available': '8.5',
                'hold': '1.5',
                'profile_id': 'profile1',
                'trading_enabled': True
            },
            {
                'currency': 'USD',
                'balance': '5000.0',
                'available': '5000.0',
                'hold': '0.0',
                'profile_id': 'profile1',
                'trading_enabled': True
            }
        ]
        
        self.position_manager = CryptoPositionManager(self.mock_client)
    
    def test_refresh_balances(self):
        """Test refreshing balances from Coinbase."""
        # The balances should be loaded during initialization
        self.assertEqual(len(self.position_manager.balances), 3)
        self.assertIn('BTC', self.position_manager.balances)
        self.assertIn('ETH', self.position_manager.balances)
        self.assertIn('USD', self.position_manager.balances)
        
        # Verify balance values
        btc_balance = self.position_manager.balances['BTC']
        self.assertEqual(btc_balance.balance, 1.5)
        self.assertEqual(btc_balance.available, 1.2)
        self.assertEqual(btc_balance.hold, 0.3)
        self.assertEqual(btc_balance.profile_id, 'profile1')
        self.assertTrue(btc_balance.trading_enabled)
    
    def test_get_crypto_balance(self):
        """Test getting balance for a specific cryptocurrency."""
        # Test getting an existing balance
        btc_balance = self.position_manager.get_crypto_balance('BTC')
        self.assertIsNotNone(btc_balance)
        self.assertEqual(btc_balance.currency, 'BTC')
        self.assertEqual(btc_balance.balance, 1.5)
        
        # Test getting a non-existent balance
        self.mock_client.get_accounts.return_value = []  # No balances returned on refresh
        xrp_balance = self.position_manager.get_crypto_balance('XRP')
        self.assertIsNone(xrp_balance)
    
    def test_get_all_balances(self):
        """Test getting all cryptocurrency balances."""
        balances = self.position_manager.get_all_balances()
        self.assertEqual(len(balances), 3)
        self.assertIn('BTC', balances)
        self.assertIn('ETH', balances)
        self.assertIn('USD', balances)
    
    def test_get_position_value_usd(self):
        """Test calculating position value in USD."""
        # BTC balance is 1.5, so at $40,000 per BTC, value should be $60,000
        btc_value = self.position_manager.get_position_value_usd('BTC', 40000.0)
        self.assertEqual(btc_value, 60000.0)
        
        # Test with non-existent currency
        xrp_value = self.position_manager.get_position_value_usd('XRP', 1.0)
        self.assertEqual(xrp_value, 0.0)
    
    def test_calculate_available_balance(self):
        """Test calculating available balance."""
        # BTC available balance is 1.2
        btc_available = self.position_manager.calculate_available_balance('BTC')
        self.assertEqual(btc_available, 1.2)
        
        # Test with non-existent currency
        xrp_available = self.position_manager.calculate_available_balance('XRP')
        self.assertEqual(xrp_available, 0.0)
    
    def test_track_crypto_position_buy(self):
        """Test tracking a buy position."""
        # Track a BTC buy
        self.position_manager.track_crypto_position('BTC', 0.5, 35000.0, datetime.now(), 10.0)
        
        # Verify position entries
        self.assertIn('BTC', self.position_manager.position_entries)
        self.assertEqual(len(self.position_manager.position_entries['BTC']), 1)
        
        entry = self.position_manager.position_entries['BTC'][0]
        self.assertEqual(entry.quantity, 0.5)
        self.assertEqual(entry.price, 35000.0)
        self.assertEqual(entry.fees, 10.0)
        
        # Verify position history
        self.assertIn('BTC', self.position_manager.position_history)
        self.assertEqual(len(self.position_manager.position_history['BTC']), 1)
        
        history_entry = self.position_manager.position_history['BTC'][0]
        self.assertEqual(history_entry['action'], 'buy')
        self.assertEqual(history_entry['amount'], 0.5)
        self.assertEqual(history_entry['price'], 35000.0)
        self.assertEqual(history_entry['fees'], 10.0)
    
    def test_track_crypto_position_sell(self):
        """Test tracking a sell position after a buy."""
        # First track a buy
        buy_time = datetime.now() - timedelta(days=1)
        self.position_manager.track_crypto_position('BTC', 0.5, 35000.0, buy_time, 10.0)
        
        # Then track a sell
        sell_time = datetime.now()
        self.position_manager.track_crypto_position('BTC', -0.3, 40000.0, sell_time, 8.0)
        
        # Verify position entries (should have 0.2 BTC left)
        self.assertIn('BTC', self.position_manager.position_entries)
        self.assertEqual(len(self.position_manager.position_entries['BTC']), 1)
        
        entry = self.position_manager.position_entries['BTC'][0]
        self.assertEqual(entry.quantity, 0.2)
        
        # Verify trade history (should have one trade)
        self.assertEqual(len(self.position_manager.trade_history), 1)
        
        trade = self.position_manager.trade_history[0]
        self.assertEqual(trade.currency, 'BTC')
        self.assertEqual(trade.quantity, 0.3)
        self.assertEqual(trade.entry_price, 35000.0)
        self.assertEqual(trade.exit_price, 40000.0)
        self.assertEqual(trade.entry_time, buy_time)
        self.assertEqual(trade.exit_time, sell_time)
        
        # Verify realized P&L: (40000 - 35000) * 0.3 - 8.0 * (0.3/0.3) = 1492.0
        expected_pnl = (40000.0 - 35000.0) * 0.3 - 8.0
        self.assertAlmostEqual(trade.realized_pnl, expected_pnl, places=2)
    
    def test_get_position_summary(self):
        """Test getting position summary."""
        # Track a BTC buy
        self.position_manager.track_crypto_position('BTC', 0.5, 35000.0, datetime.now(), 10.0)
        
        # Get position summary with current price of $40,000
        summary = self.position_manager.get_position_summary('BTC', 40000.0)
        
        # Verify summary values
        self.assertEqual(summary['currency'], 'BTC')
        self.assertEqual(summary['balance'], 1.5)  # From mock data
        self.assertEqual(summary['avg_entry_price'], 35000.0)
        self.assertEqual(summary['cost_basis'], 35000.0 * 0.5 + 10.0)
        
        # Unrealized P&L should be (40000 - 35000) * 0.5 = 2500.0
        # But this is only for the tracked position, not the full balance
        self.assertAlmostEqual(summary['unrealized_pnl'], 2500.0, places=2)
    
    def test_get_portfolio_summary(self):
        """Test getting portfolio summary."""
        # Track positions
        self.position_manager.track_crypto_position('BTC', 0.5, 35000.0, datetime.now(), 10.0)
        self.position_manager.track_crypto_position('ETH', 2.0, 2000.0, datetime.now(), 5.0)
        
        # Get portfolio summary with current prices
        market_prices = {
            'BTC': 40000.0,
            'ETH': 2500.0,
            'USD': 1.0
        }
        
        summary = self.position_manager.get_portfolio_summary(market_prices)
        
        # Verify summary values
        self.assertGreater(summary['total_market_value_usd'], 0)
        self.assertEqual(summary['position_count'], 2)  # BTC and ETH
        
        # Total unrealized P&L should include both BTC and ETH
        # BTC: (40000 - 35000) * 0.5 = 2500.0
        # ETH: (2500 - 2000) * 2.0 = 1000.0
        # Total: 3500.0
        self.assertAlmostEqual(summary['total_unrealized_pnl'], 3500.0, places=2)
    
    def test_export_import_position_data(self):
        """Test exporting and importing position data."""
        # Track some positions
        self.position_manager.track_crypto_position('BTC', 0.5, 35000.0, datetime.now(), 10.0)
        self.position_manager.track_crypto_position('ETH', 2.0, 2000.0, datetime.now(), 5.0)
        
        # Export data to a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Export data
            export_success = self.position_manager.export_position_data(temp_path)
            self.assertTrue(export_success)
            
            # Create a new position manager
            new_position_manager = CryptoPositionManager(self.mock_client)
            
            # Import data
            import_success = new_position_manager.import_position_data(temp_path)
            self.assertTrue(import_success)
            
            # Verify imported data
            self.assertEqual(
                len(new_position_manager.position_entries['BTC']),
                len(self.position_manager.position_entries['BTC'])
            )
            self.assertEqual(
                len(new_position_manager.position_entries['ETH']),
                len(self.position_manager.position_entries['ETH'])
            )
            
            # Verify entry details
            btc_entry = new_position_manager.position_entries['BTC'][0]
            self.assertEqual(btc_entry.quantity, 0.5)
            self.assertEqual(btc_entry.price, 35000.0)
            self.assertEqual(btc_entry.fees, 10.0)
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_get_position_history(self):
        """Test getting position history."""
        # Track multiple position changes
        self.position_manager.track_crypto_position('BTC', 0.5, 35000.0, datetime.now(), 10.0)
        self.position_manager.track_crypto_position('BTC', 0.3, 36000.0, datetime.now(), 7.0)
        self.position_manager.track_crypto_position('BTC', -0.2, 40000.0, datetime.now(), 8.0)
        
        # Get position history
        history = self.position_manager.get_position_history('BTC')
        
        # Verify history
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]['action'], 'buy')
        self.assertEqual(history[0]['amount'], 0.5)
        self.assertEqual(history[1]['action'], 'buy')
        self.assertEqual(history[1]['amount'], 0.3)
        self.assertEqual(history[2]['action'], 'sell')
        self.assertEqual(history[2]['amount'], 0.2)
    
    def test_update_performance_metrics(self):
        """Test updating performance metrics."""
        # Initial high water mark should be 0
        self.assertEqual(self.position_manager.high_water_mark, 0.0)
        
        # Update with a portfolio value
        self.position_manager._update_performance_metrics(100000.0)
        self.assertEqual(self.position_manager.high_water_mark, 100000.0)
        
        # Update with a lower value (should create drawdown)
        self.position_manager._update_performance_metrics(80000.0)
        self.assertEqual(self.position_manager.high_water_mark, 100000.0)
        self.assertEqual(self.position_manager.max_drawdown, 0.2)  # 20% drawdown
        
        # Update with a higher value (should update high water mark)
        self.position_manager._update_performance_metrics(120000.0)
        self.assertEqual(self.position_manager.high_water_mark, 120000.0)
        self.assertEqual(self.position_manager.max_drawdown, 0.2)  # Still 20% max drawdown


if __name__ == '__main__':
    unittest.main()