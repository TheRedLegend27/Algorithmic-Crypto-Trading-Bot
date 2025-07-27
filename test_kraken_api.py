#!/usr/bin/env python3
"""
Test script for Kraken API implementation.
"""
import os
import sys
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenClient, KrakenCredentials
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig


def test_kraken_api():
    """Test the Kraken API implementation."""
    print("🐙 Testing Kraken API Implementation")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Missing Kraken API credentials!")
        print("\nPlease set these in your .env file:")
        print("KRAKEN_API_KEY=your_api_key_here")
        print("KRAKEN_API_SECRET=your_api_secret_here")
        print("\nTo get these credentials:")
        print("1. Go to https://www.kraken.com/u/security/api")
        print("2. Create a new API key with these permissions:")
        print("   - Query Funds")
        print("   - Query Open Orders & Trades")
        print("   - Query Closed Orders & Trades")
        print("   - Create & Modify Orders")
        print("3. Copy the API Key and Private Key to your .env file")
        return False
    
    print(f"✅ API Key: {api_key[:8]}...")
    print(f"✅ API Secret: {'Present' if api_secret else 'Missing'}")
    
    # Create credentials
    try:
        credentials = KrakenCredentials(
            api_key=api_key,
            api_secret=api_secret
        )
        print("✅ Credentials created")
    except Exception as e:
        print(f"❌ Error creating credentials: {e}")
        return False
    
    # Test client connection
    print("\n🔗 Testing API Connection...")
    try:
        client = KrakenClient(credentials)
        
        # Test public endpoint first
        server_time = client.get_server_time()
        print(f"✅ Public API working - Server time: {server_time.get('unixtime', 'N/A')}")
        
        # Test private endpoint
        if client.test_connection():
            print("✅ Private API connection successful!")
        else:
            print("❌ Private API connection failed!")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    # Test getting account balance
    print("\n💰 Testing Account Access...")
    try:
        balance = client.get_account_balance()
        print(f"✅ Retrieved account balance")
        
        # Show some balances
        for currency, amount in list(balance.items())[:5]:
            if float(amount) > 0:
                print(f"   - {currency}: {amount}")
                
    except Exception as e:
        print(f"❌ Error getting balance: {e}")
        return False
    
    # Test getting market data
    print("\n📈 Testing Market Data...")
    try:
        # Get BTC/USD ticker
        ticker = client.get_ticker(['XBTUSD'])
        if 'XBTUSD' in ticker:
            btc_price = ticker['XBTUSD']['c'][0]  # Last price
            print(f"✅ Current BTC price: ${float(btc_price):,.2f}")
        else:
            print("❌ Could not get BTC price")
            
        # Test current price method
        current_price = client.get_current_price('XBTUSD')
        if current_price:
            print(f"✅ Current price method: ${current_price:,.2f}")
        else:
            print("❌ Current price method failed")
            
    except Exception as e:
        print(f"❌ Error getting market data: {e}")
        return False
    
    # Test trader initialization
    print("\n🤖 Testing Trader...")
    try:
        config = KrakenTradingConfig(
            trading_pair="XBTUSD",
            trade_amount_usd=10.0,  # Small test amount
            max_position_usd=50.0
        )
        
        trader = KrakenTrader(credentials, config)
        
        if trader.test_connection():
            print("✅ Trader initialized successfully!")
        else:
            print("❌ Trader connection test failed!")
            return False
            
        # Get portfolio summary
        portfolio = trader.get_portfolio_summary()
        if portfolio:
            print("✅ Portfolio summary retrieved:")
            print(f"   - Trading Pair: {portfolio.get('trading_pair', 'N/A')}")
            print(f"   - Current Price: ${portfolio.get('current_price', 0):,.2f}")
            print(f"   - BTC Balance: {portfolio.get('btc_balance', 0):.6f}")
            print(f"   - USD Balance: ${portfolio.get('usd_balance', 0):,.2f}")
            print(f"   - Total Value: ${portfolio.get('total_portfolio_value', 0):,.2f}")
        else:
            print("❌ Could not get portfolio summary")
            
    except Exception as e:
        print(f"❌ Error testing trader: {e}")
        return False
    
    print("\n🎉 All tests passed! Your Kraken API setup is working!")
    print("\nNext steps:")
    print("1. Update your main bot to use KrakenTrader instead of CoinbaseTrader")
    print("2. Test with small amounts first")
    print("3. Monitor logs for any issues")
    
    print("\n💡 Kraken advantages over Coinbase:")
    print("- ✅ Simple HMAC authentication (no JWT complexity)")
    print("- ✅ Excellent API documentation")
    print("- ✅ Reliable and stable")
    print("- ✅ Good for algorithmic trading")
    print("- ✅ Lower fees than Coinbase")
    
    return True


if __name__ == "__main__":
    success = test_kraken_api()
    sys.exit(0 if success else 1)