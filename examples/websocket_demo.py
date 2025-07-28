#!/usr/bin/env python3
"""
Demo script showing enhanced Kraken WebSocket functionality.
This script demonstrates the new WebSocket features implemented for the Kraken migration.
"""
import os
import sys
import time
from datetime import datetime

# Add the bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from bot.kraken_websocket import (
    WebSocketClientFactory,
    EnhancedWebSocketCallbackHandler,
    WebSocketHealthMonitor,
    WebSocketPerformanceOptimizer,
    WebSocketConnectionPool,
    WebSocketState
)
from bot.kraken_client import KrakenCredentials


class DemoCallbackHandler(EnhancedWebSocketCallbackHandler):
    """Demo callback handler that prints received data."""
    
    def __init__(self):
        super().__init__()
        self.message_count = 0
    
    def on_ticker(self, pair: str, data: dict) -> None:
        """Handle ticker updates."""
        super().on_ticker(pair, data)
        self.message_count += 1
        
        # Parse ticker data for display
        try:
            last_price = float(data.get('c', ['0', '0'])[0])
            bid_price = float(data.get('b', ['0', '0', '0'])[0])
            ask_price = float(data.get('a', ['0', '0', '0'])[0])
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {pair} Ticker:")
            print(f"  Last: ${last_price:.2f}")
            print(f"  Bid:  ${bid_price:.2f}")
            print(f"  Ask:  ${ask_price:.2f}")
            print(f"  Spread: ${ask_price - bid_price:.2f}")
            print()
        except (ValueError, IndexError):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {pair} Ticker: {data}")
    
    def on_trade(self, pair: str, data: dict) -> None:
        """Handle trade updates."""
        super().on_trade(pair, data)
        self.message_count += 1
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {pair} Trades: {len(data)} trades")
    
    def on_book(self, pair: str, data: dict) -> None:
        """Handle order book updates."""
        super().on_book(pair, data)
        self.message_count += 1
        
        asks = len(data.get('as', []))
        bids = len(data.get('bs', []))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {pair} Order Book: {asks} asks, {bids} bids")
    
    def on_connection_status(self, status: WebSocketState) -> None:
        """Handle connection status changes."""
        super().on_connection_status(status)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection status: {status.value}")
    
    def on_error(self, error: Exception) -> None:
        """Handle errors."""
        super().on_error(error)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {str(error)}")


def demo_basic_websocket():
    """Demonstrate basic WebSocket functionality."""
    print("=== Basic WebSocket Demo ===")
    
    # Create credentials (using dummy values for demo)
    credentials = KrakenCredentials(
        api_key=os.getenv('KRAKEN_API_KEY', 'demo_key'),
        api_secret=os.getenv('KRAKEN_API_SECRET', 'ZGVtb19zZWNyZXQ=')  # base64 "demo_secret"
    )
    
    # Create basic client
    client = WebSocketClientFactory.create_basic_client(credentials)
    
    print(f"Created basic WebSocket client")
    print(f"Initial state: {client.get_connection_state()}")
    print(f"Queue size: {client.get_queue_size()}")
    print()
    
    # Note: In a real demo, you would connect to Kraken here
    # client.connect()
    # client.subscribe_ticker(['XBT/USD', 'ETH/USD'])
    
    print("Basic demo complete (connection skipped for demo purposes)")
    print()


def demo_enhanced_websocket():
    """Demonstrate enhanced WebSocket functionality."""
    print("=== Enhanced WebSocket Demo ===")
    
    # Create credentials
    credentials = KrakenCredentials(
        api_key=os.getenv('KRAKEN_API_KEY', 'demo_key'),
        api_secret=os.getenv('KRAKEN_API_SECRET', 'ZGVtb19zZWNyZXQ=')
    )
    
    # Create enhanced client
    client = WebSocketClientFactory.create_enhanced_client(credentials)
    
    print(f"Created enhanced WebSocket client")
    print(f"Handler type: {type(client.callback_handler).__name__}")
    print(f"Queue size: {client.config.message_queue_size}")
    print(f"Ping interval: {client.config.ping_interval}s")
    print()
    
    # Demonstrate health monitoring
    monitor = WebSocketHealthMonitor(client)
    
    # Simulate some activity
    monitor.record_message()
    monitor.record_message()
    monitor.record_error()
    
    metrics = monitor.get_health_metrics()
    print("Health Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    print(f"Is healthy: {monitor.is_healthy()}")
    print()


def demo_high_frequency_websocket():
    """Demonstrate high-frequency WebSocket configuration."""
    print("=== High-Frequency WebSocket Demo ===")
    
    # Create credentials
    credentials = KrakenCredentials(
        api_key=os.getenv('KRAKEN_API_KEY', 'demo_key'),
        api_secret=os.getenv('KRAKEN_API_SECRET', 'ZGVtb19zZWNyZXQ=')
    )
    
    # Create high-frequency client
    client = WebSocketClientFactory.create_high_frequency_client(credentials)
    
    print(f"Created high-frequency WebSocket client")
    print(f"Queue size: {client.config.message_queue_size}")
    print(f"Ping interval: {client.config.ping_interval}s")
    print(f"Max reconnect attempts: {client.config.max_reconnect_attempts}")
    print(f"Reconnect delay: {client.config.reconnect_delay}s")
    print()
    
    # Demonstrate performance optimization
    optimizer = WebSocketPerformanceOptimizer(client)
    
    # Simulate high message rate
    for i in range(100):
        optimizer.record_message_rate("ticker")
    
    print(f"Ticker message rate: {optimizer.get_message_rate('ticker'):.2f} msg/sec")
    
    # Get optimized config
    optimized_config = optimizer.optimize_config()
    print(f"Optimized queue size: {optimized_config.message_queue_size}")
    print(f"Optimized ping interval: {optimized_config.ping_interval}s")
    print()


def demo_connection_pool():
    """Demonstrate WebSocket connection pool."""
    print("=== Connection Pool Demo ===")
    
    # Create credentials
    credentials = KrakenCredentials(
        api_key=os.getenv('KRAKEN_API_KEY', 'demo_key'),
        api_secret=os.getenv('KRAKEN_API_SECRET', 'ZGVtb19zZWNyZXQ=')
    )
    
    # Create connection pool
    pool = WebSocketConnectionPool(credentials, max_connections=3)
    
    # Get connections for different pairs
    pairs = ['XBT/USD', 'ETH/USD', 'LTC/USD', 'ADA/USD', 'DOT/USD']
    
    print("Assigning pairs to connections:")
    for pair in pairs:
        conn = pool.get_connection_for_pair(pair)
        print(f"  {pair} -> Connection {id(conn)}")
    
    # Get pool statistics
    stats = pool.get_pool_stats()
    print("\nPool Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()


def demo_callback_features():
    """Demonstrate enhanced callback handler features."""
    print("=== Enhanced Callback Handler Demo ===")
    
    # Create demo handler
    handler = DemoCallbackHandler()
    
    # Simulate ticker updates
    print("Simulating ticker updates:")
    
    # First update
    ticker_data1 = {
        'c': ['50000.0', '1'],
        'a': ['50100.0', '2', '2.000'],
        'b': ['49900.0', '1', '1.000']
    }
    handler.on_ticker('XBT/USD', ticker_data1)
    
    # Second update (price change)
    ticker_data2 = {
        'c': ['50150.0', '1'],
        'a': ['50250.0', '2', '2.000'],
        'b': ['50050.0', '1', '1.000']
    }
    handler.on_ticker('XBT/USD', ticker_data2)
    
    # Show price tracking
    print("Price Tracking:")
    print(f"  Last prices: {handler.get_last_prices()}")
    print(f"  Price changes: {handler.get_price_changes()}")
    print(f"  Total messages: {handler.message_count}")
    print()


def main():
    """Run all demos."""
    print("Kraken WebSocket Enhanced Features Demo")
    print("=" * 50)
    print()
    
    try:
        demo_basic_websocket()
        demo_enhanced_websocket()
        demo_high_frequency_websocket()
        demo_connection_pool()
        demo_callback_features()
        
        print("All demos completed successfully!")
        
    except Exception as e:
        print(f"Demo error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()