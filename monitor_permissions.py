#!/usr/bin/env python3
"""
Monitor Coinbase API permissions until they work.
"""
import os
import sys
import time
import jwt
import requests
from datetime import datetime
from dotenv import load_dotenv

def test_permissions():
    """Test if permissions are working."""
    load_dotenv()
    
    api_key = os.getenv("COINBASE_ADVANCED_API_KEY")
    private_key = os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
    
    if not api_key or not private_key:
        return False, "Missing credentials"
    
    # Generate JWT
    private_key = private_key.replace('\\n', '\n')
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
    except Exception as e:
        return False, f"JWT generation failed: {e}"
    
    # Test accounts endpoint
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(
            "https://api.coinbase.com/api/v3/brokerage/accounts", 
            headers=headers, 
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "Success!"
        else:
            return False, f"HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Request failed: {e}"

def main():
    print("🔄 Monitoring Coinbase API Permissions")
    print("=" * 40)
    print("This will test every 30 seconds until permissions work...")
    print("Press Ctrl+C to stop\n")
    
    attempt = 1
    start_time = time.time()
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            
            success, message = test_permissions()
            
            if success:
                elapsed = int(time.time() - start_time)
                print(f"🎉 [{current_time}] SUCCESS! Permissions are working!")
                print(f"   Took {elapsed} seconds ({elapsed//60}m {elapsed%60}s)")
                print(f"\n✅ You can now run: python3 test_advanced_api.py")
                break
            else:
                elapsed = int(time.time() - start_time)
                print(f"⏳ [{current_time}] Attempt {attempt} - Still waiting... ({message}) - {elapsed}s elapsed")
                
            attempt += 1
            time.sleep(30)  # Wait 30 seconds between attempts
            
        except KeyboardInterrupt:
            print(f"\n\n🛑 Monitoring stopped by user")
            elapsed = int(time.time() - start_time)
            print(f"   Monitored for {elapsed} seconds ({elapsed//60}m {elapsed%60}s)")
            break
        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()