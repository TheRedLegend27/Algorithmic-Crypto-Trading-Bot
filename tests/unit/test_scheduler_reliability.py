"""
Tests for scheduler reliability under different system load conditions.
"""
import unittest
from unittest.mock import patch, MagicMock, Mock, call
import time
import threading
import queue
from datetime import datetime, timedelta

from bot.scheduler import TradingScheduler, TradingCycle
from bot.error_handler import ErrorHandler


class TestSchedulerReliability(unittest.TestCase):
    """Test cases for scheduler reliability."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock trading cycle
        self.mock_trading_cycle = Mock()
        self.mock_trading_cycle.execute.return_value = True
        
        # Create error handler
        self.error_handler = ErrorHandler()
        
        # Create scheduler
        self.scheduler = TradingScheduler(
            trading_cycle=self.mock_trading_cycle,
            interval_minutes=1,  # Short interval for testing
            error_handler=self.error_handler
        )
    
    def test_scheduler_timing_accuracy(self):
        """Test scheduler timing accuracy."""
        # Mock the scheduler's add_job method
        self.scheduler.scheduler = Mock()
        
        # Start the scheduler
        self.scheduler.start_scheduler()
        
        # Verify that add_job was called with the correct interval
        self.scheduler.scheduler.add_job.assert_called_once()
        args, kwargs = self.scheduler.scheduler.add_job.call_args
        trigger = kwargs.get('trigger')
        
        # Verify trigger is an IntervalTrigger with correct minutes
        self.assertEqual(trigger.interval.minutes, 1)
    
    def test_scheduler_under_cpu_load(self):
        """Test scheduler reliability under CPU load."""
        # Create a queue for communication between threads
        result_queue = queue.Queue()
        
        # Create a function to simulate CPU load
        def cpu_load():
            # Perform CPU-intensive operations
            for _ in range(1000000):
                _ = 1 + 1
        
        # Create a function to run the scheduler
        def run_scheduler():
            try:
                # Start time
                start_time = time.time()
                
                # Execute trading cycle
                self.scheduler.execute_trading_cycle()
                
                # End time
                end_time = time.time()
                
                # Put execution time in queue
                result_queue.put(end_time - start_time)
            except Exception as e:
                result_queue.put(e)
        
        # Create and start CPU load thread
        cpu_thread = threading.Thread(target=cpu_load)
        cpu_thread.start()
        
        # Create and start scheduler thread
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.start()
        
        # Wait for threads to complete
        cpu_thread.join()
        scheduler_thread.join()
        
        # Get result from queue
        result = result_queue.get()
        
        # Verify result is not an exception
        self.assertNotIsInstance(result, Exception)
        
        # Verify trading cycle was executed
        self.mock_trading_cycle.execute.assert_called_once()
    
    def test_scheduler_recovery_after_system_overload(self):
        """Test scheduler recovery after system overload."""
        # Configure mock to raise exception then succeed
        self.mock_trading_cycle.execute.side_effect = [
            Exception("System overload"),
            True
        ]
        
        # Mock the scheduler's add_job method
        self.scheduler.scheduler = Mock()
        
        # Execute trading cycle (will fail)
        self.scheduler.execute_trading_cycle()
        
        # Verify error recovery was attempted
        self.assertEqual(self.scheduler.error_recovery_attempts, 1)
        self.scheduler.scheduler.add_job.assert_called_once()
        
        # Reset mock
        self.scheduler.scheduler.reset_mock()
        
        # Execute trading cycle again (will succeed)
        self.scheduler.execute_trading_cycle()
        
        # Verify error recovery attempts was reset
        self.assertEqual(self.scheduler.error_recovery_attempts, 0)
    
    def test_scheduler_handles_multiple_errors(self):
        """Test scheduler handling of multiple consecutive errors."""
        # Configure mock to raise exceptions
        self.mock_trading_cycle.execute.side_effect = Exception("Test error")
        
        # Mock the scheduler's add_job method
        self.scheduler.scheduler = Mock()
        
        # Execute trading cycle multiple times
        for _ in range(3):
            self.scheduler.execute_trading_cycle()
        
        # Verify error recovery attempts increased
        self.assertEqual(self.scheduler.error_recovery_attempts, 3)
        
        # Verify add_job was called with increasing delays
        self.assertEqual(self.scheduler.scheduler.add_job.call_count, 3)
        
        # Get the run_date arguments from each call
        call_args_list = self.scheduler.scheduler.add_job.call_args_list
        run_dates = [kwargs['run_date'] for args, kwargs in call_args_list]
        
        # Verify delays are increasing (exponential backoff)
        delay1 = (run_dates[1] - run_dates[0]).total_seconds()
        delay2 = (run_dates[2] - run_dates[1]).total_seconds()
        self.assertGreater(delay2, delay1)
    
    def test_scheduler_circuit_breaker_activation(self):
        """Test circuit breaker activation after multiple errors."""
        # Configure error handler to trigger circuit breaker
        with patch.object(self.error_handler, 'should_circuit_break', return_value=True):
            # Configure mock to raise exception
            self.mock_trading_cycle.execute.side_effect = Exception("Test error")
            
            # Mock the scheduler's add_job method
            self.scheduler.scheduler = Mock()
            
            # Execute trading cycle
            self.scheduler.execute_trading_cycle()
            
            # Verify circuit breaker was activated
            self.assertTrue(self.scheduler.circuit_breaker_active)
            self.assertIsNotNone(self.scheduler.circuit_breaker_until)
            
            # Verify add_job was not called (circuit breaker prevents it)
            self.scheduler.scheduler.add_job.assert_not_called()
    
    def test_scheduler_circuit_breaker_expiration(self):
        """Test circuit breaker expiration and resumption of normal operation."""
        # Set up scheduler with expired circuit breaker
        self.scheduler.circuit_breaker_active = True
        self.scheduler.circuit_breaker_until = datetime.now() - timedelta(minutes=1)
        
        # Mock the scheduler's add_job method
        self.scheduler.scheduler = Mock()
        
        # Configure mock to raise exception
        self.mock_trading_cycle.execute.side_effect = Exception("Test error")
        
        # Execute trading cycle
        self.scheduler.execute_trading_cycle()
        
        # Verify circuit breaker was deactivated
        self.assertFalse(self.scheduler.circuit_breaker_active)
        
        # Verify add_job was called (normal operation resumed)
        self.scheduler.scheduler.add_job.assert_called_once()
    
    def test_scheduler_concurrent_execution(self):
        """Test scheduler handling of concurrent execution attempts."""
        # Create a threading event to synchronize threads
        event = threading.Event()
        
        # Create a mock trading cycle that waits for the event
        def waiting_execute():
            event.wait(timeout=1.0)  # Wait for event or timeout
            return True
        
        self.mock_trading_cycle.execute.side_effect = waiting_execute
        
        # Create a function to run the scheduler
        def run_scheduler():
            self.scheduler.execute_trading_cycle()
        
        # Create and start first thread
        thread1 = threading.Thread(target=run_scheduler)
        thread1.start()
        
        # Small delay to ensure first thread starts
        time.sleep(0.1)
        
        # Create and start second thread
        thread2 = threading.Thread(target=run_scheduler)
        thread2.start()
        
        # Signal threads to continue
        event.set()
        
        # Wait for threads to complete
        thread1.join()
        thread2.join()
        
        # Verify trading cycle was executed twice
        self.assertEqual(self.mock_trading_cycle.execute.call_count, 2)
    
    def test_scheduler_shutdown_during_execution(self):
        """Test scheduler shutdown during execution."""
        # Create a threading event to synchronize threads
        event = threading.Event()
        
        # Create a mock trading cycle that waits for the event
        def waiting_execute():
            event.wait(timeout=1.0)  # Wait for event or timeout
            return True
        
        self.mock_trading_cycle.execute.side_effect = waiting_execute
        
        # Create a function to run the scheduler
        def run_scheduler():
            self.scheduler.execute_trading_cycle()
        
        # Create and start scheduler thread
        thread = threading.Thread(target=run_scheduler)
        thread.start()
        
        # Small delay to ensure thread starts
        time.sleep(0.1)
        
        # Set shutdown event
        self.scheduler.shutdown_event.set()
        
        # Signal thread to continue
        event.set()
        
        # Wait for thread to complete
        thread.join()
        
        # Verify trading cycle was not executed (shutdown prevented it)
        self.mock_trading_cycle.execute.assert_not_called()
    
    def test_scheduler_job_error_listener(self):
        """Test job error listener handling."""
        # Mock the scheduler's add_job method
        self.scheduler.scheduler = Mock()
        
        # Create mock event
        mock_event = Mock()
        mock_event.job_id = 'trading_cycle'
        mock_event.exception = Exception("Test exception")
        
        # Call the job error listener
        self.scheduler._job_error_listener(mock_event)
        
        # Verify error recovery attempt was incremented
        self.assertEqual(self.scheduler.error_recovery_attempts, 1)
        
        # Verify recovery job was scheduled
        self.scheduler.scheduler.add_job.assert_called_once()
    
    def test_scheduler_job_executed_listener(self):
        """Test job executed listener handling."""
        # Set up scheduler with error recovery attempts
        self.scheduler.error_recovery_attempts = 2
        
        # Create mock event
        mock_event = Mock()
        mock_event.job_id = 'trading_cycle'
        
        # Call the job executed listener
        self.scheduler._job_executed_listener(mock_event)
        
        # Verify error recovery attempts was reset
        self.assertEqual(self.scheduler.error_recovery_attempts, 0)
    
    def test_scheduler_signal_handler(self):
        """Test signal handler for graceful shutdown."""
        # Mock the scheduler's scheduler attribute
        self.scheduler.scheduler = Mock()
        self.scheduler.is_running = True
        
        # Call the signal handler
        self.scheduler._signal_handler(15, None)  # 15 is SIGTERM
        
        # Verify scheduler was stopped
        self.scheduler.scheduler.shutdown.assert_called_once_with(wait=False)
        self.assertFalse(self.scheduler.is_running)
        self.assertTrue(self.scheduler.shutdown_event.is_set())


if __name__ == '__main__':
    unittest.main()