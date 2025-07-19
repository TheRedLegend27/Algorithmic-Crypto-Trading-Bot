"""
Configuration management for the crypto trading bot.
Handles loading environment variables and validating configuration.
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

from bot.utils import log_error


@dataclass
class AlpacaCredentials:
    """Dataclass for storing Alpaca API credentials."""
    api_key: str
    secret_key: str
    base_url: str
    paper_trading: bool


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
        self._trading_settings = TradingSettings()
        self._initialized = True
        
    def load_env_variables(self) -> bool:
        """
        Load environment variables from .env file.
        
        Returns:
            bool: True if loading was successful, False otherwise.
        """
        try:
            load_dotenv()
            
            # Check if required environment variables exist
            required_vars = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_BASE_URL"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                log_error(f"Missing required environment variables: {', '.join(missing_vars)}")
                return False
                
            # Load Alpaca credentials
            self._alpaca_credentials = AlpacaCredentials(
                api_key=os.getenv("ALPACA_API_KEY"),
                secret_key=os.getenv("ALPACA_SECRET_KEY"),
                base_url=os.getenv("ALPACA_BASE_URL"),
                paper_trading=os.getenv("IS_PAPER_TRADING", "True").lower() in ("true", "1", "t")
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
    
    def get_trading_settings(self) -> TradingSettings:
        """
        Get trading settings.
        
        Returns:
            TradingSettings: Object containing trading parameters.
        """
        return self._trading_settings
    
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