#!/usr/bin/env python3
"""
Test Ed25519 key detection and conversion.
"""
import os
import base64
from dotenv import load_dotenv

def test_ed25519_key():
    load_dotenv()
    
    private_key_raw = os.getenv("COINBASE_API_SECRET")
    print(f"🔍 Testing Ed25519 key detection")
    print(f"Raw key: {private_key_raw}")
    print(f"Key length: {len(private_key_raw)}")
    
    # Test base64 decoding
    try:
        decoded = base64.b64decode(private_key_raw)
        print(f"✅ Base64 decode successful")
        print(f"Decoded length: {len(decoded)} bytes")
        print(f"Expected length for Ed25519: 32 bytes")
        
        if len(decoded) == 32:
            print("✅ Correct length for Ed25519 private key")
            
            # Try to create Ed25519 key
            from cryptography.hazmat.primitives.asymmetric import ed25519
            from cryptography.hazmat.primitives import serialization
            
            try:
                ed25519_key = ed25519.Ed25519PrivateKey.from_private_bytes(decoded)
                print("✅ Successfully created Ed25519 private key")
                
                # Convert to PEM
                pem_key = ed25519_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')
                
                print("✅ Successfully converted to PEM format")
                print("PEM key preview:")
                print(pem_key[:100] + "...")
                
                return True
                
            except Exception as e:
                print(f"❌ Failed to create Ed25519 key: {e}")
                return False
        else:
            print(f"❌ Wrong length: {len(decoded)} bytes (expected 32)")
            return False
            
    except Exception as e:
        print(f"❌ Base64 decode failed: {e}")
        return False

if __name__ == "__main__":
    test_ed25519_key()