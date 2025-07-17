# Crypto Trading Bot

A modular cryptocurrency trading bot that uses technical analysis strategies to automate trading on the Alpaca API. The bot implements multiple trading strategies, provides real-time monitoring through a rich terminal interface, and includes comprehensive error handling and recovery mechanisms.

## Features

- **Automated Trading**: Execute trades automatically based on technical indicators
- **Multiple Trading Strategies**: 
  - Moving Average Crossover strategy
  - RSI (Relative Strength Index) strategy
  - Easily extendable to add custom strategies
- **Real-time Dashboard**: Rich terminal interface showing prices, positions, signals, and trades
- **Comprehensive Logging**: Colored console output and persistent file logging
- **Configurable Parameters**: Customize trading behavior through command-line options
- **Error Recovery**: Robust error handling with exponential backoff retry mechanisms
- **Paper Trading Support**: Test strategies without risking real money
- **Position Management**: Accurate tracking of crypto positions with reconciliation
- **Scheduled Execution**: Run trading cycles at configurable intervals

## System Requirements

- Python 3.8 or higher
- Internet connection for API access
- Alpaca API account with crypto trading enabled

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/crypto-trading-bot.git
   cd crypto-trading-bot
   ```

2. Create and activate a virtual environment:
   ```bash
   # On macOS/Linux
   python -m venv .venv
   source .venv/bin/activate
   
   # On Windows
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   ```bash
   cp .env.template .env
   ```
   Edit the `.env` file with your Alpaca API credentials:
   ```
   ALPACA_API_KEY=your_api_key_here
   ALPACA_SECRET_KEY=your_secret_key_here
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   IS_PAPER_TRADING=True
   ```

## Usage

### Basic Usage

Run the bot with default settings:
```bash
python run_bot.py
```

This will start the bot with the following default configuration:
- Trading symbol: BTC/USD
- Trading interval: 5 minutes
- Trade amount: $10.0
- Maximum position size: $100.0
- Stop loss: 5%
- Take profit: 10%

### Command-line Options

The bot supports numerous command-line options to customize its behavior:

#### Trading Configuration
- `--symbol`: Trading symbol (default: BTC/USD)
- `--amount`: Amount to trade in USD (default: 10.0)
- `--max-position`: Maximum position size in USD (default: 100.0)
- `--stop-loss`: Stop loss percentage (default: 0.05)
- `--take-profit`: Take profit percentage (default: 0.1)

#### Scheduling Options
- `--interval`: Trading interval in minutes (default: 5)
- `--start-delay`: Delay in seconds before starting the first trading cycle (default: 0)
- `--health-check-interval`: Interval in minutes between health checks (default: 30)
- `--skip-health-check`: Skip initial health check on startup

#### Strategy Parameters
- `--ma-fast`: Fast period for Moving Average Crossover strategy (default: 10)
- `--ma-slow`: Slow period for Moving Average Crossover strategy (default: 30)
- `--rsi-period`: Period for RSI strategy (default: 14)
- `--rsi-oversold`: Oversold threshold for RSI strategy (default: 30)
- `--rsi-overbought`: Overbought threshold for RSI strategy (default: 70)

#### Execution Modes
- `--dry-run`: Run in dry-run mode (no actual trades will be executed)
- `--backtest`: Run in backtest mode using historical data
- `--backtest-days`: Number of days to backtest (default: 30)

#### Display and Logging
- `--no-dashboard`: Disable rich dashboard display
- `--log-level`: Set the logging level (choices: DEBUG, INFO, WARNING, ERROR, CRITICAL; default: INFO)
- `--log-file`: Path to log file (default: bot.log)

### Examples

Trade ETH/USD with a 15-minute interval and $20 per trade:
```bash
python run_bot.py --symbol ETH/USD --interval 15 --amount 20.0
```

Run in dry-run mode with custom strategy parameters:
```bash
python run_bot.py --dry-run --ma-fast 5 --ma-slow 20 --rsi-period 10
```

Run a backtest for the last 60 days:
```bash
python run_bot.py --backtest --backtest-days 60
```

Increase logging verbosity:
```bash
python run_bot.py --log-level DEBUG
```

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

## Disclaimer

This bot is for educational purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred from using this software. Cryptocurrency trading involves significant risk and you should never trade with money you cannot afford to lose.

## License

MIT