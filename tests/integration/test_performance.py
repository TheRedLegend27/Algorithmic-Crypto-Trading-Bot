"""
Performance tests for data processing and API response times.
"""
import unittest
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock

from bot.data_fetcher import DataFetcher
from bot.strategy import MovingAverageCrossover, RSIStrategy, SignalGenerator
from bot.config import AlpacaCredentials
from bot.trader import Trader, TradeResult
from bot.scheduler import TradingCycle


class TestPerformance(unittest.TestCase):
    """Performance tests for the crypto trading bot."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock credentials
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        
        # Create sample data
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='5Min')
        self.sample_data = pd.DataFrame({
            'open': np.random.uniform(45000, 46000, 1000),
            'high': np.random.uniform(45500, 46500, 1000),
            'low': np.random.uniform(44500, 45500, 1000),
            'close': np.random.uniform(45000, 46000, 1000),
            'volume': np.random.uniform(1000, 2000, 1000)
        }, index=dates)
        
        # Ensure high >= open, close, low and low <= open, close
        for i in range(len(self.sample_data)):
            self.sample_data.loc[self.sample_data.index[i], 'high'] = max(
                self.sample_data.loc[self.sample_data.index[i], 'high'],
                self.sample_data.loc[self.sample_data.index[i], 'open'],
                self.sample_data.loc[self.sample_data.index[i], 'close']
            ) + 1
            self.sample_data.loc[self.sample_data.index[i], 'low'] = min(
                self.sample_data.loc[self.sample_data.index[i], 'low'],
                self.sample_data.loc[self.sample_data.index[i], 'open'],
                self.sample_data.loc[self.sample_data.index[i], 'close']
            ) - 1
    
    def test_strategy_calculation_performance(self):
        """Test performance of strategy calculations."""
        # Create strategies
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
        
        # Measure time for strategy calculations
        start_time = time.time()
        signal = signal_generator.evaluate_all_strategies(self.sample_data)
        end_time = time.time()
        
        # Calculate execution time
        execution_time = end_time - start_time
        
        # Log performance metrics
        print(f"\nStrategy calculation time for 1000 data points: {execution_time:.4f} seconds")
        
        # Assert that execution time is reasonable (adjust threshold as needed)
        self.assertLess(execution_time, 1.0, "Strategy calculation took too long")
    
    def test_data_processing_performance(self):
        """Test performance of data processing operations."""
        # Create data fetcher with mocked client
        with patch('bot.data_fetcher.CryptoHistoricalDataClient'):
            data_fetcher = DataFetcher(self.credentials)
            
            # Mock fetch_crypto_data to return our sample data
            data_fetcher.fetch_crypto_data = Mock(return_value=self.sample_data)
            
            # Measure time for data validation
            start_time = time.time()
            is_valid = data_fetcher.validate_data(self.sample_data)
            end_time = time.time()
            
            # Calculate execution time
            validation_time = end_time - start_time
            
            # Log performance metrics
            print(f"\nData validation time for 1000 data points: {validation_time:.4f} seconds")
            
            # Assert that execution time is reasonable
            self.assertLess(validation_time, 0.1, "Data validation took too long")
            
            # Test DataFrame to list conversion performance
            start_time = time.time()
            data_list = self.sample_data.to_dict('records')
            end_time = time.time()
            
            # Calculate execution time
            conversion_time = end_time - start_time
            
            # Log performance metrics
            print(f"DataFrame to dict conversion time for 1000 data points: {conversion_time:.4f} seconds")
            
            # Assert that execution time is reasonable
            self.assertLess(conversion_time, 0.1, "DataFrame conversion took too long")
    
    def test_trading_cycle_performance(self):
        """Test performance of a complete trading cycle."""
        # Create mocks
        mock_data_fetcher = Mock()
        mock_data_fetcher.fetch_crypto_data.return_value = self.sample_data
        mock_data_fetcher.get_latest_price.return_value = self.sample_data['close'].iloc[-1]
        
        # Create strategies
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
        
        # Create mock trader and logger
        mock_trader = Mock()
        mock_logger = Mock()
        
        # Create trading cycle
        trading_cycle = TradingCycle(
            data_fetcher=mock_data_fetcher,
            signal_generator=signal_generator,
            trader=mock_trader,
            logger=mock_logger,
            symbol="BTC/USD"
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
        self.assertLess(execution_time, 2.0, "Trading cycle execution took too long")
    
    def test_api_response_simulation(self):
        """Test simulated API response times."""
        # Create data fetcher with mocked client
        with patch('bot.data_fetcher.CryptoHistoricalDataClient'):
            data_fetcher = DataFetcher(self.credentials)
            
            # Create a mock for the client's get_crypto_bars method
            mock_client = Mock()
            data_fetcher.client = mock_client
            
            # Create mock bars response
            mock_bars = {"BTC/USD": [
                MagicMock(
                    timestamp=datetime.now(),
                    open=45000,
                    high=45500,
                    low=44500,
                    close=45100,
                    volume=1000
                ) for _ in range(50)
            ]}
            
            # Configure mock to return our bars with a delay to simulate API latency
            def delayed_response(*args, **kwargs):
                time.sleep(0.1)  # Simulate 100ms API latency
                return mock_bars
            
            mock_client.get_crypto_bars.side_effect = delayed_response
            
            # Measure time for API request
            start_time = time.time()
            with patch.object(data_fetcher, '_bars_to_dataframe', return_value=self.sample_data.iloc[:50]):
                df = data_fetcher.fetch_crypto_data("BTC/USD", timeframe="5Min", limit=50)
            end_time = time.time()
            
            # Calculate execution time
            api_time = end_time - start_time
            
            # Log performance metrics
            print(f"Simulated API response time: {api_time:.4f} seconds")
            
            # Assert that execution time includes our simulated delay
            self.assertGreaterEqual(api_time, 0.1, "API response time was faster than expected")
            self.assertLess(api_time, 0.5, "API response handling took too long")
    
    def test_memory_usage(self):
        """Test memory usage during data processing."""
        import psutil
        import os
        
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Measure memory before test
        memory_before = process.memory_info().rss / 1024 / 1024  # Convert to MB
        
        # Create large dataset (10,000 data points)
        dates = pd.date_range(start='2023-01-01', periods=10000, freq='5Min')
        large_data = pd.DataFrame({
            'open': np.random.uniform(45000, 46000, 10000),
            'high': np.random.uniform(45500, 46500, 10000),
            'low': np.random.uniform(44500, 45500, 10000),
            'close': np.random.uniform(45000, 46000, 10000),
            'volume': np.random.uniform(1000, 2000, 10000)
        }, index=dates)
        
        # Create strategies
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
        
        # Process data
        signal = signal_generator.evaluate_all_strategies(large_data)
        
        # Measure memory after test
        memory_after = process.memory_info().rss / 1024 / 1024  # Convert to MB
        
        # Calculate memory usage
        memory_used = memory_after - memory_before
        
        # Log memory usage
        print(f"\nMemory usage for processing 10,000 data points: {memory_used:.2f} MB")
        
        # No strict assertion as memory usage can vary, but log for monitoring
        # In a real test, you might want to set a threshold based on your requirements
        print(f"Total process memory: {memory_after:.2f} MB")


if __name__ == '__main__':
    unittest.main()