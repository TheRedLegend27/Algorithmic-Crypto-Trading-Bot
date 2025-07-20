#!/usr/bin/env python3
"""
Demo script showcasing the Market Data Integration functionality.

This script demonstrates:
1. Real-time market data fetching from multiple sources
2. Data validation and quality scoring
3. Market hours handling
4. Caching and fallback mechanisms
5. Multiple symbol price fetching
6. Real-time subscriptions and updates
"""
import time
import asyncio
from datetime import datetime
from typing import List

from market_data_integration import MarketDataIntegration, MarketDataPoint
from mock_config import MockTradingConfig
from bot.config import AlpacaCredentials


def demo_basic_market_data():
    """Demonstrate basic market data fetching."""
    print("=== Basic Market Data Fetching Demo ===")
    
    # Initialize with default configuration
    config = MockTradingConfig()
    integration = MarketDataIntegration(config)
    
    symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
    
    print(f"Fetching current prices for: {', '.join(symbols)}")
    
    for symbol in symbols:
        try:
            data_point = integration.get_current_price(symbol, use_cache=False)
            if data_point:
                print(f"{symbol}: ${data_point.price:,.2f} "
                      f"(Quality: {data_point.quality_score:.2f}, "
                      f"Source: {data_point.source.value})")
            else:
                print(f"{symbol}: No data available")
        except Exception as e:
            print(f"{symbol}: Error - {e}")
    
    integration.cleanup()
    print()


def demo_multiple_prices():
    """Demonstrate efficient multiple price fetching."""
    print("=== Multiple Price Fetching Demo ===")
    
    config = MockTradingConfig()
    integration = MarketDataIntegration(config)
    
    symbols = ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD", "DOT/USD"]
    
    print(f"Fetching prices for {len(symbols)} symbols simultaneously...")
    start_time = time.time()
    
    results = integration.get_multiple_prices(symbols, use_cache=False)
    
    end_time = time.time()
    
    print(f"Fetched {len(results)} prices in {end_time - start_time:.2f} seconds:")
    
    for symbol, data_point in results.items():
        if data_point:
            print(f"  {symbol}: ${data_point.price:,.2f} "
                  f"(Spread: {data_point.spread*100:.3f}%)")
        else:
            print(f"  {symbol}: No data")
    
    integration.cleanup()
    print()


def demo_data_quality_monitoring():
    """Demonstrate data quality monitoring."""
    print("=== Data Quality Monitoring Demo ===")
    
    config = MockTradingConfig()
    integration = MarketDataIntegration(config)
    
    # Fetch some data to populate cache
    symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
    for symbol in symbols:
        integration.get_current_price(symbol, use_cache=False)
        integration.tracked_symbols.add(symbol)
    
    # Get quality report
    quality_report = integration.get_data_quality_report()
    
    print("Data Quality Report:")
    print(f"  Total symbols tracked: {quality_report['total_symbols']}")
    print(f"  Symbols with data: {quality_report['symbols_with_data']}")
    print(f"  Average quality score: {quality_report['average_quality_score']:.3f}")
    print(f"  Data sources used: {quality_report['data_sources_used']}")
    
    if quality_report['symbols_with_stale_data'] > 0:
        print(f"  ⚠️  Symbols with stale data: {quality_report['symbols_with_stale_data']}")
    
    if quality_report['symbols_with_low_quality'] > 0:
        print(f"  ⚠️  Symbols with low quality: {quality_report['symbols_with_low_quality']}")
    
    if quality_report['validation_issues']:
        print("  Validation issues:")
        for symbol, issues in quality_report['validation_issues'].items():
            print(f"    {symbol}: {', '.join(issues)}")
    
    integration.cleanup()
    print()


def demo_market_hours():
    """Demonstrate market hours handling."""
    print("=== Market Hours Handling Demo ===")
    
    config = MockTradingConfig()
    config.market.market_hours_enforcement = True
    integration = MarketDataIntegration(config)
    
    current_status = integration.get_market_status()
    print(f"Current market status: {current_status.value}")
    
    # Test with different settings
    symbols = ["BTC/USD", "ETH/USD"]
    
    for symbol in symbols:
        allowed = integration.validate_market_hours(symbol)
        print(f"Trading allowed for {symbol}: {'✅ Yes' if allowed else '❌ No'}")
    
    # Test with extended hours
    config.market.extended_hours_trading = True
    print("\nWith extended hours trading enabled:")
    
    for symbol in symbols:
        allowed = integration.validate_market_hours(symbol)
        print(f"Trading allowed for {symbol}: {'✅ Yes' if allowed else '❌ No'}")
    
    integration.cleanup()
    print()


def demo_real_time_subscriptions():
    """Demonstrate real-time price subscriptions."""
    print("=== Real-Time Price Subscriptions Demo ===")
    
    config = MockTradingConfig()
    integration = MarketDataIntegration(config)
    integration.update_interval = 2  # Update every 2 seconds for demo
    
    received_updates = []
    
    def price_callback(data_point: MarketDataPoint):
        received_updates.append(data_point)
        print(f"📈 {data_point.symbol}: ${data_point.price:,.2f} "
              f"at {data_point.timestamp.strftime('%H:%M:%S')}")
    
    # Subscribe to updates
    symbol = "BTC/USD"
    integration.subscribe_to_symbol(symbol, price_callback)
    
    print(f"Subscribed to real-time updates for {symbol}")
    print("Starting real-time updates (will run for 10 seconds)...")
    
    # Start updates
    integration.start_real_time_updates()
    
    # Wait for some updates
    time.sleep(10)
    
    # Stop updates
    integration.stop_real_time_updates()
    
    print(f"Received {len(received_updates)} price updates")
    
    integration.cleanup()
    print()


def demo_integration_stats():
    """Demonstrate integration statistics."""
    print("=== Integration Statistics Demo ===")
    
    config = MockTradingConfig()
    integration = MarketDataIntegration(config)
    
    # Add some tracked symbols
    symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
    for symbol in symbols:
        integration.get_current_price(symbol, use_cache=False)
        integration.tracked_symbols.add(symbol)
    
    # Get comprehensive stats
    stats = integration.get_integration_stats()
    
    print("Integration Statistics:")
    print(f"  Tracked symbols: {stats['tracked_symbols']}")
    print(f"  Active subscribers: {stats['subscribers']}")
    print(f"  Real-time updates running: {stats['running']}")
    print(f"  Update interval: {stats['update_interval']} seconds")
    print(f"  Market status: {stats['market_status']}")
    print(f"  Primary source available: {stats['primary_source_available']}")
    print(f"  Fallback source available: {stats['fallback_source_available']}")
    
    # Cache statistics
    cache_stats = stats['cache_stats']
    print(f"  Cache entries (memory): {cache_stats['memory_entries']}")
    print(f"  Cache files (disk): {cache_stats['disk_files']}")
    
    # Data quality summary
    quality = stats['data_quality']
    print(f"  Data quality score: {quality['average_quality_score']:.3f}")
    
    integration.cleanup()
    print()


def main():
    """Run all demo functions."""
    print("🚀 Market Data Integration Demo")
    print("=" * 50)
    
    try:
        demo_basic_market_data()
        demo_multiple_prices()
        demo_data_quality_monitoring()
        demo_market_hours()
        demo_real_time_subscriptions()
        demo_integration_stats()
        
        print("✅ All demos completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()