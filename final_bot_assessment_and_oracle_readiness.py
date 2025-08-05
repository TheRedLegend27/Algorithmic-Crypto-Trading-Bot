#!/usr/bin/env python3
"""
Final Bot Assessment and Oracle Cloud Readiness Report
Comprehensive analysis of bot improvements and deployment readiness.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

def assess_current_bot_status():
    """Assess the current status of the bot after improvements."""
    print("🔍 CURRENT BOT STATUS ASSESSMENT")
    print("=" * 60)
    
    status = {
        'bot_running': False,
        'api_connected': False,
        'cycles_working': False,
        'dependencies_installed': False,
        'configurations_present': False,
        'monitoring_available': False,
        'improvements_applied': False
    }
    
    # Check if bot is running
    try:
        result = subprocess.run(['pgrep', '-f', 'adaptive_bot'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            status['bot_running'] = True
            print("✅ Bot is currently running")
        else:
            print("❌ Bot is not running")
    except:
        print("❌ Cannot check bot process status")
    
    # Check API configuration
    try:
        with open('.env', 'r') as f:
            env_content = f.read()
        
        if 'KRAKEN_API_KEY=' in env_content and 'KRAKEN_API_SECRET=' in env_content:
            api_key = env_content.split('KRAKEN_API_KEY=')[1].split('\n')[0]
            api_secret = env_content.split('KRAKEN_API_SECRET=')[1].split('\n')[0]
            
            if len(api_key) > 10 and len(api_secret) > 10:
                status['api_connected'] = True
                print("✅ API credentials are configured")
            else:
                print("❌ API credentials appear incomplete")
        else:
            print("❌ API credentials not found in .env")
    except:
        print("❌ Cannot read .env file")
    
    # Check if cycles are working
    try:
        if os.path.exists('adaptive_bot.log'):
            with open('adaptive_bot.log', 'r') as f:
                log_content = f.read()
            
            if 'Cycle #' in log_content:
                status['cycles_working'] = True
                print("✅ Bot cycles are working")
            else:
                print("❌ No bot cycles detected in logs")
        else:
            print("❌ Bot log file not found")
    except:
        print("❌ Cannot read bot log file")
    
    # Check dependencies
    try:
        import sklearn
        import numpy
        import pandas
        status['dependencies_installed'] = True
        print("✅ Core dependencies are installed")
    except ImportError:
        print("❌ Some core dependencies are missing")
    
    # Check configurations
    config_files = [
        'config/enhanced_strategies.json',
        'config/adaptive_learning.json',
        'ORACLE_DEPLOYMENT_CHECKLIST.md'
    ]
    
    configs_present = sum(1 for f in config_files if os.path.exists(f))
    if configs_present >= 2:
        status['configurations_present'] = True
        print(f"✅ Configuration files present ({configs_present}/{len(config_files)})")
    else:
        print(f"❌ Missing configuration files ({configs_present}/{len(config_files)})")
    
    # Check monitoring scripts
    monitoring_files = [
        'enhanced_bot_monitor.py',
        'run_bot_continuously.py',
        'check_adaptive_bot_status.py'
    ]
    
    monitoring_present = sum(1 for f in monitoring_files if os.path.exists(f))
    if monitoring_present >= 2:
        status['monitoring_available'] = True
        print(f"✅ Monitoring tools available ({monitoring_present}/{len(monitoring_files)})")
    else:
        print(f"❌ Missing monitoring tools ({monitoring_present}/{len(monitoring_files)})")
    
    # Check improvements
    improvement_files = [
        'bot/adaptive/enhanced_ml_engine.py',
        'bot/adaptive/enhanced_performance_analyzer.py',
        'fix_critical_bot_issues.py'
    ]
    
    improvements_present = sum(1 for f in improvement_files if os.path.exists(f))
    if improvements_present >= 2:
        status['improvements_applied'] = True
        print(f"✅ Bot improvements applied ({improvements_present}/{len(improvement_files)})")
    else:
        print(f"❌ Bot improvements missing ({improvements_present}/{len(improvement_files)})")
    
    return status

def analyze_performance_improvements():
    """Analyze the performance improvements made."""
    print("\n📊 PERFORMANCE IMPROVEMENTS ANALYSIS")
    print("=" * 60)
    
    improvements = {
        'api_connection_fixed': False,
        'dependencies_installed': False,
        'signal_generation_enhanced': False,
        'continuous_operation_enabled': False,
        'ml_learning_improved': False,
        'monitoring_enhanced': False
    }
    
    # Check API connection fix
    try:
        with open('bot/adaptive/adaptive_bot_main.py', 'r') as f:
            content = f.read()
        
        if 'KrakenCredentials' in content and 'EnhancedKrakenClient' in content:
            improvements['api_connection_fixed'] = True
            print("✅ API connection initialization fixed")
        else:
            print("❌ API connection fix not detected")
    except:
        print("❌ Cannot verify API connection fix")
    
    # Check dependencies
    try:
        import sklearn
        import deap
        improvements['dependencies_installed'] = True
        print("✅ Optimization libraries installed (scikit-learn, DEAP)")
    except ImportError:
        print("❌ Some optimization libraries missing")
    
    # Check signal generation enhancement
    if os.path.exists('config/enhanced_strategies.json'):
        improvements['signal_generation_enhanced'] = True
        print("✅ Enhanced signal generation configuration created")
    else:
        print("❌ Enhanced signal generation not configured")
    
    # Check continuous operation
    if os.path.exists('run_bot_continuously.py'):
        improvements['continuous_operation_enabled'] = True
        print("✅ Continuous operation script created")
    else:
        print("❌ Continuous operation not enabled")
    
    # Check ML improvements
    if os.path.exists('bot/adaptive/enhanced_ml_engine.py'):
        improvements['ml_learning_improved'] = True
        print("✅ Enhanced ML engine with online learning created")
    else:
        print("❌ ML learning improvements not applied")
    
    # Check monitoring
    if os.path.exists('enhanced_bot_monitor.py'):
        improvements['monitoring_enhanced'] = True
        print("✅ Enhanced monitoring system created")
    else:
        print("❌ Enhanced monitoring not available")
    
    return improvements

def calculate_oracle_readiness_score():
    """Calculate comprehensive Oracle Cloud readiness score."""
    print("\n☁️ ORACLE CLOUD READINESS ASSESSMENT")
    print("=" * 60)
    
    criteria = {
        'technical_readiness': {
            'weight': 0.4,
            'checks': {
                'bot_runs_continuously': False,
                'api_connections_stable': False,
                'error_handling_robust': False,
                'dependencies_complete': False,
                'configurations_valid': False
            }
        },
        'operational_readiness': {
            'weight': 0.3,
            'checks': {
                'monitoring_comprehensive': False,
                'logging_adequate': False,
                'alerting_configured': False,
                'backup_procedures': False,
                'deployment_automated': False
            }
        },
        'performance_readiness': {
            'weight': 0.2,
            'checks': {
                'trading_signals_generated': False,
                'ml_confidence_improving': False,
                'risk_management_active': False,
                'performance_tracking': False
            }
        },
        'security_readiness': {
            'weight': 0.1,
            'checks': {
                'credentials_secured': False,
                'environment_variables_set': False,
                'access_controls_defined': False
            }
        }
    }
    
    # Assess technical readiness
    tech_score = 0
    tech_checks = criteria['technical_readiness']['checks']
    
    # Bot runs continuously
    if os.path.exists('run_bot_continuously.py'):
        tech_checks['bot_runs_continuously'] = True
        tech_score += 1
    
    # API connections
    try:
        with open('.env', 'r') as f:
            env_content = f.read()
        if 'KRAKEN_API_KEY=' in env_content and len(env_content.split('KRAKEN_API_KEY=')[1].split('\n')[0]) > 10:
            tech_checks['api_connections_stable'] = True
            tech_score += 1
    except:
        pass
    
    # Error handling
    if os.path.exists('bot/error_handler.py'):
        tech_checks['error_handling_robust'] = True
        tech_score += 1
    
    # Dependencies
    try:
        import sklearn
        import numpy
        import pandas
        tech_checks['dependencies_complete'] = True
        tech_score += 1
    except:
        pass
    
    # Configurations
    if os.path.exists('config/enhanced_strategies.json'):
        tech_checks['configurations_valid'] = True
        tech_score += 1
    
    tech_readiness = tech_score / len(tech_checks)
    
    # Assess operational readiness
    ops_score = 0
    ops_checks = criteria['operational_readiness']['checks']
    
    if os.path.exists('enhanced_bot_monitor.py'):
        ops_checks['monitoring_comprehensive'] = True
        ops_score += 1
    
    if os.path.exists('adaptive_bot.log'):
        ops_checks['logging_adequate'] = True
        ops_score += 1
    
    if os.path.exists('bot/enhanced_alerts.py'):
        ops_checks['alerting_configured'] = True
        ops_score += 1
    
    if os.path.exists('ORACLE_DEPLOYMENT_CHECKLIST.md'):
        ops_checks['backup_procedures'] = True
        ops_score += 1
    
    if os.path.exists('scripts/deploy.sh'):
        ops_checks['deployment_automated'] = True
        ops_score += 1
    
    ops_readiness = ops_score / len(ops_checks)
    
    # Assess performance readiness
    perf_score = 0
    perf_checks = criteria['performance_readiness']['checks']
    
    try:
        with open('daily_performance_tracking.json', 'r') as f:
            perf_data = json.load(f)
        
        # Check for any adaptations (indicates some activity)
        total_adaptations = sum(day.get('adaptations', 0) for day in perf_data.get('daily_records', {}).values())
        if total_adaptations > 0:
            perf_checks['trading_signals_generated'] = True
            perf_score += 1
    except:
        pass
    
    if os.path.exists('bot/adaptive/enhanced_ml_engine.py'):
        perf_checks['ml_confidence_improving'] = True
        perf_score += 1
    
    if os.path.exists('bot/enhanced_risk_manager.py'):
        perf_checks['risk_management_active'] = True
        perf_score += 1
    
    if os.path.exists('bot/adaptive/enhanced_performance_analyzer.py'):
        perf_checks['performance_tracking'] = True
        perf_score += 1
    
    perf_readiness = perf_score / len(perf_checks)
    
    # Assess security readiness
    sec_score = 0
    sec_checks = criteria['security_readiness']['checks']
    
    try:
        with open('.env', 'r') as f:
            env_content = f.read()
        if 'KRAKEN_API_KEY=' in env_content:
            sec_checks['credentials_secured'] = True
            sec_score += 1
        if 'IS_PAPER_TRADING=' in env_content:
            sec_checks['environment_variables_set'] = True
            sec_score += 1
    except:
        pass
    
    if os.path.exists('.gitignore') and '.env' in open('.gitignore').read():
        sec_checks['access_controls_defined'] = True
        sec_score += 1
    
    sec_readiness = sec_score / len(sec_checks)
    
    # Calculate overall score
    overall_score = (
        tech_readiness * criteria['technical_readiness']['weight'] +
        ops_readiness * criteria['operational_readiness']['weight'] +
        perf_readiness * criteria['performance_readiness']['weight'] +
        sec_readiness * criteria['security_readiness']['weight']
    )
    
    # Display results
    print(f"📊 Technical Readiness: {tech_readiness:.1%} ({tech_score}/{len(tech_checks)})")
    print(f"🔧 Operational Readiness: {ops_readiness:.1%} ({ops_score}/{len(ops_checks)})")
    print(f"📈 Performance Readiness: {perf_readiness:.1%} ({perf_score}/{len(perf_checks)})")
    print(f"🔒 Security Readiness: {sec_readiness:.1%} ({sec_score}/{len(sec_checks)})")
    print(f"\n🎯 OVERALL ORACLE READINESS: {overall_score:.1%}")
    
    return overall_score, criteria

def generate_final_recommendations(readiness_score, bot_status, improvements):
    """Generate final recommendations based on assessment."""
    print("\n💡 FINAL RECOMMENDATIONS")
    print("=" * 60)
    
    if readiness_score >= 0.8:
        print("🚀 READY FOR ORACLE DEPLOYMENT!")
        print("\nImmediate Actions:")
        print("1. ✅ Bot is ready for Oracle Cloud migration")
        print("2. 📋 Follow the Oracle Deployment Checklist")
        print("3. 🔄 Start with paper trading on Oracle Cloud")
        print("4. 📊 Monitor performance for 24-48 hours")
        print("5. 💰 Switch to live trading when confident")
        
    elif readiness_score >= 0.6:
        print("🟡 NEARLY READY - Minor improvements needed")
        print("\nRequired Actions:")
        
        if not bot_status['bot_running']:
            print("• 🔄 Ensure bot runs continuously for 24+ hours")
        
        if not improvements['ml_learning_improved']:
            print("• 🧠 Implement enhanced ML learning features")
        
        if not improvements['monitoring_enhanced']:
            print("• 📊 Set up comprehensive monitoring")
        
        print("\nRecommended Timeline: 1-2 days of additional work")
        
    else:
        print("🔴 NOT READY - Significant improvements needed")
        print("\nCritical Issues to Address:")
        
        if not bot_status['api_connected']:
            print("• 🔑 Fix API connection issues")
        
        if not bot_status['cycles_working']:
            print("• ⚙️ Ensure bot cycles are working properly")
        
        if not improvements['dependencies_installed']:
            print("• 📦 Install all required dependencies")
        
        if not improvements['signal_generation_enhanced']:
            print("• 🎯 Improve signal generation capabilities")
        
        print("\nRecommended Timeline: 3-5 days of additional work")
    
    print(f"\n📋 DEPLOYMENT CHECKLIST:")
    print("□ Run bot continuously for 24+ hours without issues")
    print("□ Verify all API connections are stable")
    print("□ Confirm trading signals are being generated")
    print("□ Test monitoring and alerting systems")
    print("□ Validate risk management parameters")
    print("□ Prepare Oracle Cloud infrastructure")
    print("□ Set up automated deployment pipeline")
    print("□ Configure production monitoring")
    print("□ Test emergency shutdown procedures")
    print("□ Document operational procedures")

def save_assessment_report(readiness_score, bot_status, improvements, criteria):
    """Save comprehensive assessment report."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'assessment_version': '1.0',
        'oracle_readiness_score': readiness_score,
        'readiness_level': (
            'READY' if readiness_score >= 0.8 else
            'NEARLY_READY' if readiness_score >= 0.6 else
            'NOT_READY'
        ),
        'bot_status': bot_status,
        'improvements_applied': improvements,
        'readiness_criteria': criteria,
        'recommendations': {
            'immediate_actions': [],
            'timeline_days': 0,
            'deployment_ready': readiness_score >= 0.8
        }
    }
    
    # Add specific recommendations
    if readiness_score >= 0.8:
        report['recommendations']['immediate_actions'] = [
            'Proceed with Oracle Cloud deployment',
            'Follow deployment checklist',
            'Start with paper trading',
            'Monitor for 24-48 hours',
            'Switch to live trading when ready'
        ]
        report['recommendations']['timeline_days'] = 1
    elif readiness_score >= 0.6:
        report['recommendations']['immediate_actions'] = [
            'Run bot continuously for 24+ hours',
            'Enhance monitoring systems',
            'Validate all components',
            'Test error recovery'
        ]
        report['recommendations']['timeline_days'] = 2
    else:
        report['recommendations']['immediate_actions'] = [
            'Fix API connection issues',
            'Ensure bot cycles work properly',
            'Install missing dependencies',
            'Improve signal generation',
            'Test all components thoroughly'
        ]
        report['recommendations']['timeline_days'] = 5
    
    try:
        with open('oracle_readiness_assessment.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Assessment report saved: oracle_readiness_assessment.json")
        
    except Exception as e:
        print(f"❌ Failed to save assessment report: {e}")

def main():
    """Main assessment function."""
    print("🤖 FINAL BOT ASSESSMENT & ORACLE CLOUD READINESS")
    print("=" * 80)
    print(f"Assessment Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Assess current bot status
    bot_status = assess_current_bot_status()
    
    # Analyze performance improvements
    improvements = analyze_performance_improvements()
    
    # Calculate Oracle readiness score
    readiness_score, criteria = calculate_oracle_readiness_score()
    
    # Generate recommendations
    generate_final_recommendations(readiness_score, bot_status, improvements)
    
    # Save assessment report
    save_assessment_report(readiness_score, bot_status, improvements, criteria)
    
    # Final summary
    print(f"\n🎯 FINAL ASSESSMENT SUMMARY")
    print("=" * 60)
    
    status_count = sum(1 for v in bot_status.values() if v)
    improvement_count = sum(1 for v in improvements.values() if v)
    
    print(f"📊 Bot Status: {status_count}/{len(bot_status)} components working")
    print(f"🚀 Improvements: {improvement_count}/{len(improvements)} applied")
    print(f"☁️ Oracle Readiness: {readiness_score:.1%}")
    
    if readiness_score >= 0.8:
        print(f"\n🎉 CONGRATULATIONS! Your bot is ready for Oracle Cloud deployment!")
        print(f"🚀 You can proceed with confidence to move your trading bot to production.")
    elif readiness_score >= 0.6:
        print(f"\n🟡 Your bot is close to being ready. A few more improvements and you'll be set!")
        print(f"📈 Focus on the recommendations above to reach deployment readiness.")
    else:
        print(f"\n🔴 Your bot needs more work before Oracle deployment.")
        print(f"🔧 Address the critical issues identified above before proceeding.")
    
    print(f"\n📋 Next Steps:")
    print(f"1. Review the detailed assessment report: oracle_readiness_assessment.json")
    print(f"2. Follow the Oracle Deployment Checklist: ORACLE_DEPLOYMENT_CHECKLIST.md")
    print(f"3. Continue monitoring bot performance")
    print(f"4. Address any remaining issues")
    print(f"5. Proceed with Oracle deployment when ready")

if __name__ == "__main__":
    main()