#!/usr/bin/env python3
"""
Test Kraken API for real market data access.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_kraken_market_data():
    """Test if we can get market data from Kraken (no auth needed)."""
    try:
        import requests
        
        print("🔍 Testing Kraken public API (no authentication needed)...")
        
        # Test public ticker endpoint
        url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'XXBTZUSD' in data['result']:
                ticker = data['result']['XXBTZUSD']
                price = float(ticker['c'][0])  # Last trade price
                print(f"✅ Kraken public API working!")
                print(f"   BTC/USD Price: ${price:,.2f}")
                print(f"   24h Volume: {float(ticker['v'][1]):,.2f} BTC")
                return True
            else:
                print(f"❌ Unexpected response format: {data}")
                return False
        else:
            print(f"❌ API request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Kraken API: {str(e)}")
        return False

def test_data_fetcher():
    """Test if our data fetcher can get real data."""
    try:
        from bot.data_fetcher import DataFetcher
        
        print("\n📊 Testing data fetcher with real Kraken data...")
        
        # Initialize data fetcher
        data_fetcher = DataFetcher()
        
        # Try to fetch real data
        data = data_fetcher.fetch_crypto_data("XBTUSD", timeframe="5Min", limit=10)
        
        if data and len(data) > 0:
            print(f"✅ Data fetcher working!")
            print(f"   Retrieved {len(data)} data points")
            if isinstance(data, list) and len(data) > 0:
                latest = data[-1]
                print(f"   Latest close price: ${latest.get('close', 'N/A')}")
            return True
        else:
            print("❌ Data fetcher returned no data")
            return False
            
    except Exception as e:
        print(f"❌ Error testing data fetcher: {str(e)}")
        return False

def create_hybrid_data_manager():
    """Create a modified data manager that uses real data in paper trading."""
    
    hybrid_code = '''
import os
from bot.enhanced_data_manager import EnhancedDataManager

class HybridDataManager(EnhancedDataManager):
    """
    Enhanced data manager that uses real market data even in paper trading mode.
    """
    
    def get_latest_data(self, pair: str, periods: int = 100):
        """Get latest data with real data priority."""
        
        # Always try real data first if available
        try:
            # Use the data fetcher to get real data
            data = self.data_fetcher.fetch_crypto_data(pair, timeframe="5Min", limit=periods)
            
            if data and len(data) > 0:
                # Process and return real data
                df = self._process_real_data(data)
                if not df.empty:
                    self.logger.info(f"Using real market data for {pair} ({len(df)} points)")
                    return df
        except Exception as e:
            self.logger.warning(f"Real data fetch failed for {pair}: {str(e)}")
        
        # Fall back to mock data only if real data fails
        self.logger.info(f"Falling back to mock data for {pair}")
        return self._generate_mock_data(pair, periods)
    
    def _process_real_data(self, data):
        """Process real data into DataFrame format."""
        import pandas as pd
        from datetime import datetime
        
        if isinstance(data, list):
            # Convert list to DataFrame
            df = pd.DataFrame(data)
            
            # Ensure timestamp is datetime and set as index
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df.set_index('timestamp', inplace=True)
            else:
                # Create timestamp index if missing
                df.index = pd.date_range(
                    start=datetime.now() - pd.Timedelta(minutes=len(df)*5),
                    periods=len(df),
                    freq='5min'
                )
                df.index.name = 'timestamp'
            
            # Ensure numeric columns
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        
        return pd.DataFrame()
'''
    
    print("\n🔧 Hybrid Data Manager Code:")
    print("   This would replace mock data with real Kraken data")
    print("   while keeping paper trading for execution")
    
    # Save the hybrid code to a file
    with open('hybrid_data_manager.py', 'w') as f:
        f.write(hybrid_code)
    
    print("   📝 Saved to: hybrid_data_manager.py")
    
    return hybrid_code

def recommend_approach():
    """Recommend the best approach based on API availability."""
    
    print("\n" + "="*60)
    print("🎯 RECOMMENDATIONS")
    print("="*60)
    
    # Test both APIs
    kraken_works = test_kraken_market_data()
    data_fetcher_works = test_data_fetcher()
    
    if kraken_works and data_fetcher_works:
        print("\n✅ RECOMMENDED: Hybrid Mode (Real Data + Paper Trading)")
        print("   ✓ Kraken API is accessible")
        print("   ✓ Data fetcher is working")
        print("   ✓ ML will learn from real market patterns")
        print("   ✓ No risk from paper trading")
        
        print("\n🔧 Implementation Steps:")
        print("   1. Use the HybridDataManager class")
        print("   2. Keep IS_PAPER_TRADING=True")
        print("   3. Bot will fetch real data but simulate trades")
        print("   4. ML models will learn from real market behavior")
        
        create_hybrid_data_manager()
        
    elif kraken_works:
        print("\n⚠️  ALTERNATIVE: Fix Data Fetcher or Use Direct API")
        print("   ✓ Kraken API is accessible")
        print("   ❌ Data fetcher has issues")
        print("   → Consider implementing direct Kraken data fetching")
        
    else:
        print("\n❌ FALLBACK OPTIONS:")
        print("   1. 💰 Live Trading with Small Amounts")
        print("      - Set IS_PAPER_TRADING=False")
        print("      - Use $10-20 position sizes")
        print("      - Monitor closely")
        
        print("\n   2. 📊 Historical Data Training")
        print("      - Download historical data")
        print("      - Train models offline")
        print("      - Switch to live data later")
        
        print("\n   3. 🔄 Keep Mock Data Temporarily")
        print("      - Use for system testing")
        print("      - Switch to real data once API issues resolved")

def main():
    """Main function."""
    print("🚀 Testing Real Market Data Access")
    print("="*50)
    
    recommend_approach()
    
    print("\n" + "="*60)
    print("💡 NEXT STEPS:")
    print("   Choose one of the recommended approaches above")
    print("   The hybrid approach is safest for learning with real data")
    print("="*60)

if __name__ == "__main__":
    main()