#!/usr/bin/env python3
"""
Aggressive Trading Bot with Yahoo Finance Data

This version uses Yahoo Finance for market data instead of Alpaca,
while still supporting Alpaca for paper trading execution.
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
from bot.aggressive_strategies import (
    create_aggressive_strategy_suite,
    AggressiveRiskManager
)
from bot.aggressive_config import get_aggressive_config, calculate_dynamic_position_size
from bot.utils import setup_logging, log_info, log_error, log_warning


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggressive Crypto Trading Bot with Yahoo Finance Data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with paper trading (recommended for testing)
    python run_aggressive_bot_yahoo.py --paper-trading
    
    # Run with real money (be careful!)
    python run_aggressive_bot_yahoo.py --capital 100
    
    # Test with different crypto
    python run_aggressive_bot_yahoo.py --paper-trading --symbol ETH/USD
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
    
    log_info("🔥 Starting Aggressive Crypto Trading Bot with Yahoo Finance")
    log_info(f"💰 Starting Capital: ${args.capital}")
    log_info(f"📊 Trading Symbol: {args.symbol}")
    log_info(f"🎯 Paper Trading: {args.paper_trading}")
    
    # Initialize Yahoo Finance data fetcher
    data_fetcher = YahooDataFetcher()
    
    # Test data connection
    log_info("🔍 Testing data connection...")
    test_data = data_fetcher.fetch_crypto_data(args.symbol, limit=10)
    if test_data is None or test_data.empty:
        log_error(f"Failed to fetch data for {args.symbol}")
        return None
    
    log_info(f"✅ Data connection successful - {len(test_data)} data points")
    log_info(f"📈 Current price: ${test_data['close'].iloc[-1]:.2f}")
    
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
    
    # Initialize trader (only if not paper trading)
    trader = None
    if not args.paper_trading:
        try:
            # Load Alpaca config for real trading
            config = Config()
            if config.load_env_variables() and config.validate_config():
                credentials = config.get_alpaca_credentials()
                trader_settings = config.get_trading_settings()
                trader_settings.symbol = args.symbol
                trader_settings.aggressive_mode = True
                trader_settings.initial_capital = args.capital
                trader_settings.use_dynamic_sizing = True
                
                trader = Trader(credentials, trader_settings)
                log_info("✅ Real trading enabled with Alpaca")
            else:
                log_warning("⚠️ Alpaca config failed, falling back to paper trading")
                args.paper_trading = True
        except Exception as e:
            log_warning(f"⚠️ Trader setup failed: {e}, using paper trading")
            args.paper_trading = True
    
    return {
        'data_fetcher': data_fetcher,
        'signal_generator': signal_generator,
        'risk_manager': risk_manager,
        'trader': trader,
        'trading_settings': trading_settings,
        'aggressive_config': aggressive_config
    }


def run_trading_cycle(components, args):
    """Run a single trading cycle."""
    data_fetcher = components['data_fetcher']
    signal_generator = components['signal_generator']
    risk_manager = components['risk_manager']
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
        data = data_fetcher.fetch_crypto_data(args.symbol, timeframe="5Min", limit=100)
        
        if data is None or data.empty:
            log_error("Failed to fetch market data")
            return False
        
        log_info(f"✅ Fetched {len(data)} data points, latest price: ${data['close'].iloc[-1]:.2f}")
        
        # Generate trading signals
        log_info("🎯 Analyzing market conditions...")
        signal = signal_generator.evaluate_all_strategies(data)
        
        # Check for individual strategy signals if combined is weak
        if signal.confidence < 0.4:
            individual_signals = []
            for strategy in signal_generator.strategies:
                try:
                    individual_signal = strategy.calculate_signals(data)
                    if individual_signal.confidence > 0.4:
                        individual_signals.append(individual_signal)
                except:
                    pass
            
            if individual_signals:
                signal = max(individual_signals, key=lambda s: s.confidence)
                log_info(f"Using individual strategy signal: {signal.strategy}")
        
        # Check signal strength
        if signal.confidence < 0.4:
            log_info(f"Signal too weak: {signal.action.value} with {signal.confidence:.2f} confidence")
            return True
        
        # Calculate position size
        current_price = data['close'].iloc[-1]
        volatility = data['close'].pct_change().rolling(10).std().iloc[-1]
        
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
        
        if args.paper_trading:
            # Paper trading simulation
            print("📝 PAPER TRADE - No real money involved")
            
            # Simulate trade outcome based on signal confidence
            import random
            success_rate = 0.5 + (signal.confidence * 0.2)  # 50-70% success rate
            
            if random.random() < success_rate:
                profit_pct = random.uniform(0.01, 0.04)  # 1-4% profit
                pnl = position_size * profit_pct
                print(f"   ✅ Simulated Result: +${pnl:.2f} ({profit_pct*100:.1f}%)")
            else:
                loss_pct = random.uniform(0.01, 0.025)  # 1-2.5% loss
                pnl = -position_size * loss_pct
                print(f"   ❌ Simulated Result: ${pnl:.2f} ({loss_pct*100:.1f}%)")
            
            # Update risk manager for tracking
            risk_manager.update_capital(pnl)
            
        else:
            # Real trading with Alpaca
            print("💰 REAL MONEY TRADE")
            
            if trader:
                success = trader.execute_trade(
                    signal=signal,
                    position_size=position_size,
                    current_price=current_price
                )
                
                if success:
                    print("   ✅ Trade executed successfully")
                    # Note: Real P&L would be updated by the trader
                else:
                    print("   ❌ Trade execution failed")
            else:
                print("   ❌ No trader available - check Alpaca configuration")
        
        # Log current status
        print(f"   💰 Current Capital: ${risk_manager.current_capital:.2f}")
        print(f"   📊 Daily P&L: ${risk_manager.daily_pnl:.2f}")
        print(f"   📈 Total Return: {((risk_manager.current_capital / args.capital) - 1) * 100:.1f}%")
        
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
    print("🔥 AGGRESSIVE CRYPTO TRADING BOT - YAHOO FINANCE")
    print("="*60)
    print(f"💰 Starting Capital: ${args.capital}")
    print(f"📊 Trading Symbol: {args.symbol}")
    print(f"🎯 Paper Trading: {'YES' if args.paper_trading else 'NO'}")
    print(f"⚡ Max Risk/Trade: {args.max_risk_per_trade*100}%")
    print(f"🛡️ Max Daily Loss: {args.max_daily_loss*100}%")
    print(f"⏱️ Trading Interval: {args.interval}s")
    print(f"📡 Data Source: Yahoo Finance")
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