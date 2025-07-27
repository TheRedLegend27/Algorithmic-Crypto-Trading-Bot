#!/usr/bin/env python3
"""
Test script for the new Coinbase Advanced Trade API implementation.
"""
import os
import sys
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.coinbase_advanced_client import CoinbaseAdvancedClient, AdvancedTradeCredentials
from bot.coinbase_advanced_trader import CoinbaseAdvancedTrader, TradingConfig


def test_advanced_api():
    """Test the new Advanced Trade API implementation."""
    print("🚀 Testing Coinbase Advanced Trade API Implementation")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment
    api_key = os.getenv("COINBASE_ADVANCED_API_KEY")
    private_key = os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("❌ Missing Advanced Trade API credentials!")
        print("\nPlease set these in your .env file:")
        print("COINBASE_ADVANCED_API_KEY=organizations/your_org_id/apiKeys/your_key_id")
        print("COINBASE_ADVANCED_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----")
        print("\nTo get these credentials:")
        print("1. Go to https://www.coinbase.com/cloud")
        print("2. Create a new API key with View + Trade permissions")
        print("3. Download the credentials and update your .env file")
        return False
    
    print(f"✅ API Key: {api_key}")
    print(f"✅ Private Key: {'Present' if private_key else 'Missing'}")
    
    # Create credentials
    try:
        credentials = AdvancedTradeCredentials(
            api_key=api_key,
            private_key=private_key
        )
        print("✅ Credentials created")
    except Exception as e:
        print(f"❌ Error creating credentials: {e}")
        return False
    
    # Test client connection
    print("\n🔗 Testing API Connection...")
    try:
        client = CoinbaseAdvancedClient(credentials)
        if client.test_connection():
            print("✅ API connection successful!")
        else:
            print("❌ API connection failed!")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    # Test getting accounts
    print("\n💰 Testing Account Access...")
    try:
        accounts = client.get_accounts()
        print(f"✅ Retrieved {len(accounts)} accounts")
        
        for account in accounts[:5]:  # Show first 5
            currency = account.get('currency', 'Unknown')
            available = account.get('available_balance', {}).get('value', '0')
            print(f"   - {currency}: {available} available")
            
    except Exception as e:
        print(f"❌ Error getting accounts: {e}")
        return False
    
    # Test getting products
    print("\n📈 Testing Market Data...")
    try:
        products = client.get_products()
        print(f"✅ Retrieved {len(products)} products")
        
        # Find BTC-USD
        btc_usd = next((p for p in products if p.get('product_id') == 'BTC-USD'), None)
        if btc_usd:
            print(f"   - BTC-USD: {btc_usd.get('status', 'Unknown')} status")
            
            # Get current price
            try:
                btc_data = client.get_product('BTC-USD')
                price = btc_data.get('price', 'N/A')
                print(f"   - Current BTC price: ${price}")
            except Exception as e:
                print(f"   - Could not get BTC price: {e}")
        else:
            print("   - BTC-USD not found")
            
    except Exception as e:
        print(f"❌ Error getting market data: {e}")
        return False
    
    # Test trader initialization
    print("\n🤖 Testing Trader...")
    try:
        config = TradingConfig(
            product_id="BTC-USD",
            trade_amount_usd=10.0,  # Small test amount
            max_position_usd=50.0
        )
        
        trader = CoinbaseAdvancedTrader(credentials, config)
        
        if trader.test_connection():
            print("✅ Trader initialized successfully!")
        else:
            print("❌ Trader connection test failed!")
            return False
            
        # Get portfolio summary
        portfolio = trader.get_portfolio_summary()
        if portfolio:
            print("✅ Portfolio summary retrieved:")
            print(f"   - Product: {portfolio.get('product_id', 'N/A')}")
            print(f"   - Current Price: ${portfolio.get('current_price', 0):.2f}")
            print(f"   - Total Value: ${portfolio.get('total_portfolio_value', 0):.2f}")
        else:
            print("❌ Could not get portfolio summary")
            
    except Exception as e:
        print(f"❌ Error testing trader: {e}")
        return False
    
    print("\n🎉 All tests passed! Your Advanced Trade API setup is working!")
    print("\nNext steps:")
    print("1. Update your main bot to use the new CoinbaseAdvancedTrader")
    print("2. Test with small amounts first")
    print("3. Monitor logs for any issues")
    
    return True


if __name__ == "__main__":
    success = test_advanced_api()
    sys.exit(0 if success else 1)