#!/usr/bin/env python3
"""
Diagnose the warnings and errors found in the bot logs.
"""
import sys
import os
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def diagnose_log_issues():
    """Analyze the warnings and errors in detail."""
    print("🔍 DIAGNOSING WARNINGS AND ERRORS")
    print("="*50)
    
    # Check adaptive bot log
    if not os.path.exists("adaptive_bot.log"):
        print("❌ No adaptive_bot.log file found")
        return
    
    with open("adaptive_bot.log", "r") as f:
        log_lines = f.readlines()
    
    # Get recent log entries (last 200 lines for better context)
    recent_logs = log_lines[-200:] if len(log_lines) > 200 else log_lines
    
    # Separate warnings and errors
    warnings = []
    errors = []
    
    for i, line in enumerate(recent_logs):
        if 'WARNING' in line:
            # Get context (line before and after if available)
            context_start = max(0, i-1)
            context_end = min(len(recent_logs), i+2)
            context = recent_logs[context_start:context_end]
            warnings.append({
                'line': line.strip(),
                'context': [l.strip() for l in context],
                'line_num': len(log_lines) - len(recent_logs) + i
            })
        elif 'ERROR' in line:
            context_start = max(0, i-1)
            context_end = min(len(recent_logs), i+2)
            context = recent_logs[context_start:context_end]
            errors.append({
                'line': line.strip(),
                'context': [l.strip() for l in context],
                'line_num': len(log_lines) - len(recent_logs) + i
            })
    
    # Analyze warnings
    print(f"\n⚠️  WARNINGS ANALYSIS ({len(warnings)} found)")
    print("-" * 40)
    
    if warnings:
        # Categorize warnings
        warning_categories = {}
        for warning in warnings:
            # Extract the warning message
            warning_msg = warning['line']
            
            # Categorize common warnings
            if 'Strategy engine returned no signal' in warning_msg:
                category = 'No Signal Generated'
                severity = 'LOW'
                explanation = 'Normal during startup - strategies need time to find good opportunities'
            elif 'insufficient' in warning_msg.lower():
                category = 'Insufficient Data/Models'
                severity = 'LOW'
                explanation = 'Normal during initial learning phase'
            elif 'fallback' in warning_msg.lower():
                category = 'Fallback Mechanism'
                severity = 'LOW'
                explanation = 'System using backup methods - not critical'
            elif 'api' in warning_msg.lower() or 'connection' in warning_msg.lower():
                category = 'API/Connection'
                severity = 'MEDIUM'
                explanation = 'May affect data quality but has fallbacks'
            else:
                category = 'Other'
                severity = 'MEDIUM'
                explanation = 'Needs investigation'
            
            if category not in warning_categories:
                warning_categories[category] = []
            warning_categories[category].append({
                'warning': warning,
                'severity': severity,
                'explanation': explanation
            })
        
        # Display categorized warnings
        for category, category_warnings in warning_categories.items():
            print(f"\n📋 {category} ({len(category_warnings)} warnings)")
            severity = category_warnings[0]['severity']
            explanation = category_warnings[0]['explanation']
            
            if severity == 'LOW':
                print(f"   🟢 Severity: {severity} - {explanation}")
            elif severity == 'MEDIUM':
                print(f"   🟡 Severity: {severity} - {explanation}")
            else:
                print(f"   🔴 Severity: {severity} - {explanation}")
            
            # Show first few examples
            for i, item in enumerate(category_warnings[:2]):  # Show max 2 examples
                warning = item['warning']
                timestamp = warning['line'].split(' - ')[0] if ' - ' in warning['line'] else 'Unknown'
                message = warning['line'].split(' - ')[-1] if ' - ' in warning['line'] else warning['line']
                print(f"      {i+1}. {timestamp}: {message}")
    else:
        print("✅ No warnings found in recent logs")
    
    # Analyze errors
    print(f"\n❌ ERRORS ANALYSIS ({len(errors)} found)")
    print("-" * 40)
    
    if errors:
        # Categorize errors
        error_categories = {}
        for error in errors:
            error_msg = error['line']
            
            # Categorize common errors
            if 'balance' in error_msg.lower() or 'get_account_balance' in error_msg:
                category = 'Balance/API Access'
                severity = 'LOW'
                explanation = 'Expected in paper trading mode - using mock balances'
            elif 'connection' in error_msg.lower() or 'timeout' in error_msg.lower():
                category = 'Network/Connection'
                severity = 'MEDIUM'
                explanation = 'May cause temporary data issues but has retries'
            elif 'import' in error_msg.lower() or 'module' in error_msg.lower():
                category = 'Import/Module'
                severity = 'HIGH'
                explanation = 'Missing dependencies or code issues'
            elif 'file' in error_msg.lower() and 'not found' in error_msg.lower():
                category = 'File Not Found'
                severity = 'MEDIUM'
                explanation = 'Missing configuration or data files'
            else:
                category = 'Other'
                severity = 'HIGH'
                explanation = 'Needs immediate investigation'
            
            if category not in error_categories:
                error_categories[category] = []
            error_categories[category].append({
                'error': error,
                'severity': severity,
                'explanation': explanation
            })
        
        # Display categorized errors
        for category, category_errors in error_categories.items():
            print(f"\n📋 {category} ({len(category_errors)} errors)")
            severity = category_errors[0]['severity']
            explanation = category_errors[0]['explanation']
            
            if severity == 'LOW':
                print(f"   🟢 Severity: {severity} - {explanation}")
            elif severity == 'MEDIUM':
                print(f"   🟡 Severity: {severity} - {explanation}")
            else:
                print(f"   🔴 Severity: {severity} - {explanation}")
            
            # Show examples with more context for errors
            for i, item in enumerate(category_errors[:2]):
                error = item['error']
                timestamp = error['line'].split(' - ')[0] if ' - ' in error['line'] else 'Unknown'
                message = error['line'].split(' - ')[-1] if ' - ' in error['line'] else error['line']
                print(f"      {i+1}. {timestamp}: {message}")
                
                # Show context for errors
                if len(error['context']) > 1:
                    print(f"         Context: {error['context'][0] if len(error['context']) > 0 else 'N/A'}")
    else:
        print("✅ No errors found in recent logs")
    
    # Overall assessment
    print(f"\n🎯 OVERALL ASSESSMENT")
    print("-" * 30)
    
    # Count severity levels
    low_severity = 0
    medium_severity = 0
    high_severity = 0
    
    # Count from warnings
    if warnings:
        for category, category_warnings in warning_categories.items():
            severity = category_warnings[0]['severity']
            count = len(category_warnings)
            if severity == 'LOW':
                low_severity += count
            elif severity == 'MEDIUM':
                medium_severity += count
            else:
                high_severity += count
    
    # Count from errors
    if errors:
        for category, category_errors in error_categories.items():
            severity = category_errors[0]['severity']
            count = len(category_errors)
            if severity == 'LOW':
                low_severity += count
            elif severity == 'MEDIUM':
                medium_severity += count
            else:
                high_severity += count
    
    print(f"🟢 Low Severity: {low_severity} (expected/normal)")
    print(f"🟡 Medium Severity: {medium_severity} (monitor)")
    print(f"🔴 High Severity: {high_severity} (needs attention)")
    
    # Recommendation
    if high_severity > 0:
        print(f"\n❌ RECOMMENDATION: INVESTIGATE HIGH SEVERITY ISSUES")
        print("   Fix high severity errors before continuing long-term operation")
    elif medium_severity > 3:
        print(f"\n⚠️  RECOMMENDATION: MONITOR MEDIUM SEVERITY ISSUES")
        print("   Bot can run but monitor these issues closely")
    elif low_severity <= 10:
        print(f"\n✅ RECOMMENDATION: NORMAL OPERATION")
        print("   These are expected warnings/errors during initial operation")
        print("   Bot is safe to run for extended periods")
    else:
        print(f"\n⚠️  RECOMMENDATION: TOO MANY LOW SEVERITY ISSUES")
        print("   While individually minor, the volume suggests system stress")
    
    # Specific recommendations
    print(f"\n💡 SPECIFIC RECOMMENDATIONS:")
    
    recommendations = []
    
    if any('no signal' in w['line'].lower() for w in warnings):
        recommendations.append("🎯 'No signal' warnings are normal - strategies are being selective")
    
    if any('balance' in e['line'].lower() for e in errors):
        recommendations.append("💰 Balance errors are expected in paper trading mode")
    
    if any('insufficient' in w['line'].lower() for w in warnings):
        recommendations.append("📊 'Insufficient' warnings will decrease as the bot learns")
    
    if any('connection' in e['line'].lower() for e in errors):
        recommendations.append("🌐 Connection errors suggest network issues - check internet stability")
    
    # General recommendations
    recommendations.extend([
        "📈 Monitor for 24-48 hours to see if issues decrease",
        "🔄 Restart bot if high severity errors persist",
        "📊 Check daily_bot_monitor.py for trends"
    ])
    
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec}")
    
    return {
        'warnings': len(warnings),
        'errors': len(errors),
        'low_severity': low_severity,
        'medium_severity': medium_severity,
        'high_severity': high_severity,
        'safe_to_run': high_severity == 0 and medium_severity <= 3
    }

if __name__ == "__main__":
    result = diagnose_log_issues()
    
    print(f"\n{'='*50}")
    if result['safe_to_run']:
        print("✅ CONCLUSION: SAFE TO CONTINUE RUNNING")
        print("   Your bot is operating normally with expected startup issues")
    else:
        print("⚠️  CONCLUSION: NEEDS ATTENTION")
        print("   Address the issues above before extended operation")
    print(f"{'='*50}")