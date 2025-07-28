#!/usr/bin/env python3
"""
Enhanced Alert System Demo

This script demonstrates the capabilities of the enhanced alert system
including multi-channel notifications, custom rules, throttling, and
various alert types.
"""

import sys
import os
import time
import asyncio
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.enhanced_alerts import (
    EnhancedAlertSystem,
    AlertSeverity,
    SystemAlertType,
    AlertRule,
    RiskEvent,
    TradeExecution,
    PerformanceMetrics,
    DEFAULT_ALERT_CONFIG,
    create_enhanced_alert_system
)
from bot.enhanced_logger import EnhancedLogger


def create_demo_config():
    """Create demo configuration with console and webhook channels"""
    config = DEFAULT_ALERT_CONFIG.copy()
    
    # Enable console notifications
    config['channels']['console']['enabled'] = True
    
    # Enable webhook for demo (using httpbin.org for testing)
    config['channels']['webhook'] = {
        'enabled': True,
        'url': 'https://httpbin.org/post',
        'headers': {
            'X-Demo-Bot': 'Enhanced-Alerts-Demo',
            'Authorization': 'Bearer demo-token'
        },
        'timeout': 10
    }
    
    # Add custom alert rules
    config['rules'] = [
        {
            'rule_id': 'large_trade_rule',
            'name': 'Large Trade Detection',
            'alert_type': 'trade_executed',
            'condition': {
                'field': 'trade_value',
                'operator': 'gt',
                'value': 5000
            },
            'severity': 3,  # HIGH
            'enabled': True,
            'throttle_minutes': 10,
            'channels': ['console', 'webhook'],
            'metadata': {
                'description': 'Alerts for trades over $5000',
                'priority': 'high'
            }
        },
        {
            'rule_id': 'poor_performance_rule',
            'name': 'Poor Performance Detection',
            'alert_type': 'performance_alert',
            'condition': {
                'field': 'win_rate',
                'operator': 'lt',
                'value': 0.4
            },
            'severity': 4,  # CRITICAL
            'enabled': True,
            'throttle_minutes': 60,
            'channels': ['console', 'webhook'],
            'metadata': {
                'description': 'Alerts when win rate drops below 40%',
                'priority': 'critical'
            }
        }
    ]
    
    # Configure throttling
    config['throttling'] = {
        'trade_executed': 2,  # 2 minutes
        'system_error': 5,    # 5 minutes
        'performance_alert': 30,  # 30 minutes
        'risk_limit_approached': 15  # 15 minutes
    }
    
    return config


def demo_basic_alerts(alert_system: EnhancedAlertSystem):
    """Demonstrate basic alert functionality"""
    print("\n" + "="*60)
    print("DEMO 1: Basic Alert Types")
    print("="*60)
    
    # System alerts
    alert_system.send_system_alert(
        SystemAlertType.SYSTEM_ERROR,
        "Database connection timeout",
        AlertSeverity.HIGH,
        {
            'error_code': 'DB_TIMEOUT_001',
            'retry_count': 3,
            'last_success': '2023-12-01T10:30:00Z'
        }
    )
    
    time.sleep(1)
    
    alert_system.send_system_alert(
        SystemAlertType.WEBSOCKET_DISCONNECTED,
        "Kraken WebSocket connection lost",
        AlertSeverity.MEDIUM,
        {
            'reconnect_attempts': 2,
            'last_message': '2023-12-01T10:35:00Z',
            'reason': 'network_timeout'
        }
    )
    
    time.sleep(1)


def demo_trade_alerts(alert_system: EnhancedAlertSystem):
    """Demonstrate trade execution alerts"""
    print("\n" + "="*60)
    print("DEMO 2: Trade Execution Alerts")
    print("="*60)
    
    # Small trade (should not trigger custom rule)
    small_trade = TradeExecution(
        trade_id='TRD_001',
        pair='BTC/USD',
        side='BUY',
        quantity=0.01,
        price=45000.0,  # $450 trade value
        timestamp=datetime.now(),
        strategy='dca',
        fee=2.25
    )
    
    alert_system.send_trade_alert(small_trade)
    time.sleep(1)
    
    # Large trade (should trigger custom rule)
    large_trade = TradeExecution(
        trade_id='TRD_002',
        pair='ETH/USD',
        side='SELL',
        quantity=3.0,
        price=2500.0,  # $7500 trade value
        timestamp=datetime.now(),
        strategy='momentum',
        fee=37.50
    )
    
    alert_system.send_trade_alert(large_trade)
    time.sleep(1)


def demo_performance_alerts(alert_system: EnhancedAlertSystem):
    """Demonstrate performance metric alerts"""
    print("\n" + "="*60)
    print("DEMO 3: Performance Metric Alerts")
    print("="*60)
    
    # Good performance metrics
    good_metrics = PerformanceMetrics(
        timestamp=datetime.now(),
        total_pnl=1250.0,
        daily_pnl=150.0,
        win_rate=0.68,  # 68% win rate
        total_trades=50,
        successful_trades=34,
        sharpe_ratio=1.4,
        max_drawdown=0.08,
        current_positions={'BTC/USD': 0.5, 'ETH/USD': 1.2},
        account_balance=12500.0
    )
    
    alert_system.send_performance_alert(good_metrics)
    time.sleep(1)
    
    # Poor performance metrics (should trigger custom rule)
    poor_metrics = PerformanceMetrics(
        timestamp=datetime.now(),
        total_pnl=-450.0,
        daily_pnl=-200.0,
        win_rate=0.35,  # 35% win rate - below threshold
        total_trades=80,
        successful_trades=28,
        sharpe_ratio=0.2,
        max_drawdown=0.25,
        current_positions={'BTC/USD': -0.2},
        account_balance=8500.0
    )
    
    alert_system.send_performance_alert(poor_metrics)
    time.sleep(1)


def demo_risk_alerts(alert_system: EnhancedAlertSystem):
    """Demonstrate risk event alerts"""
    print("\n" + "="*60)
    print("DEMO 4: Risk Event Alerts")
    print("="*60)
    
    # Position limit risk
    position_risk = RiskEvent(
        event_type='position_limit',
        severity=AlertSeverity.HIGH,
        message='Position size approaching limit for BTC/USD',
        details={
            'current_position': 0.85,
            'position_limit': 1.0,
            'utilization': 0.85,
            'recommendation': 'Consider reducing position size'
        },
        pair='BTC/USD',
        position_size=0.85,
        risk_level=0.85
    )
    
    alert_system.send_risk_alert(position_risk)
    time.sleep(1)
    
    # Drawdown risk
    drawdown_risk = RiskEvent(
        event_type='max_drawdown',
        severity=AlertSeverity.CRITICAL,
        message='Maximum drawdown limit exceeded',
        details={
            'current_drawdown': 0.22,
            'max_allowed': 0.20,
            'excess': 0.02,
            'action_taken': 'Emergency position reduction initiated'
        },
        risk_level=1.1
    )
    
    alert_system.send_risk_alert(drawdown_risk)
    time.sleep(1)


def demo_summary_alerts(alert_system: EnhancedAlertSystem):
    """Demonstrate summary alerts"""
    print("\n" + "="*60)
    print("DEMO 5: Summary Reports")
    print("="*60)
    
    # Daily summary
    daily_summary = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'daily_pnl': 275.50,
        'total_trades': 18,
        'successful_trades': 12,
        'win_rate': 0.67,
        'best_trade': 85.25,
        'worst_trade': -32.10,
        'total_fees': 24.75,
        'active_pairs': ['BTC/USD', 'ETH/USD', 'ADA/USD'],
        'strategies_used': ['momentum', 'mean_reversion', 'dca'],
        'market_conditions': 'bullish'
    }
    
    alert_system.send_daily_summary(daily_summary)
    time.sleep(1)
    
    # Weekly summary
    weekly_summary = {
        'week_start': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
        'week_end': datetime.now().strftime('%Y-%m-%d'),
        'weekly_pnl': 1450.75,
        'total_trades': 125,
        'successful_trades': 82,
        'win_rate': 0.656,
        'best_day': 425.30,
        'worst_day': -185.20,
        'sharpe_ratio': 1.35,
        'max_drawdown': 0.12,
        'volatility': 0.18,
        'total_volume': 45000.0
    }
    
    alert_system.send_weekly_summary(weekly_summary)
    time.sleep(1)


def demo_alert_statistics(alert_system: EnhancedAlertSystem):
    """Display alert system statistics"""
    print("\n" + "="*60)
    print("DEMO 6: Alert System Statistics")
    print("="*60)
    
    # Wait a moment for processing
    time.sleep(2)
    
    stats = alert_system.get_alert_statistics()
    
    print(f"Total alerts sent: {stats['total_alerts']}")
    print(f"Active rules: {stats['active_rules']}")
    print(f"Enabled channels: {stats['enabled_channels']}")
    print(f"Queue size: {stats['queue_size']}")
    
    print("\nAlerts by type:")
    for alert_type, count in stats['alerts_by_type'].items():
        print(f"  {alert_type}: {count}")
    
    print("\nAlerts by severity:")
    for severity, count in stats['alerts_by_severity'].items():
        print(f"  {severity}: {count}")
    
    print("\nChannel success rates:")
    for channel, rate in stats['channel_success_rates'].items():
        print(f"  {channel}: {rate:.1%}")


def main():
    """Main demo function"""
    print("Enhanced Alert System Demo")
    print("=" * 60)
    print("This demo showcases the enhanced alert system capabilities:")
    print("- Multi-channel notifications (console + webhook)")
    print("- Custom alert rules with conditions")
    print("- Alert prioritization and throttling")
    print("- Various alert types (trades, performance, risk, summaries)")
    print("- Real-time statistics and monitoring")
    
    # Create demo configuration
    config = create_demo_config()
    
    # Create enhanced logger for the demo
    logger_config = {
        'log_level': 'INFO',
        'log_file': 'logs/enhanced_alerts_demo.log',
        'max_file_size': 10 * 1024 * 1024,
        'backup_count': 3,
        'use_rich': False
    }
    logger = EnhancedLogger(logger_config)
    
    # Create alert system
    alert_system = EnhancedAlertSystem(config, logger)
    
    try:
        # Run demos
        demo_basic_alerts(alert_system)
        demo_trade_alerts(alert_system)
        demo_performance_alerts(alert_system)
        demo_risk_alerts(alert_system)
        demo_summary_alerts(alert_system)
        demo_alert_statistics(alert_system)
        
        print("\n" + "="*60)
        print("Demo completed successfully!")
        print("Check the logs/enhanced_alerts_demo.log file for detailed logs.")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo error: {e}")
    finally:
        # Shutdown alert system
        print("\nShutting down alert system...")
        alert_system.shutdown()
        print("Demo finished.")


if __name__ == '__main__':
    main()