#!/usr/bin/env python3
"""
Demonstration of Strategy Performance Tracking and Adaptation functionality.

This script demonstrates the key features implemented in task 5.3:
- Real-time strategy performance monitoring
- Strategy allocation adjustment based on recent performance
- Strategy disabling mechanism for consistently poor performers
- Strategy re-enabling logic when conditions improve
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from bot.adaptive.adaptive_strategy_engine import AdaptiveStrategyEngine
from bot.adaptive.data_models import PerformanceMetrics
from bot.strategy import BaseStrategy, TradingSignal, SignalType


class MockStrategy(BaseStrategy):
    """Mock strategy for demonstration."""
    
    def __init__(self, name: str, signal_type: SignalType = SignalType.HOLD, 
                 confidence: float = 0.5):
        super().__init__(name)
        self.signal_type = signal_type
        self.confidence = confidence
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        return TradingSignal(
            action=self.signal_type,
            confidence=self.confidence,
            strategy=self.name,
            timestamp=datetime.now(),
            price=100.0,
            reasoning=f"Mock signal from {self.name}"
        )


def demonstrate_performance_tracking():
    """Demonstrate real-time performance tracking and adaptation."""
    
    print("=" * 80)
    print("STRATEGY PERFORMANCE TRACKING AND ADAPTATION DEMO")
    print("=" * 80)
    
    # Initialize the adaptive strategy engine
    config = {
        'hysteresis_threshold': 0.15,
        'min_switch_interval_minutes': 30,
        'min_strategies_for_ensemble': 2,
        'confidence_decay_factor': 0.95,
        'min_performance_threshold': -0.1,
        'disable_threshold': -0.2,
        'reenable_threshold': 0.05
    }
    
    # Mock the strategy imports to avoid dependency issues
    with patch.multiple(
        'bot.adaptive.adaptive_strategy_engine',
        EnhancedMomentumStrategy=Mock,
        PriceActionStrategy=Mock,
        MultiTimeframeStrategy=Mock,
        VolatilityAdjustedStrategy=Mock
    ):
        engine = AdaptiveStrategyEngine(config)
    
    # Clear default strategies and add test strategies
    engine.strategies.clear()
    engine.strategy_allocations.clear()
    
    # Add demonstration strategies
    momentum_strategy = MockStrategy("momentum_strategy", SignalType.BUY, 0.7)
    mean_reversion_strategy = MockStrategy("mean_reversion_strategy", SignalType.SELL, 0.6)
    breakout_strategy = MockStrategy("breakout_strategy", SignalType.BUY, 0.8)
    
    engine.add_strategy("momentum_strategy", momentum_strategy, {'base_weight': 0.4})
    engine.add_strategy("mean_reversion_strategy", mean_reversion_strategy, {'base_weight': 0.3})
    engine.add_strategy("breakout_strategy", breakout_strategy, {'base_weight': 0.3})
    
    print("\n1. INITIAL STRATEGY SETUP")
    print("-" * 40)
    allocations = engine.get_strategy_allocation()
    for name, allocation in allocations.items():
        print(f"Strategy: {name}")
        print(f"  Base Weight: {allocation.base_weight:.3f}")
        print(f"  Current Weight: {allocation.current_weight:.3f}")
        print(f"  Active: {allocation.is_active}")
        print()
    
    # Simulate performance data over time
    print("2. SIMULATING PERFORMANCE DATA")
    print("-" * 40)
    
    # Week 1: All strategies performing well
    print("Week 1: All strategies performing well")
    week1_performance = {
        "momentum_strategy": PerformanceMetrics(
            total_return=0.12,
            annualized_return=0.15,
            excess_return=0.08,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=1.2,
            max_drawdown=0.03,
            volatility=0.12,
            downside_deviation=0.08,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=50,
            avg_win=0.025,
            avg_loss=-0.015
        ),
        "mean_reversion_strategy": PerformanceMetrics(
            total_return=0.08,
            annualized_return=0.10,
            excess_return=0.05,
            sharpe_ratio=1.2,
            sortino_ratio=1.4,
            calmar_ratio=0.9,
            max_drawdown=0.05,
            volatility=0.15,
            downside_deviation=0.10,
            win_rate=0.60,
            profit_factor=1.5,
            avg_trade_duration=timedelta(hours=6),
            trades_count=40,
            avg_win=0.022,
            avg_loss=-0.018
        ),
        "breakout_strategy": PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.18,
            excess_return=0.12,
            sharpe_ratio=1.8,
            sortino_ratio=2.0,
            calmar_ratio=1.5,
            max_drawdown=0.02,
            volatility=0.10,
            downside_deviation=0.06,
            win_rate=0.70,
            profit_factor=2.2,
            avg_trade_duration=timedelta(hours=3),
            trades_count=60,
            avg_win=0.030,
            avg_loss=-0.012
        )
    }
    
    engine.update_strategy_weights(week1_performance)
    
    print("Updated allocations after Week 1:")
    allocations = engine.get_strategy_allocation()
    for name, allocation in allocations.items():
        print(f"  {name}: {allocation.current_weight:.3f} (Active: {allocation.is_active})")
    
    # Week 2: Mean reversion strategy starts underperforming
    print("\nWeek 2: Mean reversion strategy starts underperforming")
    week2_performance = {
        "momentum_strategy": PerformanceMetrics(
            total_return=0.10,
            annualized_return=0.12,
            excess_return=0.07,
            sharpe_ratio=1.3,
            sortino_ratio=1.5,
            calmar_ratio=1.0,
            max_drawdown=0.04,
            volatility=0.14,
            downside_deviation=0.09,
            win_rate=0.62,
            profit_factor=1.6,
            avg_trade_duration=timedelta(hours=4),
            trades_count=45,
            avg_win=0.024,
            avg_loss=-0.016
        ),
        "mean_reversion_strategy": PerformanceMetrics(
            total_return=-0.05,  # Starting to decline
            annualized_return=-0.08,
            excess_return=-0.12,
            sharpe_ratio=0.2,
            sortino_ratio=0.1,
            calmar_ratio=0.1,
            max_drawdown=0.12,
            volatility=0.25,
            downside_deviation=0.20,
            win_rate=0.45,
            profit_factor=0.9,
            avg_trade_duration=timedelta(hours=8),
            trades_count=35,
            avg_win=0.018,
            avg_loss=-0.025
        ),
        "breakout_strategy": PerformanceMetrics(
            total_return=0.13,
            annualized_return=0.16,
            excess_return=0.10,
            sharpe_ratio=1.6,
            sortino_ratio=1.8,
            calmar_ratio=1.3,
            max_drawdown=0.03,
            volatility=0.11,
            downside_deviation=0.07,
            win_rate=0.68,
            profit_factor=2.0,
            avg_trade_duration=timedelta(hours=3),
            trades_count=55,
            avg_win=0.028,
            avg_loss=-0.013
        )
    }
    
    engine.update_strategy_weights(week2_performance)
    
    print("Updated allocations after Week 2:")
    allocations = engine.get_strategy_allocation()
    for name, allocation in allocations.items():
        print(f"  {name}: {allocation.current_weight:.3f} (Active: {allocation.is_active})")
    
    # Week 3: Mean reversion strategy performance degrades further - should be disabled
    print("\nWeek 3: Mean reversion strategy degrades further")
    week3_performance = {
        "momentum_strategy": PerformanceMetrics(
            total_return=0.09,
            annualized_return=0.11,
            excess_return=0.06,
            sharpe_ratio=1.2,
            sortino_ratio=1.4,
            calmar_ratio=0.9,
            max_drawdown=0.05,
            volatility=0.15,
            downside_deviation=0.10,
            win_rate=0.60,
            profit_factor=1.5,
            avg_trade_duration=timedelta(hours=5),
            trades_count=42,
            avg_win=0.023,
            avg_loss=-0.017
        ),
        "mean_reversion_strategy": PerformanceMetrics(
            total_return=-0.25,  # Below disable threshold
            annualized_return=-0.30,
            excess_return=-0.35,
            sharpe_ratio=-0.8,
            sortino_ratio=-1.0,
            calmar_ratio=-0.5,
            max_drawdown=0.28,
            volatility=0.35,
            downside_deviation=0.30,
            win_rate=0.30,
            profit_factor=0.5,
            avg_trade_duration=timedelta(hours=10),
            trades_count=25,
            avg_win=0.015,
            avg_loss=-0.035
        ),
        "breakout_strategy": PerformanceMetrics(
            total_return=0.11,
            annualized_return=0.14,
            excess_return=0.08,
            sharpe_ratio=1.4,
            sortino_ratio=1.6,
            calmar_ratio=1.1,
            max_drawdown=0.04,
            volatility=0.12,
            downside_deviation=0.08,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=50,
            avg_win=0.026,
            avg_loss=-0.014
        )
    }
    
    engine.update_strategy_weights(week3_performance)
    
    print("Updated allocations after Week 3:")
    allocations = engine.get_strategy_allocation()
    for name, allocation in allocations.items():
        print(f"  {name}: {allocation.current_weight:.3f} (Active: {allocation.is_active})")
    
    # Check performance alerts
    print("\n3. PERFORMANCE ALERTS")
    print("-" * 40)
    alerts = engine.get_performance_alerts(24)
    for alert in alerts[-3:]:  # Show last 3 alerts
        print(f"Alert: {alert['alert_type']} for {alert['strategy_name']}")
        print(f"  Message: {alert['message']}")
        print(f"  Severity: {alert.get('severity', 'N/A')}")
        print(f"  Time: {alert['timestamp']}")
        print()
    
    # Week 4: Mean reversion strategy improves - should be re-enabled
    print("Week 4: Mean reversion strategy improves")
    week4_performance = {
        "momentum_strategy": PerformanceMetrics(
            total_return=0.08,
            annualized_return=0.10,
            excess_return=0.05,
            sharpe_ratio=1.1,
            sortino_ratio=1.3,
            calmar_ratio=0.8,
            max_drawdown=0.06,
            volatility=0.16,
            downside_deviation=0.11,
            win_rate=0.58,
            profit_factor=1.4,
            avg_trade_duration=timedelta(hours=5),
            trades_count=40,
            avg_win=0.022,
            avg_loss=-0.018
        ),
        "mean_reversion_strategy": PerformanceMetrics(
            total_return=0.08,  # Above re-enable threshold
            annualized_return=0.10,
            excess_return=0.05,
            sharpe_ratio=1.0,
            sortino_ratio=1.2,
            calmar_ratio=0.7,
            max_drawdown=0.08,
            volatility=0.18,
            downside_deviation=0.12,
            win_rate=0.55,
            profit_factor=1.3,
            avg_trade_duration=timedelta(hours=6),
            trades_count=38,
            avg_win=0.021,
            avg_loss=-0.019
        ),
        "breakout_strategy": PerformanceMetrics(
            total_return=0.10,
            annualized_return=0.12,
            excess_return=0.07,
            sharpe_ratio=1.3,
            sortino_ratio=1.5,
            calmar_ratio=1.0,
            max_drawdown=0.05,
            volatility=0.13,
            downside_deviation=0.09,
            win_rate=0.63,
            profit_factor=1.7,
            avg_trade_duration=timedelta(hours=4),
            trades_count=48,
            avg_win=0.025,
            avg_loss=-0.015
        )
    }
    
    engine.update_strategy_weights(week4_performance)
    
    print("Updated allocations after Week 4:")
    allocations = engine.get_strategy_allocation()
    for name, allocation in allocations.items():
        print(f"  {name}: {allocation.current_weight:.3f} (Active: {allocation.is_active})")
    
    # Show final performance summary
    print("\n4. FINAL PERFORMANCE SUMMARY")
    print("-" * 40)
    summary = engine.get_strategy_performance_summary()
    print(f"Total Strategies: {summary['total_strategies']}")
    print(f"Active Strategies: {summary['active_strategies']}")
    print("\nStrategy Details:")
    for name, details in summary['strategy_details'].items():
        print(f"  {name}:")
        print(f"    Active: {details['is_active']}")
        print(f"    Weight: {details['current_weight']:.3f}")
        print(f"    Recent Performance: {details['recent_performance']:.3f}")
        print(f"    Performance Trend: {details['performance_trend']:.3f}")
        print(f"    Confidence: {details['confidence_level']:.3f}")
    
    # Show monitoring report
    print("\n5. PERFORMANCE MONITORING REPORT")
    print("-" * 40)
    monitoring_report = engine.monitor_strategy_performance_degradation(24)
    print(f"Strategies Analyzed: {monitoring_report['strategies_analyzed']}")
    print(f"Degrading Strategies: {len(monitoring_report['degrading_strategies'])}")
    print(f"Stable Strategies: {len(monitoring_report['stable_strategies'])}")
    print(f"Improving Strategies: {len(monitoring_report['improving_strategies'])}")
    print(f"Disabled Strategies: {len(monitoring_report['disabled_strategies'])}")
    
    if monitoring_report['degrading_strategies']:
        print("\nDegrading Strategies:")
        for strategy in monitoring_report['degrading_strategies']:
            print(f"  - {strategy['strategy_name']}: {strategy['degradation_reason']}")
    
    if monitoring_report['improving_strategies']:
        print("\nImproving Strategies:")
        for strategy in monitoring_report['improving_strategies']:
            print(f"  - {strategy['strategy_name']}: {strategy['improvement_reason']}")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("✓ Real-time strategy performance monitoring")
    print("✓ Strategy allocation adjustment based on recent performance")
    print("✓ Strategy disabling mechanism for consistently poor performers")
    print("✓ Strategy re-enabling logic when conditions improve")
    print("✓ Performance alerts and notifications")
    print("✓ Comprehensive performance tracking and reporting")


if __name__ == "__main__":
    demonstrate_performance_tracking()