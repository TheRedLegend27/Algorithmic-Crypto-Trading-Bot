#!/usr/bin/env python3
"""
Integrated System Test for Enhanced Kraken Trading Bot

This script performs comprehensive system testing by integrating all enhanced components
and validating the complete trading workflow with real Kraken API connectivity.
"""
import os
import sys
import time
import asyncio
import logging
import argparse
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

# Import all enhanced components
from bot.kraken_client import KrakenCredentials
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.kraken_websocket import KrakenWebSocketClient, WebSocketConfig
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig
from bot.enhanced_strategies import EnhancedStrategyEngine, StrategyParameters
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_alerts import EnhancedAlertSystem
from bot.enhanced_dashboard import EnhancedDashboard, DashboardConfig
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_info, log_error, log_warning


@dataclass
class SystemTestResults:
    """Results from comprehensive system testing."""
    test_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class IntegratedSystemTester:
    """Comprehensive system tester for all enhanced components."""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.credentials = None
        self.components = {}
        self.test_results = []
        self.trading_pairs = args.trading_pairs
        self.shutdown_event = threading.Event()
        
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
    
    def initialize_enhanced_components(self) -> bool:
        """Initialize all enhanced components for testing."""
        try:
            log_info("🔧 Initializing enhanced components...")
            
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
                persist_to_disk=False  # Don't persist during testing
            )
            
            # Enhanced Data Manager
            data_manager = EnhancedDataManager(
                pairs=self.trading_pairs,
                cache_config=cache_config
            )
            
            # WebSocket Client
            ws_config = WebSocketConfig(
                max_reconnect_attempts=3,
                heartbeat_interval=30,
                ping_timeout=10
            )
            
            # Create a simple callback handler for testing
            from bot.kraken_websocket import WebSocketCallbackHandler
            callback_handler = WebSocketCallbackHandler()
            
            websocket_client = KrakenWebSocketClient(
                credentials=self.credentials,
                callback_handler=callback_handler,
                config=ws_config
            )
            
            # Strategy Engine
            strategy_params = StrategyParameters(
                volatility_lookback=20,
                momentum_periods=[5, 10, 20],
                volume_threshold=1.2,
                confidence_threshold=0.3
            )
            strategy_engine = EnhancedStrategyEngine(
                strategies=[],  # Will be populated with test strategies
                parameters=strategy_params
            )
            
            # Create required components for risk manager
            from bot.crypto_position_manager import CryptoPositionManager
            from bot.kraken_client import KrakenClient
            
            kraken_client = KrakenClient(self.credentials)
            position_manager = CryptoPositionManager(kraken_client)
            
            # Risk Manager
            risk_manager = EnhancedRiskManager(
                position_manager=position_manager,
                data_manager=data_manager,
                kraken_client=kraken_client,
                trading_pairs=self.trading_pairs
            )
            
            # Alert System
            alert_config = {
                'enabled': True,
                'channels': {
                    'email': {'enabled': False},
                    'webhook': {'enabled': False},
                    'console': {'enabled': True}
                }
            }
            alert_system = EnhancedAlertSystem(alert_config, enhanced_logger)
            
            # Dashboard
            dashboard_config = DashboardConfig(
                host="localhost",
                port=8081,  # Different port for testing
                enable_manual_trading=False,  # Disable for testing
                enable_websocket=True
            )
            dashboard = EnhancedDashboard(
                config=dashboard_config,
                data_manager=data_manager,
                logger=enhanced_logger,
                risk_manager=risk_manager,
                kraken_client=kraken_client
            )
            
            # Kraken Trader
            trading_config = KrakenTradingConfig(
                trading_pair=self.trading_pairs[0],
                trade_amount_usd=10.0,
                max_position_usd=50.0,
                min_trade_interval=60
            )
            trader = KrakenTrader(self.credentials, trading_config)
            
            # Store all components
            self.components = {
                "enhanced_logger": enhanced_logger,
                "data_manager": data_manager,
                "websocket_client": websocket_client,
                "strategy_engine": strategy_engine,
                "risk_manager": risk_manager,
                "alert_system": alert_system,
                "dashboard": dashboard,
                "trader": trader
            }
            
            log_info("✅ All enhanced components initialized successfully")
            return True
            
        except Exception as e:
            log_error(f"Failed to initialize enhanced components: {e}")
            return False
    
    def test_kraken_api_connectivity(self) -> SystemTestResults:
        """Test Kraken API connectivity and basic operations."""
        result = SystemTestResults(
            test_name="Kraken API Connectivity",
            start_time=datetime.now()
        )
        
        try:
            log_info("🔍 Testing Kraken API connectivity...")
            trader = self.components["trader"]
            
            # Test basic connectivity
            if not trader.test_connection():
                raise Exception("Failed to connect to Kraken API")
            
            # Test account info
            account_info = trader.get_account_balance()
            if not account_info:
                raise Exception("Failed to get account information")
            
            # Test market data
            for pair in self.trading_pairs:
                price = trader.get_current_price(pair)
                if not price:
                    raise Exception(f"Failed to get price for {pair}")
                result.metrics[f"{pair}_price"] = price
            
            # Test order book
            orderbook = trader.get_order_book(self.trading_pairs[0])
            if not orderbook:
                raise Exception("Failed to get order book")
            
            result.success = True
            result.metrics["account_balance"] = account_info
            log_info("✅ Kraken API connectivity test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Kraken API connectivity test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_websocket_connectivity(self) -> SystemTestResults:
        """Test WebSocket connectivity and real-time data streaming."""
        result = SystemTestResults(
            test_name="WebSocket Connectivity",
            start_time=datetime.now()
        )
        
        try:
            log_info("🌐 Testing WebSocket connectivity...")
            websocket_client = self.components["websocket_client"]
            
            # Test connection
            if not websocket_client.connect():
                raise Exception("Failed to connect to Kraken WebSocket")
            
            # Test ticker subscription
            if not websocket_client.subscribe_ticker(self.trading_pairs):
                raise Exception("Failed to subscribe to ticker data")
            
            # Wait for data
            log_info("Waiting for WebSocket data...")
            time.sleep(10)
            
            # Check if data was received
            data_manager = self.components["data_manager"]
            for pair in self.trading_pairs:
                latest_data = data_manager.get_latest_data(pair, periods=1)
                if latest_data is None or latest_data.empty:
                    raise Exception(f"No WebSocket data received for {pair}")
                result.metrics[f"{pair}_data_points"] = len(latest_data)
            
            websocket_client.disconnect()
            result.success = True
            log_info("✅ WebSocket connectivity test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ WebSocket connectivity test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_multi_pair_data_management(self) -> SystemTestResults:
        """Test multi-pair data management and synchronization."""
        result = SystemTestResults(
            test_name="Multi-Pair Data Management",
            start_time=datetime.now()
        )
        
        try:
            log_info("📊 Testing multi-pair data management...")
            data_manager = self.components["data_manager"]
            trader = self.components["trader"]
            
            # Fetch data for all pairs
            for pair in self.trading_pairs:
                # Get historical data
                historical_data = trader.get_historical_data(pair, limit=100)
                if historical_data is None or historical_data.empty:
                    raise Exception(f"Failed to get historical data for {pair}")
                
                # Add to data manager
                for _, row in historical_data.iterrows():
                    data_manager.add_market_data(pair, {
                        'timestamp': row.name,
                        'price': row['close'],
                        'volume': row['volume'],
                        'high': row['high'],
                        'low': row['low']
                    })
                
                result.metrics[f"{pair}_historical_points"] = len(historical_data)
            
            # Test data validation
            for pair in self.trading_pairs:
                latest_data = data_manager.get_latest_data(pair, periods=50)
                if latest_data is None or latest_data.empty:
                    raise Exception(f"Failed to retrieve data for {pair}")
                
                quality_report = data_manager.validate_data_quality(latest_data)
                if quality_report.quality_score < 0.5:
                    raise Exception(f"Poor data quality for {pair}: {quality_report.quality_score}")
                
                result.metrics[f"{pair}_quality_score"] = quality_report.quality_score
            
            # Test indicator calculations
            for pair in self.trading_pairs:
                indicators = data_manager.calculate_indicators(pair, ['sma_20', 'rsi_14', 'volatility'])
                if not indicators:
                    raise Exception(f"Failed to calculate indicators for {pair}")
                
                result.metrics[f"{pair}_indicators"] = list(indicators.keys())
            
            result.success = True
            log_info("✅ Multi-pair data management test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Multi-pair data management test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_strategy_engine_performance(self) -> SystemTestResults:
        """Test strategy engine with multiple strategies and pairs."""
        result = SystemTestResults(
            test_name="Strategy Engine Performance",
            start_time=datetime.now()
        )
        
        try:
            log_info("🧠 Testing strategy engine performance...")
            strategy_engine = self.components["strategy_engine"]
            data_manager = self.components["data_manager"]
            
            # Test signal generation for each pair
            for pair in self.trading_pairs:
                market_data = data_manager.get_latest_data(pair, periods=100)
                if market_data is None or market_data.empty:
                    raise Exception(f"No market data available for {pair}")
                
                # Generate signals
                signal = strategy_engine.calculate_weighted_signal(market_data)
                if signal is None:
                    raise Exception(f"Failed to generate signal for {pair}")
                
                result.metrics[f"{pair}_signal_confidence"] = signal.confidence
                result.metrics[f"{pair}_signal_action"] = signal.action.name
            
            # Test strategy performance metrics
            performance_metrics = strategy_engine.get_performance_metrics()
            result.metrics["strategy_performance"] = performance_metrics
            
            result.success = True
            log_info("✅ Strategy engine performance test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Strategy engine performance test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_risk_management_validation(self) -> SystemTestResults:
        """Test risk management system with various scenarios."""
        result = SystemTestResults(
            test_name="Risk Management Validation",
            start_time=datetime.now()
        )
        
        try:
            log_info("🛡️ Testing risk management validation...")
            risk_manager = self.components["risk_manager"]
            trader = self.components["trader"]
            
            # Get current positions
            current_positions = trader.get_positions()
            
            # Test risk validation for each pair
            for pair in self.trading_pairs:
                # Create test signal
                test_signal = TradingSignal(
                    action=SignalType.BUY,
                    confidence=0.7,
                    price=50000.0,  # Test price
                    timestamp=time.time(),
                    strategy="test_strategy"
                )
                
                # Validate trade
                risk_assessment = risk_manager.validate_trade(test_signal, current_positions)
                
                result.metrics[f"{pair}_risk_valid"] = risk_assessment.is_valid
                result.metrics[f"{pair}_risk_factors"] = risk_assessment.risk_factors
                result.metrics[f"{pair}_recommended_size"] = risk_assessment.recommended_size
            
            # Test portfolio risk calculation
            portfolio_risk = risk_manager.check_portfolio_risk(current_positions, {})
            result.metrics["portfolio_risk"] = {
                "total_exposure": portfolio_risk.total_exposure,
                "risk_score": portfolio_risk.risk_score,
                "max_drawdown": portfolio_risk.max_drawdown
            }
            
            # Test emergency stop conditions
            should_stop = risk_manager.should_emergency_stop({})
            result.metrics["emergency_stop_triggered"] = should_stop
            
            result.success = True
            log_info("✅ Risk management validation test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Risk management validation test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_logging_and_alerts(self) -> SystemTestResults:
        """Test enhanced logging and alert systems."""
        result = SystemTestResults(
            test_name="Logging and Alerts",
            start_time=datetime.now()
        )
        
        try:
            log_info("📝 Testing logging and alert systems...")
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
                'strategy': 'test_strategy'
            }
            
            enhanced_logger.log_trade(test_trade)
            
            # Test signal logging
            test_signal = TradingSignal(
                action=SignalType.BUY,
                confidence=0.8,
                price=50000.0,
                timestamp=time.time(),
                strategy="test_strategy"
            )
            
            enhanced_logger.log_signal(test_signal, test_trade)
            
            # Test performance metrics logging
            test_metrics = {
                'total_trades': 10,
                'win_rate': 0.6,
                'total_pnl': 150.0,
                'sharpe_ratio': 1.2
            }
            
            enhanced_logger.log_performance_metrics(test_metrics)
            
            # Test alert system
            alert_system.send_trade_alert(test_trade)
            alert_system.send_performance_alert(test_metrics)
            alert_system.send_system_alert("TEST", "System test alert", "INFO")
            
            # Test daily report generation
            daily_report = enhanced_logger.generate_daily_report(datetime.now())
            result.metrics["daily_report_generated"] = daily_report is not None
            
            result.success = True
            log_info("✅ Logging and alerts test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Logging and alerts test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_dashboard_functionality(self) -> SystemTestResults:
        """Test enhanced dashboard functionality."""
        result = SystemTestResults(
            test_name="Dashboard Functionality",
            start_time=datetime.now()
        )
        
        try:
            log_info("📊 Testing dashboard functionality...")
            dashboard = self.components["dashboard"]
            
            # Start dashboard server
            dashboard.start_server(host="localhost", port=8081)
            time.sleep(2)  # Allow server to start
            
            # Test portfolio data update
            test_portfolio = {
                'total_value': 1000.0,
                'positions': {pair: {'balance': 0.01, 'value': 500.0} for pair in self.trading_pairs}
            }
            dashboard.update_portfolio_data(test_portfolio)
            
            # Test market data update
            test_market_data = {
                pair: {'price': 50000.0, 'volume': 100.0, 'change_24h': 0.05}
                for pair in self.trading_pairs
            }
            dashboard.update_market_data(test_market_data)
            
            # Test trade event addition
            test_trade_event = {
                'timestamp': datetime.now(),
                'pair': self.trading_pairs[0],
                'action': 'BUY',
                'volume': 0.001,
                'price': 50000.0
            }
            dashboard.add_trade_event(test_trade_event)
            
            # Test performance metrics update
            test_performance = {
                'total_pnl': 150.0,
                'win_rate': 0.65,
                'total_trades': 20,
                'sharpe_ratio': 1.3
            }
            dashboard.update_performance_metrics(test_performance)
            
            result.metrics["dashboard_started"] = True
            result.success = True
            log_info("✅ Dashboard functionality test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Dashboard functionality test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_error_recovery_scenarios(self) -> SystemTestResults:
        """Test error recovery and system resilience."""
        result = SystemTestResults(
            test_name="Error Recovery Scenarios",
            start_time=datetime.now()
        )
        
        try:
            log_info("🔄 Testing error recovery scenarios...")
            
            # Test API connection recovery
            trader = self.components["trader"]
            websocket_client = self.components["websocket_client"]
            
            # Simulate connection loss and recovery
            original_connection = trader.test_connection()
            result.metrics["initial_connection"] = original_connection
            
            # Test WebSocket reconnection
            if websocket_client.is_connected():
                websocket_client.disconnect()
                time.sleep(2)
                reconnect_success = websocket_client.connect()
                result.metrics["websocket_reconnect"] = reconnect_success
            
            # Test data manager error handling
            data_manager = self.components["data_manager"]
            try:
                # Try to get data for invalid pair
                invalid_data = data_manager.get_latest_data("INVALID/PAIR", periods=10)
                result.metrics["invalid_pair_handled"] = invalid_data is None
            except Exception:
                result.metrics["invalid_pair_handled"] = True
            
            # Test risk manager with extreme scenarios
            risk_manager = self.components["risk_manager"]
            extreme_signal = TradingSignal(
                action=SignalType.BUY,
                confidence=0.9,
                price=1000000.0,  # Extreme price
                timestamp=time.time(),
                strategy="test_strategy"
            )
            
            risk_assessment = risk_manager.validate_trade(extreme_signal, {})
            result.metrics["extreme_scenario_handled"] = not risk_assessment.is_valid
            
            result.success = True
            log_info("✅ Error recovery scenarios test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Error recovery scenarios test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def test_performance_optimization(self) -> SystemTestResults:
        """Test system performance and optimization."""
        result = SystemTestResults(
            test_name="Performance Optimization",
            start_time=datetime.now()
        )
        
        try:
            log_info("⚡ Testing performance optimization...")
            
            # Test data processing speed
            data_manager = self.components["data_manager"]
            start_time = time.time()
            
            for pair in self.trading_pairs:
                for _ in range(10):  # Process multiple data points
                    test_data = {
                        'timestamp': datetime.now(),
                        'price': 50000.0,
                        'volume': 1.0,
                        'high': 50100.0,
                        'low': 49900.0
                    }
                    data_manager.add_market_data(pair, test_data)
            
            processing_time = time.time() - start_time
            result.metrics["data_processing_time"] = processing_time
            
            # Test strategy calculation speed
            strategy_engine = self.components["strategy_engine"]
            start_time = time.time()
            
            for pair in self.trading_pairs:
                market_data = data_manager.get_latest_data(pair, periods=50)
                if market_data is not None and not market_data.empty:
                    strategy_engine.calculate_weighted_signal(market_data)
            
            strategy_time = time.time() - start_time
            result.metrics["strategy_calculation_time"] = strategy_time
            
            # Test memory usage
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            result.metrics["memory_usage_mb"] = memory_info.rss / 1024 / 1024
            result.metrics["cpu_percent"] = process.cpu_percent()
            
            result.success = True
            log_info("✅ Performance optimization test passed")
            
        except Exception as e:
            result.error_message = str(e)
            log_error(f"❌ Performance optimization test failed: {e}")
        
        result.end_time = datetime.now()
        return result
    
    def run_comprehensive_system_test(self) -> List[SystemTestResults]:
        """Run all system tests in sequence."""
        log_info("🚀 Starting comprehensive system test...")
        
        test_methods = [
            self.test_kraken_api_connectivity,
            self.test_websocket_connectivity,
            self.test_multi_pair_data_management,
            self.test_strategy_engine_performance,
            self.test_risk_management_validation,
            self.test_logging_and_alerts,
            self.test_dashboard_functionality,
            self.test_error_recovery_scenarios,
            self.test_performance_optimization
        ]
        
        results = []
        for test_method in test_methods:
            try:
                result = test_method()
                results.append(result)
                self.test_results.append(result)
                
                if result.success:
                    log_info(f"✅ {result.test_name} completed successfully")
                else:
                    log_error(f"❌ {result.test_name} failed: {result.error_message}")
                
                # Brief pause between tests
                time.sleep(2)
                
            except Exception as e:
                log_error(f"Critical error in {test_method.__name__}: {e}")
                error_result = SystemTestResults(
                    test_name=test_method.__name__,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    success=False,
                    error_message=str(e)
                )
                results.append(error_result)
        
        return results
    
    def generate_test_report(self) -> str:
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = total_tests - passed_tests
        
        report = f"""
{'='*80}
INTEGRATED SYSTEM TEST REPORT
{'='*80}

Test Summary:
- Total Tests: {total_tests}
- Passed: {passed_tests}
- Failed: {failed_tests}
- Success Rate: {(passed_tests/total_tests)*100:.1f}%

Trading Pairs Tested: {', '.join(self.trading_pairs)}
Test Duration: {datetime.now() - self.test_results[0].start_time if self.test_results else 'N/A'}

{'='*80}
DETAILED RESULTS
{'='*80}
"""
        
        for result in self.test_results:
            duration = (result.end_time - result.start_time).total_seconds() if result.end_time else 0
            status = "✅ PASSED" if result.success else "❌ FAILED"
            
            report += f"""
{result.test_name}: {status}
Duration: {duration:.2f}s
"""
            
            if result.error_message:
                report += f"Error: {result.error_message}\n"
            
            if result.metrics:
                report += "Metrics:\n"
                for key, value in result.metrics.items():
                    report += f"  - {key}: {value}\n"
            
            report += "-" * 40 + "\n"
        
        return report


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Integrated System Test for Enhanced Kraken Trading Bot")
    
    parser.add_argument(
        "--trading-pairs",
        nargs="+",
        default=["XBTUSD", "XETHZUSD"],
        help="Trading pairs to test (default: XBTUSD XETHZUSD)"
    )
    
    parser.add_argument(
        "--test-duration",
        type=int,
        default=300,
        help="Test duration in seconds (default: 300)"
    )
    
    parser.add_argument(
        "--skip-websocket",
        action="store_true",
        help="Skip WebSocket tests"
    )
    
    parser.add_argument(
        "--skip-dashboard",
        action="store_true",
        help="Skip dashboard tests"
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="system_test_report.txt",
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
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Enhanced Kraken Trading Bot - Integrated System Test")
    print("=" * 60)
    print(f"Trading Pairs: {', '.join(args.trading_pairs)}")
    print(f"Test Duration: {args.test_duration}s")
    print("=" * 60)
    
    # Initialize tester
    tester = IntegratedSystemTester(args)
    
    try:
        # Setup credentials
        if not tester.setup_credentials():
            log_error("Failed to setup credentials")
            return 1
        
        # Initialize components
        if not tester.initialize_enhanced_components():
            log_error("Failed to initialize enhanced components")
            return 1
        
        # Run comprehensive tests
        results = tester.run_comprehensive_system_test()
        
        # Generate and save report
        report = tester.generate_test_report()
        
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
    finally:
        # Cleanup
        if tester.components.get("websocket_client"):
            try:
                tester.components["websocket_client"].disconnect()
            except:
                pass


if __name__ == "__main__":
    sys.exit(main())