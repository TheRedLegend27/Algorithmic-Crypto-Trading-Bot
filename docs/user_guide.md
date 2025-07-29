# Enhanced Trading Strategies and Risk Management User Guide

This guide explains how to use the advanced trading strategies and risk management features of the Enhanced Kraken Trading Bot.

## Table of Contents

1. [Trading Strategies Overview](#trading-strategies-overview)
2. [Strategy Configuration](#strategy-configuration)
3. [Risk Management System](#risk-management-system)
4. [Multi-Pair Trading](#multi-pair-trading)
5. [Performance Optimization](#performance-optimization)
6. [Advanced Features](#advanced-features)

## Trading Strategies Overview

The bot implements five sophisticated trading strategies that can be used individually or in combination:

### 1. Enhanced Momentum Strategy

**Purpose**: Captures trending price movements with volatility adjustment

**How it works**:
- Calculates price momentum over multiple timeframes
- Adjusts for market volatility to avoid false signals
- Uses volume confirmation for signal validation
- Implements dynamic stop-loss based on volatility

**Best for**: Trending markets with clear directional movement

**Configuration**:
```json
{
  "momentum_weight": 0.3,
  "momentum_lookback_periods": 14,
  "volatility_adjustment": true,
  "volume_confirmation": true
}
```

**Example Signal**:
```
Strategy: Enhanced Momentum
Action: BUY
Confidence: 0.75
Reasoning: Strong upward momentum (0.85) with high volume confirmation
Price: $45,250.00
Volatility: 0.023 (Low)
```

### 2. Volatility Breakout Strategy

**Purpose**: Identifies breakout opportunities from consolidation periods

**How it works**:
- Monitors price compression periods (low volatility)
- Detects breakouts above/below volatility bands
- Confirms with volume and momentum indicators
- Uses adaptive position sizing based on breakout strength

**Best for**: Range-bound markets transitioning to trends

**Configuration**:
```json
{
  "volatility_weight": 0.25,
  "volatility_lookback_periods": 20,
  "breakout_threshold": 2.0,
  "volume_multiplier": 1.5
}
```

### 3. Volume-Weighted Strategy

**Purpose**: Uses volume analysis to identify institutional activity

**How it works**:
- Analyzes volume patterns and price-volume relationships
- Identifies accumulation/distribution phases
- Uses VWAP (Volume Weighted Average Price) for entry/exit
- Confirms signals with volume momentum

**Best for**: Markets with significant institutional participation

**Configuration**:
```json
{
  "volume_weight": 0.2,
  "volume_lookback_periods": 20,
  "vwap_periods": 50,
  "volume_threshold": 1.2
}
```

### 4. Bollinger Bands Strategy

**Purpose**: Mean reversion trading with volatility-adjusted bands

**How it works**:
- Creates dynamic support/resistance levels
- Identifies overbought/oversold conditions
- Uses band squeeze for breakout detection
- Combines with RSI for confirmation

**Best for**: Range-bound and mean-reverting markets

**Configuration**:
```json
{
  "bollinger_weight": 0.15,
  "bollinger_periods": 20,
  "bollinger_std_dev": 2.0,
  "rsi_confirmation": true
}
```

### 5. MACD Strategy

**Purpose**: Trend following with momentum confirmation

**How it works**:
- Uses Moving Average Convergence Divergence
- Identifies trend changes and momentum shifts
- Signal line crossovers for entry/exit timing
- Histogram analysis for momentum strength

**Best for**: Medium to long-term trend identification

**Configuration**:
```json
{
  "macd_weight": 0.1,
  "macd_fast_period": 12,
  "macd_slow_period": 26,
  "macd_signal_period": 9
}
```

## Strategy Configuration

### Weighted Strategy Combination

The bot combines multiple strategies using configurable weights:

```json
{
  "strategy": {
    "momentum_weight": 0.3,      // 30% weight
    "volatility_weight": 0.25,   // 25% weight
    "volume_weight": 0.2,        // 20% weight
    "bollinger_weight": 0.15,    // 15% weight
    "macd_weight": 0.1,          // 10% weight
    "min_signal_strength": 0.65, // Minimum combined confidence
    "max_signal_age_minutes": 5  // Signal expiration time
  }
}
```

### Multi-Timeframe Analysis

Enable cross-timeframe confirmation for higher accuracy:

```json
{
  "enable_multi_timeframe": true,
  "primary_timeframe": "1h",      // Main analysis timeframe
  "confirmation_timeframe": "4h", // Higher timeframe confirmation
  "timeframe_agreement_threshold": 0.7
}
```

### Strategy Customization

#### Conservative Setup (Lower Risk)
```json
{
  "momentum_weight": 0.2,
  "volatility_weight": 0.2,
  "volume_weight": 0.3,
  "bollinger_weight": 0.2,
  "macd_weight": 0.1,
  "min_signal_strength": 0.75
}
```

#### Aggressive Setup (Higher Risk/Reward)
```json
{
  "momentum_weight": 0.4,
  "volatility_weight": 0.3,
  "volume_weight": 0.15,
  "bollinger_weight": 0.1,
  "macd_weight": 0.05,
  "min_signal_strength": 0.55
}
```

## Risk Management System

### Dynamic Position Sizing

The bot calculates position sizes based on multiple factors:

```python
position_size = base_amount * confidence_multiplier * volatility_adjustment * correlation_factor
```

**Factors**:
- **Signal Confidence**: Higher confidence = larger position
- **Market Volatility**: Higher volatility = smaller position
- **Portfolio Correlation**: Correlated positions = reduced size
- **Account Balance**: Percentage-based sizing

### Risk Limits

#### Per-Trade Limits
```json
{
  "risk_per_trade_pct": 0.02,        // 2% max risk per trade
  "max_position_per_pair_usd": 1000, // $1000 max per trading pair
  "min_trade_amount_usd": 10         // $10 minimum trade size
}
```

#### Portfolio Limits
```json
{
  "max_total_position_usd": 5000,    // $5000 max total exposure
  "max_open_positions": 10,          // Maximum 10 open positions
  "max_correlation_exposure": 0.7    // 70% max correlated exposure
}
```

#### Time-Based Limits
```json
{
  "max_daily_trades": 50,            // 50 trades per day maximum
  "max_daily_loss_pct": 0.05,        // 5% max daily loss
  "max_weekly_loss_pct": 0.15,       // 15% max weekly loss
  "trading_hours": {
    "start": "00:00",
    "end": "23:59",
    "timezone": "UTC"
  }
}
```

### Stop Loss and Take Profit

#### Dynamic Stop Loss
```json
{
  "enable_stop_loss": true,
  "default_stop_loss_pct": 0.03,     // 3% default stop loss
  "volatility_adjusted_stops": true,  // Adjust based on volatility
  "trailing_stop_enabled": true,     // Enable trailing stops
  "trailing_stop_distance_pct": 0.02 // 2% trailing distance
}
```

#### Take Profit Levels
```json
{
  "enable_take_profit": true,
  "default_take_profit_pct": 0.06,   // 6% default take profit
  "partial_profit_levels": [0.03, 0.06, 0.09], // Multiple levels
  "partial_profit_sizes": [0.3, 0.4, 0.3]      // 30%, 40%, 30%
}
```

### Emergency Stops

#### Circuit Breakers
```json
{
  "emergency_stop_loss_pct": 0.2,    // 20% portfolio loss triggers stop
  "max_consecutive_losses": 5,       // Stop after 5 consecutive losses
  "volatility_circuit_breaker": 0.1, // Stop if volatility > 10%
  "api_error_threshold": 10          // Stop after 10 API errors
}
```

## Multi-Pair Trading

### Supported Trading Pairs

The bot supports multiple Kraken trading pairs:

```json
{
  "trading_pairs": [
    {
      "symbol": "XBTUSD",
      "base_currency": "XBT",
      "quote_currency": "USD",
      "enabled": true,
      "weight": 0.4
    },
    {
      "symbol": "ETHUSD",
      "base_currency": "ETH",
      "quote_currency": "USD",
      "enabled": true,
      "weight": 0.3
    },
    {
      "symbol": "ADAUSD",
      "base_currency": "ADA",
      "quote_currency": "USD",
      "enabled": true,
      "weight": 0.2
    },
    {
      "symbol": "SOLUSD",
      "base_currency": "SOL",
      "quote_currency": "USD",
      "enabled": true,
      "weight": 0.1
    }
  ]
}
```

### Correlation Management

The bot monitors correlations between trading pairs:

```json
{
  "correlation_settings": {
    "lookback_periods": 50,           // Periods for correlation calculation
    "max_correlation_threshold": 0.8, // Maximum allowed correlation
    "rebalance_frequency": "daily",   // Correlation check frequency
    "correlation_decay": 0.95         // Exponential decay factor
  }
}
```

### Portfolio Rebalancing

Automatic rebalancing based on performance:

```json
{
  "rebalancing": {
    "enabled": true,
    "frequency": "weekly",            // Rebalance frequency
    "threshold": 0.1,                // 10% deviation threshold
    "method": "equal_weight",        // Rebalancing method
    "min_rebalance_amount": 50       // Minimum rebalance size
  }
}
```

## Performance Optimization

### Signal Quality Metrics

Monitor strategy performance:

```json
{
  "performance_tracking": {
    "win_rate_threshold": 0.55,      // Minimum 55% win rate
    "sharpe_ratio_threshold": 1.0,   // Minimum Sharpe ratio
    "max_drawdown_threshold": 0.15,  // Maximum 15% drawdown
    "profit_factor_threshold": 1.2   // Minimum profit factor
  }
}
```

### Strategy Adaptation

Automatic parameter adjustment:

```json
{
  "adaptive_parameters": {
    "enabled": true,
    "adaptation_period": "weekly",    // Adaptation frequency
    "performance_window": 100,       // Trades to evaluate
    "adjustment_factor": 0.1,        // 10% parameter adjustment
    "min_trades_required": 20        // Minimum trades before adaptation
  }
}
```

### Backtesting Integration

Test strategies on historical data:

```bash
# Backtest single strategy
python -m bot.backtest --strategy momentum --days 30

# Backtest strategy combination
python -m bot.backtest --config enhanced_config.json --days 90

# Parameter optimization
python -m bot.optimize --strategy all --metric sharpe_ratio
```

## Advanced Features

### Machine Learning Integration

Optional ML-enhanced signals:

```json
{
  "ml_features": {
    "enabled": false,                // Enable ML features
    "model_type": "random_forest",   // ML model type
    "feature_window": 100,           // Feature calculation window
    "retrain_frequency": "weekly",   // Model retraining frequency
    "confidence_threshold": 0.7      // ML signal confidence threshold
  }
}
```

### Custom Indicators

Add custom technical indicators:

```python
from bot.indicators import BaseIndicator

class CustomRSI(BaseIndicator):
    def __init__(self, period=14, overbought=70, oversold=30):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
    
    def calculate(self, data):
        # Custom RSI calculation
        return rsi_values
```

### Webhook Integration

Real-time notifications:

```json
{
  "webhooks": {
    "trade_execution": "https://your-webhook.com/trades",
    "risk_alerts": "https://your-webhook.com/alerts",
    "performance_reports": "https://your-webhook.com/reports"
  }
}
```

## Best Practices

### Strategy Selection

1. **Market Conditions**: Choose strategies based on current market regime
2. **Backtesting**: Always backtest before live trading
3. **Diversification**: Use multiple uncorrelated strategies
4. **Regular Review**: Monitor and adjust strategy weights

### Risk Management

1. **Start Small**: Begin with minimal position sizes
2. **Gradual Scaling**: Increase size as confidence grows
3. **Regular Monitoring**: Check risk metrics daily
4. **Emergency Plans**: Have clear exit strategies

### Performance Monitoring

1. **Key Metrics**: Track win rate, Sharpe ratio, max drawdown
2. **Regular Reviews**: Analyze performance weekly/monthly
3. **Strategy Attribution**: Understand which strategies perform best
4. **Market Adaptation**: Adjust to changing market conditions

---

**⚠️ Risk Warning**: All trading strategies involve risk. Past performance does not guarantee future results. Always use proper risk management and never trade with money you cannot afford to lose.