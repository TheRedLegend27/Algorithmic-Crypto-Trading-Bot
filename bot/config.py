"""
Configuration management for the crypto trading bot.
Handles loading environment variables and validating configuration.
"""
import os
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from bot.utils import log_error, log_info


@dataclass
class KrakenCredentials:
    """Dataclass for storing Kraken API credentials."""
    api_key: str
    api_secret: str
    base_url: str = "https://api.kraken.com"
    
    def validate(self) -> bool:
        """Validate Kraken credentials."""
        if not self.api_key or not self.api_secret:
            return False
        if not self.base_url:
            return False
        return True


@dataclass
class KrakenTradingPair:
    """Enhanced trading pair configuration for Kraken."""
    symbol: str  # Kraken symbol (e.g., 'XBTUSD', 'ETHUSD')
    base_currency: str  # Base currency (e.g., 'XBT', 'ETH')
    quote_currency: str  # Quote currency (e.g., 'USD', 'EUR')
    min_order_size: float  # Minimum order size
    price_precision: int  # Price decimal precision
    size_precision: int  # Size decimal precision
    maker_fee: float = 0.0016  # Default Kraken maker fee (0.16%)
    taker_fee: float = 0.0026  # Default Kraken taker fee (0.26%)
    enabled: bool = True  # Whether trading is enabled for this pair
    
    def validate(self) -> bool:
        """Validate trading pair configuration."""
        if not self.symbol or not self.base_currency or not self.quote_currency:
            return False
        if self.min_order_size <= 0:
            return False
        if self.price_precision < 0 or self.size_precision < 0:
            return False
        if self.maker_fee < 0 or self.taker_fee < 0:
            return False
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KrakenTradingPair':
        """Create KrakenTradingPair from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert KrakenTradingPair to dictionary."""
        return {
            'symbol': self.symbol,
            'base_currency': self.base_currency,
            'quote_currency': self.quote_currency,
            'min_order_size': self.min_order_size,
            'price_precision': self.price_precision,
            'size_precision': self.size_precision,
            'maker_fee': self.maker_fee,
            'taker_fee': self.taker_fee,
            'enabled': self.enabled
        }


@dataclass
class StrategyConfig:
    """Configuration for enhanced trading strategies."""
    # Strategy weights (must sum to 1.0)
    momentum_weight: float = 0.3
    volatility_weight: float = 0.2
    volume_weight: float = 0.2
    bollinger_weight: float = 0.15
    macd_weight: float = 0.15
    
    # Strategy parameters
    momentum_lookback_periods: int = 14
    volatility_lookback_periods: int = 20
    volume_lookback_periods: int = 20
    bollinger_periods: int = 20
    bollinger_std_dev: float = 2.0
    macd_fast_period: int = 12
    macd_slow_period: int = 26
    macd_signal_period: int = 9
    
    # Multi-timeframe analysis
    enable_multi_timeframe: bool = True
    primary_timeframe: str = "1h"  # Primary trading timeframe
    confirmation_timeframe: str = "4h"  # Confirmation timeframe
    
    # Signal thresholds
    min_signal_strength: float = 0.6  # Minimum signal strength to trade
    max_signal_age_minutes: int = 5  # Maximum age of signal in minutes
    
    def validate(self) -> bool:
        """Validate strategy configuration."""
        # Check weights sum to approximately 1.0
        total_weight = (self.momentum_weight + self.volatility_weight + 
                       self.volume_weight + self.bollinger_weight + self.macd_weight)
        if abs(total_weight - 1.0) > 0.01:
            return False
        
        # Check all weights are non-negative
        weights = [self.momentum_weight, self.volatility_weight, self.volume_weight,
                  self.bollinger_weight, self.macd_weight]
        if any(w < 0 for w in weights):
            return False
        
        # Check lookback periods are positive
        periods = [self.momentum_lookback_periods, self.volatility_lookback_periods,
                  self.volume_lookback_periods, self.bollinger_periods]
        if any(p <= 0 for p in periods):
            return False
        
        # Check MACD parameters
        if (self.macd_fast_period >= self.macd_slow_period or 
            self.macd_signal_period <= 0):
            return False
        
        # Check signal parameters
        if (self.min_signal_strength < 0 or self.min_signal_strength > 1 or
            self.max_signal_age_minutes <= 0):
            return False
        
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyConfig':
        """Create StrategyConfig from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert StrategyConfig to dictionary."""
        return {
            'momentum_weight': self.momentum_weight,
            'volatility_weight': self.volatility_weight,
            'volume_weight': self.volume_weight,
            'bollinger_weight': self.bollinger_weight,
            'macd_weight': self.macd_weight,
            'momentum_lookback_periods': self.momentum_lookback_periods,
            'volatility_lookback_periods': self.volatility_lookback_periods,
            'volume_lookback_periods': self.volume_lookback_periods,
            'bollinger_periods': self.bollinger_periods,
            'bollinger_std_dev': self.bollinger_std_dev,
            'macd_fast_period': self.macd_fast_period,
            'macd_slow_period': self.macd_slow_period,
            'macd_signal_period': self.macd_signal_period,
            'enable_multi_timeframe': self.enable_multi_timeframe,
            'primary_timeframe': self.primary_timeframe,
            'confirmation_timeframe': self.confirmation_timeframe,
            'min_signal_strength': self.min_signal_strength,
            'max_signal_age_minutes': self.max_signal_age_minutes
        }


@dataclass
class RiskConfig:
    """Configuration for enhanced risk management."""
    # Position sizing
    default_trade_amount_usd: float = 100.0
    max_position_per_pair_usd: float = 1000.0
    max_total_position_usd: float = 5000.0
    risk_per_trade_pct: float = 0.02  # 2% of portfolio per trade
    
    # Portfolio limits
    max_open_positions: int = 10
    max_daily_trades: int = 50
    max_correlation_exposure: float = 0.7  # Max correlation between positions
    
    # Stop loss and take profit
    enable_stop_loss: bool = True
    enable_take_profit: bool = True
    default_stop_loss_pct: float = 0.03  # 3%
    default_take_profit_pct: float = 0.06  # 6%
    trailing_stop_enabled: bool = True
    trailing_stop_distance_pct: float = 0.02  # 2%
    
    # Drawdown protection
    max_daily_loss_pct: float = 0.05  # 5% max daily loss
    max_weekly_loss_pct: float = 0.15  # 15% max weekly loss
    emergency_stop_loss_pct: float = 0.20  # 20% emergency stop
    
    # Volatility adjustments
    enable_volatility_adjustment: bool = True
    volatility_lookback_periods: int = 20
    max_volatility_reduction: float = 0.5  # Reduce position by up to 50%
    high_volatility_threshold: float = 0.05  # 5% daily volatility threshold
    
    def validate(self) -> bool:
        """Validate risk configuration."""
        # Check amounts are positive
        amounts = [self.default_trade_amount_usd, self.max_position_per_pair_usd,
                  self.max_total_position_usd]
        if any(a <= 0 for a in amounts):
            return False
        
        # Check percentages are valid
        percentages = [self.risk_per_trade_pct, self.default_stop_loss_pct,
                      self.default_take_profit_pct, self.trailing_stop_distance_pct,
                      self.max_daily_loss_pct, self.max_weekly_loss_pct,
                      self.emergency_stop_loss_pct, self.max_volatility_reduction,
                      self.high_volatility_threshold]
        if any(p < 0 or p > 1 for p in percentages):
            return False
        
        # Check position limits
        if (self.max_open_positions <= 0 or self.max_daily_trades <= 0 or
            self.volatility_lookback_periods <= 0):
            return False
        
        # Check correlation exposure
        if self.max_correlation_exposure < 0 or self.max_correlation_exposure > 1:
            return False
        
        # Check logical relationships
        if self.max_position_per_pair_usd > self.max_total_position_usd:
            return False
        
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskConfig':
        """Create RiskConfig from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert RiskConfig to dictionary."""
        return {
            'default_trade_amount_usd': self.default_trade_amount_usd,
            'max_position_per_pair_usd': self.max_position_per_pair_usd,
            'max_total_position_usd': self.max_total_position_usd,
            'risk_per_trade_pct': self.risk_per_trade_pct,
            'max_open_positions': self.max_open_positions,
            'max_daily_trades': self.max_daily_trades,
            'max_correlation_exposure': self.max_correlation_exposure,
            'enable_stop_loss': self.enable_stop_loss,
            'enable_take_profit': self.enable_take_profit,
            'default_stop_loss_pct': self.default_stop_loss_pct,
            'default_take_profit_pct': self.default_take_profit_pct,
            'trailing_stop_enabled': self.trailing_stop_enabled,
            'trailing_stop_distance_pct': self.trailing_stop_distance_pct,
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'max_weekly_loss_pct': self.max_weekly_loss_pct,
            'emergency_stop_loss_pct': self.emergency_stop_loss_pct,
            'enable_volatility_adjustment': self.enable_volatility_adjustment,
            'volatility_lookback_periods': self.volatility_lookback_periods,
            'max_volatility_reduction': self.max_volatility_reduction,
            'high_volatility_threshold': self.high_volatility_threshold
        }


@dataclass
class EnhancedTradingConfig:
    """Enhanced configuration for multi-pair crypto trading."""
    # Trading pairs configuration
    trading_pairs: List[KrakenTradingPair] = field(default_factory=list)
    
    # Strategy configuration
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    
    # Risk management configuration
    risk: RiskConfig = field(default_factory=RiskConfig)
    
    # System configuration
    enable_websocket: bool = True
    websocket_reconnect_attempts: int = 5
    websocket_reconnect_delay: int = 5  # seconds
    
    # Logging configuration
    log_level: str = "INFO"
    log_trades: bool = True
    log_signals: bool = True
    log_performance: bool = True
    
    # Dashboard configuration
    enable_dashboard: bool = True
    dashboard_host: str = "localhost"
    dashboard_port: int = 8080
    
    # Alert configuration
    enable_alerts: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["console"])
    
    def __post_init__(self):
        """Initialize default trading pairs if none provided."""
        if not self.trading_pairs:
            self.trading_pairs = self._get_default_trading_pairs()
    
    def _get_default_trading_pairs(self) -> List[KrakenTradingPair]:
        """Get default trading pairs configuration."""
        return [
            KrakenTradingPair(
                symbol="XBTUSD",
                base_currency="XBT",
                quote_currency="USD",
                min_order_size=0.0001,
                price_precision=1,
                size_precision=8
            ),
            KrakenTradingPair(
                symbol="ETHUSD",
                base_currency="ETH",
                quote_currency="USD",
                min_order_size=0.001,
                price_precision=2,
                size_precision=6
            )
        ]
    
    def validate(self) -> bool:
        """Validate the entire configuration."""
        # Validate trading pairs
        if not self.trading_pairs:
            log_error("No trading pairs configured")
            return False
        
        for pair in self.trading_pairs:
            if not pair.validate():
                log_error(f"Invalid trading pair configuration: {pair.symbol}")
                return False
        
        # Validate strategy configuration
        if not self.strategy.validate():
            log_error("Invalid strategy configuration")
            return False
        
        # Validate risk configuration
        if not self.risk.validate():
            log_error("Invalid risk configuration")
            return False
        
        # Validate system settings
        if self.websocket_reconnect_attempts <= 0 or self.websocket_reconnect_delay <= 0:
            log_error("Invalid websocket configuration")
            return False
        
        if self.dashboard_port <= 0 or self.dashboard_port > 65535:
            log_error("Invalid dashboard port")
            return False
        
        return True
    
    def get_enabled_pairs(self) -> List[KrakenTradingPair]:
        """Get list of enabled trading pairs."""
        return [pair for pair in self.trading_pairs if pair.enabled]
    
    def get_pair_by_symbol(self, symbol: str) -> Optional[KrakenTradingPair]:
        """Get trading pair by symbol."""
        for pair in self.trading_pairs:
            if pair.symbol == symbol:
                return pair
        return None
    
    def add_trading_pair(self, pair: KrakenTradingPair) -> bool:
        """Add a new trading pair."""
        if not pair.validate():
            log_error(f"Invalid trading pair: {pair.symbol}")
            return False
        
        # Check if pair already exists
        if self.get_pair_by_symbol(pair.symbol):
            log_error(f"Trading pair already exists: {pair.symbol}")
            return False
        
        self.trading_pairs.append(pair)
        return True
    
    def remove_trading_pair(self, symbol: str) -> bool:
        """Remove a trading pair by symbol."""
        for i, pair in enumerate(self.trading_pairs):
            if pair.symbol == symbol:
                del self.trading_pairs[i]
                return True
        return False
    
    def update_trading_pair(self, symbol: str, updates: Dict[str, Any]) -> bool:
        """Update a trading pair configuration."""
        pair = self.get_pair_by_symbol(symbol)
        if not pair:
            log_error(f"Trading pair not found: {symbol}")
            return False
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(pair, key):
                setattr(pair, key, value)
            else:
                log_error(f"Unknown trading pair attribute: {key}")
                return False
        
        # Validate updated pair
        if not pair.validate():
            log_error(f"Invalid trading pair after update: {symbol}")
            return False
        
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedTradingConfig':
        """Create EnhancedTradingConfig from dictionary."""
        # Handle trading pairs
        trading_pairs = []
        if 'trading_pairs' in data:
            for pair_data in data['trading_pairs']:
                trading_pairs.append(KrakenTradingPair.from_dict(pair_data))
        
        # Handle strategy config
        strategy = StrategyConfig()
        if 'strategy' in data:
            strategy = StrategyConfig.from_dict(data['strategy'])
        
        # Handle risk config
        risk = RiskConfig()
        if 'risk' in data:
            risk = RiskConfig.from_dict(data['risk'])
        
        # Create config with parsed components
        config_data = data.copy()
        config_data['trading_pairs'] = trading_pairs
        config_data['strategy'] = strategy
        config_data['risk'] = risk
        
        return cls(**config_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert EnhancedTradingConfig to dictionary."""
        return {
            'trading_pairs': [pair.to_dict() for pair in self.trading_pairs],
            'strategy': self.strategy.to_dict(),
            'risk': self.risk.to_dict(),
            'enable_websocket': self.enable_websocket,
            'websocket_reconnect_attempts': self.websocket_reconnect_attempts,
            'websocket_reconnect_delay': self.websocket_reconnect_delay,
            'log_level': self.log_level,
            'log_trades': self.log_trades,
            'log_signals': self.log_signals,
            'log_performance': self.log_performance,
            'enable_dashboard': self.enable_dashboard,
            'dashboard_host': self.dashboard_host,
            'dashboard_port': self.dashboard_port,
            'enable_alerts': self.enable_alerts,
            'alert_channels': self.alert_channels
        }
    
    def save_to_file(self, file_path: str) -> bool:
        """Save configuration to JSON file."""
        try:
            with open(file_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            log_error(f"Error saving configuration to file: {str(e)}")
            return False
    
    @classmethod
    def load_from_file(cls, file_path: str) -> Optional['EnhancedTradingConfig']:
        """Load configuration from JSON file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            log_error(f"Error loading configuration from file: {str(e)}")
            return None


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
    """Singleton class for managing enhanced configuration."""
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
        self._trading_settings = TradingSettings()  # Keep for backward compatibility
        self._enhanced_config = EnhancedTradingConfig()
        self._available_trading_pairs = []
        self._pair_metadata = {}  # Store metadata for each trading pair
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
            api_key = os.getenv("KRAKEN_API_KEY", "").strip()
            api_secret = os.getenv("KRAKEN_API_SECRET", "").strip()
            base_url = os.getenv("KRAKEN_BASE_URL", "https://api.kraken.com").strip()
            
            self._kraken_credentials = KrakenCredentials(
                api_key=api_key,
                api_secret=api_secret,
                base_url=base_url
            )
            
            # Load optional configuration overrides from environment
            self._load_config_overrides_from_env()
            
            return True
            
        except Exception as e:
            log_error(f"Error loading environment variables: {str(e)}")
            return False
    
    def _load_config_overrides_from_env(self):
        """Load configuration overrides from environment variables."""
        try:
            # Risk configuration overrides
            if os.getenv("DEFAULT_TRADE_AMOUNT_USD"):
                self._enhanced_config.risk.default_trade_amount_usd = float(os.getenv("DEFAULT_TRADE_AMOUNT_USD"))
            
            if os.getenv("MAX_POSITION_PER_PAIR_USD"):
                self._enhanced_config.risk.max_position_per_pair_usd = float(os.getenv("MAX_POSITION_PER_PAIR_USD"))
            
            if os.getenv("MAX_TOTAL_POSITION_USD"):
                self._enhanced_config.risk.max_total_position_usd = float(os.getenv("MAX_TOTAL_POSITION_USD"))
            
            if os.getenv("RISK_PER_TRADE_PCT"):
                self._enhanced_config.risk.risk_per_trade_pct = float(os.getenv("RISK_PER_TRADE_PCT"))
            
            if os.getenv("MAX_DAILY_TRADES"):
                self._enhanced_config.risk.max_daily_trades = int(os.getenv("MAX_DAILY_TRADES"))
            
            # System configuration overrides
            if os.getenv("ENABLE_WEBSOCKET"):
                self._enhanced_config.enable_websocket = os.getenv("ENABLE_WEBSOCKET").lower() == "true"
            
            if os.getenv("ENABLE_DASHBOARD"):
                self._enhanced_config.enable_dashboard = os.getenv("ENABLE_DASHBOARD").lower() == "true"
            
            if os.getenv("DASHBOARD_PORT"):
                self._enhanced_config.dashboard_port = int(os.getenv("DASHBOARD_PORT"))
            
            if os.getenv("LOG_LEVEL"):
                self._enhanced_config.log_level = os.getenv("LOG_LEVEL").upper()
            
        except Exception as e:
            log_error(f"Error loading configuration overrides from environment: {str(e)}")
    
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
    
    def get_crypto_trading_settings(self) -> 'CryptoTradingSettings':
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
        # Validate Kraken credentials
        if not self._kraken_credentials:
            log_error("Kraken credentials not loaded")
            return False
            
        if not self._kraken_credentials.validate():
            log_error("Invalid Kraken credentials")
            return False
        
        # Validate enhanced configuration
        if not self._enhanced_config.validate():
            log_error("Invalid enhanced trading configuration")
            return False
            
        return True
        
    def get_enhanced_config(self) -> EnhancedTradingConfig:
        """
        Get enhanced trading configuration.
        
        Returns:
            EnhancedTradingConfig: Enhanced configuration object.
        """
        return self._enhanced_config
    
    def update_enhanced_config(self, config: EnhancedTradingConfig) -> bool:
        """
        Update enhanced trading configuration.
        
        Args:
            config: New enhanced configuration
            
        Returns:
            bool: True if update was successful, False otherwise.
        """
        if not config.validate():
            log_error("Invalid enhanced configuration")
            return False
        
        self._enhanced_config = config
        return True
    
    def load_enhanced_config_from_file(self, file_path: str) -> bool:
        """
        Load enhanced configuration from JSON file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            bool: True if loading was successful, False otherwise.
        """
        config = EnhancedTradingConfig.load_from_file(file_path)
        if config is None:
            return False
        
        return self.update_enhanced_config(config)
    
    def save_enhanced_config_to_file(self, file_path: str) -> bool:
        """
        Save enhanced configuration to JSON file.
        
        Args:
            file_path: Path to save configuration file
            
        Returns:
            bool: True if saving was successful, False otherwise.
        """
        return self._enhanced_config.save_to_file(file_path)
    
    def validate_trading_pair(self, trading_pair: str) -> bool:
        """
        Validate that a trading pair exists on Kraken.
        
        Args:
            trading_pair: Trading pair to validate (e.g., 'XBTUSD')
            
        Returns:
            bool: True if trading pair is valid, False otherwise.
        """
        # Check if pair is in our configuration
        if self._enhanced_config.get_pair_by_symbol(trading_pair):
            return True
        
        # If we haven't fetched available pairs yet, return True to avoid API call during testing
        if not self._available_trading_pairs:
            return True
            
        return trading_pair in self._available_trading_pairs
    
    def load_available_trading_pairs(self, kraken_client) -> bool:
        """
        Load available trading pairs from Kraken and update metadata.
        
        Args:
            kraken_client: Initialized KrakenClient instance
            
        Returns:
            bool: True if loading was successful, False otherwise.
        """
        try:
            asset_pairs = kraken_client.get_asset_pairs()
            self._available_trading_pairs = list(asset_pairs.keys())
            
            # Store metadata for each pair
            self._pair_metadata = {}
            for symbol, pair_info in asset_pairs.items():
                self._pair_metadata[symbol] = {
                    'base': pair_info.get('base', ''),
                    'quote': pair_info.get('quote', ''),
                    'pair_decimals': pair_info.get('pair_decimals', 8),
                    'lot_decimals': pair_info.get('lot_decimals', 8),
                    'lot_multiplier': pair_info.get('lot_multiplier', 1),
                    'leverage_buy': pair_info.get('leverage_buy', []),
                    'leverage_sell': pair_info.get('leverage_sell', []),
                    'fees': pair_info.get('fees', []),
                    'fees_maker': pair_info.get('fees_maker', []),
                    'fee_volume_currency': pair_info.get('fee_volume_currency', ''),
                    'margin_call': pair_info.get('margin_call', 80),
                    'margin_stop': pair_info.get('margin_stop', 40),
                    'ordermin': pair_info.get('ordermin', '0')
                }
            
            log_info(f"Loaded {len(self._available_trading_pairs)} trading pairs from Kraken")
            return True
            
        except Exception as e:
            log_error(f"Error loading available trading pairs: {str(e)}")
            return False
    
    def get_pair_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a trading pair.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dict containing pair metadata or None if not found.
        """
        return self._pair_metadata.get(symbol)
    
    def update_trading_pair_from_metadata(self, symbol: str) -> bool:
        """
        Update trading pair configuration from Kraken metadata.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            bool: True if update was successful, False otherwise.
        """
        metadata = self.get_pair_metadata(symbol)
        if not metadata:
            log_error(f"No metadata found for trading pair: {symbol}")
            return False
        
        # Get existing pair or create new one
        pair = self._enhanced_config.get_pair_by_symbol(symbol)
        if not pair:
            pair = KrakenTradingPair(
                symbol=symbol,
                base_currency=metadata['base'],
                quote_currency=metadata['quote'],
                min_order_size=float(metadata.get('ordermin', '0.001')),
                price_precision=metadata.get('pair_decimals', 8),
                size_precision=metadata.get('lot_decimals', 8)
            )
            return self._enhanced_config.add_trading_pair(pair)
        else:
            # Update existing pair with metadata
            updates = {
                'base_currency': metadata['base'],
                'quote_currency': metadata['quote'],
                'min_order_size': float(metadata.get('ordermin', '0.001')),
                'price_precision': metadata.get('pair_decimals', 8),
                'size_precision': metadata.get('lot_decimals', 8)
            }
            return self._enhanced_config.update_trading_pair(symbol, updates)
    
    def get_available_trading_pairs(self) -> List[str]:
        """
        Get list of available trading pairs from Kraken.
        
        Returns:
            List of trading pair symbols.
        """
        return self._available_trading_pairs.copy()
    
    def get_configured_trading_pairs(self) -> List[KrakenTradingPair]:
        """
        Get list of configured trading pairs.
        
        Returns:
            List of KrakenTradingPair objects.
        """
        return self._enhanced_config.trading_pairs.copy()
    
    def get_enabled_trading_pairs(self) -> List[KrakenTradingPair]:
        """
        Get list of enabled trading pairs.
        
        Returns:
            List of enabled KrakenTradingPair objects.
        """
        return self._enhanced_config.get_enabled_pairs()
    
    def add_trading_pair(self, pair: KrakenTradingPair) -> bool:
        """
        Add a new trading pair to configuration.
        
        Args:
            pair: KrakenTradingPair to add
            
        Returns:
            bool: True if successful, False otherwise.
        """
        return self._enhanced_config.add_trading_pair(pair)
    
    def remove_trading_pair(self, symbol: str) -> bool:
        """
        Remove a trading pair from configuration.
        
        Args:
            symbol: Trading pair symbol to remove
            
        Returns:
            bool: True if successful, False otherwise.
        """
        return self._enhanced_config.remove_trading_pair(symbol)
    
    def update_trading_pair(self, symbol: str, updates: Dict[str, Any]) -> bool:
        """
        Update a trading pair configuration.
        
        Args:
            symbol: Trading pair symbol to update
            updates: Dictionary of updates to apply
            
        Returns:
            bool: True if successful, False otherwise.
        """
        return self._enhanced_config.update_trading_pair(symbol, updates)
    
    def apply_default_values(self) -> bool:
        """
        Apply safe default values to configuration.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Ensure we have at least one trading pair
            if not self._enhanced_config.trading_pairs:
                self._enhanced_config.trading_pairs = self._enhanced_config._get_default_trading_pairs()
            
            # Apply safe defaults to risk configuration
            risk = self._enhanced_config.risk
            if risk.default_trade_amount_usd <= 0:
                risk.default_trade_amount_usd = 100.0
            
            if risk.max_position_per_pair_usd <= 0:
                risk.max_position_per_pair_usd = 1000.0
            
            if risk.max_total_position_usd <= 0:
                risk.max_total_position_usd = 5000.0
            
            # Ensure max_position_per_pair_usd doesn't exceed max_total_position_usd
            if risk.max_position_per_pair_usd > risk.max_total_position_usd:
                risk.max_position_per_pair_usd = risk.max_total_position_usd * 0.5
            
            # Apply safe defaults to strategy configuration
            strategy = self._enhanced_config.strategy
            total_weight = (strategy.momentum_weight + strategy.volatility_weight + 
                           strategy.volume_weight + strategy.bollinger_weight + strategy.macd_weight)
            
            if abs(total_weight - 1.0) > 0.01:
                # Reset to default weights
                strategy.momentum_weight = 0.3
                strategy.volatility_weight = 0.2
                strategy.volume_weight = 0.2
                strategy.bollinger_weight = 0.15
                strategy.macd_weight = 0.15
            
            return True
            
        except Exception as e:
            log_error(f"Error applying default values: {str(e)}")
            return False
    
    # Keep backward compatibility methods
    def get_crypto_trading_settings(self) -> 'CryptoTradingSettings':
        """
        Get crypto trading settings (backward compatibility).
        
        Returns:
            CryptoTradingSettings: Legacy crypto trading settings.
        """
        # Create legacy settings from enhanced config for backward compatibility
        if self._enhanced_config.trading_pairs:
            first_pair = self._enhanced_config.trading_pairs[0]
            return CryptoTradingSettings(
                trading_pair=f"{first_pair.base_currency}-{first_pair.quote_currency}",
                base_currency=first_pair.base_currency,
                quote_currency=first_pair.quote_currency,
                trade_amount_usd=self._enhanced_config.risk.default_trade_amount_usd,
                max_position_usd=self._enhanced_config.risk.max_position_per_pair_usd,
                min_order_size=first_pair.min_order_size,
                price_precision=first_pair.price_precision,
                size_precision=first_pair.size_precision,
                maker_fee_rate=first_pair.maker_fee,
                taker_fee_rate=first_pair.taker_fee,
                max_risk_per_trade_pct=self._enhanced_config.risk.risk_per_trade_pct,
                max_daily_loss_pct=self._enhanced_config.risk.max_daily_loss_pct,
                max_open_positions=self._enhanced_config.risk.max_open_positions,
                stop_loss_pct=self._enhanced_config.risk.default_stop_loss_pct,
                take_profit_pct=self._enhanced_config.risk.default_take_profit_pct,
                volatility_adjustment=self._enhanced_config.risk.enable_volatility_adjustment,
                max_volatility_multiplier=self._enhanced_config.risk.max_volatility_reduction
            )
        else:
            return CryptoTradingSettings()
    
    def update_crypto_trading_settings(self, settings: dict) -> bool:
        """
        Update crypto trading settings (backward compatibility).
        
        Args:
            settings: Dictionary of settings to update
            
        Returns:
            bool: True if update was successful, False otherwise.
        """
        try:
            # Map legacy settings to enhanced config
            risk_mappings = {
                'trade_amount_usd': 'default_trade_amount_usd',
                'max_position_usd': 'max_position_per_pair_usd',
                'max_risk_per_trade_pct': 'risk_per_trade_pct',
                'max_daily_loss_pct': 'max_daily_loss_pct',
                'max_open_positions': 'max_open_positions',
                'stop_loss_pct': 'default_stop_loss_pct',
                'take_profit_pct': 'default_take_profit_pct'
            }
            
            for legacy_key, value in settings.items():
                if legacy_key in risk_mappings:
                    enhanced_key = risk_mappings[legacy_key]
                    if hasattr(self._enhanced_config.risk, enhanced_key):
                        setattr(self._enhanced_config.risk, enhanced_key, value)
                elif legacy_key == 'volatility_adjustment':
                    self._enhanced_config.risk.enable_volatility_adjustment = value
                elif legacy_key == 'max_volatility_multiplier':
                    self._enhanced_config.risk.max_volatility_reduction = value
                else:
                    log_error(f"Unknown crypto trading setting: {legacy_key}")
            
            return True
        except Exception as e:
            log_error(f"Error updating crypto trading settings: {str(e)}")
            return False


# Legacy class for backward compatibility
@dataclass
class CryptoTradingSettings:
    """Legacy dataclass for storing crypto-specific trading parameters."""
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
            
