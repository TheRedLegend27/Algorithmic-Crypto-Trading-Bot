# Enhanced Crypto Trading Dashboard

## Overview

The Enhanced Crypto Trading Dashboard provides a real-time web interface for monitoring and controlling your cryptocurrency trading bot. It features a modern dark theme, real-time updates via WebSocket, and comprehensive trading controls.

## Features

### 🔍 Real-time Monitoring
- **Portfolio Overview**: Live portfolio value, P&L tracking, and asset allocation
- **System Health**: CPU/memory usage, API rate limits, bot uptime, error rates
- **Market Data**: Real-time price feeds and market indicators
- **Trading Activity**: Live trade execution feed with detailed metrics

### 📊 Performance Analytics
- **Performance Metrics**: Win rate, Sharpe ratio, maximum drawdown
- **Risk Monitoring**: Portfolio risk assessment and exposure analysis
- **Historical Charts**: Price charts with technical indicators

### 🎛️ Manual Trading Controls
- **Order Execution**: Place market and limit orders directly from the dashboard
- **Risk Management**: Built-in position sizing and risk validation
- **Bot Controls**: Emergency stop, pause/resume trading, system restart

### 🔄 Real-time Updates
- **WebSocket Integration**: Live data streaming without page refresh
- **Auto-refresh**: Configurable update intervals
- **Connection Status**: Visual indicators for system connectivity

## Quick Start

### 1. Test the Dashboard (Mock Data)
```bash
python3 test_dashboard.py
```
This runs the dashboard with mock data for testing and demonstration.

### 2. Run with Real Kraken Data
```bash
python3 run_dashboard.py
```
This connects to your actual Kraken account using your API credentials.

### 3. Access the Dashboard
Open your browser and navigate to:
```
http://localhost:8080
```

## Configuration

The dashboard can be configured through the `DashboardConfig` class:

```python
dashboard_config = DashboardConfig(
    host="localhost",           # Server host
    port=8080,                 # Server port
    debug=False,               # Debug mode
    auto_refresh_interval=5,   # Update interval (seconds)
    enable_manual_trading=True, # Allow manual trades
    enable_websocket=True,     # Real-time updates
    theme="dark"               # UI theme
)
```

## Dashboard Sections

### Portfolio Overview
- **Total Value**: Current portfolio value in USD
- **Available Balance**: Cash available for trading
- **Daily P&L**: Profit/loss for the current day
- **Unrealized P&L**: Open position profits/losses
- **Realized P&L**: Closed position profits/losses

### System Health
- **Bot Uptime**: How long the bot has been running
- **CPU Usage**: Current CPU utilization
- **Memory Usage**: Current memory utilization
- **API Rate Limit**: Kraken API usage vs limits
- **Error Rate**: System error rate over 24 hours

### Manual Trading
- **Trading Pairs**: Select from available cryptocurrency pairs
- **Order Types**: Market orders (immediate) or limit orders (at specific price)
- **Volume**: Amount to trade
- **Risk Controls**: Automatic position sizing and risk validation

### Bot Controls
- **Emergency Stop**: Immediately halt all trading activity
- **Pause Trading**: Temporarily stop new trades
- **Resume Trading**: Restart trading operations
- **Restart Bot**: Full system restart

## API Endpoints

The dashboard provides REST API endpoints for integration:

- `GET /api/portfolio` - Current portfolio data
- `GET /api/system_health` - System health metrics
- `POST /api/trade` - Execute manual trade
- `POST /api/bot_control` - Control bot operations

## WebSocket Events

Real-time updates are delivered via WebSocket:

- `portfolio_update` - Portfolio data changes
- `system_health_update` - System metrics updates
- `market_data_update` - Market price updates
- `trade_update` - New trade executions

## Security Features

- **API Key Protection**: Credentials stored securely in environment variables
- **Risk Management**: Built-in position limits and validation
- **Manual Trading Controls**: Optional disable for production environments
- **Rate Limiting**: Respects Kraken API rate limits

## Troubleshooting

### Dashboard Won't Start
1. Check that all dependencies are installed: `pip3 install psutil flask flask-socketio`
2. Verify your `.env` file contains valid Kraken API credentials
3. Ensure port 8080 is not in use by another application

### No Real Data Showing
1. Verify your Kraken API credentials are correct
2. Check that your API key has the required permissions
3. Look at the console logs for API connection errors

### WebSocket Not Connecting
1. Check browser console for connection errors
2. Verify firewall settings allow WebSocket connections
3. Try refreshing the page or restarting the dashboard

## Development

### Adding New Features
The dashboard is built with Flask and Socket.IO. To add new features:

1. Add new routes in `_setup_routes()`
2. Add WebSocket handlers in `_setup_websocket_handlers()`
3. Update the HTML template in `_get_dashboard_template()`
4. Add JavaScript handlers for new functionality

### Customizing the UI
The dashboard uses a dark theme with CSS variables. Key styling can be modified in the `<style>` section of the HTML template.

## Dependencies

- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket support
- **psutil**: System monitoring
- **Your existing bot components**: KrakenClient, EnhancedLogger, etc.

## Support

For issues or questions:
1. Check the console logs for error messages
2. Verify your configuration matches the examples
3. Test with the mock dashboard first to isolate issues