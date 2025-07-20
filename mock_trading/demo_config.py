#!/usr/bin/env python3
"""
Demonstration script for mock trading configuration system.
Shows how to load, validate, and use different configuration templates.
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mock_trading.mock_config import MockTradingConfig, load_mock_config, create_default_config_file
from mock_trading.config_validator import ConfigValidator, validate_config_with_logging
from mock_trading.mock_trader import MockTrader


def demo_default_config():
    """Demonstrate default configuration creation and validation."""
    print("=== Default Configuration Demo ===")
    
    # Create default configuration
    config = MockTradingConfig()
    print(f"Starting Capital: ${config.starting_capital:,.2f}")
    print(f"Max Position Size: ${config.max_position_size:,.2f}")
    print(f"Max Daily Loss: ${config.max_daily_loss:,.2f}")
    print(f"Base Slippage: {config.execution.slippage_base:.4%}")
    print(f"Trading Fee: {config.fees.trading_fee_percent:.3%}")
    
    # Validate configuration
    is_valid = config.validate_config()
    print(f"Configuration Valid: {is_valid}")
    print()


def demo_template_configs():
    """Demonstrate loading different configuration templates."""
    print("=== Configuration Templates Demo ===")
    
    templates = [
        ("Default", "mock_trading/config_templates/default_config.json"),
        ("Conservative", "mock_trading/config_templates/conservative_config.json"),
        ("Aggressive", "mock_trading/config_templates/aggressive_config.json")
    ]
    
    for name, template_path in templates:
        if os.path.exists(template_path):
            print(f"\n{name} Configuration:")
            config = MockTradingConfig.from_file(template_path)
            print(f"  Starting Capital: ${config.starting_capital:,.2f}")
            print(f"  Max Position Size: ${config.max_position_size:,.2f}")
            print(f"  Base Slippage: {config.execution.slippage_base:.4%}")
            print(f"  Execution Delay: {config.execution.execution_delay_min_ms}-{config.execution.execution_delay_max_ms}ms")
            print(f"  Extended Hours: {config.market.extended_hours_trading}")
            print(f"  Valid: {config.validate_config()}")
        else:
            print(f"{name} template not found at {template_path}")
    print()


def demo_config_validation():
    """Demonstrate comprehensive configuration validation."""
    print("=== Configuration Validation Demo ===")
    
    # Create a problematic configuration
    problematic_config = MockTradingConfig(
        starting_capital=500.0,  # Low capital (warning)
        max_position_size=600.0,  # Exceeds capital (error)
        max_daily_loss=1000.0,   # Exceeds capital (error)
    )
    
    print("Validating problematic configuration...")
    result = ConfigValidator.validate_full_config(problematic_config)
    
    print(f"Valid: {result.is_valid}")
    print(f"Errors ({len(result.errors)}):")
    for error in result.errors:
        print(f"  - {error}")
    
    print(f"Warnings ({len(result.warnings)}):")
    for warning in result.warnings:
        print(f"  - {warning}")
    
    # Apply safe defaults
    print("\nApplying safe defaults...")
    safe_config = problematic_config.apply_safe_defaults()
    safe_result = ConfigValidator.validate_full_config(safe_config)
    
    print(f"Safe config valid: {safe_result.is_valid}")
    print(f"Safe starting capital: ${safe_config.starting_capital:,.2f}")
    print(f"Safe max position: ${safe_config.max_position_size:,.2f}")
    print()


def demo_mock_trader_integration():
    """Demonstrate mock trader integration with configuration."""
    print("=== Mock Trader Integration Demo ===")
    
    # Load configuration
    config = load_mock_config()
    print(f"Loaded configuration with ${config.starting_capital:,.2f} starting capital")
    
    # Create mock trader
    trader = MockTrader(config)
    print(f"Mock trader initialized: {trader.is_initialized()}")
    
    # Initialize trader
    if trader.initialize():
        print("Mock trader initialization successful")
        print(f"Trader config starting capital: ${trader.get_config().starting_capital:,.2f}")
    else:
        print("Mock trader initialization failed")
    print()


def demo_config_file_operations():
    """Demonstrate configuration file save/load operations."""
    print("=== Configuration File Operations Demo ===")
    
    # Create custom configuration
    custom_config = MockTradingConfig(
        starting_capital=15000.0,
        max_position_size=7500.0,
        max_daily_loss=1500.0
    )
    
    # Save to file
    config_file = "demo_config.json"
    if custom_config.save_to_file(config_file):
        print(f"Configuration saved to {config_file}")
        
        # Load from file
        loaded_config = MockTradingConfig.from_file(config_file)
        print(f"Loaded configuration: ${loaded_config.starting_capital:,.2f} starting capital")
        
        # Clean up
        os.remove(config_file)
        print("Demo configuration file cleaned up")
    else:
        print("Failed to save configuration file")
    print()


def main():
    """Run all configuration demonstrations."""
    print("Mock Trading Configuration System Demo")
    print("=" * 50)
    
    demo_default_config()
    demo_template_configs()
    demo_config_validation()
    demo_mock_trader_integration()
    demo_config_file_operations()
    
    print("Demo completed successfully!")


if __name__ == "__main__":
    main()