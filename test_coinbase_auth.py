#!/usr/bin/env python3
"""
Test script to help set up Coinbase Advanced Trade API authentication.
This script will help you verify your API credentials are working correctly.
"""
import os
import sys
from dotenv import load_dotenv

# Add the bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.config import Config, CoinbaseCredentials
from bot.coinbase_client import CoinbaseClient

def test_coinbase_auth():
    """Test Coinbase API authentication."""
    print("🔐 Testing Coinbase Advanced Trade API Authentication")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Check if credentials are set
    api_key = os.getenv("COINBASE_API_KEY")
    api_secret = os.getenv("COINBASE_API_SECRET")
    sandbox = os.getenv("COINBASE_SANDBOX", "True").lower() in ("true", "1", "t")
    
    if not api_key or not api_secret:
        print("❌ ERROR: Missing Coinbase API credentials!")
        print("\nPlease set the following in your .env file:")
        print("COINBASE_API_KEY=your_api_key_here")
        print("COINBASE_API_SECRET=your_private_key_here")
        print("COINBASE_SANDBOX=True")
        print("\nNote: COINBASE_API_SECRET should be your private key (starts with -----BEGIN EC PRIVATE KEY-----)")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...")
    print(f"✅ API Secret found: {'Yes' if api_secret else 'No'}")
    print(f"✅ Sandbox mode: {sandbox}")
    
    # Create credentials
    try:
        credentials = CoinbaseCredentials(
            api_key=api_key,
            api_secret=api_secret,
            sandbox=sandbox
        )
        print(f"✅ Credentials created successfully")
        print(f"   Base URL: {credentials.base_url}")
    except Exception as e:
        print(f"❌ ERROR creating credentials: {str(e)}")
        return False
    
    # Test API client
    try:
        client = CoinbaseClient(credentials)
        print("✅ Coinbase client created successfully")
    except Exception as e:
        print(f"❌ ERROR creating client: {str(e)}")
        return False
    
    # Test authentication
    print("\n🔍 Testing API authentication...")
    try:
        if client.test_authentication():
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed!")
            return False
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        print("\nCommon issues:")
        print("1. Make sure your API key is correct")
        print("2. Make sure your private key is in the correct format (PEM)")
        print("3. Check that your API key has the required permissions")
        print("4. Verify you're using the correct sandbox/production settings")
        return False
    
    # Test getting accounts
    print("\n📊 Testing account access...")
    try:
        accounts = client.get_accounts()
        print(f"✅ Successfully retrieved {len(accounts)} accounts")
        for account in accounts[:3]:  # Show first 3 accounts
            currency = account.get('currency', 'Unknown')
            balance = account.get('available_balance', {}).get('value', '0')
            print(f"   - {currency}: {balance}")
    except Exception as e:
        print(f"❌ Error getting accounts: {str(e)}")
        return False
    
    # Test getting products
    print("\n🏪 Testing market data access...")
    try:
        products = client.get_products()
        print(f"✅ Successfully retrieved {len(products)} trading products")
        
        # Find BTC-USD
        btc_usd = next((p for p in products if p.get('product_id') == 'BTC-USD'), None)
        if btc_usd:
            print(f"   - BTC-USD found: {btc_usd.get('status', 'Unknown status')}")
        else:
            print("   - BTC-USD not found in products")
    except Exception as e:
        print(f"❌ Error getting products: {str(e)}")
        return False
    
    print("\n🎉 All tests passed! Your Coinbase API setup is working correctly.")
    return True

if __name__ == "__main__":
    success = test_coinbase_auth()
    sys.exit(0 if success else 1)