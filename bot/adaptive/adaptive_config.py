"""
Adaptive bot configuration system with runtime updates and validation.
"""
import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import threading
import logging

from .enums import RegimeType, AdaptationType, OptimizationMethod, ModelType
from .data_models import ParameterBounds, ParameterType


logger = logging.getLogger(__name__)


@dataclass
class MLEngineConfig:
    """Configuration for the machine learning engine."""
    # Model settings
    enabled_models: List[ModelType] = field(default_factory=lambda: [
        ModelType.RANDOM_FOREST, ModelType.GRADIENT_BOOSTING
    ])
    ensemble_enabled: bool = True
    online_learning_enabled: bool = True
    
    # Training parameters
    training_window_days: int = 30
    min_training_samples: int = 25  # Reduced from 100 to 50 for faster initial learning
    validation_split: float = 0.2
    retrain_frequency_hours: int = 6  # Reduced from 24 to 12 for more frequent retraining
    
    # Feature engineering
    feature_lookback_periods: List[int] = field(default_factory=lambda: [5, 10, 20, 50])
    include_technical_indicators: bool = True
    include_market_microstructure: bool = True
    include_sentiment_features: bool = False
    
    # Model performance thresholds
    min_model_confidence: float = 0.3  # Reduced from 0.6 to 0.4 for more responsive learning
    model_drift_threshold: float = 0.1
    auto_rollback_threshold: float = 0.05
    
    # Resource limits
    max_training_time_minutes: int = 30
    max_memory_usage_gb: float = 2.0
    
    def validate(self) -> bool:
        """Validate ML engine configuration."""
        if not self.enabled_models:
            return False
        if not 0.0 <= self.validation_split <= 1.0:
            return False
        if not 0.0 <= self.min_model_confidence <= 1.0:
            return False
        if self.training_window_days <= 0 or self.min_training_samples <= 0:
            return False
        return True


@dataclass
class RegimeDetectionConfig:
    """Configuration for market regime detection."""
    # Detection parameters
    enabled: bool = True
    confidence_threshold: float = 0.7
    regime_change_threshold: float = 0.3
    
    # Timeframes for analysis
    timeframes: List[str] = field(default_factory=lambda: ["5m", "15m", "1h", "4h"])
    primary_timeframe: str = "1h"
    
    # Indicator settings
    volatility_lookback: int = 20
    trend_lookback: int = 50
    momentum_lookback: int = 14
    volume_lookback: int = 20
    
    # Regime transition smoothing
    transition_smoothing: bool = True
    min_regime_duration_minutes: int = 30
    
    # Regime-specific thresholds
    high_volatility_threshold: float = 0.05
    strong_trend_threshold: float = 0.7
    momentum_threshold: float = 0.6
    
    def validate(self) -> bool:
        """Validate regime detection configuration."""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            return False
        if not 0.0 <= self.regime_change_threshold <= 1.0:
            return False
        if not self.timeframes or self.primary_timeframe not in self.timeframes:
            return False
        if any(period <= 0 for period in [self.volatility_lookback, self.trend_lookback, 
                                         self.momentum_lookback, self.volume_lookback]):
            return False
        return True


@dataclass
class ParameterOptimizationConfig:
    """Configuration for dynamic parameter optimization."""
    # Optimization settings
    enabled: bool = True
    optimization_methods: List[OptimizationMethod] = field(default_factory=lambda: [
        OptimizationMethod.BAYESIAN, OptimizationMethod.GENETIC_ALGORITHM
    ])
    
    # Optimization frequency and triggers
    optimization_frequency_hours: int = 24
    min_performance_degradation: float = 0.05  # 5% degradation triggers optimization
    min_trades_for_optimization: int = 50
    
    # Validation settings
    walk_forward_enabled: bool = True
    validation_window_days: int = 7
    out_of_sample_ratio: float = 0.3
    
    # Parameter bounds and constraints
    parameter_bounds: Dict[str, ParameterBounds] = field(default_factory=dict)
    max_parameter_change_pct: float = 0.5  # Max 50% change per optimization
    
    # Optimization limits
    max_optimization_time_minutes: int = 60
    max_iterations: int = 100
    convergence_tolerance: float = 1e-6
    
    def validate(self) -> bool:
        """Validate parameter optimization configuration."""
        if not self.optimization_methods:
            return False
        if not 0.0 <= self.out_of_sample_ratio <= 1.0:
            return False
        if not 0.0 <= self.max_parameter_change_pct <= 1.0:
            return False
        if any(val <= 0 for val in [self.optimization_frequency_hours, self.min_trades_for_optimization,
                                   self.validation_window_days, self.max_optimization_time_minutes]):
            return False
        return True


@dataclass
class AdaptationControlConfig:
    """Configuration for adaptation control and limits."""
    # Adaptation frequency limits
    max_adaptations_per_hour: int = 5  # Increased from 2 to 3
    max_adaptations_per_day: int = 10
    min_time_between_adaptations_minutes: int = 10  # Reduced from 30 to 15
    
    # Performance thresholds for adaptation
    min_performance_threshold: float = -0.05  # Changed from 0.7 to -0.1 (10% drop triggers adaptation)
    adaptation_confidence_threshold: float = 0.5  # Reduced from 0.8 to 0.6
    
    # Rollback settings
    auto_rollback_enabled: bool = True
    rollback_performance_threshold: float = -0.05  # 5% performance drop
    rollback_evaluation_period_hours: int = 24
    
    # A/B testing
    ab_testing_enabled: bool = True
    ab_test_allocation_pct: float = 0.2  # 20% of capital for testing
    ab_test_duration_hours: int = 48
    
    # Emergency controls
    emergency_stop_enabled: bool = True
    emergency_stop_loss_pct: float = 0.1  # 10% loss triggers emergency stop
    
    def validate(self) -> bool:
        """Validate adaptation control configuration."""
        if any(val <= 0 for val in [self.max_adaptations_per_hour, self.max_adaptations_per_day,
                                   self.min_time_between_adaptations_minutes]):
            return False
        if not 0.0 <= self.min_performance_threshold <= 1.0:
            return False
        if not 0.0 <= self.adaptation_confidence_threshold <= 1.0:
            return False
        if not 0.0 <= self.ab_test_allocation_pct <= 1.0:
            return False
        return True


@dataclass
class StrategyConfig:
    """Configuration for adaptive strategy management."""
    # Strategy selection
    enabled_strategies: List[str] = field(default_factory=lambda: [
        "momentum", "mean_reversion", "volatility_breakout", "trend_following"
    ])
    
    # Dynamic weighting
    dynamic_weighting_enabled: bool = True
    weight_adjustment_frequency_hours: int = 6
    performance_lookback_days: int = 7
    
    # Strategy allocation bounds
    min_strategy_weight: float = 0.05  # Minimum 5% allocation
    max_strategy_weight: float = 0.6   # Maximum 60% allocation
    
    # Strategy switching
    strategy_switching_enabled: bool = True
    switching_hysteresis: float = 0.1  # 10% hysteresis to prevent whipsaws
    min_strategy_performance_period_hours: int = 12
    
    # Ensemble settings
    ensemble_enabled: bool = True
    ensemble_voting_method: str = "weighted"  # "weighted", "majority", "confidence"
    
    def validate(self) -> bool:
        """Validate strategy configuration."""
        if not self.enabled_strategies:
            return False
        if not 0.0 <= self.min_strategy_weight <= self.max_strategy_weight <= 1.0:
            return False
        if not 0.0 <= self.switching_hysteresis <= 1.0:
            return False
        if self.ensemble_voting_method not in ["weighted", "majority", "confidence"]:
            return False
        return True


@dataclass
class RiskManagementConfig:
    """Configuration for adaptive risk management."""
    # Position sizing
    adaptive_position_sizing: bool = True
    base_position_size_usd: float = 100.0
    max_position_size_usd: float = 1000.0
    
    # Volatility-based adjustments
    volatility_adjustment_enabled: bool = True
    volatility_lookback_periods: int = 20
    max_volatility_reduction: float = 0.5  # Reduce position by up to 50%
    
    # Regime-based risk adjustments
    regime_risk_multipliers: Dict[RegimeType, float] = field(default_factory=lambda: {
        RegimeType.TRENDING_BULL: 1.2,
        RegimeType.TRENDING_BEAR: 0.8,
        RegimeType.RANGING: 1.0,
        RegimeType.HIGH_VOLATILITY: 0.6,
        RegimeType.LOW_VOLATILITY: 1.1,
        RegimeType.UNCERTAIN: 0.5
    })
    
    # Correlation limits
    max_correlation_exposure: float = 0.7
    correlation_lookback_days: int = 30
    
    # Drawdown protection
    max_portfolio_drawdown_pct: float = 0.15  # 15%
    daily_loss_limit_pct: float = 0.05  # 5%
    
    def validate(self) -> bool:
        """Validate risk management configuration."""
        if self.base_position_size_usd <= 0 or self.max_position_size_usd <= 0:
            return False
        if self.base_position_size_usd > self.max_position_size_usd:
            return False
        if not 0.0 <= self.max_volatility_reduction <= 1.0:
            return False
        if not 0.0 <= self.max_correlation_exposure <= 1.0:
            return False
        if not all(0.0 <= mult <= 2.0 for mult in self.regime_risk_multipliers.values()):
            return False
        return True


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and alerting."""
    # Performance monitoring
    performance_monitoring_enabled: bool = True
    performance_check_frequency_minutes: int = 15
    performance_alert_threshold_pct: float = 0.05  # 5% change triggers alert
    
    # System health monitoring
    health_check_frequency_minutes: int = 5
    component_timeout_seconds: int = 30
    
    # Alerting
    alerting_enabled: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["console", "log"])
    critical_alert_threshold: float = 0.1  # 10% performance drop
    
    # Dashboard
    dashboard_enabled: bool = True
    dashboard_update_frequency_seconds: int = 30
    dashboard_history_days: int = 30
    
    def validate(self) -> bool:
        """Validate monitoring configuration."""
        if any(val <= 0 for val in [self.performance_check_frequency_minutes,
                                   self.health_check_frequency_minutes,
                                   self.component_timeout_seconds]):
            return False
        if not 0.0 <= self.performance_alert_threshold_pct <= 1.0:
            return False
        if not self.alert_channels:
            return False
        return True


@dataclass
class AdaptiveBotConfig:
    """Main configuration class for the adaptive trading bot."""
    # Component configurations
    ml_engine: MLEngineConfig = field(default_factory=MLEngineConfig)
    regime_detection: RegimeDetectionConfig = field(default_factory=RegimeDetectionConfig)
    parameter_optimization: ParameterOptimizationConfig = field(default_factory=ParameterOptimizationConfig)
    adaptation_control: AdaptationControlConfig = field(default_factory=AdaptationControlConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk_management: RiskManagementConfig = field(default_factory=RiskManagementConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Global settings
    enabled: bool = True
    trading_pairs: List[str] = field(default_factory=lambda: ["XBTUSD", "ETHUSD"])
    
    # Trading settings
    paper_trading: bool = True
    initial_capital: float = 480.0
    adaptation_enabled: bool = True
    max_risk_per_trade: float = 0.08
    max_portfolio_risk: float = 0.25
    max_drawdown_threshold: float = 0.20
    
    # System settings
    max_threads: int = 4
    monitoring_enabled: bool = True
    alerting_enabled: bool = True
    adaptation_frequency_minutes: int = 60
    performance_evaluation_hours: int = 24
    health_check_interval_seconds: int = 30
    state_persistence_interval_minutes: int = 15
    data_retention_days: int = 90
    backup_frequency_hours: int = 24
    log_level: str = "INFO"
    
    # Configuration metadata
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)
    
    def get_regime_detector_config(self) -> Dict[str, Any]:
        """Get configuration for market regime detector."""
        return self.regime_detection.__dict__
    
    def get_ml_engine_config(self) -> Dict[str, Any]:
        """Get configuration for ML engine."""
        config = self.ml_engine.__dict__.copy()
        config['model_storage_path'] = 'models/adaptive'
        return config
    
    def get_optimizer_config(self) -> Dict[str, Any]:
        """Get configuration for parameter optimizer."""
        return self.parameter_optimization.__dict__
    
    def get_performance_config(self) -> Dict[str, Any]:
        """Get configuration for performance analyzer."""
        return {
            'lookback_periods': [24, 168, 720],  # 1 day, 1 week, 1 month in hours
            'metrics_to_track': ['return', 'sharpe', 'max_drawdown', 'win_rate'],
            'benchmark_symbol': 'BTC/USD'
        }
    
    def get_strategy_engine_config(self) -> Dict[str, Any]:
        """Get configuration for adaptive strategy engine."""
        return self.strategy.__dict__
    
    def get_adaptation_config(self) -> Dict[str, Any]:
        """Get configuration for adaptation controller."""
        return self.adaptation_control.__dict__
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get configuration for monitoring dashboard."""
        return self.monitoring.__dict__
    
    def get_alerting_config(self) -> Dict[str, Any]:
        """Get configuration for alerting system."""
        return {
            'email_enabled': False,
            'slack_enabled': False,
            'discord_enabled': False,
            'alert_thresholds': {
                'drawdown': 0.1,
                'consecutive_losses': 5,
                'system_error': True
            }
        }

    def validate(self) -> bool:
        """Validate the entire adaptive bot configuration."""
        if not self.trading_pairs:
            logger.error("No trading pairs configured")
            return False
        
        # Validate all component configurations
        components = [
            ("ml_engine", self.ml_engine),
            ("regime_detection", self.regime_detection),
            ("parameter_optimization", self.parameter_optimization),
            ("adaptation_control", self.adaptation_control),
            ("strategy", self.strategy),
            ("risk_management", self.risk_management),
            ("monitoring", self.monitoring)
        ]
        
        for name, config in components:
            if not config.validate():
                logger.error(f"Invalid {name} configuration")
                return False
        
        # Validate global settings
        if self.data_retention_days <= 0 or self.backup_frequency_hours <= 0:
            logger.error("Invalid system settings")
            return False
        
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            logger.error("Invalid log level")
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        config_dict = asdict(self)
        
        # Convert RegimeType enum keys to strings in regime_risk_multipliers
        if 'risk_management' in config_dict and 'regime_risk_multipliers' in config_dict['risk_management']:
            regime_multipliers = config_dict['risk_management']['regime_risk_multipliers']
            if regime_multipliers:
                # Convert enum keys to string values
                string_multipliers = {}
                for regime, multiplier in regime_multipliers.items():
                    if hasattr(regime, 'value'):
                        string_multipliers[regime.value] = multiplier
                    else:
                        string_multipliers[str(regime)] = multiplier
                config_dict['risk_management']['regime_risk_multipliers'] = string_multipliers
        
        return config_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdaptiveBotConfig':
        """Create configuration from dictionary."""
        # Handle datetime fields
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'last_modified' in data and isinstance(data['last_modified'], str):
            data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        
        # Handle risk management regime multipliers
        if 'risk_management' in data and 'regime_risk_multipliers' in data['risk_management']:
            regime_multipliers = data['risk_management']['regime_risk_multipliers']
            if regime_multipliers and isinstance(list(regime_multipliers.keys())[0], str):
                # Convert string keys back to RegimeType enums
                enum_multipliers = {}
                for regime_str, multiplier in regime_multipliers.items():
                    try:
                        regime_enum = RegimeType(regime_str)
                        enum_multipliers[regime_enum] = multiplier
                    except ValueError:
                        # Skip invalid regime types
                        continue
                data['risk_management']['regime_risk_multipliers'] = enum_multipliers
        
        # Create component configurations
        if 'ml_engine' in data:
            data['ml_engine'] = MLEngineConfig(**data['ml_engine'])
        if 'regime_detection' in data:
            data['regime_detection'] = RegimeDetectionConfig(**data['regime_detection'])
        if 'parameter_optimization' in data:
            data['parameter_optimization'] = ParameterOptimizationConfig(**data['parameter_optimization'])
        if 'adaptation_control' in data:
            data['adaptation_control'] = AdaptationControlConfig(**data['adaptation_control'])
        if 'strategy' in data:
            data['strategy'] = StrategyConfig(**data['strategy'])
        if 'risk_management' in data:
            data['risk_management'] = RiskManagementConfig(**data['risk_management'])
        if 'monitoring' in data:
            data['monitoring'] = MonitoringConfig(**data['monitoring'])
        
        return cls(**data)


class AdaptiveConfigManager:
    """Manager for adaptive bot configuration with runtime updates and validation."""
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory to store configuration files
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.config_file = self.config_dir / "adaptive_bot_config.json"
        self.backup_dir = self.config_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        self._config: Optional[AdaptiveBotConfig] = None
        self._config_lock = threading.RLock()
        self._change_callbacks: List[callable] = []
        
        logger.info(f"Initialized AdaptiveConfigManager with config dir: {self.config_dir}")
    
    def load_config(self, config_path: Optional[str] = None) -> bool:
        """
        Load configuration from file.
        
        Args:
            config_path: Optional path to config file, uses default if None
            
        Returns:
            bool: True if loading was successful
        """
        config_path = Path(config_path) if config_path else self.config_file
        
        try:
            with self._config_lock:
                if not config_path.exists():
                    logger.info("Config file not found, creating default configuration")
                    self._config = AdaptiveBotConfig()
                    self.save_config()
                    return True
                
                with open(config_path, 'r') as f:
                    data = json.load(f)
                
                self._config = AdaptiveBotConfig.from_dict(data)
                
                if not self._config.validate():
                    logger.error("Loaded configuration is invalid")
                    return False
                
                logger.info(f"Successfully loaded configuration from {config_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return False
    
    def save_config(self, config_path: Optional[str] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config_path: Optional path to save config file, uses default if None
            
        Returns:
            bool: True if saving was successful
        """
        if self._config is None:
            logger.error("No configuration to save")
            return False
        
        config_path = Path(config_path) if config_path else self.config_file
        
        try:
            with self._config_lock:
                # Update last modified timestamp
                self._config.last_modified = datetime.now()
                
                # Create backup before saving
                if config_path.exists():
                    self._create_backup()
                
                # Save configuration
                config_dict = self._config.to_dict()
                
                # Convert datetime objects to ISO format strings
                if 'created_at' in config_dict:
                    config_dict['created_at'] = config_dict['created_at'].isoformat()
                if 'last_modified' in config_dict:
                    config_dict['last_modified'] = config_dict['last_modified'].isoformat()
                
                with open(config_path, 'w') as f:
                    json.dump(config_dict, f, indent=2, default=str)
                
                logger.info(f"Successfully saved configuration to {config_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def get_config(self) -> Optional[AdaptiveBotConfig]:
        """Get the current configuration."""
        with self._config_lock:
            return self._config
    
    def update_config(self, updates: Dict[str, Any], validate: bool = True) -> bool:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
            validate: Whether to validate the configuration after updates
            
        Returns:
            bool: True if update was successful
        """
        if self._config is None:
            logger.error("No configuration loaded")
            return False
        
        try:
            with self._config_lock:
                # Create a copy for validation
                config_dict = self._config.to_dict()
                
                # Apply updates recursively
                self._apply_updates(config_dict, updates)
                
                # Create new configuration from updated dictionary
                new_config = AdaptiveBotConfig.from_dict(config_dict)
                
                # Validate if requested
                if validate and not new_config.validate():
                    logger.error("Configuration updates would result in invalid configuration")
                    return False
                
                # Apply the updates
                self._config = new_config
                
                # Save the updated configuration
                if not self.save_config():
                    logger.error("Failed to save updated configuration")
                    return False
                
                # Notify callbacks
                self._notify_change_callbacks(updates)
                
                logger.info("Successfully updated configuration")
                return True
                
        except Exception as e:
            logger.error(f"Error updating configuration: {str(e)}")
            return False
    
    def _apply_updates(self, config_dict: Dict[str, Any], updates: Dict[str, Any]):
        """Recursively apply updates to configuration dictionary."""
        for key, value in updates.items():
            if isinstance(value, dict) and key in config_dict and isinstance(config_dict[key], dict):
                self._apply_updates(config_dict[key], value)
            else:
                config_dict[key] = value
    
    def _create_backup(self) -> bool:
        """Create a backup of the current configuration."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"adaptive_bot_config_{timestamp}.json"
            
            shutil.copy2(self.config_file, backup_file)
            
            # Clean up old backups (keep last 10)
            backups = sorted(self.backup_dir.glob("adaptive_bot_config_*.json"))
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    old_backup.unlink()
            
            logger.debug(f"Created configuration backup: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating configuration backup: {str(e)}")
            return False
    
    def restore_backup(self, backup_timestamp: str) -> bool:
        """
        Restore configuration from a backup.
        
        Args:
            backup_timestamp: Timestamp of the backup to restore (YYYYMMDD_HHMMSS)
            
        Returns:
            bool: True if restore was successful
        """
        backup_file = self.backup_dir / f"adaptive_bot_config_{backup_timestamp}.json"
        
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False
        
        try:
            # Load configuration from backup
            if self.load_config(str(backup_file)):
                # Save as current configuration
                return self.save_config()
            return False
            
        except Exception as e:
            logger.error(f"Error restoring backup: {str(e)}")
            return False
    
    def list_backups(self) -> List[str]:
        """List available configuration backups."""
        try:
            backups = sorted(self.backup_dir.glob("adaptive_bot_config_*.json"))
            return [backup.stem.replace("adaptive_bot_config_", "") for backup in backups]
        except Exception as e:
            logger.error(f"Error listing backups: {str(e)}")
            return []
    
    def add_change_callback(self, callback: callable):
        """Add a callback to be notified of configuration changes."""
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: callable):
        """Remove a configuration change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def _notify_change_callbacks(self, changes: Dict[str, Any]):
        """Notify all registered callbacks of configuration changes."""
        for callback in self._change_callbacks:
            try:
                callback(changes)
            except Exception as e:
                logger.error(f"Error in configuration change callback: {str(e)}")
    
    def validate_current_config(self) -> bool:
        """Validate the current configuration."""
        if self._config is None:
            return False
        return self._config.validate()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration."""
        if self._config is None:
            return {}
        
        return {
            "version": self._config.version,
            "enabled": self._config.enabled,
            "trading_pairs": self._config.trading_pairs,
            "created_at": self._config.created_at.isoformat(),
            "last_modified": self._config.last_modified.isoformat(),
            "components": {
                "ml_engine_enabled": self._config.ml_engine.ensemble_enabled,
                "regime_detection_enabled": self._config.regime_detection.enabled,
                "parameter_optimization_enabled": self._config.parameter_optimization.enabled,
                "adaptation_control_enabled": self._config.adaptation_control.auto_rollback_enabled,
                "monitoring_enabled": self._config.monitoring.performance_monitoring_enabled
            }
        }