"""
Integration tests for the Coinbase error handler.

These tests verify that the Coinbase error handler works correctly with
the Coinbase client and other components in realistic scenarios.
"""
import unittest
import json
import time
from unittest.mock import MagicMock, patch, Mock
import requests
import pytest

from bot.coinbase_error_handler import (
    CoinbaseErrorHandler, CoinbaseErrorCategory, CoinbaseErrorConfig,
    handle_coinbase_error
)
from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials
from bot.error_handler import ErrorCategory


class TestCoinbaseErrorHandlerIntegration:
    """Integration tests for the CoinbaseErrorHandler with CoinbaseClient"""
    
    @pytest.fixture
    def credentials(self):
        """Create test credentials"""
        return CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
    
    @pytest.fixture
    def client(self, credentials):
        """Create test client"""
        return CoinbaseClient(credentials)
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler"""
        return CoinbaseErrorHandler()
    
    def test_handle_authentication_error_integration(self, client, error_handler):
        """Test handling authentication errors with client integration"""
        # Mock a 401 response for invalid credentials
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 401
        mock_response.text = json.dumps({"message": "Invalid API key"})
        mock_response.json = MagicMock(return_value={"message": "Invalid API key"})
        
        # Create an authentication error
        error = requests.exceptions.HTTPError("401 Client Error: Unauthorized")
        error.response = mock_response
        
        # Handle the error
        with patch.object(error_handler, 'handle_authentication_error', return_value=False) as mock_auth_handler:
            result = error_handler.handle_coinbase_error(error, "coinbase_client", mock_response)
            
            # Verify authentication handler was called
            mock_auth_handler.assert_called_once()
    
    def test_handle_rate_limit_error_integration(self, client, error_handler):
        """Test handling rate limit errors with client integration"""
        # Mock a 429 response for rate limiting
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 429
        mock_response.text = json.dumps({"message": "Rate limit exceeded"})
        mock_response.json = MagicMock(return_value={"message": "Rate limit exceeded"})
        mock_response.headers = {"Retry-After": "5"}
        
        # Create a rate limit error
        error = requests.exceptions.HTTPError("429 Client Error: Too Many Requests")
        error.response = mock_response
        
        # Handle the error
        with patch.object(error_handler, 'handle_rate_limit_error', return_value=True) as mock_rate_handler:
            result = error_handler.handle_coinbase_error(error, "coinbase_client", mock_response)
            
            # Verify rate limit handler was called
            mock_rate_handler.assert_called_once()
    
    def test_handle_order_error_integration(self, client, error_handler):
        """Test handling order errors with client integration"""
        # Mock a 400 response for invalid order
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.text = json.dumps({"message": "Size too small"})
        mock_response.json = MagicMock(return_value={"message": "Size too small"})
        
        # Create an order error
        error = requests.exceptions.HTTPError("400 Client Error: Bad Request")
        error.response = mock_response
        
        # Order parameters
        order_params = {
            "type": "limit",
            "side": "buy",
            "size": 0.0001,
            "price": 50000.0
        }
        
        # Handle the error
        with patch.object(error_handler, 'handle_order_error', return_value=(True, {"size": 0.001})) as mock_order_handler:
            result = error_handler.handle_coinbase_error(
                error, "coinbase_client", mock_response, {"order_params": order_params}
            )
            
            # Verify order handler was called
            mock_order_handler.assert_called_once()
    
    def test_handle_network_error_integration(self, client, error_handler):
        """Test handling network errors with client integration"""
        # Create a network error
        error = requests.exceptions.ConnectionError("Connection refused")
        
        # Handle the error
        with patch.object(error_handler, 'handle_network_error', return_value=True) as mock_network_handler:
            result = error_handler.handle_coinbase_error(error, "coinbase_client")
            
            # Verify network handler was called
            mock_network_handler.assert_called_once()
    
    def test_error_recovery_flow(self, client, error_handler):
        """Test complete error recovery flow"""
        # Mock client's _make_request method to simulate errors and recovery
        original_make_request = client._make_request
        
        # Counter for tracking retry attempts
        attempts = [0]
        
        def mock_make_request(method, endpoint, params=None, data=None, is_private=True):
            attempts[0] += 1
            
            if attempts[0] == 1:
                # First attempt: rate limit error
                mock_response = Mock(spec=requests.Response)
                mock_response.status_code = 429
                mock_response.text = json.dumps({"message": "Rate limit exceeded"})
                mock_response.json = MagicMock(return_value={"message": "Rate limit exceeded"})
                mock_response.headers = {"Retry-After": "1"}
                
                error = requests.exceptions.HTTPError("429 Client Error: Too Many Requests")
                error.response = mock_response
                raise error
            elif attempts[0] == 2:
                # Second attempt: network error
                raise requests.exceptions.ConnectionError("Connection refused")
            else:
                # Third attempt: success
                return {"success": True}
        
        try:
            # Replace client's _make_request method
            client._make_request = mock_make_request
            
            # Attempt to make a request with error handling
            max_retries = 5
            retry_count = 0
            result = None
            
            while retry_count < max_retries:
                try:
                    # Attempt the request
                    result = client._make_request("GET", "/test")
                    break  # Success, exit the loop
                except Exception as e:
                    # Handle the error
                    retry = error_handler.handle_coinbase_error(
                        e, "coinbase_client", getattr(e, "response", None)
                    )
                    
                    if not retry:
                        # Can't recover, re-raise the error
                        raise
                    
                    retry_count += 1
            
            # Verify we got a successful result after retries
            assert result is not None
            assert result == {"success": True}
            assert attempts[0] == 3  # Took 3 attempts
            
        finally:
            # Restore original method
            client._make_request = original_make_request
    
    def test_error_metrics_integration(self, client, error_handler):
        """Test error metrics integration"""
        # Create various errors
        auth_error = requests.exceptions.HTTPError("401 Client Error: Unauthorized")
        auth_response = Mock(spec=requests.Response)
        auth_response.status_code = 401
        auth_response.text = json.dumps({"message": "Invalid API key"})
        auth_response.json = MagicMock(return_value={"message": "Invalid API key"})
        auth_error.response = auth_response
        
        rate_error = requests.exceptions.HTTPError("429 Client Error: Too Many Requests")
        rate_response = Mock(spec=requests.Response)
        rate_response.status_code = 429
        rate_response.text = json.dumps({"message": "Rate limit exceeded"})
        rate_response.json = MagicMock(return_value={"message": "Rate limit exceeded"})
        rate_response.headers = {}
        rate_error.response = rate_response
        
        network_error = requests.exceptions.ConnectionError("Connection refused")
        
        # Handle the errors
        with patch.object(error_handler.error_handler, 'handle_error', return_value=False):
            error_handler.handle_coinbase_error(auth_error, "coinbase_client", auth_response)
            error_handler.handle_coinbase_error(rate_error, "coinbase_client", rate_response)
            error_handler.handle_coinbase_error(network_error, "coinbase_client")
        
        # Get metrics
        metrics = error_handler.get_error_metrics()
        
        # Verify metrics
        assert metrics['coinbase_errors']['AUTH_INVALID_KEY'] == 1
        assert metrics['coinbase_errors']['RATE_LIMIT_EXCEEDED'] == 1
        assert metrics['coinbase_errors']['NETWORK_CONNECTION_ERROR'] == 1
        assert metrics['recent_coinbase_errors'] == 3
        
        # Reset metrics
        error_handler.reset_metrics()
        
        # Verify metrics were reset
        metrics = error_handler.get_error_metrics()
        assert metrics['coinbase_errors']['AUTH_INVALID_KEY'] == 0
        assert metrics['recent_coinbase_errors'] == 0


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
"""