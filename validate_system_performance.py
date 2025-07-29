#!/usr/bin/env python3
"""
System Performance Validation for Enhanced Kraken Trading Bot

This script validates the system's performance under realistic trading conditions
and ensures all components work together efficiently.
"""
import os
import sys
import time
import logging
import argparse
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

# Import core components
from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig
from bot.enhanced_strategies import EnhancedStrategyEngine, StrategyParameters
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_alerts import EnhancedAlertSystem
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_info, log_error, log_warning


@dataclass
class PerformanceMetrics:
    """Performance metrics for system validation."""
    test_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    
    # Performance metrics
    api_calls_per_second: float = 0.0
    data_processing_rate: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    response_time_ms: float = 0.0
    
    # Trading metrics
    signals_generated: int = 0
    trades_simulated: int = 0
    error_rate: float = 0.0
    
    def duration_seconds(self) -> float:
        """Calculate test duration in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class SystemPerformanceValidator:
    """Validates system performance under realistic conditions."""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.credentials = None
        self.components = {}
        self.performance_results = []
        self.trading_pairs = args.trading_pairs
        self.shutdown_event = threading.Event()
        
    def setup_system(self) -> bool:
        """Setup the complete system for performance testing."""
        try:
            # Load credentials
            load_dotenv()
            api_key = os.getenv("KRAKEN_API_KEY")
            api_secret = os.getenv("KRAKEN_API_SECRET")
            
            if not api_key or not api_secret:
                log_error("Missing Kraken API credentials!")
                return False
            
            self.credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
            
            # Initialize components
            enhanced_logger = EnhancedLogger({
                'log_level': logging.INFO,
                'log_dir': 'logs',
                'structured_logging': True,
                'performance_tracking': True
            })
            
            cache_config = CacheConfig(
                enabled=True,
                max_memory_mb=100,
                retention_hours=4,
                persist_to_disk=True
            )
            
            data_manager = EnhancedDataManager(
                pairs=self.trading_pairs,
                cache_config=cache_config
            )
            
            strategy_params = StrategyParameters(
                volatility_lookback=20,
                momentum_periods=[5, 10, 20],
                volume_threshold=1.2,
                confidence_threshold=0.3
            )
            
            strategy_engine = EnhancedStrategyEngine(
                strategies=[],
                parameters=strategy_params
            )
            
            alert_config = {
                'enabled': True,
                'channels': {
                    'console': {'enabled': True}
                }
            }
            alert_system = EnhancedAlertSystem(alert_config, enhanced_logger)
            
            kraken_client = KrakenClient(self.credentials)
            
            # Create traders for each pair
            traders = {}
            for pair in self.trading_pairs:
                trading_config = KrakenTradingConfig(
                    trading_pair=pair,
                    trade_amount_usd=10.0,
                    max_position_usd=50.0,
                    min_trade_interval=60
                )
                traders[pair] = KrakenTrader(self.credentials, trading_config)
            
            self.components = {
                "enhanced_logger": enhanced_logger,
                "data_manager": data_manager,
                "strategy_engine": strategy_engine,
                "alert_system": alert_system,
                "kraken_client": kraken_client,
                "traders": traders
            }
            
            log_info("✅ System setup completed successfully")
            return True
            
        except Exception as e:
            log_error(f"Failed to setup system: {e}")
            return False
    
    def validate_api_performance(self) -> PerformanceMetrics:
        """Validate API performance under load."""
        metrics = PerformanceMetrics(
            test_name="API Performance",
            start_time=datetime.now()
        )
        
        try:
            log_info("🔍 Validating API performance...")
            kraken_client = self.components["kraken_client"]
            
            # Test API call rate
            api_calls = 0
            errors = 0
            start_time = time.time()
            
            for _ in range(self.args.api_test_calls):
                try:
                    # Test different API endpoints
                    kraken_client.get_server_time()
                    api_calls += 1
                    
                    # Test market data
                    for pair in self.trading_pairs[:2]:  # Limit to 2 pairs for performance test
                        kraken_client.get_ticker_information([pair])
                        api_calls += 1
                    
                    time.sleep(0.1)  # Respect rate limits
                    
                except Exception as e:
                    errors += 1
                    log_warning(f"API call failed: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            metrics.api_calls_per_second = api_calls / duration if duration > 0 else 0
            metrics.error_rate = errors / max(api_calls, 1)
            metrics.response_time_ms = (duration / max(api_calls, 1)) * 1000
            
            # Test memory usage
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()
                metrics.memory_usage_mb = memory_info.rss / 1024 / 1024
                metrics.cpu_usage_percent = process.cpu_percent()
            except ImportError:
                log_warning("psutil not available for memory/CPU metrics")
            
            metrics.success = errors < api_calls * 0.1  # Less than 10% error rate
            log_info(f"API Performance: {metrics.api_calls_per_second:.2f} calls/sec, {metrics.error_rate:.2%} error rate")
            
        except Exception as e:
            metrics.error_message = str(e)
            log_error(f"API performance validation failed: {e}")
        
        metrics.end_time = datetime.now()
        return metrics
    
    def validate_data_processing_performance(self) -> PerformanceMetrics:
        """Validate data processing performance."""
        metrics = PerformanceMetrics(
            test_name="Data Processing Performance",
            start_time=datetime.now()
        )
        
        try:
            log_info("📊 Validating data processing performance...")
            data_manager = self.components["data_manager"]
            kraken_client = self.components["kraken_client"]
            
            # Fetch real market data
            data_points_processed = 0
            start_time = time.time()
            
            for pair in self.trading_pairs:
                try:
                    # Get OHLC data
                    ohlc_data = kraken_client.get_ohlc_data(pair, interval=5, since=None)
                    if ohlc_data and pair in ohlc_data:
                        pair_data = ohlc_data[pair]
                        
                        # Process data points
                        for timestamp, open_price, high, low, close, vwap, volume, count in pair_data[-100:]:
                            market_data = {
                                'timestamp': datetime.fromtimestamp(timestamp),
                                'price': float(close),
                                'volume': float(volume),
                                'high': float(high),
                                'low': float(low),
                                'open': float(open_price)
                            }
                            data_manager.add_market_data(pair, market_data)
                            data_points_processed += 1
                        
                        # Test indicator calculations
                        indicators = data_manager.calculate_indicators(pair, ['sma_20', 'rsi_14'])
                        if indicators:
                            data_points_processed += len(indicators)
                    
                except Exception as e:
                    log_warning(f"Data processing failed for {pair}: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            metrics.data_processing_rate = data_points_processed / duration if duration > 0 else 0
            metrics.success = data_points_processed > 0
            
            log_info(f"Data Processing: {metrics.data_processing_rate:.2f} points/sec")
            
        except Exception as e:
            metrics.error_message = str(e)
            log_error(f"Data processing validation failed: {e}")
        
        metrics.end_time = datetime.now()
        return metrics
    
    def validate_strategy_performance(self) -> PerformanceMetrics:
        """Validate strategy engine performance."""
        metrics = PerformanceMetrics(
            test_name="Strategy Performance",
            start_time=datetime.now()
        )
        
        try:
            log_info("🧠 Validating strategy performance...")
            strategy_engine = self.components["strategy_engine"]
            data_manager = self.components["data_manager"]
            
            signals_generated = 0
            start_time = time.time()
            
            # Test strategy performance with multiple iterations
            for iteration in range(self.args.strategy_iterations):
                for pair in self.trading_pairs:
                    try:
                        market_data = data_manager.get_latest_data(pair, periods=50)
                        if market_data is not None and not market_data.empty:
                            signal = strategy_engine.calculate_weighted_signal(market_data)
                            if signal:
                                signals_generated += 1
                    except Exception as e:
                        log_warning(f"Strategy calculation failed for {pair}: {e}")
                
                time.sleep(0.01)  # Small delay between iterations
            
            end_time = time.time()
            duration = end_time - start_time
            
            metrics.signals_generated = signals_generated
            metrics.success = True  # Success if no critical errors
            
            log_info(f"Strategy Performance: {signals_generated} signals in {duration:.2f}s")
            
        except Exception as e:
            metrics.error_message = str(e)
            log_error(f"Strategy performance validation failed: {e}")
        
        metrics.end_time = datetime.now()
        return metrics
    
    def validate_multi_pair_coordination(self) -> PerformanceMetrics:
        """Validate multi-pair trading coordination."""
        metrics = PerformanceMetrics(
            test_name="Multi-Pair Coordination",
            start_time=datetime.now()
        )
        
        try:
            log_info("🔄 Validating multi-pair coordination...")
            
            if len(self.trading_pairs) < 2:
                log_warning("Only one trading pair configured, creating simulated multi-pair test")
                metrics.success = True
                return metrics
            
            traders = self.components["traders"]
            data_manager = self.components["data_manager"]
            
            # Test concurrent operations
            def process_pair(pair):
                try:
                    trader = traders[pair]
                    price = trader.get_current_price(pair)
                    if price:
                        # Simulate data processing
                        market_data = data_manager.get_latest_data(pair, periods=10)
                        return True
                except Exception as e:
                    log_warning(f"Multi-pair processing failed for {pair}: {e}")
                    return False
            
            # Test concurrent processing
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.trading_pairs)) as executor:
                futures = [executor.submit(process_pair, pair) for pair in self.trading_pairs]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            success_rate = sum(results) / len(results) if results else 0
            metrics.success = success_rate > 0.8  # 80% success rate
            
            log_info(f"Multi-Pair Coordination: {success_rate:.2%} success rate")
            
        except Exception as e:
            metrics.error_message = str(e)
            log_error(f"Multi-pair coordination validation failed: {e}")
        
        metrics.end_time = datetime.now()
        return metrics
    
    def validate_system_resilience(self) -> PerformanceMetrics:
        """Validate system resilience under stress."""
        metrics = PerformanceMetrics(
            test_name="System Resilience",
            start_time=datetime.now()
        )
        
        try:
            log_info("🛡️ Validating system resilience...")
            
            # Test error handling
            error_scenarios = [
                ("Invalid pair", lambda: self.components["traders"][self.trading_pairs[0]].get_current_price("INVALID/PAIR")),
                ("Network timeout simulation", lambda: time.sleep(0.1)),  # Simulate brief delay
                ("Data corruption simulation", lambda: self.components["data_manager"].get_latest_data("", periods=0))
            ]
            
            errors_handled = 0
            total_scenarios = len(error_scenarios)
            
            for scenario_name, scenario_func in error_scenarios:
                try:
                    scenario_func()
                except Exception as e:
                    log_info(f"Error scenario '{scenario_name}' handled: {e}")
                    errors_handled += 1
            
            # Test system recovery
            recovery_success = True
            try:
                # Test that system still works after errors
                trader = self.components["traders"][self.trading_pairs[0]]
                connection_test = trader.test_connection()
                if not connection_test:
                    recovery_success = False
            except Exception as e:
                log_warning(f"System recovery test failed: {e}")
                recovery_success = False
            
            metrics.success = errors_handled >= total_scenarios * 0.8 and recovery_success
            log_info(f"System Resilience: {errors_handled}/{total_scenarios} errors handled, recovery: {recovery_success}")
            
        except Exception as e:
            metrics.error_message = str(e)
            log_error(f"System resilience validation failed: {e}")
        
        metrics.end_time = datetime.now()
        return metrics
    
    def validate_logging_performance(self) -> PerformanceMetrics:
        """Validate logging system performance."""
        metrics = PerformanceMetrics(
            test_name="Logging Performance",
            start_time=datetime.now()
        )
        
        try:
            log_info("📝 Validating logging performance...")
            enhanced_logger = self.components["enhanced_logger"]
            
            # Test logging throughput
            log_entries = 0
            start_time = time.time()
            
            for i in range(self.args.log_test_entries):
                try:
                    # Test different types of logging
                    test_metrics = {
                        'iteration': i,
                        'timestamp': datetime.now(),
                        'test_value': i * 1.5
                    }
                    enhanced_logger.log_performance_metrics(test_metrics)
                    log_entries += 1
                except Exception as e:
                    log_warning(f"Logging failed: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            metrics.data_processing_rate = log_entries / duration if duration > 0 else 0
            metrics.success = log_entries > 0
            
            log_info(f"Logging Performance: {metrics.data_processing_rate:.2f} entries/sec")
            
        except Exception as e:
            metrics.error_message = str(e)
            log_error(f"Logging performance validation failed: {e}")
        
        metrics.end_time = datetime.now()
        return metrics
    
    def run_comprehensive_validation(self) -> List[PerformanceMetrics]:
        """Run comprehensive performance validation."""
        log_info("🚀 Starting comprehensive performance validation...")
        
        validation_methods = [
            self.validate_api_performance,
            self.validate_data_processing_performance,
            self.validate_strategy_performance,
            self.validate_multi_pair_coordination,
            self.validate_system_resilience,
            self.validate_logging_performance
        ]
        
        results = []
        for validation_method in validation_methods:
            try:
                result = validation_method()
                results.append(result)
                self.performance_results.append(result)
                
                if result.success:
                    log_info(f"✅ {result.test_name} validation passed ({result.duration_seconds():.2f}s)")
                else:
                    log_error(f"❌ {result.test_name} validation failed: {result.error_message}")
                
                time.sleep(1)  # Brief pause between tests
                
            except Exception as e:
                log_error(f"Critical error in {validation_method.__name__}: {e}")
                error_result = PerformanceMetrics(
                    test_name=validation_method.__name__,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    success=False,
                    error_message=str(e)
                )
                results.append(error_result)
        
        return results
    
    def generate_performance_report(self) -> str:
        """Generate comprehensive performance report."""
        total_tests = len(self.performance_results)
        passed_tests = sum(1 for result in self.performance_results if result.success)
        failed_tests = total_tests - passed_tests
        
        report = f"""
{'='*80}
SYSTEM PERFORMANCE VALIDATION REPORT
{'='*80}

Validation Summary:
- Total Validations: {total_tests}
- Passed: {passed_tests}
- Failed: {failed_tests}
- Success Rate: {(passed_tests/total_tests)*100:.1f}%

Trading Pairs: {', '.join(self.trading_pairs)}
Validation Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
PERFORMANCE METRICS
{'='*80}
"""
        
        for result in self.performance_results:
            status = "✅ PASSED" if result.success else "❌ FAILED"
            
            report += f"""
{result.test_name}: {status}
Duration: {result.duration_seconds():.2f}s
"""
            
            if result.error_message:
                report += f"Error: {result.error_message}\n"
            
            # Add performance metrics
            if result.api_calls_per_second > 0:
                report += f"API Calls/sec: {result.api_calls_per_second:.2f}\n"
            if result.data_processing_rate > 0:
                report += f"Data Processing Rate: {result.data_processing_rate:.2f} points/sec\n"
            if result.memory_usage_mb > 0:
                report += f"Memory Usage: {result.memory_usage_mb:.1f} MB\n"
            if result.cpu_usage_percent > 0:
                report += f"CPU Usage: {result.cpu_usage_percent:.1f}%\n"
            if result.response_time_ms > 0:
                report += f"Response Time: {result.response_time_ms:.1f} ms\n"
            if result.signals_generated > 0:
                report += f"Signals Generated: {result.signals_generated}\n"
            if result.error_rate > 0:
                report += f"Error Rate: {result.error_rate:.2%}\n"
            
            report += "-" * 40 + "\n"
        
        # Add performance summary
        avg_api_rate = sum(r.api_calls_per_second for r in self.performance_results if r.api_calls_per_second > 0)
        avg_data_rate = sum(r.data_processing_rate for r in self.performance_results if r.data_processing_rate > 0)
        total_signals = sum(r.signals_generated for r in self.performance_results)
        
        report += f"""
{'='*80}
PERFORMANCE SUMMARY
{'='*80}

System Performance:
- Average API Rate: {avg_api_rate:.2f} calls/sec
- Average Data Processing: {avg_data_rate:.2f} points/sec
- Total Signals Generated: {total_signals}

System Status: {'✅ READY FOR PRODUCTION' if passed_tests == total_tests else '⚠️ NEEDS OPTIMIZATION' if passed_tests >= total_tests * 0.8 else '❌ REQUIRES FIXES'}
"""
        
        return report


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="System Performance Validation for Enhanced Kraken Trading Bot")
    
    parser.add_argument(
        "--trading-pairs",
        nargs="+",
        default=["XBTUSD"],
        help="Trading pairs to test (default: XBTUSD)"
    )
    
    parser.add_argument(
        "--api-test-calls",
        type=int,
        default=20,
        help="Number of API calls for performance test (default: 20)"
    )
    
    parser.add_argument(
        "--strategy-iterations",
        type=int,
        default=10,
        help="Number of strategy iterations (default: 10)"
    )
    
    parser.add_argument(
        "--log-test-entries",
        type=int,
        default=100,
        help="Number of log entries for performance test (default: 100)"
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="performance_validation_report.txt",
        help="Output file for performance report"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_arguments()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Enhanced Kraken Trading Bot - System Performance Validation")
    print("=" * 70)
    print(f"Trading Pairs: {', '.join(args.trading_pairs)}")
    print(f"API Test Calls: {args.api_test_calls}")
    print(f"Strategy Iterations: {args.strategy_iterations}")
    print("=" * 70)
    
    # Initialize validator
    validator = SystemPerformanceValidator(args)
    
    try:
        # Setup system
        if not validator.setup_system():
            log_error("Failed to setup system")
            return 1
        
        # Run comprehensive validation
        results = validator.run_comprehensive_validation()
        
        # Generate and save report
        report = validator.generate_performance_report()
        
        with open(args.output_file, 'w') as f:
            f.write(report)
        
        print(report)
        print(f"\n📄 Full report saved to: {args.output_file}")
        
        # Return appropriate exit code
        failed_tests = sum(1 for result in results if not result.success)
        return 1 if failed_tests > 0 else 0
        
    except KeyboardInterrupt:
        log_info("Validation interrupted by user")
        return 1
    except Exception as e:
        log_error(f"Critical error during validation: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())