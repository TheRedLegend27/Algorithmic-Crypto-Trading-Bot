#!/usr/bin/env python3
"""
Demo script for the Enhanced Data Manager system.
Shows data synchronization, caching, indicator calculations, and quality validation.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from datetime import datetime
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig, MarketData


def main():
    """Demonstrate the Enhanced Data Manager functionality."""
    print("=== Enhanced Data Manager Demo ===\n")
    
    # Configuration
    pairs = ['XBTUSD', 'ETHUSD']  # Kraken format
    cache_config = CacheConfig(
        enabled=True,
        max_memory_mb=50,
        retention_hours=1,
        persist_to_disk=False,  # Disable for demo
        cleanup_interval_minutes=5
    )
    
    # Initialize data manager
    print("1. Initializing Enhanced Data Manager...")
    data_manager = EnhancedDataManager(pairs, cache_config)
    print(f"   ✓ Initialized with {len(pairs)} trading pairs")
    print()
    
    # Demonstrate data fetching and caching
    print("2. Fetching market data...")
    for pair in pairs:
        print(f"   Fetching data for {pair}...")
        try:
            # First fetch (should hit API)
            start_time = time.time()
            data = data_manager.get_latest_data(pair, periods=100)
            fetch_time1 = time.time() - start_time
            
            if not data.empty:
                print(f"   ✓ Retrieved {len(data)} data points in {fetch_time1:.3f}s")
                
                # Second fetch (should use cache)
                start_time = time.time()
                cached_data = data_manager.get_latest_data(pair, periods=100)
                fetch_time2 = time.time() - start_time
                
                print(f"   ✓ Cached retrieval in {fetch_time2:.3f}s (speedup: {fetch_time1/fetch_time2:.1f}x)")
            else:
                print(f"   ⚠ No data retrieved for {pair}")
        except Exception as e:
            print(f"   ✗ Error fetching data for {pair}: {str(e)}")
    print()
    
    # Demonstrate indicator calculations
    print("3. Calculating technical indicators...")
    indicators = ['sma', 'ema', 'rsi', 'macd', 'bollinger_bands']
    
    for pair in pairs:
        print(f"   Calculating indicators for {pair}...")
        try:
            start_time = time.time()
            results = data_manager.calculate_indicators(pair, indicators)
            calc_time = time.time() - start_time
            
            calculated_indicators = [name for name, value in results.items() if value is not None]
            print(f"   ✓ Calculated {len(calculated_indicators)} indicators in {calc_time:.3f}s")
            print(f"     Indicators: {', '.join(calculated_indicators)}")
        except Exception as e:
            print(f"   ✗ Error calculating indicators for {pair}: {str(e)}")
    print()
    
    # Demonstrate data quality validation
    print("4. Validating data quality...")
    for pair in pairs:
        try:
            data = data_manager.get_latest_data(pair, periods=50)
            if not data.empty:
                quality_report = data_manager.validate_data_quality(data)
                
                status = "✓ VALID" if quality_report.is_valid else "⚠ INVALID"
                print(f"   {pair}: {status} (Score: {quality_report.quality_score:.3f})")
                
                if quality_report.issues:
                    for issue in quality_report.issues:
                        print(f"     - {issue}")
            else:
                print(f"   {pair}: No data to validate")
        except Exception as e:
            print(f"   ✗ Error validating {pair}: {str(e)}")
    print()
    
    # Demonstrate adding market data
    print("5. Adding real-time market data...")
    for i, pair in enumerate(pairs):
        market_data = MarketData(
            pair=pair,
            timestamp=datetime.now(),
            price=50000.0 + i * 1000,
            volume=1000.0 + i * 100,
            bid=50000.0 + i * 1000 - 5,
            ask=50000.0 + i * 1000 + 5,
            spread=10.0
        )
        
        data_manager.add_market_data(pair, market_data)
        print(f"   ✓ Added market data for {pair} (Price: ${market_data.price:,.2f})")
    print()
    
    # Demonstrate performance metrics
    print("6. Performance metrics...")
    try:
        metrics = data_manager.calculate_performance_metrics()
        
        print(f"   Memory usage: {metrics.memory_usage_mb:.2f} MB")
        print(f"   Cache hit rate: {metrics.cache_hit_rate:.1%}")
        print(f"   Data quality score: {metrics.data_quality_score:.3f}")
        print(f"   Active pairs: {metrics.active_pairs}")
        print(f"   Total data points: {metrics.total_data_points}")
        print(f"   Last updated: {metrics.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"   ✗ Error getting performance metrics: {str(e)}")
    print()
    
    # Demonstrate system status
    print("7. System status overview...")
    try:
        status = data_manager.get_system_status()
        
        print(f"   Active pairs: {status['active_pairs']}")
        print(f"   Performance metrics available: {'performance_metrics' in status}")
        print(f"   Cache statistics available: {'cache_stats' in status}")
        
        print("\n   Pair summaries:")
        for pair, summary in status['pair_summaries'].items():
            data_points = summary.get('latest_data_points', 0)
            last_price = summary.get('last_price')
            quality = summary.get('data_quality', {})
            
            price_str = f"${last_price:,.2f}" if last_price else "N/A"
            quality_str = f"{quality.get('quality_score', 0):.3f}" if quality else "N/A"
            
            print(f"     {pair}: {data_points} points, Price: {price_str}, Quality: {quality_str}")
    except Exception as e:
        print(f"   ✗ Error getting system status: {str(e)}")
    print()
    
    # Demonstrate pair management
    print("8. Trading pair management...")
    try:
        # Add a new pair
        new_pair = 'SOLUSD'
        result = data_manager.add_trading_pair(new_pair)
        if result:
            print(f"   ✓ Added new trading pair: {new_pair}")
        else:
            print(f"   ⚠ Failed to add trading pair: {new_pair}")
        
        # Remove a pair
        result = data_manager.remove_trading_pair(new_pair)
        if result:
            print(f"   ✓ Removed trading pair: {new_pair}")
        else:
            print(f"   ⚠ Failed to remove trading pair: {new_pair}")
    except Exception as e:
        print(f"   ✗ Error managing trading pairs: {str(e)}")
    print()
    
    # Demonstrate synchronization
    print("9. Synchronizing all pairs...")
    try:
        sync_results = data_manager.sync_all_pairs()
        
        for pair, success in sync_results.items():
            status = "✓ SUCCESS" if success else "✗ FAILED"
            print(f"   {pair}: {status}")
    except Exception as e:
        print(f"   ✗ Error synchronizing pairs: {str(e)}")
    print()
    
    # Cleanup
    print("10. Cleaning up...")
    data_manager.cleanup()
    print("    ✓ Enhanced Data Manager cleaned up")
    print()
    
    print("=== Demo completed successfully! ===")


if __name__ == "__main__":
    main()