"""
Configuration validation utilities for mock trading environment.
Provides comprehensive validation functions with error handling and safe defaults.
"""
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from .mock_config import MockTradingConfig, ExecutionConfig, MarketConfig, FeeConfig
from bot.utils import log_error


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0


class ConfigValidator:
    """Comprehensive configuration validator for mock trading environment."""
    
    @staticmethod
    def validate_capital_settings(config: MockTradingConfig) -> ValidationResult:
        """
        Validate capital and risk management settings.
        
        Args:
            config: Configuration to validate
            
        Returns:
            ValidationResult: Validation results
        """
        errors = []
        warnings = []
        
        # Starting capital validation
        if config.starting_capital <= 0:
            errors.append("Starting capital must be positive")
        elif config.starting_capital < 1000:
            warnings.append("Starting capital below $1000 may limit trading opportunities")
        
        # Position size validation
        if config.max_position_size <= 0:
            errors.append("Maximum position size must be positive")
        elif config.max_position_size > config.starting_capital:
            errors.append("Maximum position size cannot exceed starting capital")
        elif config.max_position_size > config.starting_capital * 0.8:
            warnings.append("Maximum position size > 80% of capital increases risk")
        
        # Daily loss validation
        if config.max_daily_loss <= 0:
            errors.append("Maximum daily loss must be positive")
        elif config.max_daily_loss > config.starting_capital:
            errors.append("Maximum daily loss cannot exceed starting capital")
        elif config.max_daily_loss > config.starting_capital * 0.3:
            warnings.append("Maximum daily loss > 30% of capital is very aggressive")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    @staticmethod
    def validate_execution_settings(execution: ExecutionConfig) -> ValidationResult:
        """
        Validate execution configuration settings.
        
        Args:
            execution: Execution configuration to validate
            
        Returns:
            ValidationResult: Validation results
        """
        errors = []
        warnings = []
        
        # Slippage validation
        if execution.slippage_base < 0:
            errors.append("Base slippage cannot be negative")
        elif execution.slippage_base > 0.01:  # 1%
            warnings.append("Base slippage > 1% is unusually high")
        
        if execution.slippage_impact_factor < 0:
            errors.append("Slippage impact factor cannot be negative")
        elif execution.slippage_impact_factor > 0.001:
            warnings.append("Slippage impact factor > 0.1% per $1000 is high")
        
        # Execution delay validation
        if execution.execution_delay_min_ms < 0:
            errors.append("Minimum execution delay cannot be negative")
        
        if execution.execution_delay_max_ms < execution.execution_delay_min_ms:
            errors.append("Maximum execution delay must be >= minimum execution delay")
        elif execution.execution_delay_max_ms > 5000:  # 5 seconds
            warnings.append("Maximum execution delay > 5 seconds is unrealistic")
        
        # Market impact validation
        if execution.market_impact_threshold <= 0:
            errors.append("Market impact threshold must be positive")
        elif execution.market_impact_threshold < 100:
            warnings.append("Market impact threshold < $100 may cause excessive impact simulation")
        
        # Partial fill validation
        if not (0 <= execution.partial_fill_probability <= 1):
            errors.append("Partial fill probability must be between 0 and 1")
        elif execution.partial_fill_probability > 0.5:
            warnings.append("Partial fill probability > 50% is unusually high")
        
        if not (0 < execution.min_fill_percentage <= 1):
            errors.append("Minimum fill percentage must be between 0 and 1")
        elif execution.min_fill_percentage < 0.1:
            warnings.append("Minimum fill percentage < 10% may cause excessive partial fills")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    @staticmethod
    def validate_market_settings(market: MarketConfig) -> ValidationResult:
        """
        Validate market simulation settings.
        
        Args:
            market: Market configuration to validate
            
        Returns:
            ValidationResult: Validation results
        """
        errors = []
        warnings = []
        
        # Volatility multiplier validation
        if market.volatility_multiplier <= 0:
            errors.append("Volatility multiplier must be positive")
        elif market.volatility_multiplier > 5.0:
            warnings.append("Volatility multiplier > 5.0 creates unrealistic conditions")
        elif market.volatility_multiplier < 0.1:
            warnings.append("Volatility multiplier < 0.1 may underestimate market volatility")
        
        # Liquidity factor validation
        if market.liquidity_factor <= 0:
            errors.append("Liquidity factor must be positive")
        elif market.liquidity_factor > 5.0:
            warnings.append("Liquidity factor > 5.0 may create unrealistic liquidity conditions")
        elif market.liquidity_factor < 0.1:
            warnings.append("Liquidity factor < 0.1 simulates extremely low liquidity")
        
        # Market hours configuration warnings
        if not market.market_hours_enforcement and not market.extended_hours_trading:
            warnings.append("No market hours enforcement may not reflect real trading conditions")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    @staticmethod
    def validate_fee_settings(fees: FeeConfig) -> ValidationResult:
        """
        Validate fee configuration settings.
        
        Args:
            fees: Fee configuration to validate
            
        Returns:
            ValidationResult: Validation results
        """
        errors = []
        warnings = []
        
        # Fee percentage validation
        if fees.trading_fee_percent < 0:
            errors.append("Trading fee percentage cannot be negative")
        elif fees.trading_fee_percent > 0.1:  # 10%
            warnings.append("Trading fee percentage > 10% is extremely high")
        elif fees.trading_fee_percent == 0 and fees.trading_fee_fixed == 0:
            warnings.append("Zero trading fees may not reflect real trading costs")
        
        # Fixed fee validation
        if fees.trading_fee_fixed < 0:
            errors.append("Fixed trading fee cannot be negative")
        elif fees.trading_fee_fixed > 50:
            warnings.append("Fixed trading fee > $50 is unusually high")
        
        # Fee limits validation
        if fees.minimum_fee < 0:
            errors.append("Minimum fee cannot be negative")
        
        if fees.maximum_fee < fees.minimum_fee:
            errors.append("Maximum fee must be >= minimum fee")
        elif fees.maximum_fee > 1000:
            warnings.append("Maximum fee > $1000 is extremely high")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    @staticmethod
    def validate_general_settings(config: MockTradingConfig) -> ValidationResult:
        """
        Validate general configuration settings.
        
        Args:
            config: Configuration to validate
            
        Returns:
            ValidationResult: Validation results
        """
        errors = []
        warnings = []
        
        # History retention validation
        if config.history_retention_days <= 0:
            errors.append("History retention days must be positive")
        elif config.history_retention_days < 30:
            warnings.append("History retention < 30 days may limit analysis capabilities")
        elif config.history_retention_days > 1095:  # 3 years
            warnings.append("History retention > 3 years may consume excessive storage")
        
        # Simulation mode validation
        if not config.simulation_mode:
            errors.append("Mock trading must always be in simulation mode")
        
        # Random seed validation
        if config.random_seed is not None and config.random_seed < 0:
            warnings.append("Negative random seed may cause unexpected behavior")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    @classmethod
    def validate_full_config(cls, config: MockTradingConfig) -> ValidationResult:
        """
        Perform comprehensive validation of the entire configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            ValidationResult: Combined validation results
        """
        all_errors = []
        all_warnings = []
        
        # Validate each section
        validations = [
            cls.validate_capital_settings(config),
            cls.validate_execution_settings(config.execution),
            cls.validate_market_settings(config.market),
            cls.validate_fee_settings(config.fees),
            cls.validate_general_settings(config)
        ]
        
        # Combine results
        for validation in validations:
            all_errors.extend(validation.errors)
            all_warnings.extend(validation.warnings)
        
        # Cross-validation checks
        cross_validation = cls._cross_validate_settings(config)
        all_errors.extend(cross_validation.errors)
        all_warnings.extend(cross_validation.warnings)
        
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings
        )
    
    @staticmethod
    def _cross_validate_settings(config: MockTradingConfig) -> ValidationResult:
        """
        Perform cross-validation between different configuration sections.
        
        Args:
            config: Configuration to validate
            
        Returns:
            ValidationResult: Cross-validation results
        """
        errors = []
        warnings = []
        
        # Check if fees are reasonable relative to position sizes
        max_fee_per_trade = max(
            config.fees.trading_fee_percent * config.max_position_size,
            config.fees.trading_fee_fixed
        )
        max_fee_per_trade = min(max_fee_per_trade, config.fees.maximum_fee)
        max_fee_per_trade = max(max_fee_per_trade, config.fees.minimum_fee)
        
        if max_fee_per_trade > config.max_position_size * 0.1:
            warnings.append("Maximum trading fees > 10% of position size is very high")
        
        # Check if slippage and fees combined are reasonable
        max_slippage = config.execution.slippage_base + (
            config.execution.slippage_impact_factor * 
            (config.max_position_size / 1000)
        )
        total_cost_percentage = max_slippage + config.fees.trading_fee_percent
        
        if total_cost_percentage > 0.05:  # 5%
            warnings.append("Combined slippage and fees > 5% may significantly impact returns")
        
        # Check if daily loss limit is reasonable relative to position size
        if config.max_daily_loss < config.max_position_size * 0.1:
            warnings.append("Daily loss limit < 10% of max position size may be too restrictive")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


def validate_config_with_logging(config: MockTradingConfig) -> bool:
    """
    Validate configuration and log results.
    
    Args:
        config: Configuration to validate
        
    Returns:
        bool: True if configuration is valid
    """
    result = ConfigValidator.validate_full_config(config)
    
    # Log errors
    for error in result.errors:
        log_error(f"Configuration validation error: {error}")
    
    # Log warnings
    for warning in result.warnings:
        log_error(f"Configuration validation warning: {warning}")
    
    return result.is_valid