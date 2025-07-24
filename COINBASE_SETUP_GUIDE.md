# Coinbase Advanced Trade API Setup Guide

## Overview
Coinbase has migrated from the old Coinbase Pro API to the new Advanced Trade API, which uses JWT (JSON Web Token) authentication instead of the old HMAC method with passphrases.

## Step 1: Create API Keys

**IMPORTANT**: There are two different Coinbase APIs:
1. **Coinbase Advanced Trade API** (new) - uses format `organizations/xxx/apiKeys/yyy`
2. **Coinbase Cloud Trading API** (older) - uses UUID format like `2de5865b-de74-49ed-89a0-ad72f098f92a`

### For Advanced Trade API (Recommended):
1. Go to [Coinbase Developer Platform](https://www.coinbase.com/cloud)
2. Sign in with your Coinbase account
3. Navigate to "API Keys" section
4. Click "Create API Key"
5. Select the permissions you need:
   - **View** (required for account info and market data)
   - **Trade** (required for placing orders)
   - **Transfer** (if you need to move funds)

### For Cloud Trading API (Legacy):
1. Go to [Coinbase Cloud](https://cloud.coinbase.com/)
2. Create a project and API key
3. This gives you a UUID-style key and base64 private key

## Step 2: Download Your Credentials

After creating the API key, you'll get:
- **API Key Name**: A human-readable name for your key
- **API Key**: A string that looks like `organizations/abc123/apiKeys/def456`
- **Private Key**: A PEM-formatted private key (starts with `-----BEGIN EC PRIVATE KEY-----`)

## Step 3: Update Your .env File

Update your `.env` file with the new format:

```bash
# Coinbase Advanced Trade API credentials (JWT-based authentication)
COINBASE_API_KEY=organizations/your_org_id/apiKeys/your_key_id
COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIAbcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqr
stuvwxyzaAoGCCqGSM49AwEHoUQDQgAE1234567890abcdefghijklmnopqrst
uvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrst
uvwxyz==
-----END EC PRIVATE KEY-----

# Set to True for sandbox trading, False for live trading
COINBASE_SANDBOX=True
```

**Important Notes:**
- The `COINBASE_API_SECRET` should be your entire private key including the `-----BEGIN EC PRIVATE KEY-----` and `-----END EC PRIVATE KEY-----` lines
- Make sure there are no extra spaces or line breaks
- The private key should be on multiple lines as shown above

## Step 4: Test Your Setup

Run the test script to verify your credentials:

```bash
python test_coinbase_auth.py
```

This will:
- ✅ Check if your credentials are properly set
- ✅ Test JWT token generation
- ✅ Verify API authentication
- ✅ Test account access
- ✅ Test market data access

## Step 5: Run Your Bot

Once the test passes, you can run your bot:

```bash
python run_coinbase_bot.py
```

## Troubleshooting

### Common Issues:

1. **"Invalid JWT token"**
   - Make sure your private key is in the correct PEM format
   - Verify there are no extra spaces or characters
   - Check that the key includes the BEGIN/END lines

2. **"API key not found"**
   - Verify your API key format: `organizations/xxx/apiKeys/yyy`
   - Make sure you copied the full key string

3. **"Insufficient permissions" or "Unauthorized" (401 errors)**
   - **MOST COMMON ISSUE**: Your API key only has public/read-only permissions
   - Go back to Coinbase Developer Platform
   - Edit your API key to add required permissions:
     - ✅ **View** (required for account info and market data)
     - ✅ **Trade** (required for placing orders)
     - ✅ **Transfer** (if you need to move funds)
   - If you can't edit permissions, create a new API key with proper permissions

4. **"Authentication failed"**
   - Double-check your API key and private key
   - Verify you're using the correct sandbox/production settings
   - Make sure your API key is active (not revoked)

5. **"Only public endpoints work"**
   - This means your API key has read-only permissions
   - You can get market data but cannot access accounts or trade
   - Create a new API key with trading permissions

### Getting Help:

If you're still having issues:
1. Run `python test_coinbase_auth.py` and share the output
2. Check the Coinbase Developer documentation
3. Verify your API key permissions in the Coinbase Developer Platform

## Security Notes:

- Never share your private key or API credentials
- Use sandbox mode for testing
- Regularly rotate your API keys
- Monitor your API key usage in the Coinbase Developer Platform