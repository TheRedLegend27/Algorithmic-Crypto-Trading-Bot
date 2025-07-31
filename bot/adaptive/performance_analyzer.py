"""
Performance analyzer for the adaptive trading bot system.

This module implements comprehensive performance metrics calculation, degradation detection,
and reporting functionality for strategies and the overall trading system.
"""
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import warnings
from scipy import stats
from enum import Enum

from .interfaces import PerformanceAnalyzerInterface
from .data_models import PerformanceMetrics, AdaptationEvent
from .enums import RegimeType, PerformanceMetricType


@dataclass
class TradeRecord:
    """Represents a completed trade for performance analysis."""
    trade_id: str
    strategy_name: str
    pair: str
    side: str  # 'buy' or 'sell'
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percentage: float
    regime_type: Optional[RegimeType] = None
    fees: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> timedelta:
        """Get trade duration."""
        return self.exit_time - self.entry_time
    
    @property
    def is_winning_trade(self) -> bool:
        """Check if this is a winning trade."""
        return self.pnl > 0


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of performance alerts."""
    PERFORMANCE_DEGRADATION = "performance_degradation"
    PERFORMANCE_RECOVERY = "performance_recovery"
    STATISTICAL_ANOMALY = "statistical_anomaly"
    BENCHMARK_UNDERPERFORMANCE = "benchmark_underperformance"
    DRAWDOWN_THRESHOLD = "drawdown_threshold"
    WIN_RATE_DECLINE = "win_rate_decline"


@dataclass
class PerformanceDegradationAlert:
    """Alert for performance degradation detection."""
    strategy_name: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    current_value: float
    threshold_value: float
    detection_time: datetime
    metric_name: str
    statistical_significance: Optional[float] = None
    p_value: Optional[float] = None
    suggested_actions: List[str] = field(default_factory=list)
    recovery_detected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            'strategy_name': self.strategy_name,
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'message': self.message,
            'current_value': self.current_value,
            'threshold_value': self.threshold_value,
            'detection_time': self.detection_time.isoformat(),
            'metric_name': self.metric_name,
            'statistical_significance': self.statistical_significance,
            'p_value': self.p_value,
            'suggested_actions': self.suggested_actions,
            'recovery_detected': self.recovery_detected
        }


@dataclass
class PerformanceBenchmark:
    """Benchmark data for performance comparison."""
    strategy_name: str
    metric_name: str
    benchmark_value: float
    benchmark_period: timedelta
    calculation_method: str  # 'rolling_average', 'exponential_average', 'percentile'
    confidence_interval: Tuple[float, float]
    last_updated: datetime = field(default_factory=datetime.now)
    sample_size: int = 0
    
    def is_underperforming(self, current_value: float, significance_level: float = 0.05) -> bool:
        """Check if current value is significantly underperforming benchmark."""
        lower_bound, upper_bound = self.confidence_interval
        return current_value < lower_bound


@dataclass
class StatisticalTest:
    """Result of a statistical test for performance degradation."""
    test_name: str
    statistic: float
    p_value: float
    critical_value: float
    is_significant: bool
    confidence_level: float
    interpretation: str


class PerformanceAnalyzer(PerformanceAnalyzerInterface):
    """
    Comprehensive performance analyzer for adaptive trading strategies.
    
    This class calculates various performance metrics, detects performance degradation,
    and generates detailed reports for strategy evaluation and optimization.
    """
    
    def __init__(self, 
                 risk_free_rate: float = 0.02,  # 2% annual risk-free rate
                 benchmark_return: float = 0.0,  # Benchmark return for comparison
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the performance analyzer.
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe ratio calculation
            benchmark_return: Benchmark return for excess return calculation
            logger: Logger instance
        """
        self.risk_free_rate = risk_free_rate
        self.benchmark_return = benchmark_return
        self.logger = logger or logging.getLogger(__name__)
        
        # Data storage
        self.trade_records: Dict[str, List[TradeRecord]] = defaultdict(list)
        self.performance_history: Dict[str, List[PerformanceMetrics]] = defaultdict(list)
        self.degradation_alerts: List[PerformanceDegradationAlert] = []
        self.performance_benchmarks: Dict[str, Dict[str, PerformanceBenchmark]] = defaultdict(dict)
        
        # Configuration
        self.degradation_thresholds = {
            'sharpe_ratio_decline': -0.5,  # 50% decline in Sharpe ratio
            'max_drawdown_increase': 0.1,  # 10% increase in max drawdown
            'win_rate_decline': -0.2,  # 20% decline in win rate
            'return_decline': -0.3,  # 30% decline in returns
            'profit_factor_decline': -0.3,  # 30% decline in profit factor
        }
        
        # Statistical test configuration
        self.statistical_config = {
            'significance_level': 0.05,  # 5% significance level
            'min_sample_size': 10,  # Minimum trades for statistical tests
            'rolling_window_size': 20,  # Rolling window for comparisons
            'benchmark_lookback_days': 90,  # Days to look back for benchmark calculation
        }
        
        # Performance tracking windows
        self.short_window = timedelta(days=7)
        self.medium_window = timedelta(days=30)
        self.long_window = timedelta(days=90)
        
        self.logger.info("PerformanceAnalyzer initialized")
    
    def add_trade_record(self, trade_record: TradeRecord) -> None:
        """
        Add a trade record for performance analysis.
        
        Args:
            trade_record: Completed trade record
        """
        try:
            self.trade_records[trade_record.strategy_name].append(trade_record)
            self.logger.debug(f"Added trade record for strategy {trade_record.strategy_name}")
        except Exception as e:
            self.logger.error(f"Error adding trade record: {str(e)}")
    
    def analyze_strategy_performance(self, 
                                   strategy_name: str, 
                                   timeframe: str = "24h") -> PerformanceMetrics:
        """
        Analyze performance of a specific strategy.
        
        Args:
            strategy_name: Name of the strategy to analyze
            timeframe: Time window for analysis (e.g., "24h", "7d", "30d")
            
        Returns:
            PerformanceMetrics object with comprehensive metrics
        """
        try:
            # Parse timeframe
            end_time = datetime.now()
            start_time = self._parse_timeframe(timeframe, end_time)
            
            # Get trades within timeframe
            trades = self._get_trades_in_timeframe(strategy_name, start_time, end_time)
            
            if not trades:
                return self._create_empty_metrics(strategy_name, timeframe)
            
            # Calculate all performance metrics
            metrics = self._calculate_comprehensive_metrics(trades, timeframe)
            
            # Store metrics in history
            self.performance_history[strategy_name].append(metrics)
            
            self.logger.info(f"Analyzed performance for {strategy_name} over {timeframe}")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error analyzing strategy performance: {str(e)}")
            return self._create_empty_metrics(strategy_name, timeframe)
    
    def calculate_risk_adjusted_returns(self, strategy_name: str) -> Dict[str, float]:
        """
        Calculate risk-adjusted return metrics.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dictionary of risk-adjusted metrics
        """
        try:
            trades = self.trade_records.get(strategy_name, [])
            if not trades:
                return {}
            
            # Calculate returns series
            returns = [trade.pnl_percentage / 100 for trade in trades]
            returns_series = pd.Series(returns)
            
            # Calculate metrics
            total_return = sum(returns)
            volatility = returns_series.std() * np.sqrt(252)  # Annualized volatility
            
            # Sharpe ratio
            excess_return = total_return - self.risk_free_rate
            sharpe_ratio = excess_return / volatility if volatility > 0 else 0
            
            # Sortino ratio (using downside deviation)
            negative_returns = returns_series[returns_series < 0]
            downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
            sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
            
            # Calmar ratio
            max_drawdown = self._calculate_max_drawdown(trades)
            calmar_ratio = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            return {
                'sharpe_ratio': sharpe_ratio,
                'sortino_ratio': sortino_ratio,
                'calmar_ratio': calmar_ratio,
                'volatility': volatility,
                'excess_return': excess_return
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating risk-adjusted returns: {str(e)}")
            return {}
    
    def detect_performance_degradation(self, threshold: float = -0.1) -> List[PerformanceDegradationAlert]:
        """
        Detect strategies with performance degradation using statistical tests.
        
        Args:
            threshold: Performance decline threshold (negative value)
            
        Returns:
            List of performance degradation alerts
        """
        alerts = []
        
        try:
            for strategy_name in self.trade_records.keys():
                strategy_alerts = self._comprehensive_degradation_analysis(strategy_name, threshold)
                alerts.extend(strategy_alerts)
            
            # Store alerts
            self.degradation_alerts.extend(alerts)
            
            self.logger.info(f"Detected {len(alerts)} performance degradation alerts across {len(set(alert.strategy_name for alert in alerts))} strategies")
            
        except Exception as e:
            self.logger.error(f"Error detecting performance degradation: {str(e)}")
        
        return alerts
    
    def detect_performance_recovery(self, strategy_name: str) -> Optional[PerformanceDegradationAlert]:
        """
        Detect if a strategy has recovered from previous degradation.
        
        Args:
            strategy_name: Name of the strategy to check
            
        Returns:
            Recovery alert if recovery is detected, None otherwise
        """
        try:
            # Check if there are previous degradation alerts for this strategy
            previous_alerts = [alert for alert in self.degradation_alerts 
                             if alert.strategy_name == strategy_name and not alert.recovery_detected]
            
            if not previous_alerts:
                return None
            
            # Get recent performance
            recent_metrics = self.analyze_strategy_performance(strategy_name, "7d")
            
            # Check if performance has recovered above benchmark
            benchmark = self._get_performance_benchmark(strategy_name, "sharpe_ratio")
            if benchmark and recent_metrics.sharpe_ratio > benchmark.benchmark_value:
                
                # Perform statistical test for recovery
                recovery_test = self._test_performance_recovery(strategy_name)
                
                if recovery_test and recovery_test.is_significant:
                    # Mark previous alerts as recovered
                    for alert in previous_alerts:
                        alert.recovery_detected = True
                    
                    # Create recovery alert
                    recovery_alert = PerformanceDegradationAlert(
                        strategy_name=strategy_name,
                        alert_type=AlertType.PERFORMANCE_RECOVERY,
                        severity=AlertSeverity.MEDIUM,
                        message=f"Strategy {strategy_name} has recovered from previous performance degradation",
                        current_value=recent_metrics.sharpe_ratio,
                        threshold_value=benchmark.benchmark_value,
                        detection_time=datetime.now(),
                        metric_name="sharpe_ratio",
                        statistical_significance=recovery_test.confidence_level,
                        p_value=recovery_test.p_value,
                        suggested_actions=["Monitor continued performance", "Consider increasing allocation"],
                        recovery_detected=True
                    )
                    
                    self.degradation_alerts.append(recovery_alert)
                    self.logger.info(f"Performance recovery detected for strategy {strategy_name}")
                    
                    return recovery_alert
            
        except Exception as e:
            self.logger.error(f"Error detecting performance recovery: {str(e)}")
        
        return None
    
    def update_performance_benchmarks(self, strategy_name: str) -> None:
        """
        Update performance benchmarks for a strategy based on historical data.
        
        Args:
            strategy_name: Name of the strategy
        """
        try:
            history = self.performance_history.get(strategy_name, [])
            if len(history) < self.statistical_config['min_sample_size']:
                return
            
            # Calculate benchmarks for key metrics
            metrics_to_benchmark = ['sharpe_ratio', 'win_rate', 'profit_factor', 'max_drawdown']
            
            for metric_name in metrics_to_benchmark:
                values = [getattr(metrics, metric_name) for metrics in history[-self.statistical_config['benchmark_lookback_days']:]]
                
                if values:
                    benchmark = self._calculate_benchmark(strategy_name, metric_name, values)
                    self.performance_benchmarks[strategy_name][metric_name] = benchmark
            
            self.logger.debug(f"Updated performance benchmarks for strategy {strategy_name}")
            
        except Exception as e:
            self.logger.error(f"Error updating performance benchmarks: {str(e)}")
    
    def get_rolling_performance_comparison(self, strategy_name: str, window_days: int = 30) -> Dict[str, Any]:
        """
        Compare recent performance against rolling historical benchmarks.
        
        Args:
            strategy_name: Name of the strategy
            window_days: Rolling window size in days
            
        Returns:
            Dictionary with comparison results
        """
        try:
            history = self.performance_history.get(strategy_name, [])
            if len(history) < window_days:
                return {}
            
            # Get recent performance
            recent_metrics = history[-1] if history else None
            if not recent_metrics:
                return {}
            
            # Calculate rolling benchmarks
            comparison_results = {}
            
            for i in range(window_days, len(history)):
                window_data = history[i-window_days:i]
                
                # Calculate benchmark for this window
                sharpe_values = [m.sharpe_ratio for m in window_data]
                win_rate_values = [m.win_rate for m in window_data]
                
                if sharpe_values and win_rate_values:
                    window_benchmark = {
                        'sharpe_ratio': np.mean(sharpe_values),
                        'win_rate': np.mean(win_rate_values),
                        'sharpe_std': np.std(sharpe_values),
                        'win_rate_std': np.std(win_rate_values)
                    }
                    
                    # Compare current performance
                    comparison_results[f'window_{i}'] = {
                        'benchmark': window_benchmark,
                        'current_vs_benchmark': {
                            'sharpe_ratio_diff': recent_metrics.sharpe_ratio - window_benchmark['sharpe_ratio'],
                            'win_rate_diff': recent_metrics.win_rate - window_benchmark['win_rate']
                        }
                    }
            
            return comparison_results
            
        except Exception as e:
            self.logger.error(f"Error in rolling performance comparison: {str(e)}")
            return {}
    
    def _comprehensive_degradation_analysis(self, strategy_name: str, threshold: float) -> List[PerformanceDegradationAlert]:
        """
        Perform comprehensive degradation analysis using multiple statistical tests.
        
        Args:
            strategy_name: Name of the strategy
            threshold: Performance decline threshold
            
        Returns:
            List of degradation alerts
        """
        alerts = []
        
        try:
            # Update benchmarks first
            self.update_performance_benchmarks(strategy_name)
            
            # Get recent performance
            recent_metrics = self.analyze_strategy_performance(strategy_name, "7d")
            
            # Test 1: Statistical significance test
            stat_test = self._test_statistical_degradation(strategy_name)
            if stat_test and stat_test.is_significant:
                alerts.append(self._create_statistical_alert(strategy_name, stat_test, recent_metrics))
            
            # Test 2: Benchmark comparison
            benchmark_alerts = self._test_benchmark_underperformance(strategy_name, recent_metrics)
            alerts.extend(benchmark_alerts)
            
            # Test 3: Drawdown threshold check
            drawdown_alert = self._test_drawdown_threshold(strategy_name, recent_metrics)
            if drawdown_alert:
                alerts.append(drawdown_alert)
            
            # Test 4: Win rate decline
            win_rate_alert = self._test_win_rate_decline(strategy_name, recent_metrics)
            if win_rate_alert:
                alerts.append(win_rate_alert)
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive degradation analysis: {str(e)}")
        
        return alerts
    
    def _test_statistical_degradation(self, strategy_name: str) -> Optional[StatisticalTest]:
        """
        Test for statistical significance of performance degradation.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Statistical test result
        """
        try:
            history = self.performance_history.get(strategy_name, [])
            if len(history) < self.statistical_config['min_sample_size'] * 2:
                return None
            
            # Split data into historical and recent periods
            split_point = len(history) // 2
            historical_returns = [m.total_return for m in history[:split_point]]
            recent_returns = [m.total_return for m in history[split_point:]]
            
            # Perform t-test
            statistic, p_value = stats.ttest_ind(historical_returns, recent_returns, alternative='greater')
            
            # Determine significance
            significance_level = self.statistical_config['significance_level']
            is_significant = bool(p_value < significance_level)
            
            return StatisticalTest(
                test_name="Two-sample t-test",
                statistic=statistic,
                p_value=p_value,
                critical_value=stats.t.ppf(1 - significance_level, len(historical_returns) + len(recent_returns) - 2),
                is_significant=is_significant,
                confidence_level=1 - significance_level,
                interpretation="Historical performance significantly better than recent" if is_significant else "No significant degradation detected"
            )
            
        except Exception as e:
            self.logger.error(f"Error in statistical degradation test: {str(e)}")
            return None
    
    def _test_performance_recovery(self, strategy_name: str) -> Optional[StatisticalTest]:
        """
        Test for statistical significance of performance recovery.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Statistical test result
        """
        try:
            history = self.performance_history.get(strategy_name, [])
            if len(history) < self.statistical_config['min_sample_size']:
                return None
            
            # Get recent performance vs benchmark
            recent_metrics = history[-self.statistical_config['rolling_window_size']:]
            benchmark = self._get_performance_benchmark(strategy_name, "sharpe_ratio")
            
            if not benchmark:
                return None
            
            recent_sharpe_values = [m.sharpe_ratio for m in recent_metrics]
            
            # One-sample t-test against benchmark
            statistic, p_value = stats.ttest_1samp(recent_sharpe_values, benchmark.benchmark_value, alternative='greater')
            
            significance_level = self.statistical_config['significance_level']
            is_significant = bool(p_value < significance_level)
            
            return StatisticalTest(
                test_name="One-sample t-test (recovery)",
                statistic=statistic,
                p_value=p_value,
                critical_value=stats.t.ppf(1 - significance_level, len(recent_sharpe_values) - 1),
                is_significant=is_significant,
                confidence_level=1 - significance_level,
                interpretation="Performance significantly above benchmark" if is_significant else "No significant recovery detected"
            )
            
        except Exception as e:
            self.logger.error(f"Error in performance recovery test: {str(e)}")
            return None
    
    def _test_benchmark_underperformance(self, strategy_name: str, recent_metrics: PerformanceMetrics) -> List[PerformanceDegradationAlert]:
        """
        Test for underperformance against benchmarks.
        
        Args:
            strategy_name: Name of the strategy
            recent_metrics: Recent performance metrics
            
        Returns:
            List of benchmark underperformance alerts
        """
        alerts = []
        
        try:
            benchmarks = self.performance_benchmarks.get(strategy_name, {})
            
            for metric_name, benchmark in benchmarks.items():
                current_value = getattr(recent_metrics, metric_name, None)
                
                if current_value is not None and benchmark.is_underperforming(current_value):
                    severity = self._determine_alert_severity(current_value, benchmark.benchmark_value, metric_name)
                    
                    alert = PerformanceDegradationAlert(
                        strategy_name=strategy_name,
                        alert_type=AlertType.BENCHMARK_UNDERPERFORMANCE,
                        severity=severity,
                        message=f"Strategy {strategy_name} underperforming {metric_name} benchmark",
                        current_value=current_value,
                        threshold_value=benchmark.benchmark_value,
                        detection_time=datetime.now(),
                        metric_name=metric_name,
                        suggested_actions=self._get_suggested_actions(metric_name, severity)
                    )
                    
                    alerts.append(alert)
            
        except Exception as e:
            self.logger.error(f"Error testing benchmark underperformance: {str(e)}")
        
        return alerts
    
    def _test_drawdown_threshold(self, strategy_name: str, recent_metrics: PerformanceMetrics) -> Optional[PerformanceDegradationAlert]:
        """
        Test if drawdown exceeds threshold.
        
        Args:
            strategy_name: Name of the strategy
            recent_metrics: Recent performance metrics
            
        Returns:
            Drawdown alert if threshold exceeded
        """
        try:
            drawdown_threshold = 0.15  # 15% maximum drawdown threshold
            
            if recent_metrics.max_drawdown > drawdown_threshold:
                severity = AlertSeverity.HIGH if recent_metrics.max_drawdown > 0.25 else AlertSeverity.MEDIUM
                
                return PerformanceDegradationAlert(
                    strategy_name=strategy_name,
                    alert_type=AlertType.DRAWDOWN_THRESHOLD,
                    severity=severity,
                    message=f"Strategy {strategy_name} maximum drawdown exceeds threshold",
                    current_value=recent_metrics.max_drawdown,
                    threshold_value=drawdown_threshold,
                    detection_time=datetime.now(),
                    metric_name="max_drawdown",
                    suggested_actions=["Review risk management", "Reduce position sizes", "Consider strategy pause"]
                )
            
        except Exception as e:
            self.logger.error(f"Error testing drawdown threshold: {str(e)}")
        
        return None
    
    def _test_win_rate_decline(self, strategy_name: str, recent_metrics: PerformanceMetrics) -> Optional[PerformanceDegradationAlert]:
        """
        Test for significant win rate decline.
        
        Args:
            strategy_name: Name of the strategy
            recent_metrics: Recent performance metrics
            
        Returns:
            Win rate decline alert if detected
        """
        try:
            benchmark = self._get_performance_benchmark(strategy_name, "win_rate")
            if not benchmark:
                return None
            
            decline_threshold = self.degradation_thresholds['win_rate_decline']
            relative_decline = (recent_metrics.win_rate - benchmark.benchmark_value) / benchmark.benchmark_value
            
            if relative_decline < decline_threshold:
                severity = self._determine_alert_severity(recent_metrics.win_rate, benchmark.benchmark_value, "win_rate")
                
                return PerformanceDegradationAlert(
                    strategy_name=strategy_name,
                    alert_type=AlertType.WIN_RATE_DECLINE,
                    severity=severity,
                    message=f"Strategy {strategy_name} win rate declined significantly",
                    current_value=recent_metrics.win_rate,
                    threshold_value=benchmark.benchmark_value,
                    detection_time=datetime.now(),
                    metric_name="win_rate",
                    suggested_actions=["Review entry conditions", "Analyze market conditions", "Consider parameter optimization"]
                )
            
        except Exception as e:
            self.logger.error(f"Error testing win rate decline: {str(e)}")
        
        return None
    
    def _calculate_benchmark(self, strategy_name: str, metric_name: str, values: List[float]) -> PerformanceBenchmark:
        """
        Calculate performance benchmark from historical values.
        
        Args:
            strategy_name: Name of the strategy
            metric_name: Name of the metric
            values: Historical values
            
        Returns:
            Performance benchmark
        """
        try:
            # Calculate rolling average as benchmark
            benchmark_value = np.mean(values)
            std_dev = np.std(values)
            
            # Calculate confidence interval (95%)
            confidence_level = 0.95
            margin_of_error = stats.t.ppf((1 + confidence_level) / 2, len(values) - 1) * (std_dev / np.sqrt(len(values)))
            confidence_interval = (benchmark_value - margin_of_error, benchmark_value + margin_of_error)
            
            return PerformanceBenchmark(
                strategy_name=strategy_name,
                metric_name=metric_name,
                benchmark_value=benchmark_value,
                benchmark_period=timedelta(days=len(values)),
                calculation_method="rolling_average",
                confidence_interval=confidence_interval,
                sample_size=len(values)
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating benchmark: {str(e)}")
            # Return default benchmark
            return PerformanceBenchmark(
                strategy_name=strategy_name,
                metric_name=metric_name,
                benchmark_value=0.0,
                benchmark_period=timedelta(days=30),
                calculation_method="default",
                confidence_interval=(0.0, 0.0),
                sample_size=0
            )
    
    def _get_performance_benchmark(self, strategy_name: str, metric_name: str) -> Optional[PerformanceBenchmark]:
        """Get performance benchmark for a strategy and metric."""
        return self.performance_benchmarks.get(strategy_name, {}).get(metric_name)
    
    def _create_statistical_alert(self, strategy_name: str, stat_test: StatisticalTest, recent_metrics: PerformanceMetrics) -> PerformanceDegradationAlert:
        """Create alert from statistical test result."""
        severity = AlertSeverity.HIGH if stat_test.p_value < 0.01 else AlertSeverity.MEDIUM
        
        return PerformanceDegradationAlert(
            strategy_name=strategy_name,
            alert_type=AlertType.STATISTICAL_ANOMALY,
            severity=severity,
            message=f"Statistical degradation detected for {strategy_name}: {stat_test.interpretation}",
            current_value=recent_metrics.total_return,
            threshold_value=0.0,  # Threshold is implicit in statistical test
            detection_time=datetime.now(),
            metric_name="total_return",
            statistical_significance=stat_test.confidence_level,
            p_value=stat_test.p_value,
            suggested_actions=["Investigate recent changes", "Review market conditions", "Consider parameter adjustment"]
        )
    
    def _determine_alert_severity(self, current_value: float, benchmark_value: float, metric_name: str) -> AlertSeverity:
        """Determine alert severity based on deviation from benchmark."""
        try:
            # Special handling for max_drawdown - use absolute values
            if metric_name == 'max_drawdown':
                if current_value > 0.25:  # 25% drawdown
                    return AlertSeverity.CRITICAL
                elif current_value > 0.15:  # 15% drawdown
                    return AlertSeverity.HIGH
                elif current_value > 0.10:  # 10% drawdown
                    return AlertSeverity.MEDIUM
                else:
                    return AlertSeverity.LOW
            
            # For other metrics, use relative change
            if benchmark_value == 0:
                return AlertSeverity.MEDIUM
            
            relative_change = abs((current_value - benchmark_value) / benchmark_value)
            
            # Severity thresholds based on metric type
            if metric_name in ['sharpe_ratio', 'profit_factor']:
                if relative_change > 0.5:  # 50% change
                    return AlertSeverity.HIGH
                elif relative_change > 0.3:  # 30% change
                    return AlertSeverity.MEDIUM
                else:
                    return AlertSeverity.LOW
            else:
                # Default severity logic
                if relative_change > 0.4:
                    return AlertSeverity.HIGH
                elif relative_change > 0.2:
                    return AlertSeverity.MEDIUM
                else:
                    return AlertSeverity.LOW
                    
        except Exception:
            return AlertSeverity.MEDIUM
    
    def _get_suggested_actions(self, metric_name: str, severity: AlertSeverity) -> List[str]:
        """Get suggested actions based on metric and severity."""
        base_actions = {
            'sharpe_ratio': ["Review risk-adjusted returns", "Consider parameter optimization"],
            'win_rate': ["Analyze entry conditions", "Review market regime compatibility"],
            'profit_factor': ["Examine trade sizing", "Review exit strategies"],
            'max_drawdown': ["Implement stricter risk controls", "Reduce position sizes"]
        }
        
        actions = base_actions.get(metric_name, ["Review strategy performance"])
        
        if severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
            actions.extend(["Consider strategy pause", "Immediate review required"])
        
        return actions
    
    def generate_performance_report(self, include_charts: bool = False) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Args:
            include_charts: Whether to include chart data
            
        Returns:
            Comprehensive performance report
        """
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'summary': self._generate_summary_statistics(),
                'strategies': {},
                'regime_analysis': self._analyze_regime_performance(),
                'degradation_alerts': [alert.to_dict() for alert in self.degradation_alerts],
                'recommendations': self._generate_recommendations()
            }
            
            # Add strategy-specific reports
            for strategy_name in self.trade_records.keys():
                report['strategies'][strategy_name] = self._generate_strategy_report(
                    strategy_name, include_charts
                )
            
            self.logger.info("Generated comprehensive performance report")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating performance report: {str(e)}")
            return {'error': str(e)}
    
    def compare_strategies(self, strategy_names: List[str]) -> Dict[str, PerformanceMetrics]:
        """
        Compare performance across multiple strategies.
        
        Args:
            strategy_names: List of strategy names to compare
            
        Returns:
            Dictionary mapping strategy names to their performance metrics
        """
        comparison = {}
        
        try:
            for strategy_name in strategy_names:
                if strategy_name in self.trade_records:
                    comparison[strategy_name] = self.analyze_strategy_performance(
                        strategy_name, "30d"
                    )
            
            self.logger.info(f"Compared {len(comparison)} strategies")
            
        except Exception as e:
            self.logger.error(f"Error comparing strategies: {str(e)}")
        
        return comparison
    
    def get_regime_performance(self, regime_type: RegimeType) -> Dict[str, float]:
        """
        Get performance breakdown by market regime.
        
        Args:
            regime_type: Market regime to analyze
            
        Returns:
            Dictionary of performance metrics for the regime
        """
        try:
            regime_trades = []
            
            # Collect all trades for the specified regime
            for strategy_trades in self.trade_records.values():
                regime_trades.extend([
                    trade for trade in strategy_trades 
                    if trade.regime_type == regime_type
                ])
            
            if not regime_trades:
                return {}
            
            # Calculate regime-specific metrics
            total_pnl = sum(trade.pnl for trade in regime_trades)
            win_rate = sum(1 for trade in regime_trades if trade.is_winning_trade) / len(regime_trades)
            avg_return = np.mean([trade.pnl_percentage for trade in regime_trades])
            
            return {
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'average_return': avg_return,
                'trade_count': len(regime_trades)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing regime performance: {str(e)}")
            return {}
    
    def _parse_timeframe(self, timeframe: str, end_time: datetime) -> datetime:
        """Parse timeframe string to start datetime."""
        timeframe_map = {
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '24h': timedelta(days=1),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30),
            '90d': timedelta(days=90)
        }
        
        delta = timeframe_map.get(timeframe, timedelta(days=1))
        return end_time - delta
    
    def _get_trades_in_timeframe(self, 
                                strategy_name: str, 
                                start_time: datetime, 
                                end_time: datetime) -> List[TradeRecord]:
        """Get trades within specified timeframe."""
        trades = self.trade_records.get(strategy_name, [])
        return [
            trade for trade in trades 
            if start_time <= trade.exit_time <= end_time
        ]
    
    def _calculate_comprehensive_metrics(self, 
                                       trades: List[TradeRecord], 
                                       timeframe: str) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics from trades."""
        if not trades:
            return self._create_empty_metrics("", timeframe)
        
        # Basic calculations
        total_pnl = sum(trade.pnl for trade in trades)
        returns = [trade.pnl_percentage / 100 for trade in trades]
        returns_series = pd.Series(returns)
        
        # Return metrics
        total_return = sum(returns)
        period_days = (trades[-1].exit_time - trades[0].entry_time).days
        annualized_return = (total_return * 365 / period_days) if period_days > 0 else 0
        excess_return = annualized_return - self.risk_free_rate
        
        # Risk metrics
        volatility = returns_series.std() * np.sqrt(252) if len(returns) > 1 else 0
        max_drawdown = self._calculate_max_drawdown(trades)
        
        # Risk-adjusted metrics
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0
        
        # Sortino ratio
        negative_returns = returns_series[returns_series < 0]
        downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
        sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Trade statistics
        winning_trades = [trade for trade in trades if trade.is_winning_trade]
        losing_trades = [trade for trade in trades if not trade.is_winning_trade]
        
        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_win = np.mean([trade.pnl for trade in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([trade.pnl for trade in losing_trades]) if losing_trades else 0
        
        # Profit factor
        gross_profit = sum(trade.pnl for trade in winning_trades)
        gross_loss = abs(sum(trade.pnl for trade in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Average trade duration
        durations = [trade.duration for trade in trades]
        avg_duration = sum(durations, timedelta()) / len(durations) if durations else timedelta()
        
        # Regime-specific performance
        regime_performance = self._calculate_regime_performance(trades)
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            excess_return=excess_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility,
            downside_deviation=downside_deviation,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_duration=avg_duration,
            trades_count=len(trades),
            avg_win=avg_win,
            avg_loss=avg_loss,
            regime_performance=regime_performance,
            measurement_period=self._parse_timeframe_to_delta(timeframe)
        )
    
    def _calculate_max_drawdown(self, trades: List[TradeRecord]) -> float:
        """Calculate maximum drawdown from trades."""
        if not trades:
            return 0.0
        
        # Calculate cumulative returns
        cumulative_returns = []
        cumulative_return = 0
        
        for trade in sorted(trades, key=lambda x: x.exit_time):
            cumulative_return += trade.pnl_percentage / 100
            cumulative_returns.append(cumulative_return)
        
        if not cumulative_returns:
            return 0.0
        
        # Calculate drawdown - track running maximum and calculate drawdown from peak
        running_max = cumulative_returns[0]
        max_drawdown = 0
        
        for return_val in cumulative_returns:
            # Update running maximum
            if return_val > running_max:
                running_max = return_val
            
            # Calculate drawdown from peak (always positive)
            drawdown = running_max - return_val
            max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    def _calculate_regime_performance(self, trades: List[TradeRecord]) -> Dict[RegimeType, float]:
        """Calculate performance by market regime."""
        regime_performance = {}
        
        for regime_type in RegimeType:
            regime_trades = [trade for trade in trades if trade.regime_type == regime_type]
            if regime_trades:
                avg_return = np.mean([trade.pnl_percentage for trade in regime_trades])
                regime_performance[regime_type] = avg_return
        
        return regime_performance
    
    def _create_empty_metrics(self, strategy_name: str, timeframe: str) -> PerformanceMetrics:
        """Create empty performance metrics."""
        return PerformanceMetrics(
            total_return=0.0,
            annualized_return=0.0,
            excess_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            volatility=0.0,
            downside_deviation=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_trade_duration=timedelta(),
            trades_count=0,
            avg_win=0.0,
            avg_loss=0.0,
            regime_performance={},
            measurement_period=self._parse_timeframe_to_delta(timeframe)
        )
    
    def _parse_timeframe_to_delta(self, timeframe: str) -> timedelta:
        """Convert timeframe string to timedelta."""
        timeframe_map = {
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '24h': timedelta(days=1),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30),
            '90d': timedelta(days=90)
        }
        return timeframe_map.get(timeframe, timedelta(days=1))
    
    def _has_performance_degradation(self, strategy_name: str, threshold: float) -> bool:
        """Check if strategy has performance degradation (legacy method)."""
        try:
            # Use the new comprehensive analysis
            alerts = self._comprehensive_degradation_analysis(strategy_name, threshold)
            return len(alerts) > 0
            
        except Exception as e:
            self.logger.error(f"Error checking performance degradation: {str(e)}")
            return False
    
    def _generate_summary_statistics(self) -> Dict[str, Any]:
        """Generate summary statistics across all strategies."""
        try:
            all_trades = []
            for trades in self.trade_records.values():
                all_trades.extend(trades)
            
            if not all_trades:
                return {}
            
            total_pnl = sum(trade.pnl for trade in all_trades)
            total_trades = len(all_trades)
            winning_trades = sum(1 for trade in all_trades if trade.is_winning_trade)
            
            return {
                'total_strategies': len(self.trade_records),
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'overall_win_rate': winning_trades / total_trades if total_trades > 0 else 0,
                'active_strategies': len([s for s in self.trade_records.keys() if self.trade_records[s]]),
                'avg_trades_per_strategy': total_trades / len(self.trade_records) if self.trade_records else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error generating summary statistics: {str(e)}")
            return {}
    
    def _analyze_regime_performance(self) -> Dict[str, Any]:
        """Analyze performance across different market regimes."""
        try:
            regime_analysis = {}
            
            for regime_type in RegimeType:
                regime_performance = self.get_regime_performance(regime_type)
                if regime_performance:
                    regime_analysis[regime_type.value] = regime_performance
            
            return regime_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing regime performance: {str(e)}")
            return {}
    
    def _generate_strategy_report(self, strategy_name: str, include_charts: bool) -> Dict[str, Any]:
        """Generate detailed report for a specific strategy."""
        try:
            trades = self.trade_records.get(strategy_name, [])
            if not trades:
                return {}
            
            # Get latest performance metrics
            latest_metrics = self.analyze_strategy_performance(strategy_name, "30d")
            
            # Calculate additional statistics
            recent_trades = trades[-10:] if len(trades) >= 10 else trades
            recent_performance = sum(trade.pnl for trade in recent_trades)
            
            report = {
                'strategy_name': strategy_name,
                'total_trades': len(trades),
                'latest_metrics': latest_metrics.__dict__,
                'recent_performance': recent_performance,
                'trade_frequency': len(trades) / 30 if trades else 0,  # trades per day over 30 days
                'best_trade': max(trades, key=lambda x: x.pnl).__dict__ if trades else None,
                'worst_trade': min(trades, key=lambda x: x.pnl).__dict__ if trades else None,
            }
            
            if include_charts:
                report['chart_data'] = self._generate_chart_data(trades)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating strategy report: {str(e)}")
            return {}
    
    def _generate_chart_data(self, trades: List[TradeRecord]) -> Dict[str, Any]:
        """Generate chart data for visualization."""
        try:
            # Cumulative P&L over time
            cumulative_pnl = []
            cumulative_sum = 0
            
            for trade in sorted(trades, key=lambda x: x.exit_time):
                cumulative_sum += trade.pnl
                cumulative_pnl.append({
                    'timestamp': trade.exit_time.isoformat(),
                    'cumulative_pnl': cumulative_sum
                })
            
            # Daily P&L distribution
            daily_pnl = defaultdict(float)
            for trade in trades:
                date_key = trade.exit_time.date().isoformat()
                daily_pnl[date_key] += trade.pnl
            
            return {
                'cumulative_pnl': cumulative_pnl,
                'daily_pnl': dict(daily_pnl),
                'trade_distribution': {
                    'winning_trades': len([t for t in trades if t.is_winning_trade]),
                    'losing_trades': len([t for t in trades if not t.is_winning_trade])
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating chart data: {str(e)}")
            return {}
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on performance analysis."""
        recommendations = []
        
        try:
            # Analyze overall performance and generate recommendations
            for strategy_name in self.trade_records.keys():
                latest_metrics = self.analyze_strategy_performance(strategy_name, "7d")
                
                if latest_metrics.sharpe_ratio < 0.5:
                    recommendations.append(f"Consider optimizing parameters for {strategy_name} - low Sharpe ratio")
                
                if latest_metrics.max_drawdown > 0.15:
                    recommendations.append(f"Review risk management for {strategy_name} - high drawdown")
                
                if latest_metrics.win_rate < 0.4:
                    recommendations.append(f"Analyze entry conditions for {strategy_name} - low win rate")
            
            # Add general recommendations
            if len(self.degradation_alerts) > 0:
                recommendations.append("Multiple strategies showing degradation - consider system-wide review")
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {str(e)}")
        
        return recommendations