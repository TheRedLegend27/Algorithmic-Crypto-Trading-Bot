#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

api_secret = os.getenv("COINBASE_API_SECRET")
print("Raw from .env:")
print(repr(api_secret))
print("\nAfter newline replacement:")
processed = api_secret.replace('\\n', '\n')
print(repr(processed))
print("\nActual content:")
print(processed)