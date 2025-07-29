#!/usr/bin/env python3
"""
Test balance retrieval to debug the $0 portfolio issue.
"""
import os
import sys
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.utils import log_info, log_error


def test_balance_retrieval():
    """Test balance retrieval step by step."""
    print("🔍 Testing Balance Retrieval")
    print("=" * 40)
    
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
    
    # Test connection
    if not client.test_connection():
        print("❌ Failed to connect to Kraken API")
        return
    
    print("✅ Connected to Kraken API")
    
    # Test raw balance API call
    print("\n📊 Raw Balance API Response:")
    try:
        raw_balance = client.get_account_balance()
        print(f"Raw balance data: {raw_balance}")
        
        for currency, amount in raw_balance.items():
            if float(amount) > 0:
                print(f"   {currency}: {amount}")
    except Exception as e:
        print(f"❌ Error getting raw balance: {e}")
        return
    
    # Test trader balance methods
    print("\n🏦 Testing Trader Balance Methods:")
    config = KrakenTradingConfig(trading_pair="XBTUSD")
    trader = KrakenTrader(credentials, config)
    
    # Test USD balance
    print("\n💵 USD Balance Test:")
    usd_balance = trader.get_balance('USD')
    if usd_balance:
        print(f"   Currency: {usd_balance.currency}")
        print(f"   Balance: {usd_balance.balance}")
        print(f"   Available: {usd_balance.available}")
    else:
        print("   ❌ No USD balance returned")
    
    # Test BTC balance
    print("\n₿ BTC Balance Test:")
    btc_balance = trader.get_balance('BTC')
    if btc_balance:
        print(f"   Currency: {btc_balance.currency}")
        print(f"   Balance: {btc_balance.balance}")
        print(f"   Available: {btc_balance.available}")
    else:
        print("   ❌ No BTC balance returned")
    
    # Test portfolio summary
    print("\n📊 Portfolio Summary Test:")
    portfolio = trader.get_portfolio_summary()
    if portfolio:
        print(f"   Current Price: ${portfolio.get('current_price', 0):,.2f}")
        print(f"   BTC Balance: {portfolio.get('btc_balance', 0):.6f}")
        print(f"   USD Balance: ${portfolio.get('usd_balance', 0):,.2f}")
        print(f"   Total Value: ${portfolio.get('total_portfolio_value', 0):,.2f}")
    else:
        print("   ❌ No portfolio summary returned")
    
    # Debug currency mapping
    print("\n🔍 Currency Mapping Debug:")
    print(f"   USD -> {trader._get_kraken_currency_code('USD')}")
    print(f"   BTC -> {trader._get_kraken_currency_code('BTC')}")
    
    # Check cache
    print(f"\n💾 Balance Cache Debug:")
    trader._refresh_cache_if_needed()
    print(f"   Cache keys: {list(trader._balance_cache.keys())}")
    for key, value in trader._balance_cache.items():
        if float(value) > 0:
            print(f"   {key}: {value}")


if __name__ == "__main__":
    test_balance_retrieval()