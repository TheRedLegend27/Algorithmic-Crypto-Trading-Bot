#!/usr/bin/env python3
"""
Debug script to test market data retrieval from Kraken API.
"""
import os
import sys
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.utils import log_info, log_error


def debug_market_data():
    """Debug market data retrieval."""
    print("🔍 Debugging Market Data Retrieval")
    print("=" * 50)
    
    # Load credentials
    load_dotenv()
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ API credentials not found")
        return False
    
    credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
    
    # Test KrakenClient directly
    print("\n1. Testing KrakenClient directly...")
    try:
        client = KrakenClient(credentials)
        
        # Test server time (public endpoint)
        server_time = client.get_server_time()
        print(f"✅ Server time: {server_time}")
        
        # Test ticker data
        print("\n2. Testing ticker data...")
        ticker_data = client.get_ticker(["XBTUSD"])
        print(f"Ticker response: {ticker_data}")
        
        if ticker_data and "XBTUSD" in ticker_data:
            price_data = ticker_data["XBTUSD"]
            print(f"Price data: {price_data}")
            
            if 'c' in price_data:
                current_price = float(price_data['c'][0])
                print(f"✅ Current BTC/USD price: ${current_price:,.2f}")
            else:
                print("❌ No 'c' field in price data")
        else:
            print("❌ No XBTUSD data in ticker response")
        
        # Test get_current_price method
        print("\n3. Testing get_current_price method...")
        price = client.get_current_price("XBTUSD")
        if price:
            print(f"✅ get_current_price: ${price:,.2f}")
        else:
            print("❌ get_current_price returned None")
        
    except Exception as e:
        print(f"❌ KrakenClient test failed: {e}")
        return False
    
    # Test KrakenTrader
    print("\n4. Testing KrakenTrader...")
    try:
        config = KrakenTradingConfig(
            trading_pair="XBTUSD",
            trade_amount_usd=10.0,
            max_position_usd=100.0,
            min_trade_interval=60
        )
        trader = KrakenTrader(credentials, config)
        
        # Test connection
        if trader.test_connection():
            print("✅ KrakenTrader connection test passed")
        else:
            print("❌ KrakenTrader connection test failed")
            return False
        
        # Test get_current_price
        price = trader.get_current_price("XBTUSD")
        if price:
            print(f"✅ KrakenTrader get_current_price: ${price:,.2f}")
        else:
            print("❌ KrakenTrader get_current_price returned None")
            return False
        
    except Exception as e:
        print(f"❌ KrakenTrader test failed: {e}")
        return False
    
    # Test other pairs
    print("\n5. Testing other trading pairs...")
    test_pairs = ["XBTUSD", "XETHZUSD", "ADAUSD"]
    
    for pair in test_pairs:
        try:
            price = client.get_current_price(pair)
            if price:
                print(f"✅ {pair}: ${price:,.2f}")
            else:
                print(f"❌ {pair}: No price data")
        except Exception as e:
            print(f"❌ {pair}: Error - {e}")
    
    print("\n✅ Market data debugging complete!")
    return True


def main():
    """Main function."""
    if debug_market_data():
        print("\n🎉 Market data is working correctly!")
        return 0
    else:
        print("\n❌ Market data issues detected")
        return 1


if __name__ == "__main__":
    sys.exit(main())