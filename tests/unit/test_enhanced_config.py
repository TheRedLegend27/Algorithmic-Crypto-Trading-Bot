"""
Unit tests for enhanced configuration system.
"""
import unittest
import tempfile
import os
import json
import shutil
from unittest.mock import patch, MagicMock

from bot.config import (
    Config, 
    KrakenCredentials, 
    KrakenTradingPair, 
    StrategyConfig, 
    RiskConfig, 
    EnhancedTradingConfig,
    CryptoTradingSettings,
    TradingSettings
)


class TestKrakenCredentials(unittest.TestCase):
    """Test cases for KrakenCredentials class."""
    
    def test_valid_credentials(self):
        """Test valid credentials validation."""
        credentials = KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
        self.assertTrue(credentials.validate())
    
    def test_empty_api_key(self):
        """Test validation with empty API key."""
        credentials = KrakenCredentials(
            api_key="",
            api_secret="test_secret"
        )
        self.assertFalse(credentials.validate())
    
    def test_empty_api_secret(self):
        """Test validation with empty API secret."""
        credentials = KrakenCredentials(
            api_key="test_key",
            api_secret=""
        )
        self.assertFalse(credentials.validate())
    
    def test_empty_base_url(self):
        """Test validation with empty base URL."""
        credentials = KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret",
            base_url=""
        )
        self.assertFalse(credentials.validate())


class TestKrakenTradingPair(unittest.TestCase):
    """Test cases for KrakenTradingPair class."""
    
    def test_valid_trading_pair(self):
        """Test valid trading pair validation."""
        pair = KrakenTradingPair(
            symbol="XBTUSD",
            base_currency="XBT",
            quote_currency="USD",
            min_order_size=0.0001,
            price_precision=1,
            size_precision=8
        )
        self.assertTrue(pair.validate())
    
    def test_empty_symbol(self):
        """Test validation with empty symbol."""
        pair = KrakenTradingPair(
            symbol="",
            base_currency="XBT",
            quote_currency="USD",
            min_order_size=0.0001,
            price_precision=1,
            size_precision=8
        )
        self.assertFalse(pair.validate())
    
    def test_negative_min_order_size(self):
        """Test validation with negative minimum order size."""
        pair = KrakenTradingPair(
            symbol="XBTUSD",
            base_currency="XBT",
            quote_currency="USD",
            min_order_size=-0.0001,
            price_precision=1,
            size_precision=8
        )
        self.assertFalse(pair.validate())
    
    def test_negative_precision(self):
        """Test validation with negative precision."""
        pair = KrakenTradingPair(
            symbol="XBTUSD",
            base_currency="XBT",
            quote_currency="USD",
            min_order_size=0.0001,
            price_precision=-1,
            size_precision=8
        )
        self.assertFalse(pair.validate())
    
    def test_negative_fees(self):
        """Test validation with negative fees."""
        pair = KrakenTradingPair(
            symbol="XBTUSD",
            base_currency="XBT",
            quote_currency="USD",
            min_order_size=0.0001,
            price_precision=1,
            size_precision=8,
            maker_fee=-0.001
        )
        self.assertFalse(pair.validate())
    
    def test_from_dict(self):
        """Test creating trading pair from dictionary."""
        data = {
            'symbol': 'ETHUSD',
            'base_currency': 'ETH',
            'quote_currency': 'USD',
            'min_order_size': 0.001,
            'price_precision': 2,
            'size_precision': 6,
            'maker_fee': 0.0016,
            'taker_fee': 0.0026,
            'enabled': True
        }
        
        pair = KrakenTradingPair.from_dict(data)
        self.assertEqual(pair.symbol, 'ETHUSD')
        self.assertEqual(pair.base_currency, 'ETH')
        self.assertEqual(pair.quote_currency, 'USD')
        self.assertEqual(pair.min_order_size, 0.001)
        self.assertTrue(pair.enabled)
    
    def test_to_dict(self):
        """Test converting trading pair to dictionary."""
        pair = KrakenTradingPair(
            symbol="XBTUSD",
            base_currency="XBT",
            quote_currency="USD",
            min_order_size=0.0001,
            price_precision=1,
            size_precision=8
        )
        
        data = pair.to_dict()
        self.assertEqual(data['symbol'], 'XBTUSD')
        self.assertEqual(data['base_currency'], 'XBT')
        self.assertEqual(data['quote_currency'], 'USD')
        self.assertEqual(data['min_order_size'], 0.0001)


class TestStrategyConfig(unittest.TestCase):
    """Test cases for StrategyConfig class."""
    
    def test_valid_strategy_config(self):
        """Test valid strategy configuration."""
        config = StrategyConfig()
        self.assertTrue(config.validate())
    
    def test_invalid_weights_sum(self):
        """Test validation with invalid weights sum."""
        config = StrategyConfig(
            momentum_weight=0.5,
            volatility_weight=0.5,
            volume_weight=0.5,  # Total > 1.0
            bollinger_weight=0.0,
            macd_weight=0.0
        )
        self.assertFalse(config.validate())
    
    def test_negative_weight(self):
        """Test validation with negative weight."""
        config = StrategyConfig(
            momentum_weight=-0.1,
            volatility_weight=0.4,
            volume_weight=0.4,
            bollinger_weight=0.2,
            macd_weight=0.1
        )
        self.assertFalse(config.validate())
    
    def test_invalid_lookback_periods(self):
        """Test validation with invalid lookback periods."""
        config = StrategyConfig(
            momentum_lookback_periods=0
        )
        self.assertFalse(config.validate())
    
    def test_invalid_macd_parameters(self):
        """Test validation with invalid MACD parameters."""
        config = StrategyConfig(
            macd_fast_period=26,  # Fast >= slow
            macd_slow_period=12
        )
        self.assertFalse(config.validate())
    
    def test_invalid_signal_strength(self):
        """Test validation with invalid signal strength."""
        config = StrategyConfig(
            min_signal_strength=1.5  # > 1.0
        )
        self.assertFalse(config.validate())
    
    def test_from_dict(self):
        """Test creating strategy config from dictionary."""
        data = {
            'momentum_weight': 0.4,
            'volatility_weight': 0.3,
            'volume_weight': 0.2,
            'bollinger_weight': 0.1,
            'macd_weight': 0.0,
            'momentum_lookback_periods': 10
        }
        
        config = StrategyConfig.from_dict(data)
        self.assertEqual(config.momentum_weight, 0.4)
        self.assertEqual(config.momentum_lookback_periods, 10)
    
    def test_to_dict(self):
        """Test converting strategy config to dictionary."""
        config = StrategyConfig()
        data = config.to_dict()
        
        self.assertIn('momentum_weight', data)
        self.assertIn('volatility_weight', data)
        self.assertIn('momentum_lookback_periods', data)


class TestRiskConfig(unittest.TestCase):
    """Test cases for RiskConfig class."""
    
    def test_valid_risk_config(self):
        """Test valid risk configuration."""
        config = RiskConfig()
        self.assertTrue(config.validate())
    
    def test_negative_amounts(self):
        """Test validation with negative amounts."""
        config = RiskConfig(
            default_trade_amount_usd=-100.0
        )
        self.assertFalse(config.validate())
    
    def test_invalid_percentages(self):
        """Test validation with invalid percentages."""
        config = RiskConfig(
            risk_per_trade_pct=1.5  # > 1.0
        )
        self.assertFalse(config.validate())
    
    def test_invalid_position_limits(self):
        """Test validation with invalid position limits."""
        config = RiskConfig(
            max_open_positions=0
        )
        self.assertFalse(config.validate())
    
    def test_invalid_correlation_exposure(self):
        """Test validation with invalid correlation exposure."""
        config = RiskConfig(
            max_correlation_exposure=1.5  # > 1.0
        )
        self.assertFalse(config.validate())
    
    def test_logical_relationship_validation(self):
        """Test validation of logical relationships."""
        config = RiskConfig(
            max_position_per_pair_usd=2000.0,
            max_total_position_usd=1000.0  # Per pair > total
        )
        self.assertFalse(config.validate())
    
    def test_from_dict(self):
        """Test creating risk config from dictionary."""
        data = {
            'default_trade_amount_usd': 200.0,
            'max_position_per_pair_usd': 2000.0,
            'risk_per_trade_pct': 0.03
        }
        
        config = RiskConfig.from_dict(data)
        self.assertEqual(config.default_trade_amount_usd, 200.0)
        self.assertEqual(config.risk_per_trade_pct, 0.03)
    
    def test_to_dict(self):
        """Test converting risk config to dictionary."""
        config = RiskConfig()
        data = config.to_dict()
        
        self.assertIn('default_trade_amount_usd', data)
        self.assertIn('max_position_per_pair_usd', data)
        self.assertIn('risk_per_trade_pct', data)


class TestEnhancedTradingConfig(unittest.TestCase):
    """Test cases for EnhancedTradingConfig class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_default_config_creation(self):
        """Test creating default enhanced configuration."""
        config = EnhancedTradingConfig()
        self.assertTrue(config.validate())
        self.assertGreater(len(config.trading_pairs), 0)
        self.assertIsInstance(config.strategy, StrategyConfig)
        self.assertIsInstance(config.risk, RiskConfig)
    
    def test_get_enabled_pairs(self):
        """Test getting enabled trading pairs."""
        config = EnhancedTradingConfig()
        enabled_pairs = config.get_enabled_pairs()
        
        # All default pairs should be enabled
        self.assertEqual(len(enabled_pairs), len(config.trading_pairs))
        for pair in enabled_pairs:
            self.assertTrue(pair.enabled)
    
    def test_get_pair_by_symbol(self):
        """Test getting trading pair by symbol."""
        config = EnhancedTradingConfig()
        pair = config.get_pair_by_symbol("XBTUSD")
        
        self.assertIsNotNone(pair)
        self.assertEqual(pair.symbol, "XBTUSD")
    
    def test_add_trading_pair(self):
        """Test adding a new trading pair."""
        config = EnhancedTradingConfig()
        initial_count = len(config.trading_pairs)
        
        new_pair = KrakenTradingPair(
            symbol="ADAUSD",
            base_currency="ADA",
            quote_currency="USD",
            min_order_size=1.0,
            price_precision=4,
            size_precision=2
        )
        
        self.assertTrue(config.add_trading_pair(new_pair))
        self.assertEqual(len(config.trading_pairs), initial_count + 1)
        self.assertIsNotNone(config.get_pair_by_symbol("ADAUSD"))
    
    def test_add_duplicate_trading_pair(self):
        """Test adding duplicate trading pair."""
        config = EnhancedTradingConfig()
        
        duplicate_pair = KrakenTradingPair(
            symbol="XBTUSD",  # Already exists in default config
            base_currency="XBT",
            quote_currency="USD",
            min_order_size=0.0001,
            price_precision=1,
            size_precision=8
        )
        
        self.assertFalse(config.add_trading_pair(duplicate_pair))
    
    def test_remove_trading_pair(self):
        """Test removing a trading pair."""
        config = EnhancedTradingConfig()
        initial_count = len(config.trading_pairs)
        
        self.assertTrue(config.remove_trading_pair("XBTUSD"))
        self.assertEqual(len(config.trading_pairs), initial_count - 1)
        self.assertIsNone(config.get_pair_by_symbol("XBTUSD"))
    
    def test_remove_nonexistent_trading_pair(self):
        """Test removing non-existent trading pair."""
        config = EnhancedTradingConfig()
        self.assertFalse(config.remove_trading_pair("NONEXISTENT"))
    
    def test_update_trading_pair(self):
        """Test updating trading pair configuration."""
        config = EnhancedTradingConfig()
        
        updates = {
            'min_order_size': 0.0002,
            'enabled': False
        }
        
        self.assertTrue(config.update_trading_pair("XBTUSD", updates))
        
        pair = config.get_pair_by_symbol("XBTUSD")
        self.assertEqual(pair.min_order_size, 0.0002)
        self.assertFalse(pair.enabled)
    
    def test_update_nonexistent_trading_pair(self):
        """Test updating non-existent trading pair."""
        config = EnhancedTradingConfig()
        updates = {'min_order_size': 0.0002}
        
        self.assertFalse(config.update_trading_pair("NONEXISTENT", updates))
    
    def test_from_dict(self):
        """Test creating enhanced config from dictionary."""
        data = {
            'trading_pairs': [
                {
                    'symbol': 'XBTUSD',
                    'base_currency': 'XBT',
                    'quote_currency': 'USD',
                    'min_order_size': 0.0001,
                    'price_precision': 1,
                    'size_precision': 8,
                    'maker_fee': 0.0016,
                    'taker_fee': 0.0026,
                    'enabled': True
                }
            ],
            'strategy': {
                'momentum_weight': 0.4,
                'volatility_weight': 0.6,
                'volume_weight': 0.0,
                'bollinger_weight': 0.0,
                'macd_weight': 0.0
            },
            'risk': {
                'default_trade_amount_usd': 200.0
            },
            'enable_websocket': False
        }
        
        config = EnhancedTradingConfig.from_dict(data)
        self.assertEqual(len(config.trading_pairs), 1)
        self.assertEqual(config.strategy.momentum_weight, 0.4)
        self.assertEqual(config.risk.default_trade_amount_usd, 200.0)
        self.assertFalse(config.enable_websocket)
    
    def test_to_dict(self):
        """Test converting enhanced config to dictionary."""
        config = EnhancedTradingConfig()
        data = config.to_dict()
        
        self.assertIn('trading_pairs', data)
        self.assertIn('strategy', data)
        self.assertIn('risk', data)
        self.assertIn('enable_websocket', data)
        self.assertIsInstance(data['trading_pairs'], list)
        self.assertIsInstance(data['strategy'], dict)
        self.assertIsInstance(data['risk'], dict)
    
    def test_save_and_load_from_file(self):
        """Test saving and loading configuration from file."""
        config = EnhancedTradingConfig()
        config.risk.default_trade_amount_usd = 150.0
        
        # Save configuration
        self.assertTrue(config.save_to_file(self.config_path))
        self.assertTrue(os.path.exists(self.config_path))
        
        # Load configuration
        loaded_config = EnhancedTradingConfig.load_from_file(self.config_path)
        self.assertIsNotNone(loaded_config)
        self.assertEqual(loaded_config.risk.default_trade_amount_usd, 150.0)
    
    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file."""
        config = EnhancedTradingConfig.load_from_file("nonexistent.json")
        self.assertIsNone(config)
    
    def test_load_from_invalid_json_file(self):
        """Test loading from invalid JSON file."""
        with open(self.config_path, 'w') as f:
            f.write("{ invalid json }")
        
        config = EnhancedTradingConfig.load_from_file(self.config_path)
        self.assertIsNone(config)


class TestEnhancedConfig(unittest.TestCase):
    """Test cases for enhanced Config class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Reset Config singleton for each test
        Config._instance = None
        self.config = Config()
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)
    
    def test_enhanced_config_initialization(self):
        """Test enhanced configuration initialization."""
        enhanced_config = self.config.get_enhanced_config()
        self.assertIsInstance(enhanced_config, EnhancedTradingConfig)
        self.assertTrue(enhanced_config.validate())
    
    def test_load_env_variables_with_overrides(self):
        """Test loading environment variables with configuration overrides."""
        def mock_getenv(key, default=None):
            env_vars = {
                "KRAKEN_API_KEY": "test_key",
                "KRAKEN_API_SECRET": "test_secret",
                "DEFAULT_TRADE_AMOUNT_USD": "200.0",
                "MAX_POSITION_PER_PAIR_USD": "2000.0",
                "ENABLE_WEBSOCKET": "false",
                "DASHBOARD_PORT": "8090"
            }
            return env_vars.get(key, default)
        
        with patch('bot.config.load_dotenv', return_value=True), \
             patch('os.getenv', side_effect=mock_getenv):
            
            result = self.config.load_env_variables()
            self.assertTrue(result)
            
            # Check credentials
            credentials = self.config.get_kraken_credentials()
            self.assertEqual(credentials.api_key, "test_key")
            self.assertEqual(credentials.api_secret, "test_secret")
            
            # Check configuration overrides
            enhanced_config = self.config.get_enhanced_config()
            self.assertEqual(enhanced_config.risk.default_trade_amount_usd, 200.0)
            self.assertEqual(enhanced_config.risk.max_position_per_pair_usd, 2000.0)
            self.assertFalse(enhanced_config.enable_websocket)
            self.assertEqual(enhanced_config.dashboard_port, 8090)
    
    def test_validate_config_with_enhanced(self):
        """Test configuration validation with enhanced config."""
        # Mock valid credentials
        self.config._kraken_credentials = KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
        
        self.assertTrue(self.config.validate_config())
    
    def test_validate_config_with_invalid_enhanced(self):
        """Test configuration validation with invalid enhanced config."""
        # Mock valid credentials
        self.config._kraken_credentials = KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
        
        # Make enhanced config invalid
        self.config._enhanced_config.risk.default_trade_amount_usd = -100.0
        
        self.assertFalse(self.config.validate_config())
    
    def test_load_available_trading_pairs_with_metadata(self):
        """Test loading available trading pairs with metadata."""
        mock_client = MagicMock()
        mock_client.get_asset_pairs.return_value = {
            'XBTUSD': {
                'base': 'XXBT',
                'quote': 'ZUSD',
                'pair_decimals': 1,
                'lot_decimals': 8,
                'ordermin': '0.0001',
                'fees': [[0, 0.26], [50000, 0.24]],
                'fees_maker': [[0, 0.16], [50000, 0.14]]
            },
            'ETHUSD': {
                'base': 'XETH',
                'quote': 'ZUSD',
                'pair_decimals': 2,
                'lot_decimals': 6,
                'ordermin': '0.001',
                'fees': [[0, 0.26], [50000, 0.24]],
                'fees_maker': [[0, 0.16], [50000, 0.14]]
            }
        }
        
        result = self.config.load_available_trading_pairs(mock_client)
        self.assertTrue(result)
        
        available_pairs = self.config.get_available_trading_pairs()
        self.assertIn('XBTUSD', available_pairs)
        self.assertIn('ETHUSD', available_pairs)
        
        # Check metadata
        btc_metadata = self.config.get_pair_metadata('XBTUSD')
        self.assertIsNotNone(btc_metadata)
        self.assertEqual(btc_metadata['base'], 'XXBT')
        self.assertEqual(btc_metadata['quote'], 'ZUSD')
        self.assertEqual(btc_metadata['pair_decimals'], 1)
        self.assertEqual(btc_metadata['ordermin'], '0.0001')
    
    def test_update_trading_pair_from_metadata(self):
        """Test updating trading pair from metadata."""
        # Set up metadata
        self.config._pair_metadata = {
            'ADAUSD': {
                'base': 'ADA',
                'quote': 'USD',
                'pair_decimals': 4,
                'lot_decimals': 2,
                'ordermin': '1.0'
            }
        }
        
        result = self.config.update_trading_pair_from_metadata('ADAUSD')
        self.assertTrue(result)
        
        # Check that pair was added
        enhanced_config = self.config.get_enhanced_config()
        pair = enhanced_config.get_pair_by_symbol('ADAUSD')
        self.assertIsNotNone(pair)
        self.assertEqual(pair.base_currency, 'ADA')
        self.assertEqual(pair.quote_currency, 'USD')
        self.assertEqual(pair.price_precision, 4)
        self.assertEqual(pair.min_order_size, 1.0)
    
    def test_apply_default_values(self):
        """Test applying default values to configuration."""
        # Make config invalid
        enhanced_config = self.config.get_enhanced_config()
        enhanced_config.risk.default_trade_amount_usd = -100.0
        enhanced_config.risk.max_position_per_pair_usd = 10000.0
        enhanced_config.risk.max_total_position_usd = 5000.0  # Less than per pair
        
        # Make strategy weights invalid
        enhanced_config.strategy.momentum_weight = 0.8
        enhanced_config.strategy.volatility_weight = 0.8  # Total > 1.0
        
        result = self.config.apply_default_values()
        self.assertTrue(result)
        
        # Check that defaults were applied
        self.assertEqual(enhanced_config.risk.default_trade_amount_usd, 100.0)
        self.assertEqual(enhanced_config.risk.max_position_per_pair_usd, 2500.0)  # 50% of total
        
        # Check strategy weights
        total_weight = (enhanced_config.strategy.momentum_weight + 
                       enhanced_config.strategy.volatility_weight +
                       enhanced_config.strategy.volume_weight +
                       enhanced_config.strategy.bollinger_weight +
                       enhanced_config.strategy.macd_weight)
        self.assertAlmostEqual(total_weight, 1.0, places=2)
    
    def test_backward_compatibility_methods(self):
        """Test backward compatibility methods."""
        # Test get_crypto_trading_settings
        crypto_settings = self.config.get_crypto_trading_settings()
        self.assertIsInstance(crypto_settings, CryptoTradingSettings)
        
        # Test update_crypto_trading_settings
        updates = {
            'trade_amount_usd': 150.0,
            'max_position_usd': 1500.0,
            'stop_loss_pct': 0.04
        }
        
        result = self.config.update_crypto_trading_settings(updates)
        self.assertTrue(result)
        
        # Check that enhanced config was updated
        enhanced_config = self.config.get_enhanced_config()
        self.assertEqual(enhanced_config.risk.default_trade_amount_usd, 150.0)
        self.assertEqual(enhanced_config.risk.max_position_per_pair_usd, 1500.0)
        self.assertEqual(enhanced_config.risk.default_stop_loss_pct, 0.04)
    
    def test_enhanced_config_file_operations(self):
        """Test enhanced configuration file operations."""
        config_path = os.path.join(self.temp_dir, "enhanced_config.json")
        
        # Modify configuration
        enhanced_config = self.config.get_enhanced_config()
        enhanced_config.risk.default_trade_amount_usd = 250.0
        
        # Save to file
        result = self.config.save_enhanced_config_to_file(config_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(config_path))
        
        # Reset config and load from file
        Config._instance = None
        new_config = Config()
        
        result = new_config.load_enhanced_config_from_file(config_path)
        self.assertTrue(result)
        
        # Check loaded configuration
        loaded_enhanced_config = new_config.get_enhanced_config()
        self.assertEqual(loaded_enhanced_config.risk.default_trade_amount_usd, 250.0)


if __name__ == '__main__':
    unittest.main()