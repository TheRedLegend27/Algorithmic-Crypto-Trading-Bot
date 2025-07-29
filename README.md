# Enhanced Kraken Crypto Trading Bot

A production-ready cryptocurrency trading bot with enterprise-grade features for automated trading on the Kraken exchange. Completely migrated from legacy APIs to Kraken with comprehensive enhancements including real-time WebSocket data, advanced multi-strategy trading, sophisticated risk management, and professional monitoring capabilities.

## 🎉 **FULLY INTEGRATED & PRODUCTION READY** 

✅ **Complete Kraken Migration** - Full REST and WebSocket API integration  
✅ **Enhanced Components** - All advanced features integrated and tested  
✅ **Real-time Dashboard** - Professional web interface with live monitoring  
✅ **Multi-pair Trading** - Simultaneous trading across multiple cryptocurrency pairs  
✅ **Advanced Risk Management** - Portfolio-level risk assessment and protection  
✅ **Comprehensive Testing** - Full integration and performance validation completed

## 🚀 Features

### ⚡ **Enhanced Trading Engine**
- **Multi-Pair Trading**: Simultaneous trading across multiple cryptocurrency pairs with intelligent coordination
- **Advanced Strategies**: Moving Average Crossover, RSI, Momentum, and Volume-weighted strategies
- **Real-time Execution**: WebSocket-powered live market data with sub-second trade execution
- **Smart Order Management**: Market, limit, and advanced order types with intelligent routing
- **Portfolio Optimization**: Dynamic position sizing with correlation-based risk assessment

### 🛡️ **Advanced Risk Management**
- **Enhanced Risk Manager**: Portfolio-level exposure limits with real-time monitoring
- **Dynamic Position Sizing**: Volatility-adjusted calculations with confidence-based scaling
- **Emergency Protection**: Automatic drawdown protection and circuit breaker mechanisms
- **Multi-timeframe Analysis**: Cross-timeframe signal confirmation and validation
- **Correlation Analysis**: Real-time portfolio correlation monitoring and adjustment

### 📊 **Professional Monitoring**
- **Enhanced Dashboard**: Real-time web interface with live portfolio visualization at http://localhost:8080
- **Structured Logging**: JSON-formatted logs with performance metrics and trade tracking
- **Multi-channel Alerts**: Email, webhook, and console notifications with intelligent throttling
- **Performance Analytics**: Comprehensive trade analysis, Sharpe ratio, and drawdown metrics
- **System Health**: Real-time monitoring of API connectivity, memory usage, and bot performance

### 🔧 **Enterprise Architecture**
- **Enhanced Data Manager**: Intelligent caching, data validation, and quality scoring
- **WebSocket Integration**: Real-time market data with automatic reconnection and error recovery
- **Connection Pooling**: Optimized API connections with rate limiting and circuit breakers
- **Modular Design**: Pluggable components for strategies, risk management, and data sources
- **Configuration System**: Flexible JSON-based configuration with environment variable support

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** with pip
- **Kraken Account** with API access enabled
- **4GB RAM** minimum (8GB recommended for multi-pair trading)
- **Stable Internet** connection with low latency

### Installation

```bash
# 1. Clone repository
git clone <repository-url>
cd crypto-scalping-bot-kiro

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.template .env
# Edit .env with your Kraken API credentials
```

### Setup & Configuration

1. **Get Kraken API Keys**:
   - Log into Kraken → Security → API
   - Create new key with these permissions:
     - ✅ Query Funds
     - ✅ Query Open Orders & Trades
     - ✅ Query Closed Orders & Trades
     - ✅ Query Ledger Entries
     - ✅ Create & Modify Orders (for live trading)

2. **Configure Environment**:
   ```bash
   # Edit .env file
   KRAKEN_API_KEY=your_actual_api_key
   KRAKEN_API_SECRET=your_actual_api_secret
   IS_PAPER_TRADING=true  # Always start with paper trading
   ```

3. **Test Your Setup**:
   ```bash
   # Test API connection and credentials
   python test_kraken_setup.py
   
   # Debug market data if needed
   python debug_market_data.py
   ```

4. **Start the Enhanced Bot**:
   ```bash
   # Paper trading (recommended for testing)
   python run_enhanced_kraken_bot.py --paper-trading
   
   # Multi-pair paper trading
   python run_enhanced_kraken_bot.py --paper-trading --pairs XBTUSD XETHZUSD
   
   # Real trading (use with extreme caution)
   python run_enhanced_kraken_bot.py --pairs XBTUSD
   ```

### 📊 **Dashboard Access**
Once running, access the real-time dashboard at:
- **URL**: http://localhost:8080
- **Features**: Live portfolio, trade history, performance metrics, system health
- **Mobile**: Responsive design works on all devices

## 💡 Usage Examples

### Paper Trading (Recommended for Testing)
```bash
# Basic paper trading with dashboard
python run_enhanced_kraken_bot.py --paper-trading

# Multi-pair paper trading
python run_enhanced_kraken_bot.py --paper-trading --pairs XBTUSD XETHZUSD

# Aggressive paper trading with custom settings
python run_enhanced_kraken_bot.py --paper-trading --trade-amount 50 --confidence 0.4 --max-trades 30
```

### Live Trading (Use with Caution)
```bash
# Conservative live trading
python run_enhanced_kraken_bot.py --pairs XBTUSD --trade-amount 10 --confidence 0.5

# Multi-pair live trading
python run_enhanced_kraken_bot.py --pairs XBTUSD XETHZUSD --trade-amount 25 --max-position 100

# High-frequency trading
python run_enhanced_kraken_bot.py --pairs XBTUSD --interval 30 --max-trades 50
```

### Advanced Configuration
```bash
# Custom dashboard port
python run_enhanced_kraken_bot.py --paper-trading --dashboard-port 8081

# Disable dashboard and alerts
python run_enhanced_kraken_bot.py --paper-trading --no-dashboard --no-alerts

# Verbose logging for debugging
python run_enhanced_kraken_bot.py --paper-trading --verbose
```

### System Testing & Validation
```bash
# Run comprehensive integration tests
python run_final_integration_test.py --trading-pairs XBTUSD

# Performance validation
python validate_system_performance.py --trading-pairs XBTUSD --api-test-calls 20

# Full system integration test
python run_integrated_system_test.py --trading-pairs XBTUSD
```

### 🎛️ Command-Line Options

#### Core Trading Options
- `--pairs`: Trading pairs (space-separated, e.g., XBTUSD XETHZUSD)
- `--trade-amount`: Trade amount in USD per trade (default: 10.0)
- `--max-position`: Maximum position size in USD (default: 100.0)
- `--paper-trading`: Enable paper trading mode (recommended for testing)
- `--interval`: Trading interval in seconds (default: 60)
- `--max-trades`: Maximum trades per day (default: 20)

#### Risk Management
- `--confidence`: Minimum signal confidence threshold (default: 0.3)
- `--max-position`: Maximum position size per pair in USD
- Emergency stops and drawdown protection built-in

#### System Options
- `--dashboard-port`: Dashboard port (default: 8080)
- `--no-dashboard`: Disable web dashboard
- `--no-alerts`: Disable alert system
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `--verbose`: Enable verbose logging (same as --log-level DEBUG)

#### Examples
```bash
# Conservative setup
python run_enhanced_kraken_bot.py --paper-trading --trade-amount 10 --confidence 0.5

# Aggressive setup
python run_enhanced_kraken_bot.py --paper-trading --trade-amount 50 --confidence 0.3 --max-trades 50

# Multi-pair setup
python run_enhanced_kraken_bot.py --paper-trading --pairs XBTUSD XETHZUSD --trade-amount 25
```

## 🧠 Enhanced Trading Strategies

### **Integrated Strategy Engine**
The bot uses an enhanced strategy engine that combines multiple strategies with intelligent weighting and confidence scoring.

### **Moving Average Crossover Strategy**
Advanced implementation with dynamic period adjustment:
- **Buy Signal**: Fast MA crosses above slow MA with volume confirmation
- **Sell Signal**: Fast MA crosses below slow MA with momentum validation
- **Features**: Adaptive periods, false signal filtering, trend strength analysis
- **Parameters**: Fast period (10), Slow period (30), Volume threshold

### **RSI Strategy with Enhancements**
Sophisticated RSI implementation with multi-timeframe analysis:
- **Buy Signal**: RSI oversold with divergence confirmation
- **Sell Signal**: RSI overbought with momentum exhaustion
- **Features**: Dynamic thresholds, divergence detection, trend filtering
- **Parameters**: Period (14), Oversold (30), Overbought (70)

### **Enhanced Strategy Features**
- **Multi-timeframe Analysis**: Cross-timeframe signal confirmation
- **Volume Validation**: Volume-weighted signal strength
- **Volatility Adjustment**: Dynamic parameters based on market volatility
- **Confidence Scoring**: Probabilistic signal strength assessment
- **Strategy Coordination**: Intelligent combination of multiple strategies

### **Creating Custom Strategies**

The enhanced framework supports custom strategy development:

```python
from bot.crypto_strategies import BaseCryptoStrategy

class CustomEnhancedStrategy(BaseCryptoStrategy):
    def __init__(self, custom_param=20):
        super().__init__("CustomEnhanced")
        self.custom_param = custom_param
        
    def calculate_signals(self, data):
        # Enhanced signal calculation with confidence scoring
        signal_strength = self._calculate_signal_strength(data)
        
        return TradingSignal(
            action=SignalType.BUY if signal_strength > 0.5 else SignalType.HOLD,
            confidence=signal_strength,
            price=data['close'].iloc[-1],
            timestamp=time.time(),
            strategy=self.name,
            reasoning=f"Custom analysis with strength {signal_strength:.3f}"
        )
```

### **Strategy Performance Tracking**
- Real-time performance metrics for each strategy
- Win rate and profit factor analysis
- Strategy weight adjustment based on performance
- Backtesting capabilities with historical data

## 📊 Enhanced Dashboard

### **Real-time Web Interface**
Access the professional dashboard at **http://localhost:8080** with:

#### **Portfolio Overview**
- **Live Portfolio Value**: Real-time total portfolio value with P&L
- **Position Details**: Current positions with entry prices and unrealized P&L
- **Asset Allocation**: Visual breakdown of portfolio composition
- **Performance Metrics**: Daily, weekly, and total returns

#### **Trading Activity**
- **Live Trade Feed**: Real-time trade execution notifications
- **Signal Analysis**: Strategy signals with confidence scores and reasoning
- **Order Management**: Active orders and execution status
- **Trade History**: Comprehensive trade log with filtering

#### **Market Data**
- **Real-time Prices**: Live price feeds for all trading pairs
- **Market Depth**: Order book visualization
- **Price Charts**: Interactive candlestick charts with indicators
- **Volume Analysis**: Trading volume and market activity

#### **System Monitoring**
- **Bot Health**: System status, uptime, and performance metrics
- **API Status**: Connection status for REST and WebSocket APIs
- **Error Tracking**: Real-time error monitoring and alerts
- **Resource Usage**: CPU, memory, and network utilization

#### **Risk Management**
- **Risk Metrics**: Real-time risk assessment and exposure analysis
- **Drawdown Monitoring**: Current and maximum drawdown tracking
- **Position Limits**: Visual representation of position size limits
- **Correlation Matrix**: Portfolio correlation analysis

### **Dashboard Features**
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Real-time Updates**: WebSocket-powered live data updates
- **Interactive Charts**: Zoom, pan, and analyze market data
- **Export Capabilities**: Download trade history and performance reports
- **Dark/Light Theme**: Customizable interface themes

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

## 🧪 Testing & Validation

### **Comprehensive Test Suite**

The bot includes extensive testing capabilities to ensure reliability and performance:

#### **Integration Testing**
```bash
# Complete system integration test
python run_final_integration_test.py --trading-pairs XBTUSD --verbose

# Full integration with multiple components
python run_integrated_system_test.py --trading-pairs XBTUSD XETHZUSD

# Performance validation under load
python validate_system_performance.py --api-test-calls 50 --strategy-iterations 20
```

#### **Unit Testing**
```bash
# Run all unit tests
pytest tests/unit/ -v

# Test specific components
pytest tests/unit/test_enhanced_strategies.py
pytest tests/unit/test_enhanced_risk_manager.py
pytest tests/unit/test_enhanced_data_manager.py
```

#### **Integration Testing**
```bash
# Run all integration tests
pytest tests/integration/ -v

# Test specific integrations
pytest tests/integration/test_kraken_api_integration.py
pytest tests/integration/test_multi_pair_trading_coordination.py
pytest tests/integration/test_enhanced_main_integration.py
```

#### **API Testing**
```bash
# Test Kraken API setup and connectivity
python test_kraken_setup.py

# Debug market data retrieval
python debug_market_data.py

# Test WebSocket connections
python examples/websocket_demo.py
```

### **Test Coverage**
- **API Integration**: REST and WebSocket connectivity
- **Strategy Engine**: Signal generation and validation
- **Risk Management**: Portfolio risk assessment
- **Data Management**: Caching and data quality
- **Dashboard**: Web interface and real-time updates
- **Error Recovery**: System resilience and recovery
- **Performance**: Load testing and optimization

### **Continuous Testing**
```bash
# Run full test suite with coverage
pytest --cov=bot tests/ --cov-report=html

# Performance benchmarking
python -m pytest tests/integration/test_performance_and_load.py -v

# End-to-end trading simulation
python -m pytest tests/integration/test_end_to_end_trading.py -v
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

## ⚠️ Important Disclaimers

### **Risk Warning**

**CRYPTOCURRENCY TRADING INVOLVES SUBSTANTIAL RISK OF LOSS**

This software is provided for educational and research purposes. Key risks include:

- **Market Risk**: Cryptocurrency prices are extremely volatile and unpredictable
- **Technical Risk**: Software bugs, system failures, or connectivity issues
- **Regulatory Risk**: Changing regulations may affect trading legality
- **Liquidity Risk**: Difficulty executing trades during volatile market conditions
- **API Risk**: Exchange API changes or downtime affecting bot operations

### **Safety Guidelines**

✅ **ALWAYS start with paper trading mode**  
✅ **Never trade with money you cannot afford to lose**  
✅ **Start with small amounts and gradually increase**  
✅ **Monitor the bot actively, especially during volatile markets**  
✅ **Keep API keys secure and use appropriate permissions**  
✅ **Regularly review and adjust risk parameters**  

### **Legal Notice**

- This software is provided "AS IS" without warranty of any kind
- Authors and contributors are NOT responsible for any financial losses
- Users are solely responsible for compliance with local regulations
- Past performance does NOT guarantee future results
- Trading decisions are made at your own risk and discretion

### **Production Readiness**

While this bot has undergone comprehensive testing and integration validation, users should:

1. **Thoroughly test** in paper trading mode before live trading
2. **Start with minimal capital** to validate performance
3. **Monitor system performance** and adjust parameters as needed
4. **Keep the software updated** with latest security patches
5. **Maintain proper risk management** at all times

**The bot is production-ready but requires responsible usage and proper risk management.**

## License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

We welcome contributions to improve the Enhanced Kraken Trading Bot! 

### **Development Setup**
```bash
# Clone and setup development environment
git clone <repository-url>
cd crypto-scalping-bot-kiro
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

### **Contribution Guidelines**
- **Code Style**: Follow PEP 8 and use type hints
- **Testing**: Add tests for new features and ensure all tests pass
- **Documentation**: Update relevant documentation and docstrings
- **Pull Requests**: Create detailed PRs with clear descriptions

### **Development Resources**
- [Developer Guide](docs/developer_guide.md) - Detailed development instructions
- [API Documentation](docs/api_endpoints.md) - REST API and WebSocket documentation
- [Architecture Overview](docs/architecture.md) - System design and component interaction

### **Areas for Contribution**
- 🧠 **Strategy Development**: New trading strategies and indicators
- 🛡️ **Risk Management**: Enhanced risk assessment algorithms
- 📊 **Analytics**: Advanced performance metrics and reporting
- 🔧 **Infrastructure**: Performance optimizations and monitoring
- 📱 **UI/UX**: Dashboard improvements and mobile optimization

---

## 🎯 Project Status

### **✅ COMPLETED FEATURES**
- ✅ **Complete Kraken Migration** - Full REST and WebSocket API integration
- ✅ **Enhanced Components** - All advanced features integrated and tested
- ✅ **Multi-pair Trading** - Simultaneous trading across multiple pairs
- ✅ **Real-time Dashboard** - Professional web interface with live monitoring
- ✅ **Advanced Risk Management** - Portfolio-level risk assessment and protection
- ✅ **Comprehensive Testing** - Full integration and performance validation
- ✅ **Production Ready** - Stable, tested, and ready for live trading

### **🚀 READY FOR USE**
The Enhanced Kraken Trading Bot is now **fully integrated, comprehensively tested, and production-ready** for both paper and live trading with professional-grade features and monitoring capabilities.

---

**Built with ❤️ for the crypto trading community**  
**Enhanced with 🧠 for intelligent automated trading**  
**Secured with 🛡️ for professional risk management**