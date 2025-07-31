"""
Adaptive Strategy Engine for dynamic strategy selection and weighting.

This module implements the core adaptive strategy engine that manages
multiple trading strategies, dynamically adjusts their weights based on
performance, and generates ensemble signals with hysteresis to prevent
whipsaws.
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
import pandas as pd
import numpy as np

from .interfaces import AdaptiveStrategyEngineInterface
from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, 
    StrategyAllocation, AdaptationEvent
)
from .enums import RegimeType, SignalStrength, AdaptationType
from ..strategy import BaseStrategy, TradingSignal, SignalType
from ..enhanced_strategies import (
    EnhancedMomentumStrategy, PriceActionStrategy, 
    MultiTimeframeStrategy, VolatilityAdjustedStrategy
)
from ..utils import log_info, log_warning, log_error


logger = logging.getLogger(__name__)


class AdaptiveStrategyEngine(AdaptiveStrategyEngineInterface):
    """
    Core adaptive strategy engine that manages strategy selection and weighting.
    
    Features:
    - Dynamic strategy weight calculation based on performance
    - Strategy switching logic with hysteresis to prevent whipsaws
    - Ensemble signal generation from multiple strategies
    - Regime-aware strategy selection
    - Performance-based strategy enabling/disabling
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the adaptive strategy engine.
        
        Args:
            config: Configuration dictionary with engine parameters
        """
        self.config = config or {}
        
        # Strategy management
        self.strategies: Dict[str, BaseStrategy] = {}
        self.strategy_allocations: Dict[str, StrategyAllocation] = {}
        
        # Performance tracking
        self.strategy_performance_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )
        self.recent_signals: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=50)
        )
        
        # Hysteresis and switching logic
        self.hysteresis_threshold = self.config.get('hysteresis_threshold', 0.15)
        self.min_switch_interval = timedelta(
            minutes=self.config.get('min_switch_interval_minutes', 30)
        )
        self.last_strategy_switch: Dict[str, datetime] = {}
        
        # Ensemble parameters
        self.min_strategies_for_ensemble = self.config.get('min_strategies_for_ensemble', 2)
        self.confidence_decay_factor = self.config.get('confidence_decay_factor', 0.95)
        
        # Performance thresholds
        self.min_performance_threshold = self.config.get('min_performance_threshold', -0.1)
        self.disable_threshold = self.config.get('disable_threshold', -0.2)
        self.reenable_threshold = self.config.get('reenable_threshold', 0.05)
        
        # Initialize default strategies
        self._initialize_default_strategies()
        
        logger.info("AdaptiveStrategyEngine initialized with %d strategies", 
                   len(self.strategies))
    
    def _initialize_default_strategies(self) -> None:
        """Initialize default trading strategies."""
        try:
            # Enhanced Momentum Strategy
            momentum_strategy = EnhancedMomentumStrategy(
                short_period=3, 
                medium_period=8,
                volume_threshold=1.1,
                momentum_threshold=0.003
            )
            self.add_strategy("enhanced_momentum", momentum_strategy, {
                'base_weight': 0.3,
                'regime_preferences': [RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR]
            })
            
            # Price Action Strategy
            price_action_strategy = PriceActionStrategy(
                lookback=20,
                min_body_pct=0.002
            )
            self.add_strategy("price_action", price_action_strategy, {
                'base_weight': 0.25,
                'regime_preferences': [RegimeType.RANGING, RegimeType.LOW_VOLATILITY]
            })
            
            # Multi-Timeframe Strategy
            mtf_strategy = MultiTimeframeStrategy(
                timeframes=['5m', '15m', '1h'],
                agreement_threshold=0.6
            )
            self.add_strategy("multi_timeframe", mtf_strategy, {
                'base_weight': 0.25,
                'regime_preferences': [RegimeType.HIGH_VOLATILITY, RegimeType.UNCERTAIN]
            })
            
            # Volatility Adjusted Strategy
            vol_strategy = VolatilityAdjustedStrategy(
                name="volatility_adjusted",
                volatility_lookback=20
            )
            self.add_strategy("volatility_adjusted", vol_strategy, {
                'base_weight': 0.2,
                'regime_preferences': [RegimeType.HIGH_VOLATILITY, RegimeType.LOW_VOLATILITY]
            })
            
        except Exception as e:
            logger.error("Error initializing default strategies: %s", str(e))
            # Initialize with minimal fallback
            self._initialize_fallback_strategies()
    
    def _initialize_fallback_strategies(self) -> None:
        """Initialize minimal fallback strategies if default initialization fails."""
        try:
            # Simple momentum strategy as fallback
            momentum_strategy = EnhancedMomentumStrategy()
            self.add_strategy("fallback_momentum", momentum_strategy, {
                'base_weight': 1.0,
                'regime_preferences': list(RegimeType)
            })
            logger.warning("Initialized with fallback strategies only")
        except Exception as e:
            logger.error("Failed to initialize fallback strategies: %s", str(e))
    
    def add_strategy(self, strategy_name: str, strategy: BaseStrategy, 
                    strategy_config: Dict[str, Any] = None) -> None:
        """
        Add a new strategy to the engine.
        
        Args:
            strategy_name: Unique name for the strategy
            strategy: Strategy instance
            strategy_config: Configuration for the strategy
        """
        if strategy_name in self.strategies:
            logger.warning("Strategy %s already exists, replacing", strategy_name)
        
        self.strategies[strategy_name] = strategy
        
        config = strategy_config or {}
        base_weight = config.get('base_weight', 1.0 / len(self.strategies))
        
        self.strategy_allocations[strategy_name] = StrategyAllocation(
            strategy_name=strategy_name,
            allocation_percentage=base_weight,
            current_weight=base_weight,
            base_weight=base_weight,
            recent_performance=0.0,
            performance_trend=0.0,
            confidence_level=0.5,
            min_allocation=config.get('min_allocation', 0.0),
            max_allocation=config.get('max_allocation', 1.0),
            is_active=True
        )
        
        # Store regime preferences
        if 'regime_preferences' in config:
            self.strategy_allocations[strategy_name].regime_preferences = config['regime_preferences']
        
        logger.info("Added strategy: %s with base weight: %.3f", 
                   strategy_name, base_weight)
    
    def remove_strategy(self, strategy_name: str) -> None:
        """
        Remove a strategy from the engine.
        
        Args:
            strategy_name: Name of the strategy to remove
        """
        if strategy_name not in self.strategies:
            logger.warning("Strategy %s not found for removal", strategy_name)
            return
        
        del self.strategies[strategy_name]
        del self.strategy_allocations[strategy_name]
        
        if strategy_name in self.strategy_performance_history:
            del self.strategy_performance_history[strategy_name]
        if strategy_name in self.recent_signals:
            del self.recent_signals[strategy_name]
        
        # Rebalance remaining strategies
        self._rebalance_allocations()
        
        logger.info("Removed strategy: %s", strategy_name)
    
    def select_optimal_strategy(self, pair: str, regime: MarketRegime) -> str:
        """
        Select the optimal strategy for current conditions.
        
        Args:
            pair: Trading pair
            regime: Current market regime
            
        Returns:
            Name of the optimal strategy
        """
        if not self.strategies:
            logger.error("No strategies available for selection")
            return None
        
        # Calculate strategy scores based on regime and performance
        strategy_scores = {}
        
        for strategy_name, allocation in self.strategy_allocations.items():
            if not allocation.is_active:
                continue
            
            score = 0.0
            
            # Base weight contribution
            score += allocation.base_weight * 0.3
            
            # Recent performance contribution
            score += allocation.recent_performance * 0.4
            
            # Regime preference contribution
            regime_bonus = self._calculate_regime_bonus(strategy_name, regime)
            score += regime_bonus * 0.2
            
            # Confidence level contribution
            score += allocation.confidence_level * 0.1
            
            strategy_scores[strategy_name] = score
        
        if not strategy_scores:
            logger.warning("No active strategies available")
            return list(self.strategies.keys())[0] if self.strategies else None
        
        # Select strategy with highest score, but apply hysteresis
        best_strategy = max(strategy_scores, key=strategy_scores.get)
        current_best_score = strategy_scores[best_strategy]
        
        # Check if we should switch from current strategy
        current_strategy = self._get_current_strategy(pair)
        if current_strategy and current_strategy in strategy_scores:
            current_score = strategy_scores[current_strategy]
            
            # Apply hysteresis - only switch if improvement is significant
            if (current_best_score - current_score) < self.hysteresis_threshold:
                # Check minimum switch interval
                last_switch = self.last_strategy_switch.get(pair)
                if last_switch and (datetime.now() - last_switch) < self.min_switch_interval:
                    return current_strategy
        
        # Record strategy switch
        if current_strategy != best_strategy:
            self.last_strategy_switch[pair] = datetime.now()
            logger.info("Strategy switch for %s: %s -> %s (score: %.3f)", 
                       pair, current_strategy, best_strategy, current_best_score)
        
        return best_strategy
    
    def execute_adaptive_signal(self, pair: str, market_data: pd.DataFrame, 
                               regime: Optional[MarketRegime] = None,
                               ml_predictions: Optional[Dict[str, float]] = None) -> Optional[AdaptiveSignal]:
        """
        Generate an adaptive trading signal using ensemble methods with ML confidence
        adjustment and regime-based filtering.
        
        Args:
            pair: Trading pair
            market_data: Market data for signal generation
            regime: Current market regime (optional)
            ml_predictions: ML model predictions (optional)
            
        Returns:
            AdaptiveSignal or None if no signal generated
        """
        if not self.strategies or market_data.empty:
            return None
        
        try:
            # Get signals from all active strategies
            strategy_signals = {}
            active_strategies = [
                name for name, alloc in self.strategy_allocations.items() 
                if alloc.is_active
            ]
            
            for strategy_name in active_strategies:
                try:
                    strategy = self.strategies[strategy_name]
                    signal = strategy.calculate_signals(market_data)
                    
                    if signal and signal.action != SignalType.HOLD:
                        strategy_signals[strategy_name] = signal
                        
                        # Store signal for performance tracking
                        self.recent_signals[strategy_name].append({
                            'signal': signal,
                            'timestamp': datetime.now(),
                            'pair': pair
                        })
                        
                except Exception as e:
                    logger.error("Error getting signal from strategy %s: %s", 
                               strategy_name, str(e))
                    continue
            
            if not strategy_signals:
                return None
            
            # Apply regime-based filtering
            if regime:
                strategy_signals = self._filter_signals_by_regime(strategy_signals, regime)
                if not strategy_signals:
                    return None
            
            # Generate ensemble signal
            ensemble_signal = self._generate_ensemble_signal(
                strategy_signals, pair, market_data, regime, ml_predictions
            )
            
            # Apply ML confidence adjustment and signal strength amplification
            if ensemble_signal:
                ensemble_signal = self._adjust_signal_confidence(
                    ensemble_signal, ml_predictions, pair
                )
                ensemble_signal = self._amplify_signal_strength(
                    ensemble_signal, pair
                )
            
            return ensemble_signal
            
        except Exception as e:
            logger.error("Error executing adaptive signal for %s: %s", pair, str(e))
            return None
    
    def _generate_ensemble_signal(self, strategy_signals: Dict[str, TradingSignal], 
                                 pair: str, market_data: pd.DataFrame,
                                 regime: Optional[MarketRegime] = None,
                                 ml_predictions: Optional[Dict[str, float]] = None) -> Optional[AdaptiveSignal]:
        """
        Generate ensemble signal from multiple strategy signals with enhanced metadata.
        
        Args:
            strategy_signals: Dictionary of strategy signals
            pair: Trading pair
            market_data: Market data
            regime: Current market regime
            ml_predictions: ML model predictions
            
        Returns:
            AdaptiveSignal or None
        """
        if len(strategy_signals) < self.min_strategies_for_ensemble:
            # Use single best strategy signal
            best_strategy = max(strategy_signals.keys(), 
                              key=lambda s: strategy_signals[s].confidence)
            base_signal = strategy_signals[best_strategy]
            
            return self._create_adaptive_signal(
                base_signal, {best_strategy: 1.0}, pair, market_data, regime, ml_predictions
            )
        
        # Calculate weighted ensemble with regime-aware weighting
        buy_weight = 0.0
        sell_weight = 0.0
        total_weight = 0.0
        strategy_weights = {}
        contributing_indicators = {}
        
        for strategy_name, signal in strategy_signals.items():
            allocation = self.strategy_allocations[strategy_name]
            
            # Base weight from allocation and signal confidence
            weight = allocation.current_weight * signal.confidence
            
            # Apply regime bonus if available
            if regime:
                regime_bonus = self._calculate_regime_bonus(strategy_name, regime)
                weight *= regime_bonus
            
            strategy_weights[strategy_name] = weight
            total_weight += weight
            
            # Collect contributing indicators from signal metadata
            if hasattr(signal, 'metadata') and signal.metadata:
                for indicator, value in signal.metadata.items():
                    if isinstance(value, (int, float)):
                        contributing_indicators[f"{strategy_name}_{indicator}"] = value
            
            if signal.action == SignalType.BUY:
                buy_weight += weight
            elif signal.action == SignalType.SELL:
                sell_weight += weight
        
        if total_weight == 0:
            return None
        
        # Normalize weights
        for strategy_name in strategy_weights:
            strategy_weights[strategy_name] /= total_weight
        
        # Determine ensemble action with minimum threshold
        min_consensus_threshold = self.config.get('min_consensus_threshold', 0.6)
        
        if buy_weight > sell_weight and buy_weight / total_weight >= min_consensus_threshold:
            action = SignalType.BUY
            confidence = buy_weight / total_weight
        elif sell_weight > buy_weight and sell_weight / total_weight >= min_consensus_threshold:
            action = SignalType.SELL
            confidence = sell_weight / total_weight
        else:
            return None  # No clear consensus
        
        # Create base signal for ensemble
        base_signal = TradingSignal(
            action=action,
            confidence=confidence,
            strategy="adaptive_ensemble",
            timestamp=datetime.now(),
            price=market_data['close'].iloc[-1],
            reasoning=f"Ensemble of {len(strategy_signals)} strategies with {confidence:.2f} consensus"
        )
        
        return self._create_adaptive_signal(
            base_signal, strategy_weights, pair, market_data, regime, ml_predictions, contributing_indicators
        )
    
    def _create_adaptive_signal(self, base_signal: TradingSignal, 
                               strategy_weights: Dict[str, float],
                               pair: str, market_data: pd.DataFrame,
                               regime: Optional[MarketRegime] = None,
                               ml_predictions: Optional[Dict[str, float]] = None,
                               contributing_indicators: Optional[Dict[str, float]] = None) -> AdaptiveSignal:
        """
        Create an adaptive signal with enhanced metadata.
        
        Args:
            base_signal: Base trading signal
            strategy_weights: Weights of contributing strategies
            pair: Trading pair
            market_data: Market data
            regime: Current market regime
            ml_predictions: ML model predictions
            contributing_indicators: Technical indicators that contributed to the signal
            
        Returns:
            AdaptiveSignal
        """
        # Determine signal strength based on confidence and consensus
        strength = self._calculate_signal_strength(base_signal.confidence, strategy_weights)
        
        # Use provided regime or create default
        if regime is None:
            regime = MarketRegime(
                regime_type=RegimeType.UNCERTAIN,
                confidence=0.5,
                volatility_level=self._calculate_current_volatility(market_data),
                trend_strength=self._calculate_trend_strength(market_data),
                momentum=self._calculate_momentum(market_data),
                detected_at=datetime.now()
            )
        
        # Extract ML confidence
        ml_confidence = 0.5  # Default
        if ml_predictions:
            if 'signal_confidence' in ml_predictions:
                ml_confidence = ml_predictions['signal_confidence']
            elif 'trade_success_probability' in ml_predictions:
                ml_confidence = ml_predictions['trade_success_probability']
        
        # Calculate dynamic parameter adjustments
        parameter_adjustments = self._calculate_parameter_adjustments(
            base_signal, regime, market_data
        )
        
        # Calculate suggested position size and risk parameters
        suggested_position_size = self._calculate_position_size(
            base_signal, regime, ml_confidence
        )
        stop_loss, take_profit = self._calculate_risk_levels(
            base_signal, market_data, regime
        )
        
        return AdaptiveSignal(
            pair=pair,
            signal_type=base_signal.action.value.lower(),
            strength=strength,
            confidence=base_signal.confidence,
            price=base_signal.price,
            timestamp=base_signal.timestamp,
            regime_context=regime,
            ml_confidence=ml_confidence,
            strategy_weights=strategy_weights,
            parameter_adjustments=parameter_adjustments,
            suggested_position_size=suggested_position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            adaptation_metadata={
                'ensemble_size': len(strategy_weights),
                'base_strategy': base_signal.strategy,
                'reasoning': base_signal.reasoning,
                'regime_type': regime.regime_type.value,
                'regime_confidence': regime.confidence,
                'ml_predictions': ml_predictions or {},
                'market_volatility': regime.volatility_level,
                'trend_strength': regime.trend_strength,
                'momentum': regime.momentum
            },
            contributing_indicators=contributing_indicators or {}
        )    

    def update_strategy_weights(self, performance_data: Dict[str, PerformanceMetrics]) -> None:
        """
        Update strategy weights based on performance data.
        
        Args:
            performance_data: Dictionary mapping strategy names to performance metrics
        """
        try:
            for strategy_name, metrics in performance_data.items():
                if strategy_name not in self.strategy_allocations:
                    continue
                
                allocation = self.strategy_allocations[strategy_name]
                
                # Update performance metrics
                allocation.recent_performance = metrics.total_return
                
                # Calculate performance trend
                self.strategy_performance_history[strategy_name].append({
                    'timestamp': datetime.now(),
                    'return': metrics.total_return,
                    'sharpe': metrics.sharpe_ratio,
                    'drawdown': metrics.max_drawdown,
                    'win_rate': metrics.win_rate,
                    'trades_count': metrics.trades_count
                })
                
                # Calculate trend from recent performance
                allocation.performance_trend = self._calculate_performance_trend(strategy_name)
                
                # Update confidence based on consistency
                allocation.confidence_level = self._calculate_strategy_confidence(strategy_name, metrics)
                
                # Calculate new weight
                new_weight = self._calculate_dynamic_weight(strategy_name, metrics)
                allocation.current_weight = new_weight
                
                # Strategy performance tracking and adaptation logic
                self._track_strategy_performance(strategy_name, metrics)
                self._adapt_strategy_allocation(strategy_name, metrics)
                
                allocation.last_updated = datetime.now()
            
            # Rebalance allocations to ensure they sum to 1.0
            self._rebalance_allocations()
            
            logger.info("Updated strategy weights for %d strategies", len(performance_data))
            
        except Exception as e:
            logger.error("Error updating strategy weights: %s", str(e))
    
    def _track_strategy_performance(self, strategy_name: str, metrics: PerformanceMetrics) -> None:
        """
        Track real-time strategy performance and detect degradation.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
        """
        try:
            allocation = self.strategy_allocations[strategy_name]
            
            # Track performance degradation
            performance_degradation = self._detect_performance_degradation(strategy_name, metrics)
            
            if performance_degradation['is_degrading']:
                logger.warning(
                    "Performance degradation detected for strategy %s: %s",
                    strategy_name, performance_degradation['reason']
                )
                
                # Store degradation event
                self._record_performance_event(strategy_name, 'degradation', {
                    'reason': performance_degradation['reason'],
                    'severity': performance_degradation['severity'],
                    'metrics': {
                        'return': metrics.total_return,
                        'sharpe': metrics.sharpe_ratio,
                        'drawdown': metrics.max_drawdown,
                        'win_rate': metrics.win_rate
                    }
                })
                
                # Create performance alert
                self.create_performance_alert(strategy_name, 'degradation', {
                    'reason': performance_degradation['reason'],
                    'severity': performance_degradation['severity'],
                    'metrics': {
                        'return': metrics.total_return,
                        'sharpe': metrics.sharpe_ratio,
                        'drawdown': metrics.max_drawdown,
                        'win_rate': metrics.win_rate
                    }
                })
            
            # Track performance improvement
            performance_improvement = self._detect_performance_improvement(strategy_name, metrics)
            
            if performance_improvement['is_improving']:
                logger.info(
                    "Performance improvement detected for strategy %s: %s",
                    strategy_name, performance_improvement['reason']
                )
                
                # Store improvement event
                self._record_performance_event(strategy_name, 'improvement', {
                    'reason': performance_improvement['reason'],
                    'magnitude': performance_improvement['magnitude'],
                    'metrics': {
                        'return': metrics.total_return,
                        'sharpe': metrics.sharpe_ratio,
                        'drawdown': metrics.max_drawdown,
                        'win_rate': metrics.win_rate
                    }
                })
                
                # Create performance alert
                self.create_performance_alert(strategy_name, 'improvement', {
                    'reason': performance_improvement['reason'],
                    'magnitude': performance_improvement['magnitude'],
                    'metrics': {
                        'return': metrics.total_return,
                        'sharpe': metrics.sharpe_ratio,
                        'drawdown': metrics.max_drawdown,
                        'win_rate': metrics.win_rate
                    }
                })
            
            # Update performance statistics
            self._update_performance_statistics(strategy_name, metrics)
            
        except Exception as e:
            logger.error("Error tracking strategy performance for %s: %s", strategy_name, str(e))
    
    def _adapt_strategy_allocation(self, strategy_name: str, metrics: PerformanceMetrics) -> None:
        """
        Adapt strategy allocation based on recent performance.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
        """
        try:
            allocation = self.strategy_allocations[strategy_name]
            
            # Check if strategy should be disabled
            should_disable = self._should_disable_strategy(strategy_name, metrics)
            if should_disable['should_disable'] and allocation.is_active:
                self._disable_strategy(strategy_name, should_disable['reason'])
            
            # Check if disabled strategy should be re-enabled
            should_enable = self._should_enable_strategy(strategy_name, metrics)
            if should_enable['should_enable'] and not allocation.is_active:
                self._enable_strategy(strategy_name, should_enable['reason'])
            
            # Adjust allocation based on performance
            if allocation.is_active:
                self._adjust_strategy_allocation(strategy_name, metrics)
            
        except Exception as e:
            logger.error("Error adapting strategy allocation for %s: %s", strategy_name, str(e))
    
    def _detect_performance_degradation(self, strategy_name: str, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """
        Detect if strategy performance is degrading.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
            
        Returns:
            Dictionary with degradation information
        """
        history = self.strategy_performance_history[strategy_name]
        
        if len(history) < 5:
            return {'is_degrading': False, 'reason': 'insufficient_data', 'severity': 0.0}
        
        recent_returns = [entry['return'] for entry in list(history)[-5:]]
        older_returns = [entry['return'] for entry in list(history)[-10:-5]] if len(history) >= 10 else []
        
        # Check for consistent decline
        if len(recent_returns) >= 3:
            declining_trend = all(recent_returns[i] <= recent_returns[i-1] for i in range(1, len(recent_returns)))
            if declining_trend and recent_returns[-1] < recent_returns[0] - 0.05:
                return {
                    'is_degrading': True,
                    'reason': 'consistent_decline',
                    'severity': abs(recent_returns[-1] - recent_returns[0])
                }
        
        # Check for significant drop from historical average
        if older_returns:
            historical_avg = np.mean(older_returns)
            recent_avg = np.mean(recent_returns)
            
            if recent_avg < historical_avg - 0.1:  # 10% drop
                return {
                    'is_degrading': True,
                    'reason': 'significant_drop_from_average',
                    'severity': abs(recent_avg - historical_avg)
                }
        
        # Check for poor risk-adjusted returns
        if metrics.sharpe_ratio < -0.5 and metrics.trades_count > 10:
            return {
                'is_degrading': True,
                'reason': f'poor_risk_adjusted_returns_sharpe_{metrics.sharpe_ratio:.3f}',
                'severity': abs(metrics.sharpe_ratio)
            }
        
        # Check for increasing drawdown trend
        recent_drawdowns = [entry.get('drawdown', 0) for entry in list(history)[-5:]]
        if len(recent_drawdowns) >= 3:
            drawdown_trend = np.polyfit(range(len(recent_drawdowns)), recent_drawdowns, 1)[0]
            if drawdown_trend > 0.02:  # Increasing drawdown
                return {
                    'is_degrading': True,
                    'reason': 'increasing_drawdown_trend',
                    'severity': drawdown_trend
                }
        
        # Check for declining win rate
        recent_win_rates = [entry.get('win_rate', 0.5) for entry in list(history)[-5:]]
        if len(recent_win_rates) >= 3:
            avg_recent_win_rate = np.mean(recent_win_rates)
            if avg_recent_win_rate < 0.35 and metrics.trades_count > 15:
                return {
                    'is_degrading': True,
                    'reason': f'declining_win_rate_{avg_recent_win_rate:.3f}',
                    'severity': 0.5 - avg_recent_win_rate
                }
        
        # Check for excessive drawdown combined with poor risk metrics
        if metrics.max_drawdown > 0.15:
            return {
                'is_degrading': True,
                'reason': 'poor_risk_adjusted_returns',
                'severity': abs(metrics.sharpe_ratio) + metrics.max_drawdown
            }
        
        # Check for low win rate with high drawdown
        if metrics.win_rate < 0.3 and metrics.max_drawdown > 0.1:
            return {
                'is_degrading': True,
                'reason': 'low_win_rate_high_drawdown',
                'severity': (1 - metrics.win_rate) + metrics.max_drawdown
            }
        
        return {'is_degrading': False, 'reason': 'performance_stable', 'severity': 0.0}
    
    def _detect_performance_improvement(self, strategy_name: str, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """
        Detect if strategy performance is improving.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
            
        Returns:
            Dictionary with improvement information
        """
        history = self.strategy_performance_history[strategy_name]
        
        if len(history) < 5:
            return {'is_improving': False, 'reason': 'insufficient_data', 'magnitude': 0.0}
        
        recent_returns = [entry['return'] for entry in list(history)[-5:]]
        older_returns = [entry['return'] for entry in list(history)[-10:-5]] if len(history) >= 10 else []
        
        # Check for consistent improvement
        if len(recent_returns) >= 3:
            improving_trend = all(recent_returns[i] >= recent_returns[i-1] for i in range(1, len(recent_returns)))
            if improving_trend and recent_returns[-1] > recent_returns[0] + 0.03:
                return {
                    'is_improving': True,
                    'reason': 'consistent_improvement',
                    'magnitude': recent_returns[-1] - recent_returns[0]
                }
        
        # Check for significant improvement from historical average
        if older_returns:
            historical_avg = np.mean(older_returns)
            recent_avg = np.mean(recent_returns)
            
            if recent_avg > historical_avg + 0.05:  # 5% improvement
                return {
                    'is_improving': True,
                    'reason': 'significant_improvement_from_average',
                    'magnitude': recent_avg - historical_avg
                }
        
        # Check for improved risk-adjusted returns
        recent_sharpe = [entry['sharpe'] for entry in list(history)[-3:]]
        if len(recent_sharpe) >= 3 and np.mean(recent_sharpe) > 1.0:
            return {
                'is_improving': True,
                'reason': 'improved_risk_adjusted_returns',
                'magnitude': np.mean(recent_sharpe)
            }
        
        return {'is_improving': False, 'reason': 'no_significant_improvement', 'magnitude': 0.0}
    
    def _should_disable_strategy(self, strategy_name: str, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """
        Determine if a strategy should be disabled.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
            
        Returns:
            Dictionary with disable decision and reason
        """
        # Check absolute performance threshold
        if metrics.total_return < self.disable_threshold:
            return {
                'should_disable': True,
                'reason': f'return_below_threshold_{self.disable_threshold}'
            }
        
        # Check for consistent poor performance
        history = self.strategy_performance_history[strategy_name]
        if len(history) >= 5:
            recent_returns = [entry['return'] for entry in list(history)[-5:]]
            if all(ret < -0.05 for ret in recent_returns):
                return {
                    'should_disable': True,
                    'reason': 'consistent_losses_over_5_periods'
                }
        
        # Check for excessive drawdown
        if metrics.max_drawdown > 0.25:  # 25% drawdown
            return {
                'should_disable': True,
                'reason': f'excessive_drawdown_{metrics.max_drawdown:.3f}'
            }
        
        # Check for very poor Sharpe ratio
        if metrics.sharpe_ratio < -1.0 and metrics.trades_count > 10:
            return {
                'should_disable': True,
                'reason': f'poor_sharpe_ratio_{metrics.sharpe_ratio:.3f}'
            }
        
        # Check for very low win rate with significant trades
        if metrics.win_rate < 0.2 and metrics.trades_count > 20:
            return {
                'should_disable': True,
                'reason': f'low_win_rate_{metrics.win_rate:.3f}'
            }
        
        return {'should_disable': False, 'reason': 'performance_acceptable'}
    
    def _should_enable_strategy(self, strategy_name: str, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """
        Determine if a disabled strategy should be re-enabled.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
            
        Returns:
            Dictionary with enable decision and reason
        """
        allocation = self.strategy_allocations[strategy_name]
        
        if allocation.is_active:
            return {'should_enable': False, 'reason': 'already_active'}
        
        # Check if performance has improved above re-enable threshold
        if metrics.total_return > self.reenable_threshold:
            return {
                'should_enable': True,
                'reason': f'return_above_reenable_threshold_{self.reenable_threshold}'
            }
        
        # Check for recent improvement trend
        history = self.strategy_performance_history[strategy_name]
        if len(history) >= 3:
            recent_returns = [entry['return'] for entry in list(history)[-3:]]
            if all(recent_returns[i] > recent_returns[i-1] for i in range(1, len(recent_returns))):
                if recent_returns[-1] > 0:  # Latest return is positive
                    return {
                        'should_enable': True,
                        'reason': 'consistent_improvement_trend'
                    }
        
        # Check for improved risk metrics
        if (metrics.sharpe_ratio > 0.5 and 
            metrics.max_drawdown < 0.1 and 
            metrics.win_rate > 0.5):
            return {
                'should_enable': True,
                'reason': 'improved_risk_metrics'
            }
        
        return {'should_enable': False, 'reason': 'insufficient_improvement'}
    
    def _disable_strategy(self, strategy_name: str, reason: str) -> None:
        """
        Disable a strategy and log the event.
        
        Args:
            strategy_name: Name of the strategy to disable
            reason: Reason for disabling
        """
        allocation = self.strategy_allocations[strategy_name]
        allocation.is_active = False
        
        logger.warning("Disabled strategy %s: %s", strategy_name, reason)
        
        # Record the disable event
        self._record_performance_event(strategy_name, 'disabled', {
            'reason': reason,
            'timestamp': datetime.now(),
            'previous_weight': allocation.current_weight,
            'previous_performance': allocation.recent_performance
        })
        
        # Create performance alert
        self.create_performance_alert(strategy_name, 'disabled', {
            'reason': reason,
            'previous_weight': allocation.current_weight,
            'previous_performance': allocation.recent_performance,
            'severity': 'high'
        })
        
        # Rebalance remaining active strategies
        self._rebalance_allocations()
    
    def _enable_strategy(self, strategy_name: str, reason: str) -> None:
        """
        Enable a previously disabled strategy and log the event.
        
        Args:
            strategy_name: Name of the strategy to enable
            reason: Reason for enabling
        """
        allocation = self.strategy_allocations[strategy_name]
        allocation.is_active = True
        
        logger.info("Enabled strategy %s: %s", strategy_name, reason)
        
        # Record the enable event
        self._record_performance_event(strategy_name, 'enabled', {
            'reason': reason,
            'timestamp': datetime.now(),
            'restored_weight': allocation.base_weight,
            'current_performance': allocation.recent_performance
        })
        
        # Create performance alert
        self.create_performance_alert(strategy_name, 'enabled', {
            'reason': reason,
            'restored_weight': allocation.base_weight,
            'current_performance': allocation.recent_performance,
            'severity': 'low'
        })
        
        # Rebalance allocations
        self._rebalance_allocations()
    
    def _adjust_strategy_allocation(self, strategy_name: str, metrics: PerformanceMetrics) -> None:
        """
        Adjust strategy allocation based on recent performance.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
        """
        allocation = self.strategy_allocations[strategy_name]
        old_weight = allocation.current_weight
        
        # Calculate performance-based adjustment
        performance_multiplier = self._calculate_performance_multiplier(strategy_name, metrics)
        
        # Apply gradual adjustment to avoid sudden changes
        adjustment_rate = self.config.get('allocation_adjustment_rate', 0.1)
        target_weight = allocation.base_weight * performance_multiplier
        
        # Gradual adjustment towards target
        weight_diff = target_weight - allocation.current_weight
        adjustment = weight_diff * adjustment_rate
        
        new_weight = allocation.current_weight + adjustment
        new_weight = np.clip(new_weight, allocation.min_allocation, allocation.max_allocation)
        
        allocation.current_weight = new_weight
        
        # Log significant changes
        if abs(new_weight - old_weight) > 0.05:  # 5% change
            logger.info(
                "Adjusted allocation for strategy %s: %.3f -> %.3f (performance: %.3f)",
                strategy_name, old_weight, new_weight, metrics.total_return
            )
            
            # Record the adjustment event
            self._record_performance_event(strategy_name, 'allocation_adjusted', {
                'old_weight': old_weight,
                'new_weight': new_weight,
                'performance_multiplier': performance_multiplier,
                'performance': metrics.total_return,
                'sharpe_ratio': metrics.sharpe_ratio
            })
    
    def _calculate_performance_multiplier(self, strategy_name: str, metrics: PerformanceMetrics) -> float:
        """
        Calculate performance multiplier for allocation adjustment.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
            
        Returns:
            Performance multiplier (0.5 to 2.0)
        """
        multiplier = 1.0
        
        # Return-based adjustment
        if metrics.total_return > 0.15:  # Excellent performance
            multiplier *= 1.5
        elif metrics.total_return > 0.1:  # Good performance
            multiplier *= 1.3
        elif metrics.total_return > 0.05:  # Moderate performance
            multiplier *= 1.1
        elif metrics.total_return < -0.1:  # Poor performance
            multiplier *= 0.6
        elif metrics.total_return < -0.05:  # Below average
            multiplier *= 0.8
        
        # Sharpe ratio adjustment
        if metrics.sharpe_ratio > 2.0:
            multiplier *= 1.2
        elif metrics.sharpe_ratio > 1.5:
            multiplier *= 1.1
        elif metrics.sharpe_ratio < 0:
            multiplier *= 0.7
        elif metrics.sharpe_ratio < 0.5:
            multiplier *= 0.9
        
        # Win rate adjustment
        if metrics.win_rate > 0.7:
            multiplier *= 1.1
        elif metrics.win_rate < 0.4:
            multiplier *= 0.9
        
        # Drawdown penalty
        if metrics.max_drawdown > 0.15:
            multiplier *= 0.8
        elif metrics.max_drawdown > 0.1:
            multiplier *= 0.9
        
        # Trend adjustment
        allocation = self.strategy_allocations[strategy_name]
        if allocation.performance_trend > 0.5:  # Strong positive trend
            multiplier *= 1.1
        elif allocation.performance_trend < -0.5:  # Strong negative trend
            multiplier *= 0.9
        
        # Bound the multiplier
        return np.clip(multiplier, 0.5, 2.0)
    
    def _record_performance_event(self, strategy_name: str, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Record a performance-related event for tracking and analysis.
        
        Args:
            strategy_name: Name of the strategy
            event_type: Type of event (degradation, improvement, disabled, enabled, etc.)
            event_data: Additional event data
        """
        try:
            # Initialize performance events storage if not exists
            if not hasattr(self, 'performance_events'):
                self.performance_events = defaultdict(list)
            
            event = {
                'timestamp': datetime.now(),
                'strategy_name': strategy_name,
                'event_type': event_type,
                'event_data': event_data
            }
            
            self.performance_events[strategy_name].append(event)
            
            # Keep only recent events (last 100 per strategy)
            if len(self.performance_events[strategy_name]) > 100:
                self.performance_events[strategy_name] = self.performance_events[strategy_name][-100:]
            
            logger.debug("Recorded performance event for %s: %s", strategy_name, event_type)
            
        except Exception as e:
            logger.error("Error recording performance event: %s", str(e))
    
    def _update_performance_statistics(self, strategy_name: str, metrics: PerformanceMetrics) -> None:
        """
        Update running performance statistics for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Current performance metrics
        """
        try:
            # Initialize performance statistics if not exists
            if not hasattr(self, 'performance_statistics'):
                self.performance_statistics = defaultdict(dict)
            
            stats = self.performance_statistics[strategy_name]
            
            # Update running averages
            if 'avg_return' not in stats:
                stats['avg_return'] = metrics.total_return
                stats['avg_sharpe'] = metrics.sharpe_ratio
                stats['avg_win_rate'] = metrics.win_rate
                stats['max_drawdown_seen'] = metrics.max_drawdown
                stats['update_count'] = 1
            else:
                count = stats['update_count']
                stats['avg_return'] = (stats['avg_return'] * count + metrics.total_return) / (count + 1)
                stats['avg_sharpe'] = (stats['avg_sharpe'] * count + metrics.sharpe_ratio) / (count + 1)
                stats['avg_win_rate'] = (stats['avg_win_rate'] * count + metrics.win_rate) / (count + 1)
                stats['max_drawdown_seen'] = max(stats['max_drawdown_seen'], metrics.max_drawdown)
                stats['update_count'] = count + 1
            
            # Track best and worst performance
            if 'best_return' not in stats or metrics.total_return > stats['best_return']:
                stats['best_return'] = metrics.total_return
                stats['best_return_date'] = datetime.now()
            
            if 'worst_return' not in stats or metrics.total_return < stats['worst_return']:
                stats['worst_return'] = metrics.total_return
                stats['worst_return_date'] = datetime.now()
            
            stats['last_updated'] = datetime.now()
            
        except Exception as e:
            logger.error("Error updating performance statistics: %s", str(e))
    
    def get_strategy_allocation(self) -> Dict[str, StrategyAllocation]:
        """
        Get current strategy allocation.
        
        Returns:
            Dictionary of strategy allocations
        """
        return self.strategy_allocations.copy()
    
    def _calculate_performance_trend(self, strategy_name: str) -> float:
        """
        Calculate performance trend for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Performance trend (-1.0 to 1.0)
        """
        history = self.strategy_performance_history[strategy_name]
        if len(history) < 3:
            return 0.0
        
        # Calculate trend using linear regression on recent returns
        recent_returns = [entry['return'] for entry in list(history)[-10:]]
        if len(recent_returns) < 2:
            return 0.0
        
        # Simple trend calculation
        x = np.arange(len(recent_returns))
        slope = np.polyfit(x, recent_returns, 1)[0]
        
        # Normalize slope to [-1, 1] range
        return np.clip(slope * 10, -1.0, 1.0)
    
    def _calculate_strategy_confidence(self, strategy_name: str, 
                                     metrics: PerformanceMetrics) -> float:
        """
        Calculate confidence level for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Performance metrics
            
        Returns:
            Confidence level (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence
        
        # Adjust based on Sharpe ratio
        if metrics.sharpe_ratio > 1.0:
            confidence += 0.2
        elif metrics.sharpe_ratio < 0:
            confidence -= 0.2
        
        # Adjust based on win rate
        if metrics.win_rate > 0.6:
            confidence += 0.1
        elif metrics.win_rate < 0.4:
            confidence -= 0.1
        
        # Adjust based on drawdown
        if metrics.max_drawdown < 0.05:
            confidence += 0.1
        elif metrics.max_drawdown > 0.15:
            confidence -= 0.2
        
        # Adjust based on consistency (using performance history)
        history = self.strategy_performance_history[strategy_name]
        if len(history) >= 5:
            returns = [entry['return'] for entry in list(history)[-10:]]
            volatility = np.std(returns) if len(returns) > 1 else 0
            if volatility < 0.1:
                confidence += 0.1
            elif volatility > 0.3:
                confidence -= 0.1
        
        return np.clip(confidence, 0.0, 1.0)
    
    def _calculate_dynamic_weight(self, strategy_name: str, 
                                 metrics: PerformanceMetrics) -> float:
        """
        Calculate dynamic weight for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            metrics: Performance metrics
            
        Returns:
            Dynamic weight
        """
        allocation = self.strategy_allocations[strategy_name]
        base_weight = allocation.base_weight
        
        # Performance adjustment
        performance_multiplier = 1.0
        if metrics.total_return > 0.1:
            performance_multiplier = 1.3
        elif metrics.total_return > 0.05:
            performance_multiplier = 1.1
        elif metrics.total_return < -0.1:
            performance_multiplier = 0.5
        elif metrics.total_return < -0.05:
            performance_multiplier = 0.7
        
        # Sharpe ratio adjustment
        sharpe_multiplier = 1.0
        if metrics.sharpe_ratio > 1.5:
            sharpe_multiplier = 1.2
        elif metrics.sharpe_ratio > 1.0:
            sharpe_multiplier = 1.1
        elif metrics.sharpe_ratio < 0:
            sharpe_multiplier = 0.6
        
        # Trend adjustment
        trend_multiplier = 1.0 + (allocation.performance_trend * 0.2)
        
        # Calculate new weight
        new_weight = base_weight * performance_multiplier * sharpe_multiplier * trend_multiplier
        
        # Apply bounds
        new_weight = np.clip(new_weight, allocation.min_allocation, allocation.max_allocation)
        
        return new_weight
    
    def _rebalance_allocations(self) -> None:
        """Rebalance strategy allocations to ensure they sum to 1.0."""
        active_strategies = {
            name: alloc for name, alloc in self.strategy_allocations.items() 
            if alloc.is_active
        }
        
        if not active_strategies:
            return
        
        # Calculate total weight
        total_weight = sum(alloc.current_weight for alloc in active_strategies.values())
        
        if total_weight == 0:
            # Equal allocation if all weights are zero
            equal_weight = 1.0 / len(active_strategies)
            for alloc in active_strategies.values():
                alloc.current_weight = equal_weight
                alloc.allocation_percentage = equal_weight
        else:
            # Normalize weights
            for alloc in active_strategies.values():
                normalized_weight = alloc.current_weight / total_weight
                alloc.current_weight = normalized_weight
                alloc.allocation_percentage = normalized_weight
    
    def _calculate_regime_bonus(self, strategy_name: str, regime: MarketRegime) -> float:
        """
        Calculate regime preference bonus for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            regime: Current market regime
            
        Returns:
            Regime bonus (0.0 to 1.0)
        """
        allocation = self.strategy_allocations[strategy_name]
        
        # Check if strategy has regime preferences
        if not hasattr(allocation, 'regime_preferences'):
            return 0.5  # Neutral bonus
        
        regime_preferences = getattr(allocation, 'regime_preferences', [])
        
        if regime.regime_type in regime_preferences:
            # Bonus based on regime confidence
            return 0.5 + (regime.confidence * 0.5)
        else:
            # Penalty for non-preferred regimes
            return 0.5 - (regime.confidence * 0.3)
    
    def _get_current_strategy(self, pair: str) -> Optional[str]:
        """
        Get the currently selected strategy for a pair.
        
        Args:
            pair: Trading pair
            
        Returns:
            Current strategy name or None
        """
        # This would typically be stored in state management
        # For now, return the strategy with highest current weight
        if not self.strategy_allocations:
            return None
        
        active_strategies = {
            name: alloc for name, alloc in self.strategy_allocations.items() 
            if alloc.is_active
        }
        
        if not active_strategies:
            return None
        
        return max(active_strategies.keys(), 
                  key=lambda s: active_strategies[s].current_weight)
    
    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of strategy performance.
        
        Returns:
            Dictionary with performance summary
        """
        summary = {
            'total_strategies': len(self.strategies),
            'active_strategies': len([
                alloc for alloc in self.strategy_allocations.values() 
                if alloc.is_active
            ]),
            'strategy_details': {}
        }
        
        for name, allocation in self.strategy_allocations.items():
            summary['strategy_details'][name] = {
                'is_active': allocation.is_active,
                'current_weight': allocation.current_weight,
                'recent_performance': allocation.recent_performance,
                'performance_trend': allocation.performance_trend,
                'confidence_level': allocation.confidence_level,
                'last_updated': allocation.last_updated.isoformat()
            }
        
        return summary
    
    def reset_strategy_weights(self) -> None:
        """Reset all strategy weights to their base values."""
        for allocation in self.strategy_allocations.values():
            allocation.current_weight = allocation.base_weight
            allocation.allocation_percentage = allocation.base_weight
            allocation.is_active = True
        
        self._rebalance_allocations()
        logger.info("Reset all strategy weights to base values")
    
    def _filter_signals_by_regime(self, strategy_signals: Dict[str, TradingSignal], 
                                 regime: MarketRegime) -> Dict[str, TradingSignal]:
        """
        Filter signals based on market regime and strategy preferences.
        
        Args:
            strategy_signals: Dictionary of strategy signals
            regime: Current market regime
            
        Returns:
            Filtered dictionary of signals
        """
        filtered_signals = {}
        
        for strategy_name, signal in strategy_signals.items():
            allocation = self.strategy_allocations[strategy_name]
            
            # Check regime preferences
            regime_preferences = getattr(allocation, 'regime_preferences', [])
            
            # If strategy has no preferences, include it
            if not regime_preferences:
                filtered_signals[strategy_name] = signal
                continue
            
            # Include signal if regime matches preferences or confidence is high enough
            if (regime.regime_type in regime_preferences or 
                regime.confidence < 0.7):  # Low regime confidence = uncertain, include all
                filtered_signals[strategy_name] = signal
            else:
                # Apply penalty for non-preferred regime
                if signal.confidence > 0.7:  # Only include very confident signals
                    filtered_signals[strategy_name] = signal
        
        return filtered_signals
    
    def _adjust_signal_confidence(self, signal: AdaptiveSignal, 
                                 ml_predictions: Optional[Dict[str, float]],
                                 pair: str) -> AdaptiveSignal:
        """
        Adjust signal confidence based on ML predictions.
        
        Args:
            signal: Original adaptive signal
            ml_predictions: ML model predictions
            pair: Trading pair
            
        Returns:
            Signal with adjusted confidence
        """
        if not ml_predictions:
            return signal
        
        # Get ML confidence adjustment
        ml_confidence = ml_predictions.get('signal_confidence', 0.5)
        trade_success_prob = ml_predictions.get('trade_success_probability', 0.5)
        
        # Calculate adjustment factor
        ml_adjustment = (ml_confidence + trade_success_prob) / 2.0
        
        # Apply adjustment with bounds
        original_confidence = signal.confidence
        adjusted_confidence = original_confidence * (0.5 + ml_adjustment * 0.5)
        adjusted_confidence = np.clip(adjusted_confidence, 0.1, 0.95)
        
        # Update signal
        signal.confidence = adjusted_confidence
        signal.ml_confidence = ml_confidence
        
        # Update adaptation metadata
        signal.adaptation_metadata['ml_adjustment'] = ml_adjustment
        signal.adaptation_metadata['original_confidence'] = original_confidence
        signal.adaptation_metadata['confidence_change'] = adjusted_confidence - original_confidence
        
        logger.debug("Adjusted signal confidence for %s: %.3f -> %.3f (ML: %.3f)", 
                    pair, original_confidence, adjusted_confidence, ml_confidence)
        
        return signal
    
    def _amplify_signal_strength(self, signal: AdaptiveSignal, pair: str) -> AdaptiveSignal:
        """
        Amplify or dampen signal strength based on recent performance.
        
        Args:
            signal: Adaptive signal
            pair: Trading pair
            
        Returns:
            Signal with adjusted strength
        """
        # Calculate recent performance score
        performance_score = self._calculate_recent_performance_score(pair)
        
        # Calculate amplification factor
        if performance_score > 0.1:  # Good recent performance
            amplification = 1.0 + min(performance_score, 0.3)  # Max 30% boost
        elif performance_score < -0.1:  # Poor recent performance
            amplification = 1.0 + max(performance_score, -0.4)  # Max 40% reduction
        else:
            amplification = 1.0  # Neutral
        
        # Apply amplification to confidence
        original_confidence = signal.confidence
        amplified_confidence = original_confidence * amplification
        amplified_confidence = np.clip(amplified_confidence, 0.05, 0.95)
        
        # Update signal strength based on new confidence
        signal.confidence = amplified_confidence
        signal.strength = self._calculate_signal_strength(amplified_confidence, signal.strategy_weights)
        
        # Update metadata
        signal.adaptation_metadata['performance_amplification'] = amplification
        signal.adaptation_metadata['performance_score'] = performance_score
        signal.adaptation_metadata['strength_adjustment'] = amplified_confidence - original_confidence
        
        logger.debug("Amplified signal strength for %s: %.3f -> %.3f (factor: %.3f)", 
                    pair, original_confidence, amplified_confidence, amplification)
        
        return signal
    
    def _calculate_signal_strength(self, confidence: float, 
                                  strategy_weights: Dict[str, float]) -> SignalStrength:
        """
        Calculate signal strength based on confidence and strategy consensus.
        
        Args:
            confidence: Signal confidence
            strategy_weights: Strategy weights contributing to signal
            
        Returns:
            SignalStrength enum value
        """
        # Adjust confidence based on strategy consensus
        consensus_factor = len(strategy_weights) / max(len(self.strategies), 1)
        adjusted_confidence = confidence * (0.7 + consensus_factor * 0.3)
        
        if adjusted_confidence >= 0.8:
            return SignalStrength.VERY_STRONG
        elif adjusted_confidence >= 0.65:
            return SignalStrength.STRONG
        elif adjusted_confidence >= 0.45:
            return SignalStrength.MODERATE
        elif adjusted_confidence >= 0.25:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK
    
    def _calculate_current_volatility(self, market_data: pd.DataFrame) -> float:
        """Calculate current market volatility."""
        if len(market_data) < 20:
            return 0.5
        
        returns = market_data['close'].pct_change().dropna()
        if len(returns) < 10:
            return 0.5
        
        volatility = returns.rolling(window=min(20, len(returns))).std().iloc[-1]
        # Normalize to 0-1 range (typical crypto daily volatility 0.01-0.1)
        return np.clip(volatility / 0.05, 0.0, 1.0)
    
    def _calculate_trend_strength(self, market_data: pd.DataFrame) -> float:
        """Calculate trend strength (-1 to 1)."""
        if len(market_data) < 20:
            return 0.0
        
        # Use linear regression slope
        prices = market_data['close'].values[-20:]
        x = np.arange(len(prices))
        slope = np.polyfit(x, prices, 1)[0]
        
        # Normalize slope relative to price
        normalized_slope = slope / prices[-1] * 100  # Percentage change per period
        return np.clip(normalized_slope, -1.0, 1.0)
    
    def _calculate_momentum(self, market_data: pd.DataFrame) -> float:
        """Calculate momentum (-1 to 1)."""
        if len(market_data) < 10:
            return 0.0
        
        # Simple momentum: recent price change
        recent_change = (market_data['close'].iloc[-1] / market_data['close'].iloc[-10] - 1)
        return np.clip(recent_change * 10, -1.0, 1.0)  # Scale to [-1, 1]
    
    def _calculate_parameter_adjustments(self, base_signal: TradingSignal, 
                                       regime: MarketRegime, 
                                       market_data: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate dynamic parameter adjustments based on market conditions.
        
        Args:
            base_signal: Base trading signal
            regime: Market regime
            market_data: Market data
            
        Returns:
            Dictionary of parameter adjustments
        """
        adjustments = {}
        
        # Volatility-based adjustments
        vol_multiplier = 1.0 + regime.volatility_level * 0.5
        adjustments['stop_loss_multiplier'] = vol_multiplier
        adjustments['take_profit_multiplier'] = vol_multiplier
        
        # Trend-based adjustments
        if abs(regime.trend_strength) > 0.5:  # Strong trend
            adjustments['trend_following_bias'] = regime.trend_strength
            adjustments['position_size_multiplier'] = 1.0 + abs(regime.trend_strength) * 0.2
        
        # Regime-specific adjustments
        if regime.regime_type == RegimeType.HIGH_VOLATILITY:
            adjustments['position_size_multiplier'] = 0.7  # Reduce size in high vol
            adjustments['stop_loss_multiplier'] = 1.5  # Wider stops
        elif regime.regime_type == RegimeType.LOW_VOLATILITY:
            adjustments['position_size_multiplier'] = 1.2  # Increase size in low vol
            adjustments['stop_loss_multiplier'] = 0.8  # Tighter stops
        elif regime.regime_type in [RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR]:
            adjustments['take_profit_multiplier'] = 1.3  # Wider targets in trends
        
        return adjustments
    
    def _calculate_position_size(self, base_signal: TradingSignal, 
                               regime: MarketRegime, ml_confidence: float) -> float:
        """
        Calculate suggested position size based on signal strength and conditions.
        
        Args:
            base_signal: Base trading signal
            regime: Market regime
            ml_confidence: ML model confidence
            
        Returns:
            Suggested position size as percentage of capital
        """
        # Base position size from signal confidence
        base_size = base_signal.confidence * 0.1  # Max 10% base
        
        # Adjust for ML confidence
        ml_adjustment = (ml_confidence - 0.5) * 0.1  # ±5% adjustment
        
        # Adjust for regime
        regime_adjustment = 0.0
        if regime.regime_type == RegimeType.HIGH_VOLATILITY:
            regime_adjustment = -0.03  # Reduce by 3%
        elif regime.regime_type == RegimeType.LOW_VOLATILITY:
            regime_adjustment = 0.02  # Increase by 2%
        elif regime.regime_type in [RegimeType.TRENDING_BULL, RegimeType.TRENDING_BEAR]:
            regime_adjustment = 0.01 * regime.confidence  # Small increase for strong trends
        
        # Calculate final size
        final_size = base_size + ml_adjustment + regime_adjustment
        return np.clip(final_size, 0.01, 0.15)  # 1% to 15% of capital
    
    def _calculate_risk_levels(self, base_signal: TradingSignal, 
                              market_data: pd.DataFrame, 
                              regime: MarketRegime) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate dynamic stop-loss and take-profit levels.
        
        Args:
            base_signal: Base trading signal
            market_data: Market data
            regime: Market regime
            
        Returns:
            Tuple of (stop_loss, take_profit) prices
        """
        current_price = base_signal.price
        
        # Calculate ATR for dynamic levels
        if len(market_data) >= 14:
            high_low = market_data['high'] - market_data['low']
            high_close = np.abs(market_data['high'] - market_data['close'].shift())
            low_close = np.abs(market_data['low'] - market_data['close'].shift())
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = true_range.rolling(window=14).mean().iloc[-1]
        else:
            # Fallback to simple volatility
            returns = market_data['close'].pct_change().dropna()
            atr = current_price * returns.std() * 2 if len(returns) > 0 else current_price * 0.02
        
        # Base risk levels
        base_stop_distance = atr * 2
        base_target_distance = atr * 3
        
        # Adjust for regime
        vol_multiplier = 1.0 + regime.volatility_level * 0.5
        base_stop_distance *= vol_multiplier
        base_target_distance *= vol_multiplier
        
        # Adjust for signal confidence
        confidence_multiplier = 0.5 + base_signal.confidence * 0.5
        base_target_distance *= confidence_multiplier
        
        # Calculate levels
        if base_signal.action == SignalType.BUY:
            stop_loss = current_price - base_stop_distance
            take_profit = current_price + base_target_distance
        elif base_signal.action == SignalType.SELL:
            stop_loss = current_price + base_stop_distance
            take_profit = current_price - base_target_distance
        else:
            return None, None
        
        return stop_loss, take_profit
    
    def _calculate_recent_performance_score(self, pair: str) -> float:
        """
        Calculate recent performance score for signal amplification.
        
        Args:
            pair: Trading pair
            
        Returns:
            Performance score (-1.0 to 1.0)
        """
        # This would typically use actual trade results
        # For now, use strategy performance as proxy
        total_score = 0.0
        active_count = 0
        
        for strategy_name, allocation in self.strategy_allocations.items():
            if allocation.is_active:
                total_score += allocation.recent_performance
                active_count += 1
        
        if active_count == 0:
            return 0.0
        
        avg_performance = total_score / active_count
        return np.clip(avg_performance, -1.0, 1.0)
    
    def get_ensemble_signal_history(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Get history of ensemble signals.
        
        Args:
            hours_back: Hours to look back
            
        Returns:
            List of signal history entries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        history = []
        
        for strategy_name, signals in self.recent_signals.items():
            for signal_entry in signals:
                if signal_entry['timestamp'] >= cutoff_time:
                    history.append({
                        'strategy': strategy_name,
                        'timestamp': signal_entry['timestamp'],
                        'pair': signal_entry['pair'],
                        'action': signal_entry['signal'].action.value,
                        'confidence': signal_entry['signal'].confidence,
                        'price': signal_entry['signal'].price
                    })
        
        return sorted(history, key=lambda x: x['timestamp'], reverse=True)
    
    def get_real_time_performance_metrics(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get real-time performance metrics for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dictionary with real-time performance data
        """
        if strategy_name not in self.strategy_allocations:
            return {}
        
        allocation = self.strategy_allocations[strategy_name]
        history = self.strategy_performance_history[strategy_name]
        
        # Calculate real-time metrics
        metrics = {
            'strategy_name': strategy_name,
            'is_active': allocation.is_active,
            'current_weight': allocation.current_weight,
            'base_weight': allocation.base_weight,
            'recent_performance': allocation.recent_performance,
            'performance_trend': allocation.performance_trend,
            'confidence_level': allocation.confidence_level,
            'last_updated': allocation.last_updated.isoformat(),
            'total_signals_generated': len(self.recent_signals.get(strategy_name, [])),
            'performance_history_length': len(history)
        }
        
        # Add performance statistics if available
        if hasattr(self, 'performance_statistics') and strategy_name in self.performance_statistics:
            stats = self.performance_statistics[strategy_name]
            metrics.update({
                'avg_return': stats.get('avg_return', 0.0),
                'avg_sharpe': stats.get('avg_sharpe', 0.0),
                'avg_win_rate': stats.get('avg_win_rate', 0.5),
                'max_drawdown_seen': stats.get('max_drawdown_seen', 0.0),
                'best_return': stats.get('best_return', 0.0),
                'worst_return': stats.get('worst_return', 0.0),
                'update_count': stats.get('update_count', 0)
            })
        
        # Add recent performance events
        if hasattr(self, 'performance_events') and strategy_name in self.performance_events:
            recent_events = list(self.performance_events[strategy_name])[-5:]  # Last 5 events
            metrics['recent_events'] = [
                {
                    'timestamp': event['timestamp'].isoformat(),
                    'event_type': event['event_type'],
                    'event_data': event['event_data']
                }
                for event in recent_events
            ]
        
        return metrics
    
    def monitor_strategy_performance_degradation(self, lookback_hours: int = 24) -> Dict[str, Any]:
        """
        Monitor all strategies for performance degradation.
        
        Args:
            lookback_hours: Hours to look back for performance analysis
            
        Returns:
            Dictionary with degradation analysis for all strategies
        """
        degradation_report = {
            'timestamp': datetime.now().isoformat(),
            'lookback_hours': lookback_hours,
            'strategies_analyzed': 0,
            'degrading_strategies': [],
            'stable_strategies': [],
            'improving_strategies': [],
            'disabled_strategies': []
        }
        
        for strategy_name, allocation in self.strategy_allocations.items():
            degradation_report['strategies_analyzed'] += 1
            
            if not allocation.is_active:
                degradation_report['disabled_strategies'].append({
                    'strategy_name': strategy_name,
                    'disabled_since': allocation.last_updated.isoformat(),
                    'recent_performance': allocation.recent_performance
                })
                continue
            
            # Create mock metrics for analysis (in real implementation, this would come from actual performance data)
            mock_metrics = PerformanceMetrics(
                total_return=allocation.recent_performance,
                annualized_return=allocation.recent_performance * 12,  # Rough annualization
                excess_return=allocation.recent_performance - 0.02,  # Assume 2% risk-free rate
                sharpe_ratio=allocation.recent_performance / 0.15 if allocation.recent_performance != 0 else 0,  # Rough Sharpe
                sortino_ratio=allocation.recent_performance / 0.10 if allocation.recent_performance != 0 else 0,
                calmar_ratio=allocation.recent_performance / 0.05 if allocation.recent_performance != 0 else 0,
                max_drawdown=abs(min(allocation.recent_performance, 0)) * 1.5,
                volatility=0.15,  # Default volatility
                downside_deviation=0.10,
                win_rate=0.5 + allocation.recent_performance,  # Rough correlation
                profit_factor=1.0 + allocation.recent_performance * 2,
                avg_trade_duration=timedelta(hours=4),
                trades_count=max(int(allocation.confidence_level * 50), 1),
                avg_win=0.03,
                avg_loss=-0.02
            )
            
            # Check for degradation
            degradation_info = self._detect_performance_degradation(strategy_name, mock_metrics)
            improvement_info = self._detect_performance_improvement(strategy_name, mock_metrics)
            
            strategy_info = {
                'strategy_name': strategy_name,
                'current_weight': allocation.current_weight,
                'recent_performance': allocation.recent_performance,
                'performance_trend': allocation.performance_trend,
                'confidence_level': allocation.confidence_level
            }
            
            if degradation_info['is_degrading']:
                strategy_info.update({
                    'degradation_reason': degradation_info['reason'],
                    'degradation_severity': degradation_info['severity']
                })
                degradation_report['degrading_strategies'].append(strategy_info)
            elif improvement_info['is_improving']:
                strategy_info.update({
                    'improvement_reason': improvement_info['reason'],
                    'improvement_magnitude': improvement_info['magnitude']
                })
                degradation_report['improving_strategies'].append(strategy_info)
            else:
                degradation_report['stable_strategies'].append(strategy_info)
        
        return degradation_report
    
    def adjust_strategy_allocations_based_on_performance(self, performance_window_hours: int = 24) -> Dict[str, Any]:
        """
        Adjust strategy allocations based on recent performance.
        
        Args:
            performance_window_hours: Hours of performance data to consider
            
        Returns:
            Dictionary with adjustment details
        """
        adjustment_report = {
            'timestamp': datetime.now().isoformat(),
            'performance_window_hours': performance_window_hours,
            'adjustments_made': [],
            'strategies_disabled': [],
            'strategies_enabled': [],
            'total_strategies': len(self.strategy_allocations)
        }
        
        for strategy_name, allocation in self.strategy_allocations.items():
            old_weight = allocation.current_weight
            old_active_status = allocation.is_active
            
            # Create performance metrics for adjustment logic
            mock_metrics = PerformanceMetrics(
                total_return=allocation.recent_performance,
                annualized_return=allocation.recent_performance * 12,
                excess_return=allocation.recent_performance - 0.02,
                sharpe_ratio=allocation.recent_performance / 0.15 if allocation.recent_performance != 0 else 0,
                sortino_ratio=allocation.recent_performance / 0.10 if allocation.recent_performance != 0 else 0,
                calmar_ratio=allocation.recent_performance / 0.05 if allocation.recent_performance != 0 else 0,
                max_drawdown=abs(min(allocation.recent_performance, 0)) * 1.5,
                volatility=0.15,
                downside_deviation=0.10,
                win_rate=0.5 + allocation.recent_performance,
                profit_factor=1.0 + allocation.recent_performance * 2,
                avg_trade_duration=timedelta(hours=4),
                trades_count=max(int(allocation.confidence_level * 50), 1),
                avg_win=0.03,
                avg_loss=-0.02
            )
            
            # Apply adaptation logic
            self._adapt_strategy_allocation(strategy_name, mock_metrics)
            
            # Record changes
            new_weight = allocation.current_weight
            new_active_status = allocation.is_active
            
            if abs(new_weight - old_weight) > 0.01:  # Significant weight change
                adjustment_report['adjustments_made'].append({
                    'strategy_name': strategy_name,
                    'old_weight': old_weight,
                    'new_weight': new_weight,
                    'weight_change': new_weight - old_weight,
                    'performance': allocation.recent_performance,
                    'reason': 'performance_based_adjustment'
                })
            
            if old_active_status and not new_active_status:
                adjustment_report['strategies_disabled'].append({
                    'strategy_name': strategy_name,
                    'reason': 'poor_performance',
                    'final_weight': new_weight,
                    'performance': allocation.recent_performance
                })
            elif not old_active_status and new_active_status:
                adjustment_report['strategies_enabled'].append({
                    'strategy_name': strategy_name,
                    'reason': 'improved_performance',
                    'restored_weight': new_weight,
                    'performance': allocation.recent_performance
                })
        
        # Rebalance after all adjustments
        self._rebalance_allocations()
        
        return adjustment_report
    
    def get_strategy_performance_comparison(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """
        Compare performance across all strategies.
        
        Args:
            timeframe_hours: Hours of data to compare
            
        Returns:
            Dictionary with performance comparison
        """
        comparison = {
            'timestamp': datetime.now().isoformat(),
            'timeframe_hours': timeframe_hours,
            'strategy_rankings': [],
            'performance_summary': {
                'best_performer': None,
                'worst_performer': None,
                'most_consistent': None,
                'most_volatile': None
            }
        }
        
        strategy_performances = []
        
        for strategy_name, allocation in self.strategy_allocations.items():
            history = self.strategy_performance_history[strategy_name]
            
            # Calculate performance metrics from history
            if len(history) > 0:
                recent_returns = [entry['return'] for entry in list(history)[-10:]]
                avg_return = np.mean(recent_returns) if recent_returns else 0.0
                return_volatility = np.std(recent_returns) if len(recent_returns) > 1 else 0.0
                
                recent_sharpe = [entry.get('sharpe', 0) for entry in list(history)[-5:]]
                avg_sharpe = np.mean(recent_sharpe) if recent_sharpe else 0.0
            else:
                avg_return = allocation.recent_performance
                return_volatility = 0.0
                avg_sharpe = 0.0
            
            strategy_perf = {
                'strategy_name': strategy_name,
                'is_active': allocation.is_active,
                'current_weight': allocation.current_weight,
                'avg_return': avg_return,
                'return_volatility': return_volatility,
                'avg_sharpe': avg_sharpe,
                'performance_trend': allocation.performance_trend,
                'confidence_level': allocation.confidence_level,
                'risk_adjusted_score': avg_sharpe if avg_sharpe != 0 else avg_return / max(return_volatility, 0.01)
            }
            
            strategy_performances.append(strategy_perf)
        
        # Sort by risk-adjusted score
        strategy_performances.sort(key=lambda x: x['risk_adjusted_score'], reverse=True)
        comparison['strategy_rankings'] = strategy_performances
        
        # Identify best/worst performers
        if strategy_performances:
            comparison['performance_summary']['best_performer'] = strategy_performances[0]['strategy_name']
            comparison['performance_summary']['worst_performer'] = strategy_performances[-1]['strategy_name']
            
            # Most consistent (lowest volatility among positive performers)
            positive_performers = [s for s in strategy_performances if s['avg_return'] > 0]
            if positive_performers:
                most_consistent = min(positive_performers, key=lambda x: x['return_volatility'])
                comparison['performance_summary']['most_consistent'] = most_consistent['strategy_name']
            
            # Most volatile
            most_volatile = max(strategy_performances, key=lambda x: x['return_volatility'])
            comparison['performance_summary']['most_volatile'] = most_volatile['strategy_name']
        
        return comparison
    
    def create_performance_alert(self, strategy_name: str, alert_type: str, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a performance-related alert.
        
        Args:
            strategy_name: Name of the strategy
            alert_type: Type of alert (degradation, improvement, disabled, enabled)
            alert_data: Additional alert data
            
        Returns:
            Alert dictionary
        """
        alert = {
            'alert_id': f"{strategy_name}_{alert_type}_{int(datetime.now().timestamp())}",
            'timestamp': datetime.now().isoformat(),
            'strategy_name': strategy_name,
            'alert_type': alert_type,
            'severity': alert_data.get('severity', 'medium'),
            'message': self._generate_alert_message(strategy_name, alert_type, alert_data),
            'data': alert_data,
            'requires_action': alert_type in ['degradation', 'disabled'],
            'auto_resolved': False
        }
        
        # Store alert (in real implementation, this would go to an alerting system)
        if not hasattr(self, 'performance_alerts'):
            self.performance_alerts = []
        
        self.performance_alerts.append(alert)
        
        # Keep only recent alerts (last 100)
        if len(self.performance_alerts) > 100:
            self.performance_alerts = self.performance_alerts[-100:]
        
        logger.info("Created performance alert: %s for strategy %s", alert_type, strategy_name)
        
        return alert
    
    def _generate_alert_message(self, strategy_name: str, alert_type: str, alert_data: Dict[str, Any]) -> str:
        """
        Generate a human-readable alert message.
        
        Args:
            strategy_name: Name of the strategy
            alert_type: Type of alert
            alert_data: Alert data
            
        Returns:
            Alert message string
        """
        if alert_type == 'degradation':
            reason = alert_data.get('reason', 'unknown')
            severity = alert_data.get('severity', 0)
            return f"Strategy {strategy_name} showing performance degradation: {reason} (severity: {severity:.3f})"
        
        elif alert_type == 'improvement':
            reason = alert_data.get('reason', 'unknown')
            magnitude = alert_data.get('magnitude', 0)
            return f"Strategy {strategy_name} showing performance improvement: {reason} (magnitude: {magnitude:.3f})"
        
        elif alert_type == 'disabled':
            reason = alert_data.get('reason', 'poor performance')
            return f"Strategy {strategy_name} has been disabled due to {reason}"
        
        elif alert_type == 'enabled':
            reason = alert_data.get('reason', 'improved performance')
            return f"Strategy {strategy_name} has been re-enabled due to {reason}"
        
        else:
            return f"Performance alert for strategy {strategy_name}: {alert_type}"
    
    def get_performance_alerts(self, hours_back: int = 24, strategy_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent performance alerts.
        
        Args:
            hours_back: Hours to look back for alerts
            strategy_name: Optional strategy name to filter alerts
            
        Returns:
            List of alert dictionaries
        """
        if not hasattr(self, 'performance_alerts'):
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        filtered_alerts = []
        for alert in self.performance_alerts:
            alert_time = datetime.fromisoformat(alert['timestamp'])
            
            if alert_time >= cutoff_time:
                if strategy_name is None or alert['strategy_name'] == strategy_name:
                    filtered_alerts.append(alert)
        
        return sorted(filtered_alerts, key=lambda x: x['timestamp'], reverse=True)