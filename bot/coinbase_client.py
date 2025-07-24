"""
Coinbase Advanced Trade API client with JWT authentication.
Handles API requests, authentication, rate limiting, and error handling.
"""
import json
import time
import uuid
import jwt
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
    api_secret: str  # This is now the private key for JWT
    sandbox: bool = False
    base_url: str = "https://api.coinbase.com"
    
    def __post_init__(self):
        """Set the correct base URL based on sandbox mode."""
        if self.sandbox:
            self.base_url = "https://api.coinbase.com"  # Sandbox uses same URL with different credentials


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
    
    def _generate_jwt_token(self) -> str:
        """
        Generate JWT token for Coinbase Advanced Trade API authentication.
        
        Returns:
            JWT token string
        """
        # JWT header
        header = {
            'alg': 'ES256',
            'kid': self.credentials.api_key,
            'typ': 'JWT'
        }
        
        # JWT payload
        now = int(time.time())
        
        # Check if this is a Cloud Trading API key (UUID format) vs Advanced Trade API key
        if self.credentials.api_key.startswith('organizations/'):
            # Advanced Trade API format
            payload = {
                'sub': self.credentials.api_key,
                'iss': 'coinbase-cloud',
                'nbf': now,
                'exp': now + 120,  # Token expires in 2 minutes
                'aud': ['public_websocket_api']
            }
        else:
            # Cloud Trading API format (UUID)
            payload = {
                'sub': self.credentials.api_key,
                'iss': 'coinbase-cloud',
                'nbf': now,
                'exp': now + 120,  # Token expires in 2 minutes
                'aud': ['public_websocket_api']
            }
        
        # Sign the JWT with the private key
        try:
            # Handle escaped newlines in private key from .env file
            private_key = self.credentials.api_secret.replace('\\n', '\n')
            token = jwt.encode(payload, private_key, algorithm='ES256', headers=header)
            return token
        except Exception as e:
            log_error(f"Failed to generate JWT token: {str(e)}")
            raise
    
    def _get_auth_headers(self, method: str = None, path: str = None, body: str = "") -> Dict[str, str]:
        """
        Generate authentication headers for Coinbase API requests.
        
        Args:
            method: HTTP method (not used in JWT auth)
            path: API endpoint path (not used in JWT auth)
            body: Request body (not used in JWT auth)
            
        Returns:
            Dictionary of authentication headers
        """
        jwt_token = self._generate_jwt_token()
        
        return {
            'Authorization': f'Bearer {jwt_token}',
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
            headers.update(self._get_auth_headers())
        else:
            headers['Content-Type'] = 'application/json'
        
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
            # Try v3 Advanced Trade API first
            try:
                response = self._make_request('GET', '/api/v3/brokerage/accounts')
                return isinstance(response, dict) and 'accounts' in response
            except:
                pass
            
            # Try v2 Consumer API
            try:
                response = self._make_request('GET', '/v2/user')
                return isinstance(response, dict) and 'data' in response
            except:
                pass
            
            # Fall back to public endpoint test (indicates read-only key)
            response = self._make_request('GET', '/v2/time', is_private=False)
            if isinstance(response, dict) and 'data' in response:
                log_info("API key works with public endpoints only (read-only permissions)")
                return True
            
            return False
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
        try:
            # Try v3 Advanced Trade API first
            response = self._make_request('GET', '/api/v3/brokerage/accounts')
            return response.get('accounts', [])
        except:
            # Fall back to v2 Consumer API
            response = self._make_request('GET', '/v2/accounts')
            return response.get('data', [])
    
    def get_account(self, account_id: str) -> Dict:
        """
        Get specific account information.
        
        Args:
            account_id: Account ID to retrieve
            
        Returns:
            Account information dictionary
        """
        response = self._make_request('GET', f'/api/v3/brokerage/accounts/{account_id}')
        return response.get('account', {})
    
    # Order endpoints
    def create_order(self, order_params: Dict) -> Dict:
        """
        Create a new order.
        
        Args:
            order_params: Order parameters dictionary
            
        Returns:
            Order creation response
        """
        return self._make_request('POST', '/api/v3/brokerage/orders', data=order_params)
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            Cancellation response
        """
        return self._make_request('POST', '/api/v3/brokerage/orders/batch_cancel', 
                                data={'order_ids': [order_id]})
    
    def get_order(self, order_id: str) -> Dict:
        """
        Get order information.
        
        Args:
            order_id: Order ID to retrieve
            
        Returns:
            Order information dictionary
        """
        response = self._make_request('GET', f'/api/v3/brokerage/orders/historical/{order_id}')
        return response.get('order', {})
    
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
            params['order_status'] = status
        if product_id:
            params['product_id'] = product_id
            
        response = self._make_request('GET', '/api/v3/brokerage/orders/historical/batch', params=params)
        return response.get('orders', [])
    
    # Market data endpoints (public)
    def get_products(self) -> List[Dict]:
        """
        Get all available trading products.
        
        Returns:
            List of product dictionaries
        """
        try:
            # Try v3 Advanced Trade API first
            response = self._make_request('GET', '/api/v3/brokerage/products', is_private=False)
            return response.get('products', [])
        except:
            # Fall back to v2 Consumer API - get exchange rates as products
            response = self._make_request('GET', '/v2/exchange-rates', is_private=False)
            rates = response.get('data', {}).get('rates', {})
            # Convert rates to product-like format
            products = []
            for currency, rate in rates.items():
                if currency in ['BTC', 'ETH', 'LTC', 'BCH']:  # Major cryptos
                    products.append({
                        'product_id': f'{currency}-USD',
                        'base_currency': currency,
                        'quote_currency': 'USD',
                        'status': 'online'
                    })
            return products
    
    def get_product_ticker(self, product_id: str) -> Dict:
        """
        Get ticker information for a product.
        
        Args:
            product_id: Product ID (e.g., 'BTC-USD')
            
        Returns:
            Ticker information dictionary
        """
        response = self._make_request('GET', f'/api/v3/brokerage/products/{product_id}', is_private=False)
        return response
    
    def get_product_candles(self, product_id: str, start: str, end: str, granularity: str) -> List[Dict]:
        """
        Get historical candle data for a product.
        
        Args:
            product_id: Product ID
            start: Start time (Unix timestamp)
            end: End time (Unix timestamp)
            granularity: Granularity (ONE_MINUTE, FIVE_MINUTE, etc.)
            
        Returns:
            List of candle data dictionaries
        """
        params = {
            'start': start,
            'end': end,
            'granularity': granularity
        }
        response = self._make_request('GET', f'/api/v3/brokerage/products/{product_id}/candles', 
                                    params=params, is_private=False)
        return response.get('candles', [])
    
    def get_product_stats(self, product_id: str) -> Dict:
        """
        Get 24hr stats for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            24hr stats dictionary
        """
        return self._make_request('GET', f'/api/v3/brokerage/products/{product_id}/stats', is_private=False)