"""
Enhanced trading strategies with advanced algorithms for cryptocurrency markets.

This module implements sophisticated trading strategies including:
- Volatility-based adjustments
- Momentum strategies with multi-timeframe analysis
- Volume-weighted strategies
- Bollinger Bands with RSI confirmation
- MACD with signal line crossovers
- Strategy backtesting and parameter optimization
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
from abc import ABC, abstractmethod

from bot.strategy import BaseStrategy, TradingSignal, SignalType
from bot.utils import log_info, log_warning, log_error


@dataclass
class StrategyParameters:
    """Configuration parameters for strategies."""
    volatility_lookback: int = 20
    momentum_periods: List[int] = None
    volume_threshold: float = 1.2
    confidence_threshold: float = 0.3
    
    def __post_init__(self):
        if self.momentum_periods is None:
            self.momentum_periods = [5, 10, 20]


@dataclass
class BacktestResult:
    """Results from strategy backtesting."""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    avg_trade_duration: float
    volatility: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'total_return': self.total_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'total_trades': self.total_trades,
            'avg_trade_duration': self.avg_trade_duration,
            'volatility': self.volatility
        }


class VolatilityAdjustedStrategy(BaseStrategy):
    """Base class for strategies with volatility-based adjustments."""
    
    def __init__(self, name: str, volatility_lookback: int = 20):
        super().__init__(name)
        self.volatility_lookback = volatility_lookback
    
    def calculate_volatility_adjustment(self, data: pd.DataFrame) -> float:
        """Calculate volatility adjustment factor."""
        if len(data) < self.volatility_lookback:
            return 1.0
        
        returns = data['close'].pct_change().dropna()
        if len(returns) < self.volatility_lookback:
            return 1.0
        
        # Calculate rolling volatility
        volatility = returns.rolling(window=self.volatility_lookback).std().iloc[-1]
        
        # Normalize volatility (typical crypto volatility is around 0.03-0.05 daily)
        normalized_vol = volatility / 0.04
        
        # Return adjustment factor (higher volatility = more conservative)
        return max(0.5, min(2.0, 1.0 / normalized_vol))


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


class BollingerBandsRSIStrategy(VolatilityAdjustedStrategy):
    """
    Bollinger Bands strategy with RSI confirmation and volatility adjustments.
    """
    
    def __init__(self, bb_period: int = 20, bb_std: float = 2.0, 
                 rsi_period: int = 14, rsi_oversold: float = 30, rsi_overbought: float = 70):
        super().__init__("Bollinger Bands RSI")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate Bollinger Bands with RSI confirmation signals."""
        if not self.validate_data(data) or len(data) < max(self.bb_period, self.rsi_period) + 10:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate Bollinger Bands
        data['bb_middle'] = data['close'].rolling(window=self.bb_period).mean()
        bb_std = data['close'].rolling(window=self.bb_period).std()
        data['bb_upper'] = data['bb_middle'] + (bb_std * self.bb_std)
        data['bb_lower'] = data['bb_middle'] - (bb_std * self.bb_std)
        
        # Calculate RSI
        data['rsi'] = self._calculate_rsi(data['close'], self.rsi_period)
        
        # Calculate Bollinger Band position
        data['bb_position'] = (data['close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])
        
        # Volume analysis
        data['volume_ma'] = data['volume'].rolling(window=10).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        
        # Volatility adjustment
        vol_adjustment = self.calculate_volatility_adjustment(data)
        
        latest = data.iloc[-1]
        current_price = latest['close']
        
        # Bollinger Band squeeze detection
        band_width = (latest['bb_upper'] - latest['bb_lower']) / latest['bb_middle']
        is_squeeze = band_width < 0.1  # Tight bands indicate low volatility
        
        # Signal generation with RSI confirmation
        if (current_price <= latest['bb_lower'] and 
            latest['rsi'] < self.rsi_oversold and 
            latest['volume_ratio'] > 1.1):
            # Oversold bounce signal
            confidence = min(0.85, (0.4 + 
                           (self.rsi_oversold - latest['rsi']) / self.rsi_oversold * 0.3 +
                           (latest['bb_lower'] - current_price) / latest['bb_lower'] * 0.2) * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"BB lower breach with RSI oversold: price {current_price:.2f}, RSI {latest['rsi']:.1f}, vol {latest['volume_ratio']:.2f}x"
            )
        
        elif (current_price >= latest['bb_upper'] and 
              latest['rsi'] > self.rsi_overbought and 
              latest['volume_ratio'] > 1.1):
            # Overbought reversal signal
            confidence = min(0.85, (0.4 + 
                           (latest['rsi'] - self.rsi_overbought) / (100 - self.rsi_overbought) * 0.3 +
                           (current_price - latest['bb_upper']) / latest['bb_upper'] * 0.2) * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"BB upper breach with RSI overbought: price {current_price:.2f}, RSI {latest['rsi']:.1f}, vol {latest['volume_ratio']:.2f}x"
            )
        
        elif is_squeeze and latest['volume_ratio'] > 1.5:
            # Breakout from squeeze
            if current_price > latest['bb_middle'] and latest['rsi'] > 50:
                confidence = min(0.7, (0.3 + (latest['volume_ratio'] - 1) * 0.2) * vol_adjustment)
                return TradingSignal(
                    action=SignalType.BUY,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=current_price,
                    reasoning=f"Bullish breakout from BB squeeze: vol {latest['volume_ratio']:.2f}x, RSI {latest['rsi']:.1f}"
                )
            elif current_price < latest['bb_middle'] and latest['rsi'] < 50:
                confidence = min(0.7, (0.3 + (latest['volume_ratio'] - 1) * 0.2) * vol_adjustment)
                return TradingSignal(
                    action=SignalType.SELL,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=current_price,
                    reasoning=f"Bearish breakdown from BB squeeze: vol {latest['volume_ratio']:.2f}x, RSI {latest['rsi']:.1f}"
                )
        
        return _create_hold_signal(self.name, data, 
                                 f"No BB signal: price {current_price:.2f}, BB {latest['bb_lower']:.2f}-{latest['bb_upper']:.2f}, RSI {latest['rsi']:.1f}")
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI with exponential smoothing."""
        delta = prices.diff()
        gain = delta.copy()
        loss = delta.copy()
        gain[gain < 0] = 0
        loss[loss > 0] = 0
        loss = abs(loss)
        
        avg_gain = gain.ewm(span=period, min_periods=period).mean()
        avg_loss = loss.ewm(span=period, min_periods=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi


class MACDStrategy(VolatilityAdjustedStrategy):
    """
    MACD strategy with signal line crossovers and volatility adjustments.
    """
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        super().__init__("MACD Strategy")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate MACD signals with crossovers."""
        if not self.validate_data(data) or len(data) < self.slow_period + self.signal_period + 10:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate MACD
        ema_fast = data['close'].ewm(span=self.fast_period).mean()
        ema_slow = data['close'].ewm(span=self.slow_period).mean()
        data['macd'] = ema_fast - ema_slow
        data['macd_signal'] = data['macd'].ewm(span=self.signal_period).mean()
        data['macd_histogram'] = data['macd'] - data['macd_signal']
        
        # Volume analysis
        data['volume_ma'] = data['volume'].rolling(window=10).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        
        # Volatility adjustment
        vol_adjustment = self.calculate_volatility_adjustment(data)
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        current_price = latest['close']
        
        # MACD crossover detection
        macd_cross_up = (latest['macd'] > latest['macd_signal'] and 
                        prev['macd'] <= prev['macd_signal'])
        macd_cross_down = (latest['macd'] < latest['macd_signal'] and 
                          prev['macd'] >= prev['macd_signal'])
        
        # Histogram momentum
        histogram_increasing = latest['macd_histogram'] > prev['macd_histogram']
        histogram_decreasing = latest['macd_histogram'] < prev['macd_histogram']
        
        # Zero line analysis
        macd_above_zero = latest['macd'] > 0
        macd_below_zero = latest['macd'] < 0
        
        if macd_cross_up and latest['volume_ratio'] > 1.1:
            # Bullish MACD crossover
            confidence_base = 0.4
            
            # Boost confidence if MACD is above zero (trend confirmation)
            if macd_above_zero:
                confidence_base += 0.2
            
            # Boost confidence with histogram momentum
            if histogram_increasing:
                confidence_base += 0.1
            
            # Volume boost
            confidence_base += min(0.2, (latest['volume_ratio'] - 1) * 0.1)
            
            confidence = min(0.9, confidence_base * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Bullish MACD crossover: MACD {latest['macd']:.4f}, Signal {latest['macd_signal']:.4f}, vol {latest['volume_ratio']:.2f}x"
            )
        
        elif macd_cross_down and latest['volume_ratio'] > 1.1:
            # Bearish MACD crossover
            confidence_base = 0.4
            
            # Boost confidence if MACD is below zero (trend confirmation)
            if macd_below_zero:
                confidence_base += 0.2
            
            # Boost confidence with histogram momentum
            if histogram_decreasing:
                confidence_base += 0.1
            
            # Volume boost
            confidence_base += min(0.2, (latest['volume_ratio'] - 1) * 0.1)
            
            confidence = min(0.9, confidence_base * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Bearish MACD crossover: MACD {latest['macd']:.4f}, Signal {latest['macd_signal']:.4f}, vol {latest['volume_ratio']:.2f}x"
            )
        
        elif abs(latest['macd_histogram']) > abs(prev['macd_histogram']) * 1.5 and latest['volume_ratio'] > 1.3:
            # Strong histogram divergence
            if latest['macd_histogram'] > 0 and histogram_increasing:
                confidence = min(0.7, (0.3 + abs(latest['macd_histogram']) * 1000) * vol_adjustment)
                return TradingSignal(
                    action=SignalType.BUY,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=current_price,
                    reasoning=f"Strong bullish MACD momentum: histogram {latest['macd_histogram']:.4f}, vol {latest['volume_ratio']:.2f}x"
                )
            elif latest['macd_histogram'] < 0 and histogram_decreasing:
                confidence = min(0.7, (0.3 + abs(latest['macd_histogram']) * 1000) * vol_adjustment)
                return TradingSignal(
                    action=SignalType.SELL,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=current_price,
                    reasoning=f"Strong bearish MACD momentum: histogram {latest['macd_histogram']:.4f}, vol {latest['volume_ratio']:.2f}x"
                )
        
        return _create_hold_signal(self.name, data, 
                                 f"No MACD signal: MACD {latest['macd']:.4f}, Signal {latest['macd_signal']:.4f}")


class VolumeWeightedStrategy(VolatilityAdjustedStrategy):
    """
    Volume-weighted strategy using VWAP and volume profile analysis.
    """
    
    def __init__(self, vwap_period: int = 20, volume_threshold: float = 1.5):
        super().__init__("Volume Weighted Strategy")
        self.vwap_period = vwap_period
        self.volume_threshold = volume_threshold
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate volume-weighted signals."""
        if not self.validate_data(data) or len(data) < self.vwap_period + 10:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate VWAP
        data['typical_price'] = (data['high'] + data['low'] + data['close']) / 3
        data['vwap'] = (data['typical_price'] * data['volume']).rolling(window=self.vwap_period).sum() / \
                       data['volume'].rolling(window=self.vwap_period).sum()
        
        # Volume profile analysis
        data['volume_ma'] = data['volume'].rolling(window=20).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        data['volume_trend'] = data['volume'].rolling(window=5).mean() / data['volume'].rolling(window=20).mean()
        
        # Price-volume relationship
        data['price_change'] = data['close'].pct_change()
        data['volume_price_correlation'] = data['price_change'].rolling(window=10).corr(data['volume_ratio'])
        
        # Volatility adjustment
        vol_adjustment = self.calculate_volatility_adjustment(data)
        
        latest = data.iloc[-1]
        current_price = latest['close']
        
        # VWAP deviation
        vwap_deviation = (current_price - latest['vwap']) / latest['vwap']
        
        # Volume breakout detection
        volume_breakout = latest['volume_ratio'] > self.volume_threshold
        volume_trend_up = latest['volume_trend'] > 1.2
        
        if (vwap_deviation < -0.02 and volume_breakout and 
            latest['price_change'] > 0 and volume_trend_up):
            # Price below VWAP with volume breakout and positive price action
            confidence = min(0.8, (0.4 + 
                           abs(vwap_deviation) * 10 +
                           (latest['volume_ratio'] - self.volume_threshold) * 0.2) * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Volume breakout below VWAP: deviation {vwap_deviation:.3f}, vol {latest['volume_ratio']:.2f}x"
            )
        
        elif (vwap_deviation > 0.02 and volume_breakout and 
              latest['price_change'] < 0 and volume_trend_up):
            # Price above VWAP with volume breakout and negative price action
            confidence = min(0.8, (0.4 + 
                           abs(vwap_deviation) * 10 +
                           (latest['volume_ratio'] - self.volume_threshold) * 0.2) * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Volume breakout above VWAP: deviation {vwap_deviation:.3f}, vol {latest['volume_ratio']:.2f}x"
            )
        
        elif abs(vwap_deviation) > 0.05 and latest['volume_ratio'] > 2.0:
            # Extreme VWAP deviation with high volume (mean reversion)
            if vwap_deviation > 0:
                # Price too high, expect reversion
                confidence = min(0.7, (0.3 + abs(vwap_deviation) * 5) * vol_adjustment)
                return TradingSignal(
                    action=SignalType.SELL,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=current_price,
                    reasoning=f"Extreme VWAP deviation reversion: {vwap_deviation:.3f}, vol {latest['volume_ratio']:.2f}x"
                )
            else:
                # Price too low, expect bounce
                confidence = min(0.7, (0.3 + abs(vwap_deviation) * 5) * vol_adjustment)
                return TradingSignal(
                    action=SignalType.BUY,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=datetime.now(),
                    price=current_price,
                    reasoning=f"Extreme VWAP deviation bounce: {vwap_deviation:.3f}, vol {latest['volume_ratio']:.2f}x"
                )
        
        return _create_hold_signal(self.name, data, 
                                 f"No volume signal: VWAP dev {vwap_deviation:.3f}, vol {latest['volume_ratio']:.2f}x")


class MultiTimeframeMomentumStrategy(VolatilityAdjustedStrategy):
    """
    Advanced momentum strategy with multi-timeframe analysis.
    """
    
    def __init__(self, timeframes: List[int] = None, momentum_threshold: float = 0.02):
        super().__init__("Multi-Timeframe Momentum")
        self.timeframes = timeframes or [5, 15, 30, 60]  # Different lookback periods
        self.momentum_threshold = momentum_threshold
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate multi-timeframe momentum signals."""
        if not self.validate_data(data) or len(data) < max(self.timeframes) + 10:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate momentum for each timeframe
        momentum_scores = {}
        for tf in self.timeframes:
            data[f'momentum_{tf}'] = data['close'].pct_change(periods=tf)
            momentum_scores[tf] = data[f'momentum_{tf}'].iloc[-1]
        
        # Calculate volume-adjusted momentum
        data['volume_ma'] = data['volume'].rolling(window=20).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        
        # Volatility adjustment
        vol_adjustment = self.calculate_volatility_adjustment(data)
        
        latest = data.iloc[-1]
        current_price = latest['close']
        
        # Analyze momentum alignment across timeframes
        positive_momentum = sum(1 for score in momentum_scores.values() if score > self.momentum_threshold)
        negative_momentum = sum(1 for score in momentum_scores.values() if score < -self.momentum_threshold)
        
        # Calculate weighted momentum score
        weights = [1.0, 1.5, 2.0, 2.5]  # Give more weight to longer timeframes
        weighted_momentum = sum(momentum_scores[tf] * weight 
                              for tf, weight in zip(self.timeframes, weights)) / sum(weights)
        
        # Momentum acceleration (change in momentum)
        if len(data) >= max(self.timeframes) + 5:
            prev_momentum = {}
            for tf in self.timeframes:
                prev_momentum[tf] = data[f'momentum_{tf}'].iloc[-5]
            
            momentum_acceleration = sum(momentum_scores[tf] - prev_momentum[tf] 
                                      for tf in self.timeframes) / len(self.timeframes)
        else:
            momentum_acceleration = 0
        
        # Strong aligned momentum
        if positive_momentum >= 3 and weighted_momentum > self.momentum_threshold:
            confidence_base = 0.4 + (positive_momentum / len(self.timeframes)) * 0.3
            
            # Boost for momentum acceleration
            if momentum_acceleration > 0:
                confidence_base += min(0.2, momentum_acceleration * 10)
            
            # Volume confirmation
            if latest['volume_ratio'] > 1.2:
                confidence_base += min(0.2, (latest['volume_ratio'] - 1) * 0.1)
            
            confidence = min(0.9, confidence_base * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Strong bullish momentum: {positive_momentum}/{len(self.timeframes)} timeframes, weighted {weighted_momentum:.3f}"
            )
        
        elif negative_momentum >= 3 and weighted_momentum < -self.momentum_threshold:
            confidence_base = 0.4 + (negative_momentum / len(self.timeframes)) * 0.3
            
            # Boost for momentum acceleration
            if momentum_acceleration < 0:
                confidence_base += min(0.2, abs(momentum_acceleration) * 10)
            
            # Volume confirmation
            if latest['volume_ratio'] > 1.2:
                confidence_base += min(0.2, (latest['volume_ratio'] - 1) * 0.1)
            
            confidence = min(0.9, confidence_base * vol_adjustment)
            
            return TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=datetime.now(),
                price=current_price,
                reasoning=f"Strong bearish momentum: {negative_momentum}/{len(self.timeframes)} timeframes, weighted {weighted_momentum:.3f}"
            )
        
        return _create_hold_signal(self.name, data, 
                                 f"Mixed momentum: +{positive_momentum}/-{negative_momentum}, weighted {weighted_momentum:.3f}")


class StrategyBacktester:
    """
    Backtesting engine for trading strategies.
    """
    
    def __init__(self, initial_capital: float = 10000.0, transaction_cost: float = 0.001):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
    
    def backtest_strategy(self, strategy: BaseStrategy, data: pd.DataFrame, 
                         lookback_window: int = 100) -> BacktestResult:
        """
        Backtest a strategy on historical data.
        
        Args:
            strategy: Strategy to backtest
            data: Historical OHLCV data
            lookback_window: Minimum data points needed for strategy
            
        Returns:
            BacktestResult: Backtesting results
        """
        if len(data) < lookback_window + 50:
            log_warning(f"Insufficient data for backtesting {strategy.name}")
            return BacktestResult(0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0)
        
        # Initialize tracking variables
        capital = self.initial_capital
        position = 0.0  # Number of shares/units held
        trades = []
        equity_curve = []
        
        # Start backtesting from lookback_window
        for i in range(lookback_window, len(data)):
            current_data = data.iloc[:i+1]
            current_price = current_data['close'].iloc[-1]
            
            # Calculate current portfolio value
            portfolio_value = capital + (position * current_price)
            equity_curve.append(portfolio_value)
            
            try:
                # Generate signal
                signal = strategy.calculate_signals(current_data)
                
                # Execute trades based on signal
                if signal.action == SignalType.BUY and signal.confidence > 0.3 and position <= 0:
                    # Buy signal - close short position and go long
                    if position < 0:
                        # Close short position
                        capital += abs(position) * current_price * (1 - self.transaction_cost)
                        trades.append({
                            'type': 'cover',
                            'price': current_price,
                            'quantity': abs(position),
                            'timestamp': current_data.index[-1],
                            'pnl': abs(position) * (trades[-1]['price'] - current_price) if trades else 0
                        })
                        position = 0
                    
                    # Go long
                    if capital > current_price * 1.1:  # Ensure we have enough capital
                        quantity = (capital * 0.95) / current_price  # Use 95% of capital
                        cost = quantity * current_price * (1 + self.transaction_cost)
                        if cost <= capital:
                            capital -= cost
                            position = quantity
                        trades.append({
                            'type': 'buy',
                            'price': current_price,
                            'quantity': quantity,
                            'timestamp': current_data.index[-1],
                            'pnl': 0
                        })
                
                elif signal.action == SignalType.SELL and signal.confidence > 0.3 and position >= 0:
                    # Sell signal - close long position and go short
                    if position > 0:
                        # Close long position
                        capital += position * current_price * (1 - self.transaction_cost)
                        trades.append({
                            'type': 'sell',
                            'price': current_price,
                            'quantity': position,
                            'timestamp': current_data.index[-1],
                            'pnl': position * (current_price - trades[-1]['price']) if trades else 0
                        })
                        position = 0
                    
                    # Go short (if allowed) - simplified to avoid complexity
                    # For now, just stay in cash after selling
                    pass
                        
            except Exception as e:
                log_error(f"Error in backtesting {strategy.name}: {str(e)}")
                continue
        
        # Close final position
        if position > 0:  # Only handle long positions now
            final_price = data['close'].iloc[-1]
            capital += position * final_price * (1 - self.transaction_cost)
            final_pnl = position * (final_price - trades[-1]['price']) if trades else 0
            
            trades.append({
                'type': 'close',
                'price': final_price,
                'quantity': position,
                'timestamp': data.index[-1],
                'pnl': final_pnl
            })
            position = 0
        
        # Calculate performance metrics
        final_value = capital  # Position should be 0 after closing
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # Cap extreme returns to avoid numerical issues
        total_return = max(-0.99, min(total_return, 10.0))
        
        # Calculate other metrics
        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
            
            # Max drawdown
            peak = pd.Series(equity_curve).expanding().max()
            drawdown = (pd.Series(equity_curve) - peak) / peak
            max_drawdown = drawdown.min()
            
            volatility = returns.std() * np.sqrt(252)
        else:
            sharpe_ratio = 0
            max_drawdown = 0
            volatility = 0
        
        # Win rate
        profitable_trades = [t for t in trades if t['pnl'] > 0]
        win_rate = len(profitable_trades) / len(trades) if trades else 0
        
        # Average trade duration (simplified)
        avg_trade_duration = len(data) / len(trades) if trades else 0
        
        return BacktestResult(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=len(trades),
            avg_trade_duration=avg_trade_duration,
            volatility=volatility
        )
    
    def optimize_parameters(self, strategy_class, data: pd.DataFrame, 
                          param_ranges: Dict[str, List]) -> Tuple[Dict, BacktestResult]:
        """
        Optimize strategy parameters using grid search.
        
        Args:
            strategy_class: Strategy class to optimize
            data: Historical data for optimization
            param_ranges: Dictionary of parameter ranges to test
            
        Returns:
            Tuple of best parameters and best result
        """
        best_result = None
        best_params = None
        best_score = -np.inf
        
        # Generate parameter combinations
        import itertools
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        
        for param_combo in itertools.product(*param_values):
            params = dict(zip(param_names, param_combo))
            
            try:
                # Create strategy with these parameters
                strategy = strategy_class(**params)
                
                # Backtest
                result = self.backtest_strategy(strategy, data)
                
                # Score based on risk-adjusted return
                score = result.sharpe_ratio if result.sharpe_ratio != 0 else -1
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = result
                    
            except Exception as e:
                log_error(f"Error optimizing parameters {params}: {str(e)}")
                continue
        
        return best_params, best_result


def create_enhanced_strategy_suite() -> List[BaseStrategy]:
    """
    Create enhanced strategy suite with advanced algorithms.
    
    Returns:
        List of enhanced trading strategies with volatility adjustments
    """
    return [
        # Original enhanced strategies
        EnhancedMomentumStrategy(
            short_period=3,
            medium_period=8,
            volume_threshold=1.1,
            momentum_threshold=0.003
        ),
        PriceActionStrategy(
            lookback=15,
            min_body_pct=0.002
        ),
        MultiTimeframeStrategy(
            fast_ma=5,
            slow_ma=15,
            trend_ma=30
        ),
        
        # New advanced strategies
        BollingerBandsRSIStrategy(
            bb_period=20,
            bb_std=2.0,
            rsi_period=14,
            rsi_oversold=30,
            rsi_overbought=70
        ),
        MACDStrategy(
            fast_period=12,
            slow_period=26,
            signal_period=9
        ),
        VolumeWeightedStrategy(
            vwap_period=20,
            volume_threshold=1.5
        ),
        MultiTimeframeMomentumStrategy(
            timeframes=[5, 15, 30, 60],
            momentum_threshold=0.02
        )
    ]


def create_conservative_strategy_suite() -> List[BaseStrategy]:
    """
    Create conservative strategy suite with higher thresholds.
    
    Returns:
        List of conservative trading strategies
    """
    return [
        BollingerBandsRSIStrategy(
            bb_period=30,
            bb_std=2.5,
            rsi_period=21,
            rsi_oversold=25,
            rsi_overbought=75
        ),
        MACDStrategy(
            fast_period=15,
            slow_period=35,
            signal_period=12
        ),
        VolumeWeightedStrategy(
            vwap_period=30,
            volume_threshold=2.0
        ),
        MultiTimeframeMomentumStrategy(
            timeframes=[15, 30, 60, 120],
            momentum_threshold=0.03
        )
    ]


class EnhancedStrategyEngine:
    """
    Enhanced strategy engine that manages multiple strategies and provides
    weighted signal generation, backtesting, and parameter optimization.
    """
    
    def __init__(self, strategies: List[BaseStrategy], parameters: StrategyParameters = None):
        """
        Initialize the enhanced strategy engine.
        
        Args:
            strategies: List of trading strategies
            parameters: Strategy parameters configuration
        """
        self.strategies = strategies
        self.parameters = parameters or StrategyParameters()
        self.strategy_weights = {strategy.name: 1.0 for strategy in strategies}
        self.backtester = StrategyBacktester()
        
        # Performance tracking
        self.strategy_performance = {}
        self.last_signals = {}
        
        log_info(f"Enhanced strategy engine initialized with {len(strategies)} strategies")
    
    def add_strategy(self, strategy: BaseStrategy, weight: float = 1.0) -> None:
        """
        Add a new strategy to the engine.
        
        Args:
            strategy: Strategy to add
            weight: Weight for signal aggregation
        """
        self.strategies.append(strategy)
        self.strategy_weights[strategy.name] = weight
        log_info(f"Added strategy {strategy.name} with weight {weight}")
    
    def remove_strategy(self, strategy_name: str) -> bool:
        """
        Remove a strategy from the engine.
        
        Args:
            strategy_name: Name of strategy to remove
            
        Returns:
            bool: True if strategy was removed, False if not found
        """
        for i, strategy in enumerate(self.strategies):
            if strategy.name == strategy_name:
                self.strategies.pop(i)
                self.strategy_weights.pop(strategy_name, None)
                self.strategy_performance.pop(strategy_name, None)
                self.last_signals.pop(strategy_name, None)
                log_info(f"Removed strategy {strategy_name}")
                return True
        
        log_warning(f"Strategy {strategy_name} not found for removal")
        return False
    
    def calculate_weighted_signal(self, market_data: pd.DataFrame) -> Optional['TradingSignal']:
        """
        Calculate weighted trading signal from all strategies.
        
        Args:
            market_data: Market data for signal calculation
            
        Returns:
            Aggregated trading signal or None if no valid signals
        """
        try:
            if market_data is None or market_data.empty:
                return None
            
            signals = []
            total_weight = 0.0
            
            # Get signals from all strategies
            for strategy in self.strategies:
                try:
                    signal = strategy.generate_signal(market_data)
                    if signal and signal.confidence >= self.parameters.confidence_threshold:
                        weight = self.strategy_weights.get(strategy.name, 1.0)
                        signals.append((signal, weight))
                        total_weight += weight
                        
                        # Store last signal for tracking
                        self.last_signals[strategy.name] = signal
                        
                except Exception as e:
                    log_error(f"Error generating signal from {strategy.name}: {e}")
                    continue
            
            if not signals or total_weight == 0:
                return None
            
            # Calculate weighted averages
            weighted_confidence = sum(signal.confidence * weight for signal, weight in signals) / total_weight
            
            # Determine action based on weighted signals
            buy_weight = sum(weight for signal, weight in signals if signal.action == SignalType.BUY)
            sell_weight = sum(weight for signal, weight in signals if signal.action == SignalType.SELL)
            
            if buy_weight > sell_weight:
                action = SignalType.BUY
            elif sell_weight > buy_weight:
                action = SignalType.SELL
            else:
                action = SignalType.HOLD
            
            # Create aggregated signal
            from bot.strategy import TradingSignal
            aggregated_signal = TradingSignal(
                action=action,
                confidence=weighted_confidence,
                price=market_data['close'].iloc[-1] if 'close' in market_data.columns else 0.0,
                timestamp=datetime.now(),
                metadata={
                    'strategy_count': len(signals),
                    'total_weight': total_weight,
                    'buy_weight': buy_weight,
                    'sell_weight': sell_weight,
                    'contributing_strategies': [signal.metadata.get('strategy', 'unknown') 
                                              for signal, _ in signals]
                }
            )
            
            return aggregated_signal
            
        except Exception as e:
            log_error(f"Error calculating weighted signal: {e}")
            return None
    
    def backtest_strategy(self, historical_data: pd.DataFrame, strategy: BaseStrategy) -> BacktestResult:
        """
        Backtest a specific strategy.
        
        Args:
            historical_data: Historical market data
            strategy: Strategy to backtest
            
        Returns:
            Backtesting results
        """
        return self.backtester.backtest_strategy(strategy, historical_data)
    
    def backtest_all_strategies(self, historical_data: pd.DataFrame) -> Dict[str, BacktestResult]:
        """
        Backtest all strategies in the engine.
        
        Args:
            historical_data: Historical market data
            
        Returns:
            Dictionary of strategy names to backtest results
        """
        results = {}
        
        for strategy in self.strategies:
            try:
                result = self.backtest_strategy(historical_data, strategy)
                results[strategy.name] = result
                
                # Update performance tracking
                self.strategy_performance[strategy.name] = {
                    'total_return': result.total_return,
                    'sharpe_ratio': result.sharpe_ratio,
                    'win_rate': result.win_rate,
                    'max_drawdown': result.max_drawdown,
                    'last_updated': datetime.now()
                }
                
            except Exception as e:
                log_error(f"Error backtesting {strategy.name}: {e}")
                continue
        
        return results
    
    def optimize_parameters(self, strategy: BaseStrategy, data: pd.DataFrame) -> Dict:
        """
        Optimize parameters for a specific strategy.
        
        Args:
            strategy: Strategy to optimize
            data: Historical data for optimization
            
        Returns:
            Dictionary of optimized parameters
        """
        # Define parameter ranges based on strategy type
        param_ranges = self._get_parameter_ranges(strategy)
        
        if not param_ranges:
            log_warning(f"No parameter ranges defined for {strategy.name}")
            return {}
        
        best_params, best_result = self.backtester.optimize_parameters(
            strategy.__class__, data, param_ranges
        )
        
        if best_params:
            log_info(f"Optimized parameters for {strategy.name}: {best_params}")
            log_info(f"Best result - Return: {best_result.total_return:.2%}, "
                    f"Sharpe: {best_result.sharpe_ratio:.2f}")
        
        return best_params or {}
    
    def _get_parameter_ranges(self, strategy: BaseStrategy) -> Dict[str, List]:
        """
        Get parameter ranges for optimization based on strategy type.
        
        Args:
            strategy: Strategy to get ranges for
            
        Returns:
            Dictionary of parameter ranges
        """
        if isinstance(strategy, BollingerBandsRSIStrategy):
            return {
                'bb_period': [15, 20, 25, 30],
                'bb_std': [1.5, 2.0, 2.5],
                'rsi_period': [10, 14, 21],
                'rsi_oversold': [20, 25, 30],
                'rsi_overbought': [70, 75, 80]
            }
        elif isinstance(strategy, MACDStrategy):
            return {
                'fast_period': [8, 12, 16],
                'slow_period': [21, 26, 31],
                'signal_period': [6, 9, 12]
            }
        elif isinstance(strategy, VolumeWeightedStrategy):
            return {
                'vwap_period': [15, 20, 25, 30],
                'volume_threshold': [1.2, 1.5, 2.0]
            }
        elif isinstance(strategy, EnhancedMomentumStrategy):
            return {
                'short_period': [2, 3, 5],
                'medium_period': [5, 8, 13],
                'volume_threshold': [1.0, 1.1, 1.2],
                'momentum_threshold': [0.001, 0.003, 0.005]
            }
        else:
            return {}
    
    def get_strategy_performance(self) -> Dict[str, Dict]:
        """
        Get performance metrics for all strategies.
        
        Returns:
            Dictionary of strategy performance metrics
        """
        return self.strategy_performance.copy()
    
    def update_strategy_weights(self, performance_based: bool = True) -> None:
        """
        Update strategy weights based on performance.
        
        Args:
            performance_based: Whether to use performance-based weighting
        """
        if not performance_based or not self.strategy_performance:
            # Equal weighting
            for strategy in self.strategies:
                self.strategy_weights[strategy.name] = 1.0
            return
        
        # Performance-based weighting
        total_score = 0.0
        strategy_scores = {}
        
        for strategy_name, perf in self.strategy_performance.items():
            # Calculate composite score
            score = (
                perf.get('sharpe_ratio', 0) * 0.4 +
                perf.get('total_return', 0) * 0.3 +
                perf.get('win_rate', 0) * 0.2 +
                (1 - abs(perf.get('max_drawdown', 0))) * 0.1
            )
            
            # Ensure positive weights
            score = max(score, 0.1)
            strategy_scores[strategy_name] = score
            total_score += score
        
        # Normalize weights
        if total_score > 0:
            for strategy_name in strategy_scores:
                self.strategy_weights[strategy_name] = strategy_scores[strategy_name] / total_score
        
        log_info(f"Updated strategy weights: {self.strategy_weights}")
    
    def get_engine_status(self) -> Dict[str, Any]:
        """
        Get current engine status and statistics.
        
        Returns:
            Dictionary with engine status information
        """
        return {
            'strategy_count': len(self.strategies),
            'strategy_names': [s.name for s in self.strategies],
            'strategy_weights': self.strategy_weights.copy(),
            'last_signals': {name: signal.action.value if signal else None 
                           for name, signal in self.last_signals.items()},
            'performance_tracked': len(self.strategy_performance),
            'parameters': {
                'volatility_lookback': self.parameters.volatility_lookback,
                'confidence_threshold': self.parameters.confidence_threshold,
                'volume_threshold': self.parameters.volume_threshold
            }
        }