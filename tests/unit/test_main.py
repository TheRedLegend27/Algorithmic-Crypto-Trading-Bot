"""
Unit tests for the main module.
Tests the command-line argument parsing and component initialization.
"""
import unittest
from unittest.mock import patch, Mock, MagicMock
import argparse
import sys
import signal
import atexit

from bot.main import (
    parse_arguments, 
    update_trading_settings, 
    initialize_components, 
    perform_health_check,
    setup_signal_handlers
)


class TestMainModule(unittest.TestCase):
    """Test cases for the main module."""
    
    def test_parse_arguments_defaults(self):
        """Test parsing command-line arguments with defaults."""
        # Save original sys.argv
        original_argv = sys.argv
        
        try:
            # Set up test arguments
            sys.argv = ['run_bot.py']
            
            # Parse arguments
            args = parse_arguments()
            
            # Check default values
            self.assertEqual(args.symbol, "BTC/USD")
            self.assertEqual(args.interval, 5)
            self.assertEqual(args.amount, 10.0)
            self.assertEqual(args.max_position, 100.0)
            self.assertEqual(args.stop_loss, 0.05)
            self.assertEqual(args.take_profit, 0.1)
            self.assertFalse(args.no_dashboard)
            self.assertEqual(args.log_level, "INFO")
            
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    def test_parse_arguments_custom(self):
        """Test parsing command-line arguments with custom values."""
        # Save original sys.argv
        original_argv = sys.argv
        
        try:
            # Set up test arguments
            sys.argv = [
                'run_bot.py',
                '--symbol', 'ETH/USD',
                '--interval', '15',
                '--amount', '20.0',
                '--max-position', '200.0',
                '--stop-loss', '0.1',
                '--take-profit', '0.2',
                '--no-dashboard',
                '--log-level', 'DEBUG'
            ]
            
            # Parse arguments
            args = parse_arguments()
            
            # Check custom values
            self.assertEqual(args.symbol, "ETH/USD")
            self.assertEqual(args.interval, 15)
            self.assertEqual(args.amount, 20.0)
            self.assertEqual(args.max_position, 200.0)
            self.assertEqual(args.stop_loss, 0.1)
            self.assertEqual(args.take_profit, 0.2)
            self.assertTrue(args.no_dashboard)
            self.assertEqual(args.log_level, "DEBUG")
            
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    def test_update_trading_settings(self):
        """Test updating trading settings from command-line arguments."""
        # Create mock objects
        mock_settings = Mock()
        mock_args = Mock(
            symbol="ETH/USD",
            amount=20.0,
            max_position=200.0,
            stop_loss=0.1,
            take_profit=0.2,
            interval=15
        )
        
        # Update settings
        update_trading_settings(mock_settings, mock_args)
        
        # Check that settings were updated correctly
        self.assertEqual(mock_settings.symbol, "ETH/USD")
        self.assertEqual(mock_settings.trade_amount, 20.0)
        self.assertEqual(mock_settings.max_position_size, 200.0)
        self.assertEqual(mock_settings.stop_loss_pct, 0.1)
        self.assertEqual(mock_settings.take_profit_pct, 0.2)
        self.assertEqual(mock_settings.min_trade_interval, 15)
    
    @patch('bot.main.TradingLogger')
    @patch('bot.main.DataFetcher')
    @patch('bot.main.SignalGenerator')
    @patch('bot.main.Trader')
    @patch('bot.main.TradingCycle')
    @patch('bot.main.TradingScheduler')
    @patch('bot.main.MovingAverageCrossover')
    @patch('bot.main.RSIStrategy')
    def test_initialize_components(self, mock_rsi, mock_ma, mock_scheduler, mock_cycle, 
                                  mock_trader, mock_signal_gen, mock_fetcher, mock_logger):
        """Test initializing components."""
        # Create mock objects
        mock_config = Mock()
        mock_credentials = Mock(paper_trading=False)
        mock_config.get_alpaca_credentials.return_value = mock_credentials
        mock_config.get_trading_settings.return_value = Mock()
        
        mock_args = Mock(
            symbol="BTC/USD",
            interval=5,
            no_dashboard=False,
            dry_run=False,
            backtest=False,
            backtest_days=30,
            ma_fast=10,
            ma_slow=30,
            rsi_period=14,
            rsi_oversold=30,
            rsi_overbought=70,
            log_file="bot.log",
            start_delay=0
        )
        
        # Initialize components
        components = initialize_components(mock_config, mock_args)
        
        # Check that all components were initialized
        self.assertIn("logger", components)
        self.assertIn("data_fetcher", components)
        self.assertIn("signal_generator", components)
        self.assertIn("trader", components)
        self.assertIn("trading_cycle", components)
        self.assertIn("scheduler", components)
        
        # Check that the components were initialized with the correct arguments
        mock_logger.assert_called_once_with(use_rich=True, log_file="bot.log")
        mock_fetcher.assert_called_once_with(mock_credentials)
        mock_trader.assert_called_once_with(
            credentials=mock_credentials,
            settings=mock_config.get_trading_settings.return_value,
            paper_trading=False
        )
        mock_ma.assert_called_once_with(fast_period=10, slow_period=30)
        mock_rsi.assert_called_once_with(period=14, oversold=30, overbought=70)
        mock_cycle.assert_called_once_with(
            data_fetcher=mock_fetcher.return_value,
            signal_generator=mock_signal_gen.return_value,
            trader=mock_trader.return_value,
            logger=mock_logger.return_value,
            symbol="BTC/USD",
            backtest_mode=False,
            backtest_days=None
        )
        mock_scheduler.assert_called_once_with(
            trading_cycle=mock_cycle.return_value,
            interval_minutes=5,
            start_delay=0
        )
    
    def test_perform_health_check_success(self):
        """Test performing a health check with all components healthy."""
        # Create mock components
        mock_data_fetcher = Mock()
        mock_data_fetcher.get_latest_price.return_value = 50000.0
        
        mock_trader = Mock()
        mock_trader.get_account_info.return_value = {"equity": 10000.0}
        mock_trader.position_manager.reconcile_positions.return_value = True
        
        mock_trading_cycle = Mock()
        mock_trading_cycle.symbol = "BTC/USD"
        
        components = {
            "data_fetcher": mock_data_fetcher,
            "trader": mock_trader,
            "trading_cycle": mock_trading_cycle
        }
        
        # Perform health check
        result = perform_health_check(components)
        
        # Check result
        self.assertTrue(result)
        mock_data_fetcher.get_latest_price.assert_called_once_with("BTC/USD")
        mock_trader.get_account_info.assert_called_once()
        mock_trader.position_manager.reconcile_positions.assert_called_once()
    
    def test_perform_health_check_failure(self):
        """Test performing a health check with a failing component."""
        # Create mock components
        mock_data_fetcher = Mock()
        mock_data_fetcher.get_latest_price.side_effect = Exception("API error")
        
        mock_trading_cycle = Mock()
        mock_trading_cycle.symbol = "BTC/USD"
        
        components = {
            "data_fetcher": mock_data_fetcher,
            "trading_cycle": mock_trading_cycle
        }
        
        # Perform health check
        result = perform_health_check(components)
        
        # Check result
        self.assertFalse(result)
        mock_data_fetcher.get_latest_price.assert_called_once_with("BTC/USD")
    
    def test_setup_signal_handlers(self):
        """Test setting up signal handlers for graceful shutdown."""
        # Create mock scheduler
        mock_scheduler = Mock()
        
        # Save original signal handlers
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        
        try:
            # Set up signal handlers
            setup_signal_handlers(mock_scheduler)
            
            # Check that signal handlers were registered
            self.assertNotEqual(signal.getsignal(signal.SIGINT), original_sigint)
            self.assertNotEqual(signal.getsignal(signal.SIGTERM), original_sigterm)
            
        finally:
            # Restore original signal handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)
    
    def test_parse_arguments_execution_modes(self):
        """Test parsing command-line arguments for different execution modes."""
        # Save original sys.argv
        original_argv = sys.argv
        
        try:
            # Set up test arguments for dry-run mode
            sys.argv = [
                'run_bot.py',
                '--dry-run',
                '--backtest',
                '--backtest-days', '15',
                '--start-delay', '10'
            ]
            
            # Parse arguments
            args = parse_arguments()
            
            # Check execution mode values
            self.assertTrue(args.dry_run)
            self.assertTrue(args.backtest)
            self.assertEqual(args.backtest_days, 15)
            self.assertEqual(args.start_delay, 10)
            
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    def test_parse_arguments_strategy_params(self):
        """Test parsing command-line arguments for strategy parameters."""
        # Save original sys.argv
        original_argv = sys.argv
        
        try:
            # Set up test arguments for strategy parameters
            sys.argv = [
                'run_bot.py',
                '--ma-fast', '5',
                '--ma-slow', '20',
                '--rsi-period', '10',
                '--rsi-oversold', '25',
                '--rsi-overbought', '75'
            ]
            
            # Parse arguments
            args = parse_arguments()
            
            # Check strategy parameter values
            self.assertEqual(args.ma_fast, 5)
            self.assertEqual(args.ma_slow, 20)
            self.assertEqual(args.rsi_period, 10)
            self.assertEqual(args.rsi_oversold, 25)
            self.assertEqual(args.rsi_overbought, 75)
            
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    @patch('bot.main.TradingLogger')
    @patch('bot.main.DataFetcher')
    @patch('bot.main.SignalGenerator')
    @patch('bot.main.Trader')
    @patch('bot.main.TradingCycle')
    @patch('bot.main.TradingScheduler')
    @patch('bot.main.MovingAverageCrossover')
    @patch('bot.main.RSIStrategy')
    def test_initialize_components_with_execution_modes(self, mock_rsi, mock_ma, mock_scheduler, 
                                                      mock_cycle, mock_trader, mock_signal_gen, 
                                                      mock_fetcher, mock_logger):
        """Test initializing components with different execution modes."""
        # Create mock objects
        mock_config = Mock()
        mock_credentials = Mock(paper_trading=False)
        mock_config.get_alpaca_credentials.return_value = mock_credentials
        mock_config.get_trading_settings.return_value = Mock()
        
        # Create args with dry-run mode
        mock_args = Mock(
            symbol="BTC/USD",
            interval=5,
            no_dashboard=False,
            dry_run=True,
            backtest=True,
            backtest_days=15,
            start_delay=10,
            ma_fast=5,
            ma_slow=20,
            rsi_period=10,
            rsi_oversold=25,
            rsi_overbought=75,
            log_file="test.log"
        )
        
        # Initialize components
        components = initialize_components(mock_config, mock_args)
        
        # Check that components were initialized with the correct execution modes
        mock_trader.assert_called_once_with(
            credentials=mock_credentials,
            settings=mock_config.get_trading_settings.return_value,
            paper_trading=True  # Should be True because dry_run=True
        )
        
        mock_cycle.assert_called_once_with(
            data_fetcher=mock_fetcher.return_value,
            signal_generator=mock_signal_gen.return_value,
            trader=mock_trader.return_value,
            logger=mock_logger.return_value,
            symbol="BTC/USD",
            backtest_mode=True,
            backtest_days=15
        )
        
        mock_scheduler.assert_called_once_with(
            trading_cycle=mock_cycle.return_value,
            interval_minutes=5,
            start_delay=10
        )
        
        # Check that strategies were initialized with the correct parameters
        mock_ma.assert_called_once_with(fast_period=5, slow_period=20)
        mock_rsi.assert_called_once_with(period=10, oversold=25, overbought=75)
        
        # Check that logger was initialized with the correct parameters
        mock_logger.assert_called_once_with(use_rich=True, log_file="test.log")


if __name__ == '__main__':
    unittest.main()