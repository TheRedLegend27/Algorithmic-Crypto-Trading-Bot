#!/usr/bin/env python3
"""
Example bot using the new Coinbase Advanced Trade API implementation.
This shows how to integrate the new trader with your existing bot logic.
"""
import os
import sys
import time
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.coinbase_advanced_client import AdvancedTradeCredentials
from bot.coinbase_advanced_trader import CoinbaseAdvancedTrader, TradingConfig
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_info, log_error


def create_trader():
    """Create and initialize the Coinbase Advanced trader."""
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    api_key = os.getenv("COINBASE_ADVANCED_API_KEY")
    private_key = os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
    
    if not api_key or not private_key:
        log_error("Missing Coinbase Advanced Trade API credentials!")
        log_error("Please set COINBASE_ADVANCED_API_KEY and COINBASE_ADVANCED_PRIVATE_KEY in your .env file")
        return None
    
    # Create credentials
    credentials = AdvancedTradeCredentials(
        api_key=api_key,
        private_key=private_key
    )
    
    # Create trading configuration
    config = TradingConfig(
        product_id="BTC-USD",
        trade_amount_usd=10.0,  # Start small for testing
        max_position_usd=50.0,
        min_trade_interval=300  # 5 minutes between trades
    )
    
    # Initialize trader
    trader = CoinbaseAdvancedTrader(credentials, config)
    
    # Test connection
    if not trader.test_connection():
        log_error("Failed to connect to Coinbase API")
        return None
    
    log_info("Coinbase Advanced trader initialized successfully!")
    return trader


def generate_sample_signal(price: float) -> TradingSignal:
    """
    Generate a sample trading signal.
    In a real bot, this would come from your strategy logic.
    """
    import random
    
    # Simple random signal for demonstration
    # In practice, this would be your actual trading strategy
    actions = [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
    action = random.choice(actions)
    confidence = random.uniform(0.5, 0.9)
    
    return TradingSignal(
        action=action,
        confidence=confidence,
        price=price,
        timestamp=time.time()
    )


def run_trading_loop(trader: CoinbaseAdvancedTrader, max_iterations: int = 10):
    """
    Run a simple trading loop for demonstration.
    In a real bot, this would be your main trading logic.
    """
    log_info(f"Starting trading loop for {max_iterations} iterations...")
    
    for i in range(max_iterations):
        try:
            log_info(f"\n--- Trading Loop Iteration {i+1}/{max_iterations} ---")
            
            # Get current portfolio status
            portfolio = trader.get_portfolio_summary()
            if portfolio:
                log_info(f"Portfolio Value: ${portfolio.get('total_portfolio_value', 0):.2f}")
                log_info(f"BTC Balance: {portfolio.get('base_available', 0):.6f}")
                log_info(f"USD Balance: ${portfolio.get('quote_available', 0):.2f}")
                log_info(f"Current BTC Price: ${portfolio.get('current_price', 0):.2f}")
            
            # Get current price for signal generation
            current_price = trader.get_current_price(trader.config.product_id)
            if not current_price:
                log_error("Could not get current price, skipping iteration")
                continue
            
            # Generate trading signal (replace with your actual strategy)
            signal = generate_sample_signal(current_price)
            log_info(f"Generated signal: {signal.action.name} (confidence: {signal.confidence:.2f})")
            
            # Execute trade based on signal
            if signal.action != SignalType.HOLD:
                result = trader.execute_trade(signal)
                
                if result.success:
                    log_info(f"✅ Trade executed successfully!")
                    log_info(f"   Order ID: {result.order_id}")
                    log_info(f"   Side: {result.side}")
                    log_info(f"   Size: {result.size}")
                    log_info(f"   Price: ~${result.price}")
                else:
                    log_error(f"❌ Trade failed: {result.error}")
            else:
                log_info("HOLD signal - no trade executed")
            
            # Show recent orders
            recent_orders = trader.get_recent_orders(limit=3)
            if recent_orders:
                log_info(f"Recent orders ({len(recent_orders)}):")
                for order in recent_orders:
                    status = order.get('status', 'Unknown')
                    side = order.get('side', 'Unknown')
                    size = order.get('order_configuration', {}).get('market_market_ioc', {}).get('base_size', 'N/A')
                    log_info(f"   - {side} {size} BTC ({status})")
            
            # Wait before next iteration (in real bot, this would be your strategy interval)
            if i < max_iterations - 1:  # Don't wait on last iteration
                log_info("Waiting 30 seconds before next iteration...")
                time.sleep(30)
                
        except KeyboardInterrupt:
            log_info("Received interrupt signal, stopping trading loop...")
            break
        except Exception as e:
            log_error(f"Error in trading loop: {str(e)}")
            time.sleep(10)  # Wait before retrying
    
    log_info("Trading loop completed!")


def main():
    """Main function."""
    print("🚀 Coinbase Advanced Trade API Bot")
    print("=" * 40)
    
    # Create trader
    trader = create_trader()
    if not trader:
        print("❌ Failed to initialize trader")
        return 1
    
    # Show initial portfolio status
    print("\n📊 Initial Portfolio Status:")
    portfolio = trader.get_portfolio_summary()
    if portfolio:
        print(f"   Total Value: ${portfolio.get('total_portfolio_value', 0):.2f}")
        print(f"   BTC Balance: {portfolio.get('base_available', 0):.6f}")
        print(f"   USD Balance: ${portfolio.get('quote_available', 0):.2f}")
        print(f"   Current BTC Price: ${portfolio.get('current_price', 0):.2f}")
    
    # Ask user if they want to proceed
    print(f"\n⚠️  WARNING: This bot will make REAL trades with REAL money!")
    print(f"   Trade amount: ${trader.config.trade_amount_usd} per trade")
    print(f"   Max position: ${trader.config.max_position_usd}")
    
    response = input("\nDo you want to proceed? (yes/no): ").lower().strip()
    if response not in ['yes', 'y']:
        print("Bot cancelled by user.")
        return 0
    
    try:
        # Run trading loop
        run_trading_loop(trader, max_iterations=5)  # Run 5 iterations for demo
        
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {str(e)}")
        return 1
    
    # Show final portfolio status
    print("\n📊 Final Portfolio Status:")
    portfolio = trader.get_portfolio_summary()
    if portfolio:
        print(f"   Total Value: ${portfolio.get('total_portfolio_value', 0):.2f}")
        print(f"   BTC Balance: {portfolio.get('base_available', 0):.6f}")
        print(f"   USD Balance: ${portfolio.get('quote_available', 0):.2f}")
    
    print("\n✅ Bot completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())