"""
Unit tests for the analytics module.

Tests the PerformanceAnalyzer, TradeAnalyzer, and RiskMetrics classes
with various scenarios and edge cases.
"""

import unittest
import math
import tempfile
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from mock_trading.analytics import (
    PerformanceAnalyzer, TradeAnalyzer, RiskMetrics, TradeMetrics
)
from mock_trading.mock_models import (
    ExecutionResult, PortfolioSnapshot, PerformanceReport, MockPosition,
    Order, OrderResult
)


class TestTradeAnalyzer(unittest.TestCase):
    """Test cases for TradeAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = TradeAnalyzer()
        self.base_time = datetime(2024, 1, 1, 10, 0, 0)
    
    def create_mock_position(self, symbol: str, quantity: float, entry_price: float,
                           realized_pnl: float = 0.0, fees: float = 0.0) -> MockPosition:
        """Create a mock position for testing."""
        position = MockPosition(
            symbol=symbol,
            quantity=quantity,
            avg_entry_price=entry_price,
            realized_pnl=realized_pnl,
            fees_paid=fees
        )
        
        # Add entry data
        position.entry_prices = [entry_price]
        position.entry_quantities = [quantity]
        position.entry_timestamps = [self.base_time]
        position.cost_basis = abs(quantity) * entry_price
        
        return position
    
    def test_analyze_trade_basic(self):
        """Test basic trade analysis."""
        position = self.create_mock_position("BTCUSD", 1.0, 50000.0, 1000.0, 10.0)
        
        trade_metrics = self.analyzer.analyze_trade(position, 51000.0)
        
        self.assertEqual(trade_metrics.symbol, "BTCUSD")
        self.assertEqual(trade_metrics.entry_price, 50000.0)
        self.assertEqual(trade_metrics.quantity, 1.0)
        self.assertEqual(trade_metrics.side, "LONG")
        self.assertEqual(trade_metrics.realized_pnl, 1000.0)
        self.assertEqual(trade_metrics.fees, 10.0)
        self.assertTrue(trade_metrics.is_winner)
    
    def test_analyze_trade_short_position(self):
        """Test analysis of short position."""
        position = self.create_mock_position("ETHUSD", -2.0, 3000.0, 500.0, 5.0)
        
        trade_metrics = self.analyzer.analyze_trade(position, 2900.0)
        
        self.assertEqual(trade_metrics.side, "SHORT")
        self.assertEqual(trade_metrics.quantity, 2.0)  # Absolute quantity
        self.assertTrue(trade_metrics.is_winner)
    
    def test_analyze_trade_losing_trade(self):
        """Test analysis of losing trade."""
        position = self.create_mock_position("ADAUSD", 1000.0, 1.0, -100.0, 2.0)
        
        trade_metrics = self.analyzer.analyze_trade(position, 0.9)
        
        self.assertFalse(trade_metrics.is_winner)
        self.assertEqual(trade_metrics.realized_pnl, -100.0)
    
    def test_analyze_trade_no_entry_data(self):
        """Test analysis with no entry data raises error."""
        position = MockPosition(symbol="BTCUSD", quantity=1.0)
        
        with self.assertRaises(ValueError):
            self.analyzer.analyze_trade(position)
    
    def test_analyze_all_trades(self):
        """Test analyzing multiple trades."""
        positions = {
            "BTCUSD": self.create_mock_position("BTCUSD", 1.0, 50000.0, 1000.0, 10.0),
            "ETHUSD": self.create_mock_position("ETHUSD", 2.0, 3000.0, -200.0, 5.0),
            "ADAUSD": self.create_mock_position("ADAUSD", 1000.0, 1.0, 50.0, 1.0)
        }
        
        current_prices = {"BTCUSD": 51000.0, "ETHUSD": 2950.0, "ADAUSD": 1.05}
        
        trades = self.analyzer.analyze_all_trades(positions, current_prices)
        
        self.assertEqual(len(trades), 3)
        self.assertEqual(trades[0].symbol, "BTCUSD")
        self.assertEqual(trades[1].symbol, "ETHUSD")
        self.assertEqual(trades[2].symbol, "ADAUSD")
    
    def test_get_trade_statistics_empty(self):
        """Test trade statistics with no trades."""
        stats = self.analyzer.get_trade_statistics()
        self.assertEqual(stats, {})
    
    def test_get_trade_statistics_comprehensive(self):
        """Test comprehensive trade statistics calculation."""
        # Create test positions
        positions = {
            "WIN1": self.create_mock_position("WIN1", 1.0, 100.0, 20.0, 1.0),
            "WIN2": self.create_mock_position("WIN2", 1.0, 200.0, 30.0, 2.0),
            "LOSS1": self.create_mock_position("LOSS1", 1.0, 150.0, -10.0, 1.5),
            "LOSS2": self.create_mock_position("LOSS2", 1.0, 300.0, -25.0, 3.0)
        }
        
        self.analyzer.analyze_all_trades(positions)
        stats = self.analyzer.get_trade_statistics()
        
        # Verify basic counts
        self.assertEqual(stats["total_trades"], 4)
        self.assertEqual(stats["winning_trades"], 2)
        self.assertEqual(stats["losing_trades"], 2)
        self.assertEqual(stats["win_rate_percent"], 50.0)
        
        # Verify P&L calculations
        self.assertEqual(stats["total_realized_pnl"], 15.0)  # 20+30-10-25
        self.assertEqual(stats["total_fees"], 7.5)  # 1+2+1.5+3
        self.assertEqual(stats["net_pnl"], 7.5)  # 15 - 7.5
        
        # Verify profit factor
        gross_profit = 50.0  # 20 + 30
        gross_loss = 35.0   # 10 + 25
        expected_profit_factor = gross_profit / gross_loss
        self.assertAlmostEqual(stats["profit_factor"], expected_profit_factor, places=2)


class TestRiskMetrics(unittest.TestCase):
    """Test cases for RiskMetrics class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.risk_metrics = RiskMetrics(risk_free_rate=0.02)
    
    def test_calculate_returns(self):
        """Test return calculation from portfolio values."""
        portfolio_values = [1000, 1100, 1050, 1200]
        returns = self.risk_metrics.calculate_returns(portfolio_values)
        
        expected_returns = [0.1, -0.045454545454545456, 0.14285714285714285]
        self.assertEqual(len(returns), 3)
        for i, expected in enumerate(expected_returns):
            self.assertAlmostEqual(returns[i], expected, places=6)
    
    def test_calculate_returns_empty(self):
        """Test return calculation with insufficient data."""
        self.assertEqual(self.risk_metrics.calculate_returns([]), [])
        self.assertEqual(self.risk_metrics.calculate_returns([1000]), [])
    
    def test_calculate_volatility(self):
        """Test volatility calculation."""
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        volatility = self.risk_metrics.calculate_volatility(returns, annualize=False)
        
        # Should be standard deviation of returns
        import statistics
        expected = statistics.stdev(returns)
        self.assertAlmostEqual(volatility, expected, places=6)
    
    def test_calculate_volatility_annualized(self):
        """Test annualized volatility calculation."""
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        volatility = self.risk_metrics.calculate_volatility(returns, annualize=True)
        
        import statistics
        expected = statistics.stdev(returns) * math.sqrt(252)
        self.assertAlmostEqual(volatility, expected, places=6)
    
    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        returns = [0.01, 0.02, -0.01, 0.03, 0.01]
        sharpe = self.risk_metrics.calculate_sharpe_ratio(returns, annualize=True)
        
        import statistics
        avg_return = statistics.mean(returns) * 252
        volatility = statistics.stdev(returns) * math.sqrt(252)
        expected = (avg_return - 0.02) / volatility
        
        self.assertAlmostEqual(sharpe, expected, places=6)
    
    def test_calculate_sharpe_ratio_zero_volatility(self):
        """Test Sharpe ratio with zero volatility."""
        returns = [0.01, 0.01, 0.01, 0.01, 0.01]  # No variation
        sharpe = self.risk_metrics.calculate_sharpe_ratio(returns)
        self.assertEqual(sharpe, 0.0)
    
    def test_calculate_sortino_ratio(self):
        """Test Sortino ratio calculation."""
        returns = [0.02, -0.01, 0.03, -0.02, 0.01]
        sortino = self.risk_metrics.calculate_sortino_ratio(returns, annualize=False)
        
        import statistics
        avg_return = statistics.mean(returns)
        negative_returns = [-0.01, -0.02]
        downside_deviation = math.sqrt(statistics.mean([r**2 for r in negative_returns]))
        expected = (avg_return - 0.02/252) / downside_deviation
        
        self.assertAlmostEqual(sortino, expected, places=6)
    
    def test_calculate_sortino_ratio_no_negative_returns(self):
        """Test Sortino ratio with no negative returns."""
        returns = [0.01, 0.02, 0.03, 0.01, 0.02]
        sortino = self.risk_metrics.calculate_sortino_ratio(returns)
        
        # Should return infinity for positive average return with no downside
        self.assertEqual(sortino, float('inf'))
    
    def test_calculate_max_drawdown(self):
        """Test maximum drawdown calculation."""
        portfolio_values = [1000, 1100, 1050, 900, 950, 1200]
        max_dd, start_idx, end_idx = self.risk_metrics.calculate_max_drawdown(portfolio_values)
        
        # Max drawdown should be from 1100 to 900 = 18.18%
        expected_dd = ((1100 - 900) / 1100) * 100
        self.assertAlmostEqual(max_dd, expected_dd, places=2)
        self.assertEqual(start_idx, 1)  # Peak at index 1 (1100)
        self.assertEqual(end_idx, 3)    # Trough at index 3 (900)
    
    def test_calculate_max_drawdown_no_drawdown(self):
        """Test max drawdown with only increasing values."""
        portfolio_values = [1000, 1100, 1200, 1300]
        max_dd, start_idx, end_idx = self.risk_metrics.calculate_max_drawdown(portfolio_values)
        
        self.assertEqual(max_dd, 0.0)
        self.assertEqual(start_idx, 0)
        self.assertEqual(end_idx, 0)
    
    def test_calculate_calmar_ratio(self):
        """Test Calmar ratio calculation."""
        total_return = 0.20  # 20% total return
        max_drawdown = 10.0  # 10% max drawdown
        period_years = 2.0
        
        calmar = self.risk_metrics.calculate_calmar_ratio(total_return, max_drawdown, period_years)
        
        # Annualized return = (1.20)^(1/2) - 1 ≈ 0.0954
        # Calmar = 0.0954 / 0.10 ≈ 0.954
        expected = ((1 + total_return) ** (1 / period_years) - 1) / (max_drawdown / 100)
        self.assertAlmostEqual(calmar, expected, places=4)
    
    def test_calculate_var(self):
        """Test Value at Risk calculation."""
        returns = [-0.05, -0.02, 0.01, 0.03, -0.01, 0.02, -0.03, 0.04, -0.01, 0.01]
        var_5 = self.risk_metrics.calculate_var(returns, confidence_level=0.05)
        
        # 5% VaR should be the 5th percentile (worst 5% of returns)
        sorted_returns = sorted(returns)
        expected_index = int(len(sorted_returns) * 0.05)
        expected_var = sorted_returns[expected_index]
        
        self.assertEqual(var_5, expected_var)
    
    def test_calculate_beta(self):
        """Test beta calculation."""
        portfolio_returns = [0.02, -0.01, 0.03, -0.02, 0.01]
        market_returns = [0.015, -0.005, 0.025, -0.015, 0.005]
        
        beta = self.risk_metrics.calculate_beta(portfolio_returns, market_returns)
        
        # Calculate expected beta manually
        import statistics
        port_mean = statistics.mean(portfolio_returns)
        market_mean = statistics.mean(market_returns)
        
        covariance = statistics.mean([
            (p - port_mean) * (m - market_mean) 
            for p, m in zip(portfolio_returns, market_returns)
        ])
        market_variance = statistics.variance(market_returns)
        expected_beta = covariance / market_variance
        
        self.assertAlmostEqual(beta, expected_beta, places=6)
    
    def test_calculate_beta_mismatched_lengths(self):
        """Test beta calculation with mismatched return arrays."""
        portfolio_returns = [0.01, 0.02, 0.03]
        market_returns = [0.01, 0.02]  # Different length
        
        beta = self.risk_metrics.calculate_beta(portfolio_returns, market_returns)
        self.assertEqual(beta, 0.0)


class TestPerformanceAnalyzer(unittest.TestCase):
    """Test cases for PerformanceAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = PerformanceAnalyzer(risk_free_rate=0.02)
        self.base_time = datetime(2024, 1, 1, 10, 0, 0)
    
    def create_portfolio_snapshot(self, timestamp: datetime, cash: float, 
                                total_value: float, positions: dict = None) -> PortfolioSnapshot:
        """Create a portfolio snapshot for testing."""
        if positions is None:
            positions = {}
        
        return PortfolioSnapshot(
            timestamp=timestamp,
            cash_balance=cash,
            positions=positions,
            total_value=total_value,
            unrealized_pnl=0.0,
            realized_pnl=0.0
        )
    
    def test_add_portfolio_snapshot(self):
        """Test adding portfolio snapshots."""
        snapshot = self.create_portfolio_snapshot(self.base_time, 1000.0, 1000.0)
        self.analyzer.add_portfolio_snapshot(snapshot)
        
        self.assertEqual(len(self.analyzer.portfolio_history), 1)
        self.assertEqual(self.analyzer.portfolio_history[0], snapshot)
    
    def test_add_trade_execution(self):
        """Test adding trade executions."""
        execution = ExecutionResult(
            order_id="test_order",
            symbol="BTCUSD",
            executed_quantity=1.0,
            execution_price=50000.0,
            slippage=0.001,
            fees=10.0,
            execution_time=self.base_time
        )
        
        self.analyzer.add_trade_execution(execution)
        
        self.assertEqual(len(self.analyzer.trade_history), 1)
        self.assertEqual(self.analyzer.trade_history[0], execution)
    
    def test_calculate_total_return(self):
        """Test total return calculation."""
        # Add snapshots with different values
        snapshot1 = self.create_portfolio_snapshot(self.base_time, 1000.0, 1000.0)
        snapshot2 = self.create_portfolio_snapshot(
            self.base_time + timedelta(days=30), 800.0, 1200.0
        )
        
        self.analyzer.add_portfolio_snapshot(snapshot1)
        self.analyzer.add_portfolio_snapshot(snapshot2)
        
        total_return = self.analyzer.calculate_total_return()
        expected_return = ((1200 - 1000) / 1000) * 100  # 20%
        
        self.assertAlmostEqual(total_return, expected_return, places=2)
    
    def test_calculate_total_return_insufficient_data(self):
        """Test total return with insufficient data."""
        self.assertEqual(self.analyzer.calculate_total_return(), 0.0)
        
        # Add only one snapshot
        snapshot = self.create_portfolio_snapshot(self.base_time, 1000.0, 1000.0)
        self.analyzer.add_portfolio_snapshot(snapshot)
        self.assertEqual(self.analyzer.calculate_total_return(), 0.0)
    
    def test_calculate_annualized_return(self):
        """Test annualized return calculation."""
        # Add snapshots 1 year apart
        snapshot1 = self.create_portfolio_snapshot(self.base_time, 1000.0, 1000.0)
        snapshot2 = self.create_portfolio_snapshot(
            self.base_time + timedelta(days=365), 800.0, 1200.0
        )
        
        self.analyzer.add_portfolio_snapshot(snapshot1)
        self.analyzer.add_portfolio_snapshot(snapshot2)
        
        annualized_return = self.analyzer.calculate_annualized_return()
        # For 1 year period, annualized return should equal total return
        expected_return = 20.0  # 20% total return
        
        self.assertAlmostEqual(annualized_return, expected_return, places=1)
    
    def test_get_portfolio_values(self):
        """Test extracting portfolio values."""
        values = [1000.0, 1100.0, 1050.0, 1200.0]
        
        for i, value in enumerate(values):
            snapshot = self.create_portfolio_snapshot(
                self.base_time + timedelta(days=i), 0.0, value
            )
            self.analyzer.add_portfolio_snapshot(snapshot)
        
        extracted_values = self.analyzer.get_portfolio_values()
        self.assertEqual(extracted_values, values)
    
    def test_get_portfolio_returns(self):
        """Test calculating portfolio returns."""
        values = [1000.0, 1100.0, 1050.0, 1200.0]
        
        for i, value in enumerate(values):
            snapshot = self.create_portfolio_snapshot(
                self.base_time + timedelta(days=i), 0.0, value
            )
            self.analyzer.add_portfolio_snapshot(snapshot)
        
        returns = self.analyzer.get_portfolio_returns()
        expected_returns = [0.1, -0.045454545454545456, 0.14285714285714285]
        
        self.assertEqual(len(returns), 3)
        for i, expected in enumerate(expected_returns):
            self.assertAlmostEqual(returns[i], expected, places=6)
    
    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        # Add portfolio snapshots with varying returns
        values = [1000, 1020, 1010, 1040, 1030, 1060]
        
        for i, value in enumerate(values):
            snapshot = self.create_portfolio_snapshot(
                self.base_time + timedelta(days=i), 0.0, value
            )
            self.analyzer.add_portfolio_snapshot(snapshot)
        
        sharpe = self.analyzer.calculate_sharpe_ratio()
        
        # Should be a reasonable Sharpe ratio (not zero)
        self.assertIsInstance(sharpe, float)
        self.assertNotEqual(sharpe, 0.0)
    
    def test_calculate_max_drawdown(self):
        """Test maximum drawdown calculation."""
        values = [1000, 1100, 1050, 900, 950, 1200]
        
        for i, value in enumerate(values):
            snapshot = self.create_portfolio_snapshot(
                self.base_time + timedelta(days=i), 0.0, value
            )
            self.analyzer.add_portfolio_snapshot(snapshot)
        
        max_dd = self.analyzer.calculate_max_drawdown()
        expected_dd = ((1100 - 900) / 1100) * 100  # 18.18%
        
        self.assertAlmostEqual(max_dd, expected_dd, places=2)
    
    def test_generate_performance_report_empty(self):
        """Test generating report with no data."""
        report = self.analyzer.generate_performance_report()
        
        self.assertIsInstance(report, PerformanceReport)
        self.assertEqual(report.total_return, 0.0)
        self.assertEqual(report.total_trades, 0)
        self.assertEqual(report.starting_capital, 0.0)
    
    def test_generate_performance_report_comprehensive(self):
        """Test generating comprehensive performance report."""
        # Add portfolio history
        values = [10000, 10500, 10200, 11000, 10800, 12000]
        for i, value in enumerate(values):
            snapshot = self.create_portfolio_snapshot(
                self.base_time + timedelta(days=i*30), 0.0, value
            )
            self.analyzer.add_portfolio_snapshot(snapshot)
        
        # Add some positions for trade analysis
        position = MockPosition(
            symbol="BTCUSD",
            quantity=1.0,
            avg_entry_price=50000.0,
            realized_pnl=1000.0,
            fees_paid=10.0
        )
        position.entry_prices = [50000.0]
        position.entry_quantities = [1.0]
        position.entry_timestamps = [self.base_time]
        position.cost_basis = 50000.0
        
        self.analyzer.positions = {"BTCUSD": position}
        
        report = self.analyzer.generate_performance_report()
        
        # Verify report structure
        self.assertIsInstance(report, PerformanceReport)
        self.assertEqual(report.starting_capital, 10000.0)
        self.assertEqual(report.ending_capital, 12000.0)
        self.assertAlmostEqual(report.total_return, 20.0, places=1)  # 20% return
        self.assertGreater(report.total_trades, 0)
    
    def test_export_report_to_json(self):
        """Test exporting report to JSON."""
        # Create a simple report
        report = PerformanceReport(
            start_date=self.base_time,
            end_date=self.base_time + timedelta(days=30),
            total_return=10.0,
            annualized_return=120.0,
            sharpe_ratio=1.5,
            max_drawdown=5.0,
            win_rate=60.0,
            profit_factor=1.8,
            total_trades=10,
            avg_trade_return=1.0,
            best_trade=100.0,
            worst_trade=-50.0,
            starting_capital=10000.0,
            ending_capital=11000.0
        )
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        success = self.analyzer.export_report_to_json(report, temp_path)
        self.assertTrue(success)
        
        # Verify file contents
        with open(temp_path, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data['total_return'], 10.0)
        self.assertEqual(data['total_trades'], 10)
        self.assertEqual(data['starting_capital'], 10000.0)
    
    def test_format_report(self):
        """Test formatting report as text."""
        report = PerformanceReport(
            start_date=self.base_time,
            end_date=self.base_time + timedelta(days=30),
            total_return=10.0,
            annualized_return=120.0,
            sharpe_ratio=1.5,
            max_drawdown=5.0,
            win_rate=60.0,
            profit_factor=1.8,
            total_trades=10,
            avg_trade_return=1.0,
            best_trade=100.0,
            worst_trade=-50.0,
            starting_capital=10000.0,
            ending_capital=11000.0,
            volatility=15.0,
            sortino_ratio=2.0,
            calmar_ratio=24.0,
            avg_holding_period=2.5,
            total_fees=25.0
        )
        
        formatted_text = self.analyzer.format_report(report)
        
        # Verify key information is present
        self.assertIn("PERFORMANCE REPORT", formatted_text)
        self.assertIn("Total Return:", formatted_text)
        self.assertIn("10.00%", formatted_text)
        self.assertIn("Sharpe Ratio:", formatted_text)
        self.assertIn("1.50", formatted_text)
        self.assertIn("Total Trades:", formatted_text)
        self.assertIn("10", formatted_text)
        self.assertIn("10,000.00", formatted_text)  # Check for the number without exact spacing
        self.assertIn("11,000.00", formatted_text)


if __name__ == '__main__':
    unittest.main()