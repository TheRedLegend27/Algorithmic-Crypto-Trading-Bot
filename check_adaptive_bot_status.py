#!/usr/bin/env python3
"""
Adaptive Bot Status Checker
Monitor the adaptive bot's status and readiness for live trading.
"""
import os
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

def check_bot_process():
    """Check if the adaptive bot process is running."""
    try:
        result = subprocess.run(['pgrep', '-f', 'run_adaptive_bot'], 
                              capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except:
        return False

def get_recent_logs(lines=50):
    """Get recent log entries."""
    try:
        with open('adaptive_bot.log', 'r') as f:
            return f.readlines()[-lines:]
    except:
        return []

def check_trading_activity():
    """Check for recent trading activity in logs."""
    logs = get_recent_logs(100)
    trading_signals = []
    errors = []
    
    for line in logs:
        if any(keyword in line.lower() for keyword in ['signal', 'trade', 'order', 'buy', 'sell']):
            trading_signals.append(line.strip())
        if 'ERROR' in line:
            errors.append(line.strip())
    
    return trading_signals[-10:], errors[-5:]

def check_paper_trading_status():
    """Check if bot is in paper trading mode."""
    try:
        with open('.env', 'r') as f:
            content = f.read()
            return 'IS_PAPER_TRADING=True' in content
    except:
        return True

def check_api_credentials():
    """Check if API credentials are configured."""
    try:
        with open('.env', 'r') as f:
            content = f.read()
            has_key = 'KRAKEN_API_KEY=' in content and len(content.split('KRAKEN_API_KEY=')[1].split('\n')[0]) > 10
            has_secret = 'KRAKEN_API_SECRET=' in content and len(content.split('KRAKEN_API_SECRET=')[1].split('\n')[0]) > 10
            return has_key and has_secret
    except:
        return False

def get_bot_stats():
    """Extract bot statistics from logs."""
    logs = get_recent_logs(200)
    stats = {
        'cycles_completed': 0,
        'last_cycle_time': None,
        'trading_pairs': [],
        'initial_capital': None,
        'ml_confidence': None,
        'components_healthy': True
    }
    
    for line in logs:
        if 'Cycle #' in line:
            stats['cycles_completed'] += 1
            # Extract timestamp
            if ' - ' in line:
                time_part = line.split(' - ')[0].split(' ')[-1]
                stats['last_cycle_time'] = time_part
        
        if 'Trading pairs:' in line:
            pairs_part = line.split('Trading pairs: ')[1].strip()
            stats['trading_pairs'] = [p.strip() for p in pairs_part.split(',')]
        
        if 'Initial capital:' in line:
            capital_part = line.split('Initial capital: ')[1].strip()
            stats['initial_capital'] = capital_part
        
        if 'ML engine confidence:' in line:
            conf_part = line.split('ML engine confidence: ')[1].strip()
            try:
                stats['ml_confidence'] = float(conf_part)
            except:
                pass
        
        if 'ERROR' in line and 'component' in line.lower():
            stats['components_healthy'] = False
    
    return stats

def main():
    print("🤖 Adaptive Trading Bot Status Check")
    print("=" * 50)
    
    # Check if bot is running
    is_running = check_bot_process()
    print(f"📊 Bot Process: {'✅ Running' if is_running else '❌ Not Running'}")
    
    if not is_running:
        print("\n❌ Bot is not running. Start it with: python3 run_adaptive_bot.py")
        return
    
    # Check paper trading status
    is_paper = check_paper_trading_status()
    print(f"💰 Trading Mode: {'📝 Paper Trading' if is_paper else '💸 LIVE TRADING'}")
    
    # Check API credentials
    has_creds = check_api_credentials()
    print(f"🔑 API Credentials: {'✅ Configured' if has_creds else '❌ Missing'}")
    
    # Get bot statistics
    stats = get_bot_stats()
    print(f"\n📈 Bot Statistics:")
    print(f"   Cycles Completed: {stats['cycles_completed']}")
    print(f"   Last Cycle: {stats['last_cycle_time'] or 'Unknown'}")
    print(f"   Trading Pairs: {', '.join(stats['trading_pairs']) if stats['trading_pairs'] else 'Unknown'}")
    print(f"   Initial Capital: {stats['initial_capital'] or 'Unknown'}")
    print(f"   ML Confidence: {stats['ml_confidence'] if stats['ml_confidence'] is not None else 'Unknown'}")
    print(f"   Components: {'✅ Healthy' if stats['components_healthy'] else '❌ Issues Detected'}")
    
    # Check trading activity
    signals, errors = check_trading_activity()
    print(f"\n🎯 Recent Trading Activity:")
    if signals:
        print("   Recent Signals/Trades:")
        for signal in signals:
            print(f"   • {signal}")
    else:
        print("   • No recent trading signals detected")
    
    if errors:
        print(f"\n⚠️  Recent Errors:")
        for error in errors:
            print(f"   • {error}")
    
    # Readiness assessment
    print(f"\n🚀 Live Trading Readiness:")
    readiness_checks = [
        ("Bot is running", is_running),
        ("API credentials configured", has_creds),
        ("Components healthy", stats['components_healthy']),
        ("Cycles completing", stats['cycles_completed'] > 0),
        ("Trading pairs configured", len(stats['trading_pairs']) > 0)
    ]
    
    all_ready = True
    for check_name, passed in readiness_checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
        if not passed:
            all_ready = False
    
    if all_ready and is_paper:
        print(f"\n🎉 Bot is ready for live trading!")
        print(f"   To switch to live trading:")
        print(f"   1. Change IS_PAPER_TRADING=False in .env file")
        print(f"   2. Restart the bot: pkill -f run_adaptive_bot && python3 run_adaptive_bot.py")
        print(f"   ⚠️  WARNING: This will use real money!")
    elif all_ready and not is_paper:
        print(f"\n💸 Bot is running in LIVE TRADING mode!")
        print(f"   Monitor closely and check logs regularly.")
    else:
        print(f"\n⚠️  Bot needs attention before live trading.")
    
    print(f"\n📋 Monitoring Commands:")
    print(f"   • Watch logs: tail -f adaptive_bot.log")
    print(f"   • Check status: python3 check_adaptive_bot_status.py")
    print(f"   • Stop bot: pkill -f run_adaptive_bot")

if __name__ == "__main__":
    main()