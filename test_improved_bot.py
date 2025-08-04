#!/usr/bin/env python3
"""
Test the improved adaptive bot with the fixes applied.
"""
import asyncio
import sys
import os
import signal
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.adaptive.adaptive_bot_main import AdaptiveBotMain

class BotTester:
    def __init__(self):
        self.bot = None
        self.start_time = None
        self.should_stop = False
        
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        print(f"\n🛑 Received signal {signum}, stopping bot...")
        self.should_stop = True
        
    async def test_bot(self, duration_minutes=5):
        """Test the bot for a specified duration."""
        print(f"🚀 Testing improved adaptive bot for {duration_minutes} minutes...")
        print("Press Ctrl+C to stop early\n")
        
        # Set up signal handler
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Create and initialize bot
            self.bot = AdaptiveBotMain()
            self.start_time = datetime.now()
            
            # Start the bot
            success = await self.bot.start()
            if not success:
                print("❌ Failed to start bot")
                return
            
            print("✅ Bot started successfully!")
            print("📊 Monitoring bot performance...\n")
            
            # Run for specified duration or until stopped
            end_time = time.time() + (duration_minutes * 60)
            cycle_count = 0
            
            while time.time() < end_time and not self.should_stop:
                try:
                    # Execute one trading cycle
                    await self.bot._execute_trading_cycle()
                    cycle_count += 1
                    
                    # Print progress every 10 cycles
                    if cycle_count % 10 == 0:
                        elapsed = datetime.now() - self.start_time
                        print(f"⏱️  Cycle #{cycle_count} completed - Elapsed: {elapsed}")
                        
                        # Check for any signals or adaptations
                        if hasattr(self.bot, 'adaptation_history'):
                            adaptations = len(self.bot.adaptation_history)
                            if adaptations > 0:
                                print(f"🎛️  Adaptations made: {adaptations}")
                    
                    # Sleep between cycles (1 minute intervals)
                    await asyncio.sleep(60)
                    
                except Exception as e:
                    print(f"❌ Error in trading cycle: {str(e)}")
                    await asyncio.sleep(5)
            
            # Print final summary
            elapsed = datetime.now() - self.start_time
            print(f"\n📊 Test Summary:")
            print(f"   Duration: {elapsed}")
            print(f"   Cycles completed: {cycle_count}")
            print(f"   Average cycle time: {elapsed.total_seconds() / max(cycle_count, 1):.1f} seconds")
            
            # Check bot health
            if hasattr(self.bot, 'health'):
                print(f"   Bot health: {self.bot.health.overall_status}")
                print(f"   Errors: {self.bot.health.error_count}")
                print(f"   Warnings: {self.bot.health.warning_count}")
            
            print("\n✅ Bot test completed successfully!")
            
        except Exception as e:
            print(f"❌ Error during bot test: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
        
        finally:
            # Clean shutdown
            if self.bot:
                print("🛑 Shutting down bot...")
                self.bot.shutdown_requested = True
                self.bot.is_running = False

async def main():
    """Main test function."""
    tester = BotTester()
    await tester.test_bot(duration_minutes=3)  # Test for 3 minutes

if __name__ == "__main__":
    asyncio.run(main())