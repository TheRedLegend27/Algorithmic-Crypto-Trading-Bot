# Alpaca to Coinbase Migration Guide

This guide will walk you through the process of migrating your trading bot from Alpaca to Coinbase Advanced Trade API for cryptocurrency trading.

## Migration Overview

The migration process involves several steps:

1. Setting up Coinbase API credentials
2. Converting your configuration
3. Testing in the sandbox environment
4. Adapting your trading strategies
5. Deploying to production

## Prerequisites

Before starting the migration, ensure you have:

- A Coinbase account with Advanced Trade API access
- API keys for Coinbase Advanced Trade (see [Coinbase API Setup Guide](./coinbase_api_setup.md))
- Your existing Alpaca-based trading bot codebase
- Basic understanding of cryptocurrency trading concepts

## Step 1: Set Up Coinbase API Credentials

1. **Create Coinbase API Keys**
   - Follow the instructions in the [Coinbase API Setup Guide](./coinbase_api_setup.md)
   - Make sure to enable the appropriate permissions (View and Trade)
   - Consider setting IP restrictions for security

2. **Add Credentials to Environment**
   - Add the following to your `.env` file:
   ```
   COINBASE_API_KEY=your_api_key_here
   COINBASE_API_SECRET=your_api_secret_here
   COINBASE_PASSPHRASE=your_passphrase_here
   COINBASE_SANDBOX=True  # Start with sandbox mode for testing
   ```

## Step 2: Convert Your Configuration

### Using the Migration Utility

The easiest way to migrate is to use the provided migration utility:

```bash
# Generate a new configuration file without modifying the original
python tools/alpaca_to_coinbase_migration.py --output-env .env.coinbase

# Review the generated file and update any placeholder values

# Apply the changes to your original .env file (creates a backup automatically)
python tools/alpaca_to_coinbase_migration.py --apply
```

### Manual Configuration

If you prefer to configure manually:

1. **Update Environment Variables**
   - Keep your Alpaca credentials (commented out for reference)
   - Add Coinbase credentials as shown above

2. **Update Trading Parameters**
   - Adjust trading parameters for cryptocurrency markets:
   ```
   # Example crypto-specific settings you might want to add
   CRYPTO_TRADING_PAIR=BTC-USD
   CRYPTO_BASE_CURRENCY=BTC
   CRYPTO_QUOTE_CURRENCY=USD
   CRYPTO_MIN_ORDER_SIZE=0.001
   ```

## Step 3: Test in the Sandbox Environment

Before trading with real funds, thoroughly test in the Coinbase sandbox:

1. **Run the Bot in Sandbox Mode**
   ```bash
   python run_coinbase_bot.py --sandbox
   ```

2. **Verify Basic Functionality**
   - Check that the bot can authenticate with Coinbase
   - Verify it can fetch market data
   - Test order placement and cancellation
   - Ensure position tracking works correctly

3. **Test Error Handling**
   - Try placing invalid orders to test error handling
   - Simulate network issues to test reconnection logic
   - Verify rate limit handling

## Step 4: Adapt Your Trading Strategies

Cryptocurrency markets differ from stock markets in several ways:

1. **24/7 Trading**
   - Update your strategies to handle 24/7 markets
   - Consider time-based filters for high-volatility periods

2. **Higher Volatility**
   - Adjust position sizing for higher volatility
   - Consider tighter stop-loss settings
   - Implement volatility-based risk management

3. **Different Market Dynamics**
   - Test your strategies with historical crypto data
   - Adjust technical indicators for crypto market behavior
   - Consider crypto-specific factors (network activity, adoption metrics)

4. **Order Sizes and Precision**
   - Update order size calculations to respect minimum order sizes
   - Handle price and size precision requirements

## Step 5: Deploy to Production

Once you're confident in your testing, you can deploy to production:

1. **Switch to Live Environment**
   - Update your configuration:
   ```
   COINBASE_SANDBOX=False
   ```
   - Or run without the sandbox flag:
   ```bash
   python run_coinbase_bot.py
   ```

2. **Start with Small Positions**
   - Begin with small trade amounts
   - Gradually increase as you gain confidence
   - Monitor closely during the initial deployment

3. **Monitor Performance**
   - Watch for any unexpected behavior
   - Monitor execution prices and slippage
   - Track strategy performance in the new environment

4. **Implement Safeguards**
   - Set maximum daily loss limits
   - Implement circuit breakers for extreme volatility
   - Set up alerts for unusual activity

## Key Differences Between Alpaca and Coinbase

Understanding these differences will help you adapt your code and strategies:

### API Differences

| Feature | Alpaca | Coinbase Advanced Trade |
|---------|--------|-------------------------|
| Authentication | API Key + Secret | API Key + Secret + Passphrase |
| Rate Limits | 200 requests/min | 10 requests/sec (public), 5 requests/sec (private) |
| WebSocket | Single connection | Multiple channels, requires authentication |
| Order Types | Market, Limit, Stop, etc. | Market, Limit (more limited options) |
| Assets | Stocks, ETFs | Cryptocurrencies only |
| Trading Hours | Market hours | 24/7 trading |

### Market Data Differences

| Feature | Alpaca | Coinbase Advanced Trade |
|---------|--------|-------------------------|
| Price Precision | 2 decimal places | Varies by trading pair |
| Size Precision | Whole shares | Varies by trading pair (e.g., 0.00000001 BTC) |
| Minimum Order Size | $1.00 | Varies by trading pair |
| Fee Structure | Commission-free | Maker/taker fees |
| Market Hours | 9:30 AM - 4:00 PM ET | 24/7 trading |

### Code Structure Differences

| Component | Alpaca | Coinbase |
|-----------|--------|----------|
| Client | `AlpacaClient` | `CoinbaseClient` |
| Data Fetcher | `DataFetcher` | `CoinbaseDataFetcher` |
| Trader | `Trader` | `CoinbaseTrader` |
| Position Manager | `PositionManager` | `CryptoPositionManager` |
| Order Manager | `OrderManager` | `CryptoOrderManager` |
| Error Handler | `ErrorHandler` | `CoinbaseErrorHandler` |

## Troubleshooting

If you encounter issues during migration, refer to the [Coinbase Troubleshooting Guide](./coinbase_troubleshooting.md) for solutions to common problems.

## Rollback Plan

If you need to revert to Alpaca:

1. **Restore Environment Variables**
   - If you created a backup during migration, restore it:
   ```bash
   cp .env.bak.TIMESTAMP .env
   ```

2. **Run with Alpaca Platform**
   ```bash
   python run_bot.py --platform alpaca
   ```

## Conclusion

Migrating from Alpaca to Coinbase requires careful planning and testing, but offers the advantage of accessing cryptocurrency markets. Take your time with each step, thoroughly test in the sandbox environment, and start with small positions when going live.

For additional help, refer to:
- [Coinbase API Setup Guide](./coinbase_api_setup.md)
- [Coinbase Troubleshooting Guide](./coinbase_troubleshooting.md)
- [Coinbase Advanced Trade API Documentation](https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome)