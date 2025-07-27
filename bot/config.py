"""
Configuration management for the crypto trading bot.
Handles loading environment variables and validating configuration.
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

from bot.utils import log_error, log_info


@dataclass
class KrakenCredentials:
    """Dataclass for storing Kraken API credentials."""
    api_key: str
    api_secret: str
    base_url: str = "https://api.kraken.com"


@dataclass
class CryptoTradingSettings:
    """Dataclass for storing crypto-specific trading parameters."""
    # Trading pair settings
    trading_pair: str = "BTC-USD"
    base_currency: str = "BTC"
    quote_currency: str = "USD"
    
    # Order size settings
    trade_amount_usd: float = 10.0
    max_position_usd: float = 100.0
    min_order_size: float = 0.001  # Minimum BTC order size
    
    # Precision settings
    price_precision: int = 2
    size_precision: int = 8
    
    # Fee settings
    maker_fee_rate: float = 0.005  # 0.5%
    taker_fee_rate: float = 0.005  # 0.5%
    
    # Risk management settings
    max_risk_per_trade_pct: float = 0.02  # 2% of portfolio per trade
    max_daily_loss_pct: float = 0.05  # 5% max daily loss
    max_open_positions: int = 5  # Maximum number of open positions
    stop_loss_pct: float = 0.03  # 3% stop loss
    take_profit_pct: float = 0.06  # 6% take profit
    
    # Volatility settings
    volatility_adjustment: bool = True  # Adjust position size based on volatility
    max_volatility_multiplier: float = 0.5  # Reduce position by up to 50% in high volatility


@dataclass
class TradingSettings:
    """Dataclass for storing trading parameters."""
    symbol: str = "BTC/USD"
    trade_amount: float = 10.0  # Default amount in USD to trade
    max_position_size: float = 100.0  # Maximum position size in USD
    stop_loss_pct: float = 0.05  # 5% stop loss
    take_profit_pct: float = 0.1  # 10% take profit
    min_trade_interval: int = 5  # Minutes between trades
    
    # Aggressive trading settings
    aggressive_mode: bool = False
    initial_capital: float = 100.0
    max_risk_per_trade: float = 0.05  # 5% of capital per trade
    max_daily_loss: float = 0.15  # 15% max daily loss
    use_dynamic_sizing: bool = True
    max_trades_per_day: int = 20  # Maximum trades per day


class Config:
    """Singleton class for managing configuration."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._kraken_credentials = None
        self._trading_settings = TradingSettings()
        self._crypto_trading_settings = CryptoTradingSettings()
        self._available_trading_pairs = []
        self._initialized = True
        
    def load_env_variables(self) -> bool:
        """
        Load environment variables from .env file.
        
        Returns:
            bool: True if loading was successful, False otherwise.
        """
        try:
            # Load .env file - if it doesn't exist, environment variables might still be set
            dotenv_loaded = load_dotenv()
            
            # Check if required environment variables exist (not None)
            required_vars = ["KRAKEN_API_KEY", "KRAKEN_API_SECRET"]
            missing_vars = [var for var in required_vars if os.getenv(var) is None]
            
            if missing_vars:
                if not dotenv_loaded:
                    log_error("No .env file found and required environment variables are missing")
                else:
                    log_error(f"Missing required environment variables: {', '.join(missing_vars)}")
                return False
                
            # Load Kraken credentials
            self._kraken_credentials = KrakenCredentials(
                api_key=os.getenv("KRAKEN_API_KEY"),
                api_secret=os.getenv("KRAKEN_API_SECRET")
            )
            
            return True
            
        except Exception as e:
            log_error(f"Error loading environment variables: {str(e)}")
            return False
    
    def get_kraken_credentials(self) -> Optional[KrakenCredentials]:
        """
        Get Kraken API credentials.
        
        Returns:
            KrakenCredentials: Object containing API credentials.
        """
        return self._kraken_credentials
    
    def get_trading_settings(self) -> TradingSettings:
        """
        Get trading settings.
        
        Returns:
            TradingSettings: Object containing trading parameters.
        """
        return self._trading_settings
    
    def get_crypto_trading_settings(self) -> CryptoTradingSettings:
        """
        Get crypto trading settings.
        
        Returns:
            CryptoTradingSettings: Object containing crypto trading parameters.
        """
        return self._crypto_trading_settings
    
    def validate_config(self) -> bool:
        """
        Validate the configuration.
        
        Returns:
            bool: True if configuration is valid, False otherwise.
        """
        if not self._kraken_credentials:
            log_error("Kraken credentials not loaded")
            return False
            
        # Validate API keys are not empty
        if not self._kraken_credentials.api_key or not self._kraken_credentials.api_secret:
            log_error("API keys cannot be empty")
            return False
            
        # Validate base URL
        if not self._kraken_credentials.base_url:
            log_error("Base URL cannot be empty")
            return False
            
        return True
        
    def validate_trading_pair(self, trading_pair: str) -> bool:
        """
        Validate that a trading pair exists on Kraken.
        
        Args:
            trading_pair: Trading pair to validate (e.g., 'XBTUSD')
            
        Returns:
            bool: True if trading pair is valid, False otherwise.
        """
        # If we haven't fetched available pairs yet, return True to avoid API call during testing
        if not self._available_trading_pairs:
            return True
            
        return trading_pair in self._available_trading_pairs
        
    def load_available_trading_pairs(self, kraken_client) -> bool:
        """
        Load available trading pairs from Kraken.
        
        Args:
            kraken_client: Initialized KrakenClient instance
            
        Returns:
            bool: True if loading was successful, False otherwise.
        """
        try:
            asset_pairs = kraken_client.get_asset_pairs()
            self._available_trading_pairs = list(asset_pairs.keys())
            return True
        except Exception as e:
            log_error(f"Error loading available trading pairs: {str(e)}")
            return False
            
    def update_crypto_trading_settings(self, settings: dict) -> bool:
        """
        Update crypto trading settings with new values.
        
        Args:
            settings: Dictionary of settings to update
            
        Returns:
            bool: True if update was successful, False otherwise.
        """
        try:
            for key, value in settings.items():
                if hasattr(self._crypto_trading_settings, key):
                    setattr(self._crypto_trading_settings, key, value)
                else:
                    log_error(f"Unknown crypto trading setting: {key}")
                    # Don't return False here, continue processing other settings
            return True
        except Exception as e:
            log_error(f"Error updating crypto trading settings: {str(e)}")
            return False
            
