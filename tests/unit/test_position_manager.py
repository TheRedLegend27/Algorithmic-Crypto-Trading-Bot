"""
Unit tests for the Position Manager and P&L Calculator.

Tests cover multi-entry position tracking, P&L calculations, portfolio management,
position reconciliation, and consistency checking functionality.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import logging

from mock_trading.position_manager import PositionManager, PnLCalculator, PositionEntry, TradeRecord
from mock_trading.mock_models import MockPosition, ExecutionResult, PortfolioSnapshot
from mock_trading.mock_config import MockTradingConfig


@pytest.fixture
def mock_config():
    """Create a mock trading configuration for testing."""
    config = MockTradingConfig()
    config.starting_capital = 10000.0
    config.trading_fee_percent = 0.001
    config.slippage_base = 0.0001
    return config


@pytest.fixture
def position_manager(mock_config):
    """Create a position manager instance for testing."""
    return PositionManager(mock_config, starting_cash=10000.0)


@pytest.fixture
def pnl_calculator(mock_config):
    """Create a P&L calculator instance for testing."""
    return PnLCalculator(mock_config)


@pytest.fixture
def sample_execution_result():
    """Create a sample execution result for testing."""
    return ExecutionResult(
        order_id="BTCUSD_12345",
        executed_quantity=0.1,
        execution_price=50000.0,
        slippage=0.01,
        fees=5.0,
        execution_time=datetime.now(),
        market_impact=0.005,
        partial_fill=False
    )


class TestPnLCalculator:
    """Test cases for the PnLCalculator class."""
    
    def test_calculate_unrealized_pnl_long_position(self, pnl_calculator):
        """Test unrealized P&L calculation for long positions."""
        position = MockPosition(
            symbol="BTCUSD",
            quantity=0.1,
            avg_entry_price=50000.0
        )
        
        # Test profit scenario
        current_price = 55000.0
        unrealized_pnl = pnl_calculator.calculate_unrealized_pnl(position, current_price)
        
        expected_pnl = 0.1 * (55000.0 - 50000.0)  # 500.0
        assert unrealized_pnl == expected_pnl
        assert position.unrealized_pl == expected_pnl
        assert position.market_value == 0.1 * 55000.0
        
        # Test loss scenario
        current_price = 45000.0
        unrealized_pnl = pnl_calculator.calculate_unrealized_pnl(position, current_price)
        
        expected_pnl = 0.1 * (45000.0 - 50000.0)  # -500.0
        assert unrealized_pnl == expected_pnl
        assert position.unrealized_pl == expected_pnl
    
    def test_calculate_unrealized_pnl_short_position(self, pnl_calculator):
        """Test unrealized P&L calculation for short positions."""
        position = MockPosition(
            symbol="BTCUSD",
            quantity=-0.1,  # Short position
            avg_entry_price=50000.0
        )
        
        # Test profit scenario (price goes down)
        current_price = 45000.0
        unrealized_pnl = pnl_calculator.calculate_unrealized_pnl(position, current_price)
        
        expected_pnl = 0.1 * (50000.0 - 45000.0)  # 500.0
        assert unrealized_pnl == expected_pnl
        
        # Test loss scenario (price goes up)
        current_price = 55000.0
        unrealized_pnl = pnl_calculator.calculate_unrealized_pnl(position, current_price)
        
        expected_pnl = 0.1 * (50000.0 - 55000.0)  # -500.0
        assert unrealized_pnl == expected_pnl
    
    def test_calculate_unrealized_pnl_zero_position(self, pnl_calculator):
        """Test unrealized P&L calculation for zero positions."""
        position = MockPosition(
            symbol="BTCUSD",
            quantity=0.0,
            avg_entry_price=50000.0
        )
        
        unrealized_pnl = pnl_calculator.calculate_unrealized_pnl(position, 55000.0)
        assert unrealized_pnl == 0.0
    
    def test_calculate_realized_pnl_long_trade(self, pnl_calculator):
        """Test realized P&L calculation for long trades."""
        # Profitable long trade
        realized_pnl = pnl_calculator.calculate_realized_pnl(
            entry_price=50000.0,
            exit_price=55000.0,
            quantity=0.1,
            fees=10.0
        )
        
        expected_pnl = 0.1 * (55000.0 - 50000.0) - 10.0  # 500.0 - 10.0 = 490.0
        assert realized_pnl == expected_pnl
        
        # Losing long trade
        realized_pnl = pnl_calculator.calculate_realized_pnl(
            entry_price=50000.0,
            exit_price=45000.0,
            quantity=0.1,
            fees=10.0
        )
        
        expected_pnl = 0.1 * (45000.0 - 50000.0) - 10.0  # -500.0 - 10.0 = -510.0
        assert realized_pnl == expected_pnl
    
    def test_calculate_realized_pnl_short_trade(self, pnl_calculator):
        """Test realized P&L calculation for short trades."""
        # Profitable short trade (price goes down)
        realized_pnl = pnl_calculator.calculate_realized_pnl(
            entry_price=50000.0,
            exit_price=45000.0,
            quantity=-0.1,  # Short position
            fees=10.0
        )
        
        expected_pnl = 0.1 * (50000.0 - 45000.0) - 10.0  # 500.0 - 10.0 = 490.0
        assert realized_pnl == expected_pnl
    
    def test_calculate_position_pnl_percentage(self, pnl_calculator):
        """Test P&L percentage calculation."""
        position = MockPosition(
            symbol="BTCUSD",
            quantity=0.1,
            avg_entry_price=50000.0,
            cost_basis=5000.0  # 0.1 * 50000.0
        )
        
        # 10% gain
        pnl_percentage = pnl_calculator.calculate_position_pnl_percentage(position, 55000.0)
        assert abs(pnl_percentage - 10.0) < 0.01
        
        # 10% loss
        pnl_percentage = pnl_calculator.calculate_position_pnl_percentage(position, 45000.0)
        assert abs(pnl_percentage - (-10.0)) < 0.01
    
    def test_calculate_portfolio_pnl(self, pnl_calculator):
        """Test portfolio P&L calculation."""
        positions = {
            "BTCUSD": MockPosition(
                symbol="BTCUSD",
                quantity=0.1,
                avg_entry_price=50000.0,
                realized_pnl=100.0
            ),
            "ETHUSD": MockPosition(
                symbol="ETHUSD",
                quantity=1.0,
                avg_entry_price=3000.0,
                realized_pnl=50.0
            )
        }
        
        market_prices = {
            "BTCUSD": 55000.0,  # 500 unrealized profit
            "ETHUSD": 2800.0    # 200 unrealized loss
        }
        
        unrealized_pnl, realized_pnl = pnl_calculator.calculate_portfolio_pnl(positions, market_prices)
        
        expected_unrealized = 500.0 - 200.0  # 300.0
        expected_realized = 100.0 + 50.0     # 150.0
        
        assert unrealized_pnl == expected_unrealized
        assert realized_pnl == expected_realized


class TestPositionManager:
    """Test cases for the PositionManager class."""
    
    def test_initialization(self, position_manager):
        """Test position manager initialization."""
        assert position_manager.starting_cash == 10000.0
        assert position_manager.cash_balance == 10000.0
        assert len(position_manager.positions) == 0
        assert len(position_manager.trade_history) == 0
        assert len(position_manager.portfolio_history) == 0
    
    def test_update_position_new_buy(self, position_manager, sample_execution_result):
        """Test updating position with a new buy order."""
        # Modify execution result to simulate a buy
        sample_execution_result.executed_quantity = 0.1
        sample_execution_result.execution_price = 50000.0
        sample_execution_result.fees = 5.0
        
        success = position_manager.update_position(sample_execution_result)
        assert success
        
        # Check position was created
        position = position_manager.get_position("BTCUSD")
        assert position is not None
        assert position.quantity == 0.1
        assert position.avg_entry_price == 50000.0
        assert position.fees_paid == 5.0
        
        # Check cash balance was updated
        expected_cash = 10000.0 - (0.1 * 50000.0 + 5.0)  # 10000 - 5005 = 4995
        assert abs(position_manager.cash_balance - expected_cash) < 0.01
    
    def test_update_position_add_to_existing(self, position_manager):
        """Test adding to an existing position."""
        # First trade
        execution1 = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution1)
        
        # Second trade (add to position)
        execution2 = ExecutionResult(
            order_id="BTCUSD_2",
            executed_quantity=0.05,
            execution_price=52000.0,
            slippage=0.01,
            fees=2.5,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution2)
        
        # Check position was updated correctly
        position = position_manager.get_position("BTCUSD")
        assert position is not None
        assert abs(position.quantity - 0.15) < 0.0001
        assert position.fees_paid == 7.5
        
        # Check weighted average price
        expected_avg = (0.1 * 50000.0 + 0.05 * 52000.0) / 0.15
        assert abs(position.avg_entry_price - expected_avg) < 0.01
    
    def test_update_position_partial_close(self, position_manager):
        """Test partially closing a position."""
        # Open position
        execution1 = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution1)
        
        # Partial close (sell half)
        execution2 = ExecutionResult(
            order_id="BTCUSD_2",
            executed_quantity=-0.05,  # Negative for sell
            execution_price=55000.0,
            slippage=0.01,
            fees=2.5,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution2)
        
        # Check position was reduced
        position = position_manager.get_position("BTCUSD")
        assert position is not None
        assert abs(position.quantity - 0.05) < 0.0001
        
        # Check realized P&L was calculated
        expected_realized_pnl = 0.05 * (55000.0 - 50000.0)  # 250.0
        assert abs(position.realized_pnl - expected_realized_pnl) < 0.01
    
    def test_update_position_full_close(self, position_manager):
        """Test fully closing a position."""
        # Open position
        execution1 = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution1)
        
        # Full close
        execution2 = ExecutionResult(
            order_id="BTCUSD_2",
            executed_quantity=-0.1,  # Negative for sell
            execution_price=55000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution2)
        
        # Check position was removed
        position = position_manager.get_position("BTCUSD")
        assert position is None
    
    def test_calculate_portfolio_value(self, position_manager):
        """Test portfolio value calculation."""
        # Add some positions
        execution1 = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution1)
        
        execution2 = ExecutionResult(
            order_id="ETHUSD_1",
            executed_quantity=1.0,
            execution_price=3000.0,
            slippage=0.01,
            fees=3.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution2)
        
        # Calculate portfolio value
        market_prices = {
            "BTCUSD": 55000.0,
            "ETHUSD": 3200.0
        }
        
        portfolio_value = position_manager.calculate_portfolio_value(market_prices)
        
        # Expected: cash + BTC value + ETH value
        expected_cash = 10000.0 - (0.1 * 50000.0 + 5.0) - (1.0 * 3000.0 + 3.0)  # 1992
        expected_btc_value = 0.1 * 55000.0  # 5500
        expected_eth_value = 1.0 * 3200.0   # 3200
        expected_total = expected_cash + expected_btc_value + expected_eth_value
        
        assert abs(portfolio_value - expected_total) < 0.01
    
    def test_get_unrealized_pnl(self, position_manager):
        """Test unrealized P&L calculation."""
        # Add position
        execution = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution)
        
        # Calculate unrealized P&L
        market_prices = {"BTCUSD": 55000.0}
        unrealized_pnl = position_manager.get_unrealized_pnl(market_prices)
        
        expected_pnl = 0.1 * (55000.0 - 50000.0)  # 500.0
        assert abs(unrealized_pnl - expected_pnl) < 0.01
    
    def test_get_position_summary(self, position_manager):
        """Test position summary generation."""
        # Test empty position
        summary = position_manager.get_position_summary("BTCUSD")
        assert not summary["has_position"]
        assert summary["quantity"] == 0.0
        
        # Add position
        execution = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution)
        
        # Test position summary
        summary = position_manager.get_position_summary("BTCUSD", current_price=55000.0)
        assert summary["has_position"]
        assert summary["quantity"] == 0.1
        assert summary["avg_entry_price"] == 50000.0
        assert summary["fees_paid"] == 5.0
        assert summary["side"] == "LONG"
        assert abs(summary["pnl_percentage"] - 10.0) < 0.01  # 10% gain
    
    def test_create_portfolio_snapshot(self, position_manager):
        """Test portfolio snapshot creation."""
        # Add position
        execution = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution)
        
        # Create snapshot
        market_prices = {"BTCUSD": 55000.0}
        snapshot = position_manager.create_portfolio_snapshot(market_prices)
        
        assert isinstance(snapshot, PortfolioSnapshot)
        assert snapshot.cash_balance == position_manager.cash_balance
        assert len(snapshot.positions) == 1
        assert "BTCUSD" in snapshot.positions
        assert snapshot.total_value > 0
        assert snapshot.unrealized_pnl > 0  # Should be profitable
        
        # Check snapshot was added to history
        assert len(position_manager.portfolio_history) == 1
    
    def test_reconcile_positions(self, position_manager):
        """Test position reconciliation."""
        # Add position
        execution = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution)
        
        # Test accurate reconciliation
        expected_positions = {"BTCUSD": 0.1}
        results = position_manager.reconcile_positions(expected_positions)
        
        assert results["total_discrepancies"] == 0
        assert results["positions_accurate"] == 1
        assert len(results["discrepancies"]) == 0
        
        # Test discrepancy detection
        expected_positions = {"BTCUSD": 0.2}  # Wrong quantity
        results = position_manager.reconcile_positions(expected_positions)
        
        assert results["total_discrepancies"] == 1
        assert len(results["discrepancies"]) == 1
        assert results["discrepancies"][0]["symbol"] == "BTCUSD"
        assert results["discrepancies"][0]["expected_quantity"] == 0.2
        assert results["discrepancies"][0]["actual_quantity"] == 0.1
    
    def test_check_position_consistency(self, position_manager):
        """Test position consistency checking."""
        # Test with clean state
        results = position_manager.check_position_consistency()
        assert results["issues_found"] == 0
        assert results["cash_balance_valid"]
        
        # Add position and test again
        execution = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution)
        
        results = position_manager.check_position_consistency()
        assert results["issues_found"] == 0
        assert results["positions_checked"] == 1
        
        # Test with negative cash (simulate issue)
        position_manager.cash_balance = -100.0
        results = position_manager.check_position_consistency()
        assert results["issues_found"] > 0
        assert not results["cash_balance_valid"]
    
    def test_get_performance_summary(self, position_manager):
        """Test performance summary generation."""
        # Test initial state
        summary = position_manager.get_performance_summary()
        assert summary["starting_cash"] == 10000.0
        assert summary["current_cash"] == 10000.0
        assert summary["total_return"] == 0.0
        assert summary["active_positions"] == 0
        
        # Add profitable position
        execution = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution)
        
        # Update position with current price for unrealized P&L
        position = position_manager.get_position("BTCUSD")
        position.calculate_unrealized_pnl(55000.0)
        
        summary = position_manager.get_performance_summary()
        assert summary["active_positions"] == 1
        assert summary["total_return"] > 0  # Should be profitable
        assert summary["unrealized_pnl"] > 0
    
    def test_reset_portfolio(self, position_manager):
        """Test portfolio reset functionality."""
        # Add some data
        execution = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution)
        
        # Create snapshot
        market_prices = {"BTCUSD": 55000.0}
        position_manager.create_portfolio_snapshot(market_prices)
        
        # Verify data exists
        assert len(position_manager.positions) > 0
        assert len(position_manager.portfolio_history) > 0
        assert position_manager.cash_balance != position_manager.starting_cash
        
        # Reset portfolio
        position_manager.reset_portfolio(new_starting_cash=15000.0)
        
        # Verify reset
        assert position_manager.starting_cash == 15000.0
        assert position_manager.cash_balance == 15000.0
        assert len(position_manager.positions) == 0
        assert len(position_manager.portfolio_history) == 0
        assert len(position_manager.trade_history) == 0


class TestComplexTradingScenarios:
    """Test complex trading scenarios with multiple entries and exits."""
    
    def test_multiple_entries_fifo_exit(self, position_manager):
        """Test FIFO (First In, First Out) position closing with multiple entries."""
        # First entry
        execution1 = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution1)
        
        # Second entry at higher price
        execution2 = ExecutionResult(
            order_id="BTCUSD_2",
            executed_quantity=0.1,
            execution_price=52000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now() + timedelta(minutes=1)
        )
        position_manager.update_position(execution2)
        
        # Partial exit (should close first entry first - FIFO)
        execution3 = ExecutionResult(
            order_id="BTCUSD_3",
            executed_quantity=-0.05,  # Sell half of first entry
            execution_price=55000.0,
            slippage=0.01,
            fees=2.5,
            execution_time=datetime.now() + timedelta(minutes=2)
        )
        position_manager.update_position(execution3)
        
        position = position_manager.get_position("BTCUSD")
        assert position is not None
        assert abs(position.quantity - 0.15) < 0.0001  # 0.2 - 0.05
        
        # Check realized P&L (should be from first entry at 50000)
        expected_realized_pnl = 0.05 * (55000.0 - 50000.0)  # 250.0
        assert abs(position.realized_pnl - expected_realized_pnl) < 0.01
    
    def test_averaging_down_scenario(self, position_manager):
        """Test averaging down scenario (buying more as price falls)."""
        # Initial buy at high price
        execution1 = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=60000.0,
            slippage=0.01,
            fees=6.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(execution1)
        
        # Average down - buy more at lower price
        execution2 = ExecutionResult(
            order_id="BTCUSD_2",
            executed_quantity=0.2,
            execution_price=50000.0,
            slippage=0.01,
            fees=10.0,
            execution_time=datetime.now() + timedelta(minutes=5)
        )
        position_manager.update_position(execution2)
        
        position = position_manager.get_position("BTCUSD")
        assert abs(position.quantity - 0.3) < 0.0001
        
        # Check weighted average price
        expected_avg = (0.1 * 60000.0 + 0.2 * 50000.0) / 0.3  # 53333.33
        assert abs(position.avg_entry_price - expected_avg) < 0.01
        
        # Test unrealized P&L at breakeven price
        unrealized_pnl = position.calculate_unrealized_pnl(expected_avg)
        assert abs(unrealized_pnl) < 0.01  # Should be near zero at breakeven
    
    def test_swing_trading_scenario(self, position_manager):
        """Test swing trading with multiple complete cycles."""
        starting_cash = position_manager.cash_balance
        
        # First cycle: Buy low, sell high
        buy1 = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(buy1)
        
        sell1 = ExecutionResult(
            order_id="BTCUSD_2",
            executed_quantity=-0.1,
            execution_price=55000.0,
            slippage=0.01,
            fees=5.5,
            execution_time=datetime.now() + timedelta(hours=1)
        )
        position_manager.update_position(sell1)
        
        # Position should be closed
        assert position_manager.get_position("BTCUSD") is None
        
        # Second cycle: Buy higher, sell even higher
        buy2 = ExecutionResult(
            order_id="BTCUSD_3",
            executed_quantity=0.08,  # Different quantity
            execution_price=56000.0,
            slippage=0.01,
            fees=4.5,
            execution_time=datetime.now() + timedelta(hours=2)
        )
        position_manager.update_position(buy2)
        
        sell2 = ExecutionResult(
            order_id="BTCUSD_4",
            executed_quantity=-0.08,
            execution_price=62000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now() + timedelta(hours=3)
        )
        position_manager.update_position(sell2)
        
        # Check final cash balance
        # First cycle P&L: 0.1 * (55000 - 50000) - 10.5 = 489.5
        # Second cycle P&L: 0.08 * (62000 - 56000) - 9.5 = 470.5
        # Total expected gain: 489.5 + 470.5 = 960.0
        expected_cash = starting_cash + 960.0
        
        assert abs(position_manager.cash_balance - expected_cash) < 1.0
    
    def test_position_reversal_scenario(self, position_manager):
        """Test position reversal (long to short)."""
        # Open long position
        buy = ExecutionResult(
            order_id="BTCUSD_1",
            executed_quantity=0.1,
            execution_price=50000.0,
            slippage=0.01,
            fees=5.0,
            execution_time=datetime.now()
        )
        position_manager.update_position(buy)
        
        # Reverse to short (sell more than current position)
        sell = ExecutionResult(
            order_id="BTCUSD_2",
            executed_quantity=-0.2,  # Sell more than we have
            execution_price=55000.0,
            slippage=0.01,
            fees=11.0,
            execution_time=datetime.now() + timedelta(minutes=30)
        )
        position_manager.update_position(sell)
        
        position = position_manager.get_position("BTCUSD")
        assert position is not None
        assert abs(position.quantity - (-0.1)) < 0.0001  # Now short 0.1
        
        # Check that realized P&L was calculated for the closed long position
        expected_realized_pnl = 0.1 * (55000.0 - 50000.0)  # 500.0
        assert abs(position.realized_pnl - expected_realized_pnl) < 0.01
    
    def test_high_frequency_trading_scenario(self, position_manager):
        """Test high-frequency trading with many small trades."""
        initial_cash = position_manager.cash_balance
        
        # Execute 10 small trades
        for i in range(10):
            # Small buy
            buy = ExecutionResult(
                order_id=f"BTCUSD_buy_{i}",
                executed_quantity=0.01,
                execution_price=50000.0 + i * 10,  # Slightly increasing price
                slippage=0.001,
                fees=0.5,
                execution_time=datetime.now() + timedelta(seconds=i)
            )
            position_manager.update_position(buy)
            
            # Small sell
            sell = ExecutionResult(
                order_id=f"BTCUSD_sell_{i}",
                executed_quantity=-0.01,
                execution_price=50000.0 + i * 10 + 50,  # Small profit
                slippage=0.001,
                fees=0.5,
                execution_time=datetime.now() + timedelta(seconds=i + 0.5)
            )
            position_manager.update_position(sell)
        
        # All positions should be closed
        assert position_manager.get_position("BTCUSD") is None
        
        # Calculate expected result
        # Each trade: buy at price, sell at price + 50, pay 1.0 total fees
        # Profit per trade = 0.01 * 50 - 1.0 = 0.5 - 1.0 = -0.5 (loss due to fees)
        expected_loss = 10 * 0.5  # 10 trades * 0.5 loss each = 5.0 total loss
        expected_cash = initial_cash - expected_loss
        
        # Check that cash balance matches expected (small loss due to fees)
        assert abs(position_manager.cash_balance - expected_cash) < 1.0


if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    pytest.main([__file__, "-v"])