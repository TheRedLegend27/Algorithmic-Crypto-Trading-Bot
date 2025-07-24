#!/usr/bin/env python3
"""
Test different approaches to handle the Coinbase API key format.
"""
import base64
import json
import time
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

def test_key_formats():
    """Test different ways to handle the base64 key."""
    
    # Your credentials
    api_key = "2de5865b-de74-49ed-89a0-ad72f098f92a"
    private_key_b64 = "269R/VXm7V+bxW/5Nvm2GkC/IxcgE1bTOsnq0dKGwfXgLMmtcMaqGZYXR/li/hsF4SbZMp+GaMOw8OZSVLdyrA=="
    
    print("🔍 Testing different key format approaches...")
    print(f"API Key: {api_key}")
    print(f"Private Key (base64): {private_key_b64[:20]}...")
    
    # Decode base64
    try:
        private_key_bytes = base64.b64decode(private_key_b64)
        print(f"✅ Base64 decoded successfully ({len(private_key_bytes)} bytes)")
    except Exception as e:
        print(f"❌ Base64 decode failed: {e}")
        return
    
    # Test 1: Try as raw EC private key (assuming secp256r1)
    print("\n🧪 Test 1: Raw EC private key (secp256r1)")
    try:
        if len(private_key_bytes) == 32:
            # First 32 bytes as private key
            private_value = int.from_bytes(private_key_bytes[:32], 'big')
            private_key = ec.derive_private_key(private_value, ec.SECP256R1())
            
            # Convert to PEM
            pem_key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            print("✅ Successfully created EC private key")
            print("PEM format:")
            print(pem_key.decode('utf-8'))
            
            # Test JWT generation
            test_jwt_generation(api_key, pem_key.decode('utf-8'))
            
        elif len(private_key_bytes) == 64:
            # Try first 32 bytes
            private_value = int.from_bytes(private_key_bytes[:32], 'big')
            private_key = ec.derive_private_key(private_value, ec.SECP256R1())
            
            pem_key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            print("✅ Successfully created EC private key (first 32 bytes)")
            print("PEM format:")
            print(pem_key.decode('utf-8'))
            
            # Test JWT generation
            test_jwt_generation(api_key, pem_key.decode('utf-8'))
            
    except Exception as e:
        print(f"❌ Raw EC key test failed: {e}")
    
    # Test 2: Try direct base64 with JWT (some APIs use this)
    print("\n🧪 Test 2: Direct base64 with JWT")
    try:
        test_jwt_generation(api_key, private_key_b64)
    except Exception as e:
        print(f"❌ Direct base64 JWT test failed: {e}")

def test_jwt_generation(api_key, private_key):
    """Test JWT token generation with given key."""
    print(f"\n🔐 Testing JWT generation...")
    print(f"Key type: {type(private_key)}")
    print(f"Key preview: {str(private_key)[:50]}...")
    
    try:
        # JWT header
        header = {
            'alg': 'ES256',
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
            'aud': ['public_websocket_api']
        }
        
        # Try to generate JWT
        token = jwt.encode(payload, private_key, algorithm='ES256', headers=header)
        print(f"✅ JWT generated successfully!")
        print(f"Token preview: {token[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ JWT generation failed: {e}")
        return False

if __name__ == "__main__":
    test_key_formats()