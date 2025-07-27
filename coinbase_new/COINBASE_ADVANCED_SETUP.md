# Coinbase Advanced Trade API Setup Guide

## Overview

This guide will help you set up the new, simplified Coinbase Advanced Trade API integration. We've completely rewritten the implementation to focus exclusively on the Advanced Trade API for better reliability and performance.

## Step 1: Create Advanced Trade API Key

1. **Go to Coinbase Developer Platform**: https://www.coinbase.com/cloud
2. **Sign in** with your Coinbase account
3. **Create a new API Key**:
   - Click "Create API Key"
   - Give it a descriptive name (e.g., "Trading Bot")
   - **IMPORTANT**: Select the following permissions:
     - ✅ **View** (required for account info and market data)
     - ✅ **Trade** (required for placing orders)
     - ✅ **Transfer** (optional, for moving funds)

## Step 2: Download Your Credentials

After creating the API key, you'll receive:

- **API Key**: Format like `organizations/abc123def/apiKeys/xyz789`
- **Private Key**: Ed25519 private key in PEM format

**Example of what you'll get:**
```
API Key: organizations/12345678-1234-1234-1234-123456789abc/apiKeys/abcdef12-3456-7890-abcd-ef1234567890
Private Key: 
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIAbcdefghijklmnopqrstuvwxyz1234567890abcdef
ghijklmnopqrstuvwxyz
-----END PRIVATE KEY-----
```

## Step 3: Update Your .env File

Update your `.env` file with the new credentials:

```bash
# NEW Coinbase Advanced Trade API credentials
COINBASE_ADVANCED_API_KEY=organizations/your_org_id/apiKeys/your_key_id
COINBASE_ADVANCED_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nYOUR_ACTUAL_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----
```

**Important Notes:**
- Replace `your_org_id` and `your_key_id` with your actual values
- Replace `YOUR_ACTUAL_PRIVATE_KEY_HERE` with your actual private key content
- Keep the `\n` characters in the private key - they represent line breaks
- The private key should be one long line with `\n` for line breaks

## Step 4: Test Your Setup

Run the test script to verify everything works:

```bash
python3 test_advanced_api.py
```

This will test:
- ✅ Credential validation
- ✅ API connection
- ✅ Account access
- ✅ Market data retrieval
- ✅ Trader initialization

## Step 5: Integration with Your Bot

The new implementation provides a clean, simple interface:

```python
from bot.coinbase_advanced_client import AdvancedTradeCredentials
from bot.coinbase_advanced_trader import CoinbaseAdvancedTrader, TradingConfig

# Create credentials
credentials = AdvancedTradeCredentials(
    api_key=os.getenv("COINBASE_ADVANCED_API_KEY"),
    private_key=os.getenv("COINBASE_ADVANCED_PRIVATE_KEY")
)

# Create trading config
config = TradingConfig(
    product_id="BTC-USD",
    trade_amount_usd=10.0,
    max_position_usd=100.0
)

# Initialize trader
trader = CoinbaseAdvancedTrader(credentials, config)

# Execute trades
from bot.strategy import TradingSignal, SignalType
signal = TradingSignal(action=SignalType.BUY, confidence=0.8, price=50000.0)
result = trader.execute_trade(signal)

if result.success:
    print(f"Trade executed: {result.order_id}")
else:
    print(f"Trade failed: {result.error}")
```

## Key Features of New Implementation

### ✅ **Simplified & Focused**
- Only supports Advanced Trade API (no legacy API confusion)
- Clean, minimal codebase
- Easy to understand and maintain

### ✅ **Robust Error Handling**
- Comprehensive error messages
- Automatic retry logic
- Graceful failure handling

### ✅ **Smart Caching**
- Caches account and product data
- Reduces API calls
- Improves performance

### ✅ **Trading Features**
- Market orders (immediate execution)
- Limit orders (price-specific)
- Stop orders (risk management)
- Portfolio management
- Balance checking

## Troubleshooting

### Common Issues:

1. **"Missing Advanced Trade API credentials"**
   - Make sure you set `COINBASE_ADVANCED_API_KEY` and `COINBASE_ADVANCED_PRIVATE_KEY`
   - Check for typos in the environment variable names

2. **"API connection failed"**
   - Verify your API key format: `organizations/{org_id}/apiKeys/{key_id}`
   - Check that your private key is in correct PEM format
   - Ensure your API key has the required permissions (View + Trade)

3. **"Unauthorized" (401 errors)**
   - **Most common**: Your API key doesn't have trading permissions
   - Go back to Coinbase Developer Platform and edit your API key
   - Add "Trade" permission if it's missing

4. **"Invalid private key format"**
   - Make sure your private key starts with `-----BEGIN PRIVATE KEY-----`
   - Ensure you have `\n` characters for line breaks in the .env file
   - Don't add extra spaces or characters

5. **"Order failed" errors**
   - Check you have sufficient balance
   - Verify the trading pair is active (BTC-USD, ETH-USD, etc.)
   - Ensure order size meets minimum requirements

### Getting Help:

1. Run `python3 test_advanced_api.py` and check the output
2. Check the logs for detailed error messages
3. Verify your API key permissions in Coinbase Developer Platform
4. Make sure you're using the correct API key format

## Security Best Practices

- ✅ Never share your private key or API credentials
- ✅ Use environment variables (never hardcode credentials)
- ✅ Start with small trade amounts for testing
- ✅ Monitor your API key usage in Coinbase Developer Platform
- ✅ Regularly rotate your API keys
- ✅ Use proper file permissions on your .env file (`chmod 600 .env`)

## Migration from Old Implementation

If you were using the old Coinbase implementation:

1. **Create new Advanced Trade API key** (old UUID keys won't work)
2. **Update your .env file** with new credential format
3. **Replace old imports** with new ones:
   ```python
   # OLD
   from bot.coinbase_client import CoinbaseClient
   from bot.coinbase_trader import CoinbaseTrader
   
   # NEW
   from bot.coinbase_advanced_client import CoinbaseAdvancedClient
   from bot.coinbase_advanced_trader import CoinbaseAdvancedTrader
   ```
4. **Test thoroughly** with small amounts first

The new implementation is much simpler and more reliable than the old one!