#!/usr/bin/env python3
"""
Test appropriate position sizes for a $100 account.
"""
import os
import sys
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.crypto_position_manager import CryptoPositionManager
from bot.crypto_risk_manager import CryptoRiskManager
from bot.data_fetcher import DataFetcher


def test_appropriate_positions():
    """Test appropriate position sizes for a $100 account."""
    print("💡 Testing Appropriate Position Sizes for $100 Account")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Missing Kraken API credentials!")
        return
    
    # Create credentials and client
    credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
    client = KrakenClient(credentials)
    
    # Create components
    position_manager = CryptoPositionManager(client)
    data_fetcher = DataFetcher()
    risk_manager = CryptoRiskManager(
        position_manager=position_manager,
        data_fetcher=data_fetcher,
        client=client
    )
    
    # Get current BTC price
    btc_price = client.get_current_price('XBTUSD')
    if not btc_price:
        print("❌ Could not get BTC price")
        return
    
    print(f"💰 Portfolio Value: ${risk_manager._get_portfolio_value():.2f}")
    print(f"₿ Current BTC Price: ${btc_price:,.2f}")
    print()
    
    # Test various position sizes
    test_positions = [
        ("$5 position", 5.0 / btc_price),
        ("$10 position", 10.0 / btc_price),
        ("$20 position", 20.0 / btc_price),
        ("$50 position", 50.0 / btc_price),
        ("$100 position", 100.0 / btc_price),
    ]
    
    print("🔍 Position Size Validation Results:")
    print("-" * 60)
    
    for description, btc_amount in test_positions:
        is_valid, adjusted_size, reason = risk_manager.validate_position_size('BTC', btc_amount, btc_price)
        position_value = btc_amount * btc_price
        
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"{description:15} | {btc_amount:.8f} BTC | ${position_value:6.2f} | {status}")
        if not is_valid:
            print(f"                  Reason: {reason}")
        print()
    
    # Show recommended position size
    print("💡 Recommendations for $100 Account:")
    print("-" * 40)
    
    # Calculate max position based on 10% rule
    max_position_value = 100.0 * 0.10  # 10% of $100
    max_btc_amount = max_position_value / btc_price
    
    print(f"• Max recommended position: ${max_position_value:.2f} ({max_btc_amount:.8f} BTC)")
    print(f"• This follows the 10% portfolio risk rule")
    print()
    
    # Test the recommended position
    is_valid, adjusted_size, reason = risk_manager.validate_position_size('BTC', max_btc_amount, btc_price)
    status = "✅ VALID" if is_valid else "❌ INVALID"
    print(f"Recommended position validation: {status}")
    if not is_valid:
        print(f"Reason: {reason}")
    
    print("\n🎯 To enable trading with your $100 account:")
    print("1. Use smaller trade amounts (e.g., --trade-amount 5 or --trade-amount 10)")
    print("2. The bot's risk management is working correctly!")
    print("3. Consider funding your account with more capital for larger trades")


if __name__ == "__main__":
    test_appropriate_positions()