"""
Crypto alerts module for the trading bot.

This module provides functionality to generate and send alerts for
critical cryptocurrency trading events.

Classes:
    AlertLevel: Enum for alert severity levels
    AlertType: Enum for alert types
    CryptoAlert: Data structure for crypto alerts
    CryptoAlertManager: Manager for crypto alerts
"""
import os
import logging
import datetime
import json
import smtplib
import requests
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, asdict, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from bot.crypto_logger import CryptoLogger, global_crypto_logger


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of crypto alerts"""
    BALANCE_LOW = "balance_low"
    LARGE_PRICE_MOVEMENT = "large_price_movement"
    HIGH_API_ERROR_RATE = "high_api_error_rate"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    LARGE_TRADE = "large_trade"
    AUTHENTICATION_FAILURE = "authentication_failure"
    WEBSOCKET_DISCONNECTION = "websocket_disconnection"
    SYSTEM_PERFORMANCE = "system_performance"
    TRADING_VOLUME_SPIKE = "trading_volume_spike"
    POSITION_LIMIT_REACHED = "position_limit_reached"


@dataclass
class CryptoAlert:
    """Data structure for crypto alerts"""
    alert_type: AlertType
    level: AlertLevel
    message: str
    timestamp: datetime.datetime
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    alert_id: Optional[str] = None
    
    def __post_init__(self):
        """Generate alert ID if not provided"""
        if self.alert_id is None:
            self.alert_id = f"{self.timestamp.strftime('%Y%m%d%H%M%S')}-{self.alert_type.value}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result["alert_type"] = self.alert_type.value
        result["level"] = self.level.value
        result["timestamp"] = self.timestamp.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CryptoAlert':
        """Create alert from dictionary"""
        return cls(
            alert_type=AlertType(data["alert_type"]),
            level=AlertLevel(data["level"]),
            message=data["message"],
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
            details=data.get("details", {}),
            acknowledged=data.get("acknowledged", False),
            alert_id=data.get("alert_id")
        )


class CryptoAlertManager:
    """
    Manager for crypto trading alerts.
    
    This class handles the generation, storage, and notification of
    alerts for critical cryptocurrency trading events.
    """
    
    def __init__(self, logger: Optional[CryptoLogger] = None,
                 config_path: Optional[str] = None,
                 alerts_history_path: Optional[str] = None):
        """
        Initialize the crypto alert manager.
        
        Args:
            logger: CryptoLogger instance to use (uses global instance if None)
            config_path: Path to alert configuration file
            alerts_history_path: Path to alerts history file
        """
        self.logger = logger or global_crypto_logger
        self.config_path = config_path or "alerts_config.json"
        self.alerts_history_path = alerts_history_path or "alerts_history.json"
        
        # Load configuration
        self.config = self._load_config()
        
        # Load alerts history
        self.alerts_history = self._load_alerts_history()
        
        # Active alerts
        self.active_alerts: Dict[str, CryptoAlert] = {}
        
        # Alert handlers
        self.alert_handlers: Dict[AlertType, List[Callable]] = {}
        
        # Register default handlers
        self._register_default_handlers()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load alert configuration from file.
        
        Returns:
            Dict: Alert configuration
        """
        default_config = {
            "enabled": True,
            "alert_levels": {
                "info": True,
                "warning": True,
                "error": True,
                "critical": True
            },
            "alert_types": {
                alert_type.value: True for alert_type in AlertType
            },
            "thresholds": {
                "balance_low_usd": 100.0,
                "large_price_movement_percent": 5.0,
                "high_api_error_rate_percent": 10.0,
                "rate_limit_threshold": 5,
                "large_trade_usd": 1000.0,
                "system_cpu_percent": 80.0,
                "system_memory_percent": 80.0,
                "trading_volume_spike_percent": 200.0,
                "position_limit_percent": 90.0
            },
            "notifications": {
                "email": {
                    "enabled": False,
                    "smtp_server": "",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "from_address": "",
                    "to_addresses": []
                },
                "webhook": {
                    "enabled": False,
                    "url": "",
                    "headers": {}
                },
                "console": {
                    "enabled": True
                },
                "log": {
                    "enabled": True
                }
            },
            "cooldown_minutes": {
                "balance_low": 60,
                "large_price_movement": 15,
                "high_api_error_rate": 30,
                "rate_limit_exceeded": 15,
                "large_trade": 15,
                "authentication_failure": 60,
                "websocket_disconnection": 15,
                "system_performance": 30,
                "trading_volume_spike": 30,
                "position_limit_reached": 30
            }
        }
        
        # Try to load config from file
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                
                # Merge with default config
                for key, value in loaded_config.items():
                    if key in default_config:
                        if isinstance(value, dict) and isinstance(default_config[key], dict):
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Failed to load alert configuration")
        
        return default_config
    
    def _load_alerts_history(self) -> List[CryptoAlert]:
        """
        Load alerts history from file.
        
        Returns:
            List[CryptoAlert]: Alert history
        """
        alerts = []
        
        try:
            if os.path.exists(self.alerts_history_path):
                with open(self.alerts_history_path, 'r') as f:
                    alerts_data = json.load(f)
                
                for alert_data in alerts_data:
                    try:
                        alerts.append(CryptoAlert.from_dict(alert_data))
                    except (KeyError, ValueError) as e:
                        if self.logger:
                            self.logger.log_error(e, "Failed to load alert from history")
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Failed to load alerts history")
        
        return alerts
    
    def _save_alerts_history(self) -> bool:
        """
        Save alerts history to file.
        
        Returns:
            bool: True if successful
        """
        try:
            # Combine active and historical alerts
            all_alerts = self.alerts_history + list(self.active_alerts.values())
            
            # Sort by timestamp
            all_alerts.sort(key=lambda a: a.timestamp)
            
            # Convert to dictionaries
            alerts_data = [alert.to_dict() for alert in all_alerts]
            
            # Save to file
            with open(self.alerts_history_path, 'w') as f:
                json.dump(alerts_data, f, indent=2)
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Failed to save alerts history")
            return False
    
    def _register_default_handlers(self) -> None:
        """Register default alert handlers."""
        # Register console handler for all alert types
        for alert_type in AlertType:
            self.register_handler(alert_type, self._handle_console_alert)
            self.register_handler(alert_type, self._handle_log_alert)
    
    def register_handler(self, alert_type: AlertType, handler: Callable) -> None:
        """
        Register a handler for an alert type.
        
        Args:
            alert_type: Type of alert to handle
            handler: Handler function
        """
        if alert_type not in self.alert_handlers:
            self.alert_handlers[alert_type] = []
        
        self.alert_handlers[alert_type].append(handler)
    
    def _handle_console_alert(self, alert: CryptoAlert) -> None:
        """
        Handle alert by printing to console.
        
        Args:
            alert: Alert to handle
        """
        if not self.config["notifications"]["console"]["enabled"]:
            return
        
        # Print to console using rich if available
        if self.logger and self.logger.use_rich:
            level_colors = {
                AlertLevel.INFO: "blue",
                AlertLevel.WARNING: "yellow",
                AlertLevel.ERROR: "red",
                AlertLevel.CRITICAL: "bold red"
            }
            color = level_colors.get(alert.level, "white")
            
            self.logger.console.print(
                f"[bold {color}]{alert.level.value.upper()}[/bold {color}] "
                f"{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {alert.message}"
            )
    
    def _handle_log_alert(self, alert: CryptoAlert) -> None:
        """
        Handle alert by logging to file.
        
        Args:
            alert: Alert to handle
        """
        if not self.config["notifications"]["log"]["enabled"]:
            return
        
        # Log to file
        if self.logger:
            log_levels = {
                AlertLevel.INFO: self.logger.log_info,
                AlertLevel.WARNING: self.logger.log_warning,
                AlertLevel.ERROR: lambda msg: self.logger.log_error(Exception(msg), "ALERT")
            }
            
            log_func = log_levels.get(alert.level, self.logger.log_info)
            log_func(f"ALERT: {alert.alert_type.value} - {alert.message}")
    
    def _handle_email_alert(self, alert: CryptoAlert) -> bool:
        """
        Handle alert by sending email.
        
        Args:
            alert: Alert to handle
            
        Returns:
            bool: True if email was sent successfully
        """
        email_config = self.config["notifications"]["email"]
        if not email_config["enabled"]:
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = email_config["from_address"]
            msg["To"] = ", ".join(email_config["to_addresses"])
            msg["Subject"] = f"Crypto Trading Alert: {alert.level.value.upper()} - {alert.alert_type.value}"
            
            # Create message body
            body = f"""
            <html>
            <body>
                <h2>Crypto Trading Alert</h2>
                <p><strong>Level:</strong> {alert.level.value.upper()}</p>
                <p><strong>Type:</strong> {alert.alert_type.value}</p>
                <p><strong>Time:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Message:</strong> {alert.message}</p>
                
                <h3>Details:</h3>
                <pre>{json.dumps(alert.details, indent=2)}</pre>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, "html"))
            
            # Connect to SMTP server
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["username"], email_config["password"])
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Failed to send alert email")
            return False
    
    def _handle_webhook_alert(self, alert: CryptoAlert) -> bool:
        """
        Handle alert by sending webhook.
        
        Args:
            alert: Alert to handle
            
        Returns:
            bool: True if webhook was sent successfully
        """
        webhook_config = self.config["notifications"]["webhook"]
        if not webhook_config["enabled"]:
            return False
        
        try:
            # Create payload
            payload = {
                "alert": alert.to_dict(),
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Send webhook
            response = requests.post(
                webhook_config["url"],
                json=payload,
                headers=webhook_config.get("headers", {})
            )
            
            return response.status_code >= 200 and response.status_code < 300
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Failed to send alert webhook")
            return False
    
    def trigger_alert(self, alert_type: AlertType, level: AlertLevel, message: str,
                     details: Optional[Dict[str, Any]] = None) -> Optional[CryptoAlert]:
        """
        Trigger a new alert.
        
        Args:
            alert_type: Type of alert
            level: Severity level
            message: Alert message
            details: Additional details
            
        Returns:
            Optional[CryptoAlert]: The created alert if successful
        """
        # Check if alerts are enabled
        if not self.config["enabled"]:
            return None
        
        # Check if this alert type is enabled
        if not self.config["alert_types"].get(alert_type.value, True):
            return None
        
        # Check if this alert level is enabled
        if not self.config["alert_levels"].get(level.value, True):
            return None
        
        # Create alert
        alert = CryptoAlert(
            alert_type=alert_type,
            level=level,
            message=message,
            timestamp=datetime.datetime.now(),
            details=details or {}
        )
        
        # Check for cooldown
        if not self._check_cooldown(alert):
            return None
        
        # Add to active alerts
        self.active_alerts[alert.alert_id] = alert
        
        # Handle alert
        self._handle_alert(alert)
        
        # Save alerts history
        self._save_alerts_history()
        
        return alert
    
    def _check_cooldown(self, alert: CryptoAlert) -> bool:
        """
        Check if an alert is in cooldown period.
        
        Args:
            alert: Alert to check
            
        Returns:
            bool: True if alert is not in cooldown
        """
        # Get cooldown minutes for this alert type
        cooldown_minutes = self.config["cooldown_minutes"].get(
            alert.alert_type.value, 15
        )
        
        # Check recent alerts of the same type
        now = datetime.datetime.now()
        cooldown_threshold = now - datetime.timedelta(minutes=cooldown_minutes)
        
        # Check active alerts
        for active_alert in self.active_alerts.values():
            if (active_alert.alert_type == alert.alert_type and
                active_alert.timestamp > cooldown_threshold):
                return False
        
        # Check recent historical alerts
        for hist_alert in reversed(self.alerts_history):
            if hist_alert.timestamp < cooldown_threshold:
                break
            
            if hist_alert.alert_type == alert.alert_type:
                return False
        
        return True
    
    def _handle_alert(self, alert: CryptoAlert) -> None:
        """
        Handle an alert using registered handlers.
        
        Args:
            alert: Alert to handle
        """
        # Get handlers for this alert type
        handlers = self.alert_handlers.get(alert.alert_type, [])
        
        # Call each handler
        for handler in handlers:
            try:
                handler(alert)
            except Exception as e:
                if self.logger:
                    self.logger.log_error(e, f"Alert handler failed for {alert.alert_type.value}")
        
        # Handle email notification
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            self._handle_email_alert(alert)
        
        # Handle webhook notification
        self._handle_webhook_alert(alert)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an active alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            
        Returns:
            bool: True if alert was acknowledged
        """
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            
            # Move to history
            self.alerts_history.append(self.active_alerts[alert_id])
            del self.active_alerts[alert_id]
            
            # Save alerts history
            self._save_alerts_history()
            
            return True
        
        return False
    
    def check_balance_low(self, currency: str, balance: float, usd_value: float) -> None:
        """
        Check if balance is low and trigger alert if needed.
        
        Args:
            currency: Currency code
            balance: Balance amount
            usd_value: USD value of balance
        """
        threshold = self.config["thresholds"]["balance_low_usd"]
        
        if usd_value < threshold:
            self.trigger_alert(
                AlertType.BALANCE_LOW,
                AlertLevel.WARNING,
                f"Low balance for {currency}: {balance:.8f} (${usd_value:.2f})",
                {
                    "currency": currency,
                    "balance": balance,
                    "usd_value": usd_value,
                    "threshold": threshold
                }
            )
    
    def check_price_movement(self, symbol: str, old_price: float, new_price: float) -> None:
        """
        Check if price movement is large and trigger alert if needed.
        
        Args:
            symbol: Trading symbol
            old_price: Previous price
            new_price: Current price
        """
        threshold = self.config["thresholds"]["large_price_movement_percent"]
        
        if old_price > 0:
            percent_change = abs(new_price - old_price) / old_price * 100
            
            if percent_change > threshold:
                direction = "up" if new_price > old_price else "down"
                self.trigger_alert(
                    AlertType.LARGE_PRICE_MOVEMENT,
                    AlertLevel.WARNING,
                    f"Large price movement for {symbol}: {direction} {percent_change:.2f}% (${old_price:.2f} -> ${new_price:.2f})",
                    {
                        "symbol": symbol,
                        "old_price": old_price,
                        "new_price": new_price,
                        "percent_change": percent_change,
                        "threshold": threshold
                    }
                )
    
    def check_api_error_rate(self, error_rate: float) -> None:
        """
        Check if API error rate is high and trigger alert if needed.
        
        Args:
            error_rate: API error rate (0.0 to 1.0)
        """
        threshold = self.config["thresholds"]["high_api_error_rate_percent"] / 100.0
        
        if error_rate > threshold:
            self.trigger_alert(
                AlertType.HIGH_API_ERROR_RATE,
                AlertLevel.ERROR,
                f"High API error rate: {error_rate*100:.2f}%",
                {
                    "error_rate": error_rate,
                    "threshold": threshold
                }
            )
    
    def check_rate_limit(self, hits: int) -> None:
        """
        Check if rate limit hits are high and trigger alert if needed.
        
        Args:
            hits: Number of rate limit hits
        """
        threshold = self.config["thresholds"]["rate_limit_threshold"]
        
        if hits > threshold:
            self.trigger_alert(
                AlertType.RATE_LIMIT_EXCEEDED,
                AlertLevel.WARNING,
                f"Rate limit exceeded: {hits} hits",
                {
                    "hits": hits,
                    "threshold": threshold
                }
            )
    
    def check_large_trade(self, symbol: str, side: str, quantity: float, price: float) -> None:
        """
        Check if trade is large and trigger alert if needed.
        
        Args:
            symbol: Trading symbol
            side: Trade side (BUY/SELL)
            quantity: Trade quantity
            price: Trade price
        """
        threshold = self.config["thresholds"]["large_trade_usd"]
        trade_value = quantity * price
        
        if trade_value > threshold:
            self.trigger_alert(
                AlertType.LARGE_TRADE,
                AlertLevel.INFO,
                f"Large trade: {side} {quantity:.8f} {symbol} @ ${price:.2f} (${trade_value:.2f})",
                {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                    "trade_value": trade_value,
                    "threshold": threshold
                }
            )
    
    def alert_authentication_failure(self, error_message: str) -> None:
        """
        Trigger alert for authentication failure.
        
        Args:
            error_message: Error message
        """
        self.trigger_alert(
            AlertType.AUTHENTICATION_FAILURE,
            AlertLevel.CRITICAL,
            f"Authentication failure: {error_message}",
            {
                "error_message": error_message
            }
        )
    
    def alert_websocket_disconnection(self, reason: str) -> None:
        """
        Trigger alert for WebSocket disconnection.
        
        Args:
            reason: Disconnection reason
        """
        self.trigger_alert(
            AlertType.WEBSOCKET_DISCONNECTION,
            AlertLevel.WARNING,
            f"WebSocket disconnected: {reason}",
            {
                "reason": reason
            }
        )
    
    def check_system_performance(self, cpu_percent: float, memory_percent: float) -> None:
        """
        Check system performance and trigger alert if needed.
        
        Args:
            cpu_percent: CPU usage percentage
            memory_percent: Memory usage percentage
        """
        cpu_threshold = self.config["thresholds"]["system_cpu_percent"]
        memory_threshold = self.config["thresholds"]["system_memory_percent"]
        
        if cpu_percent > cpu_threshold:
            self.trigger_alert(
                AlertType.SYSTEM_PERFORMANCE,
                AlertLevel.WARNING,
                f"High CPU usage: {cpu_percent:.1f}%",
                {
                    "cpu_percent": cpu_percent,
                    "threshold": cpu_threshold
                }
            )
        
        if memory_percent > memory_threshold:
            self.trigger_alert(
                AlertType.SYSTEM_PERFORMANCE,
                AlertLevel.WARNING,
                f"High memory usage: {memory_percent:.1f}%",
                {
                    "memory_percent": memory_percent,
                    "threshold": memory_threshold
                }
            )
    
    def check_trading_volume_spike(self, symbol: str, normal_volume: float, current_volume: float) -> None:
        """
        Check for trading volume spike and trigger alert if needed.
        
        Args:
            symbol: Trading symbol
            normal_volume: Normal trading volume
            current_volume: Current trading volume
        """
        threshold = self.config["thresholds"]["trading_volume_spike_percent"] / 100.0
        
        if normal_volume > 0:
            ratio = current_volume / normal_volume
            
            if ratio > 1 + threshold:
                self.trigger_alert(
                    AlertType.TRADING_VOLUME_SPIKE,
                    AlertLevel.INFO,
                    f"Trading volume spike for {symbol}: {ratio:.1f}x normal volume",
                    {
                        "symbol": symbol,
                        "normal_volume": normal_volume,
                        "current_volume": current_volume,
                        "ratio": ratio,
                        "threshold": 1 + threshold
                    }
                )
    
    def check_position_limit(self, currency: str, current_value: float, max_value: float) -> None:
        """
        Check if position is approaching limit and trigger alert if needed.
        
        Args:
            currency: Currency code
            current_value: Current position value
            max_value: Maximum position value
        """
        threshold = self.config["thresholds"]["position_limit_percent"] / 100.0
        
        if max_value > 0:
            ratio = current_value / max_value
            
            if ratio > threshold:
                self.trigger_alert(
                    AlertType.POSITION_LIMIT_REACHED,
                    AlertLevel.WARNING,
                    f"Position limit approaching for {currency}: {ratio*100:.1f}% of maximum",
                    {
                        "currency": currency,
                        "current_value": current_value,
                        "max_value": max_value,
                        "ratio": ratio,
                        "threshold": threshold
                    }
                )


# Create a global instance for convenience
global_alert_manager = CryptoAlertManager()


def get_alert_manager() -> CryptoAlertManager:
    """
    Get the global alert manager instance.
    
    Returns:
        CryptoAlertManager: Global alert manager instance
    """
    return global_alert_manager