#!/usr/bin/env python3
"""
Debug Alpaca authentication issues.
"""
import os
import requests
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

def test_direct_api_call():
    """Test direct API call to Alpaca."""
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    
    print("🔍 Direct API Test")
    print(f"API Key: {api_key}")
    print(f"Secret Key: {secret_key[:8]}..." if secret_key else "No Secret Key")
    print(f"Base URL: {base_url}")
    
    # Test direct HTTP request
    headers = {
        'APCA-API-KEY-ID': api_key,
        'APCA-API-SECRET-KEY': secret_key,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(f"{base_url}/v2/account", headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Direct API call successful!")
            return True
        else:
            print("❌ Direct API call failed")
            return False
            
    except Exception as e:
        print(f"❌ Direct API call error: {str(e)}")
        return False

def test_sdk_with_debug():
    """Test SDK with more debug info."""
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    
    print("\n🔍 SDK Test with Debug")
    
    # Validate key formats
    if not api_key or not api_key.startswith('PK'):
        print("❌ API Key should start with 'PK' for paper trading")
        return False
        
    if not secret_key or len(secret_key) < 40:
        print("❌ Secret key seems too short")
        return False
    
    try:
        # Try with explicit paper=True
        client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=True
        )
        
        print("✅ Client created successfully")
        
        # Try to get account
        account = client.get_account()
        print("✅ Account retrieved successfully!")
        print(f"Account ID: {account.id}")
        print(f"Status: {account.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ SDK test failed: {str(e)}")
        
        # Try to get more details from the error
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        
        return False

if __name__ == "__main__":
    print("🚀 Alpaca Authentication Debug")
    print("=" * 40)
    
    # Test direct API call first
    if test_direct_api_call():
        print("\n" + "=" * 40)
        test_sdk_with_debug()
    else:
        print("\n" + "=" * 40)
        test_sdk_with_debug()