#!/usr/bin/env python3
"""
Test different Coinbase API endpoints to determine the correct one.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

# Add the bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

def generate_jwt_token(api_key, private_key):
    """Generate JWT token."""
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
        'aud': ['public_websocket_api']
    }
    
    private_key_processed = private_key.replace('\\n', '\n')
    return jwt.encode(payload, private_key_processed, algorithm='ES256', headers=header)

def test_endpoint(base_url, endpoint, token):
    """Test a specific endpoint."""
    url = f"{base_url}{endpoint}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"  {url}")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Success: {len(data) if isinstance(data, list) else 'OK'}")
        else:
            print(f"  Error: {response.text[:100]}")
        return response.status_code == 200
    except Exception as e:
        print(f"  Exception: {str(e)}")
        return False

def main():
    load_dotenv()
    
    api_key = os.getenv("COINBASE_API_KEY")
    private_key = os.getenv("COINBASE_API_SECRET")
    
    print("🔐 Testing Coinbase API endpoints...")
    print(f"API Key: {api_key}")
    
    # Generate JWT token
    try:
        token = generate_jwt_token(api_key, private_key)
        print("✅ JWT token generated successfully")
    except Exception as e:
        print(f"❌ JWT generation failed: {e}")
        return
    
    # Test different base URLs and endpoints
    test_configs = [
        # Advanced Trade API
        ("https://api.coinbase.com", "/api/v3/brokerage/accounts"),
        ("https://api.coinbase.com", "/api/v3/brokerage/products"),
        
        # Cloud Trading API
        ("https://api.cloud.coinbase.com", "/v1/accounts"),
        ("https://api.cloud.coinbase.com", "/v1/products"),
        
        # Alternative endpoints
        ("https://api.coinbase.com", "/v2/accounts"),
        ("https://api.coinbase.com", "/v2/exchange-rates"),
    ]
    
    print("\n🧪 Testing endpoints...")
    for base_url, endpoint in test_configs:
        print(f"\n📍 Testing {base_url}{endpoint}")
        success = test_endpoint(base_url, endpoint, token)
        if success:
            print("  ✅ SUCCESS!")
        else:
            print("  ❌ Failed")

if __name__ == "__main__":
    main()