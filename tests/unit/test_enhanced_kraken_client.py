"""
Unit tests for EnhancedKrakenClient.
Tests advanced order types, batch operations, circuit breaker, and rate limiting.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime, timedelta
import requests

from bot.kraken_client import (
    EnhancedKrakenClient, KrakenCredentials, CircuitBreaker, RateLimiter,
    CircuitBreakerConfig, RateLimitConfig, ConnectionPoolConfig,
    CircuitBreakerState
)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""
    
    def setUp(self):
        self.config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60)
        self.circuit_breaker = CircuitBreaker(self.config)
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        
        # Successful call should keep circuit closed
        result = self.circuit_breaker.call(lambda: "success")
        self.assertEqual(result, "success")
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)
    
    def test_circuit_breaker_failure_counting(self):
        """Test circuit breaker failure counting."""
        failing_func = Mock(side_effect=Exception("API Error"))
        
        # First two failures should keep circuit closed
        for i in range(2):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(failing_func)
            self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
            self.assertEqual(self.circuit_breaker.failure_count, i + 1)
        
        # Third failure should open circuit
        with self.assertRaises(Exception):
            self.circuit_breaker.call(failing_func)
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)
        self.assertEqual(self.circuit_breaker.failure_count, 3)
    
    def test_circuit_breaker_open_state(self):
        """Test circuit breaker in open state."""
        # Force circuit to open state
        self.circuit_breaker.state = CircuitBreakerState.OPEN
        self.circuit_breaker.failure_count = 5
        self.circuit_breaker.last_failure_time = datetime.now()
        
        # Should reject calls immediately
        with self.assertRaises(Exception) as context:
            self.circuit_breaker.call(lambda: "success")
        self.assertIn("Circuit breaker is OPEN", str(context.exception))
    
    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery from open to half-open."""
        # Set circuit to open state with old failure time
        self.circuit_breaker.state = CircuitBreakerState.OPEN
        self.circuit_breaker.failure_count = 5
        self.circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=70)
        
        # Should attempt reset and succeed
        result = self.circuit_breaker.call(lambda: "success")
        self.assertEqual(result, "success")
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)


class TestRateLimiter(unittest.TestCase):
    """Test rate limiter functionality."""
    
    def setUp(self):
        self.config = RateLimitConfig(max_requests_per_minute=5, burst_limit=3)
        self.rate_limiter = RateLimiter(self.config)
    
    def test_rate_limiter_normal_operation(self):
        """Test rate limiter under normal conditions."""
        # Should allow requests under limit
        for _ in range(3):
            self.rate_limiter.acquire()
        
        # Check request count
        self.assertEqual(len(self.rate_limiter.requests), 3)
    
    @patch('time.sleep')
    def test_rate_limiter_backoff(self, mock_sleep):
        """Test rate limiter backoff functionality."""
        # Set backoff period
        self.rate_limiter.set_backoff(10)
        
        # Should sleep during backoff
        self.rate_limiter.acquire()
        mock_sleep.assert_called_once()
    
    def test_rate_limiter_request_cleanup(self):
        """Test rate limiter cleans up old requests."""
        # Add old requests
        old_time = datetime.now() - timedelta(minutes=2)
        self.rate_limiter.requests = [old_time, old_time, old_time]
        
        # Acquire should clean up old requests
        self.rate_limiter.acquire()
        
        # Should have only the new request
        self.assertEqual(len(self.rate_limiter.requests), 1)


class TestEnhancedKrakenClient(unittest.TestCase):
    """Test EnhancedKrakenClient functionality."""
    
    def setUp(self):
        self.credentials = KrakenCredentials(
            api_key="test_key",
            api_secret="dGVzdF9zZWNyZXQ="  # base64 encoded "test_secret"
        )
        self.client = EnhancedKrakenClient(self.credentials)
    
    @patch('bot.kraken_client.KrakenClient._make_request')
    def test_advanced_order_types(self, mock_request):
        """Test advanced order type methods."""
        mock_request.return_value = {'txid': ['ORDER123']}
        
        # Test stop-loss order
        result = self.client.place_stop_loss_order('BTCUSD', 'sell', '0.1', '50000')
        self.assertEqual(result['txid'], ['ORDER123'])
        # Check the call was made with correct arguments (positional)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], '/0/private/AddOrder')
        self.assertEqual(args[2], True)  # is_private=True
        order_data = args[1]
        self.assertEqual(order_data['pair'], 'BTCUSD')
        self.assertEqual(order_data['type'], 'sell')
        self.assertEqual(order_data['ordertype'], 'stop-loss')
        self.assertEqual(order_data['volume'], '0.1')
        self.assertEqual(order_data['price'], '50000')
        
        # Test take-profit order
        self.client.place_take_profit_order('BTCUSD', 'buy', '0.1', '60000')
        args, kwargs = mock_request.call_args
        order_data = args[1]
        self.assertEqual(order_data['pair'], 'BTCUSD')
        self.assertEqual(order_data['type'], 'buy')
        self.assertEqual(order_data['ordertype'], 'take-profit')
        self.assertEqual(order_data['volume'], '0.1')
        self.assertEqual(order_data['price'], '60000')
        
        # Test trailing stop order
        self.client.place_trailing_stop_order('BTCUSD', 'sell', '0.1', '1000')
        args, kwargs = mock_request.call_args
        order_data = args[1]
        self.assertEqual(order_data['pair'], 'BTCUSD')
        self.assertEqual(order_data['type'], 'sell')
        self.assertEqual(order_data['ordertype'], 'trailing-stop')
        self.assertEqual(order_data['volume'], '0.1')
        self.assertEqual(order_data['price2'], '1000')
        
        # Test stop-loss-limit order
        self.client.place_stop_loss_limit_order('BTCUSD', 'sell', '0.1', '50000', '49000')
        args, kwargs = mock_request.call_args
        order_data = args[1]
        self.assertEqual(order_data['pair'], 'BTCUSD')
        self.assertEqual(order_data['type'], 'sell')
        self.assertEqual(order_data['ordertype'], 'stop-loss-limit')
        self.assertEqual(order_data['volume'], '0.1')
        self.assertEqual(order_data['price'], '50000')
        self.assertEqual(order_data['price2'], '49000')
    
    @patch('bot.kraken_client.KrakenClient.get_ticker')
    def test_multi_pair_ticker(self, mock_get_ticker):
        """Test multi-pair ticker functionality."""
        mock_get_ticker.return_value = {
            'BTCUSD': {'c': ['55000.0', '0.1']},
            'ETHUSD': {'c': ['3500.0', '1.0']}
        }
        
        result = self.client.get_multi_pair_ticker(['BTCUSD', 'ETHUSD'])
        
        self.assertIn('BTCUSD', result)
        self.assertIn('ETHUSD', result)
        mock_get_ticker.assert_called_once_with(['BTCUSD', 'ETHUSD'])
    
    @patch('bot.kraken_client.KrakenClient.get_ticker')
    def test_multi_pair_ticker_fallback(self, mock_get_ticker):
        """Test multi-pair ticker fallback to individual requests."""
        # First call fails, individual calls succeed
        mock_get_ticker.side_effect = [
            Exception("Batch request failed"),
            {'BTCUSD': {'c': ['55000.0', '0.1']}},
            {'ETHUSD': {'c': ['3500.0', '1.0']}}
        ]
        
        result = self.client.get_multi_pair_ticker(['BTCUSD', 'ETHUSD'])
        
        self.assertIn('BTCUSD', result)
        self.assertIn('ETHUSD', result)
        self.assertEqual(mock_get_ticker.call_count, 3)
    
    @patch('bot.kraken_client.KrakenClient.cancel_order')
    def test_batch_cancel_orders(self, mock_cancel_order):
        """Test batch order cancellation."""
        mock_cancel_order.return_value = {'count': 1}
        
        # Test single order cancellation
        result = self.client.batch_cancel_orders(['ORDER123'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['cancelled'], ['ORDER123'])
        
        # Test multiple order cancellation
        result = self.client.batch_cancel_orders(['ORDER123', 'ORDER456'])
        self.assertEqual(result['count'], 2)
        self.assertEqual(len(result['cancelled']), 2)
    
    @patch('bot.kraken_client.KrakenClient.cancel_order')
    def test_batch_cancel_orders_partial_failure(self, mock_cancel_order):
        """Test batch order cancellation with partial failures."""
        # First order succeeds, second fails
        mock_cancel_order.side_effect = [
            {'count': 1},
            Exception("Order not found")
        ]
        
        result = self.client.batch_cancel_orders(['ORDER123', 'ORDER456'])
        
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['cancelled'], ['ORDER123'])
        self.assertEqual(len(result['failed']), 1)
        self.assertEqual(result['failed'][0]['order_id'], 'ORDER456')
    
    @patch('bot.kraken_client.KrakenClient.get_tradable_pairs')
    def test_validate_trading_pairs(self, mock_get_pairs):
        """Test trading pair validation."""
        mock_get_pairs.return_value = {
            'BTCUSD': {'altname': 'XBTUSDT'},
            'ETHUSD': {'altname': 'ETHUSDT'}
        }
        
        result = self.client.validate_trading_pairs(['BTCUSD', 'ETHUSD', 'INVALID'])
        
        self.assertTrue(result['BTCUSD'])
        self.assertTrue(result['ETHUSD'])
        self.assertFalse(result['INVALID'])
    
    @patch('bot.kraken_client.KrakenClient.get_tradable_pairs')
    def test_get_trading_fees(self, mock_get_pairs):
        """Test trading fees retrieval."""
        mock_get_pairs.return_value = {
            'BTCUSD': {
                'fees': [[0, 0.26], [50000, 0.24]],
                'fees_maker': [[0, 0.16], [50000, 0.14]],
                'fee_volume_currency': 'USD'
            }
        }
        
        result = self.client.get_trading_fees(['BTCUSD'])
        
        self.assertIn('BTCUSD', result)
        self.assertEqual(result['BTCUSD']['maker_fee'], 0.26)
        self.assertEqual(result['BTCUSD']['taker_fee'], 0.16)
        self.assertEqual(result['BTCUSD']['fee_volume_currency'], 'USD')
    
    @patch('bot.kraken_client.KrakenClient.get_orders_info')
    def test_get_order_status(self, mock_get_orders):
        """Test order status retrieval."""
        mock_get_orders.return_value = {
            'ORDER123': {
                'status': 'open',
                'vol': '0.1',
                'vol_exec': '0.0',
                'cost': '0.0',
                'fee': '0.0'
            }
        }
        
        result = self.client.get_order_status('ORDER123')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], 'open')
        self.assertEqual(result['vol'], '0.1')
    
    @patch('bot.kraken_client.KrakenClient.get_server_time')
    @patch('bot.kraken_client.KrakenClient.get_account_balance')
    def test_get_system_status(self, mock_balance, mock_time):
        """Test system status retrieval."""
        mock_time.return_value = {'unixtime': 1234567890}
        mock_balance.return_value = {'USD': '1000.0'}
        
        result = self.client.get_system_status()
        
        self.assertTrue(result['api_accessible'])
        self.assertTrue(result['private_api_accessible'])
        self.assertIsNotNone(result['server_time'])
        self.assertEqual(result['circuit_breaker_state'], 'closed')
    
    def test_reset_circuit_breaker(self):
        """Test manual circuit breaker reset."""
        # Force circuit breaker to open state
        self.client.circuit_breaker.state = CircuitBreakerState.OPEN
        self.client.circuit_breaker.failure_count = 5
        
        # Reset circuit breaker
        self.client.reset_circuit_breaker()
        
        self.assertEqual(self.client.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.client.circuit_breaker.failure_count, 0)
    
    def test_get_rate_limit_status(self):
        """Test rate limit status retrieval."""
        # Add some requests to rate limiter
        self.client.rate_limiter.requests = [datetime.now(), datetime.now()]
        
        result = self.client.get_rate_limit_status()
        
        self.assertEqual(result['requests_in_last_minute'], 2)
        self.assertEqual(result['max_requests_per_minute'], 60)  # Default config
        self.assertIsNone(result['backoff_until'])
    
    @patch('bot.kraken_client.KrakenClient.get_ohlc_data')
    def test_get_multi_pair_ohlc(self, mock_ohlc):
        """Test multi-pair OHLC data retrieval."""
        mock_ohlc.side_effect = [
            {'BTCUSD': [[1234567890, '55000', '56000', '54000', '55500', '55250', '10.5', 100]]},
            {'ETHUSD': [[1234567890, '3500', '3600', '3400', '3550', '3525', '50.2', 200]]}
        ]
        
        result = self.client.get_multi_pair_ohlc(['BTCUSD', 'ETHUSD'])
        
        self.assertIn('BTCUSD', result)
        self.assertIn('ETHUSD', result)
        self.assertEqual(mock_ohlc.call_count, 2)
    
    @patch('bot.kraken_client.KrakenClient.get_order_book')
    def test_get_multi_pair_order_book(self, mock_order_book):
        """Test multi-pair order book retrieval."""
        mock_order_book.side_effect = [
            {'BTCUSD': {'asks': [['55000', '0.1', 1234567890]], 'bids': [['54900', '0.2', 1234567890]]}},
            {'ETHUSD': {'asks': [['3500', '1.0', 1234567890]], 'bids': [['3490', '2.0', 1234567890]]}}
        ]
        
        result = self.client.get_multi_pair_order_book(['BTCUSD', 'ETHUSD'])
        
        self.assertIn('BTCUSD', result)
        self.assertIn('ETHUSD', result)
        self.assertEqual(mock_order_book.call_count, 2)
    
    @patch('bot.kraken_client.KrakenClient.get_tradable_pairs')
    def test_get_pair_info(self, mock_get_pairs):
        """Test detailed pair information retrieval."""
        mock_get_pairs.return_value = {
            'BTCUSD': {
                'altname': 'XBTUSDT',
                'base': 'XBT',
                'quote': 'USD',
                'lot': 'unit',
                'pair_decimals': 1,
                'lot_decimals': 8,
                'lot_multiplier': 1,
                'leverage_buy': [2, 3, 4, 5],
                'leverage_sell': [2, 3, 4, 5],
                'fees': [[0, 0.26], [50000, 0.24]],
                'fees_maker': [[0, 0.16], [50000, 0.14]],
                'fee_volume_currency': 'USD',
                'margin_call': 80,
                'margin_stop': 40,
                'ordermin': '0.0001'
            }
        }
        
        result = self.client.get_pair_info(['BTCUSD'])
        
        self.assertIn('BTCUSD', result)
        pair_info = result['BTCUSD']
        self.assertEqual(pair_info['altname'], 'XBTUSDT')
        self.assertEqual(pair_info['base'], 'XBT')
        self.assertEqual(pair_info['quote'], 'USD')
        self.assertEqual(pair_info['ordermin'], '0.0001')
    
    @patch('bot.kraken_client.KrakenClient.add_order')
    def test_batch_place_orders(self, mock_add_order):
        """Test batch order placement."""
        mock_add_order.return_value = {'txid': ['ORDER123']}
        
        orders = [
            {'pair': 'BTCUSD', 'type': 'buy', 'ordertype': 'limit', 'volume': '0.1', 'price': '50000'},
            {'pair': 'ETHUSD', 'type': 'sell', 'ordertype': 'market', 'volume': '1.0'}
        ]
        
        result = self.client.batch_place_orders(orders)
        
        self.assertEqual(result['count'], 2)
        self.assertEqual(len(result['successful']), 2)
        self.assertEqual(len(result['failed']), 0)
        self.assertEqual(mock_add_order.call_count, 2)
    
    @patch('bot.kraken_client.KrakenClient.add_order')
    def test_batch_place_orders_with_failures(self, mock_add_order):
        """Test batch order placement with some failures."""
        # First order succeeds, second fails
        mock_add_order.side_effect = [
            {'txid': ['ORDER123']},
            Exception("Insufficient funds")
        ]
        
        orders = [
            {'pair': 'BTCUSD', 'type': 'buy', 'ordertype': 'limit', 'volume': '0.1', 'price': '50000'},
            {'pair': 'ETHUSD', 'type': 'sell', 'ordertype': 'market', 'volume': '1.0'}
        ]
        
        result = self.client.batch_place_orders(orders)
        
        self.assertEqual(result['count'], 1)
        self.assertEqual(len(result['successful']), 1)
        self.assertEqual(len(result['failed']), 1)
        self.assertEqual(result['failed'][0]['error'], 'Insufficient funds')
    
    @patch('bot.kraken_client.KrakenClient.add_order')
    def test_batch_place_orders_validation(self, mock_add_order):
        """Test batch order placement with invalid orders."""
        mock_add_order.return_value = {'txid': ['ORDER123']}
        
        orders = [
            {'pair': 'BTCUSD', 'type': 'buy', 'ordertype': 'limit', 'volume': '0.1', 'price': '50000'},
            {'pair': 'ETHUSD', 'type': 'sell'}  # Missing required fields
        ]
        
        result = self.client.batch_place_orders(orders)
        
        self.assertEqual(result['count'], 1)
        self.assertEqual(len(result['successful']), 1)
        self.assertEqual(len(result['failed']), 1)
        self.assertIn('Missing required fields', result['failed'][0]['error'])
        
        # Verify the successful order was called with correct parameters
        mock_add_order.assert_called_once_with(
            pair='BTCUSD', 
            type_='buy', 
            ordertype='limit', 
            volume='0.1', 
            price='50000'
        )
    
    @patch('bot.kraken_client.KrakenClient.get_account_balance')
    @patch('bot.kraken_client.EnhancedKrakenClient.get_pair_info')
    def test_get_multi_pair_balances(self, mock_pair_info, mock_balance):
        """Test multi-pair balance retrieval."""
        mock_balance.return_value = {
            'XBT': '0.5',
            'USD': '10000.0',
            'ETH': '2.0'
        }
        
        mock_pair_info.return_value = {
            'BTCUSD': {'base': 'XBT', 'quote': 'USD'},
            'ETHUSD': {'base': 'ETH', 'quote': 'USD'}
        }
        
        result = self.client.get_multi_pair_balances(['BTCUSD', 'ETHUSD'])
        
        self.assertIn('XBT', result)
        self.assertIn('USD', result)
        self.assertIn('ETH', result)
        self.assertEqual(result['XBT'], '0.5')
        self.assertEqual(result['USD'], '10000.0')
        self.assertEqual(result['ETH'], '2.0')
    
    @patch('bot.kraken_client.EnhancedKrakenClient.get_multi_pair_balances')
    @patch('bot.kraken_client.EnhancedKrakenClient.get_multi_pair_ticker')
    @patch('bot.kraken_client.EnhancedKrakenClient.get_pair_info')
    @patch('bot.kraken_client.KrakenClient.get_open_orders')
    def test_get_position_summary(self, mock_open_orders, mock_pair_info, mock_ticker, mock_balances):
        """Test position summary retrieval."""
        mock_balances.return_value = {'XBT': '0.5', 'USD': '10000.0'}
        mock_ticker.return_value = {'BTCUSD': {'c': ['55000.0', '0.1']}}
        mock_pair_info.return_value = {'BTCUSD': {'base': 'XBT', 'quote': 'USD'}}
        mock_open_orders.return_value = {'open': {}}
        
        result = self.client.get_position_summary(['BTCUSD'])
        
        self.assertIn('pairs', result)
        self.assertIn('total_value_usd', result)
        self.assertIn('balances', result)
        self.assertIn('BTCUSD', result['pairs'])
        
        btc_pair = result['pairs']['BTCUSD']
        self.assertEqual(btc_pair['current_price'], 55000.0)
        self.assertEqual(btc_pair['base_balance'], 0.5)
        self.assertEqual(btc_pair['quote_balance'], 10000.0)
    
    @patch('bot.kraken_client.KrakenClient.get_server_time')
    @patch('bot.kraken_client.KrakenClient.get_account_balance')
    def test_test_connectivity_comprehensive(self, mock_balance, mock_time):
        """Test comprehensive connectivity testing."""
        mock_time.return_value = {'unixtime': 1234567890}
        mock_balance.return_value = {'USD': '1000.0'}
        
        result = self.client.test_connectivity_comprehensive()
        
        self.assertEqual(result['overall_status'], 'healthy')
        self.assertEqual(result['public_api']['status'], 'healthy')
        self.assertEqual(result['private_api']['status'], 'healthy')
        self.assertEqual(result['websocket_ready']['status'], 'ready')
        self.assertIsNotNone(result['public_api']['latency_ms'])
        self.assertIsNotNone(result['private_api']['latency_ms'])
    
    @patch('bot.kraken_client.KrakenClient.get_server_time')
    @patch('bot.kraken_client.KrakenClient.get_account_balance')
    def test_test_connectivity_comprehensive_partial_failure(self, mock_balance, mock_time):
        """Test comprehensive connectivity testing with partial failure."""
        mock_time.return_value = {'unixtime': 1234567890}
        mock_balance.side_effect = Exception("Authentication failed")
        
        result = self.client.test_connectivity_comprehensive()
        
        self.assertEqual(result['overall_status'], 'partial')
        self.assertEqual(result['public_api']['status'], 'healthy')
        self.assertEqual(result['private_api']['status'], 'error')
        self.assertEqual(result['websocket_ready']['status'], 'not_ready')
    
    @patch('bot.kraken_client.EnhancedKrakenClient.test_connectivity_comprehensive')
    def test_auto_recover(self, mock_connectivity):
        """Test automatic recovery functionality."""
        # Set up error states
        self.client.circuit_breaker.state = CircuitBreakerState.OPEN
        self.client.rate_limiter.backoff_until = datetime.now() + timedelta(seconds=60)
        
        mock_connectivity.return_value = {'overall_status': 'healthy'}
        
        result = self.client.auto_recover()
        
        self.assertIn('Circuit breaker reset', result['recovery_actions'])
        self.assertIn('Rate limiter backoff cleared', result['recovery_actions'])
        self.assertTrue(result['recovery_successful'])
        self.assertEqual(self.client.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertIsNone(self.client.rate_limiter.backoff_until)


class TestEnhancedKrakenClientIntegration(unittest.TestCase):
    """Integration tests for EnhancedKrakenClient."""
    
    def setUp(self):
        self.credentials = KrakenCredentials(
            api_key="test_key",
            api_secret="dGVzdF9zZWNyZXQ="
        )
        
        # Custom configurations for testing
        circuit_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30)
        rate_config = RateLimitConfig(max_requests_per_minute=10, burst_limit=5)
        pool_config = ConnectionPoolConfig(pool_connections=5, pool_maxsize=10)
        
        self.client = EnhancedKrakenClient(
            self.credentials,
            circuit_config,
            rate_config,
            pool_config
        )
    
    @patch('bot.kraken_client.KrakenClient._make_request')
    def test_circuit_breaker_integration(self, mock_request):
        """Test circuit breaker integration with API calls."""
        # First call succeeds
        mock_request.return_value = {'result': 'success'}
        result = self.client.get_server_time()
        self.assertEqual(result, {'result': 'success'})
        
        # Next calls fail to trigger circuit breaker
        mock_request.side_effect = requests.RequestException("API Error")
        
        # Should fail twice and open circuit
        with self.assertRaises(requests.RequestException):
            self.client.get_server_time()
        with self.assertRaises(requests.RequestException):
            self.client.get_server_time()
        
        # Circuit should now be open
        self.assertEqual(self.client.circuit_breaker.state, CircuitBreakerState.OPEN)
        
        # Next call should be rejected by circuit breaker
        with self.assertRaises(Exception) as context:
            self.client.get_server_time()
        self.assertIn("Circuit breaker is OPEN", str(context.exception))
    
    @patch('time.sleep')
    @patch('bot.kraken_client.KrakenClient._make_request')
    def test_rate_limiting_integration(self, mock_request, mock_sleep):
        """Test rate limiting integration with API calls."""
        mock_request.return_value = {'result': 'success'}
        
        # Make requests up to burst limit
        for _ in range(5):
            self.client.get_server_time()
        
        # Check that rate limiter has tracked requests
        self.assertEqual(len(self.client.rate_limiter.requests), 5)
        
        # Verify no sleep was called (under burst limit)
        mock_sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()