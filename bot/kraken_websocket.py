"""
Kraken WebSocket client for real-time market data and order updates.
Provides real-time ticker, orderbook, trade data, and private order updates.
"""
import asyncio
import json
import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union
from queue import Queue, Empty
import websockets
import base64
import hashlib
import hmac
import urllib.parse

from bot.kraken_client import KrakenCredentials
from bot.utils import log_error, log_info, log_warning


class WebSocketState(Enum):
    """WebSocket connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class SubscriptionType(Enum):
    """WebSocket subscription types."""
    TICKER = "ticker"
    OHLC = "ohlc"
    TRADE = "trade"
    BOOK = "book"
    SPREAD = "spread"
    ORDERS = "openOrders"  # Private channel


@dataclass
class WebSocketConfig:
    """WebSocket client configuration."""
    public_url: str = "wss://ws.kraken.com"
    private_url: str = "wss://ws-auth.kraken.com"
    ping_interval: int = 30
    ping_timeout: int = 10
    max_reconnect_attempts: int = 10
    reconnect_delay: int = 5
    max_reconnect_delay: int = 300
    backoff_multiplier: float = 1.5
    message_queue_size: int = 1000
    heartbeat_interval: int = 60


@dataclass
class Subscription:
    """WebSocket subscription details."""
    subscription_id: str
    channel: str
    pairs: List[str]
    subscription_type: SubscriptionType
    is_private: bool = False
    depth: Optional[int] = None
    interval: Optional[int] = None
    snapshot: bool = True


@dataclass
class WebSocketMessage:
    """WebSocket message wrapper."""
    channel: str
    data: Dict[str, Any]
    timestamp: datetime
    subscription_id: Optional[str] = None
    pair: Optional[str] = None


class WebSocketCallbackHandler:
    """Base class for handling WebSocket callbacks."""
    
    def on_ticker(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle ticker updates."""
        pass
    
    def on_ohlc(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle OHLC updates."""
        pass
    
    def on_trade(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle trade updates."""
        pass
    
    def on_book(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle order book updates."""
        pass
    
    def on_spread(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle spread updates."""
        pass
    
    def on_orders(self, data: Dict[str, Any]) -> None:
        """Handle private order updates."""
        pass
    
    def on_connection_status(self, status: WebSocketState) -> None:
        """Handle connection status changes."""
        pass
    
    def on_error(self, error: Exception) -> None:
        """Handle errors."""
        pass
    
    def on_subscription_status(self, subscription_id: str, status: str, error: Optional[str] = None) -> None:
        """Handle subscription status updates."""
        pass


class KrakenWebSocketClient:
    """
    Kraken WebSocket client for real-time data.
    
    Features:
    - Real-time market data (ticker, orderbook, trades)
    - Private order updates
    - Auto-reconnect with exponential backoff
    - Message queuing and buffering
    - Subscription management
    """
    
    def __init__(self, credentials: KrakenCredentials, callback_handler: WebSocketCallbackHandler,
                 config: Optional[WebSocketConfig] = None):
        """Initialize WebSocket client."""
        self.credentials = credentials
        self.callback_handler = callback_handler
        self.config = config or WebSocketConfig()
        
        # Connection state
        self.state = WebSocketState.DISCONNECTED
        self.public_ws = None
        self.private_ws = None
        self.reconnect_attempts = 0
        self.last_ping = None
        self.last_pong = None
        
        # Subscription management
        self.subscriptions: Dict[str, Subscription] = {}
        self.subscription_counter = 0
        
        # Message handling
        self.message_queue = Queue(maxsize=self.config.message_queue_size)
        self.message_processor_thread = None
        self.connection_monitor_thread = None
        
        # Threading and async
        self.loop = None
        self.running = False
        self.lock = threading.Lock()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        log_info("KrakenWebSocketClient initialized")
    
    def _generate_subscription_id(self) -> str:
        """Generate unique subscription ID."""
        self.subscription_counter += 1
        return f"sub_{self.subscription_counter}_{int(time.time())}"
    
    def _get_auth_token(self) -> str:
        """Generate authentication token for private WebSocket."""
        try:
            # Create nonce
            nonce = str(int(1000 * time.time()))
            
            # Create message for signing
            message = nonce.encode()
            
            # Create signature
            secret = base64.b64decode(self.credentials.api_secret)
            signature = hmac.new(secret, message, hashlib.sha512)
            token = base64.b64encode(signature.digest()).decode()
            
            return token
        except Exception as e:
            log_error(f"Error generating auth token: {str(e)}")
            raise e
    
    async def _connect_public(self) -> bool:
        """Connect to public WebSocket."""
        try:
            log_info("Connecting to Kraken public WebSocket...")
            self.public_ws = await websockets.connect(
                self.config.public_url,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout
            )
            log_info("Connected to Kraken public WebSocket")
            return True
        except Exception as e:
            log_error(f"Failed to connect to public WebSocket: {str(e)}")
            return False
    
    async def _connect_private(self) -> bool:
        """Connect to private WebSocket."""
        try:
            log_info("Connecting to Kraken private WebSocket...")
            
            # Get authentication token
            token = self._get_auth_token()
            
            self.private_ws = await websockets.connect(
                self.config.private_url,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout
            )
            
            # Send authentication message
            auth_message = {
                "event": "subscribe",
                "subscription": {"name": "openOrders", "token": token}
            }
            await self.private_ws.send(json.dumps(auth_message))
            
            log_info("Connected to Kraken private WebSocket")
            return True
        except Exception as e:
            log_error(f"Failed to connect to private WebSocket: {str(e)}")
            return False
    
    async def _disconnect(self):
        """Disconnect WebSocket connections."""
        try:
            if self.public_ws:
                await self.public_ws.close()
                self.public_ws = None
            
            if self.private_ws:
                await self.private_ws.close()
                self.private_ws = None
            
            log_info("WebSocket connections closed")
        except Exception as e:
            log_error(f"Error during disconnect: {str(e)}")
    
    async def _send_message(self, message: Dict[str, Any], use_private: bool = False) -> bool:
        """Send message to WebSocket."""
        try:
            ws = self.private_ws if use_private else self.public_ws
            if not ws:
                log_error(f"WebSocket not connected ({'private' if use_private else 'public'})")
                return False
            
            await ws.send(json.dumps(message))
            return True
        except Exception as e:
            log_error(f"Error sending message: {str(e)}")
            return False
    
    async def _handle_message(self, message: str, is_private: bool = False):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle system messages
            if isinstance(data, dict):
                if "event" in data:
                    await self._handle_event_message(data, is_private)
                    return
                
                if "errorMessage" in data:
                    log_error(f"WebSocket error: {data['errorMessage']}")
                    self.callback_handler.on_error(Exception(data["errorMessage"]))
                    return
            
            # Handle data messages (arrays)
            if isinstance(data, list) and len(data) >= 2:
                await self._handle_data_message(data, is_private)
            
        except json.JSONDecodeError as e:
            log_error(f"Failed to parse WebSocket message: {str(e)}")
        except Exception as e:
            log_error(f"Error handling WebSocket message: {str(e)}")
            self.callback_handler.on_error(e)
    
    async def _handle_event_message(self, data: Dict[str, Any], is_private: bool):
        """Handle WebSocket event messages."""
        event = data.get("event")
        
        if event == "systemStatus":
            status = data.get("status")
            log_info(f"System status: {status}")
            
        elif event == "subscriptionStatus":
            status = data.get("status")
            channel = data.get("channelName")
            pair = data.get("pair")
            subscription = data.get("subscription", {})
            
            log_info(f"Subscription status: {status} for {channel} ({pair})")
            
            # Find subscription ID
            subscription_id = None
            for sub_id, sub in self.subscriptions.items():
                if sub.channel == channel and (not pair or pair in sub.pairs):
                    subscription_id = sub_id
                    break
            
            if subscription_id:
                error_msg = data.get("errorMessage")
                self.callback_handler.on_subscription_status(subscription_id, status, error_msg)
        
        elif event == "heartbeat":
            self.last_pong = datetime.now()
            log_info("Received heartbeat")
    
    async def _handle_data_message(self, data: List[Any], is_private: bool):
        """Handle WebSocket data messages."""
        try:
            if len(data) < 3:
                return
            
            channel_id = data[0]
            message_data = data[1]
            channel_name = data[2]
            pair = data[3] if len(data) > 3 else None
            
            # Create WebSocket message
            ws_message = WebSocketMessage(
                channel=channel_name,
                data=message_data,
                timestamp=datetime.now(),
                pair=pair
            )
            
            # Queue message for processing
            try:
                self.message_queue.put_nowait(ws_message)
            except:
                log_warning("Message queue full, dropping message")
        
        except Exception as e:
            log_error(f"Error processing data message: {str(e)}")
    
    def _process_messages(self):
        """Process messages from queue in separate thread."""
        while self.running:
            try:
                message = self.message_queue.get(timeout=1.0)
                self._dispatch_message(message)
                self.message_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                log_error(f"Error processing message: {str(e)}")
    
    def _dispatch_message(self, message: WebSocketMessage):
        """Dispatch message to appropriate callback."""
        try:
            channel = message.channel
            pair = message.pair
            data = message.data
            
            if channel == "ticker":
                self.callback_handler.on_ticker(pair, data)
            elif channel == "ohlc":
                self.callback_handler.on_ohlc(pair, data)
            elif channel == "trade":
                self.callback_handler.on_trade(pair, data)
            elif channel == "book":
                self.callback_handler.on_book(pair, data)
            elif channel == "spread":
                self.callback_handler.on_spread(pair, data)
            elif channel == "openOrders":
                self.callback_handler.on_orders(data)
            else:
                log_warning(f"Unknown channel: {channel}")
        
        except Exception as e:
            log_error(f"Error dispatching message: {str(e)}")
            self.callback_handler.on_error(e)
    
    async def _connection_monitor(self):
        """Monitor connection health and handle reconnects."""
        while self.running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                # Check connection health
                if self.state == WebSocketState.CONNECTED:
                    # Send ping if needed
                    now = datetime.now()
                    if (not self.last_ping or 
                        (now - self.last_ping).seconds >= self.config.ping_interval):
                        
                        await self._send_ping()
                        self.last_ping = now
                    
                    # Check for missed pongs
                    if (self.last_pong and 
                        (now - self.last_pong).seconds > self.config.ping_timeout * 2):
                        log_warning("Connection appears stale, reconnecting...")
                        await self._reconnect()
                
                elif self.state == WebSocketState.DISCONNECTED:
                    log_info("Connection lost, attempting to reconnect...")
                    await self._reconnect()
            
            except Exception as e:
                log_error(f"Error in connection monitor: {str(e)}")
    
    async def _send_ping(self):
        """Send ping to WebSocket."""
        try:
            ping_message = {"event": "ping"}
            await self._send_message(ping_message)
            
            if self.private_ws:
                await self._send_message(ping_message, use_private=True)
        
        except Exception as e:
            log_error(f"Error sending ping: {str(e)}")
    
    async def _reconnect(self):
        """Reconnect with exponential backoff."""
        if self.state == WebSocketState.RECONNECTING:
            return
        
        self.state = WebSocketState.RECONNECTING
        self.callback_handler.on_connection_status(self.state)
        
        while self.running and self.reconnect_attempts < self.config.max_reconnect_attempts:
            try:
                self.reconnect_attempts += 1
                
                # Calculate backoff delay
                delay = min(
                    self.config.reconnect_delay * (self.config.backoff_multiplier ** (self.reconnect_attempts - 1)),
                    self.config.max_reconnect_delay
                )
                
                log_info(f"Reconnect attempt {self.reconnect_attempts}/{self.config.max_reconnect_attempts} in {delay}s")
                await asyncio.sleep(delay)
                
                # Disconnect existing connections
                await self._disconnect()
                
                # Reconnect
                public_connected = await self._connect_public()
                private_connected = True
                
                # Connect to private if we have private subscriptions
                if any(sub.is_private for sub in self.subscriptions.values()):
                    private_connected = await self._connect_private()
                
                if public_connected and private_connected:
                    self.state = WebSocketState.CONNECTED
                    self.reconnect_attempts = 0
                    self.callback_handler.on_connection_status(self.state)
                    
                    # Resubscribe to all channels
                    await self._resubscribe_all()
                    
                    log_info("Successfully reconnected")
                    return
            
            except Exception as e:
                log_error(f"Reconnect attempt failed: {str(e)}")
        
        # Max reconnect attempts reached
        log_error("Max reconnect attempts reached, giving up")
        self.state = WebSocketState.CLOSED
        self.callback_handler.on_connection_status(self.state)
    
    async def _resubscribe_all(self):
        """Resubscribe to all active subscriptions."""
        for subscription in self.subscriptions.values():
            try:
                await self._subscribe_internal(subscription)
            except Exception as e:
                log_error(f"Failed to resubscribe to {subscription.channel}: {str(e)}")
    
    async def _subscribe_internal(self, subscription: Subscription):
        """Internal subscription method."""
        message = {
            "event": "subscribe",
            "pair": subscription.pairs,
            "subscription": {"name": subscription.channel}
        }
        
        # Add optional parameters
        if subscription.depth is not None:
            message["subscription"]["depth"] = subscription.depth
        
        if subscription.interval is not None:
            message["subscription"]["interval"] = subscription.interval
        
        if not subscription.snapshot:
            message["subscription"]["snapshot"] = False
        
        # Send subscription message
        success = await self._send_message(message, subscription.is_private)
        if not success:
            raise Exception(f"Failed to send subscription message for {subscription.channel}")
    
    # Public API methods
    def connect(self) -> bool:
        """Connect to WebSocket."""
        try:
            with self.lock:
                if self.running:
                    log_warning("WebSocket client already running")
                    return True
                
                self.running = True
                self.state = WebSocketState.CONNECTING
                self.callback_handler.on_connection_status(self.state)
            
            # Start event loop in separate thread
            def run_loop():
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(self._run())
            
            self.connection_thread = threading.Thread(target=run_loop, daemon=True)
            self.connection_thread.start()
            
            # Start message processor
            self.message_processor_thread = threading.Thread(target=self._process_messages, daemon=True)
            self.message_processor_thread.start()
            
            # Wait a bit for connection to establish
            time.sleep(2)
            
            return self.state == WebSocketState.CONNECTED
        
        except Exception as e:
            log_error(f"Error connecting: {str(e)}")
            self.callback_handler.on_error(e)
            return False
    
    async def _run(self):
        """Main WebSocket run loop."""
        try:
            # Connect to WebSockets
            public_connected = await self._connect_public()
            if not public_connected:
                raise Exception("Failed to connect to public WebSocket")
            
            self.state = WebSocketState.CONNECTED
            self.callback_handler.on_connection_status(self.state)
            
            # Start connection monitor
            monitor_task = asyncio.create_task(self._connection_monitor())
            
            # Main message loop
            while self.running:
                try:
                    # Handle public WebSocket messages
                    if self.public_ws:
                        try:
                            message = await asyncio.wait_for(self.public_ws.recv(), timeout=1.0)
                            await self._handle_message(message, is_private=False)
                        except asyncio.TimeoutError:
                            pass
                    
                    # Handle private WebSocket messages
                    if self.private_ws:
                        try:
                            message = await asyncio.wait_for(self.private_ws.recv(), timeout=1.0)
                            await self._handle_message(message, is_private=True)
                        except asyncio.TimeoutError:
                            pass
                
                except websockets.exceptions.ConnectionClosed:
                    log_warning("WebSocket connection closed")
                    self.state = WebSocketState.DISCONNECTED
                    self.callback_handler.on_connection_status(self.state)
                    break
                
                except Exception as e:
                    log_error(f"Error in message loop: {str(e)}")
                    self.callback_handler.on_error(e)
            
            # Cleanup
            monitor_task.cancel()
            await self._disconnect()
        
        except Exception as e:
            log_error(f"Error in WebSocket run loop: {str(e)}")
            self.callback_handler.on_error(e)
        finally:
            self.state = WebSocketState.DISCONNECTED
            self.callback_handler.on_connection_status(self.state)
    
    def disconnect(self) -> None:
        """Disconnect WebSocket client."""
        try:
            with self.lock:
                if not self.running:
                    return
                
                self.running = False
            
            log_info("Disconnecting WebSocket client...")
            
            # Stop the event loop
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            # Wait for threads to finish
            if self.connection_thread and self.connection_thread.is_alive():
                self.connection_thread.join(timeout=5)
            
            if self.message_processor_thread and self.message_processor_thread.is_alive():
                self.message_processor_thread.join(timeout=5)
            
            # Clear subscriptions
            self.subscriptions.clear()
            
            # Clear message queue
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except Empty:
                    break
            
            self.state = WebSocketState.CLOSED
            self.callback_handler.on_connection_status(self.state)
            
            log_info("WebSocket client disconnected")
        
        except Exception as e:
            log_error(f"Error during disconnect: {str(e)}")
    
    def subscribe_ticker(self, pairs: List[str]) -> str:
        """Subscribe to ticker updates."""
        subscription_id = self._generate_subscription_id()
        
        subscription = Subscription(
            subscription_id=subscription_id,
            channel="ticker",
            pairs=pairs,
            subscription_type=SubscriptionType.TICKER,
            is_private=False
        )
        
        self.subscriptions[subscription_id] = subscription
        
        # Send subscription if connected
        if self.state == WebSocketState.CONNECTED and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_internal(subscription),
                self.loop
            )
        
        log_info(f"Subscribed to ticker for pairs: {pairs}")
        return subscription_id
    
    def subscribe_ohlc(self, pairs: List[str], interval: int = 1) -> str:
        """Subscribe to OHLC updates."""
        subscription_id = self._generate_subscription_id()
        
        subscription = Subscription(
            subscription_id=subscription_id,
            channel="ohlc",
            pairs=pairs,
            subscription_type=SubscriptionType.OHLC,
            is_private=False,
            interval=interval
        )
        
        self.subscriptions[subscription_id] = subscription
        
        # Send subscription if connected
        if self.state == WebSocketState.CONNECTED and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_internal(subscription),
                self.loop
            )
        
        log_info(f"Subscribed to OHLC for pairs: {pairs} (interval: {interval})")
        return subscription_id
    
    def subscribe_trades(self, pairs: List[str]) -> str:
        """Subscribe to trade updates."""
        subscription_id = self._generate_subscription_id()
        
        subscription = Subscription(
            subscription_id=subscription_id,
            channel="trade",
            pairs=pairs,
            subscription_type=SubscriptionType.TRADE,
            is_private=False
        )
        
        self.subscriptions[subscription_id] = subscription
        
        # Send subscription if connected
        if self.state == WebSocketState.CONNECTED and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_internal(subscription),
                self.loop
            )
        
        log_info(f"Subscribed to trades for pairs: {pairs}")
        return subscription_id
    
    def subscribe_orderbook(self, pairs: List[str], depth: int = 10) -> str:
        """Subscribe to order book updates."""
        subscription_id = self._generate_subscription_id()
        
        subscription = Subscription(
            subscription_id=subscription_id,
            channel="book",
            pairs=pairs,
            subscription_type=SubscriptionType.BOOK,
            is_private=False,
            depth=depth
        )
        
        self.subscriptions[subscription_id] = subscription
        
        # Send subscription if connected
        if self.state == WebSocketState.CONNECTED and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_internal(subscription),
                self.loop
            )
        
        log_info(f"Subscribed to order book for pairs: {pairs} (depth: {depth})")
        return subscription_id
    
    def subscribe_spread(self, pairs: List[str]) -> str:
        """Subscribe to spread updates."""
        subscription_id = self._generate_subscription_id()
        
        subscription = Subscription(
            subscription_id=subscription_id,
            channel="spread",
            pairs=pairs,
            subscription_type=SubscriptionType.SPREAD,
            is_private=False
        )
        
        self.subscriptions[subscription_id] = subscription
        
        # Send subscription if connected
        if self.state == WebSocketState.CONNECTED and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_internal(subscription),
                self.loop
            )
        
        log_info(f"Subscribed to spread for pairs: {pairs}")
        return subscription_id
    
    def subscribe_orders(self) -> str:
        """Subscribe to private order updates."""
        subscription_id = self._generate_subscription_id()
        
        subscription = Subscription(
            subscription_id=subscription_id,
            channel="openOrders",
            pairs=[],  # Private channels don't use pairs
            subscription_type=SubscriptionType.ORDERS,
            is_private=True
        )
        
        self.subscriptions[subscription_id] = subscription
        
        # Connect to private WebSocket if not already connected
        if self.state == WebSocketState.CONNECTED and self.loop:
            if not self.private_ws:
                asyncio.run_coroutine_threadsafe(
                    self._connect_private(),
                    self.loop
                )
            
            asyncio.run_coroutine_threadsafe(
                self._subscribe_internal(subscription),
                self.loop
            )
        
        log_info("Subscribed to private order updates")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a channel."""
        try:
            if subscription_id not in self.subscriptions:
                log_warning(f"Subscription {subscription_id} not found")
                return False
            
            subscription = self.subscriptions[subscription_id]
            
            # Send unsubscribe message
            if self.state == WebSocketState.CONNECTED and self.loop:
                message = {
                    "event": "unsubscribe",
                    "pair": subscription.pairs,
                    "subscription": {"name": subscription.channel}
                }
                
                # Add optional parameters
                if subscription.depth is not None:
                    message["subscription"]["depth"] = subscription.depth
                
                if subscription.interval is not None:
                    message["subscription"]["interval"] = subscription.interval
                
                asyncio.run_coroutine_threadsafe(
                    self._send_message(message, subscription.is_private),
                    self.loop
                )
            
            # Remove subscription
            del self.subscriptions[subscription_id]
            
            log_info(f"Unsubscribed from {subscription.channel}")
            return True
        
        except Exception as e:
            log_error(f"Error unsubscribing: {str(e)}")
            return False
    
    def get_connection_state(self) -> WebSocketState:
        """Get current connection state."""
        return self.state
    
    def get_subscriptions(self) -> Dict[str, Subscription]:
        """Get all active subscriptions."""
        return self.subscriptions.copy()
    
    def get_queue_size(self) -> int:
        """Get current message queue size."""
        return self.message_queue.qsize()
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.state == WebSocketState.CONNECTED
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket client statistics."""
        return {
            "state": self.state.value,
            "reconnect_attempts": self.reconnect_attempts,
            "active_subscriptions": len(self.subscriptions),
            "queue_size": self.message_queue.qsize(),
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "last_pong": self.last_pong.isoformat() if self.last_pong else None,
            "public_connected": self.public_ws is not None,
            "private_connected": self.private_ws is not None
        }


class DefaultWebSocketCallbackHandler(WebSocketCallbackHandler):
    """Default callback handler with basic logging."""
    
    def on_ticker(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle ticker updates."""
        log_info(f"Ticker update for {pair}: {data}")
    
    def on_ohlc(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle OHLC updates."""
        log_info(f"OHLC update for {pair}: {data}")
    
    def on_trade(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle trade updates."""
        log_info(f"Trade update for {pair}: {data}")
    
    def on_book(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle order book updates."""
        log_info(f"Order book update for {pair}: {data}")
    
    def on_spread(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle spread updates."""
        log_info(f"Spread update for {pair}: {data}")
    
    def on_orders(self, data: Dict[str, Any]) -> None:
        """Handle private order updates."""
        log_info(f"Order update: {data}")
    
    def on_connection_status(self, status: WebSocketState) -> None:
        """Handle connection status changes."""
        log_info(f"WebSocket connection status: {status.value}")
    
    def on_error(self, error: Exception) -> None:
        """Handle errors."""
        log_error(f"WebSocket error: {str(error)}")
    
    def on_subscription_status(self, subscription_id: str, status: str, error: Optional[str] = None) -> None:
        """Handle subscription status updates."""
        if error:
            log_error(f"Subscription {subscription_id} error: {error}")
        else:
            log_info(f"Subscription {subscription_id} status: {status}")


# Utility functions for message parsing
def parse_ticker_data(data: Dict[str, Any]) -> Dict[str, float]:
    """Parse ticker data into standardized format."""
    try:
        return {
            "ask_price": float(data.get("a", [0])[0]),
            "ask_volume": float(data.get("a", [0, 0])[1]),
            "bid_price": float(data.get("b", [0])[0]),
            "bid_volume": float(data.get("b", [0, 0])[1]),
            "last_price": float(data.get("c", [0])[0]),
            "last_volume": float(data.get("c", [0, 0])[1]),
            "volume_today": float(data.get("v", [0])[0]),
            "volume_24h": float(data.get("v", [0, 0])[1]),
            "vwap_today": float(data.get("p", [0])[0]),
            "vwap_24h": float(data.get("p", [0, 0])[1]),
            "trades_today": int(data.get("t", [0])[0]),
            "trades_24h": int(data.get("t", [0, 0])[1]),
            "low_today": float(data.get("l", [0])[0]),
            "low_24h": float(data.get("l", [0, 0])[1]),
            "high_today": float(data.get("h", [0])[0]),
            "high_24h": float(data.get("h", [0, 0])[1]),
            "open_today": float(data.get("o", [0])[0]),
            "open_24h": float(data.get("o", [0, 0])[1])
        }
    except (ValueError, IndexError, KeyError) as e:
        log_error(f"Error parsing ticker data: {str(e)}")
        return {}


def parse_ohlc_data(data: List[Any]) -> Dict[str, Any]:
    """Parse OHLC data into standardized format."""
    try:
        if len(data) < 8:
            return {}
        
        return {
            "time": float(data[0]),
            "end_time": float(data[1]),
            "open": float(data[2]),
            "high": float(data[3]),
            "low": float(data[4]),
            "close": float(data[5]),
            "vwap": float(data[6]),
            "volume": float(data[7]),
            "count": int(data[8]) if len(data) > 8 else 0
        }
    except (ValueError, IndexError) as e:
        log_error(f"Error parsing OHLC data: {str(e)}")
        return {}


def parse_trade_data(trades: List[List[Any]]) -> List[Dict[str, Any]]:
    """Parse trade data into standardized format."""
    parsed_trades = []
    
    for trade in trades:
        try:
            if len(trade) < 6:
                continue
            
            parsed_trades.append({
                "price": float(trade[0]),
                "volume": float(trade[1]),
                "time": float(trade[2]),
                "side": "buy" if trade[3] == "b" else "sell",
                "order_type": "market" if trade[4] == "m" else "limit",
                "misc": trade[5] if len(trade) > 5 else ""
            })
        except (ValueError, IndexError) as e:
            log_error(f"Error parsing trade data: {str(e)}")
            continue
    
    return parsed_trades


def parse_book_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse order book data into standardized format."""
    try:
        parsed = {}
        
        if "as" in data:  # asks
            parsed["asks"] = []
            for ask in data["as"]:
                if len(ask) >= 3:
                    parsed["asks"].append({
                        "price": float(ask[0]),
                        "volume": float(ask[1]),
                        "timestamp": float(ask[2])
                    })
        
        if "bs" in data:  # bids
            parsed["bids"] = []
            for bid in data["bs"]:
                if len(bid) >= 3:
                    parsed["bids"].append({
                        "price": float(bid[0]),
                        "volume": float(bid[1]),
                        "timestamp": float(bid[2])
                    })
        
        if "a" in data:  # ask updates
            parsed["ask_updates"] = []
            for ask in data["a"]:
                if len(ask) >= 3:
                    parsed["ask_updates"].append({
                        "price": float(ask[0]),
                        "volume": float(ask[1]),
                        "timestamp": float(ask[2])
                    })
        
        if "b" in data:  # bid updates
            parsed["bid_updates"] = []
            for bid in data["b"]:
                if len(bid) >= 3:
                    parsed["bid_updates"].append({
                        "price": float(bid[0]),
                        "volume": float(bid[1]),
                        "timestamp": float(bid[2])
                    })
        
        return parsed
    except (ValueError, KeyError) as e:
        log_error(f"Error parsing book data: {str(e)}")
        return {}


# Enhanced callback handler with additional functionality
class EnhancedWebSocketCallbackHandler(WebSocketCallbackHandler):
    """Enhanced callback handler with additional features for trading integration."""
    
    def __init__(self, data_manager=None, strategy_engine=None, risk_manager=None):
        """Initialize enhanced callback handler."""
        self.data_manager = data_manager
        self.strategy_engine = strategy_engine
        self.risk_manager = risk_manager
        self.last_prices = {}
        self.price_changes = {}
        
    def on_ticker(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle ticker updates with enhanced processing."""
        try:
            parsed_data = parse_ticker_data(data)
            
            # Track price changes
            if pair in self.last_prices:
                self.price_changes[pair] = parsed_data.get('last_price', 0) - self.last_prices[pair]
            
            self.last_prices[pair] = parsed_data.get('last_price', 0)
            
            # Update data manager if available
            if self.data_manager:
                self.data_manager.update_ticker_data(pair, parsed_data)
            
            # Trigger strategy calculations if available
            if self.strategy_engine:
                self.strategy_engine.process_ticker_update(pair, parsed_data)
                
            log_info(f"Ticker update for {pair}: ${parsed_data.get('last_price', 0):.2f}")
            
        except Exception as e:
            log_error(f"Error processing ticker data for {pair}: {str(e)}")
    
    def on_trade(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle trade updates with enhanced processing."""
        try:
            parsed_trades = parse_trade_data(data)
            
            # Update data manager if available
            if self.data_manager:
                self.data_manager.update_trade_data(pair, parsed_trades)
            
            # Process trades for strategy signals
            if self.strategy_engine:
                for trade in parsed_trades:
                    self.strategy_engine.process_trade_update(pair, trade)
            
            log_info(f"Trade update for {pair}: {len(parsed_trades)} trades")
            
        except Exception as e:
            log_error(f"Error processing trade data for {pair}: {str(e)}")
    
    def on_book(self, pair: str, data: Dict[str, Any]) -> None:
        """Handle order book updates with enhanced processing."""
        try:
            parsed_book = parse_book_data(data)
            
            # Update data manager if available
            if self.data_manager:
                self.data_manager.update_orderbook_data(pair, parsed_book)
            
            # Calculate spread and liquidity metrics
            if parsed_book.get('asks') and parsed_book.get('bids'):
                best_ask = min(parsed_book['asks'], key=lambda x: x['price'])
                best_bid = max(parsed_book['bids'], key=lambda x: x['price'])
                spread = best_ask['price'] - best_bid['price']
                
                # Update strategy engine with spread info
                if self.strategy_engine:
                    self.strategy_engine.process_spread_update(pair, spread, best_bid, best_ask)
            
            log_info(f"Order book update for {pair}: {len(parsed_book.get('asks', []))} asks, {len(parsed_book.get('bids', []))} bids")
            
        except Exception as e:
            log_error(f"Error processing order book data for {pair}: {str(e)}")
    
    def on_orders(self, data: Dict[str, Any]) -> None:
        """Handle private order updates with enhanced processing."""
        try:
            # Update risk manager with order status changes
            if self.risk_manager:
                self.risk_manager.process_order_update(data)
            
            # Update data manager with order information
            if self.data_manager:
                self.data_manager.update_order_data(data)
            
            log_info(f"Order update received: {len(data) if isinstance(data, list) else 1} orders")
            
        except Exception as e:
            log_error(f"Error processing order data: {str(e)}")
    
    def on_connection_status(self, status: WebSocketState) -> None:
        """Handle connection status changes with enhanced logging."""
        log_info(f"WebSocket connection status changed to: {status.value}")
        
        # Notify components of connection status
        if self.data_manager:
            self.data_manager.handle_connection_status(status)
        
        if self.strategy_engine:
            self.strategy_engine.handle_connection_status(status)
        
        if self.risk_manager:
            self.risk_manager.handle_connection_status(status)
    
    def on_error(self, error: Exception) -> None:
        """Handle errors with enhanced error processing."""
        log_error(f"WebSocket error: {str(error)}")
        
        # Notify components of errors
        if self.risk_manager:
            self.risk_manager.handle_websocket_error(error)
    
    def get_price_changes(self) -> Dict[str, float]:
        """Get recent price changes for all pairs."""
        return self.price_changes.copy()
    
    def get_last_prices(self) -> Dict[str, float]:
        """Get last known prices for all pairs."""
        return self.last_prices.copy()


# WebSocket client factory for easier instantiation
class WebSocketClientFactory:
    """Factory for creating WebSocket clients with different configurations."""
    
    @staticmethod
    def create_basic_client(credentials: KrakenCredentials) -> KrakenWebSocketClient:
        """Create a basic WebSocket client with default configuration."""
        handler = DefaultWebSocketCallbackHandler()
        config = WebSocketConfig()
        return KrakenWebSocketClient(credentials, handler, config)
    
    @staticmethod
    def create_enhanced_client(credentials: KrakenCredentials, 
                             data_manager=None, 
                             strategy_engine=None, 
                             risk_manager=None) -> KrakenWebSocketClient:
        """Create an enhanced WebSocket client with trading integration."""
        handler = EnhancedWebSocketCallbackHandler(data_manager, strategy_engine, risk_manager)
        config = WebSocketConfig(
            ping_interval=20,  # More frequent pings for trading
            max_reconnect_attempts=20,  # More reconnect attempts
            message_queue_size=2000  # Larger queue for high-frequency trading
        )
        return KrakenWebSocketClient(credentials, handler, config)
    
    @staticmethod
    def create_high_frequency_client(credentials: KrakenCredentials,
                                   data_manager=None,
                                   strategy_engine=None,
                                   risk_manager=None) -> KrakenWebSocketClient:
        """Create a WebSocket client optimized for high-frequency trading."""
        handler = EnhancedWebSocketCallbackHandler(data_manager, strategy_engine, risk_manager)
        config = WebSocketConfig(
            ping_interval=10,  # Very frequent pings
            ping_timeout=5,    # Quick timeout
            max_reconnect_attempts=50,  # Many reconnect attempts
            reconnect_delay=1,  # Quick reconnection
            max_reconnect_delay=30,  # Lower max delay
            backoff_multiplier=1.2,  # Gentler backoff
            message_queue_size=5000,  # Large queue
            heartbeat_interval=30  # Frequent health checks
        )
        return KrakenWebSocketClient(credentials, handler, config)


# Connection health monitor
class WebSocketHealthMonitor:
    """Monitor WebSocket connection health and performance."""
    
    def __init__(self, ws_client: KrakenWebSocketClient):
        self.ws_client = ws_client
        self.start_time = datetime.now()
        self.message_count = 0
        self.error_count = 0
        self.reconnect_count = 0
        self.last_message_time = None
        
    def record_message(self):
        """Record a message received."""
        self.message_count += 1
        self.last_message_time = datetime.now()
    
    def record_error(self):
        """Record an error."""
        self.error_count += 1
    
    def record_reconnect(self):
        """Record a reconnection."""
        self.reconnect_count += 1
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get health metrics."""
        now = datetime.now()
        uptime = now - self.start_time
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "message_count": self.message_count,
            "error_count": self.error_count,
            "reconnect_count": self.reconnect_count,
            "messages_per_minute": self.message_count / max(uptime.total_seconds() / 60, 1),
            "error_rate": self.error_count / max(self.message_count, 1),
            "last_message_age_seconds": (now - self.last_message_time).total_seconds() if self.last_message_time else None,
            "connection_state": self.ws_client.get_connection_state().value,
            "queue_size": self.ws_client.get_queue_size(),
            "active_subscriptions": len(self.ws_client.get_subscriptions())
        }
    
    def is_healthy(self) -> bool:
        """Check if the connection is healthy."""
        metrics = self.get_health_metrics()
        
        # Check if we're connected
        if metrics["connection_state"] != "connected":
            return False
        
        # Check if we've received messages recently (within 2 minutes)
        if metrics["last_message_age_seconds"] and metrics["last_message_age_seconds"] > 120:
            return False
        
        # Check error rate (should be less than 10%)
        if metrics["error_rate"] > 0.1:
            return False
        
        # Check queue size (shouldn't be too full)
        if metrics["queue_size"] > self.ws_client.config.message_queue_size * 0.8:
            return False
        
        return True


# WebSocket message validator
class WebSocketMessageValidator:
    """Validate WebSocket messages for data integrity."""
    
    @staticmethod
    def validate_ticker_data(data: Dict[str, Any]) -> bool:
        """Validate ticker data structure."""
        required_fields = ['c']  # At least last price should be present
        return all(field in data for field in required_fields)
    
    @staticmethod
    def validate_trade_data(data: List[List[Any]]) -> bool:
        """Validate trade data structure."""
        if not isinstance(data, list):
            return False
        
        for trade in data:
            if not isinstance(trade, list) or len(trade) < 6:
                return False
        
        return True
    
    @staticmethod
    def validate_book_data(data: Dict[str, Any]) -> bool:
        """Validate order book data structure."""
        if not isinstance(data, dict):
            return False
        
        # Should have at least asks or bids
        return 'as' in data or 'bs' in data or 'a' in data or 'b' in data
    
    @staticmethod
    def validate_ohlc_data(data: List[Any]) -> bool:
        """Validate OHLC data structure."""
        return isinstance(data, list) and len(data) >= 9


# WebSocket performance optimizer
class WebSocketPerformanceOptimizer:
    """Optimize WebSocket performance based on usage patterns."""
    
    def __init__(self, ws_client: KrakenWebSocketClient):
        self.ws_client = ws_client
        self.message_rates = {}
        self.last_optimization = datetime.now()
        
    def record_message_rate(self, channel: str):
        """Record message rate for a channel."""
        now = datetime.now()
        if channel not in self.message_rates:
            self.message_rates[channel] = []
        
        self.message_rates[channel].append(now)
        
        # Keep only last minute of data
        cutoff = now - timedelta(minutes=1)
        self.message_rates[channel] = [
            timestamp for timestamp in self.message_rates[channel] 
            if timestamp > cutoff
        ]
    
    def get_message_rate(self, channel: str) -> float:
        """Get messages per second for a channel."""
        if channel not in self.message_rates:
            return 0.0
        
        return len(self.message_rates[channel]) / 60.0  # per second
    
    def optimize_config(self) -> WebSocketConfig:
        """Optimize configuration based on usage patterns."""
        now = datetime.now()
        
        # Only optimize every 5 minutes
        if (now - self.last_optimization).total_seconds() < 300:
            return self.ws_client.config
        
        self.last_optimization = now
        
        # Calculate total message rate
        total_rate = sum(self.get_message_rate(channel) for channel in self.message_rates)
        
        # Adjust queue size based on message rate
        if total_rate > 10:  # High frequency
            queue_size = min(5000, int(total_rate * 100))
        elif total_rate > 1:  # Medium frequency
            queue_size = min(2000, int(total_rate * 200))
        else:  # Low frequency
            queue_size = 1000
        
        # Adjust ping interval based on activity
        if total_rate > 5:
            ping_interval = 10  # More frequent pings for high activity
        elif total_rate > 1:
            ping_interval = 20
        else:
            ping_interval = 30
        
        # Create optimized config
        optimized_config = WebSocketConfig(
            public_url=self.ws_client.config.public_url,
            private_url=self.ws_client.config.private_url,
            ping_interval=ping_interval,
            ping_timeout=self.ws_client.config.ping_timeout,
            max_reconnect_attempts=self.ws_client.config.max_reconnect_attempts,
            reconnect_delay=self.ws_client.config.reconnect_delay,
            max_reconnect_delay=self.ws_client.config.max_reconnect_delay,
            backoff_multiplier=self.ws_client.config.backoff_multiplier,
            message_queue_size=queue_size,
            heartbeat_interval=self.ws_client.config.heartbeat_interval
        )
        
        log_info(f"Optimized WebSocket config: queue_size={queue_size}, ping_interval={ping_interval}")
        return optimized_config


# WebSocket connection pool for multiple pairs
class WebSocketConnectionPool:
    """Manage multiple WebSocket connections for different trading pairs."""
    
    def __init__(self, credentials: KrakenCredentials, max_connections: int = 5):
        self.credentials = credentials
        self.max_connections = max_connections
        self.connections = {}
        self.pair_assignments = {}
        
    def get_connection_for_pair(self, pair: str) -> KrakenWebSocketClient:
        """Get or create a connection for a trading pair."""
        # Check if pair is already assigned
        if pair in self.pair_assignments:
            return self.pair_assignments[pair]
        
        # Find connection with least pairs
        if self.connections:
            connection_loads = {
                conn_id: len([p for p, c in self.pair_assignments.items() if c == conn])
                for conn_id, conn in self.connections.items()
            }
            least_loaded_id = min(connection_loads, key=connection_loads.get)
            
            if connection_loads[least_loaded_id] < 10:  # Max 10 pairs per connection
                connection = self.connections[least_loaded_id]
                self.pair_assignments[pair] = connection
                return connection
        
        # Create new connection if under limit
        if len(self.connections) < self.max_connections:
            conn_id = f"conn_{len(self.connections) + 1}"
            connection = WebSocketClientFactory.create_enhanced_client(self.credentials)
            self.connections[conn_id] = connection
            self.pair_assignments[pair] = connection
            return connection
        
        # Use first connection as fallback
        connection = list(self.connections.values())[0]
        self.pair_assignments[pair] = connection
        return connection
    
    def connect_all(self) -> bool:
        """Connect all connections in the pool."""
        success = True
        for connection in self.connections.values():
            if not connection.connect():
                success = False
        return success
    
    def disconnect_all(self):
        """Disconnect all connections in the pool."""
        for connection in self.connections.values():
            connection.disconnect()
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics for the connection pool."""
        return {
            "total_connections": len(self.connections),
            "total_pairs": len(self.pair_assignments),
            "connection_states": {
                conn_id: conn.get_connection_state().value
                for conn_id, conn in self.connections.items()
            },
            "pair_distribution": {
                conn_id: len([p for p, c in self.pair_assignments.items() if c == conn])
                for conn_id, conn in self.connections.items()
            }
        }