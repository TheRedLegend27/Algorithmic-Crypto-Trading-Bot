# API Endpoints and Dashboard Usage

This document describes the API endpoints and dashboard features of the Enhanced Kraken Trading Bot.

## Table of Contents

1. [Dashboard Overview](#dashboard-overview)
2. [REST API Endpoints](#rest-api-endpoints)
3. [WebSocket API](#websocket-api)
4. [Dashboard Features](#dashboard-features)
5. [API Authentication](#api-authentication)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)

## Dashboard Overview

The Enhanced Kraken Trading Bot provides a comprehensive web-based dashboard accessible at:

**URL**: `http://localhost:8080` (default)

### Dashboard Sections

1. **Portfolio Overview**: Real-time account balance and positions
2. **Trading Activity**: Live trade feed and order status
3. **Performance Metrics**: P&L, win rate, and risk metrics
4. **Market Data**: Price charts and technical indicators
5. **System Status**: Bot health and connection status
6. **Risk Management**: Current risk exposure and limits
7. **Strategy Performance**: Individual strategy analytics

## REST API Endpoints

### Base URL
```
http://localhost:8080/api/v1
```

### Authentication
All API endpoints require authentication via API key header:
```
Authorization: Bearer <your_api_key>
```

### Portfolio Endpoints

#### Get Account Balance
```http
GET /portfolio/balance
```

**Response:**
```json
{
  "success": true,
  "data": {
    "total_value_usd": 5000.00,
    "available_balance": 4500.00,
    "positions_value": 500.00,
    "unrealized_pnl": 25.50,
    "realized_pnl": 125.75,
    "currencies": {
      "USD": 4500.00,
      "BTC": 0.01,
      "ETH": 0.5
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Get Current Positions
```http
GET /portfolio/positions
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "pair": "XBTUSD",
      "side": "long",
      "size": 0.01,
      "entry_price": 45000.00,
      "current_price": 45250.00,
      "unrealized_pnl": 2.50,
      "unrealized_pnl_pct": 0.56,
      "timestamp": "2024-01-15T09:15:00Z"
    }
  ]
}
```

#### Get Portfolio Performance
```http
GET /portfolio/performance?period=24h
```

**Parameters:**
- `period`: Time period (1h, 24h, 7d, 30d, 90d)

**Response:**
```json
{
  "success": true,
  "data": {
    "period": "24h",
    "total_return": 2.5,
    "total_return_pct": 0.05,
    "win_rate": 0.65,
    "profit_factor": 1.8,
    "sharpe_ratio": 1.2,
    "max_drawdown": 0.03,
    "total_trades": 15,
    "winning_trades": 10,
    "losing_trades": 5,
    "average_win": 15.50,
    "average_loss": -8.25
  }
}
```

### Trading Endpoints

#### Get Recent Trades
```http
GET /trading/trades?limit=50&pair=XBTUSD
```

**Parameters:**
- `limit`: Number of trades to return (default: 50, max: 200)
- `pair`: Trading pair filter (optional)
- `start_time`: Start time filter (ISO 8601)
- `end_time`: End time filter (ISO 8601)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "trade_id": "trade_123456",
      "pair": "XBTUSD",
      "side": "buy",
      "amount": 0.001,
      "price": 45250.00,
      "fee": 0.12,
      "timestamp": "2024-01-15T10:25:00Z",
      "strategy": "EnhancedMomentum",
      "signal_confidence": 0.75,
      "execution_time_ms": 150,
      "status": "filled"
    }
  ],
  "pagination": {
    "total": 150,
    "page": 1,
    "per_page": 50,
    "has_next": true
  }
}
```

#### Get Open Orders
```http
GET /trading/orders/open
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "order_id": "order_789012",
      "pair": "ETHUSD",
      "side": "sell",
      "type": "limit",
      "amount": 0.1,
      "price": 2850.00,
      "filled_amount": 0.0,
      "remaining_amount": 0.1,
      "status": "open",
      "timestamp": "2024-01-15T10:20:00Z",
      "expires_at": "2024-01-15T11:20:00Z"
    }
  ]
}
```

#### Place Manual Order
```http
POST /trading/orders
```

**Request Body:**
```json
{
  "pair": "XBTUSD",
  "side": "buy",
  "type": "market",
  "amount": 0.001,
  "price": null,
  "stop_loss": 44000.00,
  "take_profit": 46000.00
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "order_id": "order_345678",
    "status": "pending",
    "message": "Order submitted successfully"
  }
}
```

#### Cancel Order
```http
DELETE /trading/orders/{order_id}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "order_id": "order_345678",
    "status": "cancelled",
    "message": "Order cancelled successfully"
  }
}
```

### Market Data Endpoints

#### Get Current Market Data
```http
GET /market/ticker/{pair}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "pair": "XBTUSD",
    "price": 45250.00,
    "bid": 45248.50,
    "ask": 45251.50,
    "volume_24h": 1250.75,
    "change_24h": 125.50,
    "change_24h_pct": 0.28,
    "high_24h": 45800.00,
    "low_24h": 44200.00,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

#### Get Historical Data
```http
GET /market/history/{pair}?interval=1h&limit=100
```

**Parameters:**
- `interval`: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
- `limit`: Number of candles (default: 100, max: 1000)
- `start_time`: Start time (ISO 8601)
- `end_time`: End time (ISO 8601)

**Response:**
```json
{
  "success": true,
  "data": {
    "pair": "XBTUSD",
    "interval": "1h",
    "candles": [
      {
        "timestamp": "2024-01-15T09:00:00Z",
        "open": 45000.00,
        "high": 45300.00,
        "low": 44950.00,
        "close": 45250.00,
        "volume": 125.75
      }
    ]
  }
}
```

### Strategy Endpoints

#### Get Strategy Performance
```http
GET /strategies/performance
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "strategy": "EnhancedMomentum",
      "weight": 0.3,
      "signals_generated": 45,
      "signals_executed": 28,
      "win_rate": 0.68,
      "avg_return": 0.025,
      "sharpe_ratio": 1.5,
      "last_signal": {
        "action": "BUY",
        "confidence": 0.75,
        "timestamp": "2024-01-15T10:25:00Z"
      }
    }
  ]
}
```

#### Get Current Signals
```http
GET /strategies/signals/current
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "pair": "XBTUSD",
      "strategy": "EnhancedMomentum",
      "action": "BUY",
      "confidence": 0.75,
      "reasoning": "Strong upward momentum with volume confirmation",
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {
        "momentum_score": 0.85,
        "volume_ratio": 1.4,
        "volatility": 0.023
      }
    }
  ]
}
```

### Risk Management Endpoints

#### Get Risk Metrics
```http
GET /risk/metrics
```

**Response:**
```json
{
  "success": true,
  "data": {
    "portfolio_risk_score": 0.35,
    "max_drawdown": 0.03,
    "var_95": 125.50,
    "position_concentration": 0.45,
    "correlation_risk": 0.25,
    "leverage_ratio": 1.2,
    "daily_pnl": 25.75,
    "daily_loss_limit": 250.00,
    "trades_today": 8,
    "max_trades_per_day": 50
  }
}
```

#### Update Risk Limits
```http
PUT /risk/limits
```

**Request Body:**
```json
{
  "max_daily_loss_pct": 0.05,
  "max_position_per_pair_usd": 1000.00,
  "max_trades_per_day": 50,
  "risk_per_trade_pct": 0.02
}
```

### System Endpoints

#### Get System Status
```http
GET /system/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "running",
    "uptime": 86400,
    "version": "2.0.0",
    "api_connectivity": {
      "kraken_rest": "connected",
      "kraken_websocket": "connected",
      "last_heartbeat": "2024-01-15T10:30:00Z"
    },
    "system_health": {
      "cpu_usage": 15.5,
      "memory_usage": 45.2,
      "disk_usage": 25.8,
      "error_rate": 0.02
    },
    "trading_status": {
      "paper_trading": false,
      "auto_trading": true,
      "emergency_stop": false
    }
  }
}
```

#### Get System Logs
```http
GET /system/logs?level=INFO&limit=100
```

**Parameters:**
- `level`: Log level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `limit`: Number of log entries (default: 100, max: 1000)
- `start_time`: Start time filter
- `component`: Component filter (strategy, risk, trading, etc.)

## WebSocket API

### Connection
```
ws://localhost:8080/ws
```

### Authentication
Send authentication message after connection:
```json
{
  "type": "auth",
  "token": "your_api_token"
}
```

### Subscription Messages

#### Subscribe to Portfolio Updates
```json
{
  "type": "subscribe",
  "channel": "portfolio",
  "pairs": ["XBTUSD", "ETHUSD"]
}
```

#### Subscribe to Trade Updates
```json
{
  "type": "subscribe",
  "channel": "trades"
}
```

#### Subscribe to Market Data
```json
{
  "type": "subscribe",
  "channel": "market",
  "pairs": ["XBTUSD"],
  "interval": "1m"
}
```

### Real-time Updates

#### Portfolio Update
```json
{
  "type": "portfolio_update",
  "data": {
    "total_value": 5025.50,
    "unrealized_pnl": 25.50,
    "timestamp": "2024-01-15T10:30:15Z"
  }
}
```

#### Trade Execution
```json
{
  "type": "trade_executed",
  "data": {
    "trade_id": "trade_123456",
    "pair": "XBTUSD",
    "side": "buy",
    "amount": 0.001,
    "price": 45250.00,
    "timestamp": "2024-01-15T10:30:15Z"
  }
}
```

#### Market Data Update
```json
{
  "type": "market_update",
  "data": {
    "pair": "XBTUSD",
    "price": 45250.00,
    "volume": 1.5,
    "timestamp": "2024-01-15T10:30:15Z"
  }
}
```

## Dashboard Features

### Portfolio Overview
- **Real-time Balance**: Live account balance updates
- **Position Summary**: Current open positions with P&L
- **Asset Allocation**: Pie chart of portfolio distribution
- **Performance Chart**: Historical portfolio value

### Trading Activity
- **Live Trade Feed**: Real-time trade execution updates
- **Order Book**: Current open orders and their status
- **Trade History**: Searchable and filterable trade history
- **Manual Trading**: Place orders directly from dashboard

### Performance Analytics
- **P&L Charts**: Daily, weekly, monthly performance
- **Strategy Attribution**: Performance by strategy
- **Risk Metrics**: Real-time risk assessment
- **Win Rate Analysis**: Success rate over time

### Market Data
- **Price Charts**: Candlestick charts with indicators
- **Technical Indicators**: RSI, MACD, Bollinger Bands
- **Volume Analysis**: Volume profile and trends
- **Market Depth**: Order book visualization

### System Monitoring
- **Connection Status**: API and WebSocket connectivity
- **System Health**: CPU, memory, disk usage
- **Error Logs**: Real-time error monitoring
- **Performance Metrics**: Latency and throughput

### Risk Management
- **Risk Dashboard**: Current risk exposure
- **Limit Monitoring**: Track against risk limits
- **Correlation Matrix**: Asset correlation analysis
- **Drawdown Tracking**: Maximum drawdown monitoring

## API Authentication

### API Key Generation
1. Access dashboard settings
2. Navigate to "API Keys" section
3. Click "Generate New Key"
4. Set permissions and expiration
5. Copy and store key securely

### Authentication Methods

#### Header Authentication
```http
Authorization: Bearer <api_key>
```

#### Query Parameter
```http
GET /api/v1/portfolio/balance?api_key=<api_key>
```

### Permissions
- **Read**: View portfolio and market data
- **Trade**: Execute trades and manage orders
- **Admin**: Modify settings and risk limits

## Error Handling

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Insufficient funds for trade execution",
    "details": {
      "required": 1000.00,
      "available": 500.00
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common Error Codes
- `INVALID_API_KEY`: API key is invalid or expired
- `INSUFFICIENT_PERMISSIONS`: API key lacks required permissions
- `RATE_LIMIT_EXCEEDED`: Too many requests in time window
- `INVALID_PARAMETERS`: Request parameters are invalid
- `INSUFFICIENT_FUNDS`: Not enough balance for operation
- `MARKET_CLOSED`: Market is closed for trading
- `SYSTEM_MAINTENANCE`: System is under maintenance

## Rate Limiting

### Limits
- **REST API**: 100 requests per minute per API key
- **WebSocket**: 10 subscriptions per connection
- **Trading**: 20 orders per minute

### Rate Limit Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248600
```

### Handling Rate Limits
When rate limit is exceeded, the API returns:
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 60 seconds.",
    "retry_after": 60
  }
}
```

---

**⚠️ Important**: Always handle API errors gracefully and implement proper retry logic with exponential backoff. Never expose API keys in client-side code or logs.