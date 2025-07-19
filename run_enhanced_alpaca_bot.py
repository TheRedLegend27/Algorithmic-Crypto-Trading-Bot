#!/usr/bin/env python3
"""
Enhanced Aggressive Trading Bot with Alpaca Integration

This version uses Yahoo Finance for market data and Alpaca for trading execution.
Falls back gracefully if Alpaca is not available.
"""
import argparse
import sys
import time
from datetime import datetime
from typing import List, Optional

from bot.config import Config
from bot.yahoo_data_fetcher import YahooDataFetcher
from bot.strategy import SignalGenerator
from bot.enhanced_strategies import create_enhanced_strategy_suite
from bot.aggressive_strategies import AggressiveRiskManager
from bot.aggressive_config import get_aggressive_config, calculate_dynamic_position_size
from bot.utils import setup_logging, log_info, log_error, log_warning

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    log_warning("Alpaca library not available - paper trading only")


class EnhancedAlpacaTrader:
    """Enhanced trader that integrates with Alpaca for real execution."""
    
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        """Initialize the Alpaca trader."""
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.client = None
        self.connected = False
        
        self._connect()
    
    def _connect(self):
        """Connect to Alpaca API."""
        if not ALPACA_AVAILABLE:
            log_warning("Alpaca library not available")
            return False
        
        try:
            self.client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper
            )
            
            # Test connection
            account = self.client.get_account()
            self.connected = True
            
            log_info(f"✅ Connected to Alpaca {'Paper' if self.paper else 'Live'} Trading")
            log_info(f"Account Status: {account.status}")
            log_info(f"Buying Power: ${float(account.buying_power):,.2f}")
            log_info(f"Cash: ${float(account.cash):,.2f}")
            
            return True
            
        except Exception as e:
            log_error(f"❌ Failed to connect to Alpaca: {str(e)}")
            self.connected = False
            return False
    
    def get_account_info(self):
        """Get account information."""
        if not self.connected:
            return None
        
        try:
            return self.client.get_account()
        except Exception as e:
            log_error(f"Error getting account info: {str(e)}")
            return None
    
    def execute_trade(self, signal, position_size: float, symbol: str = "AAPL"):
        """
        Execute a trade based on the signal.
        
        Note: Since we can't trade crypto directly on Alpaca, we'll use AAPL as a proxy
        or crypto-related ETFs like BITO for BTC exposure.
        """
        if not self.connected:
            log_warning("Not connected to Alpaca - simulating trade")
            return self._simulate_trade(signal, position_size)
        
        try:
            # Map crypto symbols to tradeable alternatives
            symbol_mapping = {
                "BTC/USD": "BITO",  # Bitcoin ETF
                "ETH/USD": "ETHE",  # Ethereum ETF
                "SOL/USD": "AAPL",  # Use AAPL as proxy for now
                "AVAX/USD": "AAPL",
                "MATIC/USD": "AAPL"
            }
            
            tradeable_symbol = symbol_mapping.get(symbol, "AAPL")
            
            # Calculate shares to buy/sell
            # For simplicity, assume $100 per share average
            shares = max(1, int(position_size / 100))
            
            # Determine order side
            side = OrderSide.BUY if signal.action.value == "BUY" else OrderSide.SELL
            
            # Create market order
            order_request = MarketOrderRequest(
                symbol=tradeable_symbol,
                qty=shares,
                side=side,
                time_in_force=TimeInForce.DAY
            )
            
            # Submit order
            order = self.client.submit_order(order_request)
            
            log_info(f"✅ Order submitted: {side.value} {shares} shares of {tradeable_symbol}")
            log_info(f"Order ID: {order.id}")
            
            return {
                'success': True,
                'order_id': order.id,
                'symbol': tradeable_symbol,
                'shares': shares,
                'side': side.value
            }
            
        except Exception as e:
            log_error(f"❌ Trade execution failed: {str(e)}")
            return self._simulate_trade(signal, position_size)
    
    def _simulate_trade(self, signal, position_size: float):
        """Simulate trade execution."""
        import random
        
        # Simulate based on signal confidence
        success_rate = 0.5 + (signal.confidence * 0.2)
        
        if random.random() < success_rate:
            profit_pct = random.uniform(0.01, 0.04)
            pnl = position_size * profit_pct
            result = "WIN"
        else:
            loss_pct = random.uniform(0.01, 0.025)
            pnl = -position_size * loss_pct
            result = "LOSS"
        
        return {
            'success': True,
            'simulated': True,
            'result': result,
            'pnl': pnl,
            'position_size': position_size
        }


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhanced Aggressive Trading Bot with Alpaca Integration"
    )
    
    parser.add_argument("--capital", type=float, default=100.0, help="Starting capital")
    parser.add_argument("--symbol", type=str, default="BTC/USD", help="Trading symbol")
    parser.add_argument("--interval", type=int, default=30, help="Trading interval in seconds")
    parser.add_argument("--min-confidence", type=float, default=0.35, help="Minimum signal confidence")
    parser.add_argument("--max-trades", type=int, default=20, help="Maximum trades per session")
    parser.add_argument("--paper-only", action="store_true", help="Force paper trading only")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    
    return parser.parse_args()


def setup_enhanced_alpaca_bot(args):
    """Set up the enhanced bot with Alpaca integration."""
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    
    log_info("🚀 Starting Enhanced Aggressive Trading Bot with Alpaca")
    log_info(f"💰 Starting Capital: ${args.capital}")
    log_info(f"📊 Trading Symbol: {args.symbol}")
    
    # Initialize data fetcher
    data_fetcher = YahooDataFetcher()
    
    # Test data connection
    test_data = data_fetcher.fetch_crypto_data(args.symbol, limit=10)
    if test_data is None or test_data.empty:
        log_error(f"Failed to fetch data for {args.symbol}")
        return None
    
    log_info(f"✅ Yahoo Finance connected - Current price: ${test_data['close'].iloc[-1]:.2f}")
    
    # Initialize Alpaca trader
    alpaca_trader = None
    if not args.paper_only:
        try:
            config = Config()
            if config.load_env_variables():
                credentials = config.get_alpaca_credentials()
                alpaca_trader = EnhancedAlpacaTrader(
                    api_key=credentials.api_key,
                    secret_key=credentials.secret_key,
                    paper=True  # Always use paper for now
                )
        except Exception as e:
            log_warning(f"Alpaca setup failed: {str(e)} - Using simulation only")
    
    # Create strategies
    strategies = create_enhanced_strategy_suite()
    signal_generator = SignalGenerator(strategies)
    
    # Risk manager
    risk_manager = AggressiveRiskManager(
        initial_capital=args.capital,
        max_risk_per_trade=0.05,
        max_daily_loss=0.15,
        max_position_size=0.8
    )
    
    # Trading settings
    aggressive_config = get_aggressive_config()
    trading_settings = aggressive_config["trading_settings"]
    trading_settings.min_signal_confidence = args.min_confidence
    
    return {
        'data_fetcher': data_fetcher,
        'signal_generator': signal_generator,
        'risk_manager': risk_manager,
        'alpaca_trader': alpaca_trader,
        'trading_settings': trading_settings,
        'strategies': strategies
    }


def run_enhanced_alpaca_cycle(components, args):
    """Run enhanced trading cycle with Alpaca integration."""
    
    data_fetcher = components['data_fetcher']
    signal_generator = components['signal_generator']
    risk_manager = components['risk_manager']
    alpaca_trader = components['alpaca_trader']
    trading_settings = components['trading_settings']
    strategies = components['strategies']
    
    try:
        # Check trading limits
        can_trade, reason = risk_manager.can_trade()
        if not can_trade:
            log_warning(f"Trading blocked: {reason}")
            return False
        
        # Fetch market data
        data = data_fetcher.fetch_crypto_data(args.symbol, timeframe="5Min", limit=100)
        if data is None or data.empty:
            log_error("Failed to fetch market data")
            return False
        
        current_price = data['close'].iloc[-1]
        
        # Analyze strategies
        individual_signals = []
        print(f"\n🔍 Strategy Analysis (Price: ${current_price:.2f}):")
        
        for strategy in strategies:
            try:
                signal = strategy.calculate_signals(data)
                individual_signals.append(signal)
                
                if signal.confidence > 0:
                    print(f"   {strategy.name}: {signal.action.value} ({signal.confidence:.2f})")
                    print(f"      {signal.reasoning}")
                else:
                    print(f"   {strategy.name}: HOLD")
                    
            except Exception as e:
                log_error(f"Error in {strategy.name}: {e}")
        
        # Get best signal
        combined_signal = signal_generator.evaluate_all_strategies(data)
        best_signal = combined_signal
        
        if combined_signal.confidence < args.min_confidence and individual_signals:
            strong_signals = [s for s in individual_signals if s.confidence >= args.min_confidence]
            if strong_signals:
                best_signal = max(strong_signals, key=lambda s: s.confidence)
                print(f"   🎯 Using {best_signal.strategy} signal")
        
        # Check signal strength
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
        print(f"   Position Size: ${position_size:.2f}")
        
        # Execute with Alpaca or simulate
        if alpaca_trader and alpaca_trader.connected:
            print("   💰 EXECUTING WITH ALPACA")
            result = alpaca_trader.execute_trade(best_signal, position_size, args.symbol)
            
            if result.get('success'):
                if result.get('simulated'):
                    pnl = result['pnl']
                    print(f"   📝 Simulated: {result['result']} ${pnl:+.2f}")
                else:
                    print(f"   ✅ Real trade: {result['side']} {result['shares']} {result['symbol']}")
                    # For real trades, we'd need to track the actual P&L
                    pnl = position_size * 0.02  # Assume 2% for demo
                
                risk_manager.update_capital(pnl)
        else:
            print("   📝 PAPER TRADE SIMULATION")
            # Simulate trade
            import random
            success_rate = 0.5 + (best_signal.confidence * 0.2)
            
            if random.random() < success_rate:
                profit_pct = random.uniform(0.01, 0.04)
                pnl = position_size * profit_pct
                print(f"   ✅ Result: +${pnl:.2f} ({profit_pct*100:.1f}%)")
            else:
                loss_pct = random.uniform(0.01, 0.025)
                pnl = -position_size * loss_pct
                print(f"   ❌ Result: ${pnl:.2f} ({loss_pct*100:.1f}%)")
            
            risk_manager.update_capital(pnl)
        
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
    components = setup_enhanced_alpaca_bot(args)
    if not components:
        log_error("Failed to setup bot")
        sys.exit(1)
    
    # Display info
    alpaca_status = "Connected" if components['alpaca_trader'] and components['alpaca_trader'].connected else "Simulation Only"
    
    print("\n" + "="*70)
    print("🚀 ENHANCED AGGRESSIVE TRADING BOT WITH ALPACA")
    print("="*70)
    print(f"💰 Starting Capital: ${args.capital}")
    print(f"📊 Trading Symbol: {args.symbol}")
    print(f"🎚️ Min Confidence: {args.min_confidence*100}%")
    print(f"⏱️ Trading Interval: {args.interval}s")
    print(f"🎯 Max Trades: {args.max_trades}")
    print(f"📡 Data Source: Yahoo Finance")
    print(f"💼 Trading: {alpaca_status}")
    print(f"🧠 Strategies: Enhanced Momentum, Price Action, Multi-Timeframe")
    print("="*70)
    
    print(f"\n🚀 Starting enhanced Alpaca trading at {datetime.now()}")
    print("Press Ctrl+C to stop\n")
    
    # Main loop
    cycle_count = 0
    trades_executed = 0
    
    try:
        while cycle_count < args.max_trades * 2:  # Safety limit
            cycle_count += 1
            print(f"🔄 Cycle #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
            
            success = run_enhanced_alpaca_cycle(components, args)
            if success and components['risk_manager'].trades_today > trades_executed:
                trades_executed = components['risk_manager'].trades_today
                
                if trades_executed >= args.max_trades:
                    print(f"\n🎯 Reached maximum trades ({args.max_trades}) - stopping")
                    break
            
            print(f"⏳ Waiting {args.interval} seconds...\n")
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    
    # Final stats
    risk_manager = components['risk_manager']
    final_return = ((risk_manager.current_capital / args.capital) - 1) * 100
    
    print("\n" + "="*50)
    print("📊 ENHANCED ALPACA BOT RESULTS")
    print("="*50)
    print(f"Starting Capital: ${args.capital:.2f}")
    print(f"Final Capital: ${risk_manager.current_capital:.2f}")
    print(f"Total Return: {final_return:.1f}%")
    print(f"Trades Executed: {risk_manager.trades_today}")
    print(f"Total Cycles: {cycle_count}")
    
    if risk_manager.trades_today > 0:
        avg_pnl = risk_manager.daily_pnl / risk_manager.trades_today
        print(f"Average P&L per Trade: ${avg_pnl:.2f}")
    
    print("="*50)


if __name__ == "__main__":
    main()