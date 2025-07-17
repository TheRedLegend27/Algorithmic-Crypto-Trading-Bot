"""
Integration tests for complete trading cycles using paper trading.
Tests the end-to-end flow from data fetching to trade execution.
"""
import unittest
from unittest.mock import patch, MagicMock, Mock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import tempfile

from bot.config import Config, AlpacaCredentials, TradingSettings
from bot.data_fetcher import DataFetcher
from bot.strategy import MovingAverageCrossover, RSIStrategy, SignalGenerator, SignalType
from bot.trader import Trader, TradeResult
from bot.logger import TradingLogger
from bot.scheduler import TradingCycle, TradingScheduler
from bot.error_handler import ErrorHandler


class TestTradingCycleIntegration(unittest.TestCase):
    """Integration tests for complete trading cycles."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for logs
        self.test_log_dir = tempfile.mkdtemp()
        
        # Create mock credentials
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        
        # Create trading settings
        self.settings = TradingSettings(
            symbol="BTC/USD",
            trade_amount=10.0,
            max_position_size=100.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
            min_trade_interval=5
        )
        
        # Create sample data
        dates = pd.date_range(start='2023-01-01', periods=50, freq='5Min')
        self.sample_data = pd.DataFrame({
            'open': np.random.uniform(45000, 46000, 50),
            'high': np.random.uniform(45500, 46500, 50),
            'low': np.random.uniform(44500, 45500, 50),
            'close': np.random.uniform(45000, 46000, 50),
            'volume': np.random.uniform(1000, 2000, 50)
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
        
        # Create mocks for components
        self.mock_data_fetcher = Mock(spec=DataFetcher)
        self.mock_data_fetcher.fetch_crypto_data.return_value = self.sample_data
        self.mock_data_fetcher.get_latest_price.return_value = self.sample_data['close'].iloc[-1]
        
        # Create real components
        self.logger = TradingLogger(log_dir=self.test_log_dir, use_rich=False)
        self.error_handler = ErrorHandler()
        
        # Create strategies
        self.ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        self.rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        self.signal_generator = SignalGenerator([self.ma_strategy, self.rsi_strategy])
        
        # Create mock trader
        self.mock_trader = Mock(spec=Trader)
        self.mock_position_manager = Mock()
        self.mock_trader.position_manager = self.mock_position_manager
        
        # Create trading cycle
        self.trading_cycle = TradingCycle(
            data_fetcher=self.mock_data_fetcher,
            signal_generator=self.signal_generator,
            trader=self.mock_trader,
            logger=self.logger,
            error_handler=self.error_handler,
            symbol="BTC/USD"
        )
        
        # Create scheduler
        self.scheduler = TradingScheduler(
            trading_cycle=self.trading_cycle,
            interval_minutes=5,
            error_handler=self.error_handler
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary log directory
        import shutil
        shutil.rmtree(self.test_log_dir)
    
    def test_complete_trading_cycle_buy_signal(self):
        """Test a complete trading cycle with a buy signal."""
        # Configure mock to generate a buy signal
        with patch.object(self.signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create a buy signal
            buy_signal = Mock()
            buy_signal.action = SignalType.BUY
            buy_signal.confidence = 0.8
            buy_signal.price = 45300
            buy_signal.timestamp = datetime.now()
            buy_signal.strategy = "Test Strategy"
            buy_signal.reasoning = "Test buy signal"
            type(buy_signal.action).value = MagicMock(return_value="BUY")
            
            mock_evaluate.return_value = buy_signal
            
            # Configure trader mock
            mock_trade_result = TradeResult(
                order_id="test-order-id",
                symbol="BTC/USD",
                side="BUY",
                quantity=0.001,
                price=45300,
                status="filled",
                timestamp=datetime.now(),
                fees=0.1
            )
            self.mock_trader.execute_trade.return_value = mock_trade_result
            
            # Configure position manager mock
            mock_position = Mock()
            mock_position.qty = 0.001
            mock_position.market_value = 45.3
            mock_position.unrealized_pl = 0.0
            mock_position.avg_entry_price = 45300
            self.mock_position_manager.get_position.return_value = mock_position
            
            # Execute the trading cycle
            result = self.trading_cycle.execute()
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify method calls
            self.mock_data_fetcher.fetch_crypto_data.assert_called_once()
            mock_evaluate.assert_called_once()
            self.mock_trader.execute_trade.assert_called_once_with(buy_signal)
            self.mock_position_manager.get_position.assert_called_once()
    
    def test_complete_trading_cycle_sell_signal(self):
        """Test a complete trading cycle with a sell signal."""
        # Configure mock to generate a sell signal
        with patch.object(self.signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create a sell signal
            sell_signal = Mock()
            sell_signal.action = SignalType.SELL
            sell_signal.confidence = 0.8
            sell_signal.price = 45300
            sell_signal.timestamp = datetime.now()
            sell_signal.strategy = "Test Strategy"
            sell_signal.reasoning = "Test sell signal"
            type(sell_signal.action).value = MagicMock(return_value="SELL")
            
            mock_evaluate.return_value = sell_signal
            
            # Configure trader mock
            mock_trade_result = TradeResult(
                order_id="test-order-id",
                symbol="BTC/USD",
                side="SELL",
                quantity=0.001,
                price=45300,
                status="filled",
                timestamp=datetime.now(),
                fees=0.1
            )
            self.mock_trader.execute_trade.return_value = mock_trade_result
            
            # Configure position manager mock
            mock_position = Mock()
            mock_position.qty = 0.0
            mock_position.market_value = 0.0
            mock_position.unrealized_pl = 0.0
            mock_position.avg_entry_price = 0.0
            self.mock_position_manager.get_position.return_value = mock_position
            
            # Execute the trading cycle
            result = self.trading_cycle.execute()
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify method calls
            self.mock_data_fetcher.fetch_crypto_data.assert_called_once()
            mock_evaluate.assert_called_once()
            self.mock_trader.execute_trade.assert_called_once_with(sell_signal)
            self.mock_position_manager.get_position.assert_called_once()
    
    def test_complete_trading_cycle_hold_signal(self):
        """Test a complete trading cycle with a hold signal."""
        # Configure mock to generate a hold signal
        with patch.object(self.signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create a hold signal
            hold_signal = Mock()
            hold_signal.action = SignalType.HOLD
            hold_signal.confidence = 0.0
            hold_signal.price = 45300
            hold_signal.timestamp = datetime.now()
            hold_signal.strategy = "Test Strategy"
            hold_signal.reasoning = "Test hold signal"
            type(hold_signal.action).value = MagicMock(return_value="HOLD")
            
            mock_evaluate.return_value = hold_signal
            
            # Execute the trading cycle
            result = self.trading_cycle.execute()
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify method calls
            self.mock_data_fetcher.fetch_crypto_data.assert_called_once()
            mock_evaluate.assert_called_once()
            self.mock_trader.execute_trade.assert_not_called()
    
    def test_scheduler_execution(self):
        """Test scheduler execution of trading cycles."""
        # Configure mock to generate a hold signal
        with patch.object(self.signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create a hold signal
            hold_signal = Mock()
            hold_signal.action = SignalType.HOLD
            hold_signal.confidence = 0.0
            hold_signal.price = 45300
            hold_signal.timestamp = datetime.now()
            hold_signal.strategy = "Test Strategy"
            hold_signal.reasoning = "Test hold signal"
            type(hold_signal.action).value = MagicMock(return_value="HOLD")
            
            mock_evaluate.return_value = hold_signal
            
            # Mock the scheduler's add_job method
            self.scheduler.scheduler = Mock()
            
            # Execute the trading cycle through the scheduler
            self.scheduler.execute_trading_cycle()
            
            # Verify method calls
            self.mock_data_fetcher.fetch_crypto_data.assert_called_once()
            mock_evaluate.assert_called_once()
    
    def test_error_recovery_in_trading_cycle(self):
        """Test error recovery in trading cycle."""
        # Configure data fetcher to raise an exception then succeed
        self.mock_data_fetcher.fetch_crypto_data.side_effect = [
            Exception("Test exception"),
            self.sample_data
        ]
        
        # Configure mock to generate a hold signal
        with patch.object(self.signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create a hold signal
            hold_signal = Mock()
            hold_signal.action = SignalType.HOLD
            hold_signal.confidence = 0.0
            hold_signal.price = 45300
            hold_signal.timestamp = datetime.now()
            hold_signal.strategy = "Test Strategy"
            hold_signal.reasoning = "Test hold signal"
            type(hold_signal.action).value = MagicMock(return_value="HOLD")
            
            mock_evaluate.return_value = hold_signal
            
            # Execute the trading cycle with patched sleep to avoid delays
            with patch('time.sleep'):
                result = self.trading_cycle.execute()
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify method calls
            self.assertEqual(self.mock_data_fetcher.fetch_crypto_data.call_count, 2)
            mock_evaluate.assert_called_once()
    
    def test_paper_trading_integration(self):
        """Test integration with paper trading mode."""
        # Create a real trader with paper trading
        with patch('bot.trader.TradingClient') as mock_client_class:
            # Configure mock client
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # Create trader with paper trading
            trader = Trader(self.credentials, self.settings)
            
            # Verify paper trading was enabled
            mock_client_class.assert_called_once_with(
                api_key="test_key",
                secret_key="test_secret",
                paper=True
            )
            
            # Replace mock trader in trading cycle
            self.trading_cycle.trader = trader
            
            # Configure mock to generate a hold signal
            with patch.object(self.signal_generator, 'evaluate_all_strategies') as mock_evaluate:
                # Create a hold signal
                hold_signal = Mock()
                hold_signal.action = SignalType.HOLD
                hold_signal.confidence = 0.0
                hold_signal.price = 45300
                hold_signal.timestamp = datetime.now()
                hold_signal.strategy = "Test Strategy"
                hold_signal.reasoning = "Test hold signal"
                type(hold_signal.action).value = MagicMock(return_value="HOLD")
                
                mock_evaluate.return_value = hold_signal
                
                # Execute the trading cycle
                result = self.trading_cycle.execute()
                
                # Verify the result
                self.assertTrue(result)


class TestEndToEndDataFlow(unittest.TestCase):
    """End-to-end tests for data flow from fetching to execution."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for logs
        self.test_log_dir = tempfile.mkdtemp()
        
        # Create mock credentials
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        
        # Create trading settings
        self.settings = TradingSettings(
            symbol="BTC/USD",
            trade_amount=10.0,
            max_position_size=100.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
            min_trade_interval=5
        )
        
        # Create logger
        self.logger = TradingLogger(log_dir=self.test_log_dir, use_rich=False)
        
        # Create error handler
        self.error_handler = ErrorHandler()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary log directory
        import shutil
        shutil.rmtree(self.test_log_dir)
    
    def test_end_to_end_data_flow(self):
        """Test end-to-end data flow from fetching to execution."""
        # Create sample data with a clear buy signal pattern
        dates = pd.date_range(start='2023-01-01', periods=50, freq='5Min')
        sample_data = pd.DataFrame({
            'open': [45000] * 50,
            'high': [45500] * 50,
            'low': [44500] * 50,
            'close': [45000] * 50,
            'volume': [1000] * 50
        }, index=dates)
        
        # Create a clear buy signal pattern (fast MA crossing above slow MA)
        # First 25 bars: fast MA below slow MA
        # Last 25 bars: fast MA above slow MA
        sample_data['close'].iloc[:25] = np.linspace(44000, 45000, 25)
        sample_data['close'].iloc[25:] = np.linspace(45000, 46000, 25)
        
        # Create mocks with our sample data
        with patch('bot.data_fetcher.CryptoHistoricalDataClient'):
            # Create data fetcher with mocked client
            data_fetcher = DataFetcher(self.credentials)
            
            # Mock fetch_crypto_data to return our sample data
            data_fetcher.fetch_crypto_data = Mock(return_value=sample_data)
            data_fetcher.get_latest_price = Mock(return_value=sample_data['close'].iloc[-1])
            
            # Create real strategies
            ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
            rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
            signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
            
            # Create mock trader
            mock_trader = Mock(spec=Trader)
            mock_position_manager = Mock()
            mock_trader.position_manager = mock_position_manager
            
            # Create trading cycle
            trading_cycle = TradingCycle(
                data_fetcher=data_fetcher,
                signal_generator=signal_generator,
                trader=mock_trader,
                logger=self.logger,
                error_handler=self.error_handler,
                symbol="BTC/USD"
            )
            
            # Execute the trading cycle
            result = trading_cycle.execute()
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify trader was called with a buy signal
            mock_trader.execute_trade.assert_called_once()
            signal = mock_trader.execute_trade.call_args[0][0]
            self.assertEqual(signal.action, SignalType.BUY)
    
    def test_data_validation_in_flow(self):
        """Test data validation in the end-to-end flow."""
        # Create invalid sample data (missing columns)
        dates = pd.date_range(start='2023-01-01', periods=50, freq='5Min')
        invalid_data = pd.DataFrame({
            'open': [45000] * 50,
            'high': [45500] * 50,
            # Missing 'low' column
            'close': [45000] * 50,
            'volume': [1000] * 50
        }, index=dates)
        
        # Create mocks with our invalid data
        with patch('bot.data_fetcher.CryptoHistoricalDataClient'):
            # Create data fetcher with mocked client
            data_fetcher = DataFetcher(self.credentials)
            
            # First return invalid data, then valid data
            valid_data = invalid_data.copy()
            valid_data['low'] = [44500] * 50
            data_fetcher.fetch_crypto_data = Mock(side_effect=[invalid_data, valid_data])
            data_fetcher.get_latest_price = Mock(return_value=45000)
            
            # Create strategies
            ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
            rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
            signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
            
            # Create mock trader
            mock_trader = Mock(spec=Trader)
            mock_position_manager = Mock()
            mock_trader.position_manager = mock_position_manager
            
            # Create trading cycle
            trading_cycle = TradingCycle(
                data_fetcher=data_fetcher,
                signal_generator=signal_generator,
                trader=mock_trader,
                logger=self.logger,
                error_handler=self.error_handler,
                symbol="BTC/USD"
            )
            
            # Execute the trading cycle with patched sleep to avoid delays
            with patch('time.sleep'):
                result = trading_cycle.execute()
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify data fetcher was called twice (retry after validation failure)
            self.assertEqual(data_fetcher.fetch_crypto_data.call_count, 2)


if __name__ == '__main__':
    unittest.main()