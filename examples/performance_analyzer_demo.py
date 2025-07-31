#!/usr/bin/env python3
"""
Demo script for the PerformanceAnalyzer class.

This script demonstrates the comprehensive performance analysis capabilities
of the adaptive trading bot system.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta
from bot.adaptive.performance_analyzer import PerformanceAnalyzer, TradeRecord
from bot.adaptive.enums import RegimeType

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_sample_trades():
    """Create sample trade records for demonstration."""
    base_time = datetime.now() - timedelta(days=30)
    trades = []
    
    # Sample trade data: (strategy, pnl, pnl_pct, hours_offset, regime, pair)
    trade_data = [
        ("momentum_strategy", 150, 7.5, 0, RegimeType.TRENDING_BULL, "BTCUSD"),
        ("momentum_strategy", -80, -4.0, 2, RegimeType.TRENDING_BULL, "BTCUSD"),
        ("momentum_strategy", 200, 10.0, 4, RegimeType.TRENDING_BULL, "ETHUSD"),
        ("mean_reversion", 120, 6.0, 6, RegimeType.RANGING, "BTCUSD"),
        ("mean_reversion", -60, -3.0, 8, RegimeType.RANGING, "ETHUSD"),
        ("mean_reversion", 90, 4.5, 10, RegimeType.RANGING, "SOLUSD"),
        ("volatility_breakout", 300, 15.0, 12, RegimeType.HIGH_VOLATILITY, "BTCUSD"),
        ("volatility_breakout", -100, -5.0, 14, RegimeType.HIGH_VOLATILITY, "ETHUSD"),
        ("momentum_strategy", 180, 9.0, 16, RegimeType.TRENDING_BULL, "SOLUSD"),
        ("mean_reversion", -40, -2.0, 18, RegimeType.RANGING, "BTCUSD"),
        ("volatility_breakout", 250, 12.5, 20, RegimeType.HIGH_VOLATILITY, "SOLUSD"),
        ("momentum_strategy", 100, 5.0, 22, RegimeType.TRENDING_BULL, "ETHUSD"),
    ]
    
    for i, (strategy, pnl, pnl_pct, hours_offset, regime, pair) in enumerate(trade_data):
        entry_time = base_time + timedelta(hours=hours_offset)
        exit_time = entry_time + timedelta(hours=2)  # 2 hour trades
        
        trade = TradeRecord(
            trade_id=f"demo_trade_{i}",
            strategy_name=strategy,
            pair=pair,
            side="buy" if pnl > 0 else "sell",
            entry_price=50000.0 if pair == "BTCUSD" else (3000.0 if pair == "ETHUSD" else 100.0),
            exit_price=50000.0 + (pnl / 0.01) if pair == "BTCUSD" else (3000.0 + (pnl / 0.1) if pair == "ETHUSD" else 100.0 + (pnl / 1.0)),
            quantity=0.01 if pair == "BTCUSD" else (0.1 if pair == "ETHUSD" else 1.0),
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=pnl,
            pnl_percentage=pnl_pct,
            regime_type=regime,
            fees=5.0,
            metadata={
                "confidence": 0.8,
                "indicators_used": ["RSI", "MACD", "BB"],
                "market_conditions": "normal"
            }
        )
        trades.append(trade)
    
    return trades


def demonstrate_performance_analysis():
    """Demonstrate comprehensive performance analysis."""
    logger.info("=== Performance Analyzer Demo ===")
    
    # Initialize analyzer
    analyzer = PerformanceAnalyzer(
        risk_free_rate=0.02,
        benchmark_return=0.05,
        logger=logger
    )
    
    # Create and add sample trades
    trades = create_sample_trades()
    logger.info(f"Created {len(trades)} sample trades")
    
    for trade in trades:
        analyzer.add_trade_record(trade)
    
    # Analyze performance for each strategy
    strategies = ["momentum_strategy", "mean_reversion", "volatility_breakout"]
    
    logger.info("\n=== Strategy Performance Analysis ===")
    for strategy in strategies:
        logger.info(f"\n--- {strategy.upper()} ---")
        
        # Get performance metrics
        metrics = analyzer.analyze_strategy_performance(strategy, "30d")
        
        logger.info(f"Total Return: {metrics.total_return:.2%}")
        logger.info(f"Annualized Return: {metrics.annualized_return:.2%}")
        logger.info(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        logger.info(f"Sortino Ratio: {metrics.sortino_ratio:.2f}")
        logger.info(f"Max Drawdown: {metrics.max_drawdown:.2%}")
        logger.info(f"Win Rate: {metrics.win_rate:.2%}")
        logger.info(f"Profit Factor: {metrics.profit_factor:.2f}")
        logger.info(f"Total Trades: {metrics.trades_count}")
        
        # Get risk-adjusted returns
        risk_metrics = analyzer.calculate_risk_adjusted_returns(strategy)
        if risk_metrics:
            logger.info(f"Volatility: {risk_metrics.get('volatility', 0):.2%}")
            logger.info(f"Calmar Ratio: {risk_metrics.get('calmar_ratio', 0):.2f}")
    
    # Strategy comparison
    logger.info("\n=== Strategy Comparison ===")
    comparison = analyzer.compare_strategies(strategies)
    
    print("\nStrategy Comparison Table:")
    print(f"{'Strategy':<20} {'Return':<10} {'Sharpe':<8} {'Win Rate':<10} {'Trades':<8}")
    print("-" * 60)
    
    for strategy, metrics in comparison.items():
        print(f"{strategy:<20} {metrics.total_return:>8.2%} {metrics.sharpe_ratio:>7.2f} "
              f"{metrics.win_rate:>8.2%} {metrics.trades_count:>7}")
    
    # Regime performance analysis
    logger.info("\n=== Regime Performance Analysis ===")
    for regime in RegimeType:
        regime_perf = analyzer.get_regime_performance(regime)
        if regime_perf:
            logger.info(f"\n{regime.value.upper()}:")
            logger.info(f"  Total P&L: ${regime_perf['total_pnl']:.2f}")
            logger.info(f"  Win Rate: {regime_perf['win_rate']:.2%}")
            logger.info(f"  Avg Return: {regime_perf['average_return']:.2%}")
            logger.info(f"  Trade Count: {regime_perf['trade_count']}")
    
    # Performance degradation detection
    logger.info("\n=== Performance Degradation Detection ===")
    degraded_strategies = analyzer.detect_performance_degradation(-0.2)
    if degraded_strategies:
        logger.info(f"Strategies with performance degradation: {degraded_strategies}")
    else:
        logger.info("No performance degradation detected")
    
    # Generate comprehensive report
    logger.info("\n=== Comprehensive Performance Report ===")
    report = analyzer.generate_performance_report(include_charts=True)
    
    if 'summary' in report:
        summary = report['summary']
        logger.info(f"Total Strategies: {summary.get('total_strategies', 0)}")
        logger.info(f"Total Trades: {summary.get('total_trades', 0)}")
        logger.info(f"Total P&L: ${summary.get('total_pnl', 0):.2f}")
        logger.info(f"Overall Win Rate: {summary.get('overall_win_rate', 0):.2%}")
    
    # Show recommendations
    if 'recommendations' in report and report['recommendations']:
        logger.info("\n=== Recommendations ===")
        for i, recommendation in enumerate(report['recommendations'], 1):
            logger.info(f"{i}. {recommendation}")
    
    logger.info("\n=== Demo Complete ===")
    return analyzer, report


if __name__ == "__main__":
    try:
        analyzer, report = demonstrate_performance_analysis()
        logger.info("Performance analysis demo completed successfully!")
        
        # Optional: Save report to file
        import json
        with open("performance_report_demo.json", "w") as f:
            # Convert datetime objects and enums to strings for JSON serialization
            def serialize_objects(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, timedelta):
                    return str(obj)
                elif hasattr(obj, 'value'):  # Handle enums
                    return obj.value
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            # Convert enum keys to strings
            def convert_enum_keys(obj):
                if isinstance(obj, dict):
                    return {
                        (k.value if hasattr(k, 'value') else k): convert_enum_keys(v) 
                        for k, v in obj.items()
                    }
                elif isinstance(obj, list):
                    return [convert_enum_keys(item) for item in obj]
                else:
                    return obj
            
            serializable_report = convert_enum_keys(report)
            json.dump(serializable_report, f, indent=2, default=serialize_objects)
        logger.info("Report saved to performance_report_demo.json")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {str(e)}")
        raise