"""
Unit tests for the ErrorHandler class.
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import time
import requests
from datetime import datetime, timedelta

from bot.error_handler import (
    ErrorHandler, ErrorType, ErrorSeverity, with_error_handling
)


class TestErrorHandler(unittest.TestCase):
    """Test cases for the ErrorHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_classify_error_rate_limit(self):
        """Test error classification for rate limit errors."""
        error = Exception("Rate limit exceeded")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.API_RATE_LIMIT)
        self.assertEqual(severity, ErrorSeverity.MEDIUM)
        
        error = Exception("429 Too Many Requests")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.API_RATE_LIMIT)
    
    def test_classify_error_auth(self):
        """Test error classification for authentication errors."""
        error = Exception("Authentication failed")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.API_AUTH)
        self.assertEqual(severity, ErrorSeverity.HIGH)
        
        error = Exception("401 Unauthorized")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.API_AUTH)
    
    def test_classify_error_network(self):
        """Test error classification for network errors."""
        error = requests.exceptions.ConnectionError("Connection failed")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.NETWORK)
        self.assertEqual(severity, ErrorSeverity.MEDIUM)
        
        error = requests.exceptions.Timeout("Request timed out")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.NETWORK)
    
    def test_classify_error_data_validation(self):
        """Test error classification for data validation errors."""
        error = Exception("Data validation failed")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.DATA_VALIDATION)
        self.assertEqual(severity, ErrorSeverity.MEDIUM)
    
    def test_classify_error_trade_execution(self):
        """Test error classification for trade execution errors."""
        error = Exception("Order placement failed")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.TRADE_EXECUTION)
        self.assertEqual(severity, ErrorSeverity.HIGH)
    
    def test_classify_error_system(self):
        """Test error classification for system errors."""
        error = Exception("Out of memory")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.SYSTEM)
        self.assertEqual(severity, ErrorSeverity.HIGH)
    
    def test_classify_error_unknown(self):
        """Test error classification for unknown errors."""
        error = Exception("Some random error")
        error_type, severity = self.error_handler.classify_error(error)
        self.assertEqual(error_type, ErrorType.UNKNOWN)
        self.assertEqual(severity, ErrorSeverity.MEDIUM)
    
    def test_handle_error(self):
        """Test error handling logic."""
        error = Exception("Rate limit exceeded")
        recoverable, recovery_info = self.error_handler.handle_error(error, "test_context")
        
        self.assertTrue(recoverable)
        self.assertTrue(recovery_info["retry"])
        self.assertEqual(recovery_info["retry_delay"], 5)
        self.assertEqual(recovery_info["max_retries"], 5)
        self.assertEqual(recovery_info["fallback_action"], "skip_cycle")
    
    def test_track_error(self):
        """Test error tracking functionality."""
        error_type = ErrorType.API_RATE_LIMIT
        
        # Track error multiple times
        for _ in range(3):
            self.error_handler._track_error(error_type)
        
        self.assertEqual(self.error_handler.error_counts[error_type], 3)
        self.assertEqual(len(self.error_handler.error_timestamps[error_type]), 3)
    
    def test_get_recovery_strategy(self):
        """Test recovery strategy selection."""
        # Test API rate limit strategy
        strategy = self.error_handler._get_recovery_strategy(ErrorType.API_RATE_LIMIT, ErrorSeverity.MEDIUM)
        self.assertTrue(strategy["retry"])
        self.assertEqual(strategy["retry_delay"], 5)
        self.assertEqual(strategy["fallback_action"], "skip_cycle")
        
        # Test authentication error strategy
        strategy = self.error_handler._get_recovery_strategy(ErrorType.API_AUTH, ErrorSeverity.HIGH)
        self.assertFalse(strategy["retry"])
        self.assertEqual(strategy["fallback_action"], "exit")
        
        # Test network error strategy
        strategy = self.error_handler._get_recovery_strategy(ErrorType.NETWORK, ErrorSeverity.MEDIUM)
        self.assertTrue(strategy["retry"])
        self.assertEqual(strategy["retry_delay"], 3)
        self.assertEqual(strategy["fallback_action"], "skip_cycle")
        
        # Test data validation error strategy
        strategy = self.error_handler._get_recovery_strategy(ErrorType.DATA_VALIDATION, ErrorSeverity.MEDIUM)
        self.assertTrue(strategy["retry"])
        self.assertEqual(strategy["fallback_action"], "use_previous_data")
        
        # Test trade execution error strategy
        strategy = self.error_handler._get_recovery_strategy(ErrorType.TRADE_EXECUTION, ErrorSeverity.HIGH)
        self.assertTrue(strategy["retry"])
        self.assertEqual(strategy["fallback_action"], "skip_trade")
        
        # Test system error strategy
        strategy = self.error_handler._get_recovery_strategy(ErrorType.SYSTEM, ErrorSeverity.HIGH)
        self.assertFalse(strategy["retry"])
        self.assertEqual(strategy["fallback_action"], "restart")
        
        # Test unknown error strategy
        strategy = self.error_handler._get_recovery_strategy(ErrorType.UNKNOWN, ErrorSeverity.MEDIUM)
        self.assertTrue(strategy["retry"])
        self.assertEqual(strategy["fallback_action"], "skip_cycle")
    
    def test_calculate_backoff_delay(self):
        """Test backoff delay calculation."""
        # Test without jitter
        delay = self.error_handler.calculate_backoff_delay(1.0, 0, 2.0, False)
        self.assertEqual(delay, 1.0)
        
        delay = self.error_handler.calculate_backoff_delay(1.0, 1, 2.0, False)
        self.assertEqual(delay, 2.0)
        
        delay = self.error_handler.calculate_backoff_delay(1.0, 2, 2.0, False)
        self.assertEqual(delay, 4.0)
        
        # Test with jitter (can only test range)
        with patch('random.uniform', return_value=0.1):
            delay = self.error_handler.calculate_backoff_delay(1.0, 0, 2.0, True)
            self.assertAlmostEqual(delay, 1.1)
    
    def test_load_config(self):
        """Test configuration loading."""
        mock_config = {
            "notification": {
                "enabled": True,
                "email": {
                    "enabled": True,
                    "smtp_server": "test.smtp.com"
                }
            },
            "notification_cooldown": 1800
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))), \
             patch('os.path.exists', return_value=True):
            self.error_handler._load_config("dummy_path")
            
            self.assertTrue(self.error_handler.notification_config["enabled"])
            self.assertTrue(self.error_handler.notification_config["email"]["enabled"])
            self.assertEqual(self.error_handler.notification_config["email"]["smtp_server"], "test.smtp.com")
            self.assertEqual(self.error_handler.notification_cooldown, 1800)
    
    def test_send_notification_cooldown(self):
        """Test notification cooldown logic."""
        # Enable notifications
        self.error_handler.notification_config["enabled"] = True
        
        # Set up a recent notification time
        error_type = ErrorType.API_RATE_LIMIT
        self.error_handler.last_notification_time[error_type] = datetime.now()
        
        # Try to send notification (should be blocked by cooldown)
        result = self.error_handler._send_notification(
            Exception("Test error"),
            error_type,
            ErrorSeverity.HIGH,
            "test_context"
        )
        
        self.assertFalse(result)
        
        # Set notification time to be outside cooldown period
        self.error_handler.last_notification_time[error_type] = datetime.now() - timedelta(seconds=3700)
        
        # Mock email and webhook sending
        with patch.object(self.error_handler, '_send_email_notification', return_value=True), \
             patch.object(self.error_handler, '_send_webhook_notification', return_value=False):
            
            # Enable email notifications
            self.error_handler.notification_config["email"]["enabled"] = True
            
            # Try to send notification (should work now)
            result = self.error_handler._send_notification(
                Exception("Test error"),
                error_type,
                ErrorSeverity.HIGH,
                "test_context"
            )
            
            self.assertTrue(result)
    
    def test_send_email_notification(self):
        """Test email notification sending."""
        with patch('smtplib.SMTP') as mock_smtp:
            # Configure mock
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            # Configure email settings
            self.error_handler.notification_config["email"] = {
                "enabled": True,
                "smtp_server": "smtp.test.com",
                "smtp_port": 587,
                "username": "test_user",
                "password": "test_pass",
                "from_email": "from@test.com",
                "to_email": "to@test.com"
            }
            
            # Send notification
            result = self.error_handler._send_email_notification(
                "Test Subject",
                "Test Message"
            )
            
            # Verify result and SMTP calls
            self.assertTrue(result)
            mock_smtp.assert_called_once_with("smtp.test.com", 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("test_user", "test_pass")
            mock_server.send_message.assert_called_once()
            mock_server.quit.assert_called_once()
    
    def test_send_webhook_notification(self):
        """Test webhook notification sending."""
        with patch('requests.post') as mock_post:
            # Configure mock
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            # Configure webhook settings
            self.error_handler.notification_config["webhook"] = {
                "enabled": True,
                "url": "https://webhook.test.com",
                "headers": {"Content-Type": "application/json"}
            }
            
            # Send notification
            result = self.error_handler._send_webhook_notification(
                "Test Subject",
                "Test Message"
            )
            
            # Verify result and requests call
            self.assertTrue(result)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(kwargs["url"], "https://webhook.test.com")
            self.assertEqual(kwargs["headers"], {"Content-Type": "application/json"})
            self.assertIn("subject", kwargs["json"])
            self.assertIn("message", kwargs["json"])
    
    def test_detect_error_patterns(self):
        """Test error pattern detection."""
        error_type = ErrorType.API_RATE_LIMIT
        
        # No errors recorded
        pattern = self.error_handler.detect_error_patterns(error_type)
        self.assertEqual(pattern["count"], 0)
        self.assertEqual(pattern["frequency"], 0)
        self.assertFalse(pattern["increasing"])
        
        # Add some errors
        now = datetime.now()
        self.error_handler.error_timestamps[error_type] = [
            now - timedelta(minutes=50),
            now - timedelta(minutes=40),
            now - timedelta(minutes=30),
            now - timedelta(minutes=20),
            now - timedelta(minutes=10),
            now
        ]
        
        # Check pattern detection
        pattern = self.error_handler.detect_error_patterns(error_type, 3600)
        self.assertEqual(pattern["count"], 6)
        self.assertAlmostEqual(pattern["frequency"], 6.0, places=1)  # 6 errors per hour
    
    def test_should_circuit_break(self):
        """Test circuit breaker logic."""
        error_type = ErrorType.API_RATE_LIMIT
        
        # No errors recorded
        self.assertFalse(self.error_handler.should_circuit_break(error_type))
        
        # Add errors below threshold
        now = datetime.now()
        self.error_handler.error_timestamps[error_type] = [
            now - timedelta(seconds=10),
            now - timedelta(seconds=20),
            now - timedelta(seconds=30),
        ]
        
        # Check circuit breaker (should not trigger)
        self.assertFalse(self.error_handler.should_circuit_break(error_type, threshold=5))
        
        # Add more errors to exceed threshold
        self.error_handler.error_timestamps[error_type].extend([
            now - timedelta(seconds=40),
            now - timedelta(seconds=50),
            now - timedelta(seconds=60),
            now - timedelta(seconds=70),
            now
        ])
        
        # Check circuit breaker (should trigger)
        self.assertTrue(self.error_handler.should_circuit_break(error_type, threshold=5))
    
    def test_get_error_stats(self):
        """Test error statistics retrieval."""
        # Add some error counts
        self.error_handler.error_counts = {
            ErrorType.API_RATE_LIMIT: 10,
            ErrorType.NETWORK: 5
        }
        
        # Add some timestamps
        now = datetime.now()
        self.error_handler.error_timestamps[ErrorType.API_RATE_LIMIT] = [
            now - timedelta(minutes=30),
            now - timedelta(minutes=20),
            now - timedelta(minutes=10)
        ]
        
        # Get stats
        stats = self.error_handler.get_error_stats()
        
        # Verify stats
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[ErrorType.API_RATE_LIMIT]["total_count"], 10)
        self.assertEqual(stats[ErrorType.NETWORK]["total_count"], 5)
        self.assertEqual(stats[ErrorType.API_RATE_LIMIT]["recent"]["count"], 3)
    
    def test_with_error_handling_decorator(self):
        """Test the error handling decorator."""
        # Create a test function that raises an exception
        @with_error_handling(self.error_handler, "test_context", max_retries=2)
        def test_function():
            raise Exception("Test error")
        
        # Mock handle_error to avoid actual error handling
        with patch.object(self.error_handler, 'handle_error') as mock_handle_error, \
             patch('time.sleep'):
            
            # Configure mock to indicate recoverable error with retry
            mock_handle_error.return_value = (True, {
                "retry": True,
                "retry_delay": 1,
                "backoff_factor": 2.0,
                "jitter": False,
                "fallback_action": "skip_cycle"
            })
            
            # Call function (should retry twice then return None for skip_cycle)
            result = test_function()
            
            # Verify error handling
            self.assertEqual(mock_handle_error.call_count, 3)  # Initial + 2 retries
            self.assertIsNone(result)  # skip_cycle returns None
    
    def test_with_error_handling_success(self):
        """Test the error handling decorator with successful execution."""
        # Create a test function that succeeds on the second try
        attempt = [0]
        
        @with_error_handling(self.error_handler, "test_context", max_retries=2)
        def test_function():
            attempt[0] += 1
            if attempt[0] == 1:
                raise Exception("Test error")
            return "success"
        
        # Mock handle_error to avoid actual error handling
        with patch.object(self.error_handler, 'handle_error') as mock_handle_error, \
             patch('time.sleep'):
            
            # Configure mock to indicate recoverable error with retry
            mock_handle_error.return_value = (True, {
                "retry": True,
                "retry_delay": 1,
                "backoff_factor": 2.0,
                "jitter": False
            })
            
            # Call function (should succeed on second try)
            result = test_function()
            
            # Verify error handling
            self.assertEqual(mock_handle_error.call_count, 1)  # Only the first attempt fails
            self.assertEqual(result, "success")


if __name__ == '__main__':
    unittest.main()