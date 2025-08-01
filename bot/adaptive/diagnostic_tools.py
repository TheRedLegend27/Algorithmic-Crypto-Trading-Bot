"""
Diagnostic and debugging tools for the adaptive trading bot system.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import psutil
import threading
import time

from .manual_controls import ManualControlSystem, DiagnosticInfo
from .adaptive_config import AdaptiveConfigManager
from .data_models import PerformanceMetrics, AdaptationEvent
from .enums import RegimeType


logger = logging.getLogger(__name__)


@dataclass
class SystemHealthReport:
    """Comprehensive system health report."""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # System resources
    cpu_usage_pct: float = 0.0
    memory_usage_mb: float = 0.0
    memory_usage_pct: float = 0.0
    disk_usage_pct: float = 0.0
    
    # Component health
    component_status: Dict[str, str] = field(default_factory=dict)
    component_errors: Dict[str, List[str]] = field(default_factory=dict)
    
    # Configuration status
    config_valid: bool = True
    config_errors: List[str] = field(default_factory=list)
    
    # Control system status
    active_overrides: int = 0
    emergency_stop_active: bool = False
    adaptations_paused: bool = False
    
    # Performance indicators
    recent_performance: Optional[PerformanceMetrics] = None
    performance_alerts: List[str] = field(default_factory=list)
    
    # Data integrity
    data_integrity_score: float = 1.0
    data_issues: List[str] = field(default_factory=list)
    
    # Overall health score (0.0 to 1.0)
    overall_health_score: float = 1.0
    health_status: str = "healthy"  # healthy, warning, critical
    
    def calculate_health_score(self):
        """Calculate overall health score based on various factors."""
        score = 1.0
        
        # Resource usage penalties
        if self.cpu_usage_pct > 80:
            score -= 0.2
        elif self.cpu_usage_pct > 60:
            score -= 0.1
        
        if self.memory_usage_pct > 90:
            score -= 0.3
        elif self.memory_usage_pct > 70:
            score -= 0.1
        
        # Component health penalties
        failed_components = sum(1 for status in self.component_status.values() if status == "failed")
        if failed_components > 0:
            score -= failed_components * 0.2
        
        # Configuration penalties
        if not self.config_valid:
            score -= 0.3
        
        # Control system penalties
        if self.emergency_stop_active:
            score -= 0.4
        
        # Data integrity penalties
        score *= self.data_integrity_score
        
        self.overall_health_score = max(0.0, score)
        
        # Determine health status
        if self.overall_health_score >= 0.8:
            self.health_status = "healthy"
        elif self.overall_health_score >= 0.5:
            self.health_status = "warning"
        else:
            self.health_status = "critical"


@dataclass
class PerformanceAnalysisReport:
    """Detailed performance analysis report."""
    timestamp: datetime = field(default_factory=datetime.now)
    analysis_period: timedelta = field(default=timedelta(days=7))
    
    # Performance metrics
    current_performance: Optional[PerformanceMetrics] = None
    historical_performance: List[PerformanceMetrics] = field(default_factory=list)
    
    # Performance trends
    return_trend: str = "stable"  # improving, stable, declining
    risk_trend: str = "stable"
    volatility_trend: str = "stable"
    
    # Strategy analysis
    strategy_performance: Dict[str, PerformanceMetrics] = field(default_factory=dict)
    best_performing_strategy: Optional[str] = None
    worst_performing_strategy: Optional[str] = None
    
    # Regime analysis
    regime_performance: Dict[RegimeType, PerformanceMetrics] = field(default_factory=dict)
    current_regime: Optional[RegimeType] = None
    regime_stability: float = 0.0
    
    # Adaptation analysis
    recent_adaptations: List[AdaptationEvent] = field(default_factory=list)
    successful_adaptations: int = 0
    failed_adaptations: int = 0
    adaptation_success_rate: float = 0.0
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def analyze_trends(self):
        """Analyze performance trends."""
        if len(self.historical_performance) < 2:
            return
        
        # Analyze return trend
        recent_returns = [p.total_return for p in self.historical_performance[-5:]]
        if len(recent_returns) >= 2:
            if recent_returns[-1] > recent_returns[0] * 1.05:
                self.return_trend = "improving"
            elif recent_returns[-1] < recent_returns[0] * 0.95:
                self.return_trend = "declining"
        
        # Analyze risk trend
        recent_drawdowns = [p.max_drawdown for p in self.historical_performance[-5:]]
        if len(recent_drawdowns) >= 2:
            if recent_drawdowns[-1] > recent_drawdowns[0] * 1.2:
                self.risk_trend = "increasing"
            elif recent_drawdowns[-1] < recent_drawdowns[0] * 0.8:
                self.risk_trend = "decreasing"
    
    def generate_recommendations(self):
        """Generate recommendations based on analysis."""
        self.recommendations.clear()
        self.warnings.clear()
        
        if self.current_performance:
            # Performance-based recommendations
            if self.current_performance.sharpe_ratio < 0.5:
                self.recommendations.append("Consider reducing position sizes due to low risk-adjusted returns")
            
            if self.current_performance.max_drawdown > 0.15:
                self.warnings.append("High drawdown detected - review risk management parameters")
            
            if self.current_performance.win_rate < 0.4:
                self.recommendations.append("Low win rate - consider adjusting entry criteria")
        
        # Trend-based recommendations
        if self.return_trend == "declining":
            self.recommendations.append("Performance declining - consider pausing adaptations temporarily")
        
        if self.risk_trend == "increasing":
            self.warnings.append("Risk increasing - review position sizing and stop-loss settings")
        
        # Adaptation-based recommendations
        if self.adaptation_success_rate < 0.5:
            self.recommendations.append("Low adaptation success rate - review optimization parameters")


class DiagnosticToolkit:
    """Comprehensive diagnostic and debugging toolkit."""
    
    def __init__(self, config_manager: AdaptiveConfigManager, 
                 control_system: ManualControlSystem):
        """
        Initialize the diagnostic toolkit.
        
        Args:
            config_manager: Configuration manager instance
            control_system: Manual control system instance
        """
        self.config_manager = config_manager
        self.control_system = control_system
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_thread = None
        self._monitoring_interval = 30  # seconds
        
        # Health history
        self._health_history: List[SystemHealthReport] = []
        self._max_history_size = 1000
        
        logger.info("Initialized DiagnosticToolkit")
    
    def generate_health_report(self) -> SystemHealthReport:
        """Generate a comprehensive system health report."""
        report = SystemHealthReport()
        
        # System resources
        try:
            report.cpu_usage_pct = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            report.memory_usage_mb = memory.used / (1024 * 1024)
            report.memory_usage_pct = memory.percent
            disk = psutil.disk_usage('/')
            report.disk_usage_pct = disk.percent
        except Exception as e:
            logger.error(f"Error getting system resources: {str(e)}")
        
        # Component health (would be populated by actual components)
        report.component_status = {
            "ml_engine": "unknown",
            "regime_detector": "unknown",
            "strategy_engine": "unknown",
            "parameter_optimizer": "unknown",
            "adaptation_controller": "unknown",
            "risk_manager": "unknown",
            "data_manager": "unknown"
        }
        
        # Configuration status
        try:
            report.config_valid = self.config_manager.validate_current_config()
            if not report.config_valid:
                report.config_errors.append("Configuration validation failed")
        except Exception as e:
            report.config_valid = False
            report.config_errors.append(f"Configuration error: {str(e)}")
        
        # Control system status
        try:
            active_overrides = self.control_system.get_active_overrides()
            report.active_overrides = len(active_overrides)
            
            emergency_status = self.control_system.get_emergency_stop_status()
            report.emergency_stop_active = emergency_status.is_active
            
            # Check for adaptation pause overrides
            report.adaptations_paused = any(
                o.override_type.value == "adaptation_pause" and o.is_active
                for o in active_overrides
            )
        except Exception as e:
            logger.error(f"Error getting control system status: {str(e)}")
        
        # Calculate overall health score
        report.calculate_health_score()
        
        return report
    
    def generate_performance_analysis(self, 
                                    analysis_period: timedelta = timedelta(days=7)) -> PerformanceAnalysisReport:
        """Generate a detailed performance analysis report."""
        report = PerformanceAnalysisReport(analysis_period=analysis_period)
        
        # This would be populated with actual performance data
        # For now, we'll create a placeholder structure
        
        # Analyze trends
        report.analyze_trends()
        
        # Generate recommendations
        report.generate_recommendations()
        
        return report
    
    def run_system_diagnostics(self) -> Dict[str, Any]:
        """Run comprehensive system diagnostics."""
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "health_report": self.generate_health_report(),
            "performance_analysis": self.generate_performance_analysis(),
            "configuration_summary": self.config_manager.get_config_summary(),
            "control_system_diagnostics": self.control_system.get_system_diagnostics()
        }
        
        return diagnostics
    
    def check_data_integrity(self) -> Dict[str, Any]:
        """Check data integrity across the system."""
        integrity_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_score": 1.0,
            "issues": [],
            "checks_performed": []
        }
        
        # Configuration integrity
        try:
            config = self.config_manager.get_config()
            if config and config.validate():
                integrity_report["checks_performed"].append("Configuration validation: PASSED")
            else:
                integrity_report["issues"].append("Configuration validation failed")
                integrity_report["overall_score"] -= 0.2
        except Exception as e:
            integrity_report["issues"].append(f"Configuration check error: {str(e)}")
            integrity_report["overall_score"] -= 0.3
        
        # Control system integrity
        try:
            active_overrides = self.control_system.get_active_overrides()
            expired_overrides = [o for o in active_overrides if not o.is_valid()]
            if expired_overrides:
                integrity_report["issues"].append(f"Found {len(expired_overrides)} expired active overrides")
                integrity_report["overall_score"] -= 0.1
            
            integrity_report["checks_performed"].append("Control system validation: PASSED")
        except Exception as e:
            integrity_report["issues"].append(f"Control system check error: {str(e)}")
            integrity_report["overall_score"] -= 0.2
        
        # Ensure score doesn't go below 0
        integrity_report["overall_score"] = max(0.0, integrity_report["overall_score"])
        
        return integrity_report
    
    def start_continuous_monitoring(self, interval_seconds: int = 30):
        """Start continuous system monitoring."""
        if self._monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self._monitoring_interval = interval_seconds
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
        logger.info(f"Started continuous monitoring with {interval_seconds}s interval")
    
    def stop_continuous_monitoring(self):
        """Stop continuous system monitoring."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        
        logger.info("Stopped continuous monitoring")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Generate health report
                health_report = self.generate_health_report()
                
                # Store in history
                self._health_history.append(health_report)
                if len(self._health_history) > self._max_history_size:
                    self._health_history.pop(0)
                
                # Check for critical issues
                if health_report.health_status == "critical":
                    logger.critical(f"Critical system health detected: score={health_report.overall_health_score}")
                elif health_report.health_status == "warning":
                    logger.warning(f"System health warning: score={health_report.overall_health_score}")
                
                # Sleep until next check
                time.sleep(self._monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(self._monitoring_interval)
    
    def get_health_history(self, hours: int = 24) -> List[SystemHealthReport]:
        """Get health history for the specified number of hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [report for report in self._health_history if report.timestamp >= cutoff_time]
    
    def export_diagnostics(self, file_path: str) -> bool:
        """Export comprehensive diagnostics to file."""
        try:
            diagnostics = self.run_system_diagnostics()
            
            # Convert dataclasses to dictionaries for JSON serialization
            def convert_for_json(obj):
                if hasattr(obj, '__dict__'):
                    return obj.__dict__
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, timedelta):
                    return obj.total_seconds()
                elif hasattr(obj, 'value'):  # Enum
                    return obj.value
                return str(obj)
            
            with open(file_path, 'w') as f:
                json.dump(diagnostics, f, indent=2, default=convert_for_json)
            
            logger.info(f"Exported diagnostics to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting diagnostics: {str(e)}")
            return False
    
    def get_troubleshooting_guide(self, issue_type: str) -> List[str]:
        """Get troubleshooting steps for common issues."""
        guides = {
            "high_cpu": [
                "Check for runaway processes or infinite loops",
                "Review ML model training frequency and complexity",
                "Consider reducing optimization frequency",
                "Check for memory leaks causing excessive garbage collection"
            ],
            "high_memory": [
                "Check for memory leaks in data caching",
                "Review historical data retention settings",
                "Clear unnecessary cached data",
                "Restart the system if memory usage is critical"
            ],
            "poor_performance": [
                "Review recent adaptations and their impact",
                "Check if market conditions have changed significantly",
                "Verify strategy parameters are within reasonable bounds",
                "Consider rolling back recent parameter changes"
            ],
            "adaptation_failures": [
                "Check optimization algorithm convergence settings",
                "Verify sufficient historical data for optimization",
                "Review parameter bounds and constraints",
                "Check for data quality issues"
            ],
            "emergency_stop": [
                "Identify the trigger reason for emergency stop",
                "Review recent trading activity and losses",
                "Check system logs for errors or anomalies",
                "Verify all systems are functioning before reset"
            ]
        }
        
        return guides.get(issue_type, ["No specific guide available for this issue type"])
    
    def suggest_optimizations(self) -> List[str]:
        """Suggest system optimizations based on current state."""
        suggestions = []
        
        try:
            health_report = self.generate_health_report()
            
            # Resource-based suggestions
            if health_report.cpu_usage_pct > 70:
                suggestions.append("Consider reducing ML model training frequency")
                suggestions.append("Optimize parameter optimization algorithms")
            
            if health_report.memory_usage_pct > 80:
                suggestions.append("Reduce historical data retention period")
                suggestions.append("Implement more aggressive data caching cleanup")
            
            # Configuration-based suggestions
            config = self.config_manager.get_config()
            if config:
                if config.ml_engine.retrain_frequency_hours < 6:
                    suggestions.append("Consider increasing ML model retrain frequency to reduce CPU load")
                
                if config.parameter_optimization.optimization_frequency_hours < 12:
                    suggestions.append("Consider reducing parameter optimization frequency")
            
            # Control system suggestions
            active_overrides = self.control_system.get_active_overrides()
            if len(active_overrides) > 5:
                suggestions.append("Review and clean up unnecessary manual overrides")
            
        except Exception as e:
            logger.error(f"Error generating optimization suggestions: {str(e)}")
            suggestions.append("Unable to generate suggestions due to system error")
        
        return suggestions