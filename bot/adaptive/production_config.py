"""
Production Configuration for Adaptive Trading Bot

This module provides production-ready configuration with appropriate safety limits,
logging setup, and deployment settings.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class ProductionLimits:
    """Production safety limits"""
    max_position_size_usd: float = 1000.0  # Maximum position size in USD
    max_daily_loss_usd: float = 500.0      # Maximum daily loss limit
    max_portfolio_risk: float = 0.02       # Maximum portfolio risk (2%)
    max_drawdown_percent: float = 5.0      # Maximum drawdown before shutdown
    max_adaptation_frequency_hours: int = 4  # Minimum hours between adaptations
    min_confidence_threshold: float = 0.7   # Minimum confidence for adaptations
    max_concurrent_positions: int = 5       # Maximum concurrent positions
    emergency_stop_loss_percent: float = 10.0  # Emergency stop loss


@dataclass
class DatabaseConfig:
    """Database configuration for persistent storage"""
    host: str = "localhost"
    port: int = 5432
    database: str = "adaptive_trading"
    username: str = "trading_bot"
    password: str = ""  # Set via environment variable
    ssl_mode: str = "require"
    connection_pool_size: int = 10
    max_overflow: int = 20
    
    def get_connection_string(self) -> str:
        """Get database connection string"""
        password = os.getenv('DB_PASSWORD', self.password)
        return f"postgresql://{self.username}:{password}@{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"


@dataclass
class LoggingConfig:
    """Production logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: str = "logs/production"
    max_file_size_mb: int = 100
    backup_count: int = 10
    enable_console: bool = False
    enable_file: bool = True
    enable_syslog: bool = True
    syslog_address: str = "/dev/log"
    
    # Specific log files
    main_log_file: str = "adaptive_bot.log"
    error_log_file: str = "errors.log"
    trade_log_file: str = "trades.log"
    performance_log_file: str = "performance.log"
    adaptation_log_file: str = "adaptations.log"


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    enable_health_checks: bool = True
    health_check_interval_seconds: int = 60
    enable_performance_monitoring: bool = True
    performance_check_interval_seconds: int = 300
    enable_email_alerts: bool = True
    enable_slack_alerts: bool = False
    alert_cooldown_minutes: int = 30
    
    # Alert thresholds
    cpu_usage_threshold: float = 80.0
    memory_usage_threshold: float = 85.0
    disk_usage_threshold: float = 90.0
    api_error_rate_threshold: float = 5.0  # Errors per minute


@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_api_key_rotation: bool = True
    api_key_rotation_days: int = 30
    enable_request_signing: bool = True
    enable_ip_whitelist: bool = True
    allowed_ips: list = field(default_factory=list)
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 100
    enable_audit_logging: bool = True


@dataclass
class ProductionConfig:
    """Main production configuration"""
    environment: str = "production"
    debug: bool = False
    testing: bool = False
    
    # Component configurations
    limits: ProductionLimits = field(default_factory=ProductionLimits)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Trading configuration
    enable_live_trading: bool = False  # Start in paper trading mode
    enable_adaptations: bool = True
    enable_ml_predictions: bool = True
    enable_regime_detection: bool = True
    
    # Performance settings
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    enable_parallel_processing: bool = True
    max_worker_threads: int = 4
    
    # Backup and recovery
    enable_state_backup: bool = True
    backup_interval_hours: int = 6
    backup_retention_days: int = 30
    
    @classmethod
    def from_file(cls, config_path: str) -> 'ProductionConfig':
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return cls.from_dict(config_data)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ProductionConfig':
        """Create configuration from dictionary"""
        # This is a simplified implementation
        # In practice, you'd want more sophisticated parsing
        config = cls()
        
        # Update limits if provided
        if 'limits' in config_dict:
            limits_dict = config_dict['limits']
            config.limits = ProductionLimits(**limits_dict)
        
        # Update database config if provided
        if 'database' in config_dict:
            db_dict = config_dict['database']
            config.database = DatabaseConfig(**db_dict)
        
        # Update logging config if provided
        if 'logging' in config_dict:
            log_dict = config_dict['logging']
            config.logging = LoggingConfig(**log_dict)
        
        # Update monitoring config if provided
        if 'monitoring' in config_dict:
            mon_dict = config_dict['monitoring']
            config.monitoring = MonitoringConfig(**mon_dict)
        
        # Update security config if provided
        if 'security' in config_dict:
            sec_dict = config_dict['security']
            config.security = SecurityConfig(**sec_dict)
        
        # Update top-level settings
        for key, value in config_dict.items():
            if hasattr(config, key) and key not in ['limits', 'database', 'logging', 'monitoring', 'security']:
                setattr(config, key, value)
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'environment': self.environment,
            'debug': self.debug,
            'testing': self.testing,
            'enable_live_trading': self.enable_live_trading,
            'enable_adaptations': self.enable_adaptations,
            'enable_ml_predictions': self.enable_ml_predictions,
            'enable_regime_detection': self.enable_regime_detection,
            'enable_caching': self.enable_caching,
            'cache_ttl_seconds': self.cache_ttl_seconds,
            'enable_parallel_processing': self.enable_parallel_processing,
            'max_worker_threads': self.max_worker_threads,
            'enable_state_backup': self.enable_state_backup,
            'backup_interval_hours': self.backup_interval_hours,
            'backup_retention_days': self.backup_retention_days,
            'limits': {
                'max_position_size_usd': self.limits.max_position_size_usd,
                'max_daily_loss_usd': self.limits.max_daily_loss_usd,
                'max_portfolio_risk': self.limits.max_portfolio_risk,
                'max_drawdown_percent': self.limits.max_drawdown_percent,
                'max_adaptation_frequency_hours': self.limits.max_adaptation_frequency_hours,
                'min_confidence_threshold': self.limits.min_confidence_threshold,
                'max_concurrent_positions': self.limits.max_concurrent_positions,
                'emergency_stop_loss_percent': self.limits.emergency_stop_loss_percent
            },
            'database': {
                'host': self.database.host,
                'port': self.database.port,
                'database': self.database.database,
                'username': self.database.username,
                'ssl_mode': self.database.ssl_mode,
                'connection_pool_size': self.database.connection_pool_size,
                'max_overflow': self.database.max_overflow
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
                'log_dir': self.logging.log_dir,
                'max_file_size_mb': self.logging.max_file_size_mb,
                'backup_count': self.logging.backup_count,
                'enable_console': self.logging.enable_console,
                'enable_file': self.logging.enable_file,
                'enable_syslog': self.logging.enable_syslog,
                'syslog_address': self.logging.syslog_address
            },
            'monitoring': {
                'enable_health_checks': self.monitoring.enable_health_checks,
                'health_check_interval_seconds': self.monitoring.health_check_interval_seconds,
                'enable_performance_monitoring': self.monitoring.enable_performance_monitoring,
                'performance_check_interval_seconds': self.monitoring.performance_check_interval_seconds,
                'enable_email_alerts': self.monitoring.enable_email_alerts,
                'enable_slack_alerts': self.monitoring.enable_slack_alerts,
                'alert_cooldown_minutes': self.monitoring.alert_cooldown_minutes,
                'cpu_usage_threshold': self.monitoring.cpu_usage_threshold,
                'memory_usage_threshold': self.monitoring.memory_usage_threshold,
                'disk_usage_threshold': self.monitoring.disk_usage_threshold,
                'api_error_rate_threshold': self.monitoring.api_error_rate_threshold
            },
            'security': {
                'enable_api_key_rotation': self.security.enable_api_key_rotation,
                'api_key_rotation_days': self.security.api_key_rotation_days,
                'enable_request_signing': self.security.enable_request_signing,
                'enable_ip_whitelist': self.security.enable_ip_whitelist,
                'allowed_ips': self.security.allowed_ips,
                'enable_rate_limiting': self.security.enable_rate_limiting,
                'max_requests_per_minute': self.security.max_requests_per_minute,
                'enable_audit_logging': self.security.enable_audit_logging
            }
        }
    
    def save_to_file(self, config_path: str) -> None:
        """Save configuration to JSON file"""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def validate(self) -> list:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Validate limits
        if self.limits.max_position_size_usd <= 0:
            issues.append("max_position_size_usd must be positive")
        
        if self.limits.max_daily_loss_usd <= 0:
            issues.append("max_daily_loss_usd must be positive")
        
        if not 0 < self.limits.max_portfolio_risk <= 1:
            issues.append("max_portfolio_risk must be between 0 and 1")
        
        if not 0 < self.limits.min_confidence_threshold <= 1:
            issues.append("min_confidence_threshold must be between 0 and 1")
        
        # Validate database config
        if not self.database.host:
            issues.append("database host is required")
        
        if not self.database.database:
            issues.append("database name is required")
        
        if not self.database.username:
            issues.append("database username is required")
        
        # Validate logging config
        if self.logging.level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            issues.append("invalid logging level")
        
        # Validate monitoring thresholds
        if not 0 < self.monitoring.cpu_usage_threshold <= 100:
            issues.append("cpu_usage_threshold must be between 0 and 100")
        
        if not 0 < self.monitoring.memory_usage_threshold <= 100:
            issues.append("memory_usage_threshold must be between 0 and 100")
        
        return issues


def setup_production_logging(config: LoggingConfig) -> None:
    """Setup production logging configuration"""
    # Create log directory
    os.makedirs(config.log_dir, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # File handler for main log
    if config.enable_file:
        from logging.handlers import RotatingFileHandler
        
        main_log_path = os.path.join(config.log_dir, config.main_log_file)
        file_handler = RotatingFileHandler(
            main_log_path,
            maxBytes=config.max_file_size_mb * 1024 * 1024,
            backupCount=config.backup_count
        )
        file_handler.setFormatter(logging.Formatter(config.format))
        root_logger.addHandler(file_handler)
        
        # Error log handler
        error_log_path = os.path.join(config.log_dir, config.error_log_file)
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=config.max_file_size_mb * 1024 * 1024,
            backupCount=config.backup_count
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(config.format))
        root_logger.addHandler(error_handler)
    
    # Console handler
    if config.enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(config.format))
        root_logger.addHandler(console_handler)
    
    # Syslog handler
    if config.enable_syslog:
        try:
            from logging.handlers import SysLogHandler
            syslog_handler = SysLogHandler(address=config.syslog_address)
            syslog_handler.setFormatter(logging.Formatter(config.format))
            root_logger.addHandler(syslog_handler)
        except Exception as e:
            logging.warning(f"Failed to setup syslog handler: {e}")


def get_production_config() -> ProductionConfig:
    """Get production configuration from environment or file"""
    config_path = os.getenv('ADAPTIVE_BOT_CONFIG', 'config/production.json')
    
    if os.path.exists(config_path):
        return ProductionConfig.from_file(config_path)
    else:
        # Return default production config
        config = ProductionConfig()
        
        # Override with environment variables
        if os.getenv('ENABLE_LIVE_TRADING', '').lower() == 'true':
            config.enable_live_trading = True
        
        if os.getenv('DEBUG', '').lower() == 'true':
            config.debug = True
        
        # Database configuration from environment
        if os.getenv('DB_HOST'):
            config.database.host = os.getenv('DB_HOST')
        if os.getenv('DB_PORT'):
            config.database.port = int(os.getenv('DB_PORT'))
        if os.getenv('DB_NAME'):
            config.database.database = os.getenv('DB_NAME')
        if os.getenv('DB_USER'):
            config.database.username = os.getenv('DB_USER')
        
        return config