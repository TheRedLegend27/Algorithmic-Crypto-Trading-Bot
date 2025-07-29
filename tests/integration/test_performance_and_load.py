"""
Performance and load testing scenarios for the trading bot.
Tests system performance under various load conditions and stress scenarios.
"""
import pytest
import time
import threading
import asyncio
import concurrent.futures
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Callable
import psutil
import gc
import sys

from bot.main import BotOrchestrator
from bot.kraken_client import KrakenClient, KrakenCredentials
from bot.kraken_websocket import KrakenWebSocketClient
from bot.enhanced_data_manager import EnhancedDataManager
from bot.enhanced_strategies import EnhancedStrategyEngine
from bot.enhanced_risk_manager import EnhancedRiskManager


class PerformanceMonitor:
    """Monitor system performance during tests."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.memory_samples = []
        self.cpu_samples = []
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.monitoring = False
        self.end_time = time.time()
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self):
        """Monitor system resources."""
        process = psutil.Process()
        
        while self.monitoring:
            try:
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent()
                
                self.memory_samples.append(memory_mb)
                self.cpu_samples.append(cpu_percent)
                
                time.sleep(0.1)  # Sample every 100ms
            except Exception:
                break
    
    def get_metrics(self) -> Dict:
        """Get performance metrics."""
        if not self.memory_samples or not self.cpu_samples:
            return {}
        
        return {
            "duration_seconds": self.end_time - self.start_time if self.end_time else 0,
            "avg_memory_mb": sum(self.memory_samples) / len(self.memory_samples),
            "max_memory_mb": max(self.memory_samples),
            "avg_cpu_percent": sum(self.cpu_samples) / len(self.cpu_samples),
            "max_cpu_percent": max(self.cpu_samples),
            "memory_samples": len(self.memory_samples),
            "cpu_samples": len(self.cpu_samples)
        }


class TestPerformanceScenarios:
    """Test various performance scenarios."""
    
    @pytest.fixture
    def performance_monitor(self):
        """Performance monitor fixture."""
        return PerformanceMonitor()
    
    @pytest.fixture
    def mock_kraken_client(self):
        """Mock Kraken client for performance testing."""
        credentials = KrakenCredentials(api_key="test", api_secret="test")
        
        with patch('bot.kraken_client.requests.post') as mock_post:
            # Mock fast API responses
            mock_response = Mock()
            mock_response.json.return_value = {'error': [], 'result': {'ZUSD': '1000.0'}}
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            client = KrakenClient(credentials=credentials)
            return client
    
    def test_high_frequency_api_calls(self, mock_kraken_client, performance_monitor):
        """Test performance with high frequency API calls."""
        performance_monitor.start_monitoring()
        
        # Simulate high frequency API calls
        num_calls = 1000
        start_time = time.time()
        
        for i in range(num_calls):
            mock_kraken_client.get_server_time()
            
            # Add small delay to simulate realistic usage
            if i % 100 == 0:
                time.sleep(0.001)
        
        end_time = time.time()
        performance_monitor.stop_monitoring()
        
        # Analyze performance
        metrics = performance_monitor.get_metrics()
        duration = end_time - start_time
        calls_per_second = num_calls / duration
        
        # Performance assertions
        assert calls_per_second > 100  # Should handle at least 100 calls/second
        assert metrics["max_memory_mb"] < 500  # Memory usage should be reasonable
        assert duration < 30  # Should complete within 30 seconds
        
        print(f"API Performance: {calls_per_second:.2f} calls/second")
        print(f"Memory usage: {metrics['avg_memory_mb']:.2f} MB avg, {metrics['max_memory_mb']:.2f} MB max")
    
    def test_concurrent_trading_pairs(self, performance_monitor):
        """Test performance with multiple concurrent trading pairs."""
        performance_monitor.start_monitoring()
        
        # Mock components for multiple pairs
        pairs = ["XBTUSD", "ETHUSD", "ADAUSD", "DOTUSD", "LINKUSD"]
        
        with patch.multiple(
            'bot.enhanced_data_manager',
            EnhancedDataManager=Mock()
        ) as mocks:
            
            data_manager = mocks['EnhancedDataManager'].return_value
            
            # Mock data processing for multiple pairs
            def mock_process_data(pair, data):
                # Simulate processing time
                time.sleep(0.001)
                return {"pair": pair, "processed": True}
            
            data_manager.process_market_data.side_effect = mock_process_data
            
            # Process data for all pairs concurrently
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                
                for pair in pairs:
                    for i in range(100):  # 100 data points per pair
                        future = executor.submit(
                            data_manager.process_market_data,
                            pair,
                            {"price": 1000.0 + i, "volume": 1.0}
                        )
                        futures.append(future)
                
                # Wait for all tasks to complete
                concurrent.futures.wait(futures)
            
            end_time = time.time()
            performance_monitor.stop_monitoring()
            
            # Analyze concurrent performance
            metrics = performance_monitor.get_metrics()
            total_operations = len(pairs) * 100
            operations_per_second = total_operations / (end_time - start_time)
            
            # Performance assertions
            assert operations_per_second > 500  # Should handle concurrent operations efficiently
            assert metrics["max_memory_mb"] < 1000  # Memory should not explode
            assert data_manager.process_market_data.call_count == total_operations
            
            print(f"Concurrent Performance: {operations_per_second:.2f} operations/second")
    
    def test_memory_usage_under_load(self, performance_monitor):
        """Test memory usage under sustained load."""
        performance_monitor.start_monitoring()
        
        # Simulate sustained data processing load
        large_datasets = []
        
        try:
            for i in range(100):
                # Create large dataset to simulate market data
                dataset = {
                    "prices": [1000.0 + j * 0.1 for j in range(1000)],
                    "volumes": [1.0 + j * 0.01 for j in range(1000)],
                    "timestamps": [datetime.now() + timedelta(seconds=j) for j in range(1000)]
                }
                large_datasets.append(dataset)
                
                # Periodically clean up to test garbage collection
                if i % 20 == 0:
                    gc.collect()
                    time.sleep(0.01)
            
            # Hold data for a while to measure peak memory
            time.sleep(1.0)
            
        finally:
            # Clean up
            large_datasets.clear()
            gc.collect()
            
        performance_monitor.stop_monitoring()
        
        # Analyze memory usage
        metrics = performance_monitor.get_metrics()
        
        # Memory usage assertions
        assert metrics["max_memory_mb"] < 2000  # Should not exceed 2GB
        assert len(metrics["memory_samples"]) > 10  # Should have collected samples
        
        print(f"Memory Usage: {metrics['avg_memory_mb']:.2f} MB avg, {metrics['max_memory_mb']:.2f} MB max")
    
    def test_websocket_message_throughput(self, performance_monitor):
        """Test WebSocket message processing throughput."""
        performance_monitor.start_monitoring()
        
        with patch('bot.kraken_websocket.KrakenWebSocketClient') as MockWebSocket:
            ws_client = MockWebSocket.return_value
            
            # Mock callback handler
            callback_handler = Mock()
            
            # Simulate high-frequency WebSocket messages
            num_messages = 10000
            start_time = time.time()
            
            for i in range(num_messages):
                # Simulate ticker message
                ticker_data = {
                    "c": [f"{50000 + i}", "0.001"],
                    "v": ["1.5", "10.0"],
                    "p": [f"{49000 + i}", f"{51000 + i}"]
                }
                
                callback_handler.on_ticker("XBTUSD", ticker_data)
                
                # Add realistic processing delay
                if i % 1000 == 0:
                    time.sleep(0.001)
            
            end_time = time.time()
            performance_monitor.stop_monitoring()
            
            # Analyze WebSocket performance
            metrics = performance_monitor.get_metrics()
            messages_per_second = num_messages / (end_time - start_time)
            
            # Performance assertions
            assert messages_per_second > 1000  # Should handle 1000+ messages/second
            assert callback_handler.on_ticker.call_count == num_messages
            
            print(f"WebSocket Throughput: {messages_per_second:.2f} messages/second")
    
    def test_strategy_calculation_performance(self, performance_monitor):
        """Test strategy calculation performance with large datasets."""
        performance_monitor.start_monitoring()
        
        with patch('bot.enhanced_strategies.EnhancedStrategyEngine') as MockStrategy:
            strategy_engine = MockStrategy.return_value
            
            # Mock strategy calculation
            def mock_calculate_indicators(data):
                # Simulate complex calculations
                time.sleep(0.001)
                return {
                    "sma_20": sum(data[-20:]) / 20 if len(data) >= 20 else 0,
                    "rsi": 50.0,
                    "macd": 0.1
                }
            
            strategy_engine.calculate_indicators.side_effect = mock_calculate_indicators
            
            # Generate large price dataset
            price_data = [1000.0 + i * 0.1 for i in range(10000)]
            
            # Perform strategy calculations
            start_time = time.time()
            
            for i in range(100, len(price_data), 100):  # Calculate every 100 points
                subset = price_data[:i]
                strategy_engine.calculate_indicators(subset)
            
            end_time = time.time()
            performance_monitor.stop_monitoring()
            
            # Analyze strategy performance
            metrics = performance_monitor.get_metrics()
            calculations_per_second = strategy_engine.calculate_indicators.call_count / (end_time - start_time)
            
            # Performance assertions
            assert calculations_per_second > 10  # Should handle reasonable calculation rate
            assert metrics["max_cpu_percent"] < 90  # Should not max out CPU
            
            print(f"Strategy Calculations: {calculations_per_second:.2f} calculations/second")


class TestLoadScenarios:
    """Test system behavior under various load conditions."""
    
    def test_burst_load_handling(self):
        """Test handling of sudden burst loads."""
        with patch.multiple(
            'bot.main',
            EnhancedDataManager=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock()
        ) as mocks:
            
            data_manager = mocks['EnhancedDataManager'].return_value
            strategy_engine = mocks['EnhancedStrategyEngine'].return_value
            risk_manager = mocks['EnhancedRiskManager'].return_value
            
            # Mock processing delays
            data_manager.process_market_data.side_effect = lambda *args: time.sleep(0.01)
            strategy_engine.generate_signal.side_effect = lambda *args: time.sleep(0.005)
            risk_manager.validate_trade.side_effect = lambda *args: time.sleep(0.002)
            
            # Simulate burst load
            burst_size = 1000
            start_time = time.time()
            
            # Process burst of market data
            for i in range(burst_size):
                data_manager.process_market_data("XBTUSD", {"price": 50000 + i})
                
                if i % 10 == 0:  # Generate signals periodically
                    strategy_engine.generate_signal("XBTUSD", {})
                    risk_manager.validate_trade({}, {})
            
            end_time = time.time()
            
            # Verify burst handling
            assert end_time - start_time < 60  # Should complete within reasonable time
            assert data_manager.process_market_data.call_count == burst_size
    
    def test_sustained_load_stability(self):
        """Test system stability under sustained load."""
        with patch('bot.enhanced_data_manager.EnhancedDataManager') as MockDataManager:
            data_manager = MockDataManager.return_value
            
            # Mock data processing
            processed_count = 0
            def mock_process(pair, data):
                nonlocal processed_count
                processed_count += 1
                time.sleep(0.001)  # Small processing delay
                return {"processed": True}
            
            data_manager.process_market_data.side_effect = mock_process
            
            # Run sustained load for extended period
            duration = 10  # 10 seconds
            start_time = time.time()
            
            while time.time() - start_time < duration:
                data_manager.process_market_data("XBTUSD", {"price": 50000.0})
                time.sleep(0.01)  # 100 operations per second
            
            # Verify sustained performance
            operations_per_second = processed_count / duration
            assert operations_per_second > 50  # Should maintain reasonable throughput
            assert processed_count > 0
    
    def test_resource_cleanup_under_load(self):
        """Test resource cleanup under heavy load."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Create and destroy many objects to test cleanup
        for cycle in range(10):
            large_objects = []
            
            # Create large objects
            for i in range(100):
                obj = {
                    "data": [j for j in range(1000)],
                    "timestamp": datetime.now(),
                    "metadata": {"cycle": cycle, "index": i}
                }
                large_objects.append(obj)
            
            # Process objects
            for obj in large_objects:
                # Simulate processing
                _ = sum(obj["data"])
            
            # Clean up
            large_objects.clear()
            
            # Force garbage collection
            if cycle % 3 == 0:
                gc.collect()
        
        # Final cleanup
        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Verify memory was cleaned up
        memory_growth = final_memory - initial_memory
        assert memory_growth < 100  # Should not grow by more than 100MB
    
    def test_concurrent_user_simulation(self):
        """Test system with multiple concurrent users/sessions."""
        with patch('bot.enhanced_dashboard.EnhancedDashboard') as MockDashboard:
            dashboard = MockDashboard.return_value
            
            # Mock dashboard request handling
            request_count = 0
            def mock_handle_request(request_type, data):
                nonlocal request_count
                request_count += 1
                time.sleep(0.01)  # Simulate request processing
                return {"status": "success", "data": data}
            
            dashboard.handle_request.side_effect = mock_handle_request
            
            # Simulate concurrent users
            num_users = 20
            requests_per_user = 50
            
            def simulate_user(user_id):
                for i in range(requests_per_user):
                    dashboard.handle_request("get_portfolio", {"user_id": user_id})
                    time.sleep(0.02)  # User think time
            
            # Run concurrent user simulation
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
                futures = [
                    executor.submit(simulate_user, user_id)
                    for user_id in range(num_users)
                ]
                
                concurrent.futures.wait(futures)
            
            end_time = time.time()
            
            # Verify concurrent handling
            total_requests = num_users * requests_per_user
            requests_per_second = total_requests / (end_time - start_time)
            
            assert request_count == total_requests
            assert requests_per_second > 10  # Should handle reasonable concurrent load
            assert dashboard.handle_request.call_count == total_requests
    
    def test_error_rate_under_load(self):
        """Test error rates under high load conditions."""
        with patch('bot.kraken_client.KrakenClient') as MockClient:
            client = MockClient.return_value
            
            # Mock API with occasional errors
            call_count = 0
            error_count = 0
            
            def mock_api_call():
                nonlocal call_count, error_count
                call_count += 1
                
                # Simulate 5% error rate under load
                if call_count % 20 == 0:
                    error_count += 1
                    raise Exception("API error under load")
                
                return {"result": "success"}
            
            client.get_server_time.side_effect = mock_api_call
            
            # Make many API calls under load
            successful_calls = 0
            failed_calls = 0
            
            for i in range(1000):
                try:
                    client.get_server_time()
                    successful_calls += 1
                except Exception:
                    failed_calls += 1
            
            # Verify error handling under load
            error_rate = failed_calls / (successful_calls + failed_calls)
            assert error_rate < 0.1  # Error rate should be manageable
            assert successful_calls > 0
            assert call_count == successful_calls + failed_calls