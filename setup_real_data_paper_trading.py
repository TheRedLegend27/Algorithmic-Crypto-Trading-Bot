#!/usr/bin/env python3
"""
Setup real market data with paper trading for proper ML learning.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_kraken_connection():
    """Test if we can connect to Kraken API for market data."""
    try:
        from bot.kraken_client import KrakenClient
        
        print("🔍 Testing Kraken API connection...")
        client = KrakenClient()
        
        # Test connection
        if client.test_connection():
            print("✅ Kraken API connection successful!")
            
            # Test market data fetch
            print("📊 Testing market data fetch...")
            try:
                # Try to get ticker data (doesn't require authentication)
                ticker_data = client.get_ticker_information("XBTUSD")
                if ticker_data:
                    print(f"✅ Market data fetch successful!")
                    print(f"   BTC/USD Price: ${float(ticker_data['c'][0]):,.2f}")
                    return True
                else:
                    print("❌ Failed to fetch market data")
                    return False
            except Exception as e:
                print(f"❌ Market data fetch failed: {str(e)}")
                return False
        else:
            print("❌ Kraken API connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Kraken connection: {str(e)}")
        return False

def setup_hybrid_mode():
    """Setup hybrid mode: real data + paper trading."""
    print("\n🔧 Setting up hybrid mode (real data + paper trading)...")
    
    # Check current .env configuration
    env_path = '.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        print("Current configuration:")
        for line in env_content.split('\n'):
            if 'PAPER_TRADING' in line or 'IS_PAPER_TRADING' in line:
                print(f"  {line}")
    
    # Recommend configuration
    recommended_config = """
# Hybrid Mode Configuration (Real Data + Paper Trading)
IS_PAPER_TRADING=True
PAPER_TRADING=true
USE_REAL_MARKET_DATA=true  # New flag for using real data in paper mode

# Kraken API credentials (for market data only in paper mode)
KRAKEN_API_KEY=R7RS0VZ5f6CB5Q4X3xP6M0kpnqZqQe0iM5F0hVR94CloSuTlqIdC4KV2
KRAKEN_PRIVATE_KEY=Dx/WATD4QNCEWglliSm45f083NENV+yZskvzIdqiLB0dSSmcIjDYrzdTCG9PPrerCezhLAIxWYLRU874vKy9rg==
KRAKEN_API_SECRET=Dx/WATD4QNCEWglliSm45f083NENV+yZskvzIdqiLB0dSSmcIjDYrzdTCG9PPrerCezhLAIxWYLRU874vKy9rg==
"""
    
    print("\n📝 Recommended .env configuration:")
    print(recommended_config)
    
    # Ask user if they want to apply changes
    response = input("\nApply this configuration? (y/n): ").lower().strip()
    if response == 'y':
        with open(env_path, 'w') as f:
            f.write(recommended_config.strip())
        print("✅ Configuration updated!")
        return True
    else:
        print("⏭️  Configuration not changed")
        return False

def modify_data_manager_for_hybrid():
    """Modify the data manager to use real data in paper trading mode."""
    print("\n🔧 Modifying data manager for hybrid mode...")
    
    # Create a patch for the enhanced data manager
    patch_code = '''
    def get_latest_data(self, pair: str, periods: int = 100) -> pd.DataFrame:
        """
        Get the latest market data for a trading pair.
        Enhanced to use real data even in paper trading mode.
        """
        start_time = time.time()
        
        # Check cache first
        cache_key = f"latest_data_{periods}"
        if self.cache:
            cached_data = self.cache.get(pair, cache_key)
            if cached_data is not None:
                # ... existing cache logic ...
                self._update_cache_hit_rate(True)
                return cached_data
        
        self._update_cache_hit_rate(False)
        
        # Check if we should use real data (even in paper trading)
        use_real_data = os.getenv('USE_REAL_MARKET_DATA', 'false').lower() == 'true'
        
        try:
            if use_real_data:
                # Try to fetch real data first
                data = self.data_fetcher.fetch_crypto_data(pair, timeframe="5Min", limit=periods)
                # ... process real data ...
            else:
                # Fall back to mock data
                return self._generate_mock_data(pair, periods)
                
        except Exception as e:
            log_warning(f"Failed to get real data for {pair}: {str(e)}, using mock data")
            return self._generate_mock_data(pair, periods)
    '''
    
    print("📝 Data manager modification needed:")
    print("   - Add USE_REAL_MARKET_DATA environment variable check")
    print("   - Prioritize real data fetch even in paper trading mode")
    print("   - Fall back to mock data only if real data fails")
    
    return patch_code

def create_live_trading_option():
    """Create option for live trading with small positions."""
    print("\n💰 Live Trading Option (Alternative):")
    print("   If you want to use live trading instead of paper trading:")
    print("   1. Set IS_PAPER_TRADING=False in .env")
    print("   2. Start with very small position sizes (e.g., $10-50)")
    print("   3. Monitor closely for the first 24-48 hours")
    print("   4. Gradually increase position sizes as confidence grows")
    
    live_config = """
# Live Trading Configuration (Use with caution!)
IS_PAPER_TRADING=False
PAPER_TRADING=false

# Risk Management for Live Trading
MAX_POSITION_SIZE_USD=50.0  # Start small!
MAX_DAILY_LOSS_USD=100.0
EMERGENCY_STOP_ENABLED=true

# Kraken API credentials (full permissions needed)
KRAKEN_API_KEY=your_api_key_here
KRAKEN_PRIVATE_KEY=your_private_key_here
"""
    
    print("\n📝 Live trading .env configuration:")
    print(live_config)
    
    print("\n⚠️  WARNING: Live trading uses real money!")
    print("   - Start with very small amounts")
    print("   - Monitor the bot closely")
    print("   - Have stop-loss mechanisms in place")

def main():
    """Main setup function."""
    print("🚀 Setting up Real Market Data for Adaptive Bot")
    print("=" * 50)
    
    # Test Kraken connection
    connection_ok = test_kraken_connection()
    
    if connection_ok:
        print("\n✅ Kraken API is working - we can use real market data!")
        
        # Setup hybrid mode
        if setup_hybrid_mode():
            print("\n🎯 Next steps:")
            print("1. The bot will now use real market data for learning")
            print("2. Trading will still be simulated (paper trading)")
            print("3. ML models will learn from real market patterns")
            print("4. Run: python3 run_adaptive_bot.py")
            
            # Show the data manager modification needed
            modify_data_manager_for_hybrid()
            
        else:
            print("\n⏭️  Configuration not changed")
    else:
        print("\n❌ Kraken API connection issues detected")
        print("Options:")
        print("1. Check your API credentials in .env")
        print("2. Verify internet connection")
        print("3. Use mock data for initial testing")
        print("4. Consider live trading with small amounts")
    
    # Always show live trading option
    create_live_trading_option()
    
    print("\n" + "=" * 50)
    print("Choose your preferred approach:")
    print("1. 🔄 Hybrid: Real data + Paper trading (Recommended)")
    print("2. 💰 Live trading with small positions")
    print("3. 📊 Keep mock data for initial testing")

if __name__ == "__main__":
    main()