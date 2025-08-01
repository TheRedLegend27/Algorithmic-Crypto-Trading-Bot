"""
Real-time monitoring dashboard for the adaptive trading bot system.
Provides comprehensive monitoring of system health, performance, and adaptation activities.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict
from collections import defaultdict, deque
import threading
import time

from .interfaces import MonitoringInterface
from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, 
    AdaptationEvent, MLModelMetadata, StrategyAllocation
)
from .enums import RegimeType, AdaptationType, ModelType


class SystemHealthMonitor:
    """Monitors the health of all adaptive system components."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.component_status = {}
        self.last_heartbeat = {}
        self.error_counts = defaultdict(int)
        self.performance_metrics = {}
        self.alert_thresholds = {
            'component_timeout': 300,  # 5 minutes
            'error_rate_threshold': 0.1,  # 10% error rate
            'memory_threshold': 0.8,  # 80% memory usage
            'cpu_threshold': 0.9  # 90% CPU usage
        }
    
    def register_component(self, component_name: str, component_instance: Any) -> None:
        """Register a component for health monitoring."""
        self.component_status[component_name] = {
            'instance': component_instance,
            'status': 'active',
            'last_heartbeat': datetime.now(),
            'error_count': 0,
            'total_operations': 0,
            'avg_response_time': 0.0
        }
        self.logger.info(f"Registered component for monitoring: {component_name}")
    
    def update_component_heartbeat(self, component_name: str, 
                                 operation_time: Optional[float] = None) -> None:
        """Update component heartbeat and performance metrics."""
        if component_name in self.component_status:
            status = self.component_status[component_name]
            status['last_heartbeat'] = datetime.now()
            status['total_operations'] += 1
            
            if operation_time is not None:
                # Update rolling average response time
                current_avg = status['avg_response_time']
                total_ops = status['total_operations']
                status['avg_response_time'] = ((current_avg * (total_ops - 1)) + operation_time) / total_ops
    
    def record_component_error(self, component_name: str, error: Exception) -> None:
        """Record an error for a component."""
        if component_name in self.component_status:
            self.component_status[component_name]['error_count'] += 1
            self.error_counts[component_name] += 1
            self.logger.error(f"Error in component {component_name}: {str(error)}")
    
    def get_component_health(self) -> Dict[str, Any]:
        """Get health status of all components."""
        health_status = {}
        current_time = datetime.now()
        
        for component_name, status in self.component_status.items():
            time_since_heartbeat = (current_time - status['last_heartbeat']).total_seconds()
            error_rate = status['error_count'] / max(status['total_operations'], 1)
            
            health_status[component_name] = {
                'status': 'healthy' if time_since_heartbeat < self.alert_thresholds['component_timeout'] else 'unhealthy',
                'last_heartbeat': status['last_heartbeat'].isoformat(),
                'time_since_heartbeat': time_since_heartbeat,
                'error_rate': error_rate,
                'total_operations': status['total_operations'],
                'avg_response_time': status['avg_response_time'],
                'is_responsive': time_since_heartbeat < self.alert_thresholds['component_timeout'],
                'error_threshold_exceeded': error_rate > self.alert_thresholds['error_rate_threshold']
            }
        
        return health_status


class PerformanceTracker:
    """Tracks real-time performance metrics and trends."""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.performance_history = deque(maxlen=history_size)
        self.strategy_performance = defaultdict(lambda: deque(maxlen=history_size))
        self.regime_performance = defaultdict(lambda: deque(maxlen=history_size))
        self.current_metrics = {}
        self.logger = logging.getLogger(__name__)
    
    def update_performance(self, metrics: PerformanceMetrics, strategy_name: str = "overall") -> None:
        """Update performance metrics."""
        timestamp = datetime.now()
        performance_point = {
            'timestamp': timestamp,
            'metrics': asdict(metrics),
            'strategy': strategy_name
        }
        
        if strategy_name == "overall":
            self.performance_history.append(performance_point)
        else:
            self.strategy_performance[strategy_name].append(performance_point)
        
        self.current_metrics[strategy_name] = metrics
        self.logger.debug(f"Updated performance for {strategy_name}: {metrics.total_return:.4f}")
    
    def update_regime_performance(self, regime: RegimeType, performance: float) -> None:
        """Update performance for a specific market regime."""
        self.regime_performance[regime].append({
            'timestamp': datetime.now(),
            'performance': performance
        })
    
    def get_performance_trend(self, strategy_name: str = "overall", 
                           lookback_minutes: int = 60) -> Dict[str, Any]:
        """Get performance trend over specified time period."""
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        if strategy_name == "overall":
            history = self.performance_history
        else:
            history = self.strategy_performance.get(strategy_name, deque())
        
        recent_points = [p for p in history if p['timestamp'] >= cutoff_time]
        
        if len(recent_points) < 2:
            return {'trend': 'insufficient_data', 'change': 0.0, 'points': len(recent_points)}
        
        first_return = recent_points[0]['metrics']['total_return']
        last_return = recent_points[-1]['metrics']['total_return']
        change = last_return - first_return
        
        return {
            'trend': 'improving' if change > 0 else 'declining' if change < 0 else 'stable',
            'change': change,
            'change_percentage': (change / abs(first_return)) * 100 if first_return != 0 else 0,
            'points': len(recent_points),
            'timeframe_minutes': lookback_minutes
        }
    
    def get_current_performance(self) -> Dict[str, PerformanceMetrics]:
        """Get current performance metrics for all strategies."""
        return self.current_metrics.copy()


class AdaptationActivityMonitor:
    """Monitors adaptation activities and their effectiveness."""
    
    def __init__(self, history_size: int = 500):
        self.adaptation_history = deque(maxlen=history_size)
        self.pending_evaluations = {}
        self.adaptation_stats = defaultdict(int)
        self.logger = logging.getLogger(__name__)
    
    def record_adaptation(self, event: AdaptationEvent) -> None:
        """Record an adaptation event."""
        self.adaptation_history.append(event)
        self.adaptation_stats[event.event_type] += 1
        
        if event.rollback_available:
            self.pending_evaluations[event.event_id] = event
        
        self.logger.info(f"Recorded adaptation: {event.event_type} for {event.affected_strategies}")
    
    def update_adaptation_result(self, event_id: str, actual_impact: float, success: bool) -> None:
        """Update the result of an adaptation."""
        # Update in history
        for event in self.adaptation_history:
            if event.event_id == event_id:
                event.actual_impact = actual_impact
                event.success = success
                break
        
        # Remove from pending evaluations
        if event_id in self.pending_evaluations:
            del self.pending_evaluations[event_id]
        
        self.logger.info(f"Updated adaptation result {event_id}: impact={actual_impact:.4f}, success={success}")
    
    def get_recent_adaptations(self, hours_back: int = 24) -> List[AdaptationEvent]:
        """Get recent adaptation events."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        return [event for event in self.adaptation_history if event.timestamp >= cutoff_time]
    
    def get_adaptation_effectiveness(self) -> Dict[str, Any]:
        """Calculate adaptation effectiveness statistics."""
        if not self.adaptation_history:
            return {'total_adaptations': 0, 'success_rate': 0.0, 'avg_impact': 0.0}
        
        completed_adaptations = [e for e in self.adaptation_history if e.actual_impact is not None]
        successful_adaptations = [e for e in completed_adaptations if e.success]
        
        total_impact = sum(e.actual_impact for e in completed_adaptations)
        avg_impact = total_impact / len(completed_adaptations) if completed_adaptations else 0.0
        success_rate = len(successful_adaptations) / len(completed_adaptations) if completed_adaptations else 0.0
        
        return {
            'total_adaptations': len(self.adaptation_history),
            'completed_evaluations': len(completed_adaptations),
            'pending_evaluations': len(self.pending_evaluations),
            'success_rate': success_rate,
            'avg_impact': avg_impact,
            'successful_adaptations': len(successful_adaptations),
            'failed_adaptations': len(completed_adaptations) - len(successful_adaptations)
        }


class MarketRegimeMonitor:
    """Monitors market regime detection and changes."""
    
    def __init__(self, history_size: int = 1000):
        self.regime_history = defaultdict(lambda: deque(maxlen=history_size))
        self.current_regimes = {}
        self.regime_transitions = deque(maxlen=100)
        self.logger = logging.getLogger(__name__)
    
    def update_regime(self, pair: str, regime: MarketRegime) -> None:
        """Update market regime for a trading pair."""
        previous_regime = self.current_regimes.get(pair)
        self.current_regimes[pair] = regime
        self.regime_history[pair].append(regime)
        
        # Record regime transition
        if previous_regime and previous_regime.regime_type != regime.regime_type:
            transition = {
                'pair': pair,
                'from_regime': previous_regime.regime_type,
                'to_regime': regime.regime_type,
                'timestamp': regime.detected_at,
                'confidence': regime.confidence
            }
            self.regime_transitions.append(transition)
            self.logger.info(f"Regime transition for {pair}: {previous_regime.regime_type} -> {regime.regime_type}")
    
    def get_current_regimes(self) -> Dict[str, MarketRegime]:
        """Get current market regimes for all pairs."""
        return self.current_regimes.copy()
    
    def get_regime_stability(self, pair: str, lookback_minutes: int = 60) -> Dict[str, Any]:
        """Calculate regime stability over time period."""
        if pair not in self.regime_history:
            return {'stability': 'no_data', 'transitions': 0}
        
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        recent_regimes = [r for r in self.regime_history[pair] if r.detected_at >= cutoff_time]
        
        if len(recent_regimes) < 2:
            return {'stability': 'insufficient_data', 'transitions': 0}
        
        # Count regime changes
        transitions = 0
        for i in range(1, len(recent_regimes)):
            if recent_regimes[i].regime_type != recent_regimes[i-1].regime_type:
                transitions += 1
        
        stability_score = 1.0 - (transitions / len(recent_regimes))
        
        return {
            'stability': 'stable' if stability_score > 0.8 else 'moderate' if stability_score > 0.5 else 'unstable',
            'stability_score': stability_score,
            'transitions': transitions,
            'regime_count': len(recent_regimes),
            'timeframe_minutes': lookback_minutes
        }


class MonitoringDashboard(MonitoringInterface):
    """Main monitoring dashboard that coordinates all monitoring components."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.health_monitor = SystemHealthMonitor()
        self.performance_tracker = PerformanceTracker()
        self.adaptation_monitor = AdaptationActivityMonitor()
        self.regime_monitor = MarketRegimeMonitor()
        
        self.dashboard_data = {}
        self.update_interval = 30  # seconds
        self.is_running = False
        self.update_thread = None
        
        # System metrics
        self.system_start_time = datetime.now()
        self.total_signals_processed = 0
        self.total_adaptations = 0
        
        self.logger.info("Monitoring dashboard initialized")
    
    def start_monitoring(self) -> None:
        """Start the monitoring dashboard."""
        if self.is_running:
            return
        
        self.is_running = True
        self.update_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("Monitoring dashboard started")
    
    def stop_monitoring(self) -> None:
        """Stop the monitoring dashboard."""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        self.logger.info("Monitoring dashboard stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop that updates dashboard data."""
        while self.is_running:
            try:
                self._update_dashboard_data()
                time.sleep(self.update_interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(self.update_interval)
    
    def _update_dashboard_data(self) -> None:
        """Update all dashboard data."""
        self.dashboard_data = {
            'timestamp': datetime.now().isoformat(),
            'system_health': self.monitor_system_health(),
            'performance_metrics': self.get_performance_summary(),
            'adaptation_activity': self.get_adaptation_summary(),
            'market_conditions': self.get_market_conditions_summary(),
            'system_uptime': (datetime.now() - self.system_start_time).total_seconds(),
            'total_signals_processed': self.total_signals_processed,
            'total_adaptations': self.total_adaptations
        }
    
    def monitor_system_health(self) -> Dict[str, Any]:
        """Monitor overall system health."""
        component_health = self.health_monitor.get_component_health()
        
        # Calculate overall health score
        healthy_components = sum(1 for h in component_health.values() if h['status'] == 'healthy')
        total_components = len(component_health)
        health_score = healthy_components / total_components if total_components > 0 else 0.0
        
        return {
            'overall_status': 'healthy' if health_score > 0.8 else 'degraded' if health_score > 0.5 else 'unhealthy',
            'health_score': health_score,
            'healthy_components': healthy_components,
            'total_components': total_components,
            'component_details': component_health
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary across all strategies."""
        current_performance = self.performance_tracker.get_current_performance()
        
        summary = {
            'strategies': {},
            'overall_trend': self.performance_tracker.get_performance_trend(),
            'total_strategies': len(current_performance)
        }
        
        for strategy_name, metrics in current_performance.items():
            summary['strategies'][strategy_name] = {
                'total_return': metrics.total_return,
                'sharpe_ratio': metrics.sharpe_ratio,
                'max_drawdown': metrics.max_drawdown,
                'win_rate': metrics.win_rate,
                'trades_count': metrics.trades_count,
                'trend': self.performance_tracker.get_performance_trend(strategy_name)
            }
        
        return summary
    
    def get_adaptation_summary(self) -> Dict[str, Any]:
        """Get adaptation activity summary."""
        effectiveness = self.adaptation_monitor.get_adaptation_effectiveness()
        recent_adaptations = self.adaptation_monitor.get_recent_adaptations(hours_back=24)
        
        return {
            'effectiveness': effectiveness,
            'recent_count': len(recent_adaptations),
            'recent_adaptations': [
                {
                    'event_id': event.event_id,
                    'type': event.event_type.value,
                    'timestamp': event.timestamp.isoformat(),
                    'expected_impact': event.expected_impact,
                    'actual_impact': event.actual_impact,
                    'success': event.success
                }
                for event in recent_adaptations[-10:]  # Last 10 adaptations
            ]
        }
    
    def get_market_conditions_summary(self) -> Dict[str, Any]:
        """Get market conditions summary."""
        current_regimes = self.regime_monitor.get_current_regimes()
        
        regime_distribution = defaultdict(int)
        for regime in current_regimes.values():
            regime_distribution[regime.regime_type.value] += 1
        
        return {
            'active_pairs': len(current_regimes),
            'regime_distribution': dict(regime_distribution),
            'pair_regimes': {
                pair: {
                    'regime': regime.regime_type.value,
                    'confidence': regime.confidence,
                    'trend_strength': regime.trend_strength,
                    'volatility': regime.volatility_level,
                    'stability': self.regime_monitor.get_regime_stability(pair)
                }
                for pair, regime in current_regimes.items()
            }
        }
    
    def monitor_adaptation_performance(self) -> Dict[str, Any]:
        """Monitor performance of recent adaptations."""
        return self.adaptation_monitor.get_adaptation_effectiveness()
    
    def generate_alerts(self, alert_conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on conditions."""
        alerts = []
        
        # System health alerts
        health_data = self.monitor_system_health()
        if health_data['health_score'] < 0.8:
            alerts.append({
                'type': 'system_health',
                'severity': 'high' if health_data['health_score'] < 0.5 else 'medium',
                'message': f"System health degraded: {health_data['health_score']:.2f}",
                'timestamp': datetime.now().isoformat(),
                'data': health_data
            })
        
        # Performance alerts
        performance_data = self.get_performance_summary()
        overall_trend = performance_data['overall_trend']
        if overall_trend['trend'] == 'declining' and abs(overall_trend['change']) > 0.05:
            alerts.append({
                'type': 'performance_decline',
                'severity': 'high' if abs(overall_trend['change']) > 0.1 else 'medium',
                'message': f"Performance declining: {overall_trend['change']:.4f}",
                'timestamp': datetime.now().isoformat(),
                'data': overall_trend
            })
        
        return alerts
    
    def log_system_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log system events for monitoring."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'data': event_data
        }
        
        if event_type == 'signal_processed':
            self.total_signals_processed += 1
        elif event_type == 'adaptation_executed':
            self.total_adaptations += 1
        
        self.logger.info(f"System event: {event_type}", extra=log_entry)
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics."""
        return self.dashboard_data.copy() if self.dashboard_data else {}
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data for visualization."""
        return self.get_system_metrics()
    
    # Component registration methods
    def register_regime_detector(self, detector) -> None:
        """Register market regime detector for monitoring."""
        self.health_monitor.register_component('regime_detector', detector)
    
    def register_strategy_engine(self, engine) -> None:
        """Register adaptive strategy engine for monitoring."""
        self.health_monitor.register_component('strategy_engine', engine)
    
    def register_ml_engine(self, engine) -> None:
        """Register ML engine for monitoring."""
        self.health_monitor.register_component('ml_engine', engine)
    
    def register_parameter_optimizer(self, optimizer) -> None:
        """Register parameter optimizer for monitoring."""
        self.health_monitor.register_component('parameter_optimizer', optimizer)
    
    def register_performance_analyzer(self, analyzer) -> None:
        """Register performance analyzer for monitoring."""
        self.health_monitor.register_component('performance_analyzer', analyzer)
    
    def register_adaptation_controller(self, controller) -> None:
        """Register adaptation controller for monitoring."""
        self.health_monitor.register_component('adaptation_controller', controller)
    
    # Update methods for external components
    def update_regime(self, pair: str, regime: MarketRegime) -> None:
        """Update market regime information."""
        self.regime_monitor.update_regime(pair, regime)
        self.health_monitor.update_component_heartbeat('regime_detector')
    
    def update_performance(self, metrics: PerformanceMetrics, strategy_name: str = "overall") -> None:
        """Update performance metrics."""
        self.performance_tracker.update_performance(metrics, strategy_name)
        self.health_monitor.update_component_heartbeat('performance_analyzer')
    
    def record_adaptation(self, event: AdaptationEvent) -> None:
        """Record an adaptation event."""
        self.adaptation_monitor.record_adaptation(event)
        self.health_monitor.update_component_heartbeat('adaptation_controller')
    
    def update_adaptation_result(self, event_id: str, actual_impact: float, success: bool) -> None:
        """Update adaptation result."""
        self.adaptation_monitor.update_adaptation_result(event_id, actual_impact, success)