"""
Enhanced alert and notification system for the crypto trading bot.

This module provides advanced alerting capabilities with multi-channel support,
custom alert rules, prioritization, throttling, and comprehensive notification
management for cryptocurrency trading events.

Classes:
    AlertSeverity: Enhanced alert severity levels
    SystemAlertType: System-specific alert types
    AlertRule: Custom alert rule definition
    NotificationChannel: Base class for notification channels
    EmailNotificationChannel: Email notification implementation
    WebhookNotificationChannel: Webhook notification implementation
    ConsoleNotificationChannel: Console notification implementation
    RiskEvent: Risk-related event data structure
    TradeExecution: Trade execution data structure
    PerformanceMetrics: Performance metrics data structure
    EnhancedAlertSystem: Main enhanced alert system
"""

import os
import json
import time
import asyncio
import smtplib
import requests
import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Union, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict, deque
import logging

from bot.enhanced_logger import EnhancedLogger, ErrorSeverity


class AlertSeverity(Enum):
    """Enhanced alert severity levels with priority ordering"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SystemAlertType(Enum):
    """System-specific alert types"""
    TRADE_EXECUTED = "trade_executed"
    PRICE_MOVEMENT = "price_movement"
    RISK_LIMIT_APPROACHED = "risk_limit_approached"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    SYSTEM_ERROR = "system_error"
    API_ERROR = "api_error"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    BALANCE_LOW = "balance_low"
    PERFORMANCE_ALERT = "performance_alert"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    POSITION_LIMIT = "position_limit"
    AUTHENTICATION_FAILURE = "authentication_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SYSTEM_HEALTH = "system_health"


@dataclass
class AlertRule:
    """Custom alert rule definition"""
    rule_id: str
    name: str
    alert_type: SystemAlertType
    condition: Callable[[Dict[str, Any]], bool]
    severity: AlertSeverity
    enabled: bool = True
    throttle_minutes: int = 15
    channels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskEvent:
    """Risk-related event data structure"""
    event_type: str
    severity: AlertSeverity
    message: str
    details: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    pair: Optional[str] = None
    position_size: Optional[float] = None
    risk_level: Optional[float] = None


@dataclass
class TradeExecution:
    """Trade execution data structure"""
    trade_id: str
    pair: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    strategy: str
    fee: float = 0.0
    order_type: str = "market"
    execution_time_ms: int = 0
    status: str = "completed"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    timestamp: datetime
    total_pnl: float
    daily_pnl: float
    win_rate: float
    total_trades: int
    successful_trades: int
    sharpe_ratio: float
    max_drawdown: float
    current_positions: Dict[str, float]
    account_balance: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationChannel(ABC):
    """Base class for notification channels"""
    
    def __init__(self, channel_id: str, config: Dict[str, Any]):
        self.channel_id = channel_id
        self.config = config
        self.enabled = config.get('enabled', True)
        self.last_sent = {}
        self.send_count = defaultdict(int)
    
    @abstractmethod
    async def send_notification(self, alert_type: SystemAlertType, severity: AlertSeverity,
                              message: str, details: Dict[str, Any]) -> bool:
        """Send notification through this channel"""
        pass
    
    def can_send(self, alert_type: SystemAlertType, throttle_minutes: int) -> bool:
        """Check if notification can be sent based on throttling"""
        if not self.enabled:
            return False
        
        last_sent_time = self.last_sent.get(alert_type)
        if last_sent_time:
            time_diff = datetime.now() - last_sent_time
            if time_diff.total_seconds() < throttle_minutes * 60:
                return False
        
        return True
    
    def mark_sent(self, alert_type: SystemAlertType):
        """Mark notification as sent"""
        self.last_sent[alert_type] = datetime.now()
        self.send_count[alert_type] += 1


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel implementation"""
    
    async def send_notification(self, alert_type: SystemAlertType, severity: AlertSeverity,
                              message: str, details: Dict[str, Any]) -> bool:
        """Send email notification"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.config["from_address"]
            msg["To"] = ", ".join(self.config["to_addresses"])
            msg["Subject"] = f"Crypto Bot Alert [{severity.name}]: {alert_type.value}"
            
            # Create HTML body
            body = self._create_email_body(alert_type, severity, message, details)
            msg.attach(MIMEText(body, "html"))
            
            # Send email
            with smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"]) as server:
                server.starttls()
                server.login(self.config["username"], self.config["password"])
                server.send_message(msg)
            
            self.mark_sent(alert_type)
            return True
            
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")
            return False
    
    def _create_email_body(self, alert_type: SystemAlertType, severity: AlertSeverity,
                          message: str, details: Dict[str, Any]) -> str:
        """Create HTML email body"""
        severity_colors = {
            AlertSeverity.LOW: "#28a745",
            AlertSeverity.MEDIUM: "#ffc107", 
            AlertSeverity.HIGH: "#fd7e14",
            AlertSeverity.CRITICAL: "#dc3545"
        }
        
        color = severity_colors.get(severity, "#6c757d")
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="border-left: 4px solid {color}; padding-left: 20px;">
                <h2 style="color: {color}; margin-top: 0;">
                    Crypto Trading Bot Alert
                </h2>
                <p><strong>Severity:</strong> <span style="color: {color};">{severity.name}</span></p>
                <p><strong>Type:</strong> {alert_type.value}</p>
                <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p><strong>Message:</strong> {message}</p>
                
                <h3>Details:</h3>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                    <pre style="margin: 0; white-space: pre-wrap;">{json.dumps(details, indent=2, default=str)}</pre>
                </div>
            </div>
            
            <hr style="margin: 30px 0;">
            <p style="color: #6c757d; font-size: 12px;">
                This is an automated message from your crypto trading bot.
            </p>
        </body>
        </html>
        """


class WebhookNotificationChannel(NotificationChannel):
    """Webhook notification channel implementation"""
    
    async def send_notification(self, alert_type: SystemAlertType, severity: AlertSeverity,
                              message: str, details: Dict[str, Any]) -> bool:
        """Send webhook notification"""
        try:
            payload = {
                "alert_type": alert_type.value,
                "severity": severity.name,
                "message": message,
                "details": details,
                "timestamp": datetime.now().isoformat(),
                "channel_id": self.channel_id
            }
            
            headers = self.config.get("headers", {})
            headers.update({"Content-Type": "application/json"})
            
            response = requests.post(
                self.config["url"],
                json=payload,
                headers=headers,
                timeout=self.config.get("timeout", 30)
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                self.mark_sent(alert_type)
                return True
            else:
                logging.error(f"Webhook returned status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Failed to send webhook notification: {e}")
            return False


class ConsoleNotificationChannel(NotificationChannel):
    """Console notification channel implementation"""
    
    async def send_notification(self, alert_type: SystemAlertType, severity: AlertSeverity,
                              message: str, details: Dict[str, Any]) -> bool:
        """Send console notification"""
        try:
            severity_colors = {
                AlertSeverity.LOW: "\033[92m",      # Green
                AlertSeverity.MEDIUM: "\033[93m",   # Yellow
                AlertSeverity.HIGH: "\033[91m",     # Red
                AlertSeverity.CRITICAL: "\033[95m"  # Magenta
            }
            
            reset_color = "\033[0m"
            color = severity_colors.get(severity, "")
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n{color}{'='*60}{reset_color}")
            print(f"{color}[{severity.name}] CRYPTO BOT ALERT{reset_color}")
            print(f"{color}{'='*60}{reset_color}")
            print(f"Time: {timestamp}")
            print(f"Type: {alert_type.value}")
            print(f"Message: {message}")
            
            if details:
                print(f"\nDetails:")
                for key, value in details.items():
                    print(f"  {key}: {value}")
            
            print(f"{color}{'='*60}{reset_color}\n")
            
            self.mark_sent(alert_type)
            return True
            
        except Exception as e:
            logging.error(f"Failed to send console notification: {e}")
            return False


class EnhancedAlertSystem:
    """
    Enhanced alert and notification system with multi-channel support,
    custom rules, prioritization, and throttling mechanisms.
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[EnhancedLogger] = None):
        """
        Initialize the enhanced alert system.
        
        Args:
            config: Alert system configuration
            logger: Enhanced logger instance
        """
        self.config = config
        self.logger = logger
        self.enabled = config.get('enabled', True)
        
        # Initialize notification channels
        self.channels: Dict[str, NotificationChannel] = {}
        self._initialize_channels()
        
        # Alert rules
        self.rules: Dict[str, AlertRule] = {}
        self._load_alert_rules()
        
        # Alert history and throttling
        self.alert_history: deque = deque(maxlen=config.get('max_history', 1000))
        self.throttle_state: Dict[str, datetime] = {}
        self.priority_queue: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.performance_stats = {
            'total_alerts': 0,
            'alerts_by_type': defaultdict(int),
            'alerts_by_severity': defaultdict(int),
            'channel_success_rate': defaultdict(list)
        }
        
        # Background processing
        self._processing_thread = None
        self._stop_processing = threading.Event()
        self._start_background_processing()
    
    def _initialize_channels(self):
        """Initialize notification channels from configuration"""
        channels_config = self.config.get('channels', {})
        
        # Email channel
        if 'email' in channels_config and channels_config['email'].get('enabled', False):
            self.channels['email'] = EmailNotificationChannel('email', channels_config['email'])
        
        # Webhook channel
        if 'webhook' in channels_config and channels_config['webhook'].get('enabled', False):
            self.channels['webhook'] = WebhookNotificationChannel('webhook', channels_config['webhook'])
        
        # Console channel
        if 'console' in channels_config and channels_config['console'].get('enabled', True):
            self.channels['console'] = ConsoleNotificationChannel('console', channels_config['console'])
    
    def _load_alert_rules(self):
        """Load custom alert rules from configuration"""
        rules_config = self.config.get('rules', [])
        
        for rule_config in rules_config:
            try:
                rule = AlertRule(
                    rule_id=rule_config['rule_id'],
                    name=rule_config['name'],
                    alert_type=SystemAlertType(rule_config['alert_type']),
                    condition=self._create_condition_function(rule_config['condition']),
                    severity=AlertSeverity(rule_config['severity']),
                    enabled=rule_config.get('enabled', True),
                    throttle_minutes=rule_config.get('throttle_minutes', 15),
                    channels=rule_config.get('channels', []),
                    metadata=rule_config.get('metadata', {})
                )
                self.rules[rule.rule_id] = rule
            except Exception as e:
                if self.logger:
                    self.logger.log_error(e, {"rule_config": rule_config}, ErrorSeverity.MEDIUM)
    
    def _create_condition_function(self, condition_config: Dict[str, Any]) -> Callable:
        """Create condition function from configuration"""
        # This is a simplified implementation - in practice, you'd want a more
        # sophisticated rule engine
        def condition_func(data: Dict[str, Any]) -> bool:
            try:
                field = condition_config.get('field')
                operator = condition_config.get('operator')
                value = condition_config.get('value')
                
                if field not in data:
                    return False
                
                data_value = data[field]
                
                if operator == 'gt':
                    return data_value > value
                elif operator == 'lt':
                    return data_value < value
                elif operator == 'eq':
                    return data_value == value
                elif operator == 'gte':
                    return data_value >= value
                elif operator == 'lte':
                    return data_value <= value
                elif operator == 'contains':
                    return value in str(data_value)
                
                return False
            except Exception:
                return False
        
        return condition_func
    
    def _start_background_processing(self):
        """Start background processing thread"""
        if self._processing_thread is None or not self._processing_thread.is_alive():
            self._processing_thread = threading.Thread(target=self._process_alerts_background)
            self._processing_thread.daemon = True
            self._processing_thread.start()
    
    def _process_alerts_background(self):
        """Background processing of alert queue"""
        while not self._stop_processing.is_set():
            try:
                if self.priority_queue:
                    # Sort by severity (highest first)
                    self.priority_queue.sort(key=lambda x: x['severity'].value, reverse=True)
                    
                    # Process highest priority alert
                    alert_data = self.priority_queue.pop(0)
                    asyncio.run(self._send_alert_to_channels(
                        alert_data['alert_type'],
                        alert_data['severity'],
                        alert_data['message'],
                        alert_data['details'],
                        alert_data['channels']
                    ))
                
                time.sleep(0.1)  # Small delay to prevent busy waiting
                
            except Exception as e:
                if self.logger:
                    self.logger.log_error(e, {"context": "background_alert_processing"}, ErrorSeverity.HIGH)
                time.sleep(1)
    
    async def _send_alert_to_channels(self, alert_type: SystemAlertType, severity: AlertSeverity,
                                    message: str, details: Dict[str, Any], 
                                    target_channels: Optional[List[str]] = None):
        """Send alert to specified channels"""
        channels_to_use = target_channels or list(self.channels.keys())
        
        for channel_id in channels_to_use:
            if channel_id in self.channels:
                channel = self.channels[channel_id]
                
                # Check throttling
                throttle_key = f"{channel_id}:{alert_type.value}"
                throttle_minutes = self.config.get('default_throttle_minutes', 15)
                
                if channel.can_send(alert_type, throttle_minutes):
                    try:
                        success = await channel.send_notification(alert_type, severity, message, details)
                        self.performance_stats['channel_success_rate'][channel_id].append(success)
                        
                        # Keep only last 100 results for success rate calculation
                        if len(self.performance_stats['channel_success_rate'][channel_id]) > 100:
                            self.performance_stats['channel_success_rate'][channel_id].pop(0)
                            
                    except Exception as e:
                        if self.logger:
                            self.logger.log_error(e, {"channel_id": channel_id, "context": "send_alert"}, ErrorSeverity.MEDIUM)
    
    def add_alert_rule(self, rule: AlertRule) -> None:
        """
        Add a custom alert rule.
        
        Args:
            rule: Alert rule to add
        """
        self.rules[rule.rule_id] = rule
        
        if self.logger:
            self.logger.logger.info(f"Added alert rule: {rule.name} ({rule.rule_id})")
    
    def remove_alert_rule(self, rule_id: str) -> bool:
        """
        Remove an alert rule.
        
        Args:
            rule_id: ID of rule to remove
            
        Returns:
            bool: True if rule was removed
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            if self.logger:
                self.logger.logger.info(f"Removed alert rule: {rule_id}")
            return True
        return False
    
    def send_trade_alert(self, trade: TradeExecution) -> None:
        """
        Send alert for trade execution.
        
        Args:
            trade: Trade execution details
        """
        if not self.enabled:
            return
        
        # Determine severity based on trade size
        trade_value = trade.quantity * trade.price
        if trade_value > 10000:
            severity = AlertSeverity.HIGH
        elif trade_value > 1000:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW
        
        message = f"Trade executed: {trade.side} {trade.quantity:.8f} {trade.pair} @ ${trade.price:.2f}"
        
        details = {
            'trade_id': trade.trade_id,
            'pair': trade.pair,
            'side': trade.side,
            'quantity': trade.quantity,
            'price': trade.price,
            'trade_value': trade_value,
            'strategy': trade.strategy,
            'fee': trade.fee,
            'execution_time_ms': trade.execution_time_ms,
            'timestamp': trade.timestamp.isoformat()
        }
        
        self._queue_alert(SystemAlertType.TRADE_EXECUTED, severity, message, details)
    
    def send_performance_alert(self, metrics: PerformanceMetrics) -> None:
        """
        Send alert for performance metrics.
        
        Args:
            metrics: Performance metrics
        """
        if not self.enabled:
            return
        
        # Determine severity based on performance
        if metrics.daily_pnl < -1000 or metrics.max_drawdown > 0.2:
            severity = AlertSeverity.CRITICAL
        elif metrics.daily_pnl < -500 or metrics.max_drawdown > 0.1:
            severity = AlertSeverity.HIGH
        elif metrics.win_rate < 0.4:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW
        
        message = f"Performance update: Daily P&L: ${metrics.daily_pnl:.2f}, Win Rate: {metrics.win_rate:.1%}"
        
        details = {
            'total_pnl': metrics.total_pnl,
            'daily_pnl': metrics.daily_pnl,
            'win_rate': metrics.win_rate,
            'total_trades': metrics.total_trades,
            'successful_trades': metrics.successful_trades,
            'sharpe_ratio': metrics.sharpe_ratio,
            'max_drawdown': metrics.max_drawdown,
            'account_balance': metrics.account_balance,
            'timestamp': metrics.timestamp.isoformat()
        }
        
        self._queue_alert(SystemAlertType.PERFORMANCE_ALERT, severity, message, details)
    
    def send_system_alert(self, alert_type: SystemAlertType, message: str, 
                         severity: AlertSeverity, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Send system alert.
        
        Args:
            alert_type: Type of system alert
            message: Alert message
            severity: Alert severity
            details: Additional details
        """
        if not self.enabled:
            return
        
        self._queue_alert(alert_type, severity, message, details or {})
    
    def send_risk_alert(self, risk_event: RiskEvent) -> None:
        """
        Send alert for risk event.
        
        Args:
            risk_event: Risk event details
        """
        if not self.enabled:
            return
        
        message = f"Risk event: {risk_event.message}"
        
        details = {
            'event_type': risk_event.event_type,
            'pair': risk_event.pair,
            'position_size': risk_event.position_size,
            'risk_level': risk_event.risk_level,
            'timestamp': risk_event.timestamp.isoformat(),
            **risk_event.details
        }
        
        alert_type = SystemAlertType.RISK_LIMIT_APPROACHED if risk_event.severity != AlertSeverity.CRITICAL else SystemAlertType.RISK_LIMIT_EXCEEDED
        
        self._queue_alert(alert_type, risk_event.severity, message, details)
    
    def configure_alert_throttling(self, alert_type: str, max_frequency: int) -> None:
        """
        Configure alert throttling for specific alert type.
        
        Args:
            alert_type: Alert type to configure
            max_frequency: Maximum frequency in minutes
        """
        if 'throttling' not in self.config:
            self.config['throttling'] = {}
        
        self.config['throttling'][alert_type] = max_frequency
        
        if self.logger:
            self.logger.logger.info(f"Configured throttling for {alert_type}: {max_frequency} minutes")
    
    def _queue_alert(self, alert_type: SystemAlertType, severity: AlertSeverity,
                    message: str, details: Dict[str, Any]):
        """Queue alert for processing"""
        # Check custom rules
        matching_rules = []
        for rule in self.rules.values():
            if rule.enabled and rule.alert_type == alert_type:
                if rule.condition(details):
                    matching_rules.append(rule)
        
        # Use rule channels if available, otherwise use all channels
        channels = []
        if matching_rules:
            for rule in matching_rules:
                channels.extend(rule.channels)
            channels = list(set(channels))  # Remove duplicates
        
        alert_data = {
            'alert_type': alert_type,
            'severity': severity,
            'message': message,
            'details': details,
            'channels': channels,
            'timestamp': datetime.now()
        }
        
        # Add to priority queue
        self.priority_queue.append(alert_data)
        
        # Add to history
        self.alert_history.append(alert_data)
        
        # Update statistics
        self.performance_stats['total_alerts'] += 1
        self.performance_stats['alerts_by_type'][alert_type.value] += 1
        self.performance_stats['alerts_by_severity'][severity.name] += 1
        
        if self.logger:
            self.logger.logger.info(f"Queued alert: {alert_type.value} - {message}")
    
    def send_daily_summary(self, summary_data: Dict[str, Any]) -> None:
        """
        Send daily performance summary.
        
        Args:
            summary_data: Daily summary data
        """
        if not self.enabled:
            return
        
        message = f"Daily Summary - P&L: ${summary_data.get('daily_pnl', 0):.2f}, Trades: {summary_data.get('total_trades', 0)}"
        
        self._queue_alert(SystemAlertType.DAILY_SUMMARY, AlertSeverity.LOW, message, summary_data)
    
    def send_weekly_summary(self, summary_data: Dict[str, Any]) -> None:
        """
        Send weekly performance summary.
        
        Args:
            summary_data: Weekly summary data
        """
        if not self.enabled:
            return
        
        message = f"Weekly Summary - P&L: ${summary_data.get('weekly_pnl', 0):.2f}, Win Rate: {summary_data.get('win_rate', 0):.1%}"
        
        self._queue_alert(SystemAlertType.WEEKLY_SUMMARY, AlertSeverity.LOW, message, summary_data)
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """
        Get alert system statistics.
        
        Returns:
            Dict: Alert statistics
        """
        # Calculate channel success rates
        success_rates = {}
        for channel_id, results in self.performance_stats['channel_success_rate'].items():
            if results:
                success_rates[channel_id] = sum(results) / len(results)
            else:
                success_rates[channel_id] = 0.0
        
        return {
            'total_alerts': self.performance_stats['total_alerts'],
            'alerts_by_type': dict(self.performance_stats['alerts_by_type']),
            'alerts_by_severity': dict(self.performance_stats['alerts_by_severity']),
            'channel_success_rates': success_rates,
            'active_rules': len([r for r in self.rules.values() if r.enabled]),
            'total_rules': len(self.rules),
            'enabled_channels': len([c for c in self.channels.values() if c.enabled]),
            'queue_size': len(self.priority_queue)
        }
    
    def shutdown(self):
        """Shutdown the alert system"""
        self._stop_processing.set()
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5)
        
        if self.logger:
            self.logger.logger.info("Enhanced alert system shutdown complete")


# Default configuration
DEFAULT_ALERT_CONFIG = {
    'enabled': True,
    'max_history': 1000,
    'default_throttle_minutes': 15,
    'channels': {
        'console': {
            'enabled': True
        },
        'email': {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': '',
            'password': '',
            'from_address': '',
            'to_addresses': []
        },
        'webhook': {
            'enabled': False,
            'url': '',
            'headers': {},
            'timeout': 30
        }
    },
    'rules': [],
    'throttling': {
        'trade_executed': 5,
        'price_movement': 15,
        'risk_limit_approached': 30,
        'system_error': 10,
        'performance_alert': 60
    }
}


def create_enhanced_alert_system(config: Optional[Dict[str, Any]] = None,
                               logger: Optional[EnhancedLogger] = None) -> EnhancedAlertSystem:
    """
    Create an enhanced alert system instance.
    
    Args:
        config: Alert system configuration (uses default if None)
        logger: Enhanced logger instance
        
    Returns:
        EnhancedAlertSystem: Configured alert system
    """
    if config is None:
        config = DEFAULT_ALERT_CONFIG.copy()
    
    return EnhancedAlertSystem(config, logger)