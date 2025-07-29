"""
Trading strategy implementations.

This module contains the implementation of various trading strategies
for the crypto trading bot, including:
- BaseStrategy: Abstract base class for all strategies
- MovingAverageCrossover: Strategy based on MA crossovers
- RSIStrategy: Strategy based on RSI overbought/oversold conditions
- SignalGenerator: Class to orchestrate and combine multiple strategies
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np

from bot.utils import log_info, log_warning, log_error


class SignalType(Enum):
    """Enum for different types of trading signals."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradingSignal:
    """Data class for trading signals."""
    action: SignalType
    confidence: float  # 0.0 to 1.0
    strategy: str
    timestamp: datetime
    price: float
    reasoning: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    def __init__(self, name: str):
        """
        Initialize the strategy.
        
        Args:
            name: Name of the strategy
        """
        self.name = name
        self.last_signal: Optional[TradingSignal] = None
    
    @abstractmethod
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """
        Calculate trading signals based on the provided data.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            TradingSignal: The generated trading signal
        """
        pass
    
    def get_signal_strength(self) -> float:
        """
        Get the strength of the last signal.
        
        Returns:
            float: Signal strength between 0.0 and 1.0
        """
        return self.last_signal.confidence if self.last_signal else 0.0
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate that the data contains the required columns for this strategy.
        
        Args:
            data: DataFrame to validate
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        if data is None or data.empty:
            log_warning(f"{self.name}: Empty data provided")
            return False
            
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            log_warning(f"{self.name}: Missing required columns: {missing_columns}")
            return False
            
        return True


class MovingAverageCrossover(BaseStrategy):
    """
    Moving Average Crossover strategy implementation.
    
    Generates buy signals when the fast MA crosses above the slow MA,
    and sell signals when the fast MA crosses below the slow MA.
    """
    
    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        """
        Initialize the Moving Average Crossover strategy.
        
        Args:
            fast_period: Period for the fast moving average
            slow_period: Period for the slow moving average
        """
        super().__init__("MA Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        
        if fast_period >= slow_period:
            log_warning(f"{self.name}: Fast period should be less than slow period")
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """
        Calculate trading signals based on moving average crossovers.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            TradingSignal: The generated trading signal
        """
        if not self.validate_data(data):
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="Invalid data for strategy calculation"
            )
            
        # Check if we have enough data points
        if len(data) < self.slow_period:
            log_warning(f"{self.name}: Not enough data points for calculation")
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1],
                reasoning="Insufficient data points for calculation"
            )
            
        # Calculate moving averages
        data = data.copy()
        data['fast_ma'] = data['close'].rolling(window=self.fast_period).mean()
        data['slow_ma'] = data['close'].rolling(window=self.slow_period).mean()
        
        # Drop NaN values
        data = data.dropna()
        
        if len(data) < 2:
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="Insufficient data after calculating indicators"
            )
            
        # Get the last two rows to check for crossover
        last_row = data.iloc[-1]
        prev_row = data.iloc[-2]
        
        # Current state
        current_fast_ma = last_row['fast_ma']
        current_slow_ma = last_row['slow_ma']
        
        # Previous state
        prev_fast_ma = prev_row['fast_ma']
        prev_slow_ma = prev_row['slow_ma']
        
        # Current price
        current_price = last_row['close']
        
        # Check for crossover
        if prev_fast_ma <= prev_slow_ma and current_fast_ma > current_slow_ma:
            # Bullish crossover (fast MA crosses above slow MA)
            confidence = self._calculate_confidence(current_fast_ma, current_slow_ma, current_price)
            signal = TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=current_price,
                reasoning=f"Bullish crossover: Fast MA ({current_fast_ma:.2f}) crossed above Slow MA ({current_slow_ma:.2f})"
            )
        elif prev_fast_ma >= prev_slow_ma and current_fast_ma < current_slow_ma:
            # Bearish crossover (fast MA crosses below slow MA)
            confidence = self._calculate_confidence(current_fast_ma, current_slow_ma, current_price)
            signal = TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=current_price,
                reasoning=f"Bearish crossover: Fast MA ({current_fast_ma:.2f}) crossed below Slow MA ({current_slow_ma:.2f})"
            )
        else:
            # No crossover
            signal = TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=current_price,
                reasoning=f"No crossover: Fast MA ({current_fast_ma:.2f}) vs Slow MA ({current_slow_ma:.2f})"
            )
            
        self.last_signal = signal
        return signal
    
    def _calculate_confidence(self, fast_ma: float, slow_ma: float, current_price: float) -> float:
        """
        Calculate the confidence level of the signal.
        
        Args:
            fast_ma: Current fast moving average
            slow_ma: Current slow moving average
            current_price: Current price
            
        Returns:
            float: Confidence level between 0.0 and 1.0
        """
        # Calculate the percentage difference between the MAs
        ma_diff_pct = abs(fast_ma - slow_ma) / slow_ma
        
        # Calculate the percentage difference between current price and slow MA
        price_ma_diff_pct = abs(current_price - slow_ma) / slow_ma
        
        # Combine the two factors to determine confidence
        # Higher MA difference and price-MA difference increase confidence
        confidence = min(0.3 + ma_diff_pct * 5 + price_ma_diff_pct * 2, 1.0)
        
        return confidence


class RSIStrategy(BaseStrategy):
    """
    Relative Strength Index (RSI) strategy implementation.
    
    Generates buy signals when RSI is below the oversold threshold,
    and sell signals when RSI is above the overbought threshold.
    """
    
    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        """
        Initialize the RSI strategy.
        
        Args:
            period: Period for RSI calculation
            oversold: Threshold for oversold condition (typically 30)
            overbought: Threshold for overbought condition (typically 70)
        """
        super().__init__("RSI Strategy")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """
        Calculate trading signals based on RSI values.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            TradingSignal: The generated trading signal
        """
        if not self.validate_data(data):
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="Invalid data for strategy calculation"
            )
            
        # Check if we have enough data points
        if len(data) < self.period + 1:
            log_warning(f"{self.name}: Not enough data points for calculation")
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1],
                reasoning="Insufficient data points for calculation"
            )
            
        # Calculate RSI
        data = data.copy()
        data['rsi'] = self._calculate_rsi(data['close'], self.period)
        
        # Drop NaN values
        data = data.dropna()
        
        if len(data) < 2:
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="Insufficient data after calculating indicators"
            )
            
        # Get the last two rows to check for crossover
        last_row = data.iloc[-1]
        prev_row = data.iloc[-2]
        
        # Current state
        current_rsi = last_row['rsi']
        prev_rsi = prev_row['rsi']
        current_price = last_row['close']
        
        # Check for oversold/overbought conditions
        if current_rsi < self.oversold and prev_rsi >= self.oversold:
            # RSI crossed below oversold threshold (buy signal)
            confidence = self._calculate_confidence(current_rsi, self.oversold, self.overbought)
            signal = TradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=current_price,
                reasoning=f"Oversold condition: RSI ({current_rsi:.2f}) crossed below {self.oversold}"
            )
        elif current_rsi > self.overbought and prev_rsi <= self.overbought:
            # RSI crossed above overbought threshold (sell signal)
            confidence = self._calculate_confidence(current_rsi, self.oversold, self.overbought)
            signal = TradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=current_price,
                reasoning=f"Overbought condition: RSI ({current_rsi:.2f}) crossed above {self.overbought}"
            )
        else:
            # No signal
            signal = TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=data.index[-1].to_pydatetime(),
                price=current_price,
                reasoning=f"No condition met: RSI ({current_rsi:.2f})"
            )
            
        self.last_signal = signal
        return signal
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate the Relative Strength Index.
        
        Args:
            prices: Series of price data
            period: RSI period
            
        Returns:
            Series: RSI values
        """
        # Calculate price changes
        delta = prices.diff()
        
        # Separate gains and losses
        gain = delta.copy()
        loss = delta.copy()
        gain[gain < 0] = 0
        loss[loss > 0] = 0
        loss = abs(loss)
        
        # Calculate average gain and loss
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_confidence(self, rsi: float, oversold: float, overbought: float) -> float:
        """
        Calculate the confidence level of the signal.
        
        Args:
            rsi: Current RSI value
            oversold: Oversold threshold
            overbought: Overbought threshold
            
        Returns:
            float: Confidence level between 0.0 and 1.0
        """
        if rsi <= oversold:
            # Buy signal confidence increases as RSI decreases below oversold
            confidence = min(1.0, (oversold - rsi) / oversold + 0.3)
        elif rsi >= overbought:
            # Sell signal confidence increases as RSI increases above overbought
            confidence = min(1.0, (rsi - overbought) / (100 - overbought) + 0.3)
        else:
            # No strong signal
            confidence = 0.0
            
        return confidence


class SignalGenerator:
    """
    Class to orchestrate and combine multiple trading strategies.
    
    Evaluates signals from multiple strategies and combines them
    to generate a final trading signal.
    """
    
    def __init__(self, strategies: List[BaseStrategy]):
        """
        Initialize the SignalGenerator with a list of strategies.
        
        Args:
            strategies: List of strategy instances
        """
        self.strategies = strategies
    
    def evaluate_all_strategies(self, data: pd.DataFrame) -> TradingSignal:
        """
        Evaluate all strategies and combine their signals.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            TradingSignal: The combined trading signal
        """
        signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.calculate_signals(data)
                signals.append(signal)
                log_info(f"Strategy {strategy.name} generated {signal.action.value} signal with {signal.confidence:.2f} confidence")
            except Exception as e:
                log_error(f"Error evaluating strategy {strategy.name}: {str(e)}")
        
        if not signals:
            # If no signals were generated, return a HOLD signal
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy="SignalGenerator",
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="No strategies generated valid signals"
            )
        
        # Combine signals
        combined_signal = self.combine_signals(signals)
        log_info(f"Combined signal: {combined_signal.action.value} with {combined_signal.confidence:.2f} confidence")
        
        return combined_signal
    
    def combine_signals(self, signals: List[TradingSignal]) -> TradingSignal:
        """
        Combine multiple signals into a single trading signal.
        
        Args:
            signals: List of trading signals from different strategies
            
        Returns:
            TradingSignal: The combined trading signal
        """
        if not signals:
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy="SignalGenerator",
                timestamp=datetime.now(),
                price=0.0,
                reasoning="No signals to combine"
            )
            
        # Count signals by type
        buy_signals = [s for s in signals if s.action == SignalType.BUY]
        sell_signals = [s for s in signals if s.action == SignalType.SELL]
        hold_signals = [s for s in signals if s.action == SignalType.HOLD]
        
        # Get the latest timestamp and price
        latest_signal = max(signals, key=lambda s: s.timestamp)
        timestamp = latest_signal.timestamp
        price = latest_signal.price
        
        # Calculate weighted confidence for each signal type
        buy_confidence = sum(s.confidence for s in buy_signals) / len(signals) if buy_signals else 0
        sell_confidence = sum(s.confidence for s in sell_signals) / len(signals) if sell_signals else 0
        
        # Determine the final signal
        if buy_confidence > sell_confidence and buy_confidence > 0.3:
            # Buy signal
            action = SignalType.BUY
            confidence = buy_confidence
            strategies = ", ".join(s.strategy for s in buy_signals)
            reasoning = f"Buy signal from strategies: {strategies} with combined confidence {confidence:.2f}"
        elif sell_confidence > buy_confidence and sell_confidence > 0.3:
            # Sell signal
            action = SignalType.SELL
            confidence = sell_confidence
            strategies = ", ".join(s.strategy for s in sell_signals)
            reasoning = f"Sell signal from strategies: {strategies} with combined confidence {confidence:.2f}"
        else:
            # Hold signal (no strong buy or sell)
            action = SignalType.HOLD
            confidence = 0.0
            reasoning = "No strong buy or sell signals"
            
        return TradingSignal(
            action=action,
            confidence=confidence,
            strategy="SignalGenerator",
            timestamp=timestamp,
            price=price,
            reasoning=reasoning
        )