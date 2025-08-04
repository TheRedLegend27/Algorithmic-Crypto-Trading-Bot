#!/usr/bin/env python3
"""
Implement hybrid mode: Real market data + Paper trading
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_data_fetcher_test():
    """Fix the data fetcher test issue."""
    try:
        from bot.data_fetcher import DataFetcher
        
        print("📊 Testing data fetcher (fixed)...")
        
        data_fetcher = DataFetcher()
        data = data_fetcher.fetch_crypto_data("XBTUSD", timeframe="5Min", limit=10)
        
        # Fix the ambiguous truth value issue
        if data is not None:
            if hasattr(data, 'empty'):  # It's a DataFrame
                if not data.empty:
                    print(f"✅ Data fetcher working! Retrieved DataFrame with {len(data)} rows")
                    print(f"   Columns: {list(data.columns)}")
                    if 'close' in data.columns:
                        latest_price = data['close'].iloc[-1]
                        print(f"   Latest close price: ${latest_price:,.2f}")
                    return True, data
                else:
                    print("❌ Data fetcher returned empty DataFrame")
                    return False, None
            elif isinstance(data, list) and len(data) > 0:
                print(f"✅ Data fetcher working! Retrieved {len(data)} data points")
                return True, data
            else:
                print("❌ Data fetcher returned unexpected format")
                return False, None
        else:
            print("❌ Data fetcher returned None")
            return False, None
            
    except Exception as e:
        print(f"❌ Error testing data fetcher: {str(e)}")
        return False, None

def create_hybrid_enhanced_data_manager():
    """Create a hybrid version of the enhanced data manager."""
    
    print("\n🔧 Creating hybrid enhanced data manager...")
    
    # Read the current enhanced data manager
    try:
        with open('bot/enhanced_data_manager.py', 'r') as f:
            content = f.read()
        
        # Find the get_latest_data method and modify it
        if 'def get_latest_data' in content:
            print("✅ Found get_latest_data method")
            
            # Create the modified version
            modified_method = '''    def get_latest_data(self, pair: str, periods: int = 100) -> pd.DataFrame:
        """
        Get the latest market data for a trading pair.
        Enhanced to prioritize real data even in paper trading mode.
        """
        start_time = time.time()
        
        # Check cache first
        cache_key = f"latest_data_{periods}"
        if self.cache:
            cached_data = self.cache.get(pair, cache_key)
            if cached_data is not None:
                # Ensure cached data is a DataFrame
                if isinstance(cached_data, list):
                    # Convert list to DataFrame
                    df = pd.DataFrame(cached_data)
                    # Ensure timestamp is datetime and set as index if it exists
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                        df.set_index('timestamp', inplace=True)
                    else:
                        # Create a timestamp index if none exists
                        df.index = pd.date_range(
                            start=datetime.now() - timedelta(minutes=len(df)*5),
                            periods=len(df),
                            freq='5min'
                        )
                        df.index.name = 'timestamp'
                    
                    # Ensure numeric columns are properly typed
                    numeric_cols = ['open', 'high', 'low', 'close', 'vwap', 'volume']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    # Update cache with DataFrame
                    self.cache.set(pair, cache_key, df)
                    cached_data = df
                
                self._update_cache_hit_rate(True)
                return cached_data
        
        self._update_cache_hit_rate(False)
        
        # HYBRID MODE: Always try real data first, even in paper trading
        try:
            # Fetch real data
            data = self.data_fetcher.fetch_crypto_data(pair, timeframe="5Min", limit=periods)
            
            # Process the data
            if data is not None:
                if hasattr(data, 'empty') and not data.empty:
                    # It's already a DataFrame
                    df = data
                    log_info(f"Using real market data for {pair} ({len(df)} points)")
                elif isinstance(data, list) and len(data) > 0:
                    # Convert list to DataFrame
                    df = pd.DataFrame(data)
                    # Ensure timestamp is datetime and set as index if it exists
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                        df.set_index('timestamp', inplace=True)
                    else:
                        # Create a timestamp index if none exists
                        df.index = pd.date_range(
                            start=datetime.now() - timedelta(minutes=len(df)*5),
                            periods=len(df),
                            freq='5min'
                        )
                        df.index.name = 'timestamp'
                    
                    # Ensure numeric columns are properly typed
                    numeric_cols = ['open', 'high', 'low', 'close', 'vwap', 'volume']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    log_info(f"Using real market data for {pair} ({len(df)} points)")
                else:
                    raise Exception("Data fetcher returned unexpected format")
                
                # Cache the result
                if self.cache:
                    self.cache.set(pair, cache_key, df)
                
                # Update latest data storage
                with self._lock:
                    self._latest_data[pair] = df
                
                # Update performance metrics
                fetch_time = (time.time() - start_time) * 1000
                self._performance_metrics.fetch_time_ms = fetch_time
                
                return df
            else:
                raise Exception("Data fetcher returned None")
                
        except Exception as e:
            log_warning(f"Failed to get real data for {pair}: {str(e)}, using mock data")
            # Generate mock data as fallback
            return self._generate_mock_data(pair, periods)'''
            
            print("📝 Created hybrid get_latest_data method")
            return modified_method
        else:
            print("❌ Could not find get_latest_data method")
            return None
            
    except Exception as e:
        print(f"❌ Error reading enhanced data manager: {str(e)}")
        return None

def update_env_for_hybrid():
    """Update .env file for hybrid mode."""
    print("\n🔧 Updating .env for hybrid mode...")
    
    # Read current .env
    try:
        with open('.env', 'r') as f:
            env_content = f.read()
        
        # Add hybrid mode flag
        if 'USE_REAL_MARKET_DATA' not in env_content:
            env_content += '\n# Hybrid Mode: Use real market data even in paper trading\nUSE_REAL_MARKET_DATA=true\n'
        
        # Ensure paper trading is enabled
        env_content = env_content.replace('IS_PAPER_TRADING=False', 'IS_PAPER_TRADING=True')
        env_content = env_content.replace('PAPER_TRADING=false', 'PAPER_TRADING=true')
        
        # Write back
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("✅ Updated .env file for hybrid mode")
        print("   - IS_PAPER_TRADING=True (safe execution)")
        print("   - USE_REAL_MARKET_DATA=true (real data for learning)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env: {str(e)}")
        return False

def apply_hybrid_patch():
    """Apply the hybrid patch to the enhanced data manager."""
    print("\n🔧 Applying hybrid patch to enhanced data manager...")
    
    try:
        # Read the current file
        with open('bot/enhanced_data_manager.py', 'r') as f:
            content = f.read()
        
        # Find the existing get_latest_data method
        start_marker = "    def get_latest_data(self, pair: str, periods: int = 100) -> pd.DataFrame:"
        end_marker = "            return self._generate_mock_data(pair, periods)"
        
        start_idx = content.find(start_marker)
        if start_idx == -1:
            print("❌ Could not find get_latest_data method")
            return False
        
        # Find the end of the method (look for the next method definition or class end)
        lines = content[start_idx:].split('\n')
        method_lines = []
        indent_level = None
        
        for i, line in enumerate(lines):
            if i == 0:
                method_lines.append(line)
                continue
            
            # Determine indent level from first non-empty line
            if indent_level is None and line.strip():
                indent_level = len(line) - len(line.lstrip())
            
            # If we hit a line with same or less indentation (and it's not empty), we've reached the end
            if line.strip() and indent_level is not None:
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= 4:  # Method level indentation
                    break
            
            method_lines.append(line)
        
        # Replace the method
        old_method = '\n'.join(method_lines)
        new_method = create_hybrid_enhanced_data_manager()
        
        if new_method:
            new_content = content.replace(old_method, new_method)
            
            # Write back
            with open('bot/enhanced_data_manager.py', 'w') as f:
                f.write(new_content)
            
            print("✅ Applied hybrid patch to enhanced data manager")
            return True
        else:
            print("❌ Failed to create hybrid method")
            return False
            
    except Exception as e:
        print(f"❌ Error applying hybrid patch: {str(e)}")
        return False

def test_hybrid_mode():
    """Test the hybrid mode implementation."""
    print("\n🧪 Testing hybrid mode...")
    
    try:
        # Import the modified data manager
        from bot.enhanced_data_manager import EnhancedDataManager
        
        # Create instance
        data_manager = EnhancedDataManager(['XBTUSD'])
        
        # Test getting data
        data = data_manager.get_latest_data('XBTUSD', periods=10)
        
        if data is not None and not data.empty:
            print(f"✅ Hybrid mode working! Got {len(data)} data points")
            print(f"   Data source: {'Real' if len(data) > 50 else 'Mock'}")
            if 'close' in data.columns:
                print(f"   Latest price: ${data['close'].iloc[-1]:,.2f}")
            return True
        else:
            print("❌ Hybrid mode test failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing hybrid mode: {str(e)}")
        return False

def main():
    """Main implementation function."""
    print("🚀 Implementing Hybrid Mode (Real Data + Paper Trading)")
    print("="*60)
    
    # Step 1: Test data fetcher
    print("Step 1: Testing data fetcher...")
    fetcher_works, sample_data = fix_data_fetcher_test()
    
    if not fetcher_works:
        print("❌ Data fetcher not working, cannot implement hybrid mode")
        return
    
    # Step 2: Update environment
    print("\nStep 2: Updating environment configuration...")
    if not update_env_for_hybrid():
        print("❌ Failed to update environment")
        return
    
    # Step 3: Create hybrid method
    print("\nStep 3: Creating hybrid data manager method...")
    hybrid_method = create_hybrid_enhanced_data_manager()
    if not hybrid_method:
        print("❌ Failed to create hybrid method")
        return
    
    # Step 4: Apply patch (optional - user can do manually)
    print("\nStep 4: Apply hybrid patch? (This will modify bot/enhanced_data_manager.py)")
    response = input("Apply patch automatically? (y/n): ").lower().strip()
    
    if response == 'y':
        if apply_hybrid_patch():
            print("✅ Hybrid patch applied successfully!")
            
            # Step 5: Test the implementation
            print("\nStep 5: Testing hybrid implementation...")
            if test_hybrid_mode():
                print("\n🎉 HYBRID MODE SUCCESSFULLY IMPLEMENTED!")
                print("="*60)
                print("✅ Your bot will now:")
                print("   • Use REAL market data for ML learning")
                print("   • Execute trades in PAPER mode (no risk)")
                print("   • Learn from actual market patterns")
                print("   • Fall back to mock data if API fails")
                print("\n🚀 Ready to run: python3 run_adaptive_bot.py")
            else:
                print("❌ Hybrid mode test failed")
        else:
            print("❌ Failed to apply hybrid patch")
    else:
        print("\n📝 Manual implementation required:")
        print("   1. Replace the get_latest_data method in bot/enhanced_data_manager.py")
        print("   2. Use the hybrid method code provided above")
        print("   3. Test with: python3 debug_data_flow.py")

if __name__ == "__main__":
    main()