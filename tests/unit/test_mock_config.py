"""
Unit tests for mock trading configuration.
"""
import unittest
import tempfile
import os
import json
from pathlib import Path

from mock_trading.mock_config import (
    MockTradingConfig, 
    ExecutionConfig, 
    MarketConfig, 
    FeeConfig,
    load_mock_config,
    create_default_config_file
)
from mock_trading.config_validator import ConfigValidator, validate_config_with_logging


class TestMockTradingConfig(unittest.TestCase):
    """Test cases for MockTradingConfig class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        os.rmdir(self.temp_dir)
    
    def test_default_config_creation(self):
        """Test creating default configuration."""
        config = MockTradingConfig()
        
        # Check default values
        self.assertEqual(config.starting_capital, 10000.0)
        self.assertEqual(config.max_position_size, 5000.0)
        self.assertEqual(config.max_daily_loss, 1000.0)
        self.assertTrue(config.simulation_mode)
        
        # Check nested configurations are created
        self.assertIsInstance(config.execution, ExecutionConfig)
        self.assertIsInstance(config.market, MarketConfig)
        self.assertIsInstance(config.fees, FeeConfig)
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        config = MockTradingConfig()
        self.assertTrue(config.validate_config())
    
    def test_config_validation_failure(self):
        """Test configuration validation with invalid values."""
        config = MockTradingConfig(
            starting_capital=-1000.0,  # Invalid: negative
            max_position_size=0,       # Invalid: zero
        )
        self.assertFalse(config.validate_config())
    
    def test_safe_defaults_application(self):
        """Test application of safe defaults."""
        config = MockTradingConfig(
            starting_capital=-1000.0,  # Will be corrected
            max_position_size=50000.0,  # Will be limited
        )
        
        safe_config = config.apply_safe_defaults()
        
        # Check corrections were applied
        self.assertGreaterEqual(safe_config.starting_capital, 1000.0)
        self.assertLessEqual(safe_config.max_position_size, safe_config.starting_capital * 0.5)
    
    def test_config_to_dict_conversion(self):
        """Test converting configuration to dictionary."""
        config = MockTradingConfig()
        config_dict = config.to_dict()
        
        self.assertIsInstance(config_dict, dict)
        self.assertIn('starting_capital', config_dict)
        self.assertIn('execution', config_dict)
        self.assertIn('market', config_dict)
        self.assertIn('fees', config_dict)
    
    def test_config_from_dict_creation(self):
        """Test creating configuration from dictionary."""
        config_dict = {
            'starting_capital': 5000.0,
            'max_position_size': 2000.0,
            'execution': {
                'slippage_base': 0.0002
            },
            'market': {
                'volatility_multiplier': 1.5
            },
            'fees': {
                'trading_fee_percent': 0.002
            }
        }
        
        config = MockTradingConfig.from_dict(config_dict)
        
        self.assertEqual(config.starting_capital, 5000.0)
        self.assertEqual(config.max_position_size, 2000.0)
        self.assertEqual(config.execution.slippage_base, 0.0002)
        self.assertEqual(config.market.volatility_multiplier, 1.5)
        self.assertEqual(config.fees.trading_fee_percent, 0.002)
    
    def test_config_file_save_and_load(self):
        """Test saving and loading configuration from file."""
        config = MockTradingConfig(starting_capital=7500.0)
        
        # Save configuration
        self.assertTrue(config.save_to_file(self.config_path))
        self.assertTrue(os.path.exists(self.config_path))
        
        # Load configuration
        loaded_config = MockTradingConfig.from_file(self.config_path)
        self.assertEqual(loaded_config.starting_capital, 7500.0)
    
    def test_config_file_load_nonexistent(self):
        """Test loading configuration from non-existent file."""
        with self.assertRaises(ValueError):
            MockTradingConfig.from_file("nonexistent.json")
    
    def test_config_file_load_invalid_json(self):
        """Test loading configuration from invalid JSON file."""
        # Create invalid JSON file
        with open(self.config_path, 'w') as f:
            f.write("{ invalid json }")
        
        with self.assertRaises(ValueError):
            MockTradingConfig.from_file(self.config_path)
    
    def test_load_mock_config_with_file(self):
        """Test load_mock_config function with existing file."""
        config = MockTradingConfig(starting_capital=8000.0)
        config.save_to_file(self.config_path)
        
        loaded_config = load_mock_config(self.config_path)
        self.assertEqual(loaded_config.starting_capital, 8000.0)
    
    def test_load_mock_config_without_file(self):
        """Test load_mock_config function without file (defaults)."""
        config = load_mock_config()
        self.assertEqual(config.starting_capital, 10000.0)
        self.assertTrue(config.validate_config())
    
    def test_create_default_config_file(self):
        """Test creating default configuration file."""
        self.assertTrue(create_default_config_file(self.config_path))
        self.assertTrue(os.path.exists(self.config_path))
        
        # Verify file contains valid JSON
        with open(self.config_path, 'r') as f:
            config_data = json.load(f)
        
        self.assertIn('starting_capital', config_data)
        self.assertEqual(config_data['starting_capital'], 10000.0)


class TestConfigValidator(unittest.TestCase):
    """Test cases for ConfigValidator class."""
    
    def test_validate_capital_settings_success(self):
        """Test successful capital settings validation."""
        config = MockTradingConfig()
        result = ConfigValidator.validate_capital_settings(config)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_validate_capital_settings_failure(self):
        """Test capital settings validation with errors."""
        config = MockTradingConfig(
            starting_capital=-1000.0,
            max_position_size=0
        )
        result = ConfigValidator.validate_capital_settings(config)
        
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
    
    def test_validate_execution_settings_success(self):
        """Test successful execution settings validation."""
        execution = ExecutionConfig()
        result = ConfigValidator.validate_execution_settings(execution)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_validate_execution_settings_failure(self):
        """Test execution settings validation with errors."""
        execution = ExecutionConfig(
            slippage_base=-0.1,  # Invalid: negative
            execution_delay_max_ms=50,  # Invalid: less than min
            execution_delay_min_ms=100
        )
        result = ConfigValidator.validate_execution_settings(execution)
        
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
    
    def test_validate_market_settings_success(self):
        """Test successful market settings validation."""
        market = MarketConfig()
        result = ConfigValidator.validate_market_settings(market)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_validate_fee_settings_success(self):
        """Test successful fee settings validation."""
        fees = FeeConfig()
        result = ConfigValidator.validate_fee_settings(fees)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_validate_full_config_success(self):
        """Test successful full configuration validation."""
        config = MockTradingConfig()
        result = ConfigValidator.validate_full_config(config)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_validate_config_with_logging(self):
        """Test configuration validation with logging."""
        config = MockTradingConfig()
        self.assertTrue(validate_config_with_logging(config))
        
        # Test with invalid config
        invalid_config = MockTradingConfig(starting_capital=-1000.0)
        self.assertFalse(validate_config_with_logging(invalid_config))


if __name__ == '__main__':
    unittest.main()