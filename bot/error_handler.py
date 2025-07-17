"""
Comprehensive error handling and recovery module for the crypto trading bot.
Provides centralized error handling, notification, and recovery mechanisms.
"""
import time
import random
import logging
import traceback
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from functools import wraps
from datetime import datetime, timedelta
import os
import json

from bot.utils import log_error, log_info, log_warning


class ErrorType:
    """Enum-like class for error types"""
    API_RATE_LIMIT = "api_rate_limit"
    API_AUTH = "api_auth"
    NETWORK = "network"
    DATA_VALIDATION = "data_validation"
    TRADE_EXECUTION = "trade_execution"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorSeverity:
    """Enum-like class for error severity levels"""
    LOW = "low"           # Non-critical, can continue
    MEDIUM = "medium"     # Potentially problematic, needs attention
    HIGH = "high"         # Critical, requires immediate action
    FATAL = "fatal"       # System cannot continue


class ErrorHandler:
    """
    Centralized error handling and recovery system.
    Manages error classification, recovery strategies, and notifications.
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the error handler.
        
        Args:
            config_path: Optional path to error handler configuration file
        """
        self.error_counts: Dict[str, int] = {}
        self.error_timestamps: Dict[str, List[datetime]] = {}
        self.last_notification_time: Dict[str, datetime] = {}
        self.notification_cooldown = 3600  # 1 hour between notifications for same error type
        
        # Default notification settings
        self.notification_config = {
            "enabled": False,
            "email": {
                "enabled": False,
                "smtp_server": "",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_email": "",
                "to_email": ""
            },
            "webhook": {
                "enabled": False,
                "url": "",
                "headers": {}
            }
        }
        
        # Load configuration if provided
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> None:
        """
        Load error handler configuration from file.
        
        Args:
            config_path: Path to configuration file
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Update notification config
            if "notification" in config:
                self.notification_config.update(config["notification"])
                
            # Update cooldown if specified
            if "notification_cooldown" in config:
                self.notification_cooldown = config["notification_cooldown"]
                
            log_info(f"Loaded error handler configuration from {config_path}")
            
        except Exception as e:
            log_error(f"Error loading error handler configuration: {str(e)}")
    
    def classify_error(self, error: Exception) -> Tuple[str, str]:
        """
        Classify an error by type and severity.
        
        Args:
            error: The exception to classify
            
        Returns:
            Tuple of (error_type, error_severity)
        """
        error_str = str(error).lower()
        error_type = ErrorType.UNKNOWN
        severity = ErrorSeverity.MEDIUM
        
        # API rate limit errors
        if any(term in error_str for term in ["rate limit", "429", "too many requests"]):
            error_type = ErrorType.API_RATE_LIMIT
            severity = ErrorSeverity.MEDIUM
        
        # Authentication errors
        elif any(term in error_str for term in ["auth", "401", "403", "unauthorized", "forbidden"]):
            error_type = ErrorType.API_AUTH
            severity = ErrorSeverity.HIGH
        
        # Network errors
        elif isinstance(error, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            error_type = ErrorType.NETWORK
            severity = ErrorSeverity.MEDIUM
        elif any(term in error_str for term in ["connection", "timeout", "network", "unreachable"]):
            error_type = ErrorType.NETWORK
            severity = ErrorSeverity.MEDIUM
        
        # Data validation errors
        elif any(term in error_str for term in ["validation", "invalid data", "missing data"]):
            error_type = ErrorType.DATA_VALIDATION
            severity = ErrorSeverity.MEDIUM
        
        # Trade execution errors
        elif any(term in error_str for term in ["order", "trade", "position", "execution"]):
            error_type = ErrorType.TRADE_EXECUTION
            severity = ErrorSeverity.HIGH
        
        # System errors
        elif any(term in error_str for term in ["memory", "disk", "system", "permission"]):
            error_type = ErrorType.SYSTEM
            severity = ErrorSeverity.HIGH
        
        return error_type, severity
    
    def handle_error(self, error: Exception, context: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Handle an error with appropriate recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Context in which the error occurred
            
        Returns:
            Tuple of (recoverable, recovery_info)
        """
        # Classify the error
        error_type, severity = self.classify_error(error)
        
        # Track error occurrence
        self._track_error(error_type)
        
        # Log the error
        log_error(f"Error in {context} - Type: {error_type}, Severity: {severity}", error)
        
        # Determine if error is recoverable
        recoverable = severity != ErrorSeverity.FATAL
        
        # Get recovery strategy
        recovery_info = self._get_recovery_strategy(error_type, severity)
        
        # Send notification if needed
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.FATAL]:
            self._send_notification(error, error_type, severity, context)
        
        return recoverable, recovery_info
    
    def _track_error(self, error_type: str) -> None:
        """
        Track error occurrence for rate limiting and pattern detection.
        
        Args:
            error_type: Type of error that occurred
        """
        # Increment error count
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Track timestamp
        if error_type not in self.error_timestamps:
            self.error_timestamps[error_type] = []
        
        self.error_timestamps[error_type].append(datetime.now())
        
        # Keep only last 100 timestamps
        if len(self.error_timestamps[error_type]) > 100:
            self.error_timestamps[error_type].pop(0)
    
    def _get_recovery_strategy(self, error_type: str, severity: str) -> Dict[str, Any]:
        """
        Get recovery strategy for an error type.
        
        Args:
            error_type: Type of error
            severity: Severity of error
            
        Returns:
            Dictionary with recovery strategy information
        """
        recovery_info = {
            "retry": False,
            "retry_delay": 0,
            "max_retries": 0,
            "backoff_factor": 2.0,
            "jitter": True,
            "fallback_action": None
        }
        
        # API rate limit errors
        if error_type == ErrorType.API_RATE_LIMIT:
            recovery_info.update({
                "retry": True,
                "retry_delay": 5,
                "max_retries": 5,
                "backoff_factor": 2.0,
                "jitter": True,
                "fallback_action": "skip_cycle"
            })
        
        # Authentication errors
        elif error_type == ErrorType.API_AUTH:
            recovery_info.update({
                "retry": False,
                "fallback_action": "exit"
            })
        
        # Network errors
        elif error_type == ErrorType.NETWORK:
            recovery_info.update({
                "retry": True,
                "retry_delay": 3,
                "max_retries": 5,
                "backoff_factor": 1.5,
                "jitter": True,
                "fallback_action": "skip_cycle"
            })
        
        # Data validation errors
        elif error_type == ErrorType.DATA_VALIDATION:
            recovery_info.update({
                "retry": True,
                "retry_delay": 2,
                "max_retries": 3,
                "backoff_factor": 1.5,
                "jitter": False,
                "fallback_action": "use_previous_data"
            })
        
        # Trade execution errors
        elif error_type == ErrorType.TRADE_EXECUTION:
            recovery_info.update({
                "retry": True,
                "retry_delay": 1,
                "max_retries": 2,
                "backoff_factor": 2.0,
                "jitter": False,
                "fallback_action": "skip_trade"
            })
        
        # System errors
        elif error_type == ErrorType.SYSTEM:
            recovery_info.update({
                "retry": False,
                "fallback_action": "restart"
            })
        
        # Unknown errors
        else:
            recovery_info.update({
                "retry": True,
                "retry_delay": 2,
                "max_retries": 3,
                "backoff_factor": 2.0,
                "jitter": True,
                "fallback_action": "skip_cycle"
            })
        
        return recovery_info
    
    def calculate_backoff_delay(self, base_delay: float, attempt: int, 
                              factor: float = 2.0, jitter: bool = True) -> float:
        """
        Calculate backoff delay with optional jitter.
        
        Args:
            base_delay: Base delay in seconds
            attempt: Current attempt number (0-based)
            factor: Backoff factor
            jitter: Whether to add jitter
            
        Returns:
            float: Delay in seconds
        """
        delay = base_delay * (factor ** attempt)
        
        if jitter:
            # Add random jitter between 0-25%
            jitter_amount = random.uniform(0, 0.25) * delay
            delay += jitter_amount
        
        return delay
    
    def _send_notification(self, error: Exception, error_type: str, 
                         severity: str, context: str) -> bool:
        """
        Send notification about critical error.
        
        Args:
            error: The exception that occurred
            error_type: Type of error
            severity: Severity of error
            context: Context in which the error occurred
            
        Returns:
            bool: True if notification was sent
        """
        # Check if notifications are enabled
        if not self.notification_config["enabled"]:
            return False
        
        # Check cooldown period
        now = datetime.now()
        last_time = self.last_notification_time.get(error_type)
        if last_time and (now - last_time).total_seconds() < self.notification_cooldown:
            return False
        
        # Update last notification time
        self.last_notification_time[error_type] = now
        
        # Prepare notification message
        subject = f"Crypto Bot Error: {error_type.upper()} - {severity.upper()}"
        message = f"""
        Error Type: {error_type}
        Severity: {severity}
        Context: {context}
        Time: {now.strftime('%Y-%m-%d %H:%M:%S')}
        
        Error Message: {str(error)}
        
        Traceback:
        {traceback.format_exc()}
        """
        
        # Send email notification
        email_sent = False
        if self.notification_config["email"]["enabled"]:
            email_sent = self._send_email_notification(subject, message)
        
        # Send webhook notification
        webhook_sent = False
        if self.notification_config["webhook"]["enabled"]:
            webhook_sent = self._send_webhook_notification(subject, message)
        
        return email_sent or webhook_sent
    
    def _send_email_notification(self, subject: str, message: str) -> bool:
        """
        Send email notification.
        
        Args:
            subject: Email subject
            message: Email message
            
        Returns:
            bool: True if email was sent
        """
        try:
            email_config = self.notification_config["email"]
            
            # Create message
            msg = MIMEMultipart()
            msg["From"] = email_config["from_email"]
            msg["To"] = email_config["to_email"]
            msg["Subject"] = subject
            
            # Attach message
            msg.attach(MIMEText(message, "plain"))
            
            # Connect to server
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["username"], email_config["password"])
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            log_info(f"Sent email notification: {subject}")
            return True
            
        except Exception as e:
            log_error(f"Error sending email notification: {str(e)}")
            return False
    
    def _send_webhook_notification(self, subject: str, message: str) -> bool:
        """
        Send webhook notification.
        
        Args:
            subject: Notification subject
            message: Notification message
            
        Returns:
            bool: True if webhook was sent
        """
        try:
            webhook_config = self.notification_config["webhook"]
            
            # Prepare payload
            payload = {
                "subject": subject,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send webhook
            response = requests.post(
                webhook_config["url"],
                json=payload,
                headers=webhook_config["headers"],
                timeout=10
            )
            
            if response.status_code < 400:
                log_info(f"Sent webhook notification: {subject}")
                return True
            else:
                log_error(f"Webhook notification failed with status {response.status_code}")
                return False
                
        except Exception as e:
            log_error(f"Error sending webhook notification: {str(e)}")
            return False
    
    def detect_error_patterns(self, error_type: str, time_window: int = 3600) -> Dict[str, Any]:
        """
        Detect patterns in error occurrences.
        
        Args:
            error_type: Type of error to analyze
            time_window: Time window in seconds
            
        Returns:
            Dictionary with pattern information
        """
        if error_type not in self.error_timestamps:
            return {"count": 0, "frequency": 0, "increasing": False}
        
        # Get timestamps in window
        now = datetime.now()
        window_start = now - timedelta(seconds=time_window)
        
        timestamps_in_window = [ts for ts in self.error_timestamps[error_type] 
                              if ts >= window_start]
        
        if not timestamps_in_window:
            return {"count": 0, "frequency": 0, "increasing": False}
        
        # Calculate metrics
        count = len(timestamps_in_window)
        frequency = count / (time_window / 3600)  # Errors per hour
        
        # Check if frequency is increasing
        if count >= 2:
            half_point = len(timestamps_in_window) // 2
            first_half = timestamps_in_window[:half_point]
            second_half = timestamps_in_window[half_point:]
            
            first_half_window = (max(first_half) - min(first_half)).total_seconds()
            second_half_window = (max(second_half) - min(second_half)).total_seconds()
            
            # Avoid division by zero
            if first_half_window > 0 and second_half_window > 0:
                first_freq = len(first_half) / (first_half_window / 3600)
                second_freq = len(second_half) / (second_half_window / 3600)
                increasing = second_freq > first_freq
            else:
                increasing = False
        else:
            increasing = False
        
        return {
            "count": count,
            "frequency": frequency,
            "increasing": increasing
        }
    
    def should_circuit_break(self, error_type: str, threshold: int = 10, 
                           time_window: int = 300) -> bool:
        """
        Determine if circuit breaker should be activated due to error frequency.
        
        Args:
            error_type: Type of error to check
            threshold: Number of errors to trigger circuit breaker
            time_window: Time window in seconds
            
        Returns:
            bool: True if circuit breaker should activate
        """
        pattern = self.detect_error_patterns(error_type, time_window)
        return pattern["count"] >= threshold
    
    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get statistics about errors.
        
        Returns:
            Dictionary with error statistics
        """
        stats = {}
        
        for error_type in self.error_counts.keys():
            stats[error_type] = {
                "total_count": self.error_counts.get(error_type, 0),
                "recent": self.detect_error_patterns(error_type, 3600)
            }
        
        return stats


def with_error_handling(error_handler: ErrorHandler, context: str, max_retries: int = 3):
    """
    Decorator for functions to add error handling with retries.
    
    Args:
        error_handler: ErrorHandler instance
        context: Context for error handling
        max_retries: Maximum number of retries
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            last_exception = None
            
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    recoverable, recovery_info = error_handler.handle_error(e, context)
                    
                    if not recoverable or not recovery_info["retry"] or retries >= max_retries:
                        break
                    
                    # Calculate backoff delay
                    delay = error_handler.calculate_backoff_delay(
                        recovery_info["retry_delay"],
                        retries,
                        recovery_info["backoff_factor"],
                        recovery_info["jitter"]
                    )
                    
                    log_warning(f"Retry {retries + 1}/{max_retries} for {func.__name__} "
                               f"after error: {str(e)}. Waiting {delay:.2f}s")
                    time.sleep(delay)
                    retries += 1
            
            # Handle fallback action
            if last_exception:
                _, recovery_info = error_handler.handle_error(last_exception, context)
                fallback = recovery_info.get("fallback_action")
                
                if fallback == "exit":
                    log_error(f"Critical error in {context}, exiting")
                    raise last_exception
                elif fallback == "skip_cycle":
                    log_warning(f"Skipping cycle due to error in {context}")
                    return None
                elif fallback == "use_previous_data":
                    log_warning(f"Using previous data due to error in {context}")
                    # Return None and let caller handle fallback
                    return None
                elif fallback == "skip_trade":
                    log_warning(f"Skipping trade due to error in {context}")
                    return None
                elif fallback == "restart":
                    log_warning(f"System error requires restart")
                    # In a real system, we might trigger a restart here
                    return None
            
            raise last_exception
            
        return wrapper
    return decorator


# Create a global instance for convenience
global_error_handler = ErrorHandler()