"""
Unit tests for the scheduler module.
Tests the TradingScheduler and TradingCycle classes.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock
import time
from datetime import datetime, timedelta
import pandas as pd
import threading
import signal

from bot.scheduler import TradingScheduler, TradingCycle
from bot.strategy import TradingSignal, SignalType
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED


class TestTradingCycle(unittest.TestCase):
    """Test cases for the TradingCycle class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mocks for dependencies
        self.mock_data_fetcher = Mock()
        self.mock_signal_generator = Mock()
        self.mock_trader = Mock()
        self.mock_logger = Mock()
        self.mock_error_handler = Mock()
        
        # Configure error handler mock
        self.mock_error_handler.handle_error.return_value = (True, {
            "retry": True,
            "retry_delay": 1,
            "max_retries": 3,
            "backoff_factor": 2.0,
            "jitter": False,
            "fallback_action": "skip_cycle"
        })
        self.mock_error_handler.classify_error.return_value = ("test_error", "medium")
        self.mock_error_handler.should_circuit_break.return_value = False
        
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
        
        # Create trading cycle instance
        self.trading_cycle = TradingCycle(
            data_fetcher=self.mock_data_fetcher,
            signal_generator=self.mock_signal_generator,
            trader=self.mock_trader,
            logger=self.mock_logger,
            error_handler=self.mock_error_handler,
            symbol="BTC/USD"
        )
    
    def test_execute_successful_cycle(self):
        """Test successful execution of a trading cycle."""
        # Set up mock signal
        mock_signal = Mock()
        mock_signal.action = SignalType.BUY
        mock_signal.confidence = 0.8
        mock_signal.price = 45300
        mock_signal.timestamp = datetime.now()
        mock_signal.strategy = "Test Strategy"
        mock_signal.reasoning = "Test reasoning"
        # Create a property to return the value
        type(mock_signal.action).value = PropertyMock(return_value="BUY")
        
        self.mock_signal_generator.evaluate_all_strategies.return_value = mock_signal
        
        # Set up mock trade result
        mock_trade_result = Mock()
        mock_trade_result.order_id = "test-order-id"
        mock_trade_result.symbol = "BTC/USD"
        mock_trade_result.side = "BUY"
        mock_trade_result.quantity = 0.001
        mock_trade_result.price = 45300
        mock_trade_result.timestamp = datetime.now()
        mock_trade_result.status = "filled"
        mock_trade_result.fees = 0.1
        
        self.mock_trader.execute_trade.return_value = mock_trade_result
        
        # Set up mock position
        mock_position = Mock()
        mock_position.qty = 0.001
        mock_position.market_value = 45.3
        mock_position.unrealized_pl = 0.5
        mock_position.avg_entry_price = 45300
        
        self.mock_trader.position_manager.get_position.return_value = mock_position
        
        # Execute the cycle
        result = self.trading_cycle.execute()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify method calls
        self.mock_data_fetcher.fetch_crypto_data.assert_called_once_with(
            "BTC/USD", timeframe="5Min", limit=50
        )
        self.mock_signal_generator.evaluate_all_strategies.assert_called_once_with(
            self.sample_data
        )
        self.mock_trader.execute_trade.assert_called_once_with(mock_signal)
        self.mock_logger.log_signal.assert_called_once()
        self.mock_logger.log_trade.assert_called_once()
        self.mock_logger.update_position.assert_called_once()
        
        # Verify execution count was incremented
        self.assertEqual(self.trading_cycle.execution_count, 1)
    
    def test_execute_hold_signal(self):
        """Test execution with a HOLD signal."""
        # Set up mock signal with HOLD action
        mock_signal = Mock()
        mock_signal.action = SignalType.HOLD
        mock_signal.confidence = 0.0
        mock_signal.price = 45300
        mock_signal.timestamp = datetime.now()
        mock_signal.strategy = "Test Strategy"
        mock_signal.reasoning = "No clear signal"
        # Create a property to return the value
        type(mock_signal.action).value = PropertyMock(return_value="HOLD")
        
        self.mock_signal_generator.evaluate_all_strategies.return_value = mock_signal
        
        # Execute the cycle
        result = self.trading_cycle.execute()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify method calls
        self.mock_trader.execute_trade.assert_not_called()
        self.mock_logger.log_signal.assert_called_once()
        self.mock_logger.log_trade.assert_not_called()
    
    def test_execute_data_fetch_error(self):
        """Test execution when data fetching fails."""
        # Set up mock to return empty DataFrame
        self.mock_data_fetcher.fetch_crypto_data.return_value = pd.DataFrame()
        
        # Execute the cycle
        result = self.trading_cycle.execute()
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify method calls
        self.mock_signal_generator.evaluate_all_strategies.assert_not_called()
        self.mock_trader.execute_trade.assert_not_called()
    
    def test_execute_with_exception(self):
        """Test execution when an exception occurs."""
        # Set up mock to raise exception
        self.mock_data_fetcher.fetch_crypto_data.side_effect = Exception("Test exception")
        
        # Execute the cycle
        result = self.trading_cycle.execute()
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify method calls
        self.mock_logger.log_error.assert_called_once()
        self.mock_error_handler.handle_error.assert_called_once()
        self.mock_error_handler.should_circuit_break.assert_called_once()
        
        # Verify error count was incremented
        self.assertEqual(self.trading_cycle.error_count, 1)
        
    def test_fetch_market_data_with_error_handling(self):
        """Test fetch_market_data with error handling."""
        # Set up mock to raise exception on first call, then succeed
        self.mock_data_fetcher.fetch_crypto_data.side_effect = [
            Exception("Test exception"),
            self.sample_data
        ]
        
        # Call the method
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.trading_cycle._fetch_market_data()
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(len(result), len(self.sample_data))
        
        # Verify error handler was used
        self.mock_error_handler.handle_error.assert_called_once()
        
    def test_evaluate_strategies_with_error_handling(self):
        """Test _evaluate_strategies with error handling."""
        # Set up mock signal
        mock_signal = Mock()
        
        # Set up mock to raise exception on first call, then succeed
        self.mock_signal_generator.evaluate_all_strategies.side_effect = [
            Exception("Test exception"),
            mock_signal
        ]
        
        # Call the method
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.trading_cycle._evaluate_strategies(self.sample_data)
        
        # Verify result
        self.assertEqual(result, mock_signal)
        
        # Verify error handler was used
        self.mock_error_handler.handle_error.assert_called_once()
        
    def test_execute_trade_with_error_handling(self):
        """Test _execute_trade with error handling."""
        # Set up mock signal
        mock_signal = Mock()
        mock_signal.action = SignalType.BUY
        type(mock_signal.action).value = PropertyMock(return_value="BUY")
        mock_signal.confidence = 0.8
        
        # Set up mock trade result
        mock_trade_result = Mock()
        
        # Set up mock to raise exception on first call, then succeed
        self.mock_trader.execute_trade.side_effect = [
            Exception("Test exception"),
            mock_trade_result
        ]
        
        # Call the method
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.trading_cycle._execute_trade(mock_signal)
        
        # Verify result
        self.assertEqual(result, mock_trade_result)
        
        # Verify error handler was used
        self.mock_error_handler.handle_error.assert_called_once()
        
    def test_execute_with_fallback_data(self):
        """Test execution with fallback to previous data."""
        # Set up previous data
        previous_data = pd.DataFrame({
            'open': [44000, 44100, 44200],
            'high': [44200, 44300, 44400],
            'low': [43800, 43900, 44000],
            'close': [44100, 44200, 44300],
            'volume': [90, 100, 110]
        })
        self.trading_cycle.previous_data = previous_data
        
        # Set up mock to return empty DataFrame (trigger fallback)
        self.mock_data_fetcher.fetch_crypto_data.return_value = pd.DataFrame()
        
        # Set up mock signal
        mock_signal = Mock()
        mock_signal.action = SignalType.HOLD
        type(mock_signal.action).value = PropertyMock(return_value="HOLD")
        mock_signal.confidence = 0.0
        mock_signal.price = 44300
        mock_signal.timestamp = datetime.now()
        mock_signal.strategy = "Test Strategy"
        mock_signal.reasoning = "Test reasoning"
        
        self.mock_signal_generator.evaluate_all_strategies.return_value = mock_signal
        
        # Execute the cycle
        result = self.trading_cycle.execute()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify that strategies were evaluated with previous data
        self.mock_signal_generator.evaluate_all_strategies.assert_called_once_with(previous_data)
        
    def test_execute_with_circuit_breaker(self):
        """Test execution with circuit breaker activation."""
        # Set up mock to raise exception
        self.mock_data_fetcher.fetch_crypto_data.side_effect = Exception("Test exception")
        
        # Configure error handler to trigger circuit breaker
        self.mock_error_handler.should_circuit_break.return_value = True
        
        # Execute the cycle
        result = self.trading_cycle.execute()
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify circuit breaker was checked
        self.mock_error_handler.should_circuit_break.assert_called_once()
    
    def test_update_position_info(self):
        """Test updating position information."""
        # Set up mock position
        mock_position = Mock()
        mock_position.qty = 0.001
        mock_position.market_value = 45.3
        mock_position.unrealized_pl = 0.5
        mock_position.avg_entry_price = 45300
        
        self.mock_trader.position_manager.get_position.return_value = mock_position
        
        # Call the method
        self.trading_cycle._update_position_info()
        
        # Verify method calls
        self.mock_trader.position_manager.get_position.assert_called_once_with("BTC/USD")
        self.mock_logger.update_position.assert_called_once()
    
    def test_update_position_info_no_position(self):
        """Test updating position information when no position exists."""
        # Set up mock to return None
        self.mock_trader.position_manager.get_position.return_value = None
        
        # Call the method
        self.trading_cycle._update_position_info()
        
        # Verify method calls
        self.mock_trader.position_manager.get_position.assert_called_once_with("BTC/USD")
        self.mock_logger.update_position.assert_called_once()
    
    def test_update_position_info_with_exception(self):
        """Test updating position information when an exception occurs."""
        # Set up mock to raise exception
        self.mock_trader.position_manager.get_position.side_effect = Exception("Test exception")
        
        # Call the method
        self.trading_cycle._update_position_info()
        
        # No assertions needed as the method should catch the exception


class TestTradingScheduler(unittest.TestCase):
    """Test cases for the TradingScheduler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock for trading cycle
        self.mock_trading_cycle = Mock()
        self.mock_error_handler = Mock()
        
        # Configure error handler mock
        self.mock_error_handler.handle_error.return_value = (True, {
            "retry": True,
            "retry_delay": 1,
            "max_retries": 3,
            "backoff_factor": 2.0,
            "jitter": False,
            "fallback_action": "skip_cycle"
        })
        self.mock_error_handler.classify_error.return_value = ("test_error", "medium")
        self.mock_error_handler.should_circuit_break.return_value = False
        self.mock_error_handler.calculate_backoff_delay.return_value = 30.0
        
        # Create scheduler instance
        self.scheduler = TradingScheduler(
            trading_cycle=self.mock_trading_cycle,
            interval_minutes=5,
            error_handler=self.mock_error_handler
        )
    
    @patch('bot.scheduler.BackgroundScheduler')
    def test_start_scheduler(self, mock_scheduler_class):
        """Test starting the scheduler."""
        # Set up mock scheduler
        mock_scheduler_instance = Mock()
        mock_scheduler_class.return_value = mock_scheduler_instance
        
        # Create new scheduler with the mock
        scheduler = TradingScheduler(
            trading_cycle=self.mock_trading_cycle,
            interval_minutes=5
        )
        
        # Start the scheduler
        result = scheduler.start_scheduler()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify method calls
        mock_scheduler_instance.add_job.assert_called_once()
        mock_scheduler_instance.start.assert_called_once()
        self.mock_trading_cycle.execute.assert_called_once()
        
        # Verify scheduler is running
        self.assertTrue(scheduler.is_running)
    
    @patch('bot.scheduler.BackgroundScheduler')
    def test_start_scheduler_already_running(self, mock_scheduler_class):
        """Test starting the scheduler when it's already running."""
        # Set up mock scheduler
        mock_scheduler_instance = Mock()
        mock_scheduler_class.return_value = mock_scheduler_instance
        
        # Create new scheduler with the mock
        scheduler = TradingScheduler(
            trading_cycle=self.mock_trading_cycle,
            interval_minutes=5
        )
        
        # Set scheduler as running
        scheduler.is_running = True
        
        # Start the scheduler
        result = scheduler.start_scheduler()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify method calls (should not be called)
        mock_scheduler_instance.add_job.assert_not_called()
        mock_scheduler_instance.start.assert_not_called()
        self.mock_trading_cycle.execute.assert_not_called()
    
    @patch('bot.scheduler.BackgroundScheduler')
    def test_start_scheduler_with_exception(self, mock_scheduler_class):
        """Test starting the scheduler when an exception occurs."""
        # Set up mock scheduler to raise exception
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.add_job.side_effect = Exception("Test exception")
        mock_scheduler_class.return_value = mock_scheduler_instance
        
        # Create new scheduler with the mock
        scheduler = TradingScheduler(
            trading_cycle=self.mock_trading_cycle,
            interval_minutes=5
        )
        
        # Start the scheduler
        result = scheduler.start_scheduler()
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify scheduler is not running
        self.assertFalse(scheduler.is_running)
    
    def test_stop_scheduler(self):
        """Test stopping the scheduler."""
        # Set up scheduler as running
        self.scheduler.is_running = True
        self.scheduler.scheduler = Mock()
        
        # Stop the scheduler
        result = self.scheduler.stop_scheduler()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify method calls
        self.scheduler.scheduler.shutdown.assert_called_once_with(wait=False)
        self.assertFalse(self.scheduler.is_running)
        self.assertTrue(self.scheduler.shutdown_event.is_set())
    
    def test_stop_scheduler_not_running(self):
        """Test stopping the scheduler when it's not running."""
        # Set up scheduler as not running
        self.scheduler.is_running = False
        self.scheduler.scheduler = Mock()
        
        # Stop the scheduler
        result = self.scheduler.stop_scheduler()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify method calls (should not be called)
        self.scheduler.scheduler.shutdown.assert_not_called()
    
    def test_stop_scheduler_with_exception(self):
        """Test stopping the scheduler when an exception occurs."""
        # Set up scheduler as running
        self.scheduler.is_running = True
        self.scheduler.scheduler = Mock()
        self.scheduler.scheduler.shutdown.side_effect = Exception("Test exception")
        
        # Stop the scheduler
        result = self.scheduler.stop_scheduler()
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify scheduler is still running
        self.assertTrue(self.scheduler.is_running)
    
    def test_execute_trading_cycle(self):
        """Test executing a trading cycle."""
        # Set up mock to return True
        self.mock_trading_cycle.execute.return_value = True
        
        # Execute the trading cycle
        self.scheduler.execute_trading_cycle()
        
        # Verify method calls
        self.mock_trading_cycle.execute.assert_called_once()
    
    def test_execute_trading_cycle_with_failure(self):
        """Test executing a trading cycle that fails."""
        # Set up mock to return False
        self.mock_trading_cycle.execute.return_value = False
        
        # Set up scheduler
        self.scheduler.scheduler = Mock()
        
        # Execute the trading cycle
        self.scheduler.execute_trading_cycle()
        
        # Verify method calls
        self.mock_trading_cycle.execute.assert_called_once()
        
        # Verify error handling
        self.assertEqual(self.scheduler.error_recovery_attempts, 1)
        self.scheduler.scheduler.add_job.assert_called_once()
    
    def test_execute_trading_cycle_with_shutdown(self):
        """Test executing a trading cycle during shutdown."""
        # Set shutdown event
        self.scheduler.shutdown_event.set()
        
        # Execute the trading cycle
        self.scheduler.execute_trading_cycle()
        
        # Verify method calls
        self.mock_trading_cycle.execute.assert_not_called()
    
    def test_handle_cycle_error(self):
        """Test handling a cycle error."""
        # Set up scheduler
        self.scheduler.scheduler = Mock()
        
        # Handle an error
        self.scheduler.handle_cycle_error(Exception("Test error"))
        
        # Verify error recovery attempt was incremented
        self.assertEqual(self.scheduler.error_recovery_attempts, 1)
        
        # Verify error handler was used
        self.mock_error_handler.classify_error.assert_called_once()
        self.mock_error_handler.handle_error.assert_called_once()
        self.mock_error_handler.should_circuit_break.assert_called_once()
        
        # Verify recovery job was scheduled
        self.scheduler.scheduler.add_job.assert_called_once()
        
    def test_handle_cycle_error_with_circuit_breaker(self):
        """Test handling a cycle error with circuit breaker activation."""
        # Set up scheduler
        self.scheduler.scheduler = Mock()
        
        # Configure error handler to trigger circuit breaker
        self.mock_error_handler.should_circuit_break.return_value = True
        
        # Handle an error
        self.scheduler.handle_cycle_error(Exception("Test error"))
        
        # Verify circuit breaker was activated
        self.assertTrue(self.scheduler.circuit_breaker_active)
        self.assertIsNotNone(self.scheduler.circuit_breaker_until)
        
        # Verify recovery job was not scheduled (circuit breaker prevents it)
        self.scheduler.scheduler.add_job.assert_not_called()
        
    def test_handle_cycle_error_with_active_circuit_breaker(self):
        """Test handling a cycle error when circuit breaker is already active."""
        # Set up scheduler with active circuit breaker
        self.scheduler.circuit_breaker_active = True
        self.scheduler.circuit_breaker_until = datetime.now() + timedelta(minutes=5)
        self.scheduler.scheduler = Mock()
        
        # Handle an error
        self.scheduler.handle_cycle_error(Exception("Test error"))
        
        # Verify error handler was not used (circuit breaker prevents it)
        self.mock_error_handler.classify_error.assert_not_called()
        self.mock_error_handler.handle_error.assert_not_called()
        
        # Verify recovery job was not scheduled
        self.scheduler.scheduler.add_job.assert_not_called()
        
    def test_handle_cycle_error_with_expired_circuit_breaker(self):
        """Test handling a cycle error when circuit breaker has expired."""
        # Set up scheduler with expired circuit breaker
        self.scheduler.circuit_breaker_active = True
        self.scheduler.circuit_breaker_until = datetime.now() - timedelta(minutes=1)
        self.scheduler.scheduler = Mock()
        
        # Handle an error
        self.scheduler.handle_cycle_error(Exception("Test error"))
        
        # Verify circuit breaker was deactivated
        self.assertFalse(self.scheduler.circuit_breaker_active)
        
        # Verify error handler was used
        self.mock_error_handler.classify_error.assert_called_once()
        self.mock_error_handler.handle_error.assert_called_once()
        
        # Verify recovery job was scheduled
        self.scheduler.scheduler.add_job.assert_called_once()
    
    def test_handle_cycle_error_multiple_attempts(self):
        """Test handling multiple cycle errors."""
        # Set up scheduler
        self.scheduler.scheduler = Mock()
        self.scheduler.error_recovery_attempts = 1
        
        # Handle an error
        self.scheduler.handle_cycle_error(Exception("Test error"))
        
        # Verify error recovery attempt was incremented
        self.assertEqual(self.scheduler.error_recovery_attempts, 2)
        
        # Verify recovery job was scheduled with longer delay
        self.scheduler.scheduler.add_job.assert_called_once()
        
        # Check that the delay is doubled (exponential backoff)
        args, kwargs = self.scheduler.scheduler.add_job.call_args
        self.assertIn('run_date', kwargs)
        # The run_date should be about 60 seconds in the future (30 * 2^1)
        time_diff = (kwargs['run_date'] - datetime.now()).total_seconds()
        self.assertGreater(time_diff, 55)  # Allow for small timing differences
        self.assertLess(time_diff, 65)
    
    def test_handle_cycle_error_max_attempts(self):
        """Test handling a cycle error with maximum attempts reached."""
        # Set up scheduler with max attempts reached
        self.scheduler.error_recovery_attempts = self.scheduler.max_recovery_attempts
        
        # Handle an error
        self.scheduler.handle_cycle_error(Exception("Test error"))
        
        # Verify error recovery attempt was reset
        self.assertEqual(self.scheduler.error_recovery_attempts, 0)
    
    def test_job_executed_listener(self):
        """Test the job executed listener."""
        # Create mock event
        mock_event = Mock()
        mock_event.job_id = 'trading_cycle'
        
        # Set up scheduler with error recovery attempts
        self.scheduler.error_recovery_attempts = 2
        
        # Call the listener
        self.scheduler._job_executed_listener(mock_event)
        
        # Verify error recovery attempts was reset
        self.assertEqual(self.scheduler.error_recovery_attempts, 0)
    
    def test_job_executed_listener_different_job(self):
        """Test the job executed listener with a different job ID."""
        # Create mock event
        mock_event = Mock()
        mock_event.job_id = 'other_job'
        
        # Set up scheduler with error recovery attempts
        self.scheduler.error_recovery_attempts = 2
        
        # Call the listener
        self.scheduler._job_executed_listener(mock_event)
        
        # Verify error recovery attempts was not reset
        self.assertEqual(self.scheduler.error_recovery_attempts, 2)
    
    def test_job_error_listener(self):
        """Test the job error listener."""
        # Create mock event
        mock_event = Mock()
        mock_event.job_id = 'trading_cycle'
        mock_event.exception = Exception("Test exception")
        
        # Set up scheduler
        self.scheduler.scheduler = Mock()
        
        # Call the listener
        self.scheduler._job_error_listener(mock_event)
        
        # Verify error recovery attempt was incremented
        self.assertEqual(self.scheduler.error_recovery_attempts, 1)
        
        # Verify recovery job was scheduled
        self.scheduler.scheduler.add_job.assert_called_once()
    
    def test_job_error_listener_different_job(self):
        """Test the job error listener with a different job ID."""
        # Create mock event
        mock_event = Mock()
        mock_event.job_id = 'other_job'
        mock_event.exception = Exception("Test exception")
        
        # Set up scheduler
        self.scheduler.scheduler = Mock()
        
        # Call the listener
        self.scheduler._job_error_listener(mock_event)
        
        # Verify error recovery attempt was not incremented
        self.assertEqual(self.scheduler.error_recovery_attempts, 0)
        
        # Verify recovery job was not scheduled
        self.scheduler.scheduler.add_job.assert_not_called()
    
    @patch('signal.signal')
    def test_signal_handler_setup(self, mock_signal):
        """Test that signal handlers are set up correctly."""
        # Create new scheduler to trigger __init__
        scheduler = TradingScheduler(
            trading_cycle=self.mock_trading_cycle,
            interval_minutes=5
        )
        
        # Verify signal handlers were set up
        mock_signal.assert_has_calls([
            call(signal.SIGINT, scheduler._signal_handler),
            call(signal.SIGTERM, scheduler._signal_handler)
        ])
    
    def test_signal_handler(self):
        """Test the signal handler."""
        # Set up scheduler
        self.scheduler.is_running = True
        self.scheduler.scheduler = Mock()
        
        # Call the signal handler
        self.scheduler._signal_handler(signal.SIGINT, None)
        
        # Verify scheduler was stopped
        self.scheduler.scheduler.shutdown.assert_called_once_with(wait=False)
        self.assertFalse(self.scheduler.is_running)
        self.assertTrue(self.scheduler.shutdown_event.is_set())


if __name__ == '__main__':
    unittest.main()