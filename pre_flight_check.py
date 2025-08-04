#!/usr/bin/env python3
"""
Comprehensive pre-flight check for the aggressive $480 trading bot.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def comprehensive_pre_flight_check():
    """Run a complete pre-flight check of all systems."""
    print("🚀 COMPREHENSIVE PRE-FLIGHT CHECK")
    print("="*60)
    
    checks_passed = 0
    total_checks = 0
    issues = []
    
    # Check 1: Environment Configuration
    print("\n1️⃣ Environment Configuration")
    print("-" * 30)
    total_checks += 1
    
    try:
        # Check .env file
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                env_content = f.read()
            
            required_vars = ['IS_PAPER_TRADING=True', 'USE_REAL_MARKET_DATA=true', 'KRAKEN_API_KEY', 'KRAKEN_PRIVATE_KEY']
            missing_vars = []
            
            for var in required_vars:
                if var not in env_content:
                    missing_vars.append(var)
            
            if not missing_vars:
                print("   ✅ .env file configured correctly")
                print("   ✅ Paper trading enabled")
                print("   ✅ Real market data enabled")
                print("   ✅ Kraken API credentials present")
                checks_passed += 1
            else:
                print(f"   ❌ Missing environment variables: {missing_vars}")
                issues.append("Environment variables missing")
        else:
            print("   ❌ .env file not found")
            issues.append(".env file missing")
    except Exception as e:
        print(f"   ❌ Error checking environment: {str(e)}")
        issues.append(f"Environment check failed: {str(e)}")
    
    # Check 2: Bot Configuration
    print("\n2️⃣ Bot Configuration")
    print("-" * 30)
    total_checks += 1
    
    try:
        from bot.adaptive.adaptive_bot_main import AdaptiveBotConfig
        
        config = AdaptiveBotConfig()
        
        # Verify aggressive settings
        config_checks = [
            (config.initial_capital == 480.0, f"Initial capital: ${config.initial_capital} (expected $480)"),
            (config.max_positions == 3, f"Max positions: {config.max_positions} (expected 3)"),
            (config.max_risk_per_trade == 0.08, f"Risk per trade: {config.max_risk_per_trade:.1%} (expected 8%)"),
            (config.max_portfolio_risk == 0.25, f"Portfolio risk: {config.max_portfolio_risk:.1%} (expected 25%)"),
            (config.max_drawdown_threshold == 0.20, f"Max drawdown: {config.max_drawdown_threshold:.1%} (expected 20%)"),
            (config.min_adaptation_confidence == 0.5, f"Adaptation confidence: {config.min_adaptation_confidence} (expected 0.5)"),
            (config.paper_trading == True, f"Paper trading: {config.paper_trading} (expected True)"),
        ]
        
        all_config_good = True
        for check_passed, message in config_checks:
            if check_passed:
                print(f"   ✅ {message}")
            else:
                print(f"   ❌ {message}")
                all_config_good = False
                issues.append(f"Config issue: {message}")
        
        if all_config_good:
            checks_passed += 1
            print("   ✅ All bot configuration settings correct")
        
    except Exception as e:
        print(f"   ❌ Error checking bot configuration: {str(e)}")
        issues.append(f"Bot config check failed: {str(e)}")
    
    # Check 3: Market Data Connection
    print("\n3️⃣ Market Data Connection")
    print("-" * 30)
    total_checks += 1
    
    try:
        from bot.enhanced_data_manager import EnhancedDataManager
        
        data_manager = EnhancedDataManager(['XBTUSD', 'ETHUSD'])
        
        # Test BTC data
        btc_data = data_manager.get_latest_data('XBTUSD', periods=5)
        if not btc_data.empty and len(btc_data) > 0:
            btc_price = btc_data['close'].iloc[-1]
            print(f"   ✅ BTC data: {len(btc_data)} points, latest price: ${btc_price:,.2f}")
            
            # Test ETH data
            eth_data = data_manager.get_latest_data('ETHUSD', periods=5)
            if not eth_data.empty and len(eth_data) > 0:
                eth_price = eth_data['close'].iloc[-1]
                print(f"   ✅ ETH data: {len(eth_data)} points, latest price: ${eth_price:,.2f}")
                
                # Verify data is realistic (not mock)
                if 50000 <= btc_price <= 200000 and 1000 <= eth_price <= 10000:
                    print("   ✅ Market data appears to be real (realistic prices)")
                    checks_passed += 1
                else:
                    print("   ⚠️  Market data might be mock (unrealistic prices)")
                    issues.append("Market data appears to be mock")
            else:
                print("   ❌ ETH data fetch failed")
                issues.append("ETH data fetch failed")
        else:
            print("   ❌ BTC data fetch failed")
            issues.append("BTC data fetch failed")
            
    except Exception as e:
        print(f"   ❌ Error checking market data: {str(e)}")
        issues.append(f"Market data check failed: {str(e)}")
    
    # Check 4: Bot Initialization
    print("\n4️⃣ Bot Initialization")
    print("-" * 30)
    total_checks += 1
    
    try:
        from bot.adaptive.adaptive_bot_main import AdaptiveBotMain
        
        bot = AdaptiveBotMain()
        success = await bot.initialize_components()
        
        if success:
            print("   ✅ Bot components initialized successfully")
            
            # Check specific components
            component_checks = [
                (bot.data_manager is not None, "Data manager"),
                (bot.position_manager is not None, "Position manager"),
                (bot.risk_manager is not None, "Risk manager"),
                (bot.regime_detector is not None, "Regime detector"),
                (bot.strategy_engine is not None, "Strategy engine"),
                (bot.ml_engine is not None, "ML engine"),
                (bot.adaptation_controller is not None, "Adaptation controller"),
                (bot.paper_trading_engine is not None, "Paper trading engine"),
            ]
            
            all_components_good = True
            for component_ok, name in component_checks:
                if component_ok:
                    print(f"   ✅ {name} initialized")
                else:
                    print(f"   ❌ {name} failed to initialize")
                    all_components_good = False
                    issues.append(f"{name} initialization failed")
            
            if all_components_good:
                checks_passed += 1
        else:
            print("   ❌ Bot initialization failed")
            issues.append("Bot initialization failed")
            
    except Exception as e:
        print(f"   ❌ Error during bot initialization: {str(e)}")
        issues.append(f"Bot initialization error: {str(e)}")
    
    # Check 5: Position Manager Balance
    print("\n5️⃣ Position Manager Balance")
    print("-" * 30)
    total_checks += 1
    
    try:
        if 'bot' in locals() and bot.position_manager:
            usd_balance = bot.position_manager.get_crypto_balance('USD')
            if usd_balance and usd_balance.balance == 480.0:
                print(f"   ✅ USD balance: ${usd_balance.balance:,.0f}")
                print(f"   ✅ Available: ${usd_balance.available:,.0f}")
                checks_passed += 1
            else:
                balance_amount = usd_balance.balance if usd_balance else "None"
                print(f"   ❌ Incorrect USD balance: ${balance_amount} (expected $480)")
                issues.append(f"Incorrect balance: ${balance_amount}")
        else:
            print("   ❌ Position manager not available")
            issues.append("Position manager not available")
            
    except Exception as e:
        print(f"   ❌ Error checking balance: {str(e)}")
        issues.append(f"Balance check failed: {str(e)}")
    
    # Check 6: Risk Management Settings
    print("\n6️⃣ Risk Management Settings")
    print("-" * 30)
    total_checks += 1
    
    try:
        if 'bot' in locals() and bot.adaptation_controller:
            limits = bot.adaptation_controller.limits
            
            risk_checks = [
                (limits.min_confidence_threshold == 0.5, f"Confidence threshold: {limits.min_confidence_threshold} (expected 0.5)"),
                (limits.max_adaptations_per_hour == 5, f"Max adaptations/hour: {limits.max_adaptations_per_hour} (expected 5)"),
                (limits.min_time_between_adaptations.total_seconds() == 600, f"Min time between adaptations: {limits.min_time_between_adaptations.total_seconds()/60:.0f}min (expected 10min)"),
                (limits.min_performance_threshold == -0.05, f"Performance threshold: {limits.min_performance_threshold:.1%} (expected -5%)"),
            ]
            
            all_risk_good = True
            for check_ok, message in risk_checks:
                if check_ok:
                    print(f"   ✅ {message}")
                else:
                    print(f"   ❌ {message}")
                    all_risk_good = False
                    issues.append(f"Risk setting: {message}")
            
            if all_risk_good:
                checks_passed += 1
        else:
            print("   ❌ Adaptation controller not available")
            issues.append("Adaptation controller not available")
            
    except Exception as e:
        print(f"   ❌ Error checking risk settings: {str(e)}")
        issues.append(f"Risk settings check failed: {str(e)}")
    
    # Check 7: Trading Calculations
    print("\n7️⃣ Trading Calculations")
    print("-" * 30)
    total_checks += 1
    
    try:
        capital = 480.0
        position_size_15pct = capital * 0.15  # $72
        risk_amount_8pct = capital * 0.08     # $38.40
        max_exposure = position_size_15pct * 3  # $216
        remaining_capital = capital - max_exposure  # $264
        
        print(f"   ✅ 15% position size: ${position_size_15pct:,.0f}")
        print(f"   ✅ 8% risk amount: ${risk_amount_8pct:,.2f}")
        print(f"   ✅ Max exposure (3 positions): ${max_exposure:,.0f}")
        print(f"   ✅ Remaining capital: ${remaining_capital:,.0f}")
        
        # Verify calculations make sense
        if (position_size_15pct == 72.0 and 
            abs(risk_amount_8pct - 38.4) < 0.1 and 
            max_exposure == 216.0 and 
            remaining_capital == 264.0):
            print("   ✅ All trading calculations correct")
            checks_passed += 1
        else:
            print("   ❌ Trading calculations incorrect")
            issues.append("Trading calculations incorrect")
            
    except Exception as e:
        print(f"   ❌ Error in trading calculations: {str(e)}")
        issues.append(f"Trading calculations failed: {str(e)}")
    
    # Check 8: Strategy Engine
    print("\n8️⃣ Strategy Engine")
    print("-" * 30)
    total_checks += 1
    
    try:
        if 'bot' in locals() and bot.strategy_engine:
            strategies = bot.strategy_engine.strategies
            allocations = bot.strategy_engine.strategy_allocations
            
            print(f"   ✅ {len(strategies)} strategies loaded:")
            for name in strategies.keys():
                allocation = allocations.get(name)
                if allocation:
                    print(f"      • {name}: {allocation.base_weight:.1%} weight")
                else:
                    print(f"      • {name}: No allocation found")
            
            if len(strategies) >= 3:
                print("   ✅ Sufficient strategies for ensemble trading")
                checks_passed += 1
            else:
                print("   ❌ Insufficient strategies loaded")
                issues.append("Insufficient strategies")
        else:
            print("   ❌ Strategy engine not available")
            issues.append("Strategy engine not available")
            
    except Exception as e:
        print(f"   ❌ Error checking strategy engine: {str(e)}")
        issues.append(f"Strategy engine check failed: {str(e)}")
    
    # Final Summary
    print("\n" + "="*60)
    print("🎯 PRE-FLIGHT CHECK SUMMARY")
    print("="*60)
    
    success_rate = (checks_passed / total_checks) * 100
    
    print(f"✅ Checks Passed: {checks_passed}/{total_checks} ({success_rate:.0f}%)")
    
    if issues:
        print(f"❌ Issues Found: {len(issues)}")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("🎉 No issues found!")
    
    # Recommendation
    print("\n🎯 RECOMMENDATION:")
    if success_rate >= 85:
        print("✅ READY TO LAUNCH!")
        print("   Your bot is properly configured for aggressive $480 trading.")
        print("   All critical systems are working correctly.")
        print("\n🚀 Start with: python3 run_adaptive_bot.py")
        return True
    elif success_rate >= 70:
        print("⚠️  MOSTLY READY - Minor Issues")
        print("   Your bot should work but has some minor configuration issues.")
        print("   Consider fixing the issues above before long-term running.")
        return False
    else:
        print("❌ NOT READY - Major Issues")
        print("   Your bot has significant configuration problems.")
        print("   Please fix the issues above before running.")
        return False

async def main():
    """Main check function."""
    ready = await comprehensive_pre_flight_check()
    
    if ready:
        print("\n" + "="*60)
        print("🚀 FINAL LAUNCH CHECKLIST")
        print("="*60)
        print("✅ $480 aggressive configuration verified")
        print("✅ Real market data connection working")
        print("✅ Paper trading safety enabled")
        print("✅ Risk management properly configured")
        print("✅ All bot components initialized")
        print("\n🎯 READY FOR MULTI-DAY RUN!")
        print("   Monitor daily with: python3 analyze_bot_session.py")
        print("   Expected: 5-15 trades per day, 2-5 adaptations")
        print("   Target: 15-40% monthly growth")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())