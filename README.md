# Enhanced Kraken Crypto Trading Bot

A sophisticated cryptocurrency trading bot with advanced features for automated trading on the Kraken exchange. The bot has been completely migrated from legacy APIs (Coinbase/Alpaca) to Kraken and enhanced with real-time WebSocket data, advanced trading strategies, comprehensive risk management, and professional monitoring capabilities.

## Features

### 🚀 Core Trading Features
- **Multi-Pair Trading**: Support for multiple cryptocurrency pairs simultaneously
- **Advanced Order Types**: Market, limit, stop-loss, take-profit, and trailing stop orders
- **Real-time Data**: WebSocket integration for live market data and order updates
- **Enhanced Strategies**: Momentum, volatility, volume-weighted, Bollinger Bands, and MACD strategies
- **Portfolio Management**: Intelligent position sizing and correlation-based risk assessment

### 🛡️ Risk Management
- **Dynamic Position Sizing**: Volatility-adjusted position calculations
- **Portfolio-level Limits**: Exposure limits and correlation analysis
- **Emergency Stops**: Automatic drawdown protection and circuit breakers
- **Multi-timeframe Analysis**: Cross-timeframe signal confirmation
- **Advanced Risk Metrics**: Real-time risk assessment and monitoring

### 📊 Monitoring & Analytics
- **Real-time Dashboard**: Web-based interface with live portfolio visualization
- **Enhanced Logging**: Structured JSON logging with performance metrics
- **Alert System**: Multi-channel notifications (email, webhook, console)
- **Performance Analytics**: Comprehensive trade analysis and reporting
- **System Health Monitoring**: Connection status and bot health metrics

### 🔧 Technical Features
- **Kraken API Integration**: Full REST and WebSocket API support
- **Connection Management**: Auto-reconnect with exponential backoff
- **Rate Limiting**: Intelligent request throttling and connection pooling
- **Error Recovery**: Robust error handling with circuit breaker patterns
- **Configuration Management**: Flexible JSON-based configuration system

## Quick Start

### Prerequisites
- **Python 3.8+** with pip
- **Kraken Account** with API access
- **2GB RAM** minimum (4GB recommended)
- **Stable Internet** connection

### Installation

```bash
# 1. Clone repository
git clone <repository-url>
cd crypto-trading-bot

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.template .env
# Edit .env with your Kraken API credentials
```

### Basic Setup

1. **Get Kraken API Keys**:
   - Log into Kraken → Security → API
   - Create new key with trading permissions
   - Copy API key and secret

2. **Configure Environment**:
   ```bash
   # Edit .env file
   KRAKEN_API_KEY=your_api_key_here
   KRAKEN_API_SECRET=your_api_secret_here
   IS_PAPER_TRADING=true  # Start with paper trading
   ```

3. **Test Connection**:
   ```bash
   python test_kraken_api.py
   ```

4. **Start Trading**:
   ```bash
   # Paper trading (recommended)
   python run_enhanced_bot.py --paper-trading
   
   # Real trading (use with caution)
   python run_enhanced_bot.py
   ```

## Usage Examples

### Paper Trading (Recommended for Testing)
```bash
# Basic paper trading
python run_enhanced_bot.py --paper-trading

# Multi-pair paper trading
python run_enhanced_bot.py --paper-trading --pairs XBTUSD,ETHUSD

# Aggressive paper trading
python run_enhanced_bot.py --paper-trading --capital 1000 --risk-per-trade 0.03
```

### Live Trading
```bash
# Conservative live trading
python run_enhanced_bot.py --capital 500 --risk-per-trade 0.01

# Multi-pair live trading
python run_enhanced_bot.py --pairs XBTUSD,ETHUSD,ADAUSD --capital 2000

# High-frequency trading
python run_enhanced_bot.py --interval 30 --max-trades-per-day 100
```

### Advanced Configuration
```bash
# Custom strategy weights
python run_enhanced_bot.py --momentum-weight 0.4 --volatility-weight 0.3

# Risk management focused
python run_enhanced_bot.py --max-daily-loss 0.02 --emergency-stop 0.15

# Performance optimization
python run_enhanced_bot.py --enable-caching --optimize-indicators
```

### Command-Line Options

#### Core Trading Options
- `--pairs`: Trading pairs (e.g., XBTUSD,ETHUSD)
- `--capital`: Starting capital in USD
- `--paper-trading`: Enable paper trading mode
- `--interval`: Trading interval in seconds (default: 60)
- `--max-trades-per-day`: Maximum trades per day

#### Risk Management
- `--risk-per-trade`: Risk per trade as percentage (0.02 = 2%)
- `--max-daily-loss`: Maximum daily loss percentage
- `--max-position-per-pair`: Maximum position size per pair
- `--emergency-stop`: Emergency stop loss percentage

#### Strategy Configuration
- `--momentum-weight`: Weight for momentum strategy
- `--volatility-weight`: Weight for volatility strategy
- `--volume-weight`: Weight for volume strategy
- `--min-signal-confidence`: Minimum signal confidence (0.0-1.0)

#### System Options
- `--enable-dashboard`: Enable web dashboard (default: true)
- `--dashboard-port`: Dashboard port (default: 8080)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `--config-file`: Path to configuration file

## Trading Strategies

### Moving Average Crossover

This strategy generates signals based on the crossing of two moving averages:
- **Buy Signal**: When the fast moving average crosses above the slow moving average
- **Sell Signal**: When the fast moving average crosses below the slow moving average
- **Parameters**:
  - `--ma-fast`: Period for the fast moving average (default: 10)
  - `--ma-slow`: Period for the slow moving average (default: 30)

### RSI Strategy

This strategy uses the Relative Strength Index (RSI) to identify overbought and oversold conditions:
- **Buy Signal**: When RSI crosses below the oversold threshold
- **Sell Signal**: When RSI crosses above the overbought threshold
- **Parameters**:
  - `--rsi-period`: Period for RSI calculation (default: 14)
  - `--rsi-oversold`: Oversold threshold (default: 30)
  - `--rsi-overbought`: Overbought threshold (default: 70)

### Creating Custom Strategies

To implement a custom strategy:

1. Create a new class that inherits from `BaseStrategy` in `bot/strategy.py`
2. Implement the `calculate_signals` method to generate trading signals
3. Add your strategy to the `strategies` list in `bot/main.py`

Example of a custom strategy:
```python
from bot.strategy import BaseStrategy

class CustomStrategy(BaseStrategy):
    def __init__(self, param1=10, param2=20):
        self.param1 = param1
        self.param2 = param2
        
    def calculate_signals(self, data):
        # Implement your strategy logic here
        # Return a dictionary with signal information
        return {
            'action': 'BUY',  # or 'SELL' or 'HOLD'
            'confidence': 0.8,
            'strategy': 'CustomStrategy',
            'reasoning': 'Custom strategy reasoning'
        }
```

## Dashboard

The bot includes a real-time dashboard that displays:

- **Market Data**: Current price and timestamp
- **Positions**: Current position size, value, entry price, and P&L
- **Trades**: Recent trade history with timestamps
- **Signals**: Recent trading signals from strategies
- **Errors**: Recent error messages

The dashboard updates in real-time as new data is received and trades are executed.

## Logging

The bot implements a comprehensive logging system:

- **Console Logging**: Colored output in the terminal
- **File Logging**:
  - `bot.log`: General application logs
  - `logs/trades.log`: Record of all executed trades
  - `logs/signals.log`: Record of all generated trading signals
  - `logs/errors.log`: Detailed error logs

You can configure the logging level using the `--log-level` option.

## Error Handling

The bot includes robust error handling mechanisms:

- **API Rate Limiting**: Exponential backoff with jitter
- **Network Errors**: Automatic retry with increasing delays
- **Data Validation**: Skip cycles with invalid data
- **Critical Errors**: Graceful shutdown and detailed logging

## Testing

Run the test suite to verify the bot's functionality:

```bash
pytest
```

Run specific test categories:

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/
```

## Documentation

### 📚 Complete Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](docs/setup_guide.md) | Complete installation and configuration guide |
| [User Guide](docs/user_guide.md) | Trading strategies and risk management guide |
| [API Documentation](docs/api_endpoints.md) | REST API and dashboard usage |
| [Developer Guide](docs/developer_guide.md) | Extending and customizing the bot |
| [Troubleshooting](docs/troubleshooting_guide.md) | Common issues and solutions |

### 🎯 Quick Links

- **New Users**: Start with [Setup Guide](docs/setup_guide.md)
- **Strategy Configuration**: See [User Guide](docs/user_guide.md)
- **API Integration**: Check [API Documentation](docs/api_endpoints.md)
- **Issues**: Consult [Troubleshooting Guide](docs/troubleshooting_guide.md)
- **Development**: Read [Developer Guide](docs/developer_guide.md)

### 📊 Dashboard Access

Once running, access the web dashboard at:
- **URL**: http://localhost:8080
- **Features**: Real-time portfolio, performance metrics, manual trading
- **Mobile**: Responsive design works on mobile devices

## Configuration Files

### Environment Variables (.env)
```bash
# Kraken API
KRAKEN_API_KEY=your_api_key
KRAKEN_API_SECRET=your_api_secret

# Trading Settings
IS_PAPER_TRADING=true
DEFAULT_TRADE_AMOUNT_USD=100.0
MAX_DAILY_LOSS_PCT=0.05

# System Settings
LOG_LEVEL=INFO
ENABLE_DASHBOARD=true
DASHBOARD_PORT=8080
```

### Trading Configuration (config_examples/enhanced_trading_config.json)
```json
{
  "trading_pairs": [
    {"symbol": "XBTUSD", "enabled": true},
    {"symbol": "ETHUSD", "enabled": true}
  ],
  "strategy": {
    "momentum_weight": 0.3,
    "volatility_weight": 0.25,
    "min_signal_strength": 0.65
  },
  "risk": {
    "risk_per_trade_pct": 0.02,
    "max_daily_loss_pct": 0.05,
    "enable_stop_loss": true
  }
}
```

## Supported Trading Pairs

The bot supports all major Kraken cryptocurrency pairs:

### Major Pairs
- **XBTUSD** - Bitcoin/USD
- **ETHUSD** - Ethereum/USD
- **ADAUSD** - Cardano/USD
- **SOLUSD** - Solana/USD
- **MATICUSD** - Polygon/USD

### Additional Pairs
- **XBTEUR** - Bitcoin/EUR
- **ETHEUR** - Ethereum/EUR
- **LINKUSD** - Chainlink/USD
- **DOTUSD** - Polkadot/USD
- **AVAXUSD** - Avalanche/USD

*See [Kraken API documentation](https://docs.kraken.com/rest/#tag/Market-Data/operation/getTradableAssetPairs) for complete list*

## Performance Metrics

The bot tracks comprehensive performance metrics:

### Portfolio Metrics
- **Total Return**: Overall portfolio performance
- **Sharpe Ratio**: Risk-adjusted returns
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of gross profit to gross loss

### Risk Metrics
- **Value at Risk (VaR)**: Potential loss at confidence level
- **Portfolio Beta**: Correlation with market movements
- **Position Concentration**: Exposure to individual assets
- **Correlation Risk**: Risk from correlated positions

### System Metrics
- **API Latency**: Response time for API calls
- **Execution Speed**: Time from signal to trade execution
- **Error Rate**: Percentage of failed operations
- **Uptime**: System availability percentage

## Security Features

### API Security
- ✅ Secure credential storage in environment variables
- ✅ API key permissions validation
- ✅ Request signing and authentication
- ✅ Rate limiting and connection pooling
- ✅ IP restrictions support

### Trading Security
- ✅ Paper trading mode for testing
- ✅ Position size limits and validation
- ✅ Emergency stop mechanisms
- ✅ Trade confirmation and logging
- ✅ Risk limit enforcement

### System Security
- ✅ Input validation and sanitization
- ✅ Secure logging (no sensitive data)
- ✅ Error handling without information disclosure
- ✅ Audit trail for all operations

## Monitoring and Alerts

### Real-time Monitoring
- **System Health**: CPU, memory, disk usage
- **API Connectivity**: REST and WebSocket status
- **Trading Performance**: Live P&L and metrics
- **Error Tracking**: Real-time error monitoring

### Alert Channels
- **Console**: Terminal notifications
- **Email**: SMTP email alerts
- **Webhook**: HTTP POST notifications
- **Dashboard**: Web interface alerts

### Alert Types
- **Trade Execution**: Buy/sell confirmations
- **Risk Events**: Limit breaches and warnings
- **System Events**: Errors and status changes
- **Performance**: Daily/weekly reports

## Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Verify API credentials in `.env`
   - Check API permissions in Kraken dashboard
   - Ensure system time is synchronized

2. **WebSocket Disconnections**
   - Check internet connectivity
   - Verify firewall settings
   - Review WebSocket configuration

3. **Trading Errors**
   - Confirm sufficient account balance
   - Check trading pair availability
   - Verify order parameters

4. **Performance Issues**
   - Monitor system resources
   - Adjust data retention settings
   - Optimize strategy parameters

### Getting Help

- **Documentation**: Check relevant guide in `docs/`
- **Logs**: Review error logs in `logs/` directory
- **Configuration**: Validate settings with test scripts
- **Support**: Create issue with diagnostic information

## Disclaimer

⚠️ **Important Risk Warning**

This software is for educational and research purposes. Cryptocurrency trading involves substantial risk of loss and is not suitable for all investors. Key risks include:

- **Market Risk**: Cryptocurrency prices are highly volatile
- **Technical Risk**: Software bugs or system failures
- **Regulatory Risk**: Changing regulations may affect trading
- **Liquidity Risk**: Difficulty executing trades in volatile markets

**Never trade with money you cannot afford to lose. Always start with paper trading and small amounts.**

### Legal Notice

- This software is provided "as is" without warranty
- Authors are not responsible for any financial losses
- Users are responsible for compliance with local regulations
- Past performance does not guarantee future results

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions! Please see our [Developer Guide](docs/developer_guide.md) for:

- Code style guidelines
- Testing requirements
- Pull request process
- Development setup

---

**Built with ❤️ for the crypto trading community**