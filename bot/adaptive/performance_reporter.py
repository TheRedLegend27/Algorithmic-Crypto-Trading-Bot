"""
Performance reporting and visualization module for the adaptive trading bot.

This module extends the PerformanceAnalyzer with comprehensive reporting capabilities,
including detailed performance attribution, comparison tools, and export functionality.
"""
import logging
import json
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
import warnings
from collections import defaultdict

from .performance_analyzer import PerformanceAnalyzer, TradeRecord, PerformanceDegradationAlert
from .data_models import PerformanceMetrics, AdaptationEvent
from .enums import RegimeType


@dataclass
class PerformanceAttribution:
    """Performance attribution breakdown by various dimensions."""
    strategy_attribution: Dict[str, float] = field(default_factory=dict)
    regime_attribution: Dict[str, float] = field(default_factory=dict)
    time_period_attribution: Dict[str, float] = field(default_factory=dict)
    pair_attribution: Dict[str, float] = field(default_factory=dict)
    total_return: float = 0.0
    attribution_period: str = "30d"
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceComparison:
    """Comparison of performance between different configurations or periods."""
    comparison_id: str
    baseline_config: str
    comparison_config: str
    baseline_metrics: PerformanceMetrics
    comparison_metrics: PerformanceMetrics
    relative_performance: Dict[str, float] = field(default_factory=dict)
    statistical_significance: Dict[str, float] = field(default_factory=dict)
    comparison_period: str = "30d"
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DetailedPerformanceReport:
    """Comprehensive performance report with all analysis components."""
    report_id: str
    generated_at: datetime
    report_period: str
    
    # Summary statistics
    executive_summary: Dict[str, Any] = field(default_factory=dict)
    overall_metrics: Optional[PerformanceMetrics] = None
    
    # Strategy analysis
    strategy_performance: Dict[str, PerformanceMetrics] = field(default_factory=dict)
    strategy_rankings: List[Tuple[str, float]] = field(default_factory=list)
    
    # Attribution analysis
    performance_attribution: Optional[PerformanceAttribution] = None
    
    # Risk analysis
    risk_analysis: Dict[str, Any] = field(default_factory=dict)
    
    # Regime analysis
    regime_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Time series analysis
    time_series_data: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    
    # Alerts and recommendations
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Metadata
    data_quality_metrics: Dict[str, Any] = field(default_factory=dict)
    report_configuration: Dict[str, Any] = field(default_factory=dict)


class PerformanceReporter:
    """
    Enhanced performance reporting and visualization system.
    
    This class extends the PerformanceAnalyzer with comprehensive reporting capabilities,
    including detailed attribution analysis, comparison tools, and export functionality.
    """
    
    def __init__(self, 
                 performance_analyzer: PerformanceAnalyzer,
                 export_directory: str = "reports",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the performance reporter.
        
        Args:
            performance_analyzer: Instance of PerformanceAnalyzer
            export_directory: Directory for exporting reports
            logger: Logger instance
        """
        self.analyzer = performance_analyzer
        self.export_directory = Path(export_directory)
        self.export_directory.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(__name__)
        
        # Report cache
        self.report_cache: Dict[str, DetailedPerformanceReport] = {}
        self.cache_ttl = timedelta(minutes=15)  # Cache reports for 15 minutes
        
        # Configuration
        self.default_periods = ["1d", "7d", "30d", "90d"]
        self.attribution_methods = ["absolute", "relative", "risk_adjusted"]
        
        self.logger.info("PerformanceReporter initialized")
    
    def generate_detailed_report(self, 
                               report_period: str = "30d",
                               include_charts: bool = True,
                               include_attribution: bool = True,
                               strategy_filter: Optional[List[str]] = None) -> DetailedPerformanceReport:
        """
        Generate a comprehensive performance report.
        
        Args:
            report_period: Time period for the report
            include_charts: Whether to include chart data
            include_attribution: Whether to include attribution analysis
            strategy_filter: Optional list of strategies to include
            
        Returns:
            Detailed performance report
        """
        try:
            report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{report_period}"
            
            # Check cache first
            if report_id in self.report_cache:
                cached_report = self.report_cache[report_id]
                if datetime.now() - cached_report.generated_at < self.cache_ttl:
                    self.logger.debug(f"Returning cached report {report_id}")
                    return cached_report
            
            self.logger.info(f"Generating detailed performance report for period {report_period}")
            
            # Initialize report
            report = DetailedPerformanceReport(
                report_id=report_id,
                generated_at=datetime.now(),
                report_period=report_period
            )
            
            # Get strategy list
            strategies = strategy_filter or list(self.analyzer.trade_records.keys())
            
            # Generate executive summary
            report.executive_summary = self._generate_executive_summary(report_period, strategies)
            
            # Calculate overall metrics
            report.overall_metrics = self._calculate_overall_metrics(report_period, strategies)
            
            # Analyze individual strategies
            report.strategy_performance = self._analyze_strategies(report_period, strategies)
            report.strategy_rankings = self._rank_strategies(report.strategy_performance)
            
            # Performance attribution
            if include_attribution:
                report.performance_attribution = self._calculate_performance_attribution(
                    report_period, strategies
                )
            
            # Risk analysis
            report.risk_analysis = self._perform_risk_analysis(report_period, strategies)
            
            # Regime analysis
            report.regime_performance = self._analyze_regime_performance(strategies)
            
            # Time series data
            if include_charts:
                report.time_series_data = self._generate_time_series_data(report_period, strategies)
            
            # Alerts and recommendations
            report.active_alerts = self._get_active_alerts()
            report.recommendations = self._generate_recommendations(report)
            
            # Data quality metrics
            report.data_quality_metrics = self._calculate_data_quality_metrics(strategies)
            
            # Report configuration
            report.report_configuration = {
                "period": report_period,
                "include_charts": include_charts,
                "include_attribution": include_attribution,
                "strategy_filter": strategy_filter,
                "strategies_analyzed": len(strategies),
                "total_trades": sum(len(self.analyzer.trade_records.get(s, [])) for s in strategies)
            }
            
            # Cache the report
            self.report_cache[report_id] = report
            
            self.logger.info(f"Generated detailed performance report {report_id}")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating detailed report: {str(e)}")
            # Return minimal report with error information
            return DetailedPerformanceReport(
                report_id=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                generated_at=datetime.now(),
                report_period=report_period,
                executive_summary={"error": str(e), "report_period": report_period, "strategies_analyzed": 0, "generated_at": datetime.now().isoformat()}
            )
    
    def calculate_performance_attribution(self, 
                                        report_period: str = "30d",
                                        attribution_method: str = "absolute") -> PerformanceAttribution:
        """
        Calculate detailed performance attribution across multiple dimensions.
        
        Args:
            report_period: Time period for attribution analysis
            attribution_method: Method for attribution calculation
            
        Returns:
            Performance attribution breakdown
        """
        try:
            self.logger.info(f"Calculating performance attribution for period {report_period}")
            
            attribution = PerformanceAttribution(
                attribution_period=report_period,
                generated_at=datetime.now()
            )
            
            # Get all trades in the period
            end_time = datetime.now()
            start_time = self.analyzer._parse_timeframe(report_period, end_time)
            
            all_trades = []
            for strategy_name in self.analyzer.trade_records.keys():
                trades = self.analyzer._get_trades_in_timeframe(strategy_name, start_time, end_time)
                for trade in trades:
                    trade.strategy_name = strategy_name  # Ensure strategy name is set
                all_trades.extend(trades)
            
            if not all_trades:
                return attribution
            
            # Calculate total return
            attribution.total_return = sum(trade.pnl for trade in all_trades)
            
            # Strategy attribution
            strategy_returns = defaultdict(float)
            for trade in all_trades:
                strategy_returns[trade.strategy_name] += trade.pnl
            
            if attribution_method == "absolute":
                attribution.strategy_attribution = dict(strategy_returns)
            elif attribution_method == "relative":
                total_return = attribution.total_return
                if total_return != 0:
                    attribution.strategy_attribution = {
                        strategy: returns / total_return 
                        for strategy, returns in strategy_returns.items()
                    }
            
            # Regime attribution
            regime_returns = defaultdict(float)
            for trade in all_trades:
                if trade.regime_type:
                    regime_returns[trade.regime_type.value] += trade.pnl
            
            if attribution_method == "absolute":
                attribution.regime_attribution = dict(regime_returns)
            elif attribution_method == "relative":
                total_return = attribution.total_return
                if total_return != 0:
                    attribution.regime_attribution = {
                        regime: returns / total_return 
                        for regime, returns in regime_returns.items()
                    }
            
            # Time period attribution (by week)
            time_returns = defaultdict(float)
            for trade in all_trades:
                week_key = trade.exit_time.strftime("%Y-W%U")
                time_returns[week_key] += trade.pnl
            
            attribution.time_period_attribution = dict(time_returns)
            
            # Pair attribution
            pair_returns = defaultdict(float)
            for trade in all_trades:
                pair_returns[trade.pair] += trade.pnl
            
            if attribution_method == "absolute":
                attribution.pair_attribution = dict(pair_returns)
            elif attribution_method == "relative":
                total_return = attribution.total_return
                if total_return != 0:
                    attribution.pair_attribution = {
                        pair: returns / total_return 
                        for pair, returns in pair_returns.items()
                    }
            
            self.logger.info("Performance attribution calculation completed")
            return attribution
            
        except Exception as e:
            self.logger.error(f"Error calculating performance attribution: {str(e)}")
            return PerformanceAttribution(
                attribution_period=report_period,
                generated_at=datetime.now()
            )
    
    def compare_performance_configurations(self, 
                                         baseline_config: str,
                                         comparison_config: str,
                                         comparison_period: str = "30d") -> PerformanceComparison:
        """
        Compare performance between different configurations or time periods.
        
        Args:
            baseline_config: Baseline configuration identifier
            comparison_config: Comparison configuration identifier
            comparison_period: Time period for comparison
            
        Returns:
            Performance comparison results
        """
        try:
            self.logger.info(f"Comparing configurations: {baseline_config} vs {comparison_config}")
            
            comparison_id = f"comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # For this implementation, we'll compare different time periods
            # In a full implementation, this could compare different strategy configurations
            
            # Get baseline metrics (e.g., previous period)
            baseline_metrics = self._get_period_metrics(baseline_config, comparison_period)
            
            # Get comparison metrics (e.g., current period)
            comparison_metrics = self._get_period_metrics(comparison_config, comparison_period)
            
            # Calculate relative performance
            relative_performance = self._calculate_relative_performance(
                baseline_metrics, comparison_metrics
            )
            
            # Calculate statistical significance
            statistical_significance = self._calculate_statistical_significance(
                baseline_config, comparison_config, comparison_period
            )
            
            comparison = PerformanceComparison(
                comparison_id=comparison_id,
                baseline_config=baseline_config,
                comparison_config=comparison_config,
                baseline_metrics=baseline_metrics,
                comparison_metrics=comparison_metrics,
                relative_performance=relative_performance,
                statistical_significance=statistical_significance,
                comparison_period=comparison_period,
                generated_at=datetime.now()
            )
            
            self.logger.info(f"Performance comparison completed: {comparison_id}")
            return comparison
            
        except Exception as e:
            self.logger.error(f"Error comparing performance configurations: {str(e)}")
            # Return empty comparison with error info
            return PerformanceComparison(
                comparison_id=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                baseline_config=baseline_config,
                comparison_config=comparison_config,
                baseline_metrics=PerformanceMetrics(
                    total_return=0, annualized_return=0, excess_return=0,
                    sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
                    max_drawdown=0, volatility=0, downside_deviation=0,
                    win_rate=0, profit_factor=0, avg_trade_duration=timedelta(),
                    trades_count=0, avg_win=0, avg_loss=0
                ),
                comparison_metrics=PerformanceMetrics(
                    total_return=0, annualized_return=0, excess_return=0,
                    sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
                    max_drawdown=0, volatility=0, downside_deviation=0,
                    win_rate=0, profit_factor=0, avg_trade_duration=timedelta(),
                    trades_count=0, avg_win=0, avg_loss=0
                ),
                comparison_period=comparison_period
            )
    
    def export_report_json(self, report: DetailedPerformanceReport, filename: Optional[str] = None) -> str:
        """
        Export performance report to JSON format.
        
        Args:
            report: Performance report to export
            filename: Optional filename (auto-generated if not provided)
            
        Returns:
            Path to exported file
        """
        try:
            if filename is None:
                filename = f"performance_report_{report.report_id}.json"
            
            filepath = self.export_directory / filename
            
            # Convert report to dictionary, handling datetime and timedelta objects
            report_dict = self._serialize_report_for_export(report)
            
            with open(filepath, 'w') as f:
                json.dump(report_dict, f, indent=2, default=str)
            
            self.logger.info(f"Exported performance report to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error exporting report to JSON: {str(e)}")
            raise
    
    def export_report_csv(self, report: DetailedPerformanceReport, filename: Optional[str] = None) -> str:
        """
        Export performance report to CSV format.
        
        Args:
            report: Performance report to export
            filename: Optional filename (auto-generated if not provided)
            
        Returns:
            Path to exported file
        """
        try:
            if filename is None:
                filename = f"performance_report_{report.report_id}.csv"
            
            filepath = self.export_directory / filename
            
            # Create CSV data from report
            csv_data = self._convert_report_to_csv_data(report)
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(['Metric', 'Value', 'Category', 'Strategy'])
                
                # Write data
                for row in csv_data:
                    writer.writerow(row)
            
            self.logger.info(f"Exported performance report to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error exporting report to CSV: {str(e)}")
            raise
    
    def export_attribution_analysis(self, 
                                  attribution: PerformanceAttribution, 
                                  filename: Optional[str] = None) -> str:
        """
        Export performance attribution analysis to JSON.
        
        Args:
            attribution: Performance attribution to export
            filename: Optional filename
            
        Returns:
            Path to exported file
        """
        try:
            if filename is None:
                timestamp = attribution.generated_at.strftime('%Y%m%d_%H%M%S')
                filename = f"attribution_analysis_{timestamp}.json"
            
            filepath = self.export_directory / filename
            
            # Convert attribution to dictionary
            attribution_dict = asdict(attribution)
            
            # Handle datetime serialization
            attribution_dict['generated_at'] = attribution.generated_at.isoformat()
            
            with open(filepath, 'w') as f:
                json.dump(attribution_dict, f, indent=2, default=str)
            
            self.logger.info(f"Exported attribution analysis to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error exporting attribution analysis: {str(e)}")
            raise
    
    def export_comparison_analysis(self, 
                                 comparison: PerformanceComparison, 
                                 filename: Optional[str] = None) -> str:
        """
        Export performance comparison analysis to JSON.
        
        Args:
            comparison: Performance comparison to export
            filename: Optional filename
            
        Returns:
            Path to exported file
        """
        try:
            if filename is None:
                filename = f"comparison_analysis_{comparison.comparison_id}.json"
            
            filepath = self.export_directory / filename
            
            # Convert comparison to dictionary
            comparison_dict = self._serialize_comparison_for_export(comparison)
            
            with open(filepath, 'w') as f:
                json.dump(comparison_dict, f, indent=2, default=str)
            
            self.logger.info(f"Exported comparison analysis to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error exporting comparison analysis: {str(e)}")
            raise
    
    def generate_visualization_data(self, report: DetailedPerformanceReport) -> Dict[str, Any]:
        """
        Generate data optimized for visualization libraries.
        
        Args:
            report: Performance report
            
        Returns:
            Dictionary with visualization-ready data
        """
        try:
            viz_data = {
                'charts': {},
                'tables': {},
                'metrics': {}
            }
            
            # Strategy performance chart data
            if report.strategy_performance:
                viz_data['charts']['strategy_performance'] = {
                    'type': 'bar',
                    'data': {
                        'labels': list(report.strategy_performance.keys()),
                        'datasets': [{
                            'label': 'Total Return',
                            'data': [metrics.total_return for metrics in report.strategy_performance.values()],
                            'backgroundColor': 'rgba(54, 162, 235, 0.6)'
                        }, {
                            'label': 'Sharpe Ratio',
                            'data': [metrics.sharpe_ratio for metrics in report.strategy_performance.values()],
                            'backgroundColor': 'rgba(255, 99, 132, 0.6)'
                        }]
                    }
                }
            
            # Time series data
            if report.time_series_data:
                viz_data['charts']['cumulative_returns'] = {
                    'type': 'line',
                    'data': report.time_series_data.get('cumulative_returns', [])
                }
            
            # Attribution pie chart
            if report.performance_attribution:
                viz_data['charts']['strategy_attribution'] = {
                    'type': 'pie',
                    'data': {
                        'labels': list(report.performance_attribution.strategy_attribution.keys()),
                        'datasets': [{
                            'data': list(report.performance_attribution.strategy_attribution.values()),
                            'backgroundColor': [
                                'rgba(255, 99, 132, 0.6)',
                                'rgba(54, 162, 235, 0.6)',
                                'rgba(255, 205, 86, 0.6)',
                                'rgba(75, 192, 192, 0.6)',
                                'rgba(153, 102, 255, 0.6)'
                            ]
                        }]
                    }
                }
            
            # Risk metrics table
            if report.risk_analysis:
                viz_data['tables']['risk_metrics'] = {
                    'headers': ['Metric', 'Value', 'Status'],
                    'rows': [
                        ['Portfolio VaR', f"{report.risk_analysis.get('portfolio_var', 0):.2%}", 'Normal'],
                        ['Max Drawdown', f"{report.risk_analysis.get('max_drawdown', 0):.2%}", 'Normal'],
                        ['Volatility', f"{report.risk_analysis.get('volatility', 0):.2%}", 'Normal']
                    ]
                }
            
            # Key metrics summary
            if report.overall_metrics:
                viz_data['metrics']['key_metrics'] = {
                    'total_return': report.overall_metrics.total_return,
                    'sharpe_ratio': report.overall_metrics.sharpe_ratio,
                    'max_drawdown': report.overall_metrics.max_drawdown,
                    'win_rate': report.overall_metrics.win_rate,
                    'trades_count': report.overall_metrics.trades_count
                }
            
            return viz_data
            
        except Exception as e:
            self.logger.error(f"Error generating visualization data: {str(e)}")
            return {'charts': {}, 'tables': {}, 'metrics': {}}
    
    def _generate_executive_summary(self, period: str, strategies: List[str]) -> Dict[str, Any]:
        """Generate executive summary for the report."""
        try:
            summary = {}
            
            # Overall performance
            overall_metrics = self._calculate_overall_metrics(period, strategies)
            if overall_metrics:
                summary['total_return'] = overall_metrics.total_return
                summary['sharpe_ratio'] = overall_metrics.sharpe_ratio
                summary['max_drawdown'] = overall_metrics.max_drawdown
                summary['win_rate'] = overall_metrics.win_rate
                summary['total_trades'] = overall_metrics.trades_count
            
            # Best and worst performing strategies
            strategy_performance = self._analyze_strategies(period, strategies)
            if strategy_performance:
                best_strategy = max(strategy_performance.items(), key=lambda x: x[1].total_return)
                worst_strategy = min(strategy_performance.items(), key=lambda x: x[1].total_return)
                
                summary['best_strategy'] = {
                    'name': best_strategy[0],
                    'return': best_strategy[1].total_return
                }
                summary['worst_strategy'] = {
                    'name': worst_strategy[0],
                    'return': worst_strategy[1].total_return
                }
            
            # Active alerts count
            alerts = self.analyzer.degradation_alerts
            summary['active_alerts'] = len([a for a in alerts if not a.recovery_detected])
            
            # Period information
            summary['report_period'] = period
            summary['strategies_analyzed'] = len(strategies)
            summary['generated_at'] = datetime.now().isoformat()
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating executive summary: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_overall_metrics(self, period: str, strategies: List[str]) -> Optional[PerformanceMetrics]:
        """Calculate overall portfolio metrics across all strategies."""
        try:
            # Collect all trades from all strategies
            end_time = datetime.now()
            start_time = self.analyzer._parse_timeframe(period, end_time)
            
            all_trades = []
            for strategy_name in strategies:
                trades = self.analyzer._get_trades_in_timeframe(strategy_name, start_time, end_time)
                all_trades.extend(trades)
            
            if not all_trades:
                return None
            
            # Calculate comprehensive metrics using the analyzer's method
            return self.analyzer._calculate_comprehensive_metrics(all_trades, period)
            
        except Exception as e:
            self.logger.error(f"Error calculating overall metrics: {str(e)}")
            # Re-raise the exception so it can be caught by the main report generation
            raise
    
    def _analyze_strategies(self, period: str, strategies: List[str]) -> Dict[str, PerformanceMetrics]:
        """Analyze performance of individual strategies."""
        strategy_performance = {}
        
        for strategy_name in strategies:
            try:
                metrics = self.analyzer.analyze_strategy_performance(strategy_name, period)
                strategy_performance[strategy_name] = metrics
            except Exception as e:
                self.logger.error(f"Error analyzing strategy {strategy_name}: {str(e)}")
        
        return strategy_performance
    
    def _rank_strategies(self, strategy_performance: Dict[str, PerformanceMetrics]) -> List[Tuple[str, float]]:
        """Rank strategies by Sharpe ratio."""
        try:
            rankings = [
                (strategy, metrics.sharpe_ratio) 
                for strategy, metrics in strategy_performance.items()
            ]
            return sorted(rankings, key=lambda x: x[1], reverse=True)
        except Exception as e:
            self.logger.error(f"Error ranking strategies: {str(e)}")
            return []
    
    def _calculate_performance_attribution(self, period: str, strategies: List[str]) -> PerformanceAttribution:
        """Calculate performance attribution for the report."""
        return self.calculate_performance_attribution(period, "absolute")
    
    def _perform_risk_analysis(self, period: str, strategies: List[str]) -> Dict[str, Any]:
        """Perform comprehensive risk analysis."""
        try:
            risk_analysis = {}
            
            # Calculate portfolio-level risk metrics
            overall_metrics = self._calculate_overall_metrics(period, strategies)
            if overall_metrics:
                risk_analysis['max_drawdown'] = overall_metrics.max_drawdown
                risk_analysis['volatility'] = overall_metrics.volatility
                risk_analysis['downside_deviation'] = overall_metrics.downside_deviation
                
                # Calculate VaR (Value at Risk) - simplified 95% VaR
                end_time = datetime.now()
                start_time = self.analyzer._parse_timeframe(period, end_time)
                
                all_trades = []
                for strategy_name in strategies:
                    trades = self.analyzer._get_trades_in_timeframe(strategy_name, start_time, end_time)
                    all_trades.extend(trades)
                
                if all_trades:
                    returns = [trade.pnl_percentage / 100 for trade in all_trades]
                    if returns:
                        var_95 = np.percentile(returns, 5)  # 5th percentile for 95% VaR
                        risk_analysis['portfolio_var'] = var_95
            
            # Strategy-specific risk metrics
            strategy_risks = {}
            for strategy_name in strategies:
                try:
                    metrics = self.analyzer.analyze_strategy_performance(strategy_name, period)
                    strategy_risks[strategy_name] = {
                        'max_drawdown': metrics.max_drawdown,
                        'volatility': metrics.volatility,
                        'sharpe_ratio': metrics.sharpe_ratio
                    }
                except Exception as e:
                    self.logger.error(f"Error calculating risk for strategy {strategy_name}: {str(e)}")
            
            risk_analysis['strategy_risks'] = strategy_risks
            
            return risk_analysis
            
        except Exception as e:
            self.logger.error(f"Error performing risk analysis: {str(e)}")
            return {}
    
    def _analyze_regime_performance(self, strategies: List[str]) -> Dict[str, Dict[str, float]]:
        """Analyze performance by market regime."""
        try:
            regime_performance = {}
            
            for regime_type in RegimeType:
                regime_perf = self.analyzer.get_regime_performance(regime_type)
                if regime_perf:
                    regime_performance[regime_type.value] = regime_perf
            
            return regime_performance
            
        except Exception as e:
            self.logger.error(f"Error analyzing regime performance: {str(e)}")
            return {}
    
    def _generate_time_series_data(self, period: str, strategies: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Generate time series data for charts."""
        try:
            time_series = {}
            
            # Cumulative returns over time
            end_time = datetime.now()
            start_time = self.analyzer._parse_timeframe(period, end_time)
            
            all_trades = []
            for strategy_name in strategies:
                trades = self.analyzer._get_trades_in_timeframe(strategy_name, start_time, end_time)
                all_trades.extend(trades)
            
            if all_trades:
                # Sort trades by time
                sorted_trades = sorted(all_trades, key=lambda x: x.exit_time)
                
                cumulative_returns = []
                cumulative_pnl = 0
                
                for trade in sorted_trades:
                    cumulative_pnl += trade.pnl
                    cumulative_returns.append({
                        'timestamp': trade.exit_time.isoformat(),
                        'cumulative_pnl': cumulative_pnl,
                        'trade_pnl': trade.pnl,
                        'strategy': trade.strategy_name
                    })
                
                time_series['cumulative_returns'] = cumulative_returns
            
            return time_series
            
        except Exception as e:
            self.logger.error(f"Error generating time series data: {str(e)}")
            return {}
    
    def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active performance alerts."""
        try:
            active_alerts = []
            
            for alert in self.analyzer.degradation_alerts:
                if not alert.recovery_detected:
                    active_alerts.append(alert.to_dict())
            
            return active_alerts
            
        except Exception as e:
            self.logger.error(f"Error getting active alerts: {str(e)}")
            return []
    
    def _generate_recommendations(self, report: DetailedPerformanceReport) -> List[str]:
        """Generate recommendations based on the report."""
        recommendations = []
        
        try:
            # Check overall performance
            if report.overall_metrics:
                if report.overall_metrics.sharpe_ratio < 0.5:
                    recommendations.append("Overall Sharpe ratio is below 0.5 - consider reviewing strategy allocation")
                
                if report.overall_metrics.max_drawdown > 0.15:
                    recommendations.append("Maximum drawdown exceeds 15% - review risk management parameters")
                
                if report.overall_metrics.win_rate < 0.4:
                    recommendations.append("Win rate is below 40% - analyze entry conditions across strategies")
            
            # Check strategy performance
            if report.strategy_performance:
                underperforming = [
                    name for name, metrics in report.strategy_performance.items()
                    if metrics.sharpe_ratio < 0
                ]
                
                if underperforming:
                    recommendations.append(f"Strategies with negative Sharpe ratio: {', '.join(underperforming)}")
            
            # Check active alerts
            if len(report.active_alerts) > 0:
                recommendations.append(f"{len(report.active_alerts)} active performance alerts require attention")
            
            # Attribution-based recommendations
            if report.performance_attribution:
                # Find strategies contributing negatively
                negative_contributors = [
                    strategy for strategy, contribution in report.performance_attribution.strategy_attribution.items()
                    if contribution < 0
                ]
                
                if negative_contributors:
                    recommendations.append(f"Consider reducing allocation to negative contributors: {', '.join(negative_contributors)}")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {str(e)}")
            return ["Error generating recommendations - please review manually"]
    
    def _calculate_data_quality_metrics(self, strategies: List[str]) -> Dict[str, Any]:
        """Calculate data quality metrics for the report."""
        try:
            quality_metrics = {}
            
            total_trades = 0
            strategies_with_data = 0
            
            for strategy_name in strategies:
                trades = self.analyzer.trade_records.get(strategy_name, [])
                if trades:
                    strategies_with_data += 1
                    total_trades += len(trades)
            
            quality_metrics['total_trades'] = total_trades
            quality_metrics['strategies_with_data'] = strategies_with_data
            quality_metrics['data_coverage'] = strategies_with_data / len(strategies) if strategies else 0
            quality_metrics['avg_trades_per_strategy'] = total_trades / strategies_with_data if strategies_with_data > 0 else 0
            
            return quality_metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating data quality metrics: {str(e)}")
            return {}
    
    def _get_period_metrics(self, config: str, period: str) -> PerformanceMetrics:
        """Get metrics for a specific configuration/period."""
        # This is a simplified implementation
        # In practice, this would retrieve metrics for different configurations
        try:
            # For now, treat config as a time offset
            if config == "previous":
                # Get metrics for previous period
                end_time = datetime.now() - self.analyzer._parse_timeframe_to_delta(period)
                start_time = end_time - self.analyzer._parse_timeframe_to_delta(period)
            else:
                # Current period
                end_time = datetime.now()
                start_time = end_time - self.analyzer._parse_timeframe_to_delta(period)
            
            # Collect trades from all strategies in the period
            all_trades = []
            for strategy_trades in self.analyzer.trade_records.values():
                period_trades = [
                    trade for trade in strategy_trades
                    if start_time <= trade.exit_time <= end_time
                ]
                all_trades.extend(period_trades)
            
            if all_trades:
                return self.analyzer._calculate_comprehensive_metrics(all_trades, period)
            else:
                return self.analyzer._create_empty_metrics("", period)
                
        except Exception as e:
            self.logger.error(f"Error getting period metrics: {str(e)}")
            return self.analyzer._create_empty_metrics("", period)
    
    def _calculate_relative_performance(self, 
                                      baseline: PerformanceMetrics, 
                                      comparison: PerformanceMetrics) -> Dict[str, float]:
        """Calculate relative performance between two metrics."""
        try:
            relative = {}
            
            # Calculate relative changes
            if baseline.total_return != 0:
                relative['total_return_change'] = (comparison.total_return - baseline.total_return) / abs(baseline.total_return)
            else:
                relative['total_return_change'] = 0
            
            relative['sharpe_ratio_change'] = comparison.sharpe_ratio - baseline.sharpe_ratio
            relative['win_rate_change'] = comparison.win_rate - baseline.win_rate
            relative['max_drawdown_change'] = comparison.max_drawdown - baseline.max_drawdown
            
            return relative
            
        except Exception as e:
            self.logger.error(f"Error calculating relative performance: {str(e)}")
            return {}
    
    def _calculate_statistical_significance(self, 
                                          baseline_config: str, 
                                          comparison_config: str, 
                                          period: str) -> Dict[str, float]:
        """Calculate statistical significance of performance differences."""
        try:
            # This is a simplified implementation
            # In practice, you would perform statistical tests (t-test, etc.)
            
            significance = {}
            
            # Placeholder values - in practice, calculate actual p-values
            significance['return_difference_p_value'] = 0.05
            significance['sharpe_difference_p_value'] = 0.10
            significance['win_rate_difference_p_value'] = 0.15
            
            return significance
            
        except Exception as e:
            self.logger.error(f"Error calculating statistical significance: {str(e)}")
            return {}
    
    def _serialize_report_for_export(self, report: DetailedPerformanceReport) -> Dict[str, Any]:
        """Serialize report for JSON export, handling special types."""
        try:
            report_dict = asdict(report)
            
            # Handle datetime objects
            report_dict['generated_at'] = report.generated_at.isoformat()
            
            # Handle PerformanceMetrics objects
            if report.overall_metrics:
                metrics_dict = asdict(report.overall_metrics)
                metrics_dict['last_updated'] = report.overall_metrics.last_updated.isoformat()
                metrics_dict['avg_trade_duration'] = str(report.overall_metrics.avg_trade_duration)
                metrics_dict['measurement_period'] = str(report.overall_metrics.measurement_period)
                
                # Handle RegimeType enum keys in regime_performance
                if 'regime_performance' in metrics_dict:
                    regime_perf = {}
                    for regime, value in metrics_dict['regime_performance'].items():
                        if hasattr(regime, 'value'):
                            regime_perf[regime.value] = value
                        else:
                            regime_perf[str(regime)] = value
                    metrics_dict['regime_performance'] = regime_perf
                
                report_dict['overall_metrics'] = metrics_dict
            
            # Handle strategy performance metrics
            for strategy, metrics in report.strategy_performance.items():
                metrics_dict = asdict(metrics)
                metrics_dict['last_updated'] = metrics.last_updated.isoformat()
                metrics_dict['avg_trade_duration'] = str(metrics.avg_trade_duration)
                metrics_dict['measurement_period'] = str(metrics.measurement_period)
                
                # Handle RegimeType enum keys in regime_performance
                if 'regime_performance' in metrics_dict:
                    regime_perf = {}
                    for regime, value in metrics_dict['regime_performance'].items():
                        if hasattr(regime, 'value'):
                            regime_perf[regime.value] = value
                        else:
                            regime_perf[str(regime)] = value
                    metrics_dict['regime_performance'] = regime_perf
                
                report_dict['strategy_performance'][strategy] = metrics_dict
            
            # Handle performance attribution
            if report.performance_attribution:
                attr_dict = asdict(report.performance_attribution)
                attr_dict['generated_at'] = report.performance_attribution.generated_at.isoformat()
                report_dict['performance_attribution'] = attr_dict
            
            return report_dict
            
        except Exception as e:
            self.logger.error(f"Error serializing report: {str(e)}")
            return {'error': str(e)}
    
    def _serialize_comparison_for_export(self, comparison: PerformanceComparison) -> Dict[str, Any]:
        """Serialize comparison for JSON export."""
        try:
            comp_dict = asdict(comparison)
            
            # Handle datetime objects
            comp_dict['generated_at'] = comparison.generated_at.isoformat()
            
            # Handle PerformanceMetrics objects
            baseline_dict = asdict(comparison.baseline_metrics)
            baseline_dict['last_updated'] = comparison.baseline_metrics.last_updated.isoformat()
            baseline_dict['avg_trade_duration'] = str(comparison.baseline_metrics.avg_trade_duration)
            baseline_dict['measurement_period'] = str(comparison.baseline_metrics.measurement_period)
            
            # Handle RegimeType enum keys in regime_performance
            if 'regime_performance' in baseline_dict:
                regime_perf = {}
                for regime, value in baseline_dict['regime_performance'].items():
                    if hasattr(regime, 'value'):
                        regime_perf[regime.value] = value
                    else:
                        regime_perf[str(regime)] = value
                baseline_dict['regime_performance'] = regime_perf
            
            comp_dict['baseline_metrics'] = baseline_dict
            
            comparison_dict = asdict(comparison.comparison_metrics)
            comparison_dict['last_updated'] = comparison.comparison_metrics.last_updated.isoformat()
            comparison_dict['avg_trade_duration'] = str(comparison.comparison_metrics.avg_trade_duration)
            comparison_dict['measurement_period'] = str(comparison.comparison_metrics.measurement_period)
            
            # Handle RegimeType enum keys in regime_performance
            if 'regime_performance' in comparison_dict:
                regime_perf = {}
                for regime, value in comparison_dict['regime_performance'].items():
                    if hasattr(regime, 'value'):
                        regime_perf[regime.value] = value
                    else:
                        regime_perf[str(regime)] = value
                comparison_dict['regime_performance'] = regime_perf
            
            comp_dict['comparison_metrics'] = comparison_dict
            
            return comp_dict
            
        except Exception as e:
            self.logger.error(f"Error serializing comparison: {str(e)}")
            return {'error': str(e)}
    
    def _convert_report_to_csv_data(self, report: DetailedPerformanceReport) -> List[List[str]]:
        """Convert report to CSV-friendly data structure."""
        try:
            csv_data = []
            
            # Overall metrics
            if report.overall_metrics:
                metrics = report.overall_metrics
                csv_data.extend([
                    ['Total Return', f"{metrics.total_return:.4f}", 'Overall', 'All'],
                    ['Sharpe Ratio', f"{metrics.sharpe_ratio:.4f}", 'Overall', 'All'],
                    ['Max Drawdown', f"{metrics.max_drawdown:.4f}", 'Overall', 'All'],
                    ['Win Rate', f"{metrics.win_rate:.4f}", 'Overall', 'All'],
                    ['Trades Count', str(metrics.trades_count), 'Overall', 'All']
                ])
            
            # Strategy metrics
            for strategy_name, metrics in report.strategy_performance.items():
                csv_data.extend([
                    ['Total Return', f"{metrics.total_return:.4f}", 'Strategy', strategy_name],
                    ['Sharpe Ratio', f"{metrics.sharpe_ratio:.4f}", 'Strategy', strategy_name],
                    ['Max Drawdown', f"{metrics.max_drawdown:.4f}", 'Strategy', strategy_name],
                    ['Win Rate', f"{metrics.win_rate:.4f}", 'Strategy', strategy_name],
                    ['Trades Count', str(metrics.trades_count), 'Strategy', strategy_name]
                ])
            
            # Attribution data
            if report.performance_attribution:
                for strategy, contribution in report.performance_attribution.strategy_attribution.items():
                    csv_data.append(['Attribution', f"{contribution:.4f}", 'Attribution', strategy])
            
            return csv_data
            
        except Exception as e:
            self.logger.error(f"Error converting report to CSV: {str(e)}")
            return [['Error', str(e), 'Error', 'Error']]