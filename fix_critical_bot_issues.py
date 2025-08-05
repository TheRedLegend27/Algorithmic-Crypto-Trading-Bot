#!/usr/bin/env python3
"""
Fix Critical Bot Issues
Address the main issues preventing the bot from working properly.
"""
import os
import sys
import json
import subprocess
from pathlib import Path

def install_missing_dependencies():
    """Install missing optimization libraries."""
    print("🔧 Installing Missing Dependencies...")
    
    try:
        # Install scikit-optimize
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'scikit-optimize'], check=True)
        print("✅ Installed scikit-optimize")
        
        # Install DEAP
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'deap'], check=True)
        print("✅ Installed DEAP")
        
        # Install other useful libraries
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'ta-lib'], check=False)  # Optional
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'plotly'], check=False)  # Optional
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def fix_api_initialization():
    """Fix the API initialization issue in the adaptive bot."""
    print("🔧 Fixing API Initialization...")
    
    # Read the adaptive bot main file
    try:
        with open('bot/adaptive/adaptive_bot_main.py', 'r') as f:
            content = f.read()
        
        # Check if Kraken client is properly initialized
        if "self.kraken_client = None" in content or "kraken_client=None" in content:
            print("🔍 Found API initialization issue")
            
            # Create a fixed version
            fixed_content = content.replace(
                "self.kraken_client = None",
                """# Initialize Kraken client with credentials
        from bot.kraken_client import EnhancedKrakenClient, KrakenCredentials
        import os
        
        # Get API credentials from environment
        api_key = os.getenv('KRAKEN_API_KEY', '')
        api_secret = os.getenv('KRAKEN_API_SECRET', '')
        
        if api_key and api_secret:
            credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
            self.kraken_client = EnhancedKrakenClient(credentials)
            log_info("Kraken client initialized successfully")
        else:
            log_warning("Kraken API credentials not found, using mock client")
            self.kraken_client = None"""
            )
            
            # Write the fixed content
            with open('bot/adaptive/adaptive_bot_main.py', 'w') as f:
                f.write(fixed_content)
            
            print("✅ Fixed API initialization in adaptive_bot_main.py")
            return True
        else:
            print("✅ API initialization appears to be correct")
            return True
            
    except Exception as e:
        print(f"❌ Failed to fix API initialization: {e}")
        return False

def enhance_signal_generation():
    """Enhance the signal generation in the strategy engine."""
    print("🔧 Enhancing Signal Generation...")
    
    try:
        # Create an enhanced strategy configuration
        enhanced_config = {
            "strategies": {
                "enhanced_momentum": {
                    "enabled": True,
                    "weight": 0.4,
                    "parameters": {
                        "rsi_period": 14,
                        "rsi_oversold": 30,
                        "rsi_overbought": 70,
                        "macd_fast": 12,
                        "macd_slow": 26,
                        "macd_signal": 9,
                        "bb_period": 20,
                        "bb_std": 2,
                        "volume_threshold": 1.5,
                        "min_confidence": 0.6
                    }
                },
                "price_action": {
                    "enabled": True,
                    "weight": 0.3,
                    "parameters": {
                        "support_resistance_periods": [20, 50],
                        "breakout_threshold": 0.02,
                        "volume_confirmation": True,
                        "min_confidence": 0.5
                    }
                },
                "multi_timeframe": {
                    "enabled": True,
                    "weight": 0.3,
                    "parameters": {
                        "timeframes": ["5m", "15m", "1h"],
                        "trend_alignment_required": True,
                        "min_timeframes_aligned": 2,
                        "min_confidence": 0.7
                    }
                }
            },
            "signal_generation": {
                "min_overall_confidence": 0.4,
                "max_signals_per_hour": 10,
                "cooldown_minutes": 5,
                "require_volume_confirmation": True,
                "risk_reward_ratio": 2.0
            }
        }
        
        # Save enhanced configuration
        with open('config/enhanced_strategies.json', 'w') as f:
            json.dump(enhanced_config, f, indent=2)
        
        print("✅ Created enhanced strategy configuration")
        return True
        
    except Exception as e:
        print(f"❌ Failed to enhance signal generation: {e}")
        return False

def create_continuous_operation_script():
    """Create a script for continuous bot operation."""
    print("🔧 Creating Continuous Operation Script...")
    
    script_content = '''#!/usr/bin/env python3
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
        print(f"\\n🛑 Received signal {signum}, shutting down...")
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
'''
    
    try:
        with open('run_bot_continuously.py', 'w') as f:
            f.write(script_content)
        
        # Make it executable
        os.chmod('run_bot_continuously.py', 0o755)
        
        print("✅ Created continuous operation script: run_bot_continuously.py")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create continuous operation script: {e}")
        return False

def create_enhanced_monitoring():
    """Create enhanced monitoring and alerting."""
    print("🔧 Creating Enhanced Monitoring...")
    
    monitoring_script = '''#!/usr/bin/env python3
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
            print("\\n🛑 Monitoring stopped")

if __name__ == "__main__":
    monitor = BotMonitor()
    monitor.monitor_continuously()
'''
    
    try:
        with open('enhanced_bot_monitor.py', 'w') as f:
            f.write(monitoring_script)
        
        os.chmod('enhanced_bot_monitor.py', 0o755)
        
        print("✅ Created enhanced monitoring script: enhanced_bot_monitor.py")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create enhanced monitoring: {e}")
        return False

def create_oracle_deployment_checklist():
    """Create a checklist for Oracle deployment readiness."""
    print("🔧 Creating Oracle Deployment Checklist...")
    
    checklist_content = '''# Oracle Cloud Deployment Readiness Checklist

## Pre-Deployment Requirements

### ✅ Bot Functionality
- [ ] Bot runs continuously for 24+ hours without crashes
- [ ] API connections working properly (no NoneType errors)
- [ ] Trading signals being generated regularly
- [ ] ML confidence improving over time
- [ ] Error rate < 5 per day
- [ ] Performance score > 60/100

### ✅ Dependencies
- [ ] All Python packages installed (scikit-optimize, DEAP, etc.)
- [ ] Environment variables properly configured
- [ ] API credentials validated and working
- [ ] Configuration files present and valid

### ✅ Monitoring & Logging
- [ ] Comprehensive logging enabled
- [ ] Performance tracking working
- [ ] Alert system configured
- [ ] Dashboard accessible
- [ ] Monitoring scripts tested

### ✅ Security
- [ ] API credentials secured (not in code)
- [ ] Environment variables properly set
- [ ] Access controls configured
- [ ] Backup procedures in place

### ✅ Testing
- [ ] Paper trading tested extensively
- [ ] Multi-pair trading validated
- [ ] Error recovery tested
- [ ] Performance under load tested
- [ ] Integration tests passing

## Oracle Cloud Specific

### ✅ Infrastructure
- [ ] Oracle Cloud account set up
- [ ] Compute instance configured
- [ ] Network security groups configured
- [ ] Storage volumes attached
- [ ] Backup strategy implemented

### ✅ Deployment
- [ ] Code repository accessible from Oracle Cloud
- [ ] Environment setup automated
- [ ] Service configuration files ready
- [ ] Monitoring integration configured
- [ ] Rollback plan prepared

### ✅ Production Readiness
- [ ] Live trading configuration tested
- [ ] Risk management parameters validated
- [ ] Capital allocation confirmed
- [ ] Emergency procedures documented
- [ ] Support contacts established

## Deployment Steps

1. **Prepare Oracle Cloud Environment**
   ```bash
   # Set up compute instance
   # Configure security groups
   # Install required software
   ```

2. **Deploy Bot Code**
   ```bash
   git clone <repository>
   cd crypto-scalping-bot-kiro
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp .env.template .env
   # Edit .env with production values
   # Set IS_PAPER_TRADING=False for live trading
   ```

4. **Start Services**
   ```bash
   python3 run_bot_continuously.py &
   python3 enhanced_bot_monitor.py &
   ```

5. **Verify Deployment**
   ```bash
   python3 check_adaptive_bot_status.py
   tail -f adaptive_bot.log
   ```

## Post-Deployment Monitoring

- Monitor bot performance for first 24 hours
- Check logs regularly for errors
- Validate trading activity
- Monitor capital and P&L
- Ensure alerts are working

## Emergency Procedures

### If Bot Stops Working
1. Check process status: `ps aux | grep adaptive_bot`
2. Check logs: `tail -100 adaptive_bot.log`
3. Restart if needed: `python3 run_adaptive_bot.py`
4. Contact support if issues persist

### If Unexpected Losses
1. Stop bot immediately: `pkill -f adaptive_bot`
2. Review recent trades and logs
3. Check market conditions
4. Investigate before restarting

### If API Issues
1. Check Kraken API status
2. Verify API credentials
3. Check rate limiting
4. Test connection: `python3 test_kraken_api.py`

## Success Criteria

- Bot runs continuously without manual intervention
- Trading signals generated and executed properly
- Performance metrics within expected ranges
- No critical errors in logs
- Monitoring and alerts working
- Capital preserved and growing

## Contact Information

- Technical Support: [Your contact]
- Emergency Contact: [Emergency contact]
- Kraken Support: https://support.kraken.com/
'''
    
    try:
        with open('ORACLE_DEPLOYMENT_CHECKLIST.md', 'w') as f:
            f.write(checklist_content)
        
        print("✅ Created Oracle deployment checklist: ORACLE_DEPLOYMENT_CHECKLIST.md")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create deployment checklist: {e}")
        return False

def main():
    """Main function to fix all critical issues."""
    print("🚀 FIXING CRITICAL BOT ISSUES")
    print("=" * 60)
    
    fixes_applied = []
    
    # 1. Install missing dependencies
    if install_missing_dependencies():
        fixes_applied.append("✅ Installed missing optimization libraries")
    else:
        fixes_applied.append("❌ Failed to install dependencies")
    
    # 2. Fix API initialization
    if fix_api_initialization():
        fixes_applied.append("✅ Fixed API initialization")
    else:
        fixes_applied.append("❌ Failed to fix API initialization")
    
    # 3. Enhance signal generation
    if enhance_signal_generation():
        fixes_applied.append("✅ Enhanced signal generation configuration")
    else:
        fixes_applied.append("❌ Failed to enhance signal generation")
    
    # 4. Create continuous operation script
    if create_continuous_operation_script():
        fixes_applied.append("✅ Created continuous operation script")
    else:
        fixes_applied.append("❌ Failed to create continuous operation script")
    
    # 5. Create enhanced monitoring
    if create_enhanced_monitoring():
        fixes_applied.append("✅ Created enhanced monitoring")
    else:
        fixes_applied.append("❌ Failed to create enhanced monitoring")
    
    # 6. Create Oracle deployment checklist
    if create_oracle_deployment_checklist():
        fixes_applied.append("✅ Created Oracle deployment checklist")
    else:
        fixes_applied.append("❌ Failed to create deployment checklist")
    
    # Summary
    print("\n📋 FIXES APPLIED:")
    for fix in fixes_applied:
        print(f"   {fix}")
    
    successful_fixes = len([f for f in fixes_applied if "✅" in f])
    total_fixes = len(fixes_applied)
    
    print(f"\n🎯 SUCCESS RATE: {successful_fixes}/{total_fixes} ({successful_fixes/total_fixes*100:.1f}%)")
    
    if successful_fixes >= 4:
        print("\n🚀 NEXT STEPS:")
        print("1. Test the bot with: python3 run_adaptive_bot.py")
        print("2. For continuous operation: python3 run_bot_continuously.py")
        print("3. Monitor with: python3 enhanced_bot_monitor.py")
        print("4. Check status: python3 check_adaptive_bot_status.py")
        print("5. Review Oracle checklist: ORACLE_DEPLOYMENT_CHECKLIST.md")
    else:
        print("\n⚠️ CRITICAL ISSUES REMAIN:")
        print("Some fixes failed. Review the errors above and fix manually.")
        print("The bot may not work properly until all issues are resolved.")

if __name__ == "__main__":
    main()