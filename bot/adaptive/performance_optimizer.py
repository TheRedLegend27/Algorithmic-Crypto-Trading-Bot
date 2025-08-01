"""
Performance Optimization and Scaling Module

This module provides performance profiling, optimization, and scaling capabilities
for the adaptive trading bot to handle computational bottlenecks and resource management.
"""

import time
import asyncio
import logging
import psutil
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import wraps
import cProfile
import pstats
import io
from contextlib import contextmanager
import weakref
import gc
from collections import defaultdict, deque
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_available: float = 0.0
    disk_usage: float = 0.0
    network_io: Dict[str, float] = field(default_factory=dict)
    process_count: int = 0
    thread_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FunctionProfile:
    """Profile data for a function"""
    function_name: str
    call_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    last_called: Optional[datetime] = None


class PerformanceProfiler:
    """Performance profiler for identifying bottlenecks"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.profiles: Dict[str, FunctionProfile] = {}
        self.call_stack: List[Tuple[str, float]] = []
        self._lock = threading.Lock()
    
    def profile_function(self, func_name: str = None):
        """Decorator to profile function performance"""
        def decorator(func):
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)
                
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    execution_time = end_time - start_time
                    self._record_execution(name, execution_time)
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.enabled:
                    return await func(*args, **kwargs)
                
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    execution_time = end_time - start_time
                    self._record_execution(name, execution_time)
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
        return decorator
    
    def _record_execution(self, func_name: str, execution_time: float):
        """Record function execution time"""
        with self._lock:
            if func_name not in self.profiles:
                self.profiles[func_name] = FunctionProfile(func_name)
            
            profile = self.profiles[func_name]
            profile.call_count += 1
            profile.total_time += execution_time
            profile.avg_time = profile.total_time / profile.call_count
            profile.min_time = min(profile.min_time, execution_time)
            profile.max_time = max(profile.max_time, execution_time)
            profile.last_called = datetime.utcnow()
    
    @contextmanager
    def profile_block(self, block_name: str):
        """Context manager to profile code blocks"""
        if not self.enabled:
            yield
            return
        
        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            self._record_execution(block_name, execution_time)
    
    def get_top_functions(self, limit: int = 10) -> List[FunctionProfile]:
        """Get top functions by total execution time"""
        with self._lock:
            return sorted(
                self.profiles.values(),
                key=lambda p: p.total_time,
                reverse=True
            )[:limit]
    
    def get_profile_report(self) -> str:
        """Generate performance profile report"""
        top_functions = self.get_top_functions(20)
        
        report = ["Performance Profile Report", "=" * 50]
        report.append(f"{'Function':<40} {'Calls':<8} {'Total(s)':<10} {'Avg(ms)':<10} {'Max(ms)':<10}")
        report.append("-" * 88)
        
        for profile in top_functions:
            report.append(
                f"{profile.function_name:<40} "
                f"{profile.call_count:<8} "
                f"{profile.total_time:<10.3f} "
                f"{profile.avg_time * 1000:<10.2f} "
                f"{profile.max_time * 1000:<10.2f}"
            )
        
        return "\n".join(report)
    
    def reset(self):
        """Reset all profile data"""
        with self._lock:
            self.profiles.clear()
            self.call_stack.clear()


class CacheManager:
    """Advanced caching system with TTL and memory management"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._cleanup_thread = None
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread"""
        def cleanup_worker():
            while True:
                try:
                    self._cleanup_expired()
                    time.sleep(60)  # Cleanup every minute
                except Exception as e:
                    logger.error(f"Cache cleanup error: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # Check if expired
            if datetime.utcnow() > entry['expires_at']:
                del self._cache[key]
                del self._access_times[key]
                return None
            
            # Update access time
            self._access_times[key] = datetime.utcnow()
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        with self._lock:
            # Enforce size limit
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            ttl = ttl or self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': datetime.utcnow()
            }
            self._access_times[key] = datetime.utcnow()
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._access_times[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def _evict_lru(self) -> None:
        """Evict least recently used item"""
        if not self._access_times:
            return
        
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[lru_key]
        del self._access_times[lru_key]
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        with self._lock:
            now = datetime.utcnow()
            expired_keys = [
                key for key, entry in self._cache.items()
                if now > entry['expires_at']
            ]
            
            for key in expired_keys:
                del self._cache[key]
                del self._access_times[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': getattr(self, '_hit_count', 0) / max(getattr(self, '_total_requests', 1), 1),
                'memory_usage': sum(len(str(entry)) for entry in self._cache.values())
            }


class ParallelProcessor:
    """Parallel processing manager for CPU-intensive tasks"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(4, (psutil.cpu_count() or 1))
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=self.max_workers)
        self._active_tasks: Dict[str, asyncio.Task] = {}
    
    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Run function in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_executor, func, *args, **kwargs)
    
    async def run_in_process(self, func: Callable, *args, **kwargs) -> Any:
        """Run function in process pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.process_executor, func, *args, **kwargs)
    
    async def run_parallel_tasks(self, tasks: List[Tuple[Callable, tuple, dict]], 
                                use_processes: bool = False) -> List[Any]:
        """Run multiple tasks in parallel"""
        executor = self.process_executor if use_processes else self.thread_executor
        loop = asyncio.get_event_loop()
        
        futures = [
            loop.run_in_executor(executor, func, *args, **kwargs)
            for func, args, kwargs in tasks
        ]
        
        return await asyncio.gather(*futures)
    
    async def run_batch_processing(self, items: List[Any], processor: Callable,
                                 batch_size: int = None, use_processes: bool = False) -> List[Any]:
        """Process items in batches"""
        batch_size = batch_size or self.max_workers * 2
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            tasks = [(processor, (item,), {}) for item in batch]
            batch_results = await self.run_parallel_tasks(tasks, use_processes)
            results.extend(batch_results)
        
        return results
    
    def shutdown(self):
        """Shutdown executors"""
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)


class ResourceMonitor:
    """System resource monitoring and alerting"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.metrics_history: deque = deque(maxlen=1440)  # 24 hours of minute data
        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'disk_usage': 90.0
        }
        self.alert_callbacks: List[Callable] = []
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    def add_alert_callback(self, callback: Callable[[str, PerformanceMetrics], None]):
        """Add callback for resource alerts"""
        self.alert_callbacks.append(callback)
    
    def set_threshold(self, metric: str, threshold: float):
        """Set alert threshold for metric"""
        self.alert_thresholds[metric] = threshold
    
    async def start_monitoring(self):
        """Start resource monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Resource monitoring started")
    
    async def stop_monitoring(self):
        """Stop resource monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                metrics = self.get_current_metrics()
                self.metrics_history.append(metrics)
                
                # Check for alerts
                await self._check_alerts(metrics)
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                await asyncio.sleep(self.check_interval)
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current system metrics"""
        # CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        memory_available = memory.available / (1024 ** 3)  # GB
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage = disk.percent
        
        # Network I/O
        network = psutil.net_io_counters()
        network_io = {
            'bytes_sent': network.bytes_sent,
            'bytes_recv': network.bytes_recv,
            'packets_sent': network.packets_sent,
            'packets_recv': network.packets_recv
        }
        
        # Process info
        process = psutil.Process()
        process_count = len(psutil.pids())
        thread_count = process.num_threads()
        
        return PerformanceMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            memory_available=memory_available,
            disk_usage=disk_usage,
            network_io=network_io,
            process_count=process_count,
            thread_count=thread_count
        )
    
    async def _check_alerts(self, metrics: PerformanceMetrics):
        """Check metrics against thresholds and trigger alerts"""
        alerts = []
        
        if metrics.cpu_usage > self.alert_thresholds.get('cpu_usage', 80):
            alerts.append(f"High CPU usage: {metrics.cpu_usage:.1f}%")
        
        if metrics.memory_usage > self.alert_thresholds.get('memory_usage', 85):
            alerts.append(f"High memory usage: {metrics.memory_usage:.1f}%")
        
        if metrics.disk_usage > self.alert_thresholds.get('disk_usage', 90):
            alerts.append(f"High disk usage: {metrics.disk_usage:.1f}%")
        
        # Trigger alert callbacks
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    await callback(alert, metrics)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for specified time period"""
        if not self.metrics_history:
            return {}
        
        # Get recent metrics
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {}
        
        # Calculate statistics
        cpu_values = [m.cpu_usage for m in recent_metrics]
        memory_values = [m.memory_usage for m in recent_metrics]
        
        return {
            'period_hours': hours,
            'sample_count': len(recent_metrics),
            'cpu_usage': {
                'avg': np.mean(cpu_values),
                'max': np.max(cpu_values),
                'min': np.min(cpu_values),
                'std': np.std(cpu_values)
            },
            'memory_usage': {
                'avg': np.mean(memory_values),
                'max': np.max(memory_values),
                'min': np.min(memory_values),
                'std': np.std(memory_values)
            },
            'latest': recent_metrics[-1]
        }


class PerformanceOptimizer:
    """Main performance optimization coordinator"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.profiler = PerformanceProfiler(
            enabled=self.config.get('enable_profiling', True)
        )
        self.cache = CacheManager(
            max_size=self.config.get('cache_max_size', 1000),
            default_ttl=self.config.get('cache_ttl_seconds', 300)
        )
        self.parallel_processor = ParallelProcessor(
            max_workers=self.config.get('max_worker_threads', 4)
        )
        self.resource_monitor = ResourceMonitor(
            check_interval=self.config.get('monitor_interval_seconds', 60)
        )
        
        # Setup resource monitoring alerts
        self.resource_monitor.add_alert_callback(self._handle_resource_alert)
        
        # Performance optimization settings
        self.optimization_enabled = self.config.get('enable_optimization', True)
        self.auto_gc_enabled = self.config.get('enable_auto_gc', True)
        self.gc_threshold = self.config.get('gc_threshold_mb', 100)
        
        # Start background tasks
        self._optimization_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start performance optimization"""
        await self.resource_monitor.start_monitoring()
        
        if self.optimization_enabled:
            self._optimization_task = asyncio.create_task(self._optimization_loop())
        
        logger.info("Performance optimizer started")
    
    async def stop(self):
        """Stop performance optimization"""
        await self.resource_monitor.stop_monitoring()
        
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass
        
        self.parallel_processor.shutdown()
        logger.info("Performance optimizer stopped")
    
    async def _optimization_loop(self):
        """Main optimization loop"""
        while True:
            try:
                await self._run_optimizations()
                await asyncio.sleep(300)  # Run every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Optimization loop error: {e}")
                await asyncio.sleep(60)
    
    async def _run_optimizations(self):
        """Run performance optimizations"""
        # Memory optimization
        if self.auto_gc_enabled:
            await self._optimize_memory()
        
        # Cache optimization
        await self._optimize_cache()
        
        # Profile analysis
        await self._analyze_performance()
    
    async def _optimize_memory(self):
        """Optimize memory usage"""
        try:
            # Get current memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 ** 2)
            
            if memory_mb > self.gc_threshold:
                # Force garbage collection
                collected = gc.collect()
                logger.debug(f"Garbage collection freed {collected} objects")
                
                # Clear weak references
                gc.collect()
                
        except Exception as e:
            logger.error(f"Memory optimization error: {e}")
    
    async def _optimize_cache(self):
        """Optimize cache performance"""
        try:
            stats = self.cache.get_stats()
            
            # If cache hit rate is low, consider adjusting TTL or size
            if stats['hit_rate'] < 0.5 and stats['size'] < stats['max_size']:
                logger.debug("Low cache hit rate detected, consider tuning cache settings")
            
        except Exception as e:
            logger.error(f"Cache optimization error: {e}")
    
    async def _analyze_performance(self):
        """Analyze performance profiles"""
        try:
            top_functions = self.profiler.get_top_functions(5)
            
            # Log slow functions
            for profile in top_functions:
                if profile.avg_time > 1.0:  # Functions taking more than 1 second on average
                    logger.warning(
                        f"Slow function detected: {profile.function_name} "
                        f"(avg: {profile.avg_time:.2f}s, calls: {profile.call_count})"
                    )
            
        except Exception as e:
            logger.error(f"Performance analysis error: {e}")
    
    async def _handle_resource_alert(self, alert: str, metrics: PerformanceMetrics):
        """Handle resource alerts"""
        logger.warning(f"Resource alert: {alert}")
        
        # Take corrective actions
        if "High memory usage" in alert:
            await self._optimize_memory()
        
        if "High CPU usage" in alert:
            # Reduce parallel processing temporarily
            logger.info("Reducing parallel processing due to high CPU usage")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        return {
            'profiler': {
                'enabled': self.profiler.enabled,
                'top_functions': [
                    {
                        'name': p.function_name,
                        'calls': p.call_count,
                        'total_time': p.total_time,
                        'avg_time': p.avg_time
                    }
                    for p in self.profiler.get_top_functions(10)
                ]
            },
            'cache': self.cache.get_stats(),
            'resources': self.resource_monitor.get_metrics_summary(1),
            'parallel_processing': {
                'max_workers': self.parallel_processor.max_workers,
                'active_tasks': len(self.parallel_processor._active_tasks)
            }
        }


# Global performance optimizer instance
_performance_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer(config: Dict[str, Any] = None) -> PerformanceOptimizer:
    """Get or create performance optimizer instance"""
    global _performance_optimizer
    
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer(config)
    
    return _performance_optimizer


# Convenience decorators
def profile_performance(func_name: str = None):
    """Decorator to profile function performance"""
    optimizer = get_performance_optimizer()
    return optimizer.profiler.profile_function(func_name)


def cached(ttl: int = None, key_func: Callable = None):
    """Decorator to cache function results"""
    def decorator(func):
        cache = get_performance_optimizer().cache
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
    return decorator