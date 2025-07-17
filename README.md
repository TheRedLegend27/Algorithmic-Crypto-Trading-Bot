# Crypto Trading Bot

A cryptocurrency trading bot that uses technical analysis strategies to automate trading on the Alpaca API.

## Features

- Automated trading based on technical indicators
- Multiple trading strategies (Moving Average Crossover, RSI)
- Real-time dashboard with trading activity
- Configurable trading parameters
- Error recovery and graceful shutdown
- Paper trading support for risk-free testing

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/crypto-trading-bot.git
   cd crypto-trading-bot
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   ```
   cp .env.template .env
   ```
   Edit the `.env` file with your Alpaca API credentials.

## Usage

Run the bot with default settings:
```
python run_bot.py
```

### Command-line Options

- `--symbol`: Trading symbol (default: BTC/USD)
- `--interval`: Trading interval in minutes (default: 5)
- `--amount`: Amount to trade in USD (default: 10.0)
- `--max-position`: Maximum position size in USD (default: 100.0)
- `--stop-loss`: Stop loss percentage (default: 0.05)
- `--take-profit`: Take profit percentage (default: 0.1)
- `--no-dashboard`: Disable rich dashboard display

Example:
```
python run_bot.py --symbol ETH/USD --interval 15 --amount 20.0
```

## Trading Strategies

### Moving Average Crossover

This strategy generates buy signals when the fast moving average crosses above the slow moving average, and sell signals when the fast moving average crosses below the slow moving average.

### RSI Strategy

This strategy generates buy signals when the RSI indicator crosses below the oversold threshold (default: 30), and sell signals when it crosses above the overbought threshold (default: 70).

## Dashboard

The bot includes a real-time dashboard that displays:
- Current market data
- Active positions
- Recent trades
- Trading signals
- Error messages

Press Ctrl+C to gracefully exit the bot.

## Disclaimer

This bot is for educational purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred from using this software.

## License

MIT