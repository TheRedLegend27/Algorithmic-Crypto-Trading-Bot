#!/usr/bin/env python3
"""
Comprehensive diagnosis of Coinbase API access.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

def generate_jwt_token(api_key, private_key_raw):
    """Generate JWT token with Ed25519 support."""
    # Handle escaped newlines in private key from .env file
    private_key_raw = private_key_raw.replace('\\n', '\n')
    
    # Determine key type and algorithm
    if 'BEGIN EC PRIVATE KEY' in private_key_raw:
        algorithm = 'ES256'
        private_key = private_key_raw
    elif 'BEGIN PRIVATE KEY' in private_key_raw:
        algorithm = 'EdDSA'
        private_key = private_key_raw
    else:
        # Try base64 Ed25519
        try:
            import base64
            decoded = base64.b64decode(private_key_raw)
            
            if len(decoded) == 32:
                algorithm = 'EdDSA'
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric import ed25519
                ed25519_key = ed25519.Ed25519PrivateKey.from_private_bytes(decoded)
                private_key = ed25519_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')
            elif len(decoded) == 64:
                algorithm = 'EdDSA'
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric import ed25519
                ed25519_key = ed25519.Ed25519PrivateKey.from_private_bytes(decoded[:32])
                private_key = ed25519_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')
            else:
                raise ValueError("Invalid key length")
        except:
            algorithm = 'ES256'
            private_key = private_key_raw
    
    header = {
        'alg': algorithm,
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
    
    return jwt.encode(payload, private_key, algorithm=algorithm, headers=header)

def test_endpoint(url, token, is_public=False):
    """Test endpoint and return detailed info."""
    headers = {
        'Content-Type': 'application/json'
    }
    
    if not is_public:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return {
            'url': url,
            'status': response.status_code,
            'success': response.status_code == 200,
            'response': response.json() if response.status_code == 200 else response.text[:200]
        }
    except Exception as e:
        return {
            'url': url,
            'status': 'ERROR',
            'success': False,
            'response': str(e)
        }

def main():
    load_dotenv()
    
    api_key = os.getenv("COINBASE_API_KEY")
    private_key = os.getenv("COINBASE_API_SECRET")
    
    print("🔍 Comprehensive Coinbase API Diagnosis")
    print("=" * 50)
    print(f"API Key: {api_key}")
    print(f"Key Type: {'UUID format (Consumer/Cloud API)' if len(api_key.split('-')) == 5 else 'Advanced Trade API'}")
    
    # Generate JWT token
    try:
        token = generate_jwt_token(api_key, private_key)
        print("✅ JWT token generated successfully")
    except Exception as e:
        print(f"❌ JWT generation failed: {e}")
        return
    
    # Test different endpoint categories
    test_categories = {
        "Public Endpoints (No Auth)": [
            ("https://api.coinbase.com/v2/exchange-rates", True),
            ("https://api.coinbase.com/v2/currencies", True),
            ("https://api.coinbase.com/v2/time", True),
        ],
        "Consumer API v2 (Private)": [
            ("https://api.coinbase.com/v2/user", False),
            ("https://api.coinbase.com/v2/accounts", False),
            ("https://api.coinbase.com/v2/transactions", False),
        ],
        "Advanced Trade API v3 (Private)": [
            ("https://api.coinbase.com/api/v3/brokerage/accounts", False),
            ("https://api.coinbase.com/api/v3/brokerage/products", False),
            ("https://api.coinbase.com/api/v3/brokerage/orders/historical/batch", False),
        ],
        "Cloud Trading API": [
            ("https://api.coinbase.com/api/v1/accounts", False),
            ("https://api.coinbase.com/api/v1/products", False),
        ]
    }
    
    results = {}
    
    for category, endpoints in test_categories.items():
        print(f"\n📂 {category}")
        print("-" * 40)
        
        category_results = []
        for url, is_public in endpoints:
            result = test_endpoint(url, token, is_public)
            category_results.append(result)
            
            status_icon = "✅" if result['success'] else "❌"
            print(f"{status_icon} {result['url']}")
            print(f"   Status: {result['status']}")
            if result['success']:
                response_preview = str(result['response'])[:100] + "..." if len(str(result['response'])) > 100 else str(result['response'])
                print(f"   Response: {response_preview}")
            else:
                print(f"   Error: {result['response']}")
        
        results[category] = category_results
    
    # Summary
    print(f"\n📊 SUMMARY")
    print("=" * 50)
    
    for category, category_results in results.items():
        successful = sum(1 for r in category_results if r['success'])
        total = len(category_results)
        print(f"{category}: {successful}/{total} endpoints working")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print("=" * 50)
    
    public_working = sum(1 for r in results["Public Endpoints (No Auth)"] if r['success'])
    consumer_working = sum(1 for r in results["Consumer API v2 (Private)"] if r['success'])
    advanced_working = sum(1 for r in results["Advanced Trade API v3 (Private)"] if r['success'])
    
    if public_working > 0 and consumer_working == 0 and advanced_working == 0:
        print("🔍 Your API key appears to only work with public endpoints.")
        print("   This suggests you might have a read-only or public API key.")
        print("   For trading, you need a key with trading permissions.")
    elif consumer_working > 0:
        print("✅ Your API key works with Consumer API v2.")
        print("   This is good for wallet operations but limited for trading.")
        print("   Consider upgrading to Advanced Trade API for full trading features.")
    elif advanced_working > 0:
        print("✅ Your API key works with Advanced Trade API v3.")
        print("   This is perfect for trading operations!")
    else:
        print("❌ Your API key doesn't seem to work with any private endpoints.")
        print("   Please check your API key permissions in Coinbase Developer Platform.")

if __name__ == "__main__":
    main()