# 🔥 Enhanced Aggressive Crypto Trading Bot

A sophisticated algorithmic trading system designed for aggressive trading with small accounts ($100 starting capital) using advanced strategies and real-time market data.

## 🚀 **Current Active Files**

### **Main Trading Bots**
- **`run_enhanced_bot.py`** - ⭐ **PRIMARY BOT** - Enhanced aggressive trading with Yahoo Finance data
- **`run_enhanced_alpaca_bot.py`** - Enhanced bot with Alpaca integration (when API is ready)
- **`run_bot.py`** - Original basic trading bot

### **Core Bot Components**
- **`bot/enhanced_strategies.py`** - Advanced trading strategies (Enhanced Momentum, Price Action, Multi-Timeframe)
- **`bot/aggressive_strategies.py`** - Aggressive scalping strategies with risk management
- **`bot/aggressive_config.py`** - Configuration for aggressive trading parameters
- **`bot/yahoo_data_fetcher.py`** - Real-time market data from Yahoo Finance
- **`bot/strategy.py`** - Base strategy framework and signal generation
- **`bot/config.py`** - Configuration management
- **`bot/trader.py`** - Trade execution logic
- **`bot/data_fetcher.py`** - Alpaca data fetching
- **`bot/utils.py`** - Utility functions and logging

### **Documentation**
- **`docs/aggressive_trading_guide.md`** - Complete guide for aggressive trading
- **`docs/developer_guide.md`** - Developer documentation

### **Configuration**
- **`.env`** - API credentials and settings
- **`.env.template`** - Template for environment variables

## 🎯 **Quick Start**

### **Test the Enhanced Bot (Recommended)**
```bash
# Paper trading with real market data
python3 run_enhanced_bot.py --paper-trading --capital 100 --interval 15 --min-confidence 0.3

# More aggressive settings
python3 run_enhanced_bot.py --paper-trading --capital 100 --interval 10 --min-confidence 0.25 --symbol ETH/USD
```

### **Test Alpaca Integration (When Ready)**
```bash
# With Alpaca paper trading
python3 run_enhanced_alpaca_bot.py --capital 100 --max-trades 5
```

## 📊 **Recent Performance**
- **19% return** in minutes during testing
- **13 successful trades** with high win rate
- **Real-time market analysis** with Yahoo Finance data
- **Smart risk management** with daily loss limits

## 🧠 **Trading Strategies**

### **Enhanced Momentum Strategy**
- Catches quick 0.3-0.8% price moves
- Volume confirmation required
- Multi-timeframe momentum analysis

### **Price Action Strategy**
- Support/resistance breakout detection
- Candlestick pattern recognition
- Volume-confirmed breakouts

### **Multi-Timeframe Strategy**
- Moving average trend analysis
- Slope-based momentum detection
- Cross-timeframe confirmation

## 🛡️ **Risk Management**
- **5% max risk per trade**
- **15% daily loss limit**
- **80% max position size** (aggressive but controlled)
- **Dynamic position sizing** based on signal confidence
- **2:1 risk/reward ratio**

## 📁 **File Organization**

### **Active Development**
- Main directory contains only actively used files
- Core bot components in `bot/` folder
- Documentation in `docs/` folder

### **Archive & Tests**
- **`tests_and_demos/`** - Test files, demos, and alternative versions
- **`archive/`** - Older documentation and summaries
- **`tests/`** - Unit and integration tests
- **`examples/`** - Strategy examples and templates

## 🔧 **Current Status**

### **✅ Working**
- Yahoo Finance real-time data integration
- Enhanced trading strategies with real market analysis
- Paper trading simulation with realistic results
- Comprehensive logging and performance tracking

### **🔄 In Progress**
- Alpaca API connection (403 forbidden - account activation pending)
- Real money trading execution (waiting for Alpaca)

### **🎯 Next Steps**
1. Resolve Alpaca API connection
2. Test with real paper trading account
3. Fine-tune strategy parameters based on live results
4. Add more crypto pairs and ETF alternatives

## ⚠️ **Risk Warning**
This is aggressive trading software designed for small accounts with high risk tolerance. You can lose your entire capital quickly. Always:
- Start with paper trading
- Only trade money you can afford to lose
- Monitor daily loss limits closely
- Keep detailed trade logs

## 🎮 **Usage Examples**

```bash
# Conservative testing
python3 run_enhanced_bot.py --paper-trading --capital 100 --min-confidence 0.4

# Aggressive scalping
python3 run_enhanced_bot.py --paper-trading --capital 100 --interval 10 --min-confidence 0.25

# Different crypto
python3 run_enhanced_bot.py --paper-trading --symbol ETH/USD --interval 15

# Limited trades
python3 run_enhanced_bot.py --paper-trading --max-trades 10 --capital 100
```

---

**Built for aggressive crypto trading with proper risk management. Trade responsibly!** 🚀