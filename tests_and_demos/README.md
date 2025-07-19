# Tests and Demos Archive

This folder contains test files, demo versions, and alternative implementations that are not part of the main trading system.

## 📁 **Contents**

### **Alpaca API Tests**
- `test_alpaca_connection.py` - Basic Alpaca API connection test
- `test_alpaca_simple.py` - Direct HTTP test for Alpaca API
- `test_alpaca_stocks.py` - Stock and ETF data testing
- `diagnose_alpaca.py` - Detailed Alpaca API diagnostics

### **Demo Bots**
- `demo_aggressive_bot.py` - Simulation-only demo with fake data
- `aggressive_trading_example.py` - Example implementation

### **Alternative Versions**
- `run_aggressive_bot_yahoo.py` - Yahoo Finance version (superseded by enhanced bot)
- `run_aggressive_bot.py` - Original aggressive bot (superseded)

## 🎯 **Usage**

These files are kept for reference and testing purposes. The main trading system uses the files in the parent directory.

To run any of these tests:
```bash
cd tests_and_demos
python3 test_alpaca_connection.py
python3 demo_aggressive_bot.py --capital 100 --cycles 20
```