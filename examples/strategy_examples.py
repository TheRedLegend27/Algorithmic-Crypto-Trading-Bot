"""
Example implementations of trading strategies for the crypto trading bot.

This file contains example implementations of various trading strategies that can be
used with the crypto trading bot. These examples demonstrate how to create custom
strategies by extending the BaseStrategy class.

Usage:
    To use these strategies, import them in main.py and add them to the strategies list.
"""
from typing import Dict, Any
import pandas as pd
import numpy as np
from bot.strategy import BaseStrategy


class BollingerBandsStrategy(BaseStrategy):
    """
    Trading strategy based on Bollinger Bands.
    
    This strategy generates buy signals when the price touches the lower band
    and sell signals when the price touches the upper band.
    
    Attributes:
        period: Period for calculating the moving average
        std_dev: Number of standard deviations for the bands
    """
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        """
        Initialize the Bollinger Bands strategy.
        
        Args:
            period: Period for calculating the moving average (default: 20)
            std_dev: Number of standard deviations for the bands (default: 2.0)
        """
        self.period = period
        self.std_dev = std_dev
        self.name = "BollingerBands"
    
    def calculate_signals(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate trading signals based on Bollinger Bands.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            Dictionary containing signal information
        """
        if len(data) < self.period:
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'strategy': self.name,
                'reasoning': f"Insufficient data for {self.name} calculation"
            }
        
        # Calculate Bollinger Bands
        data['sma'] = data['close'].rolling(window=self.period).mean()
        data['std'] = data['close'].rolling(window=self.period).std()
        data['upper_band'] = data['sma'] + (data['std'] * self.std_dev)
        data['lower_band'] = data['sma'] - (data['std'] * self.std_dev)
        
        # Get the latest values
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Calculate percentage distance from bands
        upper_distance = (latest['upper_band'] - latest['close']) / latest['close']
        lower_distance = (latest['close'] - latest['lower_band']) / latest['close']
        
        # Generate signals
        if latest['close'] <= latest['lower_band'] and prev['close'] > prev['lower_band']:
            # Price crossed below lower band - buy signal
            return {
                'action': 'BUY',
                'confidence': min(lower_distance * 10, 0.95),
                'strategy': self.name,
                'reasoning': f"Price crossed below lower Bollinger Band (SMA{self.period} - {self.std_dev}σ)"
            }
        elif latest['close'] >= latest['upper_band'] and prev['close'] < prev['upper_band']:
            # Price crossed above upper band - sell signal
            return {
                'action': 'SELL',
                'confidence': min(upper_distance * 10, 0.95),
                'strategy': self.name,
                'reasoning': f"Price crossed above upper Bollinger Band (SMA{self.period} + {self.std_dev}σ)"
            }
        else:
            # No signal
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'strategy': self.name,
                'reasoning': f"Price within Bollinger Bands (SMA{self.period} ± {self.std_dev}σ)"
            }


class MACDStrategy(BaseStrategy):
    """
    Trading strategy based on the MACD (Moving Average Convergence Divergence) indicator.
    
    This strategy generates buy signals when the MACD line crosses above the signal line
    and sell signals when the MACD line crosses below the signal line.
    
    Attributes:
        fast_period: Period for the fast EMA
        slow_period: Period for the slow EMA
        signal_period: Period for the signal line
    """
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        Initialize the MACD strategy.
        
        Args:
            fast_period: Period for the fast EMA (default: 12)
            slow_period: Period for the slow EMA (default: 26)
            signal_period: Period for the signal line (default: 9)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.name = "MACD"
    
    def calculate_signals(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate trading signals based on MACD.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            Dictionary containing signal information
        """
        if len(data) < self.slow_period + self.signal_period:
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'strategy': self.name,
                'reasoning': f"Insufficient data for {self.name} calculation"
            }
        
        # Calculate MACD
        data['ema_fast'] = data['close'].ewm(span=self.fast_period, adjust=False).mean()
        data['ema_slow'] = data['close'].ewm(span=self.slow_period, adjust=False).mean()
        data['macd'] = data['ema_fast'] - data['ema_slow']
        data['signal'] = data['macd'].ewm(span=self.signal_period, adjust=False).mean()
        data['histogram'] = data['macd'] - data['signal']
        
        # Get the latest values
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Calculate signal strength
        signal_strength = abs(latest['histogram'] / latest['signal']) if latest['signal'] != 0 else 0
        confidence = min(signal_strength, 0.95)
        
        # Generate signals
        if latest['macd'] > latest['signal'] and prev['macd'] <= prev['signal']:
            # MACD crossed above signal line - buy signal
            return {
                'action': 'BUY',
                'confidence': confidence,
                'strategy': self.name,
                'reasoning': f"MACD crossed above signal line (MACD: {latest['macd']:.4f}, Signal: {latest['signal']:.4f})"
            }
        elif latest['macd'] < latest['signal'] and prev['macd'] >= prev['signal']:
            # MACD crossed below signal line - sell signal
            return {
                'action': 'SELL',
                'confidence': confidence,
                'strategy': self.name,
                'reasoning': f"MACD crossed below signal line (MACD: {latest['macd']:.4f}, Signal: {latest['signal']:.4f})"
            }
        else:
            # No signal
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'strategy': self.name,
                'reasoning': f"No MACD crossover detected (MACD: {latest['macd']:.4f}, Signal: {latest['signal']:.4f})"
            }


class SupertrendStrategy(BaseStrategy):
    """
    Trading strategy based on the Supertrend indicator.
    
    This strategy generates buy signals when the price crosses above the Supertrend line
    and sell signals when the price crosses below the Supertrend line.
    
    Attributes:
        period: Period for the ATR calculation
        multiplier: Multiplier for the ATR
    """
    
    def __init__(self, period: int = 10, multiplier: float = 3.0):
        """
        Initialize the Supertrend strategy.
        
        Args:
            period: Period for the ATR calculation (default: 10)
            multiplier: Multiplier for the ATR (default: 3.0)
        """
        self.period = period
        self.multiplier = multiplier
        self.name = "Supertrend"
    
    def calculate_signals(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate trading signals based on Supertrend.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            Dictionary containing signal information
        """
        if len(data) < self.period + 1:
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'strategy': self.name,
                'reasoning': f"Insufficient data for {self.name} calculation"
            }
        
        # Calculate ATR
        data['tr'] = np.maximum(
            np.maximum(
                data['high'] - data['low'],
                abs(data['high'] - data['close'].shift(1))
            ),
            abs(data['low'] - data['close'].shift(1))
        )
        data['atr'] = data['tr'].rolling(window=self.period).mean()
        
        # Calculate Supertrend
        data['hl2'] = (data['high'] + data['low']) / 2
        data['basic_upper_band'] = data['hl2'] + (self.multiplier * data['atr'])
        data['basic_lower_band'] = data['hl2'] - (self.multiplier * data['atr'])
        
        # Initialize Supertrend columns
        data['supertrend'] = 0.0
        data['supertrend_direction'] = 0  # 1 for uptrend, -1 for downtrend
        
        # Calculate Supertrend
        for i in range(1, len(data)):
            if data['close'].iloc[i-1] <= data['supertrend'].iloc[i-1]:
                data.loc[data.index[i], 'supertrend'] = max(
                    data['basic_lower_band'].iloc[i],
                    data['supertrend'].iloc[i-1]
                )
            else:
                data.loc[data.index[i], 'supertrend'] = min(
                    data['basic_upper_band'].iloc[i],
                    data['supertrend'].iloc[i-1]
                )
                
            # Determine trend direction
            if data['close'].iloc[i] > data['supertrend'].iloc[i]:
                data.loc[data.index[i], 'supertrend_direction'] = 1
            else:
                data.loc[data.index[i], 'supertrend_direction'] = -1
        
        # Get the latest values
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Calculate confidence based on distance from Supertrend line
        distance = abs(latest['close'] - latest['supertrend']) / latest['close']
        confidence = min(distance * 10, 0.95)
        
        # Generate signals
        if latest['supertrend_direction'] == 1 and prev['supertrend_direction'] == -1:
            # Price crossed above Supertrend - buy signal
            return {
                'action': 'BUY',
                'confidence': confidence,
                'strategy': self.name,
                'reasoning': f"Price crossed above Supertrend (ATR{self.period} * {self.multiplier})"
            }
        elif latest['supertrend_direction'] == -1 and prev['supertrend_direction'] == 1:
            # Price crossed below Supertrend - sell signal
            return {
                'action': 'SELL',
                'confidence': confidence,
                'strategy': self.name,
                'reasoning': f"Price crossed below Supertrend (ATR{self.period} * {self.multiplier})"
            }
        else:
            # No signal
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'strategy': self.name,
                'reasoning': f"No Supertrend crossover detected"
            }


# Example of how to use these strategies in main.py:
"""
# Import custom strategies
from examples.strategy_examples import BollingerBandsStrategy, MACDStrategy, SupertrendStrategy

# Initialize strategies with command-line parameters
strategies: List[BaseStrategy] = [
    MovingAverageCrossover(
        fast_period=args.ma_fast,
        slow_period=args.ma_slow
    ),
    RSIStrategy(
        period=args.rsi_period,
        oversold=args.rsi_oversold,
        overbought=args.rsi_overbought
    ),
    # Add custom strategies
    BollingerBandsStrategy(period=20, std_dev=2.0),
    MACDStrategy(fast_period=12, slow_period=26, signal_period=9),
    SupertrendStrategy(period=10, multiplier=3.0)
]
"""