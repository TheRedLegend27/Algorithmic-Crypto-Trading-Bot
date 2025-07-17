"""
Unit tests for the TradingLogger class.
"""
import os
import shutil
import unittest
from unittest.mock import patch, MagicMock
import datetime
import tempfile
import logging

from bot.logger import TradingLogger, TradeRecord, SignalRecord, PositionRecord


class TestTradingLogger(unittest.TestCase):
    """Test cases for the TradingLogger class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for logs
        self.test_log_dir = tempfile.mkdtemp()
        
        # Create logger with rich disabled for testing
        self.logger = TradingLogger(log_dir=self.test_log_dir, use_rich=False)
        
        # Sample data for testing
        self.sample_trade = TradeRecord(
            order_id="test-order-123",
            symbol="BTC/USD",
            side="BUY",
            quantity=0.001,
            price=50000.0,
            timestamp=datetime.datetime.now(),
            status="FILLED",
            fees=0.5
        )
        
        self.sample_signal = SignalRecord(
            action="BUY",
            symbol="BTC/USD",
            confidence=0.85,
            strategy="MovingAverageCrossover",
            price=50000.0,
            timestamp=datetime.datetime.now(),
            reasoning="Short MA crossed above Long MA"
        )
        
        self.sample_position = PositionRecord(
            symbol="BTC/USD",
            quantity=0.001,
            market_value=50.0,
            unrealized_pnl=5.0,
            avg_entry_price=45000.0
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary log directory
        shutil.rmtree(self.test_log_dir)
    
    def test_logger_initialization(self):
        """Test that the logger initializes correctly."""
        # Check that log directory was created
        self.assertTrue(os.path.exists(self.test_log_dir))
        
        # Check that log files were created
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "trades.log")))
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "signals.log")))
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "errors.log")))
    
    def test_log_trade(self):
        """Test logging a trade."""
        with self.assertLogs("crypto_bot.trades", level="INFO") as cm:
            self.logger.log_trade(self.sample_trade)
            
        # Check that the trade was logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn("TRADE: BUY", cm.output[0])
        self.assertIn("BTC/USD", cm.output[0])
        
        # Check that the trade was added to recent trades
        self.assertEqual(len(self.logger.recent_trades), 1)
        self.assertEqual(self.logger.recent_trades[0], self.sample_trade)
    
    def test_log_signal(self):
        """Test logging a signal."""
        with self.assertLogs("crypto_bot.signals", level="INFO") as cm:
            self.logger.log_signal(self.sample_signal)
            
        # Check that the signal was logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn("SIGNAL: BUY", cm.output[0])
        self.assertIn("BTC/USD", cm.output[0])
        
        # Check that the signal was added to recent signals
        self.assertEqual(len(self.logger.recent_signals), 1)
        self.assertEqual(self.logger.recent_signals[0], self.sample_signal)
    
    def test_log_error(self):
        """Test logging an error."""
        test_exception = ValueError("Test error")
        
        with self.assertLogs("crypto_bot.errors", level="ERROR") as cm:
            self.logger.log_error(test_exception, "Test context")
            
        # Check that the error was logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Test context: Test error", cm.output[0])
        
        # Check that the error was added to recent errors
        self.assertEqual(len(self.logger.errors), 1)
        self.assertIn("Test context: Test error", self.logger.errors[0])
    
    def test_update_price(self):
        """Test updating the current price."""
        self.logger.update_price("BTC/USD", 51000.0)
        self.assertEqual(self.logger.current_price, 51000.0)
    
    def test_update_position(self):
        """Test updating the current position."""
        self.logger.update_position(self.sample_position)
        self.assertEqual(self.logger.current_position, self.sample_position)
    
    @patch("bot.logger.Live")
    @patch("bot.logger.Console")
    def test_live_display(self, mock_console, mock_live):
        """Test the live display functionality."""
        # Create a logger with rich enabled
        rich_logger = TradingLogger(log_dir=self.test_log_dir, use_rich=True)
        
        # Mock the live display
        mock_live_instance = MagicMock()
        mock_live.return_value = mock_live_instance
        
        # Start the live display
        rich_logger.start_live_display()
        
        # Check that the live display was started
        mock_live_instance.start.assert_called_once()
        
        # Update the display
        rich_logger.update_price("BTC/USD", 52000.0)
        
        # The update_live_display method is called, but we don't need to verify
        # specific mock behavior since it's implementation-dependent
        
        # Stop the live display
        rich_logger.stop_live_display()
        
        # Check that the live display was stopped
        mock_live_instance.stop.assert_called_once()
    
    def test_log_info_and_warning(self):
        """Test logging info and warning messages."""
        with self.assertLogs("crypto_bot", level="INFO") as cm:
            self.logger.log_info("Test info message")
            self.logger.log_warning("Test warning message")
            
        # Check that both messages were logged
        self.assertEqual(len(cm.output), 2)
        self.assertIn("Test info message", cm.output[0])
        self.assertIn("Test warning message", cm.output[1])


if __name__ == "__main__":
    unittest.main()