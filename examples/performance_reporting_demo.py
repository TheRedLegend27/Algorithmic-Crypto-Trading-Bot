"""
Demo script for the performance reporting and visualization functionality.

This script demonstrates how to use the PerformanceReporter to generate comprehensive
performance reports, attribution analysis, and export functionality.
"""
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.adaptive.performance_analyzer import PerformanceAnalyzer, TradeRecord
from bot.adaptive.performance_reporter import PerformanceReporter
from bot.adaptive.enums import RegimeType


def create_sample_trades():
    """Create sample trade data for demonstration."""
    trades = []
    
    # Strategy A trades (generally profitable)
    base_time = datetime.now() - timedelta(days=30)
    
    for i in range(20):
        trade_time = base_time + timedelta(hours=i * 6)
        profit = 100 + (i * 10) if i % 4 != 0 else -50  # 75% win rate
        
        trade = TradeRecord(
            trade_id=f"trade_a_{i}",
            strategy_name="momentum_strategy",
            pair="BTCUSD",
            side="buy" if i % 2 == 0 else "sell",
            entry_price=50000 + (i * 100),
            exit_price=50000 + (i * 100) + profit,
            quantity=0.1,
            entry_time=trade_time,
            exit_time=trade_time + timedelta(hours=2),
            pnl=profit,
            pnl_percentage=(profit / 50000) * 100,
            regime_type=RegimeType.TRENDING_BULL if i < 10 else RegimeType.RANGING
        )
        trades.append(trade)
    
    # Strategy B trades (mixed performance)
    for i in range(15):
        trade_time = base_time + timedelta(hours=i * 8)
        profit = 80 if i % 3 != 0 else -120  # 67% win rate, but worse risk/reward
        
        trade = TradeRecord(
            trade_id=f"trade_b_{i}",
            strategy_name="mean_reversion_strategy",
            pair="ETHUSD",
            side="buy" if i % 2 == 0 else "sell",
            entry_price=3000 + (i * 50),
            exit_price=3000 + (i * 50) + profit,
            quantity=1.0,
            entry_time=trade_time,
            exit_time=trade_time + timedelta(hours=3),
            pnl=profit,
            pnl_percentage=(profit / 3000) * 100,
            regime_type=RegimeType.RANGING if i < 8 else RegimeType.HIGH_VOLATILITY
        )
        trades.append(trade)
    
    # Strategy C trades (underperforming)
    for i in range(10):
        trade_time = base_time + timedelta(hours=i * 12)
        profit = 50 if i % 5 != 0 else -200  # 80% win rate but poor risk management
        
        trade = TradeRecord(
            trade_id=f"trade_c_{i}",
            strategy_name="breakout_strategy",
            pair="SOLUSD",
            side="buy" if i % 2 == 0 else "sell",
            entry_price=100 + (i * 5),
            exit_price=100 + (i * 5) + profit,
            quantity=5.0,
            entry_time=trade_time,
            exit_time=trade_time + timedelta(hours=1),
            pnl=profit,
            pnl_percentage=(profit / 100) * 100,
            regime_type=RegimeType.HIGH_VOLATILITY
        )
        trades.append(trade)
    
    return trades


def setup_performance_analyzer(trades):
    """Set up the performance analyzer with sample data."""
    analyzer = PerformanceAnalyzer()
    
    # Add trades to analyzer
    for trade in trades:
        analyzer.add_trade_record(trade)
    
    return analyzer


def demonstrate_basic_reporting(reporter):
    """Demonstrate basic performance reporting functionality."""
    print("=" * 60)
    print("BASIC PERFORMANCE REPORTING DEMO")
    print("=" * 60)
    
    # Generate a detailed report
    print("\n1. Generating detailed performance report...")
    report = reporter.generate_detailed_report(
        report_period="30d",
        include_charts=True,
        include_attribution=True
    )
    
    print(f"Report ID: {report.report_id}")
    print(f"Generated at: {report.generated_at}")
    print(f"Report period: {report.report_period}")
    
    # Display executive summary
    print("\n2. Executive Summary:")
    summary = report.executive_summary
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    {sub_key}: {sub_value}")
        else:
            print(f"  {key}: {value}")
    
    # Display strategy performance
    print("\n3. Strategy Performance:")
    for strategy, metrics in report.strategy_performance.items():
        print(f"  {strategy}:")
        print(f"    Total Return: {metrics.total_return:.4f}")
        print(f"    Sharpe Ratio: {metrics.sharpe_ratio:.4f}")
        print(f"    Win Rate: {metrics.win_rate:.2%}")
        print(f"    Max Drawdown: {metrics.max_drawdown:.2%}")
        print(f"    Trades: {metrics.trades_count}")
    
    # Display strategy rankings
    print("\n4. Strategy Rankings (by Sharpe Ratio):")
    for i, (strategy, sharpe) in enumerate(report.strategy_rankings, 1):
        print(f"  {i}. {strategy}: {sharpe:.4f}")
    
    return report


def demonstrate_attribution_analysis(reporter):
    """Demonstrate performance attribution analysis."""
    print("\n" + "=" * 60)
    print("PERFORMANCE ATTRIBUTION ANALYSIS DEMO")
    print("=" * 60)
    
    # Calculate attribution
    print("\n1. Calculating performance attribution...")
    attribution = reporter.calculate_performance_attribution(
        report_period="30d",
        attribution_method="absolute"
    )
    
    print(f"Total Return: {attribution.total_return:.2f}")
    print(f"Attribution Period: {attribution.attribution_period}")
    
    # Strategy attribution
    print("\n2. Strategy Attribution:")
    for strategy, contribution in attribution.strategy_attribution.items():
        percentage = (contribution / attribution.total_return * 100) if attribution.total_return != 0 else 0
        print(f"  {strategy}: {contribution:.2f} ({percentage:.1f}%)")
    
    # Regime attribution
    print("\n3. Regime Attribution:")
    for regime, contribution in attribution.regime_attribution.items():
        percentage = (contribution / attribution.total_return * 100) if attribution.total_return != 0 else 0
        print(f"  {regime}: {contribution:.2f} ({percentage:.1f}%)")
    
    # Pair attribution
    print("\n4. Pair Attribution:")
    for pair, contribution in attribution.pair_attribution.items():
        percentage = (contribution / attribution.total_return * 100) if attribution.total_return != 0 else 0
        print(f"  {pair}: {contribution:.2f} ({percentage:.1f}%)")
    
    return attribution


def demonstrate_comparison_analysis(reporter):
    """Demonstrate performance comparison functionality."""
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON ANALYSIS DEMO")
    print("=" * 60)
    
    # Compare configurations
    print("\n1. Comparing performance configurations...")
    comparison = reporter.compare_performance_configurations(
        baseline_config="previous",
        comparison_config="current",
        comparison_period="30d"
    )
    
    print(f"Comparison ID: {comparison.comparison_id}")
    print(f"Baseline: {comparison.baseline_config}")
    print(f"Comparison: {comparison.comparison_config}")
    
    # Display metrics comparison
    print("\n2. Metrics Comparison:")
    baseline = comparison.baseline_metrics
    current = comparison.comparison_metrics
    
    metrics_to_compare = [
        ('Total Return', 'total_return'),
        ('Sharpe Ratio', 'sharpe_ratio'),
        ('Win Rate', 'win_rate'),
        ('Max Drawdown', 'max_drawdown')
    ]
    
    for name, attr in metrics_to_compare:
        baseline_val = getattr(baseline, attr)
        current_val = getattr(current, attr)
        change = current_val - baseline_val
        change_pct = (change / baseline_val * 100) if baseline_val != 0 else 0
        
        print(f"  {name}:")
        print(f"    Baseline: {baseline_val:.4f}")
        print(f"    Current: {current_val:.4f}")
        print(f"    Change: {change:+.4f} ({change_pct:+.1f}%)")
    
    # Display relative performance
    print("\n3. Relative Performance:")
    for metric, change in comparison.relative_performance.items():
        print(f"  {metric}: {change:+.4f}")
    
    return comparison


def demonstrate_export_functionality(reporter, report, attribution, comparison):
    """Demonstrate export functionality."""
    print("\n" + "=" * 60)
    print("EXPORT FUNCTIONALITY DEMO")
    print("=" * 60)
    
    # Create exports directory
    export_dir = Path("demo_exports")
    export_dir.mkdir(exist_ok=True)
    
    # Export report to JSON
    print("\n1. Exporting detailed report to JSON...")
    json_path = reporter.export_report_json(report, "demo_performance_report.json")
    print(f"Exported to: {json_path}")
    
    # Export report to CSV
    print("\n2. Exporting detailed report to CSV...")
    csv_path = reporter.export_report_csv(report, "demo_performance_report.csv")
    print(f"Exported to: {csv_path}")
    
    # Export attribution analysis
    print("\n3. Exporting attribution analysis...")
    attr_path = reporter.export_attribution_analysis(attribution, "demo_attribution_analysis.json")
    print(f"Exported to: {attr_path}")
    
    # Export comparison analysis
    print("\n4. Exporting comparison analysis...")
    comp_path = reporter.export_comparison_analysis(comparison, "demo_comparison_analysis.json")
    print(f"Exported to: {comp_path}")
    
    print(f"\nAll exports saved to: {reporter.export_directory}")


def demonstrate_visualization_data(reporter, report):
    """Demonstrate visualization data generation."""
    print("\n" + "=" * 60)
    print("VISUALIZATION DATA DEMO")
    print("=" * 60)
    
    # Generate visualization data
    print("\n1. Generating visualization data...")
    viz_data = reporter.generate_visualization_data(report)
    
    # Display chart data structure
    print("\n2. Available Charts:")
    for chart_name, chart_data in viz_data['charts'].items():
        print(f"  {chart_name}: {chart_data['type']} chart")
        if 'data' in chart_data:
            if 'labels' in chart_data['data']:
                print(f"    Labels: {len(chart_data['data']['labels'])} items")
            if 'datasets' in chart_data['data']:
                print(f"    Datasets: {len(chart_data['data']['datasets'])} series")
    
    # Display table data structure
    print("\n3. Available Tables:")
    for table_name, table_data in viz_data['tables'].items():
        print(f"  {table_name}:")
        if 'headers' in table_data:
            print(f"    Headers: {table_data['headers']}")
        if 'rows' in table_data:
            print(f"    Rows: {len(table_data['rows'])} items")
    
    # Display key metrics
    print("\n4. Key Metrics:")
    for metric_name, metric_value in viz_data['metrics'].items():
        print(f"  {metric_name}: {metric_value}")


def main():
    """Main demo function."""
    print("Performance Reporting and Visualization Demo")
    print("=" * 60)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create sample data
    print("Setting up sample trade data...")
    trades = create_sample_trades()
    print(f"Created {len(trades)} sample trades across 3 strategies")
    
    # Set up performance analyzer
    print("Setting up performance analyzer...")
    analyzer = setup_performance_analyzer(trades)
    
    # Create performance reporter
    print("Creating performance reporter...")
    reporter = PerformanceReporter(
        performance_analyzer=analyzer,
        export_directory="demo_reports"
    )
    
    try:
        # Demonstrate basic reporting
        report = demonstrate_basic_reporting(reporter)
        
        # Demonstrate attribution analysis
        attribution = demonstrate_attribution_analysis(reporter)
        
        # Demonstrate comparison analysis
        comparison = demonstrate_comparison_analysis(reporter)
        
        # Demonstrate export functionality
        demonstrate_export_functionality(reporter, report, attribution, comparison)
        
        # Demonstrate visualization data
        demonstrate_visualization_data(reporter, report)
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Check the '{reporter.export_directory}' directory for exported files.")
        
    except Exception as e:
        print(f"\nError during demo: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()