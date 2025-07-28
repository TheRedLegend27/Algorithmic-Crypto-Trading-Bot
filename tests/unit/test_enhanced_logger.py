"""
Unit tests for the enhanced logging system.

This module tests all functionality of the EnhancedLogger including:
- JSON structured logging
- Trade execution logging
- Signal logging
- Performance metrics tracking
- Error categorization
- Daily report generation
- Log rotation and archiving
"""
import os
import json
import tempfile
import datetime
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from bot.enhanced_logger import (
    EnhancedLogger, ErrorSeverity, TradeExecution, TradingSignal,
    PerformanceMetrics, SystemHealth, DailyReport, JSONFormatter,
    get_enhanced_logger
)


class TestJSONFormatter:
    """Test the JSON formatter"""
    
    def test_json_formatter_basic(self):
        """Test basic JSON formatting"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=1,
            msg="Test message", args=(), exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data['level'] == 'INFO'
        assert data['logger'] == 'test'
        assert data['message'] == 'Test message'
        assert data['module'] == 'test_module'
        assert data['function'] == 'test_function'
        assert 'timestamp' in data
    
    def test_json_formatter_with_extra_data(self):
        """Test JSON formatting with extra data"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=1,
            msg="Test message", args=(), exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.extra_data = {'trade_id': '123', 'amount': 100.0}
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data['trade_id'] == '123'
        assert data['amount'] == 100.0
    
    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception info"""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="", lineno=1,
                msg="Error occurred", args=(), exc_info=sys.exc_info()
            )
            record.module = "test_module"
            record.funcName = "test_function"
            
            result = formatter.format(record)
            data = json.loads(result)
            
            assert 'exception' in data
            assert 'ValueError' in data['exception']


class TestDataStructures:
    """Test data structure classes"""
    
    def test_trade_execution_to_dict(self):
        """Test TradeExecution to_dict conversion"""
        timestamp = datetime.datetime.now()
        trade = TradeExecution(
            trade_id="trade_123",
            pair="BTC/USD",
            side="BUY",
            order_type="market",
            volume=0.1,
            price=50000.0,
            fee=25.0,
            timestamp=timestamp,
            strategy="momentum",
            signal_confidence=0.85,
            execution_time_ms=150,
            status="filled"
        )
        
        data = trade.to_dict()
        
        assert data['trade_id'] == "trade_123"
        assert data['pair'] == "BTC/USD"
        assert data['side'] == "BUY"
        assert data['volume'] == 0.1
        assert data['price'] == 50000.0
        assert data['timestamp'] == timestamp.isoformat()
    
    def test_trading_signal_to_dict(self):
        """Test TradingSignal to_dict conversion"""
        timestamp = datetime.datetime.now()
        signal = TradingSignal(
            signal_id="signal_123",
            pair="ETH/USD",
            action="SELL",
            confidence=0.75,
            strategy="rsi_divergence",
            price=3000.0,
            timestamp=timestamp,
            reasoning="RSI overbought",
            indicators={'rsi': 75.0, 'macd': -0.5}
        )
        
        data = signal.to_dict()
        
        assert data['signal_id'] == "signal_123"
        assert data['action'] == "SELL"
        assert data['confidence'] == 0.75
        assert data['indicators']['rsi'] == 75.0
        assert data['timestamp'] == timestamp.isoformat()
    
    def test_performance_metrics_to_dict(self):
        """Test PerformanceMetrics to_dict conversion"""
        timestamp = datetime.datetime.now()
        metrics = PerformanceMetrics(
            timestamp=timestamp,
            total_trades=100,
            successful_trades=75,
            failed_trades=25,
            total_volume_usd=50000.0,
            total_fees_usd=250.0,
            realized_pnl=1500.0,
            unrealized_pnl=500.0,
            win_rate=0.75,
            average_trade_duration_minutes=45.0,
            portfolio_value_usd=25000.0
        )
        
        data = metrics.to_dict()
        
        assert data['total_trades'] == 100
        assert data['win_rate'] == 0.75
        assert data['realized_pnl'] == 1500.0
        assert data['timestamp'] == timestamp.isoformat()
    
    def test_system_health_to_dict(self):
        """Test SystemHealth to_dict conversion"""
        timestamp = datetime.datetime.now()
        last_trade = datetime.datetime.now() - datetime.timedelta(minutes=5)
        
        health = SystemHealth(
            timestamp=timestamp,
            cpu_usage_percent=45.5,
            memory_usage_percent=60.2,
            disk_usage_percent=30.0,
            api_response_time_ms=250.0,
            websocket_connection_status="connected",
            active_orders=3,
            open_positions=2,
            last_trade_time=last_trade,
            error_count_last_hour=1
        )
        
        data = health.to_dict()
        
        assert data['cpu_usage_percent'] == 45.5
        assert data['websocket_connection_status'] == "connected"
        assert data['timestamp'] == timestamp.isoformat()
        assert data['last_trade_time'] == last_trade.isoformat()
    
    def test_daily_report_to_dict(self):
        """Test DailyReport to_dict conversion"""
        date = datetime.date.today()
        report = DailyReport(
            date=date,
            total_trades=50,
            successful_trades=35,
            total_volume_usd=25000.0,
            total_fees_usd=125.0,
            realized_pnl=750.0,
            unrealized_pnl=250.0,
            net_pnl=1000.0,
            win_rate=0.70,
            best_trade_pnl=150.0,
            worst_trade_pnl=-50.0,
            average_trade_size_usd=500.0,
            portfolio_start_value=20000.0,
            portfolio_end_value=21000.0,
            daily_return_percent=5.0,
            strategies_used=["momentum", "rsi"],
            error_count=2,
            api_calls=500
        )
        
        data = report.to_dict()
        
        assert data['total_trades'] == 50
        assert data['win_rate'] == 0.70
        assert data['net_pnl'] == 1000.0
        assert data['date'] == date.isoformat()
        assert data['strategies_used'] == ["momentum", "rsi"]


class TestEnhancedLogger:
    """Test the EnhancedLogger class"""
    
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
            'log_level': logging.INFO,
            'max_file_size_mb': 1,
            'backup_count': 3,
            'structured_logging': True,
            'compression': False  # Disable for testing
        }
    
    def test_logger_initialization(self, logger_config):
        """Test logger initialization"""
        logger = EnhancedLogger(logger_config)
        
        assert logger.config['log_dir'] == logger_config['log_dir']
        assert logger.config['structured_logging'] is True
        assert logger.log_dir.exists()
        assert len(logger.trades_today) == 0
        assert len(logger.signals_today) == 0
        assert len(logger.errors_today) == 0
    
    def test_log_trade(self, logger_config):
        """Test trade logging"""
        logger = EnhancedLogger(logger_config)
        
        trade = TradeExecution(
            trade_id="test_trade_1",
            pair="BTC/USD",
            side="BUY",
            order_type="market",
            volume=0.1,
            price=50000.0,
            fee=25.0,
            timestamp=datetime.datetime.now(),
            strategy="test_strategy",
            signal_confidence=0.8,
            execution_time_ms=100,
            status="filled"
        )
        
        logger.log_trade(trade)
        
        # Check that trade was added to daily tracking
        assert len(logger.trades_today) == 1
        assert logger.trades_today[0].trade_id == "test_trade_1"
        
        # Check that log file was created
        trade_log_file = Path(logger_config['log_dir']) / 'trades.log'
        assert trade_log_file.exists()
        
        # Check log content
        with open(trade_log_file, 'r') as f:
            log_content = f.read()
            assert "Trade executed" in log_content
            assert "test_trade_1" in log_content
    
    def test_log_signal(self, logger_config):
        """Test signal logging"""
        logger = EnhancedLogger(logger_config)
        
        signal = TradingSignal(
            signal_id="test_signal_1",
            pair="ETH/USD",
            action="SELL",
            confidence=0.75,
            strategy="rsi_strategy",
            price=3000.0,
            timestamp=datetime.datetime.now(),
            reasoning="RSI overbought condition"
        )
        
        logger.log_signal(signal)
        
        # Check that signal was added to daily tracking
        assert len(logger.signals_today) == 1
        assert logger.signals_today[0].signal_id == "test_signal_1"
        
        # Check that log file was created
        signal_log_file = Path(logger_config['log_dir']) / 'signals.log'
        assert signal_log_file.exists()
        
        # Check log content
        with open(signal_log_file, 'r') as f:
            log_content = f.read()
            assert "Trading signal generated" in log_content
            assert "test_signal_1" in log_content
    
    def test_log_performance_metrics(self, logger_config):
        """Test performance metrics logging"""
        logger = EnhancedLogger(logger_config)
        
        metrics = PerformanceMetrics(
            timestamp=datetime.datetime.now(),
            total_trades=10,
            successful_trades=8,
            failed_trades=2,
            total_volume_usd=5000.0,
            total_fees_usd=25.0,
            realized_pnl=150.0,
            unrealized_pnl=50.0,
            win_rate=0.8,
            average_trade_duration_minutes=30.0,
            portfolio_value_usd=10000.0
        )
        
        logger.log_performance_metrics(metrics)
        
        # Check that metrics were stored
        assert 'total_trades' in logger.daily_metrics
        assert logger.daily_metrics['total_trades'] == 10
        
        # Check that log file was created
        metrics_log_file = Path(logger_config['log_dir']) / 'performance_metrics.log'
        assert metrics_log_file.exists()
    
    def test_log_error_categorization(self, logger_config):
        """Test error logging with categorization"""
        logger = EnhancedLogger(logger_config)
        
        # Test different severity levels
        test_cases = [
            (ValueError("Low severity error"), ErrorSeverity.LOW),
            (ConnectionError("Medium severity error"), ErrorSeverity.MEDIUM),
            (RuntimeError("High severity error"), ErrorSeverity.HIGH),
            (SystemError("Critical error"), ErrorSeverity.CRITICAL)
        ]
        
        for error, severity in test_cases:
            context = {'component': 'test', 'operation': 'test_operation'}
            logger.log_error(error, context, severity)
        
        # Check that errors were tracked
        assert len(logger.errors_today) == 4
        
        # Check severity levels
        severities = [error['severity'] for error in logger.errors_today]
        assert 'low' in severities
        assert 'medium' in severities
        assert 'high' in severities
        assert 'critical' in severities
        
        # Check that error log file was created
        error_log_file = Path(logger_config['log_dir']) / 'errors.log'
        assert error_log_file.exists()
    
    def test_log_system_health(self, logger_config):
        """Test system health logging"""
        logger = EnhancedLogger(logger_config)
        
        health = SystemHealth(
            timestamp=datetime.datetime.now(),
            cpu_usage_percent=45.0,
            memory_usage_percent=60.0,
            disk_usage_percent=30.0,
            api_response_time_ms=200.0,
            websocket_connection_status="connected",
            active_orders=2,
            open_positions=1
        )
        
        logger.log_system_health(health)
        
        # Check that health check time was updated
        assert logger.last_health_check is not None
    
    def test_system_health_alerts(self, logger_config):
        """Test system health alerting"""
        logger = EnhancedLogger(logger_config)
        
        # Test high CPU usage alert
        health = SystemHealth(
            timestamp=datetime.datetime.now(),
            cpu_usage_percent=85.0,  # Above threshold
            memory_usage_percent=90.0,  # Above threshold
            disk_usage_percent=30.0,
            api_response_time_ms=200.0,
            websocket_connection_status="disconnected",  # Problem
            active_orders=2,
            open_positions=1
        )
        
        logger.log_system_health(health)
        
        # Should have generated error alerts
        assert len(logger.errors_today) >= 2  # CPU, memory, and websocket issues
    
    def test_daily_report_generation(self, logger_config):
        """Test daily report generation"""
        logger = EnhancedLogger(logger_config)
        
        # Add some test data
        timestamp = datetime.datetime.now()
        
        # Add trades
        for i in range(5):
            side = "BUY" if i % 2 == 0 else "SELL"
            price = 50000.0 + i * 100
            # Create profitable trades based on side
            if side == "BUY":
                fill_price = price + 100  # Buy low, fill higher (profit)
            else:
                fill_price = price - 100  # Sell high, fill lower (profit)
            
            trade = TradeExecution(
                trade_id=f"trade_{i}",
                pair="BTC/USD",
                side=side,
                order_type="market",
                volume=0.1,
                price=price,
                fee=5.0,  # Lower fee to ensure profit
                timestamp=timestamp,
                strategy="test_strategy",
                signal_confidence=0.8,
                execution_time_ms=100,
                status="filled",
                fill_price=fill_price
            )
            logger.trades_today.append(trade)
        
        # Generate report
        report = logger.generate_daily_report()
        
        assert report.total_trades == 5
        assert report.successful_trades == 5
        assert report.win_rate > 0
        assert report.total_volume_usd > 0
        
        # Check that report file was created
        report_file = Path(logger_config['log_dir']) / f"daily_report_{datetime.date.today().isoformat()}.json"
        assert report_file.exists()
        
        # Check report content
        with open(report_file, 'r') as f:
            report_data = json.load(f)
            assert report_data['total_trades'] == 5
    
    def test_log_rotation_setup(self, logger_config):
        """Test that log rotation is properly configured"""
        logger = EnhancedLogger(logger_config)
        
        # Check that handlers are configured with rotation
        trade_handler = logger.trade_logger.handlers[0]
        assert hasattr(trade_handler, 'maxBytes')
        assert trade_handler.maxBytes == logger_config['max_file_size_mb'] * 1024 * 1024
        
        signal_handler = logger.signal_logger.handlers[0]
        assert hasattr(signal_handler, 'maxBytes')
        
        error_handler = logger.error_logger.handlers[0]
        assert hasattr(error_handler, 'maxBytes')
    
    def test_get_log_stats(self, logger_config):
        """Test log statistics retrieval"""
        logger = EnhancedLogger(logger_config)
        
        # Add some test data
        trade = TradeExecution(
            trade_id="test_trade",
            pair="BTC/USD",
            side="BUY",
            order_type="market",
            volume=0.1,
            price=50000.0,
            fee=25.0,
            timestamp=datetime.datetime.now(),
            strategy="test_strategy",
            signal_confidence=0.8,
            execution_time_ms=100,
            status="filled"
        )
        logger.log_trade(trade)
        
        signal = TradingSignal(
            signal_id="test_signal",
            pair="ETH/USD",
            action="SELL",
            confidence=0.75,
            strategy="test_strategy",
            price=3000.0,
            timestamp=datetime.datetime.now(),
            reasoning="Test signal"
        )
        logger.log_signal(signal)
        
        stats = logger.get_log_stats()
        
        assert stats['trades_today'] == 1
        assert stats['signals_today'] == 1
        assert stats['errors_today'] == 0
        assert 'last_health_check' in stats
        assert 'log_directory' in stats
        assert 'config' in stats
    
    def test_cleanup_old_logs(self, logger_config):
        """Test old log cleanup"""
        logger = EnhancedLogger(logger_config)
        
        # Create some old log files
        old_file = Path(logger_config['log_dir']) / 'old_log.log'
        old_file.touch()
        
        # Set modification time to 40 days ago
        old_time = datetime.datetime.now() - datetime.timedelta(days=40)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))
        
        # Create a recent file
        recent_file = Path(logger_config['log_dir']) / 'recent_log.log'
        recent_file.touch()
        
        # Cleanup logs older than 30 days
        logger.cleanup_old_logs(days_to_keep=30)
        
        # Old file should be deleted, recent file should remain
        assert not old_file.exists()
        assert recent_file.exists()
    
    def test_export_logs_to_json(self, logger_config):
        """Test log export functionality"""
        logger = EnhancedLogger(logger_config)
        
        # Add test data
        timestamp = datetime.datetime.now()
        
        trade = TradeExecution(
            trade_id="export_trade",
            pair="BTC/USD",
            side="BUY",
            order_type="market",
            volume=0.1,
            price=50000.0,
            fee=25.0,
            timestamp=timestamp,
            strategy="export_strategy",
            signal_confidence=0.8,
            execution_time_ms=100,
            status="filled"
        )
        logger.trades_today.append(trade)
        
        signal = TradingSignal(
            signal_id="export_signal",
            pair="ETH/USD",
            action="SELL",
            confidence=0.75,
            strategy="export_strategy",
            price=3000.0,
            timestamp=timestamp,
            reasoning="Export test signal"
        )
        logger.signals_today.append(signal)
        
        # Export logs
        export_file = Path(logger_config['log_dir']) / 'export_test.json'
        start_date = datetime.date.today()
        end_date = datetime.date.today()
        
        logger.export_logs_to_json(start_date, end_date, str(export_file))
        
        # Check export file
        assert export_file.exists()
        
        with open(export_file, 'r') as f:
            export_data = json.load(f)
            
            assert 'export_info' in export_data
            assert 'trades' in export_data
            assert 'signals' in export_data
            assert 'errors' in export_data
            
            assert len(export_data['trades']) == 1
            assert len(export_data['signals']) == 1
            assert export_data['trades'][0]['trade_id'] == 'export_trade'
            assert export_data['signals'][0]['signal_id'] == 'export_signal'


class TestGlobalLogger:
    """Test global logger functionality"""
    
    def test_get_enhanced_logger_singleton(self):
        """Test that get_enhanced_logger returns singleton"""
        # Reset global logger
        import bot.enhanced_logger
        bot.enhanced_logger._global_enhanced_logger = None
        
        logger1 = get_enhanced_logger()
        logger2 = get_enhanced_logger()
        
        assert logger1 is logger2
    
    def test_get_enhanced_logger_with_config(self):
        """Test get_enhanced_logger with custom config"""
        # Reset global logger
        import bot.enhanced_logger
        bot.enhanced_logger._global_enhanced_logger = None
        
        config = {'log_level': logging.DEBUG}
        logger = get_enhanced_logger(config)
        
        assert logger.config['log_level'] == logging.DEBUG


if __name__ == '__main__':
    pytest.main([__file__])