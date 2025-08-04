#!/usr/bin/env python3
"""
Test that the bot is actually using real market data.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_real_data_integration():
    """Test that the adaptive bot uses real market data."""
    print("🧪 Testing Real Data Integration")
    print("="*50)
    
    try:
        from bot.enhanced_data_manager import EnhancedDataManager
        
        # Test 1: Direct data manager test
        print("Test 1: Direct data manager test...")
        data_manager = EnhancedDataManager(['XBTUSD', 'ETHUSD'])
        
        # Get data for BTC
        btc_data = data_manager.get_latest_data('XBTUSD', periods=10)
        print(f"   BTC data points: {len(btc_data)}")
        print(f"   BTC latest price: ${btc_data['close'].iloc[-1]:,.2f}")
        print(f"   Data source: {'Real' if len(btc_data) > 50 else 'Mock'}")
        
        # Get data for ETH
        eth_data = data_manager.get_latest_data('ETHUSD', periods=10)
        print(f"   ETH data points: {len(eth_data)}")
        print(f"   ETH latest price: ${eth_data['close'].iloc[-1]:,.2f}")
        print(f"   Data source: {'Real' if len(eth_data) > 50 else 'Mock'}")
        
        # Test 2: Full bot integration test
        print("\nTest 2: Full bot integration test...")
        from bot.adaptive.adaptive_bot_main import AdaptiveBotMain
        
        bot = AdaptiveBotMain()
        success = await bot.initialize_components()
        
        if success:
            print("   ✅ Bot initialized successfully")
            
            # Test data fetching through bot
            if bot.data_manager:
                bot_btc_data = await bot.data_manager.get_market_data('XBTUSD', limit=10)
                print(f"   Bot BTC data points: {len(bot_btc_data)}")
                print(f"   Bot BTC latest price: ${bot_btc_data['close'].iloc[-1]:,.2f}")
                print(f"   Bot data source: {'Real' if len(bot_btc_data) > 50 else 'Mock'}")
                
                # Test regime detection with real data
                if bot.regime_detector:
                    regime = bot.regime_detector.detect_regime(bot_btc_data, 'XBTUSD')
                    print(f"   Regime detected: {regime.regime_type.value}")
                    print(f"   Regime confidence: {regime.confidence:.3f}")
                
                # Test strategy engine with real data
                if bot.strategy_engine:
                    signal = bot.strategy_engine.execute_adaptive_signal('XBTUSD', bot_btc_data)
                    if signal:
                        print(f"   Signal generated: {signal.signal_type}")
                        print(f"   Signal confidence: {signal.confidence:.3f}")
                        print(f"   Signal price: ${signal.price:,.2f}")
                    else:
                        print("   No signal generated")
            else:
                print("   ❌ Bot data manager not initialized")
        else:
            print("   ❌ Bot initialization failed")
        
        # Test 3: Compare real vs mock data characteristics
        print("\nTest 3: Data characteristics comparison...")
        
        # Real data characteristics
        if len(btc_data) > 50:  # Likely real data
            price_range = btc_data['high'].max() - btc_data['low'].min()
            avg_volume = btc_data['volume'].mean()
            price_volatility = btc_data['close'].pct_change().std()
            
            print(f"   Real data characteristics:")
            print(f"     Price range: ${price_range:,.2f}")
            print(f"     Average volume: {avg_volume:,.2f}")
            print(f"     Price volatility: {price_volatility:.4f}")
            
            # Check if prices are realistic for BTC
            latest_price = btc_data['close'].iloc[-1]
            if 50000 <= latest_price <= 200000:  # Reasonable BTC price range
                print(f"   ✅ Price range realistic for BTC: ${latest_price:,.2f}")
            else:
                print(f"   ⚠️  Price might be mock data: ${latest_price:,.2f}")
        else:
            print("   ⚠️  Data appears to be mock (small dataset)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in real data integration test: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def check_environment():
    """Check environment configuration."""
    print("\n🔧 Environment Configuration Check")
    print("="*40)
    
    # Check .env file
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            env_content = f.read()
        
        print("Current .env settings:")
        for line in env_content.split('\n'):
            if any(key in line for key in ['PAPER_TRADING', 'USE_REAL_MARKET_DATA', 'KRAKEN']):
                print(f"   {line}")
    
    # Check environment variables
    paper_trading = os.getenv('IS_PAPER_TRADING', 'True')
    use_real_data = os.getenv('USE_REAL_MARKET_DATA', 'false')
    
    print(f"\nEnvironment variables:")
    print(f"   IS_PAPER_TRADING: {paper_trading}")
    print(f"   USE_REAL_MARKET_DATA: {use_real_data}")
    
    if paper_trading.lower() == 'true' and use_real_data.lower() == 'true':
        print("   ✅ Hybrid mode configuration detected")
    elif paper_trading.lower() == 'false':
        print("   ⚠️  Live trading mode detected")
    else:
        print("   ⚠️  Mock data mode detected")

async def main():
    """Main test function."""
    check_environment()
    await test_real_data_integration()
    
    print("\n" + "="*50)
    print("🎯 SUMMARY:")
    print("   If you see 'Real' data sources above, the hybrid mode is working!")
    print("   If you see 'Mock' data sources, check the data fetcher configuration.")
    print("="*50)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())