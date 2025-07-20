"""
Configuration management for the mock trading environment.
Handles loading simulation parameters and validating configuration.
"""
import os
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from pathlib import Path

from bot.utils import log_error


@dataclass
class ExecutionConfig:
    """Configuration for order execution simulation."""
    slippage_base: float = 0.0001  # 0.01% base slippage
    slippage_impact_factor: float = 0.00001  # Additional slippage per $1000 order size
    execution_delay_min_ms: int = 100  # Minimum execution delay in milliseconds
    execution_delay_max_ms: int = 500  # Maximum execution delay in milliseconds
    market_impact_threshold: float = 1000.0  # Order size threshold for market impact
    enable_partial_fills: bool = True  # Enable partial fill simulation
    partial_fill_probability: float = 0.1  # Probability of partial fills (10%)
    min_fill_percentage: float = 0.5  # Minimum percentage of order filled in partial fills


@dataclass
class MarketConfig:
    """Configuration for market condition simulation."""
    volatility_multiplier: float = 1.0  # Multiplier for volatility-based adjustments
    liquidity_factor: float = 1.0  # Factor affecting order execution in low liquidity
    market_hours_enforcement: bool = True  # Enforce market hours restrictions
    extended_hours_trading: bool = False  # Allow extended hours trading
    gap_simulation_enabled: bool = True  # Enable market gap simulation
    correlation_simulation: bool = False  # Enable symbol correlation simulation


@dataclass
class FeeConfig:
    """Configuration for trading fees and costs."""
    trading_fee_percent: float = 0.001  # 0.1% trading fee
    trading_fee_fixed: float = 0.0  # Fixed fee per trade
    minimum_fee: float = 0.0  # Minimum fee per trade
    maximum_fee: float = 100.0  # Maximum fee per trade


@dataclass
class MockTradingConfig:
    """Main configuration class for mock trading environment."""
    
    # Capital and risk management
    starting_capital: float = 10000.0  # Starting capital in USD
    max_position_size: float = 5000.0  # Maximum position size in USD
    max_daily_loss: float = 1000.0  # Maximum daily loss limit
    
    # Execution configuration
    execution: ExecutionConfig = None
    
    # Market simulation configuration
    market: MarketConfig = None
    
    # Fee configuration
    fees: FeeConfig = None
    
    # Reporting and analytics
    enable_detailed_logging: bool = True
    performance_tracking: bool = True
    save_trade_history: bool = True
    history_retention_days: int = 365
    
    # Environment settings
    simulation_mode: bool = True
    random_seed: Optional[int] = None  # For reproducible simulations
    
    def __post_init__(self):
        """Initialize nested configurations with defaults if not provided."""
        if self.execution is None:
            self.execution = ExecutionConfig()
        if self.market is None:
            self.market = MarketConfig()
        if self.fees is None:
            self.fees = FeeConfig()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'MockTradingConfig':
        """
        Create MockTradingConfig from dictionary.
        
        Args:
            config_dict: Dictionary containing configuration parameters
            
        Returns:
            MockTradingConfig: Configured instance
        """
        # Extract nested configurations
        execution_dict = config_dict.pop('execution', {})
        market_dict = config_dict.pop('market', {})
        fees_dict = config_dict.pop('fees', {})
        
        # Create nested config objects
        execution_config = ExecutionConfig(**execution_dict)
        market_config = MarketConfig(**market_dict)
        fee_config = FeeConfig(**fees_dict)
        
        # Create main config
        return cls(
            execution=execution_config,
            market=market_config,
            fees=fee_config,
            **config_dict
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'MockTradingConfig':
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            MockTradingConfig: Loaded configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
            with open(config_file, 'r') as f:
                config_dict = json.load(f)
            
            return cls.from_dict(config_dict)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dict[str, Any]: Configuration as dictionary
        """
        config_dict = asdict(self)
        return config_dict
    
    def save_to_file(self, config_path: str) -> bool:
        """
        Save configuration to JSON file.
        
        Args:
            config_path: Path where to save configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            config_file = Path(config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            return True
            
        except Exception as e:
            log_error(f"Error saving configuration: {e}")
            return False
    
    def validate_config(self) -> bool:
        """
        Validate the mock trading configuration.
        
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        errors = []
        
        # Validate capital settings
        if self.starting_capital <= 0:
            errors.append("Starting capital must be positive")
        
        if self.max_position_size <= 0:
            errors.append("Maximum position size must be positive")
        
        if self.max_position_size > self.starting_capital:
            errors.append("Maximum position size cannot exceed starting capital")
        
        if self.max_daily_loss <= 0:
            errors.append("Maximum daily loss must be positive")
        
        if self.max_daily_loss > self.starting_capital:
            errors.append("Maximum daily loss cannot exceed starting capital")
        
        # Validate execution configuration
        if self.execution.slippage_base < 0:
            errors.append("Base slippage cannot be negative")
        
        if self.execution.slippage_impact_factor < 0:
            errors.append("Slippage impact factor cannot be negative")
        
        if self.execution.execution_delay_min_ms < 0:
            errors.append("Minimum execution delay cannot be negative")
        
        if self.execution.execution_delay_max_ms < self.execution.execution_delay_min_ms:
            errors.append("Maximum execution delay must be >= minimum execution delay")
        
        if self.execution.market_impact_threshold <= 0:
            errors.append("Market impact threshold must be positive")
        
        if not (0 <= self.execution.partial_fill_probability <= 1):
            errors.append("Partial fill probability must be between 0 and 1")
        
        if not (0 < self.execution.min_fill_percentage <= 1):
            errors.append("Minimum fill percentage must be between 0 and 1")
        
        # Validate market configuration
        if self.market.volatility_multiplier <= 0:
            errors.append("Volatility multiplier must be positive")
        
        if self.market.liquidity_factor <= 0:
            errors.append("Liquidity factor must be positive")
        
        # Validate fee configuration
        if self.fees.trading_fee_percent < 0:
            errors.append("Trading fee percentage cannot be negative")
        
        if self.fees.trading_fee_fixed < 0:
            errors.append("Fixed trading fee cannot be negative")
        
        if self.fees.minimum_fee < 0:
            errors.append("Minimum fee cannot be negative")
        
        if self.fees.maximum_fee < self.fees.minimum_fee:
            errors.append("Maximum fee must be >= minimum fee")
        
        # Validate retention settings
        if self.history_retention_days <= 0:
            errors.append("History retention days must be positive")
        
        # Log errors if any
        if errors:
            for error in errors:
                log_error(f"Configuration validation error: {error}")
            return False
        
        return True
    
    def apply_safe_defaults(self) -> 'MockTradingConfig':
        """
        Apply safe defaults to configuration parameters.
        
        Returns:
            MockTradingConfig: Configuration with safe defaults applied
        """
        # Create a copy to avoid modifying the original
        safe_config = MockTradingConfig(
            starting_capital=max(1000.0, self.starting_capital),
            max_position_size=min(self.max_position_size, self.starting_capital * 0.5),
            max_daily_loss=min(self.max_daily_loss, self.starting_capital * 0.2),
            execution=ExecutionConfig(
                slippage_base=max(0.0, min(0.01, self.execution.slippage_base)),
                slippage_impact_factor=max(0.0, min(0.001, self.execution.slippage_impact_factor)),
                execution_delay_min_ms=max(0, min(5000, self.execution.execution_delay_min_ms)),
                execution_delay_max_ms=max(
                    self.execution.execution_delay_min_ms,
                    min(10000, self.execution.execution_delay_max_ms)
                ),
                market_impact_threshold=max(100.0, self.execution.market_impact_threshold),
                enable_partial_fills=self.execution.enable_partial_fills,
                partial_fill_probability=max(0.0, min(1.0, self.execution.partial_fill_probability)),
                min_fill_percentage=max(0.1, min(1.0, self.execution.min_fill_percentage))
            ),
            market=MarketConfig(
                volatility_multiplier=max(0.1, min(10.0, self.market.volatility_multiplier)),
                liquidity_factor=max(0.1, min(10.0, self.market.liquidity_factor)),
                market_hours_enforcement=self.market.market_hours_enforcement,
                extended_hours_trading=self.market.extended_hours_trading,
                gap_simulation_enabled=self.market.gap_simulation_enabled,
                correlation_simulation=self.market.correlation_simulation
            ),
            fees=FeeConfig(
                trading_fee_percent=max(0.0, min(0.1, self.fees.trading_fee_percent)),
                trading_fee_fixed=max(0.0, self.fees.trading_fee_fixed),
                minimum_fee=max(0.0, self.fees.minimum_fee),
                maximum_fee=max(self.fees.minimum_fee, self.fees.maximum_fee)
            ),
            enable_detailed_logging=self.enable_detailed_logging,
            performance_tracking=self.performance_tracking,
            save_trade_history=self.save_trade_history,
            history_retention_days=max(1, self.history_retention_days),
            simulation_mode=True,  # Always True for mock trading
            random_seed=self.random_seed
        )
        
        return safe_config


def load_mock_config(config_path: Optional[str] = None) -> MockTradingConfig:
    """
    Load mock trading configuration with fallback to defaults.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        MockTradingConfig: Loaded and validated configuration
    """
    try:
        if config_path and os.path.exists(config_path):
            config = MockTradingConfig.from_file(config_path)
        else:
            # Use default configuration
            config = MockTradingConfig()
        
        # Validate configuration
        if not config.validate_config():
            log_error("Configuration validation failed, applying safe defaults")
            config = config.apply_safe_defaults()
        
        return config
        
    except Exception as e:
        log_error(f"Error loading mock configuration: {e}")
        log_error("Using default configuration with safe defaults")
        return MockTradingConfig().apply_safe_defaults()


def create_default_config_file(config_path: str) -> bool:
    """
    Create a default configuration file.
    
    Args:
        config_path: Path where to create the configuration file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        default_config = MockTradingConfig()
        return default_config.save_to_file(config_path)
    except Exception as e:
        log_error(f"Error creating default configuration file: {e}")
        return False