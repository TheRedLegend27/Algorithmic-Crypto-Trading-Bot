"""
Integration tests for the error handling system.
"""
import unittest
from unittest.mock import MagicMock, patch

from bot.error_handler import ErrorHandler, handle_error, ErrorCategory
from bot.utils import retry_with_backoff, safe_execute


class TestErrorIntegration(unittest.TestCase):
    """Test cases for error handling integration with other components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.error_handler = ErrorHandler()
    
    def test_retry_with_backoff_integration(self):
        """Test integration between retry_with_backoff and error handler"""
        # Create a function that fails twice then succeeds
        mock_func = MagicMock()
        mock_func.side_effect = [
            ConnectionError("Network error"),
            ConnectionError("Network error"),
            "success"
        ]
        
        # Apply retry_with_backoff decorator
        decorated_func = retry_with_backoff(
            max_retries=3,
            initial_delay=0.01,
            exceptions=(ConnectionError,)
        )(mock_func)
        
        # Execute with patched sleep to avoid actual delays
        with patch("time.sleep"):
            result = decorated_func()
        
        # Verify function was called 3 times and returned success
        self.assertEqual(mock_func.call_count, 3)
        self.assertEqual(result, "success")
    
    def test_safe_execute_integration(self):
        """Test integration between safe_execute and error handler"""
        # Create a function that raises an exception
        def failing_func():
            raise ValueError("Data error")
        
        # Execute safely with default return value
        with patch("bot.utils.log_error") as mock_log_error:
            result = safe_execute(failing_func, default_return="fallback")
        
        # Verify function failed gracefully and logged the error
        self.assertEqual(result, "fallback")
        mock_log_error.assert_called_once()
    
    def test_handle_error_with_utils(self):
        """Test handle_error integration with utility functions"""
        # Create a mock recovery strategy
        mock_strategy = MagicMock()
        mock_strategy.can_recover.return_value = True
        mock_strategy.execute.return_value = True
        
        # Register the mock strategy
        self.error_handler.register_recovery_strategy(ErrorCategory.DATA_ERROR, mock_strategy)
        
        # Handle an error with the global handler
        with patch("bot.error_handler.global_error_handler", self.error_handler):
            result = handle_error(ValueError("Data error"), "test_component")
        
        # Verify error was handled successfully
        self.assertTrue(result)
        mock_strategy.execute.assert_called_once()
    
    def test_error_handler_with_retry(self):
        """Test error handler with retry recovery strategy"""
        # Create a function that fails with API error
        def api_function():
            raise Exception("API rate limit exceeded")
        
        # Create a wrapper that uses error handler
        def wrapper():
            try:
                return api_function()
            except Exception as e:
                if self.error_handler.handle_error(e, "api_component"):
                    # If recovery was successful, retry
                    return api_function()
                raise
        
        # Create a mock retry strategy that just sets a flag
        retry_attempted = False
        
        class TestRetryStrategy:
            def can_recover(self, _):
                return True
                
            def execute(self, _):
                nonlocal retry_attempted
                retry_attempted = True
                return True
        
        # Register the test strategy
        self.error_handler.register_recovery_strategy(
            ErrorCategory.API_ERROR,
            TestRetryStrategy()
        )
        
        # Execute with expected failure
        with self.assertRaises(Exception):
            wrapper()
        
        # Verify retry was attempted
        self.assertTrue(retry_attempted)


if __name__ == "__main__":
    unittest.main()