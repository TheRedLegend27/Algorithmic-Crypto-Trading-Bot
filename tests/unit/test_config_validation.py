"""
Tests for configuration validation with various .env file scenarios.
"""
import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import tempfile
import shutil

from bot.config import Config, KrakenCredentials, TradingSettings


class TestConfigValidation(unittest.TestCase):
    """Test cases for configuration validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Reset Config singleton for each test
        Config._instance = None
        
        # Create a new Config instance
        self.config = Config()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_valid_env_file(self):
        """Test loading a valid .env file."""
        # Create a valid .env file content
        env_content = """
        ALPACA_API_KEY=valid_api_key
        ALPACA_SECRET_KEY=valid_secret_key
        ALPACA_BASE_URL=https://paper-api.alpaca.markets
        IS_PAPER_TRADING=True
        """
        
        # Mock os.getenv to return values from our env_content
        def mock_getenv(key, default=None):
            if key == "KRAKEN_API_KEY":
                return "valid_api_key"
            elif key == "KRAKEN_API_SECRET":
                return "valid_secret_key"
            elif key == "KRAKEN_BASE_URL":
                return "https://api.kraken.com"
            return default
        
        # Patch load_dotenv and os.getenv
        with patch('bot.config.load_dotenv', return_value=True), \
             patch('os.getenv', side_effect=mock_getenv):
            
            # Load environment variables
            result = self.config.load_env_variables()
            
            # Verify result
            self.assertTrue(result)
            
            # Verify credentials were loaded correctly
            credentials = self.config.get_kraken_credentials()
            self.assertEqual(credentials.api_key, "valid_api_key")
            self.assertEqual(credentials.api_secret, "valid_secret_key")
            self.assertEqual(credentials.base_url, "https://api.kraken.com")
            
            # Verify config validation passes
            self.assertTrue(self.config.validate_config())
    
    def test_missing_required_variables(self):
        """Test loading an .env file with missing required variables."""
        # Mock os.getenv to return None for required variables
        def mock_getenv(key, default=None):
            if key == "KRAKEN_API_KEY":
                return None  # Missing API key
            elif key == "KRAKEN_API_SECRET":
                return "valid_secret_key"
            elif key == "KRAKEN_BASE_URL":
                return "https://api.kraken.com"
            return default
        
        # Patch load_dotenv and os.getenv
        with patch('bot.config.load_dotenv', return_value=True), \
             patch('os.getenv', side_effect=mock_getenv), \
             patch('bot.config.log_error') as mock_log_error:
            
            # Load environment variables
            result = self.config.load_env_variables()
            
            # Verify result
            self.assertFalse(result)
            
            # Verify error was logged
            mock_log_error.assert_called_once()
            self.assertIn("Missing required environment variables", mock_log_error.call_args[0][0])
    
    def test_empty_api_keys(self):
        """Test loading an .env file with empty API keys."""
        # Mock os.getenv to return empty strings for API keys
        def mock_getenv(key, default=None):
            if key == "KRAKEN_API_KEY":
                return ""  # Empty API key
            elif key == "KRAKEN_API_SECRET":
                return ""  # Empty secret key
            elif key == "KRAKEN_BASE_URL":
                return "https://api.kraken.com"
            return default
        
        # Patch load_dotenv and os.getenv
        with patch('bot.config.load_dotenv', return_value=True), \
             patch('os.getenv', side_effect=mock_getenv), \
             patch('bot.config.log_error') as mock_log_error:
            
            # Load environment variables
            result = self.config.load_env_variables()
            
            # Verify result
            self.assertTrue(result)  # Loading succeeds but validation will fail
            
            # Verify config validation fails
            self.assertFalse(self.config.validate_config())
            
            # Verify error was logged
            mock_log_error.assert_called_once()
            self.assertIn("Invalid Kraken credentials", mock_log_error.call_args[0][0])
    
    def test_custom_base_url(self):
        """Test loading with custom base URL."""
        # Mock os.getenv to return custom base URL
        def mock_getenv(key, default=None):
            if key == "KRAKEN_API_KEY":
                return "valid_api_key"
            elif key == "KRAKEN_API_SECRET":
                return "valid_secret_key"
            elif key == "KRAKEN_BASE_URL":
                return "https://api.kraken.com/custom"
            return default
        
        # Patch load_dotenv and os.getenv
        with patch('bot.config.load_dotenv', return_value=True), \
             patch('os.getenv', side_effect=mock_getenv):
            
            # Load environment variables
            result = self.config.load_env_variables()
            
            # Verify result
            self.assertTrue(result)
            
            # Verify credentials were loaded correctly with custom base URL
            credentials = self.config.get_kraken_credentials()
            self.assertEqual(credentials.base_url, "https://api.kraken.com/custom")
    
    def test_missing_env_file(self):
        """Test behavior when .env file is missing."""
        # Mock os.getenv to return None for required variables
        def mock_getenv(key, default=None):
            return None  # No environment variables set
        
        # Patch load_dotenv to return False (file not found) and os.getenv
        with patch('bot.config.load_dotenv', return_value=False), \
             patch('os.getenv', side_effect=mock_getenv), \
             patch('bot.config.log_error') as mock_log_error:
            
            # Load environment variables
            result = self.config.load_env_variables()
            
            # Verify result
            self.assertFalse(result)
    
    def test_exception_during_loading(self):
        """Test handling of exceptions during .env loading."""
        # Patch load_dotenv to raise an exception
        with patch('bot.config.load_dotenv', side_effect=Exception("Test exception")), \
             patch('bot.config.log_error') as mock_log_error:
            
            # Load environment variables
            result = self.config.load_env_variables()
            
            # Verify result
            self.assertFalse(result)
            
            # Verify error was logged
            mock_log_error.assert_called_once()
            self.assertIn("Error loading environment variables", mock_log_error.call_args[0][0])
    
    def test_trading_settings_defaults(self):
        """Test default values for trading settings."""
        # Get trading settings
        settings = self.config.get_trading_settings()
        
        # Verify default values
        self.assertEqual(settings.symbol, "BTC/USD")
        self.assertEqual(settings.trade_amount, 10.0)
        self.assertEqual(settings.max_position_size, 100.0)
        self.assertEqual(settings.stop_loss_pct, 0.05)
        self.assertEqual(settings.take_profit_pct, 0.1)
        self.assertEqual(settings.min_trade_interval, 5)
    
    def test_config_singleton_behavior(self):
        """Test that Config class behaves as a singleton."""
        # Create two instances
        config1 = Config()
        config2 = Config()
        
        # Verify they are the same instance
        self.assertIs(config1, config2)
        
        # Modify one instance
        with patch('bot.config.load_dotenv', return_value=True), \
             patch('os.getenv', return_value="test_value"):
            config1.load_env_variables()
        
        # Verify the other instance is also modified
        self.assertIsNotNone(config2.get_kraken_credentials())
    
    def test_real_env_file_creation_and_loading(self):
        """Test creating and loading a real .env file."""
        # Create a real .env file in the temporary directory
        env_path = os.path.join(self.test_dir, ".env")
        with open(env_path, "w") as f:
            f.write("KRAKEN_API_KEY=real_test_key\n")
            f.write("KRAKEN_API_SECRET=real_test_secret\n")
            f.write("KRAKEN_BASE_URL=https://api.kraken.com\n")
        
        # Patch load_dotenv to use our file and actually load it
        def mock_load_dotenv(dotenv_path=None):
            # Load from our test file
            with open(env_path, "r") as f:
                for line in f:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        os.environ[key] = value
            return True
        
        # Save original environment
        original_environ = os.environ.copy()
        
        try:
            # Patch load_dotenv
            with patch('bot.config.load_dotenv', side_effect=mock_load_dotenv):
                # Create a new Config instance
                test_config = Config()
                
                # Load environment variables
                result = test_config.load_env_variables()
                
                # Verify result
                self.assertTrue(result)
                
                # Verify credentials were loaded correctly
                credentials = test_config.get_kraken_credentials()
                self.assertEqual(credentials.api_key, "real_test_key")
                self.assertEqual(credentials.api_secret, "real_test_secret")
                self.assertEqual(credentials.base_url, "https://api.kraken.com")
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_environ)


if __name__ == '__main__':
    unittest.main()