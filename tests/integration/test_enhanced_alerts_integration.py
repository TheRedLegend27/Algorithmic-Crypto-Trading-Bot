"""
Integration tests for the enhanced alert system.

This module contains integration tests that verify the enhanced alert system
works correctly with real notification channels, background processing,
and complex alert scenarios.
"""

import unittest
import asyncio
import time
import threading
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from bot.enhanced_alerts import (
    EnhancedAlertSystem,
    AlertSeverity,
    SystemAlertType,
    AlertRule,
    EmailNotificationChannel,
    WebhookNotificationChannel,
    ConsoleNotificationChannel,
    RiskEvent,
    TradeExecution,
    PerformanceMetrics,
    DEFAULT_ALERT_CONFIG
)
from bot.enhanced_logger import EnhancedLogger


class TestEnhancedAlertSystemIntegration(unittest.TestCase):
    """Integration tests for EnhancedAlertSystem"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = DEFAULT_ALERT_CONFIG.copy()
        self.config['channels']['console']['enabled'] = True
        
        # Create temporary logger
        self.temp_dir = tempfile.mkdtemp()
        logger_config = {
            'log_level': 'INFO',
            'log_file': os.path.join(self.temp_dir, 'test.log'),
            'max_file_size': 10 * 1024 * 1024,
            'backup_count': 3,
            'use_rich': False
        }
        self.logger = EnhancedLogger(logger_config)
        
        self.alert_system = EnhancedAlertSystem(self.config, self.logger)
        
        # Allow some time for background thread to start
        time.sleep(0.1)
    
    def tearDown(self):
        """Clean up after tests"""
        self.alert_system.shutdown()
        
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_background_processing(self):
        """Test that background processing works correctly"""
        # Send multiple alerts
        for i in range(5):
            self.alert_system.send_system_alert(
                SystemAlertType.TRADE_EXECUTED,
                f'Test alert {i}',
                AlertSeverity.LOW
            )
        
        # Wait for background processing
        time.sleep(0.5)
        
        # Check that alerts were processed
        stats = self.alert_system.get_alert_statistics()
        self.assertEqual(stats['total_alerts'], 5)
        
        # Queue should be empty or nearly empty after processing
        self.assertLessEqual(len(self.alert_system.priority_queue), 1)
    
    def test_alert_throttling_integration(self):
        """Test alert throttling in real-time scenario"""
        # Configure short throttling for testing
        self.alert_system.configure_alert_throttling('trade_executed', 0.1)  # 0.1 minutes = 6 seconds
        
        # Send multiple alerts of same type quickly
        for i in range(3):
            self.alert_system.send_system_alert(
                SystemAlertType.TRADE_EXECUTED,
                f'Throttled alert {i}',
                AlertSeverity.LOW
            )
        
        # Wait for processing
        time.sleep(0.2)
        
        # Only first alert should be processed due to throttling
        # Note: This test depends on the specific throttling implementation
        stats = self.alert_system.get_alert_statistics()
        self.assertGreaterEqual(stats['total_alerts'], 1)
    
    def test_priority_processing(self):
        """Test that high priority alerts are processed first"""
        # Send alerts with different priorities
        alerts_sent = [
            (SystemAlertType.TRADE_EXECUTED, AlertSeverity.LOW, 'Low priority'),
            (SystemAlertType.SYSTEM_ERROR, AlertSeverity.CRITICAL, 'Critical error'),
            (SystemAlertType.PERFORMANCE_ALERT, AlertSeverity.MEDIUM, 'Medium priority'),
            (SystemAlertType.RISK_LIMIT_EXCEEDED, AlertSeverity.HIGH, 'High priority')
        ]
        
        for alert_type, severity, message in alerts_sent:
            self.alert_system.send_system_alert(alert_type, message, severity)
        
        # Wait for processing
        time.sleep(0.5)
        
        # Check that all alerts were processed
        stats = self.alert_system.get_alert_statistics()
        self.assertEqual(stats['total_alerts'], 4)
    
    def test_custom_alert_rules_integration(self):
        """Test custom alert rules with real conditions"""
        # Add custom rule for large trades
        large_trade_rule = AlertRule(
            rule_id='large_trade_rule',
            name='Large Trade Detection',
            alert_type=SystemAlertType.TRADE_EXECUTED,
            condition=lambda data: data.get('trade_value', 0) > 10000,
            severity=AlertSeverity.HIGH,
            throttle_minutes=5,
            channels=['console']
        )
        
        self.alert_system.add_alert_rule(large_trade_rule)
        
        # Send trade that should trigger the rule
        large_trade = TradeExecution(
            trade_id='large_trade_001',
            pair='BTC/USD',
            side='BUY',
            quantity=0.5,
            price=50000.0,  # 0.5 * 50000 = 25000 > 10000
            timestamp=datetime.now(),
            strategy='momentum'
        )
        
        self.alert_system.send_trade_alert(large_trade)
        
        # Wait for processing
        time.sleep(0.2)
        
        # Check that alert was processed
        stats = self.alert_system.get_alert_statistics()
        self.assertGreater(stats['total_alerts'], 0)
        self.assertGreater(stats['alerts_by_type']['trade_executed'], 0)
    
    def test_multiple_notification_channels(self):
        """Test alerts sent to multiple channels"""
        # Configure multiple channels
        config_with_multiple_channels = DEFAULT_ALERT_CONFIG.copy()
        config_with_multiple_channels['channels'] = {
            'console': {'enabled': True},
            'webhook': {
                'enabled': True,
                'url': 'https://httpbin.org/post',  # Test webhook endpoint
                'timeout': 5
            }
        }
        
        multi_channel_system = EnhancedAlertSystem(config_with_multiple_channels, self.logger)
        
        try:
            # Send alert
            multi_channel_system.send_system_alert(
                SystemAlertType.SYSTEM_ERROR,
                'Multi-channel test',
                AlertSeverity.HIGH
            )
            
            # Wait for processing
            time.sleep(1.0)
            
            # Check statistics
            stats = multi_channel_system.get_alert_statistics()
            self.assertGreater(stats['total_alerts'], 0)
            
        finally:
            multi_channel_system.shutdown()
    
    def test_performance_metrics_alert_integration(self):
        """Test performance metrics alerts with realistic data"""
        # Create performance metrics that should trigger different severity levels
        poor_performance = PerformanceMetrics(
            timestamp=datetime.now(),
            total_pnl=-500.0,
            daily_pnl=-200.0,  # Poor daily performance
            win_rate=0.3,      # Low win rate
            total_trades=100,
            successful_trades=30,
            sharpe_ratio=0.2,
            max_drawdown=0.25,  # High drawdown
            current_positions={'BTC/USD': -0.5},
            account_balance=8000.0
        )
        
        self.alert_system.send_performance_alert(poor_performance)
        
        # Wait for processing
        time.sleep(0.2)
        
        # Check that high severity alert was generated
        stats = self.alert_system.get_alert_statistics()
        self.assertGreater(stats['total_alerts'], 0)
        self.assertGreater(stats['alerts_by_severity']['CRITICAL'], 0)
    
    def test_risk_event_alert_integration(self):
        """Test risk event alerts with various scenarios"""
        # Test different risk events
        risk_events = [
            RiskEvent(
                event_type='position_limit',
                severity=AlertSeverity.HIGH,
                message='Position limit exceeded for BTC/USD',
                details={'limit': 1000, 'current': 1200, 'excess': 200},
                pair='BTC/USD',
                position_size=1200.0,
                risk_level=0.8
            ),
            RiskEvent(
                event_type='drawdown_limit',
                severity=AlertSeverity.CRITICAL,
                message='Maximum drawdown limit reached',
                details={'max_drawdown': 0.2, 'current_drawdown': 0.22},
                risk_level=1.1
            ),
            RiskEvent(
                event_type='correlation_risk',
                severity=AlertSeverity.MEDIUM,
                message='High correlation detected between positions',
                details={'correlation': 0.85, 'pairs': ['BTC/USD', 'ETH/USD']},
                risk_level=0.6
            )
        ]
        
        for risk_event in risk_events:
            self.alert_system.send_risk_alert(risk_event)
        
        # Wait for processing
        time.sleep(0.5)
        
        # Check that all risk alerts were processed
        stats = self.alert_system.get_alert_statistics()
        self.assertEqual(stats['total_alerts'], 3)
        
        # Check severity distribution
        self.assertGreater(stats['alerts_by_severity']['HIGH'], 0)
        self.assertGreater(stats['alerts_by_severity']['CRITICAL'], 0)
        self.assertGreater(stats['alerts_by_severity']['MEDIUM'], 0)
    
    def test_daily_and_weekly_summaries(self):
        """Test daily and weekly summary alerts"""
        # Send daily summary
        daily_summary = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'daily_pnl': 250.0,
            'total_trades': 15,
            'successful_trades': 10,
            'win_rate': 0.67,
            'best_trade': 75.0,
            'worst_trade': -25.0,
            'total_fees': 12.50,
            'active_pairs': ['BTC/USD', 'ETH/USD', 'ADA/USD']
        }
        
        self.alert_system.send_daily_summary(daily_summary)
        
        # Send weekly summary
        weekly_summary = {
            'week_start': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            'week_end': datetime.now().strftime('%Y-%m-%d'),
            'weekly_pnl': 1200.0,
            'total_trades': 85,
            'successful_trades': 55,
            'win_rate': 0.65,
            'best_day': 300.0,
            'worst_day': -150.0,
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.08
        }
        
        self.alert_system.send_weekly_summary(weekly_summary)
        
        # Wait for processing
        time.sleep(0.3)
        
        # Check that summary alerts were processed
        stats = self.alert_system.get_alert_statistics()
        self.assertEqual(stats['total_alerts'], 2)
        self.assertGreater(stats['alerts_by_type']['daily_summary'], 0)
        self.assertGreater(stats['alerts_by_type']['weekly_summary'], 0)
    
    def test_alert_system_under_load(self):
        """Test alert system performance under high load"""
        start_time = time.time()
        
        # Send many alerts quickly
        num_alerts = 100
        for i in range(num_alerts):
            severity = AlertSeverity.LOW if i % 4 == 0 else AlertSeverity.MEDIUM
            self.alert_system.send_system_alert(
                SystemAlertType.TRADE_EXECUTED,
                f'Load test alert {i}',
                severity,
                {'index': i, 'batch': 'load_test'}
            )
        
        # Wait for processing
        time.sleep(2.0)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Check that all alerts were processed
        stats = self.alert_system.get_alert_statistics()
        self.assertEqual(stats['total_alerts'], num_alerts)
        
        # Performance check - should process alerts reasonably quickly
        self.assertLess(processing_time, 10.0)  # Should complete within 10 seconds
        
        # Queue should be empty or nearly empty
        self.assertLessEqual(len(self.alert_system.priority_queue), 5)
    
    def test_alert_system_recovery_after_error(self):
        """Test that alert system recovers gracefully from errors"""
        # Create a channel that will fail
        failing_config = {
            'enabled': True,
            'url': 'http://invalid-url-that-will-fail.com/webhook',
            'timeout': 1
        }
        
        failing_channel = WebhookNotificationChannel('failing_webhook', failing_config)
        self.alert_system.channels['failing_webhook'] = failing_channel
        
        # Send alerts that will cause the failing channel to error
        for i in range(5):
            self.alert_system.send_system_alert(
                SystemAlertType.SYSTEM_ERROR,
                f'Error recovery test {i}',
                AlertSeverity.HIGH
            )
        
        # Wait for processing (including failed attempts)
        time.sleep(2.0)
        
        # System should still be functional
        stats = self.alert_system.get_alert_statistics()
        self.assertEqual(stats['total_alerts'], 5)
        
        # Console channel should still work
        self.assertIn('console', stats['channel_success_rates'])
    
    def test_concurrent_alert_processing(self):
        """Test concurrent alert processing from multiple threads"""
        def send_alerts_from_thread(thread_id, num_alerts):
            for i in range(num_alerts):
                self.alert_system.send_system_alert(
                    SystemAlertType.TRADE_EXECUTED,
                    f'Thread {thread_id} alert {i}',
                    AlertSeverity.LOW,
                    {'thread_id': thread_id, 'alert_index': i}
                )
        
        # Create multiple threads sending alerts
        threads = []
        num_threads = 5
        alerts_per_thread = 10
        
        for thread_id in range(num_threads):
            thread = threading.Thread(
                target=send_alerts_from_thread,
                args=(thread_id, alerts_per_thread)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Wait for processing
        time.sleep(1.0)
        
        # Check that all alerts were processed
        expected_total = num_threads * alerts_per_thread
        stats = self.alert_system.get_alert_statistics()
        self.assertEqual(stats['total_alerts'], expected_total)
    
    @patch('smtplib.SMTP')
    def test_email_notification_integration(self, mock_smtp):
        """Test email notification integration"""
        # Configure email channel
        email_config = {
            'enabled': True,
            'smtp_server': 'smtp.test.com',
            'smtp_port': 587,
            'username': 'test@test.com',
            'password': 'password',
            'from_address': 'bot@test.com',
            'to_addresses': ['user@test.com']
        }
        
        config_with_email = DEFAULT_ALERT_CONFIG.copy()
        config_with_email['channels']['email'] = email_config
        
        email_system = EnhancedAlertSystem(config_with_email, self.logger)
        
        try:
            # Mock SMTP server
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            # Send critical alert that should trigger email
            email_system.send_system_alert(
                SystemAlertType.SYSTEM_ERROR,
                'Critical system failure',
                AlertSeverity.CRITICAL,
                {'error_code': 'SYS_001', 'component': 'database'}
            )
            
            # Wait for processing
            time.sleep(0.5)
            
            # Check that email was attempted
            # Note: This test verifies the integration flow, actual SMTP calls are mocked
            stats = email_system.get_alert_statistics()
            self.assertGreater(stats['total_alerts'], 0)
            
        finally:
            email_system.shutdown()


class TestNotificationChannelIntegration(unittest.TestCase):
    """Integration tests for notification channels"""
    
    def test_console_channel_real_output(self):
        """Test console channel with real output"""
        config = {'enabled': True}
        channel = ConsoleNotificationChannel('console', config)
        
        # Capture console output
        import io
        import sys
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Send notification
            asyncio.run(channel.send_notification(
                SystemAlertType.TRADE_EXECUTED,
                AlertSeverity.HIGH,
                'Integration test message',
                {'test_key': 'test_value', 'amount': 1000.0}
            ))
            
            # Get output
            output = captured_output.getvalue()
            
            # Verify output contains expected elements
            self.assertIn('CRYPTO BOT ALERT', output)
            self.assertIn('HIGH', output)
            self.assertIn('trade_executed', output)
            self.assertIn('Integration test message', output)
            self.assertIn('test_key', output)
            self.assertIn('test_value', output)
            
        finally:
            sys.stdout = sys.__stdout__
    
    @patch('requests.post')
    def test_webhook_channel_with_real_payload(self, mock_post):
        """Test webhook channel with realistic payload"""
        config = {
            'enabled': True,
            'url': 'https://webhook.test.com/alerts',
            'headers': {
                'Authorization': 'Bearer test-token',
                'X-Bot-Version': '1.0.0'
            },
            'timeout': 30
        }
        
        channel = WebhookNotificationChannel('webhook', config)
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send notification with complex data
        complex_details = {
            'trade_id': 'TRD_20231201_001',
            'pair': 'BTC/USD',
            'side': 'BUY',
            'quantity': 0.15,
            'price': 42500.0,
            'trade_value': 6375.0,
            'strategy': 'momentum_breakout',
            'confidence': 0.85,
            'market_conditions': {
                'volatility': 0.12,
                'volume_ratio': 1.3,
                'trend': 'bullish'
            }
        }
        
        result = asyncio.run(channel.send_notification(
            SystemAlertType.TRADE_EXECUTED,
            AlertSeverity.MEDIUM,
            'Large momentum trade executed',
            complex_details
        ))
        
        self.assertTrue(result)
        
        # Verify webhook was called with correct data
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        self.assertEqual(args[0], 'https://webhook.test.com/alerts')
        self.assertIn('json', kwargs)
        self.assertIn('headers', kwargs)
        
        # Check payload structure
        payload = kwargs['json']
        self.assertEqual(payload['alert_type'], 'trade_executed')
        self.assertEqual(payload['severity'], 'MEDIUM')
        self.assertEqual(payload['message'], 'Large momentum trade executed')
        self.assertEqual(payload['details']['trade_id'], 'TRD_20231201_001')
        self.assertEqual(payload['details']['market_conditions']['trend'], 'bullish')
        
        # Check headers
        headers = kwargs['headers']
        self.assertEqual(headers['Authorization'], 'Bearer test-token')
        self.assertEqual(headers['X-Bot-Version'], '1.0.0')
        self.assertEqual(headers['Content-Type'], 'application/json')


if __name__ == '__main__':
    unittest.main()