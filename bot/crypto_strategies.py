"""
Cryptocurrency-specific trading strategies adapted for 24/7 markets and high volatility.

This module contains adaptations of existing trading strategies optimized for
cryptocurrency markets, with adjustments for:
- 24/7 trading hours
- Higher volatility
- Crypto-specific market behaviors
- Signal validation for crypto markets
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from bot.strategy import BaseStrategy, TradingSignal, SignalType
from bot.utils import log_info, log_warning, log_error


class CryptoTradingSignal(TradingSignal):
    """Extended trading signal with crypto-specific attributes."""
    
    def __init__(self, action: SignalType, confidence: float, strategy: str,
                timestamp: datetime, price: float, reasoning: str,
                market_cap: float = 0.0, volume_24h: float = 0.0,
                price_change_24h: float = 0.0, volatility: float = 0.0,
                liquidity_score: float = 0.0):
        """
        Initialize a crypto trading signal with additional attributes.
        
        Args:
            action: Signal type (BUY, SELL, HOLD)
            confidence: Signal confidence (0.0 to 1.0)
            strategy: Strategy name that generated the signal
            timestamp: Signal generation timestamp
            price: Current asset price
            reasoning: Explanation for the signal
            market_cap: Market capitalization of the crypto asset
            volume_24h: 24-hour trading volume
            price_change_24h: 24-hour price change percentage
            volatility: Volatility measure (e.g., standard deviation)
            liquidity_score: Measure of market liquidity (0.0 to 1.0)
        """
        super().__init__(action, confidence, strategy, timestamp, price, reasoning)
        self.market_cap = market_cap
        self.volume_24h = volume_24h
        self.price_change_24h = price_change_24h
        self.volatility = volatility
        self.liquidity_score = liquidity_score


class CryptoBaseStrategy(BaseStrategy):
    """Base class for crypto-specific trading strategies."""
    
    def __init__(self, name: str):
        """Initialize the crypto strategy."""
        super().__init__(name)
        self.market_hours = "24/7"  # Crypto markets are always open
    
    def validate_crypto_data(self, data: pd.DataFrame) -> bool:
        """
        Validate that the data is suitable for crypto trading strategies.
        
        Args:
            data: DataFrame to validate
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        if not self.validate_data(data):
            return False
            
        # Check for minimum data points
        if len(data) < 10:
            log_warning(f"{self.name}: Insufficient data points for crypto analysis")
            return False
        
        # Data freshness check disabled - not critical for trading functionality
        # The bot fetches fresh data from Kraken API for each trading cycle
        
        # Check for extreme price movements (common in crypto)
        price_changes = data['close'].pct_change().abs()
        extreme_changes = price_changes > 0.2  # 20% change threshold for crypto
        if extreme_changes.any():
            log_info(f"{self.name}: Detected {extreme_changes.sum()} instances of extreme price movements")
            # Don't fail validation, just inform
        
        return True
    
    def _get_timestamp(self, timestamp_value) -> datetime:
        """Convert various timestamp formats to datetime."""
        try:
            if isinstance(timestamp_value, pd.Timestamp):
                return timestamp_value.to_pydatetime()
            elif isinstance(timestamp_value, (int, np.int64)):
                return datetime.fromtimestamp(timestamp_value)
            elif isinstance(timestamp_value, datetime):
                return timestamp_value
            else:
                # Fallback to current time
                return datetime.now()
        except Exception:
            return datetime.now()
    
    def calculate_crypto_metrics(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate crypto-specific metrics for signal generation.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            Dictionary of crypto metrics
        """
        metrics = {}
        
        # Calculate volatility (standard deviation of returns)
        returns = data['close'].pct_change().dropna()
        metrics['volatility'] = returns.std() * np.sqrt(365)  # Annualized
        
        # Calculate average volume
        metrics['avg_volume'] = data['volume'].mean()
        
        # Calculate 24h price change
        if len(data) > 24:
            metrics['price_change_24h'] = (
                (data['close'].iloc[-1] / data['close'].iloc[-25]) - 1
            ) * 100
        else:
            metrics['price_change_24h'] = 0.0
        
        # Calculate volume profile
        metrics['volume_profile'] = data['volume'].iloc[-1] / metrics['avg_volume']
        
        # Calculate price momentum
        metrics['momentum_1h'] = data['close'].pct_change(periods=1).iloc[-1] * 100
        metrics['momentum_4h'] = data['close'].pct_change(periods=4).iloc[-1] * 100
        metrics['momentum_24h'] = data['close'].pct_change(periods=24).iloc[-1] * 100
        
        return metrics


class CryptoMovingAverageCrossover(CryptoBaseStrategy):
    """
    Moving Average Crossover strategy adapted for cryptocurrency markets.
    
    Adjustments for crypto:
    - Shorter periods for faster signals in volatile markets
    - Dynamic confidence based on volume and volatility
    - 24/7 market handling
    - Volatility-based signal filtering
    """
    
    def __init__(self, fast_period: int = 8, slow_period: int = 21, 
                 signal_threshold: float = 0.005):
        """
        Initialize the Crypto Moving Average Crossover strategy.
        
        Args:
            fast_period: Period for the fast moving average (shorter for crypto)
            slow_period: Period for the slow moving average (shorter for crypto)
            signal_threshold: Minimum price change threshold for valid signals
        """
        super().__init__("Crypto MA Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_threshold = signal_threshold
        
        if fast_period >= slow_period:
            log_warning(f"{self.name}: Fast period should be less than slow period")
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """
        Calculate trading signals based on moving average crossovers for crypto.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            TradingSignal: The generated trading signal
        """
        if not self.validate_crypto_data(data):
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="Invalid data for crypto strategy calculation"
            )
            
        # Check if we have enough data points
        if len(data) < self.slow_period + 5:  # Need extra points for volatility calculation
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
        
        # Calculate crypto-specific metrics
        crypto_metrics = self.calculate_crypto_metrics(data)
        
        # Calculate volatility-adjusted signal threshold
        # Higher volatility = higher threshold to avoid false signals
        volatility_factor = min(3.0, max(1.0, crypto_metrics['volatility'] / 0.5))
        adjusted_threshold = self.signal_threshold * volatility_factor
        
        # Calculate price momentum and volume profile
        data['momentum'] = data['close'].pct_change(periods=3)
        data['volume_sma'] = data['volume'].rolling(window=10).mean()
        data['volume_ratio'] = data['volume'] / data['volume_sma']
        
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
        
        # Current price and volume
        current_price = last_row['close']
        current_volume_ratio = last_row['volume_ratio']
        
        # Calculate MA difference as percentage
        ma_diff_pct = abs(current_fast_ma - current_slow_ma) / current_slow_ma
        
        # Check if the difference is significant enough (adjusted for crypto volatility)
        significant_diff = ma_diff_pct > adjusted_threshold
        
        # Check for crossover with volume confirmation
        if prev_fast_ma <= prev_slow_ma and current_fast_ma > current_slow_ma and significant_diff:
            # Bullish crossover (fast MA crosses above slow MA)
            # Adjust confidence based on volume and volatility
            volume_factor = min(1.5, max(0.5, current_volume_ratio))
            confidence = self._calculate_crypto_confidence(
                current_fast_ma, current_slow_ma, current_price,
                volume_factor, crypto_metrics['volatility']
            )
            
            # Create crypto-specific signal
            signal = CryptoTradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=self._get_timestamp(data.index[-1]),
                price=current_price,
                reasoning=f"Bullish crossover: Fast MA ({current_fast_ma:.2f}) crossed above Slow MA ({current_slow_ma:.2f}) with volume {current_volume_ratio:.2f}x",
                volume_24h=crypto_metrics['avg_volume'],
                price_change_24h=crypto_metrics['price_change_24h'],
                volatility=crypto_metrics['volatility']
            )
        elif prev_fast_ma >= prev_slow_ma and current_fast_ma < current_slow_ma and significant_diff:
            # Bearish crossover (fast MA crosses below slow MA)
            # Adjust confidence based on volume and volatility
            volume_factor = min(1.5, max(0.5, current_volume_ratio))
            confidence = self._calculate_crypto_confidence(
                current_fast_ma, current_slow_ma, current_price,
                volume_factor, crypto_metrics['volatility']
            )
            
            # Create crypto-specific signal
            signal = CryptoTradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=self._get_timestamp(data.index[-1]),
                price=current_price,
                reasoning=f"Bearish crossover: Fast MA ({current_fast_ma:.2f}) crossed below Slow MA ({current_slow_ma:.2f}) with volume {current_volume_ratio:.2f}x",
                volume_24h=crypto_metrics['avg_volume'],
                price_change_24h=crypto_metrics['price_change_24h'],
                volatility=crypto_metrics['volatility']
            )
        else:
            # No crossover
            signal = TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=self._get_timestamp(data.index[-1]),
                price=current_price,
                reasoning=f"No crossover: Fast MA ({current_fast_ma:.2f}) vs Slow MA ({current_slow_ma:.2f})"
            )
            
        self.last_signal = signal
        return signal
    
    def _calculate_crypto_confidence(self, fast_ma: float, slow_ma: float, 
                                   current_price: float, volume_factor: float,
                                   volatility: float) -> float:
        """
        Calculate the confidence level of the signal with crypto-specific adjustments.
        
        Args:
            fast_ma: Current fast moving average
            slow_ma: Current slow moving average
            current_price: Current price
            volume_factor: Volume multiplier for confidence
            volatility: Current volatility measure
            
        Returns:
            float: Confidence level between 0.0 and 1.0
        """
        # Calculate the percentage difference between the MAs
        ma_diff_pct = abs(fast_ma - slow_ma) / slow_ma
        
        # Calculate the percentage difference between current price and slow MA
        price_ma_diff_pct = abs(current_price - slow_ma) / slow_ma
        
        # Adjust confidence based on volatility (lower confidence in high volatility)
        volatility_factor = max(0.5, min(1.5, 1.0 / (volatility * 2)))
        
        # Combine the factors to determine confidence
        # Higher MA difference and price-MA difference increase confidence
        # Volume factor boosts confidence
        # Volatility factor reduces confidence in high volatility
        confidence = min(0.3 + ma_diff_pct * 8 + price_ma_diff_pct * 3, 1.0)
        confidence = confidence * volume_factor * volatility_factor
        
        return min(confidence, 1.0)


class CryptoRSIStrategy(CryptoBaseStrategy):
    """
    RSI Strategy adapted for cryptocurrency markets.
    
    Adjustments for crypto:
    - Dynamic overbought/oversold thresholds based on market volatility
    - Volume confirmation for signals
    - Trend-based signal filtering
    - Volatility-based confidence adjustment
    """
    
    def __init__(self, period: int = 14, base_oversold: float = 30.0, 
                 base_overbought: float = 70.0, volatility_adjustment: bool = True):
        """
        Initialize the Crypto RSI strategy.
        
        Args:
            period: Period for RSI calculation
            base_oversold: Base threshold for oversold condition
            base_overbought: Base threshold for overbought condition
            volatility_adjustment: Whether to adjust thresholds based on volatility
        """
        super().__init__("Crypto RSI Strategy")
        self.period = period
        self.base_oversold = base_oversold
        self.base_overbought = base_overbought
        self.volatility_adjustment = volatility_adjustment
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """
        Calculate trading signals based on RSI values for crypto.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            TradingSignal: The generated trading signal
        """
        if not self.validate_crypto_data(data):
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="Invalid data for crypto strategy calculation"
            )
            
        # Check if we have enough data points
        if len(data) < self.period + 10:  # Need extra points for trend calculation
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
        
        # Calculate crypto-specific metrics
        crypto_metrics = self.calculate_crypto_metrics(data)
        
        # Calculate volume profile
        data['volume_sma'] = data['volume'].rolling(window=10).mean()
        data['volume_ratio'] = data['volume'] / data['volume_sma']
        
        # Calculate price trend (simple moving average)
        data['price_sma'] = data['close'].rolling(window=20).mean()
        data['trend'] = (data['close'] > data['price_sma']).astype(int)
        
        # Adjust overbought/oversold thresholds based on volatility
        if self.volatility_adjustment:
            # Higher volatility = wider thresholds to avoid false signals
            volatility_factor = min(2.0, max(1.0, crypto_metrics['volatility'] / 0.5))
            oversold = self.base_oversold - (5 * (volatility_factor - 1))  # Lower threshold
            overbought = self.base_overbought + (5 * (volatility_factor - 1))  # Higher threshold
        else:
            oversold = self.base_oversold
            overbought = self.base_overbought
        
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
        current_volume_ratio = last_row['volume_ratio']
        current_trend = last_row['trend']
        
        # Check for oversold/overbought conditions with volume confirmation
        if current_rsi < oversold and prev_rsi >= oversold and current_volume_ratio > 0.8:
            # RSI crossed below oversold threshold (buy signal)
            # Higher confidence if trend is up (counter-trend bounce)
            trend_factor = 1.2 if current_trend == 1 else 0.8
            confidence = self._calculate_crypto_confidence(
                current_rsi, oversold, overbought, current_volume_ratio, trend_factor
            )
            
            # Create crypto-specific signal
            signal = CryptoTradingSignal(
                action=SignalType.BUY,
                confidence=confidence,
                strategy=self.name,
                timestamp=self._get_timestamp(data.index[-1]),
                price=current_price,
                reasoning=f"Crypto oversold condition: RSI ({current_rsi:.2f}) crossed below {oversold} with volume {current_volume_ratio:.2f}x",
                volume_24h=crypto_metrics['avg_volume'],
                price_change_24h=crypto_metrics['price_change_24h'],
                volatility=crypto_metrics['volatility']
            )
        elif current_rsi > overbought and prev_rsi <= overbought and current_volume_ratio > 0.8:
            # RSI crossed above overbought threshold (sell signal)
            # Higher confidence if trend is down (counter-trend reversal)
            trend_factor = 1.2 if current_trend == 0 else 0.8
            confidence = self._calculate_crypto_confidence(
                current_rsi, oversold, overbought, current_volume_ratio, trend_factor
            )
            
            # Create crypto-specific signal
            signal = CryptoTradingSignal(
                action=SignalType.SELL,
                confidence=confidence,
                strategy=self.name,
                timestamp=self._get_timestamp(data.index[-1]),
                price=current_price,
                reasoning=f"Crypto overbought condition: RSI ({current_rsi:.2f}) crossed above {overbought} with volume {current_volume_ratio:.2f}x",
                volume_24h=crypto_metrics['avg_volume'],
                price_change_24h=crypto_metrics['price_change_24h'],
                volatility=crypto_metrics['volatility']
            )
        else:
            # No signal
            signal = TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=self._get_timestamp(data.index[-1]),
                price=current_price,
                reasoning=f"No condition met: RSI ({current_rsi:.2f}), thresholds {oversold}/{overbought}"
            )
            
        self.last_signal = signal
        return signal
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate the Relative Strength Index with crypto-specific adjustments.
        
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
        # Use exponential moving average for crypto (more responsive)
        avg_gain = gain.ewm(span=period, min_periods=period).mean()
        avg_loss = loss.ewm(span=period, min_periods=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_crypto_confidence(self, rsi: float, oversold: float, 
                                   overbought: float, volume_ratio: float,
                                   trend_factor: float) -> float:
        """
        Calculate the confidence level of the signal with crypto-specific adjustments.
        
        Args:
            rsi: Current RSI value
            oversold: Oversold threshold
            overbought: Overbought threshold
            volume_ratio: Current volume ratio
            trend_factor: Trend confirmation factor
            
        Returns:
            float: Confidence level between 0.0 and 1.0
        """
        if rsi <= oversold:
            # Buy signal confidence increases as RSI decreases below oversold
            # and as volume increases
            base_confidence = (oversold - rsi) / oversold + 0.3
            volume_boost = min(0.3, (volume_ratio - 1) * 0.2) if volume_ratio > 1 else 0
            confidence = (base_confidence + volume_boost) * trend_factor
        elif rsi >= overbought:
            # Sell signal confidence increases as RSI increases above overbought
            # and as volume increases
            base_confidence = (rsi - overbought) / (100 - overbought) + 0.3
            volume_boost = min(0.3, (volume_ratio - 1) * 0.2) if volume_ratio > 1 else 0
            confidence = (base_confidence + volume_boost) * trend_factor
        else:
            # No strong signal
            confidence = 0.0
            
        return min(confidence, 1.0)


class Crypto24hMarketStrategy(CryptoBaseStrategy):
    """
    Strategy specifically designed for 24/7 crypto markets.
    
    Focuses on:
    - Time-of-day effects in crypto markets
    - Weekend vs weekday trading patterns
    - Global market session overlaps
    - Handling continuous trading without market close/open gaps
    """
    
    def __init__(self):
        """Initialize the 24/7 market strategy."""
        super().__init__("Crypto 24/7 Market")
        
        # Define global trading sessions (UTC times)
        self.asia_session = (0, 8)  # 00:00-08:00 UTC
        self.europe_session = (7, 16)  # 07:00-16:00 UTC
        self.us_session = (13, 21)  # 13:00-21:00 UTC
        
        # Session overlap periods (highest liquidity)
        self.asia_europe_overlap = (7, 8)  # 07:00-08:00 UTC
        self.europe_us_overlap = (13, 16)  # 13:00-16:00 UTC
    
    def calculate_signals(self, data: pd.DataFrame) -> TradingSignal:
        """
        Calculate trading signals based on 24/7 market patterns.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            TradingSignal: The generated trading signal
        """
        if not self.validate_crypto_data(data):
            return TradingSignal(
                action=SignalType.HOLD,
                confidence=0.0,
                strategy=self.name,
                timestamp=datetime.now(),
                price=data['close'].iloc[-1] if not data.empty else 0.0,
                reasoning="Invalid data for crypto strategy calculation"
            )
        
        # Get current UTC time and day of week
        current_time = datetime.utcnow()
        current_hour = current_time.hour
        is_weekend = current_time.weekday() >= 5  # 5=Saturday, 6=Sunday
        
        # Calculate crypto-specific metrics
        crypto_metrics = self.calculate_crypto_metrics(data)
        
        # Determine current trading session
        in_asia_session = self.asia_session[0] <= current_hour < self.asia_session[1]
        in_europe_session = self.europe_session[0] <= current_hour < self.europe_session[1]
        in_us_session = self.us_session[0] <= current_hour < self.us_session[1]
        
        # Check for session overlaps (high liquidity periods)
        in_asia_europe_overlap = (self.asia_europe_overlap[0] <= current_hour < 
                                self.asia_europe_overlap[1])
        in_europe_us_overlap = (self.europe_us_overlap[0] <= current_hour < 
                              self.europe_us_overlap[1])
        
        # Calculate recent volatility and volume
        if len(data) >= 24:
            recent_data = data.iloc[-24:]
            volatility = recent_data['close'].pct_change().std() * np.sqrt(24)
            avg_volume = recent_data['volume'].mean()
            current_volume = data['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        else:
            volatility = crypto_metrics['volatility']
            volume_ratio = 1.0
        
        # Current price
        current_price = data['close'].iloc[-1]
        
        # Analyze weekend vs weekday patterns
        if is_weekend:
            # Weekends typically have lower volume and can be more volatile
            if volume_ratio > 1.5 and volatility > 0.03:
                # Unusual high volume and volatility on weekend - potential breakout
                confidence = min(0.7, 0.4 + (volume_ratio - 1) * 0.2)
                
                # Determine direction based on recent price action
                if len(data) >= 3:
                    recent_change = (data['close'].iloc[-1] / data['close'].iloc[-3] - 1)
                    if recent_change > 0.02:  # 2% up
                        action = SignalType.BUY
                        reasoning = f"Weekend breakout with {volume_ratio:.2f}x volume and {recent_change:.2%} gain"
                    elif recent_change < -0.02:  # 2% down
                        action = SignalType.SELL
                        reasoning = f"Weekend breakdown with {volume_ratio:.2f}x volume and {recent_change:.2%} loss"
                    else:
                        action = SignalType.HOLD
                        reasoning = f"No clear weekend direction despite {volume_ratio:.2f}x volume"
                        confidence = 0.0
                else:
                    action = SignalType.HOLD
                    reasoning = "Insufficient recent data for weekend analysis"
                    confidence = 0.0
            else:
                # Normal weekend activity - typically avoid trading
                action = SignalType.HOLD
                reasoning = f"Normal weekend market conditions, volume ratio: {volume_ratio:.2f}x"
                confidence = 0.0
        else:
            # Weekday trading - focus on session overlaps
            if in_europe_us_overlap:
                # Highest liquidity period
                if volume_ratio > 1.3 and volatility > 0.02:
                    # Strong momentum during high liquidity
                    if len(data) >= 4:
                        # Check for consistent direction
                        price_changes = data['close'].pct_change().iloc[-4:]
                        consistent_up = (price_changes > 0).sum() >= 3
                        consistent_down = (price_changes < 0).sum() >= 3
                        
                        if consistent_up:
                            action = SignalType.BUY
                            confidence = min(0.8, 0.5 + volume_ratio * 0.1 + volatility * 5)
                            reasoning = f"Strong bullish momentum during Europe-US overlap, {volume_ratio:.2f}x volume"
                        elif consistent_down:
                            action = SignalType.SELL
                            confidence = min(0.8, 0.5 + volume_ratio * 0.1 + volatility * 5)
                            reasoning = f"Strong bearish momentum during Europe-US overlap, {volume_ratio:.2f}x volume"
                        else:
                            action = SignalType.HOLD
                            confidence = 0.0
                            reasoning = "Mixed price action during Europe-US overlap"
                    else:
                        action = SignalType.HOLD
                        confidence = 0.0
                        reasoning = "Insufficient data for session analysis"
                else:
                    action = SignalType.HOLD
                    confidence = 0.0
                    reasoning = f"Normal Europe-US session, volume: {volume_ratio:.2f}x, volatility: {volatility:.4f}"
            elif in_asia_europe_overlap:
                # Secondary liquidity peak
                # Similar logic to Europe-US but with lower confidence
                if volume_ratio > 1.5 and volatility > 0.025:  # Higher thresholds
                    if len(data) >= 4:
                        price_changes = data['close'].pct_change().iloc[-4:]
                        consistent_up = (price_changes > 0).sum() >= 3
                        consistent_down = (price_changes < 0).sum() >= 3
                        
                        if consistent_up:
                            action = SignalType.BUY
                            confidence = min(0.7, 0.4 + volume_ratio * 0.1 + volatility * 4)
                            reasoning = f"Bullish momentum during Asia-Europe overlap, {volume_ratio:.2f}x volume"
                        elif consistent_down:
                            action = SignalType.SELL
                            confidence = min(0.7, 0.4 + volume_ratio * 0.1 + volatility * 4)
                            reasoning = f"Bearish momentum during Asia-Europe overlap, {volume_ratio:.2f}x volume"
                        else:
                            action = SignalType.HOLD
                            confidence = 0.0
                            reasoning = "Mixed price action during Asia-Europe overlap"
                    else:
                        action = SignalType.HOLD
                        confidence = 0.0
                        reasoning = "Insufficient data for session analysis"
                else:
                    action = SignalType.HOLD
                    confidence = 0.0
                    reasoning = f"Normal Asia-Europe session, volume: {volume_ratio:.2f}x"
            else:
                # Single market session - lower liquidity
                action = SignalType.HOLD
                confidence = 0.0
                if in_asia_session:
                    reasoning = "Asia session - lower liquidity period"
                elif in_europe_session:
                    reasoning = "Europe-only session - moderate liquidity"
                elif in_us_session:
                    reasoning = "US-only session - moderate liquidity"
                else:
                    reasoning = "Off-peak trading hours - lowest liquidity"
        
        # Create signal
        signal = CryptoTradingSignal(
            action=action,
            confidence=confidence,
            strategy=self.name,
            timestamp=datetime.now(),
            price=current_price,
            reasoning=reasoning,
            volume_24h=crypto_metrics['avg_volume'],
            price_change_24h=crypto_metrics['price_change_24h'],
            volatility=crypto_metrics['volatility'],
            liquidity_score=0.8 if in_europe_us_overlap else 0.6 if in_asia_europe_overlap else 0.4
        )
        
        self.last_signal = signal
        return signal


class CryptoSignalValidator:
    """
    Validates and filters trading signals for cryptocurrency markets.
    
    Applies crypto-specific rules to avoid false signals and reduce risk:
    - Volatility-based signal filtering
    - Volume confirmation requirements
    - Market condition awareness
    - Signal strength thresholds
    """
    
    def __init__(self, min_confidence: float = 0.4, 
                 min_volume_ratio: float = 0.8,
                 max_volatility: float = 0.1,
                 require_volume_confirmation: bool = True):
        """
        Initialize the crypto signal validator.
        
        Args:
            min_confidence: Minimum confidence threshold for valid signals
            min_volume_ratio: Minimum volume ratio for confirmation
            max_volatility: Maximum acceptable volatility (annualized)
            require_volume_confirmation: Whether to require volume confirmation
        """
        self.min_confidence = min_confidence
        self.min_volume_ratio = min_volume_ratio
        self.max_volatility = max_volatility
        self.require_volume_confirmation = require_volume_confirmation
    
    def validate_signal(self, signal: TradingSignal, 
                       market_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a trading signal for crypto markets.
        
        Args:
            signal: The trading signal to validate
            market_data: Dictionary with market metrics
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Skip validation for HOLD signals
        if signal.action == SignalType.HOLD:
            return True, "HOLD signal requires no validation"
        
        # Check confidence threshold
        if signal.confidence < self.min_confidence:
            return False, f"Signal confidence too low: {signal.confidence:.2f} < {self.min_confidence:.2f}"
        
        # Check volume confirmation if required
        if self.require_volume_confirmation:
            volume_ratio = market_data.get('volume_ratio', 0.0)
            if volume_ratio < self.min_volume_ratio:
                return False, f"Insufficient volume confirmation: {volume_ratio:.2f}x < {self.min_volume_ratio:.2f}x"
        
        # Check volatility
        volatility = market_data.get('volatility', 0.0)
        if volatility > self.max_volatility:
            return False, f"Excessive market volatility: {volatility:.4f} > {self.max_volatility:.4f}"
        
        # Check for extreme price movements
        price_change_24h = abs(market_data.get('price_change_24h', 0.0))
        if price_change_24h > 20.0:  # 20% in 24h is extreme
            return False, f"Extreme price movement in last 24h: {price_change_24h:.2f}%"
        
        # Check for weekend low liquidity conditions
        is_weekend = datetime.now().weekday() >= 5
        if is_weekend and market_data.get('volume_ratio', 1.0) < 0.7:
            return False, "Low liquidity weekend conditions"
        
        return True, "Signal passed all validation checks"


def create_crypto_strategy_suite() -> List[BaseStrategy]:
    """
    Create a suite of crypto-specific trading strategies.
    
    Returns:
        List of crypto trading strategies
    """
    return [
        CryptoMovingAverageCrossover(
            fast_period=8,
            slow_period=21,
            signal_threshold=0.005
        ),
        CryptoRSIStrategy(
            period=14,
            base_oversold=30.0,
            base_overbought=70.0,
            volatility_adjustment=True
        ),
        Crypto24hMarketStrategy()
    ]