#!/usr/bin/env python3
"""
Daily monitoring script for the aggressive $480 trading bot.
Run this once per day to track progress and performance.
"""
import sys
import os
import json
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def daily_monitoring_report():
    """Generate a comprehensive daily monitoring report."""
    print("📊 DAILY BOT MONITORING REPORT")
    print("="*50)
    print(f"📅 Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Session Analysis
    print("\n1️⃣ SESSION ANALYSIS")
    print("-" * 30)
    
    try:
        # Run the session analyzer
        os.system("python3 analyze_bot_session.py > temp_session_report.txt")
        
        # Read and parse the results
        if os.path.exists("temp_session_report.txt"):
            with open("temp_session_report.txt", "r") as f:
                session_report = f.read()
            
            # Extract key metrics
            if "Duration:" in session_report:
                print("✅ Session data found")
                
                # Extract duration
                duration_line = [line for line in session_report.split('\n') if 'Duration:' in line]
                if duration_line:
                    print(f"   {duration_line[0].strip()}")
                
                # Extract cycles
                cycles_line = [line for line in session_report.split('\n') if 'Total Cycles:' in line]
                if cycles_line:
                    print(f"   {cycles_line[0].strip()}")
                
                # Extract ML confidence
                ml_line = [line for line in session_report.split('\n') if 'ML confidence' in line]
                if ml_line:
                    print(f"   {ml_line[0].strip()}")
                
                # Extract performance score
                score_line = [line for line in session_report.split('\n') if 'Performance Score:' in line]
                if score_line:
                    print(f"   {score_line[0].strip()}")
            else:
                print("⚠️  No recent session data found")
            
            # Clean up
            os.remove("temp_session_report.txt")
        else:
            print("❌ Could not generate session report")
    
    except Exception as e:
        print(f"❌ Error in session analysis: {str(e)}")
    
    # 2. Log Analysis
    print("\n2️⃣ LOG ANALYSIS")
    print("-" * 30)
    
    try:
        # Check bot log files (try bot.log first, then adaptive_bot.log)
        log_file = None
        if os.path.exists("bot.log"):
            log_file = "bot.log"
        elif os.path.exists("adaptive_bot.log"):
            log_file = "adaptive_bot.log"
        
        if log_file:
            with open(log_file, "r") as f:
                log_lines = f.readlines()
            
            # Get today's log entries (filter by today's date)
            today_str = datetime.now().strftime('%Y-%m-%d')
            recent_logs = [line for line in log_lines if today_str in line]
            
            # If no today's logs, get last 500 lines for analysis
            if not recent_logs:
                recent_logs = log_lines[-500:] if len(log_lines) > 500 else log_lines
            
            # Count different types of events
            events = {
                'trades': 0,
                'adaptations': 0,
                'errors': 0,
                'warnings': 0,
                'signals': 0,
                'cycles': 0
            }
            
            for line in recent_logs:
                if 'executed' in line.lower() and ('buy' in line.lower() or 'sell' in line.lower()):
                    events['trades'] += 1
                elif 'adaptation' in line.lower():
                    events['adaptations'] += 1
                elif 'ERROR' in line:
                    events['errors'] += 1
                elif 'WARNING' in line:
                    events['warnings'] += 1
                elif 'signal' in line.lower() and 'generated' in line.lower():
                    events['signals'] += 1
                elif 'Cycle #' in line:
                    events['cycles'] += 1
            
            print(f"   🔄 Total Cycles: {events['cycles']}")
            print(f"   📈 Recent Trades: {events['trades']}")
            print(f"   🎛️ Adaptations: {events['adaptations']}")
            print(f"   🎯 Signals Generated: {events['signals']}")
            print(f"   ⚠️  Warnings: {events['warnings']}")
            print(f"   ❌ Errors: {events['errors']}")
            
            # Show last few important log entries
            important_logs = [line for line in recent_logs[-20:] 
                            if any(keyword in line.lower() for keyword in 
                                 ['executed', 'adaptation', 'signal', 'error'])]
            
            if important_logs:
                print("\n   📋 Recent Important Events:")
                for log in important_logs[-5:]:  # Last 5 important events
                    timestamp = log.split(' - ')[0] if ' - ' in log else "Unknown"
                    message = log.split(' - ')[-1].strip() if ' - ' in log else log.strip()
                    print(f"      {timestamp}: {message[:80]}...")
        else:
            print("⚠️  No bot log files found (checked bot.log and adaptive_bot.log)")
    
    except Exception as e:
        print(f"❌ Error in log analysis: {str(e)}")
    
    # 3. Performance Tracking
    print("\n3️⃣ PERFORMANCE TRACKING")
    print("-" * 30)
    
    try:
        # Create or update performance tracking file
        perf_file = "daily_performance_tracking.json"
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Load existing data
        if os.path.exists(perf_file):
            with open(perf_file, 'r') as f:
                perf_data = json.load(f)
        else:
            perf_data = {"start_date": today, "daily_records": {}}
        
        # Add today's record
        perf_data["daily_records"][today] = {
            "date": today,
            "trades": events.get('trades', 0),
            "adaptations": events.get('adaptations', 0),
            "signals": events.get('signals', 0),
            "errors": events.get('errors', 0),
            "warnings": events.get('warnings', 0),
            "capital": 480.0,  # Starting capital (would be updated with actual performance)
            "notes": "Aggressive $480 configuration"
        }
        
        # Save updated data
        with open(perf_file, 'w') as f:
            json.dump(perf_data, f, indent=2)
        
        # Show performance summary
        total_days = len(perf_data["daily_records"])
        total_trades = sum(day["trades"] for day in perf_data["daily_records"].values())
        total_adaptations = sum(day["adaptations"] for day in perf_data["daily_records"].values())
        
        print(f"   📊 Total Days Tracked: {total_days}")
        print(f"   📈 Total Trades: {total_trades}")
        print(f"   🎛️ Total Adaptations: {total_adaptations}")
        print(f"   📊 Avg Trades/Day: {total_trades/max(total_days,1):.1f}")
        print(f"   🎛️ Avg Adaptations/Day: {total_adaptations/max(total_days,1):.1f}")
        
        # Show trend
        if total_days >= 3:
            recent_days = list(perf_data["daily_records"].values())[-3:]
            recent_trades = sum(day["trades"] for day in recent_days)
            recent_adaptations = sum(day["adaptations"] for day in recent_days)
            
            print(f"\n   📈 Last 3 Days:")
            print(f"      Trades: {recent_trades} ({recent_trades/3:.1f}/day)")
            print(f"      Adaptations: {recent_adaptations} ({recent_adaptations/3:.1f}/day)")
    
    except Exception as e:
        print(f"❌ Error in performance tracking: {str(e)}")
    
    # 4. Health Check
    print("\n4️⃣ SYSTEM HEALTH")
    print("-" * 30)
    
    try:
        # Check if bot is currently running
        import psutil
        
        bot_running = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any('run_adaptive_bot.py' in cmd for cmd in proc.info['cmdline']):
                    bot_running = True
                    print(f"   ✅ Bot is running (PID: {proc.info['pid']})")
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not bot_running:
            print("   ⚠️  Bot does not appear to be running")
        
        # Check log file age
        log_file_to_check = None
        if os.path.exists("bot.log"):
            log_file_to_check = "bot.log"
        elif os.path.exists("adaptive_bot.log"):
            log_file_to_check = "adaptive_bot.log"
            
        if log_file_to_check:
            log_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(log_file_to_check))
            if log_age.total_seconds() < 3600:  # Less than 1 hour
                print(f"   ✅ Log file is recent (updated {log_age.total_seconds()/60:.0f} minutes ago)")
            else:
                print(f"   ⚠️  Log file is old (updated {log_age.total_seconds()/3600:.1f} hours ago)")
        
        # Check disk space
        disk_usage = psutil.disk_usage('.')
        free_gb = disk_usage.free / (1024**3)
        if free_gb > 1.0:
            print(f"   ✅ Sufficient disk space ({free_gb:.1f} GB free)")
        else:
            print(f"   ⚠️  Low disk space ({free_gb:.1f} GB free)")
    
    except Exception as e:
        print(f"❌ Error in health check: {str(e)}")
    
    # 5. Recommendations
    print("\n5️⃣ DAILY RECOMMENDATIONS")
    print("-" * 30)
    
    recommendations = []
    
    # Based on trading activity
    if events.get('trades', 0) == 0:
        recommendations.append("🎯 No trades detected - check if signals are being generated")
    elif events.get('trades', 0) > 20:
        recommendations.append("⚡ High trading activity - monitor for overtrading")
    
    # Based on adaptations
    if events.get('adaptations', 0) == 0:
        recommendations.append("🎛️ No adaptations - this is normal in early stages")
    elif events.get('adaptations', 0) > 10:
        recommendations.append("🎛️ High adaptation rate - system is learning quickly")
    
    # Based on errors
    if events.get('errors', 0) > 5:
        recommendations.append("❌ High error count - investigate log file")
    
    # General recommendations
    recommendations.extend([
        "📊 Check market conditions and news for context",
        "💰 Consider adding more capital if performance is good",
        "📈 Review strategy weights if performance is poor",
        "🎯 Monitor for 2-4 weeks before considering live trading"
    ])
    
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec}")
    
    print("\n" + "="*50)
    print("📊 DAILY MONITORING COMPLETE")
    print("="*50)
    print(f"💡 Next check: {(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}")
    print("🚀 Keep the bot running and check back tomorrow!")

if __name__ == "__main__":
    daily_monitoring_report()