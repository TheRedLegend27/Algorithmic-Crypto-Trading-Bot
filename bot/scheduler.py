"""
Scheduler module for managing periodic execution of trading cycles.
Uses APScheduler to run trading operations at specified intervals.
"""
import time
import signal
import threading
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from bot.data_fetcher import DataFetcher
from bot.strategy import SignalGenerator, TradingSignal
from bot.logger import SignalRecord
from bot.trader import Trader
from bot.logger import TradeRecord
from bot.logger import TradingLogger, PositionRecord
from bot.utils import log_error, log_info, log_warning, safe_execute
from bot.error_handler import ErrorHandler, ErrorType, with_error_handling


class TradingCycle:
    """
    Represents a single execution cycle of the trading logic.
    Handles data fetching, strategy evaluation, and trade execution.
    """
    
    def __init__(self, data_fetcher: DataFetcher, signal_generator: SignalGenerator,
                trader: Trader, logger: TradingLogger, error_handler: ErrorHandler = None,
                symbol: str = "BTC/USD"):
        """
        Initialize the trading cycle.
        
        Args:
            data_fetcher: DataFetcher instance for retrieving market data
            signal_generator: SignalGenerator instance for evaluating trading strategies
            trader: Trader instance for executing trades
            logger: TradingLogger instance for logging
            error_handler: ErrorHandler instance for error handling and recovery
            symbol: Trading symbol to use
        """
        self.data_fetcher = data_fetcher
        self.signal_generator = signal_generator
        self.trader = trader
        self.logger = logger
        self.symbol = symbol
        self.last_execution_time = None
        self.execution_count = 0
        self.error_count = 0
        self.error_handler = error_handler or ErrorHandler()
        self.previous_data = None  # Store previous data for fallback
    
    @with_error_handling(None, "trading_cycle_execution", max_retries=3)
    def _fetch_market_data(self):
        """
        Fetch market data with error handling.
        
        Returns:
            DataFrame with market data or None if failed
        """
        # Use the instance's error handler
        # The decorator will use this error handler instead of the None passed above
        with_error_handling.current_error_handler = self.error_handler
        
        data = self.data_fetcher.fetch_crypto_data(self.symbol, timeframe="5Min", limit=50)
        
        # Store successful data for fallback
        if data is not None and not data.empty:
            self.previous_data = data
            
        return data
    
    @with_error_handling(None, "strategy_evaluation", max_retries=2)
    def _evaluate_strategies(self, data):
        """
        Evaluate trading strategies with error handling.
        
        Args:
            data: Market data DataFrame
            
        Returns:
            TradingSignal object
        """
        # Use the instance's error handler
        with_error_handling.current_error_handler = self.error_handler
        
        return self.signal_generator.evaluate_all_strategies(data)
    
    @with_error_handling(None, "trade_execution", max_retries=1)
    def _execute_trade(self, signal):
        """
        Execute trade with error handling.
        
        Args:
            signal: TradingSignal object
            
        Returns:
            TradeResult object or None if failed
        """
        # Use the instance's error handler
        with_error_handling.current_error_handler = self.error_handler
        
        if signal.action.value != "HOLD" and signal.confidence > 0.3:
            return self.trader.execute_trade(signal)
        return None
    
    def execute(self) -> bool:
        """
        Execute a single trading cycle.
        
        Returns:
            bool: True if cycle executed successfully, False otherwise
        """
        try:
            start_time = time.time()
            self.last_execution_time = datetime.now()
            self.execution_count += 1
            
            log_info(f"Starting trading cycle #{self.execution_count} at {self.last_execution_time}")
            
            # Step 1: Fetch market data with error handling
            data = self._fetch_market_data()
            
            # If data fetching failed and we have previous data, use it as fallback
            if (data is None or data.empty) and self.previous_data is not None:
                log_warning("Using previous data as fallback due to data fetching failure")
                data = self.previous_data
            elif data is None or data.empty:
                log_warning("No data received and no fallback data available, skipping cycle")
                return False
                
            # Get latest price
            latest_price = data['close'].iloc[-1]
            self.logger.update_price(self.symbol, latest_price)
            
            # Step 2: Evaluate strategies with error handling
            signal = self._evaluate_strategies(data)
            
            if signal is None:
                log_warning("Strategy evaluation failed, skipping cycle")
                return False
            
            # Log the signal
            signal_record = SignalRecord(
                action=signal.action.value,
                symbol=self.symbol,
                confidence=signal.confidence,
                strategy=signal.strategy,
                price=signal.price,
                timestamp=signal.timestamp,
                reasoning=signal.reasoning
            )
            self.logger.log_signal(signal_record)
            
            # Step 3: Execute trade if needed with error handling
            trade_result = self._execute_trade(signal)
                
            if trade_result:
                # Log the trade
                trade_record = TradeRecord(
                    order_id=trade_result.order_id,
                    symbol=trade_result.symbol,
                    side=trade_result.side,
                    quantity=trade_result.quantity,
                    price=trade_result.price,
                    timestamp=trade_result.timestamp,
                    status=trade_result.status,
                    fees=trade_result.fees
                )
                self.logger.log_trade(trade_record)
            
            # Step 4: Update position information
            try:
                self._update_position_info()
            except Exception as e:
                # Just log position errors, don't fail the cycle
                log_error("Error updating position information", e)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            log_info(f"Trading cycle completed in {execution_time:.2f} seconds")
            
            return True
            
        except Exception as e:
            self.error_count += 1
            recoverable, recovery_info = self.error_handler.handle_error(e, "trading_cycle")
            log_error(f"Error in trading cycle #{self.execution_count}: {str(e)}")
            self.logger.log_error(e, "Trading cycle execution")
            
            # Check if we should activate circuit breaker
            if self.error_handler.should_circuit_break(ErrorType.UNKNOWN, threshold=5, time_window=600):
                log_error("Circuit breaker activated due to frequent errors")
                # In a real system, we might want to pause trading for a while
                
            return False
    
    def _update_position_info(self) -> None:
        """Update position information in the logger."""
        try:
            # Get current position
            position = self.trader.position_manager.get_position(self.symbol)
            
            if position:
                # Create position record
                position_record = PositionRecord(
                    symbol=self.symbol,
                    quantity=float(position.qty),
                    market_value=float(position.market_value),
                    unrealized_pnl=float(position.unrealized_pl),
                    avg_entry_price=float(position.avg_entry_price)
                )
                
                # Update logger
                self.logger.update_position(position_record)
            else:
                # No position, update with zero values
                position_record = PositionRecord(
                    symbol=self.symbol,
                    quantity=0.0,
                    market_value=0.0,
                    unrealized_pnl=0.0,
                    avg_entry_price=0.0
                )
                self.logger.update_position(position_record)
                
        except Exception as e:
            log_error("Error updating position information", e)


class TradingScheduler:
    """
    Manages scheduling of trading cycles using APScheduler.
    Handles job scheduling, error recovery, and graceful shutdown.
    """
    
    def __init__(self, trading_cycle: TradingCycle, interval_minutes: int = 5, 
                error_handler: ErrorHandler = None):
        """
        Initialize the trading scheduler.
        
        Args:
            trading_cycle: TradingCycle instance to execute
            interval_minutes: Interval between trading cycles in minutes
            error_handler: ErrorHandler instance for error handling and recovery
        """
        self.trading_cycle = trading_cycle
        self.interval_minutes = interval_minutes
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.job = None
        self.error_recovery_attempts = 0
        self.max_recovery_attempts = 3
        self.shutdown_event = threading.Event()
        self.error_handler = error_handler or trading_cycle.error_handler or ErrorHandler()
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
        
        # Set up event listeners
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def start_scheduler(self) -> bool:
        """
        Start the scheduler.
        
        Returns:
            bool: True if scheduler started successfully, False otherwise
        """
        if self.is_running:
            log_warning("Scheduler is already running")
            return True
            
        try:
            # Add job with interval trigger
            self.job = self.scheduler.add_job(
                self.execute_trading_cycle,
                trigger=IntervalTrigger(minutes=self.interval_minutes),
                id='trading_cycle',
                name='Trading Cycle',
                replace_existing=True
            )
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            log_info(f"Scheduler started with {self.interval_minutes} minute interval")
            
            # Execute immediately for the first time
            self.execute_trading_cycle()
            
            return True
            
        except Exception as e:
            log_error("Error starting scheduler", e)
            return False
    
    def stop_scheduler(self) -> bool:
        """
        Stop the scheduler gracefully.
        
        Returns:
            bool: True if scheduler stopped successfully, False otherwise
        """
        if not self.is_running:
            log_warning("Scheduler is not running")
            return True
            
        try:
            # Set shutdown event
            self.shutdown_event.set()
            
            # Shutdown the scheduler
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            
            log_info("Scheduler stopped gracefully")
            return True
            
        except Exception as e:
            log_error("Error stopping scheduler", e)
            return False
    
    def execute_trading_cycle(self) -> None:
        """Execute a single trading cycle."""
        if self.shutdown_event.is_set():
            log_info("Shutdown in progress, skipping trading cycle")
            return
            
        success = self.trading_cycle.execute()
        
        if not success:
            self.handle_cycle_error(Exception("Trading cycle failed"))
    
    def handle_cycle_error(self, error: Exception) -> None:
        """
        Handle errors in the trading cycle with recovery mechanisms.
        
        Args:
            error: The exception that occurred
        """
        # Check if circuit breaker is active
        if self.circuit_breaker_active:
            now = datetime.now()
            if now < self.circuit_breaker_until:
                remaining = (self.circuit_breaker_until - now).total_seconds()
                log_warning(f"Circuit breaker active, skipping recovery for {remaining:.0f} more seconds")
                return
            else:
                log_info("Circuit breaker period ended, resuming normal operation")
                self.circuit_breaker_active = False
        
        # Use error handler to classify and handle the error
        error_type, severity = self.error_handler.classify_error(error)
        recoverable, recovery_info = self.error_handler.handle_error(error, "trading_cycle_scheduler")
        
        # Check if we should activate circuit breaker
        if self.error_handler.should_circuit_break(error_type, threshold=5, time_window=300):
            log_error(f"Circuit breaker activated due to frequent {error_type} errors")
            self.circuit_breaker_active = True
            self.circuit_breaker_until = datetime.now() + timedelta(minutes=5)  # 5 minute pause
            return
        
        # If error is not recoverable, log and return
        if not recoverable:
            log_error(f"Unrecoverable error in trading cycle: {str(error)}")
            return
        
        # Increment recovery attempts
        self.error_recovery_attempts += 1
        
        log_warning(f"Trading cycle error (attempt {self.error_recovery_attempts}/{self.max_recovery_attempts}): {str(error)}")
        
        if self.error_recovery_attempts >= self.max_recovery_attempts:
            log_error("Maximum recovery attempts reached, resetting error counter")
            self.error_recovery_attempts = 0
            return
        
        # Use error handler's backoff calculation
        retry_delay = self.error_handler.calculate_backoff_delay(
            recovery_info.get("retry_delay", 30),
            self.error_recovery_attempts - 1,
            recovery_info.get("backoff_factor", 2.0),
            recovery_info.get("jitter", True)
        )
        
        log_info(f"Scheduling recovery attempt in {retry_delay:.2f} seconds")
        
        # Schedule a one-time recovery job
        self.scheduler.add_job(
            self.execute_trading_cycle,
            trigger='date',
            run_date=datetime.now() + timedelta(seconds=retry_delay),
            id=f'recovery_{self.error_recovery_attempts}',
            name='Trading Cycle Recovery',
            replace_existing=True
        )
    
    def _job_executed_listener(self, event) -> None:
        """
        Listener for job execution events.
        
        Args:
            event: The job event
        """
        if event.job_id == 'trading_cycle':
            # Reset error recovery attempts on successful execution
            if self.error_recovery_attempts > 0:
                log_info("Trading cycle recovered successfully")
                self.error_recovery_attempts = 0
    
    def _job_error_listener(self, event) -> None:
        """
        Listener for job error events.
        
        Args:
            event: The job event
        """
        if event.job_id == 'trading_cycle':
            log_error(f"Job error: {str(event.exception)}")
            self.handle_cycle_error(event.exception)
    
    def _signal_handler(self, sig, frame) -> None:
        """
        Handle termination signals for graceful shutdown.
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        log_info(f"Received signal {sig}, shutting down scheduler gracefully")
        self.stop_scheduler()