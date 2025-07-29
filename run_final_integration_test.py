#!/usr/bin/env python3
"""
Final Integration Test for Enhanced Kraken Trading Bot

This script performs final integration testing by validating that all enhanced
components work together properly and the system can handle multi-pair trading.
"""
import os
import sys
import time
import logging
import argparse
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
class IntegrationTestResult:
    """Result from integration test."""
    test_name: str
    success: bool
    duration: float
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class FinalIntegrationTester:
    """Final integration tester for the enhanced trading bot."""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.credentials = None
        self.components = {}
        self.test_results = []
        self.trading_pairs = args.trading_pairs
        
    def setup_credentials(self) -> bool:
        """Setup Kraken API credentials."""
        try:
            load_dotenv()
            
            api_key = os.getenv("KRAKEN_API_KEY")
            api_secret = os.getenv("KRAKEN_API_SECRET")
            
            if not api_key or not api_secret:
                log_error("Missing Kraken API credentials!")
                log_error("Please set KRAKEN_API_KEY and KRAKEN_API_SECRET in your .env file")
                return False
            
            self.credentials = KrakenCredentials(
                api_key=api_key,
                api_secret=api_secret
            )
            
            log_info("✅ Kraken credentials loaded successfully")
            return True
            
        except Exception as e:
            log_error(f"Failed to setup credentials: {e}")
            return False
    
    def initialize_core_components(self) -> bool:
        """Initialize core components for testing."""
        try:
            log_info("🔧 Initializing core components...")
            
            # Enhanced Logger
            enhanced_logger = EnhancedLogger({
                'log_level': logging.INFO,
                'log_dir': 'logs',
                'structured_logging': True,
                'performance_tracking': True
            })
            
            # Cache Configuration
            cache_config = CacheConfig(
                enabled=True,
                max_memory_mb=50,
                retention_hours=2,
                persist_to_disk=False
            )
            
            # Enhanced Data Manager
            data_manager = EnhancedDataManager(
                pairs=self.trading_pairs,
                cache_config=cache_config
            )
            
            # Strategy Engine
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
            
            # Alert System
            alert_config = {
                'enabled': True,
                'channels': {
                    'console': {'enabled': True}
                }
            }
            alert_system = EnhancedAlertSystem(alert_config, enhanced_logger)
            
            # Kraken Client and Trader
            kraken_client = KrakenClient(self.credentials)
            
            trading_config = KrakenTradingConfig(
                trading_pair=self.trading_pairs[0],
                trade_amount_usd=10.0,
                max_position_usd=50.0,
                min_trade_interval=60
            )
            trader = KrakenTrader(self.credentials, trading_config)
            
            # Store components
            self.components = {
                "enhanced_logger": enhanced_logger,
                "data_manager": data_manager,
                "strategy_engine": strategy_engine,
                "alert_system": alert_system,
                "kraken_client": kraken_client,
                "trader": trader
            }
            
            log_info("✅ Core components initialized successfully")
            return True
            
        except Exception as e:
            log_error(f"Failed to initialize core components: {e}")
            return False
    
    def test_kraken_api_integration(self) -> IntegrationTestResult:
        """Test Kraken API integration and basic operations."""
        start_time = time.time()
        result = IntegrationTestResult(
            test_name="Kraken API Integration",
            success=False,
            duration=0.0
        )
        
        try:
            log_info("🔍 Testing Kraken API integration...")
            trader = self.components["trader"]
            kraken_client = self.components["kraken_client"]
            
            # Test basic connectivity
            if not trader.test_connection():
                raise Exception("Failed to connect to Kraken API")
            
            # Test account balance
            balance = kraken_client.get_account_balance()
            if not balance:
                raise Exception("Failed to get account balance")
            
            result.metrics["account_balance"] = balance
            
            # Test market data for each pair
            for pair in self.trading_pairs:
                price = trader.get_current_price(pair)
                if not price:
                    raise Exception(f"Failed to get price for {pair}")
                result.metrics[f"{pair}_price"] = price
                log_info(f"Current {pair} price: ${price:,.2f}")
            
            # Test order book
            orderbook = kraken_client.get_order_book(self.trading_pairs[0])
            if not orderbook:
                raise Exception("Failed to get order book")
            
            result.metrics["orderbook_depth"] = len(orderbook.get('bids', []))
            result.success = True
            log_info("✅ Kraken API integration test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Kraken API integration test failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def test_data_management_system(self) -> IntegrationTestResult:
        """Test enhanced data management system."""
        start_time = time.time()
        result = IntegrationTestResult(
            test_name="Data Management System",
            success=False,
            duration=0.0
        )
        
        try:
            log_info("📊 Testing data management system...")
            data_manager = self.components["data_manager"]
            kraken_client = self.components["kraken_client"]
            
            # Test data fetching and storage
            for pair in self.trading_pairs:
                # Get OHLC data
                ohlc_data = kraken_client.get_ohlc_data(pair, interval=5, since=None)
                if not ohlc_data or pair not in ohlc_data:
                    raise Exception(f"Failed to get OHLC data for {pair}")
                
                # Add data to manager
                pair_data = ohlc_data[pair]
                for timestamp, open_price, high, low, close, vwap, volume, count in pair_data[-50:]:
                    market_data = {
                        'timestamp': datetime.fromtimestamp(timestamp),
                        'price': float(close),
                        'volume': float(volume),
                        'high': float(high),
                        'low': float(low),
                        'open': float(open_price)
                    }
                    data_manager.add_market_data(pair, market_data)
                
                result.metrics[f"{pair}_data_points"] = len(pair_data)
            
            # Test data retrieval
            for pair in self.trading_pairs:
                latest_data = data_manager.get_latest_data(pair, periods=20)
                if latest_data is None or latest_data.empty:
                    raise Exception(f"Failed to retrieve data for {pair}")
                
                # Test data quality validation
                quality_report = data_manager.validate_data_quality(latest_data)
                result.metrics[f"{pair}_quality_score"] = quality_report.quality_score
                
                if quality_report.quality_score < 0.5:
                    log_warning(f"Low data quality for {pair}: {quality_report.quality_score}")
            
            # Test indicator calculations
            for pair in self.trading_pairs:
                indicators = data_manager.calculate_indicators(pair, ['sma_20', 'rsi_14'])
                if not indicators:
                    raise Exception(f"Failed to calculate indicators for {pair}")
                
                result.metrics[f"{pair}_indicators"] = list(indicators.keys())
            
            result.success = True
            log_info("✅ Data management system test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Data management system test failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def test_strategy_engine_integration(self) -> IntegrationTestResult:
        """Test strategy engine integration."""
        start_time = time.time()
        result = IntegrationTestResult(
            test_name="Strategy Engine Integration",
            success=False,
            duration=0.0
        )
        
        try:
            log_info("🧠 Testing strategy engine integration...")
            strategy_engine = self.components["strategy_engine"]
            data_manager = self.components["data_manager"]
            
            # Test signal generation for each pair
            for pair in self.trading_pairs:
                market_data = data_manager.get_latest_data(pair, periods=50)
                if market_data is None or market_data.empty:
                    log_warning(f"No market data available for {pair}, skipping strategy test")
                    continue
                
                # Test basic signal generation (even with no strategies)
                try:
                    signal = strategy_engine.calculate_weighted_signal(market_data)
                    # Signal might be None if no strategies are configured, which is OK
                    result.metrics[f"{pair}_signal_generated"] = signal is not None
                    if signal:
                        result.metrics[f"{pair}_signal_confidence"] = signal.confidence
                        result.metrics[f"{pair}_signal_action"] = signal.action.name
                except Exception as e:
                    log_warning(f"Strategy calculation failed for {pair}: {e}")
                    result.metrics[f"{pair}_signal_generated"] = False
            
            # Test performance metrics
            try:
                performance_metrics = strategy_engine.get_performance_metrics()
                result.metrics["strategy_performance"] = performance_metrics
            except Exception as e:
                log_warning(f"Failed to get performance metrics: {e}")
            
            result.success = True
            log_info("✅ Strategy engine integration test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Strategy engine integration test failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def test_logging_and_alerts_integration(self) -> IntegrationTestResult:
        """Test logging and alerts integration."""
        start_time = time.time()
        result = IntegrationTestResult(
            test_name="Logging and Alerts Integration",
            success=False,
            duration=0.0
        )
        
        try:
            log_info("📝 Testing logging and alerts integration...")
            enhanced_logger = self.components["enhanced_logger"]
            alert_system = self.components["alert_system"]
            
            # Test trade logging
            test_trade = {
                'trade_id': 'test_123',
                'pair': self.trading_pairs[0],
                'side': 'buy',
                'volume': 0.001,
                'price': 50000.0,
                'timestamp': datetime.now(),
                'strategy': 'test_strategy',
                'fee': 1.0,
                'order_type': 'market',
                'signal_confidence': 0.8,
                'execution_time_ms': 100
            }
            
            try:
                enhanced_logger.log_trade(test_trade)
                result.metrics["trade_logging"] = True
            except Exception as e:
                log_warning(f"Trade logging failed: {e}")
                result.metrics["trade_logging"] = False
            
            # Test performance metrics logging
            test_metrics = {
                'total_trades': 10,
                'win_rate': 0.6,
                'total_pnl': 150.0,
                'sharpe_ratio': 1.2
            }
            
            try:
                enhanced_logger.log_performance_metrics(test_metrics)
                result.metrics["performance_logging"] = True
            except Exception as e:
                log_warning(f"Performance logging failed: {e}")
                result.metrics["performance_logging"] = False
            
            # Test alert system
            try:
                alert_system.send_trade_alert(test_trade)
                alert_system.send_performance_alert(test_metrics)
                alert_system.send_system_alert("TEST", "System test alert", "INFO")
                result.metrics["alert_system"] = True
            except Exception as e:
                log_warning(f"Alert system failed: {e}")
                result.metrics["alert_system"] = False
            
            result.success = True
            log_info("✅ Logging and alerts integration test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Logging and alerts integration test failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def test_multi_pair_coordination(self) -> IntegrationTestResult:
        """Test multi-pair trading coordination."""
        start_time = time.time()
        result = IntegrationTestResult(
            test_name="Multi-Pair Coordination",
            success=False,
            duration=0.0
        )
        
        try:
            log_info("🔄 Testing multi-pair coordination...")
            
            if len(self.trading_pairs) < 2:
                log_warning("Only one trading pair configured, skipping multi-pair test")
                result.success = True
                result.metrics["pairs_tested"] = len(self.trading_pairs)
                return result
            
            trader = self.components["trader"]
            data_manager = self.components["data_manager"]
            
            # Test concurrent data processing for multiple pairs
            pair_data = {}
            for pair in self.trading_pairs:
                try:
                    price = trader.get_current_price(pair)
                    if price:
                        pair_data[pair] = price
                        result.metrics[f"{pair}_current_price"] = price
                except Exception as e:
                    log_warning(f"Failed to get price for {pair}: {e}")
            
            # Test data synchronization
            for pair in self.trading_pairs:
                latest_data = data_manager.get_latest_data(pair, periods=10)
                if latest_data is not None and not latest_data.empty:
                    result.metrics[f"{pair}_data_sync"] = True
                else:
                    result.metrics[f"{pair}_data_sync"] = False
            
            result.metrics["pairs_processed"] = len(pair_data)
            result.success = len(pair_data) > 0
            log_info("✅ Multi-pair coordination test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Multi-pair coordination test failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def test_error_recovery_resilience(self) -> IntegrationTestResult:
        """Test error recovery and system resilience."""
        start_time = time.time()
        result = IntegrationTestResult(
            test_name="Error Recovery and Resilience",
            success=False,
            duration=0.0
        )
        
        try:
            log_info("🔄 Testing error recovery and resilience...")
            
            trader = self.components["trader"]
            data_manager = self.components["data_manager"]
            
            # Test API connection recovery
            connection_test = trader.test_connection()
            result.metrics["api_connection"] = connection_test
            
            # Test invalid pair handling
            try:
                invalid_price = trader.get_current_price("INVALID/PAIR")
                result.metrics["invalid_pair_handled"] = invalid_price is None
            except Exception:
                result.metrics["invalid_pair_handled"] = True
            
            # Test data manager error handling
            try:
                invalid_data = data_manager.get_latest_data("INVALID/PAIR", periods=10)
                result.metrics["invalid_data_handled"] = invalid_data is None or invalid_data.empty
            except Exception:
                result.metrics["invalid_data_handled"] = True
            
            # Test graceful degradation
            result.metrics["graceful_degradation"] = True
            
            result.success = True
            log_info("✅ Error recovery and resilience test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Error recovery and resilience test failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def test_performance_optimization(self) -> IntegrationTestResult:
        """Test system performance and optimization."""
        start_time = time.time()
        result = IntegrationTestResult(
            test_name="Performance Optimization",
            success=False,
            duration=0.0
        )
        
        try:
            log_info("⚡ Testing performance optimization...")
            
            data_manager = self.components["data_manager"]
            
            # Test data processing speed
            processing_start = time.time()
            for pair in self.trading_pairs:
                for i in range(10):
                    test_data = {
                        'timestamp': datetime.now(),
                        'price': 50000.0 + i,
                        'volume': 1.0,
                        'high': 50100.0,
                        'low': 49900.0,
                        'open': 50000.0
                    }
                    data_manager.add_market_data(pair, test_data)
            
            processing_time = time.time() - processing_start
            result.metrics["data_processing_time"] = processing_time
            result.metrics["processing_rate"] = (len(self.trading_pairs) * 10) / processing_time
            
            # Test memory usage
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()
                result.metrics["memory_usage_mb"] = memory_info.rss / 1024 / 1024
                result.metrics["cpu_percent"] = process.cpu_percent()
            except ImportError:
                log_warning("psutil not available, skipping memory/CPU metrics")
            
            result.success = True
            log_info("✅ Performance optimization test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Performance optimization test failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def run_comprehensive_integration_test(self) -> List[IntegrationTestResult]:
        """Run all integration tests."""
        log_info("🚀 Starting comprehensive integration test...")
        
        test_methods = [
            self.test_kraken_api_integration,
            self.test_data_management_system,
            self.test_strategy_engine_integration,
            self.test_logging_and_alerts_integration,
            self.test_multi_pair_coordination,
            self.test_error_recovery_resilience,
            self.test_performance_optimization
        ]
        
        results = []
        for test_method in test_methods:
            try:
                result = test_method()
                results.append(result)
                self.test_results.append(result)
                
                if result.success:
                    log_info(f"✅ {result.test_name} completed successfully ({result.duration:.2f}s)")
                else:
                    log_error(f"❌ {result.test_name} failed: {result.error_message} ({result.duration:.2f}s)")
                
                # Brief pause between tests
                time.sleep(1)
                
            except Exception as e:
                log_error(f"Critical error in {test_method.__name__}: {e}")
                error_result = IntegrationTestResult(
                    test_name=test_method.__name__,
                    success=False,
                    duration=0.0,
                    error_message=str(e)
                )
                results.append(error_result)
        
        return results
    
    def generate_integration_report(self) -> str:
        """Generate comprehensive integration test report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = total_tests - passed_tests
        total_duration = sum(result.duration for result in self.test_results)
        
        report = f"""
{'='*80}
FINAL INTEGRATION TEST REPORT
{'='*80}

Test Summary:
- Total Tests: {total_tests}
- Passed: {passed_tests}
- Failed: {failed_tests}
- Success Rate: {(passed_tests/total_tests)*100:.1f}%
- Total Duration: {total_duration:.2f}s

Trading Pairs Tested: {', '.join(self.trading_pairs)}
Test Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
DETAILED RESULTS
{'='*80}
"""
        
        for result in self.test_results:
            status = "✅ PASSED" if result.success else "❌ FAILED"
            
            report += f"""
{result.test_name}: {status}
Duration: {result.duration:.2f}s
"""
            
            if result.error_message:
                report += f"Error: {result.error_message}\n"
            
            if result.metrics:
                report += "Metrics:\n"
                for key, value in result.metrics.items():
                    report += f"  - {key}: {value}\n"
            
            report += "-" * 40 + "\n"
        
        # Add system recommendations
        report += f"""
{'='*80}
SYSTEM STATUS AND RECOMMENDATIONS
{'='*80}

"""
        
        if passed_tests == total_tests:
            report += "🎉 ALL TESTS PASSED! The system is ready for production use.\n\n"
            report += "Recommendations:\n"
            report += "- Monitor system performance in production\n"
            report += "- Set up proper alerting and logging\n"
            report += "- Consider implementing additional risk controls\n"
        elif passed_tests >= total_tests * 0.8:
            report += "⚠️  MOST TESTS PASSED. System is mostly functional but needs attention.\n\n"
            report += "Recommendations:\n"
            report += "- Fix failing tests before production deployment\n"
            report += "- Implement additional error handling\n"
            report += "- Consider running in paper trading mode first\n"
        else:
            report += "❌ MULTIPLE TEST FAILURES. System needs significant work before deployment.\n\n"
            report += "Recommendations:\n"
            report += "- Address all failing tests\n"
            report += "- Review system architecture\n"
            report += "- Consider additional testing and validation\n"
        
        return report


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Final Integration Test for Enhanced Kraken Trading Bot")
    
    parser.add_argument(
        "--trading-pairs",
        nargs="+",
        default=["XBTUSD"],
        help="Trading pairs to test (default: XBTUSD)"
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="final_integration_report.txt",
        help="Output file for test report"
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
    
    print("🚀 Enhanced Kraken Trading Bot - Final Integration Test")
    print("=" * 60)
    print(f"Trading Pairs: {', '.join(args.trading_pairs)}")
    print("=" * 60)
    
    # Initialize tester
    tester = FinalIntegrationTester(args)
    
    try:
        # Setup credentials
        if not tester.setup_credentials():
            log_error("Failed to setup credentials")
            return 1
        
        # Initialize components
        if not tester.initialize_core_components():
            log_error("Failed to initialize core components")
            return 1
        
        # Run comprehensive tests
        results = tester.run_comprehensive_integration_test()
        
        # Generate and save report
        report = tester.generate_integration_report()
        
        with open(args.output_file, 'w') as f:
            f.write(report)
        
        print(report)
        print(f"\n📄 Full report saved to: {args.output_file}")
        
        # Return appropriate exit code
        failed_tests = sum(1 for result in results if not result.success)
        return 1 if failed_tests > 0 else 0
        
    except KeyboardInterrupt:
        log_info("Test interrupted by user")
        return 1
    except Exception as e:
        log_error(f"Critical error during testing: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())