#!/usr/bin/env python3
"""
Test the aggressive $480 configuration.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_aggressive_config():
    """Test the aggressive $480 configuration."""
    print("🧪 Testing Aggressive $480 Configuration")
    print("="*50)
    
    try:
        from bot.adaptive.adaptive_bot_main import AdaptiveBotMain, AdaptiveBotConfig
        
        # Test 1: Check configuration values
        print("Test 1: Configuration Values")
        config = AdaptiveBotConfig()
        
        print(f"   💰 Initial Capital: ${config.initial_capital:,.0f}")
        print(f"   🎯 Max Positions: {config.max_positions}")
        print(f"   ⚠️  Risk Per Trade: {config.max_risk_per_trade:.1%}")
        print(f"   📊 Portfolio Risk: {config.max_portfolio_risk:.1%}")
        print(f"   🛑 Max Drawdown: {config.max_drawdown_threshold:.1%}")
        print(f"   🔄 Adaptation Confidence: {config.min_adaptation_confidence:.1f}")
        print(f"   📈 Max Adaptations/Day: {config.max_adaptations_per_day}")
        
        # Verify aggressive settings
        assert config.initial_capital == 480.0, f"Expected $480, got ${config.initial_capital}"
        assert config.max_positions == 3, f"Expected 3 positions, got {config.max_positions}"
        assert config.max_risk_per_trade == 0.08, f"Expected 8% risk, got {config.max_risk_per_trade:.1%}"
        assert config.max_portfolio_risk == 0.25, f"Expected 25% portfolio risk, got {config.max_portfolio_risk:.1%}"
        
        print("   ✅ All configuration values correct!")
        
        # Test 2: Initialize bot with aggressive config
        print("\nTest 2: Bot Initialization")
        bot = AdaptiveBotMain(config)
        
        success = await bot.initialize_components()
        if success:
            print("   ✅ Bot initialized successfully with aggressive config")
            
            # Test 3: Check position manager balance
            print("\nTest 3: Position Manager Balance")
            if bot.position_manager:
                usd_balance = bot.position_manager.get_crypto_balance('USD')
                if usd_balance:
                    print(f"   💰 USD Balance: ${usd_balance.balance:,.0f}")
                    print(f"   💰 Available: ${usd_balance.available:,.0f}")
                    
                    assert usd_balance.balance == 480.0, f"Expected $480 balance, got ${usd_balance.balance}"
                    print("   ✅ Position manager balance correct!")
                else:
                    print("   ❌ No USD balance found")
            
            # Test 4: Calculate aggressive position sizes
            print("\nTest 4: Aggressive Position Sizing")
            position_size_15pct = config.initial_capital * 0.15  # 15% aggressive
            position_size_8pct_risk = config.initial_capital * config.max_risk_per_trade  # 8% risk
            
            print(f"   📊 15% Position Size: ${position_size_15pct:,.0f}")
            print(f"   ⚠️  8% Risk Amount: ${position_size_8pct_risk:,.0f}")
            print(f"   🎯 Max 3 Positions: ${position_size_15pct * 3:,.0f} total exposure")
            print(f"   📈 Remaining Capital: ${config.initial_capital - (position_size_15pct * 3):,.0f}")
            
            # Test 5: Verify adaptive settings
            print("\nTest 5: Adaptive Settings")
            if bot.adaptation_controller:
                limits = bot.adaptation_controller.limits
                print(f"   🔄 Max Adaptations/Hour: {limits.max_adaptations_per_hour}")
                print(f"   ⚡ Min Time Between: {limits.min_time_between_adaptations.total_seconds()/60:.0f} minutes")
                print(f"   🎯 Confidence Threshold: {limits.min_confidence_threshold:.1f}")
                print(f"   📉 Performance Threshold: {limits.min_performance_threshold:.1%}")
                
                # Verify aggressive adaptation settings
                assert limits.max_adaptations_per_hour == 5, "Expected 5 adaptations/hour"
                assert limits.min_confidence_threshold == 0.5, "Expected 0.5 confidence threshold"
                print("   ✅ Adaptive settings configured for aggressive trading!")
            
            # Test 6: Test with real market data
            print("\nTest 6: Real Market Data Integration")
            if bot.data_manager:
                btc_data = await bot.data_manager.get_market_data('XBTUSD', limit=10)
                if not btc_data.empty:
                    latest_price = btc_data['close'].iloc[-1]
                    print(f"   📊 BTC Price: ${latest_price:,.2f}")
                    
                    # Calculate how much BTC we could buy with aggressive position
                    btc_amount = position_size_15pct / latest_price
                    print(f"   🪙 BTC Amount (15% position): {btc_amount:.6f} BTC")
                    print(f"   💰 USD Value: ${btc_amount * latest_price:,.2f}")
                    print("   ✅ Real market data integration working!")
                else:
                    print("   ❌ No market data received")
            
            print("\n🎉 AGGRESSIVE $480 CONFIGURATION TEST PASSED!")
            print("="*50)
            print("✅ Ready for aggressive trading with:")
            print(f"   💰 ${config.initial_capital:,.0f} starting capital")
            print(f"   📈 {config.max_risk_per_trade:.1%} risk per trade")
            print(f"   🎯 Up to {config.max_positions} positions")
            print(f"   ⚡ {limits.max_adaptations_per_hour} adaptations/hour max")
            print("   🚀 Real market data for learning")
            
        else:
            print("   ❌ Bot initialization failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error in aggressive config test: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main test function."""
    success = await test_aggressive_config()
    
    if success:
        print("\n🚀 READY TO START AGGRESSIVE TRADING!")
        print("Run: python3 run_adaptive_bot.py")
    else:
        print("\n❌ Configuration test failed - check errors above")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())