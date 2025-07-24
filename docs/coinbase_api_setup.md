# Coinbase Advanced Trade API Setup Guide

This guide will walk you through the process of setting up the Coinbase Advanced Trade API for use with the crypto trading bot.

## Prerequisites

- A Coinbase account
- Two-factor authentication (2FA) enabled on your Coinbase account
- Basic understanding of API keys and security practices

## Creating API Keys

1. **Log in to your Coinbase account**
   - Go to [https://www.coinbase.com/](https://www.coinbase.com/) and log in

2. **Navigate to API settings**
   - Click on your profile icon in the top-right corner
   - Select "Settings"
   - Click on "API" in the left sidebar
   - You may need to verify your identity again for security purposes

3. **Create a new API key**
   - Click on "New API Key"
   - You'll be prompted to enter your 2FA code

4. **Configure API key permissions**
   - Select the following permissions:
     - ✅ View permissions (required)
     - ✅ Trade permissions (required for executing trades)
     - ❌ Transfer permissions (not recommended for security reasons)
   - Set appropriate IP address restrictions (recommended for security)
   - Give your API key a descriptive name (e.g., "Trading Bot")

5. **Complete the API key creation**
   - Click "Create API Key"
   - You'll be shown your API key, API secret, and passphrase
   - **IMPORTANT**: Store these securely! You won't be able to see the API secret again.

## Configuring the Trading Bot

1. **Update your environment variables**
   - Open your `.env` file or create one if it doesn't exist
   - Add the following variables:
   ```
   COINBASE_API_KEY=your_api_key_here
   COINBASE_API_SECRET=your_api_secret_here
   COINBASE_PASSPHRASE=your_passphrase_here
   COINBASE_SANDBOX=True  # Set to False for live trading
   ```

2. **Using the migration utility**
   - If you're migrating from Alpaca, you can use the provided migration utility:
   ```
   python tools/alpaca_to_coinbase_migration.py --output-env .env.coinbase
   ```
   - Review the generated `.env.coinbase` file and update the placeholder values
   - Once verified, you can apply the changes:
   ```
   python tools/alpaca_to_coinbase_migration.py --apply
   ```

3. **Testing your configuration**
   - Run the bot in sandbox mode first:
   ```
   python run_coinbase_bot.py --sandbox
   ```
   - Verify that the bot can connect to the Coinbase API and fetch market data

## Sandbox vs. Live Environment

Coinbase provides a sandbox environment for testing your API integration without using real funds.

### Sandbox Environment
- URL: `https://api-public.sandbox.exchange.coinbase.com`
- Requires separate API keys created in the sandbox
- Uses test funds, not real money
- Perfect for development and testing

### Live Environment
- URL: `https://api.exchange.coinbase.com`
- Uses your actual Coinbase account and real funds
- Be extremely careful when trading with real money

### Switching Between Environments
- Set `COINBASE_SANDBOX=True` for sandbox mode
- Set `COINBASE_SANDBOX=False` for live trading
- You can also use the `--sandbox` command-line flag:
  ```
  python run_coinbase_bot.py --sandbox  # For sandbox mode
  python run_coinbase_bot.py  # For live trading
  ```

## Security Best Practices

1. **Restrict API key permissions**
   - Only enable the permissions your bot needs
   - Never enable transfer permissions unless absolutely necessary

2. **Use IP restrictions**
   - Limit API access to specific IP addresses where your bot runs

3. **Secure your API credentials**
   - Never commit API keys to version control
   - Use environment variables or secure credential storage
   - Rotate your API keys periodically

4. **Start small**
   - Begin with small trade amounts until you're confident in your setup
   - Gradually increase position sizes as you gain confidence

5. **Monitor your bot**
   - Regularly check your bot's performance and account balance
   - Set up alerts for unusual activity

## Next Steps

- Review the [Coinbase Advanced Trade API documentation](https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome)
- Configure your trading strategies for cryptocurrency markets
- Test thoroughly in the sandbox environment before going live