"""
Unit tests for mock trading data models.

Tests all data model classes including ExecutionResult, PortfolioSnapshot,
PerformanceReport, MockPosition, Order, and OrderResult, as well as
validation functions.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce

from mock_trading.mock_models import (
    ExecutionResult, PortfolioSnapshot, PerformanceReport, MockPosition,
    Order, OrderResult, OrderType, ExecutionStatus,
    validate_numeric, validate_symbol, validate_order,
    validate_execution_result, validate_portfolio_snapshot,
    validate_performance_report
)


class TestExecutionResult:
    """Test cases for ExecutionResult data model."""
    
    def test_valid_execution_result_creation(self):
        """Test creating a valid ExecutionResult."""
        result = ExecutionResult(
            order_id="test-order-123",
            executed_quantity=100.0,
            execution_price=50.0,
            slippage=0.001,
            fees=0.5,
            execution_time=datetime.now()
        )
        
        assert result.order_id == "test-order-123"
        assert result.executed_quantity == 100.0
        assert result.execution_price == 50.0
        assert result.slippage == 0.001
        assert result.fees == 0.5
        assert result.market_impact == 0.0  # default value
        assert result.partial_fill is False  # default value
    
    def test_execution_result_with_all_fields(self):
        """Test creating ExecutionResult with all fields."""
        execution_time = datetime.now()
        result = ExecutionResult(
            order_id="test-order-456",
            executed_quantity=50.0,
            execution_price=25.0,
            slippage=0.002,
            fees=1.0,
            execution_time=execution_time,
            market_impact=0.001,
            partial_fill=True,
            remaining_quantity=50.0,
            execution_delay_ms=250,
            liquidity_impact=0.0005
        )
        
        assert result.order_id == "test-order-456"
        assert result.executed_quantity == 50.0
        assert result.execution_price == 25.0
        assert result.slippage == 0.002
        assert result.fees == 1.0
        assert result.execution_time == execution_time
        assert result.market_impact == 0.001
        assert result.partial_fill is True
        assert result.remaining_quantity == 50.0
        assert result.execution_delay_ms == 250
        assert result.liquidity_impact == 0.0005
    
    def test_execution_result_validation_negative_quantity(self):
        """Test ExecutionResult validation with negative quantity."""
        with pytest.raises(ValueError, match="Executed quantity cannot be negative"):
            ExecutionResult(
                order_id="test",
                executed_quantity=-10.0,
                execution_price=50.0,
                slippage=0.001,
                fees=0.5,
                execution_time=datetime.now()
            )
    
    def test_execution_result_validation_zero_price(self):
        """Test ExecutionResult validation with zero price."""
        with pytest.raises(ValueError, match="Execution price must be positive"):
            ExecutionResult(
                order_id="test",
                executed_quantity=10.0,
                execution_price=0.0,
                slippage=0.001,
                fees=0.5,
                execution_time=datetime.now()
            )
    
    def test_execution_result_validation_invalid_slippage(self):
        """Test ExecutionResult validation with invalid slippage."""
        with pytest.raises(ValueError, match="Slippage must be between -1 and 1"):
            ExecutionResult(
                order_id="test",
                executed_quantity=10.0,
                execution_price=50.0,
                slippage=1.5,
                fees=0.5,
                execution_time=datetime.now()
            )
    
    def test_execution_result_validation_negative_fees(self):
        """Test ExecutionResult validation with negative fees."""
        with pytest.raises(ValueError, match="Fees cannot be negative"):
            ExecutionResult(
                order_id="test",
                executed_quantity=10.0,
                execution_price=50.0,
                slippage=0.001,
                fees=-0.5,
                execution_time=datetime.now()
            )


class TestPortfolioSnapshot:
    """Test cases for PortfolioSnapshot data model."""
    
    def test_valid_portfolio_snapshot_creation(self):
        """Test creating a valid PortfolioSnapshot."""
        timestamp = datetime.now()
        positions = {
            "BTCUSD": MockPosition("BTCUSD", 1.0, 50000.0, 49000.0, 1000.0),
            "ETHUSD": MockPosition("ETHUSD", 10.0, 30000.0, 2900.0, 1000.0)
        }
        
        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            cash_balance=10000.0,
            positions=positions,
            total_value=90000.0,
            unrealized_pnl=2000.0,
            realized_pnl=500.0
        )
        
        assert snapshot.timestamp == timestamp
        assert snapshot.cash_balance == 10000.0
        assert len(snapshot.positions) == 2
        assert snapshot.total_value == 90000.0
        assert snapshot.unrealized_pnl == 2000.0
        assert snapshot.realized_pnl == 500.0
        assert snapshot.position_count == 2  # calculated in __post_init__
        assert snapshot.largest_position_value == 50000.0  # calculated in __post_init__
    
    def test_portfolio_snapshot_with_empty_positions(self):
        """Test PortfolioSnapshot with no positions."""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            cash_balance=10000.0,
            positions={},
            total_value=10000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0
        )
        
        assert snapshot.position_count == 0
        assert snapshot.largest_position_value == 0.0
    
    def test_portfolio_snapshot_with_zero_quantity_positions(self):
        """Test PortfolioSnapshot with zero quantity positions."""
        positions = {
            "BTCUSD": MockPosition("BTCUSD", 0.0, 0.0, 49000.0, 0.0),
            "ETHUSD": MockPosition("ETHUSD", 10.0, 30000.0, 2900.0, 1000.0)
        }
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            cash_balance=10000.0,
            positions=positions,
            total_value=40000.0,
            unrealized_pnl=1000.0,
            realized_pnl=500.0
        )
        
        assert snapshot.position_count == 1  # Only counts non-zero positions


class TestPerformanceReport:
    """Test cases for PerformanceReport data model."""
    
    def test_valid_performance_report_creation(self):
        """Test creating a valid PerformanceReport."""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        report = PerformanceReport(
            start_date=start_date,
            end_date=end_date,
            total_return=0.15,
            annualized_return=0.20,
            sharpe_ratio=1.5,
            max_drawdown=0.05,
            win_rate=0.65,
            profit_factor=1.8,
            total_trades=50,
            avg_trade_return=0.003,
            best_trade=0.08,
            worst_trade=-0.04,
            starting_capital=10000.0
        )
        
        assert report.start_date == start_date
        assert report.end_date == end_date
        assert report.total_return == 0.15
        assert report.sharpe_ratio == 1.5
        assert report.total_trades == 50
        assert report.starting_capital == 10000.0
    
    def test_performance_report_validation_invalid_dates(self):
        """Test PerformanceReport validation with invalid dates."""
        start_date = datetime.now()
        end_date = datetime.now() - timedelta(days=1)  # End before start
        
        with pytest.raises(ValueError, match="Start date must be before end date"):
            PerformanceReport(
                start_date=start_date,
                end_date=end_date,
                total_return=0.15,
                annualized_return=0.20,
                sharpe_ratio=1.5,
                max_drawdown=0.05,
                win_rate=0.65,
                profit_factor=1.8,
                total_trades=50,
                avg_trade_return=0.003,
                best_trade=0.08,
                worst_trade=-0.04,
                starting_capital=10000.0
            )
    
    def test_performance_report_validation_negative_trades(self):
        """Test PerformanceReport validation with negative trades."""
        with pytest.raises(ValueError, match="Total trades cannot be negative"):
            PerformanceReport(
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
                total_return=0.15,
                annualized_return=0.20,
                sharpe_ratio=1.5,
                max_drawdown=0.05,
                win_rate=0.65,
                profit_factor=1.8,
                total_trades=-5,
                avg_trade_return=0.003,
                best_trade=0.08,
                worst_trade=-0.04,
                starting_capital=10000.0
            )
    
    def test_performance_report_validation_zero_capital(self):
        """Test PerformanceReport validation with zero starting capital."""
        with pytest.raises(ValueError, match="Starting capital must be positive"):
            PerformanceReport(
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
                total_return=0.15,
                annualized_return=0.20,
                sharpe_ratio=1.5,
                max_drawdown=0.05,
                win_rate=0.65,
                profit_factor=1.8,
                total_trades=50,
                avg_trade_return=0.003,
                best_trade=0.08,
                worst_trade=-0.04,
                starting_capital=0.0
            )


class TestMockPosition:
    """Test cases for MockPosition data model."""
    
    def test_mock_position_creation(self):
        """Test creating a MockPosition."""
        position = MockPosition(
            symbol="BTCUSD",
            quantity=1.0,
            market_value=50000.0,
            avg_entry_price=49000.0,
            unrealized_pl=1000.0
        )
        
        assert position.symbol == "BTCUSD"
        assert position.quantity == 1.0
        assert position.market_value == 50000.0
        assert position.avg_entry_price == 49000.0
        assert position.unrealized_pl == 1000.0
        assert position.realized_pnl == 0.0
        assert position.fees_paid == 0.0
        assert position.side == "LONG"
    
    def test_mock_position_with_entries(self):
        """Test MockPosition with entry tracking."""
        entry_time = datetime.now()
        position = MockPosition(
            symbol="ETHUSD",
            quantity=10.0,
            entry_prices=[3000.0, 2900.0],
            entry_quantities=[5.0, 5.0],
            entry_timestamps=[entry_time, entry_time + timedelta(minutes=5)]
        )
        
        assert len(position.entry_prices) == 2
        assert len(position.entry_quantities) == 2
        assert len(position.entry_timestamps) == 2
        assert position.cost_basis == 29500.0  # (3000*5 + 2900*5)
        assert position.avg_entry_price == 2950.0  # 29500/10
    
    def test_calculate_weighted_avg_price(self):
        """Test weighted average price calculation."""
        position = MockPosition(
            symbol="BTCUSD",
            quantity=3.0,
            entry_prices=[50000.0, 48000.0, 52000.0],
            entry_quantities=[1.0, 1.0, 1.0]
        )
        
        avg_price = position.calculate_weighted_avg_price()
        expected_avg = (50000.0 + 48000.0 + 52000.0) / 3
        assert avg_price == expected_avg
    
    def test_add_trade_same_direction(self):
        """Test adding trade in same direction."""
        position = MockPosition("BTCUSD", 1.0)
        position.entry_prices = [50000.0]
        position.entry_quantities = [1.0]
        position.entry_timestamps = [datetime.now()]
        
        # Add another buy trade
        position.add_trade(0.5, 51000.0, datetime.now(), 5.0)
        
        assert position.quantity == 1.5
        assert len(position.entry_prices) == 2
        assert position.entry_prices[1] == 51000.0
        assert position.entry_quantities[1] == 0.5
        assert position.fees_paid == 5.0
    
    def test_add_trade_opposite_direction_partial_close(self):
        """Test adding trade in opposite direction (partial close)."""
        entry_time = datetime.now()
        position = MockPosition("BTCUSD", 2.0)
        position.entry_prices = [50000.0]
        position.entry_quantities = [2.0]
        position.entry_timestamps = [entry_time]
        
        # Sell 1.0 (partial close)
        position.add_trade(-1.0, 52000.0, datetime.now(), 5.0)
        
        assert position.quantity == 1.0
        assert position.realized_pnl == 2000.0  # 1.0 * (52000 - 50000)
        assert position.fees_paid == 5.0
        assert len(position.entry_quantities) == 1
        assert position.entry_quantities[0] == 1.0  # Remaining quantity
    
    def test_add_trade_opposite_direction_full_close(self):
        """Test adding trade in opposite direction (full close)."""
        entry_time = datetime.now()
        position = MockPosition("BTCUSD", 1.0)
        position.entry_prices = [50000.0]
        position.entry_quantities = [1.0]
        position.entry_timestamps = [entry_time]
        
        # Sell all (full close)
        position.add_trade(-1.0, 52000.0, datetime.now(), 5.0)
        
        assert position.quantity == 0.0
        assert position.realized_pnl == 2000.0  # 1.0 * (52000 - 50000)
        assert position.fees_paid == 5.0
        assert len(position.entry_quantities) == 0
    
    def test_calculate_unrealized_pnl_long(self):
        """Test unrealized P&L calculation for long position."""
        position = MockPosition("BTCUSD", 1.0, avg_entry_price=50000.0)
        
        unrealized_pnl = position.calculate_unrealized_pnl(52000.0)
        
        assert unrealized_pnl == 2000.0
        assert position.unrealized_pl == 2000.0
        assert position.market_value == 52000.0
        assert position.last_price == 52000.0
    
    def test_calculate_unrealized_pnl_short(self):
        """Test unrealized P&L calculation for short position."""
        position = MockPosition("BTCUSD", -1.0, avg_entry_price=50000.0)
        
        unrealized_pnl = position.calculate_unrealized_pnl(48000.0)
        
        assert unrealized_pnl == 2000.0  # Short profits when price goes down
        assert position.unrealized_pl == 2000.0
        assert position.market_value == -48000.0
    
    def test_get_position_summary(self):
        """Test position summary generation."""
        position = MockPosition(
            symbol="ETHUSD",
            quantity=10.0,
            market_value=30000.0,
            avg_entry_price=2900.0,
            unrealized_pl=1000.0,
            realized_pnl=500.0,
            fees_paid=25.0,
            cost_basis=29000.0,
            last_price=3000.0
        )
        
        summary = position.get_position_summary()
        
        assert summary["symbol"] == "ETHUSD"
        assert summary["quantity"] == 10.0
        assert summary["market_value"] == 30000.0
        assert summary["unrealized_pnl"] == 1000.0
        assert summary["realized_pnl"] == 500.0
        assert summary["fees_paid"] == 25.0
        assert summary["pnl_percentage"] == pytest.approx(3.45, rel=1e-2)  # 1000/29000*100


class TestOrder:
    """Test cases for Order data model."""
    
    def test_order_creation_defaults(self):
        """Test creating Order with default values."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        
        assert order.symbol == "BTCUSD"
        assert order.quantity == 1.0
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.NEW
        assert order.time_in_force == TimeInForce.GTC
        assert order.filled_quantity == 0.0
        assert order.remaining_quantity == 1.0
        assert order.client_order_id == order.id
    
    def test_order_creation_with_all_fields(self):
        """Test creating Order with all fields specified."""
        order = Order(
            symbol="ETHUSD",
            quantity=10.0,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=3000.0,
            time_in_force=TimeInForce.DAY,
            client_order_id="custom-123"
        )
        
        assert order.symbol == "ETHUSD"
        assert order.quantity == 10.0
        assert order.side == OrderSide.SELL
        assert order.order_type == OrderType.LIMIT
        assert order.price == 3000.0
        assert order.time_in_force == TimeInForce.DAY
        assert order.client_order_id == "custom-123"
    
    def test_order_is_filled(self):
        """Test order filled status check."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        assert not order.is_filled()
        
        order.status = OrderStatus.FILLED
        assert order.is_filled()
    
    def test_order_is_active(self):
        """Test order active status check."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        assert order.is_active()  # NEW status
        
        order.status = OrderStatus.ACCEPTED
        assert order.is_active()
        
        order.status = OrderStatus.PARTIALLY_FILLED
        assert order.is_active()
        
        order.status = OrderStatus.FILLED
        assert not order.is_active()
        
        order.status = OrderStatus.CANCELED
        assert not order.is_active()
    
    def test_order_can_cancel(self):
        """Test order cancellation eligibility."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        assert order.can_cancel()  # NEW status
        
        order.status = OrderStatus.FILLED
        assert not order.can_cancel()
        
        order.status = OrderStatus.CANCELED
        assert not order.can_cancel()
    
    def test_order_update_fill(self):
        """Test updating order with fill information."""
        order = Order(symbol="BTCUSD", quantity=2.0)
        
        # First partial fill
        order.update_fill(1.0, 50000.0, 5.0)
        
        assert order.filled_quantity == 1.0
        assert order.remaining_quantity == 1.0
        assert order.avg_fill_price == 50000.0
        assert order.fees == 5.0
        assert order.status == OrderStatus.PARTIALLY_FILLED
        
        # Second fill completes the order
        order.update_fill(1.0, 51000.0, 5.0)
        
        assert order.filled_quantity == 2.0
        assert order.remaining_quantity == 0.0
        assert order.avg_fill_price == 50500.0  # (50000 + 51000) / 2
        assert order.fees == 10.0
        assert order.status == OrderStatus.FILLED
    
    def test_order_update_fill_zero_quantity(self):
        """Test updating order with zero fill quantity."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        original_filled = order.filled_quantity
        
        order.update_fill(0.0, 50000.0, 5.0)
        
        assert order.filled_quantity == original_filled  # No change


class TestOrderResult:
    """Test cases for OrderResult data model."""
    
    def test_order_result_success(self):
        """Test successful OrderResult."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        result = OrderResult(order=order, success=True)
        
        assert result.order == order
        assert result.success is True
        assert result.error_message is None
        assert result.is_successful() is True
    
    def test_order_result_failure(self):
        """Test failed OrderResult."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        result = OrderResult(
            order=order,
            success=False,
            error_message="Insufficient funds",
            rejection_reason="INSUFFICIENT_BUYING_POWER"
        )
        
        assert result.order == order
        assert result.success is False
        assert result.error_message == "Insufficient funds"
        assert result.rejection_reason == "INSUFFICIENT_BUYING_POWER"
        assert result.is_successful() is False


class TestValidationFunctions:
    """Test cases for validation functions."""
    
    def test_validate_numeric_valid(self):
        """Test validate_numeric with valid values."""
        assert validate_numeric(10.5) is True
        assert validate_numeric("15.2") is True
        assert validate_numeric(0) is True
        assert validate_numeric(-5.5) is True
    
    def test_validate_numeric_with_bounds(self):
        """Test validate_numeric with bounds."""
        assert validate_numeric(10.0, min_value=5.0, max_value=15.0) is True
        assert validate_numeric(4.0, min_value=5.0) is False
        assert validate_numeric(16.0, max_value=15.0) is False
    
    def test_validate_numeric_invalid(self):
        """Test validate_numeric with invalid values."""
        assert validate_numeric("abc") is False
        assert validate_numeric(None) is False
        assert validate_numeric([1, 2, 3]) is False
    
    def test_validate_symbol_valid(self):
        """Test validate_symbol with valid symbols."""
        assert validate_symbol("BTCUSD") is True
        assert validate_symbol("BTC/USD") is True
        assert validate_symbol("ETH-USD") is True
        assert validate_symbol("AAPL") is True
    
    def test_validate_symbol_invalid(self):
        """Test validate_symbol with invalid symbols."""
        assert validate_symbol("") is False
        assert validate_symbol("AB") is False  # Too short
        assert validate_symbol("VERYLONGSYMBOLNAME") is False  # Too long
        assert validate_symbol("BTC$USD") is False  # Invalid character
        assert validate_symbol(123) is False  # Not a string
    
    def test_validate_order_valid(self):
        """Test validate_order with valid order."""
        order = Order(symbol="BTCUSD", quantity=1.0)
        is_valid, error = validate_order(order)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_order_invalid_symbol(self):
        """Test validate_order with invalid symbol."""
        order = Order(symbol="", quantity=1.0)
        is_valid, error = validate_order(order)
        
        assert is_valid is False
        assert "Invalid symbol" in error
    
    def test_validate_order_invalid_quantity(self):
        """Test validate_order with invalid quantity."""
        order = Order(symbol="BTCUSD", quantity=0.0)
        is_valid, error = validate_order(order)
        
        assert is_valid is False
        assert "Invalid quantity" in error
    
    def test_validate_order_limit_without_price(self):
        """Test validate_order for limit order without price."""
        order = Order(symbol="BTCUSD", quantity=1.0, order_type=OrderType.LIMIT)
        is_valid, error = validate_order(order)
        
        assert is_valid is False
        assert "Invalid price for LIMIT order" in error
    
    def test_validate_execution_result_valid(self):
        """Test validate_execution_result with valid result."""
        result = ExecutionResult(
            order_id="test",
            executed_quantity=1.0,
            execution_price=50000.0,
            slippage=0.001,
            fees=5.0,
            execution_time=datetime.now()
        )
        
        is_valid, error = validate_execution_result(result)
        assert is_valid is True
        assert error is None
    
    def test_validate_execution_result_invalid(self):
        """Test validate_execution_result with invalid result."""
        # Create a result that will fail validation by bypassing __post_init__
        result = object.__new__(ExecutionResult)
        result.order_id = "test"
        result.executed_quantity = -1.0
        result.execution_price = 50000.0
        result.slippage = 0.001
        result.fees = 5.0
        result.execution_time = datetime.now()
        result.market_impact = 0.0
        result.partial_fill = False
        result.remaining_quantity = 0.0
        result.execution_delay_ms = 0
        result.liquidity_impact = 0.0
        
        is_valid, error = validate_execution_result(result)
        assert is_valid is False
        assert "Executed quantity cannot be negative" in error
    
    def test_validate_portfolio_snapshot_valid(self):
        """Test validate_portfolio_snapshot with valid snapshot."""
        positions = {"BTCUSD": MockPosition("BTCUSD", 1.0)}
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            cash_balance=10000.0,
            positions=positions,
            total_value=60000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0
        )
        
        is_valid, error = validate_portfolio_snapshot(snapshot)
        assert is_valid is True
        assert error is None
    
    def test_validate_portfolio_snapshot_invalid_cash(self):
        """Test validate_portfolio_snapshot with invalid cash balance."""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            cash_balance=-1000.0,  # Negative cash
            positions={},
            total_value=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0
        )
        
        is_valid, error = validate_portfolio_snapshot(snapshot)
        assert is_valid is False
        assert "Invalid cash balance" in error
    
    def test_validate_performance_report_valid(self):
        """Test validate_performance_report with valid report."""
        report = PerformanceReport(
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            total_return=0.15,
            annualized_return=0.20,
            sharpe_ratio=1.5,
            max_drawdown=0.05,
            win_rate=0.65,
            profit_factor=1.8,
            total_trades=50,
            avg_trade_return=0.003,
            best_trade=0.08,
            worst_trade=-0.04,
            starting_capital=10000.0
        )
        
        is_valid, error = validate_performance_report(report)
        assert is_valid is True
        assert error is None
    
    def test_validate_performance_report_invalid_dates(self):
        """Test validate_performance_report with invalid dates."""
        # Create a report that will fail validation by bypassing __post_init__
        report = object.__new__(PerformanceReport)
        report.start_date = datetime.now()
        report.end_date = datetime.now() - timedelta(days=1)  # End before start
        report.total_return = 0.15
        report.annualized_return = 0.20
        report.sharpe_ratio = 1.5
        report.max_drawdown = 0.05
        report.win_rate = 0.65
        report.profit_factor = 1.8
        report.total_trades = 50
        report.avg_trade_return = 0.003
        report.best_trade = 0.08
        report.worst_trade = -0.04
        report.starting_capital = 10000.0
        report.avg_holding_period = 0.0
        report.volatility = 0.0
        report.calmar_ratio = 0.0
        report.sortino_ratio = 0.0
        report.total_fees = 0.0
        report.ending_capital = 0.0
        
        is_valid, error = validate_performance_report(report)
        assert is_valid is False
        assert "Start date must be before end date" in error