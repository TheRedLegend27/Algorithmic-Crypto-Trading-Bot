#!/usr/bin/env python3
"""
Test the working endpoint to understand the API structure.
"""
import os
import sys
import time
import jwt
import requests
from dotenv import load_dotenv

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

def test_endpoint_detailed(url, token):
    """Test endpoint with detailed response."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
        else:
            print(f"Error Response: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def main():
    load_dotenv()
    
    api_key = os.getenv("COINBASE_API_KEY")
    private_key = os.getenv("COINBASE_API_SECRET")
    
    print("🔐 Testing working Coinbase endpoint...")
    
    # Generate JWT token
    token = generate_jwt_token(api_key, private_key)
    
    # Test the working endpoint
    print("\n📍 Testing working endpoint:")
    test_endpoint_detailed("https://api.coinbase.com/v2/exchange-rates", token)
    
    # Test some other v2 endpoints
    print("\n📍 Testing other v2 endpoints:")
    v2_endpoints = [
        "/v2/currencies",
        "/v2/time",
        "/v2/user",
        "/v2/accounts",
        "/v2/payment-methods"
    ]
    
    for endpoint in v2_endpoints:
        print(f"\n--- Testing {endpoint} ---")
        test_endpoint_detailed(f"https://api.coinbase.com{endpoint}", token)

if __name__ == "__main__":
    main()