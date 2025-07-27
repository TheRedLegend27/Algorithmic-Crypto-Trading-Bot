"""
Integration tests for Kraken WebSocket client.
Tests real WebSocket connectivity and message handling.
"""
import asyncio
import json
import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from bot.kraken_websocket import (
    KrakenWebSocketClient,
    WebSocketCallbackHandler,
    WebSocketConfig,
    WebSocketState,
    SubscriptionType
)
from bot.kraken_client import KrakenCredentials


class TestCallbackHandler(WebSocketCallbackHandler):
    """Test callback handler that captures events."""
    
    def __init__(self):
        self.ticker_events = []
        self.ohlc_events = []
        self.trade_events = []
        self.book_events = []
        self.spread_events = []
        self.order_events = []
        self.connection_events = []
        self.error_events = []
        self.subscription_events = []
    
    def on_ticker(self, pair: str, data: dict) -> None:
        self.ticker_events.append({"pair": pair, "data": data, "timestamp": datetime.now()})
    
    def on_ohlc(self, pair: str, data: dict) -> None:
        self.ohlc_events.append({"pair": pair, "data": data, "timestamp": datetime.now()})
    
    def on_trade(self, pair: str, data: dict) -> None:
        self.trade_events.append({"pair": pair, "data": data, "timestamp": datetime.now()})
    
    def on_book(self, pair: str, data: dict) -> None:
        self.book_events.append({"pair": pair, "data": data, "timestamp": datetime.now()})
    
    def on_spread(self, pair: str, data: dict) -> None:
        self.spread_events.append({"pair": pair, "data": data, "timestamp": datetime.now()})
    
    def on_orders(self, data: dict) -> None:
        self.order_events.append({"data": data, "timestamp": datetime.now()})
    
    def on_connection_status(self, status: WebSocketState) -> None:
        self.connection_events.append({"status": status, "timestamp": datetime.now()})
    
    def on_error(self, error: Exception) -> None:
        self.error_events.append({"error": error, "timestamp": datetime.now()})
    
    def on_subscription_status(self, subscription_id: str, status: str, error: str = None) -> None:
        self.subscription_events.append({
            "subscription_id": subscription_id,
            "status": status,
            "error": error,
            "timestamp": datetime.now()
        })
    
    def clear_events(self):
        """Clear all captured events."""
        self.ticker_events.clear()
        self.ohlc_events.clear()
        self.trade_events.clear()
        self.book_events.clear()
        self.spread_events.clear()
        self.order_events.clear()
        self.connection_events.clear()
        self.error_events.clear()
        self.subscription_events.clear()


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.sent_messages = []
        self.received_messages = []
        self.closed = False
        self.connection_error = False
    
    async def send(self, message: str):
        """Mock send method."""
        if self.connection_error:
            raise Exception("Connection error")
        self.sent_messages.append(json.loads(message))
    
    async def recv(self):
        """Mock receive method."""
        if self.connection_error:
            raise Exception("Connection error")
        
        if self.received_messages:
            return self.received_messages.pop(0)
        
        # Simulate timeout
        await asyncio.sleep(1.1)
        raise asyncio.TimeoutError()
    
    async def close(self):
        """Mock close method."""
        self.closed = True
    
    def add_message(self, message):
        """Add message to be received."""
        if isinstance(message, dict):
            message = json.dumps(message)
        self.received_messages.append(message)
    
    def simulate_connection_error(self):
        """Simulate connection error."""
        self.connection_error = True
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


@pytest.fixture
def credentials():
    """Create test credentials."""
    return KrakenCredentials(
        api_key="test_key",
        api_secret="dGVzdF9zZWNyZXQ="  # base64 encoded "test_secret"
    )


@pytest.fixture
def callback_handler():
    """Create test callback handler."""
    return TestCallbackHandler()


@pytest.fixture
def config():
    """Create test configuration."""
    return WebSocketConfig(
        ping_interval=5,
        ping_timeout=3,
        max_reconnect_attempts=3,
        reconnect_delay=1,
        max_reconnect_delay=10,
        message_queue_size=100,
        heartbeat_interval=10
    )


@pytest.fixture
def ws_client(credentials, callback_handler, config):
    """Create WebSocket client."""
    return KrakenWebSocketClient(credentials, callback_handler, config)


class TestWebSocketConnection:
    """Test WebSocket connection functionality."""
    
    @patch('websockets.connect')
    def test_successful_connection(self, mock_connect, ws_client, callback_handler):
        """Test successful WebSocket connection."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Connect
        result = ws_client.connect()
        
        # Wait for connection to establish
        time.sleep(3)
        
        # Verify connection
        assert result is True
        assert ws_client.is_connected() is True
        
        # Check connection events
        connection_events = [e for e in callback_handler.connection_events 
                           if e["status"] == WebSocketState.CONNECTED]
        assert len(connection_events) > 0
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_connection_failure(self, mock_connect, ws_client, callback_handler):
        """Test WebSocket connection failure."""
        # Simulate connection failure
        mock_connect.side_effect = Exception("Connection failed")
        
        # Attempt to connect
        result = ws_client.connect()
        
        # Wait a bit
        time.sleep(2)
        
        # Verify connection failed
        assert result is False
        assert ws_client.is_connected() is False
        
        # Check error events
        assert len(callback_handler.error_events) > 0
    
    @patch('websockets.connect')
    def test_reconnection_logic(self, mock_connect, ws_client, callback_handler):
        """Test automatic reconnection."""
        # Setup mock WebSocket that fails after connection
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Connect successfully first
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        result = ws_client.connect()
        time.sleep(2)
        assert result is True
        
        # Simulate connection loss
        mock_ws.simulate_connection_error()
        
        # Wait for reconnection attempts
        time.sleep(5)
        
        # Check that reconnection was attempted
        reconnecting_events = [e for e in callback_handler.connection_events 
                             if e["status"] == WebSocketState.RECONNECTING]
        assert len(reconnecting_events) > 0
        
        # Cleanup
        ws_client.disconnect()


class TestSubscriptionManagement:
    """Test subscription management."""
    
    @patch('websockets.connect')
    def test_ticker_subscription(self, mock_connect, ws_client, callback_handler):
        """Test ticker subscription."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status and subscription status messages
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        mock_ws.add_message({
            "event": "subscriptionStatus",
            "status": "subscribed",
            "channelName": "ticker",
            "pair": "XBT/USD",
            "subscription": {"name": "ticker"}
        })
        
        # Connect and subscribe
        ws_client.connect()
        time.sleep(1)
        
        sub_id = ws_client.subscribe_ticker(["XBT/USD"])
        time.sleep(1)
        
        # Verify subscription was sent
        sent_messages = mock_ws.sent_messages
        subscription_messages = [msg for msg in sent_messages if msg.get("event") == "subscribe"]
        assert len(subscription_messages) > 0
        
        sub_msg = subscription_messages[-1]
        assert sub_msg["pair"] == ["XBT/USD"]
        assert sub_msg["subscription"]["name"] == "ticker"
        
        # Check subscription status events
        sub_events = [e for e in callback_handler.subscription_events 
                     if e["status"] == "subscribed"]
        assert len(sub_events) > 0
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_multiple_subscriptions(self, mock_connect, ws_client, callback_handler):
        """Test multiple subscriptions."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Connect
        ws_client.connect()
        time.sleep(1)
        
        # Subscribe to multiple channels
        ticker_sub = ws_client.subscribe_ticker(["XBT/USD", "ETH/USD"])
        trades_sub = ws_client.subscribe_trades(["XBT/USD"])
        book_sub = ws_client.subscribe_orderbook(["XBT/USD"], depth=25)
        
        time.sleep(1)
        
        # Verify all subscriptions are tracked
        subscriptions = ws_client.get_subscriptions()
        assert len(subscriptions) == 3
        assert ticker_sub in subscriptions
        assert trades_sub in subscriptions
        assert book_sub in subscriptions
        
        # Verify subscription messages were sent
        sent_messages = mock_ws.sent_messages
        subscription_messages = [msg for msg in sent_messages if msg.get("event") == "subscribe"]
        assert len(subscription_messages) >= 3
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_unsubscription(self, mock_connect, ws_client, callback_handler):
        """Test unsubscription."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Connect and subscribe
        ws_client.connect()
        time.sleep(1)
        
        sub_id = ws_client.subscribe_ticker(["XBT/USD"])
        time.sleep(1)
        
        # Unsubscribe
        result = ws_client.unsubscribe(sub_id)
        time.sleep(1)
        
        assert result is True
        assert sub_id not in ws_client.get_subscriptions()
        
        # Verify unsubscribe message was sent
        sent_messages = mock_ws.sent_messages
        unsubscribe_messages = [msg for msg in sent_messages if msg.get("event") == "unsubscribe"]
        assert len(unsubscribe_messages) > 0
        
        # Cleanup
        ws_client.disconnect()


class TestMessageHandling:
    """Test message handling and processing."""
    
    @patch('websockets.connect')
    def test_ticker_message_processing(self, mock_connect, ws_client, callback_handler):
        """Test ticker message processing."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Add ticker data message
        ticker_data = [
            123,  # Channel ID
            {
                "a": ["50100.0", "2", "2.000"],
                "b": ["50000.0", "1", "1.000"],
                "c": ["50050.0", "0.5"],
                "v": ["100.0", "200.0"],
                "p": ["50025.0", "50030.0"],
                "t": [50, 100],
                "l": ["49000.0", "48000.0"],
                "h": ["51000.0", "52000.0"],
                "o": ["49500.0", "49000.0"]
            },
            "ticker",
            "XBT/USD"
        ]
        mock_ws.add_message(ticker_data)
        
        # Connect and subscribe
        ws_client.connect()
        time.sleep(1)
        
        ws_client.subscribe_ticker(["XBT/USD"])
        time.sleep(2)  # Wait for message processing
        
        # Check ticker events
        assert len(callback_handler.ticker_events) > 0
        
        ticker_event = callback_handler.ticker_events[0]
        assert ticker_event["pair"] == "XBT/USD"
        assert "a" in ticker_event["data"]
        assert "b" in ticker_event["data"]
        assert "c" in ticker_event["data"]
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_trade_message_processing(self, mock_connect, ws_client, callback_handler):
        """Test trade message processing."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Add trade data message
        trade_data = [
            124,  # Channel ID
            [
                ["50000.0", "1.0", "1234567890.0", "b", "m", ""],
                ["50100.0", "0.5", "1234567891.0", "s", "l", ""]
            ],
            "trade",
            "XBT/USD"
        ]
        mock_ws.add_message(trade_data)
        
        # Connect and subscribe
        ws_client.connect()
        time.sleep(1)
        
        ws_client.subscribe_trades(["XBT/USD"])
        time.sleep(2)  # Wait for message processing
        
        # Check trade events
        assert len(callback_handler.trade_events) > 0
        
        trade_event = callback_handler.trade_events[0]
        assert trade_event["pair"] == "XBT/USD"
        assert isinstance(trade_event["data"], list)
        assert len(trade_event["data"]) == 2
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_order_book_message_processing(self, mock_connect, ws_client, callback_handler):
        """Test order book message processing."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Add order book data message
        book_data = [
            125,  # Channel ID
            {
                "as": [["50100.0", "2.0", "1234567890.0"], ["50200.0", "1.0", "1234567891.0"]],
                "bs": [["50000.0", "1.5", "1234567890.0"], ["49900.0", "3.0", "1234567891.0"]]
            },
            "book-25",
            "XBT/USD"
        ]
        mock_ws.add_message(book_data)
        
        # Connect and subscribe
        ws_client.connect()
        time.sleep(1)
        
        ws_client.subscribe_orderbook(["XBT/USD"], depth=25)
        time.sleep(2)  # Wait for message processing
        
        # Check book events
        assert len(callback_handler.book_events) > 0
        
        book_event = callback_handler.book_events[0]
        assert book_event["pair"] == "XBT/USD"
        assert "as" in book_event["data"]  # asks
        assert "bs" in book_event["data"]  # bids
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_error_message_handling(self, mock_connect, ws_client, callback_handler):
        """Test error message handling."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Add error message
        error_message = {
            "errorMessage": "Currency pair not supported INVALID/PAIR"
        }
        mock_ws.add_message(error_message)
        
        # Connect
        ws_client.connect()
        time.sleep(2)  # Wait for message processing
        
        # Check error events
        assert len(callback_handler.error_events) > 0
        
        error_event = callback_handler.error_events[0]
        assert "Currency pair not supported" in str(error_event["error"])
        
        # Cleanup
        ws_client.disconnect()


class TestConnectionMonitoring:
    """Test connection monitoring and health checks."""
    
    @patch('websockets.connect')
    def test_ping_pong_mechanism(self, mock_connect, ws_client, callback_handler):
        """Test ping/pong mechanism."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Connect
        ws_client.connect()
        time.sleep(1)
        
        # Wait for ping to be sent
        time.sleep(6)  # Ping interval is 5 seconds in test config
        
        # Check that ping was sent
        sent_messages = mock_ws.sent_messages
        ping_messages = [msg for msg in sent_messages if msg.get("event") == "ping"]
        assert len(ping_messages) > 0
        
        # Simulate pong response
        mock_ws.add_message({"event": "heartbeat"})
        time.sleep(1)
        
        # Check that pong was processed
        assert ws_client.last_pong is not None
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_connection_health_monitoring(self, mock_connect, ws_client, callback_handler):
        """Test connection health monitoring."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Connect
        ws_client.connect()
        time.sleep(1)
        
        # Get initial stats
        stats = ws_client.get_stats()
        assert stats["state"] == "connected"
        assert stats["public_connected"] is True
        assert stats["reconnect_attempts"] == 0
        
        # Cleanup
        ws_client.disconnect()


class TestPrivateChannels:
    """Test private channel functionality."""
    
    @patch('websockets.connect')
    def test_private_orders_subscription(self, mock_connect, ws_client, callback_handler):
        """Test private orders subscription."""
        # Setup mock WebSockets (both public and private)
        mock_public_ws = MockWebSocket()
        mock_private_ws = MockWebSocket()
        
        async def connect_side_effect(url, **kwargs):
            if "ws-auth" in url:
                return mock_private_ws
            else:
                return mock_public_ws
        
        mock_connect.side_effect = connect_side_effect
        
        # Add system status messages
        mock_public_ws.add_message({"event": "systemStatus", "status": "online"})
        mock_private_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Connect
        ws_client.connect()
        time.sleep(1)
        
        # Subscribe to orders
        sub_id = ws_client.subscribe_orders()
        time.sleep(1)
        
        # Verify private connection was established
        stats = ws_client.get_stats()
        assert stats["private_connected"] is True
        
        # Verify auth message was sent to private WebSocket
        auth_messages = [msg for msg in mock_private_ws.sent_messages 
                        if msg.get("subscription", {}).get("name") == "openOrders"]
        assert len(auth_messages) > 0
        
        auth_msg = auth_messages[0]
        assert "token" in auth_msg["subscription"]
        
        # Cleanup
        ws_client.disconnect()


class TestPerformanceAndStress:
    """Test performance and stress scenarios."""
    
    @patch('websockets.connect')
    def test_high_message_volume(self, mock_connect, ws_client, callback_handler):
        """Test handling of high message volume."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Add many ticker messages
        for i in range(100):
            ticker_data = [
                123 + i,
                {"c": [f"{50000 + i}.0", "1"]},
                "ticker",
                "XBT/USD"
            ]
            mock_ws.add_message(ticker_data)
        
        # Connect and subscribe
        ws_client.connect()
        time.sleep(1)
        
        ws_client.subscribe_ticker(["XBT/USD"])
        time.sleep(3)  # Wait for all messages to be processed
        
        # Check that messages were processed
        assert len(callback_handler.ticker_events) > 0
        
        # Check queue didn't overflow
        assert ws_client.get_queue_size() < ws_client.config.message_queue_size
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_queue_overflow_handling(self, mock_connect, ws_client, callback_handler):
        """Test queue overflow handling."""
        # Create client with small queue
        small_config = WebSocketConfig(message_queue_size=5)
        small_ws_client = KrakenWebSocketClient(
            ws_client.credentials,
            callback_handler,
            small_config
        )
        
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Add more messages than queue can handle
        for i in range(20):
            ticker_data = [
                123 + i,
                {"c": [f"{50000 + i}.0", "1"]},
                "ticker",
                "XBT/USD"
            ]
            mock_ws.add_message(ticker_data)
        
        # Connect and subscribe
        small_ws_client.connect()
        time.sleep(1)
        
        small_ws_client.subscribe_ticker(["XBT/USD"])
        time.sleep(2)  # Wait for processing
        
        # Verify client handled overflow gracefully
        assert small_ws_client.get_queue_size() <= small_config.message_queue_size
        
        # Cleanup
        small_ws_client.disconnect()


class TestErrorRecovery:
    """Test error recovery scenarios."""
    
    @patch('websockets.connect')
    def test_websocket_disconnect_recovery(self, mock_connect, ws_client, callback_handler):
        """Test recovery from WebSocket disconnect."""
        # Setup mock WebSocket that will disconnect
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Connect
        ws_client.connect()
        time.sleep(1)
        
        # Subscribe to something
        sub_id = ws_client.subscribe_ticker(["XBT/USD"])
        time.sleep(1)
        
        # Simulate connection loss
        mock_ws.simulate_connection_error()
        
        # Wait for reconnection attempts
        time.sleep(3)
        
        # Check that reconnection was attempted
        reconnecting_events = [e for e in callback_handler.connection_events 
                             if e["status"] == WebSocketState.RECONNECTING]
        assert len(reconnecting_events) > 0
        
        # Cleanup
        ws_client.disconnect()
    
    @patch('websockets.connect')
    def test_malformed_message_handling(self, mock_connect, ws_client, callback_handler):
        """Test handling of malformed messages."""
        # Setup mock WebSocket
        mock_ws = MockWebSocket()
        
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        # Add system status message
        mock_ws.add_message({"event": "systemStatus", "status": "online"})
        
        # Add malformed messages
        mock_ws.add_message("invalid json")
        mock_ws.add_message('{"incomplete": ')
        mock_ws.add_message([])  # Empty array
        mock_ws.add_message([123])  # Insufficient data
        
        # Connect
        ws_client.connect()
        time.sleep(2)  # Wait for message processing
        
        # Client should handle malformed messages gracefully
        assert ws_client.is_connected() is True
        
        # Cleanup
        ws_client.disconnect()