#!/usr/bin/env python3
"""
Adaptive Bot Management Console
Central management interface for the adaptive trading bot.
"""
import os
import sys
import subprocess
import time
from datetime import datetime

class AdaptiveBotManager:
    def __init__(self):
        self.bot_script = "run_adaptive_bot.py"
        self.log_file = "adaptive_bot.log"
    
    def is_bot_running(self):
        """Check if the bot is currently running."""
        try:
            result = subprocess.run(['pgrep', '-f', self.bot_script], 
                                  capture_output=True, text=True)
            return len(result.stdout.strip()) > 0
        except:
            return False
    
    def start_bot(self):
        """Start the adaptive bot."""
        if self.is_bot_running():
            print("🤖 Bot is already running!")
            return False
        
        print("🚀 Starting adaptive bot...")
        try:
            subprocess.run([f"python3 {self.bot_script} > {self.log_file} 2>&1 &"], 
                         shell=True, check=True)
            time.sleep(3)
            
            if self.is_bot_running():
                print("✅ Bot started successfully!")
                return True
            else:
                print("❌ Failed to start bot - check logs")
                return False
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            return False
    
    def stop_bot(self):
        """Stop the adaptive bot."""
        if not self.is_bot_running():
            print("🤖 Bot is not running!")
            return False
        
        print("🛑 Stopping adaptive bot...")
        try:
            subprocess.run(['pkill', '-f', self.bot_script], check=True)
            time.sleep(2)
            
            if not self.is_bot_running():
                print("✅ Bot stopped successfully!")
                return True
            else:
                print("⚠️  Bot may still be running - check manually")
                return False
        except Exception as e:
            print(f"❌ Error stopping bot: {e}")
            return False
    
    def restart_bot(self):
        """Restart the adaptive bot."""
        print("🔄 Restarting adaptive bot...")
        self.stop_bot()
        time.sleep(2)
        return self.start_bot()
    
    def show_status(self):
        """Show current bot status."""
        print("📊 ADAPTIVE BOT STATUS")
        print("=" * 30)
        
        # Bot running status
        running = self.is_bot_running()
        print(f"🤖 Bot Status: {'✅ Running' if running else '❌ Stopped'}")
        
        if running:
            # Get recent log info
            try:
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                
                # Find last cycle
                last_cycle = None
                for line in reversed(lines):
                    if 'Cycle #' in line:
                        last_cycle = line.strip()
                        break
                
                # Find ML confidence
                ml_confidence = None
                for line in reversed(lines):
                    if 'ML engine confidence:' in line:
                        try:
                            conf_str = line.split('ML engine confidence: ')[1].strip()
                            ml_confidence = float(conf_str)
                            break
                        except:
                            pass
                
                # Find initial capital
                initial_capital = None
                for line in lines:
                    if 'Initial capital:' in line:
                        initial_capital = line.split('Initial capital: ')[1].strip()
                        break
                
                print(f"💰 Capital: {initial_capital or 'Unknown'}")
                print(f"🧠 ML Confidence: {ml_confidence:.3f}" if ml_confidence is not None else "🧠 ML Confidence: Unknown")
                print(f"🔄 Last Activity: {last_cycle.split(' - ')[-1] if last_cycle else 'Unknown'}")
                
            except Exception as e:
                print(f"⚠️  Could not read log file: {e}")
        
        # Trading mode
        try:
            with open('.env', 'r') as f:
                env_content = f.read()
            is_paper = 'IS_PAPER_TRADING=True' in env_content
            print(f"📝 Trading Mode: {'Paper Trading' if is_paper else '💸 LIVE TRADING'}")
        except:
            print(f"📝 Trading Mode: Unknown")
    
    def show_logs(self, lines=20):
        """Show recent log entries."""
        print(f"📋 RECENT LOGS (last {lines} lines)")
        print("=" * 40)
        
        try:
            result = subprocess.run(['tail', f'-{lines}', self.log_file], 
                                  capture_output=True, text=True)
            print(result.stdout)
        except Exception as e:
            print(f"❌ Could not read logs: {e}")
    
    def switch_trading_mode(self):
        """Switch between paper and live trading."""
        try:
            with open('.env', 'r') as f:
                content = f.read()
        except:
            print("❌ Could not read .env file")
            return
        
        is_paper = 'IS_PAPER_TRADING=True' in content
        
        print(f"Current mode: {'Paper Trading' if is_paper else 'LIVE TRADING'}")
        
        if is_paper:
            print("⚠️  WARNING: Switching to LIVE TRADING will use real money!")
            confirm = input("Type 'CONFIRM' to switch to live trading: ")
            if confirm != 'CONFIRM':
                print("❌ Operation cancelled")
                return
            
            new_content = content.replace('IS_PAPER_TRADING=True', 'IS_PAPER_TRADING=False')
            mode_name = "LIVE TRADING"
        else:
            new_content = content.replace('IS_PAPER_TRADING=False', 'IS_PAPER_TRADING=True')
            mode_name = "Paper Trading"
        
        try:
            with open('.env', 'w') as f:
                f.write(new_content)
            
            print(f"✅ Switched to {mode_name}")
            
            if self.is_bot_running():
                print("🔄 Restarting bot to apply changes...")
                self.restart_bot()
            
        except Exception as e:
            print(f"❌ Error updating .env file: {e}")
    
    def run_diagnostics(self):
        """Run comprehensive diagnostics."""
        print("🔧 Running diagnostics...")
        
        # Check if monitoring scripts exist
        scripts = [
            ('check_adaptive_bot_status.py', 'Basic Status Check'),
            ('monitor_learning_progress.py', 'Learning Progress Monitor'),
            ('optimize_bot_performance.py', 'Performance Optimizer'),
            ('trading_readiness_checker.py', 'Trading Readiness Assessment'),
            ('watch_bot_learning.py', 'Real-time Monitor')
        ]
        
        print("\n📋 Available Tools:")
        for script, description in scripts:
            exists = os.path.exists(script)
            print(f"   {'✅' if exists else '❌'} {description}: {script}")
        
        print("\n🔍 Quick Diagnostics:")
        
        # Check log file
        if os.path.exists(self.log_file):
            size = os.path.getsize(self.log_file)
            print(f"   ✅ Log file exists ({size} bytes)")
        else:
            print(f"   ❌ Log file missing")
        
        # Check .env file
        if os.path.exists('.env'):
            print(f"   ✅ Configuration file exists")
        else:
            print(f"   ❌ Configuration file missing")
        
        # Check bot process
        running = self.is_bot_running()
        print(f"   {'✅' if running else '❌'} Bot process {'running' if running else 'stopped'}")
    
    def show_menu(self):
        """Show the main menu."""
        print("\n🤖 ADAPTIVE BOT MANAGEMENT CONSOLE")
        print("=" * 40)
        print("1. 📊 Show Status")
        print("2. 🚀 Start Bot")
        print("3. 🛑 Stop Bot")
        print("4. 🔄 Restart Bot")
        print("5. 📋 Show Recent Logs")
        print("6. 🔧 Run Diagnostics")
        print("7. 💰 Switch Trading Mode")
        print("8. 📈 Monitor Learning Progress")
        print("9. 🎯 Check Trading Readiness")
        print("10. ⚡ Optimize Performance")
        print("11. 👁️  Watch Real-time")
        print("0. 🚪 Exit")
        print("-" * 40)
    
    def run_external_script(self, script_name, description):
        """Run an external monitoring script."""
        if not os.path.exists(script_name):
            print(f"❌ {script_name} not found")
            return
        
        print(f"🔍 Running {description}...")
        try:
            subprocess.run(['python3', script_name])
        except KeyboardInterrupt:
            print(f"\n⏹️  {description} interrupted")
        except Exception as e:
            print(f"❌ Error running {script_name}: {e}")
    
    def main_loop(self):
        """Main interactive loop."""
        while True:
            try:
                self.show_menu()
                choice = input("\nSelect option (0-11): ").strip()
                
                if choice == '0':
                    print("👋 Goodbye!")
                    break
                elif choice == '1':
                    self.show_status()
                elif choice == '2':
                    self.start_bot()
                elif choice == '3':
                    self.stop_bot()
                elif choice == '4':
                    self.restart_bot()
                elif choice == '5':
                    lines = input("Number of log lines to show (default 20): ").strip()
                    lines = int(lines) if lines.isdigit() else 20
                    self.show_logs(lines)
                elif choice == '6':
                    self.run_diagnostics()
                elif choice == '7':
                    self.switch_trading_mode()
                elif choice == '8':
                    self.run_external_script('monitor_learning_progress.py', 'Learning Progress Monitor')
                elif choice == '9':
                    self.run_external_script('trading_readiness_checker.py', 'Trading Readiness Assessment')
                elif choice == '10':
                    self.run_external_script('optimize_bot_performance.py', 'Performance Optimizer')
                elif choice == '11':
                    self.run_external_script('watch_bot_learning.py', 'Real-time Monitor')
                else:
                    print("❌ Invalid option. Please try again.")
                
                if choice != '0':
                    input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                input("Press Enter to continue...")

def main():
    if len(sys.argv) > 1:
        # Command line mode
        manager = AdaptiveBotManager()
        command = sys.argv[1].lower()
        
        if command == 'start':
            manager.start_bot()
        elif command == 'stop':
            manager.stop_bot()
        elif command == 'restart':
            manager.restart_bot()
        elif command == 'status':
            manager.show_status()
        elif command == 'logs':
            lines = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 20
            manager.show_logs(lines)
        else:
            print("Usage: python3 manage_adaptive_bot.py [start|stop|restart|status|logs]")
    else:
        # Interactive mode
        manager = AdaptiveBotManager()
        manager.main_loop()

if __name__ == "__main__":
    main()