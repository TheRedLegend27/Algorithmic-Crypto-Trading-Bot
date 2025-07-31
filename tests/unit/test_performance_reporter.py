"""
Unit tests for the performance reporter module.
"""
import unittest
import tempfile
import shutil
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import numpy as np

from bot.adaptive.performance_reporter import (
    PerformanceReporter, PerformanceAttribution, PerformanceComparison, 
    DetailedPerformanceReport
)
from bot.adaptive.performance_analyzer import PerformanceAnalyzer, TradeRecord
from bot.adaptive.data_models import PerformanceMetrics
from bot.adaptive.enums import RegimeType


class TestPerformanceReporter(unittest.TestCase):
    """Test cases for PerformanceReporter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for exports
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock performance analyzer
        self.mock_analyzer = Mock(spec=PerformanceAnalyzer)
        
        # Create sample trade records
        self.sample_trades = [
            TradeRecord(
                trade_id="trade_1",
                strategy_name="strategy_a",
                pair="BTCUSD",
                side="buy",
                entry_price=50000,
                exit_price=51000,
                quantity=0.1,
                entry_time=datetime.now() - timedelta(hours=2),
                exit_time=datetime.now() - timedelta(hours=1),
                pnl=100,
                pnl_percentage=2.0,
                regime_type=RegimeType.TRENDING_BULL
            ),
            TradeRecord(
                trade_id="trade_2",
                strategy_name="strategy_b",
                pair="ETHUSD",
                side="sell",
                entry_price=3000,
                exit_price=2950,
                quantity=1.0,
                entry_time=datetime.now() - timedelta(hours=3),
                exit_time=datetime.now() - timedelta(minutes=30),
                pnl=50,
                pnl_percentage=1.67,
                regime_type=RegimeType.RANGING
            )
        ]
        
        # Create sample performance metrics
        self.sample_metrics = PerformanceMetrics(
            total_return=0.05,
            annualized_return=0.15,
            excess_return=0.13,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=0.08,
            volatility=0.12,
            downside_deviation=0.08,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=2),
            trades_count=10,
            avg_win=150,
            avg_loss=-80,
            regime_performance={RegimeType.TRENDING_BULL: 0.08, RegimeType.RANGING: 0.02}
        )
        
        # Set up mock analyzer behavior
        self.mock_analyzer.trade_records = {
            "strategy_a": [self.sample_trades[0]],
            "strategy_b": [self.sample_trades[1]]
        }
        self.mock_analyzer.degradation_alerts = []
        self.mock_analyzer._parse_timeframe.return_value = datetime.now() - timedelta(days=30)
        self.mock_analyzer._get_trades_in_timeframe.return_value = self.sample_trades
        self.mock_analyzer._calculate_comprehensive_metrics.return_value = self.sample_metrics
        self.mock_analyzer.analyze_strategy_performance.return_value = self.sample_metrics
        self.mock_analyzer.get_regime_performance.return_value = {"total_pnl": 150, "win_rate": 0.65}
        self.mock_analyzer._parse_timeframe_to_delta.return_value = timedelta(days=30)
        self.mock_analyzer._create_empty_metrics.return_value = PerformanceMetrics(
            total_return=0, annualized_return=0, excess_return=0,
            sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
            max_drawdown=0, volatility=0, downside_deviation=0,
            win_rate=0, profit_factor=0, avg_trade_duration=timedelta(),
            trades_count=0, avg_win=0, avg_loss=0
        )
        
        # Create reporter instance
        self.reporter = PerformanceReporter(
            performance_analyzer=self.mock_analyzer,
            export_directory=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test reporter initialization."""
        self.assertIsInstance(self.reporter, PerformanceReporter)
        self.assertEqual(self.reporter.analyzer, self.mock_analyzer)
        self.assertTrue(Path(self.temp_dir).exists())
        self.assertEqual(len(self.reporter.report_cache), 0)
    
    def test_generate_detailed_report_basic(self):
        """Test basic detailed report generation."""
        report = self.reporter.generate_detailed_report(
            report_period="30d",
            include_charts=False,
            include_attribution=False
        )
        
        self.assertIsInstance(report, DetailedPerformanceReport)
        self.assertEqual(report.report_period, "30d")
        self.assertIsNotNone(report.generated_at)
        self.assertIsNotNone(report.executive_summary)
        self.assertIsNotNone(report.strategy_performance)
        self.assertIsNotNone(report.report_configuration)
    
    def test_generate_detailed_report_with_charts(self):
        """Test detailed report generation with charts."""
        report = self.reporter.generate_detailed_report(
            report_period="7d",
            include_charts=True,
            include_attribution=True
        )
        
        self.assertIsInstance(report, DetailedPerformanceReport)
        self.assertIsNotNone(report.time_series_data)
        self.assertIsNotNone(report.performance_attribution)
        self.assertTrue(report.report_configuration["include_charts"])
        self.assertTrue(report.report_configuration["include_attribution"])
    
    def test_generate_detailed_report_with_strategy_filter(self):
        """Test detailed report generation with strategy filter."""
        strategy_filter = ["strategy_a"]
        
        report = self.reporter.generate_detailed_report(
            report_period="30d",
            strategy_filter=strategy_filter
        )
        
        self.assertEqual(report.report_configuration["strategy_filter"], strategy_filter)
        self.assertIn("strategy_a", report.strategy_performance)
    
    def test_calculate_performance_attribution(self):
        """Test performance attribution calculation."""
        attribution = self.reporter.calculate_performance_attribution(
            report_period="30d",
            attribution_method="absolute"
        )
        
        self.assertIsInstance(attribution, PerformanceAttribution)
        self.assertEqual(attribution.attribution_period, "30d")
        self.assertIsNotNone(attribution.strategy_attribution)
        self.assertIsNotNone(attribution.regime_attribution)
        self.assertIsNotNone(attribution.time_period_attribution)
        self.assertIsNotNone(attribution.pair_attribution)
    
    def test_calculate_performance_attribution_relative(self):
        """Test relative performance attribution calculation."""
        attribution = self.reporter.calculate_performance_attribution(
            report_period="7d",
            attribution_method="relative"
        )
        
        self.assertIsInstance(attribution, PerformanceAttribution)
        
        # Check that relative attribution sums to approximately 1.0 (allowing for floating point errors)
        if attribution.strategy_attribution:
            total_attribution = sum(attribution.strategy_attribution.values())
            self.assertAlmostEqual(abs(total_attribution), 1.0, places=2)
    
    def test_compare_performance_configurations(self):
        """Test performance configuration comparison."""
        comparison = self.reporter.compare_performance_configurations(
            baseline_config="previous",
            comparison_config="current",
            comparison_period="30d"
        )
        
        self.assertIsInstance(comparison, PerformanceComparison)
        self.assertEqual(comparison.baseline_config, "previous")
        self.assertEqual(comparison.comparison_config, "current")
        self.assertEqual(comparison.comparison_period, "30d")
        self.assertIsNotNone(comparison.baseline_metrics)
        self.assertIsNotNone(comparison.comparison_metrics)
        self.assertIsNotNone(comparison.relative_performance)
    
    def test_export_report_json(self):
        """Test JSON report export."""
        report = self.reporter.generate_detailed_report("30d")
        
        filepath = self.reporter.export_report_json(report)
        
        self.assertTrue(Path(filepath).exists())
        
        # Verify JSON content
        with open(filepath, 'r') as f:
            exported_data = json.load(f)
        
        self.assertIn('report_id', exported_data)
        self.assertIn('generated_at', exported_data)
        self.assertIn('executive_summary', exported_data)
    
    def test_export_report_json_custom_filename(self):
        """Test JSON report export with custom filename."""
        report = self.reporter.generate_detailed_report("7d")
        custom_filename = "custom_report.json"
        
        filepath = self.reporter.export_report_json(report, custom_filename)
        
        self.assertTrue(filepath.endswith(custom_filename))
        self.assertTrue(Path(filepath).exists())
    
    def test_export_report_csv(self):
        """Test CSV report export."""
        report = self.reporter.generate_detailed_report("30d")
        
        filepath = self.reporter.export_report_csv(report)
        
        self.assertTrue(Path(filepath).exists())
        
        # Verify CSV content
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.assertEqual(headers, ['Metric', 'Value', 'Category', 'Strategy'])
            
            # Check that there's at least one data row
            first_row = next(reader, None)
            self.assertIsNotNone(first_row)
            self.assertEqual(len(first_row), 4)
    
    def test_export_attribution_analysis(self):
        """Test attribution analysis export."""
        attribution = self.reporter.calculate_performance_attribution("30d")
        
        filepath = self.reporter.export_attribution_analysis(attribution)
        
        self.assertTrue(Path(filepath).exists())
        
        # Verify JSON content
        with open(filepath, 'r') as f:
            exported_data = json.load(f)
        
        self.assertIn('strategy_attribution', exported_data)
        self.assertIn('regime_attribution', exported_data)
        self.assertIn('generated_at', exported_data)
    
    def test_export_comparison_analysis(self):
        """Test comparison analysis export."""
        comparison = self.reporter.compare_performance_configurations(
            "previous", "current", "30d"
        )
        
        filepath = self.reporter.export_comparison_analysis(comparison)
        
        self.assertTrue(Path(filepath).exists())
        
        # Verify JSON content
        with open(filepath, 'r') as f:
            exported_data = json.load(f)
        
        self.assertIn('comparison_id', exported_data)
        self.assertIn('baseline_config', exported_data)
        self.assertIn('comparison_config', exported_data)
    
    def test_generate_visualization_data(self):
        """Test visualization data generation."""
        report = self.reporter.generate_detailed_report("30d", include_charts=True)
        
        viz_data = self.reporter.generate_visualization_data(report)
        
        self.assertIn('charts', viz_data)
        self.assertIn('tables', viz_data)
        self.assertIn('metrics', viz_data)
        
        # Check chart data structure
        if 'strategy_performance' in viz_data['charts']:
            chart_data = viz_data['charts']['strategy_performance']
            self.assertIn('type', chart_data)
            self.assertIn('data', chart_data)
    
    def test_report_caching(self):
        """Test report caching functionality."""
        # Generate first report
        report1 = self.reporter.generate_detailed_report("30d")
        
        # Check cache
        self.assertEqual(len(self.reporter.report_cache), 1)
        
        # Generate second report with same parameters (should use cache)
        with patch.object(self.reporter, '_generate_executive_summary') as mock_summary:
            report2 = self.reporter.generate_detailed_report("30d")
            
            # Should not call the expensive operations again
            mock_summary.assert_not_called()
        
        self.assertEqual(report1.report_id, report2.report_id)
    
    def test_error_handling_in_report_generation(self):
        """Test error handling during report generation."""
        # Mock analyzer to raise exception during executive summary generation
        self.mock_analyzer.trade_records = {"strategy_a": [self.sample_trades[0]]}  # Keep some trades
        self.mock_analyzer._get_trades_in_timeframe.return_value = [self.sample_trades[0]]  # Return trades
        self.mock_analyzer._calculate_comprehensive_metrics.side_effect = Exception("Test error")
        
        report = self.reporter.generate_detailed_report("30d")
        
        # Should return error report instead of crashing
        self.assertIsInstance(report, DetailedPerformanceReport)
        self.assertIn("error", report.executive_summary)
    
    def test_error_handling_in_attribution(self):
        """Test error handling during attribution calculation."""
        # Mock analyzer to raise exception
        self.mock_analyzer._parse_timeframe.side_effect = Exception("Test error")
        
        attribution = self.reporter.calculate_performance_attribution("30d")
        
        # Should return empty attribution instead of crashing
        self.assertIsInstance(attribution, PerformanceAttribution)
        self.assertEqual(len(attribution.strategy_attribution), 0)
    
    def test_error_handling_in_export(self):
        """Test error handling during export operations."""
        report = self.reporter.generate_detailed_report("30d")
        
        # Test with read-only directory to simulate permission error
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            
            with self.assertRaises(PermissionError):
                PerformanceReporter(
                    self.mock_analyzer,
                    export_directory="/some/path"
                )
    
    def test_executive_summary_generation(self):
        """Test executive summary generation."""
        report = self.reporter.generate_detailed_report("30d")
        
        summary = report.executive_summary
        
        self.assertIn('total_return', summary)
        self.assertIn('sharpe_ratio', summary)
        self.assertIn('report_period', summary)
        self.assertIn('strategies_analyzed', summary)
        
        if 'best_strategy' in summary:
            self.assertIn('name', summary['best_strategy'])
            self.assertIn('return', summary['best_strategy'])
    
    def test_strategy_ranking(self):
        """Test strategy ranking functionality."""
        # Set up different performance for strategies
        strategy_metrics = {
            "strategy_a": PerformanceMetrics(
                total_return=0.1, annualized_return=0.3, excess_return=0.28,
                sharpe_ratio=1.5, sortino_ratio=1.8, calmar_ratio=1.0,
                max_drawdown=0.05, volatility=0.15, downside_deviation=0.1,
                win_rate=0.7, profit_factor=2.0, avg_trade_duration=timedelta(hours=1),
                trades_count=20, avg_win=100, avg_loss=-50
            ),
            "strategy_b": PerformanceMetrics(
                total_return=0.05, annualized_return=0.15, excess_return=0.13,
                sharpe_ratio=0.8, sortino_ratio=1.0, calmar_ratio=0.6,
                max_drawdown=0.08, volatility=0.18, downside_deviation=0.12,
                win_rate=0.6, profit_factor=1.5, avg_trade_duration=timedelta(hours=2),
                trades_count=15, avg_win=80, avg_loss=-60
            )
        }
        
        rankings = self.reporter._rank_strategies(strategy_metrics)
        
        self.assertEqual(len(rankings), 2)
        # Strategy A should rank higher due to better Sharpe ratio
        self.assertEqual(rankings[0][0], "strategy_a")
        self.assertEqual(rankings[1][0], "strategy_b")
    
    def test_risk_analysis(self):
        """Test risk analysis functionality."""
        report = self.reporter.generate_detailed_report("30d")
        
        risk_analysis = report.risk_analysis
        
        self.assertIsInstance(risk_analysis, dict)
        if risk_analysis:
            # Check for expected risk metrics
            expected_metrics = ['max_drawdown', 'volatility', 'strategy_risks']
            for metric in expected_metrics:
                if metric in risk_analysis:
                    self.assertIsNotNone(risk_analysis[metric])
    
    def test_regime_performance_analysis(self):
        """Test regime performance analysis."""
        report = self.reporter.generate_detailed_report("30d")
        
        regime_performance = report.regime_performance
        
        self.assertIsInstance(regime_performance, dict)
        # Should have performance data for regimes that have trades
        if regime_performance:
            for regime, performance in regime_performance.items():
                self.assertIsInstance(performance, dict)
    
    def test_time_series_data_generation(self):
        """Test time series data generation."""
        report = self.reporter.generate_detailed_report("30d", include_charts=True)
        
        time_series = report.time_series_data
        
        self.assertIsInstance(time_series, dict)
        if 'cumulative_returns' in time_series:
            cumulative_data = time_series['cumulative_returns']
            self.assertIsInstance(cumulative_data, list)
            
            if cumulative_data:
                # Check structure of first data point
                first_point = cumulative_data[0]
                self.assertIn('timestamp', first_point)
                self.assertIn('cumulative_pnl', first_point)
                self.assertIn('trade_pnl', first_point)
    
    def test_data_quality_metrics(self):
        """Test data quality metrics calculation."""
        report = self.reporter.generate_detailed_report("30d")
        
        quality_metrics = report.data_quality_metrics
        
        self.assertIsInstance(quality_metrics, dict)
        self.assertIn('total_trades', quality_metrics)
        self.assertIn('strategies_with_data', quality_metrics)
        self.assertIn('data_coverage', quality_metrics)
    
    def test_recommendations_generation(self):
        """Test recommendations generation."""
        report = self.reporter.generate_detailed_report("30d")
        
        recommendations = report.recommendations
        
        self.assertIsInstance(recommendations, list)
        # Each recommendation should be a string
        for recommendation in recommendations:
            self.assertIsInstance(recommendation, str)
    
    def test_csv_data_conversion(self):
        """Test CSV data conversion."""
        report = self.reporter.generate_detailed_report("30d")
        
        csv_data = self.reporter._convert_report_to_csv_data(report)
        
        self.assertIsInstance(csv_data, list)
        if csv_data:
            # Check structure of first row
            first_row = csv_data[0]
            self.assertEqual(len(first_row), 4)  # Metric, Value, Category, Strategy
    
    def test_serialization_for_export(self):
        """Test report serialization for export."""
        report = self.reporter.generate_detailed_report("30d")
        
        serialized = self.reporter._serialize_report_for_export(report)
        
        self.assertIsInstance(serialized, dict)
        self.assertIn('report_id', serialized)
        self.assertIn('generated_at', serialized)
        
        # Check that datetime objects are properly serialized
        self.assertIsInstance(serialized['generated_at'], str)


class TestPerformanceAttribution(unittest.TestCase):
    """Test cases for PerformanceAttribution class."""
    
    def test_initialization(self):
        """Test PerformanceAttribution initialization."""
        attribution = PerformanceAttribution(
            strategy_attribution={"strategy_a": 0.6, "strategy_b": 0.4},
            regime_attribution={"trending": 0.8, "ranging": 0.2},
            total_return=0.15,
            attribution_period="30d"
        )
        
        self.assertEqual(attribution.total_return, 0.15)
        self.assertEqual(attribution.attribution_period, "30d")
        self.assertEqual(len(attribution.strategy_attribution), 2)
        self.assertEqual(len(attribution.regime_attribution), 2)


class TestPerformanceComparison(unittest.TestCase):
    """Test cases for PerformanceComparison class."""
    
    def test_initialization(self):
        """Test PerformanceComparison initialization."""
        baseline_metrics = PerformanceMetrics(
            total_return=0.05, annualized_return=0.15, excess_return=0.13,
            sharpe_ratio=1.0, sortino_ratio=1.2, calmar_ratio=0.8,
            max_drawdown=0.08, volatility=0.12, downside_deviation=0.08,
            win_rate=0.6, profit_factor=1.5, avg_trade_duration=timedelta(hours=2),
            trades_count=10, avg_win=100, avg_loss=-60
        )
        
        comparison_metrics = PerformanceMetrics(
            total_return=0.08, annualized_return=0.20, excess_return=0.18,
            sharpe_ratio=1.3, sortino_ratio=1.5, calmar_ratio=1.0,
            max_drawdown=0.06, volatility=0.15, downside_deviation=0.10,
            win_rate=0.65, profit_factor=1.8, avg_trade_duration=timedelta(hours=1.5),
            trades_count=15, avg_win=120, avg_loss=-50
        )
        
        comparison = PerformanceComparison(
            comparison_id="test_comp",
            baseline_config="config_a",
            comparison_config="config_b",
            baseline_metrics=baseline_metrics,
            comparison_metrics=comparison_metrics,
            comparison_period="30d"
        )
        
        self.assertEqual(comparison.comparison_id, "test_comp")
        self.assertEqual(comparison.baseline_config, "config_a")
        self.assertEqual(comparison.comparison_config, "config_b")
        self.assertEqual(comparison.comparison_period, "30d")


if __name__ == '__main__':
    unittest.main()