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
class CoinbaseCredentials:
    """Dataclass for storing Coinbase API credentials."""
    api_key: str
    api_secret: str  # This is now the private key for JWT authentication
    sandbox: bool = False
    base_url: str = "https://api.coinbase.com"
    
    def __post_init__(self):
        """Set the correct base URL based on sandbox mode."""
        self.update_base_url()
    
    def update_base_url(self):
        """Update the base URL based on sandbox mode."""
        # Both sandbox and production use the same base URL for Advanced Trade API
        self.base_url = "https://api.coinbase.com"


@dataclass
class AlpacaCredentials:
    """Dataclass for storing Alpaca API credentials."""
    api_key: str
    secret_key: str
    base_url: str
    paper_trading: bool


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
            
        self._alpaca_credentials = None
        self._coinbase_credentials = None
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
            required_vars = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_BASE_URL"]
            missing_vars = [var for var in required_vars if os.getenv(var) is None]
            
            if missing_vars:
                if not dotenv_loaded:
                    log_error("No .env file found and required environment variables are missing")
                else:
                    log_error(f"Missing required environment variables: {', '.join(missing_vars)}")
                return False
                
            # Load Alpaca credentials
            self._alpaca_credentials = AlpacaCredentials(
                api_key=os.getenv("ALPACA_API_KEY"),
                secret_key=os.getenv("ALPACA_SECRET_KEY"),
                base_url=os.getenv("ALPACA_BASE_URL"),
                paper_trading=os.getenv("IS_PAPER_TRADING", "True").lower() in ("true", "1", "t")
            )
            
            # Load Coinbase credentials if available
            coinbase_key = os.getenv("COINBASE_API_KEY")
            coinbase_secret = os.getenv("COINBASE_API_SECRET")
            
            if coinbase_key and coinbase_secret:
                self._coinbase_credentials = CoinbaseCredentials(
                    api_key=coinbase_key,
                    api_secret=coinbase_secret,
                    sandbox=os.getenv("COINBASE_SANDBOX", "True").lower() in ("true", "1", "t")
                )
            
            return True
            
        except Exception as e:
            log_error(f"Error loading environment variables: {str(e)}")
            return False
    
    def get_alpaca_credentials(self) -> Optional[AlpacaCredentials]:
        """
        Get Alpaca API credentials.
        
        Returns:
            AlpacaCredentials: Object containing API credentials.
        """
        return self._alpaca_credentials
    
    def get_coinbase_credentials(self) -> Optional[CoinbaseCredentials]:
        """
        Get Coinbase API credentials.
        
        Returns:
            CoinbaseCredentials: Object containing API credentials.
        """
        return self._coinbase_credentials
    
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
        if not self._alpaca_credentials:
            log_error("Alpaca credentials not loaded")
            return False
            
        # Validate API keys are not empty
        if not self._alpaca_credentials.api_key or not self._alpaca_credentials.secret_key:
            log_error("API keys cannot be empty")
            return False
            
        # Validate base URL
        if not self._alpaca_credentials.base_url:
            log_error("Base URL cannot be empty")
            return False
            
        return True
    
    def validate_coinbase_config(self) -> bool:
        """
        Validate the Coinbase configuration.
        
        Returns:
            bool: True if Coinbase configuration is valid, False otherwise.
        """
        if not self._coinbase_credentials:
            log_error("Coinbase credentials not loaded")
            return False
            
        # Validate API credentials are not empty
        if not self._coinbase_credentials.api_key:
            log_error("Coinbase API key cannot be empty")
            return False
            
        if not self._coinbase_credentials.api_secret:
            log_error("Coinbase API secret cannot be empty")
            return False
            
        # Validate base URL
        if not self._coinbase_credentials.base_url:
            log_error("Coinbase base URL cannot be empty")
            return False
            
        return True
        
    def validate_trading_pair(self, trading_pair: str) -> bool:
        """
        Validate that a trading pair exists on Coinbase.
        
        Args:
            trading_pair: Trading pair to validate (e.g., 'BTC-USD')
            
        Returns:
            bool: True if trading pair is valid, False otherwise.
        """
        # If we haven't fetched available pairs yet, return True to avoid API call during testing
        if not self._available_trading_pairs:
            return True
            
        return trading_pair in self._available_trading_pairs
        
    def load_available_trading_pairs(self, coinbase_client) -> bool:
        """
        Load available trading pairs from Coinbase.
        
        Args:
            coinbase_client: Initialized CoinbaseClient instance
            
        Returns:
            bool: True if loading was successful, False otherwise.
        """
        try:
            products = coinbase_client.get_products()
            self._available_trading_pairs = [product['id'] for product in products]
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
            
    def toggle_sandbox_mode(self, enable_sandbox: bool) -> bool:
        """
        Toggle between sandbox and live environment.
        
        Args:
            enable_sandbox: True to enable sandbox mode, False for live
            
        Returns:
            bool: True if toggle was successful, False otherwise.
        """
        if not self._coinbase_credentials:
            log_error("Cannot toggle sandbox mode: Coinbase credentials not loaded")
            return False
            
        try:
            self._coinbase_credentials.sandbox = enable_sandbox
            self._coinbase_credentials.update_base_url()  # Update base URL
            log_info(f"Switched to {'sandbox' if enable_sandbox else 'live'} environment")
            return True
        except Exception as e:
            log_error(f"Error toggling sandbox mode: {str(e)}")
            return False