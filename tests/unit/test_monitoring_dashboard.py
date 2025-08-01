"""
Unit tests for the monitoring dashboard system.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time
import threading

from bot.adaptive.monitoring_dashboard import (
    SystemHealthMonitor, PerformanceTracker, AdaptationActivityMonitor,
    MarketRegimeMonitor, MonitoringDashboard
)
from bot.adaptive.data_models import (
    MarketRegime, PerformanceMetrics, AdaptationEvent, StrategyAllocation
)
from bot.adaptive.enums import RegimeType, AdaptationType, SignalStrength


class TestSystemHealthMonitor(unittest.TestCase):
    """Test system health monitoring functionality."""
    
    def setUp(self):
        self.health_monitor = SystemHealthMonitor()
    
    def test_register_component(self):
        """Test component registration."""
        mock_component = Mock()
        self.health_monitor.register_component('test_component', mock_component)
        
        self.assertIn('test_component', self.health_monitor.component_status)
        status = self.health_monitor.component_status['test_component']
        self.assertEqual(status['instance'], mock_component)
        self.assertEqual(status['status'], 'active')
        self.assertEqual(status['error_count'], 0)
    
    def test_update_component_heartbeat(self):
        """Test heartbeat updates."""
        mock_component = Mock()
        self.health_monitor.register_component('test_component', mock_component)
        
        # Update heartbeat with operation time
        self.health_monitor.update_component_heartbeat('test_component', 0.5)
        
        status = self.health_monitor.component_status['test_component']
        self.assertEqual(status['total_operations'], 1)
        self.assertEqual(status['avg_response_time'], 0.5)
    
    def test_record_component_error(self):
        """Test error recording."""
        mock_component = Mock()
        self.health_monitor.register_component('test_component', mock_component)
        
        error = Exception("Test error")
        self.health_monitor.record_component_error('test_component', error)
        
        status = self.health_monitor.component_status['test_component']
        self.assertEqual(status['error_count'], 1)
        self.assertEqual(self.health_monitor.error_counts['test_component'], 1)
    
    def test_get_component_health(self):
        """Test health status retrieval."""
        mock_component = Mock()
        self.health_monitor.register_component('test_component', mock_component)
        
        # Update some metrics
        self.health_monitor.update_component_heartbeat('test_component', 0.3)
        self.health_monitor.update_component_heartbeat('test_component', 0.7)
        
        health_status = self.health_monitor.get_component_health()
        
        self.assertIn('test_component', health_status)
        component_health = health_status['test_component']
        self.assertEqual(component_health['status'], 'healthy')
        self.assertEqual(component_health['total_operations'], 2)
        self.assertEqual(component_health['avg_response_time'], 0.5)
        self.assertFalse(component_health['error_threshold_exceeded'])
    
    def test_unhealthy_component_detection(self):
        """Test detection of unhealthy components."""
        mock_component = Mock()
        self.health_monitor.register_component('test_component', mock_component)
        
        # Simulate old heartbeat
        old_time = datetime.now() - timedelta(minutes=10)
        self.health_monitor.component_status['test_component']['last_heartbeat'] = old_time
        
        health_status = self.health_monitor.get_component_health()
        component_health = health_status['test_component']
        
        self.assertEqual(component_health['status'], 'unhealthy')
        self.assertFalse(component_health['is_responsive'])


class TestPerformanceTracker(unittest.TestCase):
    """Test performance tracking functionality."""
    
    def setUp(self):
        self.performance_tracker = PerformanceTracker(history_size=100)
    
    def create_test_metrics(self, total_return: float = 0.05) -> PerformanceMetrics:
        """Create test performance metrics."""
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=total_return * 12,
            excess_return=total_return - 0.02,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=1.2,
            max_drawdown=-0.03,
            volatility=0.15,
            downside_deviation=0.08,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=50,
            avg_win=0.02,
            avg_loss=-0.015
        )
    
    def test_update_performance(self):
        """Test performance metric updates."""
        metrics = self.create_test_metrics()
        self.performance_tracker.update_performance(metrics, "test_strategy")
        
        current_metrics = self.performance_tracker.get_current_performance()
        self.assertIn("test_strategy", current_metrics)
        self.assertEqual(current_metrics["test_strategy"].total_return, 0.05)
    
    def test_performance_trend_calculation(self):
        """Test performance trend calculation."""
        # Add multiple performance points
        for i in range(5):
            metrics = self.create_test_metrics(total_return=0.01 * (i + 1))
            self.performance_tracker.update_performance(metrics, "test_strategy")
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        trend = self.performance_tracker.get_performance_trend("test_strategy", lookback_minutes=1)
        
        self.assertEqual(trend['trend'], 'improving')
        self.assertGreater(trend['change'], 0)
        self.assertEqual(trend['points'], 5)
    
    def test_regime_performance_update(self):
        """Test regime-specific performance updates."""
        self.performance_tracker.update_regime_performance(RegimeType.TRENDING_BULL, 0.08)
        self.performance_tracker.update_regime_performance(RegimeType.RANGING, 0.03)
        
        self.assertEqual(len(self.performance_tracker.regime_performance), 2)
        self.assertIn(RegimeType.TRENDING_BULL, self.performance_tracker.regime_performance)
    
    def test_insufficient_data_trend(self):
        """Test trend calculation with insufficient data."""
        metrics = self.create_test_metrics()
        self.performance_tracker.update_performance(metrics, "test_strategy")
        
        trend = self.performance_tracker.get_performance_trend("test_strategy")
        self.assertEqual(trend['trend'], 'insufficient_data')
        self.assertEqual(trend['change'], 0.0)


class TestAdaptationActivityMonitor(unittest.TestCase):
    """Test adaptation activity monitoring."""
    
    def setUp(self):
        self.adaptation_monitor = AdaptationActivityMonitor(history_size=100)
    
    def create_test_adaptation_event(self, event_id: str = "test_event") -> AdaptationEvent:
        """Create test adaptation event."""
        return AdaptationEvent(
            event_id=event_id,
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Performance degradation",
            changes_made={"param1": 0.5, "param2": 1.2},
            expected_impact=0.03,
            affected_strategies=["strategy1"],
            affected_pairs=["BTC/USD"]
        )
    
    def test_record_adaptation(self):
        """Test adaptation event recording."""
        event = self.create_test_adaptation_event()
        self.adaptation_monitor.record_adaptation(event)
        
        self.assertEqual(len(self.adaptation_monitor.adaptation_history), 1)
        self.assertIn(event.event_id, self.adaptation_monitor.pending_evaluations)
        self.assertEqual(self.adaptation_monitor.adaptation_stats[AdaptationType.PARAMETER_OPTIMIZATION], 1)
    
    def test_update_adaptation_result(self):
        """Test updating adaptation results."""
        event = self.create_test_adaptation_event()
        self.adaptation_monitor.record_adaptation(event)
        
        # Update result
        self.adaptation_monitor.update_adaptation_result("test_event", 0.025, True)
        
        # Check that event was updated
        updated_event = list(self.adaptation_monitor.adaptation_history)[0]
        self.assertEqual(updated_event.actual_impact, 0.025)
        self.assertTrue(updated_event.success)
        self.assertNotIn("test_event", self.adaptation_monitor.pending_evaluations)
    
    def test_get_recent_adaptations(self):
        """Test retrieval of recent adaptations."""
        # Create events with different timestamps
        for i in range(3):
            event = self.create_test_adaptation_event(f"event_{i}")
            event.timestamp = datetime.now() - timedelta(hours=i)
            self.adaptation_monitor.record_adaptation(event)
        
        recent = self.adaptation_monitor.get_recent_adaptations(hours_back=2)
        self.assertEqual(len(recent), 2)  # Only events within 2 hours
    
    def test_adaptation_effectiveness_calculation(self):
        """Test adaptation effectiveness statistics."""
        # Create and record multiple events
        for i in range(5):
            event = self.create_test_adaptation_event(f"event_{i}")
            self.adaptation_monitor.record_adaptation(event)
            
            # Update some with results
            if i < 3:
                success = i < 2  # First 2 successful, 3rd failed
                impact = 0.02 if success else -0.01
                self.adaptation_monitor.update_adaptation_result(f"event_{i}", impact, success)
        
        effectiveness = self.adaptation_monitor.get_adaptation_effectiveness()
        
        self.assertEqual(effectiveness['total_adaptations'], 5)
        self.assertEqual(effectiveness['completed_evaluations'], 3)
        self.assertEqual(effectiveness['pending_evaluations'], 2)
        self.assertEqual(effectiveness['successful_adaptations'], 2)
        self.assertEqual(effectiveness['failed_adaptations'], 1)
        self.assertAlmostEqual(effectiveness['success_rate'], 2/3, places=2)


class TestMarketRegimeMonitor(unittest.TestCase):
    """Test market regime monitoring."""
    
    def setUp(self):
        self.regime_monitor = MarketRegimeMonitor(history_size=100)
    
    def create_test_regime(self, regime_type: RegimeType = RegimeType.TRENDING_BULL) -> MarketRegime:
        """Create test market regime."""
        return MarketRegime(
            regime_type=regime_type,
            confidence=0.85,
            volatility_level=0.3,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now(),
            supporting_indicators={"rsi": 65, "macd": 0.5}
        )
    
    def test_update_regime(self):
        """Test regime updates."""
        regime = self.create_test_regime()
        self.regime_monitor.update_regime("BTC/USD", regime)
        
        current_regimes = self.regime_monitor.get_current_regimes()
        self.assertIn("BTC/USD", current_regimes)
        self.assertEqual(current_regimes["BTC/USD"].regime_type, RegimeType.TRENDING_BULL)
    
    def test_regime_transition_detection(self):
        """Test detection of regime transitions."""
        # Initial regime
        regime1 = self.create_test_regime(RegimeType.TRENDING_BULL)
        self.regime_monitor.update_regime("BTC/USD", regime1)
        
        # Transition to different regime
        regime2 = self.create_test_regime(RegimeType.RANGING)
        self.regime_monitor.update_regime("BTC/USD", regime2)
        
        self.assertEqual(len(self.regime_monitor.regime_transitions), 1)
        transition = self.regime_monitor.regime_transitions[0]
        self.assertEqual(transition['from_regime'], RegimeType.TRENDING_BULL)
        self.assertEqual(transition['to_regime'], RegimeType.RANGING)
    
    def test_regime_stability_calculation(self):
        """Test regime stability calculation."""
        # Add multiple regimes with same type (stable)
        for i in range(5):
            regime = self.create_test_regime(RegimeType.TRENDING_BULL)
            regime.detected_at = datetime.now() - timedelta(minutes=i)
            self.regime_monitor.update_regime("BTC/USD", regime)
        
        stability = self.regime_monitor.get_regime_stability("BTC/USD", lookback_minutes=10)
        
        self.assertEqual(stability['stability'], 'stable')
        self.assertEqual(stability['transitions'], 0)
        self.assertGreater(stability['stability_score'], 0.8)
    
    def test_regime_instability_detection(self):
        """Test detection of regime instability."""
        # Alternate between different regimes
        regimes = [RegimeType.TRENDING_BULL, RegimeType.RANGING, RegimeType.TRENDING_BULL, RegimeType.RANGING]
        
        for i, regime_type in enumerate(regimes):
            regime = self.create_test_regime(regime_type)
            regime.detected_at = datetime.now() - timedelta(minutes=i)
            self.regime_monitor.update_regime("BTC/USD", regime)
        
        stability = self.regime_monitor.get_regime_stability("BTC/USD", lookback_minutes=10)
        
        self.assertEqual(stability['stability'], 'unstable')
        self.assertEqual(stability['transitions'], 3)
        self.assertLess(stability['stability_score'], 0.5)


class TestMonitoringDashboard(unittest.TestCase):
    """Test the main monitoring dashboard."""
    
    def setUp(self):
        self.dashboard = MonitoringDashboard()
    
    def test_dashboard_initialization(self):
        """Test dashboard initialization."""
        self.assertIsNotNone(self.dashboard.health_monitor)
        self.assertIsNotNone(self.dashboard.performance_tracker)
        self.assertIsNotNone(self.dashboard.adaptation_monitor)
        self.assertIsNotNone(self.dashboard.regime_monitor)
        self.assertFalse(self.dashboard.is_running)
    
    def test_component_registration(self):
        """Test component registration methods."""
        mock_detector = Mock()
        mock_engine = Mock()
        
        self.dashboard.register_regime_detector(mock_detector)
        self.dashboard.register_strategy_engine(mock_engine)
        
        self.assertIn('regime_detector', self.dashboard.health_monitor.component_status)
        self.assertIn('strategy_engine', self.dashboard.health_monitor.component_status)
    
    def test_system_health_monitoring(self):
        """Test system health monitoring."""
        # Register some components
        self.dashboard.register_regime_detector(Mock())
        self.dashboard.register_strategy_engine(Mock())
        
        health_data = self.dashboard.monitor_system_health()
        
        self.assertIn('overall_status', health_data)
        self.assertIn('health_score', health_data)
        self.assertIn('component_details', health_data)
        self.assertEqual(health_data['total_components'], 2)
    
    def test_performance_summary(self):
        """Test performance summary generation."""
        # Add some performance data
        metrics = PerformanceMetrics(
            total_return=0.05,
            annualized_return=0.6,
            excess_return=0.03,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=1.2,
            max_drawdown=-0.03,
            volatility=0.15,
            downside_deviation=0.08,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=50,
            avg_win=0.02,
            avg_loss=-0.015
        )
        
        self.dashboard.update_performance(metrics, "test_strategy")
        
        summary = self.dashboard.get_performance_summary()
        
        self.assertIn('strategies', summary)
        self.assertIn('overall_trend', summary)
        self.assertIn('test_strategy', summary['strategies'])
        self.assertEqual(summary['total_strategies'], 1)
    
    def test_adaptation_summary(self):
        """Test adaptation summary generation."""
        # Create and record adaptation event
        event = AdaptationEvent(
            event_id="test_adaptation",
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Test trigger",
            changes_made={"param1": 0.5},
            expected_impact=0.02,
            affected_strategies=["strategy1"]
        )
        
        self.dashboard.record_adaptation(event)
        
        summary = self.dashboard.get_adaptation_summary()
        
        self.assertIn('effectiveness', summary)
        self.assertIn('recent_count', summary)
        self.assertIn('recent_adaptations', summary)
        self.assertEqual(summary['recent_count'], 1)
    
    def test_market_conditions_summary(self):
        """Test market conditions summary."""
        # Add regime data
        regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.85,
            volatility_level=0.3,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now()
        )
        
        self.dashboard.update_regime("BTC/USD", regime)
        
        summary = self.dashboard.get_market_conditions_summary()
        
        self.assertIn('active_pairs', summary)
        self.assertIn('regime_distribution', summary)
        self.assertIn('pair_regimes', summary)
        self.assertEqual(summary['active_pairs'], 1)
        self.assertIn('BTC/USD', summary['pair_regimes'])
    
    def test_alert_generation(self):
        """Test alert generation."""
        # Create conditions that should trigger alerts
        # Register unhealthy component
        mock_component = Mock()
        self.dashboard.register_regime_detector(mock_component)
        
        # Make component appear unhealthy
        old_time = datetime.now() - timedelta(minutes=10)
        self.dashboard.health_monitor.component_status['regime_detector']['last_heartbeat'] = old_time
        
        alerts = self.dashboard.generate_alerts({})
        
        # Should generate system health alert
        health_alerts = [a for a in alerts if a['type'] == 'system_health']
        self.assertGreater(len(health_alerts), 0)
    
    def test_system_event_logging(self):
        """Test system event logging."""
        initial_signals = self.dashboard.total_signals_processed
        initial_adaptations = self.dashboard.total_adaptations
        
        self.dashboard.log_system_event('signal_processed', {'pair': 'BTC/USD'})
        self.dashboard.log_system_event('adaptation_executed', {'type': 'parameter_optimization'})
        
        self.assertEqual(self.dashboard.total_signals_processed, initial_signals + 1)
        self.assertEqual(self.dashboard.total_adaptations, initial_adaptations + 1)
    
    @patch('time.sleep')
    def test_monitoring_loop_start_stop(self, mock_sleep):
        """Test starting and stopping the monitoring loop."""
        # Mock sleep to prevent actual delays in test
        mock_sleep.return_value = None
        
        self.assertFalse(self.dashboard.is_running)
        
        # Start monitoring
        self.dashboard.start_monitoring()
        self.assertTrue(self.dashboard.is_running)
        self.assertIsNotNone(self.dashboard.update_thread)
        
        # Stop monitoring
        self.dashboard.stop_monitoring()
        self.assertFalse(self.dashboard.is_running)
    
    def test_dashboard_data_structure(self):
        """Test the structure of dashboard data."""
        # Add some test data
        self.dashboard.register_regime_detector(Mock())
        
        metrics = PerformanceMetrics(
            total_return=0.05,
            annualized_return=0.6,
            excess_return=0.03,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=1.2,
            max_drawdown=-0.03,
            volatility=0.15,
            downside_deviation=0.08,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=50,
            avg_win=0.02,
            avg_loss=-0.015
        )
        self.dashboard.update_performance(metrics)
        
        # Update dashboard data
        self.dashboard._update_dashboard_data()
        
        data = self.dashboard.get_dashboard_data()
        
        # Check required fields
        required_fields = [
            'timestamp', 'system_health', 'performance_metrics',
            'adaptation_activity', 'market_conditions', 'system_uptime',
            'total_signals_processed', 'total_adaptations'
        ]
        
        for field in required_fields:
            self.assertIn(field, data)


if __name__ == '__main__':
    unittest.main()