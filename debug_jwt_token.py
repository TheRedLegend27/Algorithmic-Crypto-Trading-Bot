#!/usr/bin/env python3
"""
Debug JWT token generation and structure.
"""
import os
import sys
import time
import jwt
import json
from dotenv import load_dotenv

def generate_and_debug_jwt(api_key, private_key):
    """Generate JWT and show its structure."""
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
    
    print("🔍 JWT Generation Debug")
    print("=" * 40)
    print(f"API Key: {api_key}")
    print(f"Key Type: {'ECDSA (EC)' if 'EC PRIVATE KEY' in private_key else 'Unknown'}")
    print(f"Current Time: {now}")
    
    print(f"\nJWT Header:")
    print(json.dumps(header, indent=2))
    
    print(f"\nJWT Payload:")
    print(json.dumps(payload, indent=2))
    
    # Generate token
    private_key_processed = private_key.replace('\\n', '\n')
    print(f"\nPrivate Key Preview:")
    print(f"{private_key_processed[:50]}...")
    print(f"{private_key_processed[-50:]}")
    
    try:
        token = jwt.encode(payload, private_key_processed, algorithm='ES256', headers=header)
        print(f"\n✅ JWT Token Generated Successfully!")
        print(f"Token Length: {len(token)} characters")
        print(f"Token Preview: {token[:50]}...{token[-50:]}")
        
        # Try to decode it back (without verification)
        try:
            decoded_header = jwt.get_unverified_header(token)
            decoded_payload = jwt.decode(token, options={"verify_signature": False})
            
            print(f"\n🔍 Decoded JWT (unverified):")
            print(f"Header: {json.dumps(decoded_header, indent=2)}")
            print(f"Payload: {json.dumps(decoded_payload, indent=2)}")
            
        except Exception as e:
            print(f"❌ Could not decode JWT: {e}")
        
        return token
        
    except Exception as e:
        print(f"❌ JWT Generation Failed: {e}")
        return None

def main():
    load_dotenv()
    
    api_key = os.getenv("COINBASE_API_KEY")
    private_key = os.getenv("COINBASE_API_SECRET")
    
    if not api_key or not private_key:
        print("❌ Missing API credentials in .env file")
        return
    
    token = generate_and_debug_jwt(api_key, private_key)
    
    if token:
        print(f"\n💡 Next Steps:")
        print("1. Verify API key has proper permissions in Coinbase Developer Platform")
        print("2. Check if the key is active and not revoked")
        print("3. Ensure 'View' and 'Trade' permissions are enabled")
        print("4. Try using the token in a manual API request")

if __name__ == "__main__":
    main()