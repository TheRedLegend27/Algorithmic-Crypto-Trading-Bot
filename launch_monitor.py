#!/usr/bin/env python3
"""
Monitor Launcher - Choose the right monitoring tool for your needs.
"""
import os
import sys
import subprocess
from datetime import datetime


def print_banner():
    """Print banner."""
    print("🚀 CRYPTO TRADING MONITOR LAUNCHER 🚀")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def print_menu():
    """Print menu options."""
    print("\n📊 Choose your monitoring tool:")
    print()
    print("1. 📈 Market Dashboard")
    print("   └─ Real-time price, volume, and trend display")
    print("   └─ Visual market condition assessment")
    print("   └─ Best for: Quick market overview")
    print()
    print("2. 🚨 Trading Opportunity Alerts")
    print("   └─ Alerts when trading signals are detected")
    print("   └─ Strategy-based signal generation")
    print("   └─ Best for: Getting notified of trade opportunities")
    print()
    print("3. 🔍 Market Condition Monitor")
    print("   └─ Comprehensive market analysis")
    print("   └─ Volatility, volume, and momentum tracking")
    print("   └─ Best for: Detailed market condition analysis")
    print()
    print("4. 🎯 Start Paper Trading Bot")
    print("   └─ Run the enhanced Kraken bot in paper trading mode")
    print("   └─ Conservative settings for safe testing")
    print("   └─ Best for: Testing strategies with fake money")
    print()
    print("5. ⚡ Start Aggressive Paper Trading")
    print("   └─ More sensitive settings for active markets")
    print("   └─ Lower confidence thresholds")
    print("   └─ Best for: Active trading in volatile conditions")
    print()
    print("6. 🛠️  Debug Market Data")
    print("   └─ Check API connection and data quality")
    print("   └─ Test signal generation")
    print("   └─ Best for: Troubleshooting issues")
    print()
    print("0. ❌ Exit")


def run_command(command: list, description: str):
    """Run a command with description."""
    print(f"\n🚀 Starting: {description}")
    print(f"💻 Command: {' '.join(command)}")
    print("=" * 50)
    
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {description}: {e}")
    except KeyboardInterrupt:
        print(f"\n🛑 {description} stopped by user")
    except FileNotFoundError:
        print(f"❌ Python not found. Make sure Python 3 is installed.")


def main():
    """Main function."""
    print_banner()
    
    # Check if we have the required files
    required_files = [
        "market_dashboard.py",
        "trading_opportunity_alert.py", 
        "market_monitor.py",
        "run_enhanced_kraken_bot.py",
        "debug_market_data.py"
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        return 1
    
    # Check environment
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found")
        print("   Make sure you have KRAKEN_API_KEY and KRAKEN_API_SECRET set")
    
    while True:
        print_menu()
        
        try:
            choice = input("\n🎯 Enter your choice (0-6): ").strip()
            
            if choice == "0":
                print("👋 Goodbye!")
                break
                
            elif choice == "1":
                run_command(
                    ["python3", "market_dashboard.py"],
                    "Market Dashboard"
                )
                
            elif choice == "2":
                run_command(
                    ["python3", "trading_opportunity_alert.py"],
                    "Trading Opportunity Alerts"
                )
                
            elif choice == "3":
                run_command(
                    ["python3", "market_monitor.py"],
                    "Market Condition Monitor"
                )
                
            elif choice == "4":
                run_command(
                    ["python3", "run_enhanced_kraken_bot.py", 
                     "--paper-trading", "--confidence", "0.3", 
                     "--trade-amount", "10", "--max-trades", "10"],
                    "Conservative Paper Trading Bot"
                )
                
            elif choice == "5":
                run_command(
                    ["python3", "run_enhanced_kraken_bot.py",
                     "--paper-trading", "--confidence", "0.15",
                     "--trade-amount", "10", "--interval", "30", 
                     "--max-trades", "20"],
                    "Aggressive Paper Trading Bot"
                )
                
            elif choice == "6":
                print("\n🛠️  Debug Options:")
                print("1. Test API connection and market data")
                print("2. Test signal generation")
                
                debug_choice = input("Choose debug option (1-2): ").strip()
                
                if debug_choice == "1":
                    run_command(
                        ["python3", "debug_market_data.py"],
                        "Market Data Debug"
                    )
                elif debug_choice == "2":
                    run_command(
                        ["python3", "debug_signals.py"],
                        "Signal Generation Debug"
                    )
                else:
                    print("❌ Invalid debug option")
                    
            else:
                print("❌ Invalid choice. Please enter 0-6.")
                
        except KeyboardInterrupt:
            print(f"\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())