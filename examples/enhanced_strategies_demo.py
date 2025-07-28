#!/usr/bin/env python3
"""
Enhanced Trading Strategies Demo

This script demonstrates the enhanced trading strategies with:
- Volatility-based adjustments
- Momentum strategies with multi-timeframe analysis
- Volume-weighted and Bollinger Bands strategies
- MACD strategy with signal line crossovers
- Strategy backtesting and parameter optimization
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from bot.enhanced_strategies import (
    BollingerBandsRSIStrategy,
    MACDStrategy,
    VolumeWeightedStrategy,
    MultiTimeframeMomentumStrategy,
    StrategyBacktester,
    create_enhanced_strategy_suite,
    create_conservative_strategy_suite
)
from bot.strategy import SignalGenerator


def create_sample_data(periods: int = 1000, volatility: float = 0.02) -> pd.DataFrame:
    """Create sample OHLCV data for demonstration."""
    np.random.seed(42)
    
    # Create realistic price data with trends and cycles
    dates = pd.date_range(start='2023-01-01', periods=periods, freq='h')
    prices = []
    volumes = []
    base_price = 100.0
    base_volume = 5000
    
    for i in range(periods):
        # Add market cycles and trends
        cycle_factor = np.sin(i / 100) * 0.05  # Market cycles
        trend_factor = i / 50000  # Slight upward trend
        news_factor = 0
        
        # Add occasional news events
        if i % 200 == 0 and i > 0:
            news_factor = np.random.choice([-0.05, 0.05])  # ±5% news impact
        
        # Calculate price change
        noise = np.random.randn() * volatility
        price_change = cycle_factor + trend_factor + news_factor + noise
        base_price *= (1 + price_change)
        prices.append(base_price)
        
        # Volume increases with price volatility
        volume_factor = 1 + abs(price_change) * 20
        volume = base_volume * volume_factor * (1 + np.random.randn() * 0.3)
        volumes.append(max(1000, volume))
    
    # Create OHLCV data
    prices = np.array(prices)
    return pd.DataFrame({
        'open': prices * (1 + np.random.randn(periods) * 0.002),
        'high': prices * (1 + np.abs(np.random.randn(periods)) * 0.003),
        'low': prices * (1 - np.abs(np.random.randn(periods)) * 0.003),
        'close': prices,
        'volume': volumes
    }, index=dates)


def demonstrate_individual_strategies():
    """Demonstrate individual enhanced strategies."""
    print("=" * 60)
    print("ENHANCED TRADING STRATEGIES DEMONSTRATION")
    print("=" * 60)
    
    # Create sample data
    data = create_sample_data(periods=500, volatility=0.025)
    print(f"Created sample data: {len(data)} periods")
    print(f"Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
    print(f"Average volume: {data['volume'].mean():.0f}")
    print()
    
    # Test individual strategies
    strategies = [
        BollingerBandsRSIStrategy(),
        MACDStrategy(),
        VolumeWeightedStrategy(),
        MultiTimeframeMomentumStrategy()
    ]
    
    print("INDIVIDUAL STRATEGY SIGNALS:")
    print("-" * 40)
    
    for strategy in strategies:
        signal = strategy.calculate_signals(data)
        print(f"{strategy.name:25} | {signal.action.value:4} | "
              f"Confidence: {signal.confidence:.3f} | {signal.reasoning}")
    
    print()


def demonstrate_strategy_backtesting():
    """Demonstrate strategy backtesting capabilities."""
    print("STRATEGY BACKTESTING RESULTS:")
    print("-" * 60)
    
    # Create longer dataset for backtesting
    data = create_sample_data(periods=1000, volatility=0.02)
    backtester = StrategyBacktester(initial_capital=10000.0)
    
    strategies = [
        BollingerBandsRSIStrategy(),
        MACDStrategy(),
        VolumeWeightedStrategy(),
        MultiTimeframeMomentumStrategy()
    ]
    
    results = []
    for strategy in strategies:
        result = backtester.backtest_strategy(strategy, data)
        results.append((strategy.name, result))
        
        print(f"{strategy.name}:")
        print(f"  Total Return:    {result.total_return:8.2%}")
        print(f"  Sharpe Ratio:    {result.sharpe_ratio:8.2f}")
        print(f"  Max Drawdown:    {result.max_drawdown:8.2%}")
        print(f"  Win Rate:        {result.win_rate:8.2%}")
        print(f"  Total Trades:    {result.total_trades:8d}")
        print(f"  Avg Trade Dur:   {result.avg_trade_duration:8.1f}")
        print()
    
    # Find best performing strategy
    best_strategy = max(results, key=lambda x: x[1].sharpe_ratio)
    print(f"Best performing strategy: {best_strategy[0]} "
          f"(Sharpe: {best_strategy[1].sharpe_ratio:.2f})")
    print()


def demonstrate_parameter_optimization():
    """Demonstrate parameter optimization."""
    print("PARAMETER OPTIMIZATION EXAMPLE:")
    print("-" * 40)
    
    data = create_sample_data(periods=800, volatility=0.02)
    backtester = StrategyBacktester(initial_capital=10000.0)
    
    # Optimize Bollinger Bands parameters
    print("Optimizing Bollinger Bands RSI Strategy...")
    param_ranges = {
        'bb_period': [15, 20, 25],
        'bb_std': [1.5, 2.0, 2.5],
        'rsi_period': [10, 14, 18]
    }
    
    best_params, best_result = backtester.optimize_parameters(
        BollingerBandsRSIStrategy, data, param_ranges
    )
    
    print(f"Best parameters: {best_params}")
    print(f"Best result:")
    print(f"  Total Return:    {best_result.total_return:8.2%}")
    print(f"  Sharpe Ratio:    {best_result.sharpe_ratio:8.2f}")
    print(f"  Win Rate:        {best_result.win_rate:8.2%}")
    print()


def demonstrate_volatility_adjustment():
    """Demonstrate volatility adjustment features."""
    print("VOLATILITY ADJUSTMENT DEMONSTRATION:")
    print("-" * 45)
    
    # Create high and low volatility datasets
    high_vol_data = create_sample_data(periods=300, volatility=0.05)
    low_vol_data = create_sample_data(periods=300, volatility=0.01)
    
    strategy = BollingerBandsRSIStrategy()
    
    # Test volatility adjustments
    high_vol_adj = strategy.calculate_volatility_adjustment(high_vol_data)
    low_vol_adj = strategy.calculate_volatility_adjustment(low_vol_data)
    
    print(f"High volatility data adjustment factor: {high_vol_adj:.3f}")
    print(f"Low volatility data adjustment factor:  {low_vol_adj:.3f}")
    print()
    
    # Generate signals for both datasets
    high_vol_signal = strategy.calculate_signals(high_vol_data)
    low_vol_signal = strategy.calculate_signals(low_vol_data)
    
    print("High volatility signal:")
    print(f"  Action: {high_vol_signal.action.value}, Confidence: {high_vol_signal.confidence:.3f}")
    print(f"  Reasoning: {high_vol_signal.reasoning}")
    print()
    
    print("Low volatility signal:")
    print(f"  Action: {low_vol_signal.action.value}, Confidence: {low_vol_signal.confidence:.3f}")
    print(f"  Reasoning: {low_vol_signal.reasoning}")
    print()


def demonstrate_multi_strategy_coordination():
    """Demonstrate multi-strategy coordination."""
    print("MULTI-STRATEGY COORDINATION:")
    print("-" * 35)
    
    data = create_sample_data(periods=400, volatility=0.025)
    
    # Create enhanced and conservative strategy suites
    enhanced_strategies = create_enhanced_strategy_suite()
    conservative_strategies = create_conservative_strategy_suite()
    
    # Generate combined signals
    enhanced_generator = SignalGenerator(enhanced_strategies)
    conservative_generator = SignalGenerator(conservative_strategies)
    
    enhanced_signal = enhanced_generator.evaluate_all_strategies(data)
    conservative_signal = conservative_generator.evaluate_all_strategies(data)
    
    print("Enhanced strategy suite:")
    print(f"  Combined Signal: {enhanced_signal.action.value}")
    print(f"  Confidence:      {enhanced_signal.confidence:.3f}")
    print(f"  Reasoning:       {enhanced_signal.reasoning}")
    print()
    
    print("Conservative strategy suite:")
    print(f"  Combined Signal: {conservative_signal.action.value}")
    print(f"  Confidence:      {conservative_signal.confidence:.3f}")
    print(f"  Reasoning:       {conservative_signal.reasoning}")
    print()


def demonstrate_market_condition_adaptation():
    """Demonstrate how strategies adapt to different market conditions."""
    print("MARKET CONDITION ADAPTATION:")
    print("-" * 35)
    
    # Create different market scenarios
    bull_market = create_sample_data(periods=300, volatility=0.015)
    # Add consistent upward trend
    bull_market['close'] *= np.linspace(1.0, 1.3, len(bull_market))
    
    bear_market = create_sample_data(periods=300, volatility=0.02)
    # Add consistent downward trend
    bear_market['close'] *= np.linspace(1.0, 0.7, len(bear_market))
    
    volatile_market = create_sample_data(periods=300, volatility=0.04)
    
    strategy = MultiTimeframeMomentumStrategy()
    
    scenarios = [
        ("Bull Market", bull_market),
        ("Bear Market", bear_market),
        ("Volatile Market", volatile_market)
    ]
    
    for name, data in scenarios:
        signal = strategy.calculate_signals(data)
        vol_adj = strategy.calculate_volatility_adjustment(data)
        
        print(f"{name}:")
        print(f"  Signal:     {signal.action.value}")
        print(f"  Confidence: {signal.confidence:.3f}")
        print(f"  Vol Adj:    {vol_adj:.3f}")
        print(f"  Reasoning:  {signal.reasoning}")
        print()


def main():
    """Run all demonstrations."""
    try:
        demonstrate_individual_strategies()
        demonstrate_strategy_backtesting()
        demonstrate_parameter_optimization()
        demonstrate_volatility_adjustment()
        demonstrate_multi_strategy_coordination()
        demonstrate_market_condition_adaptation()
        
        print("=" * 60)
        print("DEMONSTRATION COMPLETE")
        print("=" * 60)
        print()
        print("Key Features Demonstrated:")
        print("✓ Volatility-based strategy adjustments")
        print("✓ Multi-timeframe momentum analysis")
        print("✓ Volume-weighted trading signals")
        print("✓ Bollinger Bands with RSI confirmation")
        print("✓ MACD with signal line crossovers")
        print("✓ Strategy backtesting and performance metrics")
        print("✓ Parameter optimization")
        print("✓ Multi-strategy coordination")
        print("✓ Market condition adaptation")
        
    except Exception as e:
        print(f"Error during demonstration: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()