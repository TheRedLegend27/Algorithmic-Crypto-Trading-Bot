"""
Integration tests for market data integration scenarios.
Tests various data availability scenarios and real-world conditions.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import time
import threading
from datetime import datetime, timedelta
import pandas as pd
import tempfile
import shutil

from mock_trading.market_data_integration import (
    MarketDataIntegration, MarketDataPoint, MarketDataSource, MarketStatus
)
from mock_trading.mock_config import MockTradingConfig
from mock_trading.mock_trader import MockTrader
from bot.config import AlpacaCredentials, TradingSettings
from bot.strategy import TradingSignal, SignalType


class TestMarketDataAvailabilityScenarios(unittest.TestCase):
    """Test various market data availability scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = MockTradingConfig()
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        self.settings = TradingSettings(
            symbol="BTC/USD",
            trade_amount=1000.0,
            max_position_size=5000.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
            min_trade_interval=5
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        pass
    
    def test_primary_source_available(self):
        """Test scenario where primary data source (Alpaca) is available."""
        with patch('mock_trading.market_data_integration.DataFetcher') as mock_data_fetcher:
            # Mock successful Alpaca data fetching
            mock_fetcher_instance = Mock()
            mock_fetcher_instance.get_latest_price.return_value = 50000.0
            mock_data_fetcher.return_value = mock_fetcher_instance
            
            integration = MarketDataIntegration(self.config, self.credentials)
            
            # Test data fetching
            data_point = integration.get_current_price("BTC/USD", use_cache=False)
            
            self.assertIsNotNone(data_point)
            self.assertEqual(data_point.price, 50000.0)
            self.assertEqual(data_point.source, MarketDataSource.ALPACA)
            
            integration.cleanup()
    
    def test_primary_source_unavailable_fallback_works(self):
        """Test scenario where primary source fails but fallback works."""
        with patch('mock_trading.market_data_integration.DataFetcher') as mock_data_fetcher:
            with patch('mock_trading.market_data_integration.YahooDataFetcher') as mock_yahoo_fetcher:
                # Mock Alpaca failure
                mock_data_fetcher.side_effect = Exception("Alpaca API unavailable")
                
                # Mock Yahoo success
                mock_yahoo_instance = Mock()
                mock_yahoo_instance.get_current_price.return_value = 49500.0
                mock_yahoo_fetcher.return_value = mock_yahoo_instance
                
                integration = MarketDataIntegration(self.config, self.credentials)
                integration.fallback_fetcher = mock_yahoo_instance
                
                # Test data fetching
                data_point = integration.get_current_price("BTC/USD", use_cache=False)
                
                self.assertIsNotNone(data_point)
                self.assertEqual(data_point.price, 49500.0)
                self.assertEqual(data_point.source, MarketDataSource.YAHOO)
                
                integration.cleanup()
    
    def test_all_sources_unavailable_cache_fallback(self):
        """Test scenario where all sources fail but cached data is available."""
        integration = MarketDataIntegration(self.config)
        
        # Add cached data
        cached_data = MarketDataPoint(
            symbol="BTC/USD",
            price=48000.0,
            bid=47995.0,
            ask=48005.0,
            volume=1000000.0,
            timestamp=datetime.now() - timedelta(minutes=10),  # Stale but available
            source=MarketDataSource.CACHED
        )
        integration.cache.set("BTC/USD", cached_data)
        
        # Mock all sources to fail
        with patch.object(integration.fallback_fetcher, 'get_current_price', side_effect=Exception("All sources failed")):
            data_point = integration.get_current_price("BTC/USD", use_cache=True)
            
            # Should return stale cached data as last resort
            self.assertIsNotNone(data_point)
            self.assertEqual(data_point.price, 48000.0)
        
        integration.cleanup()
    
    def test_no_data_available_anywhere(self):
        """Test scenario where no data is available from any source."""
        integration = MarketDataIntegration(self.config)
        
        # Mock all sources to fail
        with patch.object(integration.fallback_fetcher, 'get_current_price', side_effect=Exception("No data available")):
            data_point = integration.get_current_price("BTC/USD", use_cache=False)
            
            self.assertIsNone(data_point)
        
        integration.cleanup()
    
    def test_intermittent_data_availability(self):
        """Test scenario with intermittent data availability."""
        integration = MarketDataIntegration(self.config)
        
        # Mock intermittent failures
        call_count = 0
        def mock_get_price(symbol):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Fail every other call
                raise Exception("Intermittent failure")
            return 50000.0 + call_count * 100  # Varying prices
        
        with patch.object(integration.fallback_fetcher, 'get_current_price', side_effect=mock_get_price):
            results = []
            for i in range(5):
                data_point = integration.get_current_price("BTC/USD", use_cache=False)
                results.append(data_point)
                time.sleep(0.1)  # Small delay between calls
            
            # Should have some successful and some failed calls
            successful_calls = [r for r in results if r is not None]
            failed_calls = [r for r in results if r is None]
            
            self.assertGreater(len(successful_calls), 0)
            self.assertGreater(len(failed_calls), 0)
        
        integration.cleanup()


class TestMarketHoursScenarios(unittest.TestCase):
    """Test market hours handling scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = MockTradingConfig()
        self.config.market.market_hours_enforcement = True
        self.integration = MarketDataIntegration(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.integration.cleanup()
    
    def test_regular_market_hours_trading_allowed(self):
        """Test trading during regular market hours."""
        with patch.object(self.integration.market_hours, 'get_market_status', return_value=MarketStatus.OPEN):
            self.assertTrue(self.integration.validate_market_hours("BTC/USD"))
    
    def test_market_closed_trading_blocked(self):
        """Test trading blocked when market is closed."""
        with patch.object(self.integration.market_hours, 'get_market_status', return_value=MarketStatus.CLOSED):
            self.assertFalse(self.integration.validate_market_hours("BTC/USD"))
    
    def test_extended_hours_trading_with_setting_enabled(self):
        """Test extended hours trading when setting is enabled."""
        self.config.market.extended_hours_trading = True
        
        with patch.object(self.integration.market_hours, 'get_market_status', return_value=MarketStatus.PRE_MARKET):
            self.assertTrue(self.integration.validate_market_hours("BTC/USD"))
        
        with patch.object(self.integration.market_hours, 'get_market_status', return_value=MarketStatus.AFTER_HOURS):
            self.assertTrue(self.integration.validate_market_hours("BTC/USD"))
    
    def test_extended_hours_trading_with_setting_disabled(self):
        """Test extended hours trading when setting is disabled."""
        self.config.market.extended_hours_trading = False
        
        with patch.object(self.integration.market_hours, 'get_market_status', return_value=MarketStatus.PRE_MARKET):
            self.assertFalse(self.integration.validate_market_hours("BTC/USD"))
        
        with patch.object(self.integration.market_hours, 'get_market_status', return_value=MarketStatus.AFTER_HOURS):
            self.assertFalse(self.integration.validate_market_hours("BTC/USD"))
    
    def test_market_hours_enforcement_disabled(self):
        """Test when market hours enforcement is completely disabled."""
        self.config.market.market_hours_enforcement = False
        
        # Should allow trading regardless of market status
        with patch.object(self.integration.market_hours, 'get_market_status', return_value=MarketStatus.CLOSED):
            self.assertTrue(self.integration.validate_market_hours("BTC/USD"))


class TestRealTimeDataUpdates(unittest.TestCase):
    """Test real-time data update scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = MockTradingConfig()
        self.integration = MarketDataIntegration(self.config)
        self.integration.update_interval = 1  # Fast updates for testing
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.integration.cleanup()
    
    def test_real_time_subscription_and_updates(self):
        """Test real-time subscription and data updates."""
        received_updates = []
        update_event = threading.Event()
        
        def price_callback(data_point):
            received_updates.append(data_point)
            if len(received_updates) >= 2:
                update_event.set()
        
        # Subscribe to updates
        self.integration.subscribe_to_symbol("BTC/USD", price_callback)
        
        # Mock data source to return different prices
        prices = [50000.0, 50100.0, 49900.0]
        price_index = 0
        
        def mock_get_price(symbol):
            nonlocal price_index
            price = prices[price_index % len(prices)]
            price_index += 1
            return price
        
        with patch.object(self.integration.fallback_fetcher, 'get_current_price', side_effect=mock_get_price):
            # Start real-time updates
            self.integration.start_real_time_updates()
            
            # Wait for updates
            update_event.wait(timeout=5.0)
            
            # Stop updates
            self.integration.stop_real_time_updates()
        
        # Verify we received updates
        self.assertGreaterEqual(len(received_updates), 2)
        
        # Verify prices are different (indicating real updates)
        prices_received = [update.price for update in received_updates]
        self.assertGreater(len(set(prices_received)), 1)
    
    def test_multiple_symbol_subscriptions(self):
        """Test subscriptions to multiple symbols."""
        btc_updates = []
        eth_updates = []
        
        def btc_callback(data_point):
            btc_updates.append(data_point)
        
        def eth_callback(data_point):
            eth_updates.append(data_point)
        
        # Subscribe to multiple symbols
        self.integration.subscribe_to_symbol("BTC/USD", btc_callback)
        self.integration.subscribe_to_symbol("ETH/USD", eth_callback)
        
        # Mock different prices for different symbols
        def mock_get_price(symbol):
            if symbol == "BTC/USD":
                return 50000.0
            elif symbol == "ETH/USD":
                return 3000.0
            else:
                return 100.0
        
        with patch.object(self.integration.fallback_fetcher, 'get_current_price', side_effect=mock_get_price):
            # Manually trigger updates
            self.integration.get_current_price("BTC/USD", use_cache=False)
            self.integration.get_current_price("ETH/USD", use_cache=False)
        
        # Verify both symbols received updates
        self.assertEqual(len(btc_updates), 1)
        self.assertEqual(len(eth_updates), 1)
        self.assertEqual(btc_updates[0].price, 50000.0)
        self.assertEqual(eth_updates[0].price, 3000.0)


class TestMockTraderIntegration(unittest.TestCase):
    """Test integration of market data with MockTrader."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        self.settings = TradingSettings(
            symbol="BTC/USD",
            trade_amount=1000.0,
            max_position_size=5000.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
            min_trade_interval=5
        )
    
    def test_mock_trader_with_real_market_data(self):
        """Test MockTrader using real market data for execution."""
        with patch('mock_trading.market_data_integration.YahooDataFetcher') as mock_yahoo:
            # Mock market data
            mock_yahoo_instance = Mock()
            mock_yahoo_instance.get_current_price.return_value = 50000.0
            mock_yahoo.return_value = mock_yahoo_instance
            
            trader = MockTrader(self.credentials, self.settings)
            
            # Test getting current market price
            price = trader.get_current_market_price("BTC/USD")
            self.assertIsNotNone(price)
            self.assertEqual(price, 50000.0)
            
            # Test market data stats
            stats = trader.get_market_data_stats()
            self.assertIn("tracked_symbols", stats)
            self.assertIn("market_status", stats)
            
            trader.cleanup()
    
    def test_mock_trader_market_hours_validation(self):
        """Test MockTrader respects market hours."""
        with patch('mock_trading.market_data_integration.YahooDataFetcher'):
            trader = MockTrader(self.credentials, self.settings)
            
            # Mock market closed
            with patch.object(trader.market_data_integration, 'validate_market_hours', return_value=False):
                signal = TradingSignal(
                    action=SignalType.BUY,
                    confidence=0.8,
                    strategy="test_strategy",
                    price=50000.0,
                    timestamp=datetime.now(),
                    reasoning="Test market hours validation"
                )
                
                # Should not trade when market is closed
                result = trader.execute_trade(signal)
                self.assertIsNone(result)
            
            trader.cleanup()
    
    def test_mock_trader_price_subscription(self):
        """Test MockTrader price subscription functionality."""
        with patch('mock_trading.market_data_integration.YahooDataFetcher'):
            trader = MockTrader(self.credentials, self.settings)
            
            received_prices = []
            
            def price_callback(price):
                received_prices.append(price)
            
            # Subscribe to price updates
            trader.subscribe_to_price_updates("BTC/USD", price_callback)
            
            # Simulate price update
            mock_data_point = MarketDataPoint(
                symbol="BTC/USD",
                price=51000.0,
                bid=50995.0,
                ask=51005.0,
                volume=1000000.0,
                timestamp=datetime.now(),
                source=MarketDataSource.YAHOO
            )
            
            trader.market_data_integration._notify_subscribers(mock_data_point)
            
            # Verify callback was called
            self.assertEqual(len(received_prices), 1)
            self.assertEqual(received_prices[0], 51000.0)
            
            trader.cleanup()
    
    def test_mock_trader_multiple_prices(self):
        """Test MockTrader multiple price fetching."""
        with patch('mock_trading.market_data_integration.YahooDataFetcher') as mock_yahoo:
            # Mock Yahoo fetcher
            mock_yahoo_instance = Mock()
            def mock_price_func(symbol):
                prices = {"BTC/USD": 50000.0, "ETH/USD": 3000.0, "SOL/USD": 100.0}
                return prices.get(symbol, 1000.0)
            mock_yahoo_instance.get_current_price.side_effect = mock_price_func
            mock_yahoo.return_value = mock_yahoo_instance
            
            trader = MockTrader(self.credentials, self.settings)
            trader.market_data_integration.fallback_fetcher = mock_yahoo_instance
            
            # Test multiple price fetching
            symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
            prices = trader.get_multiple_current_prices(symbols)
            
            self.assertEqual(len(prices), 3)
            self.assertEqual(prices["BTC/USD"], 50000.0)
            self.assertEqual(prices["ETH/USD"], 3000.0)
            self.assertEqual(prices["SOL/USD"], 100.0)
            
            trader.cleanup()


class TestDataQualityAndValidation(unittest.TestCase):
    """Test data quality and validation scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = MockTradingConfig()
        self.integration = MarketDataIntegration(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.integration.cleanup()
    
    def test_data_quality_scoring(self):
        """Test data quality scoring and filtering."""
        # Test with valid data that has quality issues
        with patch.object(self.integration.fallback_fetcher, 'get_current_price', return_value=50000.0):
            # Get good data
            good_data = self.integration.get_current_price("BTC/USD", use_cache=False)
            self.assertIsNotNone(good_data)
            self.assertGreater(good_data.quality_score, 0.5)
        
        # Test data quality validation directly
        # Create a data point with quality issues (bid >= ask)
        bad_data_point = MarketDataPoint(
            symbol="ETH/USD",
            price=3000.0,
            bid=3005.0,  # Bid higher than ask (invalid)
            ask=3000.0,
            volume=1000000.0,
            timestamp=datetime.now(),
            source=MarketDataSource.YAHOO
        )
        
        # Should have low quality score due to validation failure
        self.assertEqual(bad_data_point.quality_score, 0.0)
    
    def test_extreme_price_movement_detection(self):
        """Test detection of extreme price movements."""
        symbol = "BTC/USD"
        
        # First, establish a baseline price
        with patch.object(self.integration.fallback_fetcher, 'get_current_price', return_value=50000.0):
            baseline_data = self.integration.get_current_price(symbol, use_cache=False)
            self.assertIsNotNone(baseline_data)
        
        # Then, simulate extreme price movement
        with patch.object(self.integration.fallback_fetcher, 'get_current_price', return_value=100000.0):  # 100% increase
            extreme_data = self.integration.get_current_price(symbol, use_cache=False)
            self.assertIsNotNone(extreme_data)
            
            # The extreme movement should have been detected during processing
            # Check that the quality score was reduced due to validation issues
            self.assertLess(extreme_data.quality_score, 1.0, "Quality score should be reduced for extreme price movements")
        
        # Test the validator directly by manually adding price history and then validating
        # This tests the validator's extreme movement detection logic directly
        validator = self.integration.validator
        
        # Manually add baseline price to history
        validator.price_history[symbol] = [(datetime.now() - timedelta(minutes=1), 50000.0)]
        
        # Create extreme price data point
        extreme_data_point = MarketDataPoint(
            symbol=symbol,
            price=100000.0,  # 100% increase
            bid=99995.0,
            ask=100005.0,
            volume=1000000.0,
            timestamp=datetime.now(),
            source=MarketDataSource.YAHOO
        )
        
        # Validate - should detect extreme movement
        is_valid, issues = validator.validate_data_point(extreme_data_point)
        
        # Should flag extreme price movement
        extreme_movement_detected = any("Extreme price movement" in issue for issue in issues)
        self.assertTrue(extreme_movement_detected, f"Expected extreme price movement detection, got issues: {issues}")
    
    def test_data_consistency_across_sources(self):
        """Test data consistency when multiple sources are available."""
        # Mock both sources with slightly different prices
        with patch('mock_trading.market_data_integration.DataFetcher') as mock_alpaca:
            with patch.object(self.integration.fallback_fetcher, 'get_current_price', return_value=50100.0):
                # Mock Alpaca with different price
                mock_alpaca_instance = Mock()
                mock_alpaca_instance.get_latest_price.return_value = 50000.0
                mock_alpaca.return_value = mock_alpaca_instance
                
                integration = MarketDataIntegration(self.config, AlpacaCredentials("test", "test", "test", True))
                integration.primary_fetcher = mock_alpaca_instance
                
                # Should prefer primary source (Alpaca)
                data_point = integration.get_current_price("BTC/USD", use_cache=False)
                self.assertIsNotNone(data_point)
                self.assertEqual(data_point.price, 50000.0)
                self.assertEqual(data_point.source, MarketDataSource.ALPACA)
                
                integration.cleanup()


if __name__ == '__main__':
    unittest.main()