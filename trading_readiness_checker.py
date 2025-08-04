#!/usr/bin/env python3
"""
Trading Readiness Checker
Comprehensive assessment of bot readiness for live trading.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

class TradingReadinessChecker:
    def __init__(self):
        self.log_file = "adaptive_bot.log"
        self.readiness_score = 0
        self.max_score = 100
        self.checks = []
        
    def check_bot_stability(self):
        """Check bot stability and uptime."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {'score': 0, 'status': 'No logs found'}
        
        # Find bot start time
        start_time = None
        error_count = 0
        restart_count = 0
        
        for line in lines:
            if 'Adaptive bot started successfully' in line:
                restart_count += 1
                try:
                    timestamp_str = line.split(' - ')[0]
                    start_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                except:
                    pass
            elif 'ERROR' in line:
                error_count += 1
        
        if not start_time:
            return {'score': 0, 'status': 'Bot not started properly'}
        
        # Calculate uptime
        uptime_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        # Score based on uptime and stability
        score = 0
        if uptime_hours >= 24:
            score += 15  # Full points for 24+ hours
        elif uptime_hours >= 12:
            score += 12  # Good uptime
        elif uptime_hours >= 4:
            score += 8   # Minimum acceptable
        elif uptime_hours >= 1:
            score += 4   # Too short
        
        # Penalize for restarts and errors
        if restart_count > 1:
            score -= min(5, restart_count - 1)
        
        if error_count > 20:
            score -= min(10, (error_count - 20) // 10)
        
        return {
            'score': max(0, score),
            'uptime_hours': uptime_hours,
            'restart_count': restart_count,
            'error_count': error_count,
            'status': f"{uptime_hours:.1f}h uptime, {restart_count} restarts, {error_count} errors"
        }
    
    def check_ml_confidence(self):
        """Check ML confidence levels."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {'score': 0, 'status': 'No logs found'}
        
        confidence_readings = []
        
        for line in lines:
            if 'ML engine confidence:' in line:
                try:
                    conf_str = line.split('ML engine confidence: ')[1].strip()
                    confidence = float(conf_str)
                    confidence_readings.append(confidence)
                except:
                    pass
        
        if not confidence_readings:
            return {'score': 0, 'status': 'No confidence readings'}
        
        current_confidence = confidence_readings[-1]
        avg_confidence = sum(confidence_readings) / len(confidence_readings)
        
        # Score based on confidence level
        score = 0
        if current_confidence >= 0.7:
            score = 20  # Excellent confidence
        elif current_confidence >= 0.5:
            score = 15  # Good confidence
        elif current_confidence >= 0.3:
            score = 10  # Acceptable confidence
        elif current_confidence >= 0.1:
            score = 5   # Low confidence
        
        return {
            'score': score,
            'current_confidence': current_confidence,
            'average_confidence': avg_confidence,
            'readings_count': len(confidence_readings),
            'status': f"Current: {current_confidence:.3f}, Average: {avg_confidence:.3f}"
        }
    
    def check_trading_activity(self):
        """Check trading signal generation and activity."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {'score': 0, 'status': 'No logs found'}
        
        signals = 0
        trades = 0
        no_signal_count = 0
        
        for line in lines:
            if 'signal' in line.lower():
                if 'no signal' in line.lower():
                    no_signal_count += 1
                else:
                    signals += 1
            
            if any(keyword in line.lower() for keyword in ['buy', 'sell', 'order', 'trade']):
                if 'ERROR' not in line:
                    trades += 1
        
        # Score based on activity
        score = 0
        if signals >= 10:
            score += 10  # Good signal generation
        elif signals >= 5:
            score += 7
        elif signals >= 1:
            score += 4
        
        if trades >= 5:
            score += 5   # Active trading
        elif trades >= 1:
            score += 3
        
        # Penalize for too many "no signal" instances
        if no_signal_count > 100:
            score -= 3
        
        return {
            'score': max(0, score),
            'signals': signals,
            'trades': trades,
            'no_signal_count': no_signal_count,
            'status': f"{signals} signals, {trades} trades, {no_signal_count} no-signals"
        }
    
    def check_paper_trading_performance(self):
        """Check paper trading performance metrics."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {'score': 0, 'status': 'No logs found'}
        
        pnl_mentions = 0
        profit_mentions = 0
        loss_mentions = 0
        
        for line in lines:
            if any(keyword in line.lower() for keyword in ['pnl', 'profit', 'return']):
                pnl_mentions += 1
                if any(pos in line.lower() for pos in ['profit', 'gain', 'positive']):
                    profit_mentions += 1
                elif any(neg in line.lower() for neg in ['loss', 'negative', 'drawdown']):
                    loss_mentions += 1
        
        # Score based on performance tracking
        score = 0
        if pnl_mentions >= 10:
            score += 10  # Good performance tracking
        elif pnl_mentions >= 5:
            score += 7
        elif pnl_mentions >= 1:
            score += 4
        
        # Bonus for positive performance indicators
        if profit_mentions > loss_mentions and profit_mentions > 0:
            score += 5
        
        return {
            'score': score,
            'pnl_mentions': pnl_mentions,
            'profit_mentions': profit_mentions,
            'loss_mentions': loss_mentions,
            'status': f"{pnl_mentions} performance updates, {profit_mentions} profits, {loss_mentions} losses"
        }
    
    def check_risk_management(self):
        """Check risk management functionality."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {'score': 0, 'status': 'No logs found'}
        
        risk_checks = 0
        position_management = 0
        drawdown_monitoring = 0
        
        for line in lines:
            if any(keyword in line.lower() for keyword in ['risk', 'exposure', 'limit']):
                risk_checks += 1
            
            if any(keyword in line.lower() for keyword in ['position', 'size', 'allocation']):
                position_management += 1
            
            if any(keyword in line.lower() for keyword in ['drawdown', 'loss', 'stop']):
                drawdown_monitoring += 1
        
        # Score based on risk management activity
        score = 0
        if risk_checks >= 20:
            score += 8
        elif risk_checks >= 10:
            score += 6
        elif risk_checks >= 5:
            score += 4
        
        if position_management >= 10:
            score += 4
        elif position_management >= 5:
            score += 2
        
        if drawdown_monitoring >= 5:
            score += 3
        elif drawdown_monitoring >= 1:
            score += 1
        
        return {
            'score': score,
            'risk_checks': risk_checks,
            'position_management': position_management,
            'drawdown_monitoring': drawdown_monitoring,
            'status': f"{risk_checks} risk checks, {position_management} position updates"
        }
    
    def check_api_connectivity(self):
        """Check API connectivity and credentials."""
        # Check .env file
        try:
            with open('.env', 'r') as f:
                env_content = f.read()
        except:
            return {'score': 0, 'status': 'No .env file found'}
        
        has_api_key = 'KRAKEN_API_KEY=' in env_content and len(env_content.split('KRAKEN_API_KEY=')[1].split('\n')[0]) > 10
        has_api_secret = 'KRAKEN_API_SECRET=' in env_content and len(env_content.split('KRAKEN_API_SECRET=')[1].split('\n')[0]) > 10
        is_paper_trading = 'IS_PAPER_TRADING=True' in env_content
        
        # Check for API-related errors in logs
        api_errors = 0
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                if 'ERROR' in line and any(keyword in line.lower() for keyword in ['api', 'connection', 'auth', 'kraken']):
                    api_errors += 1
        except:
            pass
        
        # Score based on API setup
        score = 0
        if has_api_key and has_api_secret:
            score += 10  # Credentials configured
        
        if api_errors == 0:
            score += 5   # No API errors
        elif api_errors < 5:
            score += 3   # Few API errors
        
        return {
            'score': score,
            'has_credentials': has_api_key and has_api_secret,
            'is_paper_trading': is_paper_trading,
            'api_errors': api_errors,
            'status': f"Credentials: {'✅' if has_api_key and has_api_secret else '❌'}, Paper: {'✅' if is_paper_trading else '❌'}, API Errors: {api_errors}"
        }
    
    def check_market_data_quality(self):
        """Check market data collection and quality."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {'score': 0, 'status': 'No logs found'}
        
        data_updates = 0
        data_errors = 0
        regime_detections = 0
        
        for line in lines:
            if any(keyword in line.lower() for keyword in ['data', 'price', 'ohlc', 'market']):
                if 'ERROR' in line:
                    data_errors += 1
                else:
                    data_updates += 1
            
            if 'regime' in line.lower() and 'detected' in line.lower():
                regime_detections += 1
        
        # Score based on data quality
        score = 0
        if data_updates >= 50:
            score += 8
        elif data_updates >= 20:
            score += 6
        elif data_updates >= 10:
            score += 4
        
        if regime_detections >= 5:
            score += 4
        elif regime_detections >= 1:
            score += 2
        
        # Penalize for data errors
        if data_errors > 10:
            score -= min(5, data_errors // 10)
        
        return {
            'score': max(0, score),
            'data_updates': data_updates,
            'data_errors': data_errors,
            'regime_detections': regime_detections,
            'status': f"{data_updates} data updates, {data_errors} errors, {regime_detections} regime changes"
        }
    
    def run_comprehensive_check(self):
        """Run comprehensive trading readiness assessment."""
        print("🚀 TRADING READINESS ASSESSMENT")
        print("=" * 50)
        
        # Check if bot is running
        try:
            result = subprocess.run(['pgrep', '-f', 'run_adaptive_bot'], 
                                  capture_output=True, text=True)
            bot_running = len(result.stdout.strip()) > 0
        except:
            bot_running = False
        
        if not bot_running:
            print("❌ Bot is not running - cannot assess readiness")
            return
        
        total_score = 0
        
        # Run all checks
        checks = [
            ("Bot Stability", self.check_bot_stability, 15),
            ("ML Confidence", self.check_ml_confidence, 20),
            ("Trading Activity", self.check_trading_activity, 15),
            ("Paper Performance", self.check_paper_trading_performance, 15),
            ("Risk Management", self.check_risk_management, 15),
            ("API Connectivity", self.check_api_connectivity, 10),
            ("Market Data", self.check_market_data_quality, 10)
        ]
        
        results = {}
        
        for check_name, check_func, max_points in checks:
            print(f"\n🔍 Checking {check_name}...")
            result = check_func()
            score = result['score']
            total_score += score
            results[check_name] = result
            
            # Display result
            percentage = (score / max_points) * 100 if max_points > 0 else 0
            if percentage >= 80:
                status_icon = "✅"
            elif percentage >= 60:
                status_icon = "🟡"
            else:
                status_icon = "🔴"
            
            print(f"   {status_icon} {check_name}: {score}/{max_points} ({percentage:.0f}%)")
            print(f"      {result['status']}")
        
        # Calculate overall readiness
        overall_percentage = (total_score / 100) * 100
        
        print(f"\n" + "="*50)
        print(f"📊 OVERALL TRADING READINESS")
        print(f"="*50)
        print(f"Total Score: {total_score}/100 ({overall_percentage:.0f}%)")
        
        # Readiness assessment
        if overall_percentage >= 85:
            readiness_level = "🚀 READY FOR LIVE TRADING"
            recommendation = "Bot is performing excellently and ready for live trading"
        elif overall_percentage >= 70:
            readiness_level = "🟡 MOSTLY READY"
            recommendation = "Bot is mostly ready - address minor issues before live trading"
        elif overall_percentage >= 50:
            readiness_level = "📚 NEEDS MORE TIME"
            recommendation = "Bot needs more learning time or configuration adjustments"
        else:
            readiness_level = "🔴 NOT READY"
            recommendation = "Bot has significant issues that must be resolved"
        
        print(f"\nReadiness Level: {readiness_level}")
        print(f"Recommendation: {recommendation}")
        
        # Specific recommendations
        print(f"\n💡 SPECIFIC RECOMMENDATIONS:")
        print("-" * 30)
        
        if results["Bot Stability"]["score"] < 10:
            print("• Let bot run for at least 12-24 hours for stability")
        
        if results["ML Confidence"]["score"] < 15:
            print("• Wait for ML confidence to reach at least 0.5")
        
        if results["Trading Activity"]["score"] < 10:
            print("• Monitor for more trading signals and activity")
        
        if results["API Connectivity"]["score"] < 8:
            print("• Fix API connectivity issues before live trading")
        
        if results["Risk Management"]["score"] < 10:
            print("• Ensure risk management systems are functioning")
        
        # Final steps
        if overall_percentage >= 70:
            print(f"\n🎯 NEXT STEPS FOR LIVE TRADING:")
            print("1. Backup current configuration")
            print("2. Set IS_PAPER_TRADING=False in .env")
            print("3. Start with small position sizes")
            print("4. Monitor closely for first few hours")
            print("5. Keep emergency stop procedures ready")
        else:
            print(f"\n📚 CONTINUE LEARNING:")
            print("1. Let bot run longer in paper trading mode")
            print("2. Monitor progress with: python3 monitor_learning_progress.py")
            print("3. Run this check again in 4-6 hours")
            print("4. Address specific issues mentioned above")
        
        # Save results
        assessment_data = {
            'timestamp': datetime.now().isoformat(),
            'total_score': total_score,
            'overall_percentage': overall_percentage,
            'readiness_level': readiness_level,
            'recommendation': recommendation,
            'detailed_results': results
        }
        
        with open('trading_readiness_assessment.json', 'w') as f:
            json.dump(assessment_data, f, indent=2, default=str)
        
        print(f"\n💾 Assessment saved to: trading_readiness_assessment.json")
        
        return assessment_data

def main():
    checker = TradingReadinessChecker()
    checker.run_comprehensive_check()

if __name__ == "__main__":
    main()