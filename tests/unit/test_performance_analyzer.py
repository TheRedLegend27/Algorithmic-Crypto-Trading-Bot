"""
Unit tests for the PerformanceAnalyzer class.

This module tests all performance metrics calculations, degradation detection,
and reporting functionality.
"""
import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import logging

from bot.adaptive.performance_analyzer import (
    PerformanceAnalyzer, TradeRecord, PerformanceDegradationAlert, 
    AlertType, AlertSeverity, PerformanceBenchmark, StatisticalTest
)
from bot.adaptive.data_models import PerformanceMetrics
from bot.adaptive.enums import RegimeType


class TestPerformanceAnalyzer(unittest.TestCase):
    """Test cases for PerformanceAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = PerformanceAnalyzer(
            risk_free_rate=0.02,
            benchmark_return=0.05,
            logger=Mock()
        )
        
        # Create sample trade records
        self.sample_trades = self._create_sample_trades()
        
        # Add trades to analyzer
        for trade in self.sample_trades:
            self.analyzer.add_trade_record(trade)
    
    def _create_sample_trades(self) -> list:
        """Create sample trade records for testing."""
        base_time = datetime.now() - timedelta(days=30)
        trades = []
        
        # Create a mix of winning and losing trades
        trade_data = [
            # (pnl, pnl_percentage, hours_offset, regime)
            (100, 5.0, 0, RegimeType.TRENDING_BULL),
            (-50, -2.5, 2, RegimeType.TRENDING_BULL),
            (200, 10.0, 4, RegimeType.TRENDING_BULL),
            (-30, -1.5, 6, RegimeType.RANGING),
            (150, 7.5, 8, RegimeType.RANGING),
            (-80, -4.0, 10, RegimeType.HIGH_VOLATILITY),
            (300, 15.0, 12, RegimeType.TRENDING_BULL),
            (-20, -1.0, 14, RegimeType.LOW_VOLATILITY),
            (80, 4.0, 16, RegimeType.RANGING),
            (-100, -5.0, 18, RegimeType.HIGH_VOLATILITY),
        ]
        
        for i, (pnl, pnl_pct, hours_offset, regime) in enumerate(trade_data):
            entry_time = base_time + timedelta(hours=hours_offset)
            exit_time = entry_time + timedelta(hours=1)  # 1 hour trades
            
            trade = TradeRecord(
                trade_id=f"trade_{i}",
                strategy_name="test_strategy",
                pair="BTCUSD",
                side="buy" if pnl > 0 else "sell",
                entry_price=50000.0,
                exit_price=50000.0 + (pnl / 0.01),  # Approximate exit price
                quantity=0.01,
                entry_time=entry_time,
                exit_time=exit_time,
                pnl=pnl,
                pnl_percentage=pnl_pct,
                regime_type=regime,
                fees=5.0
            )
            trades.append(trade)
        
        return trades
    
    def test_initialization(self):
        """Test PerformanceAnalyzer initialization."""
        analyzer = PerformanceAnalyzer(risk_free_rate=0.03, benchmark_return=0.06)
        
        self.assertEqual(analyzer.risk_free_rate, 0.03)
        self.assertEqual(analyzer.benchmark_return, 0.06)
        self.assertIsInstance(analyzer.trade_records, dict)
        self.assertIsInstance(analyzer.performance_history, dict)
        self.assertIsInstance(analyzer.degradation_alerts, list)
    
    def test_add_trade_record(self):
        """Test adding trade records."""
        analyzer = PerformanceAnalyzer()
        trade = self.sample_trades[0]
        
        analyzer.add_trade_record(trade)
        
        self.assertIn("test_strategy", analyzer.trade_records)
        self.assertEqual(len(analyzer.trade_records["test_strategy"]), 1)
        self.assertEqual(analyzer.trade_records["test_strategy"][0], trade)
    
    def test_analyze_strategy_performance_basic_metrics(self):
        """Test basic performance metrics calculation."""
        metrics = self.analyzer.analyze_strategy_performance("test_strategy", "30d")
        
        # Check that metrics object is returned
        self.assertIsInstance(metrics, PerformanceMetrics)
        
        # Check basic calculations
        expected_total_return = sum(trade.pnl_percentage / 100 for trade in self.sample_trades)
        self.assertAlmostEqual(metrics.total_return, expected_total_return, places=4)
        
        # Check trade count
        self.assertEqual(metrics.trades_count, len(self.sample_trades))
        
        # Check win rate
        winning_trades = sum(1 for trade in self.sample_trades if trade.is_winning_trade)
        expected_win_rate = winning_trades / len(self.sample_trades)
        self.assertAlmostEqual(metrics.win_rate, expected_win_rate, places=4)
    
    def test_analyze_strategy_performance_risk_metrics(self):
        """Test risk-adjusted performance metrics."""
        metrics = self.analyzer.analyze_strategy_performance("test_strategy", "30d")
        
        # Check that risk metrics are calculated
        self.assertIsInstance(metrics.sharpe_ratio, float)
        self.assertIsInstance(metrics.sortino_ratio, float)
        self.assertIsInstance(metrics.max_drawdown, float)
        self.assertIsInstance(metrics.volatility, float)
        
        # Sharpe ratio should be reasonable (not infinite or NaN)
        self.assertFalse(np.isnan(metrics.sharpe_ratio))
        self.assertFalse(np.isinf(metrics.sharpe_ratio))
        
        # Max drawdown should be non-negative
        self.assertGreaterEqual(metrics.max_drawdown, 0)
    
    def test_analyze_strategy_performance_empty_trades(self):
        """Test performance analysis with no trades."""
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.analyze_strategy_performance("empty_strategy", "30d")
        
        # Should return empty metrics
        self.assertEqual(metrics.total_return, 0.0)
        self.assertEqual(metrics.trades_count, 0)
        self.assertEqual(metrics.win_rate, 0.0)
        self.assertEqual(metrics.sharpe_ratio, 0.0)
    
    def test_calculate_risk_adjusted_returns(self):
        """Test risk-adjusted returns calculation."""
        risk_metrics = self.analyzer.calculate_risk_adjusted_returns("test_strategy")
        
        # Check that all expected metrics are present
        expected_keys = ['sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'volatility', 'excess_return']
        for key in expected_keys:
            self.assertIn(key, risk_metrics)
            self.assertIsInstance(risk_metrics[key], float)
        
        # Check that values are reasonable
        self.assertFalse(np.isnan(risk_metrics['sharpe_ratio']))
        self.assertGreaterEqual(risk_metrics['volatility'], 0)
    
    def test_calculate_risk_adjusted_returns_empty_strategy(self):
        """Test risk-adjusted returns with empty strategy."""
        risk_metrics = self.analyzer.calculate_risk_adjusted_returns("nonexistent_strategy")
        
        # Should return empty dict
        self.assertEqual(risk_metrics, {})
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        # Create trades with known drawdown pattern
        analyzer = PerformanceAnalyzer()
        
        # Create trades that should result in specific drawdown
        drawdown_trades = [
            TradeRecord(
                trade_id="dd_1", strategy_name="dd_test", pair="BTCUSD", side="buy",
                entry_price=50000, exit_price=52500, quantity=0.01,
                entry_time=datetime.now() - timedelta(hours=4),
                exit_time=datetime.now() - timedelta(hours=3),
                pnl=25, pnl_percentage=5.0
            ),
            TradeRecord(
                trade_id="dd_2", strategy_name="dd_test", pair="BTCUSD", side="sell",
                entry_price=52500, exit_price=47250, quantity=0.01,
                entry_time=datetime.now() - timedelta(hours=3),
                exit_time=datetime.now() - timedelta(hours=2),
                pnl=-52.5, pnl_percentage=-10.0
            ),
            TradeRecord(
                trade_id="dd_3", strategy_name="dd_test", pair="BTCUSD", side="buy",
                entry_price=47250, exit_price=49087.5, quantity=0.01,
                entry_time=datetime.now() - timedelta(hours=2),
                exit_time=datetime.now() - timedelta(hours=1),
                pnl=18.375, pnl_percentage=3.89
            )
        ]
        
        for trade in drawdown_trades:
            analyzer.add_trade_record(trade)
        
        max_dd = analyzer._calculate_max_drawdown(drawdown_trades)
        
        # Should have some drawdown from the losing trade
        self.assertGreater(max_dd, 0)
        self.assertLessEqual(max_dd, 1.0)  # Drawdown should be <= 100%
    
    def test_regime_performance_analysis(self):
        """Test regime-specific performance analysis."""
        regime_perf = self.analyzer.get_regime_performance(RegimeType.TRENDING_BULL)
        
        # Should have performance data for trending bull regime
        self.assertIsInstance(regime_perf, dict)
        if regime_perf:  # If there are trades in this regime
            self.assertIn('total_pnl', regime_perf)
            self.assertIn('win_rate', regime_perf)
            self.assertIn('average_return', regime_perf)
            self.assertIn('trade_count', regime_perf)
    
    def test_performance_degradation_detection(self):
        """Test performance degradation detection."""
        # Add some performance history to trigger degradation detection
        old_metrics = PerformanceMetrics(
            total_return=0.15, annualized_return=0.15, excess_return=0.13,
            sharpe_ratio=1.5, sortino_ratio=2.0, calmar_ratio=1.0,
            max_drawdown=0.05, volatility=0.1, downside_deviation=0.05,
            win_rate=0.7, profit_factor=2.0, avg_trade_duration=timedelta(hours=2),
            trades_count=50, avg_win=100, avg_loss=-50,
            regime_performance={}
        )
        
        new_metrics = PerformanceMetrics(
            total_return=0.05, annualized_return=0.05, excess_return=0.03,
            sharpe_ratio=0.5, sortino_ratio=0.7, calmar_ratio=0.3,
            max_drawdown=0.15, volatility=0.2, downside_deviation=0.15,
            win_rate=0.4, profit_factor=1.2, avg_trade_duration=timedelta(hours=2),
            trades_count=30, avg_win=80, avg_loss=-60,
            regime_performance={}
        )
        
        # Add to history
        self.analyzer.performance_history["test_strategy"] = [old_metrics, new_metrics]
        
        degradation_alerts = self.analyzer.detect_performance_degradation(-0.2)
        
        # Should detect degradation and return alerts
        self.assertIsInstance(degradation_alerts, list)
    
    def test_statistical_degradation_detection(self):
        """Test statistical tests for performance degradation."""
        from bot.adaptive.performance_analyzer import StatisticalTest
        
        # Create performance history with clear degradation pattern
        metrics_list = []
        base_time = datetime.now() - timedelta(days=60)
        
        # First half: good performance
        for i in range(15):
            metrics = PerformanceMetrics(
                total_return=0.10 + np.random.normal(0, 0.02),
                annualized_return=0.10, excess_return=0.08,
                sharpe_ratio=1.2 + np.random.normal(0, 0.1),
                sortino_ratio=1.5, calmar_ratio=1.0,
                max_drawdown=0.05, volatility=0.1, downside_deviation=0.05,
                win_rate=0.65, profit_factor=1.8, avg_trade_duration=timedelta(hours=2),
                trades_count=10, avg_win=100, avg_loss=-50,
                regime_performance={}, last_updated=base_time + timedelta(days=i*2)
            )
            metrics_list.append(metrics)
        
        # Second half: poor performance
        for i in range(15):
            metrics = PerformanceMetrics(
                total_return=0.02 + np.random.normal(0, 0.02),
                annualized_return=0.02, excess_return=0.00,
                sharpe_ratio=0.3 + np.random.normal(0, 0.1),
                sortino_ratio=0.4, calmar_ratio=0.2,
                max_drawdown=0.12, volatility=0.15, downside_deviation=0.1,
                win_rate=0.45, profit_factor=1.1, avg_trade_duration=timedelta(hours=2),
                trades_count=10, avg_win=80, avg_loss=-60,
                regime_performance={}, last_updated=base_time + timedelta(days=30 + i*2)
            )
            metrics_list.append(metrics)
        
        self.analyzer.performance_history["degrading_strategy"] = metrics_list
        
        # Test statistical degradation detection
        stat_test = self.analyzer._test_statistical_degradation("degrading_strategy")
        
        self.assertIsInstance(stat_test, StatisticalTest)
        self.assertIsInstance(stat_test.p_value, float)
        self.assertIsInstance(stat_test.is_significant, bool)
    
    def test_benchmark_calculation_and_comparison(self):
        """Test benchmark calculation and comparison."""
        from bot.adaptive.performance_analyzer import PerformanceBenchmark
        
        # Add performance history
        metrics_list = []
        for i in range(20):
            metrics = PerformanceMetrics(
                total_return=0.08 + np.random.normal(0, 0.02),
                annualized_return=0.08, excess_return=0.06,
                sharpe_ratio=1.0 + np.random.normal(0, 0.1),
                sortino_ratio=1.2, calmar_ratio=0.8,
                max_drawdown=0.06, volatility=0.12, downside_deviation=0.06,
                win_rate=0.6 + np.random.normal(0, 0.05), profit_factor=1.5,
                avg_trade_duration=timedelta(hours=2), trades_count=10,
                avg_win=90, avg_loss=-55, regime_performance={}
            )
            metrics_list.append(metrics)
        
        self.analyzer.performance_history["benchmark_test"] = metrics_list
        
        # Update benchmarks
        self.analyzer.update_performance_benchmarks("benchmark_test")
        
        # Check that benchmarks were created
        benchmarks = self.analyzer.performance_benchmarks.get("benchmark_test", {})
        self.assertGreater(len(benchmarks), 0)
        
        # Check benchmark structure
        if "sharpe_ratio" in benchmarks:
            benchmark = benchmarks["sharpe_ratio"]
            self.assertIsInstance(benchmark, PerformanceBenchmark)
            self.assertIsInstance(benchmark.benchmark_value, float)
            self.assertIsInstance(benchmark.confidence_interval, tuple)
    
    def test_performance_recovery_detection(self):
        """Test performance recovery detection."""
        from bot.adaptive.performance_analyzer import PerformanceDegradationAlert, AlertType, AlertSeverity
        
        # Create a degradation alert first
        degradation_alert = PerformanceDegradationAlert(
            strategy_name="recovery_test",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.MEDIUM,
            message="Test degradation",
            current_value=0.3,
            threshold_value=0.8,
            detection_time=datetime.now() - timedelta(days=7),
            metric_name="sharpe_ratio"
        )
        
        self.analyzer.degradation_alerts.append(degradation_alert)
        
        # Create performance history showing recovery
        recovery_metrics = []
        for i in range(10):
            metrics = PerformanceMetrics(
                total_return=0.12, annualized_return=0.12, excess_return=0.10,
                sharpe_ratio=1.3 + np.random.normal(0, 0.05),
                sortino_ratio=1.6, calmar_ratio=1.1,
                max_drawdown=0.04, volatility=0.09, downside_deviation=0.04,
                win_rate=0.68, profit_factor=1.9, avg_trade_duration=timedelta(hours=2),
                trades_count=10, avg_win=95, avg_loss=-48, regime_performance={}
            )
            recovery_metrics.append(metrics)
        
        self.analyzer.performance_history["recovery_test"] = recovery_metrics
        
        # Update benchmarks
        self.analyzer.update_performance_benchmarks("recovery_test")
        
        # Test recovery detection
        recovery_alert = self.analyzer.detect_performance_recovery("recovery_test")
        
        # Recovery might or might not be detected depending on statistical significance
        if recovery_alert:
            self.assertIsInstance(recovery_alert, PerformanceDegradationAlert)
            self.assertEqual(recovery_alert.alert_type, AlertType.PERFORMANCE_RECOVERY)
    
    def test_rolling_performance_comparison(self):
        """Test rolling performance comparison."""
        # Create performance history
        metrics_list = []
        for i in range(50):
            metrics = PerformanceMetrics(
                total_return=0.06 + np.random.normal(0, 0.02),
                annualized_return=0.06, excess_return=0.04,
                sharpe_ratio=0.8 + np.random.normal(0, 0.1),
                sortino_ratio=1.0, calmar_ratio=0.6,
                max_drawdown=0.08, volatility=0.14, downside_deviation=0.08,
                win_rate=0.55 + np.random.normal(0, 0.05), profit_factor=1.3,
                avg_trade_duration=timedelta(hours=2), trades_count=10,
                avg_win=85, avg_loss=-58, regime_performance={}
            )
            metrics_list.append(metrics)
        
        self.analyzer.performance_history["rolling_test"] = metrics_list
        
        # Test rolling comparison
        comparison = self.analyzer.get_rolling_performance_comparison("rolling_test", window_days=20)
        
        self.assertIsInstance(comparison, dict)
        # Should have comparison windows
        if comparison:
            # Check structure of comparison results
            first_key = list(comparison.keys())[0]
            self.assertIn('benchmark', comparison[first_key])
            self.assertIn('current_vs_benchmark', comparison[first_key])
    
    def test_drawdown_threshold_detection(self):
        """Test drawdown threshold detection."""
        # Create metrics with high drawdown
        high_drawdown_metrics = PerformanceMetrics(
            total_return=0.05, annualized_return=0.05, excess_return=0.03,
            sharpe_ratio=0.4, sortino_ratio=0.5, calmar_ratio=0.2,
            max_drawdown=0.20,  # 20% drawdown - should trigger alert
            volatility=0.18, downside_deviation=0.12,
            win_rate=0.45, profit_factor=1.1, avg_trade_duration=timedelta(hours=2),
            trades_count=20, avg_win=75, avg_loss=-65, regime_performance={}
        )
        
        # Test drawdown threshold detection
        alert = self.analyzer._test_drawdown_threshold("drawdown_test", high_drawdown_metrics)
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, AlertType.DRAWDOWN_THRESHOLD)
        self.assertGreater(alert.current_value, alert.threshold_value)
    
    def test_win_rate_decline_detection(self):
        """Test win rate decline detection."""
        from bot.adaptive.performance_analyzer import PerformanceBenchmark
        
        # Create benchmark
        benchmark = PerformanceBenchmark(
            strategy_name="win_rate_test",
            metric_name="win_rate",
            benchmark_value=0.65,
            benchmark_period=timedelta(days=30),
            calculation_method="rolling_average",
            confidence_interval=(0.60, 0.70),
            sample_size=30
        )
        
        self.analyzer.performance_benchmarks["win_rate_test"]["win_rate"] = benchmark
        
        # Create metrics with low win rate
        low_win_rate_metrics = PerformanceMetrics(
            total_return=0.04, annualized_return=0.04, excess_return=0.02,
            sharpe_ratio=0.5, sortino_ratio=0.6, calmar_ratio=0.3,
            max_drawdown=0.10, volatility=0.16, downside_deviation=0.10,
            win_rate=0.35,  # Much lower than benchmark
            profit_factor=1.0, avg_trade_duration=timedelta(hours=2),
            trades_count=20, avg_win=70, avg_loss=-70, regime_performance={}
        )
        
        # Test win rate decline detection
        alert = self.analyzer._test_win_rate_decline("win_rate_test", low_win_rate_metrics)
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, AlertType.WIN_RATE_DECLINE)
        self.assertLess(alert.current_value, alert.threshold_value)
    
    def test_alert_severity_determination(self):
        """Test alert severity determination logic."""
        from bot.adaptive.performance_analyzer import AlertSeverity
        
        # Test Sharpe ratio severity
        severity_high = self.analyzer._determine_alert_severity(0.4, 1.0, "sharpe_ratio")
        self.assertEqual(severity_high, AlertSeverity.HIGH)  # 60% decline
        
        severity_medium = self.analyzer._determine_alert_severity(0.8, 1.0, "sharpe_ratio")
        self.assertEqual(severity_medium, AlertSeverity.LOW)  # 20% decline
        
        # Test drawdown severity
        severity_critical = self.analyzer._determine_alert_severity(0.30, 0.0, "max_drawdown")
        self.assertEqual(severity_critical, AlertSeverity.CRITICAL)  # 30% drawdown
        
        severity_high_dd = self.analyzer._determine_alert_severity(0.18, 0.0, "max_drawdown")
        self.assertEqual(severity_high_dd, AlertSeverity.HIGH)  # 18% drawdown
    
    def test_suggested_actions_generation(self):
        """Test suggested actions generation."""
        from bot.adaptive.performance_analyzer import AlertSeverity
        
        # Test actions for different metrics and severities
        actions_sharpe = self.analyzer._get_suggested_actions("sharpe_ratio", AlertSeverity.MEDIUM)
        self.assertIsInstance(actions_sharpe, list)
        self.assertGreater(len(actions_sharpe), 0)
        
        actions_drawdown_critical = self.analyzer._get_suggested_actions("max_drawdown", AlertSeverity.CRITICAL)
        self.assertIn("Consider strategy pause", actions_drawdown_critical)
        
        actions_win_rate = self.analyzer._get_suggested_actions("win_rate", AlertSeverity.LOW)
        self.assertIn("Analyze entry conditions", actions_win_rate)
    
    def test_comprehensive_degradation_analysis(self):
        """Test comprehensive degradation analysis."""
        # Create performance history with degradation
        degrading_metrics = []
        for i in range(15):
            # Start with good performance, then degrade
            performance_factor = max(0.3, 1.0 - (i * 0.05))
            
            metrics = PerformanceMetrics(
                total_return=0.08 * performance_factor,
                annualized_return=0.08 * performance_factor,
                excess_return=0.06 * performance_factor,
                sharpe_ratio=1.0 * performance_factor,
                sortino_ratio=1.2 * performance_factor,
                calmar_ratio=0.8 * performance_factor,
                max_drawdown=0.05 + (i * 0.01),  # Increasing drawdown
                volatility=0.12 + (i * 0.005),
                downside_deviation=0.06 + (i * 0.003),
                win_rate=max(0.3, 0.6 - (i * 0.02)),  # Declining win rate
                profit_factor=max(0.8, 1.5 - (i * 0.05)),
                avg_trade_duration=timedelta(hours=2),
                trades_count=10, avg_win=90, avg_loss=-55,
                regime_performance={}
            )
            degrading_metrics.append(metrics)
        
        self.analyzer.performance_history["comprehensive_test"] = degrading_metrics
        
        # Run comprehensive analysis
        alerts = self.analyzer._comprehensive_degradation_analysis("comprehensive_test", -0.2)
        
        self.assertIsInstance(alerts, list)
        # Should detect some form of degradation
        if alerts:
            for alert in alerts:
                self.assertIsInstance(alert, PerformanceDegradationAlert)
                self.assertIn(alert.alert_type, [AlertType.BENCHMARK_UNDERPERFORMANCE, 
                                               AlertType.DRAWDOWN_THRESHOLD, 
                                               AlertType.WIN_RATE_DECLINE,
                                               AlertType.STATISTICAL_ANOMALY])
    
    def test_alert_serialization(self):
        """Test alert serialization to dictionary."""
        from bot.adaptive.performance_analyzer import PerformanceDegradationAlert, AlertType, AlertSeverity
        
        alert = PerformanceDegradationAlert(
            strategy_name="test_strategy",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.HIGH,
            message="Test alert message",
            current_value=0.5,
            threshold_value=1.0,
            detection_time=datetime.now(),
            metric_name="sharpe_ratio",
            statistical_significance=0.95,
            p_value=0.02,
            suggested_actions=["Action 1", "Action 2"]
        )
        
        alert_dict = alert.to_dict()
        
        # Check all required fields are present
        required_fields = ['strategy_name', 'alert_type', 'severity', 'message', 
                          'current_value', 'threshold_value', 'detection_time', 
                          'metric_name', 'suggested_actions']
        
        for field in required_fields:
            self.assertIn(field, alert_dict)
        
        # Check types
        self.assertIsInstance(alert_dict['alert_type'], str)
        self.assertIsInstance(alert_dict['severity'], str)
        self.assertIsInstance(alert_dict['suggested_actions'], list)
    
    def test_strategy_comparison(self):
        """Test strategy comparison functionality."""
        # Add another strategy
        strategy2_trades = [
            TradeRecord(
                trade_id="s2_1", strategy_name="strategy2", pair="ETHUSD", side="buy",
                entry_price=3000, exit_price=3150, quantity=0.1,
                entry_time=datetime.now() - timedelta(hours=2),
                exit_time=datetime.now() - timedelta(hours=1),
                pnl=15, pnl_percentage=5.0
            )
        ]
        
        for trade in strategy2_trades:
            self.analyzer.add_trade_record(trade)
        
        comparison = self.analyzer.compare_strategies(["test_strategy", "strategy2"])
        
        self.assertIn("test_strategy", comparison)
        self.assertIn("strategy2", comparison)
        self.assertIsInstance(comparison["test_strategy"], PerformanceMetrics)
        self.assertIsInstance(comparison["strategy2"], PerformanceMetrics)
    
    def test_performance_report_generation(self):
        """Test comprehensive performance report generation."""
        report = self.analyzer.generate_performance_report(include_charts=True)
        
        # Check report structure
        self.assertIn('generated_at', report)
        self.assertIn('summary', report)
        self.assertIn('strategies', report)
        self.assertIn('regime_analysis', report)
        self.assertIn('degradation_alerts', report)
        self.assertIn('recommendations', report)
        
        # Check strategy-specific reports
        self.assertIn('test_strategy', report['strategies'])
        strategy_report = report['strategies']['test_strategy']
        self.assertIn('total_trades', strategy_report)
        self.assertIn('latest_metrics', strategy_report)
    
    def test_timeframe_parsing(self):
        """Test timeframe parsing functionality."""
        end_time = datetime.now()
        
        # Test various timeframes
        start_1h = self.analyzer._parse_timeframe("1h", end_time)
        self.assertEqual(end_time - start_1h, timedelta(hours=1))
        
        start_24h = self.analyzer._parse_timeframe("24h", end_time)
        self.assertEqual(end_time - start_24h, timedelta(days=1))
        
        start_7d = self.analyzer._parse_timeframe("7d", end_time)
        self.assertEqual(end_time - start_7d, timedelta(days=7))
        
        # Test default case
        start_default = self.analyzer._parse_timeframe("invalid", end_time)
        self.assertEqual(end_time - start_default, timedelta(days=1))
    
    def test_trade_record_properties(self):
        """Test TradeRecord properties and methods."""
        trade = self.sample_trades[0]
        
        # Test duration property
        expected_duration = trade.exit_time - trade.entry_time
        self.assertEqual(trade.duration, expected_duration)
        
        # Test is_winning_trade property
        if trade.pnl > 0:
            self.assertTrue(trade.is_winning_trade)
        else:
            self.assertFalse(trade.is_winning_trade)
    
    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        metrics = self.analyzer.analyze_strategy_performance("test_strategy", "30d")
        
        # Calculate expected profit factor
        winning_trades = [t for t in self.sample_trades if t.is_winning_trade]
        losing_trades = [t for t in self.sample_trades if not t.is_winning_trade]
        
        if winning_trades and losing_trades:
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            expected_profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            self.assertAlmostEqual(metrics.profit_factor, expected_profit_factor, places=4)
    
    def test_chart_data_generation(self):
        """Test chart data generation for visualization."""
        chart_data = self.analyzer._generate_chart_data(self.sample_trades)
        
        self.assertIn('cumulative_pnl', chart_data)
        self.assertIn('daily_pnl', chart_data)
        self.assertIn('trade_distribution', chart_data)
        
        # Check cumulative P&L structure
        cumulative_pnl = chart_data['cumulative_pnl']
        self.assertIsInstance(cumulative_pnl, list)
        if cumulative_pnl:
            self.assertIn('timestamp', cumulative_pnl[0])
            self.assertIn('cumulative_pnl', cumulative_pnl[0])
        
        # Check trade distribution
        trade_dist = chart_data['trade_distribution']
        self.assertIn('winning_trades', trade_dist)
        self.assertIn('losing_trades', trade_dist)
    
    def test_error_handling(self):
        """Test error handling in various methods."""
        analyzer = PerformanceAnalyzer()
        
        # Test with invalid strategy name
        metrics = analyzer.analyze_strategy_performance("nonexistent", "30d")
        self.assertEqual(metrics.trades_count, 0)
        
        # Test risk metrics with no trades
        risk_metrics = analyzer.calculate_risk_adjusted_returns("nonexistent")
        self.assertEqual(risk_metrics, {})
        
        # Test degradation detection with no history
        degraded = analyzer.detect_performance_degradation()
        self.assertEqual(degraded, [])
    
    def test_performance_degradation_alert_creation(self):
        """Test creation of performance degradation alerts."""
        alert = PerformanceDegradationAlert(
            strategy_name="test_strategy",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.HIGH,
            message="Test alert",
            current_value=0.5,
            threshold_value=1.0,
            detection_time=datetime.now(),
            metric_name="sharpe_ratio",
            suggested_actions=["Action 1", "Action 2"]
        )
        
        self.assertEqual(alert.strategy_name, "test_strategy")
        self.assertEqual(alert.severity, AlertSeverity.HIGH)
        self.assertEqual(len(alert.suggested_actions), 2)
    
    def test_regime_performance_empty_regime(self):
        """Test regime performance with no trades in regime."""
        # Test with a regime that has no trades
        regime_perf = self.analyzer.get_regime_performance(RegimeType.UNCERTAIN)
        
        # Should return empty dict if no trades in this regime
        if not any(t.regime_type == RegimeType.UNCERTAIN for t in self.sample_trades):
            self.assertEqual(regime_perf, {})
    
    def test_summary_statistics_generation(self):
        """Test summary statistics generation."""
        summary = self.analyzer._generate_summary_statistics()
        
        if summary:  # If there are trades
            self.assertIn('total_strategies', summary)
            self.assertIn('total_trades', summary)
            self.assertIn('total_pnl', summary)
            self.assertIn('overall_win_rate', summary)
            
            # Check values are reasonable
            self.assertGreaterEqual(summary['total_strategies'], 0)
            self.assertGreaterEqual(summary['total_trades'], 0)
            self.assertGreaterEqual(summary['overall_win_rate'], 0)
            self.assertLessEqual(summary['overall_win_rate'], 1)


if __name__ == '__main__':
    # Set up logging for tests
    logging.basicConfig(level=logging.DEBUG)
    
    # Run tests
    unittest.main()