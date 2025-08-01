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
        
        # Enhanced validation system
        self.validation_queue: List[AdaptationEvent] = []
        self.validation_in_progress: Dict[str, Dict[str, Any]] = {}
        
        # A/B testing configuration
        self.ab_test_config = {
            'default_test_duration': timedelta(hours=12),
            'min_sample_size': 50,
            'significance_threshold': 0.05,
            'control_group_ratio': 0.5,
            'max_concurrent_tests': 3
        }
        
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
    
    # Enhanced validation and A/B testing methods
    
    def validate_adaptation_impact(self, adaptation_event: AdaptationEvent) -> Dict[str, Any]:
        """
        Validate adaptation impact before full deployment.
        
        This method implements comprehensive pre-deployment validation including:
        - Risk assessment of proposed changes
        - Performance simulation
        - Resource impact analysis
        - Conflict detection with existing adaptations
        
        Args:
            adaptation_event: The adaptation event to validate
            
        Returns:
            Dict containing validation results and recommendations
        """
        try:
            validation_id = f"validation_{adaptation_event.event_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            validation_result = {
                'validation_id': validation_id,
                'adaptation_id': adaptation_event.event_id,
                'timestamp': datetime.now(),
                'status': 'in_progress',
                'checks': {},
                'overall_score': 0.0,
                'recommendation': 'pending',
                'risk_level': 'unknown',
                'estimated_impact': 0.0
            }
            
            # 1. Risk Assessment
            risk_assessment = self._assess_adaptation_risk(adaptation_event)
            validation_result['checks']['risk_assessment'] = risk_assessment
            
            # 2. Performance Simulation
            performance_simulation = self._simulate_adaptation_performance(adaptation_event)
            validation_result['checks']['performance_simulation'] = performance_simulation
            
            # 3. Resource Impact Analysis
            resource_impact = self._analyze_resource_impact(adaptation_event)
            validation_result['checks']['resource_impact'] = resource_impact
            
            # 4. Conflict Detection
            conflict_check = self._check_adaptation_conflicts(adaptation_event)
            validation_result['checks']['conflict_detection'] = conflict_check
            
            # 5. Market Condition Suitability
            market_suitability = self._assess_market_condition_suitability(adaptation_event)
            validation_result['checks']['market_suitability'] = market_suitability
            
            # 6. Historical Pattern Analysis
            historical_analysis = self._analyze_historical_patterns(adaptation_event)
            validation_result['checks']['historical_analysis'] = historical_analysis
            
            # Calculate overall validation score
            validation_result['overall_score'] = self._calculate_validation_score(validation_result['checks'])
            validation_result['risk_level'] = self._determine_risk_level(validation_result['overall_score'])
            validation_result['estimated_impact'] = performance_simulation.get('estimated_impact', 0.0)
            
            # Make recommendation
            validation_result['recommendation'] = self._make_validation_recommendation(validation_result)
            validation_result['status'] = 'completed'
            
            # Store validation result
            self.validation_results[validation_id] = validation_result
            
            self.logger.info("Adaptation validation completed for %s: score=%.3f, recommendation=%s",
                           adaptation_event.event_id, validation_result['overall_score'], 
                           validation_result['recommendation'])
            
            return validation_result
            
        except Exception as e:
            self.logger.error("Error validating adaptation impact for %s: %s", 
                            adaptation_event.event_id, str(e))
            return {
                'validation_id': f"error_{adaptation_event.event_id}",
                'status': 'error',
                'error': str(e),
                'recommendation': 'reject'
            }
    
    def create_ab_test(self, adaptation_event: AdaptationEvent, test_config: Optional[Dict[str, Any]] = None) -> str:
        """
        Create an A/B test for gradual adaptation rollout.
        
        Args:
            adaptation_event: The adaptation to test
            test_config: Optional configuration for the test
            
        Returns:
            str: A/B test ID
        """
        try:
            # Check if we can create a new A/B test
            if len(self.ab_tests) >= self.ab_test_config['max_concurrent_tests']:
                raise ValueError(f"Maximum concurrent A/B tests ({self.ab_test_config['max_concurrent_tests']}) reached")
            
            test_id = f"ab_test_{adaptation_event.event_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Merge default config with provided config
            config = self.ab_test_config.copy()
            if test_config:
                config.update(test_config)
            
            ab_test = {
                'test_id': test_id,
                'adaptation_id': adaptation_event.event_id,
                'adaptation_event': adaptation_event,
                'status': 'created',
                'created_at': datetime.now(),
                'started_at': None,
                'ended_at': None,
                
                # Test configuration
                'duration': config['default_test_duration'],
                'control_group_ratio': config['control_group_ratio'],
                'min_sample_size': config['min_sample_size'],
                'significance_threshold': config['significance_threshold'],
                
                # Test groups
                'control_group': {
                    'size': 0,
                    'performance_metrics': [],
                    'trades': []
                },
                'treatment_group': {
                    'size': 0,
                    'performance_metrics': [],
                    'trades': []
                },
                
                # Results
                'results': {
                    'statistical_significance': None,
                    'effect_size': None,
                    'confidence_interval': None,
                    'p_value': None,
                    'winner': None,
                    'recommendation': None
                },
                
                # Monitoring
                'interim_analyses': [],
                'early_stopping_triggered': False,
                'safety_checks': []
            }
            
            self.ab_tests[test_id] = ab_test
            
            self.logger.info("Created A/B test %s for adaptation %s", test_id, adaptation_event.event_id)
            return test_id
            
        except Exception as e:
            self.logger.error("Error creating A/B test for adaptation %s: %s", 
                            adaptation_event.event_id, str(e))
            raise
    
    def start_ab_test(self, test_id: str) -> bool:
        """
        Start an A/B test.
        
        Args:
            test_id: ID of the test to start
            
        Returns:
            bool: True if test started successfully
        """
        try:
            if test_id not in self.ab_tests:
                self.logger.error("A/B test %s not found", test_id)
                return False
            
            ab_test = self.ab_tests[test_id]
            
            if ab_test['status'] != 'created':
                self.logger.error("A/B test %s cannot be started (status: %s)", test_id, ab_test['status'])
                return False
            
            # Start the test
            ab_test['status'] = 'running'
            ab_test['started_at'] = datetime.now()
            
            # Initialize control and treatment groups
            self._initialize_ab_test_groups(ab_test)
            
            self.logger.info("Started A/B test %s", test_id)
            return True
            
        except Exception as e:
            self.logger.error("Error starting A/B test %s: %s", test_id, str(e))
            return False
    
    def update_ab_test(self, test_id: str, trade_data: Dict[str, Any]) -> None:
        """
        Update A/B test with new trade data.
        
        Args:
            test_id: ID of the test to update
            trade_data: Trade data to add to the test
        """
        try:
            if test_id not in self.ab_tests:
                return
            
            ab_test = self.ab_tests[test_id]
            
            if ab_test['status'] != 'running':
                return
            
            # Determine which group this trade belongs to
            group = self._assign_trade_to_group(ab_test, trade_data)
            
            if group:
                ab_test[f'{group}_group']['trades'].append(trade_data)
                ab_test[f'{group}_group']['size'] += 1
                
                # Update performance metrics
                self._update_group_performance(ab_test, group)
                
                # Check for interim analysis
                if self._should_perform_interim_analysis(ab_test):
                    self._perform_interim_analysis(ab_test)
                
                # Check for early stopping
                if self._should_stop_test_early(ab_test):
                    self._stop_ab_test_early(ab_test)
            
        except Exception as e:
            self.logger.error("Error updating A/B test %s: %s", test_id, str(e))
    
    def analyze_ab_test(self, test_id: str) -> Dict[str, Any]:
        """
        Analyze A/B test results.
        
        Args:
            test_id: ID of the test to analyze
            
        Returns:
            Dict containing analysis results
        """
        try:
            if test_id not in self.ab_tests:
                raise ValueError(f"A/B test {test_id} not found")
            
            ab_test = self.ab_tests[test_id]
            
            # Perform statistical analysis
            analysis_result = self._perform_statistical_analysis(ab_test)
            
            # Update test results
            ab_test['results'].update(analysis_result)
            
            # Make recommendation
            recommendation = self._make_ab_test_recommendation(ab_test)
            ab_test['results']['recommendation'] = recommendation
            
            self.logger.info("A/B test analysis completed for %s: winner=%s, p_value=%.4f",
                           test_id, analysis_result.get('winner', 'none'), 
                           analysis_result.get('p_value', 1.0))
            
            return ab_test['results']
            
        except Exception as e:
            self.logger.error("Error analyzing A/B test %s: %s", test_id, str(e))
            return {'error': str(e)}
    
    def rollback_failed_adaptation(self, adaptation_id: str, reason: str = "Performance degradation") -> bool:
        """
        Automatically rollback a failed adaptation.
        
        Args:
            adaptation_id: ID of the adaptation to rollback
            reason: Reason for the rollback
            
        Returns:
            bool: True if rollback was successful
        """
        try:
            # Find the adaptation event
            adaptation_event = None
            for event in self.adaptation_history:
                if event.event_id == adaptation_id:
                    adaptation_event = event
                    break
            
            if not adaptation_event:
                self.logger.error("Adaptation %s not found for rollback", adaptation_id)
                return False
            
            if not adaptation_event.rollback_available:
                self.logger.error("Adaptation %s is not available for rollback", adaptation_id)
                return False
            
            # Create rollback record
            rollback_record = {
                'rollback_id': str(uuid.uuid4()),
                'adaptation_id': adaptation_id,
                'reason': reason,
                'timestamp': datetime.now(),
                'rollback_data': adaptation_event.rollback_data,
                'success': False,
                'impact_before_rollback': adaptation_event.actual_impact,
                'impact_after_rollback': None
            }
            
            # Perform the rollback
            rollback_success = self._execute_rollback(adaptation_event, rollback_record)
            
            if rollback_success:
                # Update adaptation event
                adaptation_event.success = False
                adaptation_event.rollback_available = False
                
                # Remove from pending adaptations
                if adaptation_id in self.pending_adaptations:
                    del self.pending_adaptations[adaptation_id]
                
                # Record rollback
                rollback_record['success'] = True
                self.rollback_history.append(rollback_record)
                
                # Create rollback adaptation event
                rollback_event = AdaptationEvent(
                    event_id=rollback_record['rollback_id'],
                    event_type=AdaptationType.EMERGENCY_ADAPTATION,
                    trigger_reason=f"Automatic rollback: {reason}",
                    changes_made=rollback_record['rollback_data'] or {},
                    expected_impact=0.0,
                    rollback_available=False,
                    rollback_data=None
                )
                
                self.adaptation_history.append(rollback_event)
                
                self.logger.info("Successfully rolled back adaptation %s: %s", adaptation_id, reason)
                return True
            else:
                rollback_record['success'] = False
                self.rollback_history.append(rollback_record)
                self.logger.error("Failed to rollback adaptation %s", adaptation_id)
                return False
                
        except Exception as e:
            self.logger.error("Error rolling back adaptation %s: %s", adaptation_id, str(e))
            return False
    
    def get_adaptation_history_analysis(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Analyze adaptation history for patterns and insights.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            Dict containing historical analysis
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days_back)
            
            # Filter relevant adaptations
            relevant_adaptations = [
                event for event in self.adaptation_history
                if event.timestamp >= cutoff_time
            ]
            
            if not relevant_adaptations:
                return {
                    'period_days': days_back,
                    'total_adaptations': 0,
                    'analysis': 'No adaptations in the specified period'
                }
            
            analysis = {
                'period_days': days_back,
                'total_adaptations': len(relevant_adaptations),
                'successful_adaptations': 0,
                'failed_adaptations': 0,
                'pending_adaptations': 0,
                'rollbacks': len([r for r in self.rollback_history if r['timestamp'] >= cutoff_time]),
                
                # Performance metrics
                'average_impact': 0.0,
                'total_impact': 0.0,
                'best_adaptation': None,
                'worst_adaptation': None,
                
                # Patterns
                'adaptation_types': {},
                'trigger_reasons': {},
                'success_rate_by_type': {},
                'temporal_patterns': {},
                
                # Insights
                'insights': [],
                'recommendations': []
            }
            
            # Analyze adaptations
            impacts = []
            for event in relevant_adaptations:
                # Count by status
                if event.success is True:
                    analysis['successful_adaptations'] += 1
                elif event.success is False:
                    analysis['failed_adaptations'] += 1
                else:
                    analysis['pending_adaptations'] += 1
                
                # Track impacts
                if event.actual_impact is not None:
                    impacts.append(event.actual_impact)
                    analysis['total_impact'] += event.actual_impact
                
                # Count by type
                event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
                analysis['adaptation_types'][event_type] = analysis['adaptation_types'].get(event_type, 0) + 1
                
                # Count by trigger reason
                trigger = event.trigger_reason[:50]  # Truncate for grouping
                analysis['trigger_reasons'][trigger] = analysis['trigger_reasons'].get(trigger, 0) + 1
            
            # Calculate averages
            if impacts:
                analysis['average_impact'] = sum(impacts) / len(impacts)
                analysis['best_adaptation'] = max(impacts)
                analysis['worst_adaptation'] = min(impacts)
            
            # Calculate success rates by type
            for adaptation_type in analysis['adaptation_types']:
                type_events = [e for e in relevant_adaptations 
                             if (e.event_type.value if hasattr(e.event_type, 'value') else str(e.event_type)) == adaptation_type]
                successful = sum(1 for e in type_events if e.success is True)
                total = len(type_events)
                analysis['success_rate_by_type'][adaptation_type] = successful / total if total > 0 else 0.0
            
            # Temporal patterns
            analysis['temporal_patterns'] = self._analyze_temporal_patterns(relevant_adaptations)
            
            # Generate insights
            analysis['insights'] = self._generate_adaptation_insights(analysis, relevant_adaptations)
            analysis['recommendations'] = self._generate_adaptation_recommendations(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error("Error analyzing adaptation history: %s", str(e))
            return {'error': str(e)}
    
    def get_rollback_history(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Get rollback history for analysis.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of rollback records
        """
        cutoff_time = datetime.now() - timedelta(days=days_back)
        return [
            rollback for rollback in self.rollback_history
            if rollback['timestamp'] >= cutoff_time
        ]    

    # Private helper methods for validation and A/B testing
    
    def _assess_adaptation_risk(self, adaptation_event: AdaptationEvent) -> Dict[str, Any]:
        """Assess the risk level of an adaptation."""
        try:
            risk_factors = []
            risk_score = 0.0
            
            # Change magnitude risk
            change_magnitude = self._calculate_change_magnitude(adaptation_event.changes_made)
            if change_magnitude > 0.2:  # 20% change
                risk_factors.append("large_change_magnitude")
                risk_score += 0.3
            elif change_magnitude > 0.1:  # 10% change
                risk_factors.append("moderate_change_magnitude")
                risk_score += 0.1
            
            # Strategy impact risk
            if len(adaptation_event.affected_strategies) > 3:
                risk_factors.append("multiple_strategies_affected")
                risk_score += 0.2
            
            # Market condition risk
            if adaptation_event.market_conditions:
                volatility = adaptation_event.market_conditions.get('volatility', 0.0)
                if volatility > 0.3:  # High volatility
                    risk_factors.append("high_market_volatility")
                    risk_score += 0.2
            
            # Historical failure risk
            recent_failures = self._get_recent_adaptation_failures()
            if recent_failures > 2:
                risk_factors.append("recent_adaptation_failures")
                risk_score += 0.3
            
            # Emergency adaptation risk
            if adaptation_event.event_type == AdaptationType.EMERGENCY_ADAPTATION:
                risk_factors.append("emergency_adaptation")
                risk_score += 0.4
            
            return {
                'risk_score': min(risk_score, 1.0),
                'risk_factors': risk_factors,
                'risk_level': 'high' if risk_score > 0.7 else 'medium' if risk_score > 0.3 else 'low',
                'passed': risk_score <= 0.8
            }
            
        except Exception as e:
            self.logger.error("Error assessing adaptation risk: %s", str(e))
            return {'risk_score': 1.0, 'risk_factors': ['assessment_error'], 'risk_level': 'high', 'passed': False}
    
    def _simulate_adaptation_performance(self, adaptation_event: AdaptationEvent) -> Dict[str, Any]:
        """Simulate the expected performance impact of an adaptation."""
        try:
            # This is a simplified simulation - in practice, you'd use historical data
            # and more sophisticated modeling
            
            base_impact = adaptation_event.expected_impact
            
            # Adjust based on confidence and risk factors
            confidence_adjustment = 0.0
            if 'confidence' in adaptation_event.changes_made:
                confidence = adaptation_event.changes_made['confidence']
                confidence_adjustment = (confidence - 0.5) * 0.1  # -0.05 to +0.05
            
            # Market condition adjustment
            market_adjustment = 0.0
            if adaptation_event.market_conditions:
                # Favorable conditions boost expected impact
                trend_strength = adaptation_event.market_conditions.get('trend_strength', 0.0)
                market_adjustment = trend_strength * 0.02
            
            # Historical pattern adjustment
            historical_success_rate = self._get_recent_adaptation_success_rate()
            historical_adjustment = (historical_success_rate - 0.5) * 0.05
            
            estimated_impact = base_impact + confidence_adjustment + market_adjustment + historical_adjustment
            
            # Calculate confidence interval
            uncertainty = 0.02  # 2% uncertainty
            confidence_interval = (estimated_impact - uncertainty, estimated_impact + uncertainty)
            
            return {
                'estimated_impact': estimated_impact,
                'confidence_interval': confidence_interval,
                'base_impact': base_impact,
                'adjustments': {
                    'confidence': confidence_adjustment,
                    'market': market_adjustment,
                    'historical': historical_adjustment
                },
                'uncertainty': uncertainty,
                'passed': estimated_impact > -0.02  # Accept if expected loss < 2%
            }
            
        except Exception as e:
            self.logger.error("Error simulating adaptation performance: %s", str(e))
            return {'estimated_impact': -0.1, 'passed': False, 'error': str(e)}
    
    def _analyze_resource_impact(self, adaptation_event: AdaptationEvent) -> Dict[str, Any]:
        """Analyze the resource impact of an adaptation."""
        try:
            resource_impact = {
                'cpu_impact': 0.0,
                'memory_impact': 0.0,
                'network_impact': 0.0,
                'storage_impact': 0.0,
                'total_impact': 0.0,
                'passed': True
            }
            
            # Estimate resource impact based on adaptation type and changes
            if 'ml_models' in adaptation_event.changes_made:
                resource_impact['cpu_impact'] += 0.2  # ML models are CPU intensive
                resource_impact['memory_impact'] += 0.1
            
            if 'parameters' in adaptation_event.changes_made:
                param_count = len(adaptation_event.changes_made['parameters'])
                resource_impact['cpu_impact'] += param_count * 0.01
            
            if 'strategy_weights' in adaptation_event.changes_made:
                strategy_count = len(adaptation_event.changes_made['strategy_weights'])
                resource_impact['cpu_impact'] += strategy_count * 0.02
                resource_impact['memory_impact'] += strategy_count * 0.01
            
            # Calculate total impact
            resource_impact['total_impact'] = (
                resource_impact['cpu_impact'] + 
                resource_impact['memory_impact'] + 
                resource_impact['network_impact'] + 
                resource_impact['storage_impact']
            ) / 4
            
            # Check if impact is acceptable
            resource_impact['passed'] = resource_impact['total_impact'] <= 0.3  # 30% max impact
            
            return resource_impact
            
        except Exception as e:
            self.logger.error("Error analyzing resource impact: %s", str(e))
            return {'total_impact': 1.0, 'passed': False, 'error': str(e)}
    
    def _check_adaptation_conflicts(self, adaptation_event: AdaptationEvent) -> Dict[str, Any]:
        """Check for conflicts with pending adaptations."""
        try:
            conflicts = []
            conflict_severity = 0.0
            
            for pending_id, pending_event in self.pending_adaptations.items():
                # Check for strategy conflicts
                if adaptation_event.affected_strategies and pending_event.affected_strategies:
                    strategy_overlap = set(adaptation_event.affected_strategies) & set(pending_event.affected_strategies)
                    if strategy_overlap:
                        conflicts.append({
                            'type': 'strategy_overlap',
                            'pending_adaptation': pending_id,
                            'overlapping_strategies': list(strategy_overlap)
                        })
                        conflict_severity += 0.3
                
                # Check for parameter conflicts
                if ('parameters' in adaptation_event.changes_made and 
                    'parameters' in pending_event.changes_made):
                    param_overlap = (set(adaptation_event.changes_made['parameters'].keys()) & 
                                   set(pending_event.changes_made['parameters'].keys()))
                    if param_overlap:
                        conflicts.append({
                            'type': 'parameter_overlap',
                            'pending_adaptation': pending_id,
                            'overlapping_parameters': list(param_overlap)
                        })
                        conflict_severity += 0.4
                
                # Check for timing conflicts
                time_diff = abs((adaptation_event.timestamp - pending_event.timestamp).total_seconds())
                if time_diff < 1800:  # 30 minutes
                    conflicts.append({
                        'type': 'timing_conflict',
                        'pending_adaptation': pending_id,
                        'time_difference_seconds': time_diff
                    })
                    conflict_severity += 0.2
            
            return {
                'conflicts': conflicts,
                'conflict_count': len(conflicts),
                'conflict_severity': min(conflict_severity, 1.0),
                'passed': len(conflicts) == 0 or conflict_severity <= 0.5
            }
            
        except Exception as e:
            self.logger.error("Error checking adaptation conflicts: %s", str(e))
            return {'conflicts': [], 'conflict_count': 0, 'passed': True}
    
    def _assess_market_condition_suitability(self, adaptation_event: AdaptationEvent) -> Dict[str, Any]:
        """Assess if current market conditions are suitable for the adaptation."""
        try:
            if not adaptation_event.market_conditions:
                return {'suitability_score': 0.5, 'passed': True, 'reason': 'no_market_data'}
            
            conditions = adaptation_event.market_conditions
            suitability_factors = []
            suitability_score = 0.5  # Neutral baseline
            
            # Volatility suitability
            volatility = conditions.get('volatility', 0.0)
            if adaptation_event.event_type == AdaptationType.PARAMETER_OPTIMIZATION:
                # Parameter optimization works better in stable conditions
                if volatility < 0.2:  # Low volatility
                    suitability_factors.append('favorable_volatility')
                    suitability_score += 0.2
                elif volatility > 0.4:  # High volatility
                    suitability_factors.append('unfavorable_volatility')
                    suitability_score -= 0.3
            
            # Trend suitability
            trend_strength = conditions.get('trend_strength', 0.0)
            if adaptation_event.event_type == AdaptationType.STRATEGY_REBALANCING:
                # Strategy rebalancing works better in trending markets
                if abs(trend_strength) > 0.3:
                    suitability_factors.append('favorable_trend')
                    suitability_score += 0.2
                else:
                    suitability_factors.append('weak_trend')
                    suitability_score -= 0.1
            
            # Liquidity suitability
            liquidity = conditions.get('liquidity', 1.0)
            if liquidity < 0.5:  # Low liquidity
                suitability_factors.append('low_liquidity_risk')
                suitability_score -= 0.2
            
            # Market regime suitability
            regime = conditions.get('regime', 'unknown')
            if regime == 'high_volatility' and adaptation_event.event_type != AdaptationType.EMERGENCY_ADAPTATION:
                suitability_factors.append('unsuitable_regime')
                suitability_score -= 0.3
            
            suitability_score = max(0.0, min(1.0, suitability_score))
            
            return {
                'suitability_score': suitability_score,
                'suitability_factors': suitability_factors,
                'market_conditions': conditions,
                'passed': suitability_score >= 0.4
            }
            
        except Exception as e:
            self.logger.error("Error assessing market condition suitability: %s", str(e))
            return {'suitability_score': 0.0, 'passed': False, 'error': str(e)}
    
    def _analyze_historical_patterns(self, adaptation_event: AdaptationEvent) -> Dict[str, Any]:
        """Analyze historical patterns for similar adaptations."""
        try:
            # Find similar historical adaptations
            similar_adaptations = []
            for historical_event in self.adaptation_history:
                if (historical_event.event_type == adaptation_event.event_type and
                    historical_event.success is not None):
                    
                    # Calculate similarity score
                    similarity = self._calculate_adaptation_similarity(adaptation_event, historical_event)
                    if similarity > 0.5:  # 50% similarity threshold
                        similar_adaptations.append({
                            'event': historical_event,
                            'similarity': similarity
                        })
            
            if not similar_adaptations:
                return {
                    'historical_success_rate': 0.5,  # Neutral when no history
                    'similar_adaptations_count': 0,
                    'pattern_confidence': 0.0,
                    'passed': True,
                    'insights': ['no_historical_data']
                }
            
            # Analyze patterns
            successful_count = sum(1 for item in similar_adaptations if item['event'].success)
            total_count = len(similar_adaptations)
            success_rate = successful_count / total_count
            
            # Calculate average impact of similar adaptations
            impacts = [item['event'].actual_impact for item in similar_adaptations 
                      if item['event'].actual_impact is not None]
            avg_impact = sum(impacts) / len(impacts) if impacts else 0.0
            
            # Generate insights
            insights = []
            if success_rate > 0.7:
                insights.append('high_historical_success_rate')
            elif success_rate < 0.3:
                insights.append('low_historical_success_rate')
            
            if avg_impact > 0.05:
                insights.append('historically_positive_impact')
            elif avg_impact < -0.05:
                insights.append('historically_negative_impact')
            
            pattern_confidence = min(total_count / 10.0, 1.0)  # More data = higher confidence
            
            return {
                'historical_success_rate': success_rate,
                'similar_adaptations_count': total_count,
                'average_historical_impact': avg_impact,
                'pattern_confidence': pattern_confidence,
                'insights': insights,
                'passed': success_rate >= 0.4 or total_count < 3  # Pass if good history or insufficient data
            }
            
        except Exception as e:
            self.logger.error("Error analyzing historical patterns: %s", str(e))
            return {'historical_success_rate': 0.0, 'passed': False, 'error': str(e)}
    
    def _calculate_adaptation_similarity(self, event1: AdaptationEvent, event2: AdaptationEvent) -> float:
        """Calculate similarity between two adaptation events."""
        try:
            similarity_factors = []
            
            # Event type similarity
            if event1.event_type == event2.event_type:
                similarity_factors.append(1.0)
            else:
                similarity_factors.append(0.0)
            
            # Strategy overlap similarity
            if event1.affected_strategies and event2.affected_strategies:
                overlap = len(set(event1.affected_strategies) & set(event2.affected_strategies))
                total = len(set(event1.affected_strategies) | set(event2.affected_strategies))
                similarity_factors.append(overlap / total if total > 0 else 0.0)
            
            # Change magnitude similarity
            mag1 = self._calculate_change_magnitude(event1.changes_made)
            mag2 = self._calculate_change_magnitude(event2.changes_made)
            if mag1 > 0 and mag2 > 0:
                mag_similarity = 1.0 - abs(mag1 - mag2) / max(mag1, mag2)
                similarity_factors.append(mag_similarity)
            
            # Market condition similarity (if available)
            if (event1.market_conditions and event2.market_conditions):
                market_similarity = self._calculate_market_condition_similarity(
                    event1.market_conditions, event2.market_conditions)
                similarity_factors.append(market_similarity)
            
            return sum(similarity_factors) / len(similarity_factors) if similarity_factors else 0.0
            
        except Exception as e:
            self.logger.error("Error calculating adaptation similarity: %s", str(e))
            return 0.0
    
    def _calculate_market_condition_similarity(self, conditions1: Dict, conditions2: Dict) -> float:
        """Calculate similarity between market conditions."""
        try:
            similarities = []
            
            # Compare common metrics
            common_metrics = ['volatility', 'trend_strength', 'liquidity']
            for metric in common_metrics:
                if metric in conditions1 and metric in conditions2:
                    val1, val2 = conditions1[metric], conditions2[metric]
                    if val1 != 0 or val2 != 0:
                        similarity = 1.0 - abs(val1 - val2) / max(abs(val1), abs(val2), 1.0)
                        similarities.append(similarity)
            
            # Compare regime if available
            if 'regime' in conditions1 and 'regime' in conditions2:
                regime_similarity = 1.0 if conditions1['regime'] == conditions2['regime'] else 0.0
                similarities.append(regime_similarity)
            
            return sum(similarities) / len(similarities) if similarities else 0.5
            
        except Exception as e:
            self.logger.error("Error calculating market condition similarity: %s", str(e))
            return 0.5
    
    def _calculate_validation_score(self, checks: Dict[str, Dict[str, Any]]) -> float:
        """Calculate overall validation score from individual checks."""
        try:
            scores = []
            weights = {
                'risk_assessment': 0.25,
                'performance_simulation': 0.25,
                'resource_impact': 0.15,
                'conflict_detection': 0.15,
                'market_suitability': 0.10,
                'historical_analysis': 0.10
            }
            
            for check_name, check_result in checks.items():
                weight = weights.get(check_name, 0.1)
                
                if check_result.get('passed', False):
                    # Extract score from different check types
                    if 'risk_score' in check_result:
                        score = 1.0 - check_result['risk_score']  # Invert risk score
                    elif 'suitability_score' in check_result:
                        score = check_result['suitability_score']
                    elif 'historical_success_rate' in check_result:
                        score = check_result['historical_success_rate']
                    elif 'total_impact' in check_result:
                        score = max(0.0, 1.0 - check_result['total_impact'])
                    else:
                        score = 1.0  # Default for passed checks
                else:
                    score = 0.0  # Failed checks get 0 score
                
                scores.append(score * weight)
            
            return sum(scores)
            
        except Exception as e:
            self.logger.error("Error calculating validation score: %s", str(e))
            return 0.0
    
    def _determine_risk_level(self, validation_score: float) -> str:
        """Determine risk level based on validation score."""
        if validation_score >= 0.8:
            return 'low'
        elif validation_score >= 0.6:
            return 'medium'
        elif validation_score >= 0.4:
            return 'high'
        else:
            return 'critical'
    
    def _make_validation_recommendation(self, validation_result: Dict[str, Any]) -> str:
        """Make a recommendation based on validation results."""
        try:
            score = validation_result['overall_score']
            risk_level = validation_result['risk_level']
            
            # Check for critical failures
            critical_failures = []
            for check_name, check_result in validation_result['checks'].items():
                if not check_result.get('passed', True):
                    if check_name in ['risk_assessment', 'performance_simulation']:
                        critical_failures.append(check_name)
            
            if critical_failures:
                return 'reject'
            
            # Make recommendation based on score and risk
            if score >= 0.8 and risk_level in ['low', 'medium']:
                return 'approve'
            elif score >= 0.6 and risk_level != 'critical':
                return 'approve_with_monitoring'
            elif score >= 0.4:
                return 'approve_with_ab_test'
            else:
                return 'reject'
                
        except Exception as e:
            self.logger.error("Error making validation recommendation: %s", str(e))
            return 'reject'
    
    # A/B testing helper methods
    
    def _initialize_ab_test_groups(self, ab_test: Dict[str, Any]) -> None:
        """Initialize control and treatment groups for A/B test."""
        try:
            # Reset group data
            ab_test['control_group'] = {
                'size': 0,
                'performance_metrics': [],
                'trades': [],
                'allocation_ratio': ab_test['control_group_ratio']
            }
            
            ab_test['treatment_group'] = {
                'size': 0,
                'performance_metrics': [],
                'trades': [],
                'allocation_ratio': 1.0 - ab_test['control_group_ratio']
            }
            
            self.logger.info("Initialized A/B test groups for test %s", ab_test['test_id'])
            
        except Exception as e:
            self.logger.error("Error initializing A/B test groups: %s", str(e))
    
    def _assign_trade_to_group(self, ab_test: Dict[str, Any], trade_data: Dict[str, Any]) -> Optional[str]:
        """Assign a trade to control or treatment group."""
        try:
            # Simple random assignment based on control group ratio
            import random
            if random.random() < ab_test['control_group_ratio']:
                return 'control'
            else:
                return 'treatment'
                
        except Exception as e:
            self.logger.error("Error assigning trade to group: %s", str(e))
            return None
    
    def _update_group_performance(self, ab_test: Dict[str, Any], group: str) -> None:
        """Update performance metrics for a group."""
        try:
            group_data = ab_test[f'{group}_group']
            trades = group_data['trades']
            
            if not trades:
                return
            
            # Calculate basic performance metrics
            total_return = sum(trade.get('return', 0.0) for trade in trades)
            win_count = sum(1 for trade in trades if trade.get('return', 0.0) > 0)
            win_rate = win_count / len(trades) if trades else 0.0
            
            # Calculate other metrics as needed
            performance_metrics = {
                'total_return': total_return,
                'average_return': total_return / len(trades) if trades else 0.0,
                'win_rate': win_rate,
                'trade_count': len(trades),
                'timestamp': datetime.now()
            }
            
            group_data['performance_metrics'].append(performance_metrics)
            
        except Exception as e:
            self.logger.error("Error updating group performance: %s", str(e))
    
    def _should_perform_interim_analysis(self, ab_test: Dict[str, Any]) -> bool:
        """Check if interim analysis should be performed."""
        try:
            # Perform interim analysis every 25% of minimum sample size
            total_trades = ab_test['control_group']['size'] + ab_test['treatment_group']['size']
            interim_threshold = ab_test['min_sample_size'] * 0.25
            
            # Check if we've reached an interim milestone
            last_interim = len(ab_test['interim_analyses'])
            expected_interims = int(total_trades / interim_threshold)
            
            return expected_interims > last_interim
            
        except Exception as e:
            self.logger.error("Error checking interim analysis: %s", str(e))
            return False
    
    def _perform_interim_analysis(self, ab_test: Dict[str, Any]) -> None:
        """Perform interim analysis of A/B test."""
        try:
            analysis_result = self._perform_statistical_analysis(ab_test)
            
            interim_analysis = {
                'timestamp': datetime.now(),
                'analysis_number': len(ab_test['interim_analyses']) + 1,
                'results': analysis_result,
                'recommendation': 'continue'  # Default to continue
            }
            
            # Check for early stopping conditions
            if analysis_result.get('statistical_significance', False):
                p_value = analysis_result.get('p_value', 1.0)
                if p_value < ab_test['significance_threshold'] / 2:  # Bonferroni correction
                    interim_analysis['recommendation'] = 'stop_early'
            
            ab_test['interim_analyses'].append(interim_analysis)
            
            self.logger.info("Performed interim analysis for A/B test %s: %s", 
                           ab_test['test_id'], interim_analysis['recommendation'])
            
        except Exception as e:
            self.logger.error("Error performing interim analysis: %s", str(e))
    
    def _should_stop_test_early(self, ab_test: Dict[str, Any]) -> bool:
        """Check if A/B test should be stopped early."""
        try:
            # Check if test duration has been reached
            if ab_test['started_at']:
                elapsed = datetime.now() - ab_test['started_at']
                if elapsed >= ab_test['duration']:
                    return True
            
            # Check interim analysis recommendations
            if ab_test['interim_analyses']:
                latest_interim = ab_test['interim_analyses'][-1]
                if latest_interim['recommendation'] == 'stop_early':
                    return True
            
            # Check safety conditions
            for safety_check in ab_test['safety_checks']:
                if safety_check.get('triggered', False):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error("Error checking early stopping: %s", str(e))
            return False
    
    def _stop_ab_test_early(self, ab_test: Dict[str, Any]) -> None:
        """Stop A/B test early."""
        try:
            ab_test['status'] = 'stopped_early'
            ab_test['ended_at'] = datetime.now()
            ab_test['early_stopping_triggered'] = True
            
            # Perform final analysis
            final_results = self._perform_statistical_analysis(ab_test)
            ab_test['results'].update(final_results)
            
            self.logger.info("Stopped A/B test %s early", ab_test['test_id'])
            
        except Exception as e:
            self.logger.error("Error stopping A/B test early: %s", str(e))
    
    def _perform_statistical_analysis(self, ab_test: Dict[str, Any]) -> Dict[str, Any]:
        """Perform statistical analysis of A/B test results."""
        try:
            control_group = ab_test['control_group']
            treatment_group = ab_test['treatment_group']
            
            # Get performance data
            control_returns = [trade.get('return', 0.0) for trade in control_group['trades']]
            treatment_returns = [trade.get('return', 0.0) for trade in treatment_group['trades']]
            
            if not control_returns or not treatment_returns:
                return {
                    'statistical_significance': False,
                    'p_value': 1.0,
                    'effect_size': 0.0,
                    'confidence_interval': (0.0, 0.0),
                    'winner': 'inconclusive',
                    'error': 'insufficient_data'
                }
            
            # Calculate basic statistics
            control_mean = np.mean(control_returns)
            treatment_mean = np.mean(treatment_returns)
            effect_size = treatment_mean - control_mean
            
            # Perform t-test (simplified)
            control_std = np.std(control_returns, ddof=1) if len(control_returns) > 1 else 0.0
            treatment_std = np.std(treatment_returns, ddof=1) if len(treatment_returns) > 1 else 0.0
            
            # Pooled standard error
            n1, n2 = len(control_returns), len(treatment_returns)
            pooled_se = np.sqrt((control_std**2 / n1) + (treatment_std**2 / n2)) if n1 > 0 and n2 > 0 else 1.0
            
            # T-statistic and p-value (simplified)
            t_stat = effect_size / pooled_se if pooled_se > 0 else 0.0
            
            # Simplified p-value calculation (in practice, use scipy.stats)
            p_value = 2 * (1 - abs(t_stat) / (abs(t_stat) + 1))  # Rough approximation
            
            # Confidence interval (simplified)
            margin_of_error = 1.96 * pooled_se  # 95% CI
            confidence_interval = (effect_size - margin_of_error, effect_size + margin_of_error)
            
            # Determine winner
            winner = 'inconclusive'
            if p_value < ab_test['significance_threshold']:
                winner = 'treatment' if effect_size > 0 else 'control'
            
            return {
                'statistical_significance': p_value < ab_test['significance_threshold'],
                'p_value': p_value,
                'effect_size': effect_size,
                'confidence_interval': confidence_interval,
                'winner': winner,
                'control_mean': control_mean,
                'treatment_mean': treatment_mean,
                'control_sample_size': n1,
                'treatment_sample_size': n2
            }
            
        except Exception as e:
            self.logger.error("Error performing statistical analysis: %s", str(e))
            return {
                'statistical_significance': False,
                'p_value': 1.0,
                'effect_size': 0.0,
                'winner': 'error',
                'error': str(e)
            }
    
    def _make_ab_test_recommendation(self, ab_test: Dict[str, Any]) -> str:
        """Make recommendation based on A/B test results."""
        try:
            results = ab_test['results']
            
            if results.get('error'):
                return 'inconclusive'
            
            if not results.get('statistical_significance', False):
                return 'no_significant_difference'
            
            winner = results.get('winner', 'inconclusive')
            effect_size = results.get('effect_size', 0.0)
            
            if winner == 'treatment' and effect_size > 0.01:  # 1% improvement
                return 'deploy_treatment'
            elif winner == 'control':
                return 'keep_control'
            else:
                return 'inconclusive'
                
        except Exception as e:
            self.logger.error("Error making A/B test recommendation: %s", str(e))
            return 'error'
    
    def _execute_rollback(self, adaptation_event: AdaptationEvent, rollback_record: Dict[str, Any]) -> bool:
        """Execute the actual rollback of an adaptation."""
        try:
            # This is where you would implement the actual rollback logic
            # For now, we'll simulate a successful rollback
            
            rollback_data = rollback_record['rollback_data']
            if not rollback_data:
                self.logger.error("No rollback data available for adaptation %s", adaptation_event.event_id)
                return False
            
            # Simulate rollback operations
            self.logger.info("Executing rollback for adaptation %s", adaptation_event.event_id)
            
            # In a real implementation, you would:
            # 1. Restore previous parameter values
            # 2. Revert strategy weights
            # 3. Reset ML model states
            # 4. Clear any cached data
            # 5. Notify other system components
            
            return True  # Simulate successful rollback
            
        except Exception as e:
            self.logger.error("Error executing rollback: %s", str(e))
            return False
    
    def _analyze_temporal_patterns(self, adaptations: List[AdaptationEvent]) -> Dict[str, Any]:
        """Analyze temporal patterns in adaptations."""
        try:
            patterns = {
                'hourly_distribution': {},
                'daily_distribution': {},
                'weekly_distribution': {},
                'success_by_hour': {},
                'success_by_day': {}
            }
            
            for event in adaptations:
                hour = event.timestamp.hour
                day = event.timestamp.strftime('%A')
                
                # Count by hour
                patterns['hourly_distribution'][hour] = patterns['hourly_distribution'].get(hour, 0) + 1
                
                # Count by day
                patterns['daily_distribution'][day] = patterns['daily_distribution'].get(day, 0) + 1
                
                # Success rates by time
                if event.success is not None:
                    if hour not in patterns['success_by_hour']:
                        patterns['success_by_hour'][hour] = {'total': 0, 'successful': 0}
                    patterns['success_by_hour'][hour]['total'] += 1
                    if event.success:
                        patterns['success_by_hour'][hour]['successful'] += 1
                    
                    if day not in patterns['success_by_day']:
                        patterns['success_by_day'][day] = {'total': 0, 'successful': 0}
                    patterns['success_by_day'][day]['total'] += 1
                    if event.success:
                        patterns['success_by_day'][day]['successful'] += 1
            
            # Calculate success rates
            for hour_data in patterns['success_by_hour'].values():
                hour_data['success_rate'] = hour_data['successful'] / hour_data['total'] if hour_data['total'] > 0 else 0.0
            
            for day_data in patterns['success_by_day'].values():
                day_data['success_rate'] = day_data['successful'] / day_data['total'] if day_data['total'] > 0 else 0.0
            
            return patterns
            
        except Exception as e:
            self.logger.error("Error analyzing temporal patterns: %s", str(e))
            return {}
    
    def _generate_adaptation_insights(self, analysis: Dict[str, Any], adaptations: List[AdaptationEvent]) -> List[str]:
        """Generate insights from adaptation analysis."""
        try:
            insights = []
            
            # Success rate insights
            total_adaptations = analysis['total_adaptations']
            if total_adaptations > 0:
                success_rate = analysis['successful_adaptations'] / total_adaptations
                if success_rate > 0.8:
                    insights.append("High adaptation success rate indicates effective decision-making")
                elif success_rate < 0.4:
                    insights.append("Low adaptation success rate suggests need for improved validation")
            
            # Impact insights
            if analysis['average_impact'] > 0.05:
                insights.append("Adaptations are generating significant positive impact")
            elif analysis['average_impact'] < -0.02:
                insights.append("Adaptations are causing negative impact - review criteria")
            
            # Rollback insights
            if analysis['rollbacks'] > analysis['successful_adaptations']:
                insights.append("High rollback rate indicates need for better pre-deployment validation")
            
            # Type-specific insights
            for adaptation_type, success_rate in analysis['success_rate_by_type'].items():
                if success_rate > 0.9:
                    insights.append(f"{adaptation_type} adaptations are highly successful")
                elif success_rate < 0.3:
                    insights.append(f"{adaptation_type} adaptations have low success rate")
            
            return insights
            
        except Exception as e:
            self.logger.error("Error generating adaptation insights: %s", str(e))
            return []
    
    def _generate_adaptation_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on adaptation analysis."""
        try:
            recommendations = []
            
            # Success rate recommendations
            total_adaptations = analysis['total_adaptations']
            if total_adaptations > 0:
                success_rate = analysis['successful_adaptations'] / total_adaptations
                if success_rate < 0.5:
                    recommendations.append("Increase validation thresholds to improve success rate")
                    recommendations.append("Consider longer evaluation periods before adaptations")
            
            # Rollback recommendations
            if analysis['rollbacks'] > 3:
                recommendations.append("Implement more rigorous pre-deployment testing")
                recommendations.append("Consider A/B testing for all significant adaptations")
            
            # Impact recommendations
            if analysis['average_impact'] < 0:
                recommendations.append("Review adaptation triggers - may be too aggressive")
                recommendations.append("Increase confidence thresholds for adaptations")
            
            # Frequency recommendations
            adaptation_rate = total_adaptations / analysis['period_days'] if analysis['period_days'] > 0 else 0
            if adaptation_rate > 2:  # More than 2 per day
                recommendations.append("Consider reducing adaptation frequency to allow proper evaluation")
            elif adaptation_rate < 0.1:  # Less than 1 per 10 days
                recommendations.append("System may be too conservative - consider lowering thresholds")
            
            return recommendations
            
        except Exception as e:
            self.logger.error("Error generating adaptation recommendations: %s", str(e))
            return []