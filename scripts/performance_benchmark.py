#!/usr/bin/env python3
"""
Performance Benchmark Script for Adaptive Trading Bot

This script runs comprehensive performance benchmarks to measure system
performance and identify optimization opportunities.
"""

import asyncio
import time
import statistics
import json
import sys
import os
from typing import Dict, List, Any, Callable
from datetime import datetime
import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.adaptive.performance_optimizer import (
    PerformanceOptimizer, PerformanceProfiler, CacheManager,
    ParallelProcessor, ResourceMonitor
)
from bot.adaptive.market_regime_detector import MarketRegimeDetector
from bot.adaptive.ml_engine import MLEngine
from bot.adaptive.adaptive_strategy_engine import AdaptiveStrategyEngine
from bot.adaptive.parameter_optimizer import ParameterOptimizer


class PerformanceBenchmark:
    """Performance benchmark suite"""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.optimizer = PerformanceOptimizer({
            'enable_profiling': True,
            'cache_max_size': 1000,
            'max_worker_threads': 4
        })
    
    async def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all performance benchmarks"""
        print("Starting Performance Benchmark Suite")
        print("=" * 50)
        
        await self.optimizer.start()
        
        try:
            # Core component benchmarks
            await self.benchmark_cache_performance()
            await self.benchmark_parallel_processing()
            await self.benchmark_market_regime_detection()
            await self.benchmark_ml_engine()
            await self.benchmark_strategy_engine()
            await self.benchmark_parameter_optimization()
            
            # System benchmarks
            await self.benchmark_memory_usage()
            await self.benchmark_cpu_usage()
            
            # Generate summary
            self.results['summary'] = self.generate_summary()
            self.results['timestamp'] = datetime.utcnow().isoformat()
            
        finally:
            await self.optimizer.stop()
        
        return self.results
    
    async def benchmark_cache_performance(self):
        """Benchmark cache performance"""
        print("Benchmarking cache performance...")
        
        cache = CacheManager(max_size=1000, default_ttl=300)
        
        # Test cache write performance
        write_times = []
        for i in range(1000):
            start_time = time.perf_counter()
            cache.set(f"key_{i}", f"value_{i}")
            end_time = time.perf_counter()
            write_times.append(end_time - start_time)
        
        # Test cache read performance
        read_times = []
        for i in range(1000):
            start_time = time.perf_counter()
            cache.get(f"key_{i}")
            end_time = time.perf_counter()
            read_times.append(end_time - start_time)
        
        # Test cache miss performance
        miss_times = []
        for i in range(100):
            start_time = time.perf_counter()
            cache.get(f"missing_key_{i}")
            end_time = time.perf_counter()
            miss_times.append(end_time - start_time)
        
        self.results['cache_performance'] = {
            'write_performance': {
                'avg_time_ms': statistics.mean(write_times) * 1000,
                'median_time_ms': statistics.median(write_times) * 1000,
                'max_time_ms': max(write_times) * 1000,
                'operations_per_second': 1000 / sum(write_times)
            },
            'read_performance': {
                'avg_time_ms': statistics.mean(read_times) * 1000,
                'median_time_ms': statistics.median(read_times) * 1000,
                'max_time_ms': max(read_times) * 1000,
                'operations_per_second': 1000 / sum(read_times)
            },
            'miss_performance': {
                'avg_time_ms': statistics.mean(miss_times) * 1000,
                'median_time_ms': statistics.median(miss_times) * 1000,
                'max_time_ms': max(miss_times) * 1000
            }
        }
    
    async def benchmark_parallel_processing(self):
        """Benchmark parallel processing performance"""
        print("Benchmarking parallel processing...")
        
        processor = ParallelProcessor(max_workers=4)
        
        def cpu_intensive_task(n: int) -> int:
            """CPU intensive task for benchmarking"""
            return sum(i * i for i in range(n))
        
        # Sequential processing benchmark
        start_time = time.perf_counter()
        sequential_results = []
        for i in range(10):
            result = cpu_intensive_task(10000)
            sequential_results.append(result)
        sequential_time = time.perf_counter() - start_time
        
        # Parallel processing benchmark
        start_time = time.perf_counter()
        tasks = [(cpu_intensive_task, (10000,), {}) for _ in range(10)]
        parallel_results = await processor.run_parallel_tasks(tasks)
        parallel_time = time.perf_counter() - start_time
        
        # Batch processing benchmark
        start_time = time.perf_counter()
        items = list(range(100))
        batch_results = await processor.run_batch_processing(
            items, lambda x: x * x, batch_size=10
        )
        batch_time = time.perf_counter() - start_time
        
        processor.shutdown()
        
        self.results['parallel_processing'] = {
            'sequential_time': sequential_time,
            'parallel_time': parallel_time,
            'batch_time': batch_time,
            'speedup_ratio': sequential_time / parallel_time if parallel_time > 0 else 0,
            'parallel_efficiency': (sequential_time / parallel_time) / 4 if parallel_time > 0 else 0  # 4 workers
        }
    
    async def benchmark_market_regime_detection(self):
        """Benchmark market regime detection"""
        print("Benchmarking market regime detection...")
        
        # Generate sample market data
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='1H')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.1)
        volumes = np.random.exponential(1000, len(dates))
        
        market_data = pd.DataFrame({
            'timestamp': dates,
            'close': prices,
            'volume': volumes,
            'high': prices * (1 + np.random.uniform(0, 0.02, len(dates))),
            'low': prices * (1 - np.random.uniform(0, 0.02, len(dates))),
            'open': prices + np.random.randn(len(dates)) * 0.05
        })
        
        detector = MarketRegimeDetector()
        
        # Benchmark regime detection
        detection_times = []
        for i in range(10):
            # Use different windows of data
            start_idx = i * 100
            end_idx = start_idx + 1000
            sample_data = market_data.iloc[start_idx:end_idx]
            
            start_time = time.perf_counter()
            regime = await detector.detect_regime(sample_data)
            end_time = time.perf_counter()
            
            detection_times.append(end_time - start_time)
        
        self.results['market_regime_detection'] = {
            'avg_detection_time_ms': statistics.mean(detection_times) * 1000,
            'median_detection_time_ms': statistics.median(detection_times) * 1000,
            'max_detection_time_ms': max(detection_times) * 1000,
            'detections_per_second': 1 / statistics.mean(detection_times)
        }
    
    async def benchmark_ml_engine(self):
        """Benchmark ML engine performance"""
        print("Benchmarking ML engine...")
        
        # Generate sample training data
        np.random.seed(42)
        n_samples = 1000
        n_features = 20
        
        X = np.random.randn(n_samples, n_features)
        y = (X[:, 0] + X[:, 1] * 0.5 + np.random.randn(n_samples) * 0.1 > 0).astype(int)
        
        feature_names = [f'feature_{i}' for i in range(n_features)]
        
        ml_engine = MLEngine()
        
        # Benchmark model training
        start_time = time.perf_counter()
        await ml_engine.train_models(X, y, feature_names)
        training_time = time.perf_counter() - start_time
        
        # Benchmark prediction
        prediction_times = []
        for i in range(100):
            sample = X[i:i+1]  # Single sample
            start_time = time.perf_counter()
            prediction = await ml_engine.predict(sample, feature_names)
            end_time = time.perf_counter()
            prediction_times.append(end_time - start_time)
        
        # Benchmark batch prediction
        start_time = time.perf_counter()
        batch_predictions = await ml_engine.predict(X[:100], feature_names)
        batch_prediction_time = time.perf_counter() - start_time
        
        self.results['ml_engine'] = {
            'training_time': training_time,
            'avg_prediction_time_ms': statistics.mean(prediction_times) * 1000,
            'median_prediction_time_ms': statistics.median(prediction_times) * 1000,
            'batch_prediction_time': batch_prediction_time,
            'predictions_per_second': 100 / batch_prediction_time
        }
    
    async def benchmark_strategy_engine(self):
        """Benchmark adaptive strategy engine"""
        print("Benchmarking strategy engine...")
        
        # Create sample market data
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='1H')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.1)
        
        market_data = pd.DataFrame({
            'timestamp': dates,
            'close': prices,
            'volume': np.random.exponential(1000, len(dates)),
            'high': prices * 1.01,
            'low': prices * 0.99,
            'open': prices + np.random.randn(len(dates)) * 0.05
        })
        
        strategy_engine = AdaptiveStrategyEngine()
        
        # Benchmark signal generation
        signal_times = []
        for i in range(50):
            start_idx = i * 10
            end_idx = start_idx + 100
            sample_data = market_data.iloc[start_idx:end_idx]
            
            start_time = time.perf_counter()
            signal = await strategy_engine.generate_signal("BTCUSD", sample_data)
            end_time = time.perf_counter()
            
            signal_times.append(end_time - start_time)
        
        self.results['strategy_engine'] = {
            'avg_signal_time_ms': statistics.mean(signal_times) * 1000,
            'median_signal_time_ms': statistics.median(signal_times) * 1000,
            'max_signal_time_ms': max(signal_times) * 1000,
            'signals_per_second': 1 / statistics.mean(signal_times)
        }
    
    async def benchmark_parameter_optimization(self):
        """Benchmark parameter optimization"""
        print("Benchmarking parameter optimization...")
        
        optimizer = ParameterOptimizer()
        
        # Define a simple objective function
        def objective_function(params: Dict[str, float]) -> float:
            x = params.get('x', 0)
            y = params.get('y', 0)
            return -(x**2 + y**2)  # Negative because we want to maximize
        
        parameter_bounds = {
            'x': (-10.0, 10.0),
            'y': (-10.0, 10.0)
        }
        
        # Benchmark optimization
        start_time = time.perf_counter()
        result = await optimizer.optimize_parameters(
            objective_function,
            parameter_bounds,
            n_calls=50
        )
        optimization_time = time.perf_counter() - start_time
        
        self.results['parameter_optimization'] = {
            'optimization_time': optimization_time,
            'evaluations_per_second': 50 / optimization_time,
            'best_score': result.fun if hasattr(result, 'fun') else None
        }
    
    async def benchmark_memory_usage(self):
        """Benchmark memory usage"""
        print("Benchmarking memory usage...")
        
        import psutil
        process = psutil.Process()
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / (1024 ** 2)  # MB
        
        # Create large data structures
        large_data = []
        memory_measurements = [baseline_memory]
        
        for i in range(10):
            # Add 1MB of data
            data_chunk = [0] * (1024 * 256)  # Approximately 1MB
            large_data.append(data_chunk)
            
            current_memory = process.memory_info().rss / (1024 ** 2)
            memory_measurements.append(current_memory)
        
        # Clean up
        del large_data
        import gc
        gc.collect()
        
        final_memory = process.memory_info().rss / (1024 ** 2)
        
        self.results['memory_usage'] = {
            'baseline_memory_mb': baseline_memory,
            'peak_memory_mb': max(memory_measurements),
            'final_memory_mb': final_memory,
            'memory_growth_mb': max(memory_measurements) - baseline_memory,
            'memory_recovered_mb': max(memory_measurements) - final_memory
        }
    
    async def benchmark_cpu_usage(self):
        """Benchmark CPU usage patterns"""
        print("Benchmarking CPU usage...")
        
        import psutil
        
        # CPU intensive task
        def cpu_task():
            return sum(i * i for i in range(100000))
        
        # Measure CPU usage during intensive task
        cpu_measurements = []
        
        for _ in range(10):
            start_cpu = psutil.cpu_percent(interval=None)
            
            # Run CPU intensive task
            start_time = time.perf_counter()
            result = cpu_task()
            end_time = time.perf_counter()
            
            end_cpu = psutil.cpu_percent(interval=0.1)
            cpu_measurements.append(end_cpu)
        
        self.results['cpu_usage'] = {
            'avg_cpu_percent': statistics.mean(cpu_measurements),
            'max_cpu_percent': max(cpu_measurements),
            'task_execution_time': end_time - start_time
        }
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate benchmark summary"""
        summary = {
            'overall_performance': 'good',  # Will be determined by thresholds
            'bottlenecks': [],
            'recommendations': []
        }
        
        # Analyze cache performance
        cache_perf = self.results.get('cache_performance', {})
        if cache_perf.get('read_performance', {}).get('avg_time_ms', 0) > 1.0:
            summary['bottlenecks'].append('Slow cache read performance')
            summary['recommendations'].append('Consider optimizing cache implementation')
        
        # Analyze parallel processing
        parallel_perf = self.results.get('parallel_processing', {})
        if parallel_perf.get('speedup_ratio', 0) < 2.0:
            summary['bottlenecks'].append('Poor parallel processing speedup')
            summary['recommendations'].append('Review parallel processing implementation')
        
        # Analyze ML engine
        ml_perf = self.results.get('ml_engine', {})
        if ml_perf.get('avg_prediction_time_ms', 0) > 10.0:
            summary['bottlenecks'].append('Slow ML predictions')
            summary['recommendations'].append('Consider model optimization or caching')
        
        # Analyze memory usage
        memory_perf = self.results.get('memory_usage', {})
        if memory_perf.get('memory_growth_mb', 0) > 100:
            summary['bottlenecks'].append('High memory usage')
            summary['recommendations'].append('Review memory management and garbage collection')
        
        # Overall performance assessment
        if len(summary['bottlenecks']) == 0:
            summary['overall_performance'] = 'excellent'
        elif len(summary['bottlenecks']) <= 2:
            summary['overall_performance'] = 'good'
        else:
            summary['overall_performance'] = 'needs_improvement'
        
        return summary
    
    def save_results(self, filename: str = None):
        """Save benchmark results to file"""
        if filename is None:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f'benchmark_results_{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"Benchmark results saved to {filename}")
    
    def print_summary(self):
        """Print benchmark summary"""
        print("\nBenchmark Summary")
        print("=" * 50)
        
        summary = self.results.get('summary', {})
        print(f"Overall Performance: {summary.get('overall_performance', 'unknown').upper()}")
        
        if summary.get('bottlenecks'):
            print("\nBottlenecks Identified:")
            for bottleneck in summary['bottlenecks']:
                print(f"  - {bottleneck}")
        
        if summary.get('recommendations'):
            print("\nRecommendations:")
            for recommendation in summary['recommendations']:
                print(f"  - {recommendation}")
        
        # Print key metrics
        print("\nKey Performance Metrics:")
        
        cache_perf = self.results.get('cache_performance', {})
        if cache_perf:
            read_ops_per_sec = cache_perf.get('read_performance', {}).get('operations_per_second', 0)
            print(f"  Cache Read Operations/sec: {read_ops_per_sec:,.0f}")
        
        parallel_perf = self.results.get('parallel_processing', {})
        if parallel_perf:
            speedup = parallel_perf.get('speedup_ratio', 0)
            print(f"  Parallel Processing Speedup: {speedup:.2f}x")
        
        ml_perf = self.results.get('ml_engine', {})
        if ml_perf:
            pred_per_sec = ml_perf.get('predictions_per_second', 0)
            print(f"  ML Predictions/sec: {pred_per_sec:.0f}")
        
        strategy_perf = self.results.get('strategy_engine', {})
        if strategy_perf:
            signals_per_sec = strategy_perf.get('signals_per_second', 0)
            print(f"  Strategy Signals/sec: {signals_per_sec:.1f}")


async def main():
    """Main benchmark execution"""
    benchmark = PerformanceBenchmark()
    
    try:
        results = await benchmark.run_all_benchmarks()
        benchmark.print_summary()
        benchmark.save_results()
        
        return 0
        
    except Exception as e:
        print(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)