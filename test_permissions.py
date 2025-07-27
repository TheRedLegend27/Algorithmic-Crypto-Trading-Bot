#!/usr/bin/env python3
"""
Simple test to check API key permissions.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

def test_permissions():
    load_dotenv()
    
    print("🔐 Coinbase API Key Permissions Test")
    print("=" * 40)
    
    api_key = os.getenv("COINBASE_ADVANCED_API_KEY")
    private_key = os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("❌ Missing credentials")
        return
    
    # Clean up private key
    private_key = private_key.replace('\\n', '\n')
    
    # Generate JWT token
    header = {'alg': 'ES256', 'kid': api_key, 'typ': 'JWT'}
    now = int(time.time())
    payload = {
        'sub': api_key,
        'iss': 'coinbase-cloud',
        'nbf': now,
        'exp': now + 120,
        'aud': ['retail_rest_api_proxy']
    }
    
    try:
        token = jwt.encode(payload, private_key, algorithm='ES256', headers=header)
        print("✅ JWT token generated")
    except Exception as e:
        print(f"❌ JWT generation failed: {e}")
        return
    
    # Test endpoints
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    tests = [
        ("Public Market Data", "https://api.coinbase.com/api/v3/brokerage/market/products", "Should work with any key"),
        ("Private Accounts", "https://api.coinbase.com/api/v3/brokerage/accounts", "Requires 'View' permission"),
        ("Private Orders", "https://api.coinbase.com/api/v3/brokerage/orders/historical/batch", "Requires 'View' permission"),
    ]
    
    print(f"\n🧪 Testing API Key Permissions:")
    print(f"   Key: ...{api_key[-20:]}")
    
    for test_name, url, requirement in tests:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"   ✅ {test_name}: WORKING")
            elif response.status_code == 401:
                print(f"   ❌ {test_name}: UNAUTHORIZED - {requirement}")
            else:
                print(f"   ⚠️  {test_name}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ {test_name}: ERROR - {str(e)}")
    
    print(f"\n💡 To fix permission issues:")
    print(f"   1. Go to: https://www.coinbase.com/cloud")
    print(f"   2. Find your API key (ending in ...{api_key[-12:]})")
    print(f"   3. Edit the key and enable these permissions:")
    print(f"      ✅ View (for account info)")
    print(f"      ✅ Trade (for placing orders)")
    print(f"      ✅ Transfer (optional)")
    print(f"   4. Save changes and test again")

if __name__ == "__main__":
    test_permissions()