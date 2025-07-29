"""
End-to-end integration tests for complete trading workflows.
Tests the entire trading pipeline from signal generation to execution.
"""
import pytest
import time
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, List

from bot.main import BotOrchestrator, SystemHealth
from bot.config import Config
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.kraken_client import KrakenCredentials
from bot.enhanced_strategies import EnhancedStrategyEngine, StrategyParameters
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.enhanced_data_manager import EnhancedDataManager
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_alerts import EnhancedAlertSystem
from bot.enhanced_dashboard import EnhancedDashboard
from bot.kraken_websocket import KrakenWebSocketClient
from bot.strategy import TradingSignal, SignalType


class TestCompleteTrading Workflow:
    """Test complete trading workflows from signal to execution."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock(spec=Config)
        config.get_kraken_credentials.return_value = KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
        config.get_crypto_trading_settings.return_value = Mock()
        return config
    
    @pytest.fixture
    def mock_args(self):
        """Mock command line arguments."""
        args = Mock()
        args.trading_pairs = ["XBTUSD", "ETHUSD"]
        args.log_level = "INFO"
        args.log_file = "test.log"
        args.performance_monitoring = True
        args.paper_trading = True
        return args
    
    @pytest.fixture
    def orchestrator(self, mock_config, mock_args):
        """Create bot orchestrator for testing."""
        return BotOrchestrator(config=mock_config, args=mock_args)
    
    def test_complete_buy_signal_workflow(self, orchestrator):
        """Test complete workflow from buy signal generation to execution."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Setup mock components
            mock_strategy = mocks['EnhancedStrategyEngine'].return_value
            mock_risk = mocks['EnhancedRiskManager'].return_value
            mock_trader = mocks['KrakenTrader'].return_value
            mock_alerts = mocks['EnhancedAlertSystem'].return_value
            mock_logger = mocks['EnhancedLogger'].return_value
            
            # Mock buy signal generation
            buy_signal = TradingSignal(
                signal_type=SignalType.BUY,
                strength=0.8,
                price=50000.0,
                timestamp=datetime.now(),
                pair="XBTUSD",
                strategy="enhanced_momentum"
            )
            mock_strategy.generate_signal.return_value = buy_signal
            
            # Mock risk validation (approved)
            mock_risk.validate_trade.return_value = Mock(
                approved=True,
                position_size=0.001,
                risk_score=0.3
            )
            
            # Mock successful trade execution
            mock_trader.execute_market_buy.return_value = Mock(
                success=True,
                order_id="ORDER123",
                side="buy",
                volume="0.001",
                price="50000.0"
            )
            
            # Initialize components
            orchestrator.initialize_components()
            
            # Simulate market data update
            market_data = {
                "XBTUSD": {
                    "price": 50000.0,
                    "volume": 1.5,
                    "timestamp": datetime.now()
                }
            }
            
            # Execute trading cycle
            orchestrator.execute_trading_cycle(market_data)
            
            # Verify workflow execution
            mock_strategy.generate_signal.assert_called()
            mock_risk.validate_trade.assert_called()
            mock_trader.execute_market_buy.assert_called()
            mock_alerts.send_trade_alert.assert_called()
            mock_logger.log_trade.assert_called()
    
    def test_complete_sell_signal_workflow(self, orchestrator):
        """Test complete workflow from sell signal generation to execution."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Setup mock components
            mock_strategy = mocks['EnhancedStrategyEngine'].return_value
            mock_risk = mocks['EnhancedRiskManager'].return_value
            mock_trader = mocks['KrakenTrader'].return_value
            
            # Mock sell signal generation
            sell_signal = TradingSignal(
                signal_type=SignalType.SELL,
                strength=0.7,
                price=49000.0,
                timestamp=datetime.now(),
                pair="XBTUSD",
                strategy="enhanced_rsi"
            )
            mock_strategy.generate_signal.return_value = sell_signal
            
            # Mock risk validation (approved)
            mock_risk.validate_trade.return_value = Mock(
                approved=True,
                position_size=0.001,
                risk_score=0.2
            )
            
            # Mock successful trade execution
            mock_trader.execute_market_sell.return_value = Mock(
                success=True,
                order_id="ORDER124",
                side="sell",
                volume="0.001",
                price="49000.0"
            )
            
            # Initialize and execute
            orchestrator.initialize_components()
            
            market_data = {
                "XBTUSD": {
                    "price": 49000.0,
                    "volume": 2.0,
                    "timestamp": datetime.now()
                }
            }
            
            orchestrator.execute_trading_cycle(market_data)
            
            # Verify sell workflow
            mock_strategy.generate_signal.assert_called()
            mock_risk.validate_trade.assert_called()
            mock_trader.execute_market_sell.assert_called()
    
    def test_risk_rejection_workflow(self, orchestrator):
        """Test workflow when risk manager rejects a trade."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Setup mock components
            mock_strategy = mocks['EnhancedStrategyEngine'].return_value
            mock_risk = mocks['EnhancedRiskManager'].return_value
            mock_trader = mocks['KrakenTrader'].return_value
            mock_alerts = mocks['EnhancedAlertSystem'].return_value
            
            # Mock buy signal generation
            buy_signal = TradingSignal(
                signal_type=SignalType.BUY,
                strength=0.9,
                price=50000.0,
                timestamp=datetime.now(),
                pair="XBTUSD",
                strategy="enhanced_momentum"
            )
            mock_strategy.generate_signal.return_value = buy_signal
            
            # Mock risk validation (rejected)
            mock_risk.validate_trade.return_value = Mock(
                approved=False,
                rejection_reason="Portfolio risk limit exceeded",
                risk_score=0.9
            )
            
            # Initialize and execute
            orchestrator.initialize_components()
            
            market_data = {
                "XBTUSD": {
                    "price": 50000.0,
                    "volume": 1.0,
                    "timestamp": datetime.now()
                }
            }
            
            orchestrator.execute_trading_cycle(market_data)
            
            # Verify risk rejection workflow
            mock_strategy.generate_signal.assert_called()
            mock_risk.validate_trade.assert_called()
            mock_trader.execute_market_buy.assert_not_called()  # Should not execute
            mock_alerts.send_risk_alert.assert_called()  # Should send risk alert
    
    def test_multi_pair_trading_workflow(self, orchestrator):
        """Test multi-pair trading coordination."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Setup mock components
            mock_strategy = mocks['EnhancedStrategyEngine'].return_value
            mock_risk = mocks['EnhancedRiskManager'].return_value
            mock_trader = mocks['KrakenTrader'].return_value
            
            # Mock signals for multiple pairs
            def mock_generate_signal(pair, market_data):
                if pair == "XBTUSD":
                    return TradingSignal(
                        signal_type=SignalType.BUY,
                        strength=0.8,
                        price=50000.0,
                        timestamp=datetime.now(),
                        pair="XBTUSD",
                        strategy="enhanced_momentum"
                    )
                elif pair == "ETHUSD":
                    return TradingSignal(
                        signal_type=SignalType.SELL,
                        strength=0.7,
                        price=3000.0,
                        timestamp=datetime.now(),
                        pair="ETHUSD",
                        strategy="enhanced_rsi"
                    )
                return None
            
            mock_strategy.generate_signal.side_effect = mock_generate_signal
            
            # Mock risk validation (both approved)
            mock_risk.validate_trade.return_value = Mock(
                approved=True,
                position_size=0.001,
                risk_score=0.3
            )
            
            # Mock successful trades
            mock_trader.execute_market_buy.return_value = Mock(success=True, order_id="BUY123")
            mock_trader.execute_market_sell.return_value = Mock(success=True, order_id="SELL124")
            
            # Initialize and execute
            orchestrator.initialize_components()
            
            multi_pair_data = {
                "XBTUSD": {"price": 50000.0, "volume": 1.5, "timestamp": datetime.now()},
                "ETHUSD": {"price": 3000.0, "volume": 10.0, "timestamp": datetime.now()}
            }
            
            orchestrator.execute_multi_pair_trading_cycle(multi_pair_data)
            
            # Verify both pairs were processed
            assert mock_strategy.generate_signal.call_count == 2
            assert mock_risk.validate_trade.call_count == 2
            mock_trader.execute_market_buy.assert_called_once()
            mock_trader.execute_market_sell.assert_called_once()
    
    def test_error_recovery_workflow(self, orchestrator):
        """Test error recovery during trading workflow."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Setup mock components
            mock_strategy = mocks['EnhancedStrategyEngine'].return_value
            mock_risk = mocks['EnhancedRiskManager'].return_value
            mock_trader = mocks['KrakenTrader'].return_value
            mock_alerts = mocks['EnhancedAlertSystem'].return_value
            
            # Mock signal generation
            buy_signal = TradingSignal(
                signal_type=SignalType.BUY,
                strength=0.8,
                price=50000.0,
                timestamp=datetime.now(),
                pair="XBTUSD",
                strategy="enhanced_momentum"
            )
            mock_strategy.generate_signal.return_value = buy_signal
            
            # Mock risk validation (approved)
            mock_risk.validate_trade.return_value = Mock(
                approved=True,
                position_size=0.001,
                risk_score=0.3
            )
            
            # Mock trade execution failure
            mock_trader.execute_market_buy.return_value = Mock(
                success=False,
                error="Insufficient funds"
            )
            
            # Initialize and execute
            orchestrator.initialize_components()
            
            market_data = {
                "XBTUSD": {
                    "price": 50000.0,
                    "volume": 1.0,
                    "timestamp": datetime.now()
                }
            }
            
            orchestrator.execute_trading_cycle(market_data)
            
            # Verify error handling
            mock_trader.execute_market_buy.assert_called()
            mock_alerts.send_system_alert.assert_called()  # Should send error alert
    
    def test_websocket_data_integration(self, orchestrator):
        """Test integration with real-time WebSocket data."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Setup mock WebSocket client
            mock_ws = mocks['KrakenWebSocketClient'].return_value
            mock_data_manager = mocks['EnhancedDataManager'].return_value
            
            # Mock WebSocket connection and data
            mock_ws.connect.return_value = True
            mock_ws.subscribe_ticker.return_value = True
            
            # Mock real-time data processing
            def mock_process_ticker_data(pair, data):
                return {
                    "pair": pair,
                    "price": data.get("c", [0])[0],
                    "volume": data.get("v", [0])[0],
                    "timestamp": datetime.now()
                }
            
            mock_data_manager.process_ticker_data.side_effect = mock_process_ticker_data
            
            # Initialize components
            orchestrator.initialize_components()
            
            # Simulate WebSocket ticker data
            ticker_data = {
                "c": ["50000.0", "0.001"],  # Close price and volume
                "v": ["1.5", "10.0"],       # Volume
                "p": ["49500.0", "50500.0"] # Price range
            }
            
            # Process WebSocket data
            processed_data = mock_data_manager.process_ticker_data("XBTUSD", ticker_data)
            
            # Verify WebSocket integration
            mock_ws.connect.assert_called()
            mock_ws.subscribe_ticker.assert_called()
            assert processed_data["pair"] == "XBTUSD"
            assert processed_data["price"] == "50000.0"


class TestSystemHealthMonitoring:
    """Test system health monitoring during trading."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for health monitoring tests."""
        config = Mock(spec=Config)
        args = Mock()
        args.trading_pairs = ["XBTUSD"]
        return BotOrchestrator(config=config, args=args)
    
    def test_health_check_success(self, orchestrator):
        """Test successful system health check."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ):
            
            # Initialize components
            orchestrator.initialize_components()
            
            # Perform health check
            health = orchestrator.perform_health_check()
            
            # Verify health status
            assert isinstance(health, SystemHealth)
            assert health.is_healthy is True
            assert health.api_connection is True
            assert health.websocket_connection is True
    
    def test_health_check_api_failure(self, orchestrator):
        """Test health check with API connection failure."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Mock API connection failure
            mock_trader = mocks['KrakenTrader'].return_value
            mock_trader.client.get_server_time.return_value = None
            
            # Initialize components
            orchestrator.initialize_components()
            
            # Perform health check
            health = orchestrator.perform_health_check()
            
            # Verify health status reflects API failure
            assert health.is_healthy is False
            assert health.api_connection is False
    
    def test_graceful_shutdown(self, orchestrator):
        """Test graceful shutdown process."""
        with patch.multiple(
            'bot.main',
            EnhancedLogger=Mock(),
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedDashboard=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Initialize components
            orchestrator.initialize_components()
            
            # Initiate graceful shutdown
            orchestrator.initiate_graceful_shutdown()
            
            # Verify shutdown process
            assert orchestrator.shutdown_event.is_set()
            
            # Verify components are properly shut down
            mock_ws = mocks['KrakenWebSocketClient'].return_value
            mock_dashboard = mocks['EnhancedDashboard'].return_value
            
            mock_ws.disconnect.assert_called()
            mock_dashboard.stop_server.assert_called()