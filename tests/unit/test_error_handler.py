"""
Unit tests for the error handler module.
"""
import unittest
import time
from unittest.mock import MagicMock, patch

from bot.error_handler import (
    ErrorHandler, ErrorCategory, ErrorContext, 
    RecoveryStrategy, RetryRecoveryStrategy, FallbackRecoveryStrategy,
    ErrorReport
)


class TestErrorHandler(unittest.TestCase):
    """Test cases for the ErrorHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.logger = MagicMock()
        self.error_handler = ErrorHandler(logger=self.logger)
    
    def test_categorize_error(self):
        """Test error categorization"""
        # API errors
        api_error = Exception("API rate limit exceeded")
        self.assertEqual(
            self.error_handler.categorize_error(api_error, "test_component"),
            ErrorCategory.API_ERROR
        )
        
        # Network errors
        network_error = ConnectionError("Connection timed out")
        self.assertEqual(
            self.error_handler.categorize_error(network_error, "test_component"),
            ErrorCategory.NETWORK_ERROR
        )
        
        # Data errors
        data_error = ValueError("Invalid data format")
        self.assertEqual(
            self.error_handler.categorize_error(data_error, "test_component"),
            ErrorCategory.DATA_ERROR
        )
        
        # Default to runtime error
        other_error = Exception("Some other error")
        self.assertEqual(
            self.error_handler.categorize_error(other_error, "test_component"),
            ErrorCategory.RUNTIME_ERROR
        )
    
    def test_register_recovery_strategy(self):
        """Test registering recovery strategies"""
        strategy = RecoveryStrategy("test_strategy")
        self.error_handler.register_recovery_strategy(ErrorCategory.API_ERROR, strategy)
        
        self.assertIn(strategy, self.error_handler.recovery_strategies[ErrorCategory.API_ERROR])
    
    def test_handle_error_with_recovery(self):
        """Test handling an error with successful recovery"""
        # Create a mock recovery strategy that always succeeds
        mock_strategy = MagicMock()
        mock_strategy.can_recover.return_value = True
        mock_strategy.execute.return_value = True
        
        # Register the mock strategy
        self.error_handler.register_recovery_strategy(ErrorCategory.API_ERROR, mock_strategy)
        
        # Handle an API error
        error = Exception("API rate limit exceeded")
        result = self.error_handler.handle_error(error, "test_component")
        
        # Verify the error was handled successfully
        self.assertTrue(result)
        mock_strategy.can_recover.assert_called_once()
        mock_strategy.execute.assert_called_once()
        
        # Verify error was logged
        self.logger.error.assert_called_once()
    
    def test_handle_error_without_recovery(self):
        """Test handling an error with failed recovery"""
        # Create a mock recovery strategy that always fails
        mock_strategy = MagicMock()
        mock_strategy.can_recover.return_value = True
        mock_strategy.execute.return_value = False
        
        # Register the mock strategy
        self.error_handler.register_recovery_strategy(ErrorCategory.NETWORK_ERROR, mock_strategy)
        
        # Handle a network error
        error = ConnectionError("Connection timed out")
        result = self.error_handler.handle_error(error, "test_component")
        
        # Verify the error was not handled successfully
        self.assertFalse(result)
        mock_strategy.can_recover.assert_called_once()
        mock_strategy.execute.assert_called_once()
    
    def test_error_metrics(self):
        """Test error metrics tracking"""
        # Handle some errors
        self.error_handler.handle_error(Exception("API error"), "component1")
        self.error_handler.handle_error(ConnectionError("Network error"), "component2")
        self.error_handler.handle_error(ValueError("Data error"), "component1")
        
        # Get metrics
        metrics = self.error_handler.get_error_metrics()
        
        # Verify metrics
        self.assertEqual(metrics["counts"][ErrorCategory.API_ERROR.name], 1)
        self.assertEqual(metrics["counts"][ErrorCategory.NETWORK_ERROR.name], 1)
        self.assertEqual(metrics["counts"][ErrorCategory.DATA_ERROR.name], 1)
        self.assertEqual(metrics["recent"], 3)
    
    def test_reset_metrics(self):
        """Test resetting error metrics"""
        # Handle some errors
        self.error_handler.handle_error(Exception("API error"), "component1")
        self.error_handler.handle_error(ConnectionError("Network error"), "component2")
        
        # Reset metrics
        self.error_handler.reset_metrics()
        
        # Get metrics
        metrics = self.error_handler.get_error_metrics()
        
        # Verify metrics were reset
        self.assertEqual(metrics["counts"][ErrorCategory.API_ERROR.name], 0)
        self.assertEqual(metrics["counts"][ErrorCategory.NETWORK_ERROR.name], 0)
        self.assertEqual(metrics["recent"], 0)


class TestRecoveryStrategies(unittest.TestCase):
    """Test cases for recovery strategies"""
    
    def test_retry_recovery_strategy(self):
        """Test retry recovery strategy"""
        strategy = RetryRecoveryStrategy(
            name="test_retry",
            max_attempts=3,
            initial_delay=0.1,
            backoff_factor=2.0
        )
        
        # Create an error context
        error_context = ErrorContext(
            error=Exception("Test error"),
            category=ErrorCategory.API_ERROR,
            component="test_component"
        )
        
        # First attempt should succeed
        self.assertTrue(strategy.can_recover(error_context))
        
        # Execute should return True and increment attempts
        with patch("time.sleep") as mock_sleep:
            self.assertTrue(strategy.execute(error_context))
            mock_sleep.assert_called_once_with(0.1)
            self.assertEqual(strategy.attempts, 1)
        
        # Second attempt should succeed with longer delay
        with patch("time.sleep") as mock_sleep:
            self.assertTrue(strategy.execute(error_context))
            mock_sleep.assert_called_once_with(0.2)
            self.assertEqual(strategy.attempts, 2)
        
        # Third attempt should succeed with even longer delay
        with patch("time.sleep") as mock_sleep:
            self.assertTrue(strategy.execute(error_context))
            mock_sleep.assert_called_once_with(0.4)
            self.assertEqual(strategy.attempts, 3)
        
        # Fourth attempt should fail (max_attempts=3)
        self.assertFalse(strategy.can_recover(error_context))
        
        # Reset should reset attempts
        strategy.reset()
        self.assertEqual(strategy.attempts, 0)
        self.assertTrue(strategy.can_recover(error_context))
    
    def test_fallback_recovery_strategy(self):
        """Test fallback recovery strategy"""
        # Create a mock fallback function
        mock_fallback = MagicMock()
        
        strategy = FallbackRecoveryStrategy(
            name="test_fallback",
            fallback_function=mock_fallback
        )
        
        # Create an error context
        error_context = ErrorContext(
            error=Exception("Test error"),
            category=ErrorCategory.DATA_ERROR,
            component="test_component"
        )
        
        # First attempt should succeed
        self.assertTrue(strategy.can_recover(error_context))
        
        # Execute should return True and call the fallback function
        self.assertTrue(strategy.execute(error_context))
        mock_fallback.assert_called_once_with(error_context)
        self.assertEqual(strategy.attempts, 1)
        
        # Second attempt should fail (max_attempts=1)
        self.assertFalse(strategy.can_recover(error_context))


class TestErrorReport(unittest.TestCase):
    """Test cases for the ErrorReport class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.error_handler = ErrorHandler()
    
    def test_generate_report(self):
        """Test generating an error report"""
        # Handle some errors
        self.error_handler.handle_error(Exception("API error"), "component1")
        self.error_handler.handle_error(ConnectionError("Network error"), "component2")
        self.error_handler.handle_error(ValueError("Data error"), "component1")
        self.error_handler.handle_error(Exception("Another API error"), "component1")
        
        # Generate report
        report = ErrorReport.generate(self.error_handler)
        
        # Verify report
        self.assertEqual(report.total_errors, 4)
        self.assertEqual(report.errors_by_category[ErrorCategory.API_ERROR], 2)
        self.assertEqual(report.errors_by_category[ErrorCategory.NETWORK_ERROR], 1)
        self.assertEqual(report.errors_by_category[ErrorCategory.DATA_ERROR], 1)
        self.assertEqual(report.errors_by_component["component1"], 3)
        self.assertEqual(report.errors_by_component["component2"], 1)
        
        # Verify most frequent errors
        self.assertEqual(len(report.most_frequent_errors), 3)  # Exception, ConnectionError, ValueError
        
        # Find the Exception entry
        exception_entry = next(
            (e for e in report.most_frequent_errors if e["type"] == "Exception"),
            None
        )
        self.assertIsNotNone(exception_entry)
        self.assertEqual(exception_entry["count"], 2)
        self.assertEqual(len(exception_entry["examples"]), 2)


if __name__ == "__main__":
    unittest.main()