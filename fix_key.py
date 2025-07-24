#!/usr/bin/env python3
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# Your base64 key
private_key_b64 = "269R/VXm7V+bxW/5Nvm2GkC/IxcgE1bTOsnq0dKGwfXgLMmtcMaqGZYXR/li/hsF4SbZMp+GaMOw8OZSVLdyrA=="

# Decode and create proper key
private_key_bytes = base64.b64decode(private_key_b64)
private_value = int.from_bytes(private_key_bytes[:32], 'big')
private_key = ec.derive_private_key(private_value, ec.SECP256R1())

# Get PEM format
pem_key = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

pem_string = pem_key.decode('utf-8')
print("Correct PEM key:")
print(pem_string)

# Create the .env line
env_line = pem_string.replace('\n', '\\n')
print("\nFor .env file:")
print(f"COINBASE_API_SECRET={env_line}")