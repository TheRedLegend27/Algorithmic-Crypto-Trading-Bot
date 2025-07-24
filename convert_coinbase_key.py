#!/usr/bin/env python3
"""
Convert Coinbase API credentials from JSON format to .env format.
This script converts the base64 encoded private key to PEM format.
"""
import base64
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

def convert_coinbase_credentials():
    """Convert Coinbase JSON credentials to proper .env format."""
    
    # Your JSON credentials
    credentials = {
        "id": "2de5865b-de74-49ed-89a0-ad72f098f92a",
        "privateKey": "269R/VXm7V+bxW/5Nvm2GkC/IxcgE1bTOsnq0dKGwfXgLMmtcMaqGZYXR/li/hsF4SbZMp+GaMOw8OZSVLdyrA=="
    }
    
    print("🔄 Converting Coinbase credentials...")
    print(f"API Key ID: {credentials['id']}")
    
    try:
        # Decode the base64 private key
        private_key_bytes = base64.b64decode(credentials['privateKey'])
        print(f"✅ Successfully decoded base64 private key ({len(private_key_bytes)} bytes)")
        
        # Try different approaches to load the key
        private_key = None
        
        # Method 1: Try as DER format
        try:
            private_key = serialization.load_der_private_key(
                private_key_bytes,
                password=None
            )
            print("✅ Successfully loaded private key as DER")
        except Exception as e1:
            print(f"⚠️  DER loading failed: {str(e1)}")
            
            # Method 2: Try as raw EC private key (32 bytes for secp256r1)
            if len(private_key_bytes) == 32:
                try:
                    # Create EC private key from raw bytes
                    private_key = ec.derive_private_key(
                        int.from_bytes(private_key_bytes, 'big'),
                        ec.SECP256R1()
                    )
                    print("✅ Successfully created EC private key from raw bytes")
                except Exception as e2:
                    print(f"⚠️  Raw EC key creation failed: {str(e2)}")
            
            # Method 3: Try as PEM format (in case it's already PEM but base64 encoded)
            if private_key is None:
                try:
                    pem_data = private_key_bytes.decode('utf-8')
                    private_key = serialization.load_pem_private_key(
                        pem_data.encode('utf-8'),
                        password=None
                    )
                    print("✅ Successfully loaded private key as PEM")
                except Exception as e3:
                    print(f"⚠️  PEM loading failed: {str(e3)}")
        
        if private_key is None:
            raise Exception("Could not load private key with any method")
        
        # Convert to PEM format
        pem_private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        pem_string = pem_private_key.decode('utf-8')
        print("✅ Successfully converted to PEM format")
        
        # Display the results
        print("\n" + "="*60)
        print("📋 Add these to your .env file:")
        print("="*60)
        print(f"COINBASE_API_KEY={credentials['id']}")
        print("COINBASE_API_SECRET=" + pem_string.replace('\n', '\\n'))
        print("COINBASE_SANDBOX=True")
        
        print("\n" + "="*60)
        print("📝 Or copy this PEM key for COINBASE_API_SECRET:")
        print("="*60)
        print(pem_string)
        
        return credentials['id'], pem_string
        
    except Exception as e:
        print(f"❌ Error converting credentials: {str(e)}")
        return None, None

if __name__ == "__main__":
    api_key, private_key_pem = convert_coinbase_credentials()
    
    if api_key and private_key_pem:
        print("🎉 Conversion successful!")
        print("\nNext steps:")
        print("1. Update your .env file with the values above")
        print("2. Run: python test_coinbase_auth.py")
    else:
        print("❌ Conversion failed!")