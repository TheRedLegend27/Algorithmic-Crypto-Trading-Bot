"""
Error recovery and resilience tests.
Tests system behavior during various error conditions and recovery scenarios.
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock, side_effect
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from bot.main import BotOrchestrator, SystemHealth
from bot.kraken_client import KrakenClient, KrakenCredentials, CircuitBreakerState
from bot.kraken_websocket import KrakenWebSocketClient, WebSocketState
from bot.enhanced_alerts import EnhancedAlertSystem, AlertSeverity
from bot.enhanced_logger import EnhancedLogger
from bot.error_handler import ErrorHandler


class TestAPIErrorRecovery:
    """Test API error recovery scenarios."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock Kraken credentials."""
        return KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
    
    @pytest.fixture
    def kraken_client(self, mock_credentials):
        """Kraken client for error testing."""
        return KrakenClient(credentials=mock_credentials)
    
    def test_network_timeout_recovery(self, kraken_client):
        """Test recovery from network timeout errors."""
        with patch('requests.post') as mock_post:
            # Simulate network timeout followed by success
            mock_post.side_effect = [
                Exception("Connection timeout"),
                Exception("Connection timeout"),
                Mock(json=lambda: {'error': [], 'result': {'unixtime': 1234567890}}, status_code=200)
            ]
            
            # Attempt API call with retries
            result = kraken_client.get_server_time()
            
            # Verify recovery after timeouts
            assert result is not None
            assert mock_post.call_count == 3  # Should retry after failures
    
    def test_rate_limit_recovery(self, kraken_client):
        """Test recovery from rate limiting."""
        with patch('requests.post') as mock_post:
            # Simulate rate limit followed by success
            mock_post.side_effect = [
                Mock(json=lambda: {'error': ['EAPI:Rate limit exceeded']}, status_code=429),
                Mock(json=lambda: {'error': []}, status_code=200)
            ]
            
            with patch('time.sleep') as mock_sleep:
                # Attempt API call
                result = kraken_client.get_server_time()
                
                # Verify rate limit handling
                assert mock_post.call_count == 2
                mock_sleep.assert_called()  # Should wait before retry
    
    def test_authentication_error_handling(self, kraken_client):
        """Test handling of authentication errors."""
        with patch('requests.post') as mock_post:
            # Simulate authentication error
            mock_post.return_value = Mock(
                json=lambda: {'error': ['EAPI:Invalid key']},
                status_code=401
            )
            
            # Attempt authenticated API call
            result = kraken_client.get_account_balance()
            
            # Verify authentication error handling
            assert result is None
            assert mock_post.call_count == 1  # Should not retry auth errors
    
    def test_circuit_breaker_recovery(self, kraken_client):
        """Test circuit breaker recovery mechanism."""
        with patch('requests.post') as mock_post:
            # Simulate multiple failures to trigger circuit breaker
            mock_post.side_effect = [Exception("API error")] * 6
            
            # Make multiple calls to trigger circuit breaker
            for _ in range(6):
                kraken_client.get_server_time()
            
            # Verify circuit breaker is open
            assert kraken_client.circuit_breaker.state == CircuitBreakerState.OPEN
            
            # Simulate recovery after timeout
            with patch('time.time') as mock_time:
                # Fast-forward time to allow circuit breaker recovery
                mock_time.return_value = time.time() + 120  # 2 minutes later
                
                # Mock successful response for recovery
                mock_post.side_effect = None
                mock_post.return_value = Mock(
                    json=lambda: {'error': [], 'result': {'unixtime': 1234567890}},
                    status_code=200
                )
                
                # Attempt API call after recovery timeout
                result = kraken_client.get_server_time()
                
                # Verify circuit breaker recovery
                assert result is not None
                assert kraken_client.circuit_breaker.state == CircuitBreakerState.CLOSED
    
    def test_partial_api_failure_handling(self, kraken_client):
        """Test handling of partial API failures."""
        with patch('requests.post') as mock_post:
            # Mock partial failure response
            mock_post.return_value = Mock(
                json=lambda: {
                    'error': ['EQuery:Unknown asset pair'],
                    'result': {}
                },
                status_code=200
            )
            
            # Attempt to get ticker for invalid pair
            result = kraken_client.get_ticker_information(['INVALID'])
            
            # Verify partial failure handling
            assert result is None
            assert mock_post.call_count == 1


class TestWebSocketErrorRecovery:
    """Test WebSocket error recovery scenarios."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock credentials for WebSocket testing."""
        return KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
    
    @pytest.fixture
    def callback_handler(self):
        """Mock callback handler."""
        handler = Mock()
        handler.on_connection_status = Mock()
        handler.on_error = Mock()
        handler.on_ticker = Mock()
        return handler
    
    def test_websocket_connection_failure_recovery(self, mock_credentials, callback_handler):
        """Test WebSocket connection failure and recovery."""
        with patch('websockets.connect') as mock_connect:
            # Simulate connection failure followed by success
            mock_connect.side_effect = [
                Exception("Connection failed"),
                Exception("Connection failed"),
                Mock(__aenter__=Mock(return_value=Mock()), __aexit__=Mock())
            ]
            
            ws_client = KrakenWebSocketClient(
                credentials=mock_credentials,
                callback_handler=callback_handler
            )
            
            # Attempt connection with retries
            success = ws_client.connect()
            
            # Verify connection recovery
            assert success is True
            assert mock_connect.call_count == 3
            callback_handler.on_connection_status.assert_called()
    
    def test_websocket_disconnection_recovery(self, mock_credentials, callback_handler):
        """Test WebSocket disconnection and auto-reconnect."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = Mock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket
            
            # Simulate message receiving with disconnection
            async def mock_recv():
                # First few messages succeed
                if mock_recv.call_count < 3:
                    mock_recv.call_count += 1
                    return '{"event":"heartbeat"}'
                else:
                    # Then simulate disconnection
                    raise Exception("Connection lost")
            
            mock_recv.call_count = 0
            mock_websocket.recv = mock_recv
            
            ws_client = KrakenWebSocketClient(
                credentials=mock_credentials,
                callback_handler=callback_handler
            )
            
            # Start WebSocket client
            ws_client.connect()
            
            # Simulate running for a short time
            time.sleep(0.1)
            
            # Verify disconnection was detected and recovery attempted
            callback_handler.on_error.assert_called()
    
    def test_websocket_message_parsing_errors(self, mock_credentials, callback_handler):
        """Test handling of WebSocket message parsing errors."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = Mock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket
            
            # Simulate invalid JSON messages
            mock_websocket.recv = Mock(side_effect=[
                '{"invalid": json}',  # Invalid JSON
                '{"valid": "json"}',  # Valid JSON
                'not json at all',    # Not JSON
                '{"event": "ticker"}' # Valid message
            ])
            
            ws_client = KrakenWebSocketClient(
                credentials=mock_credentials,
                callback_handler=callback_handler
            )
            
            # Process messages
            ws_client.connect()
            
            # Verify error handling for invalid messages
            callback_handler.on_error.assert_called()
    
    def test_websocket_subscription_failure_recovery(self, mock_credentials, callback_handler):
        """Test recovery from subscription failures."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = Mock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket
            
            # Mock subscription responses
            subscription_responses = [
                '{"event":"subscriptionStatus","status":"error","errorMessage":"Invalid pair"}',
                '{"event":"subscriptionStatus","status":"subscribed","pair":"XBTUSD"}'
            ]
            
            mock_websocket.recv = Mock(side_effect=subscription_responses)
            
            ws_client = KrakenWebSocketClient(
                credentials=mock_credentials,
                callback_handler=callback_handler
            )
            
            # Attempt subscription
            ws_client.connect()
            success = ws_client.subscribe_ticker(["INVALID", "XBTUSD"])
            
            # Verify subscription error handling and recovery
            callback_handler.on_subscription_status.assert_called()


class TestTradingErrorRecovery:
    """Test trading operation error recovery."""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock bot orchestrator for testing."""
        config = Mock()
        args = Mock()
        args.trading_pairs = ["XBTUSD"]
        return BotOrchestrator(config=config, args=args)
    
    def test_insufficient_funds_recovery(self, mock_orchestrator):
        """Test recovery from insufficient funds errors."""
        with patch.multiple(
            'bot.main',
            KrakenTrader=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock()
        ) as mocks:
            
            trader = mocks['KrakenTrader'].return_value
            risk_manager = mocks['EnhancedRiskManager'].return_value
            alert_system = mocks['EnhancedAlertSystem'].return_value
            
            # Mock insufficient funds error
            trader.execute_market_buy.return_value = Mock(
                success=False,
                error="Insufficient funds"
            )
            
            # Mock risk manager adjustment
            risk_manager.adjust_position_size.return_value = 0.0005  # Smaller size
            
            # Mock successful retry with smaller size
            trader.execute_market_buy.side_effect = [
                Mock(success=False, error="Insufficient funds"),
                Mock(success=True, order_id="RETRY123")
            ]
            
            # Initialize and attempt trade
            mock_orchestrator.initialize_components()
            
            # Simulate trading cycle with insufficient funds
            market_data = {"XBTUSD": {"price": 50000.0, "volume": 1.0}}
            mock_orchestrator.execute_trading_cycle(market_data)
            
            # Verify error recovery
            risk_manager.adjust_position_size.assert_called()
            alert_system.send_system_alert.assert_called()
    
    def test_order_rejection_recovery(self, mock_orchestrator):
        """Test recovery from order rejection."""
        with patch.multiple(
            'bot.main',
            KrakenTrader=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedAlertSystem=Mock()
        ) as mocks:
            
            trader = mocks['KrakenTrader'].return_value
            strategy_engine = mocks['EnhancedStrategyEngine'].return_value
            alert_system = mocks['EnhancedAlertSystem'].return_value
            
            # Mock order rejection
            trader.execute_market_buy.return_value = Mock(
                success=False,
                error="Order rejected: Invalid price"
            )
            
            # Mock strategy adjustment
            strategy_engine.adjust_signal_parameters.return_value = True
            
            # Initialize and attempt trade
            mock_orchestrator.initialize_components()
            
            market_data = {"XBTUSD": {"price": 50000.0, "volume": 1.0}}
            mock_orchestrator.execute_trading_cycle(market_data)
            
            # Verify order rejection handling
            alert_system.send_system_alert.assert_called()
    
    def test_market_closure_handling(self, mock_orchestrator):
        """Test handling of market closure scenarios."""
        with patch.multiple(
            'bot.main',
            KrakenTrader=Mock(),
            EnhancedLogger=Mock(),
            EnhancedAlertSystem=Mock()
        ) as mocks:
            
            trader = mocks['KrakenTrader'].return_value
            logger = mocks['EnhancedLogger'].return_value
            alert_system = mocks['EnhancedAlertSystem'].return_value
            
            # Mock market closure error
            trader.execute_market_buy.return_value = Mock(
                success=False,
                error="Market closed"
            )
            
            # Initialize and attempt trade during market closure
            mock_orchestrator.initialize_components()
            
            market_data = {"XBTUSD": {"price": 50000.0, "volume": 1.0}}
            mock_orchestrator.execute_trading_cycle(market_data)
            
            # Verify market closure handling
            logger.log_system_event.assert_called()
            alert_system.send_system_alert.assert_called()


class TestSystemResilienceScenarios:
    """Test overall system resilience scenarios."""
    
    def test_cascading_failure_recovery(self):
        """Test recovery from cascading system failures."""
        with patch.multiple(
            'bot.main',
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            KrakenTrader=Mock(),
            EnhancedAlertSystem=Mock()
        ) as mocks:
            
            # Simulate cascading failures
            data_manager = mocks['EnhancedDataManager'].return_value
            ws_client = mocks['KrakenWebSocketClient'].return_value
            strategy_engine = mocks['EnhancedStrategyEngine'].return_value
            trader = mocks['KrakenTrader'].return_value
            alert_system = mocks['EnhancedAlertSystem'].return_value
            
            # Mock failures in sequence
            data_manager.process_market_data.side_effect = Exception("Data processing error")
            ws_client.connect.return_value = False
            strategy_engine.generate_signal.side_effect = Exception("Strategy error")
            trader.execute_market_buy.side_effect = Exception("Trading error")
            
            config = Mock()
            args = Mock()
            args.trading_pairs = ["XBTUSD"]
            orchestrator = BotOrchestrator(config=config, args=args)
            
            # Initialize with failures
            orchestrator.initialize_components()
            
            # Attempt trading cycle with multiple failures
            market_data = {"XBTUSD": {"price": 50000.0, "volume": 1.0}}
            orchestrator.execute_trading_cycle(market_data)
            
            # Verify system continues despite failures
            alert_system.send_system_alert.assert_called()
    
    def test_memory_pressure_recovery(self):
        """Test recovery from memory pressure situations."""
        with patch('psutil.virtual_memory') as mock_memory:
            # Simulate high memory usage
            mock_memory.return_value = Mock(percent=95.0)  # 95% memory usage
            
            with patch.multiple(
                'bot.main',
                EnhancedDataManager=Mock(),
                EnhancedLogger=Mock()
            ) as mocks:
                
                data_manager = mocks['EnhancedDataManager'].return_value
                logger = mocks['EnhancedLogger'].return_value
                
                # Mock memory cleanup
                data_manager.cleanup_cache.return_value = True
                
                config = Mock()
                args = Mock()
                orchestrator = BotOrchestrator(config=config, args=args)
                
                # Trigger memory pressure handling
                orchestrator.handle_memory_pressure()
                
                # Verify memory cleanup was triggered
                data_manager.cleanup_cache.assert_called()
                logger.log_system_event.assert_called()
    
    def test_database_connection_recovery(self):
        """Test recovery from database connection issues."""
        with patch('bot.enhanced_logger.EnhancedLogger') as MockLogger:
            logger = MockLogger.return_value
            
            # Simulate database connection failure
            logger.log_trade.side_effect = [
                Exception("Database connection lost"),
                Exception("Database connection lost"),
                None  # Success after recovery
            ]
            
            # Mock database recovery
            logger.reconnect_database.return_value = True
            
            # Attempt logging with database failures
            for attempt in range(3):
                try:
                    logger.log_trade({"trade_id": f"TEST{attempt}"})
                except Exception:
                    logger.reconnect_database()
            
            # Verify database recovery attempts
            assert logger.reconnect_database.call_count >= 1
    
    def test_configuration_reload_recovery(self):
        """Test recovery through configuration reload."""
        with patch('bot.config.Config') as MockConfig:
            config = MockConfig.return_value
            
            # Mock configuration reload
            config.reload_configuration.return_value = True
            config.validate_configuration.return_value = True
            
            # Simulate configuration-related error
            config.get_trading_pairs.side_effect = [
                Exception("Configuration error"),
                ["XBTUSD", "ETHUSD"]  # Success after reload
            ]
            
            args = Mock()
            orchestrator = BotOrchestrator(config=config, args=args)
            
            # Attempt to get trading pairs with error recovery
            try:
                pairs = config.get_trading_pairs()
            except Exception:
                config.reload_configuration()
                pairs = config.get_trading_pairs()
            
            # Verify configuration recovery
            assert pairs == ["XBTUSD", "ETHUSD"]
            config.reload_configuration.assert_called()
    
    def test_emergency_shutdown_scenario(self):
        """Test emergency shutdown in critical error scenarios."""
        with patch.multiple(
            'bot.main',
            EnhancedRiskManager=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedLogger=Mock()
        ) as mocks:
            
            risk_manager = mocks['EnhancedRiskManager'].return_value
            alert_system = mocks['EnhancedAlertSystem'].return_value
            logger = mocks['EnhancedLogger'].return_value
            
            # Mock critical risk condition
            risk_manager.check_emergency_conditions.return_value = Mock(
                emergency_shutdown_required=True,
                reason="Critical portfolio loss detected"
            )
            
            config = Mock()
            args = Mock()
            orchestrator = BotOrchestrator(config=config, args=args)
            
            # Initialize components
            orchestrator.initialize_components()
            
            # Trigger emergency shutdown check
            orchestrator.check_emergency_conditions()
            
            # Verify emergency shutdown procedures
            alert_system.send_emergency_alert.assert_called()
            logger.log_emergency_shutdown.assert_called()
    
    def test_partial_system_recovery(self):
        """Test recovery when only part of the system fails."""
        with patch.multiple(
            'bot.main',
            EnhancedDataManager=Mock(),
            KrakenWebSocketClient=Mock(),
            EnhancedStrategyEngine=Mock(),
            KrakenTrader=Mock()
        ) as mocks:
            
            # Mock partial failure - only WebSocket fails
            data_manager = mocks['EnhancedDataManager'].return_value
            ws_client = mocks['KrakenWebSocketClient'].return_value
            strategy_engine = mocks['EnhancedStrategyEngine'].return_value
            trader = mocks['KrakenTrader'].return_value
            
            # WebSocket fails, but other components work
            ws_client.connect.return_value = False
            data_manager.process_market_data.return_value = {"processed": True}
            strategy_engine.generate_signal.return_value = Mock(signal_type="BUY")
            trader.execute_market_buy.return_value = Mock(success=True)
            
            config = Mock()
            args = Mock()
            orchestrator = BotOrchestrator(config=config, args=args)
            
            # Initialize with partial failure
            orchestrator.initialize_components()
            
            # System should continue operating without WebSocket
            market_data = {"XBTUSD": {"price": 50000.0, "volume": 1.0}}
            orchestrator.execute_trading_cycle(market_data)
            
            # Verify system continues with available components
            data_manager.process_market_data.assert_called()
            strategy_engine.generate_signal.assert_called()
            trader.execute_market_buy.assert_called()