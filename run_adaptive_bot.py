#!/usr/bin/env python3
"""
Run the Adaptive Trading Bot

This script properly initializes and runs the adaptive trading bot with
the correct configuration.
"""
import asyncio
import logging
from bot.adaptive.adaptive_bot_main import AdaptiveBotMain, AdaptiveBotConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Main function to run the adaptive bot."""
    
    # Create configuration
    config = AdaptiveBotConfig(
        trading_pairs=['XBTUSD', 'ETHUSD'],
        paper_trading=True,
        initial_capital=10000.0,
        adaptation_enabled=True
    )
    
    # Create and start the bot
    bot = AdaptiveBotMain(config)
    
    if await bot.start():
        print("🚀 Adaptive bot started successfully!")
        await bot.run_main_loop()
    else:
        print("❌ Failed to start adaptive bot")

if __name__ == "__main__":
    asyncio.run(main())