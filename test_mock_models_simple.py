#!/usr/bin/env python3
"""
Simple test script to verify mock_models functionality without pytest.
"""
import sys
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.insert(0, '.')

from mock_trading.mock_models import (
    ExecutionResult, PortfolioSnapshot, PerformanceReport, MockPosition,
    Order, OrderResult, OrderType, ExecutionStatus,
    validate_numeric, validate_symbol, validate_order
)

def test_execution_result():
    """Test ExecutionResult creation and validation."""
    print("Testing ExecutionResult...")
    
    # Test valid creation
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
    print("✓ ExecutionResult creation successful")
    
    # Test validation
    try:
        ExecutionResult(
            order_id="test",
            executed_quantity=-10.0,  # Should fail
            execution_price=50.0,
            slippage=0.001,
            fees=0.5,
            execution_time=datetime.now()
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Executed quantity cannot be negative" in str(e)
        print("✓ ExecutionResult validation working")

def test_mock_position():
    """Test MockPosition functionality."""
    print("Testing MockPosition...")
    
    # Test basic creation
    position = MockPosition(
        symbol="BTCUSD",
        quantity=1.0,
        market_value=50000.0,
        avg_entry_price=49000.0,
        unrealized_pl=1000.0
    )
    
    assert position.symbol == "BTCUSD"
    assert position.quantity == 1.0
    print("✓ MockPosition creation successful")
    
    # Test adding trades
    position = MockPosition("BTCUSD", 1.0)
    position.entry_prices = [50000.0]
    position.entry_quantities = [1.0]
    position.entry_timestamps = [datetime.now()]
    
    # Add another buy trade
    position.add_trade(0.5, 51000.0, datetime.now(), 5.0)
    
    assert position.quantity == 1.5
    assert len(position.entry_prices) == 2
    assert position.fees_paid == 5.0
    print("✓ MockPosition add_trade working")
    
    # Test P&L calculation
    unrealized_pnl = position.calculate_unrealized_pnl(52000.0)
    assert unrealized_pnl > 0  # Should be profitable
    print("✓ MockPosition P&L calculation working")

def test_order():
    """Test Order functionality."""
    print("Testing Order...")
    
    # Test basic creation
    order = Order(symbol="BTCUSD", quantity=1.0)
    
    assert order.symbol == "BTCUSD"
    assert order.quantity == 1.0
    assert order.remaining_quantity == 1.0
    print("✓ Order creation successful")
    
    # Test fill update
    order.update_fill(0.5, 50000.0, 2.5)
    
    assert order.filled_quantity == 0.5
    assert order.remaining_quantity == 0.5
    assert order.avg_fill_price == 50000.0
    assert order.fees == 2.5
    print("✓ Order fill update working")

def test_validation_functions():
    """Test validation functions."""
    print("Testing validation functions...")
    
    # Test validate_numeric
    assert validate_numeric(10.5) == True
    assert validate_numeric("15.2") == True
    assert validate_numeric("abc") == False
    print("✓ validate_numeric working")
    
    # Test validate_symbol
    assert validate_symbol("BTCUSD") == True
    assert validate_symbol("BTC/USD") == True
    assert validate_symbol("") == False
    assert validate_symbol("AB") == False  # Too short
    print("✓ validate_symbol working")
    
    # Test validate_order
    order = Order(symbol="BTCUSD", quantity=1.0)
    is_valid, error = validate_order(order)
    assert is_valid == True
    assert error is None
    
    order_invalid = Order(symbol="", quantity=1.0)
    is_valid, error = validate_order(order_invalid)
    assert is_valid == False
    assert "Invalid symbol" in error
    print("✓ validate_order working")

def test_portfolio_snapshot():
    """Test PortfolioSnapshot functionality."""
    print("Testing PortfolioSnapshot...")
    
    positions = {
        "BTCUSD": MockPosition("BTCUSD", 1.0, 50000.0, 49000.0, 1000.0),
        "ETHUSD": MockPosition("ETHUSD", 10.0, 30000.0, 2900.0, 1000.0)
    }
    
    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(),
        cash_balance=10000.0,
        positions=positions,
        total_value=90000.0,
        unrealized_pnl=2000.0,
        realized_pnl=500.0
    )
    
    assert snapshot.cash_balance == 10000.0
    assert len(snapshot.positions) == 2
    assert snapshot.position_count == 2  # calculated in __post_init__
    assert snapshot.largest_position_value == 50000.0
    print("✓ PortfolioSnapshot working")

def test_performance_report():
    """Test PerformanceReport functionality."""
    print("Testing PerformanceReport...")
    
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
    
    assert report.total_return == 0.15
    assert report.total_trades == 50
    assert report.starting_capital == 10000.0
    print("✓ PerformanceReport working")

def main():
    """Run all tests."""
    print("Running mock_models tests...\n")
    
    try:
        test_execution_result()
        test_mock_position()
        test_order()
        test_validation_functions()
        test_portfolio_snapshot()
        test_performance_report()
        
        print("\n🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)