"""
Unit tests for the crypto alerts module.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
import datetime
import tempfile
import json
import shutil

from bot.crypto_logger import CryptoLogger
from bot.crypto_alerts import (
    AlertLevel, AlertType, CryptoAlert, CryptoAlertManager
)


class TestCryptoAlerts(unittest.TestCase):
    """Test cases for the crypto alerts module."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create a temporary log directory
        self.test_log_dir = os.path.join(self.test_dir, "logs")
        os.makedirs(self.test_log_dir, exist_ok=True)
        
        # Create logger with rich disabled for testing
        self.logger = CryptoLogger(
            log_dir=self.test_log_dir,
            use_rich=False
        )
        
        # Create alert manager
        self.config_path = os.path.join(self.test_dir, "alerts_config.json")
        self.history_path = os.path.join(self.test_dir, "alerts_history.json")
        self.alert_manager = CryptoAlertManager(
            logger=self.logger,
            config_path=self.config_path,
            alerts_history_path=self.history_path
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_alert_creation(self):
        """Test creating a crypto alert."""
        # Create alert
        alert = CryptoAlert(
            alert_type=AlertType.BALANCE_LOW,
            level=AlertLevel.WARNING,
            message="Low balance for BTC",
            timestamp=datetime.datetime.now(),
            details={"currency": "BTC", "balance": 0.001}
        )
        
        # Check alert properties
        self.assertEqual(alert.alert_type, AlertType.BALANCE_LOW)
        self.assertEqual(alert.level, AlertLevel.WARNING)
        self.assertEqual(alert.message, "Low balance for BTC")
        self.assertFalse(alert.acknowledged)
        self.assertIsNotNone(alert.alert_id)
        self.assertEqual(alert.details["currency"], "BTC")
    
    def test_alert_serialization(self):
        """Test serializing and deserializing alerts."""
        # Create alert
        alert = CryptoAlert(
            alert_type=AlertType.BALANCE_LOW,
            level=AlertLevel.WARNING,
            message="Low balance for BTC",
            timestamp=datetime.datetime.now(),
            details={"currency": "BTC", "balance": 0.001}
        )
        
        # Serialize to dict
        alert_dict = alert.to_dict()
        
        # Check serialized data
        self.assertEqual(alert_dict["alert_type"], "balance_low")
        self.assertEqual(alert_dict["level"], "warning")
        self.assertEqual(alert_dict["message"], "Low balance for BTC")
        
        # Deserialize from dict
        deserialized = CryptoAlert.from_dict(alert_dict)
        
        # Check deserialized alert
        self.assertEqual(deserialized.alert_type, AlertType.BALANCE_LOW)
        self.assertEqual(deserialized.level, AlertLevel.WARNING)
        self.assertEqual(deserialized.message, "Low balance for BTC")
        self.assertEqual(deserialized.details["currency"], "BTC")
    
    def test_alert_manager_initialization(self):
        """Test initializing the alert manager."""
        # Check that default config was created
        self.assertTrue(self.alert_manager.config["enabled"])
        self.assertIn("thresholds", self.alert_manager.config)
        self.assertIn("notifications", self.alert_manager.config)
        
        # Check that alert handlers were registered
        self.assertIn(AlertType.BALANCE_LOW, self.alert_manager.alert_handlers)
        self.assertTrue(len(self.alert_manager.alert_handlers[AlertType.BALANCE_LOW]) > 0)
    
    def test_trigger_alert(self):
        """Test triggering an alert."""
        # Trigger alert
        alert = self.alert_manager.trigger_alert(
            AlertType.BALANCE_LOW,
            AlertLevel.WARNING,
            "Low balance for BTC",
            {"currency": "BTC", "balance": 0.001}
        )
        
        # Check that alert was created
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, AlertType.BALANCE_LOW)
        self.assertEqual(alert.message, "Low balance for BTC")
        
        # Check that alert was added to active alerts
        self.assertIn(alert.alert_id, self.alert_manager.active_alerts)
        
        # Check that alerts history was saved
        self.assertTrue(os.path.exists(self.history_path))
    
    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        # Trigger alert
        alert = self.alert_manager.trigger_alert(
            AlertType.BALANCE_LOW,
            AlertLevel.WARNING,
            "Low balance for BTC",
            {"currency": "BTC", "balance": 0.001}
        )
        
        # Acknowledge alert
        result = self.alert_manager.acknowledge_alert(alert.alert_id)
        
        # Check that acknowledgement was successful
        self.assertTrue(result)
        
        # Check that alert was moved to history
        self.assertNotIn(alert.alert_id, self.alert_manager.active_alerts)
        self.assertTrue(any(a.alert_id == alert.alert_id for a in self.alert_manager.alerts_history))
    
    def test_alert_cooldown(self):
        """Test alert cooldown period."""
        # Trigger first alert
        alert1 = self.alert_manager.trigger_alert(
            AlertType.BALANCE_LOW,
            AlertLevel.WARNING,
            "Low balance for BTC",
            {"currency": "BTC", "balance": 0.001}
        )
        
        # Trigger second alert of same type
        alert2 = self.alert_manager.trigger_alert(
            AlertType.BALANCE_LOW,
            AlertLevel.WARNING,
            "Low balance for BTC",
            {"currency": "BTC", "balance": 0.0005}
        )
        
        # Second alert should be blocked by cooldown
        self.assertIsNone(alert2)
        
        # Trigger alert of different type
        alert3 = self.alert_manager.trigger_alert(
            AlertType.LARGE_PRICE_MOVEMENT,
            AlertLevel.WARNING,
            "Large price movement for BTC",
            {"symbol": "BTC/USD", "percent_change": 10.0}
        )
        
        # Different type should not be blocked
        self.assertIsNotNone(alert3)
    
    def test_check_balance_low(self):
        """Test checking for low balance."""
        # Check balance above threshold
        self.alert_manager.check_balance_low("BTC", 0.1, 5000.0)
        
        # No alert should be triggered
        self.assertEqual(len(self.alert_manager.active_alerts), 0)
        
        # Check balance below threshold
        self.alert_manager.check_balance_low("BTC", 0.001, 50.0)
        
        # Alert should be triggered
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.BALANCE_LOW)
        self.assertIn("BTC", alert.message)
    
    def test_check_price_movement(self):
        """Test checking for large price movement."""
        # Check small price movement
        self.alert_manager.check_price_movement("BTC/USD", 50000.0, 51000.0)
        
        # No alert should be triggered (2% change, below default 5% threshold)
        self.assertEqual(len(self.alert_manager.active_alerts), 0)
        
        # Check large price movement
        self.alert_manager.check_price_movement("BTC/USD", 50000.0, 55000.0)
        
        # Alert should be triggered (10% change)
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.LARGE_PRICE_MOVEMENT)
        self.assertIn("BTC/USD", alert.message)
        self.assertIn("up", alert.message)
    
    def test_check_api_error_rate(self):
        """Test checking for high API error rate."""
        # Check low error rate
        self.alert_manager.check_api_error_rate(0.05)
        
        # No alert should be triggered (5% error rate, below default 10% threshold)
        self.assertEqual(len(self.alert_manager.active_alerts), 0)
        
        # Check high error rate
        self.alert_manager.check_api_error_rate(0.15)
        
        # Alert should be triggered (15% error rate)
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.HIGH_API_ERROR_RATE)
        self.assertIn("15.00%", alert.message)
    
    def test_check_rate_limit(self):
        """Test checking for rate limit hits."""
        # Check few rate limit hits
        self.alert_manager.check_rate_limit(3)
        
        # No alert should be triggered (below default threshold of 5)
        self.assertEqual(len(self.alert_manager.active_alerts), 0)
        
        # Check many rate limit hits
        self.alert_manager.check_rate_limit(10)
        
        # Alert should be triggered
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.RATE_LIMIT_EXCEEDED)
        self.assertIn("10 hits", alert.message)
    
    def test_check_large_trade(self):
        """Test checking for large trades."""
        # Check small trade
        self.alert_manager.check_large_trade("BTC/USD", "BUY", 0.01, 50000.0)
        
        # No alert should be triggered (500 USD, below default threshold of 1000)
        self.assertEqual(len(self.alert_manager.active_alerts), 0)
        
        # Check large trade
        self.alert_manager.check_large_trade("BTC/USD", "BUY", 0.05, 50000.0)
        
        # Alert should be triggered (2500 USD)
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.LARGE_TRADE)
        self.assertIn("BUY", alert.message)
        self.assertIn("BTC/USD", alert.message)
    
    def test_alert_authentication_failure(self):
        """Test alerting for authentication failure."""
        # Trigger authentication failure alert
        self.alert_manager.alert_authentication_failure("Invalid API key")
        
        # Alert should be triggered
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.AUTHENTICATION_FAILURE)
        self.assertEqual(alert.level, AlertLevel.CRITICAL)
        self.assertIn("Invalid API key", alert.message)
    
    def test_alert_websocket_disconnection(self):
        """Test alerting for WebSocket disconnection."""
        # Trigger WebSocket disconnection alert
        self.alert_manager.alert_websocket_disconnection("Connection reset")
        
        # Alert should be triggered
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.WEBSOCKET_DISCONNECTION)
        self.assertEqual(alert.level, AlertLevel.WARNING)
        self.assertIn("Connection reset", alert.message)
    
    def test_check_system_performance(self):
        """Test checking system performance."""
        # Create a new alert manager with cooldown disabled for testing
        test_config_path = os.path.join(self.test_dir, "test_config.json")
        test_history_path = os.path.join(self.test_dir, "test_history.json")
        
        # Create a test config with cooldown disabled
        test_config = {
            "enabled": True,
            "cooldown_minutes": {
                "system_performance": 0  # Disable cooldown for this test
            }
        }
        
        with open(test_config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Create a new alert manager with the test config
        test_alert_manager = CryptoAlertManager(
            logger=self.logger,
            config_path=test_config_path,
            alerts_history_path=test_history_path
        )
        
        # Check normal performance
        test_alert_manager.check_system_performance(50.0, 60.0)
        
        # No alert should be triggered (below default thresholds)
        self.assertEqual(len(test_alert_manager.active_alerts), 0)
        
        # Check high CPU usage
        test_alert_manager.check_system_performance(90.0, 60.0)
        
        # Alert should be triggered
        self.assertEqual(len(test_alert_manager.active_alerts), 1)
        alert = list(test_alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.SYSTEM_PERFORMANCE)
        self.assertIn("CPU", alert.message)
        
        # Acknowledge alert
        test_alert_manager.acknowledge_alert(alert.alert_id)
        
        # Check high memory usage
        test_alert_manager.check_system_performance(50.0, 90.0)
        
        # Alert should be triggered
        self.assertEqual(len(test_alert_manager.active_alerts), 1)
        alert = list(test_alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.SYSTEM_PERFORMANCE)
        self.assertIn("memory", alert.message)
    
    def test_check_trading_volume_spike(self):
        """Test checking for trading volume spike."""
        # Check normal volume
        self.alert_manager.check_trading_volume_spike("BTC/USD", 1000.0, 1500.0)
        
        # No alert should be triggered (50% increase, below default threshold of 200%)
        self.assertEqual(len(self.alert_manager.active_alerts), 0)
        
        # Check volume spike
        self.alert_manager.check_trading_volume_spike("BTC/USD", 1000.0, 5000.0)
        
        # Alert should be triggered (400% increase)
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.TRADING_VOLUME_SPIKE)
        self.assertIn("BTC/USD", alert.message)
        self.assertIn("5.0x", alert.message)
    
    def test_check_position_limit(self):
        """Test checking for position limit."""
        # Check position below limit
        self.alert_manager.check_position_limit("BTC", 5000.0, 10000.0)
        
        # No alert should be triggered (50% of limit, below default threshold of 90%)
        self.assertEqual(len(self.alert_manager.active_alerts), 0)
        
        # Check position near limit
        self.alert_manager.check_position_limit("BTC", 9500.0, 10000.0)
        
        # Alert should be triggered (95% of limit)
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        alert = list(self.alert_manager.active_alerts.values())[0]
        self.assertEqual(alert.alert_type, AlertType.POSITION_LIMIT_REACHED)
        self.assertIn("BTC", alert.message)
        self.assertIn("95.0%", alert.message)
    
    @patch("smtplib.SMTP")
    def test_email_alert(self, mock_smtp):
        """Test sending email alert."""
        # Configure email notifications
        self.alert_manager.config["notifications"]["email"]["enabled"] = True
        self.alert_manager.config["notifications"]["email"]["smtp_server"] = "smtp.example.com"
        self.alert_manager.config["notifications"]["email"]["smtp_port"] = 587
        self.alert_manager.config["notifications"]["email"]["username"] = "test@example.com"
        self.alert_manager.config["notifications"]["email"]["password"] = "password"
        self.alert_manager.config["notifications"]["email"]["from_address"] = "test@example.com"
        self.alert_manager.config["notifications"]["email"]["to_addresses"] = ["admin@example.com"]
        
        # Mock SMTP instance
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance
        
        # Trigger critical alert
        self.alert_manager.trigger_alert(
            AlertType.AUTHENTICATION_FAILURE,
            AlertLevel.CRITICAL,
            "Authentication failed",
            {"error": "Invalid API key"}
        )
        
        # Check that email was sent
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("test@example.com", "password")
        mock_smtp_instance.send_message.assert_called_once()
        mock_smtp_instance.quit.assert_called_once()
    
    @patch("requests.post")
    def test_webhook_alert(self, mock_post):
        """Test sending webhook alert."""
        # Configure webhook notifications
        self.alert_manager.config["notifications"]["webhook"]["enabled"] = True
        self.alert_manager.config["notifications"]["webhook"]["url"] = "https://example.com/webhook"
        self.alert_manager.config["notifications"]["webhook"]["headers"] = {"Authorization": "Bearer token"}
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Trigger alert
        self.alert_manager.trigger_alert(
            AlertType.BALANCE_LOW,
            AlertLevel.WARNING,
            "Low balance for BTC",
            {"currency": "BTC", "balance": 0.001}
        )
        
        # Check that webhook was sent
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://example.com/webhook")
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer token"})
        self.assertIn("alert", kwargs["json"])
        self.assertEqual(kwargs["json"]["alert"]["alert_type"], "balance_low")


if __name__ == "__main__":
    unittest.main()