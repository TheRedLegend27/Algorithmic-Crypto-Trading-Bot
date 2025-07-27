#!/usr/bin/env python3
"""
Test different JWT payload formats for Coinbase.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

def test_jwt_format(api_key, private_key, payload_format, description):
    """Test a specific JWT payload format."""
    print(f"\n🧪 Testing: {description}")
    
    private_key = private_key.replace('\\n', '\n')
    
    header = {
        'alg': 'ES256',
        'kid': api_key,
        'typ': 'JWT'
    }
    
    now = int(time.time())
    
    # Different payload formats to try
    if payload_format == "standard":
        payload = {
            'sub': api_key,
            'iss': 'coinbase-cloud',
            'nbf': now,
            'exp': now + 120,
            'aud': ['retail_rest_api_proxy']
        }
    elif payload_format == "minimal":
        payload = {
            'sub': api_key,
            'iss': 'coinbase-cloud',
            'exp': now + 120
        }
    elif payload_format == "with_iat":
        payload = {
            'sub': api_key,
            'iss': 'coinbase-cloud',
            'iat': now,
            'nbf': now,
            'exp': now + 120,
            'aud': ['retail_rest_api_proxy']
        }
    elif payload_format == "no_audience":
        payload = {
            'sub': api_key,
            'iss': 'coinbase-cloud',
            'nbf': now,
            'exp': now + 120
        }
    elif payload_format == "short_exp":
        payload = {
            'sub': api_key,
            'iss': 'coinbase-cloud',
            'nbf': now,
            'exp': now + 60,  # 1 minute instead of 2
            'aud': ['retail_rest_api_proxy']
        }
    
    print(f"   Payload: {payload}")
    
    try:
        token = jwt.encode(payload, private_key, algorithm='ES256', headers=header)
        print(f"   ✅ JWT generated")
        
        # Test the token
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = "https://api.coinbase.com/api/v3/brokerage/accounts"
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ SUCCESS!")
            return True
        else:
            try:
                error_data = response.json()
                print(f"   ❌ Error: {error_data}")
            except:
                print(f"   ❌ Error: {response.text[:100]}")
            return False
            
    except Exception as e:
        print(f"   ❌ JWT generation failed: {e}")
        return False

def main():
    load_dotenv()
    
    print("🔬 JWT Format Testing for Coinbase")
    print("=" * 40)
    
    api_key = os.getenv("COINBASE_ADVANCED_API_KEY")
    private_key = os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("❌ Missing credentials")
        return
    
    # Test different JWT formats
    formats_to_test = [
        ("standard", "Standard format with audience"),
        ("minimal", "Minimal payload"),
        ("with_iat", "With issued-at time"),
        ("no_audience", "No audience claim"),
        ("short_exp", "Shorter expiration"),
    ]
    
    success_count = 0
    for format_name, description in formats_to_test:
        if test_jwt_format(api_key, private_key, format_name, description):
            success_count += 1
            break  # Stop on first success
    
    if success_count == 0:
        print(f"\n❌ None of the JWT formats worked")
        print(f"💡 This suggests either:")
        print(f"   1. Permission changes are still propagating (wait 5-10 minutes)")
        print(f"   2. There's an account-level issue")
        print(f"   3. The API key was created for wrong product/environment")
        
        # Wait and retry suggestion
        print(f"\n⏰ Try waiting 5 minutes and running this again:")
        print(f"   python3 test_jwt_formats.py")
    else:
        print(f"\n✅ Found working JWT format!")

if __name__ == "__main__":
    main()