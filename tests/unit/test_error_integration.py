"""
Integration tests for error handling and recovery mechanisms.
Tests the interaction between ErrorHandler, TradingCycle, and TradingScheduler.
"""
import unittest
from unittest.mock import patch, MagicMock, Mock, PropertyMock
import pandas as pd
import requests
from datetime import datetime, timedelta

from bot.error_handler import ErrorHandler, ErrorType, ErrorSeverity
from bot.scheduler import TradingCycle, TradingScheduler
from bot.strategy import TradingSignal, SignalType


class TestErrorIntegration(unittest.TestCase):
    """Integration tests for error handling and recovery."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create real error handler
        self.error_handler = ErrorHandler()
        
        # Create mocks for dependencies
        self.mock_data_fetcher = Mock()
        self.mock_signal_generator = Mock()
        self.mock_trader = Mock()
        self.mock_logger = Mock()
        
        # Create sample data
        self.sample_data = pd.DataFrame({
            'open': [45000, 45100, 45200],
            'high': [45200, 45300, 45400],
            'low': [44800, 44900, 45000],
            'close': [45100, 45200, 45300],
            'volume': [100, 110, 120]
        })
        
        # Set up mock returns
        self.mock_data_fetcher.fetch_crypto_data.return_value = self.sample_data
        
        # Create trading cycle instance with real error handler
        self.trading_cycle = TradingCycle(
            data_fetcher=self.mock_data_fetcher,
            signal_generator=self.mock_signal_generator,
            trader=self.mock_trader,
            logger=self.mock_logger,
            error_handler=self.error_handler,
            symbol="BTC/USD"
        )
        
        # Create scheduler instance with real error handler
        self.scheduler = TradingScheduler(
            trading_cycle=self.trading_cycle,
            interval_minutes=5,
            error_handler=self.error_handler
        )
        self.scheduler.scheduler = Mock()  # Mock the APScheduler
    
    def test_rate_limit_error_recovery(self):
        """Test recovery from API rate limit errors."""
        # Create a rate limit error
        rate_limit_error = Exception("Rate limit exceeded")
        
        # Set up mock to raise rate limit error then succeed
        self.mock_data_fetcher.fetch_crypto_data.side_effect = [
            rate_limit_error,
            self.sample_data
        ]
        
        # Set up mock signal
        mock_signal = Mock()
        mock_signal.action = SignalType.HOLD
        type(mock_signal.action).value = PropertyMock(return_value="HOLD")
        mock_signal.confidence = 0.0
        mock_signal.price = 45300
        mock_signal.timestamp = datetime.now()
        mock_signal.strategy = "Test Strategy"
        mock_signal.reasoning = "Test reasoning"
        
        self.mock_signal_generator.evaluate_all_strategies.return_value = mock_signal
        
        # Execute with patched sleep to avoid actual delays
        with patch('time.sleep'):
            result = self.trading_cycle.execute()
        
        # Verify the cycle succeeded despite the initial error
        self.assertTrue(result)
        
        # Verify data fetcher was called twice (retry after error)
        self.assertEqual(self.mock_data_fetcher.fetch_crypto_data.call_count, 2)
        
        # Verify signal generator was called with the data
        self.mock_signal_generator.evaluate_all_strategies.assert_called_once_with(
            self.sample_data
        )
    
    def test_network_error_recovery(self):
        """Test recovery from network errors."""
        # Create a network error
        network_error = requests.exceptions.ConnectionError("Connection failed")
        
        # Set up mock to raise network error then succeed
        self.mock_data_fetcher.fetch_crypto_data.side_effect = [
            network_error,
            self.sample_data
        ]
        
        # Set up mock signal
        mock_signal = Mock()
        mock_signal.action = SignalType.HOLD
        type(mock_signal.action).value = PropertyMock(return_value="HOLD")
        mock_signal.confidence = 0.0
        
        self.mock_signal_generator.evaluate_all_strategies.return_value = mock_signal
        
        # Execute with patched sleep to avoid actual delays
        with patch('time.sleep'):
            result = self.trading_cycle.execute()
        
        # Verify the cycle succeeded despite the initial error
        self.assertTrue(result)
        
        # Verify data fetcher was called twice (retry after error)
        self.assertEqual(self.mock_data_fetcher.fetch_crypto_data.call_count, 2)
    
    def test_data_validation_error_with_fallback(self):
        """Test handling data validation errors with fallback to previous data."""
        # Set up previous data
        previous_data = pd.DataFrame({
            'open': [44000, 44100, 44200],
            'high': [44200, 44300, 44400],
            'low': [43800, 43900, 44000],
            'close': [44100, 44200, 44300],
            'volume': [90, 100, 110]
        })
        self.trading_cycle.previous_data = previous_data
        
        # Create a data validation error
        validation_error = ValueError("Data validation failed")
        
        # Set up mock to raise validation error then return empty DataFrame
        self.mock_data_fetcher.fetch_crypto_data.side_effect = [
            validation_error,
            pd.DataFrame()  # Empty DataFrame should trigger fallback
        ]
        
        # Set up mock signal
        mock_signal = Mock()
        mock_signal.action = SignalType.HOLD
        type(mock_signal.action).value = PropertyMock(return_value="HOLD")
        mock_signal.confidence = 0.0
        
        self.mock_signal_generator.evaluate_all_strategies.return_value = mock_signal
        
        # Execute with patched sleep to avoid actual delays
        with patch('time.sleep'):
            result = self.trading_cycle.execute()
        
        # Verify the cycle succeeded despite the errors
        self.assertTrue(result)
        
        # Verify data fetcher was called twice (retry after error)
        self.assertEqual(self.mock_data_fetcher.fetch_crypto_data.call_count, 2)
        
        # Verify signal generator was called with the previous data
        self.mock_signal_generator.evaluate_all_strategies.assert_called_once_with(
            previous_data
        )
    
    def test_circuit_breaker_activation(self):
        """Test circuit breaker activation after multiple errors."""
        # Create an error
        test_error = Exception("Test error")
        
        # Configure error handler to track errors
        error_type = ErrorType.API_RATE_LIMIT
        now = datetime.now()
        
        # Add multiple error timestamps to trigger circuit breaker
        self.error_handler.error_timestamps[error_type] = [
            now - timedelta(seconds=10),
            now - timedelta(seconds=20),
            now - timedelta(seconds=30),
            now - timedelta(seconds=40),
            now - timedelta(seconds=50),
            now - timedelta(seconds=60),
            now - timedelta(seconds=70),
            now - timedelta(seconds=80),
            now - timedelta(seconds=90),
            now - timedelta(seconds=100),
            now
        ]
        
        # Handle a cycle error
        self.scheduler.handle_cycle_error(test_error)
        
        # Verify circuit breaker was activated
        self.assertTrue(self.scheduler.circuit_breaker_active)
        self.assertIsNotNone(self.scheduler.circuit_breaker_until)
        
        # Verify recovery job was not scheduled due to circuit breaker
        self.scheduler.scheduler.add_job.assert_not_called()
        
        # Try to handle another error while circuit breaker is active
        self.scheduler.handle_cycle_error(test_error)
        
        # Verify error handler was not used for the second error
        self.assertEqual(self.scheduler.scheduler.add_job.call_count, 0)
    
    def test_circuit_breaker_expiration(self):
        """Test circuit breaker expiration and resumption of normal operation."""
        # Create an error
        test_error = Exception("Test error")
        
        # Set up scheduler with expired circuit breaker
        self.scheduler.circuit_breaker_active = True
        self.scheduler.circuit_breaker_until = datetime.now() - timedelta(minutes=1)
        
        # Handle a cycle error
        self.scheduler.handle_cycle_error(test_error)
        
        # Verify circuit breaker was deactivated
        self.assertFalse(self.scheduler.circuit_breaker_active)
        
        # Verify recovery job was scheduled (normal operation resumed)
        self.scheduler.scheduler.add_job.assert_called_once()
    
    def test_error_pattern_detection(self):
        """Test error pattern detection."""
        # Add error timestamps
        error_type = ErrorType.API_RATE_LIMIT
        now = datetime.now()
        
        # Add timestamps with increasing frequency
        self.error_handler.error_timestamps[error_type] = [
            now - timedelta(minutes=50),
            now - timedelta(minutes=45),
            now - timedelta(minutes=40),
            now - timedelta(minutes=30),
            now - timedelta(minutes=25),
            now - timedelta(minutes=20),
            now - timedelta(minutes=10),
            now - timedelta(minutes=5),
            now - timedelta(minutes=2),
            now
        ]
        
        # Detect patterns
        pattern = self.error_handler.detect_error_patterns(error_type, 3600)
        
        # Verify pattern detection
        self.assertEqual(pattern["count"], 10)
        self.assertGreater(pattern["frequency"], 0)
        
        # Check if circuit breaker should activate
        should_break = self.error_handler.should_circuit_break(
            error_type, threshold=5, time_window=3600
        )
        
        # Verify circuit breaker decision
        self.assertTrue(should_break)
    
    def test_error_recovery_with_backoff(self):
        """Test error recovery with exponential backoff."""
        # Create an error
        test_error = Exception("Test error")
        
        # Set up scheduler
        self.scheduler.error_recovery_attempts = 0
        
        # Handle multiple errors to test backoff
        for attempt in range(3):
            self.scheduler.handle_cycle_error(test_error)
            
            # Verify error recovery attempt was incremented
            self.assertEqual(self.scheduler.error_recovery_attempts, attempt + 1)
            
            # Verify recovery job was scheduled
            self.assertEqual(self.scheduler.scheduler.add_job.call_count, attempt + 1)
            
            # Get the delay for this attempt
            args, kwargs = self.scheduler.scheduler.add_job.call_args
            run_date = kwargs['run_date']
            delay = (run_date - datetime.now()).total_seconds()
            
            # Verify delay increases with each attempt (exponential backoff)
            if attempt > 0:
                self.assertGreater(delay, previous_delay)
            
            previous_delay = delay
    
    def test_unrecoverable_error_handling(self):
        """Test handling of unrecoverable errors."""
        # Create an authentication error (unrecoverable)
        auth_error = Exception("Authentication failed")
        
        # Classify the error
        error_type, severity = self.error_handler.classify_error(auth_error)
        
        # Verify classification
        self.assertEqual(error_type, ErrorType.API_AUTH)
        self.assertEqual(severity, ErrorSeverity.HIGH)
        
        # Get recovery strategy
        recoverable, recovery_info = self.error_handler.handle_error(
            auth_error, "test_context"
        )
        
        # Verify recovery strategy
        self.assertTrue(recoverable)  # Still technically recoverable
        self.assertFalse(recovery_info["retry"])  # But no retry
        self.assertEqual(recovery_info["fallback_action"], "exit")  # Should exit


if __name__ == '__main__':
    unittest.main()