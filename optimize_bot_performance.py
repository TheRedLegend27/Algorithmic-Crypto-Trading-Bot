#!/usr/bin/env python3
"""
Bot Performance Optimizer
Analyze and optimize the adaptive bot's performance and settings.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

class BotPerformanceOptimizer:
    def __init__(self):
        self.log_file = "adaptive_bot.log"
        self.config_recommendations = {}
        
    def analyze_cycle_performance(self):
        """Analyze trading cycle performance."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {}
        
        cycles = []
        cycle_times = []
        
        for line in lines:
            if 'Cycle #' in line:
                try:
                    timestamp_str = line.split(' - ')[0]
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    cycle_num = int(line.split('Cycle #')[1].split(' ')[0])
                    cycles.append((cycle_num, timestamp))
                except:
                    pass
        
        # Calculate cycle intervals
        if len(cycles) > 1:
            for i in range(1, len(cycles)):
                interval = (cycles[i][1] - cycles[i-1][1]).total_seconds()
                cycle_times.append(interval)
        
        if cycle_times:
            avg_cycle_time = sum(cycle_times) / len(cycle_times)
            min_cycle_time = min(cycle_times)
            max_cycle_time = max(cycle_times)
            
            return {
                'total_cycles': len(cycles),
                'avg_cycle_time': avg_cycle_time,
                'min_cycle_time': min_cycle_time,
                'max_cycle_time': max_cycle_time,
                'cycle_consistency': 1.0 - (max_cycle_time - min_cycle_time) / avg_cycle_time if avg_cycle_time > 0 else 0
            }
        
        return {'total_cycles': len(cycles)}
    
    def analyze_ml_confidence_trend(self):
        """Analyze ML confidence progression."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {}
        
        confidence_readings = []
        
        for line in lines:
            if 'ML engine confidence:' in line:
                try:
                    timestamp_str = line.split(' - ')[0]
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    conf_str = line.split('ML engine confidence: ')[1].strip()
                    confidence = float(conf_str)
                    confidence_readings.append((timestamp, confidence))
                except:
                    pass
        
        if len(confidence_readings) < 2:
            return {'readings': len(confidence_readings)}
        
        # Calculate trend
        first_conf = confidence_readings[0][1]
        last_conf = confidence_readings[-1][1]
        trend = last_conf - first_conf
        
        # Calculate learning rate (confidence increase per hour)
        time_span = (confidence_readings[-1][0] - confidence_readings[0][0]).total_seconds() / 3600
        learning_rate = trend / time_span if time_span > 0 else 0
        
        return {
            'readings': len(confidence_readings),
            'first_confidence': first_conf,
            'current_confidence': last_conf,
            'trend': trend,
            'learning_rate_per_hour': learning_rate,
            'time_span_hours': time_span
        }
    
    def analyze_error_patterns(self):
        """Analyze error patterns and frequency."""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        except:
            return {}
        
        errors = []
        error_types = {}
        
        for line in lines:
            if 'ERROR' in line:
                try:
                    timestamp_str = line.split(' - ')[0]
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    error_msg = line.split('ERROR - ')[1].strip()
                    errors.append((timestamp, error_msg))
                    
                    # Categorize error types
                    if 'balance' in error_msg.lower():
                        error_types['balance'] = error_types.get('balance', 0) + 1
                    elif 'connection' in error_msg.lower() or 'network' in error_msg.lower():
                        error_types['network'] = error_types.get('network', 0) + 1
                    elif 'api' in error_msg.lower():
                        error_types['api'] = error_types.get('api', 0) + 1
                    else:
                        error_types['other'] = error_types.get('other', 0) + 1
                except:
                    pass
        
        return {
            'total_errors': len(errors),
            'error_types': error_types,
            'recent_errors': errors[-5:] if errors else []
        }
    
    def check_system_resources(self):
        """Check system resource usage."""
        try:
            # Get bot process info
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            bot_processes = []
            for line in lines:
                if 'run_adaptive_bot' in line:
                    parts = line.split()
                    if len(parts) >= 11:
                        cpu_usage = float(parts[2])
                        memory_usage = float(parts[3])
                        bot_processes.append({
                            'cpu_percent': cpu_usage,
                            'memory_percent': memory_usage
                        })
            
            return {
                'bot_processes': len(bot_processes),
                'total_cpu': sum(p['cpu_percent'] for p in bot_processes),
                'total_memory': sum(p['memory_percent'] for p in bot_processes)
            }
        except:
            return {}
    
    def generate_optimization_recommendations(self, analysis):
        """Generate optimization recommendations based on analysis."""
        recommendations = []
        
        # Cycle performance recommendations
        if 'cycle_performance' in analysis:
            cycle_perf = analysis['cycle_performance']
            if cycle_perf.get('avg_cycle_time', 0) > 70:  # Should be ~60 seconds
                recommendations.append({
                    'type': 'performance',
                    'priority': 'medium',
                    'issue': 'Slow cycle times',
                    'recommendation': 'Consider reducing data processing load or optimizing API calls',
                    'current_value': f"{cycle_perf['avg_cycle_time']:.1f}s",
                    'target_value': '60s'
                })
            
            if cycle_perf.get('cycle_consistency', 1) < 0.8:
                recommendations.append({
                    'type': 'stability',
                    'priority': 'high',
                    'issue': 'Inconsistent cycle timing',
                    'recommendation': 'Check for network issues or resource constraints',
                    'current_value': f"{cycle_perf['cycle_consistency']:.2f}",
                    'target_value': '>0.8'
                })
        
        # ML confidence recommendations
        if 'ml_confidence' in analysis:
            ml_conf = analysis['ml_confidence']
            if ml_conf.get('learning_rate_per_hour', 0) < 0.01 and ml_conf.get('time_span_hours', 0) > 4:
                recommendations.append({
                    'type': 'learning',
                    'priority': 'medium',
                    'issue': 'Slow ML learning progress',
                    'recommendation': 'Consider adjusting learning parameters or increasing data collection frequency',
                    'current_value': f"{ml_conf['learning_rate_per_hour']:.4f}/hour",
                    'target_value': '>0.01/hour'
                })
            
            if ml_conf.get('current_confidence', 0) < 0.1 and ml_conf.get('time_span_hours', 0) > 12:
                recommendations.append({
                    'type': 'learning',
                    'priority': 'high',
                    'issue': 'Very low ML confidence after extended runtime',
                    'recommendation': 'Check data quality, market conditions, or consider restarting with fresh data',
                    'current_value': f"{ml_conf['current_confidence']:.3f}",
                    'target_value': '>0.3 after 12h'
                })
        
        # Error pattern recommendations
        if 'errors' in analysis:
            errors = analysis['errors']
            if errors.get('total_errors', 0) > 50:
                recommendations.append({
                    'type': 'stability',
                    'priority': 'high',
                    'issue': 'High error count',
                    'recommendation': 'Investigate and fix recurring errors',
                    'current_value': str(errors['total_errors']),
                    'target_value': '<10 per hour'
                })
            
            error_types = errors.get('error_types', {})
            if error_types.get('network', 0) > 10:
                recommendations.append({
                    'type': 'connectivity',
                    'priority': 'medium',
                    'issue': 'Network connectivity issues',
                    'recommendation': 'Check internet connection stability and API endpoint availability',
                    'current_value': str(error_types['network']),
                    'target_value': '<5 network errors'
                })
        
        # Resource usage recommendations
        if 'resources' in analysis:
            resources = analysis['resources']
            if resources.get('total_cpu', 0) > 50:
                recommendations.append({
                    'type': 'resources',
                    'priority': 'medium',
                    'issue': 'High CPU usage',
                    'recommendation': 'Consider optimizing algorithms or reducing processing frequency',
                    'current_value': f"{resources['total_cpu']:.1f}%",
                    'target_value': '<20%'
                })
            
            if resources.get('total_memory', 0) > 10:
                recommendations.append({
                    'type': 'resources',
                    'priority': 'medium',
                    'issue': 'High memory usage',
                    'recommendation': 'Check for memory leaks or reduce data retention periods',
                    'current_value': f"{resources['total_memory']:.1f}%",
                    'target_value': '<5%'
                })
        
        return recommendations
    
    def run_full_analysis(self):
        """Run complete performance analysis."""
        print("🔧 Adaptive Bot Performance Analysis")
        print("=" * 50)
        
        analysis = {}
        
        # Analyze cycle performance
        print("📊 Analyzing cycle performance...")
        analysis['cycle_performance'] = self.analyze_cycle_performance()
        
        # Analyze ML confidence trend
        print("🧠 Analyzing ML learning progress...")
        analysis['ml_confidence'] = self.analyze_ml_confidence_trend()
        
        # Analyze error patterns
        print("⚠️  Analyzing error patterns...")
        analysis['errors'] = self.analyze_error_patterns()
        
        # Check system resources
        print("💻 Checking system resources...")
        analysis['resources'] = self.check_system_resources()
        
        # Generate recommendations
        print("💡 Generating optimization recommendations...")
        recommendations = self.generate_optimization_recommendations(analysis)
        
        # Display results
        self.display_analysis_results(analysis, recommendations)
        
        return analysis, recommendations
    
    def display_analysis_results(self, analysis, recommendations):
        """Display analysis results in a readable format."""
        print("\n" + "="*50)
        print("📈 PERFORMANCE ANALYSIS RESULTS")
        print("="*50)
        
        # Cycle Performance
        if 'cycle_performance' in analysis:
            cycle_perf = analysis['cycle_performance']
            print(f"\n🔄 Cycle Performance:")
            print(f"   Total Cycles: {cycle_perf.get('total_cycles', 0)}")
            if 'avg_cycle_time' in cycle_perf:
                print(f"   Average Cycle Time: {cycle_perf['avg_cycle_time']:.1f}s")
                print(f"   Cycle Consistency: {cycle_perf['cycle_consistency']:.2f}")
                
                # Performance rating
                if cycle_perf['avg_cycle_time'] <= 65 and cycle_perf['cycle_consistency'] >= 0.8:
                    print(f"   Rating: ✅ Excellent")
                elif cycle_perf['avg_cycle_time'] <= 75 and cycle_perf['cycle_consistency'] >= 0.6:
                    print(f"   Rating: 🟡 Good")
                else:
                    print(f"   Rating: 🔴 Needs Improvement")
        
        # ML Confidence
        if 'ml_confidence' in analysis:
            ml_conf = analysis['ml_confidence']
            print(f"\n🧠 ML Learning Progress:")
            print(f"   Confidence Readings: {ml_conf.get('readings', 0)}")
            if 'current_confidence' in ml_conf:
                print(f"   Current Confidence: {ml_conf['current_confidence']:.3f}")
                print(f"   Learning Trend: {ml_conf['trend']:+.3f}")
                print(f"   Learning Rate: {ml_conf['learning_rate_per_hour']:.4f}/hour")
                print(f"   Runtime: {ml_conf['time_span_hours']:.1f} hours")
                
                # Learning rating
                if ml_conf['current_confidence'] >= 0.5:
                    print(f"   Rating: ✅ Ready for Trading")
                elif ml_conf['current_confidence'] >= 0.3:
                    print(f"   Rating: 🟡 Building Confidence")
                elif ml_conf['learning_rate_per_hour'] > 0.01:
                    print(f"   Rating: 📚 Learning Actively")
                else:
                    print(f"   Rating: 🔴 Learning Slowly")
        
        # Error Analysis
        if 'errors' in analysis:
            errors = analysis['errors']
            print(f"\n⚠️  Error Analysis:")
            print(f"   Total Errors: {errors.get('total_errors', 0)}")
            
            error_types = errors.get('error_types', {})
            if error_types:
                print(f"   Error Breakdown:")
                for error_type, count in error_types.items():
                    print(f"     {error_type.title()}: {count}")
            
            # Error rating
            total_errors = errors.get('total_errors', 0)
            if total_errors == 0:
                print(f"   Rating: ✅ No Errors")
            elif total_errors < 10:
                print(f"   Rating: 🟡 Minor Issues")
            else:
                print(f"   Rating: 🔴 Needs Attention")
        
        # System Resources
        if 'resources' in analysis:
            resources = analysis['resources']
            print(f"\n💻 System Resources:")
            print(f"   Bot Processes: {resources.get('bot_processes', 0)}")
            if 'total_cpu' in resources:
                print(f"   CPU Usage: {resources['total_cpu']:.1f}%")
                print(f"   Memory Usage: {resources['total_memory']:.1f}%")
                
                # Resource rating
                if resources['total_cpu'] < 20 and resources['total_memory'] < 5:
                    print(f"   Rating: ✅ Efficient")
                elif resources['total_cpu'] < 50 and resources['total_memory'] < 10:
                    print(f"   Rating: 🟡 Moderate Usage")
                else:
                    print(f"   Rating: 🔴 High Usage")
        
        # Recommendations
        if recommendations:
            print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
            print("-" * 40)
            
            # Group by priority
            high_priority = [r for r in recommendations if r['priority'] == 'high']
            medium_priority = [r for r in recommendations if r['priority'] == 'medium']
            low_priority = [r for r in recommendations if r['priority'] == 'low']
            
            for priority, recs in [('HIGH PRIORITY', high_priority), 
                                 ('MEDIUM PRIORITY', medium_priority), 
                                 ('LOW PRIORITY', low_priority)]:
                if recs:
                    print(f"\n🚨 {priority}:")
                    for i, rec in enumerate(recs, 1):
                        print(f"   {i}. {rec['issue']}")
                        print(f"      Current: {rec['current_value']}")
                        print(f"      Target: {rec['target_value']}")
                        print(f"      Action: {rec['recommendation']}")
                        print()
        else:
            print(f"\n✅ No optimization recommendations - bot is performing well!")
        
        print(f"\n📋 Next Steps:")
        print(f"   • Run this analysis regularly: python3 optimize_bot_performance.py")
        print(f"   • Monitor learning progress: python3 monitor_learning_progress.py")
        print(f"   • Check real-time status: python3 watch_bot_learning.py")

def main():
    optimizer = BotPerformanceOptimizer()
    
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
    
    # Run analysis
    analysis, recommendations = optimizer.run_full_analysis()
    
    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'analysis': analysis,
        'recommendations': recommendations
    }
    
    with open('performance_analysis.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Analysis saved to: performance_analysis.json")

if __name__ == "__main__":
    main()