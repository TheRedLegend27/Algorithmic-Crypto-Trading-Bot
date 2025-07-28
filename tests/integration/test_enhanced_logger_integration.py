"""
Integration tests for the enhanced logging system.

This module tests the integration of the enhanced logger with other system components
and real-world usage scenarios.
"""
import os
import json
import tempfile
import datetime
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from bot.enhanced_logger import (
    EnhancedLogger, ErrorSeverity, TradeExecution, TradingSignal,
    PerformanceMetrics, SystemHealth, get_enhanced_logger
)


class TestEnhancedLoggerIntegration:
    """Integration tests for EnhancedLogger"""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for logs"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def logger_config(self, temp_log_dir):
        """Create logger configuration"""
        return {
            'log_dir': temp_log_dir,
            'log_level': 20,  # INFO
            'max_file_size_mb': 1,
            'backup_count': 3,
            'structured_logging': True,
            'compression': False,
            'performance_tracking': True,
            'daily_reports': True
        }
    
    def test_concurrent_logging(self, logger_config):
        """Test concurrent logging from multiple threads"""
        logger = EnhancedLogger(logger_config)
        
        def log_trades(thread_id, num_trades):
            """Log trades from a thread"""
            for i in range(num_trades):
                trade = TradeExecution(
                    trade_id=f"thread_{thread_id}_trade_{i}",
                    pair="BTC/USD",
                    side="BUY" if i % 2 == 0 else "SELL",
                    order_type="market",
                    volume=0.1,
                    price=50000.0 + i,
                    fee=25.0,
                    timestamp=datetime.datetime.now(),
                    strategy=f"strategy_{thread_id}",
                    signal_confidence=0.8,
                    execution_time_ms=100,
                    status="filled"
                )
                logger.log_trade(trade)
                time.sleep(0.01)  # Small delay to simulate real trading
        
        # Start multiple threads
        threads = []
        num_threads = 5
        trades_per_thread = 10
        
        for thread_id in range(num_threads):
            thread = threading.Thread(
                target=log_trades,
                args=(thread_id, trades_per_thread)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all trades were logged
        assert len(logger.trades_today) == num_threads * trades_per_thread
        
        # Verify log file integrity
        trade_log_file = Path(logger_config['log_dir']) / 'trades.log'
        assert trade_log_file.exists()
        
        with open(trade_log_file, 'r') as f:
            log_lines = f.readlines()
            # Should have at least one log entry per trade
            assert len(log_lines) >= num_threads * trades_per_thread
    
    def test_high_volume_logging(self, logger_config):
        """Test logging under high volume conditions"""
        logger = EnhancedLogger(logger_config)
        
        # Log a smaller number of events for CI stability
        num_events = 100
        
        start_time = time.time()
        
        for i in range(num_events):
            # Log trade
            trade = TradeExecution(
                trade_id=f"high_volume_trade_{i}",
                pair="BTC/USD",
                side="BUY" if i % 2 == 0 else "SELL",
                order_type="market",
                volume=0.1,
                price=50000.0 + i,
                fee=25.0,
                timestamp=datetime.datetime.now(),
                strategy="high_volume_strategy",
                signal_confidence=0.8,
                execution_time_ms=100,
                status="filled"
            )
            logger.log_trade(trade)
            
            # Log signal
            signal = TradingSignal(
                signal_id=f"high_volume_signal_{i}",
                pair="ETH/USD",
                action="BUY" if i % 3 == 0 else "SELL",
                confidence=0.75,
                strategy="high_volume_strategy",
                price=3000.0 + i,
                timestamp=datetime.datetime.now(),
                reasoning=f"High volume test signal {i}"
            )
            logger.log_signal(signal)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify performance (should handle events in reasonable time)
        assert duration < 5.0  # Should complete within 5 seconds
        
        # Verify all events were logged
        assert len(logger.trades_today) == num_events
        assert len(logger.signals_today) == num_events
        
        # Verify log files exist and have content
        for log_file in ['trades.log', 'signals.log']:
            log_path = Path(logger_config['log_dir']) / log_file
            assert log_path.exists()
            assert log_path.stat().st_size > 0
    
    def test_log_rotation_behavior(self, logger_config):
        """Test log rotation under real conditions"""
        # Set very small file size to trigger rotation
        logger_config['max_file_size_mb'] = 0.001  # 1KB
        logger = EnhancedLogger(logger_config)
        
        # Generate enough logs to trigger rotation
        for i in range(100):
            trade = TradeExecution(
                trade_id=f"rotation_test_trade_{i}",
                pair="BTC/USD",
                side="BUY",
                order_type="market",
                volume=0.1,
                price=50000.0,
                fee=25.0,
                timestamp=datetime.datetime.now(),
                strategy="rotation_test_strategy",
                signal_confidence=0.8,
                execution_time_ms=100,
                status="filled"
            )
            logger.log_trade(trade)
        
        # Check for rotated files
        log_dir = Path(logger_config['log_dir'])
        log_files = list(log_dir.glob('trades.log*'))
        
        # Should have main file plus rotated files
        assert len(log_files) > 1
        
        # Check that main log file exists
        main_log = log_dir / 'trades.log'
        assert main_log.exists()
    
    def test_daily_report_workflow(self, logger_config):
        """Test complete daily report workflow"""
        logger = EnhancedLogger(logger_config)
        
        # Simulate a day of trading
        timestamp_base = datetime.datetime.now().replace(hour=9, minute=0, second=0)
        
        # Morning trades (profitable)
        for i in range(10):
            trade = TradeExecution(
                trade_id=f"morning_trade_{i}",
                pair="BTC/USD",
                side="BUY",
                order_type="market",
                volume=0.1,
                price=50000.0,
                fee=25.0,
                timestamp=timestamp_base + datetime.timedelta(minutes=i*10),
                strategy="morning_strategy",
                signal_confidence=0.8,
                execution_time_ms=100,
                status="filled",
                fill_price=50100.0  # Profitable
            )
            logger.log_trade(trade)
        
        # Afternoon trades (mixed results)
        for i in range(15):
            profit_multiplier = 1 if i % 3 == 0 else -1  # 1/3 profitable
            trade = TradeExecution(
                trade_id=f"afternoon_trade_{i}",
                pair="ETH/USD",
                side="SELL",
                order_type="limit",
                volume=1.0,
                price=3000.0,
                fee=15.0,
                timestamp=timestamp_base + datetime.timedelta(hours=4, minutes=i*5),
                strategy="afternoon_strategy",
                signal_confidence=0.7,
                execution_time_ms=150,
                status="filled",
                fill_price=3000.0 + (profit_multiplier * 50)  # Mixed results
            )
            logger.log_trade(trade)
        
        # Add some performance metrics
        metrics = PerformanceMetrics(
            timestamp=datetime.datetime.now(),
            total_trades=25,
            successful_trades=20,
            failed_trades=5,
            total_volume_usd=75000.0,
            total_fees_usd=400.0,
            realized_pnl=2500.0,
            unrealized_pnl=500.0,
            win_rate=0.8,
            average_trade_duration_minutes=30.0,
            portfolio_value_usd=50000.0,
            daily_return=5.0
        )
        logger.log_performance_metrics(metrics)
        
        # Generate daily report
        report = logger.generate_daily_report()
        
        # Verify report accuracy
        assert report.total_trades == 25
        assert report.successful_trades == 25  # All filled
        assert report.total_volume_usd > 0
        assert set(report.strategies_used) == {"morning_strategy", "afternoon_strategy"}
        
        # Verify report file was created
        report_file = Path(logger_config['log_dir']) / f"daily_report_{datetime.date.today().isoformat()}.json"
        assert report_file.exists()
        
        # Verify report content
        with open(report_file, 'r') as f:
            report_data = json.load(f)
            assert report_data['total_trades'] == 25
            assert len(report_data['strategies_used']) == 2
    
    def test_error_escalation_workflow(self, logger_config):
        """Test error escalation and categorization workflow"""
        logger = EnhancedLogger(logger_config)
        
        # Simulate escalating error conditions
        error_scenarios = [
            # Low severity - minor issues
            (ValueError("Invalid parameter"), ErrorSeverity.LOW, "parameter_validation"),
            (KeyError("Missing config key"), ErrorSeverity.LOW, "configuration"),
            
            # Medium severity - operational issues
            (ConnectionError("API timeout"), ErrorSeverity.MEDIUM, "api_connection"),
            (TimeoutError("Request timeout"), ErrorSeverity.MEDIUM, "network"),
            
            # High severity - trading issues
            (RuntimeError("Order execution failed"), ErrorSeverity.HIGH, "order_execution"),
            (ValueError("Insufficient funds"), ErrorSeverity.HIGH, "account_management"),
            
            # Critical severity - system issues
            (SystemError("Database connection lost"), ErrorSeverity.CRITICAL, "database"),
            (MemoryError("Out of memory"), ErrorSeverity.CRITICAL, "system_resources")
        ]
        
        for error, severity, component in error_scenarios:
            context = {
                'component': component,
                'timestamp': datetime.datetime.now().isoformat(),
                'severity_level': severity.value
            }
            logger.log_error(error, context, severity)
        
        # Verify error categorization
        assert len(logger.errors_today) == len(error_scenarios)
        
        # Check severity distribution
        severity_counts = {}
        for error in logger.errors_today:
            severity = error['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        assert severity_counts['low'] == 2
        assert severity_counts['medium'] == 2
        assert severity_counts['high'] == 2
        assert severity_counts['critical'] == 2
        
        # Verify error log file
        error_log_file = Path(logger_config['log_dir']) / 'errors.log'
        assert error_log_file.exists()
        
        with open(error_log_file, 'r') as f:
            error_log_content = f.read()
            # Check for log levels in JSON format
            assert '"level": "CRITICAL"' in error_log_content
            assert '"level": "ERROR"' in error_log_content
            assert '"level": "WARNING"' in error_log_content
            # Check for severity in error data
            assert '"severity": "critical"' in error_log_content
            assert '"severity": "high"' in error_log_content
            assert '"severity": "medium"' in error_log_content
    
    def test_system_monitoring_integration(self, logger_config):
        """Test integration with system monitoring"""
        logger = EnhancedLogger(logger_config)
        
        # Simulate system monitoring over time
        monitoring_scenarios = [
            # Normal conditions
            SystemHealth(
                timestamp=datetime.datetime.now(),
                cpu_usage_percent=45.0,
                memory_usage_percent=60.0,
                disk_usage_percent=30.0,
                api_response_time_ms=200.0,
                websocket_connection_status="connected",
                active_orders=3,
                open_positions=2
            ),
            
            # Degraded performance
            SystemHealth(
                timestamp=datetime.datetime.now(),
                cpu_usage_percent=75.0,
                memory_usage_percent=80.0,
                disk_usage_percent=45.0,
                api_response_time_ms=500.0,
                websocket_connection_status="connected",
                active_orders=5,
                open_positions=3,
                error_count_last_hour=5
            ),
            
            # Critical conditions
            SystemHealth(
                timestamp=datetime.datetime.now(),
                cpu_usage_percent=90.0,
                memory_usage_percent=95.0,
                disk_usage_percent=85.0,
                api_response_time_ms=2000.0,
                websocket_connection_status="disconnected",
                active_orders=0,
                open_positions=1,
                error_count_last_hour=20
            )
        ]
        
        initial_error_count = len(logger.errors_today)
        
        for health_metrics in monitoring_scenarios:
            logger.log_system_health(health_metrics)
        
        # Should have generated alerts for critical conditions
        final_error_count = len(logger.errors_today)
        assert final_error_count > initial_error_count
        
        # Check for specific health-related errors
        health_errors = [
            error for error in logger.errors_today
            if any(keyword in error['error_message'].lower() 
                  for keyword in ['cpu', 'memory', 'websocket'])
        ]
        assert len(health_errors) > 0
    
    def test_performance_under_load(self, logger_config):
        """Test logger performance under sustained load"""
        logger = EnhancedLogger(logger_config)
        
        # Measure performance metrics
        start_time = time.time()
        memory_usage_start = logger._get_memory_usage() if hasattr(logger, '_get_memory_usage') else 0
        
        # Sustained logging load
        num_iterations = 500
        
        for i in range(num_iterations):
            # Log multiple event types per iteration
            
            # Trade
            trade = TradeExecution(
                trade_id=f"load_test_trade_{i}",
                pair="BTC/USD",
                side="BUY" if i % 2 == 0 else "SELL",
                order_type="market",
                volume=0.1,
                price=50000.0 + i,
                fee=25.0,
                timestamp=datetime.datetime.now(),
                strategy="load_test_strategy",
                signal_confidence=0.8,
                execution_time_ms=100,
                status="filled"
            )
            logger.log_trade(trade)
            
            # Signal
            signal = TradingSignal(
                signal_id=f"load_test_signal_{i}",
                pair="ETH/USD",
                action="BUY" if i % 3 == 0 else "SELL",
                confidence=0.75,
                strategy="load_test_strategy",
                price=3000.0 + i,
                timestamp=datetime.datetime.now(),
                reasoning=f"Load test signal {i}"
            )
            logger.log_signal(signal)
            
            # Periodic metrics and health checks
            if i % 50 == 0:
                metrics = PerformanceMetrics(
                    timestamp=datetime.datetime.now(),
                    total_trades=i,
                    successful_trades=i,
                    failed_trades=0,
                    total_volume_usd=i * 5000.0,
                    total_fees_usd=i * 25.0,
                    realized_pnl=i * 10.0,
                    unrealized_pnl=i * 5.0,
                    win_rate=1.0,
                    average_trade_duration_minutes=30.0,
                    portfolio_value_usd=50000.0 + i * 10
                )
                logger.log_performance_metrics(metrics)
                
                health = SystemHealth(
                    timestamp=datetime.datetime.now(),
                    cpu_usage_percent=50.0 + (i % 30),
                    memory_usage_percent=60.0 + (i % 20),
                    disk_usage_percent=30.0,
                    api_response_time_ms=200.0 + (i % 100),
                    websocket_connection_status="connected",
                    active_orders=i % 10,
                    open_positions=i % 5
                )
                logger.log_system_health(health)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance assertions
        events_per_second = (num_iterations * 2) / duration  # 2 events per iteration
        print(f"Events per second: {events_per_second}")
        assert events_per_second > 50  # Should handle at least 50 events/second (reduced for CI)
        
        # Verify data integrity
        assert len(logger.trades_today) == num_iterations
        assert len(logger.signals_today) == num_iterations
        
        # Verify log files exist and have reasonable sizes
        for log_file in ['trades.log', 'signals.log', 'performance_metrics.log']:
            log_path = Path(logger_config['log_dir']) / log_file
            assert log_path.exists()
            assert log_path.stat().st_size > 1000  # Should have substantial content
    
    def test_log_export_integration(self, logger_config):
        """Test log export functionality with real data"""
        logger = EnhancedLogger(logger_config)
        
        # Generate test data over multiple days
        base_date = datetime.date.today() - datetime.timedelta(days=2)
        
        for day_offset in range(3):  # 3 days of data
            current_date = base_date + datetime.timedelta(days=day_offset)
            
            # Generate trades for each day
            for i in range(10):
                timestamp = datetime.datetime.combine(
                    current_date,
                    datetime.time(9 + i, 0, 0)
                )
                
                trade = TradeExecution(
                    trade_id=f"export_test_day_{day_offset}_trade_{i}",
                    pair="BTC/USD",
                    side="BUY" if i % 2 == 0 else "SELL",
                    order_type="market",
                    volume=0.1,
                    price=50000.0 + day_offset * 1000 + i * 100,
                    fee=25.0,
                    timestamp=timestamp,
                    strategy=f"day_{day_offset}_strategy",
                    signal_confidence=0.8,
                    execution_time_ms=100,
                    status="filled"
                )
                
                # Manually add to trades_today for testing
                logger.trades_today.append(trade)
                
                # Generate corresponding signal
                signal = TradingSignal(
                    signal_id=f"export_test_day_{day_offset}_signal_{i}",
                    pair="BTC/USD",
                    action=trade.side,
                    confidence=0.8,
                    strategy=f"day_{day_offset}_strategy",
                    price=trade.price,
                    timestamp=timestamp,
                    reasoning=f"Export test signal for day {day_offset}"
                )
                logger.signals_today.append(signal)
            
            # Generate daily report for each day
            logger.generate_daily_report(current_date)
        
        # Export logs for date range
        export_file = Path(logger_config['log_dir']) / 'integration_export.json'
        start_date = base_date
        end_date = base_date + datetime.timedelta(days=2)
        
        logger.export_logs_to_json(start_date, end_date, str(export_file))
        
        # Verify export
        assert export_file.exists()
        
        with open(export_file, 'r') as f:
            export_data = json.load(f)
            
            # Should have data from all 3 days
            assert len(export_data['trades']) == 30  # 10 trades * 3 days
            assert len(export_data['signals']) == 30  # 10 signals * 3 days
            assert len(export_data['daily_reports']) == 3  # 3 daily reports
            
            # Verify date range
            trade_dates = [
                datetime.datetime.fromisoformat(trade['timestamp']).date()
                for trade in export_data['trades']
            ]
            assert min(trade_dates) >= start_date
            assert max(trade_dates) <= end_date


if __name__ == '__main__':
    pytest.main([__file__])