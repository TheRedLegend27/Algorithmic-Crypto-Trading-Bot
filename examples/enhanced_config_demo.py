#!/usr/bin/env python3
"""
Demo script for enhanced configuration system.
Shows how to use the new multi-pair trading configuration.
"""
import os
import sys
import json

# Add the parent directory to the path so we can import bot modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import (
    Config, 
    KrakenTradingPair, 
    StrategyConfig, 
    RiskConfig, 
    EnhancedTradingConfig
)


def demo_basic_usage():
    """Demonstrate basic usage of enhanced configuration."""
    print("=== Enhanced Configuration Demo ===\n")
    
    # Create config instance
    config = Config()
    
    # Get enhanced configuration
    enhanced_config = config.get_enhanced_config()
    
    print("1. Default Configuration:")
    print(f"   Number of trading pairs: {len(enhanced_config.trading_pairs)}")
    print(f"   Enabled pairs: {len(enhanced_config.get_enabled_pairs())}")
    print(f"   Default trade amount: ${enhanced_config.risk.default_trade_amount_usd}")
    print(f"   Max position per pair: ${enhanced_config.risk.max_position_per_pair_usd}")
    print(f"   WebSocket enabled: {enhanced_config.enable_websocket}")
    print()
    
    # Show trading pairs
    print("2. Configured Trading Pairs:")
    for pair in enhanced_config.trading_pairs:
        status = "ENABLED" if pair.enabled else "DISABLED"
        print(f"   {pair.symbol}: {pair.base_currency}/{pair.quote_currency} [{status}]")
        print(f"      Min order size: {pair.min_order_size}")
        print(f"      Price precision: {pair.price_precision}")
        print(f"      Maker fee: {pair.maker_fee:.4f}")
    print()
    
    # Show strategy configuration
    print("3. Strategy Configuration:")
    strategy = enhanced_config.strategy
    print(f"   Momentum weight: {strategy.momentum_weight}")
    print(f"   Volatility weight: {strategy.volatility_weight}")
    print(f"   Volume weight: {strategy.volume_weight}")
    print(f"   Multi-timeframe: {strategy.enable_multi_timeframe}")
    print(f"   Primary timeframe: {strategy.primary_timeframe}")
    print(f"   Min signal strength: {strategy.min_signal_strength}")
    print()
    
    # Show risk configuration
    print("4. Risk Management Configuration:")
    risk = enhanced_config.risk
    print(f"   Risk per trade: {risk.risk_per_trade_pct:.1%}")
    print(f"   Max daily loss: {risk.max_daily_loss_pct:.1%}")
    print(f"   Stop loss: {risk.default_stop_loss_pct:.1%}")
    print(f"   Take profit: {risk.default_take_profit_pct:.1%}")
    print(f"   Trailing stop: {risk.trailing_stop_enabled}")
    print(f"   Volatility adjustment: {risk.enable_volatility_adjustment}")
    print()


def demo_adding_trading_pairs():
    """Demonstrate adding and managing trading pairs."""
    print("=== Trading Pair Management Demo ===\n")
    
    config = Config()
    enhanced_config = config.get_enhanced_config()
    
    print("1. Adding a new trading pair:")
    new_pair = KrakenTradingPair(
        symbol="DOTUSD",
        base_currency="DOT",
        quote_currency="USD",
        min_order_size=0.1,
        price_precision=3,
        size_precision=4,
        enabled=True
    )
    
    success = enhanced_config.add_trading_pair(new_pair)
    print(f"   Added DOT/USD pair: {success}")
    print(f"   Total pairs now: {len(enhanced_config.trading_pairs)}")
    print()
    
    print("2. Updating trading pair configuration:")
    updates = {
        'min_order_size': 0.05,
        'enabled': False
    }
    success = enhanced_config.update_trading_pair("DOTUSD", updates)
    print(f"   Updated DOT/USD pair: {success}")
    
    dot_pair = enhanced_config.get_pair_by_symbol("DOTUSD")
    if dot_pair:
        print(f"   New min order size: {dot_pair.min_order_size}")
        print(f"   Enabled: {dot_pair.enabled}")
    print()
    
    print("3. Removing trading pair:")
    success = enhanced_config.remove_trading_pair("DOTUSD")
    print(f"   Removed DOT/USD pair: {success}")
    print(f"   Total pairs now: {len(enhanced_config.trading_pairs)}")
    print()


def demo_configuration_validation():
    """Demonstrate configuration validation."""
    print("=== Configuration Validation Demo ===\n")
    
    print("1. Valid configuration:")
    valid_config = EnhancedTradingConfig()
    is_valid = valid_config.validate()
    print(f"   Configuration is valid: {is_valid}")
    print()
    
    print("2. Invalid strategy configuration (weights don't sum to 1.0):")
    invalid_config = EnhancedTradingConfig()
    invalid_config.strategy.momentum_weight = 0.8
    invalid_config.strategy.volatility_weight = 0.8  # Total > 1.0
    is_valid = invalid_config.validate()
    print(f"   Configuration is valid: {is_valid}")
    print()
    
    print("3. Invalid risk configuration (negative amounts):")
    invalid_config2 = EnhancedTradingConfig()
    invalid_config2.risk.default_trade_amount_usd = -100.0
    is_valid = invalid_config2.validate()
    print(f"   Configuration is valid: {is_valid}")
    print()
    
    print("4. Applying default values to fix invalid configuration:")
    config = Config()
    config._enhanced_config = invalid_config2
    success = config.apply_default_values()
    print(f"   Applied defaults: {success}")
    print(f"   Trade amount after fix: ${config._enhanced_config.risk.default_trade_amount_usd}")
    print()


def demo_file_operations():
    """Demonstrate saving and loading configuration from files."""
    print("=== File Operations Demo ===\n")
    
    config_file = "temp_enhanced_config.json"
    
    try:
        print("1. Creating and customizing configuration:")
        config = EnhancedTradingConfig()
        config.risk.default_trade_amount_usd = 250.0
        config.strategy.momentum_weight = 0.4
        config.strategy.volatility_weight = 0.6
        config.strategy.volume_weight = 0.0
        config.strategy.bollinger_weight = 0.0
        config.strategy.macd_weight = 0.0
        config.enable_dashboard = False
        print(f"   Trade amount: ${config.risk.default_trade_amount_usd}")
        print(f"   Dashboard enabled: {config.enable_dashboard}")
        print()
        
        print("2. Saving configuration to file:")
        success = config.save_to_file(config_file)
        print(f"   Saved to {config_file}: {success}")
        print()
        
        print("3. Loading configuration from file:")
        loaded_config = EnhancedTradingConfig.load_from_file(config_file)
        if loaded_config:
            print(f"   Loaded successfully: True")
            print(f"   Trade amount: ${loaded_config.risk.default_trade_amount_usd}")
            print(f"   Dashboard enabled: {loaded_config.enable_dashboard}")
            print(f"   Momentum weight: {loaded_config.strategy.momentum_weight}")
        else:
            print("   Failed to load configuration")
        print()
        
        print("4. Using Config class file operations:")
        main_config = Config()
        success = main_config.load_enhanced_config_from_file(config_file)
        print(f"   Loaded into Config: {success}")
        
        if success:
            enhanced = main_config.get_enhanced_config()
            print(f"   Trade amount in Config: ${enhanced.risk.default_trade_amount_usd}")
        print()
        
    finally:
        # Clean up
        if os.path.exists(config_file):
            os.remove(config_file)
            print(f"Cleaned up {config_file}")


def demo_backward_compatibility():
    """Demonstrate backward compatibility with legacy configuration."""
    print("=== Backward Compatibility Demo ===\n")
    
    config = Config()
    
    print("1. Getting legacy crypto trading settings:")
    crypto_settings = config.get_crypto_trading_settings()
    print(f"   Trading pair: {crypto_settings.trading_pair}")
    print(f"   Trade amount: ${crypto_settings.trade_amount_usd}")
    print(f"   Max position: ${crypto_settings.max_position_usd}")
    print(f"   Stop loss: {crypto_settings.stop_loss_pct:.1%}")
    print()
    
    print("2. Updating via legacy interface:")
    legacy_updates = {
        'trade_amount_usd': 150.0,
        'max_position_usd': 1500.0,
        'stop_loss_pct': 0.04
    }
    success = config.update_crypto_trading_settings(legacy_updates)
    print(f"   Updated legacy settings: {success}")
    print()
    
    print("3. Verifying updates in enhanced config:")
    enhanced_config = config.get_enhanced_config()
    print(f"   Enhanced trade amount: ${enhanced_config.risk.default_trade_amount_usd}")
    print(f"   Enhanced max position: ${enhanced_config.risk.max_position_per_pair_usd}")
    print(f"   Enhanced stop loss: {enhanced_config.risk.default_stop_loss_pct:.1%}")
    print()


def demo_environment_overrides():
    """Demonstrate environment variable overrides."""
    print("=== Environment Variable Overrides Demo ===\n")
    
    print("1. Setting environment variables:")
    os.environ["DEFAULT_TRADE_AMOUNT_USD"] = "300.0"
    os.environ["MAX_POSITION_PER_PAIR_USD"] = "3000.0"
    os.environ["ENABLE_WEBSOCKET"] = "false"
    os.environ["DASHBOARD_PORT"] = "8090"
    
    # Reset config to test environment loading
    Config._instance = None
    config = Config()
    
    # Simulate loading environment variables
    config._load_config_overrides_from_env()
    
    enhanced_config = config.get_enhanced_config()
    print(f"   Trade amount from env: ${enhanced_config.risk.default_trade_amount_usd}")
    print(f"   Max position from env: ${enhanced_config.risk.max_position_per_pair_usd}")
    print(f"   WebSocket from env: {enhanced_config.enable_websocket}")
    print(f"   Dashboard port from env: {enhanced_config.dashboard_port}")
    print()
    
    # Clean up environment variables
    for key in ["DEFAULT_TRADE_AMOUNT_USD", "MAX_POSITION_PER_PAIR_USD", 
                "ENABLE_WEBSOCKET", "DASHBOARD_PORT"]:
        if key in os.environ:
            del os.environ[key]


def main():
    """Run all demos."""
    try:
        demo_basic_usage()
        demo_adding_trading_pairs()
        demo_configuration_validation()
        demo_file_operations()
        demo_backward_compatibility()
        demo_environment_overrides()
        
        print("=== Demo Complete ===")
        print("The enhanced configuration system provides:")
        print("• Multi-pair trading support")
        print("• Advanced strategy configuration")
        print("• Comprehensive risk management")
        print("• Configuration validation")
        print("• File-based configuration")
        print("• Environment variable overrides")
        print("• Backward compatibility")
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()