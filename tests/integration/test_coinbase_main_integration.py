"""
Integration tests for the main application with Coinbase components.
Tests the initialization and basic functionality of the main application.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
import argparse
import sys

from bot.main import parse_arguments, initialize_components, perform_health_check, main
from bot.config import Config, CoinbaseCredentials, CryptoTradingSettings
from bot.coinbase_trader import CoinbaseTrader
from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.coinbase_error_handler import CoinbaseErrorHandler


class TestCoinbaseMainIntegration(unittest.TestCase):
    """Integration tests for the main application with Coinbase components."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            "COINBASE_API_KEY": "test_api_key",
            "COINBASE_API_SECRET": "test_api_secret",
            "COINBASE_PASSPHRASE": "test_passphrase",
            "COINBASE_SANDBOX": "True"
        })
        self.env_patcher.start()
        
        # Create a mock config
        self.config = Config()
        self.config.load_env_variables()
        
        # Create mock arguments
        self.args = argparse.Namespace(
            platform="coinbase",
            symbol="BTC-USD",
            interval=5,
            amount=10.0,
            max_position=100.0,
            stop_loss=0.05,
            take_profit=0.1,
            ma_fast=10,
            ma_slow=30,
            rsi_period=14,
            rsi_oversold=30,
            rsi_overbought=70,
            dry_run=False,
            backtest=False,
            backtest_days=30,
            no_dashboard=True,
            log_level="INFO",
            log_file="test.log",
            health_check_interval=30,
            skip_health_check=True,
            maxtrades=20,
            sandbox=True,
            base_currency="BTC",
            quote_currency="USD",
            min_order_size=0.001,
            start_delay=0
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
    
    @patch('bot.main.TradingLogger')
    @patch('bot.main.CoinbaseDataFetcher')
    @patch('bot.main.CoinbaseTrader')
    @patch('bot.main.SignalGenerator')
    @patch('bot.main.TradingCycle')
    @patch('bot.main.TradingScheduler')
    def test_initialize_coinbase_components(self, mock_scheduler, mock_cycle, mock_signal_gen, 
                                          mock_trader, mock_data_fetcher, mock_logger):
        """Test initialization of Coinbase components."""
        # Set up mocks
        mock_logger_instance = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        mock_data_fetcher_instance = MagicMock()
        mock_data_fetcher.return_value = mock_data_fetcher_instance
        
        mock_trader_instance = MagicMock()
        mock_trader.return_value = mock_trader_instance
        
        mock_signal_gen_instance = MagicMock()
        mock_signal_gen.return_value = mock_signal_gen_instance
        
        mock_cycle_instance = MagicMock()
        mock_cycle.return_value = mock_cycle_instance
        
        mock_scheduler_instance = MagicMock()
        mock_scheduler.return_value = mock_scheduler_instance
        
        # Call the function
        components = initialize_components(self.config, self.args)
        
        # Assertions
        self.assertIsNotNone(components)
        self.assertEqual(components["logger"], mock_logger_instance)
        self.assertEqual(components["data_fetcher"], mock_data_fetcher_instance)
        self.assertEqual(components["trader"], mock_trader_instance)
        self.assertEqual(components["signal_generator"], mock_signal_gen_instance)
        self.assertEqual(components["trading_cycle"], mock_cycle_instance)
        self.assertEqual(components["scheduler"], mock_scheduler_instance)
        
        # Verify CoinbaseTrader was initialized with correct parameters
        mock_trader.assert_called_once()
        args, kwargs = mock_trader.call_args
        self.assertIsInstance(kwargs["credentials"], CoinbaseCredentials)
        self.assertIsInstance(kwargs["settings"], CryptoTradingSettings)
        self.assertEqual(kwargs["settings"].trading_pair, "BTC-USD")
        self.assertEqual(kwargs["settings"].base_currency, "BTC")
        self.assertEqual(kwargs["settings"].quote_currency, "USD")
    
    @patch('bot.main.log_info')
    @patch('bot.main.log_error')
    def test_perform_health_check_coinbase(self, mock_log_error, mock_log_info):
        """Test health check with Coinbase components."""
        # Create mock components
        mock_data_fetcher = MagicMock()
        mock_data_fetcher.get_latest_price.return_value = 50000.0
        
        mock_trader = MagicMock()
        mock_trader.get_account_info.return_value = {"portfolio_value": 10000.0}
        mock_trader.get_portfolio_summary.return_value = {"total_value": 10000.0}
        
        mock_components = {
            "data_fetcher": mock_data_fetcher,
            "trader": mock_trader,
            "trading_cycle": MagicMock(symbol="BTC-USD")
        }
        
        # Call the function
        result = perform_health_check(mock_components, "coinbase")
        
        # Assertions
        self.assertTrue(result)
        mock_data_fetcher.get_latest_price.assert_called_once_with("BTC-USD")
        mock_trader.get_account_info.assert_called_once()
        mock_trader.get_portfolio_summary.assert_called_once()
        
        # Verify log messages
        mock_log_info.assert_any_call("Performing health check...")
        mock_log_info.assert_any_call("Data fetcher check: OK (Latest BTC-USD price: $50000.00)")
        mock_log_info.assert_any_call("Health check completed successfully")
    
    @patch('bot.main.parse_arguments')
    @patch('bot.utils.setup_logging')
    @patch('bot.main.Config')
    @patch('bot.main.initialize_components')
    @patch('bot.main.perform_health_check')
    @patch('bot.main.setup_signal_handlers')
    @patch('bot.main.log_info')
    @patch('bot.main.log_error')
    def test_main_function_coinbase(self, mock_log_error, mock_log_info, mock_setup_signals,
                                  mock_health_check, mock_init_components, mock_config,
                                  mock_setup_logging, mock_parse_args):
        """Test the main function with Coinbase components."""
        # Set up mocks
        mock_parse_args.return_value = self.args
        
        mock_config_instance = MagicMock()
        mock_config_instance.load_env_variables.return_value = True
        mock_config_instance.validate_coinbase_config.return_value = True
        mock_config.return_value = mock_config_instance
        
        mock_logger = MagicMock()
        mock_logger.start_live_display = MagicMock()
        mock_logger.stop_live_display = MagicMock()
        
        mock_scheduler = MagicMock()
        mock_scheduler.start_scheduler.return_value = True
        mock_scheduler.is_running = False
        
        mock_components = {
            "logger": mock_logger,
            "scheduler": mock_scheduler,
            "trading_cycle": MagicMock(symbol="BTC-USD")
        }
        mock_init_components.return_value = mock_components
        
        mock_health_check.return_value = True
        
        # Call the function
        result = main()
        
        # Assertions
        self.assertEqual(result, 0)
        mock_parse_args.assert_called_once()
        mock_config_instance.load_env_variables.assert_called_once()
        mock_config_instance.validate_coinbase_config.assert_called_once()
        mock_init_components.assert_called_once()
        mock_logger.start_live_display.assert_called_once()
        mock_scheduler.start_scheduler.assert_called_once()
        mock_logger.stop_live_display.assert_called_once()


if __name__ == '__main__':
    unittest.main()