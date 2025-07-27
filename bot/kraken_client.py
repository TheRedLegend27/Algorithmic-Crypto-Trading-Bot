"""
Kraken API client for cryptocurrency trading.
Simple, reliable alternative to Coinbase with excellent API documentation.
Enhanced with advanced order types, batch operations, and circuit breaker pattern.
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import requests
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime, timedelta

from bot.utils import log_error, log_info, log_warning


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class KrakenCredentials:
    """Kraken API credentials."""
    api_key: str
    api_secret: str
    base_url: str = "https://api.kraken.com"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_recovery_time: int = 30


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    max_requests_per_minute: int = 60
    burst_limit: int = 10
    backoff_factor: float = 1.5
    max_backoff: int = 300


@dataclass
class ConnectionPoolConfig:
    """Connection pool configuration."""
    pool_connections: int = 10
    pool_maxsize: int = 20
    max_retries: int = 3
    backoff_factor: float = 1.0


class CircuitBreaker:
    """Circuit breaker implementation for API calls."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self.lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True
        return (datetime.now() - self.last_failure_time).seconds >= self.config.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class RateLimiter:
    """Intelligent rate limiter with burst support."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.requests = []
        self.lock = threading.Lock()
        self.backoff_until = None
    
    def acquire(self):
        """Acquire rate limit permission."""
        with self.lock:
            now = datetime.now()
            
            # Check if we're in backoff period
            if self.backoff_until and now < self.backoff_until:
                sleep_time = (self.backoff_until - now).total_seconds()
                time.sleep(sleep_time)
            
            # Clean old requests (older than 1 minute)
            minute_ago = now - timedelta(minutes=1)
            self.requests = [req_time for req_time in self.requests if req_time > minute_ago]
            
            # Check rate limits
            if len(self.requests) >= self.config.max_requests_per_minute:
                # Calculate wait time
                oldest_request = min(self.requests)
                wait_time = 60 - (now - oldest_request).total_seconds()
                if wait_time > 0:
                    time.sleep(wait_time)
            
            # Add current request
            self.requests.append(now)
    
    def set_backoff(self, duration: int):
        """Set backoff period."""
        self.backoff_until = datetime.now() + timedelta(seconds=duration)


class KrakenClient:
    """
    Kraken API client with simple HMAC authentication.
    Much simpler than Coinbase's JWT approach.
    """
    
    def __init__(self, credentials: KrakenCredentials):
        """Initialize Kraken client."""
        self.credentials = credentials
        self.session = requests.Session()
        
        # Configure session with retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        log_info("KrakenClient initialized")
    
    def _get_kraken_signature(self, urlpath: str, data: Dict) -> str:
        """Generate Kraken API signature."""
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        
        mac = hmac.new(base64.b64decode(self.credentials.api_secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())
        return sigdigest.decode()
    
    def _make_request(self, endpoint: str, data: Optional[Dict] = None, is_private: bool = False) -> Dict[str, Any]:
        """Make request to Kraken API."""
        url = f"{self.credentials.base_url}{endpoint}"
        
        if is_private:
            if not data:
                data = {}
            data['nonce'] = str(int(1000 * time.time()))
            
            headers = {
                'API-Key': self.credentials.api_key,
                'API-Sign': self._get_kraken_signature(endpoint, data)
            }
            
            response = self.session.post(url, headers=headers, data=data, timeout=30)
        else:
            # Public endpoint
            response = self.session.get(url, params=data, timeout=30)
        
        # Handle rate limiting
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 5))
            log_warning(f"Rate limited, waiting {retry_after} seconds")
            time.sleep(retry_after)
            return self._make_request(endpoint, data, is_private)
        
        if response.status_code != 200:
            error_msg = f"Kraken API error: {response.status_code} - {response.text}"
            log_error(error_msg)
            raise requests.RequestException(error_msg)
        
        result = response.json()
        
        # Check for Kraken API errors
        if result.get('error'):
            error_msg = f"Kraken API error: {result['error']}"
            log_error(error_msg)
            raise ValueError(error_msg)
        
        return result.get('result', {})
    
    def test_connection(self) -> bool:
        """Test API connection."""
        try:
            # Test public endpoint
            self._make_request('/0/public/Time')
            
            # Test private endpoint
            self._make_request('/0/private/Balance', is_private=True)
            
            return True
        except Exception as e:
            log_error(f"Connection test failed: {str(e)}")
            return False
    
    # Public Market Data
    def get_server_time(self) -> Dict:
        """Get server time."""
        return self._make_request('/0/public/Time')
    
    def get_asset_info(self, assets: Optional[List[str]] = None) -> Dict:
        """Get asset information."""
        data = {}
        if assets:
            data['asset'] = ','.join(assets)
        return self._make_request('/0/public/Assets', data)
    
    def get_tradable_pairs(self, pairs: Optional[List[str]] = None) -> Dict:
        """Get tradable asset pairs."""
        data = {}
        if pairs:
            data['pair'] = ','.join(pairs)
        return self._make_request('/0/public/AssetPairs', data)
    
    def get_ticker(self, pairs: List[str]) -> Dict:
        """Get ticker information."""
        data = {'pair': ','.join(pairs)}
        return self._make_request('/0/public/Ticker', data)
    
    def get_ohlc_data(self, pair: str, interval: int = 1, since: Optional[int] = None) -> Dict:
        """Get OHLC data."""
        data = {'pair': pair, 'interval': interval}
        if since:
            data['since'] = since
        return self._make_request('/0/public/OHLC', data)
    
    def get_order_book(self, pair: str, count: int = 100) -> Dict:
        """Get order book."""
        data = {'pair': pair, 'count': count}
        return self._make_request('/0/public/Depth', data)
    
    def get_recent_trades(self, pair: str, since: Optional[int] = None) -> Dict:
        """Get recent trades."""
        data = {'pair': pair}
        if since:
            data['since'] = since
        return self._make_request('/0/public/Trades', data)
    
    # Private Account Data
    def get_account_balance(self) -> Dict:
        """Get account balance."""
        return self._make_request('/0/private/Balance', is_private=True)
    
    def get_trade_balance(self, asset: str = 'USD') -> Dict:
        """Get trade balance."""
        data = {'asset': asset}
        return self._make_request('/0/private/TradeBalance', data, is_private=True)
    
    def get_open_orders(self, trades: bool = False) -> Dict:
        """Get open orders."""
        data = {'trades': trades}
        return self._make_request('/0/private/OpenOrders', data, is_private=True)
    
    def get_closed_orders(self, trades: bool = False, start: Optional[int] = None, 
                         end: Optional[int] = None, ofs: Optional[int] = None, 
                         closetime: str = 'both') -> Dict:
        """Get closed orders."""
        data = {'trades': trades, 'closetime': closetime}
        if start:
            data['start'] = start
        if end:
            data['end'] = end
        if ofs:
            data['ofs'] = ofs
        return self._make_request('/0/private/ClosedOrders', data, is_private=True)
    
    def get_orders_info(self, order_ids: List[str], trades: bool = False) -> Dict:
        """Query orders info."""
        data = {'txid': ','.join(order_ids), 'trades': trades}
        return self._make_request('/0/private/QueryOrders', data, is_private=True)
    
    def get_trades_history(self, type_filter: str = 'all', trades: bool = False,
                          start: Optional[int] = None, end: Optional[int] = None,
                          ofs: Optional[int] = None) -> Dict:
        """Get trades history."""
        data = {'type': type_filter, 'trades': trades}
        if start:
            data['start'] = start
        if end:
            data['end'] = end
        if ofs:
            data['ofs'] = ofs
        return self._make_request('/0/private/TradesHistory', data, is_private=True)
    
    # Trading
    def add_order(self, pair: str, type_: str, ordertype: str, volume: str,
                  price: Optional[str] = None, price2: Optional[str] = None,
                  leverage: Optional[str] = None, oflags: Optional[str] = None,
                  starttm: Optional[str] = None, expiretm: Optional[str] = None,
                  userref: Optional[str] = None, validate: bool = False) -> Dict:
        """Add standard order."""
        data = {
            'pair': pair,
            'type': type_,  # buy or sell
            'ordertype': ordertype,  # market, limit, stop-loss, etc.
            'volume': volume
        }
        
        if price:
            data['price'] = price
        if price2:
            data['price2'] = price2
        if leverage:
            data['leverage'] = leverage
        if oflags:
            data['oflags'] = oflags
        if starttm:
            data['starttm'] = starttm
        if expiretm:
            data['expiretm'] = expiretm
        if userref:
            data['userref'] = userref
        if validate:
            data['validate'] = 'true'
        
        return self._make_request('/0/private/AddOrder', data, is_private=True)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel order."""
        data = {'txid': order_id}
        return self._make_request('/0/private/CancelOrder', data, is_private=True)
    
    def cancel_all_orders(self) -> Dict:
        """Cancel all open orders."""
        return self._make_request('/0/private/CancelAll', is_private=True)
    
    # Convenience methods
    def place_market_order(self, pair: str, side: str, volume: str) -> Dict:
        """Place a market order."""
        return self.add_order(
            pair=pair,
            type_=side.lower(),  # buy or sell
            ordertype='market',
            volume=volume
        )
    
    def place_limit_order(self, pair: str, side: str, volume: str, price: str) -> Dict:
        """Place a limit order."""
        return self.add_order(
            pair=pair,
            type_=side.lower(),  # buy or sell
            ordertype='limit',
            volume=volume,
            price=price
        )
    
    def get_current_price(self, pair: str) -> Optional[float]:
        """Get current price for a trading pair."""
        try:
            ticker_data = self.get_ticker([pair])
            if pair in ticker_data:
                # Kraken returns last trade price in 'c' field
                last_price = ticker_data[pair]['c'][0]
                return float(last_price)
            return None
        except Exception as e:
            log_error(f"Error getting price for {pair}: {str(e)}")
            return None


class EnhancedKrakenClient(KrakenClient):
    """
    Enhanced Kraken client with advanced features:
    - Advanced order types (stop-loss, take-profit, trailing stops)
    - Batch operations for multiple pairs
    - Circuit breaker pattern for error handling
    - Intelligent rate limiting
    - Connection pooling
    """
    
    def __init__(self, credentials: KrakenCredentials, 
                 circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
                 rate_limit_config: Optional[RateLimitConfig] = None,
                 connection_pool_config: Optional[ConnectionPoolConfig] = None):
        """Initialize enhanced Kraken client."""
        super().__init__(credentials)
        
        # Initialize configurations with defaults
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.connection_pool_config = connection_pool_config or ConnectionPoolConfig()
        
        # Initialize components
        self.circuit_breaker = CircuitBreaker(self.circuit_breaker_config)
        self.rate_limiter = RateLimiter(self.rate_limit_config)
        
        # Enhanced session configuration
        self._configure_enhanced_session()
        
        log_info("EnhancedKrakenClient initialized with advanced features")
    
    def _configure_enhanced_session(self):
        """Configure enhanced session with connection pooling."""
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # Enhanced retry strategy
        retry_strategy = Retry(
            total=self.connection_pool_config.max_retries,
            backoff_factor=self.connection_pool_config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"]
        )
        
        # Enhanced adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.connection_pool_config.pool_connections,
            pool_maxsize=self.connection_pool_config.pool_maxsize
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set session timeout
        self.session.timeout = 30
    
    def _make_request(self, endpoint: str, data: Optional[Dict] = None, is_private: bool = False) -> Dict[str, Any]:
        """Enhanced request method with circuit breaker and rate limiting."""
        def _request():
            # Apply rate limiting
            self.rate_limiter.acquire()
            
            # Call parent method
            return super(EnhancedKrakenClient, self)._make_request(endpoint, data, is_private)
        
        try:
            # Execute with circuit breaker protection
            return self.circuit_breaker.call(_request)
        except requests.RequestException as e:
            if "429" in str(e):
                # Handle rate limiting with backoff
                backoff_time = min(self.rate_limit_config.max_backoff, 
                                 int(self.rate_limit_config.backoff_factor * 60))
                self.rate_limiter.set_backoff(backoff_time)
                log_warning(f"Rate limited, backing off for {backoff_time} seconds")
            raise e
    
    # Advanced Order Types
    def place_stop_loss_order(self, pair: str, side: str, volume: str, stop_price: str) -> Dict:
        """Place a stop-loss order."""
        return self.add_order(
            pair=pair,
            type_=side.lower(),
            ordertype='stop-loss',
            volume=volume,
            price=stop_price
        )
    
    def place_take_profit_order(self, pair: str, side: str, volume: str, limit_price: str) -> Dict:
        """Place a take-profit order."""
        return self.add_order(
            pair=pair,
            type_=side.lower(),
            ordertype='take-profit',
            volume=volume,
            price=limit_price
        )
    
    def place_trailing_stop_order(self, pair: str, side: str, volume: str, trail_amount: str) -> Dict:
        """Place a trailing stop order."""
        return self.add_order(
            pair=pair,
            type_=side.lower(),
            ordertype='trailing-stop',
            volume=volume,
            price2=trail_amount  # Kraken uses price2 for trailing amount
        )
    
    def place_stop_loss_limit_order(self, pair: str, side: str, volume: str, 
                                   stop_price: str, limit_price: str) -> Dict:
        """Place a stop-loss-limit order."""
        return self.add_order(
            pair=pair,
            type_=side.lower(),
            ordertype='stop-loss-limit',
            volume=volume,
            price=stop_price,
            price2=limit_price
        )
    
    def place_take_profit_limit_order(self, pair: str, side: str, volume: str,
                                     trigger_price: str, limit_price: str) -> Dict:
        """Place a take-profit-limit order."""
        return self.add_order(
            pair=pair,
            type_=side.lower(),
            ordertype='take-profit-limit',
            volume=volume,
            price=trigger_price,
            price2=limit_price
        )
    
    # Batch Operations
    def get_multi_pair_ticker(self, pairs: List[str]) -> Dict:
        """Get ticker information for multiple pairs efficiently."""
        if not pairs:
            return {}
        
        try:
            # Kraken supports multiple pairs in a single request
            return self.get_ticker(pairs)
        except Exception as e:
            log_error(f"Error getting multi-pair ticker: {str(e)}")
            # Fallback to individual requests
            result = {}
            for pair in pairs:
                try:
                    ticker_data = self.get_ticker([pair])
                    result.update(ticker_data)
                except Exception as pair_error:
                    log_error(f"Error getting ticker for {pair}: {str(pair_error)}")
                    continue
            return result
    
    def batch_cancel_orders(self, order_ids: List[str]) -> Dict:
        """Cancel multiple orders efficiently."""
        if not order_ids:
            return {'count': 0}
        
        results = {'cancelled': [], 'failed': [], 'count': 0}
        
        # Try to cancel all orders at once first
        try:
            if len(order_ids) == 1:
                result = self.cancel_order(order_ids[0])
                results['cancelled'].append(order_ids[0])
                results['count'] = 1
                return results
            else:
                # For multiple orders, cancel individually for better error handling
                for order_id in order_ids:
                    try:
                        self.cancel_order(order_id)
                        results['cancelled'].append(order_id)
                        results['count'] += 1
                    except Exception as e:
                        log_error(f"Failed to cancel order {order_id}: {str(e)}")
                        results['failed'].append({'order_id': order_id, 'error': str(e)})
                
                return results
        except Exception as e:
            log_error(f"Batch cancel failed: {str(e)}")
            results['failed'] = [{'order_id': oid, 'error': str(e)} for oid in order_ids]
            return results
    
    def get_multi_pair_ohlc(self, pairs: List[str], interval: int = 1) -> Dict:
        """Get OHLC data for multiple pairs."""
        if not pairs:
            return {}
        
        result = {}
        for pair in pairs:
            try:
                ohlc_data = self.get_ohlc_data(pair, interval)
                result[pair] = ohlc_data
            except Exception as e:
                log_error(f"Error getting OHLC for {pair}: {str(e)}")
                continue
        
        return result
    
    def get_multi_pair_order_book(self, pairs: List[str], count: int = 100) -> Dict:
        """Get order book data for multiple pairs."""
        if not pairs:
            return {}
        
        result = {}
        for pair in pairs:
            try:
                order_book = self.get_order_book(pair, count)
                result[pair] = order_book
            except Exception as e:
                log_error(f"Error getting order book for {pair}: {str(e)}")
                continue
        
        return result
    
    # Enhanced Trading Information
    def get_trading_fees(self, pairs: List[str]) -> Dict:
        """Get trading fees for specified pairs."""
        try:
            # Get tradable pairs info which includes fees
            pairs_info = self.get_tradable_pairs(pairs)
            
            fees = {}
            for pair, info in pairs_info.items():
                fees[pair] = {
                    'maker_fee': float(info.get('fees', [[0, 0]])[0][1]),
                    'taker_fee': float(info.get('fees_maker', [[0, 0]])[0][1]),
                    'fee_volume_currency': info.get('fee_volume_currency', 'USD')
                }
            
            return fees
        except Exception as e:
            log_error(f"Error getting trading fees: {str(e)}")
            return {}
    
    def validate_trading_pairs(self, pairs: List[str]) -> Dict[str, bool]:
        """Validate that trading pairs are available on Kraken."""
        try:
            available_pairs = self.get_tradable_pairs()
            validation_result = {}
            
            for pair in pairs:
                validation_result[pair] = pair in available_pairs
                if not validation_result[pair]:
                    log_warning(f"Trading pair {pair} is not available on Kraken")
            
            return validation_result
        except Exception as e:
            log_error(f"Error validating trading pairs: {str(e)}")
            return {pair: False for pair in pairs}
    
    def get_pair_info(self, pairs: List[str]) -> Dict:
        """Get detailed information about trading pairs."""
        try:
            pairs_info = self.get_tradable_pairs(pairs)
            
            result = {}
            for pair, info in pairs_info.items():
                result[pair] = {
                    'altname': info.get('altname', pair),
                    'base': info.get('base', ''),
                    'quote': info.get('quote', ''),
                    'lot': info.get('lot', 'unit'),
                    'pair_decimals': info.get('pair_decimals', 8),
                    'lot_decimals': info.get('lot_decimals', 8),
                    'lot_multiplier': info.get('lot_multiplier', 1),
                    'leverage_buy': info.get('leverage_buy', []),
                    'leverage_sell': info.get('leverage_sell', []),
                    'fees': info.get('fees', []),
                    'fees_maker': info.get('fees_maker', []),
                    'fee_volume_currency': info.get('fee_volume_currency', 'USD'),
                    'margin_call': info.get('margin_call', 80),
                    'margin_stop': info.get('margin_stop', 40),
                    'ordermin': info.get('ordermin', '0')
                }
            
            return result
        except Exception as e:
            log_error(f"Error getting pair info: {str(e)}")
            return {}
    
    # Enhanced Order Management
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get detailed status of a specific order."""
        try:
            orders_info = self.get_orders_info([order_id])
            return orders_info.get(order_id)
        except Exception as e:
            log_error(f"Error getting order status for {order_id}: {str(e)}")
            return None
    
    def get_recent_orders(self, count: int = 50) -> Dict:
        """Get recent orders with limit."""
        try:
            return self.get_closed_orders(ofs=0)
        except Exception as e:
            log_error(f"Error getting recent orders: {str(e)}")
            return {}
    
    # Health and Monitoring
    def get_system_status(self) -> Dict:
        """Get system status information."""
        try:
            # Test various endpoints to determine system health
            status = {
                'server_time': None,
                'api_accessible': False,
                'private_api_accessible': False,
                'circuit_breaker_state': self.circuit_breaker.state.value,
                'failure_count': self.circuit_breaker.failure_count,
                'rate_limit_requests': len(self.rate_limiter.requests)
            }
            
            # Test public API
            try:
                server_time = self.get_server_time()
                status['server_time'] = server_time
                status['api_accessible'] = True
            except Exception:
                status['api_accessible'] = False
            
            # Test private API
            try:
                self.get_account_balance()
                status['private_api_accessible'] = True
            except Exception:
                status['private_api_accessible'] = False
            
            return status
        except Exception as e:
            log_error(f"Error getting system status: {str(e)}")
            return {'error': str(e)}
    
    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        with self.circuit_breaker.lock:
            self.circuit_breaker.state = CircuitBreakerState.CLOSED
            self.circuit_breaker.failure_count = 0
            self.circuit_breaker.last_failure_time = None
        log_info("Circuit breaker manually reset")
    
    def get_rate_limit_status(self) -> Dict:
        """Get current rate limiting status."""
        return {
            'requests_in_last_minute': len(self.rate_limiter.requests),
            'max_requests_per_minute': self.rate_limit_config.max_requests_per_minute,
            'backoff_until': self.rate_limiter.backoff_until.isoformat() if self.rate_limiter.backoff_until else None,
            'burst_limit': self.rate_limit_config.burst_limit
        }
    
    # Advanced Batch Operations
    def batch_place_orders(self, orders: List[Dict]) -> Dict:
        """Place multiple orders in batch with error handling."""
        results = {'successful': [], 'failed': [], 'count': 0}
        
        for order in orders:
            try:
                # Validate required fields
                required_fields = ['pair', 'type', 'ordertype', 'volume']
                if not all(field in order for field in required_fields):
                    raise ValueError(f"Missing required fields in order: {order}")
                
                # Convert 'type' to 'type_' for add_order method
                order_params = order.copy()
                if 'type' in order_params:
                    order_params['type_'] = order_params.pop('type')
                
                # Place order
                result = self.add_order(**order_params)
                results['successful'].append({
                    'order': order,
                    'result': result
                })
                results['count'] += 1
                
            except Exception as e:
                log_error(f"Failed to place order {order}: {str(e)}")
                results['failed'].append({
                    'order': order,
                    'error': str(e)
                })
        
        return results
    
    def get_multi_pair_balances(self, pairs: List[str]) -> Dict:
        """Get balances for assets involved in trading pairs."""
        try:
            all_balances = self.get_account_balance()
            
            # Extract unique assets from pairs
            assets = set()
            for pair in pairs:
                pair_info = self.get_pair_info([pair])
                if pair in pair_info:
                    assets.add(pair_info[pair]['base'])
                    assets.add(pair_info[pair]['quote'])
            
            # Filter balances for relevant assets
            relevant_balances = {}
            for asset in assets:
                if asset in all_balances:
                    relevant_balances[asset] = all_balances[asset]
            
            return relevant_balances
            
        except Exception as e:
            log_error(f"Error getting multi-pair balances: {str(e)}")
            return {}
    
    def get_position_summary(self, pairs: List[str]) -> Dict:
        """Get comprehensive position summary for trading pairs."""
        try:
            summary = {
                'pairs': {},
                'total_value_usd': 0.0,
                'balances': {},
                'open_orders': {},
                'recent_trades': {}
            }
            
            # Get balances
            summary['balances'] = self.get_multi_pair_balances(pairs)
            
            # Get current prices
            ticker_data = self.get_multi_pair_ticker(pairs)
            
            # Get open orders
            open_orders = self.get_open_orders()
            summary['open_orders'] = open_orders
            
            # Calculate position values
            for pair in pairs:
                if pair in ticker_data:
                    current_price = float(ticker_data[pair]['c'][0])
                    
                    pair_info = self.get_pair_info([pair])
                    if pair in pair_info:
                        base_asset = pair_info[pair]['base']
                        quote_asset = pair_info[pair]['quote']
                        
                        base_balance = float(summary['balances'].get(base_asset, '0'))
                        quote_balance = float(summary['balances'].get(quote_asset, '0'))
                        
                        position_value = base_balance * current_price + quote_balance
                        
                        summary['pairs'][pair] = {
                            'current_price': current_price,
                            'base_balance': base_balance,
                            'quote_balance': quote_balance,
                            'position_value_quote': position_value,
                            'base_asset': base_asset,
                            'quote_asset': quote_asset
                        }
                        
                        # Add to total value (assuming USD as base)
                        if quote_asset == 'USD' or quote_asset == 'ZUSD':
                            summary['total_value_usd'] += position_value
            
            return summary
            
        except Exception as e:
            log_error(f"Error getting position summary: {str(e)}")
            return {'error': str(e)}
    
    # Enhanced Error Recovery
    def test_connectivity_comprehensive(self) -> Dict:
        """Comprehensive connectivity test with detailed results."""
        results = {
            'overall_status': 'unknown',
            'public_api': {'status': 'unknown', 'latency_ms': None, 'error': None},
            'private_api': {'status': 'unknown', 'latency_ms': None, 'error': None},
            'websocket_ready': {'status': 'unknown', 'error': None},
            'circuit_breaker': {
                'state': self.circuit_breaker.state.value,
                'failure_count': self.circuit_breaker.failure_count
            },
            'rate_limiter': self.get_rate_limit_status()
        }
        
        # Test public API
        try:
            start_time = time.time()
            self.get_server_time()
            results['public_api']['latency_ms'] = int((time.time() - start_time) * 1000)
            results['public_api']['status'] = 'healthy'
        except Exception as e:
            results['public_api']['status'] = 'error'
            results['public_api']['error'] = str(e)
        
        # Test private API
        try:
            start_time = time.time()
            self.get_account_balance()
            results['private_api']['latency_ms'] = int((time.time() - start_time) * 1000)
            results['private_api']['status'] = 'healthy'
        except Exception as e:
            results['private_api']['status'] = 'error'
            results['private_api']['error'] = str(e)
        
        # Test WebSocket readiness (check if credentials are valid for WS)
        try:
            # This is a placeholder - actual WebSocket testing would be in WebSocket client
            if results['private_api']['status'] == 'healthy':
                results['websocket_ready']['status'] = 'ready'
            else:
                results['websocket_ready']['status'] = 'not_ready'
                results['websocket_ready']['error'] = 'Private API authentication failed'
        except Exception as e:
            results['websocket_ready']['status'] = 'error'
            results['websocket_ready']['error'] = str(e)
        
        # Determine overall status
        if (results['public_api']['status'] == 'healthy' and 
            results['private_api']['status'] == 'healthy'):
            results['overall_status'] = 'healthy'
        elif results['public_api']['status'] == 'healthy':
            results['overall_status'] = 'partial'
        else:
            results['overall_status'] = 'unhealthy'
        
        return results
    
    def auto_recover(self) -> Dict:
        """Attempt automatic recovery from various error states."""
        recovery_actions = []
        
        # Reset circuit breaker if it's open
        if self.circuit_breaker.state == CircuitBreakerState.OPEN:
            self.reset_circuit_breaker()
            recovery_actions.append("Circuit breaker reset")
        
        # Clear rate limiter backoff
        if self.rate_limiter.backoff_until:
            self.rate_limiter.backoff_until = None
            recovery_actions.append("Rate limiter backoff cleared")
        
        # Test connectivity after recovery
        connectivity = self.test_connectivity_comprehensive()
        
        return {
            'recovery_actions': recovery_actions,
            'connectivity_test': connectivity,
            'recovery_successful': connectivity['overall_status'] in ['healthy', 'partial']
        }