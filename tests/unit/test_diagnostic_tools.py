"""
Unit tests for the diagnostic tools system.
"""
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from bot.adaptive.diagnostic_tools import (
    SystemHealthReport, PerformanceAnalysisReport, DiagnosticToolkit
)
from bot.adaptive.adaptive_config import AdaptiveConfigManager
from bot.adaptive.manual_controls import ManualControlSystem
from bot.adaptive.enums import RegimeType


class TestSystemHealthReport:
    """Test SystemHealthReport functionality."""
    
    def test_health_report_creation(self):
        """Test creating a health report."""
        report = SystemHealthReport()
        
        assert report.timestamp is not None
        assert report.cpu_usage_pct == 0.0
        assert report.memory_usage_mb == 0.0
        assert report.overall_health_score == 1.0
        assert report.health_status == "healthy"
    
    def test_health_score_calculation(self):
        """Test health score calculation."""
        report = SystemHealthReport()
        
        # Test healthy system
        report.cpu_usage_pct = 50.0
        report.memory_usage_pct = 60.0
        report.config_valid = True
        report.emergency_stop_active = False
        report.data_integrity_score = 1.0
        
        report.calculate_health_score()
        assert report.overall_health_score == 1.0
        assert report.health_status == "healthy"
        
        # Test system with high CPU usage
        report.cpu_usage_pct = 85.0
        report.calculate_health_score()
        assert report.overall_health_score == 0.8
        assert report.health_status == "healthy"
        
        # Test system with high memory usage
        report.memory_usage_pct = 95.0
        report.calculate_health_score()
        assert report.overall_health_score < 0.8
        assert report.health_status == "warning"
        
        # Test system with emergency stop
        report.emergency_stop_active = True
        report.calculate_health_score()
        assert report.overall_health_score < 0.5
        assert report.health_status == "critical"
    
    def test_component_health_impact(self):
        """Test impact of component health on overall score."""
        report = SystemHealthReport()
        
        # Add failed components
        report.component_status = {
            "ml_engine": "failed",
            "regime_detector": "healthy",
            "strategy_engine": "failed"
        }
        
        report.calculate_health_score()
        assert report.overall_health_score <= 0.6  # Two failed components = -0.4


class TestPerformanceAnalysisReport:
    """Test PerformanceAnalysisReport functionality."""
    
    def test_performance_report_creation(self):
        """Test creating a performance analysis report."""
        report = PerformanceAnalysisReport()
        
        assert report.timestamp is not None
        assert report.analysis_period == timedelta(days=7)
        assert report.return_trend == "stable"
        assert report.adaptation_success_rate == 0.0
        assert isinstance(report.recommendations, list)
    
    def test_trend_analysis(self):
        """Test performance trend analysis."""
        from bot.adaptive.data_models import PerformanceMetrics
        
        report = PerformanceAnalysisReport()
        
        # Create mock historical performance data
        report.historical_performance = [
            PerformanceMetrics(
                total_return=0.05, annualized_return=0.20, excess_return=0.15,
                sharpe_ratio=1.2, sortino_ratio=1.5, calmar_ratio=1.0, 
                max_drawdown=0.08, volatility=0.15, downside_deviation=0.10, 
                win_rate=0.6, profit_factor=1.5, avg_trade_duration=timedelta(hours=4),
                trades_count=100, avg_win=0.02, avg_loss=-0.015
            ),
            PerformanceMetrics(
                total_return=0.08, annualized_return=0.25, excess_return=0.20,
                sharpe_ratio=1.3, sortino_ratio=1.6, calmar_ratio=1.1, 
                max_drawdown=0.06, volatility=0.14, downside_deviation=0.09, 
                win_rate=0.65, profit_factor=1.7, avg_trade_duration=timedelta(hours=3),
                trades_count=120, avg_win=0.022, avg_loss=-0.013
            )
        ]
        
        report.analyze_trends()
        assert report.return_trend == "improving"  # 0.08 > 0.05 * 1.05
    
    def test_recommendation_generation(self):
        """Test recommendation generation."""
        from bot.adaptive.data_models import PerformanceMetrics
        
        report = PerformanceAnalysisReport()
        
        # Set poor performance metrics
        report.current_performance = PerformanceMetrics(
            total_return=-0.05, annualized_return=-0.20, excess_return=-0.25,
            sharpe_ratio=0.3, sortino_ratio=0.4, calmar_ratio=0.2, 
            max_drawdown=0.20, volatility=0.25, downside_deviation=0.18, 
            win_rate=0.35, profit_factor=0.8, avg_trade_duration=timedelta(hours=6),
            trades_count=50, avg_win=0.015, avg_loss=-0.025
        )
        
        report.adaptation_success_rate = 0.3
        
        report.generate_recommendations()
        
        assert len(report.recommendations) > 0
        assert len(report.warnings) > 0
        assert any("position sizes" in rec for rec in report.recommendations)
        assert any("drawdown" in warn for warn in report.warnings)


class TestDiagnosticToolkit:
    """Test DiagnosticToolkit functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = AdaptiveConfigManager(self.temp_dir)
        self.control_system = ManualControlSystem(self.temp_dir)
        self.diagnostic_toolkit = DiagnosticToolkit(self.config_manager, self.control_system)
        
        # Load default config
        self.config_manager.load_config()
    
    def teardown_method(self):
        """Clean up test environment."""
        if hasattr(self, 'diagnostic_toolkit'):
            self.diagnostic_toolkit.stop_continuous_monitoring()
        shutil.rmtree(self.temp_dir)
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_generate_health_report(self, mock_disk, mock_memory, mock_cpu):
        """Test health report generation."""
        # Mock system resource calls
        mock_cpu.return_value = 45.0
        mock_memory.return_value = MagicMock(used=1024*1024*1024, percent=60.0)  # 1GB used, 60%
        mock_disk.return_value = MagicMock(percent=70.0)
        
        report = self.diagnostic_toolkit.generate_health_report()
        
        assert isinstance(report, SystemHealthReport)
        assert report.cpu_usage_pct == 45.0
        assert report.memory_usage_mb == 1024.0  # 1GB in MB
        assert report.memory_usage_pct == 60.0
        assert report.disk_usage_pct == 70.0
        assert report.config_valid is True
        assert report.emergency_stop_active is False
    
    def test_generate_performance_analysis(self):
        """Test performance analysis generation."""
        analysis = self.diagnostic_toolkit.generate_performance_analysis()
        
        assert isinstance(analysis, PerformanceAnalysisReport)
        assert analysis.analysis_period == timedelta(days=7)
        assert isinstance(analysis.recommendations, list)
        assert isinstance(analysis.warnings, list)
    
    def test_run_system_diagnostics(self):
        """Test comprehensive system diagnostics."""
        diagnostics = self.diagnostic_toolkit.run_system_diagnostics()
        
        assert "timestamp" in diagnostics
        assert "health_report" in diagnostics
        assert "performance_analysis" in diagnostics
        assert "configuration_summary" in diagnostics
        assert "control_system_diagnostics" in diagnostics
        
        assert isinstance(diagnostics["health_report"], SystemHealthReport)
        assert isinstance(diagnostics["performance_analysis"], PerformanceAnalysisReport)
    
    def test_check_data_integrity(self):
        """Test data integrity checking."""
        integrity_report = self.diagnostic_toolkit.check_data_integrity()
        
        assert "timestamp" in integrity_report
        assert "overall_score" in integrity_report
        assert "issues" in integrity_report
        assert "checks_performed" in integrity_report
        
        assert 0.0 <= integrity_report["overall_score"] <= 1.0
        assert isinstance(integrity_report["issues"], list)
        assert isinstance(integrity_report["checks_performed"], list)
    
    def test_data_integrity_with_issues(self):
        """Test data integrity checking with issues."""
        # Create an invalid configuration
        config = self.config_manager.get_config()
        config.trading_pairs = []  # Invalid - empty trading pairs
        
        integrity_report = self.diagnostic_toolkit.check_data_integrity()
        
        assert integrity_report["overall_score"] < 1.0
        assert len(integrity_report["issues"]) > 0
    
    def test_export_diagnostics(self):
        """Test exporting diagnostics to file."""
        export_file = Path(self.temp_dir) / "diagnostics_export.json"
        
        success = self.diagnostic_toolkit.export_diagnostics(str(export_file))
        
        assert success
        assert export_file.exists()
        
        # Verify file contents
        with open(export_file, 'r') as f:
            data = json.load(f)
        
        assert "timestamp" in data
        assert "health_report" in data
        assert "performance_analysis" in data
    
    def test_get_troubleshooting_guide(self):
        """Test getting troubleshooting guides."""
        # Test known issue type
        guide = self.diagnostic_toolkit.get_troubleshooting_guide("high_cpu")
        assert isinstance(guide, list)
        assert len(guide) > 0
        assert any("cpu" in step.lower() or "process" in step.lower() for step in guide)
        
        # Test unknown issue type
        guide = self.diagnostic_toolkit.get_troubleshooting_guide("unknown_issue")
        assert isinstance(guide, list)
        assert len(guide) == 1
        assert "No specific guide available" in guide[0]
    
    def test_suggest_optimizations(self):
        """Test optimization suggestions."""
        suggestions = self.diagnostic_toolkit.suggest_optimizations()
        
        assert isinstance(suggestions, list)
        # Should have at least some suggestions based on default config
    
    @patch('psutil.cpu_percent')
    def test_suggest_optimizations_high_cpu(self, mock_cpu):
        """Test optimization suggestions with high CPU usage."""
        mock_cpu.return_value = 85.0
        
        suggestions = self.diagnostic_toolkit.suggest_optimizations()
        
        assert isinstance(suggestions, list)
        assert any("training frequency" in suggestion.lower() for suggestion in suggestions)
    
    def test_continuous_monitoring_start_stop(self):
        """Test starting and stopping continuous monitoring."""
        # Start monitoring
        self.diagnostic_toolkit.start_continuous_monitoring(interval_seconds=1)
        assert self.diagnostic_toolkit._monitoring_active
        assert self.diagnostic_toolkit._monitoring_thread is not None
        
        # Stop monitoring
        self.diagnostic_toolkit.stop_continuous_monitoring()
        assert not self.diagnostic_toolkit._monitoring_active
    
    def test_health_history(self):
        """Test health history tracking."""
        # Generate some health reports
        report1 = self.diagnostic_toolkit.generate_health_report()
        self.diagnostic_toolkit._health_history.append(report1)
        
        report2 = self.diagnostic_toolkit.generate_health_report()
        self.diagnostic_toolkit._health_history.append(report2)
        
        # Get recent history
        history = self.diagnostic_toolkit.get_health_history(hours=1)
        assert len(history) == 2
        assert report1 in history
        assert report2 in history
        
        # Test with time filter
        old_report = SystemHealthReport()
        old_report.timestamp = datetime.now() - timedelta(hours=25)
        self.diagnostic_toolkit._health_history.insert(0, old_report)
        
        recent_history = self.diagnostic_toolkit.get_health_history(hours=24)
        assert old_report not in recent_history
        assert report1 in recent_history
        assert report2 in recent_history
    
    def test_health_report_with_control_system_issues(self):
        """Test health report generation with control system issues."""
        # Create some overrides
        self.control_system.create_strategy_override(
            strategy_name="test_strategy",
            enabled=False,
            reason="Test override"
        )
        
        # Trigger emergency stop
        self.control_system.trigger_emergency_stop("Test emergency")
        
        report = self.diagnostic_toolkit.generate_health_report()
        
        assert report.active_overrides > 0
        assert report.emergency_stop_active
        assert report.overall_health_score < 1.0
        assert report.health_status in ["warning", "critical"]


if __name__ == "__main__":
    pytest.main([__file__])