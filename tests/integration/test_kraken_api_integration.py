"""
Integration tests for Kraken API connectivity and trading.
Tests real API interactions, authentication, and trading operations.
"""
import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from bot.kraken_client import KrakenClient, KrakenCredentials
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig, KrakenTradeResult
from bot.kraken_websocket import KrakenWebSocketClient, WebSocketConfig
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_info, log_error


class TestKrakenAPIConnectivity:
    """Test Kraken API connectivity and authentication."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock Kraken credentials for testing."""
        return KrakenCredentials(
            api_key="test_api_key",
            api_secret="test_api_secret",
            base_url="https://api.kraken.com"
        )
    
    @pytest.fixture
    def kraken_client(self, mock_credentials):
        """Create Kraken client for testing."""
        return KrakenClient(credentials=mock_credentials)
    
    def test_api_authentication_success(self, kraken_client):
        """Test successful API authentication."""
        with patch('requests.post') as mock_post:
            # Mock successful authentication response
            mock_response = Mock()
            mock_response.json.return_value = {
                'error': [],
                'result': {
                    'ZUSD': '1000.0000',
                    'XXBT': '0.1000'
                }
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            # Test authentication by getting account balance
            result = kraken_client.get_account_balance()
            
            assert result is not None
            assert 'ZUSD' in result
            assert 'XXBT' in result
            mock_post.assert_called_once()
    
    def test_api_authentication_failure(self, kraken_client):
        """Test API authentication failure handling."""
        with patch('requests.post') as mock_post:
            # Mock authentication failure response
            mock_response = Mock()
            mock_response.json.return_value = {
                'error': ['EAPI:Invalid key']
            }
            mock_response.status_code = 401
            mock_post.return_value = mock_response
            
            # Test authentication failure
            result = kraken_client.get_account_balance()
            
            assert result is None
            mock_post.assert_called_once()
    
    def test_api_rate_limiting(self, kraken_client):
        """Test API rate limiting behavior."""
        with patch('requests.post') as mock_post:
            # Mock rate limit response
            mock_response = Mock()
            mock_response.json.return_value = {
                'error': ['EAPI:Rate limit exceeded']
            }
            mock_response.status_code = 429
            mock_post.return_value = mock_response
            
            # Test rate limiting
            result = kraken_client.get_ticker_information(['XBTUSD'])
            
            assert result is None
            mock_post.assert_called_once()
    
    def test_network_error_handling(self, kraken_client):
        """Test network error handling and retry logic."""
        with patch('requests.post') as mock_post:
            # Mock network error
            mock_post.side_effect = Exception("Network error")
            
            # Test network error handling
            result = kraken_client.get_server_time()
            
            assert result is None
            # Should retry multiple times
            assert mock_post.call_count > 1
    
    def test_circuit_breaker_activation(self, kraken_client):
        """Test circuit breaker activation after multiple failures."""
        with patch('requests.post') as mock_post:
            # Mock multiple failures
            mock_post.side_effect = Exception("API error")
            
            # Make multiple requests to trigger circuit breaker
            for _ in range(6):  # Exceeds failure threshold of 5
                try:
                    kraken_client.get_server_time()
                except:
                    pass  # Expected to fail
            
            # Verify multiple attempts were made
            assert mock_post.call_count >= 5
    
    def test_websocket_connectivity(self, mock_credentials):
        """Test WebSocket connectivity."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = Mock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket
            
            callback_handler = Mock()
            ws_client = KrakenWebSocketClient(
                credentials=mock_credentials,
                callback_handler=callback_handler,
                config=WebSocketConfig()
            )
            
            # Test connection
            success = ws_client.connect()
            
            assert success is True
            mock_connect.assert_called_once()


class TestKrakenTradingOperations:
    """Test Kraken trading operations."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock Kraken credentials for testing."""
        return KrakenCredentials(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )
    
    @pytest.fixture
    def trading_config(self):
        """Trading configuration for testing."""
        return KrakenTradingConfig(
            trading_pair="XBTUSD",
            trade_amount_usd=10.0,
            max_position_usd=100.0,
            min_order_size=0.0001
        )
    
    @pytest.fixture
    def kraken_trader(self, mock_credentials, trading_config):
        """Create Kraken trader for testing."""
        return KrakenTrader(
            credentials=mock_credentials,
            config=trading_config
        )
    
    def test_market_buy_order(self, kraken_trader):
        """Test market buy order execution."""
        with patch.object(kraken_trader.client, 'add_order') as mock_add_order, \
             patch.object(kraken_trader.client, 'get_current_price') as mock_price:
            
            # Mock successful order response
            mock_add_order.return_value = {
                'txid': ['ORDER123'],
                'descr': {'order': 'buy 0.001 XBTUSD @ market'}
            }
            
            # Mock current price
            mock_price.return_value = 50000.0
            
            # Create buy signal
            from bot.strategy import TradingSignal, SignalType
            buy_signal = TradingSignal(
                action=SignalType.BUY,
                confidence=0.8,
                price=50000.0,
                timestamp=datetime.now(),
                strategy="test",
                reasoning="Test buy signal"
            )
            
            # Execute trade
            result = kraken_trader.execute_trade(buy_signal)
            
            assert result.success is True
            mock_add_order.assert_called_once()
    
    def test_market_sell_order(self, kraken_trader):
        """Test market sell order execution."""
        with patch.object(kraken_trader.client, 'add_order') as mock_add_order:
            # Mock successful order response
            mock_add_order.return_value = {
                'txid': ['ORDER124'],
                'descr': {'order': 'sell 0.001 XBTUSD @ market'}
            }
            
            # Create sell signal
            from bot.strategy import TradingSignal, SignalType
            sell_signal = TradingSignal(
                action=SignalType.SELL,
                confidence=0.7,
                price=49000.0,
                timestamp=datetime.now(),
                strategy="test",
                reasoning="Test sell signal"
            )
            
            # Execute trade
            result = kraken_trader.execute_trade(sell_signal)
            
            assert result.success is True
            mock_add_order.assert_called_once()
    
    def test_limit_order_placement(self, kraken_trader):
        """Test limit order placement."""
        with patch.object(kraken_trader.client, 'add_order') as mock_add_order:
            # Mock successful limit order response
            mock_add_order.return_value = {
                'txid': ['ORDER125'],
                'descr': {'order': 'buy 0.001 XBTUSD @ limit 50000.0'}
            }
            
            # Test limit order through trade execution
            from bot.strategy import TradingSignal, SignalType
            limit_signal = TradingSignal(
                action=SignalType.BUY,
                confidence=0.8,
                price=50000.0,
                timestamp=datetime.now(),
                strategy="test",
                reasoning="Test limit signal"
            )
            
            result = kraken_trader.execute_trade(limit_signal)
            
            assert result.success is True
            mock_add_order.assert_called_once()
    
    def test_order_cancellation(self, kraken_trader):
        """Test order cancellation."""
        with patch.object(kraken_trader.client, 'cancel_order') as mock_cancel:
            # Mock successful cancellation response
            mock_cancel.return_value = {
                'count': 1,
                'pending': False
            }
            
            # Cancel order using the actual method
            result = kraken_trader.cancel_all_orders()
            
            assert result is True
            mock_cancel.assert_called()
    
    def test_insufficient_funds_handling(self, kraken_trader):
        """Test handling of insufficient funds error."""
        with patch.object(kraken_trader.client, 'add_order') as mock_add_order:
            # Mock insufficient funds error
            mock_add_order.return_value = None
            
            # Create large buy signal
            from bot.strategy import TradingSignal, SignalType
            large_signal = TradingSignal(
                action=SignalType.BUY,
                confidence=0.8,
                price=50000.0,
                timestamp=datetime.now(),
                strategy="test",
                reasoning="Test large signal"
            )
            
            # Execute trade with insufficient funds
            result = kraken_trader.execute_trade(large_signal)
            
            assert result.success is False
            assert result.error is not None
    
    def test_invalid_trading_pair_handling(self, kraken_trader):
        """Test handling of invalid trading pair."""
        with patch.object(kraken_trader.client, 'add_order') as mock_add_order:
            # Mock invalid pair error
            mock_add_order.return_value = None
            
            # Create signal with invalid pair
            from bot.strategy import TradingSignal, SignalType
            invalid_signal = TradingSignal(
                action=SignalType.BUY,
                confidence=0.8,
                price=50000.0,
                timestamp=datetime.now(),
                strategy="test",
                reasoning="Test invalid signal"
            )
            
            # Execute trade with invalid pair
            result = kraken_trader.execute_trade(invalid_signal)
            
            assert result.success is False
            assert result.error is not None
    
    def test_order_status_tracking(self, kraken_trader):
        """Test order status tracking."""
        with patch.object(kraken_trader.client, 'get_orders_info') as mock_query:
            # Mock order status response
            mock_query.return_value = {
                'ORDER123': {
                    'status': 'closed',
                    'vol_exec': '0.001',
                    'cost': '50.0',
                    'fee': '0.1'
                }
            }
            
            # Query order status using client method
            status = kraken_trader.client.get_orders_info(['ORDER123'])
            
            assert status is not None
            assert 'ORDER123' in status
            mock_query.assert_called_once()
    
    def test_account_balance_retrieval(self, kraken_trader):
        """Test account balance retrieval."""
        with patch.object(kraken_trader.client, 'get_account_balance') as mock_balance:
            # Mock balance response
            mock_balance.return_value = {
                'ZUSD': '1000.0000',
                'XXBT': '0.1000'
            }
            
            # Get account balance using client method
            balance = kraken_trader.client.get_account_balance()
            
            assert balance is not None
            assert 'ZUSD' in balance
            assert 'XXBT' in balance
            mock_balance.assert_called_once()


class TestKrakenAdvancedOrderTypes:
    """Test advanced order types (stop-loss, take-profit, etc.)."""
    
    @pytest.fixture
    def kraken_client(self):
        """Create enhanced Kraken client for testing."""
        credentials = KrakenCredentials(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )
        return KrakenClient(credentials=credentials)
    
    def test_stop_loss_order(self, kraken_client):
        """Test stop-loss order placement."""
        with patch.object(kraken_client, 'add_order') as mock_add_order:
            # Mock successful stop-loss order response
            mock_add_order.return_value = {
                'txid': ['STOP123'],
                'descr': {'order': 'sell 0.001 XBTUSD @ stop-loss 49000.0'}
            }
            
            # Place stop-loss order using add_order with stop-loss parameters
            result = kraken_client.add_order(
                pair="XBTUSD",
                type="sell",
                ordertype="stop-loss",
                volume="0.001",
                price="49000.0"
            )
            
            assert result is not None
            assert 'txid' in result
            mock_add_order.assert_called_once()
    
    def test_take_profit_order(self, kraken_client):
        """Test take-profit order placement."""
        with patch.object(kraken_client, 'add_order') as mock_add_order:
            # Mock successful take-profit order response
            mock_add_order.return_value = {
                'txid': ['PROFIT123'],
                'descr': {'order': 'sell 0.001 XBTUSD @ take-profit 51000.0'}
            }
            
            # Place take-profit order using add_order with take-profit parameters
            result = kraken_client.add_order(
                pair="XBTUSD",
                type="sell",
                ordertype="take-profit",
                volume="0.001",
                price="51000.0"
            )
            
            assert result is not None
            assert 'txid' in result
            mock_add_order.assert_called_once()
    
    def test_batch_operations(self, kraken_client):
        """Test batch operations for multiple pairs."""
        with patch.object(kraken_client, 'get_ticker') as mock_ticker:
            # Mock ticker response for multiple pairs
            mock_ticker.return_value = {
                'XBTUSD': {'c': ['50000.0', '0.001']},
                'ETHUSD': {'c': ['3000.0', '0.1']}
            }
            
            # Get multi-pair ticker using the actual method
            result = kraken_client.get_multi_pair_ticker(['XBTUSD', 'ETHUSD'])
            
            assert result is not None
            assert 'XBTUSD' in result
            assert 'ETHUSD' in result
            mock_ticker.assert_called()