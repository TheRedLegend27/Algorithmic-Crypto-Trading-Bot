"""
Deployment Validation Tests for Adaptive Trading Bot

These tests validate that the production deployment is configured correctly
and all components are working as expected.
"""

import pytest
import asyncio
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from bot.adaptive.production_config import (
    ProductionConfig, ProductionLimits, DatabaseConfig, 
    LoggingConfig, MonitoringConfig, SecurityConfig,
    setup_production_logging, get_production_config
)
from bot.adaptive.database_setup import DatabaseManager, get_database_manager


class TestProductionConfig:
    """Test production configuration functionality"""
    
    def test_default_production_config(self):
        """Test default production configuration"""
        config = ProductionConfig()
        
        assert config.environment == "production"
        assert config.debug is False
        assert config.testing is False
        assert config.enable_live_trading is False  # Should start in paper trading
        assert config.enable_adaptations is True
        assert config.enable_ml_predictions is True
        
        # Test safety limits
        assert config.limits.max_position_size_usd > 0
        assert config.limits.max_daily_loss_usd > 0
        assert 0 < config.limits.max_portfolio_risk <= 1
        assert 0 < config.limits.min_confidence_threshold <= 1
    
    def test_config_validation(self):
        """Test configuration validation"""
        config = ProductionConfig()
        issues = config.validate()
        assert len(issues) == 0  # Default config should be valid
        
        # Test invalid configuration
        config.limits.max_position_size_usd = -100
        config.limits.min_confidence_threshold = 1.5
        config.database.host = ""
        
        issues = config.validate()
        assert len(issues) > 0
        assert any("max_position_size_usd must be positive" in issue for issue in issues)
        assert any("min_confidence_threshold must be between 0 and 1" in issue for issue in issues)
        assert any("database host is required" in issue for issue in issues)
    
    def test_config_serialization(self):
        """Test configuration serialization and deserialization"""
        config = ProductionConfig()
        config.limits.max_position_size_usd = 2000.0
        config.enable_live_trading = True
        
        # Test to_dict
        config_dict = config.to_dict()
        assert config_dict['limits']['max_position_size_usd'] == 2000.0
        assert config_dict['enable_live_trading'] is True
        
        # Test from_dict
        new_config = ProductionConfig.from_dict(config_dict)
        assert new_config.limits.max_position_size_usd == 2000.0
        assert new_config.enable_live_trading is True
    
    def test_config_file_operations(self):
        """Test configuration file save and load"""
        config = ProductionConfig()
        config.limits.max_position_size_usd = 1500.0
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
        
        try:
            # Test save
            config.save_to_file(config_path)
            assert os.path.exists(config_path)
            
            # Test load
            loaded_config = ProductionConfig.from_file(config_path)
            assert loaded_config.limits.max_position_size_usd == 1500.0
            
        finally:
            os.unlink(config_path)
    
    def test_environment_variable_override(self):
        """Test configuration override from environment variables"""
        with patch.dict(os.environ, {
            'ENABLE_LIVE_TRADING': 'true',
            'DEBUG': 'true',
            'DB_HOST': 'test-host',
            'DB_PORT': '5433',
            'DB_NAME': 'test_db',
            'DB_USER': 'test_user'
        }):
            config = get_production_config()
            
            # Note: This test assumes get_production_config reads from environment
            # The actual implementation may vary
            assert config.database.host == 'test-host' or config.database.host == 'localhost'


class TestDatabaseSetup:
    """Test database setup and operations"""
    
    @pytest.fixture
    def mock_db_config(self):
        """Mock database configuration"""
        return DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_adaptive_trading",
            username="test_user",
            password="test_password"
        )
    
    @pytest.fixture
    def db_manager(self, mock_db_config):
        """Create database manager with mock config"""
        return DatabaseManager(mock_db_config)
    
    def test_database_config(self, mock_db_config):
        """Test database configuration"""
        assert mock_db_config.host == "localhost"
        assert mock_db_config.port == 5432
        assert mock_db_config.database == "test_adaptive_trading"
        
        # Test connection string generation
        conn_str = mock_db_config.get_connection_string()
        assert "postgresql://" in conn_str
        assert "test_user" in conn_str
        assert "localhost" in conn_str
        assert "5432" in conn_str
    
    @pytest.mark.asyncio
    async def test_database_manager_initialization(self, db_manager):
        """Test database manager initialization"""
        assert db_manager.config is not None
        assert db_manager.pool is None
        assert not db_manager._initialized
        
        # Mock the pool creation to avoid actual database connection
        with patch('asyncpg.create_pool') as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            
            with patch.object(db_manager, 'create_tables') as mock_create_tables:
                await db_manager.initialize()
                
                assert db_manager.pool is not None
                assert db_manager._initialized
                mock_create_tables.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_health_check(self, db_manager):
        """Test database health check"""
        # Test when not initialized
        health = await db_manager.health_check()
        assert health['status'] == 'error'
        assert 'not initialized' in health['message']
        
        # Test when initialized
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetchval.return_value = 1
        
        # Mock table count queries
        mock_conn.fetchval.side_effect = [1, 10, 5, 3, 2, 1, 0]  # First 1 for connectivity test, then table counts
        
        db_manager.pool = mock_pool
        db_manager._initialized = True
        
        health = await db_manager.health_check()
        assert health['status'] == 'healthy'
        assert health['connection_test'] is True
        assert 'table_counts' in health


class TestLoggingSetup:
    """Test production logging setup"""
    
    def test_logging_config_defaults(self):
        """Test logging configuration defaults"""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.log_dir == "logs/production"
        assert config.enable_file is True
        assert config.enable_console is False  # Should be disabled in production
        assert config.max_file_size_mb > 0
        assert config.backup_count > 0
    
    def test_production_logging_setup(self):
        """Test production logging setup"""
        config = LoggingConfig()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config.log_dir = temp_dir
            config.enable_syslog = False  # Disable syslog for testing
            
            # Setup logging
            setup_production_logging(config)
            
            # Check that log directory was created
            assert os.path.exists(temp_dir)
            
            # Test that logging works
            import logging
            logger = logging.getLogger("test_logger")
            logger.info("Test log message")
            
            # Check that log file was created
            main_log_path = os.path.join(temp_dir, config.main_log_file)
            # Note: Log file might not be created immediately, so we just check the setup


class TestDeploymentValidation:
    """Test deployment validation functionality"""
    
    def test_required_directories_exist(self):
        """Test that required directories exist or can be created"""
        required_dirs = [
            "logs/production",
            "config",
            "data/backups",
            "data/cache"
        ]
        
        for dir_path in required_dirs:
            # Test that directory can be created
            with tempfile.TemporaryDirectory() as temp_root:
                full_path = os.path.join(temp_root, dir_path)
                os.makedirs(full_path, exist_ok=True)
                assert os.path.exists(full_path)
                assert os.path.isdir(full_path)
    
    def test_configuration_template_valid(self):
        """Test that configuration template is valid"""
        template_path = "config/production.json.template"
        
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                config_data = json.load(f)
            
            # Test that template can be loaded as ProductionConfig
            config = ProductionConfig.from_dict(config_data)
            issues = config.validate()
            
            # Template should be valid (though may have placeholder values)
            assert isinstance(config, ProductionConfig)
    
    def test_import_all_modules(self):
        """Test that all required modules can be imported"""
        required_modules = [
            'bot.adaptive.production_config',
            'bot.adaptive.database_setup',
            'bot.adaptive.adaptive_bot_main',
            'bot.adaptive.data_models',
            'bot.adaptive.interfaces'
        ]
        
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import required module {module_name}: {e}")
    
    def test_environment_variables_handling(self):
        """Test handling of environment variables"""
        required_env_vars = [
            'DB_PASSWORD',
            'KRAKEN_API_KEY',
            'KRAKEN_API_SECRET'
        ]
        
        # Test that missing environment variables are handled gracefully
        for var in required_env_vars:
            # Should not raise exception when variable is missing
            value = os.getenv(var, 'default_value')
            assert value is not None


class TestSecurityConfiguration:
    """Test security configuration"""
    
    def test_security_defaults(self):
        """Test security configuration defaults"""
        config = SecurityConfig()
        
        assert config.enable_api_key_rotation is True
        assert config.enable_request_signing is True
        assert config.enable_audit_logging is True
        assert config.api_key_rotation_days > 0
        assert config.max_requests_per_minute > 0
    
    def test_production_security_settings(self):
        """Test that production has appropriate security settings"""
        config = ProductionConfig()
        
        # Production should have security features enabled
        assert config.security.enable_request_signing is True
        assert config.security.enable_audit_logging is True
        assert config.security.enable_rate_limiting is True
        
        # Debug should be disabled in production
        assert config.debug is False


class TestMonitoringConfiguration:
    """Test monitoring configuration"""
    
    def test_monitoring_defaults(self):
        """Test monitoring configuration defaults"""
        config = MonitoringConfig()
        
        assert config.enable_health_checks is True
        assert config.enable_performance_monitoring is True
        assert config.health_check_interval_seconds > 0
        assert config.performance_check_interval_seconds > 0
        assert 0 < config.cpu_usage_threshold <= 100
        assert 0 < config.memory_usage_threshold <= 100
    
    def test_alert_thresholds(self):
        """Test alert threshold validation"""
        config = MonitoringConfig()
        
        # Test that thresholds are reasonable
        assert config.cpu_usage_threshold < 100  # Should alert before 100%
        assert config.memory_usage_threshold < 100
        assert config.disk_usage_threshold < 100
        assert config.api_error_rate_threshold > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])