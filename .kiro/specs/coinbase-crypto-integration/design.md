# Design Document

## Overview

This design outlines the migration of the existing Alpaca-based trading bot to use Coinbase Advanced Trade API for cryptocurrency trading. The migration will maintain the existing architecture while replacing Alpaca-specific components with Coinbase equivalents. The system will support real-money crypto trading with proper authentication, market data integration, order management, and risk controls.

The design preserves the current modular architecture with separate components for data fetching, trading execution, strategy management, and logging. Key changes include replacing the Alpaca API client with Coinbase Advanced Trade client, adapting data structures for crypto markets, and implementing crypto-specific trading rules.

## Architecture

### High-Level Architecture

The system maintains the existing layered architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Application                         │
│  (bot/main.py - Entry point, initialization, scheduling)   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Trading Scheduler                          │
│     (bot/scheduler.py - Manages trading cycles)            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Trading Cycle                             │
│  (Orchestrates data fetching, signal generation, trading)  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼──────┐    ┌────────▼────────┐    ┌──────▼──────┐
│ Data Fetcher │    │ Signal Generator│    │   Trader    │
│ (Coinbase)   │    │  (Strategies)   │    │ (Coinbase)  │
└──────────────┘    └─────────────────┘    └─────────────┘
        │                     │                     │
┌───────▼──────┐    ┌────────▼────────┐    ┌──────▼──────┐
│Market Data   │    │   Strategies    │    │Position &   │
│Integration   │    │ (MA, RSI, etc.) │    │Order Mgmt   │
└──────────────┘    └─────────────────┘    └─────────────┘
```

### Component Modifications

**New Components:**
- `CoinbaseDataFetcher` - Replaces Alpaca data fetching
- `CoinbaseTrader` - Replaces Alpaca trading client
- `CoinbaseCredentials` - Coinbase-specific authentication
- `CryptoPositionManager` - Crypto-specific position tracking
- `CryptoOrderManager` - Crypto order management with Coinbase rules

**Modified Components:**
- `Config` - Updated for Coinbase credentials and crypto settings
- `TradingSettings` - Enhanced with crypto-specific parameters
- Error handling - Coinbase-specific error codes and rate limits

## Components and Interfaces

### 1. Authentication and Configuration

#### CoinbaseCredentials
```python
@dataclass
class CoinbaseCredentials:
    api_key: str
    api_secret: str
    passphrase: str
    sandbox: bool = False
    base_url: str = "https://api.exchange.coinbase.com"
```

#### CoinbaseConfig
```python
class CoinbaseConfig:
    def load_coinbase_credentials(self) -> CoinbaseCredentials
    def validate_coinbase_config(self) -> bool
    def get_crypto_trading_settings(self) -> CryptoTradingSettings
```

#### CryptoTradingSettings
```python
@dataclass
class CryptoTradingSettings:
    trading_pair: str = "BTC-USD"
    base_currency: str = "BTC"
    quote_currency: str = "USD"
    trade_amount_usd: float = 10.0
    max_position_usd: float = 100.0
    min_order_size: float = 0.001  # Minimum BTC order size
    price_precision: int = 2
    size_precision: int = 8
    maker_fee_rate: float = 0.005  # 0.5%
    taker_fee_rate: float = 0.005  # 0.5%
```

### 2. Market Data Integration

#### CoinbaseDataFetcher
```python
class CoinbaseDataFetcher:
    def __init__(self, credentials: CoinbaseCredentials)
    def fetch_crypto_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame
    def get_latest_price(self, symbol: str) -> float
    def get_order_book(self, symbol: str, level: int = 1) -> Dict
    def get_24h_stats(self, symbol: str) -> Dict
    def subscribe_to_websocket(self, symbol: str, channels: List[str]) -> None
    def validate_crypto_data(self, data: pd.DataFrame) -> bool
```

**Key Features:**
- REST API integration for historical data
- WebSocket support for real-time price feeds
- Crypto-specific data validation (24/7 markets, higher volatility)
- Fallback to multiple data sources if needed
- Rate limit handling (10 requests/second for REST)

#### Market Data Format
```python
@dataclass
class CryptoMarketData:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float  # Volume in quote currency (USD)
    trade_count: int
```

### 3. Trading Execution

#### CoinbaseTrader
```python
class CoinbaseTrader:
    def __init__(self, credentials: CoinbaseCredentials, settings: CryptoTradingSettings)
    def execute_crypto_trade(self, signal: TradingSignal) -> Optional[CryptoTradeResult]
    def get_account_balances(self) -> Dict[str, float]
    def get_trading_fees(self) -> Dict[str, float]
    def validate_crypto_order(self, order_params: Dict) -> bool
```

#### CryptoPositionManager
```python
class CryptoPositionManager:
    def __init__(self, coinbase_client: CoinbaseClient)
    def get_crypto_balance(self, currency: str) -> float
    def get_position_value_usd(self, currency: str, current_price: float) -> float
    def calculate_available_balance(self, currency: str) -> float
    def track_crypto_position(self, currency: str, amount: float, price: float) -> None
    def get_portfolio_summary(self) -> Dict[str, Any]
```

#### CryptoOrderManager
```python
class CryptoOrderManager:
    def __init__(self, coinbase_client: CoinbaseClient)
    def place_market_order(self, side: str, symbol: str, size: float) -> Optional[Order]
    def place_limit_order(self, side: str, symbol: str, size: float, price: float) -> Optional[Order]
    def cancel_order(self, order_id: str) -> bool
    def get_order_status(self, order_id: str) -> str
    def validate_order_size(self, symbol: str, size: float) -> bool
    def calculate_fees(self, order_type: str, size: float, price: float) -> float
```

### 4. Coinbase API Client

#### CoinbaseClient
```python
class CoinbaseClient:
    def __init__(self, credentials: CoinbaseCredentials)
    def authenticate_request(self, method: str, path: str, body: str = "") -> Dict[str, str]
    def make_request(self, method: str, endpoint: str, params: Dict = None) -> Dict
    def handle_rate_limits(self) -> None
    def handle_api_errors(self, response: requests.Response) -> None
    
    # Account endpoints
    def get_accounts(self) -> List[Dict]
    def get_account(self, account_id: str) -> Dict
    
    # Order endpoints
    def create_order(self, order_params: Dict) -> Dict
    def cancel_order(self, order_id: str) -> Dict
    def get_order(self, order_id: str) -> Dict
    def list_orders(self, status: str = None) -> List[Dict]
    
    # Market data endpoints
    def get_products(self) -> List[Dict]
    def get_product_ticker(self, product_id: str) -> Dict
    def get_product_candles(self, product_id: str, start: str, end: str, granularity: int) -> List[List]
    def get_product_stats(self, product_id: str) -> Dict
```

## Data Models

### 1. Crypto-Specific Models

#### CryptoTradeResult
```python
@dataclass
class CryptoTradeResult:
    order_id: str
    product_id: str  # e.g., "BTC-USD"
    side: str  # "buy" or "sell"
    size: float  # Amount in base currency
    price: float  # Price per unit
    total_value: float  # Total USD value
    fees: float  # Trading fees
    status: str  # "pending", "filled", "cancelled"
    timestamp: datetime
    fill_fees: float = 0.0
    settled: bool = False
```

#### CryptoBalance
```python
@dataclass
class CryptoBalance:
    currency: str
    balance: float
    available: float
    hold: float  # Amount on hold for pending orders
    profile_id: str
    trading_enabled: bool
```

#### CryptoProduct
```python
@dataclass
class CryptoProduct:
    id: str  # "BTC-USD"
    base_currency: str  # "BTC"
    quote_currency: str  # "USD"
    base_min_size: float  # Minimum order size
    base_max_size: float  # Maximum order size
    quote_increment: float  # Price precision
    base_increment: float  # Size precision
    display_name: str
    min_market_funds: float
    max_market_funds: float
    margin_enabled: bool
    status: str
    status_message: str
```

### 2. Enhanced Trading Models

#### CryptoTradingSignal
```python
@dataclass
class CryptoTradingSignal(TradingSignal):
    base_currency: str
    quote_currency: str
    market_cap: float
    volume_24h: float
    price_change_24h: float
    volatility: float
    liquidity_score: float
```

## Error Handling

### 1. Coinbase-Specific Error Handling

#### CoinbaseErrorHandler
```python
class CoinbaseErrorHandler:
    def handle_authentication_error(self, error: Dict) -> bool
    def handle_rate_limit_error(self, error: Dict) -> bool
    def handle_insufficient_funds_error(self, error: Dict) -> bool
    def handle_invalid_order_error(self, error: Dict) -> bool
    def handle_market_closed_error(self, error: Dict) -> bool  # Not applicable for crypto
    def handle_network_error(self, error: Exception) -> bool
    def get_retry_delay(self, error_type: str) -> float
```

### 2. Error Categories

**Authentication Errors (401, 403):**
- Invalid API credentials
- Expired signatures
- Insufficient permissions

**Rate Limiting Errors (429):**
- Public endpoint: 10 requests/second
- Private endpoint: 5 requests/second
- Implement exponential backoff

**Order Errors (400):**
- Insufficient funds
- Invalid order size
- Invalid price
- Product not available

**Network Errors:**
- Connection timeouts
- DNS resolution failures
- SSL certificate errors

### 3. Recovery Strategies

```python
@dataclass
class ErrorRecoveryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    
    # Error-specific configurations
    rate_limit_delay: float = 5.0
    auth_error_retry: bool = False
    network_error_retry: bool = True
    order_error_retry: bool = False
```

## Testing Strategy

### 1. Unit Testing

**Test Coverage Areas:**
- CoinbaseClient API methods
- Authentication signature generation
- Order validation logic
- Data parsing and validation
- Error handling scenarios
- Fee calculations

**Mock Strategy:**
- Mock Coinbase API responses
- Simulate various error conditions
- Test rate limiting behavior
- Validate data transformations

### 2. Integration Testing

**Sandbox Testing:**
- Use Coinbase Pro Sandbox environment
- Test complete trading workflows
- Validate order placement and execution
- Test WebSocket connections
- Verify account balance updates

**Test Scenarios:**
```python
class CoinbaseIntegrationTests:
    def test_authentication_flow(self)
    def test_market_data_fetching(self)
    def test_order_placement_and_cancellation(self)
    def test_balance_and_position_tracking(self)
    def test_websocket_connection(self)
    def test_error_handling_and_recovery(self)
    def test_rate_limit_compliance(self)
```

### 3. End-to-End Testing

**Live Testing Strategy:**
- Start with small amounts in sandbox
- Gradually increase position sizes
- Monitor for 24-48 hours before full deployment
- Test all trading strategies with crypto data
- Validate risk management triggers

**Performance Testing:**
- Latency measurements for order execution
- WebSocket connection stability
- Memory usage with continuous operation
- CPU usage during high-frequency updates

### 4. Crypto-Specific Testing

**Market Condition Tests:**
- High volatility periods
- Low liquidity conditions
- Weekend trading (24/7 markets)
- Network congestion scenarios

**Data Quality Tests:**
- Price feed accuracy
- Volume data validation
- Timestamp consistency
- Missing data handling

## Security Considerations

### 1. API Security

**Credential Management:**
- Store API keys in environment variables
- Use separate credentials for sandbox/production
- Implement credential rotation capability
- Never log sensitive credentials

**Request Security:**
- HMAC-SHA256 signature authentication
- Timestamp validation (±30 seconds)
- Nonce generation for replay protection
- HTTPS-only communication

### 2. Trading Security

**Risk Controls:**
- Maximum position size limits
- Daily loss limits
- Order size validation
- Balance verification before trades

**Monitoring:**
- Unusual trading activity detection
- Failed authentication alerts
- Large position change notifications
- System health monitoring

### 3. Data Security

**Sensitive Data Handling:**
- Encrypt stored trading history
- Sanitize logs of sensitive information
- Secure backup procedures
- Access control for trading data

## Performance Considerations

### 1. API Rate Limits

**Coinbase Advanced Trade Limits:**
- REST API: 10 requests/second (public), 5 requests/second (private)
- WebSocket: 4 connections per IP
- Order rate: 10 orders/second

**Optimization Strategies:**
- Request batching where possible
- Efficient caching of market data
- WebSocket for real-time data
- Intelligent retry mechanisms

### 2. Data Processing

**Real-time Processing:**
- Efficient pandas operations
- Minimal data copying
- Streaming data processing
- Memory-efficient storage

**Caching Strategy:**
- Cache frequently accessed data
- Implement TTL for cached data
- Use appropriate cache sizes
- Clear stale cache entries

### 3. System Resources

**Memory Management:**
- Limit historical data retention
- Efficient data structures
- Garbage collection optimization
- Memory leak prevention

**CPU Optimization:**
- Vectorized calculations
- Parallel processing where applicable
- Efficient algorithm selection
- Minimize blocking operations

## Migration Strategy

### 1. Phase 1: Core Infrastructure
- Implement CoinbaseClient and authentication
- Create basic market data fetching
- Set up error handling framework
- Implement unit tests

### 2. Phase 2: Trading Functionality
- Implement order management
- Create position tracking
- Add balance management
- Integrate with existing strategies

### 3. Phase 3: Advanced Features
- WebSocket integration
- Real-time risk management
- Performance optimization
- Comprehensive testing

### 4. Phase 4: Deployment
- Sandbox testing
- Gradual rollout
- Monitoring and alerting
- Documentation and training

## Monitoring and Alerting

### 1. System Health Monitoring

**Key Metrics:**
- API response times
- Error rates by type
- Order execution success rate
- WebSocket connection stability
- System resource usage

### 2. Trading Monitoring

**Trading Metrics:**
- Daily P&L
- Number of trades executed
- Average trade size
- Risk metrics (drawdown, Sharpe ratio)
- Strategy performance

### 3. Alert Configuration

**Critical Alerts:**
- Authentication failures
- Large losses
- System errors
- API connectivity issues
- Unusual trading patterns

**Warning Alerts:**
- High error rates
- Performance degradation
- Risk limit approaches
- Data quality issues