"""
Unit tests for the AdaptationController class.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import logging

from bot.adaptive.adaptation_controller import AdaptationController, AdaptationLimits, AdaptationContext
from bot.adaptive.data_models import PerformanceMetrics, AdaptationEvent, MarketRegime
from bot.adaptive.enums import AdaptationType, RegimeType


# Global fixtures for all test classes
@pytest.fixture
def controller():
    """Create a test adaptation controller."""
    limits = AdaptationLimits(
        min_performance_threshold=-0.05,
        min_confidence_threshold=0.6,
        max_adaptations_per_hour=2,
        max_adaptations_per_day=10,
        min_time_between_adaptations=timedelta(minutes=30)
    )
    return AdaptationController(limits=limits)

@pytest.fixture
def sample_performance_metrics():
    """Create sample performance metrics."""
    return PerformanceMetrics(
        total_return=-0.08,  # 8% loss
        annualized_return=-0.15,
        excess_return=-0.05,
        sharpe_ratio=-0.5,
        sortino_ratio=-0.3,
        calmar_ratio=-0.2,
        max_drawdown=-0.12,  # 12% drawdown
        volatility=0.25,
        downside_deviation=0.18,
        win_rate=0.35,  # Low win rate
        profit_factor=0.8,
        avg_trade_duration=timedelta(hours=4),
        trades_count=150,  # Sufficient data
        avg_win=0.02,
        avg_loss=-0.015
    )

@pytest.fixture
def sample_adaptation_event():
    """Create a sample adaptation event."""
    return AdaptationEvent(
        event_id=str(uuid.uuid4()),
        event_type=AdaptationType.PARAMETER_OPTIMIZATION,
        trigger_reason="Performance degradation detected",
        changes_made={
            'parameters': {'stop_loss': 0.02, 'take_profit': 0.04},
            'confidence': 0.75
        },
        expected_impact=0.03
    )


class TestAdaptationController:
    """Test cases for AdaptationController."""
    pass


class TestAdaptationDecisionLogic:
    """Test adaptation decision logic."""
    
    def test_should_adapt_confidence_threshold(self, controller, sample_performance_metrics):
        """Test that low confidence prevents adaptation even with poor performance."""
        # Mock low confidence calculation
        with patch.object(controller, '_calculate_adaptation_confidence', return_value=0.4):
            # Even with poor performance, low confidence should prevent adaptation
            assert not controller.should_adapt(sample_performance_metrics, "test_strategy")
    
    def test_should_adapt_evaluation_period(self, controller, sample_performance_metrics):
        """Test minimum evaluation period requirement."""
        # Add a recent adaptation
        recent_adaptation = AdaptationEvent(
            event_id="recent",
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Recent adaptation",
            changes_made={},
            expected_impact=0.01,
            timestamp=datetime.now() - timedelta(minutes=30),  # Too recent
            affected_strategies=["test_strategy"]
        )
        controller.adaptation_history.append(recent_adaptation)
        
        # Should not adapt due to insufficient evaluation period
        assert not controller.should_adapt(sample_performance_metrics, "test_strategy")
    
    def test_should_adapt_performance_trend(self, controller):
        """Test adaptation triggering based on negative performance trend."""
        # Create metrics with positive return but negative trend
        trending_down_metrics = PerformanceMetrics(
            total_return=0.01,  # Positive return
            annualized_return=0.02,
            excess_return=0.005,
            sharpe_ratio=0.3,
            sortino_ratio=0.4,
            calmar_ratio=0.2,
            max_drawdown=-0.05,
            volatility=0.20,
            downside_deviation=0.15,
            win_rate=0.50,
            profit_factor=1.1,
            avg_trade_duration=timedelta(hours=3),
            trades_count=150,
            avg_win=0.02,
            avg_loss=-0.015
        )
        
        # Mock negative trend
        with patch.object(controller, '_calculate_performance_trend', return_value=-0.03):
            with patch.object(controller, '_calculate_adaptation_confidence', return_value=0.8):
                assert controller.should_adapt(trending_down_metrics, "test_strategy")
    
    def test_should_adapt_performance_threshold(self, controller, sample_performance_metrics):
        """Test adaptation triggering based on performance threshold."""
        # Performance drop exceeds threshold - should adapt
        assert controller.should_adapt(sample_performance_metrics, "test_strategy")
        
        # Performance within threshold - should not adapt
        good_metrics = PerformanceMetrics(
            total_return=-0.02,  # Only 2% loss
            annualized_return=-0.04,
            excess_return=-0.01,
            sharpe_ratio=0.2,
            sortino_ratio=0.3,
            calmar_ratio=0.1,
            max_drawdown=-0.03,  # Small drawdown
            volatility=0.15,
            downside_deviation=0.10,
            win_rate=0.55,  # Good win rate
            profit_factor=1.2,
            avg_trade_duration=timedelta(hours=3),
            trades_count=150,
            avg_win=0.025,
            avg_loss=-0.015
        )
        assert not controller.should_adapt(good_metrics, "test_strategy")
    
    def test_should_adapt_emergency_conditions(self, controller):
        """Test emergency adaptation triggering."""
        emergency_metrics = PerformanceMetrics(
            total_return=-0.20,  # 20% loss
            annualized_return=-0.40,
            excess_return=-0.15,
            sharpe_ratio=-1.0,
            sortino_ratio=-0.8,
            calmar_ratio=-0.5,
            max_drawdown=-0.15,  # 15% drawdown - triggers emergency
            volatility=0.35,
            downside_deviation=0.25,
            win_rate=0.25,
            profit_factor=0.5,
            avg_trade_duration=timedelta(hours=6),
            trades_count=200,
            avg_win=0.015,
            avg_loss=-0.025
        )
        
        # Should trigger emergency adaptation
        assert controller.should_adapt(emergency_metrics, "test_strategy")
    
    def test_should_adapt_insufficient_data(self, controller):
        """Test that adaptation is not triggered with insufficient data."""
        insufficient_data_metrics = PerformanceMetrics(
            total_return=-0.10,
            annualized_return=-0.20,
            excess_return=-0.08,
            sharpe_ratio=-0.8,
            sortino_ratio=-0.6,
            calmar_ratio=-0.4,
            max_drawdown=-0.12,
            volatility=0.30,
            downside_deviation=0.22,
            win_rate=0.30,
            profit_factor=0.7,
            avg_trade_duration=timedelta(hours=5),
            trades_count=50,  # Below minimum threshold
            avg_win=0.018,
            avg_loss=-0.020
        )
        
        # Should not adapt due to insufficient data
        assert not controller.should_adapt(insufficient_data_metrics, "test_strategy")
    
    def test_should_adapt_consistent_underperformance(self, controller):
        """Test detection of consistent underperformance."""
        underperforming_metrics = PerformanceMetrics(
            total_return=0.02,  # Positive return but low win rate
            annualized_return=0.05,
            excess_return=0.01,
            sharpe_ratio=0.2,
            sortino_ratio=0.3,
            calmar_ratio=0.1,
            max_drawdown=-0.08,
            volatility=0.20,
            downside_deviation=0.15,
            win_rate=0.35,  # Low win rate triggers adaptation
            profit_factor=1.1,
            avg_trade_duration=timedelta(hours=3),
            trades_count=100,  # Sufficient data
            avg_win=0.025,
            avg_loss=-0.015
        )
        
        # Should adapt due to consistent underperformance
        assert controller.should_adapt(underperforming_metrics, "test_strategy")
    
    def test_rate_limiting(self, controller, sample_performance_metrics):
        """Test that rate limiting prevents excessive adaptations."""
        # First adaptation should be allowed
        assert controller.should_adapt(sample_performance_metrics, "test_strategy")
        
        # Simulate recent adaptations
        now = datetime.now()
        controller.adaptation_timestamps.extend([
            now - timedelta(minutes=10),
            now - timedelta(minutes=20)
        ])
        
        # Should be blocked by hourly rate limit
        assert not controller.should_adapt(sample_performance_metrics, "test_strategy")
    
    def test_minimum_time_between_adaptations(self, controller, sample_performance_metrics):
        """Test minimum time between adaptations."""
        # Add a recent adaptation
        controller.adaptation_timestamps.append(datetime.now() - timedelta(minutes=15))
        
        # Should be blocked by minimum time requirement
        assert not controller.should_adapt(sample_performance_metrics, "test_strategy")
        
        # Add an older adaptation
        controller.adaptation_timestamps.clear()
        controller.adaptation_timestamps.append(datetime.now() - timedelta(minutes=45))
        
        # Should be allowed now
        assert controller.should_adapt(sample_performance_metrics, "test_strategy")


class TestAdaptationValidation:
    """Test adaptation validation logic."""
    
    def test_validate_confidence_requirements_large_change(self, controller):
        """Test that large changes require higher confidence."""
        large_change = {
            'parameters': {'stop_loss': 0.15},  # 15% change - large
            'confidence': 0.65  # Normal confidence
        }
        
        # Should fail due to insufficient confidence for large change
        assert not controller.validate_adaptation(large_change)
    
    def test_validate_confidence_requirements_recent_failures(self, controller):
        """Test that recent failures require higher confidence."""
        # Add recent failed adaptations
        for i in range(3):
            failed_adaptation = AdaptationEvent(
                event_id=f"failed_{i}",
                event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                trigger_reason="Test failure",
                changes_made={},
                expected_impact=0.01,
                timestamp=datetime.now() - timedelta(hours=i+1),
                success=False
            )
            controller.adaptation_history.append(failed_adaptation)
        
        normal_change = {
            'parameters': {'stop_loss': 0.05},
            'confidence': 0.65  # Normal confidence
        }
        
        # Should fail due to recent failures requiring higher confidence
        assert not controller.validate_adaptation(normal_change)
    
    def test_validate_emergency_adaptation(self, controller):
        """Test that emergency adaptations have lower confidence requirements."""
        emergency_change = {
            'parameters': {'stop_loss': 0.05},
            'confidence': 0.45,  # Below normal threshold
            'emergency': True
        }
        
        # Should pass due to emergency status
        result = controller.validate_adaptation(emergency_change)
        if not result:
            # Debug the validation failure
            confidence_result = controller._validate_confidence_requirements(emergency_change)
            print(f"Confidence validation result: {confidence_result}")
        assert result
    
    def test_validate_system_state_too_many_pending(self, controller):
        """Test validation failure when too many adaptations are pending."""
        # Add many pending adaptations
        for i in range(6):  # Exceeds limit of 5
            adaptation = AdaptationEvent(
                event_id=f"pending_{i}",
                event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                trigger_reason="Test pending",
                changes_made={},
                expected_impact=0.01
            )
            controller.pending_adaptations[adaptation.event_id] = adaptation
        
        valid_change = {
            'parameters': {'stop_loss': 0.02},
            'confidence': 0.8
        }
        
        # Should fail due to too many pending adaptations
        assert not controller.validate_adaptation(valid_change)
    
    def test_validate_adaptation_success(self, controller):
        """Test successful adaptation validation."""
        valid_changes = {
            'parameters': {'stop_loss': 0.01, 'take_profit': 0.02},
            'strategy_weights': {'momentum': 0.05, 'mean_reversion': -0.05},
            'confidence': 0.75
        }
        
        assert controller.validate_adaptation(valid_changes)
    
    def test_validate_adaptation_low_confidence(self, controller):
        """Test validation failure due to low confidence."""
        low_confidence_changes = {
            'parameters': {'stop_loss': 0.01},
            'confidence': 0.4  # Below threshold
        }
        
        assert not controller.validate_adaptation(low_confidence_changes)
    
    def test_validate_adaptation_excessive_parameter_change(self, controller):
        """Test validation failure due to excessive parameter changes."""
        excessive_changes = {
            'parameters': {'stop_loss': 0.5},  # 50% change exceeds limit
            'confidence': 0.8
        }
        
        assert not controller.validate_adaptation(excessive_changes)
    
    def test_validate_adaptation_excessive_weight_change(self, controller):
        """Test validation failure due to excessive strategy weight changes."""
        excessive_weight_changes = {
            'strategy_weights': {'momentum': 0.3},  # 30% change exceeds limit
            'confidence': 0.8
        }
        
        assert not controller.validate_adaptation(excessive_weight_changes)
    
    def test_validate_adaptation_conflicting_changes(self, controller, sample_adaptation_event):
        """Test validation failure due to conflicting adaptations."""
        # Add a pending adaptation
        controller.pending_adaptations[sample_adaptation_event.event_id] = sample_adaptation_event
        
        # Try to make conflicting changes
        conflicting_changes = {
            'strategy_weights': {'momentum': 0.05},  # Same strategy as pending
            'confidence': 0.8
        }
        
        # Mock the changes_made to include strategy_weights
        sample_adaptation_event.changes_made['strategy_weights'] = {'momentum': 0.03}
        
        assert not controller.validate_adaptation(conflicting_changes)


class TestAdaptationExecution:
    """Test adaptation execution and management."""
    
    def test_execute_adaptation_success(self, controller, sample_adaptation_event):
        """Test successful adaptation execution."""
        initial_history_length = len(controller.adaptation_history)
        
        result = controller.execute_adaptation(sample_adaptation_event)
        
        assert result is True
        assert len(controller.adaptation_history) == initial_history_length + 1
        assert sample_adaptation_event.event_id in controller.pending_adaptations
        assert sample_adaptation_event.event_id in controller.rollback_data
    
    def test_rollback_adaptation_success(self, controller, sample_adaptation_event):
        """Test successful adaptation rollback."""
        # First execute an adaptation
        controller.execute_adaptation(sample_adaptation_event)
        
        # Then rollback
        result = controller.rollback_adaptation(sample_adaptation_event.event_id)
        
        assert result is True
        assert sample_adaptation_event.event_id not in controller.pending_adaptations
        assert sample_adaptation_event.success is False
        assert sample_adaptation_event.rollback_available is False
    
    def test_rollback_adaptation_not_found(self, controller):
        """Test rollback failure when adaptation not found."""
        result = controller.rollback_adaptation("nonexistent_id")
        assert result is False
    
    def test_get_adaptation_history(self, controller):
        """Test retrieval of adaptation history."""
        # Add some test adaptations
        old_event = AdaptationEvent(
            event_id="old",
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Old adaptation",
            changes_made={},
            expected_impact=0.01,
            timestamp=datetime.now() - timedelta(hours=48)
        )
        
        recent_event = AdaptationEvent(
            event_id="recent",
            event_type=AdaptationType.STRATEGY_WEIGHT_CHANGE,
            trigger_reason="Recent adaptation",
            changes_made={},
            expected_impact=0.02,
            timestamp=datetime.now() - timedelta(hours=12)
        )
        
        controller.adaptation_history.extend([old_event, recent_event])
        
        # Get recent history (24 hours)
        recent_history = controller.get_adaptation_history(24)
        assert len(recent_history) == 1
        assert recent_history[0].event_id == "recent"
        
        # Get longer history (72 hours)
        longer_history = controller.get_adaptation_history(72)
        assert len(longer_history) == 2
    
    def test_set_adaptation_limits(self, controller):
        """Test setting adaptation limits."""
        new_limits = {
            'min_performance_threshold': -0.08,
            'max_adaptations_per_hour': 3,
            'unknown_limit': 'should_be_ignored'
        }
        
        controller.set_adaptation_limits(new_limits)
        
        assert controller.limits.min_performance_threshold == -0.08
        assert controller.limits.max_adaptations_per_hour == 3
        # Unknown limit should not cause errors
    
    def test_get_adaptation_rate(self, controller):
        """Test calculation of adaptation rate."""
        # Add some recent adaptations
        now = datetime.now()
        controller.adaptation_timestamps.extend([
            now - timedelta(hours=2),
            now - timedelta(hours=6),
            now - timedelta(hours=12),
            now - timedelta(hours=30)  # This one is outside 24h window
        ])
        
        rate = controller.get_adaptation_rate()
        assert rate == 3 / 24.0  # 3 adaptations in 24 hours


class TestAdaptationEvaluation:
    """Test adaptation evaluation and success measurement."""
    
    def test_evaluate_pending_adaptations(self, controller):
        """Test evaluation of pending adaptations."""
        # Create an adaptation that's due for evaluation
        adaptation_event = AdaptationEvent(
            event_id="test_eval",
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Test evaluation",
            changes_made={'parameters': {'test': 0.1}},
            expected_impact=0.02,
            timestamp=datetime.now() - timedelta(hours=25),  # Past evaluation period
            evaluation_period=timedelta(hours=24)
        )
        
        controller.pending_adaptations[adaptation_event.event_id] = adaptation_event
        
        # Mock the impact measurement
        with patch.object(controller, '_measure_adaptation_impact', return_value=0.03):
            controller.evaluate_pending_adaptations()
        
        # Check that adaptation was evaluated
        assert adaptation_event.actual_impact == 0.03
        assert adaptation_event.success is True
        assert adaptation_event.event_id not in controller.pending_adaptations
    
    def test_auto_rollback_poor_performance(self, controller):
        """Test automatic rollback of poorly performing adaptations."""
        # Create an adaptation with poor performance
        adaptation_event = AdaptationEvent(
            event_id="test_rollback",
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Test rollback",
            changes_made={'parameters': {'test': 0.1}},
            expected_impact=0.02,
            timestamp=datetime.now() - timedelta(hours=25),
            evaluation_period=timedelta(hours=24),
            auto_rollback_threshold=-0.05
        )
        
        controller.pending_adaptations[adaptation_event.event_id] = adaptation_event
        controller.rollback_data[adaptation_event.event_id] = {'test': 'rollback_data'}
        
        # Mock poor performance
        with patch.object(controller, '_measure_adaptation_impact', return_value=-0.08):
            with patch.object(controller, 'rollback_adaptation', return_value=True) as mock_rollback:
                controller.evaluate_pending_adaptations()
                mock_rollback.assert_called_once_with(adaptation_event.event_id)


class TestAdaptationLimits:
    """Test adaptation limits and constraints."""
    
    def test_adaptation_limits_initialization(self):
        """Test initialization of adaptation limits."""
        limits = AdaptationLimits(
            min_performance_threshold=-0.1,
            max_adaptations_per_hour=5
        )
        
        assert limits.min_performance_threshold == -0.1
        assert limits.max_adaptations_per_hour == 5
        assert limits.min_confidence_threshold == 0.6  # Default value
    
    def test_rate_limit_checking(self, controller):
        """Test internal rate limit checking."""
        # Test empty timestamps
        assert controller._check_rate_limits() is True
        
        # Add timestamps that exceed hourly limit
        now = datetime.now()
        controller.adaptation_timestamps.extend([
            now - timedelta(minutes=10),
            now - timedelta(minutes=20)
        ])
        
        # Should fail hourly limit (limit is 2, we have 2)
        controller.adaptation_timestamps.append(now - timedelta(minutes=5))
        assert controller._check_rate_limits() is False
    
    def test_parameter_change_validation(self, controller):
        """Test parameter change validation."""
        # Valid changes
        valid_changes = {'param1': 0.1, 'param2': -0.15}
        assert controller._validate_parameter_changes(valid_changes) is True
        
        # Invalid changes (exceed limit)
        invalid_changes = {'param1': 0.5}  # 50% exceeds 20% limit
        assert controller._validate_parameter_changes(invalid_changes) is False
    
    def test_strategy_weight_change_validation(self, controller):
        """Test strategy weight change validation."""
        # Valid changes
        valid_changes = {'strategy1': 0.05, 'strategy2': -0.08}
        assert controller._validate_strategy_weight_changes(valid_changes) is True
        
        # Invalid changes (exceed limit)
        invalid_changes = {'strategy1': 0.2}  # 20% exceeds 10% limit
        assert controller._validate_strategy_weight_changes(invalid_changes) is False


if __name__ == "__main__":
    pytest.main([__file__])