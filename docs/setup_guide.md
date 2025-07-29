# Kraken Trading Bot Setup Guide

This guide will walk you through setting up the Enhanced Kraken Crypto Trading Bot from scratch.

## Prerequisites

### System Requirements
- **Python**: 3.8 or higher
- **Operating System**: macOS, Linux, or Windows
- **Memory**: Minimum 2GB RAM (4GB recommended)
- **Storage**: 1GB free space for logs and data
- **Internet**: Stable connection for API access

### Kraken Account Requirements
- Active Kraken account with API access enabled
- Sufficient funds for trading (minimum $100 recommended)
- API key with trading permissions
- Two-factor authentication enabled (recommended)

## Step 1: Clone and Setup Repository

```bash
# Clone the repository
git clone <repository-url>
cd crypto-trading-bot

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Kraken API Setup

### Creating API Keys

1. **Log into Kraken**:
   - Go to [Kraken.com](https://www.kraken.com)
   - Sign in to your account

2. **Navigate to API Settings**:
   - Click on your profile icon
   - Select "Security" → "API"

3. **Create New API Key**:
   - Click "Generate New Key"
   - Set a descriptive name (e.g., "Trading Bot")
   - **Required Permissions**:
     - ✅ Query Funds
     - ✅ Query Open Orders & Trades
     - ✅ Query Closed Orders & Trades
     - ✅ Query Ledger Entries
     - ✅ Create & Modify Orders
     - ✅ Cancel Orders
     - ✅ Access WebSockets API

4. **Security Settings**:
   - Set IP restrictions if using a fixed IP
   - Enable nonce window (recommended: 5000ms)
   - Save the API key and secret securely

### API Key Security Best Practices

- **Never share** your API keys
- **Use environment variables** (never hardcode keys)
- **Enable IP restrictions** when possible
- **Regularly rotate** API keys
- **Monitor API usage** in Kraken dashboard
- **Use separate keys** for testing and production

## Step 3: Environment Configuration

### Create Environment File

```bash
# Copy the template
cp .env.template .env
```

### Configure Environment Variables

Edit the `.env` file with your settings:

```bash
# Kraken API Credentials
KRAKEN_API_KEY=your_api_key_here
KRAKEN_API_SECRET=your_api_secret_here

# Trading Configuration
IS_PAPER_TRADING=true
DEFAULT_TRADE_AMOUNT_USD=100.0
MAX_POSITION_PER_PAIR_USD=1000.0
MAX_TOTAL_POSITION_USD=5000.0

# Risk Management
RISK_PER_TRADE_PCT=0.02
MAX_DAILY_LOSS_PCT=0.05
EMERGENCY_STOP_LOSS_PCT=0.20

# Logging
LOG_LEVEL=INFO
LOG_TRADES=true
LOG_SIGNALS=true

# Dashboard
ENABLE_DASHBOARD=true
DASHBOARD_HOST=localhost
DASHBOARD_PORT=8080

# Alerts
ENABLE_ALERTS=true
ALERT_EMAIL=your_email@example.com
WEBHOOK_URL=https://your-webhook-url.com
```

### Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `KRAKEN_API_KEY` | Your Kraken API key | - | ✅ |
| `KRAKEN_API_SECRET` | Your Kraken API secret | - | ✅ |
| `IS_PAPER_TRADING` | Enable paper trading mode | `true` | ❌ |
| `DEFAULT_TRADE_AMOUNT_USD` | Default trade size in USD | `100.0` | ❌ |
| `MAX_POSITION_PER_PAIR_USD` | Max position per trading pair | `1000.0` | ❌ |
| `MAX_TOTAL_POSITION_USD` | Max total portfolio value | `5000.0` | ❌ |
| `RISK_PER_TRADE_PCT` | Risk per trade (0.02 = 2%) | `0.02` | ❌ |
| `MAX_DAILY_LOSS_PCT` | Max daily loss (0.05 = 5%) | `0.05` | ❌ |
| `LOG_LEVEL` | Logging level | `INFO` | ❌ |
| `ENABLE_DASHBOARD` | Enable web dashboard | `true` | ❌ |
| `DASHBOARD_PORT` | Dashboard port | `8080` | ❌ |

## Step 4: Configuration Setup

### Trading Pairs Configuration

Create or modify `config_examples/enhanced_trading_config.json`:

```json
{
  "trading_pairs": [
    {
      "symbol": "XBTUSD",
      "base_currency": "XBT",
      "quote_currency": "USD",
      "min_order_size": 0.0001,
      "enabled": true
    },
    {
      "symbol": "ETHUSD",
      "base_currency": "ETH",
      "quote_currency": "USD",
      "min_order_size": 0.001,
      "enabled": true
    }
  ],
  "strategy": {
    "momentum_weight": 0.3,
    "volatility_weight": 0.25,
    "volume_weight": 0.2,
    "min_signal_strength": 0.65
  },
  "risk": {
    "default_trade_amount_usd": 100.0,
    "max_position_per_pair_usd": 1000.0,
    "risk_per_trade_pct": 0.02,
    "enable_stop_loss": true,
    "default_stop_loss_pct": 0.03
  }
}
```

### Strategy Configuration

The bot supports multiple trading strategies with configurable weights:

- **Momentum Strategy**: Trend-following based on price momentum
- **Volatility Strategy**: Volatility breakout detection
- **Volume Strategy**: Volume-weighted price analysis
- **Bollinger Bands**: Mean reversion with volatility bands
- **MACD Strategy**: Moving average convergence divergence

## Step 5: Testing the Setup

### API Connection Test

```bash
# Test Kraken API connection
python test_kraken_api.py
```

Expected output:
```
✅ API connection successful
✅ Account balance retrieved
✅ Trading pairs validated
✅ WebSocket connection established
```

### Paper Trading Test

```bash
# Run in paper trading mode
python run_enhanced_bot.py --paper-trading --capital 1000
```

This will:
- Connect to Kraken API
- Start WebSocket data feed
- Begin paper trading simulation
- Display real-time dashboard

### Configuration Validation

```bash
# Validate configuration
python -c "from bot.config import Config; print('✅ Configuration valid')"
```

## Step 6: Running the Bot

### Basic Usage

```bash
# Paper trading (recommended for testing)
python run_enhanced_bot.py --paper-trading

# Real trading (use with caution)
python run_enhanced_bot.py
```

### Advanced Usage

```bash
# Multi-pair trading with custom settings
python run_enhanced_bot.py \
  --pairs XBTUSD,ETHUSD \
  --capital 5000 \
  --risk-per-trade 0.015 \
  --max-daily-loss 0.03

# High-frequency trading mode
python run_enhanced_bot.py \
  --interval 30 \
  --min-confidence 0.6 \
  --max-trades-per-day 100
```

## Step 7: Monitoring and Maintenance

### Dashboard Access

Once running, access the web dashboard at:
- **URL**: http://localhost:8080
- **Features**: Real-time portfolio, trade history, performance metrics

### Log Files

Monitor these log files:
- `logs/enhanced_bot.log` - General application logs
- `logs/trades.log` - Trade execution records
- `logs/signals.log` - Trading signal history
- `logs/errors.log` - Error and exception logs
- `logs/performance_metrics.log` - Performance analytics

### Health Monitoring

The bot includes built-in health checks:
- API connection status
- WebSocket connectivity
- Memory usage monitoring
- Trade execution latency
- Error rate tracking

## Troubleshooting

### Common Issues

1. **API Authentication Failed**
   ```
   Error: Invalid API key or signature
   ```
   - Verify API key and secret in `.env`
   - Check API permissions in Kraken dashboard
   - Ensure system time is synchronized

2. **WebSocket Connection Issues**
   ```
   Error: WebSocket connection failed
   ```
   - Check internet connectivity
   - Verify firewall settings
   - Try restarting the bot

3. **Insufficient Funds**
   ```
   Error: Insufficient funds for trade
   ```
   - Check account balance in Kraken
   - Reduce trade amounts in configuration
   - Verify currency availability

4. **Rate Limiting**
   ```
   Error: API rate limit exceeded
   ```
   - Increase interval between requests
   - Check for multiple bot instances
   - Review API usage in Kraken dashboard

### Getting Help

- **Documentation**: Check `docs/` directory
- **Logs**: Review error logs for detailed information
- **Configuration**: Validate settings with test scripts
- **Community**: Check project issues and discussions

## Security Checklist

Before going live:

- [ ] API keys stored securely in environment variables
- [ ] Two-factor authentication enabled on Kraken account
- [ ] IP restrictions configured (if applicable)
- [ ] Paper trading tested successfully
- [ ] Risk limits configured appropriately
- [ ] Emergency stop mechanisms tested
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery plan in place

## Next Steps

After successful setup:

1. **Start with Paper Trading**: Test strategies without risk
2. **Monitor Performance**: Track metrics and adjust parameters
3. **Gradual Scaling**: Start with small amounts and increase gradually
4. **Strategy Optimization**: Fine-tune parameters based on results
5. **Risk Management**: Regularly review and adjust risk limits

---

**⚠️ Important**: Always start with paper trading and small amounts. Cryptocurrency trading involves significant risk, and you should never trade with money you cannot afford to lose.