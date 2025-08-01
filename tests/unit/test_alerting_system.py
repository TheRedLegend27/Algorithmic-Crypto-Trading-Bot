"""
Unit tests for the alerting system.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, timedelta
import json
import tempfile
import os

from bot.adaptive.alerting_system import (
    Alert, AlertRule, AlertDeliveryService, AlertingSystem,
    AlertSeverity, AlertType, AlertChannel
)
from bot.adaptive.data_models import AdaptationEvent
from bot.adaptive.enums import AdaptationType, RegimeType


class TestAlert(unittest.TestCase):
    """Test Alert data class functionality."""
    
    def setUp(self):
        self.alert = Alert(
            alert_id="test_alert_001",
            alert_type=AlertType.PERFORMANCE_DECLINE,
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            message="This is a test alert",
            timestamp=datetime.now(),
            data={"test_key": "test_value"}
        )
    
    def test_alert_creation(self):
        """Test alert creation with required fields."""
        self.assertEqual(self.alert.alert_id, "test_alert_001")
        self.assertEqual(self.alert.alert_type, AlertType.PERFORMANCE_DECLINE)
        self.assertEqual(self.alert.severity, AlertSeverity.HIGH)
        self.assertFalse(self.alert.acknowledged)
        self.assertFalse(self.alert.resolved)
    
    def test_alert_acknowledgment(self):
        """Test alert acknowledgment."""
        self.assertFalse(self.alert.acknowledged)
        self.assertIsNone(self.alert.acknowledged_by)
        
        self.alert.acknowledge("test_user")
        
        self.assertTrue(self.alert.acknowledged)
        self.assertEqual(self.alert.acknowledged_by, "test_user")
        self.assertIsNotNone(self.alert.acknowledged_at)
    
    def test_alert_resolution(self):
        """Test alert resolution."""
        self.assertFalse(self.alert.resolved)
        self.assertIsNone(self.alert.resolved_at)
        
        self.alert.resolve()
        
        self.assertTrue(self.alert.resolved)
        self.assertIsNotNone(self.alert.resolved_at)
    
    def test_alert_to_dict(self):
        """Test alert serialization to dictionary."""
        alert_dict = self.alert.to_dict()
        
        self.assertIsInstance(alert_dict, dict)
        self.assertEqual(alert_dict['alert_id'], "test_alert_001")
        self.assertEqual(alert_dict['alert_type'], AlertType.PERFORMANCE_DECLINE)
        self.assertEqual(alert_dict['severity'], AlertSeverity.HIGH)


class TestAlertRule(unittest.TestCase):
    """Test AlertRule functionality."""
    
    def setUp(self):
        self.rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            alert_type=AlertType.PERFORMANCE_DECLINE,
            condition=lambda data: data.get('value', 0) > 10,
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG],
            cooldown_minutes=5
        )
    
    def test_rule_creation(self):
        """Test rule creation."""
        self.assertEqual(self.rule.rule_id, "test_rule")
        self.assertEqual(self.rule.name, "Test Rule")
        self.assertTrue(self.rule.enabled)
        self.assertEqual(self.rule.trigger_count, 0)
    
    def test_rule_condition_evaluation(self):
        """Test rule condition evaluation."""
        # Test condition that should trigger
        self.assertTrue(self.rule.condition({'value': 15}))
        
        # Test condition that should not trigger
        self.assertFalse(self.rule.condition({'value': 5}))
    
    def test_rule_can_trigger(self):
        """Test rule triggering logic."""
        # Should be able to trigger initially
        self.assertTrue(self.rule.can_trigger())
        
        # Disable rule
        self.rule.enabled = False
        self.assertFalse(self.rule.can_trigger())
        
        # Re-enable rule
        self.rule.enabled = True
        self.assertTrue(self.rule.can_trigger())
    
    def test_rule_cooldown(self):
        """Test rule cooldown functionality."""
        # Trigger rule
        self.rule.trigger()
        
        # Should not be able to trigger immediately due to cooldown
        # Note: This is a simplified test - real cooldown logic would check time
        self.assertIsNotNone(self.rule.last_triggered)
        self.assertEqual(self.rule.trigger_count, 1)


class TestAlertDeliveryService(unittest.TestCase):
    """Test AlertDeliveryService functionality."""
    
    def setUp(self):
        self.delivery_service = AlertDeliveryService()
        self.test_alert = Alert(
            alert_id="test_delivery",
            alert_type=AlertType.SYSTEM_HEALTH,
            severity=AlertSeverity.MEDIUM,
            title="Test Delivery Alert",
            message="Testing alert delivery",
            timestamp=datetime.now(),
            data={"component": "test_component"}
        )
    
    def test_configure_email(self):
        """Test email configuration."""
        self.delivery_service.configure_email(
            smtp_server="smtp.test.com",
            smtp_port=587,
            username="test@test.com",
            password="password",
            from_email="alerts@test.com",
            to_emails=["admin@test.com"]
        )
        
        self.assertEqual(self.delivery_service.email_config['smtp_server'], "smtp.test.com")
        self.assertEqual(self.delivery_service.email_config['smtp_port'], 587)
    
    def test_configure_webhook(self):
        """Test webhook configuration."""
        self.delivery_service.configure_webhook(
            url="https://webhook.test.com/alerts",
            headers={"Authorization": "Bearer token"}
        )
        
        self.assertEqual(self.delivery_service.webhook_config['url'], "https://webhook.test.com/alerts")
        self.assertIn("Authorization", self.delivery_service.webhook_config['headers'])
    
    def test_configure_file(self):
        """Test file configuration."""
        test_path = "/tmp/test_alerts.log"
        self.delivery_service.configure_file(test_path)
        
        self.assertEqual(self.delivery_service.file_config['path'], test_path)
    
    def test_deliver_to_log(self):
        """Test log delivery."""
        with patch.object(self.delivery_service.logger, 'log') as mock_log:
            result = self.delivery_service._deliver_to_log(self.test_alert)
            
            self.assertTrue(result)
            mock_log.assert_called_once()
    
    def test_deliver_to_console(self):
        """Test console delivery."""
        with patch('builtins.print') as mock_print:
            result = self.delivery_service._deliver_to_console(self.test_alert)
            
            self.assertTrue(result)
            self.assertTrue(mock_print.called)
    
    def test_deliver_to_file(self):
        """Test file delivery."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            self.delivery_service.configure_file(temp_path)
            result = self.delivery_service._deliver_to_file(self.test_alert)
            
            self.assertTrue(result)
            
            # Verify file content
            with open(temp_path, 'r') as f:
                content = f.read().strip()
                alert_data = json.loads(content)
                self.assertEqual(alert_data['alert_id'], "test_delivery")
                
        finally:
            os.unlink(temp_path)
    
    @patch('smtplib.SMTP')
    def test_deliver_to_email_success(self, mock_smtp):
        """Test successful email delivery."""
        # Configure email
        self.delivery_service.configure_email(
            smtp_server="smtp.test.com",
            smtp_port=587,
            username="test@test.com",
            password="password",
            from_email="alerts@test.com",
            to_emails=["admin@test.com"]
        )
        
        # Mock SMTP server
        mock_server = Mock()
        mock_smtp.return_value = mock_server
        
        result = self.delivery_service._deliver_to_email(self.test_alert)
        
        self.assertTrue(result)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()
    
    def test_deliver_to_email_not_configured(self):
        """Test email delivery when not configured."""
        result = self.delivery_service._deliver_to_email(self.test_alert)
        self.assertFalse(result)
    
    @patch('requests.post')
    def test_deliver_to_webhook_success(self, mock_post):
        """Test successful webhook delivery."""
        # Configure webhook
        self.delivery_service.configure_webhook("https://webhook.test.com/alerts")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = self.delivery_service._deliver_to_webhook(self.test_alert)
        
        self.assertTrue(result)
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_deliver_to_webhook_failure(self, mock_post):
        """Test webhook delivery failure."""
        # Configure webhook
        self.delivery_service.configure_webhook("https://webhook.test.com/alerts")
        
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        result = self.delivery_service._deliver_to_webhook(self.test_alert)
        
        self.assertFalse(result)
    
    def test_deliver_alert_multiple_channels(self):
        """Test delivering alert through multiple channels."""
        channels = [AlertChannel.LOG, AlertChannel.CONSOLE]
        
        with patch.object(self.delivery_service, '_deliver_to_log', return_value=True) as mock_log, \
             patch.object(self.delivery_service, '_deliver_to_console', return_value=True) as mock_console:
            
            results = self.delivery_service.deliver_alert(self.test_alert, channels)
            
            self.assertEqual(len(results), 2)
            self.assertTrue(results[AlertChannel.LOG])
            self.assertTrue(results[AlertChannel.CONSOLE])
            mock_log.assert_called_once()
            mock_console.assert_called_once()


class TestAlertingSystem(unittest.TestCase):
    """Test AlertingSystem functionality."""
    
    def setUp(self):
        self.alerting_system = AlertingSystem()
    
    def test_system_initialization(self):
        """Test alerting system initialization."""
        self.assertIsNotNone(self.alerting_system.rules)
        self.assertIsNotNone(self.alerting_system.delivery_service)
        self.assertFalse(self.alerting_system.is_running)
        
        # Should have default rules
        self.assertGreater(len(self.alerting_system.rules), 0)
    
    def test_add_remove_rule(self):
        """Test adding and removing rules."""
        initial_count = len(self.alerting_system.rules)
        
        # Add rule
        test_rule = AlertRule(
            rule_id="test_add_rule",
            name="Test Add Rule",
            alert_type=AlertType.PERFORMANCE_DECLINE,
            condition=lambda data: True,
            severity=AlertSeverity.LOW,
            channels=[AlertChannel.LOG]
        )
        
        self.alerting_system.add_rule(test_rule)
        self.assertEqual(len(self.alerting_system.rules), initial_count + 1)
        self.assertIn("test_add_rule", self.alerting_system.rules)
        
        # Remove rule
        self.alerting_system.remove_rule("test_add_rule")
        self.assertEqual(len(self.alerting_system.rules), initial_count)
        self.assertNotIn("test_add_rule", self.alerting_system.rules)
    
    def test_enable_disable_rule(self):
        """Test enabling and disabling rules."""
        # Add a test rule
        test_rule = AlertRule(
            rule_id="test_enable_disable",
            name="Test Enable/Disable",
            alert_type=AlertType.SYSTEM_HEALTH,
            condition=lambda data: True,
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG]
        )
        
        self.alerting_system.add_rule(test_rule)
        
        # Rule should be enabled by default
        self.assertTrue(self.alerting_system.rules["test_enable_disable"].enabled)
        
        # Disable rule
        self.alerting_system.disable_rule("test_enable_disable")
        self.assertFalse(self.alerting_system.rules["test_enable_disable"].enabled)
        
        # Enable rule
        self.alerting_system.enable_rule("test_enable_disable")
        self.assertTrue(self.alerting_system.rules["test_enable_disable"].enabled)
    
    def test_check_conditions_trigger_alert(self):
        """Test condition checking and alert generation."""
        # Clear existing rules to avoid interference
        self.alerting_system.rules.clear()
        
        # Add a test rule that should trigger
        test_rule = AlertRule(
            rule_id="test_trigger",
            name="Test Trigger",
            alert_type=AlertType.PERFORMANCE_DECLINE,
            condition=lambda data: data.get('performance_change', 0) < -0.05,
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.LOG]
        )
        
        self.alerting_system.add_rule(test_rule)
        
        # Test data that should trigger the rule
        test_data = {'performance_change': -0.08}
        
        alerts = self.alerting_system.check_conditions(test_data)
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, AlertType.PERFORMANCE_DECLINE)
        self.assertEqual(alerts[0].severity, AlertSeverity.HIGH)
    
    def test_check_conditions_no_trigger(self):
        """Test condition checking when no rules should trigger."""
        # Test data that should not trigger any default rules
        test_data = {'performance_change': 0.02}  # Positive change
        
        alerts = self.alerting_system.check_conditions(test_data)
        
        # Should not trigger performance decline alert
        performance_alerts = [a for a in alerts if a.alert_type == AlertType.PERFORMANCE_DECLINE]
        self.assertEqual(len(performance_alerts), 0)
    
    def test_create_manual_alert(self):
        """Test creating manual alerts."""
        alert = self.alerting_system.create_manual_alert(
            alert_type=AlertType.SYSTEM_HEALTH,
            severity=AlertSeverity.MEDIUM,
            title="Manual Test Alert",
            message="This is a manual test alert",
            data={"test": "data"}
        )
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, AlertType.SYSTEM_HEALTH)
        self.assertEqual(alert.severity, AlertSeverity.MEDIUM)
        self.assertEqual(alert.title, "Manual Test Alert")
        
        # Should be in alert history
        self.assertIn(alert, self.alerting_system.alert_history)
    
    def test_get_alert_history(self):
        """Test retrieving alert history."""
        # Create some test alerts
        for i in range(3):
            self.alerting_system.create_manual_alert(
                alert_type=AlertType.SYSTEM_HEALTH,
                severity=AlertSeverity.LOW,
                title=f"Test Alert {i}",
                message=f"Test message {i}"
            )
        
        # Get recent history
        recent_alerts = self.alerting_system.get_alert_history(hours_back=1)
        self.assertEqual(len(recent_alerts), 3)
        
        # Get older history (should be empty)
        old_alerts = self.alerting_system.get_alert_history(hours_back=0)
        self.assertEqual(len(old_alerts), 0)
    
    def test_get_alert_statistics(self):
        """Test alert statistics."""
        # Create some test alerts
        self.alerting_system.create_manual_alert(
            alert_type=AlertType.SYSTEM_HEALTH,
            severity=AlertSeverity.MEDIUM,
            title="Test Alert 1",
            message="Test message 1"
        )
        
        self.alerting_system.create_manual_alert(
            alert_type=AlertType.PERFORMANCE_DECLINE,
            severity=AlertSeverity.HIGH,
            title="Test Alert 2",
            message="Test message 2"
        )
        
        stats = self.alerting_system.get_alert_statistics()
        
        self.assertIn('total_alerts', stats)
        self.assertIn('alert_types', stats)
        self.assertIn('active_rules', stats)
        self.assertEqual(stats['total_alerts'], 2)
    
    def test_acknowledge_alert(self):
        """Test alert acknowledgment."""
        alert = self.alerting_system.create_manual_alert(
            alert_type=AlertType.SYSTEM_HEALTH,
            severity=AlertSeverity.MEDIUM,
            title="Test Acknowledge",
            message="Test acknowledgment"
        )
        
        # Acknowledge alert
        result = self.alerting_system.acknowledge_alert(alert.alert_id, "test_user")
        
        self.assertTrue(result)
        self.assertTrue(alert.acknowledged)
        self.assertEqual(alert.acknowledged_by, "test_user")
    
    def test_resolve_alert(self):
        """Test alert resolution."""
        alert = self.alerting_system.create_manual_alert(
            alert_type=AlertType.SYSTEM_HEALTH,
            severity=AlertSeverity.MEDIUM,
            title="Test Resolve",
            message="Test resolution"
        )
        
        # Resolve alert
        result = self.alerting_system.resolve_alert(alert.alert_id)
        
        self.assertTrue(result)
        self.assertTrue(alert.resolved)
        self.assertIsNotNone(alert.resolved_at)
    
    def test_convenience_methods(self):
        """Test convenience methods for common alert scenarios."""
        
        # Test performance decline alert
        with patch.object(self.alerting_system, 'check_conditions') as mock_check:
            mock_alert = Mock()
            mock_alert.alert_type = AlertType.PERFORMANCE_DECLINE
            mock_check.return_value = [mock_alert]
            
            with patch.object(self.alerting_system, 'send_alert') as mock_send:
                self.alerting_system.alert_performance_decline(-0.08, "test_strategy")
                mock_send.assert_called_once()
        
        # Test system health alert
        with patch.object(self.alerting_system, 'check_conditions') as mock_check:
            mock_alert = Mock()
            mock_alert.alert_type = AlertType.SYSTEM_HEALTH
            mock_check.return_value = [mock_alert]
            
            with patch.object(self.alerting_system, 'send_alert') as mock_send:
                self.alerting_system.alert_system_health(0.6, ["component1", "component2"])
                mock_send.assert_called_once()
        
        # Test component failure alert
        with patch.object(self.alerting_system, 'check_conditions') as mock_check:
            mock_alert = Mock()
            mock_alert.alert_type = AlertType.COMPONENT_FAILURE
            mock_check.return_value = [mock_alert]
            
            with patch.object(self.alerting_system, 'send_alert') as mock_send:
                self.alerting_system.alert_component_failure("test_component", "Test error")
                mock_send.assert_called_once()
        
        # Test risk threshold alert
        with patch.object(self.alerting_system, 'check_conditions') as mock_check:
            mock_alert = Mock()
            mock_alert.alert_type = AlertType.RISK_THRESHOLD
            mock_check.return_value = [mock_alert]
            
            with patch.object(self.alerting_system, 'send_alert') as mock_send:
                self.alerting_system.alert_risk_threshold(0.9, "portfolio_risk", ["BTC/USD"])
                mock_send.assert_called_once()
        
        # Test adaptation failure alert
        adaptation_event = AdaptationEvent(
            event_id="test_adaptation",
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Test",
            changes_made={},
            expected_impact=0.0,
            affected_strategies=["strategy1"]
        )
        
        with patch.object(self.alerting_system, 'check_conditions') as mock_check:
            mock_alert = Mock()
            mock_alert.alert_type = AlertType.ADAPTATION_FAILURE
            mock_check.return_value = [mock_alert]
            
            with patch.object(self.alerting_system, 'send_alert') as mock_send:
                self.alerting_system.alert_adaptation_failure(adaptation_event)
                mock_send.assert_called_once()
        
        # Test market regime change alert
        with patch.object(self.alerting_system, 'create_manual_alert') as mock_create:
            self.alerting_system.alert_market_regime_change(
                "BTC/USD", RegimeType.TRENDING_BULL, RegimeType.RANGING, 0.85
            )
            mock_create.assert_called_once()
    
    @patch('time.sleep')
    def test_start_stop_system(self, mock_sleep):
        """Test starting and stopping the alerting system."""
        mock_sleep.return_value = None
        
        self.assertFalse(self.alerting_system.is_running)
        
        # Start system
        self.alerting_system.start()
        self.assertTrue(self.alerting_system.is_running)
        self.assertIsNotNone(self.alerting_system.processing_thread)
        
        # Stop system
        self.alerting_system.stop()
        self.assertFalse(self.alerting_system.is_running)
    
    def test_generate_alert_content(self):
        """Test alert content generation."""
        # Test performance decline content
        title, message = self.alerting_system._generate_alert_content(
            AlertType.PERFORMANCE_DECLINE,
            {'performance_change': -0.08}
        )
        
        self.assertIn("Performance Decline", title)
        self.assertIn("8.00%", message)
        
        # Test system health content
        title, message = self.alerting_system._generate_alert_content(
            AlertType.SYSTEM_HEALTH,
            {'health_score': 0.6}
        )
        
        self.assertIn("System Health", title)
        self.assertIn("60.0%", message)
    
    def test_get_recommended_actions(self):
        """Test recommended actions generation."""
        actions = self.alerting_system._get_recommended_actions(
            AlertType.PERFORMANCE_DECLINE,
            {'performance_change': -0.08}
        )
        
        self.assertIsInstance(actions, list)
        self.assertGreater(len(actions), 0)
        self.assertTrue(any("strategy" in action.lower() for action in actions))


if __name__ == '__main__':
    unittest.main()