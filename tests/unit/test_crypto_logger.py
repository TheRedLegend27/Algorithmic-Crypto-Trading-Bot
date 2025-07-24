"""
Unit tests for the CryptoLogger class.
"""
import os
import shutil
import unittest
from unittest.mock import patch, MagicMock
import datetime
import tempfile
import logging
import json

from bot.crypto_logger import (
    CryptoLogger, CryptoTradeRecord, CryptoBalanceRecord, CryptoMetricsRecord
)


class TestCryptoLogger(unittest.TestCase):
    """Test cases for the CryptoLogger class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for logs
        self.test_log_dir = tempfile.mkdtemp()
        
        # Create logger with rich disabled for testing
        self.logger = CryptoLogger(
            log_dir=self.test_log_dir,
            use_rich=False,
            metrics_interval_seconds=1  # Short interval for testing
        )
        
        # Sample data for testing
        self.sample_crypto_trade = CryptoTradeRecord(
            order_id="test-order-123",
            symbol="BTC/USD",
            side="BUY",
            quantity=0.001,
            price=50000.0,
            timestamp=datetime.datetime.now(),
            status="FILLED",
            product_id="BTC-USD",
            base_currency="BTC",
            quote_currency="USD",
            fees=0.5,
            fee_currency="USD",
            network_fee=0.0,
            exchange_fee=0.5,
            trade_type="spot"
        )
        
        self.sample_balance = CryptoBalanceRecord(
            currency="BTC",
            available=0.001,
            hold=0.0,
            total=0.001,
            usd_value=50.0,
            timestamp=datetime.datetime.now()
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary log directory
        shutil.rmtree(self.test_log_dir)
    
    def test_logger_initialization(self):
        """Test that the crypto logger initializes correctly."""
        # Check that log directory was created
        self.assertTrue(os.path.exists(self.test_log_dir))
        
        # Check that log files were created
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "trades.log")))
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "signals.log")))
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "errors.log")))
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "balances.log")))
        self.assertTrue(os.path.exists(os.path.join(self.test_log_dir, "metrics.log")))
    
    def test_log_crypto_trade(self):
        """Test logging a crypto trade."""
        with self.assertLogs("crypto_bot", level="INFO") as cm:
            self.logger.log_crypto_trade(self.sample_crypto_trade)
            
        # Check that the crypto trade was logged
        crypto_trade_logs = [log for log in cm.output if "CRYPTO_TRADE" in log]
        self.assertEqual(len(crypto_trade_logs), 1)
        self.assertIn("CRYPTO_TRADE: BUY", crypto_trade_logs[0])
        self.assertIn("BTC", crypto_trade_logs[0])
        
        # Check that the trade was added to recent trades
        self.assertEqual(len(self.logger.recent_crypto_trades), 1)
        self.assertEqual(self.logger.recent_crypto_trades[0], self.sample_crypto_trade)
        
        # Check that metrics were updated
        self.assertEqual(self.logger.current_metrics.trades_executed, 1)
        self.assertEqual(self.logger.current_metrics.trade_volume_usd, 50.0)  # 0.001 * 50000
        self.assertEqual(self.logger.current_metrics.fees_paid_usd, 0.5)
    
    def test_log_balance_update(self):
        """Test logging a balance update."""
        with self.assertLogs("crypto_bot.balances", level="INFO") as cm:
            self.logger.log_balance_update(self.sample_balance)
            
        # Check that the balance was logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn("BALANCE: BTC", cm.output[0])
        self.assertIn("Available: 0.00100000", cm.output[0])
        
        # Check that the balance was stored
        self.assertIn("BTC", self.logger.crypto_balances)
        self.assertEqual(self.logger.crypto_balances["BTC"], self.sample_balance)
    
    def test_log_api_call(self):
        """Test logging an API call."""
        # Log a successful API call
        self.logger.log_api_call("/api/products", 50.0, True)
        
        # Check that metrics were updated
        self.assertEqual(self.logger.current_metrics.api_calls, 1)
        self.assertEqual(self.logger.current_metrics.api_latency_ms, 50.0)
        self.assertEqual(self.logger.current_metrics.api_errors, 0)
        
        # Log a failed API call with high latency
        with self.assertLogs("crypto_bot.metrics", level="INFO") as cm:
            self.logger.log_api_call("/api/orders", 1500.0, False)
            
        # Check that the error was logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn("API_CALL", cm.output[0])
        self.assertIn("ERROR", cm.output[0])
        
        # Check that metrics were updated
        self.assertEqual(self.logger.current_metrics.api_calls, 2)
        # Latency should be weighted average: 0.9 * 50 + 0.1 * 1500 = 45 + 150 = 195
        self.assertAlmostEqual(self.logger.current_metrics.api_latency_ms, 195.0, delta=1.0)
        self.assertEqual(self.logger.current_metrics.api_errors, 1)
    
    def test_log_websocket_message(self):
        """Test logging a WebSocket message."""
        # Log a successful WebSocket message
        self.logger.log_websocket_message("ticker", True)
        
        # Check that metrics were updated
        self.assertEqual(self.logger.current_metrics.websocket_messages, 1)
        self.assertEqual(self.logger.current_metrics.websocket_errors, 0)
        
        # Log a failed WebSocket message
        with self.assertLogs("crypto_bot.metrics", level="WARNING") as cm:
            self.logger.log_websocket_message("orders", False)
            
        # Check that the error was logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn("WEBSOCKET_ERROR", cm.output[0])
        
        # Check that metrics were updated
        self.assertEqual(self.logger.current_metrics.websocket_messages, 2)
        self.assertEqual(self.logger.current_metrics.websocket_errors, 1)
    
    def test_log_rate_limit_hit(self):
        """Test logging a rate limit hit."""
        with self.assertLogs("crypto_bot.metrics", level="WARNING") as cm:
            self.logger.log_rate_limit_hit("/api/orders", 30)
            
        # Check that the rate limit hit was logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn("RATE_LIMIT", cm.output[0])
        
        # Check that metrics were updated
        self.assertEqual(self.logger.current_metrics.rate_limit_hits, 1)
    
    def test_metrics_recording(self):
        """Test that metrics are recorded at the specified interval."""
        # Set up metrics
        self.logger.log_api_call("/api/products", 50.0, True)
        self.logger.log_websocket_message("ticker", True)
        self.logger.log_crypto_trade(self.sample_crypto_trade)
        
        # Force metrics recording by setting last_metrics_time in the past
        self.logger.last_metrics_time = datetime.datetime.now() - datetime.timedelta(seconds=2)
        
        # Log another API call to trigger metrics recording
        with self.assertLogs("crypto_bot.metrics", level="INFO") as cm:
            self.logger.log_api_call("/api/orders", 60.0, True)
            
        # Check that metrics were recorded
        self.assertEqual(len(cm.output), 1)
        self.assertIn("METRICS", cm.output[0])
        
        # Check that metrics history was updated
        self.assertEqual(len(self.logger.metrics_history), 1)
        
        # Check that current metrics were reset
        # Note: The current metrics are reset after recording, but the new API call is already counted
        self.assertEqual(self.logger.current_metrics.api_calls, 0)
    
    def test_get_portfolio_summary(self):
        """Test getting portfolio summary."""
        # Add some balances
        self.logger.log_balance_update(self.sample_balance)  # BTC: $50
        
        eth_balance = CryptoBalanceRecord(
            currency="ETH",
            available=0.02,
            hold=0.0,
            total=0.02,
            usd_value=30.0,
            timestamp=datetime.datetime.now()
        )
        self.logger.log_balance_update(eth_balance)  # ETH: $30
        
        # Get portfolio summary
        summary = self.logger.get_portfolio_summary()
        
        # Check summary
        self.assertEqual(summary["total_usd_value"], 80.0)  # $50 + $30
        self.assertEqual(len(summary["balances"]), 2)
        self.assertEqual(summary["balances"]["BTC"]["usd_value"], 50.0)
        self.assertEqual(summary["balances"]["ETH"]["usd_value"], 30.0)
        self.assertEqual(summary["balances"]["BTC"]["percentage"], 62.5)  # 50/80 * 100
        self.assertEqual(summary["balances"]["ETH"]["percentage"], 37.5)  # 30/80 * 100
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        # Add some metrics history
        metrics1 = CryptoMetricsRecord(
            timestamp=datetime.datetime.now(),
            api_calls=100,
            api_errors=2,
            api_latency_ms=50.0,
            websocket_messages=500,
            websocket_errors=1,
            trades_executed=5,
            trade_volume_usd=1000.0,
            rate_limit_hits=1
        )
        
        metrics2 = CryptoMetricsRecord(
            timestamp=datetime.datetime.now(),
            api_calls=150,
            api_errors=3,
            api_latency_ms=60.0,
            websocket_messages=600,
            websocket_errors=2,
            trades_executed=7,
            trade_volume_usd=1500.0,
            rate_limit_hits=2
        )
        
        self.logger.metrics_history = [metrics1, metrics2]
        self.logger.metrics_interval_seconds = 60  # 1 minute
        
        # Get performance metrics
        metrics = self.logger.get_performance_metrics()
        
        # Check metrics
        self.assertEqual(metrics["api_calls_per_minute"], 125.0)  # (100 + 150) / 2
        self.assertEqual(metrics["api_errors_rate"], 0.02)  # (2 + 3) / (100 + 150)
        self.assertAlmostEqual(metrics["avg_latency_ms"], 56.0, delta=0.1)  # Weighted average
        self.assertEqual(metrics["websocket_messages_per_minute"], 550.0)  # (500 + 600) / 2
        self.assertAlmostEqual(metrics["websocket_error_rate"], 0.0027, delta=0.0001)  # (1 + 2) / (500 + 600)
        self.assertEqual(metrics["trades_per_minute"], 6.0)  # (5 + 7) / 2
        self.assertAlmostEqual(metrics["avg_trade_size_usd"], 208.33, delta=0.01)  # (1000 + 1500) / (5 + 7)
        self.assertEqual(metrics["rate_limit_hits"], 3)  # 1 + 2
    
    def test_export_metrics_to_json(self):
        """Test exporting metrics to JSON."""
        # Add some data
        self.logger.log_balance_update(self.sample_balance)
        self.logger.log_crypto_trade(self.sample_crypto_trade)
        
        # Force metrics recording
        self.logger.last_metrics_time = datetime.datetime.now() - datetime.timedelta(seconds=2)
        self.logger.log_api_call("/api/orders", 60.0, True)
        
        # Export metrics
        export_path = os.path.join(self.test_log_dir, "metrics_export.json")
        self.logger.export_metrics_to_json(export_path)
        
        # Check that file was created
        self.assertTrue(os.path.exists(export_path))
        
        # Check file contents
        with open(export_path, 'r') as f:
            data = json.load(f)
            
        self.assertIn("portfolio", data)
        self.assertIn("performance", data)
        self.assertIn("metrics_history", data)
        self.assertIn("balances", data)
        self.assertIn("BTC", data["balances"])
    
    @patch("bot.logger.Live")
    @patch("bot.logger.Console")
    def test_update_live_display(self, mock_console, mock_live):
        """Test updating the live display."""
        # Create a logger with rich enabled
        rich_logger = CryptoLogger(log_dir=self.test_log_dir, use_rich=True)
        
        # Mock the live display
        mock_live_instance = MagicMock()
        mock_live.return_value = mock_live_instance
        
        # Start the live display
        rich_logger.start_live_display()
        
        # Add some data
        rich_logger.log_balance_update(self.sample_balance)
        rich_logger.log_crypto_trade(self.sample_crypto_trade)
        
        # Update the display
        rich_logger.update_live_display()
        
        # Stop the live display
        rich_logger.stop_live_display()
        
        # Check that the live display was started and stopped
        mock_live_instance.start.assert_called_once()
        mock_live_instance.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()