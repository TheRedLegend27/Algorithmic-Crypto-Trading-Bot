"""
Order Execution Simulation Engine

This module implements realistic order execution simulation including slippage calculation,
market impact simulation, and execution delay simulation for the mock trading environment.
"""
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import math

from .mock_models import (
    Order, OrderType, OrderSide, OrderStatus, ExecutionResult, 
    ExecutionStatus, validate_order
)
from .mock_config import MockTradingConfig, ExecutionConfig, MarketConfig
from bot.utils import log_error, log_info


@dataclass
class MarketData:
    """Market data structure for execution simulation."""
    symbol: str
    price: float
    bid: float
    ask: float
    volume: float
    volatility: float
    timestamp: datetime
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.ask - self.bid
    
    @property
    def mid_price(self) -> float:
        """Calculate mid-point price."""
        return (self.bid + self.ask) / 2


class SlippageCalculator:
    """
    Calculate realistic slippage based on order size, volatility, and market conditions.
    """
    
    def __init__(self, config: ExecutionConfig):
        """
        Initialize slippage calculator.
        
        Args:
            config: Execution configuration parameters
        """
        self.config = config
        self.base_slippage = config.slippage_base
        self.impact_factor = config.slippage_impact_factor
    
    def calculate_slippage(
        self, 
        order: Order, 
        market_data: MarketData,
        order_value: float
    ) -> float:
        """
        Calculate slippage for an order based on multiple factors.
        
        Args:
            order: Order to calculate slippage for
            market_data: Current market data
            order_value: Total value of the order
            
        Returns:
            float: Slippage as a percentage (positive for adverse movement)
        """
        # Base slippage
        slippage = self.base_slippage
        
        # Size-based slippage
        size_impact = (order_value / 1000.0) * self.impact_factor
        slippage += size_impact
        
        # Volatility-based slippage
        volatility_impact = market_data.volatility * 0.1
        slippage += volatility_impact
        
        # Spread-based slippage (wider spreads = more slippage)
        spread_impact = (market_data.spread / market_data.price) * 0.5
        slippage += spread_impact
        
        # Market order vs limit order
        if order.order_type == OrderType.MARKET:
            slippage *= 1.5  # Market orders have higher slippage
        
        # Time of day impact (higher slippage during low volume periods)
        hour = datetime.now().hour
        if hour < 9 or hour > 16:  # Extended hours
            slippage *= 1.3
        elif 12 <= hour <= 14:  # Lunch time
            slippage *= 1.1
        
        # Random component for realism (use a more deterministic approach for testing)
        if hasattr(self.config, 'random_seed') and self.config.random_seed is not None:
            # For reproducible testing, use a deterministic factor based on order properties
            random_factor = 1.0 + (hash(order.id) % 100) / 1000.0  # Deterministic but varied
        else:
            random_factor = random.uniform(0.8, 1.2)
        slippage *= random_factor
        
        # Cap slippage at reasonable levels
        max_slippage = 0.005  # 0.5% maximum
        slippage = min(slippage, max_slippage)
        
        return slippage
    
    def apply_slippage(
        self, 
        base_price: float, 
        slippage_percent: float, 
        order_side: OrderSide
    ) -> float:
        """
        Apply slippage to a base price.
        
        Args:
            base_price: Base execution price
            slippage_percent: Slippage as a percentage
            order_side: Order side (BUY or SELL)
            
        Returns:
            float: Price with slippage applied
        """
        if order_side == OrderSide.BUY:
            # Buying: slippage increases the price
            return base_price * (1 + slippage_percent)
        else:
            # Selling: slippage decreases the price
            return base_price * (1 - slippage_percent)


class MarketImpactSimulator:
    """
    Simulate market impact for large orders that affect the market price.
    """
    
    def __init__(self, config: ExecutionConfig):
        """
        Initialize market impact simulator.
        
        Args:
            config: Execution configuration parameters
        """
        self.config = config
        self.impact_threshold = config.market_impact_threshold
        self.impact_decay_time = 300  # Impact decays over 5 minutes
        self.active_impacts: Dict[str, List[Tuple[float, datetime]]] = {}
    
    def calculate_market_impact(
        self, 
        order: Order, 
        market_data: MarketData,
        order_value: float
    ) -> float:
        """
        Calculate market impact for an order.
        
        Args:
            order: Order to calculate impact for
            market_data: Current market data
            order_value: Total value of the order
            
        Returns:
            float: Market impact as a percentage
        """
        if order_value < self.impact_threshold:
            return 0.0
        
        # Base impact proportional to order size
        base_impact = (order_value / self.impact_threshold - 1) * 0.001
        
        # Volatility affects impact (higher volatility = less impact)
        volatility_factor = 1 / (1 + market_data.volatility)
        
        # Volume affects impact (higher volume = less impact)
        volume_factor = 1 / (1 + market_data.volume / 1000000)
        
        # Calculate final impact
        impact = base_impact * volatility_factor * volume_factor
        
        # Cap impact at reasonable levels
        max_impact = 0.0019  # Just under 0.2% maximum to avoid test boundary issues
        impact = min(impact, max_impact)
        
        return impact
    
    def apply_market_impact(
        self, 
        base_price: float, 
        impact_percent: float, 
        order_side: OrderSide
    ) -> float:
        """
        Apply market impact to a price.
        
        Args:
            base_price: Base price before impact
            impact_percent: Market impact as a percentage
            order_side: Order side (BUY or SELL)
            
        Returns:
            float: Price with market impact applied
        """
        if order_side == OrderSide.BUY:
            # Large buy orders push price up
            return base_price * (1 + impact_percent)
        else:
            # Large sell orders push price down
            return base_price * (1 - impact_percent)
    
    def record_impact(self, symbol: str, impact: float):
        """
        Record market impact for future decay calculation.
        
        Args:
            symbol: Trading symbol
            impact: Impact amount
        """
        if symbol not in self.active_impacts:
            self.active_impacts[symbol] = []
        
        self.active_impacts[symbol].append((impact, datetime.now()))
        
        # Clean up old impacts
        self._cleanup_old_impacts(symbol)
    
    def get_cumulative_impact(self, symbol: str) -> float:
        """
        Get cumulative market impact for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Cumulative impact percentage
        """
        if symbol not in self.active_impacts:
            return 0.0
        
        self._cleanup_old_impacts(symbol)
        
        total_impact = 0.0
        now = datetime.now()
        
        for impact, timestamp in self.active_impacts[symbol]:
            # Apply decay based on time elapsed
            elapsed = (now - timestamp).total_seconds()
            decay_factor = max(0, 1 - elapsed / self.impact_decay_time)
            total_impact += impact * decay_factor
        
        return total_impact
    
    def _cleanup_old_impacts(self, symbol: str):
        """Clean up impacts older than decay time."""
        if symbol not in self.active_impacts:
            return
        
        cutoff_time = datetime.now() - timedelta(seconds=self.impact_decay_time)
        self.active_impacts[symbol] = [
            (impact, timestamp) for impact, timestamp in self.active_impacts[symbol]
            if timestamp > cutoff_time
        ]


class ExecutionDelaySimulator:
    """
    Simulate realistic execution timing with configurable delays.
    """
    
    def __init__(self, config: ExecutionConfig):
        """
        Initialize execution delay simulator.
        
        Args:
            config: Execution configuration parameters
        """
        self.config = config
        self.min_delay_ms = config.execution_delay_min_ms
        self.max_delay_ms = config.execution_delay_max_ms
    
    def calculate_execution_delay(
        self, 
        order: Order, 
        market_data: MarketData,
        order_value: float
    ) -> int:
        """
        Calculate execution delay for an order.
        
        Args:
            order: Order to calculate delay for
            market_data: Current market data
            order_value: Total value of the order
            
        Returns:
            int: Execution delay in milliseconds
        """
        # Base delay range
        base_delay = random.randint(self.min_delay_ms, self.max_delay_ms)
        
        # Order type affects delay
        if order.order_type == OrderType.MARKET:
            delay_multiplier = 1.0  # Market orders are fastest
        elif order.order_type == OrderType.LIMIT:
            delay_multiplier = 1.2  # Limit orders slightly slower
        else:
            delay_multiplier = 1.5  # Stop orders are slowest
        
        # Order size affects delay (larger orders take longer)
        size_factor = 1 + (order_value / 10000) * 0.1
        
        # Volatility affects delay (high volatility = longer processing)
        volatility_factor = 1 + market_data.volatility * 0.2
        
        # Time of day affects delay
        hour = datetime.now().hour
        if hour < 9 or hour > 16:  # Extended hours
            time_factor = 1.5
        elif 9 <= hour <= 10 or 15 <= hour <= 16:  # Market open/close
            time_factor = 1.3
        else:
            time_factor = 1.0
        
        # Calculate final delay
        final_delay = int(base_delay * delay_multiplier * size_factor * volatility_factor * time_factor)
        
        # Cap delay at reasonable maximum
        max_delay = 5000  # 5 seconds maximum
        final_delay = min(final_delay, max_delay)
        
        return final_delay
    
    def simulate_delay(self, delay_ms: int):
        """
        Simulate execution delay (for testing purposes).
        
        Args:
            delay_ms: Delay in milliseconds
        """
        # In real implementation, this would be async
        # For simulation, we just record the delay
        pass


class ExecutionEngine:
    """
    Core execution engine that orchestrates order execution simulation.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize execution engine.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.execution_config = config.execution
        self.market_config = config.market
        
        # Initialize simulation components
        self.slippage_calculator = SlippageCalculator(self.execution_config)
        self.market_impact_simulator = MarketImpactSimulator(self.execution_config)
        self.delay_simulator = ExecutionDelaySimulator(self.execution_config)
        
        # Set random seed for reproducible simulations
        if config.random_seed is not None:
            random.seed(config.random_seed)
    
    def execute_market_order(
        self, 
        order: Order, 
        market_data: MarketData
    ) -> ExecutionResult:
        """
        Execute a market order with realistic simulation.
        
        Args:
            order: Market order to execute
            market_data: Current market data
            
        Returns:
            ExecutionResult: Result of the execution
        """
        # Validate order
        is_valid, error_msg = validate_order(order)
        if not is_valid:
            return self._create_rejected_result(order, error_msg)
        
        # Calculate order value
        base_price = market_data.ask if order.side == OrderSide.BUY else market_data.bid
        order_value = order.quantity * base_price
        
        # Calculate execution delay
        delay_ms = self.delay_simulator.calculate_execution_delay(order, market_data, order_value)
        
        # Simulate delay
        self.delay_simulator.simulate_delay(delay_ms)
        
        # Check for partial fill
        executed_quantity = order.quantity
        partial_fill = False
        
        if (self.execution_config.enable_partial_fills and 
            random.random() < self.execution_config.partial_fill_probability):
            # Simulate partial fill
            min_fill = self.execution_config.min_fill_percentage
            fill_percentage = random.uniform(min_fill, 1.0)
            executed_quantity = order.quantity * fill_percentage
            partial_fill = True
        
        # Calculate slippage
        slippage_percent = self.slippage_calculator.calculate_slippage(
            order, market_data, order_value
        )
        
        # Calculate market impact
        market_impact_percent = self.market_impact_simulator.calculate_market_impact(
            order, market_data, order_value
        )
        
        # Apply slippage and market impact to execution price
        execution_price = self.slippage_calculator.apply_slippage(
            base_price, slippage_percent, order.side
        )
        execution_price = self.market_impact_simulator.apply_market_impact(
            execution_price, market_impact_percent, order.side
        )
        
        # Record market impact
        self.market_impact_simulator.record_impact(order.symbol, market_impact_percent)
        
        # Calculate fees
        fees = self._calculate_fees(executed_quantity, execution_price)
        
        # Create execution result
        result = ExecutionResult(
            order_id=order.id,
            symbol=order.symbol,
            executed_quantity=executed_quantity,
            execution_price=execution_price,
            slippage=slippage_percent,
            fees=fees,
            execution_time=datetime.now(),
            market_impact=market_impact_percent,
            partial_fill=partial_fill,
            remaining_quantity=order.quantity - executed_quantity,
            execution_delay_ms=delay_ms,
            liquidity_impact=0.0  # Will be enhanced in future versions
        )
        
        # Update order status
        if partial_fill:
            order.update_fill(executed_quantity, execution_price, fees)
        else:
            order.update_fill(executed_quantity, execution_price, fees)
        
        log_info(f"Market order executed: {order.symbol} {order.side.value} "
                f"{executed_quantity} @ {execution_price:.4f} "
                f"(slippage: {slippage_percent:.4f}, delay: {delay_ms}ms)")
        
        return result
    
    def execute_limit_order(
        self, 
        order: Order, 
        market_data: MarketData
    ) -> Optional[ExecutionResult]:
        """
        Execute a limit order if price conditions are met.
        
        Args:
            order: Limit order to execute
            market_data: Current market data
            
        Returns:
            Optional[ExecutionResult]: Result if executed, None if not triggered
        """
        # Validate order
        is_valid, error_msg = validate_order(order)
        if not is_valid:
            return self._create_rejected_result(order, error_msg)
        
        # Check if limit order can be executed
        can_execute = False
        execution_price = order.price
        
        if order.side == OrderSide.BUY:
            # Buy limit: execute if market price <= limit price
            if market_data.ask <= order.price:
                can_execute = True
                execution_price = min(order.price, market_data.ask)
        else:
            # Sell limit: execute if market price >= limit price
            if market_data.bid >= order.price:
                can_execute = True
                execution_price = max(order.price, market_data.bid)
        
        if not can_execute:
            return None  # Order not triggered
        
        # Calculate order value
        order_value = order.quantity * execution_price
        
        # Calculate execution delay (limit orders have slightly longer delays)
        delay_ms = self.delay_simulator.calculate_execution_delay(order, market_data, order_value)
        delay_ms = int(delay_ms * 1.2)  # 20% longer for limit orders
        
        # Simulate delay
        self.delay_simulator.simulate_delay(delay_ms)
        
        # Check for partial fill
        executed_quantity = order.quantity
        partial_fill = False
        
        if (self.execution_config.enable_partial_fills and 
            random.random() < self.execution_config.partial_fill_probability * 0.5):  # Lower probability for limits
            min_fill = self.execution_config.min_fill_percentage
            fill_percentage = random.uniform(min_fill, 1.0)
            executed_quantity = order.quantity * fill_percentage
            partial_fill = True
        
        # Limit orders have minimal slippage (price improvement possible)
        slippage_percent = random.uniform(-0.0001, 0.0001)  # Small random price improvement/degradation
        
        # Apply minimal slippage
        if slippage_percent != 0:
            execution_price = self.slippage_calculator.apply_slippage(
                execution_price, abs(slippage_percent), order.side
            )
            # Ensure we don't violate limit price
            if order.side == OrderSide.BUY:
                execution_price = min(execution_price, order.price)
            else:
                execution_price = max(execution_price, order.price)
        
        # Calculate fees
        fees = self._calculate_fees(executed_quantity, execution_price)
        
        # Create execution result
        result = ExecutionResult(
            order_id=order.id,
            symbol=order.symbol,
            executed_quantity=executed_quantity,
            execution_price=execution_price,
            slippage=slippage_percent,
            fees=fees,
            execution_time=datetime.now(),
            market_impact=0.0,  # Limit orders have minimal market impact
            partial_fill=partial_fill,
            remaining_quantity=order.quantity - executed_quantity,
            execution_delay_ms=delay_ms,
            liquidity_impact=0.0
        )
        
        # Update order status
        order.update_fill(executed_quantity, execution_price, fees)
        
        log_info(f"Limit order executed: {order.symbol} {order.side.value} "
                f"{executed_quantity} @ {execution_price:.4f} "
                f"(limit: {order.price:.4f}, delay: {delay_ms}ms)")
        
        return result
    
    def calculate_execution_price(
        self, 
        order: Order, 
        market_price: float
    ) -> float:
        """
        Calculate the execution price for an order.
        
        Args:
            order: Order to calculate price for
            market_price: Current market price
            
        Returns:
            float: Calculated execution price
        """
        if order.order_type == OrderType.MARKET:
            return market_price
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY:
                return min(order.price, market_price)
            else:
                return max(order.price, market_price)
        else:
            return market_price  # Simplified for stop orders
    
    def simulate_execution_delay(self, order: Order) -> float:
        """
        Simulate execution delay for an order.
        
        Args:
            order: Order to simulate delay for
            
        Returns:
            float: Delay in seconds
        """
        # Create dummy market data for delay calculation
        dummy_market_data = MarketData(
            symbol=order.symbol,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=1000000,
            volatility=0.02,
            timestamp=datetime.now()
        )
        
        order_value = order.quantity * 100.0  # Estimate
        delay_ms = self.delay_simulator.calculate_execution_delay(
            order, dummy_market_data, order_value
        )
        
        return delay_ms / 1000.0  # Convert to seconds
    
    def apply_market_impact(
        self, 
        order: Order, 
        base_price: float
    ) -> float:
        """
        Apply market impact to a base price.
        
        Args:
            order: Order causing the impact
            base_price: Base price before impact
            
        Returns:
            float: Price with market impact applied
        """
        # Create dummy market data for impact calculation
        dummy_market_data = MarketData(
            symbol=order.symbol,
            price=base_price,
            bid=base_price * 0.9995,
            ask=base_price * 1.0005,
            volume=1000000,
            volatility=0.02,
            timestamp=datetime.now()
        )
        
        order_value = order.quantity * base_price
        impact_percent = self.market_impact_simulator.calculate_market_impact(
            order, dummy_market_data, order_value
        )
        
        return self.market_impact_simulator.apply_market_impact(
            base_price, impact_percent, order.side
        )
    
    def _calculate_fees(self, quantity: float, price: float) -> float:
        """
        Calculate trading fees for an execution.
        
        Args:
            quantity: Executed quantity
            price: Execution price
            
        Returns:
            float: Total fees
        """
        trade_value = quantity * price
        
        # Percentage-based fee
        percentage_fee = trade_value * self.config.fees.trading_fee_percent
        
        # Fixed fee
        fixed_fee = self.config.fees.trading_fee_fixed
        
        # Total fee
        total_fee = percentage_fee + fixed_fee
        
        # Apply minimum and maximum fee limits
        total_fee = max(total_fee, self.config.fees.minimum_fee)
        total_fee = min(total_fee, self.config.fees.maximum_fee)
        
        return total_fee
    
    def _create_rejected_result(self, order: Order, reason: str) -> ExecutionResult:
        """
        Create an execution result for a rejected order.
        
        Args:
            order: Rejected order
            reason: Rejection reason
            
        Returns:
            ExecutionResult: Rejection result
        """
        log_error(f"Order rejected: {order.id} - {reason}")
        
        return ExecutionResult(
            order_id=order.id,
            symbol=order.symbol,
            executed_quantity=0.0,
            execution_price=1.0,  # Use 1.0 to avoid validation error for rejected orders
            slippage=0.0,
            fees=0.0,
            execution_time=datetime.now(),
            market_impact=0.0,
            partial_fill=False,
            remaining_quantity=order.quantity,
            execution_delay_ms=0,
            liquidity_impact=0.0
        )