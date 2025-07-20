# Mock Trading Environment Configuration

This directory contains the configuration system for the mock trading environment, providing a comprehensive paper trading simulator that mimics Alpaca's API behavior while using real market data.

## Overview

The mock trading configuration system provides:

- **Flexible Configuration**: Support for different trading scenarios (conservative, aggressive, default)
- **Comprehensive Validation**: Multi-level validation with error handling and safe defaults
- **Template System**: Pre-configured templates for common trading strategies
- **File-based Configuration**: JSON-based configuration files for easy customization
- **Integration Ready**: Seamless integration with existing trading strategies

## Quick Start

### Basic Usage

```python
from mock_trading.mock_config import MockTradingConfig, load_mock_config
from mock_trading.mock_trader import MockTrader

# Load default configuration
config = load_mock_config()

# Create mock trader
trader = MockTrader(config)
trader.initialize()
```

### Using Configuration Templates

```python
# Load conservative configuration
config = MockTradingConfig.from_file("mock_trading/config_templates/conservative_config.json")

# Load aggressive configuration  
config = MockTradingConfig.from_file("mock_trading/config_templates/aggressive_config.json")
```

### Custom Configuration

```python
# Create custom configuration
config = MockTradingConfig(
    starting_capital=15000.0,
    max_position_size=7500.0,
    max_daily_loss=1500.0
)

# Validate and apply safe defaults if needed
if not config.validate_config():
    config = config.apply_safe_defaults()
```

## Configuration Structure

### Main Configuration (`MockTradingConfig`)

- **starting_capital**: Starting capital in USD (default: $10,000)
- **max_position_size**: Maximum position size in USD (default: $5,000)
- **max_daily_loss**: Maximum daily loss limit (default: $1,000)
- **simulation_mode**: Always True for mock trading
- **enable_detailed_logging**: Enable detailed logging (default: True)
- **performance_tracking**: Enable performance tracking (default: True)
- **save_trade_history**: Save trade history (default: True)
- **history_retention_days**: Days to retain history (default: 365)

### Execution Configuration (`ExecutionConfig`)

- **slippage_base**: Base slippage percentage (default: 0.01%)
- **slippage_impact_factor**: Additional slippage per $1000 order size
- **execution_delay_min_ms**: Minimum execution delay in milliseconds
- **execution_delay_max_ms**: Maximum execution delay in milliseconds
- **market_impact_threshold**: Order size threshold for market impact
- **enable_partial_fills**: Enable partial fill simulation
- **partial_fill_probability**: Probability of partial fills
- **min_fill_percentage**: Minimum percentage filled in partial fills

### Market Configuration (`MarketConfig`)

- **volatility_multiplier**: Multiplier for volatility-based adjustments
- **liquidity_factor**: Factor affecting order execution in low liquidity
- **market_hours_enforcement**: Enforce market hours restrictions
- **extended_hours_trading**: Allow extended hours trading
- **gap_simulation_enabled**: Enable market gap simulation
- **correlation_simulation**: Enable symbol correlation simulation

### Fee Configuration (`FeeConfig`)

- **trading_fee_percent**: Percentage-based trading fee
- **trading_fee_fixed**: Fixed fee per trade
- **minimum_fee**: Minimum fee per trade
- **maximum_fee**: Maximum fee per trade

## Configuration Templates

### Default Configuration
- Balanced settings suitable for most testing scenarios
- Moderate slippage and execution delays
- Standard market hours enforcement

### Conservative Configuration
- Lower position sizes and higher safety margins
- Higher slippage and execution delays
- More restrictive trading parameters

### Aggressive Configuration
- Higher position sizes and risk tolerance
- Lower slippage and faster execution
- Extended hours trading enabled

## Validation System

The configuration system includes comprehensive validation:

### Error Validation
- Prevents invalid configurations that would cause system failures
- Checks for negative values, impossible constraints, and logical inconsistencies

### Warning System
- Alerts for potentially problematic but valid configurations
- Provides guidance on recommended parameter ranges

### Safe Defaults
- Automatically applies safe defaults when validation fails
- Ensures system can always operate with valid parameters

### Cross-Validation
- Validates relationships between different configuration sections
- Ensures fees, slippage, and position sizes are reasonable relative to each other

## File Operations

### Saving Configuration
```python
config = MockTradingConfig(starting_capital=20000.0)
config.save_to_file("my_config.json")
```

### Loading Configuration
```python
config = MockTradingConfig.from_file("my_config.json")
```

### Creating Default Config File
```python
from mock_trading.mock_config import create_default_config_file
create_default_config_file("default.json")
```

## Integration with Existing System

The mock trading configuration is designed to integrate seamlessly with the existing trading bot:

### Environment Switching
```python
from bot.config import Config as LiveConfig
from mock_trading.mock_config import MockTradingConfig

# Switch between live and mock based on configuration
if use_mock_trading:
    config = MockTradingConfig.from_file("mock_config.json")
    trader = MockTrader(config)
else:
    config = LiveConfig()
    trader = Trader(config.get_alpaca_credentials())
```

### Configuration Compatibility
- Uses similar parameter names and structures as live configuration
- Maintains compatibility with existing strategy interfaces
- Provides clear migration path between mock and live trading

## Testing and Validation

### Running Tests
```bash
# Run configuration tests
PYTHONPATH=. python tests/unit/test_mock_config.py

# Run configuration demo
PYTHONPATH=. python mock_trading/demo_config.py
```

### Validation Functions
```python
from mock_trading.config_validator import ConfigValidator, validate_config_with_logging

# Comprehensive validation
result = ConfigValidator.validate_full_config(config)

# Validation with logging
is_valid = validate_config_with_logging(config)
```

## Error Handling

The configuration system includes robust error handling:

- **File Errors**: Graceful handling of missing or corrupted configuration files
- **Validation Errors**: Clear error messages with specific guidance
- **Safe Fallbacks**: Automatic fallback to safe defaults when needed
- **Logging Integration**: Integration with existing logging system

## Best Practices

### Configuration Management
1. Use configuration templates as starting points
2. Always validate configurations before use
3. Apply safe defaults for production use
4. Keep configuration files in version control

### Parameter Selection
1. Start with conservative settings for new strategies
2. Gradually adjust parameters based on testing results
3. Monitor validation warnings for potential issues
4. Consider market conditions when setting parameters

### Testing Approach
1. Test strategies with multiple configuration templates
2. Validate edge cases with extreme parameter values
3. Use reproducible configurations with fixed random seeds
4. Compare results across different configuration scenarios

## Future Enhancements

The configuration system is designed to be extensible:

- Additional validation rules can be easily added
- New configuration sections can be integrated
- Template system can be expanded with more scenarios
- Integration with external configuration management systems

## Support and Troubleshooting

### Common Issues
1. **Configuration Validation Failures**: Check parameter ranges and relationships
2. **File Loading Errors**: Verify JSON syntax and file permissions
3. **Integration Issues**: Ensure proper initialization order

### Getting Help
- Review validation error messages for specific guidance
- Use the demo script to understand configuration behavior
- Check test cases for usage examples
- Refer to design documentation for detailed specifications