#!/usr/bin/env python3
"""
Adaptive Bot Learning Progress Monitor
Track the bot's learning progress and trading behavior over time.
"""
import os
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import re

class LearningProgressMonitor:
    def __init__(self):
        self.log_file = "adaptive_bot.log"
        self.start_time = datetime.now()
        
    def get_recent_logs(self, minutes=60):
        """Get logs from the last N minutes."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
            
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            recent_lines = []
            
            for line in lines:
                # Extract timestamp from log line
                if ' - ' in line:
                    try:
                        timestamp_str = line.split(' - ')[0]
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                        if timestamp >= cutoff_time:
                            recent_lines.append(line)
                    except:
                        recent_lines.append(line)  # Include lines without timestamps
            
            return recent_lines
        except:
            return []
    
    def extract_ml_confidence(self, logs):
        """Extract ML confidence values over time."""
        confidence_values = []
        for line in logs:
            if 'ML engine confidence:' in line:
                try:
                    conf_str = line.split('ML engine confidence: ')[1].strip()
                    confidence = float(conf_str)
                    timestamp_str = line.split(' - ')[0]
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    confidence_values.append((timestamp, confidence))
                except:
                    pass
        return confidence_values
    
    def extract_trading_signals(self, logs):
        """Extract trading signals and decisions."""
        signals = []
        for line in logs:
            if any(keyword in line.lower() for keyword in ['signal', 'buy', 'sell', 'trade', 'order']):
                if 'no signal' not in line.lower():
                    signals.append(line.strip())
        return signals
    
    def extract_market_regime_changes(self, logs):
        """Extract market regime detection changes."""
        regime_changes = []
        for line in logs:
            if 'regime' in line.lower() and ('detected' in line.lower() or 'changed' in line.lower()):
                regime_changes.append(line.strip())
        return regime_changes
    
    def extract_adaptations(self, logs):
        """Extract adaptation events."""
        adaptations = []
        for line in logs:
            if 'adaptation' in line.lower() and ('triggered' in line.lower() or 'applied' in line.lower()):
                adaptations.append(line.strip())
        return adaptations
    
    def extract_performance_metrics(self, logs):
        """Extract performance metrics."""
        metrics = []
        for line in logs:
            if any(keyword in line.lower() for keyword in ['pnl', 'profit', 'loss', 'return', 'drawdown']):
                if 'ERROR' not in line:
                    metrics.append(line.strip())
        return metrics
    
    def count_cycles(self, logs):
        """Count completed trading cycles."""
        cycle_count = 0
        for line in logs:
            if 'Cycle #' in line:
                cycle_count += 1
        return cycle_count
    
    def check_data_collection(self, logs):
        """Check if the bot is collecting market data."""
        data_indicators = []
        for line in logs:
            if any(keyword in line.lower() for keyword in ['data', 'price', 'volume', 'ohlc', 'market']):
                if 'ERROR' not in line and 'initialized' not in line:
                    data_indicators.append(line.strip())
        return data_indicators[-10:]  # Last 10 data collection events
    
    def analyze_learning_progress(self):
        """Analyze the bot's learning progress."""
        print("🧠 Adaptive Bot Learning Progress Analysis")
        print("=" * 60)
        
        # Get logs from different time periods
        logs_1h = self.get_recent_logs(60)
        logs_4h = self.get_recent_logs(240)
        logs_24h = self.get_recent_logs(1440)
        
        # Basic activity metrics
        cycles_1h = self.count_cycles(logs_1h)
        cycles_4h = self.count_cycles(logs_4h)
        
        print(f"📊 Activity Summary:")
        print(f"   Cycles (last hour): {cycles_1h}")
        print(f"   Cycles (last 4 hours): {cycles_4h}")
        print(f"   Expected cycles/hour: ~60 (1 per minute)")
        
        # ML Confidence tracking
        confidence_values = self.extract_ml_confidence(logs_24h)
        if confidence_values:
            latest_confidence = confidence_values[-1][1]
            if len(confidence_values) > 1:
                first_confidence = confidence_values[0][1]
                confidence_trend = latest_confidence - first_confidence
            else:
                confidence_trend = 0
            
            print(f"\n🎯 ML Learning Progress:")
            print(f"   Current ML Confidence: {latest_confidence:.3f}")
            print(f"   Confidence Trend: {confidence_trend:+.3f}")
            print(f"   Confidence Readings: {len(confidence_values)}")
            
            # Show confidence progression
            if len(confidence_values) >= 5:
                print(f"   Recent Confidence Values:")
                for timestamp, conf in confidence_values[-5:]:
                    print(f"     {timestamp.strftime('%H:%M:%S')}: {conf:.3f}")
        else:
            print(f"\n🎯 ML Learning Progress:")
            print(f"   ⚠️  No ML confidence readings found")
        
        # Trading signals
        signals = self.extract_trading_signals(logs_4h)
        print(f"\n📈 Trading Activity (last 4 hours):")
        if signals:
            print(f"   Trading signals detected: {len(signals)}")
            print(f"   Recent signals:")
            for signal in signals[-3:]:
                print(f"     • {signal}")
        else:
            print(f"   • No trading signals detected yet")
            print(f"   • This is normal during initial learning phase")
        
        # Market regime detection
        regime_changes = self.extract_market_regime_changes(logs_4h)
        print(f"\n🌊 Market Regime Detection:")
        if regime_changes:
            print(f"   Regime changes detected: {len(regime_changes)}")
            for change in regime_changes[-2:]:
                print(f"     • {change}")
        else:
            print(f"   • No regime changes detected recently")
        
        # Adaptations
        adaptations = self.extract_adaptations(logs_4h)
        print(f"\n🔄 Adaptive Behavior:")
        if adaptations:
            print(f"   Adaptations triggered: {len(adaptations)}")
            for adaptation in adaptations[-2:]:
                print(f"     • {adaptation}")
        else:
            print(f"   • No adaptations triggered yet")
            print(f"   • Bot is still in initial learning phase")
        
        # Data collection
        data_events = self.check_data_collection(logs_1h)
        print(f"\n📊 Data Collection (last hour):")
        if data_events:
            print(f"   Data collection events: {len(data_events)}")
            print(f"   Recent data activity:")
            for event in data_events[-3:]:
                print(f"     • {event}")
        else:
            print(f"   • Limited data collection activity visible")
        
        # Performance metrics
        performance = self.extract_performance_metrics(logs_4h)
        print(f"\n💰 Performance Tracking:")
        if performance:
            print(f"   Performance updates: {len(performance)}")
            for perf in performance[-2:]:
                print(f"     • {perf}")
        else:
            print(f"   • No performance metrics available yet")
        
        # Learning phase assessment
        print(f"\n🎓 Learning Phase Assessment:")
        
        if cycles_1h < 30:
            print(f"   ⚠️  Low activity - check if bot is running properly")
        elif confidence_values and latest_confidence > 0.1:
            print(f"   ✅ Bot is building confidence - learning in progress")
        elif signals:
            print(f"   ✅ Bot is generating trading signals - active learning")
        elif cycles_1h >= 30:
            print(f"   📚 Bot is in data collection phase - this is normal")
        else:
            print(f"   ❓ Bot status unclear - may need attention")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        if not confidence_values:
            print(f"   • Let bot run for at least 2-4 hours to build initial confidence")
        elif latest_confidence < 0.3:
            print(f"   • Bot is still learning - expect 6-24 hours for meaningful confidence")
        elif latest_confidence >= 0.3 and not signals:
            print(f"   • Bot has some confidence but no signals - market may be unclear")
        elif signals and latest_confidence >= 0.5:
            print(f"   • Bot is ready for more active trading - consider monitoring closely")
        
        print(f"   • Check status regularly: python3 monitor_learning_progress.py")
        print(f"   • Watch live logs: tail -f adaptive_bot.log")
        print(f"   • For detailed status: python3 check_adaptive_bot_status.py")
        
        return {
            'cycles_1h': cycles_1h,
            'ml_confidence': latest_confidence if confidence_values else 0,
            'signals_count': len(signals),
            'adaptations_count': len(adaptations),
            'learning_active': cycles_1h >= 30 and (confidence_values or signals)
        }

def main():
    monitor = LearningProgressMonitor()
    
    # Check if bot is running
    try:
        result = subprocess.run(['pgrep', '-f', 'run_adaptive_bot'], 
                              capture_output=True, text=True)
        bot_running = len(result.stdout.strip()) > 0
    except:
        bot_running = False
    
    if not bot_running:
        print("❌ Adaptive bot is not running!")
        print("Start it with: python3 run_adaptive_bot.py")
        return
    
    # Analyze learning progress
    progress = monitor.analyze_learning_progress()
    
    # Summary status
    print(f"\n🚀 Quick Status:")
    if progress['learning_active']:
        print(f"   ✅ Bot is actively learning")
    else:
        print(f"   📚 Bot is in initial setup/learning phase")
    
    print(f"   ML Confidence: {progress['ml_confidence']:.3f}")
    print(f"   Signals Generated: {progress['signals_count']}")
    print(f"   Recent Activity: {progress['cycles_1h']} cycles/hour")

if __name__ == "__main__":
    main()