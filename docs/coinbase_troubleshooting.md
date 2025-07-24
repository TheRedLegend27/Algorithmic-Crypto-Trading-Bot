# Coinbase Integration Troubleshooting Guide

This guide addresses common issues you might encounter when integrating with the Coinbase Advanced Trade API and provides solutions to resolve them.

## Authentication Issues

### Issue: Invalid API Key

**Symptoms:**
- Error message: `Invalid API key`
- HTTP status code: `401 Unauthorized`

**Solutions:**
1. Verify that your API key is correctly copied from Coinbase
2. Check for extra spaces or characters in your `.env` file
3. Ensure you're using the correct API key for the environment (sandbox vs. live)
4. Try regenerating your API key in the Coinbase dashboard

### Issue: Invalid Signature

**Symptoms:**
- Error message: `Invalid signature`
- HTTP status code: `401 Unauthorized`

**Solutions:**
1. Check that your API secret is correctly copied from Coinbase
2. Verify that your system clock is synchronized (timestamp mismatch can cause signature failures)
3. Ensure you're using the correct hashing algorithm (HMAC-SHA256)
4. Check for any encoding issues in your API secret

### Issue: Invalid Passphrase

**Symptoms:**
- Error message: `Invalid passphrase`
- HTTP status code: `401 Unauthorized`

**Solutions:**
1. Verify that your passphrase is correctly copied from Coinbase
2. Check for extra spaces or characters in your `.env` file
3. Try regenerating your API key and passphrase

## Rate Limiting Issues

### Issue: Too Many Requests

**Symptoms:**
- Error message: `Rate limit exceeded`
- HTTP status code: `429 Too Many Requests`

**Solutions:**
1. Reduce the frequency of your API calls
2. Implement exponential backoff in your retry logic
3. Use WebSocket for real-time data instead of frequent REST API calls
4. Check if you're making redundant API calls that could be optimized

### Issue: Connection Throttling

**Symptoms:**
- Slow responses
- Intermittent timeouts

**Solutions:**
1. Implement proper caching for frequently accessed data
2. Reduce polling frequency for market data
3. Use the WebSocket API for real-time updates
4. Batch API requests where possible

## Order Execution Issues

### Issue: Insufficient Funds

**Symptoms:**
- Error message: `Insufficient funds`
- Orders fail to execute

**Solutions:**
1. Check your account balance in the Coinbase dashboard
2. Verify that you have enough funds for the order plus fees
3. Reduce the order size
4. Check if funds are on hold due to pending transactions

### Issue: Invalid Order Size

**Symptoms:**
- Error message: `Order size is too small` or `Order size is invalid`
- Orders fail to execute

**Solutions:**
1. Check the minimum order size for the trading pair
2. Ensure your order meets the size precision requirements
3. Update your `min_order_size` setting in `CryptoTradingSettings`
4. Increase your trade amount

### Issue: Price Precision Errors

**Symptoms:**
- Error message: `Invalid price precision`
- Orders fail to execute

**Solutions:**
1. Check the price precision requirements for the trading pair
2. Update your `price_precision` setting in `CryptoTradingSettings`
3. Ensure your price rounding logic matches Coinbase requirements

## WebSocket Issues

### Issue: WebSocket Connection Drops

**Symptoms:**
- Frequent disconnections
- Missing market data updates

**Solutions:**
1. Implement proper reconnection logic with exponential backoff
2. Check your network stability
3. Ensure you're handling WebSocket ping/pong messages correctly
4. Verify you're not exceeding the maximum number of WebSocket connections

### Issue: WebSocket Authentication Failures

**Symptoms:**
- Cannot subscribe to authenticated channels
- Error messages in WebSocket responses

**Solutions:**
1. Verify your authentication process for WebSocket connections
2. Check that you're sending the correct authentication message
3. Ensure your API key has the necessary permissions
4. Check for clock synchronization issues

## Data Issues

### Issue: Missing or Delayed Market Data

**Symptoms:**
- Strategies making decisions on stale data
- Unexpected trading behavior

**Solutions:**
1. Check your data fetching logic and error handling
2. Implement fallback mechanisms for when primary data source fails
3. Add logging to track data freshness
4. Consider using multiple data sources for redundancy

### Issue: Inconsistent Order Book Data

**Symptoms:**
- Unexpected price execution
- Difficulty calculating accurate price levels

**Solutions:**
1. Use the appropriate order book depth for your needs
2. Implement proper order book management and updates
3. Consider using the WebSocket feed for real-time order book updates
4. Add validation for order book data consistency

## Environment Issues

### Issue: Sandbox vs. Live Environment Confusion

**Symptoms:**
- Trades not appearing in your real account
- Test trades affecting your real balance

**Solutions:**
1. Double-check your `COINBASE_SANDBOX` setting
2. Verify the base URL being used for API calls
3. Ensure you're using the correct API keys for each environment
4. Add clear logging to indicate which environment is being used

### Issue: Configuration Not Loading

**Symptoms:**
- Default values being used instead of configured values
- Error messages about missing configuration

**Solutions:**
1. Check that your `.env` file is in the correct location
2. Verify that environment variables are being loaded correctly
3. Use the `--validate-only` flag with the migration utility to check your configuration
4. Add debug logging for configuration loading

## Debugging Tips

### Enable Verbose Logging

Add the `--log-level DEBUG` flag when running the bot:
```
python run_coinbase_bot.py --log-level DEBUG
```

### Check API Responses

Examine the full API responses in the logs to identify specific error messages.

### Use the Sandbox Environment

Test your changes in the sandbox environment before using real funds:
```
python run_coinbase_bot.py --sandbox
```

### Validate Your Configuration

Use the migration utility to validate your configuration:
```
python tools/alpaca_to_coinbase_migration.py --validate-only
```

### Check Coinbase Status

If you're experiencing widespread issues, check the [Coinbase status page](https://status.coinbase.com/) to see if there are known service disruptions.

## Common Error Codes

| HTTP Status | Error Code | Description | Solution |
|-------------|------------|-------------|----------|
| 400 | invalid_request | Malformed request | Check request parameters and format |
| 401 | invalid_api_key | Invalid API key | Verify API key is correct |
| 401 | invalid_signature | Invalid signature | Check API secret and timestamp |
| 401 | invalid_passphrase | Invalid passphrase | Verify passphrase is correct |
| 403 | forbidden | Insufficient permissions | Check API key permissions |
| 429 | rate_limit_exceeded | Too many requests | Implement backoff and reduce request frequency |
| 500 | internal_server_error | Server error | Retry with exponential backoff |

## Getting Help

If you continue to experience issues after trying the solutions in this guide:

1. Check the [Coinbase Advanced Trade API documentation](https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome)
2. Review the error handling code in `bot/coinbase_error_handler.py`
3. Look for similar issues in the project's issue tracker
4. Reach out to the community for support