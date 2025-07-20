"""
Position and Portfolio Tracking System for Mock Trading Environment

This module implements comprehensive position tracking, portfolio management, and P&L calculations
for the mock trading environment. It provides multi-entry position tracking, real-time P&L
calculations, portfolio value computation, and position reconciliation functionality.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import logging

from mock_trading.mock_models import MockPosition, ExecutionResult, PortfolioSnapshot
from mock_trading.mock_config import MockTradingConfig


@dataclass
class PositionEntry:
    """Individual position entry for tracking multiple entries."""
    quantity: float
    price: float
    timestamp: datetime
    fees: float = 0.0
    entry_id: str = field(default_factory=lambda: str(int(time.time() * 1000000)))


@dataclass
class TradeRecord:
    """Record of a completed trade for P&L tracking."""
    symbol: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    realized_pnl: float
    fees: float
    holding_period: timedelta


class PnLCalculator:
    """
    Handles profit and loss calculations for positions and portfolio.
    Provides real-time and realized P&L calculations with accurate cost basis tracking.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize the P&L calculator.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def calculate_unrealized_pnl(self, position: MockPosition, current_price: float) -> float:
        """
        Calculate unrealized P&L for a position.
        
        Args:
            position: MockPosition object
            current_price: Current market price
            
        Returns:
            float: Unrealized profit/loss
        """
        if position.quantity == 0:
            return 0.0
            
        # Update position with current price
        position.last_price = current_price
        position.market_value = position.quantity * current_price
        
        # Calculate unrealized P&L
        if position.quantity > 0:  # Long position
            unrealized_pnl = position.quantity * (current_price - position.avg_entry_price)
        else:  # Short position
            unrealized_pnl = abs(position.quantity) * (position.avg_entry_price - current_price)
            
        position.unrealized_pl = unrealized_pnl
        return unrealized_pnl
    
    def calculate_realized_pnl(self, entry_price: float, exit_price: float, 
                             quantity: float, fees: float = 0.0) -> float:
        """
        Calculate realized P&L for a trade.
        
        Args:
            entry_price: Entry price of the trade
            exit_price: Exit price of the trade
            quantity: Quantity traded (positive for long, negative for short)
            fees: Total fees for the trade
            
        Returns:
            float: Realized profit/loss
        """
        if quantity == 0:
            return 0.0
            
        # Calculate gross P&L
        if quantity > 0:  # Long position closed
            gross_pnl = quantity * (exit_price - entry_price)
        else:  # Short position closed
            gross_pnl = abs(quantity) * (entry_price - exit_price)
            
        # Subtract fees
        net_pnl = gross_pnl - fees
        
        return net_pnl
    
    def calculate_position_pnl_percentage(self, position: MockPosition, current_price: float) -> float:
        """
        Calculate P&L percentage for a position.
        
        Args:
            position: MockPosition object
            current_price: Current market price
            
        Returns:
            float: P&L percentage
        """
        if position.cost_basis == 0:
            return 0.0
            
        unrealized_pnl = self.calculate_unrealized_pnl(position, current_price)
        return (unrealized_pnl / position.cost_basis) * 100
    
    def calculate_portfolio_pnl(self, positions: Dict[str, MockPosition], 
                              market_prices: Dict[str, float]) -> Tuple[float, float]:
        """
        Calculate total portfolio P&L.
        
        Args:
            positions: Dictionary of symbol to MockPosition
            market_prices: Dictionary of symbol to current price
            
        Returns:
            Tuple[float, float]: (total_unrealized_pnl, total_realized_pnl)
        """
        total_unrealized = 0.0
        total_realized = 0.0
        
        for symbol, position in positions.items():
            if symbol in market_prices:
                # Calculate unrealized P&L
                unrealized = self.calculate_unrealized_pnl(position, market_prices[symbol])
                total_unrealized += unrealized
                
            # Add realized P&L
            total_realized += position.realized_pnl
            
        return total_unrealized, total_realized


class PositionManager:
    """
    Manages positions and portfolio state for the mock trading environment.
    Provides multi-entry position tracking, portfolio value calculations, and reconciliation.
    """
    
    def __init__(self, config: MockTradingConfig, starting_cash: float = 10000.0):
        """
        Initialize the position manager.
        
        Args:
            config: Mock trading configuration
            starting_cash: Starting cash balance
        """
        self.config = config
        self.starting_cash = starting_cash
        self.cash_balance = starting_cash
        self.positions: Dict[str, MockPosition] = {}
        self.pnl_calculator = PnLCalculator(config)
        self.trade_history: List[TradeRecord] = []
        self.portfolio_history: List[PortfolioSnapshot] = []
        self.logger = logging.getLogger(__name__)
        
        # Position tracking
        self.last_reconciliation_time = datetime.now()
        self.reconciliation_interval = timedelta(minutes=5)
        
        # Performance tracking
        self.daily_pnl_history: Dict[str, float] = {}  # Date -> Daily P&L
        self.high_water_mark = starting_cash
        self.max_drawdown = 0.0
        
        self.logger.info(f"PositionManager initialized with ${starting_cash:,.2f} starting cash")
    
    def update_position(self, execution_result: ExecutionResult) -> bool:
        """
        Update position based on trade execution result.
        
        Args:
            execution_result: ExecutionResult from order execution
            
        Returns:
            bool: True if update was successful
        """
        try:
            symbol = execution_result.symbol
            quantity = execution_result.executed_quantity
            price = execution_result.execution_price
            fees = execution_result.fees
            timestamp = execution_result.execution_time
            
            # Get or create position
            if symbol not in self.positions:
                self.positions[symbol] = MockPosition(
                    symbol=symbol,
                    quantity=0.0,
                    market_value=0.0,
                    avg_entry_price=0.0,
                    unrealized_pl=0.0
                )
            
            position = self.positions[symbol]
            
            # Use the quantity as-is (positive for buy, negative for sell)
            trade_quantity = quantity
            
            # Update position with new trade
            position.add_trade(trade_quantity, price, timestamp, fees)
            
            # Update cash balance
            cash_impact = -(trade_quantity * price + fees)  # Negative for buy, positive for sell
            self.cash_balance += cash_impact
            
            # Log the position update
            self.logger.info(f"Updated position for {symbol}: "
                           f"Qty: {position.quantity}, "
                           f"Avg Price: ${position.avg_entry_price:.4f}, "
                           f"Cash: ${self.cash_balance:,.2f}")
            
            # Clean up zero positions
            if abs(position.quantity) < 0.0001:
                if symbol in self.positions:
                    del self.positions[symbol]
                    self.logger.info(f"Removed zero position for {symbol}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
            return False
    
    def get_position(self, symbol: str) -> Optional[MockPosition]:
        """
        Get current position for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            MockPosition if exists, None otherwise
        """
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, MockPosition]:
        """
        Get all current positions.
        
        Returns:
            Dictionary of symbol to MockPosition
        """
        return self.positions.copy()
    
    def calculate_portfolio_value(self, market_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value including cash and positions.
        
        Args:
            market_prices: Dictionary of symbol to current market price
            
        Returns:
            float: Total portfolio value
        """
        total_value = self.cash_balance
        
        for symbol, position in self.positions.items():
            if symbol in market_prices:
                position_value = position.quantity * market_prices[symbol]
                total_value += position_value
            else:
                # Use last known price if current price not available
                position_value = position.quantity * position.last_price
                total_value += position_value
                self.logger.warning(f"Using last known price for {symbol}: ${position.last_price:.4f}")
        
        return total_value
    
    def get_unrealized_pnl(self, market_prices: Dict[str, float]) -> float:
        """
        Calculate total unrealized P&L across all positions.
        
        Args:
            market_prices: Dictionary of symbol to current market price
            
        Returns:
            float: Total unrealized P&L
        """
        unrealized_pnl, _ = self.pnl_calculator.calculate_portfolio_pnl(self.positions, market_prices)
        return unrealized_pnl
    
    def get_realized_pnl(self) -> float:
        """
        Get total realized P&L across all positions.
        
        Returns:
            float: Total realized P&L
        """
        total_realized = sum(position.realized_pnl for position in self.positions.values())
        
        # Add P&L from completed trades (positions that were fully closed)
        total_realized += sum(trade.realized_pnl for trade in self.trade_history)
        
        return total_realized
    
    def get_position_summary(self, symbol: str, current_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Get comprehensive position summary.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price (optional)
            
        Returns:
            Dictionary with position details
        """
        position = self.get_position(symbol)
        
        if not position:
            return {
                "symbol": symbol,
                "quantity": 0.0,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "avg_entry_price": 0.0,
                "cost_basis": 0.0,
                "pnl_percentage": 0.0,
                "fees_paid": 0.0,
                "has_position": False,
                "entry_count": 0,
                "last_price": 0.0
            }
        
        # Use current price if provided, otherwise use last known price
        price_to_use = current_price if current_price is not None else position.last_price
        
        # Calculate current metrics
        if price_to_use > 0:
            unrealized_pnl = self.pnl_calculator.calculate_unrealized_pnl(position, price_to_use)
            pnl_percentage = self.pnl_calculator.calculate_position_pnl_percentage(position, price_to_use)
        else:
            unrealized_pnl = position.unrealized_pl
            pnl_percentage = 0.0
        
        return {
            "symbol": position.symbol,
            "quantity": position.quantity,
            "market_value": position.market_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": position.realized_pnl,
            "avg_entry_price": position.avg_entry_price,
            "cost_basis": position.cost_basis,
            "pnl_percentage": pnl_percentage,
            "fees_paid": position.fees_paid,
            "has_position": True,
            "entry_count": len(position.entry_prices),
            "last_price": position.last_price,
            "side": "LONG" if position.quantity > 0 else "SHORT" if position.quantity < 0 else "FLAT"
        }
    
    def create_portfolio_snapshot(self, market_prices: Dict[str, float]) -> PortfolioSnapshot:
        """
        Create a snapshot of the current portfolio state.
        
        Args:
            market_prices: Dictionary of symbol to current market price
            
        Returns:
            PortfolioSnapshot object
        """
        # Calculate portfolio metrics
        total_value = self.calculate_portfolio_value(market_prices)
        unrealized_pnl = self.get_unrealized_pnl(market_prices)
        realized_pnl = self.get_realized_pnl()
        
        # Calculate daily P&L
        today = datetime.now().date().isoformat()
        previous_value = self.daily_pnl_history.get(today, total_value)
        daily_pnl = total_value - previous_value
        
        # Update daily P&L history
        self.daily_pnl_history[today] = total_value
        
        # Calculate total fees paid
        total_fees = sum(position.fees_paid for position in self.positions.values())
        
        # Create snapshot
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            cash_balance=self.cash_balance,
            positions=self.positions.copy(),
            total_value=total_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            daily_pnl=daily_pnl,
            total_fees_paid=total_fees
        )
        
        # Add to history
        self.portfolio_history.append(snapshot)
        
        # Keep only last 1000 snapshots to manage memory
        if len(self.portfolio_history) > 1000:
            self.portfolio_history = self.portfolio_history[-1000:]
        
        # Update performance tracking
        self._update_performance_metrics(total_value)
        
        return snapshot
    
    def reconcile_positions(self, expected_positions: Dict[str, float]) -> Dict[str, Any]:
        """
        Reconcile positions against expected values and detect discrepancies.
        
        Args:
            expected_positions: Dictionary of symbol to expected quantity
            
        Returns:
            Dictionary with reconciliation results
        """
        reconciliation_results = {
            "timestamp": datetime.now(),
            "discrepancies": [],
            "total_discrepancies": 0,
            "cash_balance": self.cash_balance,
            "positions_checked": 0,
            "positions_accurate": 0
        }
        
        # Check each expected position
        for symbol, expected_qty in expected_positions.items():
            actual_position = self.get_position(symbol)
            actual_qty = actual_position.quantity if actual_position else 0.0
            
            reconciliation_results["positions_checked"] += 1
            
            # Check for discrepancies (tolerance of 0.0001)
            if abs(actual_qty - expected_qty) > 0.0001:
                discrepancy = {
                    "symbol": symbol,
                    "expected_quantity": expected_qty,
                    "actual_quantity": actual_qty,
                    "difference": actual_qty - expected_qty,
                    "percentage_diff": ((actual_qty - expected_qty) / expected_qty * 100) if expected_qty != 0 else 0
                }
                reconciliation_results["discrepancies"].append(discrepancy)
                reconciliation_results["total_discrepancies"] += 1
                
                self.logger.warning(f"Position discrepancy for {symbol}: "
                                  f"Expected {expected_qty}, Actual {actual_qty}")
            else:
                reconciliation_results["positions_accurate"] += 1
        
        # Check for unexpected positions
        for symbol, position in self.positions.items():
            if symbol not in expected_positions and abs(position.quantity) > 0.0001:
                discrepancy = {
                    "symbol": symbol,
                    "expected_quantity": 0.0,
                    "actual_quantity": position.quantity,
                    "difference": position.quantity,
                    "percentage_diff": 100.0  # 100% unexpected
                }
                reconciliation_results["discrepancies"].append(discrepancy)
                reconciliation_results["total_discrepancies"] += 1
                
                self.logger.warning(f"Unexpected position found: {symbol} with quantity {position.quantity}")
        
        # Update last reconciliation time
        self.last_reconciliation_time = datetime.now()
        
        # Log reconciliation summary
        if reconciliation_results["total_discrepancies"] == 0:
            self.logger.info(f"Position reconciliation successful: "
                           f"{reconciliation_results['positions_accurate']} positions accurate")
        else:
            self.logger.error(f"Position reconciliation found {reconciliation_results['total_discrepancies']} discrepancies")
        
        return reconciliation_results
    
    def check_position_consistency(self) -> Dict[str, Any]:
        """
        Check internal position consistency and data integrity.
        
        Returns:
            Dictionary with consistency check results
        """
        consistency_results = {
            "timestamp": datetime.now(),
            "issues": [],
            "positions_checked": 0,
            "issues_found": 0,
            "cash_balance_valid": True
        }
        
        # Check cash balance
        if self.cash_balance < 0:
            consistency_results["issues"].append({
                "type": "negative_cash",
                "description": f"Negative cash balance: ${self.cash_balance:,.2f}",
                "severity": "high"
            })
            consistency_results["cash_balance_valid"] = False
            consistency_results["issues_found"] += 1
        
        # Check each position
        for symbol, position in self.positions.items():
            consistency_results["positions_checked"] += 1
            
            # Check for zero quantity positions
            if abs(position.quantity) < 0.0001:
                consistency_results["issues"].append({
                    "type": "zero_position",
                    "symbol": symbol,
                    "description": f"Position with zero quantity should be removed",
                    "severity": "low"
                })
                consistency_results["issues_found"] += 1
            
            # Check cost basis consistency
            if position.quantity != 0 and position.cost_basis <= 0:
                consistency_results["issues"].append({
                    "type": "invalid_cost_basis",
                    "symbol": symbol,
                    "description": f"Position has invalid cost basis: {position.cost_basis}",
                    "severity": "medium"
                })
                consistency_results["issues_found"] += 1
            
            # Check entry data consistency
            if len(position.entry_prices) != len(position.entry_quantities):
                consistency_results["issues"].append({
                    "type": "entry_data_mismatch",
                    "symbol": symbol,
                    "description": f"Entry prices and quantities arrays have different lengths",
                    "severity": "high"
                })
                consistency_results["issues_found"] += 1
            
            # Check average entry price calculation
            if position.entry_prices and position.entry_quantities:
                calculated_avg = position.calculate_weighted_avg_price()
                if abs(calculated_avg - position.avg_entry_price) > 0.01:
                    consistency_results["issues"].append({
                        "type": "avg_price_mismatch",
                        "symbol": symbol,
                        "description": f"Average entry price mismatch: stored {position.avg_entry_price}, calculated {calculated_avg}",
                        "severity": "medium"
                    })
                    consistency_results["issues_found"] += 1
        
        # Log consistency check results
        if consistency_results["issues_found"] == 0:
            self.logger.info(f"Position consistency check passed: {consistency_results['positions_checked']} positions checked")
        else:
            self.logger.warning(f"Position consistency check found {consistency_results['issues_found']} issues")
        
        return consistency_results
    
    def _update_performance_metrics(self, current_portfolio_value: float) -> None:
        """
        Update performance tracking metrics.
        
        Args:
            current_portfolio_value: Current total portfolio value
        """
        # Update high water mark
        if current_portfolio_value > self.high_water_mark:
            self.high_water_mark = current_portfolio_value
        
        # Calculate current drawdown
        current_drawdown = (self.high_water_mark - current_portfolio_value) / self.high_water_mark
        
        # Update max drawdown
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive performance summary.
        
        Returns:
            Dictionary with performance metrics
        """
        current_value = self.cash_balance + sum(
            pos.market_value for pos in self.positions.values()
        )
        
        total_return = (current_value - self.starting_cash) / self.starting_cash
        total_realized_pnl = self.get_realized_pnl()
        total_unrealized_pnl = sum(pos.unrealized_pl for pos in self.positions.values())
        total_fees = sum(pos.fees_paid for pos in self.positions.values())
        
        return {
            "starting_cash": self.starting_cash,
            "current_cash": self.cash_balance,
            "current_portfolio_value": current_value,
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "realized_pnl": total_realized_pnl,
            "unrealized_pnl": total_unrealized_pnl,
            "total_pnl": total_realized_pnl + total_unrealized_pnl,
            "total_fees_paid": total_fees,
            "high_water_mark": self.high_water_mark,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown * 100,
            "active_positions": len(self.positions),
            "total_trades": len(self.trade_history),
            "portfolio_snapshots": len(self.portfolio_history)
        }
    
    def reset_portfolio(self, new_starting_cash: Optional[float] = None) -> None:
        """
        Reset portfolio to initial state.
        
        Args:
            new_starting_cash: New starting cash amount (optional)
        """
        if new_starting_cash is not None:
            self.starting_cash = new_starting_cash
        
        self.cash_balance = self.starting_cash
        self.positions.clear()
        self.trade_history.clear()
        self.portfolio_history.clear()
        self.daily_pnl_history.clear()
        self.high_water_mark = self.starting_cash
        self.max_drawdown = 0.0
        
        self.logger.info(f"Portfolio reset with ${self.starting_cash:,.2f} starting cash")