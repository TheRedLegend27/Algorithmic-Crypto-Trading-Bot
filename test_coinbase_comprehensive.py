#!/usr/bin/env python3
"""
Comprehensive test of different Coinbase API approaches.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

def generate_jwt_token(api_key, private_key, audience=None, uri=None):
    """Generate JWT token with different parameter combinations."""
    private_key = private_key.replace('\\n', '\n')
    
    header = {
        'alg': 'ES256',
        'kid': api_key,
        'typ': 'JWT'
    }
    
    now = int(time.time())
    payload = {
        'sub': api_key,
        'iss': 'coinbase-cloud',
        'nbf': now,
        'exp': now + 120,
    }
    
    # Try different audience configurations
    if audience:
        payload['aud'] = [audience]
    
    # Try adding URI if provided
    if uri:
        payload['uri'] = uri
    
    try:
        token = jwt.encode(payload, private_key, algorithm='ES256', headers=header)
        return token
    except Exception as e:
        print(f"❌ JWT generation failed: {e}")
        return None

def test_endpoint_with_token(url, token, description):
    """Test endpoint with given token."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   {description}: Status {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"      ✅ Success: Got {len(str(data))} chars of data")
                return True
            except:
                print(f"      ✅ Success: {response.text[:100]}...")
                return True
        else:
            try:
                error_data = response.json()
                print(f"      ❌ Error: {error_data}")
            except:
                print(f"      ❌ Error: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"      ❌ Exception: {e}")
        return False

def main():
    load_dotenv()
    
    print("🔬 Comprehensive Coinbase API Test")
    print("=" * 50)
    
    api_key = os.getenv("COINBASE_ADVANCED_API_KEY")
    private_key = os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("❌ Missing credentials")
        return
    
    print(f"🔑 API Key: {api_key}")
    
    # Test different JWT configurations
    test_configs = [
        # (audience, uri, description)
        (None, None, "No audience/URI"),
        ('retail_rest_api_proxy', None, "retail_rest_api_proxy audience"),
        ('public_websocket_api', None, "public_websocket_api audience"),
        (None, 'GET /api/v3/brokerage/accounts', "URI-based auth"),
        ('retail_rest_api_proxy', 'GET /api/v3/brokerage/accounts', "Both audience and URI"),
    ]
    
    test_url = "https://api.coinbase.com/api/v3/brokerage/accounts"
    
    print(f"\n🧪 Testing different JWT configurations:")
    
    for audience, uri, description in test_configs:
        print(f"\n--- {description} ---")
        
        token = generate_jwt_token(api_key, private_key, audience, uri)
        if token:
            print(f"✅ JWT generated")
            test_endpoint_with_token(test_url, token, "Accounts endpoint")
        else:
            print(f"❌ JWT generation failed")
    
    # Also test some alternative endpoints
    print(f"\n🔍 Testing alternative endpoints with basic JWT:")
    
    basic_token = generate_jwt_token(api_key, private_key, 'retail_rest_api_proxy')
    if basic_token:
        alternative_endpoints = [
            ("https://api.coinbase.com/api/v3/brokerage/accounts", "v3 Accounts"),
            ("https://api.coinbase.com/v2/accounts", "v2 Accounts"),
            ("https://api.coinbase.com/v2/user", "v2 User"),
            ("https://api.coinbase.com/api/v3/brokerage/portfolios", "v3 Portfolios"),
        ]
        
        for url, desc in alternative_endpoints:
            test_endpoint_with_token(url, basic_token, desc)
    
    print(f"\n💡 If none of these work, the issue might be:")
    print(f"   1. Permission changes haven't propagated yet (wait 5-10 minutes)")
    print(f"   2. API key was created for a different Coinbase product")
    print(f"   3. Account verification issues")
    print(f"   4. Regional restrictions")

if __name__ == "__main__":
    main()