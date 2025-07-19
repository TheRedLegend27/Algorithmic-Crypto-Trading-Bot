#!/usr/bin/env python3
"""
Enhanced Aggressive Trading Bot

This version uses enhanced strategies that are more sensitive to market
movements and should generate more trading signals.
"""
import argparse
import sys
import time
from datetime import datetime
from typing import List

from bot.config import Config
from bot.yahoo_data_fetcher import YahooDataFetcher
from bot.trader import Trader
from bot.strategy import SignalGenerator
from bot.enhanced_strategies import create_enhanced_strategy_suite
from bot.aggressive_strategies import AggressiveRiskManager
from bot.aggressive_config import get_aggressive_config, calculate_dynamic_position_size
from bot.utils import setup_logging, log_info, log_error, log_warning


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhanced Aggressive Crypto Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with paper trading (recommended)
    python run_enhanced_bot.py --paper-trading
    
    # Run with different crypto
    python run_enhanced_bot.py --paper-trading --symbol ETH/USD
    
    # More aggressive settings
    python run_enhanced_bot.py --paper-trading --max-risk-per-trade 0.08
        """
    )
    
    parser.add_argument(
        "--paper-trading",
        action="store_true",
        help="Run in paper trading mode (simulated trades)"
    )
    
    parser.add_argument(
        "--capital",
        type=float,
        default=100.0,
        help="Starting capital in USD (default: 100)"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTC/USD",
        choices=["BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", "MATIC/USD"],
        help="Trading symbol (default: BTC/USD)"
    )
    
    parser.add_argument(
        "--max-daily-loss",
        type=float,
        default=0.15,
        help="Maximum daily loss as percentage (default: 0.15 = 15%%)"
    )
    
    parser.add_argument(
        "--max-risk-per-trade",
        type=float,
        default=0.05,
        help="Maximum risk per trade as percentage (default: 0.05 = 5%%)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=45,
        help="Trading interval in seconds (default: 45)"
    )
    
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.35,
        help="Minimum signal confidence (default: 0.35 = 35%%)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def setup_enhanced_bot(args):
    """Set up the enhanced trading bot."""
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    
    log_info("🚀 Starting Enhanced Aggressive Trading Bot")
    log_info(f"💰 Starting Capital: ${args.capital}")
    log_info(f"📊 Trading Symbol: {args.symbol}")
    log_info(f"🎯 Paper Trading: {args.paper_trading}")
    log_info(f"🎚️ Min Confidence: {args.min_confidence}")
    
    # Initialize data fetcher
    data_fetcher = YahooDataFetcher()
    
    # Test connection
    log_info("🔍 Testing data connection...")
    test_data = data_fetcher.fetch_crypto_data(args.symbol, limit=10)
    if test_data is None or test_data.empty:
        log_error(f"Failed to fetch data for {args.symbol}")
        return None
    
    log_info(f"✅ Data connection successful - {len(test_data)} data points")
    log_info(f"📈 Current price: ${test_data['close'].iloc[-1]:.2f}")
    
    # Create enhanced strategies
    log_info("⚡ Creating enhanced trading strategies...")
    strategies = create_enhanced_strategy_suite()
    signal_generator = SignalGenerator(strategies)
    
    # Initialize risk manager
    log_info("🛡️ Setting up risk management...")
    risk_manager = AggressiveRiskManager(
        initial_capital=args.capital,
        max_risk_per_trade=args.max_risk_per_trade,
        max_daily_loss=args.max_daily_loss,
        max_position_size=0.8
    )
    
    # Get trading settings
    aggressive_config = get_aggressive_config()
    trading_settings = aggressive_config["trading_settings"]
    trading_settings.initial_capital = args.capital
    trading_settings.max_daily_loss_pct = args.max_daily_loss
    trading_settings.max_risk_per_trade_pct = args.max_risk_per_trade
    trading_settings.min_signal_confidence = args.min_confidence
    
    return {
        'data_fetcher': data_fetcher,
        'signal_generator': signal_generator,
        'risk_manager': risk_manager,
        'trading_settings': trading_settings,
        'strategies': strategies
    }


def run_enhanced_cycle(components, args):
    """Run enhanced trading cycle with individual strategy analysis."""
    data_fetcher = components['data_fetcher']
    signal_generator = components['signal_generator']
    risk_manager = components['risk_manager']
    trading_settings = components['trading_settings']
    strategies = components['strategies']
    
    try:
        # Check trading limits
        can_trade, reason = risk_manager.can_trade()
        if not can_trade:
            log_warning(f"Trading blocked: {reason}")
            return False
        
        # Fetch market data
        log_info(f"📊 Fetching market data for {args.symbol}...")
        data = data_fetcher.fetch_crypto_data(args.symbol, timeframe="5Min", limit=100)
        
        if data is None or data.empty:
            log_error("Failed to fetch market data")
            return False
        
        current_price = data['close'].iloc[-1]
        log_info(f"✅ Current price: ${current_price:.2f}")
        
        # Analyze individual strategies first
        individual_signals = []
        print(f"\n🔍 Strategy Analysis:")
        
        for strategy in strategies:
            try:
                signal = strategy.calculate_signals(data)
                individual_signals.append(signal)
                
                if signal.confidence > 0:
                    print(f"   {strategy.name}: {signal.action.value} ({signal.confidence:.2f}) - {signal.reasoning}")
                else:
                    print(f"   {strategy.name}: HOLD - {signal.reasoning}")
                    
            except Exception as e:
                log_error(f"Error in {strategy.name}: {e}")
        
        # Get combined signal
        combined_signal = signal_generator.evaluate_all_strategies(data)
        
        # Find best individual signal if combined is weak
        best_signal = combined_signal
        if combined_signal.confidence < args.min_confidence and individual_signals:
            strong_signals = [s for s in individual_signals if s.confidence >= args.min_confidence]
            if strong_signals:
                best_signal = max(strong_signals, key=lambda s: s.confidence)
                print(f"   🎯 Using individual signal from {best_signal.strategy}")
        
        # Check if signal is strong enough
        if best_signal.confidence < args.min_confidence:
            print(f"   ❌ All signals too weak (best: {best_signal.confidence:.2f})")
            return True
        
        # Calculate position size
        volatility = data['close'].pct_change().rolling(10).std().iloc[-1]
        position_size = calculate_dynamic_position_size(
            capital=risk_manager.current_capital,
            signal_confidence=best_signal.confidence,
            volatility=volatility,
            settings=trading_settings
        )
        
        # Execute trade
        print(f"\n🚨 {best_signal.action.value} SIGNAL TRIGGERED!")
        print(f"   Strategy: {best_signal.strategy}")
        print(f"   Confidence: {best_signal.confidence:.2f}")
        print(f"   Price: ${current_price:.2f}")
        print(f"   Position Size: ${position_size:.2f}")
        print(f"   Reasoning: {best_signal.reasoning}")
        
        if args.paper_trading:
            # Simulate trade
            print("   📝 PAPER TRADE")
            
            # Enhanced simulation based on signal quality
            base_success_rate = 0.45
            confidence_bonus = best_signal.confidence * 0.3
            success_rate = min(base_success_rate + confidence_bonus, 0.75)
            
            import random
            if random.random() < success_rate:
                # Winning trade
                profit_pct = random.uniform(0.008, 0.035)  # 0.8% to 3.5%
                if best_signal.confidence > 0.7:
                    profit_pct *= 1.3  # Bonus for high confidence
                pnl = position_size * profit_pct
                print(f"   ✅ Result: +${pnl:.2f} ({profit_pct*100:.1f}%)")
            else:
                # Losing trade
                loss_pct = random.uniform(0.008, 0.025)  # 0.8% to 2.5%
                pnl = -position_size * loss_pct
                print(f"   ❌ Result: ${pnl:.2f} ({loss_pct*100:.1f}%)")
            
            # Update capital
            risk_manager.update_capital(pnl)
            
        else:
            print("   💰 REAL TRADE - Not implemented yet")
        
        # Show status
        print(f"   💰 Capital: ${risk_manager.current_capital:.2f}")
        print(f"   📊 Daily P&L: ${risk_manager.daily_pnl:.2f}")
        print(f"   📈 Return: {((risk_manager.current_capital / args.capital) - 1) * 100:.1f}%")
        
        return True
        
    except Exception as e:
        log_error(f"Error in trading cycle: {str(e)}")
        return False


def main():
    """Main function."""
    args = parse_arguments()
    
    # Setup
    components = setup_enhanced_bot(args)
    if not components:
        log_error("Failed to setup bot")
        sys.exit(1)
    
    # Display info
    print("\n" + "="*65)
    print("🚀 ENHANCED AGGRESSIVE CRYPTO TRADING BOT")
    print("="*65)
    print(f"💰 Starting Capital: ${args.capital}")
    print(f"📊 Trading Symbol: {args.symbol}")
    print(f"🎯 Paper Trading: {'YES' if args.paper_trading else 'NO'}")
    print(f"⚡ Max Risk/Trade: {args.max_risk_per_trade*100}%")
    print(f"🛡️ Max Daily Loss: {args.max_daily_loss*100}%")
    print(f"🎚️ Min Confidence: {args.min_confidence*100}%")
    print(f"⏱️ Trading Interval: {args.interval}s")
    print(f"📡 Data Source: Yahoo Finance")
    print(f"🧠 Strategies: Enhanced Momentum, Price Action, Multi-Timeframe")
    print("="*65)
    
    if not args.paper_trading:
        print("⚠️  WARNING: REAL MONEY TRADING!")
        response = input("Type 'YES' to continue: ")
        if response != 'YES':
            sys.exit(0)
    
    print(f"\n🚀 Starting enhanced trading at {datetime.now()}")
    print("Press Ctrl+C to stop\n")
    
    # Main loop
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            print(f"🔄 Enhanced Cycle #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
            
            success = run_enhanced_cycle(components, args)
            if not success:
                log_warning("Cycle failed, continuing...")
            
            print(f"⏳ Waiting {args.interval} seconds...\n")
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        
        # Final stats
        risk_manager = components['risk_manager']
        final_return = ((risk_manager.current_capital / args.capital) - 1) * 100
        
        print("\n" + "="*50)
        print("📊 ENHANCED BOT FINAL RESULTS")
        print("="*50)
        print(f"Starting Capital: ${args.capital:.2f}")
        print(f"Final Capital: ${risk_manager.current_capital:.2f}")
        print(f"Total Return: {final_return:.1f}%")
        print(f"Daily P&L: ${risk_manager.daily_pnl:.2f}")
        print(f"Trades Executed: {risk_manager.trades_today}")
        print(f"Total Cycles: {cycle_count}")
        
        if risk_manager.trades_today > 0:
            avg_pnl = risk_manager.daily_pnl / risk_manager.trades_today
            print(f"Average P&L per Trade: ${avg_pnl:.2f}")
            
        print("="*50)


if __name__ == "__main__":
    main()