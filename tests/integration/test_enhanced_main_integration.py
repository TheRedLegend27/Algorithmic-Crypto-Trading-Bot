"""
Integration tests for the enhanced main bot controller.
Tests the complete bot workflow with orchestration logic.
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from bot.main import (
    BotOrchestrator, 
    initialize_enhanced_components,
    perform_enhanced_health_check,
    start_multi_pair_trading_loop,
    update_system_health,
    initiate_graceful_shutdown,
    handle_error_recovery,
    monitor_performance_and_optimize,
    SystemHealth
)
from bot.config import Config


class TestBotOrchestrator:
    """Test the BotOrchestrator class."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        config = Mock(spec=Config)
        args = Mock()
        args.trading_pairs = ["XBTUSD", "ETHUSD"]
        
        orchestrator = BotOrchestrator(config=config, args=args)
        
        assert orchestrator.config == config
        assert orchestrator.args == args
        assert orchestrator.trading_pairs == []
        assert isinstance(orchestrator.system_health, SystemHealth)
        assert isinstance(orchestrator.shutdown_event, threading.Event)
        assert not orchestrator.shutdown_event.is_set()
    
    def test_system_health_initialization(self):
        """Test system health initialization."""
        health = SystemHealth()
        
        assert health.is_healthy is True
        assert isinstance(health.last_check, datetime)
        assert health.api_connection is True
        assert health.websocket_connection is True
        assert health.data_quality == 1.0
        assert health.memory_usage_mb == 0.0
        assert health.cpu_usage_pct == 0.0
        assert health.active_trades == 0
        assert health.error_count == 0
        assert health.uptime_seconds == 0.0
        assert health.issues == []


class TestEnhancedComponentInitialization:
    """Test enhanced component initialization."""
    
    @patch('bot.main.EnhancedLogger')
    @patch('bot.main.EnhancedDataManager')
    @patch('bot.main.KrakenWebSocketClient')
    @patch('bot.main.EnhancedStrategyEngine')
    @patch('bot.main.EnhancedRiskManager')
    @patch('bot.main.EnhancedAlertSystem')
    @patch('bot.main.EnhancedDashboard')
    @patch('bot.main.DataFetcher')
    @patch('bot.main.SignalGenerator')
    @patch('bot.main.KrakenTrader')
    @patch('bot.main.ErrorHandler')
    def test_initialize_enhanced_components_success(
        self, mock_error_handler, mock_trader, mock_signal_gen, mock_data_fetcher,
        mock_dashboard, mock_alerts, mock_risk, mock_strategy, mock_websocket,
        mock_data_manager, mock_logger
    ):
        """Test successful initialization of enhanced components."""
        # Setup mocks
        config = Mock(spec=Config)
        credentials = Mock()
        config.get_kraken_credentials.return_value = credentials
        config.get_crypto_trading_settings.return_value = Mock()
        
        args = Mock()
        args.trading_pairs = ["XBTUSD"]
        args.log_level = "INFO"
        args.log_file = "test.log"
        args.performance_monitoring = True
        args.enable_websocket = True
        args.enable_alerts = True
        args.enable_dashboard = True
        args.dashboard_port = 8080
        args.max_position = 100.0
        args.stop_loss = 0.05
        args.take_profit = 0.1
        args.ma_fast = 10
        args.ma_slow = 30
        args.rsi_period = 14
        args.rsi_oversold = 30
        args.rsi_overbought = 70
        args.no_dashboard = False
        
        orchestrator = BotOrchestrator(config=config, args=args)
        
        # Test initialization
        result = initialize_enhanced_components(orchestrator)
        
        assert result is True
        assert len(orchestrator.components) > 0
        assert "enhanced_logger" in orchestrator.components
        assert "data_manager" in orchestrator.components
        assert "websocket_client" in orchestrator.components
        assert "strategy_engine" in orchestrator.components
        assert "risk_manager" in orchestrator.components
        assert "alert_system" in orchestrator.components
        assert "dashboard" in orchestrator.components
        assert orchestrator.trading_pairs == ["XBTUSD"]
    
    def test_initialize_enhanced_components_no_credentials(self):
        """Test initialization failure when credentials are missing."""
        config = Mock(spec=Config)
        config.get_kraken_credentials.return_value = None
        
        args = Mock()
        orchestrator = BotOrchestrator(config=config, args=args)
        
        result = initialize_enhanced_components(orchestrator)
        
        assert result is False
        assert len(orchestrator.components) == 0


class TestHealthCheck:
    """Test enhanced health check functionality."""
    
    def test_perform_enhanced_health_check_success(self):
        """Test successful health check."""
        config = Mock(spec=Config)
        args = Mock()
        args.trading_pairs = ["XBTUSD"]
        
        orchestrator = BotOrchestrator(config=config, args=args)
        orchestrator.trading_pairs = ["XBTUSD"]
        
        # Mock components
        data_fetcher = Mock()
        data_fetcher.get_latest_price.return_value = 50000.0
        
        trader = Mock()
        trader.get_account_info.return_value = {"balance": 1000.0}
        trader.get_positions.return_value = {}
        
        data_manager = Mock()
        data_manager.get_latest_data.return_value = Mock()
        data_manager.get_latest_data.return_value.empty = False
        quality_report = Mock()
        quality_report.quality_score = 0.95
        data_manager.validate_data_quality.return_value = quality_report
        
        websocket_client = Mock()
        websocket_client.is_connected.return_value = True
        
        risk_manager = Mock()
        
        orchestrator.components = {
            "data_fetcher": data_fetcher,
            "trader": trader,
            "data_manager": data_manager,
            "websocket_client": websocket_client,
            "risk_manager": risk_manager
        }
        
        with patch('bot.main.update_system_health'):
            result = perform_enhanced_health_check(orchestrator)
        
        assert result is True
        data_fetcher.get_latest_price.assert_called_with("XBTUSD")
        trader.get_account_info.assert_called_once()
    
    def test_perform_enhanced_health_check_data_fetcher_failure(self):
        """Test health check failure when data fetcher fails."""
        config = Mock(spec=Config)
        args = Mock()
        orchestrator = BotOrchestrator(config=config, args=args)
        orchestrator.trading_pairs = ["XBTUSD"]
        
        data_fetcher = Mock()
        data_fetcher.get_latest_price.side_effect = Exception("API Error")
        
        orchestrator.components = {"data_fetcher": data_fetcher}
        
        result = perform_enhanced_health_check(orchestrator)
        
        assert result is False


class TestSystemHealthMonitoring:
    """Test system health monitoring functionality."""
    
    @patch('psutil.Process')
    def test_update_system_health(self, mock_process):
        """Test system health update."""
        # Setup mocks
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
        mock_proc.cpu_percent.return_value = 25.0
        mock_process.return_value = mock_proc
        
        config = Mock(spec=Config)
        args = Mock()
        orchestrator = BotOrchestrator(config=config, args=args)
        orchestrator.trading_pairs = ["XBTUSD"]
        orchestrator.start_time = datetime.now() - timedelta(seconds=300)
        
        # Mock components
        trader = Mock()
        trader.get_account_info.return_value = {"balance": 1000.0}
        
        websocket_client = Mock()
        websocket_client.is_connected.return_value = True
        
        data_manager = Mock()
        data_manager.get_latest_data.return_value = Mock()
        data_manager.get_latest_data.return_value.empty = False
        quality_report = Mock()
        quality_report.quality_score = 0.9
        data_manager.validate_data_quality.return_value = quality_report
        
        orchestrator.components = {
            "trader": trader,
            "websocket_client": websocket_client,
            "data_manager": data_manager
        }
        
        update_system_health(orchestrator)
        
        health = orchestrator.system_health
        assert health.memory_usage_mb == 100.0
        assert health.cpu_usage_pct == 25.0
        assert health.api_connection is True
        assert health.websocket_connection is True
        assert health.data_quality == 0.9
        assert health.uptime_seconds >= 300
        assert health.is_healthy is True


class TestTradingLoop:
    """Test multi-pair trading loop functionality."""
    
    def test_start_multi_pair_trading_loop(self):
        """Test starting the multi-pair trading loop."""
        config = Mock(spec=Config)
        args = Mock()
        args.interval = 1  # 1 minute
        args.confidence_threshold = 0.3
        
        orchestrator = BotOrchestrator(config=config, args=args)
        orchestrator.trading_pairs = ["XBTUSD"]
        
        # Mock components
        data_manager = Mock()
        data_manager.get_latest_data.return_value = Mock()
        data_manager.get_latest_data.return_value.empty = False
        
        strategy_engine = Mock()
        signal = Mock()
        signal.confidence = 0.5
        strategy_engine.calculate_weighted_signal.return_value = signal
        
        risk_manager = Mock()
        risk_assessment = Mock()
        risk_assessment.is_valid = True
        risk_assessment.recommended_size = 10.0
        risk_manager.validate_trade.return_value = risk_assessment
        
        trader = Mock()
        trader.get_positions.return_value = {}
        trader.execute_trade.return_value = Mock()
        
        enhanced_logger = Mock()
        alert_system = Mock()
        
        orchestrator.components = {
            "data_manager": data_manager,
            "strategy_engine": strategy_engine,
            "risk_manager": risk_manager,
            "trader": trader,
            "enhanced_logger": enhanced_logger,
            "alert_system": alert_system
        }
        
        with patch('bot.main.update_system_health'):
            # Start the trading loop
            start_multi_pair_trading_loop(orchestrator)
            
            # Let it run briefly
            time.sleep(0.1)
            
            # Stop the loop
            orchestrator.shutdown_event.set()
            time.sleep(0.1)
        
        # Verify components were called
        data_manager.get_latest_data.assert_called()
        strategy_engine.calculate_weighted_signal.assert_called()


class TestGracefulShutdown:
    """Test graceful shutdown functionality."""
    
    def test_initiate_graceful_shutdown(self):
        """Test graceful shutdown initiation."""
        config = Mock(spec=Config)
        args = Mock()
        args.close_positions_on_shutdown = False
        
        orchestrator = BotOrchestrator(config=config, args=args)
        
        # Mock components
        websocket_client = Mock()
        dashboard = Mock()
        enhanced_logger = Mock()
        alert_system = Mock()
        
        orchestrator.components = {
            "websocket_client": websocket_client,
            "dashboard": dashboard,
            "enhanced_logger": enhanced_logger,
            "alert_system": alert_system
        }
        
        initiate_graceful_shutdown(orchestrator)
        
        assert orchestrator.shutdown_event.is_set()
        websocket_client.disconnect.assert_called_once()
        dashboard.stop_server.assert_called_once()
        enhanced_logger.flush_logs.assert_called_once()
        alert_system.send_system_alert.assert_called_once()
    
    def test_initiate_graceful_shutdown_with_position_closing(self):
        """Test graceful shutdown with position closing."""
        config = Mock(spec=Config)
        args = Mock()
        args.close_positions_on_shutdown = True
        
        orchestrator = BotOrchestrator(config=config, args=args)
        
        # Mock trader with positions
        trader = Mock()
        trader.get_positions.return_value = {
            "XBTUSD": {"size": 0.1},
            "ETHUSD": {"size": 0.0}
        }
        
        orchestrator.components = {"trader": trader}
        
        initiate_graceful_shutdown(orchestrator)
        
        trader.close_position.assert_called_once_with("XBTUSD")


class TestErrorRecovery:
    """Test error recovery functionality."""
    
    def test_handle_error_recovery_connection_error(self):
        """Test error recovery for connection errors."""
        config = Mock(spec=Config)
        args = Mock()
        orchestrator = BotOrchestrator(config=config, args=args)
        
        # Mock components
        websocket_client = Mock()
        websocket_client.reconnect.return_value = None
        
        trader = Mock()
        trader.get_account_info.return_value = {"balance": 1000.0}
        
        orchestrator.components = {
            "websocket_client": websocket_client,
            "trader": trader,
            "error_handler": Mock()
        }
        
        error = ConnectionError("Connection lost")
        result = handle_error_recovery(orchestrator, error)
        
        assert result is True
        assert orchestrator.system_health.error_count == 1
        websocket_client.reconnect.assert_called_once()
        trader.get_account_info.assert_called_once()
    
    def test_handle_error_recovery_too_many_errors(self):
        """Test error recovery when too many errors occurred."""
        config = Mock(spec=Config)
        args = Mock()
        orchestrator = BotOrchestrator(config=config, args=args)
        orchestrator.system_health.error_count = 15
        
        orchestrator.components = {"error_handler": Mock()}
        
        error = Exception("Some error")
        result = handle_error_recovery(orchestrator, error)
        
        assert result is False


class TestPerformanceMonitoring:
    """Test performance monitoring functionality."""
    
    @patch('psutil.Process')
    @patch('gc.collect')
    def test_monitor_performance_and_optimize_high_memory(self, mock_gc, mock_process):
        """Test performance monitoring with high memory usage."""
        # Setup mocks
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 500 * 1024 * 1024  # 500MB
        mock_proc.cpu_percent.return_value = 30.0
        mock_process.return_value = mock_proc
        
        config = Mock(spec=Config)
        args = Mock()
        args.performance_monitoring = True
        
        orchestrator = BotOrchestrator(config=config, args=args)
        orchestrator.trading_pairs = ["XBTUSD"]
        
        # Mock components
        data_manager = Mock()
        enhanced_logger = Mock()
        
        orchestrator.components = {
            "data_manager": data_manager,
            "enhanced_logger": enhanced_logger
        }
        
        # Start monitoring briefly
        monitor_performance_and_optimize(orchestrator)
        time.sleep(0.1)
        orchestrator.shutdown_event.set()
        time.sleep(0.1)
        
        # Verify garbage collection was called due to high memory
        mock_gc.assert_called()
        data_manager.cleanup_cache.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])