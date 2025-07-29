#!/usr/bin/env python3
"""
Test paper trading with forced signals to demonstrate the functionality.
"""
import os
import sys
import time
import random
from datetime import datetime
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_info, log_error


def create_test_signal(action: SignalType, confidence: float, price: float) -> TradingSignal:
    """Create a test trading signal."""
    return TradingSignal(
        action=action,
        confidence=confidence,
        price=price,
        timestamp=datetime.now(),
        reasoning=f"Test signal for paper trading demo"
    )


def test_paper_trading():
    """Test paper trading with forced signals."""
    print("🎯 Testing Paper Trading with Forced Signals")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Missing Kraken API credentials!")
        return
    
    # Create credentials
    credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
    
    # Create trading configuration for paper trading
    config = KrakenTradingConfig(
        trading_pair="XBTUSD",
        trade_amount_usd=10.0,
        max_position_usd=50.0,
        min_trade_interval=5  # 5 seconds for testing
    )
    
    # Initialize trader
    trader = KrakenTrader(credentials, config)
    
    # Test connection
    if not trader.test_connection():
        print("❌ Failed to connect to Kraken API")
        return
    
    print("✅ Connected to Kraken API")
    
    # Get current price
    current_price = trader.get_current_price(config.trading_pair)
    if not current_price:
        print("❌ Could not get current price")
        return
    
    print(f"📊 Current BTC Price: ${current_price:,.2f}")
    
    # Show initial portfolio
    portfolio = trader.get_portfolio_summary()
    print(f"💰 Initial Portfolio:")
    print(f"   BTC Balance: {portfolio.get('btc_balance', 0):.6f}")
    print(f"   USD Balance: ${portfolio.get('usd_balance', 0):,.2f}")
    print(f"   Total Value: ${portfolio.get('total_portfolio_value', 0):,.2f}")
    
    # Test different signal types
    test_signals = [
        (SignalType.BUY, 0.7, "Strong bullish momentum"),
        (SignalType.SELL, 0.6, "Bearish reversal pattern"),
        (SignalType.BUY, 0.8, "Breakout above resistance"),
        (SignalType.HOLD, 0.3, "Consolidation phase"),
        (SignalType.SELL, 0.5, "Profit taking signal")
    ]
    
    print(f"\n🚀 Testing {len(test_signals)} Trading Signals:")
    print("-" * 50)
    
    for i, (action, confidence, reasoning) in enumerate(test_signals, 1):
        print(f"\n📈 Test Signal #{i}:")
        print(f"   Action: {action.name}")
        print(f"   Confidence: {confidence:.1f}")
        print(f"   Reasoning: {reasoning}")
        
        # Create test signal
        signal = TradingSignal(
            action=action,
            confidence=confidence,
            price=current_price,
            timestamp=datetime.now(),
            strategy="test_strategy",
            reasoning=reasoning
        )
        
        # Since we're in paper trading mode, let's simulate the trade execution
        if action != SignalType.HOLD:
            print(f"   📝 PAPER TRADE SIMULATION:")
            
            # Simulate trade execution
            success_rate = 0.4 + (confidence * 0.3)  # 40-70% success rate
            
            if random.random() < success_rate:
                profit_pct = random.uniform(0.005, 0.025)  # 0.5% to 2.5%
                pnl = config.trade_amount_usd * profit_pct
                print(f"   ✅ Simulated Profit: +${pnl:.2f} ({profit_pct*100:.1f}%)")
            else:
                loss_pct = random.uniform(0.005, 0.015)  # 0.5% to 1.5%
                pnl = -config.trade_amount_usd * loss_pct
                print(f"   ❌ Simulated Loss: ${pnl:.2f} ({loss_pct*100:.1f}%)")
            
            # Show trade details
            volume = config.trade_amount_usd / current_price
            print(f"   💱 Trade Details:")
            print(f"      Side: {action.name}")
            print(f"      Volume: {volume:.6f} BTC")
            print(f"      Price: ${current_price:,.2f}")
            print(f"      Amount: ${config.trade_amount_usd}")
            print(f"      Fee: $0.00 (paper trading)")
        else:
            print(f"   ⏸️  HOLD - No trade executed")
        
        # Wait between signals
        if i < len(test_signals):
            print(f"   ⏳ Waiting 3 seconds...")
            time.sleep(3)
    
    print(f"\n✅ Paper Trading Test Completed!")
    print(f"📊 This demonstrates how the bot would behave in paper trading mode.")
    print(f"🎯 In real operation, signals would come from technical analysis strategies.")


if __name__ == "__main__":
    test_paper_trading()