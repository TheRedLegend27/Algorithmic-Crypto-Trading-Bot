#!/usr/bin/env python3
"""
Simple direct HTTP test for Alpaca API.
"""
import os
import requests
import base64
from dotenv import load_dotenv

def test_alpaca_direct():
    """Test Alpaca API with direct HTTP requests."""
    
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL")
    
    print("🔍 Direct Alpaca API Test")
    print("=" * 30)
    print(f"API Key: {api_key}")
    print(f"Secret Key: {secret_key[:8]}...")
    print(f"Base URL: {base_url}")
    
    # Create basic auth header
    credentials = f"{api_key}:{secret_key}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Accept': 'application/json'
    }
    
    print(f"\nAuth Header: Basic {encoded_credentials[:20]}...")
    
    # Test account endpoint
    try:
        print("\n📊 Testing /v2/account endpoint...")
        response = requests.get(f"{base_url}/v2/account", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ SUCCESS!")
            account_data = response.json()
            print(f"Account ID: {account_data.get('id')}")
            print(f"Status: {account_data.get('status')}")
            print(f"Cash: ${account_data.get('cash')}")
            print(f"Buying Power: ${account_data.get('buying_power')}")
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Try different auth method
            print("\n🔄 Trying alternative auth method...")
            alt_headers = {
                'APCA-API-KEY-ID': api_key,
                'APCA-API-SECRET-KEY': secret_key,
                'Accept': 'application/json'
            }
            
            alt_response = requests.get(f"{base_url}/v2/account", headers=alt_headers)
            print(f"Alternative auth status: {alt_response.status_code}")
            
            if alt_response.status_code == 200:
                print("✅ Alternative auth worked!")
                account_data = alt_response.json()
                print(f"Account ID: {account_data.get('id')}")
                print(f"Status: {account_data.get('status')}")
                print(f"Cash: ${account_data.get('cash')}")
                return True
            else:
                print(f"❌ Alternative auth also failed: {alt_response.text}")
            
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

if __name__ == "__main__":
    test_alpaca_direct()