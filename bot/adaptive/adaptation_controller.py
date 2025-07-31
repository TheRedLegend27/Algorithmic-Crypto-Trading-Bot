"""
Adaptation Controller for the adaptive trading bot system.

This module implements the core logic for controlling when and how the system
adapts its strategies, parameters, and behavior based on performance feedback
and market conditions.
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from collections import defaultdict, deque

from .interfaces import AdaptationControllerInterface
from .data_models import (
    PerformanceMetrics, AdaptationEvent, MarketRegime, OptimizationResult
)
from .enums import AdaptationType, RegimeType


@dataclass
class AdaptationLimits:
    """Configuration for adaptation limits and thresholds."""
    # Performance thresholds
    min_performance_threshold: float = -0.05  # -5% performance drop triggers adaptation
    min_confidence_threshold: float = 0.6  # Minimum confidence for adaptations
    
    # Frequency limits
    max_adaptations_per_hour: int = 2
    max_adaptations_per_day: int = 10
    min_time_between_adaptations: timedelta = timedelta(minutes=30)
    
    # Change limits
    max_parameter_change_percent: float = 0.2  # Max 20% parameter change per adaptation
    max_strategy_weight_change: float = 0.1  # Max 10% weight change per adaptation
    
    # Validation requirements
    min_data_points_for_adaptation: int = 100
    min_evaluation_period: timedelta = timedelta(hours=2)
    
    # Emergency thresholds
    emergency_drawdown_threshold: float = -0.1  # -10% triggers emergency adaptation
    emergency_performance_threshold: float = -0.15  # -15% performance drop


@dataclass
class AdaptationContext:
    """Context information for adaptation decisions."""
    current_performance: PerformanceMetrics
    historical_performance: List[PerformanceMetrics]
    market_regime: MarketRegime
    recent_adaptations: List[AdaptationEvent]
    system_health: Dict[str, Any]
    
    # Calculated metrics
    performance_trend: float = 0.0  # Positive = improving, negative = declining
    adaptation_frequency: float = 0.0  # Adaptations per hour over last 24h
    confidence_score: float = 0.0  # Overall confidence in system state


class AdaptationController(AdaptationControllerInterface):
    """
    Controls the adaptation behavior of the trading system.
    
    This class implements the core logic for determining when adaptations should
    occur, validating proposed changes, and managing the adaptation lifecycle
    including rollbacks and A/B testing.
    """
    
    def __init__(self, 
                 limits: Optional[AdaptationLimits] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the adaptation controller.
        
        Args:
            limits: Configuration for adaptation limits and thresholds
            logger: Logger instance for recording adaptation events
        """
        self.limits = limits or AdaptationLimits()
        self.logger = logger or logging.getLogger(__name__)
        
        # Adaptation tracking
        self.adaptation_history: List[AdaptationEvent] = []
        self.pending_adaptations: Dict[str, AdaptationEvent] = {}
        self.rollback_data: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.performance_history: deque = deque(maxlen=1000)
        self.adaptation_success_rate: float = 0.0
        
        # Rate limiting
        self.adaptation_timestamps: deque = deque(maxlen=100)
        
        # A/B testing framework
        self.ab_tests: Dict[str, Dict[str, Any]] = {}
        
        # Validation and rollback system
        self.validation_results: Dict[str, Dict[str, Any]] = {}
        self.staged_adaptations: Dict[str, AdaptationEvent] = {}
        self.rollback_history: List[Dict[str, Any]] = []
        
        self.logger.info("AdaptationController initialized with limits: %s", self.limits)
    
    def should_adapt(self, performance_metrics: PerformanceMetrics, strategy_name: str) -> bool:
        """
        Determine if adaptation should be triggered based on performance metrics.
        
        This method implements comprehensive adaptation decision logic that considers:
        - Performance thresholds and degradation patterns
        - Rate limiting to prevent over-optimization
        - Data sufficiency requirements
        - Emergency conditions requiring immediate action
        - Confidence-based decision making
        
        Args:
            performance_metrics: Current performance metrics
            strategy_name: Name of the strategy being evaluated
            
        Returns:
            bool: True if adaptation should be triggered
        """
        try:
            # Check if we're within rate limits
            if not self._check_rate_limits():
                self.logger.debug("Adaptation skipped for %s due to rate limits", strategy_name)
                return False
            
            # Check minimum data requirements
            if performance_metrics.trades_count < self.limits.min_data_points_for_adaptation:
                self.logger.debug("Insufficient data points for adaptation on %s: %d < %d", 
                                strategy_name, performance_metrics.trades_count, 
                                self.limits.min_data_points_for_adaptation)
                return False
            
            # Check minimum evaluation period
            if not self._has_sufficient_evaluation_period(strategy_name):
                self.logger.debug("Insufficient evaluation period for %s", strategy_name)
                return False
            
            # Calculate performance metrics for decision making
            performance_drop = self._calculate_performance_drop(performance_metrics, strategy_name)
            performance_trend = self._calculate_performance_trend(performance_metrics, strategy_name)
            confidence_score = self._calculate_adaptation_confidence(performance_metrics, strategy_name)
            
            # Emergency adaptation conditions (bypass normal checks)
            if self._should_trigger_emergency_adaptation(performance_metrics, performance_drop):
                self.logger.warning("Emergency adaptation triggered for %s: drawdown=%.3f, performance_drop=%.3f",
                                  strategy_name, performance_metrics.max_drawdown, performance_drop)
                return True
            
            # Check confidence threshold for regular adaptations
            if confidence_score < self.limits.min_confidence_threshold:
                self.logger.debug("Adaptation confidence %.3f below threshold %.3f for %s", 
                                confidence_score, self.limits.min_confidence_threshold, strategy_name)
                return False
            
            # Regular adaptation conditions
            adaptation_reasons = []
            
            # 1. Performance threshold breach
            if performance_drop <= self.limits.min_performance_threshold:
                adaptation_reasons.append(f"performance drop {performance_drop:.3f} exceeds threshold {self.limits.min_performance_threshold:.3f}")
            
            # 2. Consistent underperformance
            if self._detect_consistent_underperformance(performance_metrics, strategy_name):
                adaptation_reasons.append("consistent underperformance detected")
            
            # 3. Negative performance trend
            if performance_trend < -0.02:  # 2% negative trend
                adaptation_reasons.append(f"negative performance trend {performance_trend:.3f}")
            
            # 4. Risk-adjusted performance degradation
            if self._detect_risk_adjusted_degradation(performance_metrics, strategy_name):
                adaptation_reasons.append("risk-adjusted performance degradation")
            
            # 5. Regime-specific underperformance
            if self._detect_regime_specific_underperformance(performance_metrics, strategy_name):
                adaptation_reasons.append("regime-specific underperformance")
            
            # Trigger adaptation if any conditions are met
            if adaptation_reasons:
                self.logger.info("Adaptation triggered for %s: %s (confidence: %.3f)", 
                               strategy_name, "; ".join(adaptation_reasons), confidence_score)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error("Error in should_adapt for %s: %s", strategy_name, str(e))
            return False
    
    def get_adaptation_rate(self) -> float:
        """
        Get current adaptation rate (adaptations per hour).
        
        Returns:
            float: Current adaptation rate
        """
        now = datetime.now()
        recent_adaptations = [
            ts for ts in self.adaptation_timestamps 
            if now - ts <= timedelta(hours=24)
        ]
        return len(recent_adaptations) / 24.0
    
    def validate_adaptation(self, proposed_changes: Dict[str, Any]) -> bool:
        """
        Validate proposed adaptation changes against system limits and confidence requirements.
        
        This method implements comprehensive validation including:
        - Parameter change limits
        - Strategy weight constraints
        - Confidence-based approval
        - Conflict detection
        - Risk assessment
        
        Args:
            proposed_changes: Dictionary of proposed changes
            
        Returns:
            bool: True if changes are valid and should be approved
        """
        try:
            validation_results = []
            
            # 1. Validate parameter changes
            if 'parameters' in proposed_changes:
                if not self._validate_parameter_changes(proposed_changes['parameters']):
                    validation_results.append("parameter_changes_invalid")
            
            # 2. Validate strategy weight changes
            if 'strategy_weights' in proposed_changes:
                if not self._validate_strategy_weight_changes(proposed_changes['strategy_weights']):
                    validation_results.append("strategy_weight_changes_invalid")
            
            # 3. Confidence-based validation
            confidence_validation = self._validate_confidence_requirements(proposed_changes)
            if not confidence_validation['approved']:
                validation_results.append(f"confidence_validation_failed: {confidence_validation['reason']}")
            
            # 4. Check for conflicting adaptations
            if self._has_conflicting_adaptations(proposed_changes):
                validation_results.append("conflicting_adaptations")
            
            # 5. Risk assessment validation
            if not self._validate_adaptation_risk(proposed_changes):
                validation_results.append("risk_assessment_failed")
            
            # 6. System state validation
            if not self._validate_system_state_for_adaptation():
                validation_results.append("system_state_invalid")
            
            # Log validation results
            if validation_results:
                self.logger.warning("Adaptation validation failed: %s", "; ".join(validation_results))
                return False
            
            self.logger.info("Adaptation validation passed for changes: %s", 
                           list(proposed_changes.keys()))
            return True
            
        except Exception as e:
            self.logger.error("Error validating adaptation: %s", str(e))
            return False
    
    def _validate_confidence_requirements(self, proposed_changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate confidence requirements for adaptation approval.
        
        Returns:
            Dict with 'approved' boolean and 'reason' string
        """
        try:
            confidence = proposed_changes.get('confidence', 0.0)
            
            # Emergency adaptations have lower confidence requirements - check first
            if proposed_changes.get('emergency', False):
                emergency_threshold = max(0.4, self.limits.min_confidence_threshold - 0.2)
                if confidence >= emergency_threshold:
                    return {'approved': True, 'reason': 'emergency adaptation approved'}
                else:
                    return {
                        'approved': False,
                        'reason': f'emergency adaptation requires confidence {emergency_threshold:.3f}, got {confidence:.3f}'
                    }
            
            # Basic confidence threshold for non-emergency adaptations
            if confidence < self.limits.min_confidence_threshold:
                return {
                    'approved': False,
                    'reason': f"confidence {confidence:.3f} below threshold {self.limits.min_confidence_threshold:.3f}"
                }
            
            # Enhanced confidence requirements based on change magnitude
            change_magnitude = self._calculate_change_magnitude(proposed_changes)
            
            # Higher confidence required for larger changes
            if change_magnitude > 0.1:  # 10% change
                required_confidence = min(0.9, self.limits.min_confidence_threshold + 0.2)
                if confidence < required_confidence:
                    return {
                        'approved': False,
                        'reason': f"large change (magnitude {change_magnitude:.3f}) requires confidence {required_confidence:.3f}, got {confidence:.3f}"
                    }
            
            # Check adaptation history for confidence adjustment
            recent_failures = self._get_recent_adaptation_failures()
            if recent_failures > 2:  # More than 2 recent failures
                required_confidence = min(0.95, self.limits.min_confidence_threshold + 0.3)
                if confidence < required_confidence:
                    return {
                        'approved': False,
                        'reason': f"recent failures ({recent_failures}) require higher confidence {required_confidence:.3f}"
                    }
            
            return {'approved': True, 'reason': 'confidence requirements met'}
            
        except Exception as e:
            self.logger.error("Error validating confidence requirements: %s", str(e))
            return {'approved': False, 'reason': f'validation error: {str(e)}'}
    
    def _calculate_change_magnitude(self, proposed_changes: Dict[str, Any]) -> float:
        """Calculate the overall magnitude of proposed changes."""
        try:
            total_magnitude = 0.0
            change_count = 0
            
            # Parameter changes
            if 'parameters' in proposed_changes:
                for param, change in proposed_changes['parameters'].items():
                    if isinstance(change, (int, float)):
                        total_magnitude += abs(change)
                        change_count += 1
            
            # Strategy weight changes
            if 'strategy_weights' in proposed_changes:
                for strategy, change in proposed_changes['strategy_weights'].items():
                    total_magnitude += abs(change)
                    change_count += 1
            
            return total_magnitude / max(change_count, 1)
            
        except Exception as e:
            self.logger.error("Error calculating change magnitude: %s", str(e))
            return 0.0
    
    def _get_recent_adaptation_failures(self) -> int:
        """Get count of recent adaptation failures."""
        try:
            recent_adaptations = [
                event for event in self.adaptation_history
                if event.timestamp >= datetime.now() - timedelta(days=3)
                and event.success is not None
            ]
            
            return sum(1 for event in recent_adaptations if not event.success)
            
        except Exception as e:
            self.logger.error("Error getting recent adaptation failures: %s", str(e))
            return 0
    
    def _validate_adaptation_risk(self, proposed_changes: Dict[str, Any]) -> bool:
        """Validate that the proposed adaptation doesn't introduce excessive risk."""
        try:
            # Check if changes are within acceptable risk bounds
            risk_factors = []
            
            # Parameter risk assessment
            if 'parameters' in proposed_changes:
                for param, change in proposed_changes['parameters'].items():
                    if isinstance(change, (int, float)):
                        # Risk increases with larger parameter changes
                        risk_score = min(abs(change) / self.limits.max_parameter_change_percent, 1.0)
                        risk_factors.append(risk_score)
            
            # Strategy weight risk assessment
            if 'strategy_weights' in proposed_changes:
                total_weight_change = sum(abs(change) for change in proposed_changes['strategy_weights'].values())
                weight_risk = min(total_weight_change / 0.5, 1.0)  # Risk increases with total weight changes
                risk_factors.append(weight_risk)
            
            # Calculate overall risk score
            overall_risk = sum(risk_factors) / len(risk_factors) if risk_factors else 0.0
            
            # Risk threshold (0.0 = no risk, 1.0 = maximum risk)
            risk_threshold = 0.7
            
            if overall_risk > risk_threshold:
                self.logger.warning("Adaptation risk %.3f exceeds threshold %.3f", 
                                  overall_risk, risk_threshold)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error("Error validating adaptation risk: %s", str(e))
            return False
    
    def _validate_system_state_for_adaptation(self) -> bool:
        """Validate that the system is in a suitable state for adaptation."""
        try:
            # Check system health
            system_health = self._get_system_health_score()
            if system_health < 0.5:
                self.logger.warning("System health %.3f too low for adaptation", system_health)
                return False
            
            # Check if there are too many pending adaptations
            if len(self.pending_adaptations) >= 5:
                self.logger.warning("Too many pending adaptations (%d) for new adaptation", 
                                  len(self.pending_adaptations))
                return False
            
            # Check recent adaptation frequency
            recent_rate = self.get_adaptation_rate()
            if recent_rate > self.limits.max_adaptations_per_hour * 0.8:  # 80% of max rate
                self.logger.warning("Adaptation rate %.3f approaching limit", recent_rate)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error("Error validating system state: %s", str(e))
            return False
    
    def execute_adaptation(self, adaptation_event: AdaptationEvent) -> bool:
        """
        Execute an adaptation event.
        
        Args:
            adaptation_event: The adaptation event to execute
            
        Returns:
            bool: True if adaptation was executed successfully
        """
        try:
            # Store rollback data before making changes
            self._store_rollback_data(adaptation_event)
            
            # Record the adaptation
            self.adaptation_history.append(adaptation_event)
            self.adaptation_timestamps.append(adaptation_event.timestamp)
            self.pending_adaptations[adaptation_event.event_id] = adaptation_event
            
            self.logger.info("Executed adaptation %s: %s", 
                           adaptation_event.event_id, adaptation_event.trigger_reason)
            
            # Schedule evaluation
            self._schedule_adaptation_evaluation(adaptation_event)
            
            return True
            
        except Exception as e:
            self.logger.error("Error executing adaptation %s: %s", 
                            adaptation_event.event_id, str(e))
            return False
    
    def rollback_adaptation(self, event_id: str) -> bool:
        """
        Rollback a previous adaptation.
        
        Args:
            event_id: ID of the adaptation event to rollback
            
        Returns:
            bool: True if rollback was successful
        """
        try:
            if event_id not in self.rollback_data:
                self.logger.error("No rollback data found for adaptation %s", event_id)
                return False
            
            # Find the adaptation event
            adaptation_event = None
            for event in self.adaptation_history:
                if event.event_id == event_id:
                    adaptation_event = event
                    break
            
            if not adaptation_event:
                self.logger.error("Adaptation event %s not found in history", event_id)
                return False
            
            # Restore previous state
            rollback_data = self.rollback_data[event_id]
            
            # Create rollback event
            rollback_event = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=AdaptationType.EMERGENCY_ADAPTATION,
                trigger_reason=f"Rollback of adaptation {event_id}",
                changes_made=rollback_data,
                expected_impact=0.0,
                rollback_available=False
            )
            
            # Execute rollback
            self.adaptation_history.append(rollback_event)
            
            # Mark original adaptation as rolled back
            adaptation_event.success = False
            adaptation_event.rollback_available = False
            
            # Remove from pending adaptations
            if event_id in self.pending_adaptations:
                del self.pending_adaptations[event_id]
            
            self.logger.info("Successfully rolled back adaptation %s", event_id)
            return True
            
        except Exception as e:
            self.logger.error("Error rolling back adaptation %s: %s", event_id, str(e))
            return False
    
    def get_adaptation_history(self, hours_back: int = 24) -> List[AdaptationEvent]:
        """
        Get recent adaptation history.
        
        Args:
            hours_back: Number of hours to look back
            
        Returns:
            List of recent adaptation events
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        return [
            event for event in self.adaptation_history 
            if event.timestamp >= cutoff_time
        ]
    
    def set_adaptation_limits(self, limits: Dict[str, Any]) -> None:
        """
        Set limits on adaptation behavior.
        
        Args:
            limits: Dictionary of limit configurations
        """
        try:
            for key, value in limits.items():
                if hasattr(self.limits, key):
                    setattr(self.limits, key, value)
                    self.logger.info("Updated adaptation limit %s to %s", key, value)
                else:
                    self.logger.warning("Unknown adaptation limit: %s", key)
                    
        except Exception as e:
            self.logger.error("Error setting adaptation limits: %s", str(e))
    
    def evaluate_pending_adaptations(self) -> None:
        """Evaluate pending adaptations and determine their success."""
        current_time = datetime.now()
        
        for event_id, adaptation_event in list(self.pending_adaptations.items()):
            if adaptation_event.is_due_for_evaluation():
                try:
                    # This would be implemented to measure actual performance impact
                    # For now, we'll use a placeholder
                    actual_impact = self._measure_adaptation_impact(adaptation_event)
                    adaptation_event.actual_impact = actual_impact
                    
                    # Determine success
                    adaptation_event.success = actual_impact >= adaptation_event.auto_rollback_threshold
                    
                    if adaptation_event.should_rollback():
                        self.logger.warning("Auto-rolling back adaptation %s due to poor performance: %.3f",
                                          event_id, actual_impact)
                        self.rollback_adaptation(event_id)
                    else:
                        self.logger.info("Adaptation %s evaluation complete: success=%s, impact=%.3f",
                                       event_id, adaptation_event.success, actual_impact)
                        del self.pending_adaptations[event_id]
                        
                except Exception as e:
                    self.logger.error("Error evaluating adaptation %s: %s", event_id, str(e))
    
    # Private helper methods
    
    def _check_rate_limits(self) -> bool:
        """Check if adaptation is within rate limits."""
        now = datetime.now()
        
        # Check hourly limit
        recent_hour = [ts for ts in self.adaptation_timestamps if now - ts <= timedelta(hours=1)]
        if len(recent_hour) >= self.limits.max_adaptations_per_hour:
            return False
        
        # Check daily limit
        recent_day = [ts for ts in self.adaptation_timestamps if now - ts <= timedelta(days=1)]
        if len(recent_day) >= self.limits.max_adaptations_per_day:
            return False
        
        # Check minimum time between adaptations
        if self.adaptation_timestamps and now - self.adaptation_timestamps[-1] < self.limits.min_time_between_adaptations:
            return False
        
        return True
    
    def _has_sufficient_evaluation_period(self, strategy_name: str) -> bool:
        """Check if sufficient time has passed since last adaptation for evaluation."""
        if not self.adaptation_history:
            return True
        
        # Find the most recent adaptation for this strategy
        recent_adaptations = [
            event for event in self.adaptation_history
            if strategy_name in event.affected_strategies or not event.affected_strategies
        ]
        
        if not recent_adaptations:
            return True
        
        last_adaptation = max(recent_adaptations, key=lambda x: x.timestamp)
        time_since_last = datetime.now() - last_adaptation.timestamp
        
        return time_since_last >= self.limits.min_evaluation_period
    
    def _calculate_performance_drop(self, current_metrics: PerformanceMetrics, strategy_name: str) -> float:
        """
        Calculate performance drop compared to historical average.
        
        This method compares current performance against historical performance
        to determine if there's been a significant degradation.
        """
        try:
            # Get historical performance data for comparison
            historical_performance = self._get_historical_performance(strategy_name)
            
            if not historical_performance:
                # No historical data - use current return as baseline
                return current_metrics.total_return if current_metrics.total_return < 0 else 0.0
            
            # Calculate historical average return
            historical_returns = [perf.total_return for perf in historical_performance]
            historical_avg = sum(historical_returns) / len(historical_returns)
            
            # Calculate performance drop
            performance_drop = current_metrics.total_return - historical_avg
            
            return performance_drop
            
        except Exception as e:
            self.logger.error("Error calculating performance drop for %s: %s", strategy_name, str(e))
            # Fallback to simple calculation
            return current_metrics.total_return if current_metrics.total_return < 0 else 0.0
    
    def _calculate_performance_trend(self, current_metrics: PerformanceMetrics, strategy_name: str) -> float:
        """
        Calculate the performance trend over recent periods.
        
        Returns:
            float: Positive values indicate improving performance, negative indicate declining
        """
        try:
            historical_performance = self._get_historical_performance(strategy_name, periods=5)
            
            if len(historical_performance) < 2:
                return 0.0
            
            # Calculate trend using linear regression on recent returns
            returns = [perf.total_return for perf in historical_performance]
            returns.append(current_metrics.total_return)
            
            # Simple trend calculation (slope of recent performance)
            n = len(returns)
            if n < 2:
                return 0.0
            
            x_values = list(range(n))
            x_mean = sum(x_values) / n
            y_mean = sum(returns) / n
            
            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, returns))
            denominator = sum((x - x_mean) ** 2 for x in x_values)
            
            if denominator == 0:
                return 0.0
            
            trend = numerator / denominator
            return trend
            
        except Exception as e:
            self.logger.error("Error calculating performance trend for %s: %s", strategy_name, str(e))
            return 0.0
    
    def _calculate_adaptation_confidence(self, current_metrics: PerformanceMetrics, strategy_name: str) -> float:
        """
        Calculate confidence score for making an adaptation decision.
        
        Confidence is based on:
        - Data sufficiency (more trades = higher confidence)
        - Performance consistency
        - Time since last adaptation
        - System stability
        """
        try:
            confidence_factors = []
            
            # Data sufficiency factor (0.0 to 1.0)
            data_factor = min(current_metrics.trades_count / (self.limits.min_data_points_for_adaptation * 2), 1.0)
            confidence_factors.append(('data_sufficiency', data_factor, 0.3))
            
            # Performance consistency factor
            historical_performance = self._get_historical_performance(strategy_name, periods=3)
            if historical_performance:
                returns = [perf.total_return for perf in historical_performance]
                returns.append(current_metrics.total_return)
                
                # Lower variance = higher confidence
                variance = np.var(returns) if len(returns) > 1 else 0.0
                consistency_factor = max(0.0, 1.0 - (variance * 10))  # Scale variance
                confidence_factors.append(('consistency', consistency_factor, 0.2))
            
            # Time stability factor (more time since last adaptation = higher confidence)
            time_factor = 1.0
            if self.adaptation_history:
                recent_adaptations = [
                    event for event in self.adaptation_history
                    if strategy_name in event.affected_strategies or not event.affected_strategies
                ]
                if recent_adaptations:
                    last_adaptation = max(recent_adaptations, key=lambda x: x.timestamp)
                    hours_since = (datetime.now() - last_adaptation.timestamp).total_seconds() / 3600
                    time_factor = min(hours_since / 24.0, 1.0)  # Full confidence after 24 hours
            
            confidence_factors.append(('time_stability', time_factor, 0.2))
            
            # System health factor
            system_health = self._get_system_health_score()
            confidence_factors.append(('system_health', system_health, 0.2))
            
            # Recent adaptation success rate
            success_rate = self._get_recent_adaptation_success_rate()
            confidence_factors.append(('adaptation_success', success_rate, 0.1))
            
            # Calculate weighted confidence score
            total_confidence = sum(factor * weight for _, factor, weight in confidence_factors)
            
            self.logger.debug("Adaptation confidence for %s: %.3f (factors: %s)", 
                            strategy_name, total_confidence, 
                            {name: f"{factor:.3f}" for name, factor, _ in confidence_factors})
            
            return total_confidence
            
        except Exception as e:
            self.logger.error("Error calculating adaptation confidence for %s: %s", strategy_name, str(e))
            return 0.5  # Default moderate confidence
    
    def _should_trigger_emergency_adaptation(self, metrics: PerformanceMetrics, performance_drop: float) -> bool:
        """Determine if emergency adaptation should be triggered."""
        # Emergency conditions are more restrictive - require multiple severe indicators
        severe_conditions = []
        
        if metrics.max_drawdown <= self.limits.emergency_drawdown_threshold:
            severe_conditions.append("severe_drawdown")
        
        if performance_drop <= self.limits.emergency_performance_threshold:
            severe_conditions.append("severe_performance_drop")
        
        if metrics.total_return <= -0.2:  # 20% total loss
            severe_conditions.append("severe_total_loss")
        
        if metrics.win_rate <= 0.2 and metrics.trades_count >= 50:  # Very low win rate with sufficient data
            severe_conditions.append("severe_win_rate")
        
        # Require at least 2 severe conditions for emergency adaptation
        return len(severe_conditions) >= 2
    
    def _detect_consistent_underperformance(self, metrics: PerformanceMetrics, strategy_name: str) -> bool:
        """
        Detect if a strategy is consistently underperforming across multiple metrics.
        
        Checks multiple performance indicators to identify persistent issues.
        """
        try:
            underperformance_indicators = []
            
            # Low win rate with sufficient trades
            if metrics.win_rate < 0.4 and metrics.trades_count >= 50:
                underperformance_indicators.append("low_win_rate")
            
            # Poor profit factor
            if metrics.profit_factor < 1.0:
                underperformance_indicators.append("poor_profit_factor")
            
            # Negative Sharpe ratio
            if metrics.sharpe_ratio < 0:
                underperformance_indicators.append("negative_sharpe")
            
            # High drawdown relative to returns
            if metrics.max_drawdown < 0 and abs(metrics.max_drawdown) > abs(metrics.total_return):
                underperformance_indicators.append("high_relative_drawdown")
            
            # Check historical comparison
            historical_performance = self._get_historical_performance(strategy_name, periods=3)
            if historical_performance:
                historical_avg_return = sum(perf.total_return for perf in historical_performance) / len(historical_performance)
                if metrics.total_return < historical_avg_return * 0.7:  # 30% worse than historical average
                    underperformance_indicators.append("historical_underperformance")
            
            # Require at least 2 indicators for consistent underperformance
            is_underperforming = len(underperformance_indicators) >= 2
            
            if is_underperforming:
                self.logger.debug("Consistent underperformance detected for %s: %s", 
                                strategy_name, underperformance_indicators)
            
            return is_underperforming
            
        except Exception as e:
            self.logger.error("Error detecting consistent underperformance for %s: %s", strategy_name, str(e))
            return False
    
    def _detect_risk_adjusted_degradation(self, metrics: PerformanceMetrics, strategy_name: str) -> bool:
        """Detect degradation in risk-adjusted performance metrics."""
        try:
            degradation_indicators = []
            
            # Only trigger if multiple risk metrics are poor AND returns are negative
            if metrics.total_return >= 0:
                return False  # Don't trigger for positive returns
            
            # Sharpe ratio degradation (more conservative threshold)
            if metrics.sharpe_ratio < -0.5:  # Only very poor Sharpe ratios
                degradation_indicators.append("low_sharpe_ratio")
            
            # Sortino ratio degradation (more conservative)
            if metrics.sortino_ratio < -0.3:  # Only very poor Sortino ratios
                degradation_indicators.append("low_sortino_ratio")
            
            # Calmar ratio degradation (if available)
            if hasattr(metrics, 'calmar_ratio') and metrics.calmar_ratio < -0.5:
                degradation_indicators.append("low_calmar_ratio")
            
            # Compare with historical risk-adjusted metrics (only if we have data)
            historical_performance = self._get_historical_performance(strategy_name, periods=3)
            if historical_performance and len(historical_performance) >= 2:
                historical_sharpe = sum(perf.sharpe_ratio for perf in historical_performance) / len(historical_performance)
                if historical_sharpe > 0 and metrics.sharpe_ratio < historical_sharpe * 0.5:  # 50% degradation from positive baseline
                    degradation_indicators.append("sharpe_degradation")
            
            # Require multiple indicators for degradation
            return len(degradation_indicators) >= 2
            
        except Exception as e:
            self.logger.error("Error detecting risk-adjusted degradation for %s: %s", strategy_name, str(e))
            return False
    
    def _detect_regime_specific_underperformance(self, metrics: PerformanceMetrics, strategy_name: str) -> bool:
        """Detect underperformance in specific market regimes."""
        try:
            if not hasattr(metrics, 'regime_performance') or not metrics.regime_performance:
                return False
            
            underperforming_regimes = []
            
            for regime, performance in metrics.regime_performance.items():
                if performance < -0.05:  # 5% loss in this regime
                    underperforming_regimes.append(regime)
            
            # If underperforming in multiple regimes, trigger adaptation
            return len(underperforming_regimes) >= 2
            
        except Exception as e:
            self.logger.error("Error detecting regime-specific underperformance for %s: %s", strategy_name, str(e))
            return False
    
    def _get_historical_performance(self, strategy_name: str, periods: int = 10) -> List[PerformanceMetrics]:
        """Get historical performance data for a strategy."""
        # This is a placeholder implementation
        # In a real system, this would query a database or cache
        return list(self.performance_history)[-periods:] if self.performance_history else []
    
    def _get_system_health_score(self) -> float:
        """Get overall system health score (0.0 to 1.0)."""
        try:
            health_factors = []
            
            # Recent adaptation success rate
            success_rate = self._get_recent_adaptation_success_rate()
            health_factors.append(success_rate)
            
            # System stability (no recent errors)
            stability_score = 1.0  # Placeholder - would check error logs
            health_factors.append(stability_score)
            
            # Data quality score
            data_quality = 1.0  # Placeholder - would check data freshness/quality
            health_factors.append(data_quality)
            
            return sum(health_factors) / len(health_factors) if health_factors else 0.5
            
        except Exception as e:
            self.logger.error("Error calculating system health score: %s", str(e))
            return 0.5
    
    def _get_recent_adaptation_success_rate(self) -> float:
        """Calculate success rate of recent adaptations."""
        try:
            recent_adaptations = [
                event for event in self.adaptation_history
                if event.timestamp >= datetime.now() - timedelta(days=7)
                and event.success is not None
            ]
            
            if not recent_adaptations:
                return 0.8  # Default optimistic rate when no data
            
            successful = sum(1 for event in recent_adaptations if event.success)
            return successful / len(recent_adaptations)
            
        except Exception as e:
            self.logger.error("Error calculating recent adaptation success rate: %s", str(e))
            return 0.5
    
    def _validate_parameter_changes(self, parameter_changes: Dict[str, Any]) -> bool:
        """Validate that parameter changes are within acceptable limits."""
        for param, change in parameter_changes.items():
            if isinstance(change, (int, float)):
                if abs(change) > self.limits.max_parameter_change_percent:
                    self.logger.warning("Parameter change for %s (%.3f) exceeds limit %.3f",
                                      param, change, self.limits.max_parameter_change_percent)
                    return False
        return True
    
    def _validate_strategy_weight_changes(self, weight_changes: Dict[str, float]) -> bool:
        """Validate that strategy weight changes are within acceptable limits."""
        for strategy, change in weight_changes.items():
            if abs(change) > self.limits.max_strategy_weight_change:
                self.logger.warning("Strategy weight change for %s (%.3f) exceeds limit %.3f",
                                  strategy, change, self.limits.max_strategy_weight_change)
                return False
        return True
    
    def _has_conflicting_adaptations(self, proposed_changes: Dict[str, Any]) -> bool:
        """Check if proposed changes conflict with pending adaptations."""
        # Simplified implementation - check for overlapping strategy changes
        for adaptation_event in self.pending_adaptations.values():
            if 'strategy_weights' in proposed_changes and 'strategy_weights' in adaptation_event.changes_made:
                # Check for overlapping strategies
                proposed_strategies = set(proposed_changes['strategy_weights'].keys())
                pending_strategies = set(adaptation_event.changes_made['strategy_weights'].keys())
                if proposed_strategies & pending_strategies:
                    self.logger.warning("Conflicting adaptation detected with pending adaptation %s",
                                      adaptation_event.event_id)
                    return True
        return False
    
    def _store_rollback_data(self, adaptation_event: AdaptationEvent) -> None:
        """Store data needed for potential rollback."""
        # This would store the current system state before making changes
        # For now, we'll store a placeholder
        self.rollback_data[adaptation_event.event_id] = {
            'timestamp': datetime.now(),
            'changes_to_revert': adaptation_event.changes_made
        }
    
    def _schedule_adaptation_evaluation(self, adaptation_event: AdaptationEvent) -> None:
        """Schedule evaluation of adaptation impact."""
        # In a real implementation, this might schedule a background task
        # For now, we'll just log the scheduling
        evaluation_time = adaptation_event.timestamp + adaptation_event.evaluation_period
        self.logger.info("Scheduled evaluation for adaptation %s at %s",
                        adaptation_event.event_id, evaluation_time)
    
    def _measure_adaptation_impact(self, adaptation_event: AdaptationEvent) -> float:
        """Measure the actual impact of an adaptation."""
        # This is a placeholder implementation
        # In practice, you'd compare performance before and after the adaptation
        return np.random.normal(0.02, 0.05)  # Simulate small positive impact with noise