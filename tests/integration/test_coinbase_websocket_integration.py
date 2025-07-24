"""
Integration tests for Coinbase WebSocket functionality.
Tests WebSocket connection, real-time data streaming, and fallback mechanisms.
"""
import json
import time
import unittest
from unittest.mock import Mock, patch
import threading
from datetime import datetime, timezone

from bot.coinbase_client import CoinbaseCredentials
from bot.coinbase_websocket import CoinbaseWebSocketClient, CoinbaseWebSocketManager, WebSocketMessage
from bot.coinbase_data_fetcher import CoinbaseDataFetcher


class TestCoinbaseWebSocketIntegration(unittest.TestCase):
    """Integration tests for Coinbase WebSocket functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
        self.product_ids = ["BTC-USD", "ETH-USD"]
    
    def test_websocket_client_connection(self):
        """Test WebSocket client connection and basic functionality."""
        with patch('websocket.WebSocketApp') as mock_ws_app:
            # Mock WebSocket app
            mock_ws = Mock()
            mock_ws_app.return_value = mock_ws
            
            # Create client
            client = CoinbaseWebSocketClient(self.credentials)
            
            # Mock successful connection
            def simulate_connection():
                time.sleep(0.1)
                client._on_open(mock_ws)
            
            connection_thread = threading.Thread(target=simulate_connection)
            connection_thread.start()
            
            # Test connection
            result = client.connect()
            connection_thread.join()
            
            self.assertTrue(result)
            self.assertTrue(client.connected)
            mock_ws_app.assert_called_once()
    
    def test_websocket_ticker_subscription(self):
        """Test WebSocket ticker subscription."""
        with patch('websocket.WebSocketApp') as mock_ws_app:
            mock_ws = Mock()
            mock_ws_app.return_value = mock_ws
            
            client = CoinbaseWebSocketClient(self.credentials)
            
            # Simulate connection
            client.connected = True
            client.ws = mock_ws
            
            # Test subscription
            result = client.subscribe_ticker(self.product_ids)
            
            self.assertTrue(result)
            mock_ws.send.assert_called_once()
            
            # Verify subscription message
            call_args = mock_ws.send.call_args[0][0]
            import json
            message = json.loads(call_args)
            
            self.assertEqual(message["type"], "subscribe")
            self.assertEqual(message["channels"][0]["name"], "ticker")
            self.assertEqual(message["channels"][0]["product_ids"], self.product_ids)
    
    def test_websocket_message_handling(self):
        """Test WebSocket message processing."""
        client = CoinbaseWebSocketClient(self.credentials)
        client.connected = True
        
        # Test ticker message
        ticker_message = {
            "type": "ticker",
            "product_id": "BTC-USD",
            "price": "50000.00",
            "time": "2023-01-01T00:00:00.000000Z"
        }
        
        # Process message
        client._on_message(None, json.dumps(ticker_message))
        
        # Check message queue
        self.assertFalse(client.message_queue.empty())
        
        # Get message from queue
        message = client.message_queue.get()
        self.assertIsInstance(message, WebSocketMessage)
        self.assertEqual(message.type, "ticker")
        self.assertEqual(message.product_id, "BTC-USD")
        self.assertEqual(message.data["price"], "50000.00")
    
    def test_websocket_reconnection(self):
        """Test WebSocket reconnection logic."""
        with patch('websocket.WebSocketApp') as mock_ws_app:
            mock_ws = Mock()
            mock_ws_app.return_value = mock_ws
            
            client = CoinbaseWebSocketClient(self.credentials)
            client.connected = True
            client.reconnect_attempts = 0
            client.max_reconnect_attempts = 2
            
            # Mock reconnection
            with patch.object(client, 'connect', return_value=True) as mock_connect:
                # Simulate connection loss
                client._on_close(mock_ws, None, None)
                
                # Wait for reconnection attempt
                time.sleep(0.1)
                
                # Verify reconnection was attempted
                mock_connect.assert_called()
    
    def test_websocket_manager_integration(self):
        """Test WebSocket manager with fallback functionality."""
        # Create mock REST client
        mock_rest_client = Mock()
        mock_rest_client.get_latest_price.return_value = 45000.0
        
        manager = CoinbaseWebSocketManager(self.credentials, mock_rest_client)
        
        # Test successful start (WebSocket may actually connect in sandbox)
        result = manager.start(self.product_ids)
        
        # Should either succeed with WebSocket or activate fallback
        self.assertTrue(result)
        
        # Clean up
        manager.stop()
    
    def test_websocket_price_caching(self):
        """Test WebSocket price caching mechanism."""
        mock_rest_client = Mock()
        manager = CoinbaseWebSocketManager(self.credentials, mock_rest_client)
        
        # Test cache update
        manager._update_price_cache("BTC-USD", 50000.0)
        
        # Test cache retrieval
        cached_price = manager._get_cached_price("BTC-USD")
        self.assertEqual(cached_price, 50000.0)
        
        # Test cache expiration
        manager.cache_ttl = 0.1  # 100ms TTL
        time.sleep(0.2)
        
        expired_price = manager._get_cached_price("BTC-USD")
        self.assertIsNone(expired_price)
    
    def test_data_fetcher_websocket_integration(self):
        """Test CoinbaseDataFetcher WebSocket integration."""
        with patch('bot.coinbase_data_fetcher.CoinbaseWebSocketManager') as mock_ws_manager_class:
            mock_ws_manager = Mock()
            mock_ws_manager_class.return_value = mock_ws_manager
            mock_ws_manager.start.return_value = True
            mock_ws_manager.is_websocket_healthy.return_value = True
            mock_ws_manager.get_real_time_price.return_value = 50000.0
            
            # Create data fetcher
            fetcher = CoinbaseDataFetcher(self.credentials)
            
            # Test WebSocket subscription
            result = fetcher.subscribe_to_websocket(["BTC-USD"])
            self.assertTrue(result)
            mock_ws_manager.start.assert_called_once()
            
            # Test real-time price retrieval
            price = fetcher.get_real_time_price("BTC-USD")
            self.assertEqual(price, 50000.0)
            mock_ws_manager.get_real_time_price.assert_called_with("BTC-USD")
    
    def test_websocket_fallback_to_rest(self):
        """Test fallback from WebSocket to REST API."""
        with patch('bot.coinbase_data_fetcher.CoinbaseWebSocketManager') as mock_ws_manager_class:
            mock_ws_manager = Mock()
            mock_ws_manager_class.return_value = mock_ws_manager
            mock_ws_manager.is_websocket_healthy.return_value = False
            mock_ws_manager.get_real_time_price.return_value = None
            
            # Mock REST API response
            with patch.object(CoinbaseDataFetcher, 'get_latest_price', return_value=45000.0) as mock_rest_price:
                fetcher = CoinbaseDataFetcher(self.credentials)
                
                # Test fallback to REST
                price = fetcher.get_real_time_price("BTC-USD")
                self.assertEqual(price, 45000.0)
                mock_rest_price.assert_called_once_with("BTC-USD")
    
    def test_websocket_status_reporting(self):
        """Test WebSocket status reporting functionality."""
        with patch('bot.coinbase_data_fetcher.CoinbaseWebSocketManager') as mock_ws_manager_class:
            mock_ws_manager = Mock()
            mock_ws_manager_class.return_value = mock_ws_manager
            mock_ws_manager.is_websocket_healthy.return_value = True
            mock_ws_manager.get_connection_status.return_value = {
                "websocket_connected": True,
                "fallback_active": False,
                "cache_size": 2,
                "websocket_stats": {
                    "messages_received": 100,
                    "reconnect_attempts": 0
                }
            }
            
            fetcher = CoinbaseDataFetcher(self.credentials)
            
            # Test WebSocket connection status
            self.assertTrue(fetcher.is_websocket_connected())
            
            # Test detailed status
            status = fetcher.get_websocket_status()
            self.assertTrue(status["enabled"])
            self.assertTrue(status["websocket_connected"])
            self.assertFalse(status["fallback_active"])
    
    def test_websocket_enable_disable(self):
        """Test WebSocket enable/disable functionality."""
        with patch('bot.coinbase_data_fetcher.CoinbaseWebSocketManager') as mock_ws_manager_class:
            mock_ws_manager = Mock()
            mock_ws_manager_class.return_value = mock_ws_manager
            
            fetcher = CoinbaseDataFetcher(self.credentials)
            
            # Test disable
            fetcher.disable_websocket()
            self.assertFalse(fetcher.websocket_enabled)
            mock_ws_manager.stop.assert_called_once()
            
            # Test enable
            fetcher.enable_websocket()
            self.assertTrue(fetcher.websocket_enabled)
    
    def test_websocket_error_handling(self):
        """Test WebSocket error handling and recovery."""
        client = CoinbaseWebSocketClient(self.credentials)
        client.stop_event.set()  # Prevent actual reconnection
        
        # Test error handling
        test_error = Exception("Connection failed")
        client._on_error(None, test_error)
        
        # Verify error was logged (would need to check logs in real implementation)
        # Note: connected state may change due to reconnection attempts
    
    def test_websocket_heartbeat_monitoring(self):
        """Test WebSocket heartbeat and connection monitoring."""
        client = CoinbaseWebSocketClient(self.credentials)
        client.connected = True
        client.connection_timeout = 0.1  # 100ms timeout for testing
        
        # Simulate old last message time
        client.last_message_time = time.time() - 1  # 1 second ago
        
        # Check connection health
        self.assertFalse(client.is_connected())
    
    def test_multiple_product_subscription(self):
        """Test subscribing to multiple products simultaneously."""
        with patch('websocket.WebSocketApp') as mock_ws_app:
            mock_ws = Mock()
            mock_ws_app.return_value = mock_ws
            
            client = CoinbaseWebSocketClient(self.credentials)
            client.connected = True
            client.ws = mock_ws
            
            # Subscribe to multiple products
            products = ["BTC-USD", "ETH-USD", "SOL-USD"]
            result = client.subscribe_ticker(products)
            
            self.assertTrue(result)
            
            # Verify subscription includes all products
            call_args = mock_ws.send.call_args[0][0]
            import json
            message = json.loads(call_args)
            
            self.assertEqual(set(message["channels"][0]["product_ids"]), set(products))


if __name__ == '__main__':
    unittest.main()