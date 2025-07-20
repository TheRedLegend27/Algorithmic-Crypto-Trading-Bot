"""
Performance Analytics and Reporting Module

This module provides comprehensive performance analysis capabilities for the mock trading environment.
Includes PerformanceAnalyzer, TradeAnalyzer, and RiskMetrics classes for calculating trading metrics,
analyzing individual trades, and generating detailed performance reports.
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
import json
from pathlib import Path

from .mock_models import (
    ExecutionResult, PortfolioSnapshot, PerformanceReport, MockPosition,
    Order, OrderResult, validate_numeric
)


@dataclass
class TradeMetrics:
    """Individual trade performance metrics."""
    trade_id: str
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    side: str  # "LONG" or "SHORT"
    realized_pnl: float
    unrealized_pnl: float
    fees: float
    holding_period_hours: float
    return_percentage: float
    is_winner: bool
    max_favorable_excursion: float = 0.0  # Best unrealized P&L during trade
    max_adverse_excursion: float = 0.0    # Worst unrealized P&L during trade


class TradeAnalyzer:
    """
    Analyzes individual trade performance and patterns.
    
    This class provides detailed analysis of individual trades including
    entry/exit analysis, holding periods, and trade quality metrics.
    """
    
    def __init__(self):
        self.trades: List[TradeMetrics] = []
        self.trade_history: List[ExecutionResult] = []
    
    def add_execution(self, execution: ExecutionResult):
        """
        Add an execution result to the trade history.
        
        Args:
            execution: ExecutionResult to add to history
        """
        self.trade_history.append(execution)
    
    def analyze_trade(self, position: MockPosition, current_price: Optional[float] = None) -> TradeMetrics:
        """
        Analyze a single trade/position.
        
        Args:
            position: MockPosition to analyze
            current_price: Current market price for unrealized P&L calculation
            
        Returns:
            TradeMetrics: Comprehensive trade analysis
        """
        if not position.entry_timestamps:
            raise ValueError("Position has no entry data")
        
        entry_time = min(position.entry_timestamps)
        exit_time = None
        entry_price = position.avg_entry_price
        exit_price = None
        
        # Determine if position is closed
        is_closed = position.quantity == 0
        if is_closed and position.entry_timestamps:
            # For closed positions, estimate exit time as last entry time
            exit_time = max(position.entry_timestamps)
            exit_price = position.last_price if position.last_price > 0 else entry_price
        
        # Calculate holding period
        end_time = exit_time or datetime.now()
        holding_period = (end_time - entry_time).total_seconds() / 3600  # hours
        
        # Calculate return percentage
        if position.cost_basis > 0:
            total_pnl = position.realized_pnl + (position.unrealized_pl if not is_closed else 0)
            return_pct = (total_pnl / position.cost_basis) * 100
        else:
            return_pct = 0.0
        
        # Determine if it's a winning trade
        total_pnl = position.realized_pnl + position.unrealized_pl
        is_winner = total_pnl > 0
        
        # Calculate unrealized P&L if current price provided
        unrealized_pnl = 0.0
        if current_price and not is_closed:
            unrealized_pnl = position.calculate_unrealized_pnl(current_price)
        
        trade_metrics = TradeMetrics(
            trade_id=f"{position.symbol}_{entry_time.isoformat()}",
            symbol=position.symbol,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=sum(abs(q) for q in position.entry_quantities),
            side="LONG" if sum(position.entry_quantities) > 0 else "SHORT",
            realized_pnl=position.realized_pnl,
            unrealized_pnl=unrealized_pnl,
            fees=position.fees_paid,
            holding_period_hours=holding_period,
            return_percentage=return_pct,
            is_winner=is_winner
        )
        
        return trade_metrics
    
    def analyze_all_trades(self, positions: Dict[str, MockPosition], 
                          current_prices: Optional[Dict[str, float]] = None) -> List[TradeMetrics]:
        """
        Analyze all trades from position data.
        
        Args:
            positions: Dictionary of symbol to MockPosition
            current_prices: Current market prices for unrealized P&L
            
        Returns:
            List[TradeMetrics]: List of analyzed trades
        """
        self.trades = []
        
        for symbol, position in positions.items():
            if position.entry_timestamps:  # Only analyze positions with trade history
                current_price = current_prices.get(symbol) if current_prices else None
                try:
                    trade_metrics = self.analyze_trade(position, current_price)
                    self.trades.append(trade_metrics)
                except ValueError:
                    continue  # Skip positions without valid entry data
        
        return self.trades
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive trade statistics.
        
        Returns:
            Dict: Trade statistics and metrics
        """
        if not self.trades:
            return {}
        
        winning_trades = [t for t in self.trades if t.is_winner]
        losing_trades = [t for t in self.trades if not t.is_winner]
        
        # Basic statistics
        total_trades = len(self.trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
        
        # P&L statistics
        total_realized_pnl = sum(t.realized_pnl for t in self.trades)
        total_unrealized_pnl = sum(t.unrealized_pnl for t in self.trades)
        total_fees = sum(t.fees for t in self.trades)
        
        # Return statistics
        returns = [t.return_percentage for t in self.trades if t.return_percentage != 0]
        avg_return = statistics.mean(returns) if returns else 0
        median_return = statistics.median(returns) if returns else 0
        
        # Winning trade statistics
        if winning_trades:
            avg_win = statistics.mean([t.realized_pnl + t.unrealized_pnl for t in winning_trades])
            largest_win = max(t.realized_pnl + t.unrealized_pnl for t in winning_trades)
            avg_win_return = statistics.mean([t.return_percentage for t in winning_trades])
        else:
            avg_win = largest_win = avg_win_return = 0
        
        # Losing trade statistics
        if losing_trades:
            avg_loss = statistics.mean([t.realized_pnl + t.unrealized_pnl for t in losing_trades])
            largest_loss = min(t.realized_pnl + t.unrealized_pnl for t in losing_trades)
            avg_loss_return = statistics.mean([t.return_percentage for t in losing_trades])
        else:
            avg_loss = largest_loss = avg_loss_return = 0
        
        # Profit factor
        gross_profit = sum(max(0, t.realized_pnl + t.unrealized_pnl) for t in self.trades)
        gross_loss = abs(sum(min(0, t.realized_pnl + t.unrealized_pnl) for t in self.trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Holding period statistics
        holding_periods = [t.holding_period_hours for t in self.trades if t.holding_period_hours > 0]
        avg_holding_period = statistics.mean(holding_periods) if holding_periods else 0
        median_holding_period = statistics.median(holding_periods) if holding_periods else 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_rate_percent": win_rate,
            "total_realized_pnl": total_realized_pnl,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_fees": total_fees,
            "net_pnl": total_realized_pnl + total_unrealized_pnl - total_fees,
            "average_return_percent": avg_return,
            "median_return_percent": median_return,
            "average_win": avg_win,
            "largest_win": largest_win,
            "average_win_return_percent": avg_win_return,
            "average_loss": avg_loss,
            "largest_loss": largest_loss,
            "average_loss_return_percent": avg_loss_return,
            "profit_factor": profit_factor,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "average_holding_period_hours": avg_holding_period,
            "median_holding_period_hours": median_holding_period,
            "expectancy": (win_rate/100 * avg_win) + ((100-win_rate)/100 * avg_loss) if total_trades > 0 else 0
        }


class RiskMetrics:
    """
    Calculates risk-adjusted performance metrics.
    
    This class provides comprehensive risk analysis including Sharpe ratio,
    maximum drawdown, volatility calculations, and other risk metrics.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize RiskMetrics calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe ratio calculation
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_returns(self, portfolio_values: List[float]) -> List[float]:
        """
        Calculate period returns from portfolio values.
        
        Args:
            portfolio_values: List of portfolio values over time
            
        Returns:
            List[float]: Period returns
        """
        if len(portfolio_values) < 2:
            return []
        
        returns = []
        for i in range(1, len(portfolio_values)):
            if portfolio_values[i-1] > 0:
                ret = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
                returns.append(ret)
        
        return returns
    
    def calculate_volatility(self, returns: List[float], annualize: bool = True) -> float:
        """
        Calculate volatility (standard deviation of returns).
        
        Args:
            returns: List of period returns
            annualize: Whether to annualize the volatility
            
        Returns:
            float: Volatility
        """
        if len(returns) < 2:
            return 0.0
        
        volatility = statistics.stdev(returns)
        
        if annualize:
            # Assume daily returns, annualize by sqrt(252)
            volatility *= math.sqrt(252)
        
        return volatility
    
    def calculate_sharpe_ratio(self, returns: List[float], annualize: bool = True) -> float:
        """
        Calculate Sharpe ratio (risk-adjusted return).
        
        Args:
            returns: List of period returns
            annualize: Whether to annualize the ratio
            
        Returns:
            float: Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0
        
        avg_return = statistics.mean(returns)
        volatility = statistics.stdev(returns)
        
        if volatility == 0:
            return 0.0
        
        if annualize:
            # Annualize assuming daily returns
            avg_return *= 252
            volatility *= math.sqrt(252)
            risk_free_rate = self.risk_free_rate
        else:
            # Daily risk-free rate
            risk_free_rate = self.risk_free_rate / 252
        
        sharpe = (avg_return - risk_free_rate) / volatility
        return sharpe
    
    def calculate_sortino_ratio(self, returns: List[float], annualize: bool = True) -> float:
        """
        Calculate Sortino ratio (downside deviation adjusted return).
        
        Args:
            returns: List of period returns
            annualize: Whether to annualize the ratio
            
        Returns:
            float: Sortino ratio
        """
        if len(returns) < 2:
            return 0.0
        
        avg_return = statistics.mean(returns)
        
        # Calculate downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        if not negative_returns:
            return float('inf') if avg_return > 0 else 0.0
        
        downside_deviation = math.sqrt(statistics.mean([r**2 for r in negative_returns]))
        
        if downside_deviation == 0:
            return 0.0
        
        if annualize:
            avg_return *= 252
            downside_deviation *= math.sqrt(252)
            risk_free_rate = self.risk_free_rate
        else:
            risk_free_rate = self.risk_free_rate / 252
        
        sortino = (avg_return - risk_free_rate) / downside_deviation
        return sortino
    
    def calculate_max_drawdown(self, portfolio_values: List[float]) -> Tuple[float, int, int]:
        """
        Calculate maximum drawdown and its duration.
        
        Args:
            portfolio_values: List of portfolio values over time
            
        Returns:
            Tuple[float, int, int]: (max_drawdown_percent, start_index, end_index)
        """
        if len(portfolio_values) < 2:
            return 0.0, 0, 0
        
        peak = portfolio_values[0]
        max_drawdown = 0.0
        max_dd_start = 0
        max_dd_end = 0
        current_dd_start = 0
        
        for i, value in enumerate(portfolio_values):
            if value > peak:
                peak = value
                current_dd_start = i
            else:
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_dd_start = current_dd_start
                    max_dd_end = i
        
        return max_drawdown * 100, max_dd_start, max_dd_end  # Return as percentage
    
    def calculate_calmar_ratio(self, total_return: float, max_drawdown: float, 
                              period_years: float) -> float:
        """
        Calculate Calmar ratio (annualized return / max drawdown).
        
        Args:
            total_return: Total return over the period
            max_drawdown: Maximum drawdown percentage
            period_years: Period length in years
            
        Returns:
            float: Calmar ratio
        """
        if max_drawdown == 0 or period_years == 0:
            return 0.0
        
        annualized_return = ((1 + total_return) ** (1 / period_years)) - 1
        calmar = annualized_return / (max_drawdown / 100)
        
        return calmar
    
    def calculate_var(self, returns: List[float], confidence_level: float = 0.05) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: List of period returns
            confidence_level: Confidence level (e.g., 0.05 for 95% VaR)
            
        Returns:
            float: VaR value
        """
        if not returns:
            return 0.0
        
        sorted_returns = sorted(returns)
        index = int(len(sorted_returns) * confidence_level)
        
        if index >= len(sorted_returns):
            return sorted_returns[-1]
        
        return sorted_returns[index]
    
    def calculate_beta(self, portfolio_returns: List[float], 
                      market_returns: List[float]) -> float:
        """
        Calculate beta (correlation with market).
        
        Args:
            portfolio_returns: Portfolio returns
            market_returns: Market/benchmark returns
            
        Returns:
            float: Beta coefficient
        """
        if len(portfolio_returns) != len(market_returns) or len(portfolio_returns) < 2:
            return 0.0
        
        # Calculate covariance and market variance
        portfolio_mean = statistics.mean(portfolio_returns)
        market_mean = statistics.mean(market_returns)
        
        covariance = statistics.mean([
            (p - portfolio_mean) * (m - market_mean) 
            for p, m in zip(portfolio_returns, market_returns)
        ])
        
        market_variance = statistics.variance(market_returns)
        
        if market_variance == 0:
            return 0.0
        
        beta = covariance / market_variance
        return beta


class PerformanceAnalyzer:
    """
    Main performance analysis class with comprehensive metric calculations.
    
    This class orchestrates the calculation of all performance metrics and
    generates comprehensive performance reports.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize PerformanceAnalyzer.
        
        Args:
            risk_free_rate: Annual risk-free rate for calculations
        """
        self.risk_free_rate = risk_free_rate
        self.trade_analyzer = TradeAnalyzer()
        self.risk_metrics = RiskMetrics(risk_free_rate)
        
        # Data storage
        self.portfolio_history: List[PortfolioSnapshot] = []
        self.trade_history: List[ExecutionResult] = []
        self.positions: Dict[str, MockPosition] = {}
        
    def add_portfolio_snapshot(self, snapshot: PortfolioSnapshot):
        """
        Add a portfolio snapshot to the history.
        
        Args:
            snapshot: PortfolioSnapshot to add
        """
        self.portfolio_history.append(snapshot)
        # Update positions from snapshot
        self.positions.update(snapshot.positions)
    
    def add_trade_execution(self, execution: ExecutionResult):
        """
        Add a trade execution to the history.
        
        Args:
            execution: ExecutionResult to add
        """
        self.trade_history.append(execution)
        self.trade_analyzer.add_execution(execution)
    
    def calculate_total_return(self) -> float:
        """
        Calculate total return percentage.
        
        Returns:
            float: Total return as percentage
        """
        if len(self.portfolio_history) < 2:
            return 0.0
        
        initial_value = self.portfolio_history[0].total_value
        final_value = self.portfolio_history[-1].total_value
        
        if initial_value == 0:
            return 0.0
        
        return ((final_value - initial_value) / initial_value) * 100
    
    def calculate_annualized_return(self) -> float:
        """
        Calculate annualized return.
        
        Returns:
            float: Annualized return as percentage
        """
        if len(self.portfolio_history) < 2:
            return 0.0
        
        start_date = self.portfolio_history[0].timestamp
        end_date = self.portfolio_history[-1].timestamp
        period_days = (end_date - start_date).days
        
        if period_days == 0:
            return 0.0
        
        total_return = self.calculate_total_return() / 100  # Convert to decimal
        period_years = period_days / 365.25
        
        if period_years == 0:
            return 0.0
        
        annualized = ((1 + total_return) ** (1 / period_years)) - 1
        return annualized * 100  # Convert back to percentage
    
    def get_portfolio_values(self) -> List[float]:
        """
        Extract portfolio values from history.
        
        Returns:
            List[float]: Portfolio values over time
        """
        return [snapshot.total_value for snapshot in self.portfolio_history]
    
    def get_portfolio_returns(self) -> List[float]:
        """
        Calculate portfolio returns from history.
        
        Returns:
            List[float]: Portfolio returns
        """
        values = self.get_portfolio_values()
        return self.risk_metrics.calculate_returns(values)
    
    def calculate_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio.
        
        Returns:
            float: Sharpe ratio
        """
        returns = self.get_portfolio_returns()
        return self.risk_metrics.calculate_sharpe_ratio(returns)
    
    def calculate_max_drawdown(self) -> float:
        """
        Calculate maximum drawdown percentage.
        
        Returns:
            float: Maximum drawdown as percentage
        """
        values = self.get_portfolio_values()
        max_dd, _, _ = self.risk_metrics.calculate_max_drawdown(values)
        return max_dd
    
    def calculate_volatility(self) -> float:
        """
        Calculate annualized volatility.
        
        Returns:
            float: Volatility as percentage
        """
        returns = self.get_portfolio_returns()
        return self.risk_metrics.calculate_volatility(returns) * 100
    
    def calculate_win_rate(self) -> float:
        """
        Calculate win rate from trade analysis.
        
        Returns:
            float: Win rate as percentage
        """
        if not self.positions:
            return 0.0
        
        self.trade_analyzer.analyze_all_trades(self.positions)
        stats = self.trade_analyzer.get_trade_statistics()
        return stats.get("win_rate_percent", 0.0)
    
    def calculate_profit_factor(self) -> float:
        """
        Calculate profit factor from trade analysis.
        
        Returns:
            float: Profit factor
        """
        if not self.positions:
            return 0.0
        
        self.trade_analyzer.analyze_all_trades(self.positions)
        stats = self.trade_analyzer.get_trade_statistics()
        return stats.get("profit_factor", 0.0)
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive trade statistics.
        
        Returns:
            Dict: Trade statistics
        """
        if not self.positions:
            return {}
        
        self.trade_analyzer.analyze_all_trades(self.positions)
        return self.trade_analyzer.get_trade_statistics()
    
    def calculate_period_length(self) -> float:
        """
        Calculate the analysis period length in years.
        
        Returns:
            float: Period length in years
        """
        if len(self.portfolio_history) < 2:
            return 0.0
        
        start_date = self.portfolio_history[0].timestamp
        end_date = self.portfolio_history[-1].timestamp
        period_days = (end_date - start_date).days
        
        return period_days / 365.25
    
    def generate_performance_report(self) -> PerformanceReport:
        """
        Generate comprehensive performance report.
        
        Returns:
            PerformanceReport: Complete performance analysis
        """
        if not self.portfolio_history:
            # Return empty report if no data
            now = datetime.now()
            start_date = now - timedelta(days=1)  # Ensure start_date < end_date
            return PerformanceReport(
                start_date=start_date,
                end_date=now,
                total_return=0.0,
                annualized_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                avg_trade_return=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                starting_capital=0.0,
                ending_capital=0.0
            )
        
        # Calculate all metrics
        total_return = self.calculate_total_return()
        annualized_return = self.calculate_annualized_return()
        sharpe_ratio = self.calculate_sharpe_ratio()
        max_drawdown = self.calculate_max_drawdown()
        volatility = self.calculate_volatility()
        
        # Trade statistics
        trade_stats = self.get_trade_statistics()
        win_rate = trade_stats.get("win_rate_percent", 0.0)
        profit_factor = trade_stats.get("profit_factor", 0.0)
        total_trades = trade_stats.get("total_trades", 0)
        avg_trade_return = trade_stats.get("average_return_percent", 0.0)
        best_trade = trade_stats.get("largest_win", 0.0)
        worst_trade = trade_stats.get("largest_loss", 0.0)
        total_fees = trade_stats.get("total_fees", 0.0)
        
        # Portfolio values
        starting_capital = self.portfolio_history[0].total_value
        ending_capital = self.portfolio_history[-1].total_value
        
        # Risk metrics
        returns = self.get_portfolio_returns()
        sortino_ratio = self.risk_metrics.calculate_sortino_ratio(returns)
        period_years = self.calculate_period_length()
        calmar_ratio = self.risk_metrics.calculate_calmar_ratio(
            total_return / 100, max_drawdown, period_years
        )
        
        # Calculate average holding period
        avg_holding_period = trade_stats.get("average_holding_period_hours", 0.0) / 24  # Convert to days
        
        return PerformanceReport(
            start_date=self.portfolio_history[0].timestamp,
            end_date=self.portfolio_history[-1].timestamp,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            avg_trade_return=avg_trade_return,
            best_trade=best_trade,
            worst_trade=worst_trade,
            avg_holding_period=avg_holding_period,
            volatility=volatility,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio,
            total_fees=total_fees,
            starting_capital=starting_capital,
            ending_capital=ending_capital
        )
    
    def export_report_to_json(self, report: PerformanceReport, filepath: str) -> bool:
        """
        Export performance report to JSON file.
        
        Args:
            report: PerformanceReport to export
            filepath: Path to save the JSON file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert report to dictionary
            report_dict = {
                "start_date": report.start_date.isoformat(),
                "end_date": report.end_date.isoformat(),
                "total_return": report.total_return,
                "annualized_return": report.annualized_return,
                "sharpe_ratio": report.sharpe_ratio,
                "max_drawdown": report.max_drawdown,
                "win_rate": report.win_rate,
                "profit_factor": report.profit_factor,
                "total_trades": report.total_trades,
                "avg_trade_return": report.avg_trade_return,
                "best_trade": report.best_trade,
                "worst_trade": report.worst_trade,
                "avg_holding_period": report.avg_holding_period,
                "volatility": report.volatility,
                "calmar_ratio": report.calmar_ratio,
                "sortino_ratio": report.sortino_ratio,
                "total_fees": report.total_fees,
                "starting_capital": report.starting_capital,
                "ending_capital": report.ending_capital
            }
            
            # Write to file
            with open(filepath, 'w') as f:
                json.dump(report_dict, f, indent=2)
            
            return True
        except Exception:
            return False
    
    def format_report(self, report: PerformanceReport) -> str:
        """
        Format performance report as readable text.
        
        Args:
            report: PerformanceReport to format
            
        Returns:
            str: Formatted report text
        """
        period_days = (report.end_date - report.start_date).days
        
        report_text = f"""
PERFORMANCE REPORT
==================

Period: {report.start_date.strftime('%Y-%m-%d')} to {report.end_date.strftime('%Y-%m-%d')} ({period_days} days)

RETURNS
-------
Total Return:        {report.total_return:>8.2f}%
Annualized Return:   {report.annualized_return:>8.2f}%
Volatility:          {report.volatility:>8.2f}%

RISK METRICS
------------
Sharpe Ratio:        {report.sharpe_ratio:>8.2f}
Sortino Ratio:       {report.sortino_ratio:>8.2f}
Calmar Ratio:        {report.calmar_ratio:>8.2f}
Max Drawdown:        {report.max_drawdown:>8.2f}%

TRADING STATISTICS
------------------
Total Trades:        {report.total_trades:>8}
Win Rate:            {report.win_rate:>8.2f}%
Profit Factor:       {report.profit_factor:>8.2f}
Avg Trade Return:    {report.avg_trade_return:>8.2f}%
Best Trade:          ${report.best_trade:>8.2f}
Worst Trade:         ${report.worst_trade:>8.2f}
Avg Holding Period:  {report.avg_holding_period:>8.1f} days

CAPITAL
-------
Starting Capital:    $   {report.starting_capital:>10,.2f}
Ending Capital:      $   {report.ending_capital:>10,.2f}
Total Fees:          $   {report.total_fees:>10,.2f}
Net Profit:          $   {report.ending_capital - report.starting_capital:>10,.2f}
"""
        
        return report_text.strip()