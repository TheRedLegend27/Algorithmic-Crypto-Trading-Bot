"""
Integration tests for CoinbaseTrader class.
Tests complete trading workflows with Coinbase API.
"""
import unittest
from unittest.mock import patch, MagicMock
import os
from datetime import datetime

from bot.coinbase_client import CoinbaseCredentials
from bot.coinbase_trader import CoinbaseTrader, CryptoTradingSettings
from bot.strategy import TradingSignal, SignalType


class TestCoinbaseTraderIntegration(unittest.TestCase):
    """Integration tests for CoinbaseTrader class."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        # Use sandbox credentials for testing
        cls.api_key = os.environ.get("COINBASE_API_KEY", "test_key")
        cls.api_secret = os.environ.get("COINBASE_API_SECRET", "test_secret")
        cls.passphrase = os.environ.get("COINBASE_PASSPHRASE", "test_passphrase")
        
        # Use sandbox mode for testing
        cls.credentials = CoinbaseCredentials(
            api_key=cls.api_key,
            api_secret=cls.api_secret,
            passphrase=cls.passphrase,
            sandbox=True
        )
        
        # Use test trading settings with small amounts
        cls.settings = CryptoTradingSettings(
            trading_pair="BTC-USD",
            base_currency="BTC",
            quote_currency="USD",
            trade_amount_usd=10.0,  # Small amount for testing
            max_position_usd=50.0,
            min_order_size=0.001,
            min_trade_interval=0  # No interval for testing
        )
    
    @patch('bot.coinbase_client.CoinbaseClient')
    @patch('bot.coinbase_data_fetcher.CoinbaseDataFetcher')
    @patch('bot.crypto_position_manager.CryptoPositionManager')
    @patch('bot.crypto_order_manager.CryptoOrderManager')
    def test_trader_initialization(self, mock_order_manager, mock_position_manager, 
                                 mock_data_fetcher, mock_client):
        """Test trader initialization."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        # Act
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Assert
        self.assertIsNotNone(trader)
        mock_client.assert_called_once_with(self.credentials)
        mock_data_fetcher.assert_called_once_with(self.credentials)
        mock_position_manager.assert_called_once_with(mock_client_instance)
        mock_order_manager.assert_called_once_with(mock_client_instance)
        mock_order_manager.return_value.update_fee_rates.assert_called_once_with(
            maker_fee=self.settings.maker_fee_rate,
            taker_fee=self.settings.taker_fee_rate
        )
    
    @patch('bot.coinbase_client.CoinbaseClient')
    @patch('bot.coinbase_data_fetcher.CoinbaseDataFetcher')
    @patch('bot.crypto_position_manager.CryptoPositionManager')
    @patch('bot.crypto_order_manager.CryptoOrderManager')
    def test_execute_buy_trade(self, mock_order_manager, mock_position_manager, 
                             mock_data_fetcher, mock_client):
        """Test executing a buy trade."""
        # Arrange
        mock_data_fetcher.return_value.get_latest_price.return_value = 50000.0
        
        # Mock sufficient balance
        mock_balance = MagicMock()
        mock_balance.available = 1000.0
        mock_position_manager.return_value.get_crypto_balance.return_value = mock_balance
        
        # Mock position summary
        mock_position_manager.return_value.get_position_summary.return_value = {
            "market_value_usd": 0.0,
            "has_position": False
        }
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        mock_trade_result.order_id = "test_order_id"
        mock_trade_result.fees = 0.05
        mock_order_manager.return_value.place_market_order.return_value = mock_trade_result
        
        # Create trader
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Create buy signal
        signal = TradingSignal(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            action=SignalType.BUY,
            price=50000.0,
            confidence=0.8,
            strategy_name="test_strategy"
        )
        
        # Act
        result = trader.execute_trade(signal)
        
        # Assert
        self.assertIsNotNone(result)
        mock_order_manager.return_value.place_market_order.assert_called_once()
        mock_position_manager.return_value.track_crypto_position.assert_called_once()
    
    @patch('bot.coinbase_client.CoinbaseClient')
    @patch('bot.coinbase_data_fetcher.CoinbaseDataFetcher')
    @patch('bot.crypto_position_manager.CryptoPositionManager')
    @patch('bot.crypto_order_manager.CryptoOrderManager')
    def test_execute_sell_trade(self, mock_order_manager, mock_position_manager, 
                              mock_data_fetcher, mock_client):
        """Test executing a sell trade."""
        # Arrange
        mock_data_fetcher.return_value.get_latest_price.return_value = 50000.0
        
        # Mock existing position
        mock_balance = MagicMock()
        mock_balance.available = 0.01  # Small BTC position
        mock_position_manager.return_value.get_crypto_balance.return_value = mock_balance
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        mock_trade_result.order_id = "test_order_id"
        mock_trade_result.fees = 0.05
        mock_order_manager.return_value.place_market_order.return_value = mock_trade_result
        
        # Create trader
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Create sell signal
        signal = TradingSignal(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            action=SignalType.SELL,
            price=50000.0,
            confidence=0.8,
            strategy_name="test_strategy"
        )
        
        # Act
        result = trader.execute_trade(signal)
        
        # Assert
        self.assertIsNotNone(result)
        mock_order_manager.return_value.place_market_order.assert_called_once_with(
            product_id="BTC-USD",
            side="sell",
            size=0.01
        )
        mock_position_manager.return_value.track_crypto_position.assert_called_once()
    
    @patch('bot.coinbase_client.CoinbaseClient')
    @patch('bot.coinbase_data_fetcher.CoinbaseDataFetcher')
    @patch('bot.crypto_position_manager.CryptoPositionManager')
    @patch('bot.crypto_order_manager.CryptoOrderManager')
    def test_insufficient_balance_for_buy(self, mock_order_manager, mock_position_manager, 
                                        mock_data_fetcher, mock_client):
        """Test buy order with insufficient balance."""
        # Arrange
        mock_data_fetcher.return_value.get_latest_price.return_value = 50000.0
        
        # Mock insufficient balance
        mock_balance = MagicMock()
        mock_balance.available = 5.0  # Not enough for a $10 trade at $50000
        mock_position_manager.return_value.get_crypto_balance.return_value = mock_balance
        
        # Mock position summary
        mock_position_manager.return_value.get_position_summary.return_value = {
            "market_value_usd": 0.0,
            "has_position": False
        }
        
        # Create trader
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Create buy signal
        signal = TradingSignal(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            action=SignalType.BUY,
            price=50000.0,
            confidence=0.8,
            strategy_name="test_strategy"
        )
        
        # Act
        result = trader.execute_trade(signal)
        
        # Assert
        self.assertIsNone(result)
        mock_order_manager.return_value.place_market_order.assert_not_called()
    
    @patch('bot.coinbase_client.CoinbaseClient')
    @patch('bot.coinbase_data_fetcher.CoinbaseDataFetcher')
    @patch('bot.crypto_position_manager.CryptoPositionManager')
    @patch('bot.crypto_order_manager.CryptoOrderManager')
    def test_risk_management_stop_loss(self, mock_order_manager, mock_position_manager, 
                                     mock_data_fetcher, mock_client):
        """Test risk management stop loss trigger."""
        # Arrange
        # Price dropped 10% from entry
        mock_data_fetcher.return_value.get_latest_price.return_value = 45000.0
        
        # Mock existing position
        mock_balance = MagicMock()
        mock_balance.available = 0.01  # Small BTC position
        mock_position_manager.return_value.get_crypto_balance.return_value = mock_balance
        
        # Mock position summary with 10% loss (entry at 50000)
        mock_position_manager.return_value.get_position_summary.return_value = {
            "has_position": True,
            "balance": 0.01,
            "avg_entry_price": 50000.0,
            "market_value_usd": 450.0
        }
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        mock_trade_result.order_id = "test_order_id"
        mock_trade_result.fees = 0.05
        mock_order_manager.return_value.place_market_order.return_value = mock_trade_result
        
        # Create trader with 5% stop loss
        settings = CryptoTradingSettings(
            trading_pair="BTC-USD",
            stop_loss_pct=0.05  # 5% stop loss
        )
        trader = CoinbaseTrader(self.credentials, settings)
        
        # Act
        result = trader.check_risk_management_triggers()
        
        # Assert
        self.assertTrue(result)
        mock_order_manager.return_value.place_market_order.assert_called_once_with(
            product_id="BTC-USD",
            side="sell",
            size=0.01
        )
    
    @patch('bot.coinbase_client.CoinbaseClient')
    @patch('bot.coinbase_data_fetcher.CoinbaseDataFetcher')
    @patch('bot.crypto_position_manager.CryptoPositionManager')
    @patch('bot.crypto_order_manager.CryptoOrderManager')
    def test_get_account_info(self, mock_order_manager, mock_position_manager, 
                            mock_data_fetcher, mock_client):
        """Test getting account information."""
        # Arrange
        mock_data_fetcher.return_value.get_latest_price.return_value = 50000.0
        
        # Mock balances
        mock_btc_balance = MagicMock()
        mock_btc_balance.balance = 0.01
        mock_btc_balance.available = 0.01
        
        mock_usd_balance = MagicMock()
        mock_usd_balance.balance = 1000.0
        mock_usd_balance.available = 1000.0
        
        # Return different balances based on currency
        def get_balance_side_effect(currency):
            if currency == "BTC":
                return mock_btc_balance
            elif currency == "USD":
                return mock_usd_balance
            return None
        
        mock_position_manager.return_value.get_crypto_balance.side_effect = get_balance_side_effect
        
        # Create trader
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Act
        account_info = trader.get_account_info()
        
        # Assert
        self.assertEqual(account_info["base_currency"], "BTC")
        self.assertEqual(account_info["base_balance"], 0.01)
        self.assertEqual(account_info["quote_currency"], "USD")
        self.assertEqual(account_info["quote_balance"], 1000.0)
        self.assertEqual(account_info["current_price"], 50000.0)
        self.assertEqual(account_info["portfolio_value"], 1500.0)  # 0.01 BTC at 50000 + 1000 USD


if __name__ == '__main__':
    unittest.main()