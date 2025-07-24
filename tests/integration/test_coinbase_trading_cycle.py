"""
End-to-end integration tests for Coinbase trading cycles.
Tests complete trading workflows from authentication to order execution.
"""
import unittest
import pytest
from unittest.mock import patch, Mock, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import tempfile
import time

from bot.config import Config
from bot.coinbase_client import CoinbaseClient
from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.coinbase_trader import CoinbaseTrader
from bot.coinbase_websocket import CoinbaseWebSocket
from bot.crypto_order_manager import CryptoOrderManager
from bot.crypto_position_manager import CryptoPositionManager
from bot.crypto_risk_manager import CryptoRiskManager
from bot.strategy import MovingAverageCrossover, RSIStrategy, SignalGenerator, SignalType
from bot.logger import TradingLogger
from bot.scheduler import TradingCycle, TradingScheduler
from bot.coinbase_error_handler import CoinbaseErrorHandler


class TestCoinbaseTradingCycleIntegration:
    """End-to-end integration tests for Coinbase trading cycles."""
    
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
        dates = pd.date_range(start='2023-01-01', periods=50, freq='5Min')
        data = pd.DataFrame({
            'open': np.random.uniform(45000, 46000, 50),
            'high': np.random.uniform(45500, 46500, 50),
            'low': np.random.uniform(44500, 45500, 50),
            'close': np.random.uniform(45000, 46000, 50),
            'volume': np.random.uniform(1000, 2000, 50)
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
    def log_dir(self):
        """Create temporary directory for logs."""
        log_dir = tempfile.mkdtemp()
        yield log_dir
        # Clean up
        import shutil
        shutil.rmtree(log_dir)
    
    @pytest.fixture
    def logger(self, log_dir):
        """Create logger."""
        return TradingLogger(log_dir=log_dir, use_rich=False)
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler."""
        return CoinbaseErrorHandler()
    
    @pytest.fixture
    def mock_coinbase_client(self, credentials):
        """Create mock Coinbase client."""
        with patch('bot.coinbase_client.requests.Session'):
            client = CoinbaseClient(credentials)
            # Mock authentication test
            client.test_authentication = Mock(return_value=True)
            # Mock account endpoints
            client.get_accounts = Mock(return_value=[
                {'id': 'account1', 'currency': 'BTC', 'balance': '1.0', 'available': '1.0', 'hold': '0.0'},
                {'id': 'account2', 'currency': 'USD', 'balance': '50000.0', 'available': '50000.0', 'hold': '0.0'}
            ])
            # Mock order endpoints
            client.create_order = Mock(return_value={'id': 'order1', 'status': 'pending'})
            client.get_order = Mock(return_value={'id': 'order1', 'status': 'filled'})
            # Mock market data endpoints
            client.get_product_candles = Mock(return_value=[
                [1609459200, 45000.0, 45500.0, 44500.0, 45100.0, 1000.0] for _ in range(50)
            ])
            client.get_product_ticker = Mock(return_value={'price': '45100.0'})
            return client
    
    @pytest.fixture
    def mock_data_fetcher(self, mock_coinbase_client, sample_data):
        """Create mock data fetcher."""
        data_fetcher = CoinbaseDataFetcher(mock_coinbase_client)
        data_fetcher.fetch_crypto_ohlcv = Mock(return_value=sample_data)
        data_fetcher.get_latest_price = Mock(return_value=sample_data['close'].iloc[-1])
        return data_fetcher
    
    @pytest.fixture
    def position_manager(self, mock_coinbase_client, crypto_settings):
        """Create position manager."""
        position_manager = CryptoPositionManager(mock_coinbase_client, crypto_settings)
        # Mock methods
        position_manager.get_crypto_balance = Mock(return_value=1.0)
        position_manager.get_position_value_usd = Mock(return_value=45100.0)
        position_manager.calculate_available_balance = Mock(return_value=1.0)
        return position_manager
    
    @pytest.fixture
    def order_manager(self, mock_coinbase_client, crypto_settings):
        """Create order manager."""
        order_manager = CryptoOrderManager(mock_coinbase_client, crypto_settings)
        # Mock methods
        order_manager.place_market_order = Mock(return_value={'id': 'order1', 'status': 'filled'})
        order_manager.place_limit_order = Mock(return_value={'id': 'order2', 'status': 'pending'})
        order_manager.validate_order_size = Mock(return_value=True)
        return order_manager
    
    @pytest.fixture
    def risk_manager(self, position_manager, crypto_settings):
        """Create risk manager."""
        risk_manager = CryptoRiskManager(position_manager, crypto_settings)
        # Mock methods
        risk_manager.validate_trade = Mock(return_value=True)
        return risk_manager
    
    @pytest.fixture
    def coinbase_trader(self, mock_coinbase_client, position_manager, order_manager, risk_manager, crypto_settings):
        """Create Coinbase trader."""
        trader = CoinbaseTrader(
            client=mock_coinbase_client,
            position_manager=position_manager,
            order_manager=order_manager,
            risk_manager=risk_manager,
            settings=crypto_settings
        )
        return trader
    
    @pytest.fixture
    def signal_generator(self):
        """Create signal generator with strategies."""
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        return SignalGenerator([ma_strategy, rsi_strategy])
    
    @pytest.fixture
    def trading_cycle(self, mock_data_fetcher, signal_generator, coinbase_trader, logger, error_handler):
        """Create trading cycle."""
        return TradingCycle(
            data_fetcher=mock_data_fetcher,
            signal_generator=signal_generator,
            trader=coinbase_trader,
            logger=logger,
            error_handler=error_handler,
            symbol="BTC-USD"
        )
    
    def test_complete_buy_trading_cycle(self, trading_cycle, signal_generator, coinbase_trader, sample_data):
        """Test complete trading cycle with buy signal."""
        # Configure signal generator to produce buy signal
        with patch.object(signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create buy signal
            buy_signal = Mock()
            buy_signal.action = SignalType.BUY
            buy_signal.confidence = 0.8
            buy_signal.price = sample_data['close'].iloc[-1]
            buy_signal.timestamp = datetime.now()
            buy_signal.strategy = "Test Strategy"
            buy_signal.reasoning = "Test buy signal"
            type(buy_signal.action).value = MagicMock(return_value="BUY")
            
            mock_evaluate.return_value = buy_signal
            
            # Execute trading cycle
            result = trading_cycle.execute()
            
            # Verify result
            assert result is True
            
            # Verify trader was called with buy signal
            coinbase_trader.execute_crypto_trade.assert_called_once()
            assert coinbase_trader.execute_crypto_trade.call_args[0][0].action == SignalType.BUY
    
    def test_complete_sell_trading_cycle(self, trading_cycle, signal_generator, coinbase_trader, sample_data):
        """Test complete trading cycle with sell signal."""
        # Configure signal generator to produce sell signal
        with patch.object(signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create sell signal
            sell_signal = Mock()
            sell_signal.action = SignalType.SELL
            sell_signal.confidence = 0.8
            sell_signal.price = sample_data['close'].iloc[-1]
            sell_signal.timestamp = datetime.now()
            sell_signal.strategy = "Test Strategy"
            sell_signal.reasoning = "Test sell signal"
            type(sell_signal.action).value = MagicMock(return_value="SELL")
            
            mock_evaluate.return_value = sell_signal
            
            # Execute trading cycle
            result = trading_cycle.execute()
            
            # Verify result
            assert result is True
            
            # Verify trader was called with sell signal
            coinbase_trader.execute_crypto_trade.assert_called_once()
            assert coinbase_trader.execute_crypto_trade.call_args[0][0].action == SignalType.SELL
    
    def test_hold_signal_trading_cycle(self, trading_cycle, signal_generator, coinbase_trader):
        """Test trading cycle with hold signal."""
        # Configure signal generator to produce hold signal
        with patch.object(signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create hold signal
            hold_signal = Mock()
            hold_signal.action = SignalType.HOLD
            hold_signal.confidence = 0.0
            hold_signal.price = 45100.0
            hold_signal.timestamp = datetime.now()
            hold_signal.strategy = "Test Strategy"
            hold_signal.reasoning = "Test hold signal"
            type(hold_signal.action).value = MagicMock(return_value="HOLD")
            
            mock_evaluate.return_value = hold_signal
            
            # Execute trading cycle
            result = trading_cycle.execute()
            
            # Verify result
            assert result is True
            
            # Verify trader was not called
            coinbase_trader.execute_crypto_trade.assert_not_called()
    
    def test_error_recovery_in_trading_cycle(self, trading_cycle, mock_data_fetcher, sample_data, signal_generator):
        """Test error recovery in trading cycle."""
        # Configure data fetcher to raise exception then succeed
        mock_data_fetcher.fetch_crypto_ohlcv.side_effect = [
            Exception("Test exception"),
            sample_data
        ]
        
        # Configure signal generator to produce hold signal
        with patch.object(signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create hold signal
            hold_signal = Mock()
            hold_signal.action = SignalType.HOLD
            hold_signal.confidence = 0.0
            hold_signal.price = 45100.0
            hold_signal.timestamp = datetime.now()
            hold_signal.strategy = "Test Strategy"
            hold_signal.reasoning = "Test hold signal"
            type(hold_signal.action).value = MagicMock(return_value="HOLD")
            
            mock_evaluate.return_value = hold_signal
            
            # Execute trading cycle with patched sleep to avoid delays
            with patch('time.sleep'):
                result = trading_cycle.execute()
            
            # Verify result
            assert result is True
            
            # Verify data fetcher was called twice (retry after error)
            assert mock_data_fetcher.fetch_crypto_ohlcv.call_count == 2
    
    def test_scheduler_execution(self, trading_cycle):
        """Test scheduler execution of trading cycles."""
        # Create scheduler
        scheduler = TradingScheduler(
            trading_cycle=trading_cycle,
            interval_minutes=5,
            error_handler=trading_cycle.error_handler
        )
        
        # Mock scheduler's add_job method
        scheduler.scheduler = Mock()
        
        # Execute trading cycle through scheduler
        with patch.object(trading_cycle, 'execute', return_value=True) as mock_execute:
            scheduler.execute_trading_cycle()
            
            # Verify trading cycle was executed
            mock_execute.assert_called_once()
    
    def test_websocket_integration(self, mock_coinbase_client, crypto_settings, mock_data_fetcher):
        """Test WebSocket integration with trading cycle."""
        # Create WebSocket client
        websocket = CoinbaseWebSocket(mock_coinbase_client, crypto_settings)
        
        # Mock WebSocket methods
        websocket.connect = Mock()
        websocket.subscribe = Mock()
        websocket.is_connected = Mock(return_value=True)
        websocket.get_latest_price = Mock(return_value=45100.0)
        
        # Update data fetcher to use WebSocket
        mock_data_fetcher.websocket = websocket
        mock_data_fetcher.use_websocket = True
        
        # Test WebSocket price fetching
        price = mock_data_fetcher.get_latest_price("BTC-USD")
        
        # Verify WebSocket was used
        assert price == 45100.0
        websocket.get_latest_price.assert_called_once_with("BTC-USD")


class TestCoinbaseEndToEndWorkflow:
    """Test end-to-end Coinbase trading workflows."""
    
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
    def mock_coinbase_responses(self):
        """Mock Coinbase API responses."""
        # Account response
        accounts_response = [
            {
                'id': 'btc-account',
                'currency': 'BTC',
                'balance': '1.0',
                'available': '1.0',
                'hold': '0.0',
                'profile_id': 'profile1',
                'trading_enabled': True
            },
            {
                'id': 'usd-account',
                'currency': 'USD',
                'balance': '50000.0',
                'available': '50000.0',
                'hold': '0.0',
                'profile_id': 'profile1',
                'trading_enabled': True
            }
        ]
        
        # Products response
        products_response = [
            {
                'id': 'BTC-USD',
                'base_currency': 'BTC',
                'quote_currency': 'USD',
                'base_min_size': '0.001',
                'base_max_size': '100.0',
                'quote_increment': '0.01',
                'base_increment': '0.00000001',
                'display_name': 'BTC/USD',
                'min_market_funds': '10',
                'max_market_funds': '1000000',
                'margin_enabled': False,
                'status': 'online',
                'status_message': ''
            }
        ]
        
        # Ticker response
        ticker_response = {
            'trade_id': 1234,
            'price': '45100.0',
            'size': '0.1',
            'time': datetime.now().isoformat(),
            'bid': '45095.0',
            'ask': '45105.0',
            'volume': '1000.0'
        }
        
        # Candles response (timestamp, low, high, open, close, volume)
        candles_response = [
            [int(datetime.now().timestamp()) - i * 300, 45000.0 - i * 10, 45500.0 - i * 10, 
             45100.0 - i * 10, 45200.0 - i * 10, 1000.0] for i in range(50)
        ]
        
        # Order response
        order_response = {
            'id': 'test-order-id',
            'product_id': 'BTC-USD',
            'side': 'buy',
            'size': '0.01',
            'price': '45100.0',
            'status': 'filled',
            'filled_size': '0.01',
            'executed_value': '451.0',
            'fill_fees': '2.255',
            'created_at': datetime.now().isoformat()
        }
        
        return {
            'accounts': accounts_response,
            'products': products_response,
            'ticker': ticker_response,
            'candles': candles_response,
            'order': order_response
        }
    
    @pytest.fixture
    def patched_requests(self, mock_coinbase_responses):
        """Patch requests to return mock responses."""
        with patch('requests.Session.request') as mock_request:
            # Configure mock response
            mock_response = Mock()
            mock_response.status_code = 200
            
            # Configure response content based on endpoint
            def side_effect(*args, **kwargs):
                url = kwargs.get('url', '')
                if 'accounts' in url:
                    mock_response.json.return_value = mock_coinbase_responses['accounts']
                elif 'products' in url and not 'candles' in url:
                    mock_response.json.return_value = mock_coinbase_responses['products']
                elif 'ticker' in url:
                    mock_response.json.return_value = mock_coinbase_responses['ticker']
                elif 'candles' in url:
                    mock_response.json.return_value = mock_coinbase_responses['candles']
                elif 'orders' in url:
                    mock_response.json.return_value = mock_coinbase_responses['order']
                return mock_response
            
            mock_request.side_effect = side_effect
            yield mock_request
    
    def test_end_to_end_workflow(self, setup_environment, patched_requests, mock_coinbase_responses):
        """Test end-to-end workflow from configuration to trade execution."""
        # 1. Load configuration
        config = Config()
        config.load_env_variables()
        
        # 2. Get credentials and settings
        credentials = config.get_coinbase_credentials()
        crypto_settings = config.get_crypto_trading_settings()
        
        # 3. Create Coinbase client
        client = CoinbaseClient(credentials)
        
        # 4. Create components
        data_fetcher = CoinbaseDataFetcher(client)
        position_manager = CryptoPositionManager(client, crypto_settings)
        order_manager = CryptoOrderManager(client, crypto_settings)
        risk_manager = CryptoRiskManager(position_manager, crypto_settings)
        
        # 5. Create trader
        trader = CoinbaseTrader(
            client=client,
            position_manager=position_manager,
            order_manager=order_manager,
            risk_manager=risk_manager,
            settings=crypto_settings
        )
        
        # 6. Create strategies
        ma_strategy = MovingAverageCrossover(fast_period=10, slow_period=20)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
        signal_generator = SignalGenerator([ma_strategy, rsi_strategy])
        
        # 7. Create logger and error handler
        logger = TradingLogger(log_dir=tempfile.mkdtemp(), use_rich=False)
        error_handler = CoinbaseErrorHandler()
        
        # 8. Create trading cycle
        trading_cycle = TradingCycle(
            data_fetcher=data_fetcher,
            signal_generator=signal_generator,
            trader=trader,
            logger=logger,
            error_handler=error_handler,
            symbol="BTC-USD"
        )
        
        # 9. Execute trading cycle with patched signal generator
        with patch.object(signal_generator, 'evaluate_all_strategies') as mock_evaluate:
            # Create buy signal
            buy_signal = Mock()
            buy_signal.action = SignalType.BUY
            buy_signal.confidence = 0.8
            buy_signal.price = float(mock_coinbase_responses['ticker']['price'])
            buy_signal.timestamp = datetime.now()
            buy_signal.strategy = "Test Strategy"
            buy_signal.reasoning = "Test buy signal"
            type(buy_signal.action).value = MagicMock(return_value="BUY")
            
            mock_evaluate.return_value = buy_signal
            
            # Execute trading cycle
            with patch.object(order_manager, 'place_market_order', return_value=mock_coinbase_responses['order']):
                result = trading_cycle.execute()
                
                # Verify result
                assert result is True
                
                # Verify API calls
                call_count = patched_requests.call_count
                assert call_count >= 3  # At least accounts, candles, and order calls
                
                # Verify order was placed
                order_manager.place_market_order.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])