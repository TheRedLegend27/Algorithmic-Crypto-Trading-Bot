"""
Aggressive trading strategies for higher profit potential with risk management.

These strategies are designed for higher risk/reward scenarios with proper
position sizing and risk controls for small account sizes.
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


class ScalpingMomentumStrategy(BaseStrategy):
    """
    Aggressive scalping strategy that catches quick momentum moves.
    
    Uses short-term price action and volume to identify breakouts.
    Designed for quick entries and exits with tight risk management.
    """
    
    def __init__(self, lookback_period: int = 5, volume_threshold: float = 1.5, 
                 momentum_threshold: float = 0.008):
        """
        Initialize the scalping momentum strategy.
        
        Args:
            lookback_period: Number of periods to look back for momentum
            volume_threshold: Volume multiplier vs average (1.5 = 50% above avg)
            momentum_threshold: Minimum price change % to trigger signal (0.8%)
        """
        super().__init__("Scalping Momentum")
        self.lookback_period = lookback_period
        self.volume_threshold = volume_threshold
        self.momentum_threshold = momentum_threshold
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate aggressive momentum signals."""
        if not self.validate_data(data) or len(data) < self.lookback_period + 10:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate momentum indicators
        data['price_change'] = data['close'].pct_change()
        data['volume_ma'] = data['volume'].rolling(window=10).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        data['momentum'] = data['close'].pct_change(periods=self.lookback_period)
        
        # Calculate volatility for confidence
        data['volatility'] = data['price_change'].rolling(window=10).std()
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Check for momentum breakout with volume confirmation
        strong_momentum = abs(latest['momentum']) > self.momentum_threshold
        volume_spike = latest['volume_ratio'] > self.volume_threshold
        recent_volatility = latest['volatility']
        
        if strong_momentum and volume_spike:
            if latest['momentum'] > 0:
                # Bullish momentum breakout
                confidence = min(0.9, 0.4 + (latest['momentum'] * 50) + 
                               (latest['volume_ratio'] - 1) * 0.3)
                return TradingSignal(
                    action=SignalType.BUY,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=data.index[-1].to_pydatetime(),
                    price=latest['close'],
                    reasoning=f"Bullish momentum breakout: {latest['momentum']:.3f}% with volume spike {latest['volume_ratio']:.2f}x"
                )
            else:
                # Bearish momentum breakout
                confidence = min(0.9, 0.4 + (abs(latest['momentum']) * 50) + 
                               (latest['volume_ratio'] - 1) * 0.3)
                return TradingSignal(
                    action=SignalType.SELL,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=data.index[-1].to_pydatetime(),
                    price=latest['close'],
                    reasoning=f"Bearish momentum breakout: {latest['momentum']:.3f}% with volume spike {latest['volume_ratio']:.2f}x"
                )
        
        return _create_hold_signal(self.name, data, f"No momentum breakout: {latest['momentum']:.3f}%, volume: {latest['volume_ratio']:.2f}x")


class VolatilityBreakoutStrategy(BaseStrategy):
    """
    Strategy that trades volatility breakouts after periods of low volatility.
    
    Looks for price compression followed by explosive moves.
    """
    
    def __init__(self, atr_period: int = 14, squeeze_threshold: float = 0.7, 
                 breakout_multiplier: float = 1.5):
        """
        Initialize the volatility breakout strategy.
        
        Args:
            atr_period: Period for ATR calculation
            squeeze_threshold: Threshold for detecting low volatility (0.7 = 70% of avg)
            breakout_multiplier: ATR multiplier for breakout detection
        """
        super().__init__("Volatility Breakout")
        self.atr_period = atr_period
        self.squeeze_threshold = squeeze_threshold
        self.breakout_multiplier = breakout_multiplier
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate volatility breakout signals."""
        if not self.validate_data(data) or len(data) < self.atr_period + 10:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate ATR and volatility metrics
        data['tr'] = np.maximum(
            np.maximum(
                data['high'] - data['low'],
                abs(data['high'] - data['close'].shift(1))
            ),
            abs(data['low'] - data['close'].shift(1))
        )
        data['atr'] = data['tr'].rolling(window=self.atr_period).mean()
        data['atr_ma'] = data['atr'].rolling(window=20).mean()
        data['atr_ratio'] = data['atr'] / data['atr_ma']
        
        # Bollinger Bands for squeeze detection
        data['bb_mid'] = data['close'].rolling(window=20).mean()
        data['bb_std'] = data['close'].rolling(window=20).std()
        data['bb_upper'] = data['bb_mid'] + (2 * data['bb_std'])
        data['bb_lower'] = data['bb_mid'] - (2 * data['bb_std'])
        data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['bb_mid']
        
        latest = data.iloc[-1]
        prev_5 = data.iloc[-6:-1]  # Last 5 periods
        
        # Check for volatility squeeze (low volatility period)
        recent_squeeze = (prev_5['atr_ratio'] < self.squeeze_threshold).any()
        current_breakout = latest['atr_ratio'] > 1.2  # Current volatility spike
        
        # Price breakout from recent range
        recent_high = prev_5['high'].max()
        recent_low = prev_5['low'].min()
        breakout_threshold = latest['atr'] * self.breakout_multiplier
        
        if recent_squeeze and current_breakout:
            if latest['close'] > recent_high + breakout_threshold:
                # Bullish breakout
                confidence = min(0.95, 0.5 + (latest['atr_ratio'] - 1) * 0.4)
                return TradingSignal(
                    action=SignalType.BUY,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=data.index[-1].to_pydatetime(),
                    price=latest['close'],
                    reasoning=f"Bullish volatility breakout: ATR ratio {latest['atr_ratio']:.2f}, price above {recent_high:.2f}"
                )
            elif latest['close'] < recent_low - breakout_threshold:
                # Bearish breakout
                confidence = min(0.95, 0.5 + (latest['atr_ratio'] - 1) * 0.4)
                return TradingSignal(
                    action=SignalType.SELL,
                    confidence=confidence,
                    strategy=self.name,
                    timestamp=data.index[-1].to_pydatetime(),
                    price=latest['close'],
                    reasoning=f"Bearish volatility breakout: ATR ratio {latest['atr_ratio']:.2f}, price below {recent_low:.2f}"
                )
        
        return _create_hold_signal(self.name, data, f"No breakout: ATR ratio {latest['atr_ratio']:.2f}, squeeze: {recent_squeeze}")


class MeanReversionScalpStrategy(BaseStrategy):
    """
    Aggressive mean reversion strategy for quick scalps.
    
    Looks for extreme price moves away from the mean and bets on quick reversals.
    """
    
    def __init__(self, bb_period: int = 10, bb_std: float = 2.5, rsi_period: int = 7):
        """
        Initialize the mean reversion scalp strategy.
        
        Args:
            bb_period: Bollinger Bands period (shorter for scalping)
            bb_std: Standard deviations for bands (wider for extreme moves)
            rsi_period: RSI period (shorter for quick signals)
        """
        super().__init__("Mean Reversion Scalp")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """Calculate mean reversion scalp signals."""
        if not self.validate_data(data) or len(data) < max(self.bb_period, self.rsi_period) + 5:
            return _create_hold_signal(self.name, data, "Insufficient data")
        
        data = data.copy()
        
        # Calculate Bollinger Bands
        data['bb_mid'] = data['close'].rolling(window=self.bb_period).mean()
        data['bb_std'] = data['close'].rolling(window=self.bb_period).std()
        data['bb_upper'] = data['bb_mid'] + (self.bb_std * data['bb_std'])
        data['bb_lower'] = data['bb_mid'] - (self.bb_std * data['bb_std'])
        
        # Calculate RSI
        delta = data['close'].diff()
        gain = delta.copy()
        loss = delta.copy()
        gain[gain < 0] = 0
        loss[loss > 0] = 0
        loss = abs(loss)
        
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        # Calculate distance from bands
        data['bb_position'] = (data['close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Extreme oversold conditions
        if (latest['close'] <= latest['bb_lower'] and 
            latest['rsi'] < 25 and 
            prev['close'] > prev['bb_lower']):
            
            confidence = min(0.9, 0.6 + (25 - latest['rsi']) / 100 + 
                           (1 - latest['bb_position']) * 0.3)
            return TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=latest['close'],
                reasoning=f"Extreme oversold: RSI {latest['rsi']:.1f}, below BB lower band"
            )
        
        # Extreme overbought conditions
        elif (latest['close'] >= latest['bb_upper'] and 
              latest['rsi'] > 75 and 
              prev['close'] < prev['bb_upper']):
            
            confidence = min(0.9, 0.6 + (latest['rsi'] - 75) / 100 + 
                           (latest['bb_position'] - 1) * 0.3)
            return TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=latest['close'],
                reasoning=f"Extreme overbought: RSI {latest['rsi']:.1f}, above BB upper band"
            )
        
        return _create_hold_signal(self.name, data, f"No extreme condition: RSI {latest['rsi']:.1f}, BB pos {latest['bb_position']:.2f}")


class AggressiveRiskManager:
    """
    Risk management specifically designed for aggressive trading with small accounts.
    
    Implements dynamic position sizing and risk controls for $100 starting capital.
    """
    
    def __init__(self, initial_capital: float = 100.0, max_risk_per_trade: float = 0.05,
                 max_daily_loss: float = 0.15, max_position_size: float = 0.8,
                 max_trades_per_day: int = 20):
        """
        Initialize aggressive risk manager.
        
        Args:
            initial_capital: Starting capital ($100)
            max_risk_per_trade: Max risk per trade (5% of capital)
            max_daily_loss: Max daily loss (15% of capital)
            max_position_size: Max position size (80% of capital for aggressive trading)
            max_trades_per_day: Maximum number of trades per day (default: 20)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.max_trades_per_day = max_trades_per_day
    
    def calculate_position_size(self, signal_confidence: float, current_price: float,
                              stop_loss_pct: float = 0.02) -> float:
        """
        Calculate aggressive position size based on confidence and risk.
        
        Args:
            signal_confidence: Confidence level of the signal (0.0 to 1.0)
            current_price: Current asset price
            stop_loss_pct: Stop loss percentage (2% for aggressive trading)
            
        Returns:
            Position size in USD
        """
        # Base risk amount
        base_risk = self.current_capital * self.max_risk_per_trade
        
        # Scale risk by confidence (higher confidence = larger position)
        confidence_multiplier = 0.5 + (signal_confidence * 1.5)  # 0.5x to 2x
        adjusted_risk = base_risk * confidence_multiplier
        
        # Calculate position size based on stop loss
        position_size = adjusted_risk / stop_loss_pct
        
        # Apply maximum position size limit
        max_position = self.current_capital * self.max_position_size
        position_size = min(position_size, max_position)
        
        # Ensure minimum viable position for small accounts
        min_position = max(5.0, self.current_capital * 0.1)  # At least $5 or 10%
        position_size = max(position_size, min_position)
        
        return position_size
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed based on risk limits.
        
        Returns:
            Tuple of (can_trade, reason)
        """
        # Check daily loss limit
        if self.daily_pnl < -(self.current_capital * self.max_daily_loss):
            return False, f"Daily loss limit reached: ${abs(self.daily_pnl):.2f}"
        
        # Check trade count limit
        if self.trades_today >= self.max_trades_per_day:
            return False, f"Max trades per day reached: {self.trades_today}"
        
        # Check if account is blown (less than 20% of initial capital)
        if self.current_capital < self.initial_capital * 0.2:
            return False, f"Account protection: Capital below 20% of initial"
        
        return True, "Trading allowed"
    
    def update_capital(self, pnl: float):
        """Update capital and daily P&L tracking."""
        self.current_capital += pnl
        self.daily_pnl += pnl
        self.trades_today += 1
        
        log_info(f"Capital updated: ${self.current_capital:.2f}, Daily P&L: ${self.daily_pnl:.2f}")
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at start of each trading day)."""
        self.daily_pnl = 0.0
        self.trades_today = 0
        log_info("Daily risk stats reset")


def create_aggressive_strategy_suite() -> List[BaseStrategy]:
    """
    Create a suite of aggressive strategies optimized for small accounts.
    
    Returns:
        List of aggressive trading strategies
    """
    return [
        ScalpingMomentumStrategy(
            lookback_period=3,  # Very short-term
            volume_threshold=1.3,  # Lower threshold for more signals
            momentum_threshold=0.005  # 0.5% moves
        ),
        VolatilityBreakoutStrategy(
            atr_period=10,  # Shorter period for quicker signals
            squeeze_threshold=0.8,
            breakout_multiplier=1.2  # Lower threshold for more trades
        ),
        MeanReversionScalpStrategy(
            bb_period=8,  # Very short Bollinger Bands
            bb_std=2.0,  # Tighter bands for more signals
            rsi_period=5  # Very responsive RSI
        )
    ]