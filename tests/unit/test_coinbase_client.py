"""
Unit tests for CoinbaseClient class.
Tests authentication, request signing, rate limiting, and API methods.
"""
import base64
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
import requests

from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials, RateLimiter


class TestCoinbaseCredentials(unittest.TestCase):
    """Test CoinbaseCredentials dataclass."""
    
    def test_default_production_url(self):
        """Test that production URL is used by default."""
        creds = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase"
        )
        self.assertEqual(creds.base_url, "https://api.exchange.coinbase.com")
        self.assertFalse(creds.sandbox)
    
    def test_sandbox_url(self):
        """Test that sandbox URL is used when sandbox=True."""
        creds = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
        self.assertEqual(creds.base_url, "https://api-public.sandbox.exchange.coinbase.com")
        self.assertTrue(creds.sandbox)


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = RateLimiter(max_requests=3, time_window=1)
    
    def test_no_wait_when_under_limit(self):
        """Test that no wait occurs when under rate limit."""
        start_time = time.time()
        self.rate_limiter.wait_if_needed()
        self.rate_limiter.wait_if_needed()
        end_time = time.time()
        
        # Should complete almost instantly
        self.assertLess(end_time - start_time, 0.1)
    
    @patch('time.sleep')
    def test_wait_when_at_limit(self, mock_sleep):
        """Test that wait occurs when at rate limit."""
        # Make maximum requests
        for _ in range(3):
            self.rate_limiter.wait_if_needed()
        
        # Next request should trigger wait
        self.rate_limiter.wait_if_needed()
        mock_sleep.assert_called_once()
    
    def test_requests_cleanup(self):
        """Test that old requests are cleaned up."""
        # Make requests
        for _ in range(3):
            self.rate_limiter.wait_if_needed()
        
        # Wait for time window to pass
        time.sleep(1.1)
        
        # Should be able to make requests again without waiting
        start_time = time.time()
        self.rate_limiter.wait_if_needed()
        end_time = time.time()
        
        self.assertLess(end_time - start_time, 0.1)


class TestCoinbaseClient(unittest.TestCase):
    """Test CoinbaseClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret=base64.b64encode(b"test_secret").decode(),
            passphrase="test_passphrase",
            sandbox=True
        )
        self.client = CoinbaseClient(self.credentials)
    
    def test_initialization(self):
        """Test client initialization."""
        self.assertEqual(self.client.credentials, self.credentials)
        self.assertIsInstance(self.client.session, requests.Session)
        self.assertIsNotNone(self.client.public_rate_limiter)
        self.assertIsNotNone(self.client.private_rate_limiter)
    
    def test_generate_signature(self):
        """Test HMAC-SHA256 signature generation."""
        timestamp = "1234567890"
        method = "GET"
        path = "/accounts"
        body = ""
        
        signature = self.client._generate_signature(timestamp, method, path, body)
        
        # Verify signature is base64 encoded
        self.assertIsInstance(signature, str)
        try:
            base64.b64decode(signature)
        except Exception:
            self.fail("Signature is not valid base64")
        
        # Verify signature is deterministic
        signature2 = self.client._generate_signature(timestamp, method, path, body)
        self.assertEqual(signature, signature2)
    
    def test_generate_signature_with_body(self):
        """Test signature generation with request body."""
        timestamp = "1234567890"
        method = "POST"
        path = "/orders"
        body = '{"product_id": "BTC-USD", "side": "buy"}'
        
        signature = self.client._generate_signature(timestamp, method, path, body)
        
        # Should be different from signature without body
        signature_no_body = self.client._generate_signature(timestamp, method, path, "")
        self.assertNotEqual(signature, signature_no_body)
    
    def test_get_auth_headers(self):
        """Test authentication headers generation."""
        with patch('time.time', return_value=1234567890.0):
            headers = self.client._get_auth_headers("GET", "/accounts")
        
        expected_keys = [
            'CB-ACCESS-KEY',
            'CB-ACCESS-SIGN',
            'CB-ACCESS-TIMESTAMP',
            'CB-ACCESS-PASSPHRASE',
            'Content-Type'
        ]
        
        for key in expected_keys:
            self.assertIn(key, headers)
        
        self.assertEqual(headers['CB-ACCESS-KEY'], self.credentials.api_key)
        self.assertEqual(headers['CB-ACCESS-TIMESTAMP'], '1234567890.0')
        self.assertEqual(headers['CB-ACCESS-PASSPHRASE'], self.credentials.passphrase)
        self.assertEqual(headers['Content-Type'], 'application/json')
    
    def test_validate_timestamp(self):
        """Test timestamp validation."""
        current_time = time.time()
        
        # Valid timestamp (within tolerance)
        self.assertTrue(self.client._validate_timestamp(current_time))
        self.assertTrue(self.client._validate_timestamp(current_time - 20))
        self.assertTrue(self.client._validate_timestamp(current_time + 20))
        
        # Invalid timestamp (outside tolerance)
        self.assertFalse(self.client._validate_timestamp(current_time - 40))
        self.assertFalse(self.client._validate_timestamp(current_time + 40))
    
    def test_generate_nonce(self):
        """Test nonce generation."""
        nonce1 = self.client._generate_nonce()
        nonce2 = self.client._generate_nonce()
        
        # Nonces should be different
        self.assertNotEqual(nonce1, nonce2)
        
        # Nonces should be valid UUIDs (36 characters with hyphens)
        self.assertEqual(len(nonce1), 36)
        self.assertEqual(len(nonce2), 36)
        self.assertIn('-', nonce1)
        self.assertIn('-', nonce2)
    
    @patch('requests.Session.request')
    def test_make_request_success(self, mock_request):
        """Test successful API request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_request.return_value = mock_response
        
        result = self.client._make_request('GET', '/accounts')
        
        self.assertEqual(result, {"success": True})
        mock_request.assert_called_once()
    
    @patch('requests.Session.request')
    def test_make_request_rate_limit(self, mock_request):
        """Test rate limit handling."""
        # Mock rate limit response, then success
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {'Retry-After': '1'}
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}
        
        mock_request.side_effect = [rate_limit_response, success_response]
        
        with patch('time.sleep') as mock_sleep:
            result = self.client._make_request('GET', '/accounts')
        
        self.assertEqual(result, {"success": True})
        mock_sleep.assert_called_once_with(1)
        self.assertEqual(mock_request.call_count, 2)
    
    @patch('requests.Session.request')
    def test_make_request_http_error(self, mock_request):
        """Test HTTP error handling."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.HTTPError("Bad Request")
        mock_request.return_value = mock_response
        
        with self.assertRaises(requests.HTTPError):
            self.client._make_request('GET', '/accounts')
    
    @patch('requests.Session.request')
    def test_make_request_invalid_json(self, mock_request):
        """Test invalid JSON response handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Invalid response"
        mock_request.return_value = mock_response
        
        with self.assertRaises(ValueError):
            self.client._make_request('GET', '/accounts')
    
    @patch('requests.Session.request')
    def test_make_request_public_endpoint(self, mock_request):
        """Test public endpoint request (no authentication)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "public"}
        mock_request.return_value = mock_response
        
        result = self.client._make_request('GET', '/products', is_private=False)
        
        self.assertEqual(result, {"data": "public"})
        
        # Check that authentication headers were not added
        call_args = mock_request.call_args
        headers = call_args[1]['headers']
        self.assertNotIn('CB-ACCESS-KEY', headers)
        self.assertNotIn('CB-ACCESS-SIGN', headers)
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_test_authentication_success(self, mock_make_request):
        """Test successful authentication test."""
        mock_make_request.return_value = [{"id": "account1"}]
        
        result = self.client.test_authentication()
        
        self.assertTrue(result)
        mock_make_request.assert_called_once_with('GET', '/accounts')
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_test_authentication_failure(self, mock_make_request):
        """Test failed authentication test."""
        mock_make_request.side_effect = requests.HTTPError("Unauthorized")
        
        result = self.client.test_authentication()
        
        self.assertFalse(result)
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_get_accounts(self, mock_make_request):
        """Test get_accounts method."""
        expected_accounts = [{"id": "account1"}, {"id": "account2"}]
        mock_make_request.return_value = expected_accounts
        
        result = self.client.get_accounts()
        
        self.assertEqual(result, expected_accounts)
        mock_make_request.assert_called_once_with('GET', '/accounts')
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_get_account(self, mock_make_request):
        """Test get_account method."""
        account_id = "test-account-id"
        expected_account = {"id": account_id, "balance": "100.00"}
        mock_make_request.return_value = expected_account
        
        result = self.client.get_account(account_id)
        
        self.assertEqual(result, expected_account)
        mock_make_request.assert_called_once_with('GET', f'/accounts/{account_id}')
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_create_order(self, mock_make_request):
        """Test create_order method."""
        order_params = {
            "product_id": "BTC-USD",
            "side": "buy",
            "type": "market",
            "size": "0.01"
        }
        expected_response = {"id": "order-id", "status": "pending"}
        mock_make_request.return_value = expected_response
        
        result = self.client.create_order(order_params)
        
        self.assertEqual(result, expected_response)
        mock_make_request.assert_called_once_with('POST', '/orders', data=order_params)
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_cancel_order(self, mock_make_request):
        """Test cancel_order method."""
        order_id = "test-order-id"
        expected_response = {"id": order_id, "status": "cancelled"}
        mock_make_request.return_value = expected_response
        
        result = self.client.cancel_order(order_id)
        
        self.assertEqual(result, expected_response)
        mock_make_request.assert_called_once_with('DELETE', f'/orders/{order_id}')
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_get_order(self, mock_make_request):
        """Test get_order method."""
        order_id = "test-order-id"
        expected_order = {"id": order_id, "status": "filled"}
        mock_make_request.return_value = expected_order
        
        result = self.client.get_order(order_id)
        
        self.assertEqual(result, expected_order)
        mock_make_request.assert_called_once_with('GET', f'/orders/{order_id}')
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_list_orders(self, mock_make_request):
        """Test list_orders method."""
        expected_orders = [{"id": "order1"}, {"id": "order2"}]
        mock_make_request.return_value = expected_orders
        
        result = self.client.list_orders()
        
        self.assertEqual(result, expected_orders)
        mock_make_request.assert_called_once_with('GET', '/orders', params={})
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_list_orders_with_filters(self, mock_make_request):
        """Test list_orders method with filters."""
        expected_orders = [{"id": "order1"}]
        mock_make_request.return_value = expected_orders
        
        result = self.client.list_orders(status="open", product_id="BTC-USD")
        
        self.assertEqual(result, expected_orders)
        expected_params = {"status": "open", "product_id": "BTC-USD"}
        mock_make_request.assert_called_once_with('GET', '/orders', params=expected_params)
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_get_products(self, mock_make_request):
        """Test get_products method."""
        expected_products = [{"id": "BTC-USD"}, {"id": "ETH-USD"}]
        mock_make_request.return_value = expected_products
        
        result = self.client.get_products()
        
        self.assertEqual(result, expected_products)
        mock_make_request.assert_called_once_with('GET', '/products', is_private=False)
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_get_product_ticker(self, mock_make_request):
        """Test get_product_ticker method."""
        product_id = "BTC-USD"
        expected_ticker = {"price": "50000.00", "volume": "100.0"}
        mock_make_request.return_value = expected_ticker
        
        result = self.client.get_product_ticker(product_id)
        
        self.assertEqual(result, expected_ticker)
        mock_make_request.assert_called_once_with('GET', f'/products/{product_id}/ticker', is_private=False)
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_get_product_candles(self, mock_make_request):
        """Test get_product_candles method."""
        product_id = "BTC-USD"
        start = "2023-01-01T00:00:00Z"
        end = "2023-01-02T00:00:00Z"
        granularity = 3600
        expected_candles = [[1672531200, 50000, 51000, 49000, 50500, 100]]
        mock_make_request.return_value = expected_candles
        
        result = self.client.get_product_candles(product_id, start, end, granularity)
        
        self.assertEqual(result, expected_candles)
        expected_params = {
            'start': start,
            'end': end,
            'granularity': granularity
        }
        mock_make_request.assert_called_once_with(
            'GET', f'/products/{product_id}/candles', 
            params=expected_params, is_private=False
        )
    
    @patch.object(CoinbaseClient, '_make_request')
    def test_get_product_stats(self, mock_make_request):
        """Test get_product_stats method."""
        product_id = "BTC-USD"
        expected_stats = {"high": "51000", "low": "49000", "volume": "1000"}
        mock_make_request.return_value = expected_stats
        
        result = self.client.get_product_stats(product_id)
        
        self.assertEqual(result, expected_stats)
        mock_make_request.assert_called_once_with('GET', f'/products/{product_id}/stats', is_private=False)


if __name__ == '__main__':
    unittest.main()