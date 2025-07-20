"""
Order Management and Validation System

This module implements order lifecycle management, validation, and order book simulation
for the mock trading environment. It provides comprehensive order processing with
realistic validation and execution coordination.
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import threading
from collections import defaultdict

from .mock_models import (
    Order, OrderResult, OrderType, OrderSide, OrderStatus, TimeInForce,
    MockPosition, ExecutionResult, validate_order, validate_symbol
)
from .mock_config import MockTradingConfig
from bot.utils import log_error, log_info, log_warning


class ValidationError(Exception):
    """Exception raised for order validation errors."""
    pass


class OrderRejectionReason(Enum):
    """Enumeration of order rejection reasons."""
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_PRICE = "INVALID_PRICE"
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    MARKET_CLOSED = "MARKET_CLOSED"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass
class Portfolio:
    """Portfolio state for order validation."""
    cash_balance: float
    positions: Dict[str, MockPosition]
    total_value: float
    
    def get_position_value(self, symbol: str) -> float:
        """Get the current value of a position."""
        position = self.positions.get(symbol)
        return abs(position.market_value) if position else 0.0
    
    def get_available_cash(self) -> float:
        """Get available cash for trading."""
        return max(0.0, self.cash_balance)


class OrderValidator:
    """
    Validates orders against available funds, position limits, and order constraints.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize order validator.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.max_position_size = config.max_position_size
        self.max_daily_loss = config.max_daily_loss
        self.starting_capital = config.starting_capital
        
        # Track daily trading activity
        self.daily_trades: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
    
    def validate_order(
        self, 
        order: Order, 
        portfolio: Portfolio,
        current_prices: Dict[str, float]
    ) -> Tuple[bool, Optional[str], Optional[OrderRejectionReason]]:
        """
        Comprehensive order validation.
        
        Args:
            order: Order to validate
            portfolio: Current portfolio state
            current_prices: Current market prices
            
        Returns:
            Tuple: (is_valid, error_message, rejection_reason)
        """
        try:
            # Reset daily tracking if needed
            self._reset_daily_tracking_if_needed()
            
            # Basic order validation
            is_valid, error_msg = validate_order(order)
            if not is_valid:
                return False, error_msg, OrderRejectionReason.SYSTEM_ERROR
            
            # Validate symbol first (before checking prices)
            if not self._validate_symbol(order.symbol):
                return False, f"Invalid or unsupported symbol: {order.symbol}", OrderRejectionReason.INVALID_SYMBOL
            
            # Check if we have current price data for the symbol
            if order.symbol not in current_prices or current_prices[order.symbol] <= 0:
                return False, f"No current price available for {order.symbol}", OrderRejectionReason.SYSTEM_ERROR
            
            # Validate quantity
            validation_result = self._validate_quantity(order)
            if not validation_result[0]:
                return validation_result[0], validation_result[1], OrderRejectionReason.INVALID_QUANTITY
            
            # Validate price for limit orders
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                validation_result = self._validate_price(order)
                if not validation_result[0]:
                    return validation_result[0], validation_result[1], OrderRejectionReason.INVALID_PRICE
            
            # Validate market hours (if enabled) - check early to avoid other validations
            if self.config.market.market_hours_enforcement:
                validation_result = self._validate_market_hours(order)
                if not validation_result[0]:
                    return validation_result[0], validation_result[1], OrderRejectionReason.MARKET_CLOSED
            
            # Validate funds
            validation_result = self._validate_funds(order, portfolio, current_prices)
            if not validation_result[0]:
                return validation_result[0], validation_result[1], OrderRejectionReason.INSUFFICIENT_FUNDS
            
            # Validate position limits
            validation_result = self._validate_position_limits(order, portfolio, current_prices)
            if not validation_result[0]:
                return validation_result[0], validation_result[1], OrderRejectionReason.POSITION_LIMIT_EXCEEDED
            
            # Validate daily loss limits
            validation_result = self._validate_daily_limits(order, portfolio, current_prices)
            if not validation_result[0]:
                return validation_result[0], validation_result[1], OrderRejectionReason.POSITION_LIMIT_EXCEEDED
            
            return True, None, None
            
        except Exception as e:
            log_error(f"Error validating order {order.id}: {e}")
            return False, f"Validation error: {str(e)}", OrderRejectionReason.SYSTEM_ERROR
    
    def _validate_symbol(self, symbol: str) -> bool:
        """Validate trading symbol."""
        if not isinstance(symbol, str) or len(symbol) < 3:
            return False
        
        # Allow common crypto symbols like BTCUSD, ETHUSD, etc.
        common_symbols = ["BTCUSD", "ETHUSD", "ADAUSD", "SOLUSD", "DOTUSD", "LINKUSD"]
        if symbol in common_symbols:
            return True
        
        # Use the general validation for other symbols
        return validate_symbol(symbol)
    
    def _validate_quantity(self, order: Order) -> Tuple[bool, Optional[str]]:
        """Validate order quantity."""
        if order.quantity <= 0:
            return False, f"Order quantity must be positive: {order.quantity}"
        
        # Check minimum quantity (0.0001 for fractional crypto)
        min_quantity = 0.0001
        if order.quantity < min_quantity:
            return False, f"Order quantity {order.quantity} below minimum {min_quantity}"
        
        # Check maximum quantity (reasonable upper bound)
        max_quantity = 1000000.0
        if order.quantity > max_quantity:
            return False, f"Order quantity {order.quantity} exceeds maximum {max_quantity}"
        
        return True, None
    
    def _validate_price(self, order: Order) -> Tuple[bool, Optional[str]]:
        """Validate order price for limit orders."""
        if not order.price:
            return False, "Price is required for limit orders"
        
        if order.price <= 0:
            return False, f"Order price must be positive: {order.price}"
        
        # Check reasonable price bounds
        min_price = 0.01
        max_price = 1000000.0
        
        if order.price < min_price:
            return False, f"Order price {order.price} below minimum {min_price}"
        
        if order.price > max_price:
            return False, f"Order price {order.price} exceeds maximum {max_price}"
        
        return True, None
    
    def _validate_funds(
        self, 
        order: Order, 
        portfolio: Portfolio,
        current_prices: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """Validate sufficient funds for the order."""
        if order.side == OrderSide.SELL:
            # For sell orders, check if we have enough position
            position = portfolio.positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                available_qty = position.quantity if position else 0.0
                return False, f"Insufficient position to sell: need {order.quantity}, have {available_qty}"
            return True, None
        
        # For buy orders, check cash balance
        current_price = current_prices.get(order.symbol, 0.0)
        if current_price <= 0:
            return False, f"No current price available for {order.symbol}"
        
        # Estimate order cost
        if order.order_type == OrderType.MARKET:
            estimated_price = current_price * 1.005  # Add 0.5% buffer for slippage
        elif order.order_type == OrderType.LIMIT:
            estimated_price = order.price
        else:
            estimated_price = current_price * 1.005
        
        order_cost = order.quantity * estimated_price
        
        # Add estimated fees
        estimated_fees = order_cost * self.config.fees.trading_fee_percent + self.config.fees.trading_fee_fixed
        total_cost = order_cost + estimated_fees
        
        available_cash = portfolio.get_available_cash()
        
        if total_cost > available_cash:
            return False, f"Insufficient funds: need ${total_cost:.2f}, have ${available_cash:.2f}"
        
        return True, None
    
    def _validate_position_limits(
        self, 
        order: Order, 
        portfolio: Portfolio,
        current_prices: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """Validate position size limits."""
        if order.side == OrderSide.SELL:
            return True, None  # Selling reduces position size
        
        # For buy orders, check position limits
        current_price = current_prices.get(order.symbol, 0.0)
        if current_price <= 0:
            return False, f"No current price available for {order.symbol}"
        
        # Calculate new position value after this order
        current_position_value = portfolio.get_position_value(order.symbol)
        order_value = order.quantity * current_price
        new_position_value = current_position_value + order_value
        
        if new_position_value > self.max_position_size:
            return False, (f"Position limit exceeded: new position value ${new_position_value:.2f} "
                          f"exceeds limit ${self.max_position_size:.2f}")
        
        # Check total portfolio concentration
        max_concentration = 0.5  # Maximum 50% of portfolio in single position
        max_position_value = portfolio.total_value * max_concentration
        
        if new_position_value > max_position_value:
            return False, (f"Portfolio concentration limit exceeded: position would be "
                          f"{new_position_value/portfolio.total_value*100:.1f}% of portfolio")
        
        return True, None
    
    def _validate_daily_limits(
        self, 
        order: Order, 
        portfolio: Portfolio,
        current_prices: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """Validate daily trading limits."""
        # Check daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            return False, f"Daily loss limit exceeded: current loss ${abs(self.daily_pnl):.2f}"
        
        # Check maximum number of trades per day
        max_daily_trades = 100  # Reasonable limit
        today_trades = len(self.daily_trades[datetime.now().date().isoformat()])
        
        if today_trades >= max_daily_trades:
            return False, f"Daily trade limit exceeded: {today_trades} trades today"
        
        return True, None
    
    def _validate_market_hours(self, order: Order) -> Tuple[bool, Optional[str]]:
        """Validate market hours restrictions."""
        current_time = datetime.now()
        hour = current_time.hour
        weekday = current_time.weekday()
        
        # Check if it's weekend (Saturday=5, Sunday=6)
        if weekday >= 5:
            if not self.config.market.extended_hours_trading:
                return False, "Market is closed on weekends"
        
        # Check market hours (9 AM to 4 PM EST, simplified)
        if not self.config.market.extended_hours_trading:
            if hour < 9 or hour >= 16:
                return False, f"Market is closed at {hour}:00. Trading hours: 9:00-16:00"
        
        return True, None
    
    def _reset_daily_tracking_if_needed(self):
        """Reset daily tracking if it's a new day."""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_trades.clear()
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
    
    def record_trade(self, order: Order, execution_result: ExecutionResult):
        """Record a trade for daily tracking."""
        today = datetime.now().date().isoformat()
        trade_record = {
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": execution_result.executed_quantity,
            "price": execution_result.execution_price,
            "fees": execution_result.fees,
            "timestamp": execution_result.execution_time
        }
        self.daily_trades[today].append(trade_record)


class OrderBook:
    """
    Maintains pending orders and execution queue for realistic order processing.
    """
    
    def __init__(self):
        """Initialize order book."""
        self.pending_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        self.execution_queue: List[str] = []
        self._lock = threading.Lock()
    
    def add_order(self, order: Order) -> bool:
        """
        Add an order to the order book.
        
        Args:
            order: Order to add
            
        Returns:
            bool: True if order was added successfully
        """
        with self._lock:
            if order.id in self.pending_orders:
                log_warning(f"Order {order.id} already exists in order book")
                return False
            
            self.pending_orders[order.id] = order
            
            # Add to execution queue for market orders
            if order.order_type == OrderType.MARKET:
                self.execution_queue.append(order.id)
            
            log_info(f"Added order to book: {order.id} {order.side.value} {order.quantity} {order.symbol}")
            return True
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """
        Remove an order from the order book.
        
        Args:
            order_id: ID of order to remove
            
        Returns:
            Order: Removed order if found, None otherwise
        """
        with self._lock:
            order = self.pending_orders.pop(order_id, None)
            
            if order:
                # Remove from execution queue if present
                if order_id in self.execution_queue:
                    self.execution_queue.remove(order_id)
                
                # Add to history
                self.order_history.append(order)
                
                # Keep history limited to last 1000 orders
                if len(self.order_history) > 1000:
                    self.order_history.pop(0)
                
                log_info(f"Removed order from book: {order_id}")
            
            return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        with self._lock:
            return self.pending_orders.get(order_id)
    
    def get_pending_orders(self, symbol: str = None) -> List[Order]:
        """
        Get pending orders, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            List[Order]: List of pending orders
        """
        with self._lock:
            orders = list(self.pending_orders.values())
            
            if symbol:
                orders = [order for order in orders if order.symbol == symbol]
            
            return orders
    
    def get_orders_for_execution(self) -> List[str]:
        """Get order IDs ready for execution."""
        with self._lock:
            return list(self.execution_queue)
    
    def mark_order_for_execution(self, order_id: str):
        """Mark an order as ready for execution."""
        with self._lock:
            if order_id in self.pending_orders and order_id not in self.execution_queue:
                self.execution_queue.append(order_id)
    
    def get_order_count(self) -> int:
        """Get total number of pending orders."""
        with self._lock:
            return len(self.pending_orders)
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all pending orders for a specific symbol."""
        with self._lock:
            return [order for order in self.pending_orders.values() if order.symbol == symbol]
    
    def get_orders_by_side(self, side: OrderSide) -> List[Order]:
        """Get all pending orders for a specific side."""
        with self._lock:
            return [order for order in self.pending_orders.values() if order.side == side]
    
    def cleanup_expired_orders(self) -> List[Order]:
        """
        Clean up expired orders based on time in force.
        
        Returns:
            List[Order]: List of expired orders that were removed
        """
        expired_orders = []
        current_time = datetime.now()
        
        with self._lock:
            orders_to_remove = []
            
            for order_id, order in self.pending_orders.items():
                should_expire = False
                
                # Check DAY orders after market close
                if order.time_in_force == TimeInForce.DAY:
                    # Simplified: expire DAY orders after 16:00
                    if current_time.hour >= 16:
                        should_expire = True
                
                # Check for orders older than 24 hours (safety cleanup)
                order_age = current_time - order.created_at
                if order_age > timedelta(hours=24):
                    should_expire = True
                
                if should_expire:
                    orders_to_remove.append(order_id)
                    order.status = OrderStatus.EXPIRED
                    expired_orders.append(order)
            
            # Remove expired orders
            for order_id in orders_to_remove:
                self.remove_order(order_id)
        
        if expired_orders:
            log_info(f"Expired {len(expired_orders)} orders")
        
        return expired_orders


class OrderManager:
    """
    Orchestrates order processing, validation, and lifecycle management.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize order manager.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.validator = OrderValidator(config)
        self.order_book = OrderBook()
        self.execution_callbacks: List[callable] = []
        
        # Track order statistics
        self.order_stats = {
            "total_submitted": 0,
            "total_executed": 0,
            "total_rejected": 0,
            "total_cancelled": 0
        }
    
    def submit_order(
        self, 
        order: Order, 
        portfolio: Portfolio,
        current_prices: Dict[str, float]
    ) -> OrderResult:
        """
        Submit an order for processing.
        
        Args:
            order: Order to submit
            portfolio: Current portfolio state
            current_prices: Current market prices
            
        Returns:
            OrderResult: Result of order submission
        """
        self.order_stats["total_submitted"] += 1
        
        try:
            # Validate the order
            is_valid, error_msg, rejection_reason = self.validator.validate_order(
                order, portfolio, current_prices
            )
            
            if not is_valid:
                # Create rejection result
                order.status = OrderStatus.REJECTED
                result = OrderResult(
                    order=order,
                    success=False,
                    error_message=error_msg,
                    rejection_reason=rejection_reason.value if rejection_reason else None,
                    submission_timestamp=datetime.now()
                )
                
                self.order_stats["total_rejected"] += 1
                log_warning(f"Order rejected: {order.id} - {error_msg}")
                return result
            
            # Add order to order book
            if not self.order_book.add_order(order):
                # Order already exists
                result = OrderResult(
                    order=order,
                    success=False,
                    error_message="Duplicate order ID",
                    rejection_reason=OrderRejectionReason.DUPLICATE_ORDER.value,
                    submission_timestamp=datetime.now()
                )
                self.order_stats["total_rejected"] += 1
                return result
            
            # Update order status
            order.status = OrderStatus.ACCEPTED
            order.updated_at = datetime.now()
            
            # Calculate estimates for the result
            current_price = current_prices.get(order.symbol, 0.0)
            estimated_execution_time = self._estimate_execution_time(order)
            estimated_slippage = self._estimate_slippage(order, current_price)
            
            # Create successful result
            result = OrderResult(
                order=order,
                success=True,
                estimated_execution_time=estimated_execution_time,
                estimated_slippage=estimated_slippage,
                liquidity_available=1000000.0,  # Simplified
                market_impact_estimate=0.0001,  # Simplified
                submission_timestamp=datetime.now()
            )
            
            log_info(f"Order submitted successfully: {order.id} {order.side.value} "
                    f"{order.quantity} {order.symbol}")
            
            return result
            
        except Exception as e:
            log_error(f"Error submitting order {order.id}: {e}")
            
            order.status = OrderStatus.REJECTED
            result = OrderResult(
                order=order,
                success=False,
                error_message=f"System error: {str(e)}",
                rejection_reason=OrderRejectionReason.SYSTEM_ERROR.value,
                submission_timestamp=datetime.now()
            )
            
            self.order_stats["total_rejected"] += 1
            return result
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            bool: True if order was cancelled successfully
        """
        try:
            order = self.order_book.get_order(order_id)
            
            if not order:
                log_warning(f"Cannot cancel order {order_id}: order not found")
                return False
            
            if not order.can_cancel():
                log_warning(f"Cannot cancel order {order_id}: order status is {order.status}")
                return False
            
            # Update order status
            order.status = OrderStatus.CANCELED
            order.updated_at = datetime.now()
            
            # Remove from order book
            self.order_book.remove_order(order_id)
            
            self.order_stats["total_cancelled"] += 1
            log_info(f"Order cancelled: {order_id}")
            
            return True
            
        except Exception as e:
            log_error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def modify_order(
        self, 
        order_id: str, 
        new_quantity: Optional[float] = None,
        new_price: Optional[float] = None
    ) -> bool:
        """
        Modify a pending order.
        
        Args:
            order_id: ID of order to modify
            new_quantity: New quantity (optional)
            new_price: New price (optional)
            
        Returns:
            bool: True if order was modified successfully
        """
        try:
            order = self.order_book.get_order(order_id)
            
            if not order:
                log_warning(f"Cannot modify order {order_id}: order not found")
                return False
            
            if not order.can_cancel():  # Use same logic as cancel
                log_warning(f"Cannot modify order {order_id}: order status is {order.status}")
                return False
            
            # Update order fields
            modified = False
            
            if new_quantity is not None and new_quantity != order.quantity:
                if new_quantity <= 0:
                    log_warning(f"Invalid new quantity for order {order_id}: {new_quantity}")
                    return False
                order.quantity = new_quantity
                order.remaining_quantity = new_quantity - order.filled_quantity
                modified = True
            
            if new_price is not None and new_price != order.price:
                if new_price <= 0:
                    log_warning(f"Invalid new price for order {order_id}: {new_price}")
                    return False
                order.price = new_price
                modified = True
            
            if modified:
                order.updated_at = datetime.now()
                log_info(f"Order modified: {order_id}")
                return True
            else:
                log_info(f"No changes made to order {order_id}")
                return True
                
        except Exception as e:
            log_error(f"Error modifying order {order_id}: {e}")
            return False
    
    def get_pending_orders(self, symbol: str = None) -> List[Order]:
        """Get pending orders, optionally filtered by symbol."""
        return self.order_book.get_pending_orders(symbol)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self.order_book.get_order(order_id)
    
    def process_market_update(self, symbol: str, price_data: Dict[str, float]):
        """
        Process market data update and check for limit order triggers.
        
        Args:
            symbol: Trading symbol
            price_data: Market price data (bid, ask, last, etc.)
        """
        try:
            # Get pending limit orders for this symbol
            pending_orders = self.order_book.get_orders_by_symbol(symbol)
            limit_orders = [order for order in pending_orders 
                           if order.order_type == OrderType.LIMIT and order.is_active()]
            
            current_price = price_data.get('last', price_data.get('price', 0.0))
            bid_price = price_data.get('bid', current_price * 0.9995)
            ask_price = price_data.get('ask', current_price * 1.0005)
            
            for order in limit_orders:
                should_trigger = False
                
                if order.side == OrderSide.BUY:
                    # Buy limit order triggers when ask price <= limit price
                    if ask_price <= order.price:
                        should_trigger = True
                else:
                    # Sell limit order triggers when bid price >= limit price
                    if bid_price >= order.price:
                        should_trigger = True
                
                if should_trigger:
                    self.order_book.mark_order_for_execution(order.id)
                    log_info(f"Limit order triggered: {order.id} at price {current_price}")
            
        except Exception as e:
            log_error(f"Error processing market update for {symbol}: {e}")
    
    def execute_pending_orders(self, current_prices: Dict[str, float]) -> List[str]:
        """
        Get orders ready for execution.
        
        Args:
            current_prices: Current market prices
            
        Returns:
            List[str]: List of order IDs ready for execution
        """
        try:
            # Clean up expired orders first
            self.order_book.cleanup_expired_orders()
            
            # Get orders ready for execution
            ready_orders = self.order_book.get_orders_for_execution()
            
            # Validate that orders are still executable
            executable_orders = []
            
            for order_id in ready_orders:
                order = self.order_book.get_order(order_id)
                if order and order.is_active():
                    executable_orders.append(order_id)
                else:
                    # Remove from execution queue if order is no longer active
                    if order_id in self.order_book.execution_queue:
                        self.order_book.execution_queue.remove(order_id)
            
            return executable_orders
            
        except Exception as e:
            log_error(f"Error getting pending orders for execution: {e}")
            return []
    
    def record_execution(self, order_id: str, execution_result: ExecutionResult):
        """
        Record order execution and update statistics.
        
        Args:
            order_id: ID of executed order
            execution_result: Execution result
        """
        try:
            order = self.order_book.get_order(order_id)
            
            if order:
                # Record trade for daily tracking
                self.validator.record_trade(order, execution_result)
                
                # Update order with execution details
                order.update_fill(
                    execution_result.executed_quantity,
                    execution_result.execution_price,
                    execution_result.fees
                )
                
                # Remove from order book if fully filled
                if order.is_filled():
                    self.order_book.remove_order(order_id)
                
                self.order_stats["total_executed"] += 1
                
                # Notify execution callbacks
                for callback in self.execution_callbacks:
                    try:
                        callback(order, execution_result)
                    except Exception as e:
                        log_error(f"Error in execution callback: {e}")
            
        except Exception as e:
            log_error(f"Error recording execution for order {order_id}: {e}")
    
    def add_execution_callback(self, callback: callable):
        """Add a callback to be called when orders are executed."""
        self.execution_callbacks.append(callback)
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """Get order processing statistics."""
        return {
            **self.order_stats,
            "pending_orders": self.order_book.get_order_count(),
            "execution_queue_size": len(self.order_book.execution_queue)
        }
    
    def _estimate_execution_time(self, order: Order) -> datetime:
        """Estimate when an order will be executed."""
        base_delay = 0.5 if order.order_type == OrderType.MARKET else 2.0
        return datetime.now() + timedelta(seconds=base_delay)
    
    def _estimate_slippage(self, order: Order, current_price: float) -> float:
        """Estimate slippage for an order."""
        if order.order_type == OrderType.MARKET:
            return 0.0001  # 0.01% estimated slippage for market orders
        else:
            return 0.0  # No slippage for limit orders