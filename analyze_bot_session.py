#!/usr/bin/env python3
"""
Analyze Bot Session Performance
Analyze the bot's performance from log files to see learning progress.
"""
import re
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_previous_session():
    """Analyze the bot's previous session from logs."""
    try:
        with open('adaptive_bot.log', 'r') as f:
            lines = f.readlines()
    except:
        print("❌ Could not read log file")
        return
    
    print("📊 ANALYZING PREVIOUS BOT SESSION")
    print("=" * 50)
    
    # Find session boundaries
    session_starts = []
    session_ends = []
    cycles = []
    ml_confidence_readings = []
    errors = []
    signals = []
    
    for line in lines:
        try:
            # Extract timestamp
            if ' - ' in line:
                timestamp_str = line.split(' - ')[0]
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                
                # Session starts
                if 'Adaptive bot started successfully' in line:
                    session_starts.append(timestamp)
                
                # Session ends
                if 'Main trading loop stopped' in line or 'graceful shutdown' in line:
                    session_ends.append(timestamp)
                
                # Cycles
                if 'Cycle #' in line:
                    cycle_match = re.search(r'Cycle #(\d+)', line)
                    if cycle_match:
                        cycle_num = int(cycle_match.group(1))
                        cycles.append((timestamp, cycle_num))
                
                # ML Confidence
                if 'ML engine confidence:' in line:
                    conf_match = re.search(r'ML engine confidence: ([\d.]+)', line)
                    if conf_match:
                        confidence = float(conf_match.group(1))
                        ml_confidence_readings.append((timestamp, confidence))
                
                # Errors
                if 'ERROR' in line:
                    errors.append((timestamp, line.strip()))
                
                # Signals
                if 'signal' in line.lower() and 'no signal' not in line.lower():
                    signals.append((timestamp, line.strip()))
        
        except Exception as e:
            continue
    
    # Analyze the most recent complete session
    if len(session_starts) >= 1:
        last_session_start = session_starts[-1]
        last_session_end = session_ends[-1] if session_ends else datetime.now()
        
        print(f"🕐 Last Session Analysis:")
        print(f"   Start Time: {last_session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   End Time: {last_session_end.strftime('%Y-%m-%d %H:%M:%S')}")
        
        session_duration = last_session_end - last_session_start
        duration_hours = session_duration.total_seconds() / 3600
        print(f"   Duration: {duration_hours:.1f} hours ({session_duration})")
        
        # Filter data for this session
        session_cycles = [(t, c) for t, c in cycles if last_session_start <= t <= last_session_end]
        session_ml_readings = [(t, c) for t, c in ml_confidence_readings if last_session_start <= t <= last_session_end]
        session_errors = [(t, e) for t, e in errors if last_session_start <= t <= last_session_end]
        session_signals = [(t, s) for t, s in signals if last_session_start <= t <= last_session_end]
        
        print(f"\n📈 Session Performance:")
        print(f"   Total Cycles: {len(session_cycles)}")
        if session_cycles:
            first_cycle = session_cycles[0][1]
            last_cycle = session_cycles[-1][1]
            print(f"   Cycle Range: #{first_cycle} to #{last_cycle}")
            
            # Calculate average cycle time
            if len(session_cycles) > 1:
                cycle_intervals = []
                for i in range(1, len(session_cycles)):
                    interval = (session_cycles[i][0] - session_cycles[i-1][0]).total_seconds()
                    cycle_intervals.append(interval)
                
                avg_cycle_time = sum(cycle_intervals) / len(cycle_intervals)
                print(f"   Average Cycle Time: {avg_cycle_time:.1f} seconds")
                
                # Cycle consistency
                if cycle_intervals:
                    min_interval = min(cycle_intervals)
                    max_interval = max(cycle_intervals)
                    consistency = 1.0 - (max_interval - min_interval) / avg_cycle_time if avg_cycle_time > 0 else 0
                    print(f"   Cycle Consistency: {consistency:.2f}")
        
        print(f"\n🧠 ML Learning Progress:")
        print(f"   Confidence Readings: {len(session_ml_readings)}")
        if session_ml_readings:
            first_conf = session_ml_readings[0][1]
            last_conf = session_ml_readings[-1][1]
            conf_improvement = last_conf - first_conf
            print(f"   Starting Confidence: {first_conf:.3f}")
            print(f"   Ending Confidence: {last_conf:.3f}")
            print(f"   Improvement: {conf_improvement:+.3f}")
            
            if duration_hours > 0:
                learning_rate = conf_improvement / duration_hours
                print(f"   Learning Rate: {learning_rate:.4f} per hour")
        else:
            print("   ⚠️  No ML confidence readings found")
        
        print(f"\n🎯 Trading Activity:")
        print(f"   Trading Signals: {len(session_signals)}")
        if session_signals:
            print("   Recent Signals:")
            for timestamp, signal in session_signals[-3:]:
                time_str = timestamp.strftime('%H:%M:%S')
                signal_clean = signal.split(' - ')[-1][:80] + "..." if len(signal.split(' - ')[-1]) > 80 else signal.split(' - ')[-1]
                print(f"     {time_str}: {signal_clean}")
        else:
            print("   • No trading signals detected")
        
        print(f"\n⚠️  Error Analysis:")
        print(f"   Total Errors: {len(session_errors)}")
        
        # Categorize errors
        error_types = defaultdict(int)
        for _, error in session_errors:
            if 'balance' in error.lower():
                error_types['Balance/API'] += 1
            elif 'connection' in error.lower() or 'network' in error.lower():
                error_types['Network'] += 1
            elif 'timeout' in error.lower():
                error_types['Timeout'] += 1
            else:
                error_types['Other'] += 1
        
        if error_types:
            print("   Error Breakdown:")
            for error_type, count in error_types.items():
                print(f"     {error_type}: {count}")
        
        # Performance assessment
        print(f"\n🎯 Session Assessment:")
        
        # Calculate performance score
        score = 0
        max_score = 100
        
        # Duration score (longer is better, up to 24 hours)
        duration_score = min(20, duration_hours * 20 / 24)
        score += duration_score
        
        # Cycle consistency score
        if session_cycles and len(session_cycles) > 10:
            expected_cycles = duration_hours * 60  # 1 per minute
            actual_cycles = len(session_cycles)
            cycle_score = min(20, (actual_cycles / expected_cycles) * 20) if expected_cycles > 0 else 0
            score += cycle_score
        
        # ML learning score
        if session_ml_readings:
            final_confidence = session_ml_readings[-1][1]
            ml_score = min(30, final_confidence * 30 / 0.5)  # Max score at 0.5 confidence
            score += ml_score
        
        # Error penalty
        error_penalty = min(20, len(session_errors) / 10)
        score -= error_penalty
        
        # Signal bonus
        signal_bonus = min(10, len(session_signals))
        score += signal_bonus
        
        score = max(0, min(100, score))
        
        print(f"   Overall Performance Score: {score:.0f}/100")
        
        if score >= 80:
            assessment = "🚀 Excellent - Bot is learning very well"
        elif score >= 60:
            assessment = "✅ Good - Bot is making solid progress"
        elif score >= 40:
            assessment = "🟡 Fair - Bot is learning but slowly"
        else:
            assessment = "🔴 Poor - Bot may have issues"
        
        print(f"   Assessment: {assessment}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        if duration_hours < 4:
            print("   • Run bot for longer periods (12-24 hours) for better learning")
        
        if session_ml_readings and session_ml_readings[-1][1] < 0.1:
            print("   • ML confidence is still very low - needs more time to learn")
        
        if len(session_errors) > 50:
            print("   • High error count - investigate and fix recurring issues")
        
        if len(session_signals) == 0:
            print("   • No trading signals yet - this is normal in early learning phase")
        
        if len(session_cycles) < duration_hours * 50:  # Less than 50 cycles per hour
            print("   • Low cycle frequency - check for performance issues")
        
        print(f"\n✅ CONCLUSION:")
        if score >= 60:
            print("   Your bot is working as intended and making good progress!")
            print("   Continue running it and monitor regularly.")
        else:
            print("   Your bot is working but may need attention or more time.")
            print("   Consider investigating any recurring errors.")
        
        return {
            'duration_hours': duration_hours,
            'total_cycles': len(session_cycles),
            'ml_confidence_final': session_ml_readings[-1][1] if session_ml_readings else 0,
            'total_errors': len(session_errors),
            'total_signals': len(session_signals),
            'performance_score': score
        }
    
    else:
        print("❌ No complete session found in logs")
        return None

if __name__ == "__main__":
    analyze_previous_session()