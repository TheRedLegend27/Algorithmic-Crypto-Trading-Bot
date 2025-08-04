
# Aggressive Strategy Configuration for $480 Capital
AGGRESSIVE_STRATEGY_CONFIG = {
    # Strategy weights optimized for small capital aggressive trading
    'strategy_weights': {
        'enhanced_momentum': 0.4,      # High momentum for quick gains
        'volatility_breakout': 0.3,    # Breakout trading for big moves
        'price_action': 0.2,           # Quick scalping opportunities
        'mean_reversion': 0.1          # Minimal conservative plays
    },
    
    # Aggressive parameters for each strategy
    'enhanced_momentum': {
        'momentum_threshold': 0.002,    # Lower threshold = more signals
        'volume_threshold': 1.05,       # Lower volume requirement
        'confidence_multiplier': 1.2,   # Boost signal confidence
    },
    
    'volatility_breakout': {
        'breakout_threshold': 0.015,    # 1.5% breakout threshold
        'volume_confirmation': True,    # Require volume confirmation
        'false_breakout_filter': 0.8,  # Less strict filtering
    },
    
    'price_action': {
        'min_body_pct': 0.001,         # Smaller candle body requirement
        'lookback_periods': 10,        # Shorter lookback for faster signals
        'signal_strength_multiplier': 1.3,
    },
    
    # Risk management per strategy
    'risk_management': {
        'stop_loss_pct': 0.06,         # 6% stop loss
        'take_profit_pct': 0.18,       # 18% take profit (3:1 ratio)
        'trailing_stop_pct': 0.04,     # 4% trailing stop
        'max_holding_hours': 24,       # Don't hold positions too long
    },
    
    # Market regime preferences
    'regime_preferences': {
        'high_volatility': 1.5,        # Boost signals in high volatility
        'trending_bull': 1.3,          # Strong bull market preference
        'trending_bear': 1.2,          # Also trade bear markets aggressively
        'ranging': 0.5,                # Reduce ranging market activity
        'low_volatility': 0.3,         # Minimal low volatility trading
    }
}
