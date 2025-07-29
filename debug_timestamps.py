#!/usr/bin/env python3
"""
Debug script to check timestamp formats in the data.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig
from bot.utils import log_info, log_error


def debug_timestamps():
    """Debug timestamp formats in the data."""
    print("🔍 Debugging Timestamp Formats")
    print("=" * 50)
    
    # Load credentials
    load_dotenv()
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ API credentials not found")
        return False
    
    credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
    
    # Test data manager
    print("\n1. Testing Enhanced Data Manager...")
    try:
        cache_config = CacheConfig(
            enabled=True,
            max_memory_mb=50,
            retention_hours=2,
            persist_to_disk=False
        )
        
        data_manager = EnhancedDataManager(
            pairs=["XBTUSD"],
            cache_config=cache_config
        )
        
        # Get data
        market_data = data_manager.get_latest_data("XBTUSD", periods=10)
        
        print(f"Data type: {type(market_data)}")
        print(f"Data shape: {market_data.shape if hasattr(market_data, 'shape') else 'No shape'}")
        
        if hasattr(market_data, 'index'):
            print(f"Index type: {type(market_data.index)}")
            print(f"Index values: {market_data.index[:5].tolist()}")
            print(f"Index max: {market_data.index.max()}")
            print(f"Index max type: {type(market_data.index.max())}")
            
            # Try to convert the max timestamp
            max_ts = market_data.index.max()
            print(f"Raw timestamp value: {max_ts}")
            
            # Try different conversions
            try:
                if hasattr(max_ts, 'to_pydatetime'):
                    dt1 = max_ts.to_pydatetime()
                    print(f"to_pydatetime(): {dt1}")
            except Exception as e:
                print(f"to_pydatetime() failed: {e}")
            
            try:
                dt2 = datetime.fromtimestamp(max_ts)
                print(f"fromtimestamp(): {dt2}")
            except Exception as e:
                print(f"fromtimestamp() failed: {e}")
            
            try:
                # Try as milliseconds
                dt3 = datetime.fromtimestamp(max_ts / 1000)
                print(f"fromtimestamp(ms/1000): {dt3}")
            except Exception as e:
                print(f"fromtimestamp(ms/1000) failed: {e}")
        
        if isinstance(market_data, list):
            print(f"List length: {len(market_data)}")
            if len(market_data) > 0:
                print(f"First item: {market_data[0]}")
                print(f"Last item: {market_data[-1]}")
        
    except Exception as e:
        print(f"❌ Data manager test failed: {e}")
        return False
    
    # Test Kraken client directly
    print("\n2. Testing Kraken Client OHLC...")
    try:
        client = KrakenClient(credentials)
        ohlc_data = client.get_ohlc_data("XBTUSD", interval=5)
        
        if ohlc_data and "XBTUSD" in ohlc_data:
            pair_data = ohlc_data["XBTUSD"]
            print(f"OHLC data type: {type(pair_data)}")
            print(f"OHLC data length: {len(pair_data)}")
            
            if len(pair_data) > 0:
                first_entry = pair_data[0]
                last_entry = pair_data[-1]
                
                print(f"First entry: {first_entry}")
                print(f"Last entry: {last_entry}")
                
                # The first element should be the timestamp
                if len(first_entry) > 0:
                    raw_timestamp = first_entry[0]
                    print(f"Raw timestamp from Kraken: {raw_timestamp}")
                    print(f"Raw timestamp type: {type(raw_timestamp)}")
                    
                    try:
                        dt = datetime.fromtimestamp(raw_timestamp)
                        print(f"Converted timestamp: {dt}")
                    except Exception as e:
                        print(f"Timestamp conversion failed: {e}")
        
    except Exception as e:
        print(f"❌ Kraken client test failed: {e}")
        return False
    
    print("\n✅ Timestamp debugging complete!")
    return True


def main():
    """Main function."""
    if debug_timestamps():
        print("\n🎉 Timestamp debugging successful!")
        return 0
    else:
        print("\n❌ Timestamp debugging failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())