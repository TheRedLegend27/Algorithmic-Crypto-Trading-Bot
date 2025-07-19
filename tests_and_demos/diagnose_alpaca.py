#!/usr/bin/env python3
"""
Detailed Alpaca API diagnostics to identify the issue.
"""
import os
import requests
from dotenv import load_dotenv

def diagnose_credentials():
    """Diagnose API credentials and account status."""
    
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL")
    
    print("🔍 Alpaca API Diagnostics")
    print("=" * 40)
    
    # Check environment variables
    print(f"API Key: {api_key[:8]}...{api_key[-4:] if api_key else 'None'}")
    print(f"Secret Key: {secret_key[:8]}...{secret_key[-4:] if secret_key else 'None'}")
    print(f"Base URL: {base_url}")
    print(f"Paper Trading: {os.getenv('IS_PAPER_TRADING')}")
    
    if not api_key or not secret_key:
        print("❌ Missing API credentials!")
        return False
    
    # Test direct HTTP request
    print("\n🌐 Testing direct HTTP request...")
    
    try:
        import base64
        
        # Create basic auth header
        credentials = f"{api_key}:{secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json'
        }
        
        # Test account endpoint
        response = requests.get(f"{base_url}/v2/account", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Direct HTTP request successful!")
            account_data = response.json()
            print(f"Account ID: {account_data.get('id', 'Unknown')}")
            print(f"Status: {account_data.get('status', 'Unknown')}")
            print(f"Cash: ${account_data.get('cash', '0')}")
            return True
        else:
            print(f"❌ HTTP request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ HTTP request error: {str(e)}")
        return False

def test_different_endpoints():
    """Test different API endpoints to narrow down the issue."""
    
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL")
    
    import base64
    
    credentials = f"{api_key}:{secret_key}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/json'
    }
    
    endpoints = [
        "/v2/account",
        "/v2/positions",
        "/v2/orders",
        "/v2/assets"
    ]
    
    print("\n🎯 Testing different endpoints...")
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", headers=headers)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {endpoint}: {response.status_code}")
            
            if response.status_code != 200:
                print(f"   Error: {response.text[:100]}...")
                
        except Exception as e:
            print(f"❌ {endpoint}: Exception - {str(e)}")

def check_account_requirements():
    """Check if account meets requirements."""
    
    print("\n📋 Account Requirements Check:")
    print("1. ✅ Paper trading account created")
    print("2. ✅ API keys generated")
    print("3. ❓ Account approved and active?")
    print("4. ❓ API permissions enabled?")
    print("5. ❓ Account funded (even for paper)?")
    
    print("\n💡 Common Issues:")
    print("- New accounts may need 24-48 hours for API activation")
    print("- Some paper accounts require initial 'funding' setup")
    print("- API keys might need specific permissions enabled")
    print("- Account status might be 'PENDING' instead of 'ACTIVE'")

if __name__ == "__main__":
    if diagnose_credentials():
        test_different_endpoints()
    
    check_account_requirements()
    
    print("\n🔧 Next Steps:")
    print("1. Check your Alpaca dashboard for account status")
    print("2. Verify API keys have correct permissions")
    print("3. Ensure paper account is fully activated")
    print("4. Try regenerating API keys if needed")