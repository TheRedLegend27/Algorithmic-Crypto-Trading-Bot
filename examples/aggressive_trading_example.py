"""
Example of how to set up and run aggressive trading strategies.

This example shows how to configure the bot for aggressive trading
with a $100 starting capital, focusing on higher risk/reward scenarios.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
import pandas as pd
from datetime import datetime, timedelta

from bot.strategy import SignalGenerator, BaseStrategy
from bot.aggressive_strategies import (
    ScalpingMomentumStrategy, 
    VolatilityBreakoutStrategy, 
    MeanReversionScalpStrategy,
    AggressiveRiskManager,
    create_aggressive_strategy_suite
)
from bot.aggressive_config import get_aggressive_config, calculate_dynamic_position_size
from bot.utils import log_info


def setup_aggressive_trading():
    """Set up aggressive trading configuration and strategies."""
    
    # Get aggressive configuration
    config = get_aggressive_config()
    trading_settings = config["trading_settings"]
    
    print(f"🚀 Setting up aggressive trading with ${trading_settings.initial_capital}")
    print(f"📊 Max risk per trade: {trading_settings.max_risk_per_trade_pct*100}%")
    print(f"🛡️ Max daily loss: {trading_settings.max_daily_loss_pct*100}%")
    print(f"💰 Max position size: {trading_settings.max_position_size_pct*100}%")
    
    # Create aggressive strategies
    strategies = create_aggressive_strategy_suite()
    
    # Initialize risk manager
    risk_manager = AggressiveRiskManager(
        initial_capital=trading_settings.initial_capital,
        max_risk_per_trade=trading_settings.max_risk_per_trade_pct,
        max_daily_loss=trading_settings.max_daily_loss_pct,
        max_position_size=trading_settings.max_position_size_pct
    )
    
    # Create signal generator
    signal_generator = SignalGenerator(strategies)
    
    return signal_generator, risk_manager, config


def simulate_aggressive_trading(signal_generator: SignalGenerator, 
                              risk_manager: AggressiveRiskManager,
                              sample_data: pd.DataFrame):
    """
    Simulate aggressive trading with sample data.
    
    Args:
        signal_generator: Configured signal generator
        risk_manager: Risk management system
        sample_data: Sample OHLCV data for simulation
    """
    print("\n🎯 Starting aggressive trading simulation...")
    
    trades_executed = 0
    total_pnl = 0.0
    
    for i in range(len(sample_data) - 50, len(sample_data)):
        # Get data window for analysis
        data_window = sample_data.iloc[:i+1]
        
        # Check if we can trade
        can_trade, reason = risk_manager.can_trade()
        if not can_trade:
            print(f"❌ Trading blocked: {reason}")
            continue
        
        # Generate signals
        signal = signal_generator.evaluate_all_strategies(data_window)
        
        if signal.action.value != "HOLD" and signal.confidence > 0.4:
            # Calculate position size
            current_price = data_window['close'].iloc[-1]
            volatility = data_window['close'].pct_change().rolling(10).std().iloc[-1]
            
            position_size = calculate_dynamic_position_size(
                capital=risk_manager.current_capital,
                signal_confidence=signal.confidence,
                volatility=volatility,
                settings=get_aggressive_config()["trading_settings"]
            )
            
            # Simulate trade execution
            print(f"\n📈 {signal.action.value} Signal Generated!")
            print(f"   Strategy: {signal.strategy}")
            print(f"   Confidence: {signal.confidence:.2f}")
            print(f"   Price: ${current_price:.2f}")
            print(f"   Position Size: ${position_size:.2f}")
            print(f"   Reasoning: {signal.reasoning}")
            
            # Simulate trade outcome (random for demo)
            import random
            if signal.confidence > 0.7:
                # High confidence trades have better success rate
                success_rate = 0.65
            else:
                success_rate = 0.55
            
            # Simulate trade result
            if random.random() < success_rate:
                # Winning trade
                profit_pct = random.uniform(0.01, 0.04)  # 1-4% profit
                pnl = position_size * profit_pct
                print(f"   ✅ Trade Result: +${pnl:.2f} ({profit_pct*100:.1f}%)")
            else:
                # Losing trade
                loss_pct = random.uniform(0.01, 0.025)  # 1-2.5% loss
                pnl = -position_size * loss_pct
                print(f"   ❌ Trade Result: ${pnl:.2f} ({loss_pct*100:.1f}%)")
            
            # Update risk manager
            risk_manager.update_capital(pnl)
            total_pnl += pnl
            trades_executed += 1
            
            print(f"   💰 Current Capital: ${risk_manager.current_capital:.2f}")
            print(f"   📊 Daily P&L: ${risk_manager.daily_pnl:.2f}")
    
    # Final results
    print(f"\n🏁 Simulation Complete!")
    print(f"   Trades Executed: {trades_executed}")
    print(f"   Total P&L: ${total_pnl:.2f}")
    print(f"   Final Capital: ${risk_manager.current_capital:.2f}")
    print(f"   Return: {((risk_manager.current_capital / 100) - 1) * 100:.1f}%")


def create_sample_data():
    """Create sample OHLCV data for testing."""
    import numpy as np
    
    # Generate realistic crypto price data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=1000, freq='5min')
    
    # Start with base price
    base_price = 45000.0
    prices = [base_price]
    
    # Generate price movements with volatility
    for i in range(1, len(dates)):
        # Add some trend and random walk
        trend = 0.0001 * np.sin(i / 100)  # Slight trending
        random_move = np.random.normal(0, 0.002)  # 0.2% volatility
        
        # Occasional larger moves (breakouts)
        if np.random.random() < 0.05:  # 5% chance
            random_move *= 3  # 3x larger move
        
        price_change = trend + random_move
        new_price = prices[-1] * (1 + price_change)
        prices.append(new_price)
    
    # Create OHLCV data
    data = pd.DataFrame(index=dates)
    data['close'] = prices
    
    # Generate OHLC from close prices
    data['open'] = data['close'].shift(1)
    data['high'] = data[['open', 'close']].max(axis=1) * (1 + np.random.uniform(0, 0.001, len(data)))
    data['low'] = data[['open', 'close']].min(axis=1) * (1 - np.random.uniform(0, 0.001, len(data)))
    data['volume'] = np.random.uniform(1000, 5000, len(data))
    
    # Fill NaN values
    data = data.fillna(method='bfill')
    
    return data


def main():
    """Main function to run the aggressive trading example."""
    print("🔥 Aggressive Crypto Trading Bot Example")
    print("=" * 50)
    
    # Setup
    signal_generator, risk_manager, config = setup_aggressive_trading()
    
    # Create sample data
    print("\n📊 Generating sample market data...")
    sample_data = create_sample_data()
    print(f"   Generated {len(sample_data)} data points")
    
    # Run simulation
    simulate_aggressive_trading(signal_generator, risk_manager, sample_data)
    
    print("\n💡 Tips for Aggressive Trading:")
    print("   • Start with paper trading to test strategies")
    print("   • Never risk more than you can afford to lose")
    print("   • Monitor your daily loss limits closely")
    print("   • Take profits regularly - don't get greedy")
    print("   • Keep detailed logs of all trades")
    print("   • Adjust position sizes based on performance")


if __name__ == "__main__":
    main()