"""
Unit tests for the Alpaca to Coinbase migration utility.
"""
import os
import sys
import unittest
from unittest.mock import patch, mock_open, MagicMock
import tempfile
import shutil

# Add the parent directory to the path so we can import the tools package
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.alpaca_to_coinbase_migration import (
    read_env_file,
    write_env_file,
    convert_alpaca_to_coinbase,
    validate_coinbase_config,
    create_backup
)


class TestAlpacaToCoinbaseMigration(unittest.TestCase):
    """Test cases for the Alpaca to Coinbase migration utility."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.env_file = os.path.join(self.temp_dir, ".env")
        
        # Sample environment variables
        self.sample_env_content = """
# Alpaca API credentials
ALPACA_API_KEY=test_alpaca_key
ALPACA_SECRET_KEY=test_alpaca_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Set to True for paper trading, False for live trading
IS_PAPER_TRADING=True

# Other settings
LOG_LEVEL=INFO
"""
        
        # Write sample env file
        with open(self.env_file, "w") as f:
            f.write(self.sample_env_content)

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_read_env_file(self):
        """Test reading environment variables from a file."""
        env_vars = read_env_file(self.env_file)
        
        self.assertEqual(env_vars["ALPACA_API_KEY"], "test_alpaca_key")
        self.assertEqual(env_vars["ALPACA_SECRET_KEY"], "test_alpaca_secret")
        self.assertEqual(env_vars["ALPACA_BASE_URL"], "https://paper-api.alpaca.markets")
        self.assertEqual(env_vars["IS_PAPER_TRADING"], "True")
        self.assertEqual(env_vars["LOG_LEVEL"], "INFO")

    def test_read_env_file_not_found(self):
        """Test reading from a non-existent file."""
        env_vars = read_env_file(os.path.join(self.temp_dir, "nonexistent.env"))
        self.assertEqual(env_vars, {})

    def test_write_env_file(self):
        """Test writing environment variables to a file."""
        env_vars = {
            "COINBASE_API_KEY": "test_coinbase_key",
            "COINBASE_API_SECRET": "test_coinbase_secret",
            "COINBASE_PASSPHRASE": "test_passphrase",
            "COINBASE_SANDBOX": "True",
            "LOG_LEVEL": "INFO"
        }
        
        output_file = os.path.join(self.temp_dir, ".env.coinbase")
        result = write_env_file(output_file, env_vars)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_file))
        
        # Read back the file and check contents
        with open(output_file, "r") as f:
            content = f.read()
            
        self.assertIn("COINBASE_API_KEY=test_coinbase_key", content)
        self.assertIn("COINBASE_API_SECRET=test_coinbase_secret", content)
        self.assertIn("COINBASE_PASSPHRASE=test_passphrase", content)
        self.assertIn("COINBASE_SANDBOX=True", content)
        self.assertIn("LOG_LEVEL=INFO", content)

    def test_convert_alpaca_to_coinbase(self):
        """Test converting Alpaca environment variables to Coinbase."""
        env_vars = {
            "ALPACA_API_KEY": "test_alpaca_key",
            "ALPACA_SECRET_KEY": "test_alpaca_secret",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
            "IS_PAPER_TRADING": "True",
            "LOG_LEVEL": "INFO"
        }
        
        # Test with sandbox mode
        new_env_vars = convert_alpaca_to_coinbase(env_vars, True)
        
        self.assertEqual(new_env_vars["COINBASE_SANDBOX"], "True")
        self.assertEqual(new_env_vars["COINBASE_API_KEY"], "your_coinbase_api_key_here")
        self.assertEqual(new_env_vars["COINBASE_API_SECRET"], "your_coinbase_api_secret_here")
        self.assertEqual(new_env_vars["COINBASE_PASSPHRASE"], "your_coinbase_passphrase_here")
        
        # Original variables should be preserved
        self.assertEqual(new_env_vars["ALPACA_API_KEY"], "test_alpaca_key")
        self.assertEqual(new_env_vars["LOG_LEVEL"], "INFO")
        
        # Test with live mode
        new_env_vars = convert_alpaca_to_coinbase(env_vars, False)
        self.assertEqual(new_env_vars["COINBASE_SANDBOX"], "False")

    def test_convert_alpaca_to_coinbase_existing_coinbase(self):
        """Test conversion when Coinbase credentials already exist."""
        env_vars = {
            "ALPACA_API_KEY": "test_alpaca_key",
            "ALPACA_SECRET_KEY": "test_alpaca_secret",
            "COINBASE_API_KEY": "existing_coinbase_key",
            "COINBASE_API_SECRET": "existing_coinbase_secret",
            "COINBASE_PASSPHRASE": "existing_passphrase"
        }
        
        new_env_vars = convert_alpaca_to_coinbase(env_vars, True)
        
        # Existing Coinbase credentials should be preserved
        self.assertEqual(new_env_vars["COINBASE_API_KEY"], "existing_coinbase_key")
        self.assertEqual(new_env_vars["COINBASE_API_SECRET"], "existing_coinbase_secret")
        self.assertEqual(new_env_vars["COINBASE_PASSPHRASE"], "existing_passphrase")

    def test_validate_coinbase_config(self):
        """Test validating Coinbase configuration."""
        # Valid configuration
        valid_env = {
            "COINBASE_API_KEY": "test_key",
            "COINBASE_API_SECRET": "test_secret",
            "COINBASE_PASSPHRASE": "test_passphrase",
            "COINBASE_SANDBOX": "True"
        }
        
        is_valid, errors = validate_coinbase_config(valid_env)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Missing variables
        missing_env = {
            "COINBASE_API_KEY": "test_key",
            "COINBASE_SANDBOX": "True"
        }
        
        is_valid, errors = validate_coinbase_config(missing_env)
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)
        self.assertIn("Missing required Coinbase variables", errors[0])
        
        # Placeholder values
        placeholder_env = {
            "COINBASE_API_KEY": "your_coinbase_api_key_here",
            "COINBASE_API_SECRET": "test_secret",
            "COINBASE_PASSPHRASE": "test_passphrase",
            "COINBASE_SANDBOX": "True"
        }
        
        is_valid, errors = validate_coinbase_config(placeholder_env)
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)
        self.assertIn("placeholder values", errors[0])
        
        # Invalid sandbox value
        invalid_sandbox_env = {
            "COINBASE_API_KEY": "test_key",
            "COINBASE_API_SECRET": "test_secret",
            "COINBASE_PASSPHRASE": "test_passphrase",
            "COINBASE_SANDBOX": "invalid"
        }
        
        is_valid, errors = validate_coinbase_config(invalid_sandbox_env)
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid value for COINBASE_SANDBOX", errors[0])

    @patch("shutil.copy2")
    def test_create_backup(self, mock_copy):
        """Test creating a backup of a file."""
        mock_copy.return_value = None
        
        result = create_backup(self.env_file)
        self.assertTrue(result)
        mock_copy.assert_called_once()
        
        # Test error handling
        mock_copy.side_effect = Exception("Test error")
        result = create_backup(self.env_file)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()