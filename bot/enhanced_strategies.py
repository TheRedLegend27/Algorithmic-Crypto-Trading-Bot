"""
Enhanced aggressive trading strategies with more sensitive parameters
and additional signal generation techniques.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from bot.strategy import BaseStrategy, TradingSignal, SignalType
from bot.utils import log_info, log_warning


def _create_hold_signal(strategy_name: str, data: pd.DataFrame, reasoning: str) -> TradingSignal:
    """Helper function to create HOLD signals."""
    return TradingSignal(
        action=SignalType.HOLD,
        confidence=0.0,
        strategy=strategy_name,
        timestamp=datetime.now(),
        price=data['close'].iloc[-1] if not data.empty else 0.0,
        reasoning=reasoning
    )


class EnhancedMomentumStrategy(BaseStrategy):
    """
    Enhanced momentum strategy with multiple timeframe analysis
    and more sensitive signal detection.
    """
    
    def __init__(self, short_period: int = 3, medium_period: int = 8, 
                 volume_threshold: float = 1.1, momentum_threshold: float = 0.003):
        """
        Initialize enhanced momentum strategy.
        
        Args:
            short_period: Short-term momentum period
            medium_period: Medium-term momentum period  
            volume_threshold: Volume multiplier (1.1 = 10% above average)
            momentum_threshold: Minimum momentum threshold (0.3%)
        """
        super().__init__("Enhanced Momentum")
        self.short_period = short_period
        self.medium_period = medium_period
        self.volume_threshold = volume_threshold
        self.momentum_threshold = momentum_threshold
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate enhanced momentum signals."""
        if not self.validate_data(data) or len(data) < self.medium_period + 10:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate multiple momentum indicators
        data['price_change'] = data['close'].pct_change()
        data['short_momentum'] = data['close'].pct_change(periods=self.short_period)
        data['medium_momentum'] = data['close'].pct_change(periods=self.medium_period)
        
        # Volume analysis
        data['volume_ma'] = data['volume'].rolling(window=10).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        
        # Price acceleration (momentum of momentum)
        data['momentum_change'] = data['short_momentum'].diff()
        
        # Volatility context
        data['volatility'] = data['price_change'].rolling(window=10).std()
        data['vol_ma'] = data['volatility'].rolling(window=20).mean()
        data['vol_ratio'] = data['volatility'] / data['vol_ma']
        
        latest = data.iloc[-1]
        
        # Multi-factor signal generation
        short_mom = latest['short_momentum']
        medium_mom = latest['medium_momentum']
        vol_ratio = latest['volume_ratio']
        mom_accel = latest['momentum_change']
        
        # Check for momentum alignment
        momentum_aligned = (short_mom > 0 and medium_mom > 0) or (short_mom < 0 and medium_mom < 0)
        volume_support = vol_ratio > self.volume_threshold
        strong_momentum = abs(short_mom) > self.momentum_threshold
        
        if momentum_aligned and volume_support and strong_momentum:
            if short_mom > 0:
                # Bullish momentum
                confidence = min(0.9, 0.3 + abs(short_mom) * 30 + 
                               (vol_ratio - 1) * 0.2 + 
                               (abs(mom_accel) * 100 if mom_accel > 0 else 0))
                return TradingSignal(
                    action=SignalType.BUY,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=latest['close'],
                    reasoning=f"Bullish momentum: {short_mom:.3f}% short, {medium_mom:.3f}% medium, vol {vol_ratio:.2f}x"
                )
            else:
                # Bearish momentum
                confidence = min(0.9, 0.3 + abs(short_mom) * 30 + 
                               (vol_ratio - 1) * 0.2 + 
                               (abs(mom_accel) * 100 if mom_accel < 0 else 0))
                return TradingSignal(
                    action=SignalType.SELL,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=latest['close'],
                    reasoning=f"Bearish momentum: {short_mom:.3f}% short, {medium_mom:.3f}% medium, vol {vol_ratio:.2f}x"
                )
        
        return _create_hold_signal(self.name, data, 
                                 f"No momentum signal: {short_mom:.3f}%, vol: {vol_ratio:.2f}x")


class PriceActionStrategy(BaseStrategy):
    """
    Pure price action strategy focusing on candlestick patterns
    and support/resistance levels.
    """
    
    def __init__(self, lookback: int = 20, min_body_pct: float = 0.002):
        """
        Initialize price action strategy.
        
        Args:
            lookback: Periods to look back for S/R levels
            min_body_pct: Minimum candle body size (0.2%)
        """
        super().__init__("Price Action")
        self.lookback = lookback
        self.min_body_pct = min_body_pct
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate price action signals."""
        if not self.validate_data(data) or len(data) < self.lookback + 5:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate candle properties
        data['body'] = abs(data['close'] - data['open'])
        data['body_pct'] = data['body'] / data['close']
        data['upper_shadow'] = data['high'] - data[['open', 'close']].max(axis=1)
        data['lower_shadow'] = data[['open', 'close']].min(axis=1) - data['low']
        data['total_range'] = data['high'] - data['low']
        
        # Support and resistance levels
        recent_data = data.tail(self.lookback)
        resistance = recent_data['high'].max()
        support = recent_data['low'].min()
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        current_price = latest['close']
        
        # Pattern recognition
        is_bullish_candle = latest['close'] > latest['open']
        is_bearish_candle = latest['close'] < latest['open']
        has_significant_body = latest['body_pct'] > self.min_body_pct
        
        # Breakout detection
        resistance_break = current_price > resistance * 1.001  # 0.1% above resistance
        support_break = current_price < support * 0.999  # 0.1% below support
        
        # Volume confirmation
        data['volume_ma'] = data['volume'].rolling(window=10).mean()
        volume_above_avg = latest['volume'] > data['volume_ma'].iloc[-1] * 1.2
        
        if resistance_break and is_bullish_candle and has_significant_body and volume_above_avg:
            # Bullish breakout
            distance_from_resistance = (current_price - resistance) / resistance
            confidence = min(0.85, 0.4 + distance_from_resistance * 100)
            return TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Bullish breakout above resistance ${resistance:.2f}, body {latest['body_pct']:.3f}%"
            )
        
        elif support_break and is_bearish_candle and has_significant_body and volume_above_avg:
            # Bearish breakdown
            distance_from_support = (support - current_price) / support
            confidence = min(0.85, 0.4 + distance_from_support * 100)
            return TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Bearish breakdown below support ${support:.2f}, body {latest['body_pct']:.3f}%"
            )
        
        return _create_hold_signal(self.name, data, 
                                 f"No breakout: price ${current_price:.2f}, S/R ${support:.2f}-${resistance:.2f}")


class MultiTimeframeStrategy(BaseStrategy):
    """
    Strategy that analyzes multiple timeframes to confirm signals.
    Uses the current data as short-term and creates longer-term views.
    """
    
    def __init__(self, fast_ma: int = 5, slow_ma: int = 15, trend_ma: int = 50):
        """
        Initialize multi-timeframe strategy.
        
        Args:
            fast_ma: Fast moving average period
            slow_ma: Slow moving average period  
            trend_ma: Trend moving average period
        """
        super().__init__("Multi-Timeframe")
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.trend_ma = trend_ma
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate multi-timeframe signals."""
        if not self.validate_data(data) or len(data) < self.trend_ma + 5:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate moving averages
        data['fast_ma'] = data['close'].rolling(window=self.fast_ma).mean()
        data['slow_ma'] = data['close'].rolling(window=self.slow_ma).mean()
        data['trend_ma'] = data['close'].rolling(window=self.trend_ma).mean()
        
        # Calculate slopes (trend direction)
        data['fast_slope'] = data['fast_ma'].diff(3)  # 3-period slope
        data['slow_slope'] = data['slow_ma'].diff(3)
        data['trend_slope'] = data['trend_ma'].diff(5)  # 5-period slope
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        current_price = latest['close']
        
        # Trend alignment
        bullish_trend = (latest['fast_ma'] > latest['slow_ma'] > latest['trend_ma'] and
                        latest['trend_slope'] > 0)
        bearish_trend = (latest['fast_ma'] < latest['slow_ma'] < latest['trend_ma'] and
                        latest['trend_slope'] < 0)
        
        # Crossover detection
        fast_cross_up = (latest['fast_ma'] > latest['slow_ma'] and 
                        prev['fast_ma'] <= prev['slow_ma'])
        fast_cross_down = (latest['fast_ma'] < latest['slow_ma'] and 
                          prev['fast_ma'] >= prev['slow_ma'])
        
        # Price position relative to MAs
        above_all_mas = current_price > max(latest['fast_ma'], latest['slow_ma'], latest['trend_ma'])
        below_all_mas = current_price < min(latest['fast_ma'], latest['slow_ma'], latest['trend_ma'])
        
        if fast_cross_up and bullish_trend:
            # Strong bullish signal
            confidence = min(0.8, 0.5 + abs(latest['trend_slope']) * 1000)
            return TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Bullish MA crossover with trend alignment, slope {latest['trend_slope']:.4f}"
            )
        
        elif fast_cross_down and bearish_trend:
            # Strong bearish signal
            confidence = min(0.8, 0.5 + abs(latest['trend_slope']) * 1000)
            return TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Bearish MA crossover with trend alignment, slope {latest['trend_slope']:.4f}"
            )
        
        elif above_all_mas and latest['fast_slope'] > 0 and latest['slow_slope'] > 0:
            # Momentum continuation buy
            confidence = 0.4 + abs(latest['fast_slope']) * 500
            return TradingSignal(
                action=SignalType.BUY,
                confidence=min(confidence, 0.7),
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Momentum continuation above MAs, fast slope {latest['fast_slope']:.4f}"
            )
        
        elif below_all_mas and latest['fast_slope'] < 0 and latest['slow_slope'] < 0:
            # Momentum continuation sell
            confidence = 0.4 + abs(latest['fast_slope']) * 500
            return TradingSignal(
                action=SignalType.SELL,
                confidence=min(confidence, 0.7),
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Momentum continuation below MAs, fast slope {latest['fast_slope']:.4f}"
            )
        
        return _create_hold_signal(self.name, data, 
                                 f"No clear trend signal, price vs MAs: {current_price:.2f} vs {latest['trend_ma']:.2f}")


def create_enhanced_strategy_suite() -> List[BaseStrategy]:
    """
    Create enhanced strategy suite with more sensitive parameters.
    
    Returns:
        List of enhanced trading strategies
    """
    return [
        EnhancedMomentumStrategy(
            short_period=3,
            medium_period=8,
            volume_threshold=1.1,  # Only 10% above average
            momentum_threshold=0.003  # 0.3% moves
        ),
        PriceActionStrategy(
            lookback=15,
            min_body_pct=0.002  # 0.2% minimum candle body
        ),
        MultiTimeframeStrategy(
            fast_ma=5,
            slow_ma=15,
            trend_ma=30  # Shorter for more signals
        )
    ]