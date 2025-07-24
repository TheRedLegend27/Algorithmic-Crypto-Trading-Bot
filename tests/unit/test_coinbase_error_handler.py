"""
Unit tests for the Coinbase error handler module.
"""
import unittest
import json
import time
from unittest.mock import MagicMock, patch, Mock
import requests

from bot.coinbase_error_handler import (
    CoinbaseErrorHandler, CoinbaseErrorCategory, CoinbaseErrorConfig,
    handle_coinbase_error, global_coinbase_error_handler
)
from bot.error_handler import ErrorCategory


class TestCoinbaseErrorHandler(unittest.TestCase):
    """Test cases for the CoinbaseErrorHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.logger = MagicMock()
        self.config = CoinbaseErrorConfig()
        self.error_handler = CoinbaseErrorHandler(config=self.config, logger=self.logger)
    
    def test_categorize_coinbase_error_authentication(self):
        """Test categorization of authentication errors"""
        # Invalid API key
        error = Exception("Invalid API key")
        response = Mock(spec=requests.Response)
        response.status_code = 401
        response.text = json.dumps({"message": "Invalid API key"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.AUTH_INVALID_KEY)
        
        # Invalid signature
        error = Exception("Invalid signature")
        response.text = json.dumps({"message": "Invalid signature"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.AUTH_INVALID_SIGNATURE)
        
        # Invalid passphrase
        error = Exception("Invalid passphrase")
        response.text = json.dumps({"message": "Invalid passphrase"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.AUTH_INVALID_PASSPHRASE)
        
        # Expired token
        error = Exception("Token expired")
        response.text = json.dumps({"message": "Token expired"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.AUTH_EXPIRED_TOKEN)
    
    def test_categorize_coinbase_error_rate_limit(self):
        """Test categorization of rate limit errors"""
        error = Exception("Rate limit exceeded")
        response = Mock(spec=requests.Response)
        response.status_code = 429
        response.text = json.dumps({"message": "Rate limit exceeded"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED)
    
    def test_categorize_coinbase_error_order(self):
        """Test categorization of order errors"""
        # Insufficient funds
        error = Exception("Insufficient funds")
        response = Mock(spec=requests.Response)
        response.status_code = 400
        response.text = json.dumps({"message": "Insufficient funds"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.ORDER_INSUFFICIENT_FUNDS)
        
        # Invalid size
        error = Exception("Size too small")
        response.text = json.dumps({"message": "Size too small"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.ORDER_INVALID_SIZE)
        
        # Invalid price
        error = Exception("Invalid price")
        response.text = json.dumps({"message": "Invalid price"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.ORDER_INVALID_PRICE)
        
        # Duplicate order
        error = Exception("Duplicate order")
        response.text = json.dumps({"message": "Duplicate order"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.ORDER_DUPLICATE)
        
        # Post only failed
        error = Exception("Post only order failed")
        response.text = json.dumps({"message": "Post only order failed"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.ORDER_POST_ONLY_FAILED)
        
        # Order not found
        error = Exception("Order not found")
        response.text = json.dumps({"message": "Order not found"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.ORDER_NOT_FOUND)
    
    def test_categorize_coinbase_error_market_data(self):
        """Test categorization of market data errors"""
        # Invalid product
        error = Exception("Invalid product")
        response = Mock(spec=requests.Response)
        response.status_code = 400
        response.text = json.dumps({"message": "Invalid product"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.MARKET_INVALID_PRODUCT)
        
        # Product not available
        error = Exception("Product not available")
        response.text = json.dumps({"message": "Product not available"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.MARKET_PRODUCT_NOT_AVAILABLE)
    
    def test_categorize_coinbase_error_network(self):
        """Test categorization of network errors"""
        # Connection error
        error = requests.ConnectionError("Connection error")
        
        category = self.error_handler.categorize_coinbase_error(error)
        self.assertEqual(category, CoinbaseErrorCategory.NETWORK_CONNECTION_ERROR)
        
        # Timeout
        error = requests.Timeout("Timeout error")
        
        category = self.error_handler.categorize_coinbase_error(error)
        self.assertEqual(category, CoinbaseErrorCategory.NETWORK_TIMEOUT)
        
        # DNS error
        error = Exception("DNS resolution failed")
        
        category = self.error_handler.categorize_coinbase_error(error)
        self.assertEqual(category, CoinbaseErrorCategory.NETWORK_DNS_ERROR)
    
    def test_categorize_coinbase_error_system(self):
        """Test categorization of system errors"""
        # Maintenance
        error = Exception("System under maintenance")
        response = Mock(spec=requests.Response)
        response.status_code = 503
        response.text = json.dumps({"message": "System under maintenance"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.SYSTEM_MAINTENANCE)
        
        # Overloaded
        error = Exception("System overloaded")
        response.text = json.dumps({"message": "System overloaded"})
        
        category = self.error_handler.categorize_coinbase_error(error, response)
        self.assertEqual(category, CoinbaseErrorCategory.SYSTEM_OVERLOADED)
    
    def test_map_to_error_category(self):
        """Test mapping Coinbase error categories to base error categories"""
        # Authentication errors
        self.assertEqual(
            self.error_handler.map_to_error_category(CoinbaseErrorCategory.AUTH_INVALID_KEY),
            ErrorCategory.API_ERROR
        )
        
        # Rate limiting errors
        self.assertEqual(
            self.error_handler.map_to_error_category(CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED),
            ErrorCategory.API_ERROR
        )
        
        # Order errors
        self.assertEqual(
            self.error_handler.map_to_error_category(CoinbaseErrorCategory.ORDER_INSUFFICIENT_FUNDS),
            ErrorCategory.API_ERROR
        )
        
        # Market data errors
        self.assertEqual(
            self.error_handler.map_to_error_category(CoinbaseErrorCategory.MARKET_INVALID_PRODUCT),
            ErrorCategory.DATA_ERROR
        )
        
        # Network errors
        self.assertEqual(
            self.error_handler.map_to_error_category(CoinbaseErrorCategory.NETWORK_CONNECTION_ERROR),
            ErrorCategory.NETWORK_ERROR
        )
        
        # System errors
        self.assertEqual(
            self.error_handler.map_to_error_category(CoinbaseErrorCategory.SYSTEM_MAINTENANCE),
            ErrorCategory.SYSTEM_ERROR
        )
        
        # None category
        self.assertEqual(
            self.error_handler.map_to_error_category(None),
            ErrorCategory.RUNTIME_ERROR
        )
    
    def test_handle_coinbase_error(self):
        """Test handling Coinbase errors"""
        # Mock the base error handler
        self.error_handler.error_handler.handle_error = MagicMock(return_value=True)
        
        # Create a test error
        error = Exception("Test error")
        response = Mock(spec=requests.Response)
        response.status_code = 429
        response.text = json.dumps({"message": "Rate limit exceeded"})
        response.headers = {"Retry-After": "5"}
        response.json = MagicMock(return_value={"message": "Rate limit exceeded"})
        
        # Handle the error
        result = self.error_handler.handle_coinbase_error(
            error, "test_component", response, {"test": "info"}
        )
        
        # Verify the error was handled
        self.assertTrue(result)
        self.error_handler.error_handler.handle_error.assert_called_once()
        
        # Verify error metrics were updated
        self.assertEqual(
            self.error_handler.coinbase_error_counts[CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED],
            1
        )
        self.assertEqual(len(self.error_handler.recent_coinbase_errors), 1)
    
    def test_handle_authentication_error(self):
        """Test handling authentication errors"""
        # Invalid key error
        error = Exception("Invalid API key")
        response = Mock(spec=requests.Response)
        response.status_code = 401
        response.text = json.dumps({"message": "Invalid API key"})
        
        # Should not recover from invalid key
        result = self.error_handler.handle_authentication_error(error, "test_component", response)
        self.assertFalse(result)
        
        # Expired token with retry enabled
        self.error_handler.config.auth_error_retry = True
        error = Exception("Token expired")
        response.text = json.dumps({"message": "Token expired"})
        
        # Should attempt recovery
        result = self.error_handler.handle_authentication_error(error, "test_component", response)
        self.assertTrue(result)
        
        # Non-authentication error
        error = Exception("Some other error")
        response.status_code = 400
        response.text = json.dumps({"message": "Some other error"})
        
        # Should not handle non-authentication errors
        result = self.error_handler.handle_authentication_error(error, "test_component", response)
        self.assertFalse(result)
    
    def test_handle_rate_limit_error(self):
        """Test handling rate limit errors"""
        # Rate limit error with Retry-After header
        error = Exception("Rate limit exceeded")
        response = Mock(spec=requests.Response)
        response.status_code = 429
        response.text = json.dumps({"message": "Rate limit exceeded"})
        response.headers = {"Retry-After": "5"}
        
        with patch("time.sleep") as mock_sleep:
            result = self.error_handler.handle_rate_limit_error(error, "test_component", response)
            self.assertTrue(result)
            mock_sleep.assert_called_once_with(5)
        
        # Rate limit error without Retry-After header
        response.headers = {}
        
        with patch("time.sleep") as mock_sleep:
            result = self.error_handler.handle_rate_limit_error(error, "test_component", response)
            self.assertTrue(result)
            mock_sleep.assert_called_once()
        
        # Non-rate limit error
        error = Exception("Some other error")
        response.status_code = 400
        response.text = json.dumps({"message": "Some other error"})
        
        # Should not handle non-rate limit errors
        result = self.error_handler.handle_rate_limit_error(error, "test_component", response)
        self.assertFalse(result)
    
    def test_handle_order_error(self):
        """Test handling order errors"""
        # Invalid size error
        error = Exception("Size must be at least 0.001")
        response = Mock(spec=requests.Response)
        response.status_code = 400
        response.text = json.dumps({"message": "Size must be at least 0.001"})
        
        order_params = {"type": "limit", "side": "buy", "size": 0.0005, "price": 50000.0}
        
        success, modified_params = self.error_handler.handle_order_error(
            error, "test_component", response, order_params
        )
        
        self.assertTrue(success)
        self.assertEqual(modified_params["size"], 0.001)
        
        # Invalid price error
        error = Exception("Invalid price")
        response.text = json.dumps({"message": "Invalid price"})
        
        order_params = {"type": "limit", "side": "buy", "size": 0.001, "price": -50000.0}
        
        success, modified_params = self.error_handler.handle_order_error(
            error, "test_component", response, order_params
        )
        
        self.assertTrue(success)
        self.assertEqual(modified_params["type"], "market")
        self.assertNotIn("price", modified_params)
        
        # Post-only failed error
        error = Exception("Post only order failed")
        response.text = json.dumps({"message": "Post only order failed"})
        
        order_params = {"type": "limit", "side": "buy", "size": 0.001, "price": 50000.0, "post_only": True}
        
        success, modified_params = self.error_handler.handle_order_error(
            error, "test_component", response, order_params
        )
        
        self.assertTrue(success)
        self.assertFalse(modified_params["post_only"])
        
        # Insufficient funds error (can't recover)
        error = Exception("Insufficient funds")
        response.text = json.dumps({"message": "Insufficient funds"})
        
        order_params = {"type": "market", "side": "buy", "size": 1.0}
        
        success, modified_params = self.error_handler.handle_order_error(
            error, "test_component", response, order_params
        )
        
        self.assertFalse(success)
        
        # Non-order error
        error = Exception("Some other error")
        response.status_code = 400
        response.text = json.dumps({"message": "Some other error"})
        
        # Should not handle non-order errors
        success, modified_params = self.error_handler.handle_order_error(
            error, "test_component", response, order_params
        )
        
        self.assertFalse(success)
        self.assertEqual(modified_params, {})
    
    def test_handle_network_error(self):
        """Test handling network errors"""
        # Connection error
        error = requests.ConnectionError("Connection error")
        
        with patch("time.sleep") as mock_sleep:
            result = self.error_handler.handle_network_error(error, "test_component")
            self.assertTrue(result)
            mock_sleep.assert_called()
        
        # Timeout error
        error = requests.Timeout("Timeout error")
        
        with patch("time.sleep") as mock_sleep:
            result = self.error_handler.handle_network_error(error, "test_component")
            self.assertTrue(result)
            mock_sleep.assert_called()
        
        # Non-network error
        error = Exception("Some other error")
        
        # Should not handle non-network errors
        result = self.error_handler.handle_network_error(error, "test_component")
        self.assertFalse(result)
    
    def test_get_error_metrics(self):
        """Test getting error metrics"""
        # Add some errors
        self.error_handler.coinbase_error_counts[CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED] = 5
        self.error_handler.coinbase_error_counts[CoinbaseErrorCategory.NETWORK_TIMEOUT] = 3
        
        # Add a recent error
        self.error_handler.recent_coinbase_errors.append({
            'timestamp': time.time(),
            'error_type': 'Exception',
            'error_message': 'Test error',
            'component': 'test_component',
            'coinbase_category': CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED.value,
            'response_code': 429,
            'additional_info': {}
        })
        
        # Mock base metrics
        self.error_handler.error_handler.get_error_metrics = MagicMock(return_value={
            'counts': {'API_ERROR': 5, 'NETWORK_ERROR': 3},
            'recent': 1,
            'categories': {'API_ERROR': 'api_error', 'NETWORK_ERROR': 'network_error'}
        })
        
        # Get metrics
        metrics = self.error_handler.get_error_metrics()
        
        # Verify metrics
        self.assertEqual(metrics['counts']['API_ERROR'], 5)
        self.assertEqual(metrics['counts']['NETWORK_ERROR'], 3)
        self.assertEqual(metrics['coinbase_errors']['RATE_LIMIT_EXCEEDED'], 5)
        self.assertEqual(metrics['coinbase_errors']['NETWORK_TIMEOUT'], 3)
        self.assertEqual(metrics['recent_coinbase_errors'], 1)
    
    def test_reset_metrics(self):
        """Test resetting error metrics"""
        # Add some errors
        self.error_handler.coinbase_error_counts[CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED] = 5
        self.error_handler.recent_coinbase_errors.append({
            'timestamp': time.time(),
            'error_type': 'Exception',
            'error_message': 'Test error',
            'component': 'test_component',
            'coinbase_category': CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED.value,
            'response_code': 429,
            'additional_info': {}
        })
        
        # Reset metrics
        self.error_handler.reset_metrics()
        
        # Verify metrics were reset
        self.assertEqual(self.error_handler.coinbase_error_counts[CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED], 0)
        self.assertEqual(len(self.error_handler.recent_coinbase_errors), 0)
    
    def test_global_handler(self):
        """Test the global error handler"""
        # Mock the handle_coinbase_error method
        original_method = global_coinbase_error_handler.handle_coinbase_error
        global_coinbase_error_handler.handle_coinbase_error = MagicMock(return_value=True)
        
        try:
            # Use the global handler function
            error = Exception("Test error")
            result = handle_coinbase_error(error, "test_component")
            
            # Verify the global handler was used
            self.assertTrue(result)
            global_coinbase_error_handler.handle_coinbase_error.assert_called_once_with(
                error, "test_component", None, None
            )
        finally:
            # Restore the original method
            global_coinbase_error_handler.handle_coinbase_error = original_method


if __name__ == "__main__":
    unittest.main()