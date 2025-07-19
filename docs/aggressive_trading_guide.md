# Aggressive Trading Strategies Guide

## Overview

This guide covers the aggressive trading strategies designed for small accounts ($100 starting capital) with higher risk tolerance for potentially higher returns. These strategies focus on scalping and momentum trading with proper risk management.

## 🚀 Key Features

### Aggressive Strategies

1. **Scalping Momentum Strategy**
   - Catches quick momentum moves with volume confirmation
   - Lookback period: 3-5 candles
   - Volume threshold: 1.2-1.5x average
   - Momentum threshold: 0.4-0.8% price moves

2. **Volatility Breakout Strategy**
   - Trades breakouts after volatility compression
   - Uses ATR for volatility measurement
   - Detects "squeeze" periods followed by expansion
   - Breakout multiplier: 1.1-1.5x ATR

3. **Mean Reversion Scalp Strategy**
   - Quick reversals from extreme price levels
   - Short-period Bollinger Bands (6-10 periods)
   - Fast RSI (4-7 periods)
   - Targets extreme overbought/oversold conditions

### Risk Management

- **Max Risk Per Trade**: 5% of capital
- **Max Daily Loss**: 15% of capital
- **Max Position Size**: 80% of capital (aggressive)
- **Stop Loss**: 2% (tight for scalping)
- **Take Profit**: 4% (2:1 risk/reward)
- **Max Trades Per Day**: 25

## 💰 Position Sizing

Dynamic position sizing based on:
- Signal confidence (0.3x to 1.7x multiplier)
- Market volatility (0.7x to 1.5x multiplier)
- Account balance protection

```python
# Example position calculation
base_size = capital * 0.8  # 80% max position
confidence_mult = 0.3 + (signal_confidence * 1.4)
volatility_mult = 1.5 if high_vol else 0.7 if low_vol else 1.0
position_size = base_size * confidence_mult * volatility_mult
```

## 📊 Recommended Trading Pairs

### Primary Pairs (High Liquidity)
- **BTC/USD**: Most stable, good for larger positions
- **ETH/USD**: High volatility, excellent for scalping

### Secondary Pairs (Higher Risk/Reward)
- **SOL/USD**: Very volatile, good momentum moves
- **AVAX/USD**: High beta, amplified BTC moves
- **MATIC/USD**: Lower price, accessible for small accounts

## ⚙️ Configuration

### Basic Setup

```python
from bot.aggressive_strategies import create_aggressive_strategy_suite
from bot.aggressive_config import get_aggressive_config

# Get configuration
config = get_aggressive_config()
trading_settings = config["trading_settings"]

# Create strategies
strategies = create_aggressive_strategy_suite()
```

### Custom Strategy Parameters

```python
# Scalping Momentum (more aggressive)
ScalpingMomentumStrategy(
    lookback_period=3,      # Very short-term
    volume_threshold=1.2,   # Lower for more signals
    momentum_threshold=0.004 # 0.4% moves
)

# Volatility Breakout (sensitive)
VolatilityBreakoutStrategy(
    atr_period=8,           # Shorter period
    squeeze_threshold=0.8,  # Easier to trigger
    breakout_multiplier=1.1 # Lower threshold
)

# Mean Reversion (fast)
MeanReversionScalpStrategy(
    bb_period=6,            # Very short BB
    bb_std=1.8,            # Tighter bands
    rsi_period=4           # Very responsive
)
```

## 🎯 Trading Rules

### Entry Rules
1. **Minimum Signal Confidence**: 0.4 (40%)
2. **Strong Signal Threshold**: 0.7 (70%) for larger positions
3. **Volume Confirmation**: Required for momentum strategies
4. **Time Between Trades**: Minimum 1 minute

### Exit Rules
1. **Stop Loss**: 2% from entry (tight scalping stops)
2. **Take Profit**: 4% from entry (2:1 risk/reward)
3. **Trailing Stop**: 1.5% trailing after 2% profit
4. **Scale Out**: Take 30% profit at 2%, 50% at 3.5%

### Risk Controls
1. **Daily Loss Limit**: Stop trading at -15% daily loss
2. **Trade Count Limit**: Max 25 trades per day
3. **Account Protection**: Stop at 20% of initial capital
4. **Position Size Limits**: Never exceed 80% of capital

## 📈 Performance Expectations

### Realistic Targets (with $100 starting capital)
- **Daily Target**: 2-5% gain
- **Weekly Target**: 10-25% gain
- **Monthly Target**: 50-100% gain
- **Max Drawdown**: 15-20%

### Success Metrics
- **Win Rate**: Target 55-65%
- **Risk/Reward**: Minimum 1:2 ratio
- **Profit Factor**: Target > 1.5
- **Sharpe Ratio**: Target > 1.0

## ⚠️ Risk Warnings

### High-Risk Trading
- **Capital Loss**: You can lose your entire $100 quickly
- **Emotional Stress**: Aggressive trading is mentally demanding
- **Market Conditions**: Strategies may fail in certain markets
- **Overtrading**: Easy to exceed daily limits

### Best Practices
1. **Start Small**: Begin with paper trading
2. **Keep Records**: Log every trade and decision
3. **Stay Disciplined**: Follow your rules strictly
4. **Take Breaks**: Don't trade when emotional
5. **Continuous Learning**: Analyze your performance

## 🔧 Implementation Example

```python
# Complete setup example
from bot.aggressive_strategies import AggressiveRiskManager
from bot.strategy import SignalGenerator

# Initialize risk manager
risk_manager = AggressiveRiskManager(
    initial_capital=100.0,
    max_risk_per_trade=0.05,
    max_daily_loss=0.15,
    max_position_size=0.8
)

# Create strategies
strategies = create_aggressive_strategy_suite()
signal_generator = SignalGenerator(strategies)

# Trading loop
for market_data in data_stream:
    # Check if we can trade
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        continue
    
    # Generate signals
    signal = signal_generator.evaluate_all_strategies(market_data)
    
    if signal.confidence > 0.4:
        # Calculate position size
        position_size = calculate_dynamic_position_size(
            capital=risk_manager.current_capital,
            signal_confidence=signal.confidence,
            volatility=current_volatility,
            settings=trading_settings
        )
        
        # Execute trade
        execute_trade(signal, position_size)
```

## 📚 Additional Resources

### Backtesting
- Use historical data to test strategies
- Minimum 3 months of data recommended
- Test different market conditions

### Monitoring
- Track all trades in a spreadsheet
- Monitor daily P&L closely
- Review strategy performance weekly

### Optimization
- Adjust parameters based on performance
- Consider market regime changes
- Update risk limits as account grows

## 🎮 Getting Started

1. **Paper Trade First**: Test with fake money
2. **Start Conservative**: Use smaller position sizes initially
3. **Monitor Closely**: Watch every trade for the first week
4. **Adjust Parameters**: Fine-tune based on results
5. **Scale Gradually**: Increase risk as you gain confidence

Remember: Aggressive trading with small accounts is high-risk, high-reward. Only trade money you can afford to lose completely.