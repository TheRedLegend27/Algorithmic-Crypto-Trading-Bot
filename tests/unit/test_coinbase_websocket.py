"""
Unit tests for Coinbase WebSocket client and manager.
Tests individual components and methods in isolation.
"""
import json
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from queue import Queue

from bot.coinbase_client import CoinbaseCredentials
from bot.coinbase_websocket import (
    CoinbaseWebSocketClient, 
    CoinbaseWebSocketManager, 
    WebSocketMessage
)


class TestWebSocketMessage(unittest.TestCase):
    """Test WebSocketMessage dataclass."""
    
    def test_websocket_message_creation(self):
        """Test WebSocketMessage creation and attributes."""
        timestamp = datetime.now(timezone.utc)
        data = {"price": "50000.00", "volume": "1.5"}
        
        message = WebSocketMessage(
            type="ticker",
            product_id="BTC-USD",
            timestamp=timestamp,
            data=data
        )
        
        self.assertEqual(message.type, "ticker")
        self.assertEqual(message.product_id, "BTC-USD")
        self.assertEqual(message.timestamp, timestamp)
        self.assertEqual(message.data, data)


class TestCoinbaseWebSocketClient(unittest.TestCase):
    """Test CoinbaseWebSocketClient functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
        self.client = CoinbaseWebSocketClient(self.credentials)
    
    def test_client_initialization(self):
        """Test WebSocket client initialization."""
        self.assertEqual(self.client.credentials, self.credentials)
        self.assertEqual(self.client.ws_url, "wss://ws-feed-public.sandbox.exchange.coinbase.com")
        self.assertFalse(self.client.connected)
        self.assertEqual(self.client.reconnect_attempts, 0)
        self.assertIsInstance(self.client.message_queue, Queue)
    
    def test_production_url_selection(self):
        """Test production WebSocket URL selection."""
        prod_credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=False
        )
        
        client = CoinbaseWebSocketClient(prod_credentials)
        self.assertEqual(client.ws_url, "wss://ws-feed.exchange.coinbase.com")
    
    def test_subscribe_ticker(self):
        """Test ticker subscription."""
        with patch.object(self.client, '_subscribe', return_value=True) as mock_subscribe:
            callback = Mock()
            result = self.client.subscribe_ticker(["BTC-USD"], callback)
            
            self.assertTrue(result)
            mock_subscribe.assert_called_once_with("ticker", ["BTC-USD"], callback)
    
    def test_subscribe_level2(self):
        """Test level2 (order book) subscription."""
        with patch.object(self.client, '_subscribe', return_value=True) as mock_subscribe:
            callback = Mock()
            result = self.client.subscribe_level2(["BTC-USD"], callback)
            
            self.assertTrue(result)
            mock_subscribe.assert_called_once_with("level2", ["BTC-USD"], callback)
    
    def test_subscribe_matches(self):
        """Test matches (trades) subscription."""
        with patch.object(self.client, '_subscribe', return_value=True) as mock_subscribe:
            callback = Mock()
            result = self.client.subscribe_matches(["BTC-USD"], callback)
            
            self.assertTrue(result)
            mock_subscribe.assert_called_once_with("matches", ["BTC-USD"], callback)
    
    def test_subscribe_when_not_connected(self):
        """Test subscription when WebSocket is not connected."""
        self.client.connected = False
        
        result = self.client.subscribe_ticker(["BTC-USD"])
        self.assertFalse(result)
    
    def test_subscribe_success(self):
        """Test successful subscription."""
        mock_ws = Mock()
        self.client.ws = mock_ws
        self.client.connected = True
        
        result = self.client._subscribe("ticker", ["BTC-USD"], None)
        
        self.assertTrue(result)
        mock_ws.send.assert_called_once()
        
        # Verify subscription message format
        call_args = mock_ws.send.call_args[0][0]
        message = json.loads(call_args)
        
        expected_message = {
            "type": "subscribe",
            "channels": [
                {
                    "name": "ticker",
                    "product_ids": ["BTC-USD"]
                }
            ]
        }
        
        self.assertEqual(message, expected_message)
        self.assertIn("ticker:BTC-USD", self.client.subscriptions)
    
    def test_unsubscribe(self):
        """Test unsubscription from channel."""
        mock_ws = Mock()
        self.client.ws = mock_ws
        self.client.connected = True
        self.client.subscriptions["ticker:BTC-USD"] = {
            "channel": "ticker",
            "product_ids": ["BTC-USD"],
            "callback": None
        }
        
        result = self.client.unsubscribe("ticker", ["BTC-USD"])
        
        self.assertTrue(result)
        mock_ws.send.assert_called_once()
        self.assertNotIn("ticker:BTC-USD", self.client.subscriptions)
    
    def test_on_open(self):
        """Test WebSocket connection open handler."""
        mock_ws = Mock()
        
        self.client._on_open(mock_ws)
        
        self.assertTrue(self.client.connected)
        self.assertEqual(self.client.reconnect_attempts, 0)
    
    def test_on_message_ticker(self):
        """Test ticker message handling."""
        ticker_data = {
            "type": "ticker",
            "product_id": "BTC-USD",
            "price": "50000.00",
            "time": "2023-01-01T00:00:00.000000Z"
        }
        
        self.client._on_message(None, json.dumps(ticker_data))
        
        # Check message was added to queue
        self.assertFalse(self.client.message_queue.empty())
        
        message = self.client.message_queue.get()
        self.assertEqual(message.type, "ticker")
        self.assertEqual(message.product_id, "BTC-USD")
        self.assertEqual(message.data["price"], "50000.00")
    
    def test_on_message_subscription_confirmation(self):
        """Test subscription confirmation message handling."""
        sub_data = {
            "type": "subscriptions",
            "channels": [
                {
                    "name": "ticker",
                    "product_ids": ["BTC-USD"]
                }
            ]
        }
        
        # Should not add subscription messages to queue
        self.client._on_message(None, json.dumps(sub_data))
        self.assertTrue(self.client.message_queue.empty())
    
    def test_on_message_error(self):
        """Test error message handling."""
        error_data = {
            "type": "error",
            "message": "Invalid channel"
        }
        
        # Should not add error messages to queue
        self.client._on_message(None, json.dumps(error_data))
        self.assertTrue(self.client.message_queue.empty())
    
    def test_on_message_invalid_json(self):
        """Test handling of invalid JSON messages."""
        invalid_json = "invalid json string"
        
        # Should handle gracefully without crashing
        self.client._on_message(None, invalid_json)
        self.assertTrue(self.client.message_queue.empty())
    
    def test_on_close(self):
        """Test WebSocket connection close handler."""
        mock_ws = Mock()
        
        with patch.object(self.client, '_attempt_reconnect') as mock_reconnect:
            self.client._on_close(mock_ws, None, None)
            
            self.assertFalse(self.client.connected)
            mock_reconnect.assert_called_once()
    
    def test_on_error(self):
        """Test WebSocket error handler."""
        test_error = Exception("Connection error")
        
        with patch.object(self.client, '_attempt_reconnect') as mock_reconnect:
            self.client._on_error(None, test_error)
            mock_reconnect.assert_called_once()
    
    def test_get_latest_ticker(self):
        """Test getting latest ticker from message queue."""
        # Add ticker message to queue
        ticker_message = WebSocketMessage(
            type="ticker",
            product_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            data={"price": "50000.00", "volume": "1.5"}
        )
        self.client.message_queue.put(ticker_message)
        
        # Add non-ticker message
        other_message = WebSocketMessage(
            type="level2",
            product_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            data={"bids": [], "asks": []}
        )
        self.client.message_queue.put(other_message)
        
        # Get latest ticker
        ticker = self.client.get_latest_ticker("BTC-USD")
        
        self.assertIsNotNone(ticker)
        self.assertEqual(ticker["price"], "50000.00")
        
        # Verify messages are back in queue
        self.assertEqual(self.client.message_queue.qsize(), 2)
    
    def test_is_connected_healthy(self):
        """Test connection health check."""
        self.client.connected = True
        self.client.last_message_time = time.time()
        
        self.assertTrue(self.client.is_connected())
    
    def test_is_connected_stale(self):
        """Test connection health check with stale messages."""
        self.client.connected = True
        self.client.last_message_time = time.time() - 120  # 2 minutes ago
        self.client.connection_timeout = 60  # 1 minute timeout
        
        self.assertFalse(self.client.is_connected())
    
    def test_get_connection_stats(self):
        """Test connection statistics retrieval."""
        self.client.connected = True
        self.client.messages_received = 100
        self.client.reconnect_attempts = 2
        self.client.subscriptions["ticker:BTC-USD"] = {}
        
        stats = self.client.get_connection_stats()
        
        expected_stats = {
            "connected": True,
            "messages_received": 100,
            "last_message_time": self.client.last_message_time,
            "reconnect_attempts": 2,
            "subscriptions": ["ticker:BTC-USD"],
            "queue_size": 0
        }
        
        self.assertEqual(stats, expected_stats)
    
    def test_handle_message_with_callback(self):
        """Test message handling with registered callback."""
        callback = Mock()
        self.client.subscriptions["ticker:BTC-USD"] = {
            "channel": "ticker",
            "product_ids": ["BTC-USD"],
            "callback": callback
        }
        
        message = WebSocketMessage(
            type="ticker",
            product_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            data={"price": "50000.00"}
        )
        
        self.client._handle_message(message)
        callback.assert_called_once_with(message)


class TestCoinbaseWebSocketManager(unittest.TestCase):
    """Test CoinbaseWebSocketManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
        self.mock_rest_client = Mock()
        self.manager = CoinbaseWebSocketManager(self.credentials, self.mock_rest_client)
    
    def test_manager_initialization(self):
        """Test WebSocket manager initialization."""
        self.assertEqual(self.manager.credentials, self.credentials)
        self.assertEqual(self.manager.rest_client, self.mock_rest_client)
        self.assertIsNone(self.manager.ws_client)
        self.assertEqual(self.manager.price_cache, {})
        self.assertTrue(self.manager.use_fallback)
        self.assertFalse(self.manager.fallback_active)
    
    @patch('bot.coinbase_websocket.CoinbaseWebSocketClient')
    def test_start_success(self, mock_ws_client_class):
        """Test successful WebSocket manager start."""
        mock_ws_client = Mock()
        mock_ws_client_class.return_value = mock_ws_client
        mock_ws_client.connect.return_value = True
        mock_ws_client.subscribe_ticker.return_value = True
        
        result = self.manager.start(["BTC-USD"])
        
        self.assertTrue(result)
        self.assertFalse(self.manager.fallback_active)
        mock_ws_client.connect.assert_called_once()
        mock_ws_client.subscribe_ticker.assert_called_once()
    
    @patch('bot.coinbase_websocket.CoinbaseWebSocketClient')
    def test_start_connection_failure(self, mock_ws_client_class):
        """Test WebSocket manager start with connection failure."""
        mock_ws_client = Mock()
        mock_ws_client_class.return_value = mock_ws_client
        mock_ws_client.connect.return_value = False
        
        with patch.object(self.manager, '_activate_fallback', return_value=True) as mock_fallback:
            result = self.manager.start(["BTC-USD"])
            
            self.assertTrue(result)
            mock_fallback.assert_called_once()
    
    def test_stop(self):
        """Test WebSocket manager stop."""
        mock_ws_client = Mock()
        self.manager.ws_client = mock_ws_client
        
        self.manager.stop()
        
        mock_ws_client.disconnect.assert_called_once()
        self.assertIsNone(self.manager.ws_client)
    
    def test_get_real_time_price_websocket(self):
        """Test getting real-time price from WebSocket."""
        mock_ws_client = Mock()
        mock_ws_client.is_connected.return_value = True
        mock_ws_client.get_latest_ticker.return_value = {"price": "50000.00"}
        
        self.manager.ws_client = mock_ws_client
        self.manager.fallback_active = False
        
        price = self.manager.get_real_time_price("BTC-USD")
        
        self.assertEqual(price, 50000.0)
        mock_ws_client.get_latest_ticker.assert_called_once_with("BTC-USD")
    
    def test_get_real_time_price_cache(self):
        """Test getting price from cache."""
        self.manager.price_cache["BTC-USD"] = 45000.0
        self.manager.cache_timestamps["BTC-USD"] = time.time()
        
        # Mock WebSocket as unavailable
        mock_ws_client = Mock()
        mock_ws_client.is_connected.return_value = False
        self.manager.ws_client = mock_ws_client
        
        price = self.manager.get_real_time_price("BTC-USD")
        
        self.assertEqual(price, 45000.0)
    
    def test_get_real_time_price_fallback(self):
        """Test getting price from REST API fallback."""
        # Mock WebSocket as unavailable
        mock_ws_client = Mock()
        mock_ws_client.is_connected.return_value = False
        mock_ws_client.get_latest_ticker.return_value = None
        self.manager.ws_client = mock_ws_client
        
        # Mock REST client
        self.mock_rest_client.get_latest_price.return_value = 48000.0
        
        price = self.manager.get_real_time_price("BTC-USD")
        
        self.assertEqual(price, 48000.0)
        self.mock_rest_client.get_latest_price.assert_called_once_with("BTC-USD")
    
    def test_is_websocket_healthy(self):
        """Test WebSocket health check."""
        mock_ws_client = Mock()
        mock_ws_client.is_connected.return_value = True
        self.manager.ws_client = mock_ws_client
        
        self.assertTrue(self.manager.is_websocket_healthy())
        
        # Test with no WebSocket client
        self.manager.ws_client = None
        self.assertFalse(self.manager.is_websocket_healthy())
    
    def test_get_connection_status(self):
        """Test connection status retrieval."""
        mock_ws_client = Mock()
        mock_ws_client.is_connected.return_value = True
        mock_ws_client.get_connection_stats.return_value = {
            "messages_received": 100,
            "reconnect_attempts": 0
        }
        
        self.manager.ws_client = mock_ws_client
        self.manager.fallback_active = False
        self.manager.price_cache = {"BTC-USD": 50000.0}
        
        status = self.manager.get_connection_status()
        
        expected_status = {
            "websocket_connected": True,
            "fallback_active": False,
            "cache_size": 1,
            "websocket_stats": {
                "messages_received": 100,
                "reconnect_attempts": 0
            }
        }
        
        self.assertEqual(status, expected_status)
    
    def test_on_ticker_update(self):
        """Test ticker update callback."""
        message = WebSocketMessage(
            type="ticker",
            product_id="BTC-USD",
            timestamp=datetime.now(timezone.utc),
            data={"product_id": "BTC-USD", "price": "50000.00"}
        )
        
        self.manager._on_ticker_update(message)
        
        # Check price was cached
        self.assertEqual(self.manager.price_cache["BTC-USD"], 50000.0)
        self.assertIn("BTC-USD", self.manager.cache_timestamps)
    
    def test_update_price_cache(self):
        """Test price cache update."""
        self.manager._update_price_cache("BTC-USD", 50000.0)
        
        self.assertEqual(self.manager.price_cache["BTC-USD"], 50000.0)
        self.assertIn("BTC-USD", self.manager.cache_timestamps)
    
    def test_get_cached_price_valid(self):
        """Test getting valid cached price."""
        self.manager.price_cache["BTC-USD"] = 50000.0
        self.manager.cache_timestamps["BTC-USD"] = time.time()
        
        price = self.manager._get_cached_price("BTC-USD")
        self.assertEqual(price, 50000.0)
    
    def test_get_cached_price_expired(self):
        """Test getting expired cached price."""
        self.manager.price_cache["BTC-USD"] = 50000.0
        self.manager.cache_timestamps["BTC-USD"] = time.time() - 120  # 2 minutes ago
        self.manager.cache_ttl = 60  # 1 minute TTL
        
        price = self.manager._get_cached_price("BTC-USD")
        self.assertIsNone(price)
        self.assertNotIn("BTC-USD", self.manager.price_cache)
    
    def test_get_cached_price_not_found(self):
        """Test getting price for non-cached product."""
        price = self.manager._get_cached_price("ETH-USD")
        self.assertIsNone(price)
    
    def test_activate_fallback_available(self):
        """Test fallback activation when REST client is available."""
        result = self.manager._activate_fallback()
        
        self.assertTrue(result)
        self.assertTrue(self.manager.fallback_active)
    
    def test_activate_fallback_unavailable(self):
        """Test fallback activation when REST client is not available."""
        self.manager.rest_client = None
        
        result = self.manager._activate_fallback()
        
        self.assertFalse(result)
        self.assertFalse(self.manager.fallback_active)


if __name__ == '__main__':
    unittest.main()