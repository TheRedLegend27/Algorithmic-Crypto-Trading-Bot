#!/usr/bin/env python3
"""
Debug script to test the trading cycle functionality.
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.adaptive.adaptive_bot_main import AdaptiveBotMain

async def test_trading_cycle():
    """Test the trading cycle functionality."""
    print("🔍 Testing trading cycle...")
    
    try:
        # Create bot instance
        bot = AdaptiveBotMain()
        
        # Initialize components
        print("📊 Initializing bot components...")
        success = await bot.initialize()
        
        if not success:
            print("❌ Failed to initialize bot")
            return
        
        print("✅ Bot initialized successfully")
        
        # Test single trading cycle
        print("🔄 Testing single trading cycle...")
        await bot._execute_trading_cycle()
        print("✅ Trading cycle completed")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_trading_cycle())