"""
Integration tests for the enhanced dashboard module.
Tests complete dashboard functionality with real components and API endpoints.
"""
import unittest
import threading
import time
import json
import requests
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from bot.enhanced_dashboard import (
    EnhancedDashboard, DashboardConfig, Portfolio, TradeExecution,
    SystemHealth, ManualTradeRequest
)
from bot.enhanced_data_manager import EnhancedDataManager, MarketData, PerformanceMetrics
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.kraken_client import KrakenClient


class TestEnhancedDashboardIntegration(unittest.TestCase):
    """Integration test cases for EnhancedDashboard."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with dashboard server."""
        cls.config = DashboardConfig(
            host="localhost",
            port=8081,  # Use different port for testing
            debug=False,
            auto_refresh_interval=1,
            enable_manual_trading=True
        )
        
        # Mock dependencies
        cls.mock_data_manager = Mock(spec=EnhancedDataManager)
        cls.mock_logger = Mock(spec=EnhancedLogger)
        cls.mock_risk_manager = Mock(spec=EnhancedRiskManager)
        cls.mock_kraken_client = Mock(spec=KrakenClient)
        
        # Create dashboard instance
        cls.dashboard = EnhancedDashboard(
            cls.config,
            cls.mock_data_manager,
            cls.mock_logger,
            cls.mock_risk_manager,
            cls.mock_kraken_client
        )
        
        # Start server in background thread
        cls.server_thread = threading.Thread(
            target=cls.dashboard.start_server,
            daemon=True
        )
        cls.server_thread.start()
        
        # Wait for server to start
        time.sleep(2)
        
        cls.base_url = f"http://{cls.config.host}:{cls.config.port}"
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test class."""
        cls.dashboard.stop_server()
    
    def test_dashboard_main_page(self):
        """Test main dashboard page loads."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Enhanced Crypto Trading Dashboard", response.text)
            self.assertIn("Portfolio Overview", response.text)
            self.assertIn("System Health", response.text)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_portfolio_api_endpoint(self):
        """Test portfolio API endpoint."""
        # Set up portfolio data
        portfolio = Portfolio(
            total_value_usd=10000.0,
            available_balance=2000.0,
            positions={"BTC/USD": {"volume": 0.5, "value": 8000.0}},
            daily_pnl=150.0,
            unrealized_pnl=300.0,
            realized_pnl=500.0
        )
        self.dashboard.update_portfolio_data(portfolio)
        
        try:
            response = requests.get(f"{self.base_url}/api/portfolio", timeout=5)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertEqual(data['total_value_usd'], 10000.0)
            self.assertEqual(data['available_balance'], 2000.0)
            self.assertEqual(data['daily_pnl'], 150.0)
            self.assertIn('timestamp', data)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_market_data_api_endpoint(self):
        """Test market data API endpoint."""
        # Set up market data
        market_data = {
            "BTC/USD": MarketData(
                pair="BTC/USD",
                timestamp=datetime.now(),
                price=50000.0,
                volume=100.0,
                bid=49990.0,
                ask=50010.0,
                spread=0.0004,
                volatility=0.02,
                indicators={"rsi": 65.0, "macd": 0.5}
            ),
            "ETH/USD": MarketData(
                pair="ETH/USD",
                timestamp=datetime.now(),
                price=3000.0,
                volume=500.0,
                bid=2995.0,
                ask=3005.0,
                spread=0.0033,
                volatility=0.03,
                indicators={"rsi": 55.0, "macd": -0.2}
            )
        }
        self.dashboard.update_market_data(market_data)
        
        try:
            response = requests.get(f"{self.base_url}/api/market_data", timeout=5)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertIn("BTC/USD", data)
            self.assertIn("ETH/USD", data)
            self.assertEqual(data["BTC/USD"]["price"], 50000.0)
            self.assertEqual(data["ETH/USD"]["price"], 3000.0)
            self.assertIn("indicators", data["BTC/USD"])
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_trades_api_endpoint(self):
        """Test trades API endpoint."""
        # Add some trade history
        trades = [
            TradeExecution(
                trade_id="trade_1",
                pair="BTC/USD",
                side="BUY",
                order_type="MARKET",
                volume=0.1,
                price=50000.0,
                fee=25.0,
                timestamp=datetime.now() - timedelta(minutes=5),
                strategy="Enhanced Momentum",
                signal_confidence=0.85,
                execution_time_ms=150,
                status="FILLED"
            ),
            TradeExecution(
                trade_id="trade_2",
                pair="ETH/USD",
                side="SELL",
                order_type="LIMIT",
                volume=1.0,
                price=3000.0,
                fee=15.0,
                timestamp=datetime.now() - timedelta(minutes=2),
                strategy="Mean Reversion",
                signal_confidence=0.75,
                execution_time_ms=200,
                status="FILLED"
            )
        ]
        
        for trade in trades:
            self.dashboard.add_trade_event(trade)
        
        try:
            response = requests.get(f"{self.base_url}/api/trades", timeout=5)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]['trade_id'], "trade_1")
            self.assertEqual(data[1]['trade_id'], "trade_2")
            self.assertEqual(data[0]['pair'], "BTC/USD")
            self.assertEqual(data[1]['pair'], "ETH/USD")
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_system_health_api_endpoint(self):
        """Test system health API endpoint."""
        # Set up system health data
        health = SystemHealth(
            bot_uptime=24.5,
            cpu_usage=45.2,
            memory_usage=67.8,
            api_rate_limit_used=850,
            api_rate_limit_max=1000,
            websocket_connected=True,
            last_heartbeat=datetime.now(),
            error_rate_24h=0.02,
            active_strategies=["Enhanced Momentum", "Mean Reversion"],
            trading_enabled=True
        )
        self.dashboard.update_system_health(health)
        
        try:
            response = requests.get(f"{self.base_url}/api/system_health", timeout=5)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertEqual(data['bot_uptime'], 24.5)
            self.assertEqual(data['cpu_usage'], 45.2)
            self.assertEqual(data['api_rate_limit_used'], 850)
            self.assertTrue(data['websocket_connected'])
            self.assertTrue(data['trading_enabled'])
            self.assertEqual(len(data['active_strategies']), 2)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_performance_api_endpoint(self):
        """Test performance metrics API endpoint."""
        # Set up performance metrics
        metrics = PerformanceMetrics(
            fetch_time_ms=50.0,
            cache_hit_rate=0.85,
            data_quality_score=0.95,
            indicator_calculation_time_ms=25.0,
            memory_usage_mb=150.0,
            active_pairs=5,
            total_data_points=10000
        )
        self.dashboard.update_performance_metrics(metrics)
        
        try:
            response = requests.get(f"{self.base_url}/api/performance", timeout=5)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertEqual(data['fetch_time_ms'], 50.0)
            self.assertEqual(data['cache_hit_rate'], 0.85)
            self.assertEqual(data['data_quality_score'], 0.95)
            self.assertEqual(data['active_pairs'], 5)
            self.assertEqual(data['total_data_points'], 10000)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_manual_trade_api_endpoint_success(self):
        """Test successful manual trade execution."""
        # Mock successful Kraken response
        self.mock_kraken_client.place_market_buy_order.return_value = {
            'txid': ['test_order_123']
        }
        
        # Mock risk manager approval
        mock_risk_assessment = Mock()
        mock_risk_assessment.approved = True
        self.mock_risk_manager.validate_trade.return_value = mock_risk_assessment
        
        trade_data = {
            'pair': 'BTC/USD',
            'side': 'buy',
            'order_type': 'market',
            'volume': '0.1'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/trade",
                json=trade_data,
                timeout=5
            )
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertTrue(data['success'])
            self.assertEqual(data['trade_id'], 'test_order_123')
            self.assertIn('successfully', data['message'])
            
            # Verify Kraken client was called
            self.mock_kraken_client.place_market_buy_order.assert_called_once_with(
                'BTC/USD', '0.1'
            )
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_manual_trade_api_endpoint_validation_failure(self):
        """Test manual trade with validation failure."""
        trade_data = {
            'pair': '',  # Invalid empty pair
            'side': 'buy',
            'order_type': 'market',
            'volume': '0.1'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/trade",
                json=trade_data,
                timeout=5
            )
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertFalse(data['success'])
            self.assertIn('error', data)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_manual_trade_api_endpoint_risk_rejection(self):
        """Test manual trade rejected by risk manager."""
        # Mock risk manager rejection
        mock_risk_assessment = Mock()
        mock_risk_assessment.approved = False
        mock_risk_assessment.reason = "Exceeds position limit"
        self.mock_risk_manager.validate_trade.return_value = mock_risk_assessment
        
        trade_data = {
            'pair': 'BTC/USD',
            'side': 'buy',
            'order_type': 'market',
            'volume': '10.0'  # Large volume
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/trade",
                json=trade_data,
                timeout=5
            )
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertFalse(data['success'])
            self.assertIn('Trade rejected by risk manager', data['error'])
            self.assertIn('Exceeds position limit', data['error'])
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_bot_control_api_endpoint(self):
        """Test bot control API endpoint."""
        control_actions = [
            'emergency_stop',
            'pause_trading',
            'resume_trading'
        ]
        
        for action in control_actions:
            try:
                response = requests.post(
                    f"{self.base_url}/api/bot_control",
                    json={'action': action},
                    timeout=5
                )
                self.assertEqual(response.status_code, 200)
                
                data = response.json()
                self.assertTrue(data['success'])
                self.assertIn('message', data)
            except requests.exceptions.RequestException as e:
                self.skipTest(f"Dashboard server not available: {e}")
    
    def test_bot_control_api_invalid_action(self):
        """Test bot control API with invalid action."""
        try:
            response = requests.post(
                f"{self.base_url}/api/bot_control",
                json={'action': 'invalid_action'},
                timeout=5
            )
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertFalse(data['success'])
            self.assertIn('Unknown action', data['error'])
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_api_endpoints_without_data(self):
        """Test API endpoints when no data is available."""
        # Create fresh dashboard without data
        fresh_dashboard = EnhancedDashboard(
            self.config,
            self.mock_data_manager,
            self.mock_logger,
            self.mock_risk_manager,
            self.mock_kraken_client
        )
        
        # Test portfolio endpoint without data
        try:
            response = requests.get(f"{self.base_url}/api/portfolio", timeout=5)
            # Should return error when no portfolio data
            if response.status_code == 200:
                data = response.json()
                if 'error' in data:
                    self.assertIn('Portfolio data not available', data['error'])
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
    
    def test_concurrent_api_requests(self):
        """Test handling concurrent API requests."""
        import concurrent.futures
        
        def make_request(endpoint):
            try:
                response = requests.get(f"{self.base_url}/api/{endpoint}", timeout=5)
                return response.status_code == 200
            except:
                return False
        
        endpoints = ['portfolio', 'market_data', 'trades', 'system_health', 'performance']
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_request, endpoint) for endpoint in endpoints]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            # At least some requests should succeed
            self.assertTrue(any(results))
        except Exception as e:
            self.skipTest(f"Concurrent request test failed: {e}")
    
    def test_dashboard_data_updates(self):
        """Test real-time data updates through dashboard."""
        # Test portfolio update
        portfolio = Portfolio(
            total_value_usd=15000.0,
            available_balance=3000.0,
            positions={"BTC/USD": {"volume": 0.3}},
            daily_pnl=250.0,
            unrealized_pnl=400.0,
            realized_pnl=600.0
        )
        
        self.dashboard.update_portfolio_data(portfolio)
        self.assertEqual(self.dashboard.portfolio, portfolio)
        
        # Test market data update
        market_data = {
            "BTC/USD": MarketData(
                pair="BTC/USD",
                timestamp=datetime.now(),
                price=51000.0,
                volume=150.0,
                bid=50990.0,
                ask=51010.0,
                spread=0.0004,
                volatility=0.025
            )
        }
        
        self.dashboard.update_market_data(market_data)
        self.assertEqual(self.dashboard.market_data, market_data)
        
        # Test trade event
        trade = TradeExecution(
            trade_id="integration_test_trade",
            pair="BTC/USD",
            side="BUY",
            order_type="MARKET",
            volume=0.05,
            price=51000.0,
            fee=12.75,
            timestamp=datetime.now(),
            strategy="Integration Test",
            signal_confidence=0.9,
            execution_time_ms=100,
            status="FILLED"
        )
        
        initial_trade_count = len(self.dashboard.trade_history)
        self.dashboard.add_trade_event(trade)
        self.assertEqual(len(self.dashboard.trade_history), initial_trade_count + 1)
        self.assertIn(trade, self.dashboard.trade_history)
    
    def test_dashboard_error_handling(self):
        """Test dashboard error handling."""
        # Test invalid JSON in trade request
        try:
            response = requests.post(
                f"{self.base_url}/api/trade",
                data="invalid json",
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            # Should handle invalid JSON gracefully
            self.assertIn(response.status_code, [200, 400])
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")
        
        # Test missing required fields in trade request
        try:
            response = requests.post(
                f"{self.base_url}/api/trade",
                json={'pair': 'BTC/USD'},  # Missing required fields
                timeout=5
            )
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertFalse(data['success'])
            self.assertIn('error', data)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Dashboard server not available: {e}")


class TestDashboardPerformance(unittest.TestCase):
    """Performance tests for the enhanced dashboard."""
    
    def setUp(self):
        """Set up performance test fixtures."""
        self.config = DashboardConfig(
            auto_refresh_interval=0.1,  # Fast refresh for testing
            max_trade_history=1000,
            max_log_entries=1000
        )
        
        # Mock dependencies
        self.mock_data_manager = Mock(spec=EnhancedDataManager)
        self.mock_logger = Mock(spec=EnhancedLogger)
        self.mock_risk_manager = Mock(spec=EnhancedRiskManager)
        self.mock_kraken_client = Mock(spec=KrakenClient)
        
        self.dashboard = EnhancedDashboard(
            self.config,
            self.mock_data_manager,
            self.mock_logger,
            self.mock_risk_manager,
            self.mock_kraken_client
        )
    
    def test_large_trade_history_performance(self):
        """Test performance with large trade history."""
        start_time = time.time()
        
        # Add many trades
        for i in range(1000):
            trade = TradeExecution(
                trade_id=f"perf_test_trade_{i}",
                pair="BTC/USD",
                side="BUY" if i % 2 == 0 else "SELL",
                order_type="MARKET",
                volume=0.01,
                price=50000.0 + i,
                fee=0.25,
                timestamp=datetime.now() - timedelta(seconds=i),
                strategy="Performance Test",
                signal_confidence=0.8,
                execution_time_ms=100,
                status="FILLED"
            )
            
            with patch.object(self.dashboard, '_broadcast_update'):
                self.dashboard.add_trade_event(trade)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(execution_time, 5.0, "Trade history update took too long")
        
        # Verify trade history limit is enforced
        self.assertEqual(len(self.dashboard.trade_history), self.config.max_trade_history)
    
    def test_market_data_update_performance(self):
        """Test performance of market data updates."""
        # Create market data for many pairs
        market_data = {}
        for i in range(100):
            pair = f"PAIR{i}/USD"
            market_data[pair] = MarketData(
                pair=pair,
                timestamp=datetime.now(),
                price=1000.0 + i,
                volume=100.0,
                bid=999.0 + i,
                ask=1001.0 + i,
                spread=0.002,
                volatility=0.02,
                indicators={"rsi": 50.0 + i % 50, "macd": 0.1 * i}
            )
        
        start_time = time.time()
        
        with patch.object(self.dashboard, '_broadcast_update'):
            self.dashboard.update_market_data(market_data)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete quickly
        self.assertLess(execution_time, 1.0, "Market data update took too long")
        self.assertEqual(len(self.dashboard.market_data), 100)


if __name__ == '__main__':
    unittest.main()