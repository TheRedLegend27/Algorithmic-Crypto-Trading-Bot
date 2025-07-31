#!/usr/bin/env python3
"""
Performance Degradation Detection Demo

This script demonstrates the enhanced performance degradation detection capabilities
of the adaptive trading bot's performance analyzer.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datetime import datetime, timedelta
from bot.adaptive.performance_analyzer import (
    PerformanceAnalyzer, TradeRecord, PerformanceDegradationAlert,
    AlertType, AlertSeverity
)
from bot.adaptive.data_models import PerformanceMetrics
from bot.adaptive.enums import RegimeType


def create_sample_trades(strategy_name: str, performance_pattern: str = "degrading") -> list:
    """Create sample trades with different performance patterns."""
    trades = []
    base_time = datetime.now() - timedelta(days=30)
    
    if performance_pattern == "degrading":
        # Create trades showing clear performance degradation
        for i in range(30):
            # Performance degrades over time
            performance_factor = max(0.2, 1.0 - (i * 0.025))
            
            # Winning trade probability decreases
            is_winning = np.random.random() < (0.7 * performance_factor)
            
            if is_winning:
                pnl = np.random.uniform(50, 200) * performance_factor
                pnl_pct = np.random.uniform(2, 8) * performance_factor
            else:
                pnl = -np.random.uniform(30, 150) * (2 - performance_factor)
                pnl_pct = -np.random.uniform(1, 6) * (2 - performance_factor)
            
            trade = TradeRecord(
                trade_id=f"{strategy_name}_trade_{i}",
                strategy_name=strategy_name,
                pair="BTCUSD",
                side="buy" if is_winning else "sell",
                entry_price=50000.0,
                exit_price=50000.0 + (pnl / 0.01),
                quantity=0.01,
                entry_time=base_time + timedelta(days=i),
                exit_time=base_time + timedelta(days=i, hours=1),
                pnl=pnl,
                pnl_percentage=pnl_pct,
                regime_type=np.random.choice(list(RegimeType)),
                fees=5.0
            )
            trades.append(trade)
    
    elif performance_pattern == "recovering":
        # Create trades showing recovery after initial poor performance
        for i in range(30):
            if i < 15:
                # Poor performance initially
                performance_factor = 0.3
            else:
                # Improving performance
                performance_factor = 0.3 + ((i - 15) * 0.05)
            
            is_winning = np.random.random() < (0.4 + 0.3 * performance_factor)
            
            if is_winning:
                pnl = np.random.uniform(50, 200) * performance_factor
                pnl_pct = np.random.uniform(2, 8) * performance_factor
            else:
                pnl = -np.random.uniform(30, 150)
                pnl_pct = -np.random.uniform(1, 6)
            
            trade = TradeRecord(
                trade_id=f"{strategy_name}_trade_{i}",
                strategy_name=strategy_name,
                pair="ETHUSD",
                side="buy" if is_winning else "sell",
                entry_price=3000.0,
                exit_price=3000.0 + (pnl / 0.1),
                quantity=0.1,
                entry_time=base_time + timedelta(days=i),
                exit_time=base_time + timedelta(days=i, hours=1),
                pnl=pnl,
                pnl_percentage=pnl_pct,
                regime_type=np.random.choice(list(RegimeType)),
                fees=3.0
            )
            trades.append(trade)
    
    return trades


def demonstrate_degradation_detection():
    """Demonstrate performance degradation detection."""
    print("=== Performance Degradation Detection Demo ===\n")
    
    # Initialize performance analyzer
    analyzer = PerformanceAnalyzer(
        risk_free_rate=0.02,
        benchmark_return=0.05
    )
    
    # Create sample strategies with different patterns
    print("1. Creating sample trading data...")
    
    # Strategy 1: Degrading performance
    degrading_trades = create_sample_trades("momentum_strategy", "degrading")
    for trade in degrading_trades:
        analyzer.add_trade_record(trade)
    
    # Strategy 2: Recovering performance
    recovering_trades = create_sample_trades("mean_reversion_strategy", "recovering")
    for trade in recovering_trades:
        analyzer.add_trade_record(trade)
    
    print(f"   - Created {len(degrading_trades)} trades for momentum_strategy (degrading)")
    print(f"   - Created {len(recovering_trades)} trades for mean_reversion_strategy (recovering)")
    
    # Build performance history
    print("\n2. Building performance history...")
    
    strategies = ["momentum_strategy", "mean_reversion_strategy"]
    for strategy in strategies:
        # Create performance history by analyzing different time windows
        for days_back in [30, 20, 15, 10, 7]:
            metrics = analyzer.analyze_strategy_performance(strategy, f"{days_back}d")
            print(f"   - {strategy} ({days_back}d): Sharpe={metrics.sharpe_ratio:.2f}, Win Rate={metrics.win_rate:.2f}")
    
    # Test degradation detection
    print("\n3. Running degradation detection...")
    
    alerts = analyzer.detect_performance_degradation(threshold=-0.2)
    
    print(f"\nDetected {len(alerts)} performance alerts:")
    for alert in alerts:
        print(f"\n--- {alert.alert_type.value.upper()} ALERT ---")
        print(f"Strategy: {alert.strategy_name}")
        print(f"Severity: {alert.severity.value}")
        print(f"Metric: {alert.metric_name}")
        print(f"Current Value: {alert.current_value:.3f}")
        print(f"Threshold: {alert.threshold_value:.3f}")
        print(f"Message: {alert.message}")
        if alert.p_value:
            print(f"Statistical Significance (p-value): {alert.p_value:.4f}")
        print(f"Suggested Actions: {', '.join(alert.suggested_actions)}")
    
    # Test benchmark comparison
    print("\n4. Testing benchmark comparison...")
    
    for strategy in strategies:
        analyzer.update_performance_benchmarks(strategy)
        benchmarks = analyzer.performance_benchmarks.get(strategy, {})
        
        print(f"\n{strategy} benchmarks:")
        for metric_name, benchmark in benchmarks.items():
            print(f"   - {metric_name}: {benchmark.benchmark_value:.3f} "
                  f"(CI: {benchmark.confidence_interval[0]:.3f} - {benchmark.confidence_interval[1]:.3f})")
    
    # Test rolling performance comparison
    print("\n5. Rolling performance comparison...")
    
    for strategy in strategies:
        rolling_comparison = analyzer.get_rolling_performance_comparison(strategy, window_days=10)
        
        if rolling_comparison:
            print(f"\n{strategy} rolling comparison (sample windows):")
            # Show first few windows
            for i, (window_key, comparison) in enumerate(list(rolling_comparison.items())[:3]):
                benchmark = comparison['benchmark']
                current_vs_benchmark = comparison['current_vs_benchmark']
                
                print(f"   Window {i+1}:")
                print(f"     Sharpe benchmark: {benchmark['sharpe_ratio']:.3f}")
                print(f"     Current vs benchmark: {current_vs_benchmark['sharpe_ratio_diff']:.3f}")
    
    # Test recovery detection
    print("\n6. Testing recovery detection...")
    
    for strategy in strategies:
        recovery_alert = analyzer.detect_performance_recovery(strategy)
        
        if recovery_alert:
            print(f"\n--- RECOVERY DETECTED ---")
            print(f"Strategy: {recovery_alert.strategy_name}")
            print(f"Message: {recovery_alert.message}")
            print(f"Current Sharpe Ratio: {recovery_alert.current_value:.3f}")
            print(f"Benchmark: {recovery_alert.threshold_value:.3f}")
        else:
            print(f"No recovery detected for {strategy}")
    
    # Generate comprehensive report
    print("\n7. Generating comprehensive performance report...")
    
    report = analyzer.generate_performance_report(include_charts=False)
    
    print(f"\nReport Summary:")
    summary = report.get('summary', {})
    print(f"   - Total Strategies: {summary.get('total_strategies', 0)}")
    print(f"   - Total Trades: {summary.get('total_trades', 0)}")
    print(f"   - Overall Win Rate: {summary.get('overall_win_rate', 0):.2f}")
    print(f"   - Total Alerts: {len(report.get('degradation_alerts', []))}")
    
    # Show recommendations
    recommendations = report.get('recommendations', [])
    if recommendations:
        print(f"\nRecommendations:")
        for i, rec in enumerate(recommendations[:5], 1):  # Show first 5
            print(f"   {i}. {rec}")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    demonstrate_degradation_detection()