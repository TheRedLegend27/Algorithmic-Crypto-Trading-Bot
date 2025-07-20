#!/usr/bin/env python3
"""
Demo script for the analytics module.

This script demonstrates how to use the PerformanceAnalyzer, TradeAnalyzer,
and RiskMetrics classes to analyze trading performance.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import mock_trading modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mock_trading.analytics import PerformanceAnalyzer, TradeAnalyzer, RiskMetrics
from mock_trading.mock_models import (
    ExecutionResult, PortfolioSnapshot, MockPosition, PerformanceReport
)


def create_sample_data():
    """Create sample trading data for demonstration."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    
    # Create sample portfolio snapshots (simulating 30 days of trading)
    portfolio_snapshots = []
    portfolio_values = [10000, 10200, 9950, 10400, 10150, 10800, 10600, 11200, 10900, 11500]
    
    for i, value in enumerate(portfolio_values):
        snapshot = PortfolioSnapshot(
            timestamp=base_time + timedelta(days=i*3),
            cash_balance=value * 0.2,  # 20% cash
            positions={},  # We'll add positions separately
            total_value=value,
            unrealized_pnl=(value - 10000) * 0.7,  # 70% of gains from positions
            realized_pnl=(value - 10000) * 0.3     # 30% of gains realized
        )
        portfolio_snapshots.append(snapshot)
    
    # Create sample positions with trade history
    positions = {}
    
    # Winning position - BTCUSD
    btc_position = MockPosition(
        symbol="BTCUSD",
        quantity=0.2,
        avg_entry_price=50000.0,
        realized_pnl=800.0,
        fees_paid=15.0
    )
    btc_position.entry_prices = [50000.0]
    btc_position.entry_quantities = [0.2]
    btc_position.entry_timestamps = [base_time + timedelta(days=1)]
    btc_position.cost_basis = 10000.0
    btc_position.last_price = 54000.0
    positions["BTCUSD"] = btc_position
    
    # Losing position - ETHUSD
    eth_position = MockPosition(
        symbol="ETHUSD",
        quantity=0.0,  # Closed position
        avg_entry_price=3000.0,
        realized_pnl=-150.0,
        fees_paid=8.0
    )
    eth_position.entry_prices = [3000.0]
    eth_position.entry_quantities = [2.0]
    eth_position.entry_timestamps = [base_time + timedelta(days=5)]
    eth_position.cost_basis = 6000.0
    positions["ETHUSD"] = eth_position
    
    # Another winning position - ADAUSD
    ada_position = MockPosition(
        symbol="ADAUSD",
        quantity=5000.0,
        avg_entry_price=0.50,
        realized_pnl=200.0,
        fees_paid=5.0
    )
    ada_position.entry_prices = [0.50]
    ada_position.entry_quantities = [5000.0]
    ada_position.entry_timestamps = [base_time + timedelta(days=10)]
    ada_position.cost_basis = 2500.0
    ada_position.last_price = 0.58
    positions["ADAUSD"] = ada_position
    
    # Create sample trade executions
    executions = [
        ExecutionResult(
            order_id="order_1",
            symbol="BTCUSD",
            executed_quantity=0.2,
            execution_price=50000.0,
            slippage=0.001,
            fees=15.0,
            execution_time=base_time + timedelta(days=1)
        ),
        ExecutionResult(
            order_id="order_2",
            symbol="ETHUSD",
            executed_quantity=2.0,
            execution_price=3000.0,
            slippage=0.002,
            fees=8.0,
            execution_time=base_time + timedelta(days=5)
        ),
        ExecutionResult(
            order_id="order_3",
            symbol="ETHUSD",
            executed_quantity=-2.0,  # Sell order
            execution_price=2925.0,
            slippage=0.0015,
            fees=8.0,
            execution_time=base_time + timedelta(days=8)
        ),
        ExecutionResult(
            order_id="order_4",
            symbol="ADAUSD",
            executed_quantity=5000.0,
            execution_price=0.50,
            slippage=0.001,
            fees=5.0,
            execution_time=base_time + timedelta(days=10)
        )
    ]
    
    return portfolio_snapshots, positions, executions


def demo_trade_analyzer():
    """Demonstrate TradeAnalyzer functionality."""
    print("=" * 60)
    print("TRADE ANALYZER DEMO")
    print("=" * 60)
    
    _, positions, _ = create_sample_data()
    
    analyzer = TradeAnalyzer()
    
    # Analyze all trades
    current_prices = {"BTCUSD": 54000.0, "ETHUSD": 2925.0, "ADAUSD": 0.58}
    trades = analyzer.analyze_all_trades(positions, current_prices)
    
    print(f"Analyzed {len(trades)} trades:")
    print()
    
    for trade in trades:
        print(f"Trade: {trade.symbol}")
        print(f"  Side: {trade.side}")
        print(f"  Quantity: {trade.quantity}")
        print(f"  Entry Price: ${trade.entry_price:,.2f}")
        print(f"  Realized P&L: ${trade.realized_pnl:,.2f}")
        print(f"  Unrealized P&L: ${trade.unrealized_pnl:,.2f}")
        print(f"  Fees: ${trade.fees:,.2f}")
        print(f"  Return: {trade.return_percentage:.2f}%")
        print(f"  Winner: {'Yes' if trade.is_winner else 'No'}")
        print(f"  Holding Period: {trade.holding_period_hours:.1f} hours")
        print()
    
    # Get trade statistics
    stats = analyzer.get_trade_statistics()
    print("TRADE STATISTICS:")
    print(f"  Total Trades: {stats.get('total_trades', 0)}")
    print(f"  Win Rate: {stats.get('win_rate_percent', 0):.1f}%")
    print(f"  Profit Factor: {stats.get('profit_factor', 0):.2f}")
    print(f"  Average Return: {stats.get('average_return_percent', 0):.2f}%")
    print(f"  Best Trade: ${stats.get('largest_win', 0):.2f}")
    print(f"  Worst Trade: ${stats.get('largest_loss', 0):.2f}")
    print(f"  Total Fees: ${stats.get('total_fees', 0):.2f}")
    print()


def demo_risk_metrics():
    """Demonstrate RiskMetrics functionality."""
    print("=" * 60)
    print("RISK METRICS DEMO")
    print("=" * 60)
    
    risk_metrics = RiskMetrics(risk_free_rate=0.02)
    
    # Sample portfolio values and returns
    portfolio_values = [10000, 10200, 9950, 10400, 10150, 10800, 10600, 11200, 10900, 11500]
    returns = risk_metrics.calculate_returns(portfolio_values)
    
    print("Portfolio Values:", [f"${v:,.0f}" for v in portfolio_values])
    print("Returns:", [f"{r:.3f}" for r in returns])
    print()
    
    # Calculate various risk metrics
    volatility = risk_metrics.calculate_volatility(returns)
    sharpe_ratio = risk_metrics.calculate_sharpe_ratio(returns)
    sortino_ratio = risk_metrics.calculate_sortino_ratio(returns)
    max_dd, start_idx, end_idx = risk_metrics.calculate_max_drawdown(portfolio_values)
    var_5 = risk_metrics.calculate_var(returns, confidence_level=0.05)
    
    print("RISK METRICS:")
    print(f"  Volatility (annualized): {volatility:.2f}")
    print(f"  Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"  Sortino Ratio: {sortino_ratio:.2f}")
    print(f"  Max Drawdown: {max_dd:.2f}%")
    print(f"  5% VaR: {var_5:.3f}")
    print()
    
    # Calculate Calmar ratio
    total_return = (portfolio_values[-1] - portfolio_values[0]) / portfolio_values[0]
    period_years = len(portfolio_values) / 252  # Assuming daily data
    calmar_ratio = risk_metrics.calculate_calmar_ratio(total_return, max_dd, period_years)
    print(f"  Calmar Ratio: {calmar_ratio:.2f}")
    print()


def demo_performance_analyzer():
    """Demonstrate PerformanceAnalyzer functionality."""
    print("=" * 60)
    print("PERFORMANCE ANALYZER DEMO")
    print("=" * 60)
    
    snapshots, positions, executions = create_sample_data()
    
    analyzer = PerformanceAnalyzer(risk_free_rate=0.02)
    
    # Add data to analyzer
    for snapshot in snapshots:
        # Add positions to snapshots
        snapshot.positions = positions
        analyzer.add_portfolio_snapshot(snapshot)
    
    for execution in executions:
        analyzer.add_trade_execution(execution)
    
    # Update analyzer positions
    analyzer.positions = positions
    
    # Generate comprehensive performance report
    report = analyzer.generate_performance_report()
    
    print("PERFORMANCE REPORT GENERATED:")
    print(f"  Period: {report.start_date.strftime('%Y-%m-%d')} to {report.end_date.strftime('%Y-%m-%d')}")
    print(f"  Total Return: {report.total_return:.2f}%")
    print(f"  Annualized Return: {report.annualized_return:.2f}%")
    print(f"  Sharpe Ratio: {report.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {report.max_drawdown:.2f}%")
    print(f"  Win Rate: {report.win_rate:.1f}%")
    print(f"  Profit Factor: {report.profit_factor:.2f}")
    print(f"  Total Trades: {report.total_trades}")
    print(f"  Starting Capital: ${report.starting_capital:,.2f}")
    print(f"  Ending Capital: ${report.ending_capital:,.2f}")
    print()
    
    # Format and display full report
    formatted_report = analyzer.format_report(report)
    print("FORMATTED REPORT:")
    print(formatted_report)
    print()
    
    # Export report to JSON (optional)
    try:
        success = analyzer.export_report_to_json(report, "sample_performance_report.json")
        if success:
            print("Report exported to 'sample_performance_report.json'")
        else:
            print("Failed to export report")
    except Exception as e:
        print(f"Export error: {e}")


def main():
    """Run all demos."""
    print("MOCK TRADING ANALYTICS DEMO")
    print("=" * 60)
    print("This demo shows how to use the analytics module to analyze")
    print("trading performance with sample data.")
    print()
    
    try:
        demo_trade_analyzer()
        demo_risk_metrics()
        demo_performance_analyzer()
        
        print("=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()