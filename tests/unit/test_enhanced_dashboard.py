"""
Unit tests for the enhanced dashboard module.
Tests dashboard functionality, API endpoints, WebSocket handlers, and manual trading controls.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import threading
import time
from datetime import datetime, timedelta
from dataclasses import asdict

from bot.enhanced_dashboard import (
    EnhancedDashboard, DashboardConfig, Portfolio, TradeExecution,
    SystemHealth, ManualTradeRequest, TradeResult
)
from bot.enhanced_data_manager import EnhancedDataManager, MarketData
from bot.enhanced_data_manager import PerformanceMetrics as DataPerformanceMetrics
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.kraken_client import KrakenClient


class TestEnhancedDashboard(unittest.TestCase):
    """Test cases for EnhancedDashboard class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = DashboardConfig(
            host="localhost",
            port=8080,
            debug=False,
            auto_refresh_interval=1,
            enable_manual_trading=True
        )
        
        # Mock dependencies
        self.mock_data_manager = Mock(spec=EnhancedDataManager)
        self.mock_logger = Mock(spec=EnhancedLogger)
        self.mock_risk_manager = Mock(spec=EnhancedRiskManager)
        self.mock_kraken_client = Mock(spec=KrakenClient)
        
        # Create dashboard instance
        with patch('bot.enhanced_dashboard.Flask'), \
             patch('bot.enhanced_dashboard.SocketIO'):
            self.dashboard = EnhancedDashboard(
                self.config,
                self.mock_data_manager,
                self.mock_logger,
                self.mock_risk_manager,
                self.mock_kraken_client
            )
    
    def test_dashboard_initialization(self):
        """Test dashboard initialization."""
        self.assertEqual(self.dashboard.config, self.config)
        self.assertEqual(self.dashboard.data_manager, self.mock_data_manager)
        self.assertEqual(self.dashboard.logger, self.mock_logger)
        self.assertEqual(self.dashboard.risk_manager, self.mock_risk_manager)
        self.assertEqual(self.dashboard.kraken_client, self.mock_kraken_client)
        
        # Check initial state
        self.assertIsNone(self.dashboard.portfolio)
        self.assertEqual(self.dashboard.market_data, {})
        self.assertEqual(self.dashboard.trade_history, [])
        self.assertIsNone(self.dashboard.system_health)
        self.assertIsNone(self.dashboard.performance_metrics)
        self.assertFalse(self.dashboard.running)
    
    def test_update_portfolio_data(self):
        """Test portfolio data update."""
        portfolio = Portfolio(
            total_value_usd=10000.0,
            available_balance=2000.0,
            positions={"BTC/USD": {"volume": 0.5, "value": 8000.0}},
            daily_pnl=150.0,
            unrealized_pnl=300.0,
            realized_pnl=500.0
        )
        
        with patch.object(self.dashboard, '_broadcast_update') as mock_broadcast:
            self.dashboard.update_portfolio_data(portfolio)
            
            self.assertEqual(self.dashboard.portfolio, portfolio)
            mock_broadcast.assert_called_once_with('portfolio_update', asdict(portfolio))
    
    def test_update_market_data(self):
        """Test market data update."""
        market_data = {
            "BTC/USD": MarketData(
                pair="BTC/USD",
                timestamp=datetime.now(),
                price=50000.0,
                volume=100.0,
                bid=49990.0,
                ask=50010.0,
                spread=0.0004,
                volatility=0.02,
                indicators={"rsi": 65.0, "macd": 0.5}
            )
        }
        
        with patch.object(self.dashboard, '_broadcast_update') as mock_broadcast:
            self.dashboard.update_market_data(market_data)
            
            self.assertEqual(self.dashboard.market_data, market_data)
            mock_broadcast.assert_called_once()
            
            # Check that the broadcast data is serializable
            call_args = mock_broadcast.call_args[0]
            self.assertEqual(call_args[0], 'market_data_update')
            self.assertIn("BTC/USD", call_args[1])
            self.assertEqual(call_args[1]["BTC/USD"]["price"], 50000.0)
    
    def test_add_trade_event(self):
        """Test adding trade event."""
        trade = TradeExecution(
            trade_id="test_trade_123",
            pair="BTC/USD",
            side="BUY",
            order_type="MARKET",
            volume=0.1,
            price=50000.0,
            fee=25.0,
            timestamp=datetime.now(),
            strategy="Enhanced Momentum",
            signal_confidence=0.85,
            execution_time_ms=150,
            status="FILLED"
        )
        
        with patch.object(self.dashboard, '_broadcast_update') as mock_broadcast:
            self.dashboard.add_trade_event(trade)
            
            self.assertIn(trade, self.dashboard.trade_history)
            mock_broadcast.assert_called_once()
            
            # Check broadcast data
            call_args = mock_broadcast.call_args[0]
            self.assertEqual(call_args[0], 'trade_update')
            self.assertEqual(call_args[1]['trade_id'], "test_trade_123")
    
    def test_trade_history_limit(self):
        """Test trade history size limit."""
        # Set a small limit for testing
        self.dashboard.config.max_trade_history = 3
        
        # Add more trades than the limit
        for i in range(5):
            trade = TradeExecution(
                trade_id=f"trade_{i}",
                pair="BTC/USD",
                side="BUY",
                order_type="MARKET",
                volume=0.1,
                price=50000.0,
                fee=25.0,
                timestamp=datetime.now(),
                strategy="Test",
                signal_confidence=0.8,
                execution_time_ms=100,
                status="FILLED"
            )
            
            with patch.object(self.dashboard, '_broadcast_update'):
                self.dashboard.add_trade_event(trade)
        
        # Check that only the last 3 trades are kept
        self.assertEqual(len(self.dashboard.trade_history), 3)
        self.assertEqual(self.dashboard.trade_history[0].trade_id, "trade_2")
        self.assertEqual(self.dashboard.trade_history[-1].trade_id, "trade_4")
    
    def test_update_performance_metrics(self):
        """Test performance metrics update."""
        metrics = DataPerformanceMetrics(
            fetch_time_ms=50.0,
            cache_hit_rate=0.85,
            data_quality_score=0.95,
            indicator_calculation_time_ms=25.0,
            memory_usage_mb=150.0,
            active_pairs=5,
            total_data_points=10000
        )
        
        with patch.object(self.dashboard, '_broadcast_update') as mock_broadcast:
            self.dashboard.update_performance_metrics(metrics)
            
            self.assertEqual(self.dashboard.performance_metrics, metrics)
            mock_broadcast.assert_called_once_with('performance_update', unittest.mock.ANY)
    
    def test_update_system_health(self):
        """Test system health update."""
        health = SystemHealth(
            bot_uptime=24.5,
            cpu_usage=45.2,
            memory_usage=67.8,
            api_rate_limit_used=850,
            api_rate_limit_max=1000,
            websocket_connected=True,
            last_heartbeat=datetime.now(),
            error_rate_24h=0.02,
            active_strategies=["Enhanced Momentum", "Mean Reversion"],
            trading_enabled=True
        )
        
        with patch.object(self.dashboard, '_broadcast_update') as mock_broadcast:
            self.dashboard.update_system_health(health)
            
            self.assertEqual(self.dashboard.system_health, health)
            mock_broadcast.assert_called_once_with('system_health_update', unittest.mock.ANY)
    
    def test_validate_trade_request_valid(self):
        """Test valid trade request validation."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        # Mock risk manager validation
        mock_risk_assessment = Mock()
        mock_risk_assessment.approved = True
        self.mock_risk_manager.validate_trade.return_value = mock_risk_assessment
        
        result = self.dashboard._validate_trade_request(request)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Trade request validated")
    
    def test_validate_trade_request_missing_params(self):
        """Test trade request validation with missing parameters."""
        request = ManualTradeRequest(
            pair="",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        result = self.dashboard._validate_trade_request(request)
        
        self.assertFalse(result.success)
        self.assertIn("Missing required trade parameters", result.error)
    
    def test_validate_trade_request_invalid_volume(self):
        """Test trade request validation with invalid volume."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=-0.1
        )
        
        result = self.dashboard._validate_trade_request(request)
        
        self.assertFalse(result.success)
        self.assertIn("Volume must be positive", result.error)
    
    def test_validate_trade_request_limit_without_price(self):
        """Test limit order validation without price."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="limit",
            volume=0.1
        )
        
        result = self.dashboard._validate_trade_request(request)
        
        self.assertFalse(result.success)
        self.assertIn("Price required for limit orders", result.error)
    
    def test_validate_trade_request_risk_rejection(self):
        """Test trade request rejected by risk manager."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        # Mock risk manager rejection
        mock_risk_assessment = Mock()
        mock_risk_assessment.approved = False
        mock_risk_assessment.reason = "Exceeds position limit"
        self.mock_risk_manager.validate_trade.return_value = mock_risk_assessment
        
        result = self.dashboard._validate_trade_request(request)
        
        self.assertFalse(result.success)
        self.assertIn("Trade rejected by risk manager", result.error)
        self.assertIn("Exceeds position limit", result.error)
    
    def test_execute_market_order_success(self):
        """Test successful market order execution."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        # Mock successful Kraken response
        self.mock_kraken_client.place_market_order.return_value = {
            'txid': ['test_order_123']
        }
        
        with patch.object(self.dashboard, 'add_trade_event') as mock_add_trade:
            result = self.dashboard._execute_market_order(request)
            
            self.assertTrue(result.success)
            self.assertEqual(result.trade_id, 'test_order_123')
            self.assertIn("Market buy order placed successfully", result.message)
            
            # Check that trade event was added
            mock_add_trade.assert_called_once()
            trade_arg = mock_add_trade.call_args[0][0]
            self.assertEqual(trade_arg.trade_id, 'test_order_123')
            self.assertEqual(trade_arg.pair, "BTC/USD")
            self.assertEqual(trade_arg.side, "BUY")
            
            # Verify Kraken client was called correctly
            self.mock_kraken_client.place_market_order.assert_called_once_with(
                "BTC/USD", "buy", "0.1"
            )
    
    def test_execute_market_order_failure(self):
        """Test failed market order execution."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        # Mock failed Kraken response
        self.mock_kraken_client.place_market_order.return_value = None
        
        result = self.dashboard._execute_market_order(request)
        
        self.assertFalse(result.success)
        self.assertIn("Failed to place market order", result.error)
    
    def test_execute_limit_order_success(self):
        """Test successful limit order execution."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="sell",
            order_type="limit",
            volume=0.1,
            price=51000.0
        )
        
        # Mock successful Kraken response
        self.mock_kraken_client.place_limit_order.return_value = {
            'txid': ['test_limit_order_456']
        }
        
        with patch.object(self.dashboard, 'add_trade_event') as mock_add_trade:
            result = self.dashboard._execute_limit_order(request)
            
            self.assertTrue(result.success)
            self.assertEqual(result.trade_id, 'test_limit_order_456')
            self.assertIn("Limit sell order placed successfully", result.message)
            
            # Check that trade event was added
            mock_add_trade.assert_called_once()
            trade_arg = mock_add_trade.call_args[0][0]
            self.assertEqual(trade_arg.trade_id, 'test_limit_order_456')
            self.assertEqual(trade_arg.order_type, "LIMIT")
            self.assertEqual(trade_arg.price, 51000.0)
    
    def test_handle_manual_trade_request_disabled(self):
        """Test manual trade request when trading is disabled."""
        self.dashboard.config.enable_manual_trading = False
        
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        result = self.dashboard.handle_manual_trade_request(request)
        
        self.assertFalse(result.success)
        self.assertIn("Manual trading is disabled", result.error)
    
    def test_handle_manual_trade_request_market_order(self):
        """Test handling manual market order request."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        # Mock validation success
        with patch.object(self.dashboard, '_validate_trade_request') as mock_validate, \
             patch.object(self.dashboard, '_execute_market_order') as mock_execute:
            
            mock_validate.return_value = TradeResult(success=True)
            mock_execute.return_value = TradeResult(success=True, trade_id="test_123")
            
            result = self.dashboard.handle_manual_trade_request(request)
            
            self.assertTrue(result.success)
            mock_validate.assert_called_once_with(request)
            mock_execute.assert_called_once_with(request)
    
    def test_handle_manual_trade_request_limit_order(self):
        """Test handling manual limit order request."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="limit",
            volume=0.1,
            price=49000.0
        )
        
        # Mock validation success
        with patch.object(self.dashboard, '_validate_trade_request') as mock_validate, \
             patch.object(self.dashboard, '_execute_limit_order') as mock_execute:
            
            mock_validate.return_value = TradeResult(success=True)
            mock_execute.return_value = TradeResult(success=True, trade_id="test_456")
            
            result = self.dashboard.handle_manual_trade_request(request)
            
            self.assertTrue(result.success)
            mock_validate.assert_called_once_with(request)
            mock_execute.assert_called_once_with(request)
    
    def test_handle_manual_trade_request_validation_failure(self):
        """Test handling manual trade request with validation failure."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="market",
            volume=0.1
        )
        
        # Mock validation failure
        with patch.object(self.dashboard, '_validate_trade_request') as mock_validate:
            mock_validate.return_value = TradeResult(
                success=False,
                error="Invalid trade parameters"
            )
            
            result = self.dashboard.handle_manual_trade_request(request)
            
            self.assertFalse(result.success)
            self.assertEqual(result.error, "Invalid trade parameters")
    
    @patch('bot.enhanced_dashboard.psutil')
    def test_update_system_health(self, mock_psutil):
        """Test system health update."""
        # Mock psutil
        mock_psutil.cpu_percent.return_value = 45.2
        mock_memory = Mock()
        mock_memory.percent = 67.8
        mock_psutil.virtual_memory.return_value = mock_memory
        
        with patch.object(self.dashboard, 'update_system_health') as mock_update:
            self.dashboard._update_system_health()
            
            mock_update.assert_called_once()
            health_arg = mock_update.call_args[0][0]
            self.assertEqual(health_arg.cpu_usage, 45.2)
            self.assertEqual(health_arg.memory_usage, 67.8)
            self.assertTrue(health_arg.trading_enabled)
    
    def test_broadcast_update(self):
        """Test WebSocket broadcast functionality."""
        test_data = {"test": "data"}
        
        with patch.object(self.dashboard.socketio, 'emit') as mock_emit:
            self.dashboard._broadcast_update('test_event', test_data)
            
            mock_emit.assert_called_once_with('test_event', test_data)
    
    def test_broadcast_update_disabled(self):
        """Test WebSocket broadcast when disabled."""
        self.dashboard.config.enable_websocket = False
        test_data = {"test": "data"}
        
        with patch.object(self.dashboard.socketio, 'emit') as mock_emit:
            self.dashboard._broadcast_update('test_event', test_data)
            
            mock_emit.assert_not_called()
    
    def test_background_update_loop(self):
        """Test background update loop."""
        self.dashboard.running = True
        
        # Mock data manager method
        mock_metrics = DataPerformanceMetrics(
            fetch_time_ms=50.0,
            cache_hit_rate=0.85,
            data_quality_score=0.95,
            indicator_calculation_time_ms=25.0,
            memory_usage_mb=150.0,
            active_pairs=5,
            total_data_points=10000
        )
        self.mock_data_manager.calculate_performance_metrics.return_value = mock_metrics
        
        with patch.object(self.dashboard, '_update_system_health') as mock_update_health, \
             patch.object(self.dashboard, 'update_performance_metrics') as mock_update_perf, \
             patch('time.sleep') as mock_sleep:
            
            # Run one iteration
            def stop_after_one_iteration(*args):
                self.dashboard.running = False
            
            mock_sleep.side_effect = stop_after_one_iteration
            
            self.dashboard._background_update_loop()
            
            mock_update_health.assert_called_once()
            mock_update_perf.assert_called_once_with(mock_metrics)
            mock_sleep.assert_called_once_with(self.dashboard.config.auto_refresh_interval)


class TestDashboardConfig(unittest.TestCase):
    """Test cases for DashboardConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DashboardConfig()
        
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 8080)
        self.assertFalse(config.debug)
        self.assertEqual(config.auto_refresh_interval, 5)
        self.assertEqual(config.max_trade_history, 100)
        self.assertEqual(config.max_log_entries, 500)
        self.assertTrue(config.enable_manual_trading)
        self.assertTrue(config.enable_websocket)
        self.assertEqual(config.chart_data_points, 100)
        self.assertEqual(config.theme, "dark")
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = DashboardConfig(
            host="0.0.0.0",
            port=9090,
            debug=True,
            auto_refresh_interval=10,
            enable_manual_trading=False,
            theme="light"
        )
        
        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 9090)
        self.assertTrue(config.debug)
        self.assertEqual(config.auto_refresh_interval, 10)
        self.assertFalse(config.enable_manual_trading)
        self.assertEqual(config.theme, "light")


class TestDataStructures(unittest.TestCase):
    """Test cases for dashboard data structures."""
    
    def test_portfolio_creation(self):
        """Test Portfolio dataclass creation."""
        portfolio = Portfolio(
            total_value_usd=10000.0,
            available_balance=2000.0,
            positions={"BTC/USD": {"volume": 0.5}},
            daily_pnl=150.0,
            unrealized_pnl=300.0,
            realized_pnl=500.0
        )
        
        self.assertEqual(portfolio.total_value_usd, 10000.0)
        self.assertEqual(portfolio.available_balance, 2000.0)
        self.assertEqual(portfolio.daily_pnl, 150.0)
        self.assertIsInstance(portfolio.timestamp, datetime)
    
    def test_trade_execution_creation(self):
        """Test TradeExecution dataclass creation."""
        trade = TradeExecution(
            trade_id="test_123",
            pair="BTC/USD",
            side="BUY",
            order_type="MARKET",
            volume=0.1,
            price=50000.0,
            fee=25.0,
            timestamp=datetime.now(),
            strategy="Test Strategy",
            signal_confidence=0.85,
            execution_time_ms=150,
            status="FILLED"
        )
        
        self.assertEqual(trade.trade_id, "test_123")
        self.assertEqual(trade.pair, "BTC/USD")
        self.assertEqual(trade.side, "BUY")
        self.assertEqual(trade.volume, 0.1)
        self.assertEqual(trade.signal_confidence, 0.85)
    
    def test_system_health_creation(self):
        """Test SystemHealth dataclass creation."""
        health = SystemHealth(
            bot_uptime=24.5,
            cpu_usage=45.2,
            memory_usage=67.8,
            api_rate_limit_used=850,
            api_rate_limit_max=1000,
            websocket_connected=True,
            last_heartbeat=datetime.now(),
            error_rate_24h=0.02,
            active_strategies=["Strategy1", "Strategy2"],
            trading_enabled=True
        )
        
        self.assertEqual(health.bot_uptime, 24.5)
        self.assertEqual(health.cpu_usage, 45.2)
        self.assertTrue(health.websocket_connected)
        self.assertEqual(len(health.active_strategies), 2)
    
    def test_manual_trade_request_creation(self):
        """Test ManualTradeRequest dataclass creation."""
        request = ManualTradeRequest(
            pair="BTC/USD",
            side="buy",
            order_type="limit",
            volume=0.1,
            price=49000.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )
        
        self.assertEqual(request.pair, "BTC/USD")
        self.assertEqual(request.side, "buy")
        self.assertEqual(request.order_type, "limit")
        self.assertEqual(request.volume, 0.1)
        self.assertEqual(request.price, 49000.0)
        self.assertEqual(request.stop_loss, 48000.0)
        self.assertEqual(request.take_profit, 52000.0)
    
    def test_trade_result_creation(self):
        """Test TradeResult dataclass creation."""
        result = TradeResult(
            success=True,
            trade_id="test_456",
            message="Trade executed successfully",
            error=None
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.trade_id, "test_456")
        self.assertEqual(result.message, "Trade executed successfully")
        self.assertIsNone(result.error)


if __name__ == '__main__':
    unittest.main()