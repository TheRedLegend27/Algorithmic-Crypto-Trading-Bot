#!/usr/bin/env python3
"""
Test different JWT configurations for Coinbase Advanced Trade API.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

def generate_jwt_token(api_key, private_key, aud_value):
    """Generate JWT token with specific audience."""
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
        'aud': aud_value
    }
    
    private_key_processed = private_key.replace('\\n', '\n')
    return jwt.encode(payload, private_key_processed, algorithm='ES256', headers=header)

def test_endpoint_with_token(url, token):
    """Test endpoint with specific token."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return {
            'status': response.status_code,
            'success': response.status_code == 200,
            'response': response.json() if response.status_code == 200 else response.text[:100]
        }
    except Exception as e:
        return {
            'status': 'ERROR',
            'success': False,
            'response': str(e)
        }

def main():
    load_dotenv()
    
    api_key = os.getenv("COINBASE_API_KEY")
    private_key = os.getenv("COINBASE_API_SECRET")
    
    print("🧪 Testing different JWT configurations for Advanced Trade API")
    print("=" * 60)
    print(f"API Key: {api_key}")
    
    # Different audience values to try
    audience_variations = [
        ['public_websocket_api'],
        ['retail_rest_api_proxy'],
        ['coinbase-cloud'],
        ['advanced_trade_api'],
        ['api.coinbase.com'],
        [],  # Empty audience
    ]
    
    test_url = "https://api.coinbase.com/api/v3/brokerage/accounts"
    
    for i, aud in enumerate(audience_variations, 1):
        print(f"\n🔍 Test {i}: Audience = {aud}")
        print("-" * 40)
        
        try:
            token = generate_jwt_token(api_key, private_key, aud)
            result = test_endpoint_with_token(test_url, token)
            
            status_icon = "✅" if result['success'] else "❌"
            print(f"{status_icon} Status: {result['status']}")
            
            if result['success']:
                print(f"   SUCCESS! This audience works!")
                print(f"   Response preview: {str(result['response'])[:100]}...")
                break
            else:
                print(f"   Error: {result['response']}")
                
        except Exception as e:
            print(f"❌ JWT generation failed: {e}")
    
    # Also test without JWT (public endpoint)
    print(f"\n🔍 Test Public: No JWT token")
    print("-" * 40)
    public_url = "https://api.coinbase.com/v2/time"
    try:
        response = requests.get(public_url, timeout=10)
        if response.status_code == 200:
            print("✅ Public endpoint works (confirms network/API is accessible)")
        else:
            print(f"❌ Even public endpoint fails: {response.status_code}")
    except Exception as e:
        print(f"❌ Network error: {e}")

if __name__ == "__main__":
    main()