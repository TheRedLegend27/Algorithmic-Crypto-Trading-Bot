"""
Market Regime Detection System for Adaptive Trading Bot.

This module implements multi-timeframe market regime detection using various
technical indicators to classify market conditions.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from dataclasses import asdict

from .interfaces import MarketRegimeDetectorInterface
from .data_models import MarketRegime
from .enums import RegimeType


class MarketRegimeDetector(MarketRegimeDetectorInterface):
    """
    Multi-timeframe market regime detector that analyzes trend, volatility,
    and momentum to classify market conditions.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the market regime detector.
        
        Args:
            config: Configuration dictionary with detector parameters
        """
        self.logger = logging.getLogger(__name__)
        
        # Default configuration
        self.config = {
            'timeframes': ['5m', '15m', '1h', '4h'],
            'timeframe_weights': {'5m': 0.1, '15m': 0.2, '1h': 0.3, '4h': 0.4},
            'trend_threshold': 0.6,
            'volatility_threshold': 0.7,
            'momentum_threshold': 0.5,
            'confidence_threshold': 0.5,
            'smoothing_factor': 0.3,  # For regime transition smoothing
            'min_data_points': 100,
            'regime_history_hours': 48
        }
        
        if config:
            self.config.update(config)
        
        # Internal state
        self._regime_history: Dict[str, List[MarketRegime]] = {}
        self._last_regime: Dict[str, MarketRegime] = {}
        self._indicator_cache: Dict[str, Dict] = {}
        
        self.logger.info("MarketRegimeDetector initialized with config: %s", self.config)
    
    def detect_regime(self, market_data: pd.DataFrame, pair: str) -> MarketRegime:
        """
        Detect the current market regime for a given trading pair.
        
        Args:
            market_data: Historical market data with OHLCV columns
            pair: Trading pair symbol
            
        Returns:
            MarketRegime object with detected regime and metadata
        """
        try:
            if len(market_data) < self.config['min_data_points']:
                self.logger.warning(f"Insufficient data for {pair}: {len(market_data)} points")
                return self._create_uncertain_regime()
            
            # Calculate indicators for all timeframes
            timeframe_analysis = {}
            supporting_indicators = {}
            
            for timeframe in self.config['timeframes']:
                tf_data = self._resample_data(market_data, timeframe)
                if len(tf_data) < 20:  # Minimum for meaningful analysis
                    continue
                
                # Calculate regime indicators for this timeframe
                tf_indicators = self._calculate_regime_indicators(tf_data)
                tf_regime_scores = self._calculate_regime_scores(tf_indicators)
                
                timeframe_analysis[timeframe] = tf_regime_scores
                
                # Add to supporting indicators with timeframe prefix
                for indicator, value in tf_indicators.items():
                    supporting_indicators[f"{timeframe}_{indicator}"] = value
            
            if not timeframe_analysis:
                self.logger.warning(f"No valid timeframe analysis for {pair}")
                return self._create_uncertain_regime()
            
            # Combine timeframe analysis with weights
            combined_scores = self._combine_timeframe_scores(timeframe_analysis)
            
            # Determine regime type and confidence
            regime_type, confidence = self._determine_regime(combined_scores)
            
            # Calculate additional metrics
            volatility_level = self._calculate_volatility_level(market_data)
            trend_strength = self._calculate_trend_strength(market_data)
            momentum = self._calculate_momentum(market_data)
            
            # Apply smoothing if we have previous regime
            if pair in self._last_regime:
                regime_type, confidence = self._apply_regime_smoothing(
                    regime_type, confidence, self._last_regime[pair]
                )
            
            # Create regime object
            regime = MarketRegime(
                regime_type=regime_type,
                confidence=confidence,
                volatility_level=volatility_level,
                trend_strength=trend_strength,
                momentum=momentum,
                detected_at=datetime.now(),
                supporting_indicators=supporting_indicators,
                timeframe_analysis=combined_scores
            )
            
            # Store in history and cache
            self._store_regime_in_history(pair, regime)
            self._last_regime[pair] = regime
            
            self.logger.debug(f"Detected regime for {pair}: {regime_type.value} (confidence: {confidence:.2f})")
            
            return regime
            
        except Exception as e:
            self.logger.error(f"Error detecting regime for {pair}: {e}")
            return self._create_uncertain_regime()
    
    def get_regime_confidence(self, pair: str) -> float:
        """Get confidence level for the current regime detection."""
        if pair in self._last_regime:
            return self._last_regime[pair].confidence
        return 0.0
    
    def get_regime_history(self, pair: str, lookback_hours: int = 24) -> List[MarketRegime]:
        """Get historical regime detections for analysis."""
        if pair not in self._regime_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        return [
            regime for regime in self._regime_history[pair]
            if regime.detected_at >= cutoff_time
        ]
    
    def update_regime_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update regime detection parameters."""
        self.config.update(parameters)
        self.logger.info(f"Updated regime detection parameters: {parameters}")
    
    def _resample_data(self, data: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample data to specified timeframe."""
        try:
            # Convert timeframe to pandas frequency
            freq_map = {
                '5m': '5min',
                '15m': '15min',
                '1h': '1h',
                '4h': '4h'
            }
            
            if timeframe not in freq_map:
                return data
            
            freq = freq_map[timeframe]
            
            # Ensure we have a datetime index
            if not isinstance(data.index, pd.DatetimeIndex):
                if 'timestamp' in data.columns:
                    data = data.set_index('timestamp')
                else:
                    # Assume the data is already in chronological order
                    data.index = pd.date_range(
                        start=datetime.now() - timedelta(minutes=len(data)),
                        periods=len(data),
                        freq='1T'
                    )
            
            # Resample OHLCV data
            resampled = data.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            return resampled
            
        except Exception as e:
            self.logger.error(f"Error resampling data to {timeframe}: {e}")
            return data
    
    def _calculate_regime_indicators(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate technical indicators for regime detection."""
        indicators = {}
        
        try:
            # Trend indicators
            indicators['sma_20'] = data['close'].rolling(20).mean().iloc[-1]
            indicators['sma_50'] = data['close'].rolling(50).mean().iloc[-1]
            indicators['ema_12'] = data['close'].ewm(span=12).mean().iloc[-1]
            indicators['ema_26'] = data['close'].ewm(span=26).mean().iloc[-1]
            
            # ADX for trend strength
            indicators['adx'] = self._calculate_adx(data)
            
            # Volatility indicators
            indicators['atr'] = self._calculate_atr(data)
            indicators['bb_width'] = self._calculate_bollinger_width(data)
            
            # Momentum indicators
            indicators['rsi'] = self._calculate_rsi(data)
            indicators['macd'] = indicators['ema_12'] - indicators['ema_26']
            indicators['macd_signal'] = pd.Series([indicators['macd']]).ewm(span=9).mean().iloc[0]
            
            # Price position indicators
            current_price = data['close'].iloc[-1]
            indicators['price_vs_sma20'] = (current_price - indicators['sma_20']) / indicators['sma_20']
            indicators['price_vs_sma50'] = (current_price - indicators['sma_50']) / indicators['sma_50']
            
            # Volume indicators
            indicators['volume_sma'] = data['volume'].rolling(20).mean().iloc[-1]
            indicators['volume_ratio'] = data['volume'].iloc[-1] / indicators['volume_sma']
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            # Return default values
            indicators = {key: 0.0 for key in [
                'sma_20', 'sma_50', 'ema_12', 'ema_26', 'adx', 'atr', 'bb_width',
                'rsi', 'macd', 'macd_signal', 'price_vs_sma20', 'price_vs_sma50',
                'volume_sma', 'volume_ratio'
            ]}
        
        return indicators
    
    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index."""
        try:
            high = data['high']
            low = data['low']
            close = data['close']
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            dm_plus = high - high.shift(1)
            dm_minus = low.shift(1) - low
            
            dm_plus[dm_plus < 0] = 0
            dm_minus[dm_minus < 0] = 0
            dm_plus[(dm_plus - dm_minus) <= 0] = 0
            dm_minus[(dm_minus - dm_plus) <= 0] = 0
            
            # Smoothed values
            tr_smooth = tr.rolling(period).mean()
            dm_plus_smooth = dm_plus.rolling(period).mean()
            dm_minus_smooth = dm_minus.rolling(period).mean()
            
            # Directional Indicators
            di_plus = 100 * dm_plus_smooth / tr_smooth
            di_minus = 100 * dm_minus_smooth / tr_smooth
            
            # ADX
            dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
            adx = dx.rolling(period).mean().iloc[-1]
            
            return adx if not pd.isna(adx) else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        try:
            high = data['high']
            low = data['low']
            close = data['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = tr.rolling(period).mean().iloc[-1]
            return atr if not pd.isna(atr) else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_bollinger_width(self, data: pd.DataFrame, period: int = 20) -> float:
        """Calculate Bollinger Band width as volatility measure."""
        try:
            sma = data['close'].rolling(period).mean()
            std = data['close'].rolling(period).std()
            
            upper_band = sma + (2 * std)
            lower_band = sma - (2 * std)
            
            width = ((upper_band - lower_band) / sma).iloc[-1]
            return width if not pd.isna(width) else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        try:
            delta = data['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(period).mean()
            avg_loss = loss.rolling(period).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
            
        except Exception:
            return 50.0
    
    def _calculate_regime_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate regime scores based on indicators."""
        scores = {}
        
        try:
            # Trending Bull score
            bull_score = 0.0
            if indicators['price_vs_sma20'] > 0.02:  # Price above SMA20 by 2%
                bull_score += 0.3
            if indicators['sma_20'] > indicators['sma_50']:  # SMA20 above SMA50
                bull_score += 0.2
            if indicators['macd'] > indicators['macd_signal']:  # MACD bullish
                bull_score += 0.2
            if indicators['rsi'] > 50 and indicators['rsi'] < 80:  # RSI in bullish range
                bull_score += 0.2
            if indicators['adx'] > 25:  # Strong trend
                bull_score += 0.1
            
            scores['trending_bull'] = min(bull_score, 1.0)
            
            # Trending Bear score
            bear_score = 0.0
            if indicators['price_vs_sma20'] < -0.02:  # Price below SMA20 by 2%
                bear_score += 0.3
            if indicators['sma_20'] < indicators['sma_50']:  # SMA20 below SMA50
                bear_score += 0.2
            if indicators['macd'] < indicators['macd_signal']:  # MACD bearish
                bear_score += 0.2
            if indicators['rsi'] < 50 and indicators['rsi'] > 20:  # RSI in bearish range
                bear_score += 0.2
            if indicators['adx'] > 25:  # Strong trend
                bear_score += 0.1
            
            scores['trending_bear'] = min(bear_score, 1.0)
            
            # Ranging score
            ranging_score = 0.0
            if abs(indicators['price_vs_sma20']) < 0.01:  # Price near SMA20
                ranging_score += 0.3
            if indicators['adx'] < 25:  # Weak trend
                ranging_score += 0.3
            if 40 < indicators['rsi'] < 60:  # RSI in neutral range
                ranging_score += 0.2
            if abs(indicators['macd'] - indicators['macd_signal']) < 0.001:  # MACD near signal
                ranging_score += 0.2
            
            scores['ranging'] = min(ranging_score, 1.0)
            
            # High volatility score
            high_vol_score = 0.0
            if indicators['atr'] > 0:  # We need a baseline for comparison
                # Use BB width as primary volatility measure
                if indicators['bb_width'] > 0.04:  # High BB width
                    high_vol_score += 0.4
                if indicators['volume_ratio'] > 1.5:  # High volume
                    high_vol_score += 0.3
                if indicators['atr'] > 0.02:  # High ATR (relative)
                    high_vol_score += 0.3
            
            scores['high_volatility'] = min(high_vol_score, 1.0)
            
            # Low volatility score
            low_vol_score = 0.0
            if indicators['bb_width'] < 0.02:  # Low BB width
                low_vol_score += 0.4
            if indicators['volume_ratio'] < 0.8:  # Low volume
                low_vol_score += 0.3
            if indicators['atr'] < 0.01:  # Low ATR
                low_vol_score += 0.3
            
            scores['low_volatility'] = min(low_vol_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating regime scores: {e}")
            scores = {
                'trending_bull': 0.0,
                'trending_bear': 0.0,
                'ranging': 0.0,
                'high_volatility': 0.0,
                'low_volatility': 0.0
            }
        
        return scores
    
    def _combine_timeframe_scores(self, timeframe_analysis: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Combine scores from multiple timeframes with weights."""
        combined_scores = {
            'trending_bull': 0.0,
            'trending_bear': 0.0,
            'ranging': 0.0,
            'high_volatility': 0.0,
            'low_volatility': 0.0
        }
        
        total_weight = 0.0
        
        for timeframe, scores in timeframe_analysis.items():
            weight = self.config['timeframe_weights'].get(timeframe, 0.25)
            total_weight += weight
            
            for regime_type, score in scores.items():
                combined_scores[regime_type] += score * weight
        
        # Normalize by total weight
        if total_weight > 0:
            for regime_type in combined_scores:
                combined_scores[regime_type] /= total_weight
        
        return combined_scores
    
    def _determine_regime(self, scores: Dict[str, float]) -> Tuple[RegimeType, float]:
        """Determine regime type and confidence from scores with enhanced validation."""
        # Find the regime with highest score
        max_score = max(scores.values())
        max_regime = max(scores, key=scores.get)
        
        # Map string keys to RegimeType enum
        regime_map = {
            'trending_bull': RegimeType.TRENDING_BULL,
            'trending_bear': RegimeType.TRENDING_BEAR,
            'ranging': RegimeType.RANGING,
            'high_volatility': RegimeType.HIGH_VOLATILITY,
            'low_volatility': RegimeType.LOW_VOLATILITY
        }
        
        regime_type = regime_map.get(max_regime, RegimeType.UNCERTAIN)
        
        # Enhanced confidence calculation based on multiple factors
        confidence = self._calculate_enhanced_confidence(scores, max_score, max_regime)
        
        # Validate regime consistency
        if not self._validate_regime_consistency(regime_type, scores):
            regime_type = RegimeType.UNCERTAIN
            confidence *= 0.5  # Reduce confidence for inconsistent regimes
        
        # If confidence is too low, mark as uncertain
        if confidence < self.config['confidence_threshold']:
            regime_type = RegimeType.UNCERTAIN
            confidence = max_score
        
        return regime_type, confidence
    
    def _calculate_volatility_level(self, data: pd.DataFrame) -> float:
        """Calculate normalized volatility level."""
        try:
            returns = data['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(len(returns))  # Annualized volatility
            
            # Normalize to 0-1 range (assuming typical crypto volatility of 0-200%)
            normalized_vol = min(volatility / 2.0, 1.0)
            return normalized_vol
            
        except Exception:
            return 0.5  # Default moderate volatility
    
    def _calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """Calculate trend strength (-1 to 1)."""
        try:
            # Use price change over different periods
            short_change = (data['close'].iloc[-1] - data['close'].iloc[-20]) / data['close'].iloc[-20]
            long_change = (data['close'].iloc[-1] - data['close'].iloc[-50]) / data['close'].iloc[-50]
            
            # Combine and normalize
            trend_strength = (short_change * 0.6 + long_change * 0.4)
            
            # Clamp to -1, 1 range
            return max(min(trend_strength * 5, 1.0), -1.0)  # Scale factor of 5
            
        except Exception:
            return 0.0
    
    def _calculate_momentum(self, data: pd.DataFrame) -> float:
        """Calculate momentum (-1 to 1)."""
        try:
            # Use RSI and MACD for momentum
            rsi = self._calculate_rsi(data)
            
            # Convert RSI to -1 to 1 scale
            rsi_momentum = (rsi - 50) / 50
            
            # Simple price momentum
            price_momentum = (data['close'].iloc[-1] - data['close'].iloc[-10]) / data['close'].iloc[-10]
            price_momentum = max(min(price_momentum * 10, 1.0), -1.0)
            
            # Combine
            momentum = (rsi_momentum * 0.6 + price_momentum * 0.4)
            
            return max(min(momentum, 1.0), -1.0)
            
        except Exception:
            return 0.0
    
    def _apply_regime_smoothing(
        self, 
        new_regime: RegimeType, 
        new_confidence: float, 
        last_regime: MarketRegime
    ) -> Tuple[RegimeType, float]:
        """Apply enhanced smoothing to prevent rapid regime switching with validation."""
        if new_regime == last_regime.regime_type:
            # Same regime - apply confidence smoothing
            smoothed_confidence = (
                last_regime.confidence * self.config['smoothing_factor'] +
                new_confidence * (1 - self.config['smoothing_factor'])
            )
            return new_regime, smoothed_confidence
        
        # Different regime - apply transition validation
        time_since_last = datetime.now() - last_regime.detected_at
        
        # Calculate dynamic switching thresholds based on multiple factors
        switch_decision = self._evaluate_regime_switch(
            new_regime, new_confidence, last_regime, time_since_last
        )
        
        if switch_decision['should_switch']:
            # Apply transition confidence adjustment
            transition_confidence = self._calculate_transition_confidence(
                new_confidence, last_regime, switch_decision
            )
            return new_regime, transition_confidence
        else:
            # Stay with previous regime but update confidence with decay
            confidence_decay = self._calculate_confidence_decay(time_since_last)
            smoothed_confidence = (
                last_regime.confidence * confidence_decay * self.config['smoothing_factor'] +
                new_confidence * (1 - self.config['smoothing_factor'])
            )
            return last_regime.regime_type, min(smoothed_confidence, last_regime.confidence)
    
    def _evaluate_regime_switch(
        self, 
        new_regime: RegimeType, 
        new_confidence: float, 
        last_regime: MarketRegime, 
        time_since_last: timedelta
    ) -> Dict[str, Any]:
        """Evaluate whether a regime switch should occur based on multiple criteria."""
        
        # Base time and confidence requirements
        min_switch_time = timedelta(minutes=15)  # Reduced from 30 for more responsiveness
        base_confidence_threshold = self.config['confidence_threshold']
        
        # Dynamic confidence threshold based on time
        if time_since_last < min_switch_time:
            confidence_threshold = 0.85  # Very high confidence required for quick switches
        elif time_since_last < timedelta(minutes=30):
            confidence_threshold = 0.75  # High confidence for medium-term switches
        else:
            confidence_threshold = base_confidence_threshold  # Normal threshold for longer periods
        
        # Regime transition compatibility check
        transition_compatibility = self._check_regime_transition_compatibility(
            last_regime.regime_type, new_regime
        )
        
        # Historical transition probability
        transition_probability = self._get_transition_probability_score(
            last_regime.regime_type, new_regime
        )
        
        # Confidence gap requirement (new confidence should be significantly higher)
        confidence_gap = new_confidence - last_regime.confidence
        min_confidence_gap = 0.1  # Require at least 10% confidence improvement
        
        # Decision factors
        factors = {
            'time_sufficient': bool(time_since_last >= min_switch_time),
            'confidence_sufficient': bool(new_confidence >= confidence_threshold),
            'confidence_gap_sufficient': bool(confidence_gap >= min_confidence_gap),
            'transition_compatible': bool(transition_compatibility),
            'historical_probability_good': bool(transition_probability > 0.2)
        }
        
        # Calculate switch score
        switch_score = (
            factors['time_sufficient'] * 0.2 +
            factors['confidence_sufficient'] * 0.3 +
            factors['confidence_gap_sufficient'] * 0.2 +
            factors['transition_compatible'] * 0.2 +
            factors['historical_probability_good'] * 0.1
        )
        
        # Require at least 3 out of 5 factors to be true, or very high switch score
        should_switch = (sum(factors.values()) >= 3) or (switch_score >= 0.8)
        
        return {
            'should_switch': bool(should_switch),
            'switch_score': switch_score,
            'factors': factors,
            'confidence_threshold': confidence_threshold,
            'transition_probability': transition_probability
        }
    
    def _check_regime_transition_compatibility(self, from_regime: RegimeType, to_regime: RegimeType) -> bool:
        """Check if a regime transition is logically compatible."""
        # Define compatible transitions
        compatible_transitions = {
            RegimeType.TRENDING_BULL: [RegimeType.RANGING, RegimeType.HIGH_VOLATILITY, RegimeType.LOW_VOLATILITY],
            RegimeType.TRENDING_BEAR: [RegimeType.RANGING, RegimeType.HIGH_VOLATILITY, RegimeType.LOW_VOLATILITY],
            RegimeType.RANGING: [RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR, RegimeType.HIGH_VOLATILITY, RegimeType.LOW_VOLATILITY],
            RegimeType.HIGH_VOLATILITY: [RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR, RegimeType.RANGING, RegimeType.LOW_VOLATILITY],
            RegimeType.LOW_VOLATILITY: [RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR, RegimeType.RANGING, RegimeType.HIGH_VOLATILITY],
            RegimeType.UNCERTAIN: [RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR, RegimeType.RANGING, RegimeType.HIGH_VOLATILITY, RegimeType.LOW_VOLATILITY]
        }
        
        # Direct transitions between bull and bear are less compatible (should go through ranging)
        if ((from_regime == RegimeType.TRENDING_BULL and to_regime == RegimeType.TRENDING_BEAR) or
            (from_regime == RegimeType.TRENDING_BEAR and to_regime == RegimeType.TRENDING_BULL)):
            return False
        
        return to_regime in compatible_transitions.get(from_regime, [])
    
    def _get_transition_probability_score(self, from_regime: RegimeType, to_regime: RegimeType) -> float:
        """Get a score for how likely this transition is based on historical data."""
        total_transitions = 0
        matching_transitions = 0
        
        for pair_history in self._regime_history.values():
            if len(pair_history) < 2:
                continue
            
            for i in range(1, len(pair_history)):
                prev_regime = pair_history[i-1].regime_type
                curr_regime = pair_history[i].regime_type
                
                if prev_regime == from_regime:
                    total_transitions += 1
                    if curr_regime == to_regime:
                        matching_transitions += 1
        
        if total_transitions == 0:
            return 0.5  # Neutral probability if no historical data
        
        return matching_transitions / total_transitions
    
    def _calculate_transition_confidence(
        self, 
        new_confidence: float, 
        last_regime: MarketRegime, 
        switch_decision: Dict[str, Any]
    ) -> float:
        """Calculate confidence for a regime transition."""
        # Base confidence from the new detection
        base_confidence = new_confidence
        
        # Adjust based on switch decision quality
        switch_quality_adjustment = switch_decision['switch_score'] * 0.1
        
        # Adjust based on historical transition probability
        transition_prob_adjustment = switch_decision['transition_probability'] * 0.05
        
        # Penalty for very recent switches (even if allowed)
        time_penalty = 0.0
        if hasattr(last_regime, 'detected_at'):
            time_since_last = datetime.now() - last_regime.detected_at
            if time_since_last < timedelta(minutes=30):
                time_penalty = 0.05
        
        # Calculate final transition confidence
        transition_confidence = (
            base_confidence + 
            switch_quality_adjustment + 
            transition_prob_adjustment - 
            time_penalty
        )
        
        return min(max(transition_confidence, 0.0), 1.0)
    
    def _calculate_confidence_decay(self, time_since_last: timedelta) -> float:
        """Calculate confidence decay factor based on time since last detection."""
        # Confidence decays over time if no regime switch occurs
        hours_since_last = time_since_last.total_seconds() / 3600
        
        # Decay function: starts at 1.0, decays to 0.8 over 24 hours
        decay_rate = 0.01  # 1% decay per hour
        decay_factor = max(1.0 - (hours_since_last * decay_rate), 0.8)
        
        return decay_factor
    
    def _create_uncertain_regime(self) -> MarketRegime:
        """Create an uncertain regime for error cases."""
        return MarketRegime(
            regime_type=RegimeType.UNCERTAIN,
            confidence=0.0,
            volatility_level=0.5,
            trend_strength=0.0,
            momentum=0.0,
            detected_at=datetime.now(),
            supporting_indicators={},
            timeframe_analysis={}
        )
    
    def _calculate_enhanced_confidence(self, scores: Dict[str, float], max_score: float, max_regime: str) -> float:
        """Calculate enhanced confidence based on multiple factors with improved validation."""
        # Base confidence from score separation
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2:
            separation_confidence = max_score - sorted_scores[1]
        else:
            separation_confidence = max_score
        
        # Indicator agreement factor - measures how much indicators agree
        agreement_factor = self._calculate_indicator_agreement(scores)
        
        # Regime strength factor (how strong the signals are)
        strength_factor = max_score
        
        # Historical consistency factor - how consistent with recent history
        consistency_factor = self._calculate_historical_consistency(max_regime)
        
        # Signal quality factor - penalize conflicting signals
        quality_factor = self._calculate_signal_quality(scores, max_regime)
        
        # Time stability factor - reward stable regimes over time
        stability_factor = self._calculate_time_stability_factor(max_regime)
        
        # Combine factors with enhanced weights
        confidence = (
            separation_confidence * 0.25 +  # How much the winner stands out
            agreement_factor * 0.20 +       # How much indicators agree
            strength_factor * 0.15 +        # Raw strength of the signal
            consistency_factor * 0.15 +     # Historical consistency
            quality_factor * 0.15 +         # Signal quality (no conflicts)
            stability_factor * 0.10         # Time-based stability
        )
        
        return min(max(confidence, 0.0), 1.0)
    
    def _calculate_indicator_agreement(self, scores: Dict[str, float]) -> float:
        """Calculate how much indicators agree on the regime."""
        # Calculate the variance in scores - lower variance means more agreement
        score_values = list(scores.values())
        if len(score_values) <= 1:
            return 1.0
        
        mean_score = np.mean(score_values)
        variance = np.var(score_values)
        
        # Convert variance to agreement score (lower variance = higher agreement)
        # Normalize by expected maximum variance (0.25 for scores 0-1)
        agreement = 1.0 - min(variance / 0.25, 1.0)
        
        return agreement
    
    def _calculate_historical_consistency(self, current_regime: str) -> float:
        """Calculate consistency with recent historical regimes."""
        consistency_scores = []
        
        for pair_history in self._regime_history.values():
            if len(pair_history) < 2:
                continue
            
            # Look at recent regimes (last 5)
            recent_regimes = pair_history[-5:]
            regime_types = [r.regime_type.value for r in recent_regimes]
            
            # Calculate consistency as frequency of current regime type
            if current_regime in regime_types:
                consistency = regime_types.count(current_regime) / len(regime_types)
                consistency_scores.append(consistency)
        
        if not consistency_scores:
            return 0.5  # Neutral if no history
        
        return np.mean(consistency_scores)
    
    def _calculate_signal_quality(self, scores: Dict[str, float], max_regime: str) -> float:
        """Calculate signal quality by penalizing conflicting signals."""
        quality_score = 1.0
        
        # Check for conflicting regime signals
        if max_regime == 'trending_bull':
            # Penalize if bear score is also high
            bear_penalty = min(scores.get('trending_bear', 0) * 0.5, 0.3)
            quality_score -= bear_penalty
        elif max_regime == 'trending_bear':
            # Penalize if bull score is also high
            bull_penalty = min(scores.get('trending_bull', 0) * 0.5, 0.3)
            quality_score -= bull_penalty
        elif max_regime == 'ranging':
            # Penalize if trend scores are high
            trend_penalty = min(max(scores.get('trending_bull', 0), scores.get('trending_bear', 0)) * 0.4, 0.3)
            quality_score -= trend_penalty
        
        # Check for volatility conflicts
        high_vol = scores.get('high_volatility', 0)
        low_vol = scores.get('low_volatility', 0)
        if high_vol > 0.5 and low_vol > 0.5:
            # Both high and low volatility signals are strong - penalize
            vol_penalty = min((high_vol + low_vol - 1.0) * 0.5, 0.2)
            quality_score -= vol_penalty
        
        return max(quality_score, 0.0)
    
    def _calculate_time_stability_factor(self, current_regime: str) -> float:
        """Calculate time-based stability factor for regime confidence."""
        stability_scores = []
        
        for pair, pair_history in self._regime_history.items():
            if len(pair_history) < 3:
                continue
            
            # Look at recent regime duration and stability
            recent_regimes = pair_history[-10:]  # Last 10 detections
            
            # Calculate regime persistence (how long regimes last)
            regime_durations = []
            current_regime_start = None
            current_regime_type = None
            
            for regime in recent_regimes:
                if regime.regime_type.value != current_regime_type:
                    if current_regime_start is not None:
                        duration = regime.detected_at - current_regime_start
                        regime_durations.append(duration.total_seconds() / 60)  # Duration in minutes
                    current_regime_start = regime.detected_at
                    current_regime_type = regime.regime_type.value
            
            if regime_durations:
                avg_duration = np.mean(regime_durations)
                # Normalize duration to 0-1 scale (assuming 30 minutes is good stability)
                stability_score = min(avg_duration / 30.0, 1.0)
                stability_scores.append(stability_score)
        
        if not stability_scores:
            return 0.5  # Neutral if no history
        
        return np.mean(stability_scores)
    
    def _validate_regime_consistency(self, regime_type: RegimeType, scores: Dict[str, float]) -> bool:
        """Validate that the regime is internally consistent."""
        # Check for conflicting signals
        if regime_type == RegimeType.TRENDING_BULL:
            # Bull trend shouldn't have high bear score
            if scores.get('trending_bear', 0) > 0.6:
                return False
        elif regime_type == RegimeType.TRENDING_BEAR:
            # Bear trend shouldn't have high bull score
            if scores.get('trending_bull', 0) > 0.6:
                return False
        elif regime_type == RegimeType.RANGING:
            # Ranging shouldn't have high trend scores
            if max(scores.get('trending_bull', 0), scores.get('trending_bear', 0)) > 0.7:
                return False
        
        # Check volatility consistency
        high_vol = scores.get('high_volatility', 0)
        low_vol = scores.get('low_volatility', 0)
        if high_vol > 0.7 and low_vol > 0.7:  # Can't be both high and low volatility
            return False
        
        return True
    
    def validate_regime_stability(self, pair: str, min_duration_minutes: int = 30) -> Dict[str, Any]:
        """Enhanced regime stability validation with comprehensive metrics."""
        if pair not in self._regime_history:
            return {
                'stable': False, 
                'reason': 'No history available',
                'stability_score': 0.0,
                'confidence_trend': 'unknown'
            }
        
        history = self._regime_history[pair]
        if len(history) < 2:
            return {
                'stable': False, 
                'reason': 'Insufficient history',
                'stability_score': 0.0,
                'confidence_trend': 'unknown'
            }
        
        # Check recent regime changes
        recent_cutoff = datetime.now() - timedelta(minutes=min_duration_minutes)
        recent_regimes = [r for r in history if r.detected_at >= recent_cutoff]
        
        if len(recent_regimes) < 2:
            return {
                'stable': True, 
                'reason': 'Single regime in period',
                'stability_score': 1.0,
                'confidence_trend': 'stable'
            }
        
        # Enhanced stability analysis
        stability_metrics = self._calculate_comprehensive_stability_metrics(recent_regimes)
        
        # Determine overall stability
        is_stable = (
            stability_metrics['stability_ratio'] >= 0.7 and
            stability_metrics['avg_confidence'] >= 0.6 and
            stability_metrics['confidence_trend_score'] >= 0.5
        )
        
        return {
            'stable': bool(is_stable),
            'stability_score': stability_metrics['overall_stability_score'],
            'stability_ratio': stability_metrics['stability_ratio'],
            'avg_confidence': stability_metrics['avg_confidence'],
            'confidence_trend': stability_metrics['confidence_trend'],
            'confidence_trend_score': stability_metrics['confidence_trend_score'],
            'regime_changes': stability_metrics['regime_changes'],
            'avg_regime_duration': stability_metrics['avg_regime_duration'],
            'confidence_volatility': stability_metrics['confidence_volatility'],
            'period_minutes': min_duration_minutes,
            'total_regimes_analyzed': len(recent_regimes)
        }
    
    def _calculate_comprehensive_stability_metrics(self, regimes: List[MarketRegime]) -> Dict[str, Any]:
        """Calculate comprehensive stability metrics for regime analysis."""
        if len(regimes) < 2:
            return self._get_default_stability_metrics()
        
        # Basic regime change analysis
        regime_changes = 0
        regime_durations = []
        current_regime_start = regimes[0].detected_at
        current_regime_type = regimes[0].regime_type
        
        for i in range(1, len(regimes)):
            if regimes[i].regime_type != current_regime_type:
                regime_changes += 1
                duration = regimes[i].detected_at - current_regime_start
                regime_durations.append(duration.total_seconds() / 60)  # Duration in minutes
                current_regime_start = regimes[i].detected_at
                current_regime_type = regimes[i].regime_type
        
        # Add final regime duration
        if regimes:
            final_duration = datetime.now() - current_regime_start
            regime_durations.append(final_duration.total_seconds() / 60)
        
        # Stability ratio
        stability_ratio = 1.0 - (regime_changes / len(regimes)) if len(regimes) > 0 else 0.0
        
        # Confidence analysis
        confidences = [r.confidence for r in regimes]
        avg_confidence = np.mean(confidences)
        confidence_volatility = np.std(confidences) if len(confidences) > 1 else 0.0
        
        # Confidence trend analysis
        confidence_trend_score, confidence_trend = self._analyze_confidence_trend(confidences)
        
        # Average regime duration
        avg_regime_duration = np.mean(regime_durations) if regime_durations else 0.0
        
        # Overall stability score (weighted combination)
        overall_stability_score = (
            stability_ratio * 0.4 +
            min(avg_confidence, 1.0) * 0.3 +
            confidence_trend_score * 0.2 +
            min(avg_regime_duration / 30.0, 1.0) * 0.1  # Normalize to 30 minutes
        )
        
        return {
            'stability_ratio': stability_ratio,
            'avg_confidence': avg_confidence,
            'confidence_volatility': confidence_volatility,
            'confidence_trend': confidence_trend,
            'confidence_trend_score': confidence_trend_score,
            'regime_changes': regime_changes,
            'avg_regime_duration': avg_regime_duration,
            'overall_stability_score': overall_stability_score
        }
    
    def _analyze_confidence_trend(self, confidences: List[float]) -> Tuple[float, str]:
        """Analyze the trend in confidence values over time."""
        if len(confidences) < 3:
            return 0.5, 'insufficient_data'
        
        # Calculate linear trend
        x = np.arange(len(confidences))
        y = np.array(confidences)
        
        # Simple linear regression
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)
        
        # Calculate slope
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Normalize slope to 0-1 scale
        # Positive slope = improving confidence, negative = declining
        trend_score = 0.5 + (slope * 10)  # Scale factor of 10
        trend_score = max(0.0, min(1.0, trend_score))
        
        # Classify trend
        if slope > 0.02:
            trend = 'improving'
        elif slope < -0.02:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return trend_score, trend
    
    def _get_default_stability_metrics(self) -> Dict[str, Any]:
        """Get default stability metrics for edge cases."""
        return {
            'stability_ratio': 0.0,
            'avg_confidence': 0.0,
            'confidence_volatility': 0.0,
            'confidence_trend': 'unknown',
            'confidence_trend_score': 0.5,
            'regime_changes': 0,
            'avg_regime_duration': 0.0,
            'overall_stability_score': 0.0
        }
    
    def get_regime_transition_probability(self, pair: str, target_regime: RegimeType) -> float:
        """Calculate probability of transitioning to target regime."""
        if pair not in self._regime_history:
            return 0.5  # Neutral probability
        
        history = self._regime_history[pair]
        if len(history) < 2:
            return 0.5
        
        current_regime = history[-1].regime_type
        if current_regime == target_regime:
            return 1.0  # Already in target regime
        
        # Count historical transitions
        transitions = {}
        for i in range(1, len(history)):
            from_regime = history[i-1].regime_type
            to_regime = history[i].regime_type
            
            if from_regime not in transitions:
                transitions[from_regime] = {}
            if to_regime not in transitions[from_regime]:
                transitions[from_regime][to_regime] = 0
            
            transitions[from_regime][to_regime] += 1
        
        # Calculate transition probability
        if current_regime in transitions:
            total_transitions = sum(transitions[current_regime].values())
            target_transitions = transitions[current_regime].get(target_regime, 0)
            return target_transitions / total_transitions if total_transitions > 0 else 0.0
        
        return 0.1  # Low probability for unseen transitions
    
    def get_confidence_breakdown(self, pair: str) -> Dict[str, Any]:
        """Get detailed confidence breakdown with enhanced analysis."""
        if pair not in self._last_regime:
            return {'error': 'No regime data available for pair'}
        
        regime = self._last_regime[pair]
        
        # Calculate indicator agreement from supporting indicators
        indicator_agreement = self._analyze_indicator_agreement(regime.supporting_indicators)
        
        # Get regime strength analysis
        regime_strength = self._analyze_regime_strength(regime)
        
        # Historical consistency analysis
        historical_analysis = self._get_historical_consistency_breakdown(pair, regime.regime_type.value)
        
        return {
            'overall_confidence': regime.confidence,
            'regime_type': regime.regime_type.value,
            'volatility_level': regime.volatility_level,
            'trend_strength': regime.trend_strength,
            'momentum': regime.momentum,
            'detected_at': regime.detected_at.isoformat(),
            
            # Enhanced confidence factors
            'indicator_agreement': indicator_agreement,
            'regime_strength_analysis': regime_strength,
            'historical_consistency': historical_analysis,
            
            # Supporting data
            'supporting_indicators_count': len(regime.supporting_indicators),
            'timeframe_analysis_count': len(regime.timeframe_analysis),
            'timeframe_analysis': regime.timeframe_analysis,
            
            # Validation metrics
            'confidence_validation': self._validate_confidence_factors(regime)
        }
    
    def _analyze_indicator_agreement(self, supporting_indicators: Dict[str, float]) -> Dict[str, Any]:
        """Analyze agreement between different indicators."""
        if not supporting_indicators:
            return {'agreement_score': 0.0, 'analysis': 'No indicators available'}
        
        # Group indicators by type
        trend_indicators = {}
        volatility_indicators = {}
        momentum_indicators = {}
        
        for indicator, value in supporting_indicators.items():
            if any(trend_key in indicator.lower() for trend_key in ['sma', 'ema', 'adx', 'price_vs']):
                trend_indicators[indicator] = value
            elif any(vol_key in indicator.lower() for vol_key in ['atr', 'bb_width', 'volume']):
                volatility_indicators[indicator] = value
            elif any(mom_key in indicator.lower() for mom_key in ['rsi', 'macd']):
                momentum_indicators[indicator] = value
        
        # Calculate agreement within each group
        trend_agreement = self._calculate_group_agreement(trend_indicators)
        volatility_agreement = self._calculate_group_agreement(volatility_indicators)
        momentum_agreement = self._calculate_group_agreement(momentum_indicators)
        
        # Overall agreement score
        agreements = [trend_agreement, volatility_agreement, momentum_agreement]
        valid_agreements = [a for a in agreements if a is not None]
        overall_agreement = np.mean(valid_agreements) if valid_agreements else 0.0
        
        return {
            'agreement_score': overall_agreement,
            'trend_agreement': trend_agreement,
            'volatility_agreement': volatility_agreement,
            'momentum_agreement': momentum_agreement,
            'indicator_groups': {
                'trend_count': len(trend_indicators),
                'volatility_count': len(volatility_indicators),
                'momentum_count': len(momentum_indicators)
            }
        }
    
    def _calculate_group_agreement(self, indicators: Dict[str, float]) -> Optional[float]:
        """Calculate agreement score for a group of indicators."""
        if len(indicators) < 2:
            return None
        
        values = list(indicators.values())
        
        # Normalize values to 0-1 range for comparison
        normalized_values = []
        for value in values:
            # Simple normalization - this could be improved with indicator-specific logic
            if abs(value) > 1:
                normalized_values.append(min(abs(value) / 100, 1.0))
            else:
                normalized_values.append(abs(value))
        
        # Calculate coefficient of variation (lower = more agreement)
        if len(normalized_values) > 1:
            mean_val = np.mean(normalized_values)
            std_val = np.std(normalized_values)
            if mean_val > 0:
                cv = std_val / mean_val
                # Convert to agreement score (0 = no agreement, 1 = perfect agreement)
                agreement = max(0.0, 1.0 - cv)
                return agreement
        
        return 0.5  # Neutral agreement if calculation fails
    
    def _analyze_regime_strength(self, regime: MarketRegime) -> Dict[str, Any]:
        """Analyze the strength of the detected regime."""
        strength_factors = {
            'confidence_level': self._categorize_confidence(regime.confidence),
            'trend_strength_level': self._categorize_trend_strength(regime.trend_strength),
            'momentum_level': self._categorize_momentum(regime.momentum),
            'volatility_level': self._categorize_volatility(regime.volatility_level)
        }
        
        # Calculate overall strength score
        strength_scores = {
            'high': 1.0,
            'medium': 0.6,
            'low': 0.3,
            'very_low': 0.1
        }
        
        total_score = sum(strength_scores.get(level, 0.5) for level in strength_factors.values())
        overall_strength = total_score / len(strength_factors)
        
        return {
            'overall_strength': overall_strength,
            'strength_factors': strength_factors,
            'regime_quality': self._assess_regime_quality(overall_strength)
        }
    
    def _categorize_confidence(self, confidence: float) -> str:
        """Categorize confidence level."""
        if confidence >= 0.8:
            return 'high'
        elif confidence >= 0.6:
            return 'medium'
        elif confidence >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def _categorize_trend_strength(self, trend_strength: float) -> str:
        """Categorize trend strength."""
        abs_strength = abs(trend_strength)
        if abs_strength >= 0.7:
            return 'high'
        elif abs_strength >= 0.4:
            return 'medium'
        elif abs_strength >= 0.2:
            return 'low'
        else:
            return 'very_low'
    
    def _categorize_momentum(self, momentum: float) -> str:
        """Categorize momentum level."""
        abs_momentum = abs(momentum)
        if abs_momentum >= 0.7:
            return 'high'
        elif abs_momentum >= 0.4:
            return 'medium'
        elif abs_momentum >= 0.2:
            return 'low'
        else:
            return 'very_low'
    
    def _categorize_volatility(self, volatility: float) -> str:
        """Categorize volatility level."""
        if volatility >= 0.7:
            return 'high'
        elif volatility >= 0.4:
            return 'medium'
        elif volatility >= 0.2:
            return 'low'
        else:
            return 'very_low'
    
    def _assess_regime_quality(self, strength_score: float) -> str:
        """Assess overall regime quality."""
        if strength_score >= 0.8:
            return 'excellent'
        elif strength_score >= 0.6:
            return 'good'
        elif strength_score >= 0.4:
            return 'fair'
        else:
            return 'poor'
    
    def _get_historical_consistency_breakdown(self, pair: str, regime_type: str) -> Dict[str, Any]:
        """Get detailed historical consistency analysis."""
        if pair not in self._regime_history:
            return {'consistency_score': 0.0, 'analysis': 'No historical data'}
        
        history = self._regime_history[pair]
        if len(history) < 2:
            return {'consistency_score': 0.0, 'analysis': 'Insufficient historical data'}
        
        # Analyze recent history (last 10 detections)
        recent_history = history[-10:]
        regime_counts = {}
        
        for regime in recent_history:
            regime_name = regime.regime_type.value
            regime_counts[regime_name] = regime_counts.get(regime_name, 0) + 1
        
        # Calculate consistency metrics
        total_detections = len(recent_history)
        current_regime_count = regime_counts.get(regime_type, 0)
        consistency_ratio = current_regime_count / total_detections
        
        # Analyze regime transitions
        transitions = []
        for i in range(1, len(recent_history)):
            prev_regime = recent_history[i-1].regime_type.value
            curr_regime = recent_history[i].regime_type.value
            if prev_regime != curr_regime:
                transitions.append((prev_regime, curr_regime))
        
        return {
            'consistency_score': consistency_ratio,
            'regime_frequency': regime_counts,
            'total_recent_detections': total_detections,
            'regime_transitions': len(transitions),
            'transition_details': transitions[-3:] if transitions else [],  # Last 3 transitions
            'stability_assessment': 'stable' if consistency_ratio > 0.6 else 'unstable'
        }
    
    def _validate_confidence_factors(self, regime: MarketRegime) -> Dict[str, Any]:
        """Validate the factors contributing to confidence calculation."""
        validation_results = {
            'confidence_range_valid': bool(0.0 <= regime.confidence <= 1.0),
            'trend_strength_range_valid': bool(-1.0 <= regime.trend_strength <= 1.0),
            'momentum_range_valid': bool(-1.0 <= regime.momentum <= 1.0),
            'volatility_range_valid': bool(0.0 <= regime.volatility_level <= 1.0),
            'has_supporting_indicators': bool(len(regime.supporting_indicators) > 0),
            'has_timeframe_analysis': bool(len(regime.timeframe_analysis) > 0),
            'detection_time_recent': bool((datetime.now() - regime.detected_at).total_seconds() < 3600)  # Within 1 hour
        }
        
        # Calculate validation score
        validation_score = sum(validation_results.values()) / len(validation_results)
        
        return {
            'validation_score': validation_score,
            'validation_details': validation_results,
            'overall_validity': bool(validation_score >= 0.8)
        }
    
    def _store_regime_in_history(self, pair: str, regime: MarketRegime) -> None:
        """Store regime in history with cleanup and persistence."""
        if pair not in self._regime_history:
            self._regime_history[pair] = []
        
        self._regime_history[pair].append(regime)
        
        # Cleanup old history
        cutoff_time = datetime.now() - timedelta(hours=self.config['regime_history_hours'])
        self._regime_history[pair] = [
            r for r in self._regime_history[pair]
            if r.detected_at >= cutoff_time
        ]
        
        # Persist regime data
        self._persist_regime_data(pair, regime)
        
        self.logger.debug(f"Stored regime in history for {pair}: {len(self._regime_history[pair])} total regimes")

    def _persist_regime_data(self, pair: str, regime: MarketRegime) -> None:
        """Persist regime data for long-term storage (placeholder for future implementation)."""
        # This could be implemented to store regime data in a database
        # For now, we just log the regime detection
        self.logger.debug(f"Persisting regime data for {pair}: {regime.regime_type.value} (confidence: {regime.confidence:.2f})")
    
    def reset_regime_history(self, pair: Optional[str] = None) -> None:
        """Reset regime history for a specific pair or all pairs."""
        if pair:
            if pair in self._regime_history:
                del self._regime_history[pair]
            if pair in self._last_regime:
                del self._last_regime[pair]
            self.logger.info(f"Reset regime history for {pair}")
        else:
            self._regime_history.clear()
            self._last_regime.clear()
            self.logger.info("Reset all regime history")
    
    def get_regime_statistics(self, pair: str, hours_back: int = 24) -> Dict[str, Any]:
        """Get statistical analysis of regime detections."""
        history = self.get_regime_history(pair, hours_back)
        
        if not history:
            return {'error': 'No regime history available'}
        
        # Count regime types
        regime_counts = {}
        confidence_by_regime = {}
        
        for regime in history:
            regime_type = regime.regime_type.value
            regime_counts[regime_type] = regime_counts.get(regime_type, 0) + 1
            
            if regime_type not in confidence_by_regime:
                confidence_by_regime[regime_type] = []
            confidence_by_regime[regime_type].append(regime.confidence)
        
        # Calculate statistics
        total_detections = len(history)
        regime_percentages = {k: (v / total_detections) * 100 for k, v in regime_counts.items()}
        
        avg_confidence_by_regime = {
            k: np.mean(v) for k, v in confidence_by_regime.items()
        }
        
        # Overall statistics
        overall_avg_confidence = np.mean([r.confidence for r in history])
        overall_volatility = np.mean([r.volatility_level for r in history])
        overall_trend_strength = np.mean([r.trend_strength for r in history])
        
        return {
            'total_detections': total_detections,
            'regime_counts': regime_counts,
            'regime_percentages': regime_percentages,
            'avg_confidence_by_regime': avg_confidence_by_regime,
            'overall_avg_confidence': overall_avg_confidence,
            'overall_volatility': overall_volatility,
            'overall_trend_strength': overall_trend_strength,
            'time_period_hours': hours_back
        }