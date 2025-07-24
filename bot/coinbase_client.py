"""
Coinbase Advanced Trade API client with HMAC-SHA256 authentication.
Handles API requests, authentication, rate limiting, and error handling.
"""
import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bot.utils import log_error, log_info


@dataclass
class CoinbaseCredentials:
    """Dataclass for storing Coinbase API credentials."""
    api_key: str
    api_secret: str
    passphrase: str
    sandbox: bool = False
    base_url: str = "https://api.exchange.coinbase.com"
    
    def __post_init__(self):
        """Set the correct base URL based on sandbox mode."""
        if self.sandbox:
            self.base_url = "https://api-public.sandbox.exchange.coinbase.com"


class RateLimiter:
    """Simple rate limiter for API requests."""
    
    def __init__(self, max_requests: int = 10, time_window: int = 1):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove old requests outside the time window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.time_window]
        
        # If we're at the limit, wait until we can make another request
        if len(self.requests) >= self.max_requests:
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request)
            if wait_time > 0:
                log_info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
        
        # Record this request
        self.requests.append(now)


class CoinbaseClient:
    """
    Coinbase Advanced Trade API client with authentication and rate limiting.
    """
    
    def __init__(self, credentials: CoinbaseCredentials):
        """
        Initialize Coinbase client.
        
        Args:
            credentials: Coinbase API credentials
        """
        self.credentials = credentials
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Rate limiters for different endpoint types
        self.public_rate_limiter = RateLimiter(max_requests=10, time_window=1)
        self.private_rate_limiter = RateLimiter(max_requests=5, time_window=1)
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """
        Generate HMAC-SHA256 signature for Coinbase API authentication.
        
        Args:
            timestamp: Unix timestamp as string
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            body: Request body (empty for GET requests)
            
        Returns:
            Base64 encoded signature
        """
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            base64.b64decode(self.credentials.api_secret),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(signature.digest()).decode('utf-8')
    
    def _get_auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Generate authentication headers for Coinbase API requests.
        
        Args:
            method: HTTP method
            path: API endpoint path
            body: Request body
            
        Returns:
            Dictionary of authentication headers
        """
        timestamp = str(time.time())
        signature = self._generate_signature(timestamp, method, path, body)
        
        return {
            'CB-ACCESS-KEY': self.credentials.api_key,
            'CB-ACCESS-SIGN': signature,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-PASSPHRASE': self.credentials.passphrase,
            'Content-Type': 'application/json'
        }
    
    def _validate_timestamp(self, timestamp: float, tolerance: int = 30) -> bool:
        """
        Validate that timestamp is within acceptable range.
        
        Args:
            timestamp: Timestamp to validate
            tolerance: Acceptable time difference in seconds
            
        Returns:
            True if timestamp is valid
        """
        current_time = time.time()
        return abs(current_time - timestamp) <= tolerance
    
    def _generate_nonce(self) -> str:
        """
        Generate a unique nonce for request deduplication.
        
        Returns:
            UUID4 string as nonce
        """
        return str(uuid.uuid4())
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     data: Optional[Dict] = None, is_private: bool = True) -> Dict[str, Any]:
        """
        Make authenticated request to Coinbase API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            params: Query parameters
            data: Request body data
            is_private: Whether this is a private endpoint requiring authentication
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.RequestException: For HTTP errors
            ValueError: For invalid responses
        """
        # Apply rate limiting
        if is_private:
            self.private_rate_limiter.wait_if_needed()
        else:
            self.public_rate_limiter.wait_if_needed()
        
        # Construct full URL
        url = urljoin(self.credentials.base_url, endpoint)
        
        # Prepare request body
        body = ""
        if data:
            body = json.dumps(data)
        
        # Prepare headers
        headers = {}
        if is_private:
            headers.update(self._get_auth_headers(method, endpoint, body))
        else:
            headers['Content-Type'] = 'application/json'
        
        # Add nonce to headers for private requests
        if is_private:
            headers['CB-ACCESS-NONCE'] = self._generate_nonce()
        
        try:
            # Make the request
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=body if body else None,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 5))
                log_info(f"Rate limited, waiting {retry_after} seconds")
                time.sleep(retry_after)
                # Retry the request
                return self._make_request(method, endpoint, params, data, is_private)
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                log_error(f"Invalid JSON response: {response.text}")
                raise ValueError("Invalid JSON response from API")
                
        except requests.RequestException as e:
            log_error(f"API request failed: {str(e)}")
            raise
    
    def test_authentication(self) -> bool:
        """
        Test API authentication by making a simple authenticated request.
        
        Returns:
            True if authentication is successful
        """
        try:
            response = self._make_request('GET', '/accounts')
            return isinstance(response, list) or isinstance(response, dict)
        except Exception as e:
            log_error(f"Authentication test failed: {str(e)}")
            return False
    
    # Account endpoints
    def get_accounts(self) -> List[Dict]:
        """
        Get all accounts for the authenticated user.
        
        Returns:
            List of account dictionaries
        """
        return self._make_request('GET', '/accounts')
    
    def get_account(self, account_id: str) -> Dict:
        """
        Get specific account information.
        
        Args:
            account_id: Account ID to retrieve
            
        Returns:
            Account information dictionary
        """
        return self._make_request('GET', f'/accounts/{account_id}')
    
    # Order endpoints
    def create_order(self, order_params: Dict) -> Dict:
        """
        Create a new order.
        
        Args:
            order_params: Order parameters dictionary
            
        Returns:
            Order creation response
        """
        return self._make_request('POST', '/orders', data=order_params)
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            Cancellation response
        """
        return self._make_request('DELETE', f'/orders/{order_id}')
    
    def get_order(self, order_id: str) -> Dict:
        """
        Get order information.
        
        Args:
            order_id: Order ID to retrieve
            
        Returns:
            Order information dictionary
        """
        return self._make_request('GET', f'/orders/{order_id}')
    
    def list_orders(self, status: Optional[str] = None, product_id: Optional[str] = None) -> List[Dict]:
        """
        List orders with optional filtering.
        
        Args:
            status: Filter by order status
            product_id: Filter by product ID
            
        Returns:
            List of order dictionaries
        """
        params = {}
        if status:
            params['status'] = status
        if product_id:
            params['product_id'] = product_id
            
        return self._make_request('GET', '/orders', params=params)
    
    # Market data endpoints (public)
    def get_products(self) -> List[Dict]:
        """
        Get all available trading products.
        
        Returns:
            List of product dictionaries
        """
        return self._make_request('GET', '/products', is_private=False)
    
    def get_product_ticker(self, product_id: str) -> Dict:
        """
        Get ticker information for a product.
        
        Args:
            product_id: Product ID (e.g., 'BTC-USD')
            
        Returns:
            Ticker information dictionary
        """
        return self._make_request('GET', f'/products/{product_id}/ticker', is_private=False)
    
    def get_product_candles(self, product_id: str, start: str, end: str, granularity: int) -> List[List]:
        """
        Get historical candle data for a product.
        
        Args:
            product_id: Product ID
            start: Start time (ISO 8601)
            end: End time (ISO 8601)
            granularity: Granularity in seconds
            
        Returns:
            List of candle data arrays
        """
        params = {
            'start': start,
            'end': end,
            'granularity': granularity
        }
        return self._make_request('GET', f'/products/{product_id}/candles', params=params, is_private=False)
    
    def get_product_stats(self, product_id: str) -> Dict:
        """
        Get 24hr stats for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            24hr stats dictionary
        """
        return self._make_request('GET', f'/products/{product_id}/stats', is_private=False)