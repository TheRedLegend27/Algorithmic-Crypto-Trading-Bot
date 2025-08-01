#!/usr/bin/env python3
"""
Comprehensive Testing Framework Demo

This demo shows how to use both the backtesting framework and paper trading
integration for testing adaptive trading strategies.
"""
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from bot.adaptive.backtesting_framework import (
    BacktestingFramework, BacktestConfig, create_default_backtest_config
)
from bot.adaptive.paper_trading import (
    PaperTradingEngine, PaperTradingConfig, create_default_paper_trading_config
)
from bot.adaptive.data_models import AdaptiveSignal, MarketRegime
from bot.adaptive.enums import RegimeType, SignalStrength
from bot.enhanced_data_manager import EnhancedDataManager


def create_mock_data_manager():
    """Create a mock data manager with sample data."""
    data_manager = Mock(spec=EnhancedDataManager)
    
    # Create sample historical data
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='1h')
    np.random.seed(42)  # For reproducible results
    
    # Generate realistic price data with trend and volatility
    base_price = 50000.0
    returns = np.random.normal(0.0001, 0.02, len(dates))  # Small positive drift with volatility
    prices = [base_price]
    
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    sample_data = pd.DataFrame({
        'BTC/USD_close': prices,
        'BTC/USD_high': [p * 1.01 for p in prices],
        'BTC/USD_low': [p * 0.99 for p in prices],
        'BTC/USD_volume': np.random.uniform(100, 1000, len(dates))
    }, index=dates)
    
    data_manager.get_historical_data.return_value = sample_data
    data_manager.get_latest_data.return_value = {'close': prices[-1]}
    
    return data_manager


def create_mock_strategy_engine():
    """Create a mock strategy engine that generates signals."""
    strategy_engine = Mock()
    
    def generate_signal(pair, data):
        """Generate a mock adaptive signal."""
        if len(data) < 20:
            return None
        
        # Simple momentum strategy
        recent_prices = data[f'{pair}_close'].tail(20)
        sma_short = recent_prices.tail(5).mean()
        sma_long = recent_prices.mean()
        
        current_price = recent_prices.iloc[-1]
        
        if sma_short > sma_long * 1.02:  # Strong uptrend
            return AdaptiveSignal(
                pair=pair,
                signal_type='buy',
                strength=SignalStrength.STRONG,
                confidence=0.8,
                price=current_price,
                timestamp=data.index[-1],
                stop_loss=current_price * 0.95,
                take_profit=current_price * 1.10,
                suggested_position_size=1000.0,
                strategy_weights={'momentum': 1.0}
            )
        elif sma_short < sma_long * 0.98:  # Strong downtrend
            return AdaptiveSignal(
                pair=pair,
                signal_type='sell',
                strength=SignalStrength.STRONG,
                confidence=0.7,
                price=current_price,
                timestamp=data.index[-1],
                stop_loss=current_price * 1.05,
                take_profit=current_price * 0.90,
                suggested_position_size=800.0,
                strategy_weights={'momentum': 1.0}
            )
        
        return None
    
    strategy_engine.execute_adaptive_signal.side_effect = generate_signal
    return strategy_engine


def demo_backtesting_framework():
    """Demonstrate the backtesting framework."""
    print("🔬 Backtesting Framework Demo")
    print("=" * 50)
    
    # Create mock components
    data_manager = create_mock_data_manager()
    strategy_engine = create_mock_strategy_engine()
    
    # Create backtesting framework
    framework = BacktestingFramework(
        data_manager=data_manager,
        strategy_engine=strategy_engine
    )
    
    # Create backtest configuration
    config = create_default_backtest_config(
        start_date=datetime(2023, 6, 1),
        end_date=datetime(2023, 8, 31),
        initial_capital=10000.0
    )
    
    print(f"📊 Running backtest from {config.start_date} to {config.end_date}")
    print(f"💰 Initial capital: ${config.initial_capital:,.2f}")
    
    try:
        # Run backtest
        result = framework.run_backtest(config, pairs=['BTC/USD'])
        
        print(f"\n✅ Backtest completed successfully!")
        print(f"⏱️  Execution time: {result.execution_time}")
        print(f"📈 Total return: {result.performance_metrics.total_return:.2%}")
        print(f"📊 Sharpe ratio: {result.performance_metrics.sharpe_ratio:.2f}")
        print(f"📉 Max drawdown: {result.performance_metrics.max_drawdown:.2%}")
        print(f"🎯 Win rate: {result.performance_metrics.win_rate:.2%}")
        print(f"💼 Total trades: {result.performance_metrics.trades_count}")
        
        # Show some trade details
        if result.trades:
            print(f"\n📋 Sample trades:")
            for i, trade in enumerate(result.trades[:3]):
                pnl = trade.get('pnl', 0)
                print(f"   Trade {i+1}: {trade.get('signal_type', 'N/A')} "
                      f"@ ${trade.get('price', 0):.2f}, P&L: ${pnl:.2f}")
        
        return result
        
    except Exception as e:
        print(f"❌ Backtest failed: {str(e)}")
        return None


def demo_paper_trading():
    """Demonstrate the paper trading integration."""
    print("\n📝 Paper Trading Demo")
    print("=" * 50)
    
    # Create mock components
    data_manager = create_mock_data_manager()
    strategy_engine = create_mock_strategy_engine()
    
    # Create paper trading configuration
    config = create_default_paper_trading_config()
    config.initial_capital = 10000.0
    config.max_position_size_pct = 0.2  # Allow larger positions for demo
    
    # Create paper trading engine
    engine = PaperTradingEngine(
        config=config,
        data_manager=data_manager,
        strategy_engine=strategy_engine
    )
    
    print(f"💰 Initial capital: ${config.initial_capital:,.2f}")
    print(f"📊 Max position size: {config.max_position_size_pct:.1%} of capital")
    
    # Create some test signals
    test_signals = [
        AdaptiveSignal(
            pair='BTC/USD',
            signal_type='buy',
            strength=SignalStrength.STRONG,
            confidence=0.85,
            price=50000.0,
            timestamp=datetime.now(),
            stop_loss=47500.0,
            take_profit=55000.0,
            suggested_position_size=1500.0,
            regime_context=MarketRegime(
                regime_type=RegimeType.TRENDING_BULL,
                confidence=0.8,
                volatility_level=0.15,
                trend_strength=0.7,
                momentum=0.6,
                detected_at=datetime.now(),
                supporting_indicators={'rsi': 65}
            )
        ),
        AdaptiveSignal(
            pair='ETH/USD',
            signal_type='buy',
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            price=3000.0,
            timestamp=datetime.now(),
            stop_loss=2850.0,
            take_profit=3300.0,
            suggested_position_size=1000.0
        )
    ]
    
    print(f"\n🚀 Executing {len(test_signals)} test signals:")
    
    # Execute signals
    for i, signal in enumerate(test_signals, 1):
        print(f"\n📈 Signal {i}: {signal.signal_type.upper()} {signal.pair}")
        print(f"   💪 Strength: {signal.strength.name}")
        print(f"   🎯 Confidence: {signal.confidence:.2%}")
        print(f"   💵 Price: ${signal.price:,.2f}")
        
        success = engine.execute_signal(signal)
        
        if success:
            print(f"   ✅ Signal executed successfully")
        else:
            print(f"   ❌ Signal execution failed")
    
    # Show current state
    state = engine.get_current_state()
    print(f"\n📊 Current Portfolio State:")
    print(f"   💰 Current capital: ${state.current_capital:,.2f}")
    print(f"   💼 Available capital: ${state.available_capital:,.2f}")
    print(f"   📈 Position value: ${state.total_position_value:,.2f}")
    print(f"   🏦 Total value: ${state.get_total_value():,.2f}")
    print(f"   📊 Open positions: {len(state.open_positions)}")
    
    # Show open positions
    if state.open_positions:
        print(f"\n📋 Open Positions:")
        for pos_id, position in state.open_positions.items():
            unrealized_pct = (position.unrealized_pnl / (position.quantity * position.entry_price)) * 100
            print(f"   {position.pair}: {position.side} {position.quantity:.4f} @ ${position.entry_price:,.2f}")
            print(f"      Unrealized P&L: ${position.unrealized_pnl:.2f} ({unrealized_pct:+.2f}%)")
    
    # Simulate some price movements and check exit conditions
    print(f"\n🎲 Simulating price movements...")
    
    # Update prices to trigger some exits
    for position in state.open_positions.values():
        if position.pair == 'BTC/USD':
            # Trigger take profit
            new_price = 55500.0
            position.update_current_price(new_price)
            print(f"   📈 {position.pair} price updated to ${new_price:,.2f}")
        elif position.pair == 'ETH/USD':
            # Trigger stop loss
            new_price = 2800.0
            position.update_current_price(new_price)
            print(f"   📉 {position.pair} price updated to ${new_price:,.2f}")
    
    # Check exit conditions
    engine._check_exit_conditions()
    
    # Show final state
    final_state = engine.get_current_state()
    print(f"\n📊 Final Portfolio State:")
    print(f"   💰 Final capital: ${final_state.current_capital:,.2f}")
    print(f"   📈 Total return: {((final_state.get_total_value() - config.initial_capital) / config.initial_capital):.2%}")
    print(f"   📊 Completed trades: {len(final_state.completed_trades)}")
    
    # Show completed trades
    if final_state.completed_trades:
        print(f"\n💼 Completed Trades:")
        for trade in final_state.completed_trades:
            print(f"   {trade.pair}: {trade.side} @ ${trade.entry_price:,.2f} -> ${trade.exit_price:,.2f}")
            print(f"      P&L: ${trade.pnl:.2f} ({trade.pnl_percentage:+.2%}) - {trade.exit_reason}")
    
    # Check transition readiness
    readiness = engine.check_transition_readiness()
    print(f"\n🚦 Transition Readiness:")
    print(f"   Ready for live trading: {'✅ Yes' if readiness['ready'] else '❌ No'}")
    if not readiness['ready']:
        print(f"   Reason: {readiness.get('reason', 'Performance criteria not met')}")
    
    return engine


def demo_walk_forward_analysis():
    """Demonstrate walk-forward analysis."""
    print("\n🔄 Walk-Forward Analysis Demo")
    print("=" * 50)
    
    # Create mock components
    data_manager = create_mock_data_manager()
    strategy_engine = create_mock_strategy_engine()
    
    # Create backtesting framework
    framework = BacktestingFramework(
        data_manager=data_manager,
        strategy_engine=strategy_engine
    )
    
    # Create configuration for walk-forward analysis
    config = create_default_backtest_config(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 6, 30),
        initial_capital=10000.0
    )
    
    print(f"📊 Running walk-forward analysis")
    print(f"📅 Period: {config.start_date} to {config.end_date}")
    
    try:
        # Run walk-forward analysis with shorter windows for demo
        results = framework.walk_forward_analysis(
            config=config,
            pairs=['BTC/USD'],
            optimization_window=30,  # 30 days
            validation_window=15,    # 15 days
            step_size=10            # 10 day steps
        )
        
        print(f"✅ Walk-forward analysis completed!")
        print(f"📊 Number of windows: {len(results)}")
        
        if results:
            # Calculate statistics across windows
            returns = [r.performance_metrics.total_return for r in results]
            sharpe_ratios = [r.performance_metrics.sharpe_ratio for r in results]
            
            print(f"\n📈 Performance Statistics:")
            print(f"   Average return: {np.mean(returns):.2%}")
            print(f"   Return std dev: {np.std(returns):.2%}")
            print(f"   Average Sharpe: {np.mean(sharpe_ratios):.2f}")
            print(f"   Best window return: {max(returns):.2%}")
            print(f"   Worst window return: {min(returns):.2%}")
            
            # Show consistency
            positive_windows = len([r for r in returns if r > 0])
            consistency = positive_windows / len(returns)
            print(f"   Consistency: {consistency:.1%} ({positive_windows}/{len(results)} positive windows)")
        
        return results
        
    except Exception as e:
        print(f"❌ Walk-forward analysis failed: {str(e)}")
        return []


def main():
    """Run the comprehensive testing framework demo."""
    print("🧪 Comprehensive Testing Framework Demo")
    print("=" * 60)
    print("This demo showcases the backtesting framework and paper trading")
    print("integration for testing adaptive trading strategies.")
    print("=" * 60)
    
    # Demo 1: Backtesting Framework
    backtest_result = demo_backtesting_framework()
    
    # Demo 2: Paper Trading
    paper_engine = demo_paper_trading()
    
    # Demo 3: Walk-Forward Analysis
    wf_results = demo_walk_forward_analysis()
    
    # Summary
    print(f"\n🎯 Demo Summary")
    print("=" * 50)
    print("✅ Backtesting Framework: Historical simulation with realistic market conditions")
    print("✅ Paper Trading: Real-time simulation with live market data integration")
    print("✅ Walk-Forward Analysis: Parameter optimization validation")
    print("✅ Performance Analysis: Comprehensive metrics and risk assessment")
    print("✅ Transition Readiness: Automated evaluation for live trading")
    
    print(f"\n🚀 The comprehensive testing framework provides:")
    print("   • Historical backtesting with Monte Carlo simulation")
    print("   • Real-time paper trading with risk management")
    print("   • Performance comparison and validation")
    print("   • Gradual transition to live trading")
    print("   • Regime-specific testing and analysis")
    
    print(f"\n📚 Next Steps:")
    print("   1. Run backtests on your strategies")
    print("   2. Validate with paper trading")
    print("   3. Analyze performance metrics")
    print("   4. Check transition readiness")
    print("   5. Gradually move to live trading")
    
    print(f"\n✨ Demo completed successfully!")


if __name__ == "__main__":
    main()