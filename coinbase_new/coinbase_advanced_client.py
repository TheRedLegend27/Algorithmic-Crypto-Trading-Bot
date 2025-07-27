"""
Clean, focused Coinbase Advanced Trade API client.
Supports only the new Advanced Trade API with JWT authentication.
"""
import json
import time
import uuid
import jwt
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

from bot.utils import log_error, log_info, log_warning


@dataclass
class AdvancedTradeCredentials:
    """Credentials for Coinbase Advanced Trade API."""
    api_key: str  # Format: organizations/{org_id}/apiKeys/{key_id}
    private_key: str  # Ed25519 private key in PEM format
    base_url: str = "https://api.coinbase.com"


class CoinbaseAdvancedClient:
    """
    Simplified Coinbase Advanced Trade API client.
    Focuses exclusively on the new Advanced Trade API.
    """
    
    def __init__(self, credentials: AdvancedTradeCredentials):
        """Initialize the Advanced Trade API client."""
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
        
        log_info("CoinbaseAdvancedClient initialized")
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for Advanced Trade API authentication."""
        try:
            # Clean up the private key
            private_key = self.credentials.private_key.replace('\\n', '\n')
            
            # Determine key type and algorithm
            if 'BEGIN EC PRIVATE KEY' in private_key:
                # ECDSA P-256 key (most common)
                algorithm = 'ES256'
                log_info("Using ECDSA P-256 key with ES256 algorithm")
            elif 'BEGIN PRIVATE KEY' in private_key:
                # Could be Ed25519 or ECDSA in PKCS#8 format
                # Try to detect by attempting to load as Ed25519 first
                try:
                    from cryptography.hazmat.primitives import serialization
                    from cryptography.hazmat.primitives.asymmetric import ed25519
                    
                    key_obj = serialization.load_pem_private_key(
                        private_key.encode(), password=None
                    )
                    
                    if isinstance(key_obj, ed25519.Ed25519PrivateKey):
                        algorithm = 'EdDSA'
                        log_info("Using Ed25519 key with EdDSA algorithm")
                    else:
                        algorithm = 'ES256'
                        log_info("Using ECDSA key with ES256 algorithm")
                except:
                    # Default to ES256 if detection fails
                    algorithm = 'ES256'
                    log_info("Defaulting to ES256 algorithm")
            else:
                # Default to ES256 for unknown formats
                algorithm = 'ES256'
                log_info("Unknown key format, defaulting to ES256 algorithm")
            
            # JWT header
            header = {
                'alg': algorithm,
                'kid': self.credentials.api_key,
                'typ': 'JWT'
            }
            
            # JWT payload
            now = int(time.time())
            payload = {
                'sub': self.credentials.api_key,
                'iss': 'coinbase-cloud',
                'nbf': now,
                'exp': now + 120,  # 2 minute expiration
                'aud': ['retail_rest_api_proxy']  # Correct audience for REST API
            }
            
            # Generate token
            token = jwt.encode(payload, private_key, algorithm=algorithm, headers=header)
            return token
            
        except Exception as e:
            log_error(f"Failed to generate JWT token: {str(e)}")
            raise
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Advanced Trade API."""
        try:
            # Generate fresh JWT token for each request
            jwt_token = self._generate_jwt_token()
            
            # Prepare headers
            headers = {
                'Authorization': f'Bearer {jwt_token}',
                'Content-Type': 'application/json'
            }
            
            # Construct URL
            url = urljoin(self.credentials.base_url, endpoint)
            
            # Prepare request body
            json_data = None
            if data:
                json_data = data
            
            # Make request
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 5))
                log_warning(f"Rate limited, waiting {retry_after} seconds")
                time.sleep(retry_after)
                return self._make_request(method, endpoint, params, data)
            
            # Check for errors
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = f"API request failed: {response.status_code} - {error_data}"
                except:
                    error_msg = f"API request failed: {response.status_code} - {response.text}"
                log_error(error_msg)
                raise requests.RequestException(error_msg)
            
            return response.json()
            
        except Exception as e:
            log_error(f"Request to {endpoint} failed: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """Test API connection and authentication."""
        try:
            response = self._make_request('GET', '/api/v3/brokerage/accounts')
            return 'accounts' in response
        except Exception as e:
            log_error(f"Connection test failed: {str(e)}")
            return False
    
    # Account Management
    def get_accounts(self) -> List[Dict]:
        """Get all accounts."""
        response = self._make_request('GET', '/api/v3/brokerage/accounts')
        return response.get('accounts', [])
    
    def get_account(self, account_uuid: str) -> Dict:
        """Get specific account details."""
        response = self._make_request('GET', f'/api/v3/brokerage/accounts/{account_uuid}')
        return response.get('account', {})
    
    # Market Data
    def get_products(self) -> List[Dict]:
        """Get all available trading products."""
        response = self._make_request('GET', '/api/v3/brokerage/market/products')
        return response.get('products', [])
    
    def get_product(self, product_id: str) -> Dict:
        """Get specific product details."""
        response = self._make_request('GET', f'/api/v3/brokerage/market/products/{product_id}')
        return response
    
    def get_product_candles(self, product_id: str, start: str, end: str, 
                           granularity: str = "ONE_MINUTE") -> List[Dict]:
        """Get historical candle data."""
        params = {
            'start': start,
            'end': end,
            'granularity': granularity
        }
        response = self._make_request('GET', f'/api/v3/brokerage/market/products/{product_id}/candles', params=params)
        return response.get('candles', [])
    
    def get_market_trades(self, product_id: str, limit: int = 100) -> List[Dict]:
        """Get recent market trades."""
        params = {'limit': limit}
        response = self._make_request('GET', f'/api/v3/brokerage/market/products/{product_id}/ticker', params=params)
        return response.get('trades', [])
    
    # Order Management
    def create_order(self, order_config: Dict) -> Dict:
        """Create a new order."""
        # Add client order ID if not provided
        if 'client_order_id' not in order_config:
            order_config['client_order_id'] = str(uuid.uuid4())
        
        response = self._make_request('POST', '/api/v3/brokerage/orders', data=order_config)
        return response
    
    def cancel_orders(self, order_ids: List[str]) -> Dict:
        """Cancel multiple orders."""
        data = {'order_ids': order_ids}
        response = self._make_request('POST', '/api/v3/brokerage/orders/batch_cancel', data=data)
        return response
    
    def get_order(self, order_id: str) -> Dict:
        """Get order details."""
        response = self._make_request('GET', f'/api/v3/brokerage/orders/historical/{order_id}')
        return response.get('order', {})
    
    def list_orders(self, product_id: Optional[str] = None, 
                   order_status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """List orders with optional filters."""
        params = {'limit': limit}
        if product_id:
            params['product_id'] = product_id
        if order_status:
            params['order_status'] = order_status
        
        response = self._make_request('GET', '/api/v3/brokerage/orders/historical/batch', params=params)
        return response.get('orders', [])
    
    def list_fills(self, product_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """List order fills."""
        params = {'limit': limit}
        if product_id:
            params['product_id'] = product_id
        
        response = self._make_request('GET', '/api/v3/brokerage/orders/historical/fills', params=params)
        return response.get('fills', [])
    
    # Convenience methods for common order types
    def place_market_order(self, product_id: str, side: str, size: str) -> Dict:
        """Place a market order."""
        order_config = {
            'product_id': product_id,
            'side': side.upper(),
            'order_configuration': {
                'market_market_ioc': {
                    'base_size': size
                }
            }
        }
        return self.create_order(order_config)
    
    def place_limit_order(self, product_id: str, side: str, size: str, price: str) -> Dict:
        """Place a limit order."""
        order_config = {
            'product_id': product_id,
            'side': side.upper(),
            'order_configuration': {
                'limit_limit_gtc': {
                    'base_size': size,
                    'limit_price': price
                }
            }
        }
        return self.create_order(order_config)
    
    def place_stop_order(self, product_id: str, side: str, size: str, stop_price: str) -> Dict:
        """Place a stop order."""
        order_config = {
            'product_id': product_id,
            'side': side.upper(),
            'order_configuration': {
                'stop_limit_stop_limit_gtc': {
                    'base_size': size,
                    'limit_price': stop_price,
                    'stop_price': stop_price
                }
            }
        }
        return self.create_order(order_config)