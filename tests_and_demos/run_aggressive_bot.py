#!/usr/bin/env python3
"""
Aggressive Trading Bot Runner

This script runs the crypto trading bot with aggressive strategies
optimized for small accounts ($100 starting capital) with higher
risk tolerance for potentially higher returns.

Usage:
    python run_aggressive_bot.py [--paper-trading] [--capital 100]
"""
import argparse
import sys
import time
from datetime import datetime
from typing import List

from bot.config import Config
from bot.data_fetcher import DataFetcher
from bot.trader import Trader
from bot.strategy import SignalGenerator
from bot.aggressive_strategies import (
    create_aggressive_strategy_suite,
    AggressiveRiskManager
)
from bot.aggressive_config import get_aggressive_config
# from bot.scheduler import Scheduler  # Not needed for simple loop
from bot.utils import setup_logging
from bot.utils import log_info, log_error, log_warning


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggressive Crypto Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with paper trading (recommended for testing)
    python run_aggressive_bot.py --paper-trading
    
    # Run with real money (be careful!)
    python run_aggressive_bot.py --capital 100
    
    # Run with custom settings
    python run_aggressive_bot.py --capital 50 --max-daily-loss 0.10
        """
    )
    
    parser.add_argument(
        "--paper-trading",
        action="store_true",
        help="Run in paper trading mode (no real money)"
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
        default=60,
        help="Trading interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def setup_aggressive_bot(args):
    """Set up the aggressive trading bot with all components."""
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    
    log_info("🔥 Starting Aggressive Crypto Trading Bot")
    log_info(f"💰 Starting Capital: ${args.capital}")
    log_info(f"📊 Trading Symbol: {args.symbol}")
    log_info(f"🎯 Paper Trading: {args.paper_trading}")
    
    # Load configuration
    config = Config()
    if not config.load_env_variables():
        log_error("Failed to load environment variables")
        return None
    
    if not config.validate_config():
        log_error("Configuration validation failed")
        return None
    
    # Get aggressive trading configuration
    aggressive_config = get_aggressive_config()
    trading_settings = aggressive_config["trading_settings"]
    
    # Override with command line arguments
    trading_settings.initial_capital = args.capital
    trading_settings.max_daily_loss_pct = args.max_daily_loss
    trading_settings.max_risk_per_trade_pct = args.max_risk_per_trade
    
    # Create aggressive strategies
    log_info("⚡ Creating aggressive trading strategies...")
    strategies = create_aggressive_strategy_suite()
    signal_generator = SignalGenerator(strategies)
    
    # Initialize risk manager
    log_info("🛡️ Setting up risk management...")
    risk_manager = AggressiveRiskManager(
        initial_capital=args.capital,
        max_risk_per_trade=args.max_risk_per_trade,
        max_daily_loss=args.max_daily_loss,
        max_position_size=trading_settings.max_position_size_pct
    )
    
    # Initialize components
    credentials = config.get_alpaca_credentials()
    data_fetcher = DataFetcher(credentials)
    
    # Get trading settings and update for aggressive mode
    trader_settings = config.get_trading_settings()
    trader_settings.symbol = args.symbol
    trader_settings.aggressive_mode = True
    trader_settings.initial_capital = args.capital
    trader_settings.use_dynamic_sizing = True
    
    trader = Trader(credentials, trader_settings)
    
    # Settings already configured above
    
    return {
        'config': config,
        'signal_generator': signal_generator,
        'risk_manager': risk_manager,
        'data_fetcher': data_fetcher,
        'trader': trader,
        'trading_settings': trading_settings,
        'aggressive_config': aggressive_config
    }


def run_trading_cycle(components, args):
    """Run a single trading cycle."""
    signal_generator = components['signal_generator']
    risk_manager = components['risk_manager']
    data_fetcher = components['data_fetcher']
    trader = components['trader']
    trading_settings = components['trading_settings']
    
    try:
        # Check if we can trade
        can_trade, reason = risk_manager.can_trade()
        if not can_trade:
            log_warning(f"Trading blocked: {reason}")
            return False
        
        # Fetch market data
        log_info(f"📊 Fetching market data for {args.symbol}...")
        data = data_fetcher.fetch_crypto_data(args.symbol, limit=100)
        
        if data is None or data.empty:
            log_error("Failed to fetch market data")
            return False
        
        # Generate trading signals
        log_info("🎯 Analyzing market conditions...")
        signal = signal_generator.evaluate_all_strategies(data)
        
        # Check signal strength
        if signal.confidence < trading_settings.min_signal_confidence:
            log_info(f"Signal too weak: {signal.confidence:.2f} < {trading_settings.min_signal_confidence}")
            return True
        
        # Calculate position size
        current_price = data['close'].iloc[-1]
        volatility = data['close'].pct_change().rolling(10).std().iloc[-1]
        
        from bot.aggressive_config import calculate_dynamic_position_size
        position_size = calculate_dynamic_position_size(
            capital=risk_manager.current_capital,
            signal_confidence=signal.confidence,
            volatility=volatility,
            settings=trading_settings
        )
        
        # Log signal details
        log_info(f"🚨 {signal.action.value} Signal Generated!")
        log_info(f"   Strategy: {signal.strategy}")
        log_info(f"   Confidence: {signal.confidence:.2f}")
        log_info(f"   Price: ${current_price:.2f}")
        log_info(f"   Position Size: ${position_size:.2f}")
        log_info(f"   Reasoning: {signal.reasoning}")
        
        if args.paper_trading:
            # Paper trading simulation
            log_info("📝 PAPER TRADE - No real money involved")
            
            # Simulate trade outcome (for demo purposes)
            import random
            success_rate = 0.6 if signal.confidence > 0.7 else 0.5
            
            if random.random() < success_rate:
                profit_pct = random.uniform(0.01, 0.04)
                pnl = position_size * profit_pct
                log_info(f"   ✅ Simulated Result: +${pnl:.2f} ({profit_pct*100:.1f}%)")
            else:
                loss_pct = random.uniform(0.01, 0.025)
                pnl = -position_size * loss_pct
                log_info(f"   ❌ Simulated Result: ${pnl:.2f} ({loss_pct*100:.1f}%)")
            
            # Update risk manager for tracking
            risk_manager.update_capital(pnl)
            
        else:
            # Real trading
            log_warning("💰 REAL MONEY TRADE - BE CAREFUL!")
            
            # Execute the trade
            success = trader.execute_trade(
                signal=signal,
                position_size=position_size,
                current_price=current_price
            )
            
            if success:
                log_info("✅ Trade executed successfully")
            else:
                log_error("❌ Trade execution failed")
        
        # Log current status
        log_info(f"💰 Current Capital: ${risk_manager.current_capital:.2f}")
        log_info(f"📊 Daily P&L: ${risk_manager.daily_pnl:.2f}")
        log_info(f"📈 Total Return: {((risk_manager.current_capital / args.capital) - 1) * 100:.1f}%")
        
        return True
        
    except Exception as e:
        log_error(f"Error in trading cycle: {str(e)}")
        return False


def main():
    """Main function to run the aggressive trading bot."""
    args = parse_arguments()
    
    # Setup bot components
    components = setup_aggressive_bot(args)
    if not components:
        log_error("Failed to setup trading bot")
        sys.exit(1)
    
    # Display startup information
    print("\n" + "="*60)
    print("🔥 AGGRESSIVE CRYPTO TRADING BOT")
    print("="*60)
    print(f"💰 Starting Capital: ${args.capital}")
    print(f"📊 Trading Symbol: {args.symbol}")
    print(f"🎯 Paper Trading: {'YES' if args.paper_trading else 'NO'}")
    print(f"⚡ Max Risk/Trade: {args.max_risk_per_trade*100}%")
    print(f"🛡️ Max Daily Loss: {args.max_daily_loss*100}%")
    print(f"⏱️ Trading Interval: {args.interval}s")
    print("="*60)
    
    if not args.paper_trading:
        print("⚠️  WARNING: REAL MONEY TRADING ENABLED!")
        print("⚠️  You can lose your entire capital quickly!")
        response = input("Type 'YES' to continue with real money: ")
        if response != 'YES':
            print("Exiting for safety...")
            sys.exit(0)
    
    print(f"\n🚀 Starting trading at {datetime.now()}")
    print("Press Ctrl+C to stop the bot\n")
    
    # Main trading loop
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            log_info(f"🔄 Trading Cycle #{cycle_count}")
            
            success = run_trading_cycle(components, args)
            if not success:
                log_warning("Trading cycle failed, continuing...")
            
            # Wait for next cycle
            log_info(f"⏳ Waiting {args.interval} seconds for next cycle...")
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        log_info("\n🛑 Bot stopped by user")
        
        # Final statistics
        risk_manager = components['risk_manager']
        final_return = ((risk_manager.current_capital / args.capital) - 1) * 100
        
        print("\n" + "="*50)
        print("📊 FINAL STATISTICS")
        print("="*50)
        print(f"Starting Capital: ${args.capital:.2f}")
        print(f"Final Capital: ${risk_manager.current_capital:.2f}")
        print(f"Total Return: {final_return:.1f}%")
        print(f"Daily P&L: ${risk_manager.daily_pnl:.2f}")
        print(f"Trades Today: {risk_manager.trades_today}")
        print(f"Total Cycles: {cycle_count}")
        print("="*50)
        
    except Exception as e:
        log_error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()