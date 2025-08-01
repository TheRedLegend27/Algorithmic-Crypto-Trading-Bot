"""
Unit tests for the adaptive bot configuration system.
"""
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from bot.adaptive.adaptive_config import (
    MLEngineConfig, RegimeDetectionConfig, ParameterOptimizationConfig,
    AdaptationControlConfig, StrategyConfig, RiskManagementConfig,
    MonitoringConfig, AdaptiveBotConfig, AdaptiveConfigManager
)
from bot.adaptive.enums import RegimeType, OptimizationMethod, ModelType


class TestMLEngineConfig:
    """Test MLEngineConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default ML engine config is valid."""
        config = MLEngineConfig()
        assert config.validate()
    
    def test_empty_models_invalid(self):
        """Test that empty enabled models list is invalid."""
        config = MLEngineConfig(enabled_models=[])
        assert not config.validate()
    
    def test_invalid_validation_split(self):
        """Test that invalid validation split is caught."""
        config = MLEngineConfig(validation_split=1.5)
        assert not config.validate()
        
        config = MLEngineConfig(validation_split=-0.1)
        assert not config.validate()
    
    def test_invalid_confidence_threshold(self):
        """Test that invalid confidence threshold is caught."""
        config = MLEngineConfig(min_model_confidence=1.5)
        assert not config.validate()
        
        config = MLEngineConfig(min_model_confidence=-0.1)
        assert not config.validate()
    
    def test_invalid_training_parameters(self):
        """Test that invalid training parameters are caught."""
        config = MLEngineConfig(training_window_days=0)
        assert not config.validate()
        
        config = MLEngineConfig(min_training_samples=0)
        assert not config.validate()


class TestRegimeDetectionConfig:
    """Test RegimeDetectionConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default regime detection config is valid."""
        config = RegimeDetectionConfig()
        assert config.validate()
    
    def test_invalid_confidence_threshold(self):
        """Test that invalid confidence threshold is caught."""
        config = RegimeDetectionConfig(confidence_threshold=1.5)
        assert not config.validate()
        
        config = RegimeDetectionConfig(confidence_threshold=-0.1)
        assert not config.validate()
    
    def test_invalid_timeframes(self):
        """Test that invalid timeframes are caught."""
        config = RegimeDetectionConfig(timeframes=[])
        assert not config.validate()
        
        config = RegimeDetectionConfig(
            timeframes=["1h", "4h"],
            primary_timeframe="5m"  # Not in timeframes list
        )
        assert not config.validate()
    
    def test_invalid_lookback_periods(self):
        """Test that invalid lookback periods are caught."""
        config = RegimeDetectionConfig(volatility_lookback=0)
        assert not config.validate()
        
        config = RegimeDetectionConfig(trend_lookback=-1)
        assert not config.validate()


class TestParameterOptimizationConfig:
    """Test ParameterOptimizationConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default parameter optimization config is valid."""
        config = ParameterOptimizationConfig()
        assert config.validate()
    
    def test_empty_optimization_methods_invalid(self):
        """Test that empty optimization methods list is invalid."""
        config = ParameterOptimizationConfig(optimization_methods=[])
        assert not config.validate()
    
    def test_invalid_out_of_sample_ratio(self):
        """Test that invalid out-of-sample ratio is caught."""
        config = ParameterOptimizationConfig(out_of_sample_ratio=1.5)
        assert not config.validate()
        
        config = ParameterOptimizationConfig(out_of_sample_ratio=-0.1)
        assert not config.validate()
    
    def test_invalid_parameter_change_pct(self):
        """Test that invalid parameter change percentage is caught."""
        config = ParameterOptimizationConfig(max_parameter_change_pct=1.5)
        assert not config.validate()
        
        config = ParameterOptimizationConfig(max_parameter_change_pct=-0.1)
        assert not config.validate()


class TestAdaptationControlConfig:
    """Test AdaptationControlConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default adaptation control config is valid."""
        config = AdaptationControlConfig()
        assert config.validate()
    
    def test_invalid_adaptation_limits(self):
        """Test that invalid adaptation limits are caught."""
        config = AdaptationControlConfig(max_adaptations_per_hour=0)
        assert not config.validate()
        
        config = AdaptationControlConfig(max_adaptations_per_day=-1)
        assert not config.validate()
    
    def test_invalid_thresholds(self):
        """Test that invalid thresholds are caught."""
        config = AdaptationControlConfig(min_performance_threshold=1.5)
        assert not config.validate()
        
        config = AdaptationControlConfig(adaptation_confidence_threshold=-0.1)
        assert not config.validate()
    
    def test_invalid_ab_test_allocation(self):
        """Test that invalid A/B test allocation is caught."""
        config = AdaptationControlConfig(ab_test_allocation_pct=1.5)
        assert not config.validate()
        
        config = AdaptationControlConfig(ab_test_allocation_pct=-0.1)
        assert not config.validate()


class TestStrategyConfig:
    """Test StrategyConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default strategy config is valid."""
        config = StrategyConfig()
        assert config.validate()
    
    def test_empty_strategies_invalid(self):
        """Test that empty enabled strategies list is invalid."""
        config = StrategyConfig(enabled_strategies=[])
        assert not config.validate()
    
    def test_invalid_strategy_weights(self):
        """Test that invalid strategy weights are caught."""
        config = StrategyConfig(min_strategy_weight=0.8, max_strategy_weight=0.6)
        assert not config.validate()
        
        config = StrategyConfig(min_strategy_weight=-0.1)
        assert not config.validate()
        
        config = StrategyConfig(max_strategy_weight=1.5)
        assert not config.validate()
    
    def test_invalid_voting_method(self):
        """Test that invalid voting method is caught."""
        config = StrategyConfig(ensemble_voting_method="invalid")
        assert not config.validate()


class TestRiskManagementConfig:
    """Test RiskManagementConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default risk management config is valid."""
        config = RiskManagementConfig()
        assert config.validate()
    
    def test_invalid_position_sizes(self):
        """Test that invalid position sizes are caught."""
        config = RiskManagementConfig(base_position_size_usd=0)
        assert not config.validate()
        
        config = RiskManagementConfig(max_position_size_usd=-100)
        assert not config.validate()
        
        config = RiskManagementConfig(
            base_position_size_usd=1000,
            max_position_size_usd=500
        )
        assert not config.validate()
    
    def test_invalid_volatility_reduction(self):
        """Test that invalid volatility reduction is caught."""
        config = RiskManagementConfig(max_volatility_reduction=1.5)
        assert not config.validate()
        
        config = RiskManagementConfig(max_volatility_reduction=-0.1)
        assert not config.validate()
    
    def test_invalid_regime_multipliers(self):
        """Test that invalid regime multipliers are caught."""
        config = RiskManagementConfig(
            regime_risk_multipliers={RegimeType.TRENDING_BULL: -0.5}
        )
        assert not config.validate()
        
        config = RiskManagementConfig(
            regime_risk_multipliers={RegimeType.TRENDING_BULL: 2.5}
        )
        assert not config.validate()


class TestMonitoringConfig:
    """Test MonitoringConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default monitoring config is valid."""
        config = MonitoringConfig()
        assert config.validate()
    
    def test_invalid_frequencies(self):
        """Test that invalid frequencies are caught."""
        config = MonitoringConfig(performance_check_frequency_minutes=0)
        assert not config.validate()
        
        config = MonitoringConfig(health_check_frequency_minutes=-1)
        assert not config.validate()
    
    def test_invalid_alert_threshold(self):
        """Test that invalid alert threshold is caught."""
        config = MonitoringConfig(performance_alert_threshold_pct=1.5)
        assert not config.validate()
        
        config = MonitoringConfig(performance_alert_threshold_pct=-0.1)
        assert not config.validate()
    
    def test_empty_alert_channels_invalid(self):
        """Test that empty alert channels list is invalid."""
        config = MonitoringConfig(alert_channels=[])
        assert not config.validate()


class TestAdaptiveBotConfig:
    """Test AdaptiveBotConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default adaptive bot config is valid."""
        config = AdaptiveBotConfig()
        assert config.validate()
    
    def test_empty_trading_pairs_invalid(self):
        """Test that empty trading pairs list is invalid."""
        config = AdaptiveBotConfig(trading_pairs=[])
        assert not config.validate()
    
    def test_invalid_system_settings(self):
        """Test that invalid system settings are caught."""
        config = AdaptiveBotConfig(data_retention_days=0)
        assert not config.validate()
        
        config = AdaptiveBotConfig(backup_frequency_hours=-1)
        assert not config.validate()
    
    def test_invalid_log_level(self):
        """Test that invalid log level is caught."""
        config = AdaptiveBotConfig(log_level="INVALID")
        assert not config.validate()
    
    def test_to_dict_conversion(self):
        """Test conversion to dictionary."""
        config = AdaptiveBotConfig()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert "ml_engine" in config_dict
        assert "regime_detection" in config_dict
        assert "trading_pairs" in config_dict
        assert config_dict["enabled"] == config.enabled
    
    def test_from_dict_conversion(self):
        """Test creation from dictionary."""
        config = AdaptiveBotConfig()
        config_dict = config.to_dict()
        
        # Convert datetime objects to strings for JSON serialization
        config_dict["created_at"] = config_dict["created_at"].isoformat()
        config_dict["last_modified"] = config_dict["last_modified"].isoformat()
        
        new_config = AdaptiveBotConfig.from_dict(config_dict)
        
        assert new_config.enabled == config.enabled
        assert new_config.trading_pairs == config.trading_pairs
        assert new_config.validate()


class TestAdaptiveConfigManager:
    """Test AdaptiveConfigManager functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = AdaptiveConfigManager(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test config manager initialization."""
        assert self.config_manager.config_dir.exists()
        assert self.config_manager.backup_dir.exists()
    
    def test_load_default_config(self):
        """Test loading default configuration when no file exists."""
        assert self.config_manager.load_config()
        config = self.config_manager.get_config()
        assert config is not None
        assert config.validate()
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        # Load default config
        assert self.config_manager.load_config()
        
        # Modify config
        original_config = self.config_manager.get_config()
        original_config.trading_pairs = ["BTCUSD", "ETHUSD", "ADAUSD"]
        
        # Save config
        assert self.config_manager.save_config()
        
        # Create new manager and load config
        new_manager = AdaptiveConfigManager(self.temp_dir)
        assert new_manager.load_config()
        
        loaded_config = new_manager.get_config()
        assert loaded_config.trading_pairs == ["BTCUSD", "ETHUSD", "ADAUSD"]
    
    def test_update_config(self):
        """Test updating configuration."""
        assert self.config_manager.load_config()
        
        updates = {
            "trading_pairs": ["BTCUSD"],
            "ml_engine": {
                "training_window_days": 60
            }
        }
        
        assert self.config_manager.update_config(updates)
        
        config = self.config_manager.get_config()
        assert config.trading_pairs == ["BTCUSD"]
        assert config.ml_engine.training_window_days == 60
    
    def test_invalid_update_rejected(self):
        """Test that invalid updates are rejected."""
        assert self.config_manager.load_config()
        
        # Invalid update (empty trading pairs)
        updates = {
            "trading_pairs": []
        }
        
        assert not self.config_manager.update_config(updates)
        
        # Config should remain unchanged
        config = self.config_manager.get_config()
        assert len(config.trading_pairs) > 0
    
    def test_backup_creation(self):
        """Test that backups are created when saving."""
        assert self.config_manager.load_config()
        
        # Save config to create initial file
        assert self.config_manager.save_config()
        
        # Modify and save again to trigger backup
        updates = {"trading_pairs": ["BTCUSD"]}
        assert self.config_manager.update_config(updates)
        
        # Check that backup was created
        backups = self.config_manager.list_backups()
        assert len(backups) > 0
    
    def test_backup_restore(self):
        """Test restoring from backup."""
        assert self.config_manager.load_config()
        
        # Save initial config
        assert self.config_manager.save_config()
        
        # Modify config
        updates = {"trading_pairs": ["BTCUSD"]}
        assert self.config_manager.update_config(updates)
        
        # Get backup timestamp
        backups = self.config_manager.list_backups()
        assert len(backups) > 0
        
        # Modify config again
        updates = {"trading_pairs": ["ETHUSD"]}
        assert self.config_manager.update_config(updates)
        
        # Restore from backup
        backup_timestamp = backups[0]
        assert self.config_manager.restore_backup(backup_timestamp)
        
        # Check that config was restored
        config = self.config_manager.get_config()
        assert "BTCUSD" in config.trading_pairs or len(config.trading_pairs) == 2
    
    def test_change_callbacks(self):
        """Test configuration change callbacks."""
        assert self.config_manager.load_config()
        
        callback_called = False
        callback_data = None
        
        def test_callback(changes):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = changes
        
        self.config_manager.add_change_callback(test_callback)
        
        # Update config
        updates = {"trading_pairs": ["BTCUSD"]}
        assert self.config_manager.update_config(updates)
        
        assert callback_called
        assert callback_data == updates
        
        # Remove callback
        self.config_manager.remove_change_callback(test_callback)
        
        callback_called = False
        updates = {"trading_pairs": ["ETHUSD"]}
        assert self.config_manager.update_config(updates)
        
        assert not callback_called
    
    def test_config_summary(self):
        """Test getting configuration summary."""
        assert self.config_manager.load_config()
        
        summary = self.config_manager.get_config_summary()
        
        assert "version" in summary
        assert "enabled" in summary
        assert "trading_pairs" in summary
        assert "components" in summary
        assert "created_at" in summary
        assert "last_modified" in summary
    
    def test_validate_current_config(self):
        """Test validating current configuration."""
        assert self.config_manager.load_config()
        assert self.config_manager.validate_current_config()
        
        # Corrupt the config
        config = self.config_manager.get_config()
        config.trading_pairs = []  # Invalid
        
        assert not self.config_manager.validate_current_config()
    
    @patch('json.load')
    def test_load_config_error_handling(self, mock_json_load):
        """Test error handling during config loading."""
        mock_json_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        # Create a dummy config file
        config_file = Path(self.temp_dir) / "adaptive_bot_config.json"
        config_file.write_text("invalid json")
        
        assert not self.config_manager.load_config()
    
    @patch('builtins.open')
    def test_save_config_error_handling(self, mock_open):
        """Test error handling during config saving."""
        assert self.config_manager.load_config()
        
        mock_open.side_effect = IOError("Cannot write file")
        
        assert not self.config_manager.save_config()


if __name__ == "__main__":
    pytest.main([__file__])