"""
Tests for Coinbase WebSocket connection stability and recovery.
Tests WebSocket reconnection logic, message handling, and error recovery.
"""
import unittest
import pytest
from unittest.mock import patch, Mock, MagicMock
import json
import time
from datetime import datetime, timedelta
import threading
import os
import websocket

from bot.config import Config
from bot.coinbase_client import CoinbaseClient
from bot.coinbase_websocket import CoinbaseWebSocket
from bot.coinbase_error_handler import CoinbaseErrorHandler


class TestCoinbaseWebSocketStability:
    """Tests for Coinbase WebSocket connection stability and recovery."""
    
    @pytest.fixture
    def setup_environment(self):
        """Set up environment variables for testing."""
        original_env = os.environ.copy()
        os.environ.update({
            'COINBASE_API_KEY': 'test_key',
            'COINBASE_API_SECRET': 'dGVzdF9zZWNyZXQ=',  # base64 encoded "test_secret"
            'COINBASE_PASSPHRASE': 'test_passphrase',
            'COINBASE_SANDBOX': 'True'
        })
        yield
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
    
    @pytest.fixture
    def config(self, setup_environment):
        """Create test configuration."""
        config = Config()
        config.load_env_variables()
        return config
    
    @pytest.fixture
    def credentials(self, config):
        """Get Coinbase credentials from config."""
        return config.get_coinbase_credentials()
    
    @pytest.fixture
    def crypto_settings(self, config):
        """Get crypto trading settings from config."""
        return config.get_crypto_trading_settings()
    
    @pytest.fixture
    def mock_coinbase_client(self, credentials):
        """Create mock Coinbase client."""
        with patch('bot.coinbase_client.requests.Session'):
            client = CoinbaseClient(credentials)
            return client
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler."""
        return CoinbaseErrorHandler()
    
    @pytest.fixture
    def websocket_client(self, mock_coinbase_client, crypto_settings, error_handler):
        """Create WebSocket client."""
        websocket = CoinbaseWebSocket(mock_coinbase_client, crypto_settings, error_handler)
        return websocket
    
    def test_websocket_connection_and_authentication(self, websocket_client, mock_coinbase_client):
        """Test WebSocket connection and authentication."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Mock WebSocket.WebSocketApp
        with patch('websocket.WebSocketApp', return_value=mock_ws):
            # Mock authentication response
            mock_ws.recv = Mock(return_value=json.dumps({
                'type': 'subscriptions',
                'channels': [{'name': 'ticker'}]
            }))
            
            # Connect to WebSocket
            websocket_client.connect()
            
            # Verify WebSocketApp was created
            assert websocket_client._ws is not None
            
            # Verify authentication message was sent
            mock_ws.send.assert_called()
            
            # Verify connection status
            assert websocket_client.is_connected() is True
    
    def test_websocket_subscription(self, websocket_client):
        """Test WebSocket subscription to channels."""
        # Mock WebSocket connection
        mock_ws = Mock()
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Subscribe to ticker channel
        websocket_client.subscribe(['ticker'], ['BTC-USD'])
        
        # Verify subscription message was sent
        mock_ws.send.assert_called_once()
        
        # Verify subscription message format
        call_args = mock_ws.send.call_args[0][0]
        subscription_msg = json.loads(call_args)
        assert subscription_msg['type'] == 'subscribe'
        assert 'ticker' in subscription_msg['channels']
        assert 'BTC-USD' in subscription_msg['product_ids']
    
    def test_websocket_message_processing(self, websocket_client):
        """Test WebSocket message processing."""
        # Create test message
        test_message = json.dumps({
            'type': 'ticker',
            'product_id': 'BTC-USD',
            'price': '45100.0',
            'time': datetime.now().isoformat()
        })
        
        # Process message
        websocket_client._process_message(test_message)
        
        # Verify price was updated
        assert websocket_client.get_latest_price('BTC-USD') == 45100.0
    
    def test_websocket_reconnection_logic(self, websocket_client):
        """Test WebSocket reconnection logic."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Mock _connect_websocket method
        with patch.object(websocket_client, '_connect_websocket') as mock_connect:
            mock_connect.return_value = True
            
            # Simulate connection close
            websocket_client._on_close(mock_ws)
            
            # Verify reconnection was attempted
            assert mock_connect.call_count >= 1
            
            # Verify connection status was updated
            assert websocket_client._connected is True
    
    def test_websocket_error_handling(self, websocket_client):
        """Test WebSocket error handling."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Mock error handler
        with patch.object(websocket_client.error_handler, 'handle_websocket_error') as mock_handle_error:
            # Simulate error
            websocket_client._on_error(mock_ws, Exception("Test error"))
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
    
    def test_websocket_message_handling_with_errors(self, websocket_client):
        """Test WebSocket message handling with errors."""
        # Create invalid message
        invalid_message = "invalid json"
        
        # Process message with error handling
        with patch.object(websocket_client.error_handler, 'handle_websocket_error') as mock_handle_error:
            websocket_client._process_message(invalid_message)
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
    
    def test_websocket_heartbeat(self, websocket_client):
        """Test WebSocket heartbeat mechanism."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Process heartbeat message
        heartbeat_message = json.dumps({
            'type': 'heartbeat',
            'time': datetime.now().isoformat()
        })
        
        # Process message
        websocket_client._process_message(heartbeat_message)
        
        # Verify heartbeat was processed
        assert websocket_client._last_heartbeat is not None
    
    def test_websocket_connection_stability_simulation(self, websocket_client):
        """Test WebSocket connection stability over time."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Mock _connect_websocket method
        reconnect_count = [0]
        
        def mock_connect():
            reconnect_count[0] += 1
            return True
        
        websocket_client._connect_websocket = mock_connect
        
        # Simulate multiple connection closes
        for _ in range(5):
            websocket_client._on_close(mock_ws)
        
        # Verify reconnection was attempted multiple times
        assert reconnect_count[0] >= 5
    
    def test_websocket_backoff_strategy(self, websocket_client):
        """Test WebSocket reconnection backoff strategy."""
        # Mock time.sleep to measure delay
        sleep_times = []
        
        def mock_sleep(seconds):
            sleep_times.append(seconds)
        
        # Mock WebSocket connection that fails
        def mock_connect_fail(*args, **kwargs):
            raise websocket.WebSocketException("Connection failed")
        
        # Patch methods
        with patch('time.sleep', side_effect=mock_sleep):
            with patch('websocket.create_connection', side_effect=mock_connect_fail):
                # Attempt to connect multiple times
                for _ in range(3):
                    try:
                        websocket_client._connect_websocket()
                    except:
                        pass
        
        # Verify backoff strategy
        assert len(sleep_times) >= 2
        # Verify increasing delays (exponential backoff)
        if len(sleep_times) >= 2:
            assert sleep_times[1] > sleep_times[0]
    
    def test_websocket_recovery_after_network_interruption(self, websocket_client):
        """Test WebSocket recovery after network interruption."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Mock _connect_websocket method
        connection_attempts = [0]
        connection_success = [False, False, True]  # Fail twice, then succeed
        
        def mock_connect():
            result = connection_success[min(connection_attempts[0], len(connection_success) - 1)]
            connection_attempts[0] += 1
            return result
        
        websocket_client._connect_websocket = mock_connect
        
        # Simulate network interruption
        websocket_client._on_close(mock_ws)
        
        # Verify connection status after recovery
        assert websocket_client._connected is True
        assert connection_attempts[0] >= 3
    
    def test_websocket_data_consistency(self, websocket_client):
        """Test WebSocket data consistency during reconnections."""
        # Set initial price
        websocket_client._prices['BTC-USD'] = 45000.0
        
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Simulate reconnection
        websocket_client._on_close(mock_ws)
        
        # Verify price data is preserved
        assert websocket_client.get_latest_price('BTC-USD') == 45000.0
        
        # Update price after reconnection
        new_message = json.dumps({
            'type': 'ticker',
            'product_id': 'BTC-USD',
            'price': '46000.0',
            'time': datetime.now().isoformat()
        })
        websocket_client._process_message(new_message)
        
        # Verify price was updated
        assert websocket_client.get_latest_price('BTC-USD') == 46000.0
    
    def test_websocket_multiple_product_handling(self, websocket_client):
        """Test WebSocket handling of multiple products."""
        # Subscribe to multiple products
        websocket_client._ws = Mock()
        websocket_client._connected = True
        websocket_client.subscribe(['ticker'], ['BTC-USD', 'ETH-USD', 'SOL-USD'])
        
        # Process messages for different products
        products = ['BTC-USD', 'ETH-USD', 'SOL-USD']
        prices = [45000.0, 3000.0, 100.0]
        
        for i, product in enumerate(products):
            message = json.dumps({
                'type': 'ticker',
                'product_id': product,
                'price': str(prices[i]),
                'time': datetime.now().isoformat()
            })
            websocket_client._process_message(message)
        
        # Verify all prices were updated
        for i, product in enumerate(products):
            assert websocket_client.get_latest_price(product) == prices[i]
    
    def test_websocket_long_running_stability(self, websocket_client):
        """Test WebSocket stability in long-running scenario."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Track connection status over time
        connection_status = []
        
        # Simulate long-running scenario with periodic checks
        for _ in range(10):
            # Record connection status
            connection_status.append(websocket_client.is_connected())
            
            # Simulate random events
            if _ % 3 == 0:
                # Simulate connection close
                websocket_client._on_close(mock_ws)
            elif _ % 3 == 1:
                # Simulate error
                websocket_client._on_error(mock_ws, Exception("Test error"))
            else:
                # Simulate heartbeat
                heartbeat_message = json.dumps({
                    'type': 'heartbeat',
                    'time': datetime.now().isoformat()
                })
                websocket_client._process_message(heartbeat_message)
        
        # Verify connection remained stable
        assert all(connection_status)
    
    def test_websocket_thread_safety(self, websocket_client):
        """Test WebSocket thread safety for concurrent access."""
        # Set up WebSocket
        websocket_client._ws = Mock()
        websocket_client._connected = True
        
        # Initialize price
        websocket_client._prices['BTC-USD'] = 45000.0
        
        # Create threads for concurrent access
        threads = []
        exceptions = []
        
        def update_price():
            try:
                # Update price in a thread
                for i in range(10):
                    message = json.dumps({
                        'type': 'ticker',
                        'product_id': 'BTC-USD',
                        'price': str(45000.0 + i),
                        'time': datetime.now().isoformat()
                    })
                    websocket_client._process_message(message)
            except Exception as e:
                exceptions.append(e)
        
        def read_price():
            try:
                # Read price in a thread
                for _ in range(10):
                    price = websocket_client.get_latest_price('BTC-USD')
            except Exception as e:
                exceptions.append(e)
        
        # Create and start threads
        for _ in range(5):
            threads.append(threading.Thread(target=update_price))
            threads.append(threading.Thread(target=read_price))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no exceptions occurred
        assert len(exceptions) == 0
        
        # Verify final price is within expected range
        final_price = websocket_client.get_latest_price('BTC-USD')
        assert 45000.0 <= final_price <= 45009.0


class TestCoinbaseWebSocketIntegrationWithErrorHandler:
    """Test WebSocket integration with error handler."""
    
    @pytest.fixture
    def setup_environment(self):
        """Set up environment variables for testing."""
        original_env = os.environ.copy()
        os.environ.update({
            'COINBASE_API_KEY': 'test_key',
            'COINBASE_API_SECRET': 'dGVzdF9zZWNyZXQ=',  # base64 encoded "test_secret"
            'COINBASE_PASSPHRASE': 'test_passphrase',
            'COINBASE_SANDBOX': 'True'
        })
        yield
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
    
    @pytest.fixture
    def config(self, setup_environment):
        """Create test configuration."""
        config = Config()
        config.load_env_variables()
        return config
    
    @pytest.fixture
    def credentials(self, config):
        """Get Coinbase credentials from config."""
        return config.get_coinbase_credentials()
    
    @pytest.fixture
    def crypto_settings(self, config):
        """Get crypto trading settings from config."""
        return config.get_crypto_trading_settings()
    
    @pytest.fixture
    def mock_coinbase_client(self, credentials):
        """Create mock Coinbase client."""
        with patch('bot.coinbase_client.requests.Session'):
            client = CoinbaseClient(credentials)
            return client
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler."""
        return CoinbaseErrorHandler()
    
    @pytest.fixture
    def websocket_client(self, mock_coinbase_client, crypto_settings, error_handler):
        """Create WebSocket client."""
        websocket = CoinbaseWebSocket(mock_coinbase_client, crypto_settings, error_handler)
        return websocket
    
    def test_websocket_error_recovery(self, websocket_client, error_handler):
        """Test WebSocket error recovery with error handler."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Track error handling
        with patch.object(error_handler, 'handle_websocket_error') as mock_handle_error:
            # Simulate error
            websocket_client._on_error(mock_ws, Exception("Test error"))
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
    
    def test_websocket_authentication_error_handling(self, websocket_client, error_handler):
        """Test WebSocket authentication error handling."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        
        # Process authentication error message
        error_message = json.dumps({
            'type': 'error',
            'message': 'Authentication failed',
            'reason': 'Invalid signature'
        })
        
        # Track error handling
        with patch.object(error_handler, 'handle_websocket_error') as mock_handle_error:
            websocket_client._process_message(error_message)
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
    
    def test_websocket_rate_limit_handling(self, websocket_client, error_handler):
        """Test WebSocket rate limit error handling."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        
        # Process rate limit error message
        error_message = json.dumps({
            'type': 'error',
            'message': 'Rate limit exceeded',
            'reason': 'Too many messages'
        })
        
        # Track error handling
        with patch.object(error_handler, 'handle_rate_limit_error') as mock_handle_rate_limit:
            websocket_client._process_message(error_message)
            
            # Verify error was handled
            mock_handle_rate_limit.assert_called_once()
    
    def test_websocket_subscription_error_handling(self, websocket_client, error_handler):
        """Test WebSocket subscription error handling."""
        # Mock WebSocket connection
        mock_ws = Mock()
        
        # Set up WebSocket with mock
        websocket_client._ws = mock_ws
        websocket_client._connected = True
        
        # Process subscription error message
        error_message = json.dumps({
            'type': 'error',
            'message': 'Subscription failed',
            'reason': 'Invalid product'
        })
        
        # Track error handling
        with patch.object(error_handler, 'handle_websocket_error') as mock_handle_error:
            websocket_client._process_message(error_message)
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
    
    def test_websocket_fallback_to_rest_api(self, websocket_client, mock_coinbase_client):
        """Test fallback to REST API when WebSocket fails."""
        # Configure WebSocket to be disconnected
        websocket_client._connected = False
        
        # Mock REST API call
        mock_coinbase_client.get_product_ticker = Mock(return_value={'price': '45100.0'})
        
        # Get price (should fall back to REST API)
        price = websocket_client.get_latest_price('BTC-USD')
        
        # Verify REST API was used
        assert price == 45100.0
        mock_coinbase_client.get_product_ticker.assert_called_once_with('BTC-USD')


if __name__ == '__main__':
    pytest.main([__file__])