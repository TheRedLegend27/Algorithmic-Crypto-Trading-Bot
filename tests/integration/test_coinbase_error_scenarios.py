"""
Integration tests for Coinbase error scenarios and recovery.
Tests error handling, retry logic, and recovery strategies.
"""
import unittest
import pytest
from unittest.mock import patch, Mock, MagicMock
import requests
import json
import time
from datetime import datetime, timedelta
import os

from bot.config import Config
from bot.coinbase_client import CoinbaseClient
from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.coinbase_trader import CoinbaseTrader
from bot.coinbase_websocket import CoinbaseWebSocket
from bot.crypto_order_manager import CryptoOrderManager
from bot.crypto_position_manager import CryptoPositionManager
from bot.crypto_risk_manager import CryptoRiskManager
from bot.coinbase_error_handler import CoinbaseErrorHandler


class TestCoinbaseErrorScenarios:
    """Tests for Coinbase error scenarios and recovery."""
    
    @pytest.fixture
    def setup_environment(self):
        """Set up environment variables for testing."""
        original_env = os.environ.copy()
        os.environ.update({
            'COINBASE_API_KEY': 'test_key',
            'COINBASE_API_SECRET': 'dGVzdF9zZWNyZXQ=',  # base64 encoded "test_secret"
            'COINBASE_PASSPHRASE': 'test_passphrase',
            'COINBASE_SANDBOX': 'True'
        })
        yield
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
    
    @pytest.fixture
    def config(self, setup_environment):
        """Create test configuration."""
        config = Config()
        config.load_env_variables()
        return config
    
    @pytest.fixture
    def credentials(self, config):
        """Get Coinbase credentials from config."""
        return config.get_coinbase_credentials()
    
    @pytest.fixture
    def crypto_settings(self, config):
        """Get crypto trading settings from config."""
        return config.get_crypto_trading_settings()
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler."""
        return CoinbaseErrorHandler()
    
    @pytest.fixture
    def mock_coinbase_client(self, credentials):
        """Create mock Coinbase client."""
        with patch('bot.coinbase_client.requests.Session'):
            client = CoinbaseClient(credentials)
            return client
    
    @pytest.fixture
    def data_fetcher(self, mock_coinbase_client):
        """Create data fetcher."""
        return CoinbaseDataFetcher(mock_coinbase_client)
    
    @pytest.fixture
    def position_manager(self, mock_coinbase_client, crypto_settings):
        """Create position manager."""
        return CryptoPositionManager(mock_coinbase_client, crypto_settings)
    
    @pytest.fixture
    def order_manager(self, mock_coinbase_client, crypto_settings):
        """Create order manager."""
        return CryptoOrderManager(mock_coinbase_client, crypto_settings)
    
    @pytest.fixture
    def risk_manager(self, position_manager, crypto_settings):
        """Create risk manager."""
        return CryptoRiskManager(position_manager, crypto_settings)
    
    @pytest.fixture
    def trader(self, mock_coinbase_client, position_manager, order_manager, risk_manager, crypto_settings):
        """Create trader."""
        return CoinbaseTrader(
            client=mock_coinbase_client,
            position_manager=position_manager,
            order_manager=order_manager,
            risk_manager=risk_manager,
            settings=crypto_settings
        )
    
    def test_authentication_error_handling(self, mock_coinbase_client, error_handler):
        """Test authentication error handling."""
        # Create mock response for authentication error
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'message': 'Invalid API Key',
            'type': 'authentication_error'
        }
        
        # Configure client to raise authentication error
        mock_coinbase_client.make_request = Mock(side_effect=requests.exceptions.HTTPError(response=mock_response))
        
        # Test error handling
        with patch.object(error_handler, 'handle_authentication_error') as mock_handle_auth_error:
            mock_handle_auth_error.return_value = False  # Don't retry
            
            # Attempt to make request
            success, result, error_msg = error_handler.handle_request_error(
                lambda: mock_coinbase_client.make_request('GET', '/accounts')
            )
            
            # Verify error was handled
            assert success is False
            assert error_msg is not None
            mock_handle_auth_error.assert_called_once()
    
    def test_rate_limit_error_handling(self, mock_coinbase_client, error_handler):
        """Test rate limit error handling."""
        # Create mock responses for rate limit error then success
        mock_rate_limit_response = Mock()
        mock_rate_limit_response.status_code = 429
        mock_rate_limit_response.json.return_value = {
            'message': 'Rate limit exceeded',
            'type': 'rate_limit_error'
        }
        
        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {'success': True}
        
        # Configure client to raise rate limit error then succeed
        mock_coinbase_client.make_request = Mock(side_effect=[
            requests.exceptions.HTTPError(response=mock_rate_limit_response),
            mock_success_response
        ])
        
        # Test error handling with retry
        with patch.object(error_handler, 'handle_rate_limit_error') as mock_handle_rate_limit:
            mock_handle_rate_limit.return_value = True  # Retry
            
            # Attempt to make request
            with patch('time.sleep'):  # Skip sleep delay
                success, result, error_msg = error_handler.handle_request_error(
                    lambda: mock_coinbase_client.make_request('GET', '/accounts')
                )
                
                # Verify error was handled and retried successfully
                assert success is True
                assert result == {'success': True}
                mock_handle_rate_limit.assert_called_once()
    
    def test_insufficient_funds_error_handling(self, mock_coinbase_client, error_handler):
        """Test insufficient funds error handling."""
        # Create mock response for insufficient funds error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'message': 'Insufficient funds',
            'type': 'invalid_request'
        }
        
        # Configure client to raise insufficient funds error
        mock_coinbase_client.make_request = Mock(side_effect=requests.exceptions.HTTPError(response=mock_response))
        
        # Test error handling
        with patch.object(error_handler, 'handle_insufficient_funds_error') as mock_handle_funds_error:
            mock_handle_funds_error.return_value = False  # Don't retry
            
            # Attempt to make request
            success, result, error_msg = error_handler.handle_request_error(
                lambda: mock_coinbase_client.make_request('POST', '/orders')
            )
            
            # Verify error was handled
            assert success is False
            assert error_msg is not None
            assert 'Insufficient funds' in error_msg
            mock_handle_funds_error.assert_called_once()
    
    def test_invalid_order_error_handling(self, mock_coinbase_client, error_handler):
        """Test invalid order error handling."""
        # Create mock response for invalid order error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'message': 'Invalid order size',
            'type': 'invalid_request'
        }
        
        # Configure client to raise invalid order error
        mock_coinbase_client.make_request = Mock(side_effect=requests.exceptions.HTTPError(response=mock_response))
        
        # Test error handling
        with patch.object(error_handler, 'handle_invalid_order_error') as mock_handle_order_error:
            mock_handle_order_error.return_value = False  # Don't retry
            
            # Attempt to make request
            success, result, error_msg = error_handler.handle_request_error(
                lambda: mock_coinbase_client.make_request('POST', '/orders')
            )
            
            # Verify error was handled
            assert success is False
            assert error_msg is not None
            assert 'Invalid order' in error_msg
            mock_handle_order_error.assert_called_once()
    
    def test_network_error_handling(self, mock_coinbase_client, error_handler):
        """Test network error handling."""
        # Configure client to raise network error then succeed
        mock_coinbase_client.make_request = Mock(side_effect=[
            requests.exceptions.ConnectionError("Connection refused"),
            {'success': True}
        ])
        
        # Test error handling with retry
        with patch.object(error_handler, 'handle_network_error') as mock_handle_network_error:
            mock_handle_network_error.return_value = True  # Retry
            
            # Attempt to make request
            with patch('time.sleep'):  # Skip sleep delay
                success, result, error_msg = error_handler.handle_request_error(
                    lambda: mock_coinbase_client.make_request('GET', '/accounts')
                )
                
                # Verify error was handled and retried successfully
                assert success is True
                assert result == {'success': True}
                mock_handle_network_error.assert_called_once()
    
    def test_timeout_error_handling(self, mock_coinbase_client, error_handler):
        """Test timeout error handling."""
        # Configure client to raise timeout error then succeed
        mock_coinbase_client.make_request = Mock(side_effect=[
            requests.exceptions.Timeout("Request timed out"),
            {'success': True}
        ])
        
        # Test error handling with retry
        with patch.object(error_handler, 'handle_network_error') as mock_handle_network_error:
            mock_handle_network_error.return_value = True  # Retry
            
            # Attempt to make request
            with patch('time.sleep'):  # Skip sleep delay
                success, result, error_msg = error_handler.handle_request_error(
                    lambda: mock_coinbase_client.make_request('GET', '/accounts')
                )
                
                # Verify error was handled and retried successfully
                assert success is True
                assert result == {'success': True}
                mock_handle_network_error.assert_called_once()
    
    def test_exponential_backoff(self, error_handler):
        """Test exponential backoff for retries."""
        # Track sleep times
        sleep_times = []
        
        def mock_sleep(seconds):
            sleep_times.append(seconds)
        
        # Configure error handler for multiple retries
        with patch('time.sleep', side_effect=mock_sleep):
            # Simulate multiple rate limit errors
            for _ in range(3):
                error_handler.handle_rate_limit_error({})
        
        # Verify exponential backoff
        assert len(sleep_times) == 3
        assert sleep_times[1] > sleep_times[0]
        assert sleep_times[2] > sleep_times[1]
    
    def test_max_retries_handling(self, mock_coinbase_client, error_handler):
        """Test max retries handling."""
        # Configure client to always raise rate limit error
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            'message': 'Rate limit exceeded',
            'type': 'rate_limit_error'
        }
        
        mock_coinbase_client.make_request = Mock(side_effect=requests.exceptions.HTTPError(response=mock_response))
        
        # Test error handling with max retries
        with patch.object(error_handler, 'handle_rate_limit_error') as mock_handle_rate_limit:
            mock_handle_rate_limit.return_value = True  # Always retry
            
            # Set max retries
            error_handler.max_retries = 3
            
            # Attempt to make request
            with patch('time.sleep'):  # Skip sleep delay
                success, result, error_msg = error_handler.handle_request_error(
                    lambda: mock_coinbase_client.make_request('GET', '/accounts')
                )
                
                # Verify max retries was reached
                assert success is False
                assert error_msg is not None
                assert mock_handle_rate_limit.call_count == 3
    
    def test_data_fetcher_error_recovery(self, data_fetcher, mock_coinbase_client, error_handler):
        """Test data fetcher error recovery."""
        # Configure client to raise error then succeed
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            'message': 'Internal server error',
            'type': 'api_error'
        }
        
        # Mock responses
        mock_coinbase_client.make_request = Mock(side_effect=[
            requests.exceptions.HTTPError(response=mock_response),
            [
                [int(datetime.now().timestamp()) - i * 300, 45000.0, 45500.0, 44500.0, 45100.0, 1000.0] 
                for i in range(50)
            ]
        ])
        
        # Set error handler
        data_fetcher.error_handler = error_handler
        
        # Test data fetching with error recovery
        with patch('time.sleep'):  # Skip sleep delay
            with patch.object(data_fetcher, '_process_candles', return_value=pd.DataFrame({
                'open': [45000.0] * 50,
                'high': [45500.0] * 50,
                'low': [44500.0] * 50,
                'close': [45100.0] * 50,
                'volume': [1000.0] * 50
            })):
                # Fetch data
                data = data_fetcher.fetch_crypto_ohlcv('BTC-USD', timeframe='5m', limit=50)
                
                # Verify data was fetched successfully after retry
                assert data is not None
                assert len(data) == 50
                assert mock_coinbase_client.make_request.call_count == 2
    
    def test_order_manager_error_recovery(self, order_manager, mock_coinbase_client, error_handler):
        """Test order manager error recovery."""
        # Configure client to raise error then succeed
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'message': 'Invalid order size',
            'type': 'invalid_request'
        }
        
        # Mock responses
        mock_coinbase_client.make_request = Mock(side_effect=[
            requests.exceptions.HTTPError(response=mock_response),
            {
                'id': 'test-order-id',
                'product_id': 'BTC-USD',
                'side': 'buy',
                'size': '0.01',
                'price': '45100.0',
                'status': 'pending'
            }
        ])
        
        # Set error handler
        order_manager.error_handler = error_handler
        
        # Test order placement with error recovery
        with patch('time.sleep'):  # Skip sleep delay
            with patch.object(error_handler, 'handle_invalid_order_error') as mock_handle_order_error:
                mock_handle_order_error.return_value = True  # Retry with fixed order
                
                # Place order
                order = order_manager.place_market_order('buy', 'BTC-USD', 0.01)
                
                # Verify order was placed successfully after retry
                assert order is not None
                assert order['id'] == 'test-order-id'
                assert mock_coinbase_client.make_request.call_count == 2
                mock_handle_order_error.assert_called_once()
    
    def test_position_manager_error_recovery(self, position_manager, mock_coinbase_client, error_handler):
        """Test position manager error recovery."""
        # Configure client to raise error then succeed
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            'message': 'Internal server error',
            'type': 'api_error'
        }
        
        # Mock responses
        mock_coinbase_client.make_request = Mock(side_effect=[
            requests.exceptions.HTTPError(response=mock_response),
            [
                {'id': 'btc-account', 'currency': 'BTC', 'balance': '1.0', 'available': '1.0', 'hold': '0.0'},
                {'id': 'usd-account', 'currency': 'USD', 'balance': '50000.0', 'available': '50000.0', 'hold': '0.0'}
            ]
        ])
        
        # Set error handler
        position_manager.error_handler = error_handler
        
        # Test getting balance with error recovery
        with patch('time.sleep'):  # Skip sleep delay
            # Get balance
            balance = position_manager.get_crypto_balance('BTC')
            
            # Verify balance was fetched successfully after retry
            assert balance == 1.0
            assert mock_coinbase_client.make_request.call_count == 2
    
    def test_trader_error_recovery(self, trader, mock_coinbase_client, error_handler):
        """Test trader error recovery."""
        # Configure client to raise error then succeed
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            'message': 'Rate limit exceeded',
            'type': 'rate_limit_error'
        }
        
        # Mock responses for position manager
        trader.position_manager.get_crypto_balance = Mock(side_effect=[
            Exception("API error"),
            1.0
        ])
        
        # Mock responses for order manager
        trader.order_manager.place_market_order = Mock(return_value={
            'id': 'test-order-id',
            'product_id': 'BTC-USD',
            'side': 'buy',
            'size': '0.01',
            'price': '45100.0',
            'status': 'filled'
        })
        
        # Set error handler
        trader.error_handler = error_handler
        
        # Create trading signal
        from bot.strategy import TradingSignal, SignalType
        signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.8,
            price=45100.0,
            timestamp=datetime.now(),
            strategy="Test Strategy",
            reasoning="Test buy signal"
        )
        
        # Test trade execution with error recovery
        with patch('time.sleep'):  # Skip sleep delay
            # Execute trade
            result = trader.execute_crypto_trade(signal)
            
            # Verify trade was executed successfully after retry
            assert result is not None
            assert result['id'] == 'test-order-id'
            assert trader.position_manager.get_crypto_balance.call_count == 2
    
    def test_websocket_error_recovery(self, mock_coinbase_client, crypto_settings, error_handler):
        """Test WebSocket error recovery."""
        # Create WebSocket client
        websocket = CoinbaseWebSocket(mock_coinbase_client, crypto_settings, error_handler)
        
        # Mock WebSocket connection that fails then succeeds
        connection_attempts = [0]
        connection_results = [False, True]  # Fail first, succeed second
        
        def mock_connect():
            result = connection_results[min(connection_attempts[0], len(connection_results) - 1)]
            connection_attempts[0] += 1
            if not result:
                raise Exception("WebSocket connection failed")
            return True
        
        websocket._connect_websocket = mock_connect
        
        # Test connection with error recovery
        with patch('time.sleep'):  # Skip sleep delay
            # Connect
            websocket.connect()
            
            # Verify connection was established after retry
            assert websocket.is_connected() is True
            assert connection_attempts[0] == 2
    
    def test_comprehensive_error_scenario(self, mock_coinbase_client, error_handler, crypto_settings):
        """Test comprehensive error scenario with multiple components."""
        # Create components
        data_fetcher = CoinbaseDataFetcher(mock_coinbase_client)
        position_manager = CryptoPositionManager(mock_coinbase_client, crypto_settings)
        order_manager = CryptoOrderManager(mock_coinbase_client, crypto_settings)
        risk_manager = CryptoRiskManager(position_manager, crypto_settings)
        trader = CoinbaseTrader(
            client=mock_coinbase_client,
            position_manager=position_manager,
            order_manager=order_manager,
            risk_manager=risk_manager,
            settings=crypto_settings
        )
        
        # Set error handler for all components
        data_fetcher.error_handler = error_handler
        position_manager.error_handler = error_handler
        order_manager.error_handler = error_handler
        trader.error_handler = error_handler
        
        # Configure mock responses for different scenarios
        
        # 1. Rate limit error for market data
        mock_rate_limit_response = Mock()
        mock_rate_limit_response.status_code = 429
        mock_rate_limit_response.json.return_value = {
            'message': 'Rate limit exceeded',
            'type': 'rate_limit_error'
        }
        
        # 2. Network error for account data
        network_error = requests.exceptions.ConnectionError("Connection refused")
        
        # 3. Success responses
        candles_response = [
            [int(datetime.now().timestamp()) - i * 300, 45000.0, 45500.0, 44500.0, 45100.0, 1000.0] 
            for i in range(50)
        ]
        
        accounts_response = [
            {'id': 'btc-account', 'currency': 'BTC', 'balance': '1.0', 'available': '1.0', 'hold': '0.0'},
            {'id': 'usd-account', 'currency': 'USD', 'balance': '50000.0', 'available': '50000.0', 'hold': '0.0'}
        ]
        
        order_response = {
            'id': 'test-order-id',
            'product_id': 'BTC-USD',
            'side': 'buy',
            'size': '0.01',
            'price': '45100.0',
            'status': 'filled'
        }
        
        # Configure client to return different responses based on endpoint and attempt
        candles_calls = 0
        accounts_calls = 0
        orders_calls = 0
        
        def mock_make_request(method, endpoint, params=None, data=None):
            nonlocal candles_calls, accounts_calls, orders_calls
            
            if 'candles' in endpoint:
                candles_calls += 1
                if candles_calls == 1:
                    raise requests.exceptions.HTTPError(response=mock_rate_limit_response)
                return candles_response
            elif 'accounts' in endpoint:
                accounts_calls += 1
                if accounts_calls == 1:
                    raise network_error
                return accounts_response
            elif 'orders' in endpoint:
                orders_calls += 1
                return order_response
            return {}
        
        mock_coinbase_client.make_request = Mock(side_effect=mock_make_request)
        
        # Create trading signal
        from bot.strategy import TradingSignal, SignalType
        signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.8,
            price=45100.0,
            timestamp=datetime.now(),
            strategy="Test Strategy",
            reasoning="Test buy signal"
        )
        
        # Test comprehensive scenario with error recovery
        with patch('time.sleep'):  # Skip sleep delay
            # 1. Fetch market data (will retry after rate limit error)
            with patch.object(data_fetcher, '_process_candles', return_value=pd.DataFrame({
                'open': [45000.0] * 50,
                'high': [45500.0] * 50,
                'low': [44500.0] * 50,
                'close': [45100.0] * 50,
                'volume': [1000.0] * 50
            })):
                data = data_fetcher.fetch_crypto_ohlcv('BTC-USD', timeframe='5m', limit=50)
                
                # Verify data was fetched successfully after retry
                assert data is not None
                assert len(data) == 50
                assert candles_calls == 2
            
            # 2. Execute trade (will retry after network error)
            result = trader.execute_crypto_trade(signal)
            
            # Verify trade was executed successfully after retry
            assert result is not None
            assert result['id'] == 'test-order-id'
            assert accounts_calls == 2
            assert orders_calls == 1


class TestCoinbaseErrorStatistics:
    """Test Coinbase error statistics and reporting."""
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler."""
        return CoinbaseErrorHandler()
    
    def test_error_statistics_tracking(self, error_handler):
        """Test error statistics tracking."""
        # Simulate various errors
        error_handler.track_error('authentication_error')
        error_handler.track_error('rate_limit_error')
        error_handler.track_error('rate_limit_error')
        error_handler.track_error('network_error')
        error_handler.track_error('invalid_order_error')
        
        # Get error statistics
        stats = error_handler.get_error_statistics()
        
        # Verify statistics
        assert stats['total_errors'] == 5
        assert stats['authentication_errors'] == 1
        assert stats['rate_limit_errors'] == 2
        assert stats['network_errors'] == 1
        assert stats['invalid_order_errors'] == 1
    
    def test_error_rate_calculation(self, error_handler):
        """Test error rate calculation."""
        # Reset statistics
        error_handler.reset_statistics()
        
        # Track operations and errors
        for _ in range(100):
            error_handler.track_operation()
        
        for _ in range(10):
            error_handler.track_error('rate_limit_error')
            error_handler.track_operation()
        
        # Get error statistics
        stats = error_handler.get_error_statistics()
        
        # Verify error rate
        assert stats['total_operations'] == 110
        assert stats['total_errors'] == 10
        assert stats['error_rate'] == 10 / 110
    
    def test_reset_statistics(self, error_handler):
        """Test resetting error statistics."""
        # Track some errors
        error_handler.track_error('authentication_error')
        error_handler.track_error('rate_limit_error')
        
        # Reset statistics
        error_handler.reset_statistics()
        
        # Get error statistics
        stats = error_handler.get_error_statistics()
        
        # Verify statistics were reset
        assert stats['total_errors'] == 0
        assert stats['authentication_errors'] == 0
        assert stats['rate_limit_errors'] == 0
    
    def test_retry_tracking(self, error_handler):
        """Test retry tracking."""
        # Simulate retries
        error_handler.track_retry('rate_limit_error')
        error_handler.track_retry('network_error')
        error_handler.track_retry('rate_limit_error')
        
        # Get error statistics
        stats = error_handler.get_error_statistics()
        
        # Verify retry statistics
        assert stats['total_retries'] == 3
        assert stats['rate_limit_retries'] == 2
        assert stats['network_retries'] == 1


if __name__ == '__main__':
    pytest.main([__file__])