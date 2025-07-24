"""
Coinbase Advanced Trade WebSocket client for real-time market data.
Handles WebSocket connections, real-time price updates, and order book streaming.
"""
import json
import time
import threading
import websocket
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import ssl
from queue import Queue, Empty

from bot.coinbase_client import CoinbaseCredentials
from bot.utils import log_error, log_info, log_warning


@dataclass
class WebSocketMessage:
    """Represents a WebSocket message from Coinbase."""
    type: str
    product_id: str
    timestamp: datetime
    data: Dict[str, Any]


class CoinbaseWebSocketClient:
    """
    WebSocket client for Coinbase Advanced Trade real-time feeds.
    Supports ticker, level2 (order book), and matches channels.
    """
    
    def __init__(self, credentials: CoinbaseCredentials):
        """
        Initialize WebSocket client.
        
        Args:
            credentials: Coinbase API credentials
        """
        self.credentials = credentials
        self.ws_url = "wss://ws-feed.exchange.coinbase.com" if not credentials.sandbox else "wss://ws-feed-public.sandbox.exchange.coinbase.com"
        
        # WebSocket connection
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # seconds
        
        # Threading
        self.ws_thread = None
        self.heartbeat_thread = None
        self.stop_event = threading.Event()
        
        # Message handling
        self.message_queue = Queue()
        self.message_handlers = {}
        self.subscriptions = {}
        
        # Connection management
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 60  # seconds
        
        # Statistics
        self.messages_received = 0
        self.last_message_time = time.time()
        
    def connect(self) -> bool:
        """
        Establish WebSocket connection to Coinbase.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            log_info("Connecting to Coinbase WebSocket...")
            
            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start WebSocket in separate thread
            self.ws_thread = threading.Thread(
                target=self.ws.run_forever,
                kwargs={'sslopt': {"cert_reqs": ssl.CERT_NONE}}
            )
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Wait for connection to establish
            timeout = 10
            start_time = time.time()
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if self.connected:
                log_info("WebSocket connection established")
                self._start_heartbeat()
                return True
            else:
                log_error("WebSocket connection timeout")
                return False
                
        except Exception as e:
            log_error(f"Failed to connect WebSocket: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from WebSocket and cleanup resources."""
        log_info("Disconnecting WebSocket...")
        
        # Set stop event
        self.stop_event.set()
        
        # Close WebSocket connection
        if self.ws:
            self.ws.close()
        
        # Wait for threads to finish
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
        
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=5)
        
        self.connected = False
        log_info("WebSocket disconnected")
    
    def subscribe_ticker(self, product_ids: List[str], callback: Optional[Callable] = None) -> bool:
        """
        Subscribe to ticker channel for real-time price updates.
        
        Args:
            product_ids: List of product IDs to subscribe to (e.g., ['BTC-USD'])
            callback: Optional callback function for ticker updates
            
        Returns:
            True if subscription successful, False otherwise
        """
        return self._subscribe("ticker", product_ids, callback)
    
    def subscribe_level2(self, product_ids: List[str], callback: Optional[Callable] = None) -> bool:
        """
        Subscribe to level2 channel for order book updates.
        
        Args:
            product_ids: List of product IDs to subscribe to
            callback: Optional callback function for order book updates
            
        Returns:
            True if subscription successful, False otherwise
        """
        return self._subscribe("level2", product_ids, callback)
    
    def subscribe_matches(self, product_ids: List[str], callback: Optional[Callable] = None) -> bool:
        """
        Subscribe to matches channel for trade data.
        
        Args:
            product_ids: List of product IDs to subscribe to
            callback: Optional callback function for trade updates
            
        Returns:
            True if subscription successful, False otherwise
        """
        return self._subscribe("matches", product_ids, callback)
    
    def unsubscribe(self, channel: str, product_ids: List[str]) -> bool:
        """
        Unsubscribe from a channel.
        
        Args:
            channel: Channel name (ticker, level2, matches)
            product_ids: List of product IDs to unsubscribe from
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        if not self.connected:
            log_warning("Cannot unsubscribe: WebSocket not connected")
            return False
        
        try:
            message = {
                "type": "unsubscribe",
                "channels": [
                    {
                        "name": channel,
                        "product_ids": product_ids
                    }
                ]
            }
            
            self.ws.send(json.dumps(message))
            
            # Remove from subscriptions
            key = f"{channel}:{','.join(product_ids)}"
            if key in self.subscriptions:
                del self.subscriptions[key]
            
            log_info(f"Unsubscribed from {channel} for {product_ids}")
            return True
            
        except Exception as e:
            log_error(f"Failed to unsubscribe from {channel}: {str(e)}")
            return False
    
    def get_latest_ticker(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest ticker data for a product.
        
        Args:
            product_id: Product ID to get ticker for
            
        Returns:
            Latest ticker data or None if not available
        """
        # Check message queue for latest ticker
        latest_ticker = None
        temp_messages = []
        
        try:
            while True:
                try:
                    message = self.message_queue.get_nowait()
                    temp_messages.append(message)
                    
                    if (message.type == "ticker" and 
                        message.product_id == product_id):
                        latest_ticker = message.data
                        
                except Empty:
                    break
            
            # Put messages back in queue
            for msg in temp_messages:
                self.message_queue.put(msg)
            
            return latest_ticker
            
        except Exception as e:
            log_error(f"Error getting latest ticker: {str(e)}")
            return None
    
    def is_connected(self) -> bool:
        """
        Check if WebSocket is connected and healthy.
        
        Returns:
            True if connected and healthy, False otherwise
        """
        if not self.connected:
            return False
        
        # Check if we've received messages recently
        time_since_last_message = time.time() - self.last_message_time
        if time_since_last_message > self.connection_timeout:
            log_warning(f"No messages received for {time_since_last_message:.1f} seconds")
            return False
        
        return True
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket connection statistics.
        
        Returns:
            Dictionary containing connection statistics
        """
        return {
            "connected": self.connected,
            "messages_received": self.messages_received,
            "last_message_time": self.last_message_time,
            "reconnect_attempts": self.reconnect_attempts,
            "subscriptions": list(self.subscriptions.keys()),
            "queue_size": self.message_queue.qsize()
        }
    
    def _subscribe(self, channel: str, product_ids: List[str], callback: Optional[Callable] = None) -> bool:
        """
        Internal method to subscribe to a channel.
        
        Args:
            channel: Channel name
            product_ids: List of product IDs
            callback: Optional callback function
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self.connected:
            log_warning(f"Cannot subscribe to {channel}: WebSocket not connected")
            return False
        
        try:
            message = {
                "type": "subscribe",
                "channels": [
                    {
                        "name": channel,
                        "product_ids": product_ids
                    }
                ]
            }
            
            self.ws.send(json.dumps(message))
            
            # Store subscription
            key = f"{channel}:{','.join(product_ids)}"
            self.subscriptions[key] = {
                "channel": channel,
                "product_ids": product_ids,
                "callback": callback
            }
            
            log_info(f"Subscribed to {channel} for {product_ids}")
            return True
            
        except Exception as e:
            log_error(f"Failed to subscribe to {channel}: {str(e)}")
            return False
    
    def _on_open(self, ws) -> None:
        """Handle WebSocket connection open."""
        log_info("WebSocket connection opened")
        self.connected = True
        self.reconnect_attempts = 0
        self.last_heartbeat = time.time()
    
    def _on_message(self, ws, message: str) -> None:
        """
        Handle incoming WebSocket messages.
        
        Args:
            ws: WebSocket instance
            message: Raw message string
        """
        try:
            data = json.loads(message)
            self.messages_received += 1
            self.last_message_time = time.time()
            
            # Handle different message types
            msg_type = data.get("type", "")
            
            if msg_type == "subscriptions":
                log_info(f"Subscription confirmation: {data}")
                return
            
            if msg_type == "error":
                log_error(f"WebSocket error message: {data}")
                return
            
            # Create WebSocket message object
            ws_message = WebSocketMessage(
                type=msg_type,
                product_id=data.get("product_id", ""),
                timestamp=datetime.now(timezone.utc),
                data=data
            )
            
            # Add to message queue
            self.message_queue.put(ws_message)
            
            # Call registered handlers
            self._handle_message(ws_message)
            
        except json.JSONDecodeError as e:
            log_error(f"Failed to parse WebSocket message: {str(e)}")
        except Exception as e:
            log_error(f"Error handling WebSocket message: {str(e)}")
    
    def _on_error(self, ws, error) -> None:
        """
        Handle WebSocket errors.
        
        Args:
            ws: WebSocket instance
            error: Error object
        """
        log_error(f"WebSocket error: {str(error)}")
        
        # Attempt reconnection if not intentionally disconnected
        if not self.stop_event.is_set():
            self._attempt_reconnect()
    
    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """
        Handle WebSocket connection close.
        
        Args:
            ws: WebSocket instance
            close_status_code: Close status code
            close_msg: Close message
        """
        log_info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.connected = False
        
        # Attempt reconnection if not intentionally disconnected
        if not self.stop_event.is_set():
            self._attempt_reconnect()
    
    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect WebSocket with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            log_error("Maximum reconnection attempts reached")
            return
        
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)
        
        log_info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay} seconds")
        
        # Wait before reconnecting
        if not self.stop_event.wait(delay):
            # Store current subscriptions
            current_subscriptions = dict(self.subscriptions)
            
            # Reconnect
            if self.connect():
                # Re-subscribe to previous channels
                for sub_key, sub_info in current_subscriptions.items():
                    self._subscribe(
                        sub_info["channel"],
                        sub_info["product_ids"],
                        sub_info["callback"]
                    )
                log_info("Successfully reconnected and re-subscribed")
            else:
                log_error("Reconnection failed")
    
    def _handle_message(self, message: WebSocketMessage) -> None:
        """
        Handle processed WebSocket messages by calling appropriate callbacks.
        
        Args:
            message: Processed WebSocket message
        """
        try:
            # Find matching subscription callback
            for sub_key, sub_info in self.subscriptions.items():
                if (sub_info["channel"] == message.type and
                    message.product_id in sub_info["product_ids"] and
                    sub_info["callback"]):
                    
                    # Call the callback
                    sub_info["callback"](message)
                    
        except Exception as e:
            log_error(f"Error in message handler callback: {str(e)}")
    
    def _start_heartbeat(self) -> None:
        """Start heartbeat thread to monitor connection health."""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            return
        
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
    
    def _heartbeat_loop(self) -> None:
        """Heartbeat loop to monitor connection and send pings."""
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # Check if connection is still alive
                if self.connected:
                    time_since_last_message = current_time - self.last_message_time
                    
                    if time_since_last_message > self.connection_timeout:
                        log_warning("Connection appears dead, attempting reconnection")
                        self.connected = False
                        self._attempt_reconnect()
                        continue
                
                # Wait for next heartbeat
                self.stop_event.wait(self.heartbeat_interval)
                
            except Exception as e:
                log_error(f"Error in heartbeat loop: {str(e)}")
                self.stop_event.wait(5)


class CoinbaseWebSocketManager:
    """
    High-level manager for Coinbase WebSocket connections.
    Handles multiple subscriptions and provides fallback to REST API.
    """
    
    def __init__(self, credentials: CoinbaseCredentials, rest_client=None):
        """
        Initialize WebSocket manager.
        
        Args:
            credentials: Coinbase API credentials
            rest_client: Optional REST client for fallback
        """
        self.credentials = credentials
        self.rest_client = rest_client
        self.ws_client = None
        
        # Price cache
        self.price_cache = {}
        self.cache_timestamps = {}
        self.cache_ttl = 60  # seconds
        
        # Fallback settings
        self.use_fallback = True
        self.fallback_active = False
        
        # Connection monitoring
        self.connection_check_interval = 30  # seconds
        self.last_connection_check = time.time()
    
    def start(self, product_ids: List[str]) -> bool:
        """
        Start WebSocket connection and subscribe to ticker updates.
        
        Args:
            product_ids: List of product IDs to subscribe to
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Create WebSocket client
            self.ws_client = CoinbaseWebSocketClient(self.credentials)
            
            # Connect
            if not self.ws_client.connect():
                log_error("Failed to connect WebSocket")
                return self._activate_fallback()
            
            # Subscribe to ticker updates
            if not self.ws_client.subscribe_ticker(product_ids, self._on_ticker_update):
                log_error("Failed to subscribe to ticker updates")
                return self._activate_fallback()
            
            log_info(f"WebSocket started successfully for {product_ids}")
            self.fallback_active = False
            return True
            
        except Exception as e:
            log_error(f"Failed to start WebSocket: {str(e)}")
            return self._activate_fallback()
    
    def stop(self) -> None:
        """Stop WebSocket connection."""
        if self.ws_client:
            self.ws_client.disconnect()
            self.ws_client = None
        
        log_info("WebSocket manager stopped")
    
    def get_real_time_price(self, product_id: str) -> Optional[float]:
        """
        Get real-time price for a product.
        Falls back to REST API if WebSocket is not available.
        
        Args:
            product_id: Product ID to get price for
            
        Returns:
            Current price or None if not available
        """
        # Check WebSocket first
        if self.ws_client and self.ws_client.is_connected() and not self.fallback_active:
            ticker = self.ws_client.get_latest_ticker(product_id)
            if ticker and "price" in ticker:
                price = float(ticker["price"])
                self._update_price_cache(product_id, price)
                return price
        
        # Check cache
        cached_price = self._get_cached_price(product_id)
        if cached_price is not None:
            return cached_price
        
        # Fallback to REST API
        if self.use_fallback and self.rest_client:
            try:
                price = self.rest_client.get_latest_price(product_id)
                self._update_price_cache(product_id, price)
                return price
            except Exception as e:
                log_error(f"REST API fallback failed: {str(e)}")
        
        return None
    
    def is_websocket_healthy(self) -> bool:
        """
        Check if WebSocket connection is healthy.
        
        Returns:
            True if WebSocket is connected and healthy, False otherwise
        """
        if not self.ws_client:
            return False
        
        return self.ws_client.is_connected()
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get detailed connection status.
        
        Returns:
            Dictionary containing connection status information
        """
        status = {
            "websocket_connected": False,
            "fallback_active": self.fallback_active,
            "cache_size": len(self.price_cache),
            "websocket_stats": None
        }
        
        if self.ws_client:
            status["websocket_connected"] = self.ws_client.is_connected()
            status["websocket_stats"] = self.ws_client.get_connection_stats()
        
        return status
    
    def _on_ticker_update(self, message: WebSocketMessage) -> None:
        """
        Handle ticker updates from WebSocket.
        
        Args:
            message: WebSocket message containing ticker data
        """
        try:
            data = message.data
            product_id = data.get("product_id")
            price = data.get("price")
            
            if product_id and price:
                price_float = float(price)
                self._update_price_cache(product_id, price_float)
                log_info(f"Real-time price update: {product_id} = ${price_float}")
                
        except Exception as e:
            log_error(f"Error processing ticker update: {str(e)}")
    
    def _update_price_cache(self, product_id: str, price: float) -> None:
        """
        Update price cache with new price data.
        
        Args:
            product_id: Product ID
            price: Current price
        """
        self.price_cache[product_id] = price
        self.cache_timestamps[product_id] = time.time()
    
    def _get_cached_price(self, product_id: str) -> Optional[float]:
        """
        Get price from cache if not expired.
        
        Args:
            product_id: Product ID
            
        Returns:
            Cached price or None if expired/not found
        """
        if product_id not in self.price_cache:
            return None
        
        # Check if cache is expired
        cache_age = time.time() - self.cache_timestamps.get(product_id, 0)
        if cache_age > self.cache_ttl:
            # Remove expired cache entry
            del self.price_cache[product_id]
            del self.cache_timestamps[product_id]
            return None
        
        return self.price_cache[product_id]
    
    def _activate_fallback(self) -> bool:
        """
        Activate fallback mode using REST API.
        
        Returns:
            True if fallback is available, False otherwise
        """
        if self.use_fallback and self.rest_client:
            log_info("Activating REST API fallback mode")
            self.fallback_active = True
            return True
        else:
            log_error("No fallback available")
            return False