#!/usr/bin/env python3
"""
Continuous Bot Operation Manager
Ensures the bot runs continuously with automatic restart on failure.
"""
import subprocess
import time
import signal
import sys
import os
from datetime import datetime

class BotManager:
    def __init__(self):
        self.bot_process = None
        self.running = True
        self.restart_count = 0
        self.max_restarts = 10
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.running = False
        if self.bot_process:
            self.bot_process.terminate()
            self.bot_process.wait()
        sys.exit(0)
    
    def start_bot(self):
        """Start the adaptive bot process."""
        try:
            print(f"🚀 Starting adaptive bot (attempt {self.restart_count + 1})...")
            self.bot_process = subprocess.Popen(
                [sys.executable, 'run_adaptive_bot.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            return False
    
    def monitor_bot(self):
        """Monitor bot process and restart if needed."""
        while self.running:
            if self.bot_process is None:
                if not self.start_bot():
                    time.sleep(30)
                    continue
            
            # Check if process is still running
            poll_result = self.bot_process.poll()
            
            if poll_result is not None:
                # Process has terminated
                print(f"⚠️ Bot process terminated with code {poll_result}")
                
                if self.restart_count < self.max_restarts:
                    self.restart_count += 1
                    print(f"🔄 Restarting bot (attempt {self.restart_count}/{self.max_restarts})...")
                    time.sleep(10)  # Wait before restart
                    self.bot_process = None
                else:
                    print(f"❌ Maximum restart attempts reached. Stopping.")
                    self.running = False
                    break
            else:
                # Process is running, check periodically
                time.sleep(60)  # Check every minute
    
    def run(self):
        """Run the bot manager."""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("🤖 Adaptive Bot Continuous Operation Manager")
        print("=" * 50)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Press Ctrl+C to stop")
        print()
        
        self.monitor_bot()

if __name__ == "__main__":
    manager = BotManager()
    manager.run()
