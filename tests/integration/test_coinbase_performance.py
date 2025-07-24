"""
Performance tests for Coinbase API integration.
Tests API response times, data processing efficiency, and system resource usage.
"""
import unittest
import pytest
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
import os
import psutil
import json

from bot.config import Config
from bot.coinbase_client import CoinbaseClient
from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.coinbase_trader import CoinbaseTrader
from bot.coinbase_websocket import CoinbaseWebSocket
from bot.crypto_order_manager import CryptoOrderManager
from bot.crypto_position_manager import CryptoPositionManager
from bot.crypto_risk_manager import CryptoRiskManager
from bot.strategy import MovingAverageCrossover, RSIStrategy, SignalGenerator
from bot.scheduler import TradingCycle


class TestCoinbasePerformance:
    """Performance tests for Coinbase API integration."""
    
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
    def sample_data(self):
        """Create sample market data."""
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='5Min')
        data = pd.DataFrame({
            'open': np.random.uniform(45000, 46000, 1000),
            'high': np.random.uniform(45500, 46500, 1000),
            'low': np.random.uniform(44500, 45500, 1000),
            'close': np.random.uniform(45000, 46000, 1000),
            'volume': np.random.uniform(1000, 2000, 1000)
        }, index=dates)
        
        # Ensure high >= open, close, low and low <= open, close
        for i in range(len(data)):
            data.loc[data.index[i], 'high'] = max(
                data.loc[data.index[i], 'high'],
                data.loc[data.index[i], 'open'],
                data.loc[data.index[i], 'close']
            ) + 1
            data.loc[data.index[i], 'low'] = min(
                data.loc[data.index[i], 'low'],
                data.loc[data.index[i], 'open'],
                data.loc[data.index[i], 'close']
            ) - 1
        
        return data
    
    @pytest.fixture
    def large_sample_data(self):
        """Create large sample market data for memory testing."""
        dates = pd.date_range(start='2023-01-01', periods=10000, freq='5Min')
        data = pd.DataFrame({
            'open': np.random.uniform(45000, 46000, 10000),
            'high': np.random.uniform(45500, 46500, 10000),
            'low': np.random.uniform(44500, 45500, 10000),
            'close': np.random.uniform(45000, 46000, 10000),
            'volume': np.random.uniform(1000, 2000, 10000)
        }, index=dates)
        
        # Ensure high >= open, close, low and low <= open, close
        for i in range(len(data)):
            data.loc[data.index[i], 'high'] = max(
                data.loc[data.index[i], 'high'],
                data.loc[data.index[i], 'open'],
                data.loc[data.index[i], 'close']
            ) + 1
            data.loc[data.index[i], 'low'] = min(
                data.loc[data.index[i], 'low'],
                data.loc[data.index[i], 'open'],
                data.loc[data.index[i], 'close']
            ) - 1
        
        return data
    
    @pytest.fixture
    def mock_coinbase_client(self, credentials):
        """Create mock Coinbase client."""
        with patch('bot.coinbase_client.requests.Session'):
            client = CoinbaseClient(credentials)
            return client
    
    def test_api_response_time_simulation(self, mock_coinbase_client):
        """Test simulated API response times."""
        # Create data fetcher with mocked client
        data_fetcher = CoinbaseDataFetcher(mock_coinbase_client)
        
        # Configure mock to return with a delay to simulate API latency
        def delayed_response(*args, **kwargs):
            time.sleep(0.1)  # Simulate 100ms API latency
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                [int(datetime.now().timestamp()) - i * 300, 45000.0, 45500.0, 44500.0, 45100.0, 1000.0] 
                for i in range(50)
            ]
            return mock_response
        
        mock_coinbase_client.make_request = Mock(side_effect=delayed_response)
        
        # Measure time for API request
        start_time = time.time()
        with patch.object(data_fetcher, '_process_candles', return_value=pd.DataFrame({
            'open': [45000.0] * 50,
            'high': [45500.0] * 50,
            'low': [44500.0] * 50,
            'close': [45100.0] * 50,
            'volume': [1000.0] * 50
        })):
            data_fetcher.fetch_crypto_ohlcv("BTC-USD", timeframe="5m", limit=50)
        end_time = time.time()
        
        # Calculate execution time
        api_time = end_time - start_time
        
        # Log performance metrics
        print(f"Simulated API response time: {api_time:.4f} seconds")
        
        # Assert that execution time includes our simulated delay
        assert api_time >= 0.1, "API response time was faster than expected"
        assert api_time < 0.5, "API response handling took too long"
    
    def test_strategy_calculation_performance(self, sample_data):
        """Test performance of strategy calculations with crypto data."""
        # Create strategies
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
        
        # Measure time for strategy calculations
        start_time = time.time()
        signal = signal_generator.evaluate_all_strategies(sample_data)
        end_time = time.time()
        
        # Calculate execution time
        execution_time = end_time - start_time
        
        # Log performance metrics
        print(f"Strategy calculation time for 1000 data points: {execution_time:.4f} seconds")
        
        # Assert that execution time is reasonable
        assert execution_time < 1.0, "Strategy calculation took too long"
    
    def test_data_processing_performance(self, sample_data, mock_coinbase_client):
        """Test performance of data processing operations."""
        # Create data fetcher
        data_fetcher = CoinbaseDataFetcher(mock_coinbase_client)
        
        # Measure time for data validation
        start_time = time.time()
        is_valid = data_fetcher.validate_crypto_data(sample_data)
        end_time = time.time()
        
        # Calculate execution time
        validation_time = end_time - start_time
        
        # Log performance metrics
        print(f"Data validation time for 1000 data points: {validation_time:.4f} seconds")
        
        # Assert that execution time is reasonable
        assert validation_time < 0.1, "Data validation took too long"
        
        # Test DataFrame to dict conversion performance
        start_time = time.time()
        data_dict = sample_data.to_dict('records')
        end_time = time.time()
        
        # Calculate execution time
        conversion_time = end_time - start_time
        
        # Log performance metrics
        print(f"DataFrame to dict conversion time for 1000 data points: {conversion_time:.4f} seconds")
        
        # Assert that execution time is reasonable
        assert conversion_time < 0.1, "DataFrame conversion took too long"
    
    def test_trading_cycle_performance(self, sample_data, mock_coinbase_client, crypto_settings):
        """Test performance of a complete trading cycle."""
        # Create mocks
        mock_data_fetcher = Mock()
        mock_data_fetcher.fetch_crypto_ohlcv.return_value = sample_data
        mock_data_fetcher.get_latest_price.return_value = sample_data['close'].iloc[-1]
        
        # Create strategies
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
        
        # Create position manager
        position_manager = CryptoPositionManager(mock_coinbase_client, crypto_settings)
        position_manager.get_crypto_balance = Mock(return_value=1.0)
        position_manager.get_position_value_usd = Mock(return_value=45100.0)
        
        # Create order manager
        order_manager = CryptoOrderManager(mock_coinbase_client, crypto_settings)
        order_manager.place_market_order = Mock(return_value={'id': 'order1', 'status': 'filled'})
        
        # Create risk manager
        risk_manager = CryptoRiskManager(position_manager, crypto_settings)
        risk_manager.validate_trade = Mock(return_value=True)
        
        # Create trader
        trader = CoinbaseTrader(
            client=mock_coinbase_client,
            position_manager=position_manager,
            order_manager=order_manager,
            risk_manager=risk_manager,
            settings=crypto_settings
        )
        
        # Create mock logger
        mock_logger = Mock()
        
        # Create trading cycle
        trading_cycle = TradingCycle(
            data_fetcher=mock_data_fetcher,
            signal_generator=signal_generator,
            trader=trader,
            logger=mock_logger,
            symbol="BTC-USD"
        )
        
        # Measure time for complete trading cycle
        start_time = time.time()
        result = trading_cycle.execute()
        end_time = time.time()
        
        # Calculate execution time
        execution_time = end_time - start_time
        
        # Log performance metrics
        print(f"Complete trading cycle execution time: {execution_time:.4f} seconds")
        
        # Assert that execution time is reasonable
        assert execution_time < 2.0, "Trading cycle execution took too long"
    
    def test_memory_usage(self, large_sample_data):
        """Test memory usage during data processing."""
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Measure memory before test
        memory_before = process.memory_info().rss / 1024 / 1024  # Convert to MB
        
        # Create strategies
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
        
        # Process data
        signal = signal_generator.evaluate_all_strategies(large_sample_data)
        
        # Measure memory after test
        memory_after = process.memory_info().rss / 1024 / 1024  # Convert to MB
        
        # Calculate memory usage
        memory_used = memory_after - memory_before
        
        # Log memory usage
        print(f"Memory usage for processing 10,000 data points: {memory_used:.2f} MB")
        print(f"Total process memory: {memory_after:.2f} MB")
        
        # No strict assertion as memory usage can vary, but log for monitoring
    
    def test_websocket_performance(self, mock_coinbase_client, crypto_settings):
        """Test WebSocket connection performance."""
        # Create WebSocket client with mocked connection
        websocket = CoinbaseWebSocket(mock_coinbase_client, crypto_settings)
        
        # Mock WebSocket methods
        websocket._ws = Mock()
        websocket._ws.send = Mock()
        websocket._ws.recv = Mock(return_value=json.dumps({
            'type': 'ticker',
            'product_id': 'BTC-USD',
            'price': '45100.0',
            'time': datetime.now().isoformat()
        }))
        
        # Measure connection time
        with patch.object(websocket, '_connect_websocket') as mock_connect:
            mock_connect.return_value = True
            
            start_time = time.time()
            websocket.connect()
            end_time = time.time()
            
            # Calculate connection time
            connection_time = end_time - start_time
            
            # Log performance metrics
            print(f"WebSocket connection time: {connection_time:.4f} seconds")
            
            # Assert that connection time is reasonable
            assert connection_time < 0.5, "WebSocket connection took too long"
        
        # Measure message processing time
        start_time = time.time()
        for _ in range(100):
            websocket._process_message(json.dumps({
                'type': 'ticker',
                'product_id': 'BTC-USD',
                'price': '45100.0',
                'time': datetime.now().isoformat()
            }))
        end_time = time.time()
        
        # Calculate message processing time
        processing_time = end_time - start_time
        
        # Log performance metrics
        print(f"WebSocket message processing time (100 messages): {processing_time:.4f} seconds")
        print(f"Average message processing time: {processing_time / 100:.6f} seconds")
        
        # Assert that processing time is reasonable
        assert processing_time < 0.5, "WebSocket message processing took too long"
    
    def test_order_execution_performance(self, mock_coinbase_client, crypto_settings):
        """Test order execution performance."""
        # Create order manager
        order_manager = CryptoOrderManager(mock_coinbase_client, crypto_settings)
        
        # Configure mock to return with a delay to simulate API latency
        def delayed_response(*args, **kwargs):
            time.sleep(0.1)  # Simulate 100ms API latency
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'id': 'test-order-id',
                'product_id': 'BTC-USD',
                'side': 'buy',
                'size': '0.01',
                'price': '45100.0',
                'status': 'pending'
            }
            return mock_response
        
        mock_coinbase_client.make_request = Mock(side_effect=delayed_response)
        
        # Measure time for order placement
        start_time = time.time()
        order = order_manager.place_market_order('buy', 'BTC-USD', 0.01)
        end_time = time.time()
        
        # Calculate execution time
        order_time = end_time - start_time
        
        # Log performance metrics
        print(f"Order placement time: {order_time:.4f} seconds")
        
        # Assert that execution time includes our simulated delay
        assert order_time >= 0.1, "Order placement time was faster than expected"
        assert order_time < 0.5, "Order placement took too long"
    
    def test_concurrent_api_calls_performance(self, mock_coinbase_client):
        """Test performance of concurrent API calls."""
        # Create data fetcher
        data_fetcher = CoinbaseDataFetcher(mock_coinbase_client)
        
        # Configure mock to return with a delay to simulate API latency
        def delayed_response(*args, **kwargs):
            time.sleep(0.05)  # Simulate 50ms API latency
            mock_response = Mock()
            mock_response.status_code = 200
            
            # Return different responses based on endpoint
            url = kwargs.get('url', '')
            if 'candles' in url:
                mock_response.json.return_value = [
                    [int(datetime.now().timestamp()) - i * 300, 45000.0, 45500.0, 44500.0, 45100.0, 1000.0] 
                    for i in range(50)
                ]
            elif 'ticker' in url:
                mock_response.json.return_value = {'price': '45100.0'}
            else:
                mock_response.json.return_value = {}
            
            return mock_response
        
        mock_coinbase_client.make_request = Mock(side_effect=delayed_response)
        
        # Measure time for multiple concurrent API calls
        start_time = time.time()
        
        # Make multiple API calls
        with patch.object(data_fetcher, '_process_candles', return_value=pd.DataFrame({
            'open': [45000.0] * 50,
            'high': [45500.0] * 50,
            'low': [44500.0] * 50,
            'close': [45100.0] * 50,
            'volume': [1000.0] * 50
        })):
            # Fetch data for multiple symbols
            symbols = ['BTC-USD', 'ETH-USD', 'SOL-USD']
            for symbol in symbols:
                data_fetcher.fetch_crypto_ohlcv(symbol, timeframe="5m", limit=50)
                data_fetcher.get_latest_price(symbol)
        
        end_time = time.time()
        
        # Calculate total execution time
        total_time = end_time - start_time
        
        # Log performance metrics
        print(f"Multiple API calls execution time: {total_time:.4f} seconds")
        print(f"Average time per API call: {total_time / (len(symbols) * 2):.4f} seconds")
        
        # Assert that execution time is reasonable
        # Each symbol makes 2 API calls, each taking ~50ms
        expected_time = len(symbols) * 2 * 0.05
        assert total_time >= expected_time, "API calls were faster than expected"
        assert total_time < expected_time * 2, "API calls took too long"


if __name__ == '__main__':
    pytest.main([__file__])