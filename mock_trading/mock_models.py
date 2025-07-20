"""
Mock Trading Data Models

This module contains all the data models and structures used in the mock trading environment.
Includes enhanced data models for ExecutionResult, PortfolioSnapshot, PerformanceReport,
MockPosition, Order, and OrderResult classes with simulation-specific fields.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal
import uuid

try:
    from alpaca.trading.models import Position
    from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce
except ImportError:
    # Fallback for testing without alpaca-py
    class Position:
        pass
    
    class OrderSide:
        BUY = "BUY"
        SELL = "SELL"
    
    class OrderStatus:
        NEW = "NEW"
        ACCEPTED = "ACCEPTED"
        PARTIALLY_FILLED = "PARTIALLY_FILLED"
        FILLED = "FILLED"
        CANCELED = "CANCELED"
        REJECTED = "REJECTED"
        EXPIRED = "EXPIRED"
    
    class TimeInForce:
        GTC = "GTC"
        DAY = "DAY"


class OrderType(Enum):
    """Enum for different types of orders."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class ExecutionStatus(Enum):
    """Enum for execution status."""
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class ExecutionResult:
    """
    Data class for order execution results with simulation-specific fields.
    
    Attributes:
        order_id: Unique identifier for the order
        symbol: Trading symbol for the executed order
        executed_quantity: Actual quantity executed
        execution_price: Price at which the order was executed
        slippage: Slippage applied during execution
        fees: Trading fees charged
        execution_time: Timestamp when execution occurred
        market_impact: Market impact applied to the execution
        partial_fill: Whether this was a partial fill
        remaining_quantity: Remaining quantity if partially filled
        execution_delay_ms: Simulated execution delay in milliseconds
        liquidity_impact: Impact due to liquidity constraints
    """
    order_id: str
    symbol: str
    executed_quantity: float
    execution_price: float
    slippage: float
    fees: float
    execution_time: datetime
    market_impact: float = 0.0
    partial_fill: bool = False
    remaining_quantity: float = 0.0
    execution_delay_ms: int = 0
    liquidity_impact: float = 0.0
    
    def __post_init__(self):
        """Validate execution result data after initialization."""
        if self.executed_quantity == 0:
            raise ValueError("Executed quantity cannot be zero")
        if self.execution_price <= 0:
            raise ValueError("Execution price must be positive")
        if not (0 <= abs(self.slippage) <= 1):
            raise ValueError("Slippage must be between -1 and 1")
        if self.fees < 0:
            raise ValueError("Fees cannot be negative")


@dataclass
class PortfolioSnapshot:
    """
    Data class for portfolio state snapshots.
    
    Attributes:
        timestamp: When the snapshot was taken
        cash_balance: Available cash balance
        positions: Dictionary of symbol to position data
        total_value: Total portfolio value including cash and positions
        unrealized_pnl: Total unrealized profit/loss
        realized_pnl: Total realized profit/loss
        daily_pnl: Profit/loss for the current day
        total_fees_paid: Total fees paid to date
        position_count: Number of active positions
        largest_position_value: Value of the largest position
    """
    timestamp: datetime
    cash_balance: float
    positions: Dict[str, 'MockPosition']
    total_value: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float = 0.0
    total_fees_paid: float = 0.0
    position_count: int = 0
    largest_position_value: float = 0.0
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        self.position_count = len([pos for pos in self.positions.values() if pos.quantity != 0])
        if self.positions:
            position_values = [abs(pos.market_value) for pos in self.positions.values()]
            self.largest_position_value = max(position_values) if position_values else 0.0


@dataclass
class PerformanceReport:
    """
    Data class for comprehensive performance reporting.
    
    Attributes:
        start_date: Start date of the performance period
        end_date: End date of the performance period
        total_return: Total return percentage
        annualized_return: Annualized return percentage
        sharpe_ratio: Risk-adjusted return metric
        max_drawdown: Maximum drawdown percentage
        win_rate: Percentage of winning trades
        profit_factor: Ratio of gross profit to gross loss
        total_trades: Total number of trades executed
        avg_trade_return: Average return per trade
        best_trade: Best single trade return
        worst_trade: Worst single trade return
        avg_holding_period: Average holding period in days
        volatility: Portfolio volatility (standard deviation of returns)
        calmar_ratio: Return to max drawdown ratio
        sortino_ratio: Downside deviation adjusted return
        total_fees: Total fees paid during the period
        starting_capital: Initial capital amount
        ending_capital: Final capital amount
    """
    start_date: datetime
    end_date: datetime
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_return: float
    best_trade: float
    worst_trade: float
    avg_holding_period: float = 0.0
    volatility: float = 0.0
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    total_fees: float = 0.0
    starting_capital: float = 0.0
    ending_capital: float = 0.0
    
    def __post_init__(self):
        """Validate performance metrics after initialization."""
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")
        if self.total_trades < 0:
            raise ValueError("Total trades cannot be negative")
        if self.starting_capital < 0:
            raise ValueError("Starting capital cannot be negative")


@dataclass
class MockPosition:
    """
    Enhanced position class extending base Position with entry tracking and P&L calculations.
    
    Attributes:
        symbol: Trading symbol
        quantity: Current position quantity (positive for long, negative for short)
        market_value: Current market value of the position
        avg_entry_price: Volume-weighted average entry price
        unrealized_pl: Current unrealized profit/loss
        entry_prices: List of entry prices for multiple entries
        entry_quantities: List of quantities for each entry
        entry_timestamps: List of timestamps for each entry
        realized_pnl: Total realized profit/loss from this position
        fees_paid: Total fees paid for this position
        last_price: Last known market price
        cost_basis: Total cost basis of the position
        side: Position side (LONG or SHORT)
    """
    symbol: str
    quantity: float
    market_value: float = 0.0
    avg_entry_price: float = 0.0
    unrealized_pl: float = 0.0
    entry_prices: List[float] = field(default_factory=list)
    entry_quantities: List[float] = field(default_factory=list)
    entry_timestamps: List[datetime] = field(default_factory=list)
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    last_price: float = 0.0
    cost_basis: float = 0.0
    side: str = "LONG"
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if self.entry_prices and self.entry_quantities:
            self.cost_basis = sum(price * abs(qty) for price, qty in zip(self.entry_prices, self.entry_quantities))
            if self.quantity != 0:
                self.avg_entry_price = self.cost_basis / abs(self.quantity)
        elif self.cost_basis == 0.0 and self.avg_entry_price > 0 and self.quantity != 0:
            # If cost_basis not set but avg_entry_price is available, calculate it
            self.cost_basis = abs(self.quantity) * self.avg_entry_price
    
    def calculate_weighted_avg_price(self) -> float:
        """
        Calculate volume-weighted average entry price.
        
        Returns:
            float: Volume-weighted average price
        """
        if not self.entry_prices or not self.entry_quantities:
            return 0.0
        
        total_value = sum(price * qty for price, qty in zip(self.entry_prices, self.entry_quantities))
        total_quantity = sum(abs(qty) for qty in self.entry_quantities)
        
        return total_value / total_quantity if total_quantity > 0 else 0.0
    
    def add_trade(self, quantity: float, price: float, timestamp: datetime, fees: float = 0.0):
        """
        Add a new trade to the position.
        
        Args:
            quantity: Trade quantity (positive for buy, negative for sell)
            price: Trade price
            timestamp: Trade timestamp
            fees: Trading fees for this trade
        """
        if quantity == 0:
            return
        
        # Handle position opening or adding to existing position
        if (self.quantity >= 0 and quantity > 0) or (self.quantity <= 0 and quantity < 0):
            # Same direction trade - add to position
            self.entry_prices.append(price)
            self.entry_quantities.append(quantity)
            self.entry_timestamps.append(timestamp)
            self.quantity += quantity
            self.fees_paid += fees
        else:
            # Opposite direction trade - closing or reducing position
            remaining_quantity = quantity
            
            # Process FIFO (First In, First Out) for position closing
            while remaining_quantity != 0 and self.entry_quantities:
                if (remaining_quantity > 0 and self.entry_quantities[0] < 0) or \
                   (remaining_quantity < 0 and self.entry_quantities[0] > 0):
                    
                    entry_qty = self.entry_quantities[0]
                    entry_price = self.entry_prices[0]
                    
                    # Calculate how much of this entry to close
                    close_qty = min(abs(remaining_quantity), abs(entry_qty))
                    
                    # Calculate realized P&L for this portion
                    if entry_qty > 0:  # Closing long position
                        realized_pnl = close_qty * (price - entry_price)
                    else:  # Closing short position
                        realized_pnl = close_qty * (entry_price - price)
                    
                    self.realized_pnl += realized_pnl
                    
                    # Update entry quantities
                    if abs(entry_qty) <= close_qty:
                        # Fully close this entry
                        self.entry_quantities.pop(0)
                        self.entry_prices.pop(0)
                        self.entry_timestamps.pop(0)
                        remaining_quantity += entry_qty  # entry_qty is negative for opposite direction
                    else:
                        # Partially close this entry
                        self.entry_quantities[0] = entry_qty + (close_qty if entry_qty < 0 else -close_qty)
                        remaining_quantity = 0
                else:
                    break
            
            # Update total quantity
            self.quantity += quantity
            self.fees_paid += fees
            
            # If there's remaining quantity after closing, it's a new position in opposite direction
            if remaining_quantity != 0:
                self.entry_prices.append(price)
                self.entry_quantities.append(remaining_quantity)
                self.entry_timestamps.append(timestamp)
        
        # Recalculate average entry price and cost basis
        self.__post_init__()
    
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """
        Calculate current unrealized P&L.
        
        Args:
            current_price: Current market price
            
        Returns:
            float: Unrealized profit/loss
        """
        if self.quantity == 0:
            return 0.0
        
        self.last_price = current_price
        self.market_value = self.quantity * current_price
        
        if self.quantity > 0:  # Long position
            self.unrealized_pl = self.quantity * (current_price - self.avg_entry_price)
        else:  # Short position
            self.unrealized_pl = abs(self.quantity) * (self.avg_entry_price - current_price)
        
        return self.unrealized_pl
    
    def get_position_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of the position.
        
        Returns:
            Dict: Position summary with key metrics
        """
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "market_value": self.market_value,
            "avg_entry_price": self.avg_entry_price,
            "unrealized_pnl": self.unrealized_pl,
            "realized_pnl": self.realized_pnl,
            "fees_paid": self.fees_paid,
            "cost_basis": self.cost_basis,
            "last_price": self.last_price,
            "side": self.side,
            "entry_count": len(self.entry_prices),
            "pnl_percentage": (self.unrealized_pl / self.cost_basis * 100) if self.cost_basis > 0 else 0.0
        }


@dataclass
class Order:
    """
    Order class with simulation-specific fields.
    
    Attributes:
        id: Unique order identifier
        symbol: Trading symbol
        quantity: Order quantity
        side: Order side (BUY or SELL)
        order_type: Type of order (MARKET, LIMIT, etc.)
        status: Current order status
        price: Order price (for limit orders)
        time_in_force: Time in force specification
        created_at: Order creation timestamp
        updated_at: Last update timestamp
        filled_quantity: Quantity that has been filled
        remaining_quantity: Remaining quantity to be filled
        avg_fill_price: Average fill price for executed portions
        fees: Total fees for this order
        client_order_id: Client-specified order ID
        stop_price: Stop price for stop orders
        trail_amount: Trail amount for trailing stops
        extended_hours: Whether order can execute in extended hours
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    quantity: float = 0.0
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    status: OrderStatus = OrderStatus.NEW
    price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    avg_fill_price: float = 0.0
    fees: float = 0.0
    client_order_id: Optional[str] = None
    stop_price: Optional[float] = None
    trail_amount: Optional[float] = None
    extended_hours: bool = False
    
    def __post_init__(self):
        """Initialize derived fields after creation."""
        self.remaining_quantity = self.quantity - self.filled_quantity
        if not self.client_order_id:
            self.client_order_id = self.id
    
    def is_filled(self) -> bool:
        """Check if the order is completely filled."""
        return self.status == OrderStatus.FILLED
    
    def is_active(self) -> bool:
        """Check if the order is still active (can be executed)."""
        return self.status in [OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED]
    
    def can_cancel(self) -> bool:
        """Check if the order can be cancelled."""
        return self.status in [OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED]
    
    def update_fill(self, fill_quantity: float, fill_price: float, fees: float = 0.0):
        """
        Update order with a new fill.
        
        Args:
            fill_quantity: Quantity filled in this execution
            fill_price: Price of this fill
            fees: Fees for this fill
        """
        if fill_quantity <= 0:
            return
        
        # Update filled quantity
        old_filled = self.filled_quantity
        self.filled_quantity += fill_quantity
        self.remaining_quantity = self.quantity - self.filled_quantity
        
        # Update average fill price
        if old_filled == 0:
            self.avg_fill_price = fill_price
        else:
            total_value = (old_filled * self.avg_fill_price) + (fill_quantity * fill_price)
            self.avg_fill_price = total_value / self.filled_quantity
        
        # Update fees
        self.fees += fees
        
        # Update status
        if self.remaining_quantity <= 0.0001:  # Account for floating point precision
            self.status = OrderStatus.FILLED
            self.remaining_quantity = 0.0
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        self.updated_at = datetime.now()


@dataclass
class OrderResult:
    """
    Result of order submission with simulation-specific information.
    
    Attributes:
        order: The order that was submitted
        success: Whether the order submission was successful
        error_message: Error message if submission failed
        rejection_reason: Specific reason for rejection
        estimated_execution_time: Estimated time for execution
        estimated_slippage: Estimated slippage for the order
        liquidity_available: Available liquidity for the order
        market_impact_estimate: Estimated market impact
        submission_timestamp: When the order was submitted
    """
    order: Order
    success: bool
    error_message: Optional[str] = None
    rejection_reason: Optional[str] = None
    estimated_execution_time: Optional[datetime] = None
    estimated_slippage: float = 0.0
    liquidity_available: float = 0.0
    market_impact_estimate: float = 0.0
    submission_timestamp: datetime = field(default_factory=datetime.now)
    
    def is_successful(self) -> bool:
        """Check if the order submission was successful."""
        return self.success and self.error_message is None


# Data validation functions

def validate_numeric(value: Any, min_value: Optional[float] = None, max_value: Optional[float] = None) -> bool:
    """
    Validate that a value is numeric and within specified bounds.
    
    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        num_value = float(value)
        if min_value is not None and num_value < min_value:
            return False
        if max_value is not None and num_value > max_value:
            return False
        return True
    except (ValueError, TypeError):
        return False


def validate_symbol(symbol: str) -> bool:
    """
    Validate trading symbol format.
    
    Args:
        symbol: Trading symbol to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(symbol, str):
        return False
    
    # Remove common separators and check length
    clean_symbol = symbol.replace("/", "").replace("-", "").upper()
    
    # Basic validation: 3-12 characters, alphanumeric
    if not (3 <= len(clean_symbol) <= 12):
        return False
    
    return clean_symbol.isalnum()


def validate_order(order: Order) -> tuple[bool, Optional[str]]:
    """
    Validate an order for correctness.
    
    Args:
        order: Order to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not order:
        return False, "Order cannot be None"
    
    # Validate symbol
    if not validate_symbol(order.symbol):
        return False, f"Invalid symbol: {order.symbol}"
    
    # Validate quantity
    if not validate_numeric(order.quantity, min_value=0.0001):
        return False, f"Invalid quantity: {order.quantity}"
    
    # Validate price for limit orders
    if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
        if not order.price or not validate_numeric(order.price, min_value=0.01):
            return False, f"Invalid price for {order.order_type.value} order: {order.price}"
    
    # Validate stop price for stop orders
    if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
        if not order.stop_price or not validate_numeric(order.stop_price, min_value=0.01):
            return False, f"Invalid stop price for {order.order_type.value} order: {order.stop_price}"
    
    return True, None


def validate_execution_result(result: ExecutionResult) -> tuple[bool, Optional[str]]:
    """
    Validate an execution result for correctness.
    
    Args:
        result: ExecutionResult to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not result:
        return False, "ExecutionResult cannot be None"
    
    try:
        # Validate through __post_init__ which raises ValueError for invalid data
        ExecutionResult(
            order_id=result.order_id,
            symbol=result.symbol,
            executed_quantity=result.executed_quantity,
            execution_price=result.execution_price,
            slippage=result.slippage,
            fees=result.fees,
            execution_time=result.execution_time,
            market_impact=result.market_impact,
            partial_fill=result.partial_fill,
            remaining_quantity=result.remaining_quantity,
            execution_delay_ms=result.execution_delay_ms,
            liquidity_impact=result.liquidity_impact
        )
        return True, None
    except ValueError as e:
        return False, str(e)


def validate_portfolio_snapshot(snapshot: PortfolioSnapshot) -> tuple[bool, Optional[str]]:
    """
    Validate a portfolio snapshot for correctness.
    
    Args:
        snapshot: PortfolioSnapshot to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not snapshot:
        return False, "PortfolioSnapshot cannot be None"
    
    # Validate cash balance
    if not validate_numeric(snapshot.cash_balance, min_value=0.0):
        return False, f"Invalid cash balance: {snapshot.cash_balance}"
    
    # Validate total value
    if not validate_numeric(snapshot.total_value, min_value=0.0):
        return False, f"Invalid total value: {snapshot.total_value}"
    
    # Validate positions
    if not isinstance(snapshot.positions, dict):
        return False, "Positions must be a dictionary"
    
    for symbol, position in snapshot.positions.items():
        if not validate_symbol(symbol):
            return False, f"Invalid symbol in positions: {symbol}"
        
        if not isinstance(position, MockPosition):
            return False, f"Position for {symbol} must be MockPosition instance"
    
    return True, None


def validate_performance_report(report: PerformanceReport) -> tuple[bool, Optional[str]]:
    """
    Validate a performance report for correctness.
    
    Args:
        report: PerformanceReport to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not report:
        return False, "PerformanceReport cannot be None"
    
    try:
        # Validate through __post_init__ which raises ValueError for invalid data
        PerformanceReport(
            start_date=report.start_date,
            end_date=report.end_date,
            total_return=report.total_return,
            annualized_return=report.annualized_return,
            sharpe_ratio=report.sharpe_ratio,
            max_drawdown=report.max_drawdown,
            win_rate=report.win_rate,
            profit_factor=report.profit_factor,
            total_trades=report.total_trades,
            avg_trade_return=report.avg_trade_return,
            best_trade=report.best_trade,
            worst_trade=report.worst_trade,
            starting_capital=report.starting_capital
        )
        return True, None
    except ValueError as e:
        return False, str(e)