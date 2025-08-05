#!/usr/bin/env python3
"""
Enhanced Bot Monitoring
Real-time monitoring with alerts and performance tracking.
"""
import time
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

class BotMonitor:
    def __init__(self):
        self.last_check = datetime.now()
        self.performance_history = []
        
    def check_bot_health(self):
        """Check overall bot health."""
        health_score = 0
        max_score = 100
        issues = []
        
        # Check if bot is running
        try:
            import subprocess
            result = subprocess.run(['pgrep', '-f', 'adaptive_bot'], 
                                  capture_output=True, text=True)
            if result.stdout.strip():
                health_score += 20
            else:
                issues.append("Bot process not running")
        except:
            issues.append("Cannot check bot process")
        
        # Check recent log activity
        try:
            if os.path.exists('adaptive_bot.log'):
                stat = os.stat('adaptive_bot.log')
                last_modified = datetime.fromtimestamp(stat.st_mtime)
                if (datetime.now() - last_modified).seconds < 300:  # 5 minutes
                    health_score += 20
                else:
                    issues.append("No recent log activity")
            else:
                issues.append("Log file not found")
        except:
            issues.append("Cannot check log file")
        
        # Check performance data
        try:
            if os.path.exists('daily_performance_tracking.json'):
                with open('daily_performance_tracking.json', 'r') as f:
                    perf_data = json.load(f)
                
                today = datetime.now().strftime('%Y-%m-%d')
                if today in perf_data.get('daily_records', {}):
                    today_data = perf_data['daily_records'][today]
                    if today_data.get('errors', 0) < 5:
                        health_score += 20
                    if today_data.get('adaptations', 0) > 0:
                        health_score += 20
                    if today_data.get('signals', 0) >= 0:  # Even 0 is acceptable
                        health_score += 20
                else:
                    issues.append("No performance data for today")
            else:
                issues.append("Performance tracking file not found")
        except Exception as e:
            issues.append(f"Cannot read performance data: {e}")
        
        return health_score, issues
    
    def generate_status_report(self):
        """Generate a comprehensive status report."""
        health_score, issues = self.check_bot_health()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'health_score': health_score,
            'status': 'HEALTHY' if health_score >= 80 else 'WARNING' if health_score >= 50 else 'CRITICAL',
            'issues': issues,
            'recommendations': []
        }
        
        # Add recommendations based on issues
        if 'Bot process not running' in issues:
            report['recommendations'].append('Start the bot with: python3 run_adaptive_bot.py')
        
        if 'No recent log activity' in issues:
            report['recommendations'].append('Check if bot is stuck or crashed')
        
        if any('performance' in issue.lower() for issue in issues):
            report['recommendations'].append('Review bot configuration and market conditions')
        
        return report
    
    def monitor_continuously(self, interval_minutes=5):
        """Monitor bot continuously."""
        print("🔍 Starting Enhanced Bot Monitoring")
        print(f"Monitoring interval: {interval_minutes} minutes")
        print("Press Ctrl+C to stop")
        print()
        
        try:
            while True:
                report = self.generate_status_report()
                
                # Display status
                status_emoji = "🟢" if report['status'] == 'HEALTHY' else "🟡" if report['status'] == 'WARNING' else "🔴"
                print(f"{status_emoji} {datetime.now().strftime('%H:%M:%S')} - Status: {report['status']} (Score: {report['health_score']}/100)")
                
                if report['issues']:
                    print("   Issues:")
                    for issue in report['issues']:
                        print(f"     • {issue}")
                
                if report['recommendations']:
                    print("   Recommendations:")
                    for rec in report['recommendations']:
                        print(f"     • {rec}")
                
                # Save report
                with open('monitoring_report.json', 'w') as f:
                    json.dump(report, f, indent=2)
                
                print()
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")

if __name__ == "__main__":
    monitor = BotMonitor()
    monitor.monitor_continuously()
