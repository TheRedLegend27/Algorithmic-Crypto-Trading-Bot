"""
Unit tests for CoinbaseTrader class.
Tests trader functionality with mocked dependencies.
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from bot.coinbase_client import CoinbaseCredentials
from bot.coinbase_trader import CoinbaseTrader, CryptoTradingSettings
from bot.strategy import TradingSignal, SignalType


class TestCoinbaseTrader(unittest.TestCase):
    """Unit tests for CoinbaseTrader class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create mock credentials
        self.credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
        
        # Create test trading settings
        self.settings = CryptoTradingSettings(
            trading_pair="BTC-USD",
            base_currency="BTC",
            quote_currency="USD",
            trade_amount_usd=10.0,
            max_position_usd=50.0,
            min_order_size=0.001,
            min_trade_interval=0  # No interval for testing
        )
        
        # Create mocks for dependencies
        self.mock_client = MagicMock()
        self.mock_data_fetcher = MagicMock()
        self.mock_position_manager = MagicMock()
        self.mock_order_manager = MagicMock()
        
        # Create patches
        self.client_patcher = patch('bot.coinbase_client.CoinbaseClient', return_value=self.mock_client)
        self.data_fetcher_patcher = patch('bot.coinbase_data_fetcher.CoinbaseDataFetcher', return_value=self.mock_data_fetcher)
        self.position_manager_patcher = patch('bot.crypto_position_manager.CryptoPositionManager', return_value=self.mock_position_manager)
        self.order_manager_patcher = patch('bot.crypto_order_manager.CryptoOrderManager', return_value=self.mock_order_manager)
        
        # Start patches
        self.mock_client_class = self.client_patcher.start()
        self.mock_data_fetcher_class = self.data_fetcher_patcher.start()
        self.mock_position_manager_class = self.position_manager_patcher.start()
        self.mock_order_manager_class = self.order_manager_patcher.start()
    
    def tearDown(self):
        """Clean up after each test."""
        # Stop patches
        self.client_patcher.stop()
        self.data_fetcher_patcher.stop()
        self.position_manager_patcher.stop()
        self.order_manager_patcher.stop()
    
    def test_initialization(self):
        """Test trader initialization."""
        # Act
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Assert
        self.assertIsNotNone(trader)
        self.mock_client_class.assert_called_once_with(self.credentials)
        self.mock_data_fetcher_class.assert_called_once_with(self.credentials)
        self.mock_position_manager_class.assert_called_once_with(self.mock_client)
        self.mock_order_manager_class.assert_called_once_with(self.mock_client)
        self.mock_order_manager.update_fee_rates.assert_called_once_with(
            maker_fee=self.settings.maker_fee_rate,
            taker_fee=self.settings.taker_fee_rate
        )
    
    def test_should_trade_hold_signal(self):
        """Test _should_trade with HOLD signal."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        signal = TradingSignal(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            action=SignalType.HOLD,
            price=50000.0,
            confidence=0.8,
            strategy_name="test_strategy"
        )
        
        # Act
        result = trader._should_trade(signal)
        
        # Assert
        self.assertFalse(result)
    
    def test_should_trade_low_confidence(self):
        """Test _should_trade with low confidence signal."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        signal = TradingSignal(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            action=SignalType.BUY,
            price=50000.0,
            confidence=0.3,  # Low confidence
            strategy_name="test_strategy"
        )
        
        # Act
        result = trader._should_trade(signal)
        
        # Assert
        self.assertFalse(result)
    
    def test_should_trade_valid_signal(self):
        """Test _should_trade with valid signal."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        signal = TradingSignal(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            action=SignalType.BUY,
            price=50000.0,
            confidence=0.8,  # High confidence
            strategy_name="test_strategy"
        )
        
        # Act
        result = trader._should_trade(signal)
        
        # Assert
        self.assertTrue(result)
    
    def test_execute_buy_trade_success(self):
        """Test executing a successful buy trade."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock price
        self.mock_data_fetcher.get_latest_price.return_value = 50000.0
        
        # Mock position summary
        self.mock_position_manager.get_position_summary.return_value = {
            "market_value_usd": 0.0,
            "has_position": False
        }
        
        # Mock sufficient balance
        mock_balance = MagicMock()
        mock_balance.available = 1000.0
        self.mock_position_manager.get_crypto_balance.return_value = mock_balance
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        mock_trade_result.order_id = "test_order_id"
        mock_trade_result.fees = 0.05
        self.mock_order_manager.place_market_order.return_value = mock_trade_result
        
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
        self.assertEqual(result, mock_trade_result)
        self.mock_order_manager.place_market_order.assert_called_once()
        self.mock_position_manager.track_crypto_position.assert_called_once()
    
    def test_execute_buy_trade_insufficient_balance(self):
        """Test executing a buy trade with insufficient balance."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock price
        self.mock_data_fetcher.get_latest_price.return_value = 50000.0
        
        # Mock position summary
        self.mock_position_manager.get_position_summary.return_value = {
            "market_value_usd": 0.0,
            "has_position": False
        }
        
        # Mock insufficient balance
        mock_balance = MagicMock()
        mock_balance.available = 5.0  # Not enough for $10 trade
        self.mock_position_manager.get_crypto_balance.return_value = mock_balance
        
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
        self.mock_order_manager.place_market_order.assert_not_called()
    
    def test_execute_sell_trade_success(self):
        """Test executing a successful sell trade."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock price
        self.mock_data_fetcher.get_latest_price.return_value = 50000.0
        
        # Mock existing position
        mock_balance = MagicMock()
        mock_balance.available = 0.01  # Small BTC position
        self.mock_position_manager.get_crypto_balance.return_value = mock_balance
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        mock_trade_result.order_id = "test_order_id"
        mock_trade_result.fees = 0.05
        self.mock_order_manager.place_market_order.return_value = mock_trade_result
        
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
        self.assertEqual(result, mock_trade_result)
        self.mock_order_manager.place_market_order.assert_called_once_with(
            product_id="BTC-USD",
            side="sell",
            size=0.01
        )
        self.mock_position_manager.track_crypto_position.assert_called_once_with(
            currency="BTC",
            amount=-0.01,
            price=50000.0,
            fees=0.05
        )
    
    def test_execute_sell_trade_no_position(self):
        """Test executing a sell trade with no position."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock price
        self.mock_data_fetcher.get_latest_price.return_value = 50000.0
        
        # Mock no position
        mock_balance = MagicMock()
        mock_balance.available = 0.0  # No BTC position
        self.mock_position_manager.get_crypto_balance.return_value = mock_balance
        
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
        self.assertIsNone(result)
        self.mock_order_manager.place_market_order.assert_not_called()
    
    def test_calculate_buy_quantity(self):
        """Test calculating buy quantity."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock position summary
        self.mock_position_manager.get_position_summary.return_value = {
            "market_value_usd": 0.0,
            "has_position": False
        }
        
        # Act
        quantity = trader._calculate_buy_quantity("BTC-USD", 50000.0)
        
        # Assert
        # $10 trade amount / $50000 price = 0.0002 BTC
        self.assertEqual(quantity, 0.0002)
    
    def test_calculate_buy_quantity_with_max_position_limit(self):
        """Test calculating buy quantity with max position limit."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock position summary with existing position
        self.mock_position_manager.get_position_summary.return_value = {
            "market_value_usd": 45.0,  # Already have $45 in BTC
            "has_position": True
        }
        
        # Act
        quantity = trader._calculate_buy_quantity("BTC-USD", 50000.0)
        
        # Assert
        # Max position is $50, already have $45, so can only buy $5 more
        # $5 / $50000 = 0.0001 BTC
        self.assertEqual(quantity, 0.0001)
    
    def test_check_risk_management_triggers_stop_loss(self):
        """Test risk management stop loss trigger."""
        # Arrange
        # Use settings with 5% stop loss
        settings = CryptoTradingSettings(
            trading_pair="BTC-USD",
            base_currency="BTC",
            quote_currency="USD",
            stop_loss_pct=0.05  # 5% stop loss
        )
        trader = CoinbaseTrader(self.credentials, settings)
        
        # Mock price dropped 10% from entry
        self.mock_data_fetcher.get_latest_price.return_value = 45000.0
        
        # Mock position summary with 10% loss
        self.mock_position_manager.get_position_summary.return_value = {
            "has_position": True,
            "balance": 0.01,
            "avg_entry_price": 50000.0
        }
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        self.mock_order_manager.place_market_order.return_value = mock_trade_result
        
        # Act
        result = trader.check_risk_management_triggers()
        
        # Assert
        self.assertTrue(result)
        self.mock_order_manager.place_market_order.assert_called_once_with(
            product_id="BTC-USD",
            side="sell",
            size=0.01
        )
    
    def test_check_risk_management_triggers_take_profit(self):
        """Test risk management take profit trigger."""
        # Arrange
        # Use settings with 10% take profit
        settings = CryptoTradingSettings(
            trading_pair="BTC-USD",
            base_currency="BTC",
            quote_currency="USD",
            take_profit_pct=0.1  # 10% take profit
        )
        trader = CoinbaseTrader(self.credentials, settings)
        
        # Mock price increased 15% from entry
        self.mock_data_fetcher.get_latest_price.return_value = 57500.0
        
        # Mock position summary with 15% gain
        self.mock_position_manager.get_position_summary.return_value = {
            "has_position": True,
            "balance": 0.01,
            "avg_entry_price": 50000.0
        }
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        self.mock_order_manager.place_market_order.return_value = mock_trade_result
        
        # Act
        result = trader.check_risk_management_triggers()
        
        # Assert
        self.assertTrue(result)
        self.mock_order_manager.place_market_order.assert_called_once_with(
            product_id="BTC-USD",
            side="sell",
            size=0.01
        )
    
    def test_check_risk_management_triggers_no_trigger(self):
        """Test risk management with no triggers."""
        # Arrange
        # Use settings with 5% stop loss and 10% take profit
        settings = CryptoTradingSettings(
            trading_pair="BTC-USD",
            base_currency="BTC",
            quote_currency="USD",
            stop_loss_pct=0.05,
            take_profit_pct=0.1
        )
        trader = CoinbaseTrader(self.credentials, settings)
        
        # Mock price within acceptable range (3% gain)
        self.mock_data_fetcher.get_latest_price.return_value = 51500.0
        
        # Mock position summary with 3% gain
        self.mock_position_manager.get_position_summary.return_value = {
            "has_position": True,
            "balance": 0.01,
            "avg_entry_price": 50000.0
        }
        
        # Act
        result = trader.check_risk_management_triggers()
        
        # Assert
        self.assertFalse(result)
        self.mock_order_manager.place_market_order.assert_not_called()
    
    def test_close_all_positions(self):
        """Test closing all positions."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock existing position
        mock_balance = MagicMock()
        mock_balance.available = 0.01  # Small BTC position
        self.mock_position_manager.get_crypto_balance.return_value = mock_balance
        
        # Mock price
        self.mock_data_fetcher.get_latest_price.return_value = 50000.0
        
        # Mock successful order placement
        mock_trade_result = MagicMock()
        mock_trade_result.fees = 0.05
        self.mock_order_manager.place_market_order.return_value = mock_trade_result
        
        # Act
        result = trader.close_all_positions()
        
        # Assert
        self.assertTrue(result)
        self.mock_order_manager.place_market_order.assert_called_once_with(
            product_id="BTC-USD",
            side="sell",
            size=0.01
        )
        self.mock_position_manager.track_crypto_position.assert_called_once_with(
            currency="BTC",
            amount=-0.01,
            price=50000.0,
            fees=0.05
        )
    
    def test_get_account_info(self):
        """Test getting account information."""
        # Arrange
        trader = CoinbaseTrader(self.credentials, self.settings)
        
        # Mock price
        self.mock_data_fetcher.get_latest_price.return_value = 50000.0
        
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
        
        self.mock_position_manager.get_crypto_balance.side_effect = get_balance_side_effect
        
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