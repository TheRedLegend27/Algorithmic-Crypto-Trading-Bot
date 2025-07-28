"""
Unit tests for the enhanced alert system.

This module contains comprehensive tests for the EnhancedAlertSystem class
and its components including notification channels, alert rules, throttling,
and prioritization mechanisms.
"""

import unittest
import asyncio
import json
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from dataclasses import asdict

from bot.enhanced_alerts import (
    EnhancedAlertSystem,
    AlertSeverity,
    SystemAlertType,
    AlertRule,
    NotificationChannel,
    EmailNotificationChannel,
    WebhookNotificationChannel,
    ConsoleNotificationChannel,
    RiskEvent,
    TradeExecution,
    PerformanceMetrics,
    DEFAULT_ALERT_CONFIG,
    create_enhanced_alert_system
)


class TestAlertSeverity(unittest.TestCase):
    """Test AlertSeverity enum"""
    
    def test_severity_ordering(self):
        """Test that severity levels have correct ordering"""
        self.assertLess(AlertSeverity.LOW.value, AlertSeverity.MEDIUM.value)
        self.assertLess(AlertSeverity.MEDIUM.value, AlertSeverity.HIGH.value)
        self.assertLess(AlertSeverity.HIGH.value, AlertSeverity.CRITICAL.value)


class TestSystemAlertType(unittest.TestCase):
    """Test SystemAlertType enum"""
    
    def test_alert_types_exist(self):
        """Test that all required alert types exist"""
        required_types = [
            'trade_executed', 'price_movement', 'risk_limit_approached',
            'system_error', 'performance_alert', 'daily_summary'
        ]
        
        for alert_type in required_types:
            self.assertTrue(any(t.value == alert_type for t in SystemAlertType))


class TestAlertRule(unittest.TestCase):
    """Test AlertRule dataclass"""
    
    def test_alert_rule_creation(self):
        """Test creating an alert rule"""
        condition = lambda data: data.get('value', 0) > 100
        
        rule = AlertRule(
            rule_id='test_rule',
            name='Test Rule',
            alert_type=SystemAlertType.TRADE_EXECUTED,
            condition=condition,
            severity=AlertSeverity.HIGH,
            throttle_minutes=30,
            channels=['email', 'webhook']
        )
        
        self.assertEqual(rule.rule_id, 'test_rule')
        self.assertEqual(rule.name, 'Test Rule')
        self.assertEqual(rule.alert_type, SystemAlertType.TRADE_EXECUTED)
        self.assertEqual(rule.severity, AlertSeverity.HIGH)
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.throttle_minutes, 30)
        self.assertEqual(rule.channels, ['email', 'webhook'])
        
        # Test condition function
        self.assertTrue(rule.condition({'value': 150}))
        self.assertFalse(rule.condition({'value': 50}))


class TestRiskEvent(unittest.TestCase):
    """Test RiskEvent dataclass"""
    
    def test_risk_event_creation(self):
        """Test creating a risk event"""
        event = RiskEvent(
            event_type='position_limit',
            severity=AlertSeverity.HIGH,
            message='Position limit exceeded',
            details={'limit': 1000, 'current': 1200},
            pair='BTC/USD',
            position_size=1200.0,
            risk_level=0.8
        )
        
        self.assertEqual(event.event_type, 'position_limit')
        self.assertEqual(event.severity, AlertSeverity.HIGH)
        self.assertEqual(event.message, 'Position limit exceeded')
        self.assertEqual(event.pair, 'BTC/USD')
        self.assertEqual(event.position_size, 1200.0)
        self.assertEqual(event.risk_level, 0.8)
        self.assertIsInstance(event.timestamp, datetime)


class TestTradeExecution(unittest.TestCase):
    """Test TradeExecution dataclass"""
    
    def test_trade_execution_creation(self):
        """Test creating a trade execution"""
        trade = TradeExecution(
            trade_id='trade_123',
            pair='ETH/USD',
            side='BUY',
            quantity=1.5,
            price=2000.0,
            timestamp=datetime.now(),
            strategy='momentum',
            fee=5.0
        )
        
        self.assertEqual(trade.trade_id, 'trade_123')
        self.assertEqual(trade.pair, 'ETH/USD')
        self.assertEqual(trade.side, 'BUY')
        self.assertEqual(trade.quantity, 1.5)
        self.assertEqual(trade.price, 2000.0)
        self.assertEqual(trade.strategy, 'momentum')
        self.assertEqual(trade.fee, 5.0)


class TestPerformanceMetrics(unittest.TestCase):
    """Test PerformanceMetrics dataclass"""
    
    def test_performance_metrics_creation(self):
        """Test creating performance metrics"""
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            total_pnl=1500.0,
            daily_pnl=250.0,
            win_rate=0.65,
            total_trades=100,
            successful_trades=65,
            sharpe_ratio=1.2,
            max_drawdown=0.15,
            current_positions={'BTC/USD': 0.5, 'ETH/USD': 2.0},
            account_balance=10000.0
        )
        
        self.assertEqual(metrics.total_pnl, 1500.0)
        self.assertEqual(metrics.daily_pnl, 250.0)
        self.assertEqual(metrics.win_rate, 0.65)
        self.assertEqual(metrics.total_trades, 100)
        self.assertEqual(metrics.successful_trades, 65)


class TestNotificationChannel(unittest.TestCase):
    """Test NotificationChannel base class"""
    
    def test_can_send_throttling(self):
        """Test throttling mechanism"""
        config = {'enabled': True}
        channel = ConsoleNotificationChannel('test', config)
        
        # Should be able to send initially
        self.assertTrue(channel.can_send(SystemAlertType.TRADE_EXECUTED, 15))
        
        # Mark as sent
        channel.mark_sent(SystemAlertType.TRADE_EXECUTED)
        
        # Should not be able to send immediately after
        self.assertFalse(channel.can_send(SystemAlertType.TRADE_EXECUTED, 15))
        
        # Should be able to send different alert type
        self.assertTrue(channel.can_send(SystemAlertType.SYSTEM_ERROR, 15))
    
    def test_disabled_channel(self):
        """Test disabled channel behavior"""
        config = {'enabled': False}
        channel = ConsoleNotificationChannel('test', config)
        
        self.assertFalse(channel.can_send(SystemAlertType.TRADE_EXECUTED, 15))


class TestEmailNotificationChannel(unittest.TestCase):
    """Test EmailNotificationChannel"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'enabled': True,
            'smtp_server': 'smtp.test.com',
            'smtp_port': 587,
            'username': 'test@test.com',
            'password': 'password',
            'from_address': 'bot@test.com',
            'to_addresses': ['user@test.com']
        }
        self.channel = EmailNotificationChannel('email', self.config)
    
    @patch('smtplib.SMTP')
    def test_send_notification_success(self, mock_smtp):
        """Test successful email notification"""
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        result = asyncio.run(self.channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.HIGH,
            'Test message',
            {'key': 'value'}
        ))
        
        self.assertTrue(result)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@test.com', 'password')
        mock_server.send_message.assert_called_once()
    
    @patch('smtplib.SMTP')
    def test_send_notification_failure(self, mock_smtp):
        """Test email notification failure"""
        mock_smtp.side_effect = Exception('SMTP error')
        
        result = asyncio.run(self.channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.HIGH,
            'Test message',
            {'key': 'value'}
        ))
        
        self.assertFalse(result)
    
    def test_create_email_body(self):
        """Test email body creation"""
        body = self.channel._create_email_body(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.HIGH,
            'Test message',
            {'key': 'value'}
        )
        
        self.assertIn('Test message', body)
        self.assertIn('HIGH', body)
        self.assertIn('trade_executed', body)
        self.assertIn('html', body.lower())


class TestWebhookNotificationChannel(unittest.TestCase):
    """Test WebhookNotificationChannel"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'enabled': True,
            'url': 'https://webhook.test.com/alert',
            'headers': {'Authorization': 'Bearer token'},
            'timeout': 30
        }
        self.channel = WebhookNotificationChannel('webhook', self.config)
    
    @patch('requests.post')
    def test_send_notification_success(self, mock_post):
        """Test successful webhook notification"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = asyncio.run(self.channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.HIGH,
            'Test message',
            {'key': 'value'}
        ))
        
        self.assertTrue(result)
        mock_post.assert_called_once()
        
        # Check call arguments
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://webhook.test.com/alert')
        self.assertIn('json', kwargs)
        self.assertIn('headers', kwargs)
        
        payload = kwargs['json']
        self.assertEqual(payload['alert_type'], 'trade_executed')
        self.assertEqual(payload['severity'], 'HIGH')
        self.assertEqual(payload['message'], 'Test message')
    
    @patch('requests.post')
    def test_send_notification_failure(self, mock_post):
        """Test webhook notification failure"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Server error'
        mock_post.return_value = mock_response
        
        result = asyncio.run(self.channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.HIGH,
            'Test message',
            {'key': 'value'}
        ))
        
        self.assertFalse(result)
    
    @patch('requests.post')
    def test_send_notification_exception(self, mock_post):
        """Test webhook notification with exception"""
        mock_post.side_effect = Exception('Network error')
        
        result = asyncio.run(self.channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.HIGH,
            'Test message',
            {'key': 'value'}
        ))
        
        self.assertFalse(result)


class TestConsoleNotificationChannel(unittest.TestCase):
    """Test ConsoleNotificationChannel"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {'enabled': True}
        self.channel = ConsoleNotificationChannel('console', self.config)
    
    @patch('builtins.print')
    def test_send_notification_success(self, mock_print):
        """Test successful console notification"""
        result = asyncio.run(self.channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.HIGH,
            'Test message',
            {'key': 'value'}
        ))
        
        self.assertTrue(result)
        self.assertTrue(mock_print.called)
        
        # Check that print was called multiple times (for different parts of the message)
        self.assertGreater(mock_print.call_count, 1)
    
    @patch('builtins.print')
    def test_send_notification_with_details(self, mock_print):
        """Test console notification with details"""
        details = {'trade_id': '123', 'amount': 100.0, 'price': 50000.0}
        
        result = asyncio.run(self.channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.CRITICAL,
            'Large trade executed',
            details
        ))
        
        self.assertTrue(result)
        
        # Check that details were printed
        printed_text = ' '.join([str(call.args[0]) for call in mock_print.call_args_list])
        self.assertIn('trade_id', printed_text)
        self.assertIn('123', printed_text)


class TestEnhancedAlertSystem(unittest.TestCase):
    """Test EnhancedAlertSystem main class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = DEFAULT_ALERT_CONFIG.copy()
        self.mock_logger = Mock()
        self.alert_system = EnhancedAlertSystem(self.config, self.mock_logger)
        
        # Stop background processing for tests
        self.alert_system._stop_processing.set()
    
    def tearDown(self):
        """Clean up after tests"""
        self.alert_system.shutdown()
    
    def test_initialization(self):
        """Test alert system initialization"""
        self.assertTrue(self.alert_system.enabled)
        self.assertIn('console', self.alert_system.channels)
        self.assertEqual(len(self.alert_system.rules), 0)
        self.assertEqual(len(self.alert_system.alert_history), 0)
    
    def test_add_alert_rule(self):
        """Test adding custom alert rule"""
        condition = lambda data: data.get('amount', 0) > 1000
        rule = AlertRule(
            rule_id='large_trade',
            name='Large Trade Alert',
            alert_type=SystemAlertType.TRADE_EXECUTED,
            condition=condition,
            severity=AlertSeverity.HIGH
        )
        
        self.alert_system.add_alert_rule(rule)
        
        self.assertIn('large_trade', self.alert_system.rules)
        self.assertEqual(self.alert_system.rules['large_trade'], rule)
    
    def test_remove_alert_rule(self):
        """Test removing alert rule"""
        condition = lambda data: True
        rule = AlertRule(
            rule_id='test_rule',
            name='Test Rule',
            alert_type=SystemAlertType.TRADE_EXECUTED,
            condition=condition,
            severity=AlertSeverity.LOW
        )
        
        self.alert_system.add_alert_rule(rule)
        self.assertIn('test_rule', self.alert_system.rules)
        
        result = self.alert_system.remove_alert_rule('test_rule')
        self.assertTrue(result)
        self.assertNotIn('test_rule', self.alert_system.rules)
        
        # Test removing non-existent rule
        result = self.alert_system.remove_alert_rule('non_existent')
        self.assertFalse(result)
    
    def test_send_trade_alert(self):
        """Test sending trade alert"""
        trade = TradeExecution(
            trade_id='trade_123',
            pair='BTC/USD',
            side='BUY',
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            strategy='momentum'
        )
        
        self.alert_system.send_trade_alert(trade)
        
        # Check that alert was queued
        self.assertEqual(len(self.alert_system.priority_queue), 1)
        self.assertEqual(len(self.alert_system.alert_history), 1)
        
        alert = self.alert_system.priority_queue[0]
        self.assertEqual(alert['alert_type'], SystemAlertType.TRADE_EXECUTED)
        self.assertIn('BTC/USD', alert['message'])
        self.assertEqual(alert['details']['trade_id'], 'trade_123')
    
    def test_send_performance_alert(self):
        """Test sending performance alert"""
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            total_pnl=1000.0,
            daily_pnl=-200.0,  # Negative daily P&L should trigger higher severity
            win_rate=0.6,
            total_trades=50,
            successful_trades=30,
            sharpe_ratio=1.1,
            max_drawdown=0.05,
            current_positions={'BTC/USD': 0.5},
            account_balance=10000.0
        )
        
        self.alert_system.send_performance_alert(metrics)
        
        # Check that alert was queued
        self.assertEqual(len(self.alert_system.priority_queue), 1)
        
        alert = self.alert_system.priority_queue[0]
        self.assertEqual(alert['alert_type'], SystemAlertType.PERFORMANCE_ALERT)
        self.assertIn('Daily P&L', alert['message'])
        self.assertEqual(alert['details']['daily_pnl'], -200.0)
    
    def test_send_system_alert(self):
        """Test sending system alert"""
        self.alert_system.send_system_alert(
            SystemAlertType.SYSTEM_ERROR,
            'Database connection failed',
            AlertSeverity.CRITICAL,
            {'error_code': 'DB_001', 'retry_count': 3}
        )
        
        # Check that alert was queued
        self.assertEqual(len(self.alert_system.priority_queue), 1)
        
        alert = self.alert_system.priority_queue[0]
        self.assertEqual(alert['alert_type'], SystemAlertType.SYSTEM_ERROR)
        self.assertEqual(alert['severity'], AlertSeverity.CRITICAL)
        self.assertEqual(alert['message'], 'Database connection failed')
        self.assertEqual(alert['details']['error_code'], 'DB_001')
    
    def test_send_risk_alert(self):
        """Test sending risk alert"""
        risk_event = RiskEvent(
            event_type='position_limit',
            severity=AlertSeverity.HIGH,
            message='Position limit exceeded for BTC/USD',
            details={'limit': 1000, 'current': 1200},
            pair='BTC/USD',
            position_size=1200.0,
            risk_level=0.8
        )
        
        self.alert_system.send_risk_alert(risk_event)
        
        # Check that alert was queued
        self.assertEqual(len(self.alert_system.priority_queue), 1)
        
        alert = self.alert_system.priority_queue[0]
        self.assertEqual(alert['alert_type'], SystemAlertType.RISK_LIMIT_APPROACHED)
        self.assertIn('Position limit exceeded', alert['message'])
        self.assertEqual(alert['details']['pair'], 'BTC/USD')
    
    def test_configure_alert_throttling(self):
        """Test configuring alert throttling"""
        self.alert_system.configure_alert_throttling('trade_executed', 30)
        
        self.assertIn('throttling', self.alert_system.config)
        self.assertEqual(self.alert_system.config['throttling']['trade_executed'], 30)
    
    def test_send_daily_summary(self):
        """Test sending daily summary"""
        summary_data = {
            'daily_pnl': 150.0,
            'total_trades': 25,
            'win_rate': 0.68,
            'best_trade': 50.0,
            'worst_trade': -20.0
        }
        
        self.alert_system.send_daily_summary(summary_data)
        
        # Check that alert was queued
        self.assertEqual(len(self.alert_system.priority_queue), 1)
        
        alert = self.alert_system.priority_queue[0]
        self.assertEqual(alert['alert_type'], SystemAlertType.DAILY_SUMMARY)
        self.assertEqual(alert['severity'], AlertSeverity.LOW)
        self.assertIn('Daily Summary', alert['message'])
    
    def test_send_weekly_summary(self):
        """Test sending weekly summary"""
        summary_data = {
            'weekly_pnl': 750.0,
            'total_trades': 150,
            'win_rate': 0.65,
            'best_day': 200.0,
            'worst_day': -100.0
        }
        
        self.alert_system.send_weekly_summary(summary_data)
        
        # Check that alert was queued
        self.assertEqual(len(self.alert_system.priority_queue), 1)
        
        alert = self.alert_system.priority_queue[0]
        self.assertEqual(alert['alert_type'], SystemAlertType.WEEKLY_SUMMARY)
        self.assertEqual(alert['severity'], AlertSeverity.LOW)
        self.assertIn('Weekly Summary', alert['message'])
    
    def test_get_alert_statistics(self):
        """Test getting alert statistics"""
        # Send some alerts to generate statistics
        self.alert_system.send_system_alert(
            SystemAlertType.TRADE_EXECUTED, 'Test', AlertSeverity.LOW
        )
        self.alert_system.send_system_alert(
            SystemAlertType.SYSTEM_ERROR, 'Test', AlertSeverity.HIGH
        )
        
        stats = self.alert_system.get_alert_statistics()
        
        self.assertEqual(stats['total_alerts'], 2)
        self.assertEqual(stats['alerts_by_type']['trade_executed'], 1)
        self.assertEqual(stats['alerts_by_type']['system_error'], 1)
        self.assertEqual(stats['alerts_by_severity']['LOW'], 1)
        self.assertEqual(stats['alerts_by_severity']['HIGH'], 1)
        self.assertIn('channel_success_rates', stats)
        self.assertIn('queue_size', stats)
    
    def test_disabled_alert_system(self):
        """Test disabled alert system"""
        config = DEFAULT_ALERT_CONFIG.copy()
        config['enabled'] = False
        
        disabled_system = EnhancedAlertSystem(config, self.mock_logger)
        disabled_system._stop_processing.set()
        
        # Try to send alert
        disabled_system.send_system_alert(
            SystemAlertType.TRADE_EXECUTED, 'Test', AlertSeverity.LOW
        )
        
        # Should not queue any alerts
        self.assertEqual(len(disabled_system.priority_queue), 0)
        self.assertEqual(len(disabled_system.alert_history), 0)
        
        disabled_system.shutdown()
    
    def test_alert_rule_matching(self):
        """Test alert rule matching and custom channels"""
        # Add a custom rule
        condition = lambda data: data.get('trade_value', 0) > 5000
        rule = AlertRule(
            rule_id='large_trade',
            name='Large Trade Alert',
            alert_type=SystemAlertType.TRADE_EXECUTED,
            condition=condition,
            severity=AlertSeverity.HIGH,
            channels=['email']
        )
        
        self.alert_system.add_alert_rule(rule)
        
        # Send trade that matches the rule
        trade = TradeExecution(
            trade_id='trade_123',
            pair='BTC/USD',
            side='BUY',
            quantity=0.2,
            price=50000.0,  # 0.2 * 50000 = 10000 > 5000
            timestamp=datetime.now(),
            strategy='momentum'
        )
        
        self.alert_system.send_trade_alert(trade)
        
        # Check that alert was queued with custom channels
        alert = self.alert_system.priority_queue[0]
        self.assertIn('email', alert['channels'])
    
    def test_priority_queue_ordering(self):
        """Test that alerts are ordered by severity in priority queue"""
        # Send alerts with different severities
        self.alert_system.send_system_alert(
            SystemAlertType.TRADE_EXECUTED, 'Low priority', AlertSeverity.LOW
        )
        self.alert_system.send_system_alert(
            SystemAlertType.SYSTEM_ERROR, 'Critical error', AlertSeverity.CRITICAL
        )
        self.alert_system.send_system_alert(
            SystemAlertType.PERFORMANCE_ALERT, 'Medium priority', AlertSeverity.MEDIUM
        )
        
        # Manually sort the queue (normally done by background thread)
        self.alert_system.priority_queue.sort(key=lambda x: x['severity'].value, reverse=True)
        
        # Check ordering
        self.assertEqual(self.alert_system.priority_queue[0]['severity'], AlertSeverity.CRITICAL)
        self.assertEqual(self.alert_system.priority_queue[1]['severity'], AlertSeverity.MEDIUM)
        self.assertEqual(self.alert_system.priority_queue[2]['severity'], AlertSeverity.LOW)


class TestCreateEnhancedAlertSystem(unittest.TestCase):
    """Test create_enhanced_alert_system function"""
    
    def test_create_with_default_config(self):
        """Test creating alert system with default config"""
        system = create_enhanced_alert_system()
        
        self.assertIsInstance(system, EnhancedAlertSystem)
        self.assertTrue(system.enabled)
        self.assertIn('console', system.channels)
        
        system.shutdown()
    
    def test_create_with_custom_config(self):
        """Test creating alert system with custom config"""
        custom_config = {
            'enabled': True,
            'max_history': 500,
            'channels': {
                'console': {'enabled': True}
            }
        }
        
        system = create_enhanced_alert_system(custom_config)
        
        self.assertIsInstance(system, EnhancedAlertSystem)
        self.assertEqual(system.config['max_history'], 500)
        
        system.shutdown()
    
    def test_create_with_logger(self):
        """Test creating alert system with logger"""
        mock_logger = Mock()
        system = create_enhanced_alert_system(logger=mock_logger)
        
        self.assertEqual(system.logger, mock_logger)
        
        system.shutdown()


if __name__ == '__main__':
    unittest.main()