#!/usr/bin/env python3
"""
Debug script to check what market data we're actually getting from Kraken.
"""
import os
import sys
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.utils import log_info, log_error


def debug_market_data():
    """Debug market data retrieval."""
    print("🔍 Debugging Market Data Retrieval")
    print("=" * 50)
    
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
    
    # Test current price
    print("\n📊 Testing Current Price:")
    try:
        price = client.get_current_price("XBTUSD")
        print(f"✅ Current BTC price: ${price:,.2f}")
    except Exception as e:
        print(f"❌ Error getting current price: {e}")
    
    # Test ticker data
    print("\n📈 Testing Ticker Data:")
    try:
        ticker = client.get_ticker(["XBTUSD"])
        print(f"✅ Ticker data keys: {list(ticker.keys())}")
        if ticker:
            for pair, data in ticker.items():
                print(f"   {pair}: {data}")
    except Exception as e:
        print(f"❌ Error getting ticker: {e}")
    
    # Test OHLC data
    print("\n📊 Testing OHLC Data:")
    try:
        ohlc = client.get_ohlc_data("XBTUSD", interval=5)
        print(f"✅ OHLC response type: {type(ohlc)}")
        print(f"✅ OHLC keys: {list(ohlc.keys()) if isinstance(ohlc, dict) else 'Not a dict'}")
        
        if isinstance(ohlc, dict):
            for key, value in ohlc.items():
                print(f"   {key}: {type(value)} with {len(value) if hasattr(value, '__len__') else 'no length'} items")
                if hasattr(value, '__len__') and len(value) > 0:
                    print(f"      First item: {value[0] if isinstance(value, list) else 'Not a list'}")
                    if len(value) > 1:
                        print(f"      Last item: {value[-1]}")
    except Exception as e:
        print(f"❌ Error getting OHLC: {e}")
    
    # Test tradable pairs
    print("\n🔗 Testing Tradable Pairs:")
    try:
        pairs = client.get_tradable_pairs(["XBTUSD"])
        print(f"✅ Pairs response: {list(pairs.keys()) if isinstance(pairs, dict) else 'Not a dict'}")
        if isinstance(pairs, dict):
            for pair, info in pairs.items():
                print(f"   {pair}: altname={info.get('altname', 'N/A')}")
    except Exception as e:
        print(f"❌ Error getting pairs: {e}")
    
    # Test account balance
    print("\n💰 Testing Account Balance:")
    try:
        balance = client.get_account_balance()
        print(f"✅ Balance keys: {list(balance.keys()) if isinstance(balance, dict) else 'Not a dict'}")
        if isinstance(balance, dict):
            for currency, amount in balance.items():
                if float(amount) > 0:
                    print(f"   {currency}: {amount}")
    except Exception as e:
        print(f"❌ Error getting balance: {e}")


if __name__ == "__main__":
    debug_market_data()