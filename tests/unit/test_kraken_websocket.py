"""
Unit tests for Kraken WebSocket client.
"""
import asyncio
import json
import pytest
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from queue import Queue, Empty

from bot.kraken_websocket import (
    KrakenWebSocketClient,
    WebSocketCallbackHandler,
    DefaultWebSocketCallbackHandler,
    EnhancedWebSocketCallbackHandler,
    WebSocketConfig,
    WebSocketState,
    SubscriptionType,
    Subscription,
    WebSocketMessage,
    WebSocketClientFactory,
    WebSocketHealthMonitor,
    WebSocketMessageValidator,
    WebSocketPerformanceOptimizer,
    WebSocketConnectionPool,
    parse_ticker_data,
    parse_ohlc_data,
    parse_trade_data,
    parse_book_data
)
from bot.kraken_client import KrakenCredentials


class TestWebSocketCallbackHandler:
    """Test WebSocket callback handler."""
    
    def test_callback_handler_interface(self):
        """Test callback handler interface."""
        handler = WebSocketCallbackHandler()
        
        # Test all callback methods exist and can be called
        handler.on_ticker("BTCUSD", {})
        handler.on_ohlc("BTCUSD", {})
        handler.on_trade("BTCUSD", {})
        handler.on_book("BTCUSD", {})
        handler.on_spread("BTCUSD", {})
        handler.on_orders({})
        handler.on_connection_status(WebSocketState.CONNECTED)
        handler.on_error(Exception("test"))
        handler.on_subscription_status("sub_1", "subscribed")
    
    def test_default_callback_handler(self):
        """Test default callback handler."""
        handler = DefaultWebSocketCallbackHandler()
        
        # Test that methods don't raise exceptions
        handler.on_ticker("BTCUSD", {"c": ["50000", "1"]})
        handler.on_ohlc("BTCUSD", [1234567890, 1234567900, "49000", "51000", "48000", "50000", "49500", "100", 50])
        handler.on_trade("BTCUSD", [["50000", "1", "1234567890", "b", "m", ""]])
        handler.on_book("BTCUSD", {"as": [["50100", "1", "1234567890"]]})
        handler.on_spread("BTCUSD", ["50000", "50100", "1234567890", "1", "2"])
        handler.on_orders([{"order_id": "test", "status": "open"}])
        handler.on_connection_status(WebSocketState.CONNECTED)
        handler.on_error(Exception("test error"))
        handler.on_subscription_status("sub_1", "subscribed")


class TestWebSocketConfig:
    """Test WebSocket configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = WebSocketConfig()
        
        assert config.public_url == "wss://ws.kraken.com"
        assert config.private_url == "wss://ws-auth.kraken.com"
        assert config.ping_interval == 30
        assert config.ping_timeout == 10
        assert config.max_reconnect_attempts == 10
        assert config.reconnect_delay == 5
        assert config.max_reconnect_delay == 300
        assert config.backoff_multiplier == 1.5
        assert config.message_queue_size == 1000
        assert config.heartbeat_interval == 60
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = WebSocketConfig(
            ping_interval=60,
            max_reconnect_attempts=5,
            message_queue_size=500
        )
        
        assert config.ping_interval == 60
        assert config.max_reconnect_attempts == 5
        assert config.message_queue_size == 500


class TestSubscription:
    """Test subscription data class."""
    
    def test_subscription_creation(self):
        """Test subscription creation."""
        sub = Subscription(
            subscription_id="sub_1",
            channel="ticker",
            pairs=["BTCUSD", "ETHUSD"],
            subscription_type=SubscriptionType.TICKER
        )
        
        assert sub.subscription_id == "sub_1"
        assert sub.channel == "ticker"
        assert sub.pairs == ["BTCUSD", "ETHUSD"]
        assert sub.subscription_type == SubscriptionType.TICKER
        assert sub.is_private is False
        assert sub.depth is None
        assert sub.interval is None
        assert sub.snapshot is True
    
    def test_subscription_with_options(self):
        """Test subscription with optional parameters."""
        sub = Subscription(
            subscription_id="sub_2",
            channel="book",
            pairs=["BTCUSD"],
            subscription_type=SubscriptionType.BOOK,
            is_private=False,
            depth=25,
            snapshot=False
        )
        
        assert sub.depth == 25
        assert sub.snapshot is False


class TestWebSocketMessage:
    """Test WebSocket message data class."""
    
    def test_message_creation(self):
        """Test message creation."""
        timestamp = datetime.now()
        message = WebSocketMessage(
            channel="ticker",
            data={"c": ["50000", "1"]},
            timestamp=timestamp,
            subscription_id="sub_1",
            pair="BTCUSD"
        )
        
        assert message.channel == "ticker"
        assert message.data == {"c": ["50000", "1"]}
        assert message.timestamp == timestamp
        assert message.subscription_id == "sub_1"
        assert message.pair == "BTCUSD"


class TestKrakenWebSocketClient:
    """Test Kraken WebSocket client."""
    
    @pytest.fixture
    def credentials(self):
        """Create test credentials."""
        return KrakenCredentials(
            api_key="test_key",
            api_secret="dGVzdF9zZWNyZXQ="  # base64 encoded "test_secret"
        )
    
    @pytest.fixture
    def callback_handler(self):
        """Create mock callback handler."""
        return Mock(spec=WebSocketCallbackHandler)
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return WebSocketConfig(
            ping_interval=10,
            max_reconnect_attempts=3,
            reconnect_delay=1,
            message_queue_size=100
        )
    
    @pytest.fixture
    def ws_client(self, credentials, callback_handler, config):
        """Create WebSocket client."""
        return KrakenWebSocketClient(credentials, callback_handler, config)
    
    def test_client_initialization(self, ws_client, credentials, callback_handler, config):
        """Test client initialization."""
        assert ws_client.credentials == credentials
        assert ws_client.callback_handler == callback_handler
        assert ws_client.config == config
        assert ws_client.state == WebSocketState.DISCONNECTED
        assert ws_client.subscriptions == {}
        assert ws_client.running is False
    
    def test_generate_subscription_id(self, ws_client):
        """Test subscription ID generation."""
        id1 = ws_client._generate_subscription_id()
        id2 = ws_client._generate_subscription_id()
        
        assert id1 != id2
        assert id1.startswith("sub_1_")
        assert id2.startswith("sub_2_")
    
    def test_get_auth_token(self, ws_client):
        """Test authentication token generation."""
        with patch('time.time', return_value=1234567890):
            token = ws_client._get_auth_token()
            assert isinstance(token, str)
            assert len(token) > 0
    
    def test_subscription_methods(self, ws_client):
        """Test subscription methods."""
        # Test ticker subscription
        sub_id = ws_client.subscribe_ticker(["BTCUSD", "ETHUSD"])
        assert sub_id in ws_client.subscriptions
        sub = ws_client.subscriptions[sub_id]
        assert sub.channel == "ticker"
        assert sub.pairs == ["BTCUSD", "ETHUSD"]
        assert sub.subscription_type == SubscriptionType.TICKER
        
        # Test OHLC subscription
        sub_id = ws_client.subscribe_ohlc(["BTCUSD"], interval=5)
        sub = ws_client.subscriptions[sub_id]
        assert sub.channel == "ohlc"
        assert sub.interval == 5
        
        # Test trades subscription
        sub_id = ws_client.subscribe_trades(["BTCUSD"])
        sub = ws_client.subscriptions[sub_id]
        assert sub.channel == "trade"
        
        # Test order book subscription
        sub_id = ws_client.subscribe_orderbook(["BTCUSD"], depth=25)
        sub = ws_client.subscriptions[sub_id]
        assert sub.channel == "book"
        assert sub.depth == 25
        
        # Test spread subscription
        sub_id = ws_client.subscribe_spread(["BTCUSD"])
        sub = ws_client.subscriptions[sub_id]
        assert sub.channel == "spread"
        
        # Test orders subscription
        sub_id = ws_client.subscribe_orders()
        sub = ws_client.subscriptions[sub_id]
        assert sub.channel == "openOrders"
        assert sub.is_private is True
    
    def test_unsubscribe(self, ws_client):
        """Test unsubscribe functionality."""
        # Subscribe first
        sub_id = ws_client.subscribe_ticker(["BTCUSD"])
        assert sub_id in ws_client.subscriptions
        
        # Unsubscribe
        result = ws_client.unsubscribe(sub_id)
        assert result is True
        assert sub_id not in ws_client.subscriptions
        
        # Try to unsubscribe non-existent subscription
        result = ws_client.unsubscribe("non_existent")
        assert result is False
    
    def test_connection_state_methods(self, ws_client):
        """Test connection state methods."""
        assert ws_client.get_connection_state() == WebSocketState.DISCONNECTED
        assert ws_client.is_connected() is False
        
        # Simulate connected state
        ws_client.state = WebSocketState.CONNECTED
        assert ws_client.get_connection_state() == WebSocketState.CONNECTED
        assert ws_client.is_connected() is True
    
    def test_get_subscriptions(self, ws_client):
        """Test get subscriptions method."""
        # Add some subscriptions
        sub_id1 = ws_client.subscribe_ticker(["BTCUSD"])
        sub_id2 = ws_client.subscribe_trades(["ETHUSD"])
        
        subscriptions = ws_client.get_subscriptions()
        assert len(subscriptions) == 2
        assert sub_id1 in subscriptions
        assert sub_id2 in subscriptions
        
        # Ensure it returns a copy
        subscriptions.clear()
        assert len(ws_client.subscriptions) == 2
    
    def test_get_queue_size(self, ws_client):
        """Test queue size method."""
        assert ws_client.get_queue_size() == 0
        
        # Add message to queue
        message = WebSocketMessage("ticker", {}, datetime.now())
        ws_client.message_queue.put(message)
        assert ws_client.get_queue_size() == 1
    
    def test_get_stats(self, ws_client):
        """Test statistics method."""
        stats = ws_client.get_stats()
        
        assert "state" in stats
        assert "reconnect_attempts" in stats
        assert "active_subscriptions" in stats
        assert "queue_size" in stats
        assert "last_ping" in stats
        assert "last_pong" in stats
        assert "public_connected" in stats
        assert "private_connected" in stats
        
        assert stats["state"] == "disconnected"
        assert stats["reconnect_attempts"] == 0
        assert stats["active_subscriptions"] == 0
        assert stats["queue_size"] == 0
        assert stats["public_connected"] is False
        assert stats["private_connected"] is False
    
    @patch('websockets.connect')
    @pytest.mark.asyncio
    async def test_connect_public(self, mock_connect, ws_client):
        """Test public WebSocket connection."""
        mock_ws = AsyncMock()
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the websockets.connect to return the mock_ws directly
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        result = await ws_client._connect_public()
        assert result is True
        assert ws_client.public_ws == mock_ws
        
        mock_connect.assert_called_once_with(
            ws_client.config.public_url,
            ping_interval=ws_client.config.ping_interval,
            ping_timeout=ws_client.config.ping_timeout
        )
    
    @patch('websockets.connect')
    @pytest.mark.asyncio
    async def test_connect_private(self, mock_connect, ws_client):
        """Test private WebSocket connection."""
        mock_ws = AsyncMock()
        
        # Mock the websockets.connect to return the mock_ws directly
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        with patch.object(ws_client, '_get_auth_token', return_value='test_token'):
            result = await ws_client._connect_private()
            assert result is True
            assert ws_client.private_ws == mock_ws
            
            # Verify auth message was sent
            mock_ws.send.assert_called_once()
            sent_message = json.loads(mock_ws.send.call_args[0][0])
            assert sent_message["event"] == "subscribe"
            assert sent_message["subscription"]["name"] == "openOrders"
            assert sent_message["subscription"]["token"] == "test_token"
    
    @pytest.mark.asyncio
    async def test_disconnect(self, ws_client):
        """Test WebSocket disconnection."""
        # Set up mock WebSocket connections
        mock_public_ws = AsyncMock()
        mock_private_ws = AsyncMock()
        ws_client.public_ws = mock_public_ws
        ws_client.private_ws = mock_private_ws
        
        await ws_client._disconnect()
        
        mock_public_ws.close.assert_called_once()
        mock_private_ws.close.assert_called_once()
        assert ws_client.public_ws is None
        assert ws_client.private_ws is None
    
    @pytest.mark.asyncio
    async def test_send_message(self, ws_client):
        """Test message sending."""
        # Test public message
        mock_public_ws = AsyncMock()
        ws_client.public_ws = mock_public_ws
        message = {"event": "subscribe", "pair": ["BTCUSD"]}
        
        result = await ws_client._send_message(message)
        assert result is True
        mock_public_ws.send.assert_called_once_with(json.dumps(message))
        
        # Test private message
        mock_private_ws = AsyncMock()
        ws_client.private_ws = mock_private_ws
        result = await ws_client._send_message(message, use_private=True)
        assert result is True
        mock_private_ws.send.assert_called_once_with(json.dumps(message))
        
        # Test with no connection
        ws_client.public_ws = None
        result = await ws_client._send_message(message)
        assert result is False
    
    def test_message_dispatch(self, ws_client, callback_handler):
        """Test message dispatching to callbacks."""
        timestamp = datetime.now()
        
        # Test ticker message
        message = WebSocketMessage("ticker", {"c": ["50000", "1"]}, timestamp, pair="BTCUSD")
        ws_client._dispatch_message(message)
        callback_handler.on_ticker.assert_called_once_with("BTCUSD", {"c": ["50000", "1"]})
        
        # Test OHLC message
        callback_handler.reset_mock()
        message = WebSocketMessage("ohlc", [1234567890, 1234567900, "49000"], timestamp, pair="BTCUSD")
        ws_client._dispatch_message(message)
        callback_handler.on_ohlc.assert_called_once_with("BTCUSD", [1234567890, 1234567900, "49000"])
        
        # Test trade message
        callback_handler.reset_mock()
        message = WebSocketMessage("trade", [["50000", "1", "1234567890"]], timestamp, pair="BTCUSD")
        ws_client._dispatch_message(message)
        callback_handler.on_trade.assert_called_once_with("BTCUSD", [["50000", "1", "1234567890"]])
        
        # Test book message
        callback_handler.reset_mock()
        message = WebSocketMessage("book", {"as": [["50100", "1", "1234567890"]]}, timestamp, pair="BTCUSD")
        ws_client._dispatch_message(message)
        callback_handler.on_book.assert_called_once_with("BTCUSD", {"as": [["50100", "1", "1234567890"]]})
        
        # Test spread message
        callback_handler.reset_mock()
        message = WebSocketMessage("spread", ["50000", "50100"], timestamp, pair="BTCUSD")
        ws_client._dispatch_message(message)
        callback_handler.on_spread.assert_called_once_with("BTCUSD", ["50000", "50100"])
        
        # Test orders message
        callback_handler.reset_mock()
        message = WebSocketMessage("openOrders", [{"order_id": "test"}], timestamp)
        ws_client._dispatch_message(message)
        callback_handler.on_orders.assert_called_once_with([{"order_id": "test"}])
    
    @pytest.mark.asyncio
    async def test_handle_event_message(self, ws_client, callback_handler):
        """Test event message handling."""
        # Test system status
        await ws_client._handle_event_message({"event": "systemStatus", "status": "online"}, False)
        
        # Test subscription status
        ws_client.subscriptions["sub_1"] = Subscription(
            subscription_id="sub_1",
            channel="ticker",
            pairs=["BTCUSD"],
            subscription_type=SubscriptionType.TICKER
        )
        
        await ws_client._handle_event_message({
            "event": "subscriptionStatus",
            "status": "subscribed",
            "channelName": "ticker",
            "pair": "BTCUSD"
        }, False)
        
        callback_handler.on_subscription_status.assert_called_once_with("sub_1", "subscribed", None)
        
        # Test heartbeat
        await ws_client._handle_event_message({"event": "heartbeat"}, False)
        assert ws_client.last_pong is not None
    
    @pytest.mark.asyncio
    async def test_handle_data_message(self, ws_client):
        """Test data message handling."""
        # Test valid data message
        data = [123, {"c": ["50000", "1"]}, "ticker", "BTCUSD"]
        await ws_client._handle_data_message(data, False)
        
        # Check message was queued
        assert ws_client.message_queue.qsize() == 1
        message = ws_client.message_queue.get()
        assert message.channel == "ticker"
        assert message.data == {"c": ["50000", "1"]}
        assert message.pair == "BTCUSD"
        
        # Test invalid data message
        await ws_client._handle_data_message([123], False)
        # Should not queue invalid message
        assert ws_client.message_queue.qsize() == 0
    
    def test_message_processing_thread(self, ws_client, callback_handler):
        """Test message processing in separate thread."""
        # Add message to queue
        message = WebSocketMessage("ticker", {"c": ["50000", "1"]}, datetime.now(), pair="BTCUSD")
        ws_client.message_queue.put(message)
        
        # Start processing
        ws_client.running = True
        
        # Process one message
        ws_client._process_messages()
        
        # Verify callback was called
        callback_handler.on_ticker.assert_called_once_with("BTCUSD", {"c": ["50000", "1"]})
    
    def test_disconnect_cleanup(self, ws_client):
        """Test disconnect cleanup."""
        # Add some subscriptions and messages
        ws_client.subscribe_ticker(["BTCUSD"])
        ws_client.message_queue.put(WebSocketMessage("ticker", {}, datetime.now()))
        
        # Mock threads
        ws_client.connection_thread = Mock()
        ws_client.connection_thread.is_alive.return_value = False
        ws_client.message_processor_thread = Mock()
        ws_client.message_processor_thread.is_alive.return_value = False
        
        # Mock loop
        ws_client.loop = Mock()
        ws_client.loop.is_running.return_value = False
        
        ws_client.running = True
        ws_client.disconnect()
        
        assert ws_client.running is False
        assert len(ws_client.subscriptions) == 0
        assert ws_client.message_queue.qsize() == 0
        assert ws_client.state == WebSocketState.CLOSED


class TestMessageParsing:
    """Test message parsing utilities."""
    
    def test_parse_ticker_data(self):
        """Test ticker data parsing."""
        data = {
            "a": ["50100.0", "2", "2.000"],
            "b": ["50000.0", "1", "1.000"],
            "c": ["50050.0", "0.5"],
            "v": ["100.0", "200.0"],
            "p": ["50025.0", "50030.0"],
            "t": [50, 100],
            "l": ["49000.0", "48000.0"],
            "h": ["51000.0", "52000.0"],
            "o": ["49500.0", "49000.0"]
        }
        
        parsed = parse_ticker_data(data)
        
        assert parsed["ask_price"] == 50100.0
        assert parsed["ask_volume"] == 2.0
        assert parsed["bid_price"] == 50000.0
        assert parsed["bid_volume"] == 1.0
        assert parsed["last_price"] == 50050.0
        assert parsed["last_volume"] == 0.5
        assert parsed["volume_today"] == 100.0
        assert parsed["volume_24h"] == 200.0
        assert parsed["vwap_today"] == 50025.0
        assert parsed["vwap_24h"] == 50030.0
        assert parsed["trades_today"] == 50
        assert parsed["trades_24h"] == 100
        assert parsed["low_today"] == 49000.0
        assert parsed["low_24h"] == 48000.0
        assert parsed["high_today"] == 51000.0
        assert parsed["high_24h"] == 52000.0
        assert parsed["open_today"] == 49500.0
        assert parsed["open_24h"] == 49000.0
    
    def test_parse_ticker_data_invalid(self):
        """Test ticker data parsing with invalid data."""
        # Test with empty data - should return default values
        parsed = parse_ticker_data({})
        assert "ask_price" in parsed
        assert parsed["ask_price"] == 0.0
        
        # Test with malformed data - should return empty dict due to exception
        parsed = parse_ticker_data({"a": "invalid"})
        assert parsed == {}
    
    def test_parse_ohlc_data(self):
        """Test OHLC data parsing."""
        data = [1234567890.0, 1234567900.0, "49000.0", "51000.0", "48000.0", "50000.0", "49500.0", "100.0", 50]
        
        parsed = parse_ohlc_data(data)
        
        assert parsed["time"] == 1234567890.0
        assert parsed["end_time"] == 1234567900.0
        assert parsed["open"] == 49000.0
        assert parsed["high"] == 51000.0
        assert parsed["low"] == 48000.0
        assert parsed["close"] == 50000.0
        assert parsed["vwap"] == 49500.0
        assert parsed["volume"] == 100.0
        assert parsed["count"] == 50
    
    def test_parse_ohlc_data_invalid(self):
        """Test OHLC data parsing with invalid data."""
        # Test with insufficient data
        parsed = parse_ohlc_data([1234567890.0])
        assert parsed == {}
        
        # Test with invalid values
        parsed = parse_ohlc_data(["invalid"] * 9)
        assert parsed == {}
    
    def test_parse_trade_data(self):
        """Test trade data parsing."""
        trades = [
            ["50000.0", "1.0", "1234567890.0", "b", "m", ""],
            ["50100.0", "0.5", "1234567891.0", "s", "l", "misc"]
        ]
        
        parsed = parse_trade_data(trades)
        
        assert len(parsed) == 2
        
        trade1 = parsed[0]
        assert trade1["price"] == 50000.0
        assert trade1["volume"] == 1.0
        assert trade1["time"] == 1234567890.0
        assert trade1["side"] == "buy"
        assert trade1["order_type"] == "market"
        assert trade1["misc"] == ""
        
        trade2 = parsed[1]
        assert trade2["price"] == 50100.0
        assert trade2["volume"] == 0.5
        assert trade2["time"] == 1234567891.0
        assert trade2["side"] == "sell"
        assert trade2["order_type"] == "limit"
        assert trade2["misc"] == "misc"
    
    def test_parse_trade_data_invalid(self):
        """Test trade data parsing with invalid data."""
        # Test with insufficient data
        trades = [["50000.0"]]
        parsed = parse_trade_data(trades)
        assert len(parsed) == 0
        
        # Test with invalid values
        trades = [["invalid"] * 6]
        parsed = parse_trade_data(trades)
        assert len(parsed) == 0
    
    def test_parse_book_data(self):
        """Test order book data parsing."""
        data = {
            "as": [["50100.0", "2.0", "1234567890.0"], ["50200.0", "1.0", "1234567891.0"]],
            "bs": [["50000.0", "1.5", "1234567890.0"], ["49900.0", "3.0", "1234567891.0"]],
            "a": [["50150.0", "0.5", "1234567892.0"]],
            "b": [["49950.0", "1.0", "1234567892.0"]]
        }
        
        parsed = parse_book_data(data)
        
        # Check asks
        assert len(parsed["asks"]) == 2
        assert parsed["asks"][0]["price"] == 50100.0
        assert parsed["asks"][0]["volume"] == 2.0
        assert parsed["asks"][0]["timestamp"] == 1234567890.0
        
        # Check bids
        assert len(parsed["bids"]) == 2
        assert parsed["bids"][0]["price"] == 50000.0
        assert parsed["bids"][0]["volume"] == 1.5
        assert parsed["bids"][0]["timestamp"] == 1234567890.0
        
        # Check ask updates
        assert len(parsed["ask_updates"]) == 1
        assert parsed["ask_updates"][0]["price"] == 50150.0
        
        # Check bid updates
        assert len(parsed["bid_updates"]) == 1
        assert parsed["bid_updates"][0]["price"] == 49950.0
    
    def test_parse_book_data_invalid(self):
        """Test order book data parsing with invalid data."""
        # Test with empty data
        parsed = parse_book_data({})
        assert parsed == {}
        
        # Test with malformed data
        data = {"as": [["invalid"]]}
        parsed = parse_book_data(data)
        assert "asks" in parsed
        assert len(parsed["asks"]) == 0


class TestEnhancedWebSocketCallbackHandler:
    """Test enhanced WebSocket callback handler."""
    
    def test_enhanced_handler_initialization(self):
        """Test enhanced handler initialization."""
        handler = EnhancedWebSocketCallbackHandler()
        
        assert handler.data_manager is None
        assert handler.strategy_engine is None
        assert handler.risk_manager is None
        assert handler.last_prices == {}
        assert handler.price_changes == {}
    
    def test_enhanced_ticker_processing(self):
        """Test enhanced ticker processing."""
        handler = EnhancedWebSocketCallbackHandler()
        
        # First ticker update
        ticker_data = {"c": ["50000.0", "1"]}
        handler.on_ticker("BTCUSD", ticker_data)
        
        assert "BTCUSD" in handler.last_prices
        assert handler.last_prices["BTCUSD"] == 50000.0
        
        # Second ticker update to test price change
        ticker_data = {"c": ["50100.0", "1"]}
        handler.on_ticker("BTCUSD", ticker_data)
        
        assert handler.last_prices["BTCUSD"] == 50100.0
        assert handler.price_changes["BTCUSD"] == 100.0
    
    def test_get_price_changes(self):
        """Test getting price changes."""
        handler = EnhancedWebSocketCallbackHandler()
        
        # Add some price changes
        handler.price_changes = {"BTCUSD": 100.0, "ETHUSD": -50.0}
        
        changes = handler.get_price_changes()
        assert changes == {"BTCUSD": 100.0, "ETHUSD": -50.0}
        
        # Ensure it returns a copy
        changes.clear()
        assert len(handler.price_changes) == 2


class TestWebSocketClientFactory:
    """Test WebSocket client factory."""
    
    @pytest.fixture
    def credentials(self):
        """Create test credentials."""
        return KrakenCredentials("test_key", "dGVzdF9zZWNyZXQ=")
    
    def test_create_basic_client(self, credentials):
        """Test creating basic client."""
        client = WebSocketClientFactory.create_basic_client(credentials)
        
        assert isinstance(client, KrakenWebSocketClient)
        assert isinstance(client.callback_handler, DefaultWebSocketCallbackHandler)
        assert client.config.message_queue_size == 1000
    
    def test_create_enhanced_client(self, credentials):
        """Test creating enhanced client."""
        client = WebSocketClientFactory.create_enhanced_client(credentials)
        
        assert isinstance(client, KrakenWebSocketClient)
        assert isinstance(client.callback_handler, EnhancedWebSocketCallbackHandler)
        assert client.config.message_queue_size == 2000
    
    def test_create_high_frequency_client(self, credentials):
        """Test creating high frequency client."""
        client = WebSocketClientFactory.create_high_frequency_client(credentials)
        
        assert isinstance(client, KrakenWebSocketClient)
        assert isinstance(client.callback_handler, EnhancedWebSocketCallbackHandler)
        assert client.config.message_queue_size == 5000
        assert client.config.ping_interval == 10


class TestWebSocketHealthMonitor:
    """Test WebSocket health monitor."""
    
    @pytest.fixture
    def ws_client(self):
        """Create mock WebSocket client."""
        credentials = KrakenCredentials("test_key", "dGVzdF9zZWNyZXQ=")
        return WebSocketClientFactory.create_basic_client(credentials)
    
    def test_health_monitor_initialization(self, ws_client):
        """Test health monitor initialization."""
        monitor = WebSocketHealthMonitor(ws_client)
        
        assert monitor.ws_client == ws_client
        assert monitor.message_count == 0
        assert monitor.error_count == 0
        assert monitor.reconnect_count == 0
        assert monitor.last_message_time is None
    
    def test_record_metrics(self, ws_client):
        """Test recording metrics."""
        monitor = WebSocketHealthMonitor(ws_client)
        
        # Record some events
        monitor.record_message()
        monitor.record_message()
        monitor.record_error()
        monitor.record_reconnect()
        
        assert monitor.message_count == 2
        assert monitor.error_count == 1
        assert monitor.reconnect_count == 1
        assert monitor.last_message_time is not None
    
    def test_get_health_metrics(self, ws_client):
        """Test getting health metrics."""
        monitor = WebSocketHealthMonitor(ws_client)
        
        # Record some events
        monitor.record_message()
        monitor.record_error()
        
        metrics = monitor.get_health_metrics()
        
        assert "uptime_seconds" in metrics
        assert "message_count" in metrics
        assert "error_count" in metrics
        assert "reconnect_count" in metrics
        assert "messages_per_minute" in metrics
        assert "error_rate" in metrics
        assert "connection_state" in metrics
        assert "queue_size" in metrics
        assert "active_subscriptions" in metrics
        
        assert metrics["message_count"] == 1
        assert metrics["error_count"] == 1
        assert metrics["error_rate"] == 1.0


class TestWebSocketMessageValidator:
    """Test WebSocket message validator."""
    
    def test_validate_ticker_data(self):
        """Test ticker data validation."""
        # Valid ticker data
        valid_data = {"c": ["50000.0", "1"], "a": ["50100.0", "2", "2.000"]}
        assert WebSocketMessageValidator.validate_ticker_data(valid_data) is True
        
        # Invalid ticker data (missing required field)
        invalid_data = {"a": ["50100.0", "2", "2.000"]}
        assert WebSocketMessageValidator.validate_ticker_data(invalid_data) is False
    
    def test_validate_trade_data(self):
        """Test trade data validation."""
        # Valid trade data
        valid_data = [["50000.0", "1.0", "1234567890.0", "b", "m", ""]]
        assert WebSocketMessageValidator.validate_trade_data(valid_data) is True
        
        # Invalid trade data (not a list)
        invalid_data = {"trades": []}
        assert WebSocketMessageValidator.validate_trade_data(invalid_data) is False
        
        # Invalid trade data (insufficient fields)
        invalid_data = [["50000.0", "1.0"]]
        assert WebSocketMessageValidator.validate_trade_data(invalid_data) is False
    
    def test_validate_book_data(self):
        """Test order book data validation."""
        # Valid book data
        valid_data = {"as": [["50100.0", "2.0", "1234567890.0"]]}
        assert WebSocketMessageValidator.validate_book_data(valid_data) is True
        
        # Valid book data with bids
        valid_data = {"bs": [["50000.0", "1.5", "1234567890.0"]]}
        assert WebSocketMessageValidator.validate_book_data(valid_data) is True
        
        # Invalid book data (not a dict)
        invalid_data = []
        assert WebSocketMessageValidator.validate_book_data(invalid_data) is False
        
        # Invalid book data (no asks or bids)
        invalid_data = {"other": "data"}
        assert WebSocketMessageValidator.validate_book_data(invalid_data) is False
    
    def test_validate_ohlc_data(self):
        """Test OHLC data validation."""
        # Valid OHLC data
        valid_data = [1234567890.0, 1234567900.0, "49000.0", "51000.0", "48000.0", "50000.0", "49500.0", "100.0", 50]
        assert WebSocketMessageValidator.validate_ohlc_data(valid_data) is True
        
        # Invalid OHLC data (insufficient fields)
        invalid_data = [1234567890.0, 1234567900.0]
        assert WebSocketMessageValidator.validate_ohlc_data(invalid_data) is False
        
        # Invalid OHLC data (not a list)
        invalid_data = {"time": 1234567890.0}
        assert WebSocketMessageValidator.validate_ohlc_data(invalid_data) is False


class TestWebSocketPerformanceOptimizer:
    """Test WebSocket performance optimizer."""
    
    @pytest.fixture
    def ws_client(self):
        """Create mock WebSocket client."""
        credentials = KrakenCredentials("test_key", "dGVzdF9zZWNyZXQ=")
        return WebSocketClientFactory.create_basic_client(credentials)
    
    def test_optimizer_initialization(self, ws_client):
        """Test optimizer initialization."""
        optimizer = WebSocketPerformanceOptimizer(ws_client)
        
        assert optimizer.ws_client == ws_client
        assert optimizer.message_rates == {}
        assert optimizer.last_optimization is not None
    
    def test_record_message_rate(self, ws_client):
        """Test recording message rates."""
        optimizer = WebSocketPerformanceOptimizer(ws_client)
        
        # Record some messages
        optimizer.record_message_rate("ticker")
        optimizer.record_message_rate("ticker")
        optimizer.record_message_rate("trade")
        
        assert "ticker" in optimizer.message_rates
        assert "trade" in optimizer.message_rates
        assert len(optimizer.message_rates["ticker"]) == 2
        assert len(optimizer.message_rates["trade"]) == 1
    
    def test_get_message_rate(self, ws_client):
        """Test getting message rates."""
        optimizer = WebSocketPerformanceOptimizer(ws_client)
        
        # Record messages
        for _ in range(60):  # 60 messages in last minute = 1 per second
            optimizer.record_message_rate("ticker")
        
        rate = optimizer.get_message_rate("ticker")
        assert rate == 1.0  # 1 message per second
        
        # Test unknown channel
        rate = optimizer.get_message_rate("unknown")
        assert rate == 0.0


class TestWebSocketConnectionPool:
    """Test WebSocket connection pool."""
    
    @pytest.fixture
    def credentials(self):
        """Create test credentials."""
        return KrakenCredentials("test_key", "dGVzdF9zZWNyZXQ=")
    
    def test_pool_initialization(self, credentials):
        """Test pool initialization."""
        pool = WebSocketConnectionPool(credentials, max_connections=3)
        
        assert pool.credentials == credentials
        assert pool.max_connections == 3
        assert pool.connections == {}
        assert pool.pair_assignments == {}
    
    def test_get_connection_for_pair(self, credentials):
        """Test getting connection for pair."""
        pool = WebSocketConnectionPool(credentials, max_connections=2)
        
        # First pair should create new connection
        conn1 = pool.get_connection_for_pair("BTCUSD")
        assert isinstance(conn1, KrakenWebSocketClient)
        assert len(pool.connections) == 1
        assert pool.pair_assignments["BTCUSD"] == conn1
        
        # Same pair should return same connection
        conn1_again = pool.get_connection_for_pair("BTCUSD")
        assert conn1_again == conn1
        assert len(pool.connections) == 1
        
        # Different pair should use same connection if under load limit
        conn2 = pool.get_connection_for_pair("ETHUSD")
        assert conn2 == conn1  # Should reuse same connection
        assert len(pool.connections) == 1
    
    def test_pool_stats(self, credentials):
        """Test getting pool statistics."""
        pool = WebSocketConnectionPool(credentials)
        
        # Add some pairs
        pool.get_connection_for_pair("BTCUSD")
        pool.get_connection_for_pair("ETHUSD")
        
        stats = pool.get_pool_stats()
        
        assert "total_connections" in stats
        assert "total_pairs" in stats
        assert "connection_states" in stats
        assert "pair_distribution" in stats
        
        assert stats["total_connections"] == 1
        assert stats["total_pairs"] == 2