#!/usr/bin/env python3
"""
Test Yahoo Finance data fetcher.
"""
from bot.yahoo_data_fetcher import YahooDataFetcher

def test_yahoo_data():
    """Test Yahoo Finance data fetching."""
    
    fetcher = YahooDataFetcher()
    
    print("🔍 Testing Yahoo Finance Data Fetcher")
    print("=" * 50)
    
    # Test crypto symbols
    crypto_symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
    
    for symbol in crypto_symbols:
        print(f"\n📊 Testing {symbol}...")
        
        # Test 5-minute data
        data = fetcher.fetch_crypto_data(symbol, timeframe="5Min", limit=50)
        
        if data is not None and not data.empty:
            print(f"✅ {symbol}: {len(data)} data points")
            print(f"   Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
            print(f"   Latest price: ${data['close'].iloc[-1]:.2f}")
            print(f"   Data columns: {list(data.columns)}")
            
            # Test current price
            current_price = fetcher.get_current_price(symbol)
            if current_price:
                print(f"   Current price: ${current_price:.2f}")
            
            # Show sample data
            print(f"   Sample data:")
            print(data.tail(3).to_string())
            
        else:
            print(f"❌ {symbol}: No data available")
    
    print("\n" + "=" * 50)
    print("Yahoo Finance test complete!")

if __name__ == "__main__":
    test_yahoo_data()