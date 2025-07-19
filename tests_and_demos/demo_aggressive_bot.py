#!/usr/bin/env python3
"""
Demo Aggressive Trading Bot

This demo version uses simulated market data to show how the aggressive
trading strategies work without needing real API access.
"""
import argparse
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List

from bot.strategy import SignalGenerator
from bot.aggressive_strategies import (
    create_aggressive_strategy_suite,
    AggressiveRiskManager
)
from bot.aggressive_config import get_aggressive_config, calculate_dynamic_position_size
from bot.utils import log_info, log_warning, setup_logging


def create_realistic_crypto_data(periods: int = 200) -> pd.DataFrame:
    """Create realistic crypto price data for demo purposes."""
    np.random.seed(42)  # For reproducible results
    
    # Start with a base price
    base_price = 45000.0
    dates = pd.date_range(start=datetime.now() - timedelta(minutes=periods*5), 
                         periods=periods, freq='5min')
    
    # Generate realistic price movements
    prices = [base_price]
    volumes = [np.random.uniform(800, 1200)]  # Initial volume
    
    for i in range(1, periods):
        # Add trend component
        trend = 0.0001 * np.sin(i / 50)  # Slow trending
        
        # Add random walk
        random_move = np.random.normal(0, 0.003)  # 0.3% volatility
        
        # Occasional large moves (breakouts)
        if np.random.random() < 0.08:  # 8% chance
            random_move *= np.random.choice([2, 3, 4])  # 2-4x larger move
            
        # Momentum clustering (volatility clustering)
        if i > 1 and abs(prices[-1] - prices[-2]) / prices[-2] > 0.01:
            random_move *= 1.5  # Increase volatility after big moves
        
        # Calculate new price
        price_change = trend + random_move
        new_price = prices[-1] * (1 + price_change)
        prices.append(max(new_price, 1000))  # Minimum price floor
        
        # Generate volume (higher volume with larger moves)
        base_volume = np.random.uniform(800, 1200)
        if abs(price_change) > 0.005:  # Large move
            volume_multiplier = np.random.uniform(1.5, 3.0)
        else:
            volume_multiplier = np.random.uniform(0.8, 1.2)
        volumes.append(base_volume * volume_multiplier)
    
    # Create OHLCV DataFrame
    df = pd.DataFrame(index=dates)
    df['close'] = prices
    
    # Generate OHLC from close prices
    df['open'] = df['close'].shift(1).fillna(df['close'].iloc[0])
    
    # Generate high/low with some spread
    spread_pct = np.random.uniform(0.001, 0.005, len(df))  # 0.1-0.5% spread
    df['high'] = df[['open', 'close']].max(axis=1) * (1 + spread_pct)
    df['low'] = df[['open', 'close']].min(axis=1) * (1 - spread_pct)
    df['volume'] = volumes
    
    return df


def run_demo_cycle(signal_generator: SignalGenerator, 
                  risk_manager: AggressiveRiskManager,
                  data: pd.DataFrame, 
                  current_index: int,
                  args) -> bool:
    """Run a single demo trading cycle."""
    
    # Check if we can trade
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        log_warning(f"Trading blocked: {reason}")
        return False
    
    # Get data window (last 100 periods)
    start_idx = max(0, current_index - 99)
    data_window = data.iloc[start_idx:current_index + 1].copy()
    
    if len(data_window) < 50:  # Need minimum data
        return True
    
    # Generate trading signals
    signal = signal_generator.evaluate_all_strategies(data_window)
    
    # Check signal strength - also check individual strategies
    individual_signals = []
    for strategy in signal_generator.strategies:
        try:
            individual_signal = strategy.calculate_signals(data_window)
            if individual_signal.confidence > 0.4:
                individual_signals.append(individual_signal)
        except:
            pass
    
    # Use individual signal if combined signal is weak but individual is strong
    if signal.confidence < 0.4 and individual_signals:
        signal = max(individual_signals, key=lambda s: s.confidence)
        print(f"   Using individual strategy signal: {signal.strategy}")
    
    if signal.confidence < 0.4:  # Still too weak
        log_info(f"Signal too weak: {signal.action.value} with {signal.confidence:.2f} confidence")
        return True
    
    # Calculate position size
    current_price = data_window['close'].iloc[-1]
    volatility = data_window['close'].pct_change().rolling(10).std().iloc[-1]
    
    trading_settings = get_aggressive_config()["trading_settings"]
    position_size = calculate_dynamic_position_size(
        capital=risk_manager.current_capital,
        signal_confidence=signal.confidence,
        volatility=volatility,
        settings=trading_settings
    )
    
    # Log signal details
    print(f"\n🚨 {signal.action.value} Signal Generated!")
    print(f"   Strategy: {signal.strategy}")
    print(f"   Confidence: {signal.confidence:.2f}")
    print(f"   Price: ${current_price:.2f}")
    print(f"   Position Size: ${position_size:.2f}")
    print(f"   Reasoning: {signal.reasoning}")
    
    # Simulate trade outcome based on next few periods
    if current_index < len(data) - 5:
        # Look ahead to simulate trade outcome (in real trading, this would be unknown)
        future_prices = data['close'].iloc[current_index+1:current_index+6]
        price_changes = (future_prices / current_price - 1)
        
        if signal.action.value == "BUY":
            # For buy signals, we want price to go up
            best_change = price_changes.max()
            worst_change = price_changes.min()
        else:
            # For sell signals, we want price to go down
            best_change = -price_changes.min()  # Negative of minimum (most negative becomes most positive)
            worst_change = -price_changes.max()
        
        # Simulate trade outcome based on signal confidence
        success_probability = 0.4 + (signal.confidence * 0.3)  # 40-70% success rate
        
        if np.random.random() < success_probability:
            # Winning trade - use a portion of the best possible outcome
            profit_pct = best_change * np.random.uniform(0.3, 0.8)  # Capture 30-80% of move
            profit_pct = max(profit_pct, 0.005)  # Minimum 0.5% profit
            pnl = position_size * profit_pct
            print(f"   ✅ Trade Result: +${pnl:.2f} ({profit_pct*100:.1f}%)")
        else:
            # Losing trade - use stop loss
            loss_pct = min(abs(worst_change), 0.025)  # Max 2.5% loss (stop loss)
            pnl = -position_size * loss_pct
            print(f"   ❌ Trade Result: ${pnl:.2f} ({loss_pct*100:.1f}%)")
        
        # Update risk manager
        risk_manager.update_capital(pnl)
        
        # Show current status
        print(f"   💰 Current Capital: ${risk_manager.current_capital:.2f}")
        print(f"   📊 Daily P&L: ${risk_manager.daily_pnl:.2f}")
        print(f"   📈 Total Return: {((risk_manager.current_capital / args.capital) - 1) * 100:.1f}%")
        
        return True
    
    return True


def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="Demo Aggressive Trading Bot")
    parser.add_argument("--capital", type=float, default=100.0, help="Starting capital")
    parser.add_argument("--cycles", type=int, default=50, help="Number of trading cycles to run")
    parser.add_argument("--speed", type=float, default=0.5, help="Seconds between cycles")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    
    print("🔥 AGGRESSIVE CRYPTO TRADING BOT - DEMO MODE")
    print("=" * 60)
    print(f"💰 Starting Capital: ${args.capital}")
    print(f"🎯 Demo Cycles: {args.cycles}")
    print(f"⚡ Using Simulated Market Data")
    print("=" * 60)
    
    # Create demo data
    print("\n📊 Generating realistic market data...")
    market_data = create_realistic_crypto_data(periods=300)
    print(f"   Generated {len(market_data)} data points")
    print(f"   Price range: ${market_data['close'].min():.0f} - ${market_data['close'].max():.0f}")
    
    # Setup aggressive strategies
    print("\n⚡ Setting up aggressive strategies...")
    strategies = create_aggressive_strategy_suite()
    signal_generator = SignalGenerator(strategies)
    
    # Setup risk manager
    print("🛡️ Setting up risk management...")
    risk_manager = AggressiveRiskManager(
        initial_capital=args.capital,
        max_risk_per_trade=0.05,
        max_daily_loss=0.15,
        max_position_size=0.8
    )
    
    print(f"\n🚀 Starting demo trading...")
    print("Press Ctrl+C to stop early\n")
    
    # Run demo cycles
    successful_cycles = 0
    start_time = datetime.now()
    
    try:
        for cycle in range(args.cycles):
            # Use different parts of the data for each cycle
            data_index = 100 + cycle  # Start after we have enough historical data
            if data_index >= len(market_data):
                break
                
            print(f"🔄 Demo Cycle #{cycle + 1}")
            
            success = run_demo_cycle(
                signal_generator=signal_generator,
                risk_manager=risk_manager,
                data=market_data,
                current_index=data_index,
                args=args
            )
            
            if success:
                successful_cycles += 1
            
            # Wait between cycles
            time.sleep(args.speed)
            
    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
    
    # Final statistics
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    final_return = ((risk_manager.current_capital / args.capital) - 1) * 100
    
    print("\n" + "=" * 60)
    print("📊 DEMO RESULTS")
    print("=" * 60)
    print(f"Starting Capital: ${args.capital:.2f}")
    print(f"Final Capital: ${risk_manager.current_capital:.2f}")
    print(f"Total Return: {final_return:.1f}%")
    print(f"Daily P&L: ${risk_manager.daily_pnl:.2f}")
    print(f"Trades Executed: {risk_manager.trades_today}")
    print(f"Successful Cycles: {successful_cycles}")
    print(f"Demo Duration: {duration:.1f} seconds")
    
    if risk_manager.trades_today > 0:
        avg_trade = risk_manager.daily_pnl / risk_manager.trades_today
        print(f"Average P&L per Trade: ${avg_trade:.2f}")
    
    print("=" * 60)
    print("\n💡 This was a demo with simulated data.")
    print("   Real trading results will vary significantly!")
    print("   Always test with paper trading first.")


if __name__ == "__main__":
    main()