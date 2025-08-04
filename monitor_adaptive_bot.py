#!/usr/bin/env python3
"""
Simple monitoring script for the Adaptive Trading Bot.
Shows real-time status, trading activity, and performance.
"""
import time
import os
import json
from datetime import datetime
import subprocess

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_bot_status():
    """Check if the bot process is running."""
    try:
        result = subprocess.run(['pgrep', '-f', 'run_adaptive_bot.py'], 
                              capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except:
        return False

def get_recent_logs(lines=20):
    """Get recent log entries."""
    try:
        with open('adaptive_bot.log', 'r') as f:
            log_lines = f.readlines()
            return log_lines[-lines:] if log_lines else []
    except FileNotFoundError:
        return ["Log file not found. Bot may not be running."]

def parse_log_stats(log_lines):
    """Parse log lines to extract key statistics."""
    stats = {
        'cycles': 0,
        'signals': 0,
        'trades': 0,
        'errors': 0,
        'last_cycle': 'N/A',
        'regime': 'Unknown',
        'strategies_active': 0
    }
    
    for line in log_lines:
        if 'Cycle #' in line:
            stats['cycles'] += 1
            # Extract cycle info
            if '- ' in line:
                stats['last_cycle'] = line.split('- ')[-1].strip()
        elif 'signal' in line.lower() and 'generated' in line.lower():
            stats['signals'] += 1
        elif 'trade' in line.lower() and ('executed' in line.lower() or 'placed' in line.lower()):
            stats['trades'] += 1
        elif 'ERROR' in line:
            stats['errors'] += 1
        elif 'regime' in line.lower() and 'detected' in line.lower():
            # Try to extract regime type
            if 'BULLISH' in line:
                stats['regime'] = 'BULLISH'
            elif 'BEARISH' in line:
                stats['regime'] = 'BEARISH'
            elif 'NEUTRAL' in line:
                stats['regime'] = 'NEUTRAL'
        elif 'strategies' in line.lower() and 'initialized' in line.lower():
            # Extract number of strategies
            words = line.split()
            for i, word in enumerate(words):
                if word.isdigit() and i < len(words) - 1 and 'strategies' in words[i+1]:
                    stats['strategies_active'] = int(word)
    
    return stats

def display_dashboard():
    """Display the monitoring dashboard."""
    clear_screen()
    
    print("=" * 80)
    print("🤖 ADAPTIVE TRADING BOT MONITOR")
    print("=" * 80)
    print(f"📅 Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Bot Status
    bot_running = get_bot_status()
    status_icon = "🟢" if bot_running else "🔴"
    status_text = "RUNNING" if bot_running else "STOPPED"
    print(f"🤖 Bot Status: {status_icon} {status_text}")
    
    if not bot_running:
        print("\n❌ Bot is not running!")
        print("💡 To start the bot, run: python3 run_adaptive_bot.py")
        return
    
    # Get and parse logs
    recent_logs = get_recent_logs(50)
    stats = parse_log_stats(recent_logs)
    
    print("\n📊 TRADING STATISTICS")
    print("-" * 40)
    print(f"🔄 Trading Cycles: {stats['cycles']}")
    print(f"📈 Signals Generated: {stats['signals']}")
    print(f"💰 Trades Executed: {stats['trades']}")
    print(f"⚠️  Errors: {stats['errors']}")
    print(f"🎯 Active Strategies: {stats['strategies_active']}")
    print(f"📊 Market Regime: {stats['regime']}")
    print(f"⏰ Last Cycle: {stats['last_cycle']}")
    
    print("\n📋 RECENT ACTIVITY (Last 10 entries)")
    print("-" * 80)
    
    # Show recent log entries (filtered for important info)
    important_logs = []
    for line in recent_logs[-10:]:
        if any(keyword in line.lower() for keyword in 
               ['cycle', 'signal', 'trade', 'regime', 'error', 'warning']):
            # Clean up the log line
            if ' - ' in line:
                timestamp = line.split(' - ')[0]
                message = ' - '.join(line.split(' - ')[2:])  # Skip logger name
                important_logs.append(f"{timestamp[-8:]} | {message.strip()}")
    
    if important_logs:
        for log in important_logs:
            print(log)
    else:
        print("No recent trading activity...")
    
    print("\n" + "=" * 80)
    print("💡 Press Ctrl+C to exit monitor")
    print("🔄 Refreshing every 5 seconds...")

def main():
    """Main monitoring loop."""
    try:
        while True:
            display_dashboard()
            time.sleep(5)
    except KeyboardInterrupt:
        clear_screen()
        print("👋 Monitoring stopped. Bot continues running in background.")
        print("💡 To stop the bot: pkill -f run_adaptive_bot.py")

if __name__ == "__main__":
    main()