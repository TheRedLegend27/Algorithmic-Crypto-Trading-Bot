"""
Unit Tests for Performance Optimizer

Tests for performance profiling, caching, parallel processing, and resource monitoring.
"""

import pytest
import asyncio
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from bot.adaptive.performance_optimizer import (
    PerformanceProfiler, CacheManager, ParallelProcessor,
    ResourceMonitor, PerformanceOptimizer, PerformanceMetrics,
    profile_performance, cached
)


class TestPerformanceProfiler:
    """Test performance profiler functionality"""
    
    def test_profiler_initialization(self):
        """Test profiler initialization"""
        profiler = PerformanceProfiler(enabled=True)
        assert profiler.enabled is True
        assert len(profiler.profiles) == 0
        
        profiler_disabled = PerformanceProfiler(enabled=False)
        assert profiler_disabled.enabled is False
    
    def test_function_profiling(self):
        """Test function profiling decorator"""
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile_function("test_function")
        def slow_function():
            time.sleep(0.01)  # 10ms
            return "result"
        
        # Call function multiple times
        for _ in range(3):
            result = slow_function()
            assert result == "result"
        
        # Check profile data
        assert "test_function" in profiler.profiles
        profile = profiler.profiles["test_function"]
        assert profile.call_count == 3
        assert profile.total_time > 0.025  # At least 30ms total
        assert profile.avg_time > 0.008   # At least 8ms average
        assert profile.min_time > 0
        assert profile.max_time > 0
        assert profile.last_called is not None
    
    @pytest.mark.asyncio
    async def test_async_function_profiling(self):
        """Test async function profiling"""
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile_function("async_test_function")
        async def async_slow_function():
            await asyncio.sleep(0.01)  # 10ms
            return "async_result"
        
        # Call async function
        result = await async_slow_function()
        assert result == "async_result"
        
        # Check profile data
        assert "async_test_function" in profiler.profiles
        profile = profiler.profiles["async_test_function"]
        assert profile.call_count == 1
        assert profile.total_time > 0.008
    
    def test_profile_block_context_manager(self):
        """Test profile block context manager"""
        profiler = PerformanceProfiler(enabled=True)
        
        with profiler.profile_block("test_block"):
            time.sleep(0.01)
        
        assert "test_block" in profiler.profiles
        profile = profiler.profiles["test_block"]
        assert profile.call_count == 1
        assert profile.total_time > 0.008
    
    def test_disabled_profiler(self):
        """Test that disabled profiler doesn't record data"""
        profiler = PerformanceProfiler(enabled=False)
        
        @profiler.profile_function("disabled_test")
        def test_function():
            return "result"
        
        result = test_function()
        assert result == "result"
        assert len(profiler.profiles) == 0
    
    def test_top_functions(self):
        """Test getting top functions by execution time"""
        profiler = PerformanceProfiler(enabled=True)
        
        # Create functions with different execution times
        @profiler.profile_function("fast_function")
        def fast_function():
            time.sleep(0.001)
        
        @profiler.profile_function("slow_function")
        def slow_function():
            time.sleep(0.01)
        
        # Call functions
        fast_function()
        slow_function()
        
        top_functions = profiler.get_top_functions(2)
        assert len(top_functions) == 2
        assert top_functions[0].function_name == "slow_function"
        assert top_functions[1].function_name == "fast_function"
    
    def test_profile_report(self):
        """Test profile report generation"""
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile_function("report_test")
        def test_function():
            time.sleep(0.001)
        
        test_function()
        
        report = profiler.get_profile_report()
        assert "Performance Profile Report" in report
        assert "report_test" in report
        assert "Calls" in report
        assert "Total(s)" in report
    
    def test_profile_reset(self):
        """Test profile data reset"""
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile_function("reset_test")
        def test_function():
            pass
        
        test_function()
        assert len(profiler.profiles) == 1
        
        profiler.reset()
        assert len(profiler.profiles) == 0


class TestCacheManager:
    """Test cache manager functionality"""
    
    def test_cache_initialization(self):
        """Test cache initialization"""
        cache = CacheManager(max_size=100, default_ttl=60)
        assert cache.max_size == 100
        assert cache.default_ttl == 60
        assert len(cache._cache) == 0
    
    def test_cache_set_get(self):
        """Test basic cache set and get operations"""
        cache = CacheManager(max_size=10, default_ttl=60)
        
        # Set and get value
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Get non-existent key
        assert cache.get("non_existent") is None
    
    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration"""
        cache = CacheManager(max_size=10, default_ttl=1)  # 1 second TTL
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        assert cache.get("key1") is None
    
    def test_cache_custom_ttl(self):
        """Test cache with custom TTL"""
        cache = CacheManager(max_size=10, default_ttl=60)
        
        cache.set("key1", "value1", ttl=1)  # 1 second TTL
        assert cache.get("key1") == "value1"
        
        time.sleep(1.1)
        assert cache.get("key1") is None
    
    def test_cache_size_limit(self):
        """Test cache size limit and LRU eviction"""
        cache = CacheManager(max_size=2, default_ttl=60)
        
        # Fill cache to capacity
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache._cache) == 2
        
        # Access key1 to make it more recently used
        cache.get("key1")
        
        # Add third item, should evict key2 (LRU)
        cache.set("key3", "value3")
        assert len(cache._cache) == 2
        assert cache.get("key1") == "value1"  # Still exists
        assert cache.get("key2") is None      # Evicted
        assert cache.get("key3") == "value3"  # New item
    
    def test_cache_delete(self):
        """Test cache deletion"""
        cache = CacheManager(max_size=10, default_ttl=60)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Delete existing key
        assert cache.delete("key1") is True
        assert cache.get("key1") is None
        
        # Delete non-existent key
        assert cache.delete("non_existent") is False
    
    def test_cache_clear(self):
        """Test cache clear operation"""
        cache = CacheManager(max_size=10, default_ttl=60)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache._cache) == 2
        
        cache.clear()
        assert len(cache._cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_stats(self):
        """Test cache statistics"""
        cache = CacheManager(max_size=10, default_ttl=60)
        
        cache.set("key1", "value1")
        stats = cache.get_stats()
        
        assert stats['size'] == 1
        assert stats['max_size'] == 10
        assert 'hit_rate' in stats
        assert 'memory_usage' in stats


class TestParallelProcessor:
    """Test parallel processor functionality"""
    
    def test_processor_initialization(self):
        """Test processor initialization"""
        processor = ParallelProcessor(max_workers=2)
        assert processor.max_workers == 2
        assert processor.thread_executor is not None
        assert processor.process_executor is not None
    
    @pytest.mark.asyncio
    async def test_run_in_thread(self):
        """Test running function in thread pool"""
        processor = ParallelProcessor(max_workers=2)
        
        def cpu_bound_task(n):
            return sum(i * i for i in range(n))
        
        result = await processor.run_in_thread(cpu_bound_task, 1000)
        expected = sum(i * i for i in range(1000))
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_run_parallel_tasks(self):
        """Test running multiple tasks in parallel"""
        processor = ParallelProcessor(max_workers=2)
        
        def square(x):
            return x * x
        
        tasks = [
            (square, (2,), {}),
            (square, (3,), {}),
            (square, (4,), {})
        ]
        
        results = await processor.run_parallel_tasks(tasks)
        assert results == [4, 9, 16]
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing"""
        processor = ParallelProcessor(max_workers=2)
        
        def double(x):
            return x * 2
        
        items = [1, 2, 3, 4, 5]
        results = await processor.run_batch_processing(items, double, batch_size=2)
        assert results == [2, 4, 6, 8, 10]
    
    def test_processor_shutdown(self):
        """Test processor shutdown"""
        processor = ParallelProcessor(max_workers=2)
        processor.shutdown()
        # Should not raise exception


class TestResourceMonitor:
    """Test resource monitor functionality"""
    
    def test_monitor_initialization(self):
        """Test monitor initialization"""
        monitor = ResourceMonitor(check_interval=30)
        assert monitor.check_interval == 30
        assert len(monitor.metrics_history) == 0
        assert monitor.alert_thresholds['cpu_usage'] == 80.0
        assert not monitor._monitoring
    
    def test_set_threshold(self):
        """Test setting alert thresholds"""
        monitor = ResourceMonitor()
        monitor.set_threshold('cpu_usage', 90.0)
        assert monitor.alert_thresholds['cpu_usage'] == 90.0
    
    def test_add_alert_callback(self):
        """Test adding alert callbacks"""
        monitor = ResourceMonitor()
        
        def alert_callback(alert, metrics):
            pass
        
        monitor.add_alert_callback(alert_callback)
        assert len(monitor.alert_callbacks) == 1
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.net_io_counters')
    @patch('psutil.pids')
    @patch('psutil.Process')
    def test_get_current_metrics(self, mock_process, mock_pids, mock_net, 
                                mock_disk, mock_memory, mock_cpu):
        """Test getting current system metrics"""
        # Mock system metrics
        mock_cpu.return_value = 50.0
        
        mock_memory_obj = Mock()
        mock_memory_obj.percent = 60.0
        mock_memory_obj.available = 4 * 1024 ** 3  # 4GB
        mock_memory.return_value = mock_memory_obj
        
        mock_disk_obj = Mock()
        mock_disk_obj.percent = 70.0
        mock_disk.return_value = mock_disk_obj
        
        mock_net_obj = Mock()
        mock_net_obj.bytes_sent = 1000
        mock_net_obj.bytes_recv = 2000
        mock_net_obj.packets_sent = 10
        mock_net_obj.packets_recv = 20
        mock_net.return_value = mock_net_obj
        
        mock_pids.return_value = [1, 2, 3, 4, 5]
        
        mock_process_obj = Mock()
        mock_process_obj.num_threads.return_value = 8
        mock_process.return_value = mock_process_obj
        
        monitor = ResourceMonitor()
        metrics = monitor.get_current_metrics()
        
        assert metrics.cpu_usage == 50.0
        assert metrics.memory_usage == 60.0
        assert metrics.memory_available == 4.0
        assert metrics.disk_usage == 70.0
        assert metrics.network_io['bytes_sent'] == 1000
        assert metrics.process_count == 5
        assert metrics.thread_count == 8
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring"""
        monitor = ResourceMonitor(check_interval=1)
        
        # Start monitoring
        await monitor.start_monitoring()
        assert monitor._monitoring is True
        assert monitor._monitor_task is not None
        
        # Stop monitoring
        await monitor.stop_monitoring()
        assert monitor._monitoring is False


class TestPerformanceOptimizer:
    """Test performance optimizer coordination"""
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization"""
        config = {
            'enable_profiling': True,
            'cache_max_size': 500,
            'cache_ttl_seconds': 300,
            'max_worker_threads': 2
        }
        
        optimizer = PerformanceOptimizer(config)
        assert optimizer.profiler.enabled is True
        assert optimizer.cache.max_size == 500
        assert optimizer.parallel_processor.max_workers == 2
    
    @pytest.mark.asyncio
    async def test_optimizer_start_stop(self):
        """Test optimizer start and stop"""
        optimizer = PerformanceOptimizer({'enable_optimization': False})
        
        await optimizer.start()
        # Should start without errors
        
        await optimizer.stop()
        # Should stop without errors
    
    def test_performance_report(self):
        """Test performance report generation"""
        optimizer = PerformanceOptimizer()
        report = optimizer.get_performance_report()
        
        assert 'profiler' in report
        assert 'cache' in report
        assert 'resources' in report
        assert 'parallel_processing' in report


class TestDecorators:
    """Test performance decorator functions"""
    
    def test_profile_performance_decorator(self):
        """Test profile performance decorator"""
        @profile_performance("decorated_function")
        def test_function():
            time.sleep(0.001)
            return "result"
        
        result = test_function()
        assert result == "result"
        
        # Check that profiling was recorded
        optimizer = get_performance_optimizer()
        assert "decorated_function" in optimizer.profiler.profiles
    
    def test_cached_decorator(self):
        """Test cached decorator"""
        call_count = 0
        
        @cached(ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * x
        
        # First call should execute function
        result1 = expensive_function(5)
        assert result1 == 25
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 25
        assert call_count == 1  # Function not called again
        
        # Different argument should execute function
        result3 = expensive_function(6)
        assert result3 == 36
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cached_async_decorator(self):
        """Test cached decorator with async function"""
        call_count = 0
        
        @cached(ttl=60)
        async def async_expensive_function(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)
            return x * x
        
        # First call should execute function
        result1 = await async_expensive_function(5)
        assert result1 == 25
        assert call_count == 1
        
        # Second call should use cache
        result2 = await async_expensive_function(5)
        assert result2 == 25
        assert call_count == 1  # Function not called again


if __name__ == "__main__":
    pytest.main([__file__, "-v"])