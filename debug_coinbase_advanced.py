#!/usr/bin/env python3
"""
Debug script for Coinbase Advanced Trade API issues.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

def generate_jwt_token(api_key, private_key, audience='retail_rest_api_proxy'):
    """Generate JWT token with proper algorithm detection."""
    # Clean up the private key
    private_key = private_key.replace('\\n', '\n')
    
    # Determine algorithm based on key format
    if 'BEGIN EC PRIVATE KEY' in private_key:
        algorithm = 'ES256'
        print(f"✅ Detected ECDSA P-256 key, using {algorithm}")
    elif 'BEGIN PRIVATE KEY' in private_key:
        algorithm = 'EdDSA'  # Assume Ed25519 for PKCS#8 format
        print(f"✅ Detected PKCS#8 key, using {algorithm}")
    else:
        algorithm = 'ES256'  # Default
        print(f"⚠️  Unknown key format, defaulting to {algorithm}")
    
    # JWT header
    header = {
        'alg': algorithm,
        'kid': api_key,
        'typ': 'JWT'
    }
    
    # JWT payload
    now = int(time.time())
    payload = {
        'sub': api_key,
        'iss': 'coinbase-cloud',
        'nbf': now,
        'exp': now + 120,
        'aud': [audience]
    }
    
    print(f"📝 JWT Payload (aud={audience}): {payload}")
    
    try:
        token = jwt.encode(payload, private_key, algorithm=algorithm, headers=header)
        print(f"✅ JWT token generated successfully")
        return token
    except Exception as e:
        print(f"❌ JWT generation failed: {e}")
        return None

def test_endpoint(url, token, description):
    """Test a specific endpoint."""
    print(f"\n🔍 Testing: {description}")
    print(f"   URL: {url}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ Success: {len(str(data))} chars of data")
                return True
            except:
                print(f"   ✅ Success: {response.text[:100]}...")
                return True
        else:
            try:
                error_data = response.json()
                print(f"   ❌ Error: {error_data}")
            except:
                print(f"   ❌ Error: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

def main():
    load_dotenv()
    
    print("🔧 Coinbase Advanced Trade API Debug Tool")
    print("=" * 50)
    
    api_key = os.getenv("COINBASE_ADVANCED_API_KEY")
    private_key = os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("❌ Missing credentials in .env file")
        return
    
    print(f"🔑 API Key: {api_key}")
    print(f"🔑 Private Key: {'Present' if private_key else 'Missing'}")
    
    # Test different audience values
    audiences_to_test = [
        'retail_rest_api_proxy',
        'public_websocket_api', 
        'coinbase_cloud',
        'retail_rest_api'
    ]
    
    base_url = "https://api.coinbase.com"
    test_endpoint_url = f"{base_url}/api/v3/brokerage/accounts"
    
    print(f"\n🧪 Testing different JWT audiences with: {test_endpoint_url}")
    
    best_token = None
    working_audience = None
    
    for audience in audiences_to_test:
        print(f"\n--- Testing audience: {audience} ---")
        token = generate_jwt_token(api_key, private_key, audience)
        if token and test_endpoint(test_endpoint_url, token, f"Accounts with {audience}"):
            best_token = token
            working_audience = audience
            break
    
    if not best_token:
        print(f"\n❌ None of the audience values worked for private endpoints")
        print(f"💡 Your API key might not have the required permissions")
        return
    
    print(f"\n✅ Found working audience: {working_audience}")
    
    # Test other endpoints with the working token
    endpoints_to_test = [
        (f"{base_url}/api/v3/brokerage/accounts", "Advanced Trade - Accounts"),
        (f"{base_url}/api/v3/brokerage/market/products", "Advanced Trade - Products"),
        (f"{base_url}/api/v3/brokerage/orders/historical/batch", "Advanced Trade - Orders"),
    ]
    
    print(f"\n🔍 Testing other endpoints with working audience ({working_audience}):")
    success_count = 0
    for url, description in endpoints_to_test:
        if test_endpoint(url, best_token, description):
            success_count += 1
    
    print(f"\n📊 Final Results: {success_count}/{len(endpoints_to_test)} endpoints working")
    
    if success_count == 0:
        print("\n💡 Troubleshooting suggestions:")
        print("1. Check that your API key has the correct permissions:")
        print("   - Go to https://www.coinbase.com/cloud")
        print("   - Edit your API key")
        print("   - Ensure 'View' and 'Trade' permissions are enabled")
        print("2. Verify your API key is active (not revoked)")
        print("3. Check if you're using the correct Coinbase account")
        print("4. Try creating a new API key with full permissions")

if __name__ == "__main__":
    main()