"""
Aggressive trading configuration for small account high-risk trading.

Optimized settings for $100 starting capital with higher risk tolerance
for potentially higher returns.
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class AggressiveTradingSettings:
    """Configuration for aggressive trading with small accounts."""
    
    # Account settings
    initial_capital: float = 100.0
    min_trade_size: float = 5.0  # Minimum $5 per trade
    max_position_size_pct: float = 0.8  # Use up to 80% of capital per trade
    
    # Risk management (aggressive but controlled)
    max_risk_per_trade_pct: float = 0.05  # 5% risk per trade
    max_daily_loss_pct: float = 0.15  # 15% max daily loss
    stop_loss_pct: float = 0.02  # 2% stop loss (tight for scalping)
    take_profit_pct: float = 0.04  # 4% take profit (2:1 risk/reward)
    
    # Trading frequency (aggressive scalping)
    max_trades_per_day: int = 25
    min_time_between_trades: int = 1  # 1 minute minimum
    trading_hours_start: int = 9  # 9 AM
    trading_hours_end: int = 21  # 9 PM (extended for crypto)
    
    # Strategy weights (how much to trust each strategy)
    strategy_weights: Dict[str, float] = None
    
    # Signal thresholds
    min_signal_confidence: float = 0.4  # Lower threshold for more trades
    strong_signal_threshold: float = 0.7  # Threshold for larger positions
    
    # Market conditions
    high_volatility_multiplier: float = 1.5  # Increase position size in high vol
    low_volatility_multiplier: float = 0.7  # Decrease position size in low vol
    
    def __post_init__(self):
        """Initialize default strategy weights."""
        if self.strategy_weights is None:
            self.strategy_weights = {
                "Scalping Momentum": 0.4,  # Highest weight for momentum
                "Volatility Breakout": 0.35,  # Good for catching big moves
                "Mean Reversion Scalp": 0.25,  # Counter-trend opportunities
                "MA Crossover": 0.1,  # Lower weight for slower signals
                "RSI Strategy": 0.15  # Moderate weight for confirmation
            }


class AggressiveSymbolSettings:
    """Symbol-specific settings for aggressive trading."""
    
    # Crypto pairs optimized for scalping (high volatility, good liquidity)
    RECOMMENDED_PAIRS = [
        "BTC/USD",   # Most liquid, good for large positions
        "ETH/USD",   # High volatility, good volume
        "SOL/USD",   # Very volatile, good for scalping
        "AVAX/USD",  # High beta, follows BTC with amplification
        "MATIC/USD", # Lower price, good for small accounts
    ]
    
    # Pair-specific settings
    PAIR_SETTINGS = {
        "BTC/USD": {
            "min_move_threshold": 0.003,  # 0.3% minimum move
            "volatility_adjustment": 1.0,
            "max_position_pct": 0.8
        },
        "ETH/USD": {
            "min_move_threshold": 0.004,  # 0.4% minimum move
            "volatility_adjustment": 1.1,
            "max_position_pct": 0.7
        },
        "SOL/USD": {
            "min_move_threshold": 0.006,  # 0.6% minimum move
            "volatility_adjustment": 1.3,
            "max_position_pct": 0.6
        },
        "AVAX/USD": {
            "min_move_threshold": 0.007,  # 0.7% minimum move
            "volatility_adjustment": 1.2,
            "max_position_pct": 0.6
        },
        "MATIC/USD": {
            "min_move_threshold": 0.008,  # 0.8% minimum move
            "volatility_adjustment": 1.4,
            "max_position_pct": 0.5
        }
    }


def get_aggressive_config() -> Dict[str, Any]:
    """
    Get complete aggressive trading configuration.
    
    Returns:
        Dictionary with all aggressive trading settings
    """
    settings = AggressiveTradingSettings()
    symbol_settings = AggressiveSymbolSettings()
    
    return {
        "trading_settings": settings,
        "symbol_settings": symbol_settings,
        "risk_management": {
            "use_trailing_stops": True,
            "trailing_stop_pct": 0.015,  # 1.5% trailing stop
            "break_even_threshold": 0.02,  # Move stop to break-even at 2% profit
            "scale_out_levels": [0.02, 0.035],  # Take partial profits at 2% and 3.5%
            "scale_out_percentages": [0.3, 0.5],  # Take 30% at first level, 50% at second
        },
        "market_conditions": {
            "high_volatility_threshold": 0.03,  # 3% daily range
            "low_volatility_threshold": 0.01,   # 1% daily range
            "trend_strength_threshold": 0.6,    # Minimum trend strength
        },
        "execution": {
            "slippage_tolerance": 0.001,  # 0.1% slippage tolerance
            "max_order_retries": 3,
            "order_timeout_seconds": 30,
            "use_market_orders": True,  # For aggressive entry/exit
        }
    }


def calculate_dynamic_position_size(capital: float, signal_confidence: float, 
                                  volatility: float, settings: AggressiveTradingSettings) -> float:
    """
    Calculate position size dynamically based on multiple factors.
    
    Args:
        capital: Current account capital
        signal_confidence: Confidence level of the trading signal (0.0 to 1.0)
        volatility: Current market volatility measure
        settings: Aggressive trading settings
        
    Returns:
        Position size in USD
    """
    # Base position size
    base_size = capital * settings.max_position_size_pct
    
    # Adjust for signal confidence
    confidence_multiplier = 0.3 + (signal_confidence * 1.4)  # 0.3x to 1.7x
    
    # Adjust for volatility
    if volatility > 0.03:  # High volatility
        vol_multiplier = settings.high_volatility_multiplier
    elif volatility < 0.01:  # Low volatility
        vol_multiplier = settings.low_volatility_multiplier
    else:
        vol_multiplier = 1.0
    
    # Calculate final position size
    position_size = base_size * confidence_multiplier * vol_multiplier
    
    # Apply limits
    position_size = max(position_size, settings.min_trade_size)
    position_size = min(position_size, capital * settings.max_position_size_pct)
    
    return position_size


# Example usage configuration
AGGRESSIVE_STRATEGY_CONFIG = {
    "strategies": [
        {
            "name": "ScalpingMomentumStrategy",
            "params": {
                "lookback_period": 3,
                "volume_threshold": 1.2,
                "momentum_threshold": 0.004
            },
            "weight": 0.4
        },
        {
            "name": "VolatilityBreakoutStrategy", 
            "params": {
                "atr_period": 8,
                "squeeze_threshold": 0.8,
                "breakout_multiplier": 1.1
            },
            "weight": 0.35
        },
        {
            "name": "MeanReversionScalpStrategy",
            "params": {
                "bb_period": 6,
                "bb_std": 1.8,
                "rsi_period": 4
            },
            "weight": 0.25
        }
    ],
    "risk_management": {
        "position_sizing": "dynamic",
        "stop_loss_type": "trailing",
        "profit_taking": "scaled"
    }
}