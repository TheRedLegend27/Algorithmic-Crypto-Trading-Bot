"""
Mock Trading Error Handler

This module implements comprehensive error handling and simulation realism for the mock trading environment.
It provides realistic error simulation, partial fill handling, market gap scenarios, and system failure simulation.
"""
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import threading
from collections import defaultdict

from .mock_models import (
    Order, OrderResult, OrderType, OrderSide, OrderStatus, ExecutionResult,
    MockPosition, validate_order
)
from .mock_config import MockTradingConfig
from bot.utils import log_error, log_info, log_warning


class ErrorType(Enum):
    """Types of errors that can occur in trading simulation."""
    NETWORK_ERROR = "NETWORK_ERROR"
    BROKER_ERROR = "BROKER_ERROR"
    MARKET_DATA_ERROR = "MARKET_DATA_ERROR"
    SYSTEM_OVERLOAD = "SYSTEM_OVERLOAD"
    LIQUIDITY_ERROR = "LIQUIDITY_ERROR"
    PRICE_REJECTION = "PRICE_REJECTION"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    PARTIAL_FILL_ERROR = "PARTIAL_FILL_ERROR"
    MARKET_GAP_ERROR = "MARKET_GAP_ERROR"
    SYSTEM_FAILURE = "SYSTEM_FAILURE"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ErrorScenario:
    """Configuration for error simulation scenarios."""
    error_type: ErrorType
    probability: float  # 0.0 to 1.0
    severity: ErrorSeverity
    recovery_time_seconds: float
    affects_all_orders: bool = False
    message_template: str = ""
    
    def __post_init__(self):
        """Validate error scenario configuration."""
        if not (0.0 <= self.probability <= 1.0):
            raise ValueError("Error probability must be between 0.0 and 1.0")
        if self.recovery_time_seconds < 0:
            raise ValueError("Recovery time cannot be negative")


@dataclass
class MarketGapEvent:
    """Represents a market gap event."""
    symbol: str
    gap_start_price: float
    gap_end_price: float
    gap_direction: str  # "UP" or "DOWN"
    gap_size_percent: float
    timestamp: datetime
    duration_seconds: float = 0.0  # How long the gap lasts
    
    @property
    def is_gap_up(self) -> bool:
        """Check if this is a gap up event."""
        return self.gap_direction == "UP"
    
    @property
    def is_gap_down(self) -> bool:
        """Check if this is a gap down event."""
        return self.gap_direction == "DOWN"


@dataclass
class LiquidityCondition:
    """Represents market liquidity conditions."""
    symbol: str
    available_volume: float
    bid_depth: float
    ask_depth: float
    spread_multiplier: float = 1.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def is_low_liquidity(self) -> bool:
        """Check if this represents low liquidity conditions."""
        return self.available_volume < 1000 or self.spread_multiplier > 2.0


class PartialFillSimulator:
    """
    Simulates partial fills for large orders and low liquidity conditions.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize partial fill simulator.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.partial_fill_probability = getattr(config.execution, 'partial_fill_probability', 0.1)
        self.min_fill_percentage = getattr(config.execution, 'min_fill_percentage', 0.3)
        self.large_order_threshold = getattr(config.execution, 'large_order_threshold', 5000.0)
        
        # Track liquidity conditions per symbol
        self.liquidity_conditions: Dict[str, LiquidityCondition] = {}
    
    def should_partial_fill(
        self, 
        order: Order, 
        market_price: float,
        liquidity_condition: Optional[LiquidityCondition] = None
    ) -> Tuple[bool, float]:
        """
        Determine if an order should be partially filled.
        
        Args:
            order: Order to evaluate
            market_price: Current market price
            liquidity_condition: Current liquidity conditions
            
        Returns:
            Tuple: (should_partial_fill, fill_percentage)
        """
        order_value = order.quantity * market_price
        base_probability = self.partial_fill_probability
        
        # Increase probability for large orders
        if order_value > self.large_order_threshold:
            size_factor = min(order_value / self.large_order_threshold, 5.0)
            base_probability *= size_factor
        
        # Increase probability in low liquidity conditions
        if liquidity_condition and liquidity_condition.is_low_liquidity:
            base_probability *= 2.0
        
        # Market orders are more likely to be partially filled
        if order.order_type == OrderType.MARKET:
            base_probability *= 1.5
        
        # Cap probability at 80%
        final_probability = min(base_probability, 0.8)
        
        if random.random() < final_probability:
            # Calculate fill percentage
            if liquidity_condition and liquidity_condition.is_low_liquidity:
                # Lower fill percentage in low liquidity
                fill_percentage = random.uniform(0.1, 0.5)
            else:
                # Normal partial fill
                fill_percentage = random.uniform(self.min_fill_percentage, 0.9)
            
            return True, fill_percentage
        
        return False, 1.0
    
    def simulate_partial_fill(
        self, 
        order: Order, 
        execution_price: float,
        liquidity_condition: Optional[LiquidityCondition] = None
    ) -> ExecutionResult:
        """
        Simulate a partial fill execution.
        
        Args:
            order: Order to partially fill
            execution_price: Price for execution
            liquidity_condition: Current liquidity conditions
            
        Returns:
            ExecutionResult: Partial fill result
        """
        should_partial, fill_percentage = self.should_partial_fill(
            order, execution_price, liquidity_condition
        )
        
        if not should_partial:
            fill_percentage = 1.0
        
        executed_quantity = order.remaining_quantity * fill_percentage
        remaining_quantity = order.remaining_quantity - executed_quantity
        
        # Calculate fees for executed portion
        fees = (executed_quantity * execution_price) * self.config.fees.trading_fee_percent
        fees += self.config.fees.trading_fee_fixed if executed_quantity > 0 else 0.0
        
        # Add liquidity impact if in low liquidity
        liquidity_impact = 0.0
        if liquidity_condition and liquidity_condition.is_low_liquidity:
            liquidity_impact = random.uniform(0.0001, 0.001)  # 0.01% to 0.1%
        
        result = ExecutionResult(
            order_id=order.id,
            symbol=order.symbol,
            executed_quantity=executed_quantity,
            execution_price=execution_price,
            slippage=0.0,  # Will be set by execution engine
            fees=fees,
            execution_time=datetime.now(),
            market_impact=0.0,  # Will be set by execution engine
            partial_fill=should_partial,
            remaining_quantity=remaining_quantity,
            execution_delay_ms=0,  # Will be set by execution engine
            liquidity_impact=liquidity_impact
        )
        
        # Update order with partial fill
        order.update_fill(executed_quantity, execution_price, fees)
        
        log_info(f"Partial fill simulated: {order.id} filled {executed_quantity:.4f} "
                f"of {order.quantity:.4f} at {execution_price:.4f}")
        
        return result
    
    def update_liquidity_condition(self, symbol: str, condition: LiquidityCondition):
        """Update liquidity conditions for a symbol."""
        self.liquidity_conditions[symbol] = condition
    
    def get_liquidity_condition(self, symbol: str) -> Optional[LiquidityCondition]:
        """Get current liquidity conditions for a symbol."""
        return self.liquidity_conditions.get(symbol)


class MarketGapHandler:
    """
    Handles market gap scenarios for limit orders and stop-loss orders.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize market gap handler.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.gap_probability = 0.001  # 0.1% chance per price update
        self.min_gap_size = 0.01  # 1% minimum gap
        self.max_gap_size = 0.05  # 5% maximum gap
        
        # Track active gaps
        self.active_gaps: Dict[str, MarketGapEvent] = {}
        self.gap_history: List[MarketGapEvent] = []
    
    def should_create_gap(self, symbol: str, current_price: float) -> bool:
        """
        Determine if a market gap should occur.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            bool: True if a gap should occur
        """
        # Don't create gaps too frequently
        if symbol in self.active_gaps:
            return False
        
        # Check recent gap history
        recent_gaps = [gap for gap in self.gap_history 
                      if gap.symbol == symbol and 
                      (datetime.now() - gap.timestamp).total_seconds() < 3600]  # 1 hour
        
        if len(recent_gaps) >= 2:  # Max 2 gaps per hour per symbol
            return False
        
        return random.random() < self.gap_probability
    
    def create_market_gap(self, symbol: str, current_price: float) -> MarketGapEvent:
        """
        Create a market gap event.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            MarketGapEvent: Created gap event
        """
        # Determine gap direction (slightly more likely to gap down)
        gap_direction = "DOWN" if random.random() < 0.6 else "UP"
        
        # Calculate gap size
        gap_size_percent = random.uniform(self.min_gap_size, self.max_gap_size)
        
        if gap_direction == "UP":
            gap_end_price = current_price * (1 + gap_size_percent)
        else:
            gap_end_price = current_price * (1 - gap_size_percent)
        
        gap_event = MarketGapEvent(
            symbol=symbol,
            gap_start_price=current_price,
            gap_end_price=gap_end_price,
            gap_direction=gap_direction,
            gap_size_percent=gap_size_percent,
            timestamp=datetime.now(),
            duration_seconds=random.uniform(1.0, 10.0)  # Gap lasts 1-10 seconds
        )
        
        # Store active gap
        self.active_gaps[symbol] = gap_event
        self.gap_history.append(gap_event)
        
        # Limit history size
        if len(self.gap_history) > 100:
            self.gap_history.pop(0)
        
        log_warning(f"Market gap created: {symbol} {gap_direction} "
                   f"{gap_size_percent*100:.2f}% from {current_price:.4f} to {gap_end_price:.4f}")
        
        return gap_event
    
    def handle_limit_order_gap(
        self, 
        order: Order, 
        gap_event: MarketGapEvent
    ) -> Optional[ExecutionResult]:
        """
        Handle limit order execution during a market gap.
        
        Args:
            order: Limit order to handle
            gap_event: Market gap event
            
        Returns:
            Optional[ExecutionResult]: Execution result if order is triggered
        """
        if order.order_type != OrderType.LIMIT:
            return None
        
        # Check if limit order would be triggered by the gap
        triggered = False
        execution_price = order.price
        
        if order.side == OrderSide.BUY:
            # Buy limit order: triggered if gap goes down through limit price
            if (gap_event.is_gap_down and 
                gap_event.gap_start_price >= order.price >= gap_event.gap_end_price):
                triggered = True
                # Execute at limit price or better
                execution_price = min(order.price, gap_event.gap_end_price)
        else:
            # Sell limit order: triggered if gap goes up through limit price
            if (gap_event.is_gap_up and 
                gap_event.gap_start_price <= order.price <= gap_event.gap_end_price):
                triggered = True
                # Execute at limit price or better
                execution_price = max(order.price, gap_event.gap_end_price)
        
        if not triggered:
            return None
        
        # Create execution result for gap execution
        fees = (order.quantity * execution_price) * self.config.fees.trading_fee_percent
        fees += self.config.fees.trading_fee_fixed
        
        result = ExecutionResult(
            order_id=order.id,
            symbol=order.symbol,
            executed_quantity=order.quantity,
            execution_price=execution_price,
            slippage=0.0,  # No slippage for gap executions
            fees=fees,
            execution_time=datetime.now(),
            market_impact=0.0,
            partial_fill=False,
            remaining_quantity=0.0,
            execution_delay_ms=0,  # Instant execution during gap
            liquidity_impact=0.0
        )
        
        # Update order
        order.update_fill(order.quantity, execution_price, fees)
        
        log_info(f"Limit order executed during gap: {order.id} at {execution_price:.4f} "
                f"(gap: {gap_event.gap_direction} {gap_event.gap_size_percent*100:.2f}%)")
        
        return result
    
    def handle_stop_loss_gap(
        self, 
        order: Order, 
        gap_event: MarketGapEvent
    ) -> Optional[ExecutionResult]:
        """
        Handle stop-loss order execution during a market gap.
        
        Args:
            order: Stop order to handle
            gap_event: Market gap event
            
        Returns:
            Optional[ExecutionResult]: Execution result if order is triggered
        """
        if order.order_type not in [OrderType.STOP, OrderType.STOP_LIMIT]:
            return None
        
        if not order.stop_price:
            return None
        
        # Check if stop order would be triggered by the gap
        triggered = False
        execution_price = gap_event.gap_end_price
        
        if order.side == OrderSide.SELL:
            # Stop-loss sell: triggered if gap goes down through stop price
            if (gap_event.is_gap_down and 
                gap_event.gap_start_price >= order.stop_price >= gap_event.gap_end_price):
                triggered = True
                # Execute at gap end price (slippage through stop)
                execution_price = gap_event.gap_end_price
        else:
            # Stop-loss buy: triggered if gap goes up through stop price
            if (gap_event.is_gap_up and 
                gap_event.gap_start_price <= order.stop_price <= gap_event.gap_end_price):
                triggered = True
                # Execute at gap end price
                execution_price = gap_event.gap_end_price
        
        if not triggered:
            return None
        
        # For stop-limit orders, check if limit price is still valid
        if order.order_type == OrderType.STOP_LIMIT and order.price:
            if order.side == OrderSide.SELL and execution_price < order.price:
                # Stop-limit sell: can't execute below limit price
                log_warning(f"Stop-limit order {order.id} triggered but price {execution_price:.4f} "
                           f"below limit {order.price:.4f}")
                return None
            elif order.side == OrderSide.BUY and execution_price > order.price:
                # Stop-limit buy: can't execute above limit price
                log_warning(f"Stop-limit order {order.id} triggered but price {execution_price:.4f} "
                           f"above limit {order.price:.4f}")
                return None
        
        # Calculate fees
        fees = (order.quantity * execution_price) * self.config.fees.trading_fee_percent
        fees += self.config.fees.trading_fee_fixed
        
        # Calculate slippage (significant for stop orders in gaps)
        expected_price = order.stop_price
        slippage_percent = abs(execution_price - expected_price) / expected_price
        
        result = ExecutionResult(
            order_id=order.id,
            symbol=order.symbol,
            executed_quantity=order.quantity,
            execution_price=execution_price,
            slippage=slippage_percent,
            fees=fees,
            execution_time=datetime.now(),
            market_impact=0.0,
            partial_fill=False,
            remaining_quantity=0.0,
            execution_delay_ms=0,
            liquidity_impact=0.0
        )
        
        # Update order
        order.update_fill(order.quantity, execution_price, fees)
        
        log_warning(f"Stop order executed during gap: {order.id} at {execution_price:.4f} "
                   f"(stop: {order.stop_price:.4f}, slippage: {slippage_percent*100:.2f}%)")
        
        return result
    
    def cleanup_expired_gaps(self):
        """Clean up expired gap events."""
        current_time = datetime.now()
        expired_symbols = []
        
        for symbol, gap_event in self.active_gaps.items():
            if (current_time - gap_event.timestamp).total_seconds() > gap_event.duration_seconds:
                expired_symbols.append(symbol)
        
        for symbol in expired_symbols:
            del self.active_gaps[symbol]
            log_info(f"Market gap expired for {symbol}")
    
    def get_active_gap(self, symbol: str) -> Optional[MarketGapEvent]:
        """Get active gap event for a symbol."""
        return self.active_gaps.get(symbol)


class SystemFailureSimulator:
    """
    Simulates system failures and recovery mechanisms.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize system failure simulator.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.failure_probability = 0.0001  # 0.01% chance per operation
        self.recovery_time_range = (5.0, 30.0)  # 5-30 seconds recovery time
        
        # Track system state
        self.system_failures: Dict[str, datetime] = {}
        self.failure_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
    
    def should_simulate_failure(self, operation_type: str) -> bool:
        """
        Determine if a system failure should be simulated.
        
        Args:
            operation_type: Type of operation being performed
            
        Returns:
            bool: True if failure should be simulated
        """
        with self._lock:
            # Don't simulate failures too frequently
            recent_failures = [f for f in self.failure_history 
                             if (datetime.now() - f['timestamp']).total_seconds() < 300]  # 5 minutes
            
            if len(recent_failures) >= 3:  # Max 3 failures per 5 minutes
                return False
            
            # Check if system is currently in failure state
            if operation_type in self.system_failures:
                recovery_time = datetime.now() - self.system_failures[operation_type]
                if recovery_time.total_seconds() < 60:  # Minimum 1 minute between failures
                    return False
            
            return random.random() < self.failure_probability
    
    def simulate_system_failure(self, operation_type: str) -> Dict[str, Any]:
        """
        Simulate a system failure.
        
        Args:
            operation_type: Type of operation that failed
            
        Returns:
            Dict: Failure details
        """
        with self._lock:
            failure_time = datetime.now()
            recovery_time = random.uniform(*self.recovery_time_range)
            
            failure_details = {
                'operation_type': operation_type,
                'timestamp': failure_time,
                'recovery_time_seconds': recovery_time,
                'error_message': self._generate_failure_message(operation_type),
                'failure_id': str(uuid.uuid4())[:8]
            }
            
            # Record failure
            self.system_failures[operation_type] = failure_time
            self.failure_history.append(failure_details)
            
            # Limit history size
            if len(self.failure_history) > 50:
                self.failure_history.pop(0)
            
            log_error(f"System failure simulated: {operation_type} - {failure_details['error_message']}")
            
            return failure_details
    
    def is_system_recovering(self, operation_type: str) -> Tuple[bool, Optional[float]]:
        """
        Check if system is currently recovering from a failure.
        
        Args:
            operation_type: Type of operation to check
            
        Returns:
            Tuple: (is_recovering, remaining_recovery_time_seconds)
        """
        with self._lock:
            if operation_type not in self.system_failures:
                return False, None
            
            failure_time = self.system_failures[operation_type]
            elapsed_time = (datetime.now() - failure_time).total_seconds()
            
            # Find the recovery time for this failure
            recovery_time = 30.0  # Default
            for failure in reversed(self.failure_history):
                if (failure['operation_type'] == operation_type and 
                    failure['timestamp'] == failure_time):
                    recovery_time = failure['recovery_time_seconds']
                    break
            
            if elapsed_time < recovery_time:
                return True, recovery_time - elapsed_time
            else:
                # Recovery complete
                del self.system_failures[operation_type]
                log_info(f"System recovery complete: {operation_type}")
                return False, None
    
    def _generate_failure_message(self, operation_type: str) -> str:
        """Generate realistic failure message."""
        messages = {
            'order_submission': [
                "Order gateway temporarily unavailable",
                "High system load - order processing delayed",
                "Network connectivity issues detected",
                "Order validation service timeout"
            ],
            'market_data': [
                "Market data feed interrupted",
                "Price service temporarily unavailable",
                "Data provider connection lost",
                "Quote server maintenance in progress"
            ],
            'execution': [
                "Execution engine temporarily offline",
                "Trade settlement system unavailable",
                "Clearing service connection timeout",
                "Position update service error"
            ],
            'portfolio': [
                "Portfolio service temporarily unavailable",
                "Account data synchronization error",
                "Balance calculation service timeout",
                "Position reconciliation in progress"
            ]
        }
        
        operation_messages = messages.get(operation_type, ["System temporarily unavailable"])
        return random.choice(operation_messages)


class MockTradingErrorHandler:
    """
    Main error handler that orchestrates all error simulation components.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize mock trading error handler.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        
        # Initialize simulation components
        self.partial_fill_simulator = PartialFillSimulator(config)
        self.market_gap_handler = MarketGapHandler(config)
        self.system_failure_simulator = SystemFailureSimulator(config)
        
        # Error scenario configurations
        self.error_scenarios = self._initialize_error_scenarios()
        
        # Statistics tracking
        self.error_stats = {
            'total_errors': 0,
            'partial_fills': 0,
            'market_gaps': 0,
            'system_failures': 0,
            'recoveries': 0
        }
    
    def _initialize_error_scenarios(self) -> List[ErrorScenario]:
        """Initialize default error scenarios."""
        return [
            ErrorScenario(
                error_type=ErrorType.NETWORK_ERROR,
                probability=0.001,
                severity=ErrorSeverity.MEDIUM,
                recovery_time_seconds=5.0,
                message_template="Network connectivity issues detected"
            ),
            ErrorScenario(
                error_type=ErrorType.LIQUIDITY_ERROR,
                probability=0.005,
                severity=ErrorSeverity.LOW,
                recovery_time_seconds=2.0,
                message_template="Insufficient liquidity for order size"
            ),
            ErrorScenario(
                error_type=ErrorType.SYSTEM_OVERLOAD,
                probability=0.0005,
                severity=ErrorSeverity.HIGH,
                recovery_time_seconds=15.0,
                affects_all_orders=True,
                message_template="System experiencing high load"
            ),
            ErrorScenario(
                error_type=ErrorType.TIMEOUT_ERROR,
                probability=0.002,
                severity=ErrorSeverity.MEDIUM,
                recovery_time_seconds=3.0,
                message_template="Request timeout - please retry"
            )
        ]
    
    def handle_order_execution(
        self, 
        order: Order, 
        market_price: float,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[ExecutionResult], Optional[str]]:
        """
        Handle order execution with comprehensive error simulation.
        
        Args:
            order: Order to execute
            market_price: Current market price
            market_data: Additional market data
            
        Returns:
            Tuple: (success, execution_result, error_message)
        """
        try:
            # Check for system failures first
            is_recovering, remaining_time = self.system_failure_simulator.is_system_recovering('execution')
            if is_recovering:
                return False, None, f"System recovering - {remaining_time:.1f}s remaining"
            
            # Simulate system failure
            if self.system_failure_simulator.should_simulate_failure('execution'):
                failure_details = self.system_failure_simulator.simulate_system_failure('execution')
                self.error_stats['system_failures'] += 1
                return False, None, failure_details['error_message']
            
            # Check for market gaps
            if self.market_gap_handler.should_create_gap(order.symbol, market_price):
                gap_event = self.market_gap_handler.create_market_gap(order.symbol, market_price)
                self.error_stats['market_gaps'] += 1
                
                # Handle gap execution for limit and stop orders
                if order.order_type == OrderType.LIMIT:
                    gap_result = self.market_gap_handler.handle_limit_order_gap(order, gap_event)
                    if gap_result:
                        return True, gap_result, None
                elif order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                    gap_result = self.market_gap_handler.handle_stop_loss_gap(order, gap_event)
                    if gap_result:
                        return True, gap_result, None
            
            # Get liquidity conditions
            liquidity_condition = self.partial_fill_simulator.get_liquidity_condition(order.symbol)
            
            # Simulate partial fills
            if self.config.execution.enable_partial_fills:
                result = self.partial_fill_simulator.simulate_partial_fill(
                    order, market_price, liquidity_condition
                )
                if result.partial_fill:
                    self.error_stats['partial_fills'] += 1
                return True, result, None
            
            # Normal execution (no errors)
            fees = (order.quantity * market_price) * self.config.fees.trading_fee_percent
            fees += self.config.fees.trading_fee_fixed
            
            result = ExecutionResult(
                order_id=order.id,
                symbol=order.symbol,
                executed_quantity=order.quantity,
                execution_price=market_price,
                slippage=0.0,
                fees=fees,
                execution_time=datetime.now(),
                market_impact=0.0,
                partial_fill=False,
                remaining_quantity=0.0,
                execution_delay_ms=0,
                liquidity_impact=0.0
            )
            
            order.update_fill(order.quantity, market_price, fees)
            return True, result, None
            
        except Exception as e:
            log_error(f"Error in order execution handling: {e}")
            self.error_stats['total_errors'] += 1
            return False, None, f"Execution error: {str(e)}"
    
    def handle_market_data_error(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Handle market data errors.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Tuple: (data_available, error_message)
        """
        # Check for system failures
        is_recovering, remaining_time = self.system_failure_simulator.is_system_recovering('market_data')
        if is_recovering:
            return False, f"Market data service recovering - {remaining_time:.1f}s remaining"
        
        # Simulate market data failure
        if self.system_failure_simulator.should_simulate_failure('market_data'):
            failure_details = self.system_failure_simulator.simulate_system_failure('market_data')
            self.error_stats['system_failures'] += 1
            return False, failure_details['error_message']
        
        return True, None
    
    def handle_portfolio_error(self) -> Tuple[bool, Optional[str]]:
        """
        Handle portfolio service errors.
        
        Returns:
            Tuple: (service_available, error_message)
        """
        # Check for system failures
        is_recovering, remaining_time = self.system_failure_simulator.is_system_recovering('portfolio')
        if is_recovering:
            return False, f"Portfolio service recovering - {remaining_time:.1f}s remaining"
        
        # Simulate portfolio service failure
        if self.system_failure_simulator.should_simulate_failure('portfolio'):
            failure_details = self.system_failure_simulator.simulate_system_failure('portfolio')
            self.error_stats['system_failures'] += 1
            return False, failure_details['error_message']
        
        return True, None
    
    def update_liquidity_conditions(self, symbol: str, volume: float, spread: float):
        """
        Update liquidity conditions for a symbol.
        
        Args:
            symbol: Trading symbol
            volume: Available volume
            spread: Bid-ask spread
        """
        condition = LiquidityCondition(
            symbol=symbol,
            available_volume=volume,
            bid_depth=volume * 0.3,
            ask_depth=volume * 0.3,
            spread_multiplier=max(1.0, spread / 0.001),  # Normal spread is 0.1%
            timestamp=datetime.now()
        )
        
        self.partial_fill_simulator.update_liquidity_condition(symbol, condition)
    
    def cleanup_expired_events(self):
        """Clean up expired error events and gaps."""
        self.market_gap_handler.cleanup_expired_gaps()
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        return {
            **self.error_stats,
            'active_gaps': len(self.market_gap_handler.active_gaps),
            'active_failures': len(self.system_failure_simulator.system_failures),
            'gap_history_count': len(self.market_gap_handler.gap_history),
            'failure_history_count': len(self.system_failure_simulator.failure_history)
        }
    
    def reset_statistics(self):
        """Reset error statistics."""
        self.error_stats = {
            'total_errors': 0,
            'partial_fills': 0,
            'market_gaps': 0,
            'system_failures': 0,
            'recoveries': 0
        }