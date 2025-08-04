#!/usr/bin/env python3
"""
Real-time Bot Learning Watcher
Continuously monitor the bot's learning progress with live updates.
"""
import os
import time
import subprocess
from datetime import datetime
import sys

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_bot_status():
    """Get current bot status."""
    try:
        result = subprocess.run(['pgrep', '-f', 'run_adaptive_bot'], 
                              capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except:
        return False

def get_latest_logs(lines=20):
    """Get the latest log lines."""
    try:
        with open('adaptive_bot.log', 'r') as f:
            return f.readlines()[-lines:]
    except:
        return []

def extract_key_metrics(logs):
    """Extract key metrics from recent logs."""
    metrics = {
        'last_cycle': None,
        'ml_confidence': None,
        'signals': 0,
        'errors': 0,
        'regime': None
    }
    
    for line in logs:
        if 'Cycle #' in line:
            try:
                cycle_num = line.split('Cycle #')[1].split(' ')[0]
                time_part = line.split(' - ')[-1].strip()
                metrics['last_cycle'] = f"#{cycle_num} at {time_part}"
            except:
                pass
        
        if 'ML engine confidence:' in line:
            try:
                conf_str = line.split('ML engine confidence: ')[1].strip()
                metrics['ml_confidence'] = float(conf_str)
            except:
                pass
        
        if any(keyword in line.lower() for keyword in ['signal', 'buy', 'sell', 'trade']):
            if 'no signal' not in line.lower():
                metrics['signals'] += 1
        
        if 'ERROR' in line:
            metrics['errors'] += 1
        
        if 'regime' in line.lower() and 'detected' in line.lower():
            try:
                regime_part = line.split('regime')[1].split()[0]
                metrics['regime'] = regime_part
            except:
                pass
    
    return metrics

def main():
    print("🤖 Starting Real-time Bot Learning Monitor...")
    print("Press Ctrl+C to exit")
    time.sleep(2)
    
    try:
        while True:
            clear_screen()
            
            # Header
            print("🧠 ADAPTIVE BOT LEARNING MONITOR")
            print("=" * 50)
            print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            # Bot status
            bot_running = get_bot_status()
            status_icon = "✅" if bot_running else "❌"
            print(f"🤖 Bot Status: {status_icon} {'Running' if bot_running else 'Not Running'}")
            
            if not bot_running:
                print("\n❌ Bot is not running!")
                print("Start it with: python3 run_adaptive_bot.py")
                time.sleep(5)
                continue
            
            # Get recent logs and metrics
            logs = get_latest_logs(50)
            metrics = extract_key_metrics(logs)
            
            # Display key metrics
            print(f"\n📊 Key Metrics:")
            print(f"   Last Cycle: {metrics['last_cycle'] or 'Unknown'}")
            
            if metrics['ml_confidence'] is not None:
                conf_status = "🟢" if metrics['ml_confidence'] > 0.5 else "🟡" if metrics['ml_confidence'] > 0.2 else "🔴"
                print(f"   ML Confidence: {conf_status} {metrics['ml_confidence']:.3f}")
            else:
                print(f"   ML Confidence: ⚪ Not available")
            
            print(f"   Trading Signals: {metrics['signals']}")
            print(f"   Recent Errors: {metrics['errors']}")
            
            if metrics['regime']:
                print(f"   Market Regime: {metrics['regime']}")
            
            # Learning phase indicator
            print(f"\n🎓 Learning Phase:")
            if metrics['ml_confidence'] is None:
                print(f"   📚 Initial data collection")
            elif metrics['ml_confidence'] < 0.1:
                print(f"   🔍 Building initial understanding")
            elif metrics['ml_confidence'] < 0.3:
                print(f"   📈 Developing confidence")
            elif metrics['ml_confidence'] < 0.6:
                print(f"   🎯 Active learning and trading")
            else:
                print(f"   🚀 High confidence trading")
            
            # Recent activity
            print(f"\n📝 Recent Activity (last 10 lines):")
            recent_logs = logs[-10:]
            for line in recent_logs:
                # Clean up the line for display
                if ' - ' in line:
                    parts = line.split(' - ')
                    if len(parts) >= 3:
                        timestamp = parts[0].split()[-1]  # Just the time part
                        message = ' - '.join(parts[2:]).strip()
                        
                        # Color code different types of messages
                        if 'ERROR' in line:
                            icon = "❌"
                        elif 'WARNING' in line:
                            icon = "⚠️ "
                        elif 'Cycle #' in line:
                            icon = "🔄"
                        elif 'confidence' in line.lower():
                            icon = "🧠"
                        elif 'signal' in line.lower():
                            icon = "📈"
                        else:
                            icon = "ℹ️ "
                        
                        # Truncate long messages
                        if len(message) > 60:
                            message = message[:57] + "..."
                        
                        print(f"   {icon} {timestamp} {message}")
            
            # Instructions
            print(f"\n💡 Commands:")
            print(f"   • Detailed analysis: python3 monitor_learning_progress.py")
            print(f"   • Bot status: python3 check_adaptive_bot_status.py")
            print(f"   • Stop bot: pkill -f run_adaptive_bot")
            print(f"   • Press Ctrl+C to exit this monitor")
            
            # Wait before next update
            time.sleep(10)
            
    except KeyboardInterrupt:
        print(f"\n\n👋 Monitoring stopped. Bot continues running in background.")
        print(f"Use 'python3 check_adaptive_bot_status.py' to check status anytime.")

if __name__ == "__main__":
    main()