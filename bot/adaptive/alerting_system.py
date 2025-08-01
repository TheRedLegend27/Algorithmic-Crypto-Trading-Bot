"""
Comprehensive alerting system for the adaptive trading bot.
Provides performance-based, system health, risk-based, and adaptation failure alerts.
"""
import logging
import smtplib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import time
from collections import defaultdict, deque

# Email imports with fallback
try:
    from email.mime.text import MIMEText as MimeText
    from email.mime.multipart import MIMEMultipart as MimeMultipart
except ImportError:
    # Fallback for different Python versions
    try:
        from email.MIMEText import MIMEText as MimeText
        from email.MIMEMultipart import MIMEMultipart as MimeMultipart
    except ImportError:
        # If email libraries are not available, create dummy classes
        class MimeText:
            def __init__(self, *args, **kwargs):
                pass
        
        class MimeMultipart:
            def __init__(self, *args, **kwargs):
                pass
            
            def attach(self, *args, **kwargs):
                pass

from .data_models import PerformanceMetrics, AdaptationEvent, MarketRegime
from .enums import RegimeType, AdaptationType


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts that can be generated."""
    PERFORMANCE_DECLINE = "performance_decline"
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    SYSTEM_HEALTH = "system_health"
    COMPONENT_FAILURE = "component_failure"
    RISK_THRESHOLD = "risk_threshold"
    ADAPTATION_FAILURE = "adaptation_failure"
    ADAPTATION_SUCCESS = "adaptation_success"
    MARKET_REGIME_CHANGE = "market_regime_change"
    EMERGENCY_STOP = "emergency_stop"
    DATA_QUALITY = "data_quality"
    MODEL_DRIFT = "model_drift"


class AlertChannel(Enum):
    """Alert delivery channels."""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    FILE = "file"


@dataclass
class Alert:
    """Represents an alert with all necessary information."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    data: Dict[str, Any]
    
    # Optional fields
    source_component: Optional[str] = None
    affected_strategies: Optional[List[str]] = None
    affected_pairs: Optional[List[str]] = None
    recommended_actions: Optional[List[str]] = None
    
    # Alert management
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return asdict(self)
    
    def acknowledge(self, user: str = "system") -> None:
        """Acknowledge the alert."""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = datetime.now()
    
    def resolve(self) -> None:
        """Mark the alert as resolved."""
        self.resolved = True
        self.resolved_at = datetime.now()


@dataclass
class AlertRule:
    """Defines conditions and actions for alert generation."""
    rule_id: str
    name: str
    alert_type: AlertType
    condition: Callable[[Dict[str, Any]], bool]
    severity: AlertSeverity
    channels: List[AlertChannel]
    
    # Throttling
    cooldown_minutes: int = 5
    max_alerts_per_hour: int = 10
    
    # Rule state
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    
    def can_trigger(self) -> bool:
        """Check if rule can be triggered based on cooldown and rate limits."""
        if not self.enabled:
            return False
        
        now = datetime.now()
        
        # Check cooldown
        if self.last_triggered:
            time_since_last = (now - self.last_triggered).total_seconds() / 60
            if time_since_last < self.cooldown_minutes:
                return False
        
        # Check rate limit (simplified - count triggers in last hour)
        # In a real implementation, you'd want more sophisticated rate limiting
        return True
    
    def trigger(self) -> None:
        """Record that the rule was triggered."""
        self.last_triggered = datetime.now()
        self.trigger_count += 1


class AlertDeliveryService:
    """Handles delivery of alerts through various channels."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.email_config = {}
        self.webhook_config = {}
        self.file_config = {'path': 'logs/alerts.log'}
        
    def configure_email(self, smtp_server: str, smtp_port: int, 
                       username: str, password: str, 
                       from_email: str, to_emails: List[str]) -> None:
        """Configure email delivery."""
        self.email_config = {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'username': username,
            'password': password,
            'from_email': from_email,
            'to_emails': to_emails
        }
    
    def configure_webhook(self, url: str, headers: Optional[Dict[str, str]] = None) -> None:
        """Configure webhook delivery."""
        self.webhook_config = {
            'url': url,
            'headers': headers or {}
        }
    
    def configure_file(self, file_path: str) -> None:
        """Configure file-based alert logging."""
        self.file_config['path'] = file_path
    
    def deliver_alert(self, alert: Alert, channels: List[AlertChannel]) -> Dict[AlertChannel, bool]:
        """Deliver alert through specified channels."""
        delivery_results = {}
        
        for channel in channels:
            try:
                if channel == AlertChannel.LOG:
                    delivery_results[channel] = self._deliver_to_log(alert)
                elif channel == AlertChannel.EMAIL:
                    delivery_results[channel] = self._deliver_to_email(alert)
                elif channel == AlertChannel.WEBHOOK:
                    delivery_results[channel] = self._deliver_to_webhook(alert)
                elif channel == AlertChannel.CONSOLE:
                    delivery_results[channel] = self._deliver_to_console(alert)
                elif channel == AlertChannel.FILE:
                    delivery_results[channel] = self._deliver_to_file(alert)
                else:
                    delivery_results[channel] = False
                    
            except Exception as e:
                self.logger.error(f"Failed to deliver alert {alert.alert_id} via {channel}: {str(e)}")
                delivery_results[channel] = False
        
        return delivery_results
    
    def _deliver_to_log(self, alert: Alert) -> bool:
        """Deliver alert to application log."""
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.INFO)
        
        self.logger.log(log_level, f"ALERT [{alert.severity.value.upper()}] {alert.title}: {alert.message}")
        return True
    
    def _deliver_to_email(self, alert: Alert) -> bool:
        """Deliver alert via email."""
        if not self.email_config:
            self.logger.warning("Email not configured for alert delivery")
            return False
        
        try:
            msg = MimeMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = ', '.join(self.email_config['to_emails'])
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            
            body = self._format_alert_email(alert)
            msg.attach(MimeText(body, 'html'))
            
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {str(e)}")
            return False
    
    def _deliver_to_webhook(self, alert: Alert) -> bool:
        """Deliver alert via webhook."""
        if not self.webhook_config:
            self.logger.warning("Webhook not configured for alert delivery")
            return False
        
        try:
            import requests
            
            payload = {
                'alert_id': alert.alert_id,
                'type': alert.alert_type.value,
                'severity': alert.severity.value,
                'title': alert.title,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'data': alert.data
            }
            
            response = requests.post(
                self.webhook_config['url'],
                json=payload,
                headers=self.webhook_config['headers'],
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {str(e)}")
            return False
    
    def _deliver_to_console(self, alert: Alert) -> bool:
        """Deliver alert to console."""
        severity_colors = {
            AlertSeverity.LOW: '\033[92m',      # Green
            AlertSeverity.MEDIUM: '\033[93m',   # Yellow
            AlertSeverity.HIGH: '\033[91m',     # Red
            AlertSeverity.CRITICAL: '\033[95m'  # Magenta
        }
        
        color = severity_colors.get(alert.severity, '')
        reset_color = '\033[0m'
        
        print(f"{color}[{alert.severity.value.upper()}] {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"ALERT: {alert.title}")
        print(f"MESSAGE: {alert.message}")
        if alert.recommended_actions:
            print("RECOMMENDED ACTIONS:")
            for action in alert.recommended_actions:
                print(f"  - {action}")
        print(f"{reset_color}")
        
        return True
    
    def _deliver_to_file(self, alert: Alert) -> bool:
        """Deliver alert to file."""
        try:
            alert_data = {
                'timestamp': alert.timestamp.isoformat(),
                'alert_id': alert.alert_id,
                'type': alert.alert_type.value,
                'severity': alert.severity.value,
                'title': alert.title,
                'message': alert.message,
                'data': alert.data
            }
            
            with open(self.file_config['path'], 'a') as f:
                f.write(json.dumps(alert_data) + '\n')
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write alert to file: {str(e)}")
            return False
    
    def _format_alert_email(self, alert: Alert) -> str:
        """Format alert for email delivery."""
        severity_colors = {
            AlertSeverity.LOW: '#28a745',
            AlertSeverity.MEDIUM: '#ffc107',
            AlertSeverity.HIGH: '#dc3545',
            AlertSeverity.CRITICAL: '#6f42c1'
        }
        
        color = severity_colors.get(alert.severity, '#6c757d')
        
        html = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <div style="background-color: {color}; color: white; padding: 15px; border-radius: 5px 5px 0 0;">
                    <h2 style="margin: 0;">[{alert.severity.value.upper()}] {alert.title}</h2>
                </div>
                <div style="border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px;">
                    <p><strong>Alert ID:</strong> {alert.alert_id}</p>
                    <p><strong>Type:</strong> {alert.alert_type.value}</p>
                    <p><strong>Timestamp:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <p><strong>Message:</strong></p>
                    <p style="background-color: #f8f9fa; padding: 10px; border-left: 4px solid {color};">
                        {alert.message}
                    </p>
        """
        
        if alert.affected_strategies:
            html += f"<p><strong>Affected Strategies:</strong> {', '.join(alert.affected_strategies)}</p>"
        
        if alert.affected_pairs:
            html += f"<p><strong>Affected Pairs:</strong> {', '.join(alert.affected_pairs)}</p>"
        
        if alert.recommended_actions:
            html += "<p><strong>Recommended Actions:</strong></p><ul>"
            for action in alert.recommended_actions:
                html += f"<li>{action}</li>"
            html += "</ul>"
        
        if alert.data:
            html += f"""
                    <p><strong>Additional Data:</strong></p>
                    <pre style="background-color: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto;">
{json.dumps(alert.data, indent=2)}
                    </pre>
            """
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        
        return html


class AlertingSystem:
    """Main alerting system that manages rules, generates alerts, and handles delivery."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rules = {}
        self.alert_history = deque(maxlen=1000)
        self.delivery_service = AlertDeliveryService()
        
        # Alert statistics
        self.alert_stats = defaultdict(int)
        self.delivery_stats = defaultdict(int)
        
        # Background processing
        self.is_running = False
        self.processing_thread = None
        self.alert_queue = deque()
        
        # Initialize default rules
        self._initialize_default_rules()
        
        self.logger.info("Alerting system initialized")
    
    def _initialize_default_rules(self) -> None:
        """Initialize default alert rules."""
        
        # Performance decline rule
        self.add_rule(AlertRule(
            rule_id="performance_decline",
            name="Performance Decline Alert",
            alert_type=AlertType.PERFORMANCE_DECLINE,
            condition=lambda data: (
                'performance_change' in data and 
                data['performance_change'] < -0.05  # 5% decline
            ),
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.LOG, AlertChannel.CONSOLE],
            cooldown_minutes=30
        ))
        
        # System health rule
        self.add_rule(AlertRule(
            rule_id="system_health",
            name="System Health Alert",
            alert_type=AlertType.SYSTEM_HEALTH,
            condition=lambda data: (
                'health_score' in data and 
                data['health_score'] < 0.7  # Below 70% health
            ),
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG, AlertChannel.CONSOLE],
            cooldown_minutes=15
        ))
        
        # Component failure rule
        self.add_rule(AlertRule(
            rule_id="component_failure",
            name="Component Failure Alert",
            alert_type=AlertType.COMPONENT_FAILURE,
            condition=lambda data: (
                'component_status' in data and 
                data['component_status'] == 'failed'
            ),
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.LOG, AlertChannel.CONSOLE],
            cooldown_minutes=5
        ))
        
        # Risk threshold rule
        self.add_rule(AlertRule(
            rule_id="risk_threshold",
            name="Risk Threshold Alert",
            alert_type=AlertType.RISK_THRESHOLD,
            condition=lambda data: (
                'risk_level' in data and 
                data['risk_level'] > 0.8  # Above 80% risk threshold
            ),
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.LOG, AlertChannel.CONSOLE],
            cooldown_minutes=10
        ))
        
        # Adaptation failure rule
        self.add_rule(AlertRule(
            rule_id="adaptation_failure",
            name="Adaptation Failure Alert",
            alert_type=AlertType.ADAPTATION_FAILURE,
            condition=lambda data: (
                'adaptation_success' in data and 
                not data['adaptation_success']
            ),
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG, AlertChannel.CONSOLE],
            cooldown_minutes=20
        ))
    
    def start(self) -> None:
        """Start the alerting system background processing."""
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        self.logger.info("Alerting system started")
    
    def stop(self) -> None:
        """Stop the alerting system."""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        self.logger.info("Alerting system stopped")
    
    def _processing_loop(self) -> None:
        """Background processing loop for alert delivery."""
        while self.is_running:
            try:
                if self.alert_queue:
                    alert, channels = self.alert_queue.popleft()
                    self._deliver_alert(alert, channels)
                else:
                    time.sleep(1)  # Wait if no alerts to process
            except Exception as e:
                self.logger.error(f"Error in alert processing loop: {str(e)}")
                time.sleep(1)
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self.rules[rule.rule_id] = rule
        self.logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> None:
        """Remove an alert rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.logger.info(f"Removed alert rule: {rule_id}")
    
    def enable_rule(self, rule_id: str) -> None:
        """Enable an alert rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            self.logger.info(f"Enabled alert rule: {rule_id}")
    
    def disable_rule(self, rule_id: str) -> None:
        """Disable an alert rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            self.logger.info(f"Disabled alert rule: {rule_id}")
    
    def check_conditions(self, data: Dict[str, Any]) -> List[Alert]:
        """Check all rules against provided data and generate alerts."""
        alerts = []
        
        for rule in self.rules.values():
            if not rule.can_trigger():
                continue
            
            try:
                if rule.condition(data):
                    alert = self._create_alert_from_rule(rule, data)
                    alerts.append(alert)
                    rule.trigger()
                    
            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule.rule_id}: {str(e)}")
        
        return alerts
    
    def _create_alert_from_rule(self, rule: AlertRule, data: Dict[str, Any]) -> Alert:
        """Create an alert from a triggered rule."""
        alert_id = f"{rule.rule_id}_{int(datetime.now().timestamp())}"
        
        # Generate title and message based on alert type
        title, message = self._generate_alert_content(rule.alert_type, data)
        
        alert = Alert(
            alert_id=alert_id,
            alert_type=rule.alert_type,
            severity=rule.severity,
            title=title,
            message=message,
            timestamp=datetime.now(),
            data=data,
            source_component=data.get('component'),
            affected_strategies=data.get('strategies'),
            affected_pairs=data.get('pairs'),
            recommended_actions=self._get_recommended_actions(rule.alert_type, data)
        )
        
        return alert
    
    def _generate_alert_content(self, alert_type: AlertType, data: Dict[str, Any]) -> tuple[str, str]:
        """Generate title and message for alert based on type and data."""
        
        if alert_type == AlertType.PERFORMANCE_DECLINE:
            change = data.get('performance_change', 0)
            title = "Performance Decline Detected"
            message = f"System performance has declined by {abs(change):.2%} over the monitoring period."
            
        elif alert_type == AlertType.SYSTEM_HEALTH:
            health_score = data.get('health_score', 0)
            title = "System Health Degraded"
            message = f"System health score has dropped to {health_score:.1%}. Some components may be experiencing issues."
            
        elif alert_type == AlertType.COMPONENT_FAILURE:
            component = data.get('component', 'Unknown')
            title = f"Component Failure: {component}"
            message = f"Component '{component}' has failed and is no longer responding."
            
        elif alert_type == AlertType.RISK_THRESHOLD:
            risk_level = data.get('risk_level', 0)
            title = "Risk Threshold Exceeded"
            message = f"Current risk level ({risk_level:.1%}) has exceeded the configured threshold."
            
        elif alert_type == AlertType.ADAPTATION_FAILURE:
            adaptation_type = data.get('adaptation_type', 'Unknown')
            title = "Adaptation Failed"
            message = f"Adaptation of type '{adaptation_type}' has failed to improve performance."
            
        elif alert_type == AlertType.MARKET_REGIME_CHANGE:
            old_regime = data.get('old_regime', 'Unknown')
            new_regime = data.get('new_regime', 'Unknown')
            title = "Market Regime Change"
            message = f"Market regime has changed from {old_regime} to {new_regime}."
            
        else:
            title = f"Alert: {alert_type.value}"
            message = "An alert condition has been triggered."
        
        return title, message
    
    def _get_recommended_actions(self, alert_type: AlertType, data: Dict[str, Any]) -> List[str]:
        """Get recommended actions for an alert type."""
        
        actions = {
            AlertType.PERFORMANCE_DECLINE: [
                "Review recent strategy changes and adaptations",
                "Check market conditions for unusual patterns",
                "Consider reducing position sizes temporarily",
                "Analyze individual strategy performance"
            ],
            AlertType.SYSTEM_HEALTH: [
                "Check component logs for errors",
                "Verify data feed connectivity",
                "Restart unhealthy components if necessary",
                "Monitor system resources (CPU, memory)"
            ],
            AlertType.COMPONENT_FAILURE: [
                "Restart the failed component",
                "Check component configuration",
                "Review component logs for error details",
                "Switch to backup systems if available"
            ],
            AlertType.RISK_THRESHOLD: [
                "Reduce position sizes immediately",
                "Review current market exposure",
                "Check correlation between positions",
                "Consider closing some positions"
            ],
            AlertType.ADAPTATION_FAILURE: [
                "Rollback the failed adaptation",
                "Review adaptation parameters",
                "Check if market conditions have changed",
                "Analyze the adaptation's impact on performance"
            ]
        }
        
        return actions.get(alert_type, ["Review system status and take appropriate action"])
    
    def create_manual_alert(self, alert_type: AlertType, severity: AlertSeverity,
                          title: str, message: str, data: Optional[Dict[str, Any]] = None,
                          channels: Optional[List[AlertChannel]] = None) -> Alert:
        """Create and send a manual alert."""
        
        alert_id = f"manual_{int(datetime.now().timestamp())}"
        
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            timestamp=datetime.now(),
            data=data or {}
        )
        
        # Use default channels if none specified
        if channels is None:
            channels = [AlertChannel.LOG, AlertChannel.CONSOLE]
        
        self.send_alert(alert, channels)
        return alert
    
    def send_alert(self, alert: Alert, channels: List[AlertChannel]) -> None:
        """Send an alert through specified channels."""
        self.alert_history.append(alert)
        self.alert_stats[alert.alert_type] += 1
        
        # Queue alert for delivery
        self.alert_queue.append((alert, channels))
        
        self.logger.info(f"Queued alert {alert.alert_id} for delivery via {[c.value for c in channels]}")
    
    def _deliver_alert(self, alert: Alert, channels: List[AlertChannel]) -> None:
        """Deliver an alert through specified channels."""
        delivery_results = self.delivery_service.deliver_alert(alert, channels)
        
        # Update delivery statistics
        for channel, success in delivery_results.items():
            if success:
                self.delivery_stats[f"{channel.value}_success"] += 1
            else:
                self.delivery_stats[f"{channel.value}_failure"] += 1
        
        self.logger.info(f"Delivered alert {alert.alert_id}: {delivery_results}")
    
    def get_alert_history(self, hours_back: int = 24) -> List[Alert]:
        """Get alert history for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alerting system statistics."""
        return {
            'total_alerts': len(self.alert_history),
            'alert_types': dict(self.alert_stats),
            'delivery_stats': dict(self.delivery_stats),
            'active_rules': len([r for r in self.rules.values() if r.enabled]),
            'total_rules': len(self.rules),
            'queue_size': len(self.alert_queue)
        }
    
    def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
        """Acknowledge an alert."""
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                alert.acknowledge(user)
                self.logger.info(f"Alert {alert_id} acknowledged by {user}")
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                alert.resolve()
                self.logger.info(f"Alert {alert_id} resolved")
                return True
        return False
    
    # Convenience methods for common alert scenarios
    
    def alert_performance_decline(self, performance_change: float, 
                                strategy_name: Optional[str] = None,
                                timeframe: str = "1h") -> None:
        """Alert for performance decline."""
        data = {
            'performance_change': performance_change,
            'timeframe': timeframe
        }
        if strategy_name:
            data['strategies'] = [strategy_name]
        
        alerts = self.check_conditions(data)
        for alert in alerts:
            if alert.alert_type == AlertType.PERFORMANCE_DECLINE:
                self.send_alert(alert, [AlertChannel.LOG, AlertChannel.CONSOLE])
    
    def alert_system_health(self, health_score: float, 
                          unhealthy_components: List[str]) -> None:
        """Alert for system health issues."""
        data = {
            'health_score': health_score,
            'unhealthy_components': unhealthy_components
        }
        
        alerts = self.check_conditions(data)
        for alert in alerts:
            if alert.alert_type == AlertType.SYSTEM_HEALTH:
                self.send_alert(alert, [AlertChannel.LOG, AlertChannel.CONSOLE])
    
    def alert_component_failure(self, component_name: str, error_message: str) -> None:
        """Alert for component failure."""
        data = {
            'component': component_name,
            'component_status': 'failed',
            'error_message': error_message
        }
        
        alerts = self.check_conditions(data)
        for alert in alerts:
            if alert.alert_type == AlertType.COMPONENT_FAILURE:
                self.send_alert(alert, [AlertChannel.LOG, AlertChannel.CONSOLE])
    
    def alert_risk_threshold(self, risk_level: float, risk_type: str,
                           affected_pairs: List[str]) -> None:
        """Alert for risk threshold breach."""
        data = {
            'risk_level': risk_level,
            'risk_type': risk_type,
            'pairs': affected_pairs
        }
        
        alerts = self.check_conditions(data)
        for alert in alerts:
            if alert.alert_type == AlertType.RISK_THRESHOLD:
                self.send_alert(alert, [AlertChannel.LOG, AlertChannel.CONSOLE])
    
    def alert_adaptation_failure(self, adaptation_event: AdaptationEvent) -> None:
        """Alert for adaptation failure."""
        data = {
            'adaptation_success': False,
            'adaptation_type': adaptation_event.event_type.value,
            'adaptation_id': adaptation_event.event_id,
            'strategies': adaptation_event.affected_strategies,
            'pairs': adaptation_event.affected_pairs
        }
        
        alerts = self.check_conditions(data)
        for alert in alerts:
            if alert.alert_type == AlertType.ADAPTATION_FAILURE:
                self.send_alert(alert, [AlertChannel.LOG, AlertChannel.CONSOLE])
    
    def alert_market_regime_change(self, pair: str, old_regime: RegimeType, 
                                 new_regime: RegimeType, confidence: float) -> None:
        """Alert for market regime change."""
        alert = self.create_manual_alert(
            alert_type=AlertType.MARKET_REGIME_CHANGE,
            severity=AlertSeverity.MEDIUM,
            title=f"Market Regime Change: {pair}",
            message=f"Market regime for {pair} changed from {old_regime.value} to {new_regime.value} (confidence: {confidence:.2%})",
            data={
                'pair': pair,
                'old_regime': old_regime.value,
                'new_regime': new_regime.value,
                'confidence': confidence
            },
            channels=[AlertChannel.LOG, AlertChannel.CONSOLE]
        )