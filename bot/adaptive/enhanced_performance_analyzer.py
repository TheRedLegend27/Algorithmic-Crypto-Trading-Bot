"""
Enhanced Performance Analyzer with Advanced Metrics
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging
from dataclasses import dataclass, field

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Advanced metrics
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    
    # Time-based metrics
    best_day: float = 0.0
    worst_day: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    
    # Risk metrics
    var_95: float = 0.0  # Value at Risk 95%
    cvar_95: float = 0.0  # Conditional Value at Risk 95%
    
    timestamp: datetime = field(default_factory=datetime.now)

class EnhancedPerformanceAnalyzer:
    """Enhanced performance analyzer with comprehensive metrics."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Trade history
        self.trades = []
        self.daily_returns = []
        self.portfolio_values = []
        
        # Benchmark data (if available)
        self.benchmark_returns = []
        
        # Performance history
        self.performance_history = []
        
        self.logger.info("Enhanced Performance Analyzer initialized")
    
    def add_trade(self, trade_data: Dict):
        """Add a completed trade for analysis."""
        try:
            trade = {
                'timestamp': trade_data.get('timestamp', datetime.now()),
                'pair': trade_data.get('pair', ''),
                'side': trade_data.get('side', ''),
                'entry_price': trade_data.get('entry_price', 0.0),
                'exit_price': trade_data.get('exit_price', 0.0),
                'quantity': trade_data.get('quantity', 0.0),
                'pnl': trade_data.get('pnl', 0.0),
                'pnl_percent': trade_data.get('pnl_percent', 0.0),
                'duration_minutes': trade_data.get('duration_minutes', 0),
                'fees': trade_data.get('fees', 0.0),
                'strategy': trade_data.get('strategy', 'unknown')
            }
            
            self.trades.append(trade)
            
            # Limit trade history to prevent memory issues
            max_trades = self.config.get('max_trade_history', 10000)
            if len(self.trades) > max_trades:
                self.trades = self.trades[-max_trades:]
            
            self.logger.debug(f"Added trade: {trade['pair']} {trade['side']} PnL: {trade['pnl']:.4f}")
            
        except Exception as e:
            self.logger.error(f"Error adding trade: {e}")
    
    def add_portfolio_value(self, value: float, timestamp: Optional[datetime] = None):
        """Add portfolio value for tracking."""
        try:
            if timestamp is None:
                timestamp = datetime.now()
            
            self.portfolio_values.append({
                'timestamp': timestamp,
                'value': value
            })
            
            # Calculate daily return if we have previous value
            if len(self.portfolio_values) > 1:
                prev_value = self.portfolio_values[-2]['value']
                if prev_value > 0:
                    daily_return = (value - prev_value) / prev_value
                    self.daily_returns.append(daily_return)
            
            # Limit history
            max_values = self.config.get('max_portfolio_history', 10000)
            if len(self.portfolio_values) > max_values:
                self.portfolio_values = self.portfolio_values[-max_values:]
                self.daily_returns = self.daily_returns[-max_values:]
            
        except Exception as e:
            self.logger.error(f"Error adding portfolio value: {e}")
    
    def calculate_metrics(self, period_days: Optional[int] = None) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        try:
            metrics = PerformanceMetrics()
            
            if not self.trades:
                return metrics
            
            # Filter trades by period if specified
            trades = self.trades
            if period_days:
                cutoff_date = datetime.now() - timedelta(days=period_days)
                trades = [t for t in trades if t['timestamp'] >= cutoff_date]
            
            if not trades:
                return metrics
            
            # Basic trade metrics
            metrics.total_trades = len(trades)
            
            pnls = [t['pnl'] for t in trades]
            pnl_percents = [t['pnl_percent'] for t in trades]
            
            winning_trades = [t for t in trades if t['pnl'] > 0]
            losing_trades = [t for t in trades if t['pnl'] < 0]
            
            metrics.winning_trades = len(winning_trades)
            metrics.losing_trades = len(losing_trades)
            
            if metrics.total_trades > 0:
                metrics.win_rate = metrics.winning_trades / metrics.total_trades
            
            # PnL metrics
            if pnls:
                metrics.total_return = sum(pnls)
                
                if winning_trades:
                    metrics.average_win = np.mean([t['pnl'] for t in winning_trades])
                
                if losing_trades:
                    metrics.average_loss = np.mean([t['pnl'] for t in losing_trades])
                
                # Profit factor
                gross_profit = sum(t['pnl'] for t in winning_trades)
                gross_loss = abs(sum(t['pnl'] for t in losing_trades))
                
                if gross_loss > 0:
                    metrics.profit_factor = gross_profit / gross_loss
            
            # Return-based metrics
            if self.daily_returns and len(self.daily_returns) > 1:
                returns = np.array(self.daily_returns)
                
                # Annualized return
                if period_days and period_days > 0:
                    total_return = (1 + returns).prod() - 1
                    metrics.annualized_return = (1 + total_return) ** (365 / period_days) - 1
                else:
                    metrics.annualized_return = np.mean(returns) * 365
                
                # Volatility
                metrics.volatility = np.std(returns) * np.sqrt(365)
                
                # Sharpe ratio
                if metrics.volatility > 0:
                    risk_free_rate = 0.02  # Assume 2% risk-free rate
                    metrics.sharpe_ratio = (metrics.annualized_return - risk_free_rate) / metrics.volatility
                
                # Sortino ratio (downside deviation)
                downside_returns = returns[returns < 0]
                if len(downside_returns) > 0:
                    downside_deviation = np.std(downside_returns) * np.sqrt(365)
                    if downside_deviation > 0:
                        metrics.sortino_ratio = (metrics.annualized_return - risk_free_rate) / downside_deviation
                
                # Maximum drawdown
                if self.portfolio_values:
                    values = [pv['value'] for pv in self.portfolio_values]
                    peak = values[0]
                    max_dd = 0
                    
                    for value in values:
                        if value > peak:
                            peak = value
                        drawdown = (peak - value) / peak if peak > 0 else 0
                        max_dd = max(max_dd, drawdown)
                    
                    metrics.max_drawdown = max_dd
                
                # Calmar ratio
                if metrics.max_drawdown > 0:
                    metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown
                
                # Value at Risk (VaR) and Conditional VaR
                if len(returns) >= 20:  # Need sufficient data
                    metrics.var_95 = np.percentile(returns, 5)
                    cvar_returns = returns[returns <= metrics.var_95]
                    if len(cvar_returns) > 0:
                        metrics.cvar_95 = np.mean(cvar_returns)
                
                # Best and worst days
                metrics.best_day = np.max(returns)
                metrics.worst_day = np.min(returns)
            
            # Consecutive wins/losses
            if trades:
                current_streak = 0
                max_win_streak = 0
                max_loss_streak = 0
                
                for trade in trades:
                    if trade['pnl'] > 0:
                        if current_streak >= 0:
                            current_streak += 1
                        else:
                            current_streak = 1
                        max_win_streak = max(max_win_streak, current_streak)
                    elif trade['pnl'] < 0:
                        if current_streak <= 0:
                            current_streak -= 1
                        else:
                            current_streak = -1
                        max_loss_streak = max(max_loss_streak, abs(current_streak))
                
                metrics.consecutive_wins = max_win_streak
                metrics.consecutive_losses = max_loss_streak
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {e}")
            return PerformanceMetrics()
    
    def analyze_strategy_performance(self) -> Dict[str, PerformanceMetrics]:
        """Analyze performance by strategy."""
        try:
            strategy_trades = {}
            
            # Group trades by strategy
            for trade in self.trades:
                strategy = trade.get('strategy', 'unknown')
                if strategy not in strategy_trades:
                    strategy_trades[strategy] = []
                strategy_trades[strategy].append(trade)
            
            # Calculate metrics for each strategy
            strategy_metrics = {}
            for strategy, trades in strategy_trades.items():
                # Temporarily set trades for calculation
                original_trades = self.trades
                self.trades = trades
                
                metrics = self.calculate_metrics()
                strategy_metrics[strategy] = metrics
                
                # Restore original trades
                self.trades = original_trades
            
            return strategy_metrics
            
        except Exception as e:
            self.logger.error(f"Error analyzing strategy performance: {e}")
            return {}
    
    def generate_performance_report(self) -> Dict:
        """Generate comprehensive performance report."""
        try:
            # Overall metrics
            overall_metrics = self.calculate_metrics()
            
            # Recent performance (last 7 days)
            recent_metrics = self.calculate_metrics(period_days=7)
            
            # Strategy breakdown
            strategy_metrics = self.analyze_strategy_performance()
            
            # Trading pair analysis
            pair_performance = {}
            pairs = set(t['pair'] for t in self.trades)
            
            for pair in pairs:
                pair_trades = [t for t in self.trades if t['pair'] == pair]
                if pair_trades:
                    pair_pnl = sum(t['pnl'] for t in pair_trades)
                    pair_trades_count = len(pair_trades)
                    pair_win_rate = len([t for t in pair_trades if t['pnl'] > 0]) / pair_trades_count
                    
                    pair_performance[pair] = {
                        'total_pnl': pair_pnl,
                        'trade_count': pair_trades_count,
                        'win_rate': pair_win_rate,
                        'avg_pnl': pair_pnl / pair_trades_count
                    }
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'overall_performance': {
                    'total_return': overall_metrics.total_return,
                    'annualized_return': overall_metrics.annualized_return,
                    'sharpe_ratio': overall_metrics.sharpe_ratio,
                    'max_drawdown': overall_metrics.max_drawdown,
                    'win_rate': overall_metrics.win_rate,
                    'profit_factor': overall_metrics.profit_factor,
                    'total_trades': overall_metrics.total_trades
                },
                'recent_performance': {
                    'total_return': recent_metrics.total_return,
                    'win_rate': recent_metrics.win_rate,
                    'total_trades': recent_metrics.total_trades
                },
                'strategy_performance': {
                    strategy: {
                        'total_return': metrics.total_return,
                        'win_rate': metrics.win_rate,
                        'sharpe_ratio': metrics.sharpe_ratio,
                        'total_trades': metrics.total_trades
                    }
                    for strategy, metrics in strategy_metrics.items()
                },
                'pair_performance': pair_performance,
                'risk_metrics': {
                    'max_drawdown': overall_metrics.max_drawdown,
                    'var_95': overall_metrics.var_95,
                    'volatility': overall_metrics.volatility,
                    'consecutive_losses': overall_metrics.consecutive_losses
                }
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating performance report: {e}")
            return {}
    
    def save_performance_data(self, filepath: str):
        """Save performance data to file."""
        try:
            data = {
                'trades': self.trades,
                'portfolio_values': self.portfolio_values,
                'daily_returns': self.daily_returns,
                'performance_history': self.performance_history
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            self.logger.info(f"Performance data saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving performance data: {e}")
    
    def load_performance_data(self, filepath: str):
        """Load performance data from file."""
        try:
            if not os.path.exists(filepath):
                self.logger.info("No saved performance data found")
                return
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.trades = data.get('trades', [])
            self.portfolio_values = data.get('portfolio_values', [])
            self.daily_returns = data.get('daily_returns', [])
            self.performance_history = data.get('performance_history', [])
            
            # Convert timestamp strings back to datetime objects
            for trade in self.trades:
                if isinstance(trade['timestamp'], str):
                    trade['timestamp'] = datetime.fromisoformat(trade['timestamp'])
            
            for pv in self.portfolio_values:
                if isinstance(pv['timestamp'], str):
                    pv['timestamp'] = datetime.fromisoformat(pv['timestamp'])
            
            self.logger.info(f"Performance data loaded from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error loading performance data: {e}")
