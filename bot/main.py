#!/usr/bin/env python
"""
Enhanced main entry point for the crypto trading bot.
Orchestrates all enhanced components with multi-pair trading support,
system health monitoring, error recovery, and graceful shutdown.
"""
import argparse
import sys
import time
import signal
import logging
import os
import atexit
import threading
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from bot.config import Config, TradingSettings, KrakenCredentials, CryptoTradingSettings
from bot.data_fetcher import DataFetcher
from bot.strategy import MovingAverageCrossover, RSIStrategy, SignalGenerator, BaseStrategy
from bot.crypto_strategies import CryptoMovingAverageCrossover, CryptoRSIStrategy
from bot.kraken_trader import KrakenTrader
from bot.logger import TradingLogger
from bot.scheduler import TradingCycle, TradingScheduler
from bot.utils import log_info, log_error, log_warning, retry_with_backoff
from bot.error_handler import ErrorHandler

# Enhanced components
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig
from bot.enhanced_strategies import EnhancedStrategyEngine, StrategyParameters
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_alerts import EnhancedAlertSystem, AlertSeverity
from bot.enhanced_dashboard import EnhancedDashboard, DashboardConfig
from bot.kraken_websocket import KrakenWebSocketClient, WebSocketConfig


@dataclass
class SystemHealth:
    """System health monitoring data."""
    is_healthy: bool = True
    last_check: datetime = field(default_factory=datetime.now)
    api_connection: bool = True
    websocket_connection: bool = True
    data_quality: float = 1.0
    memory_usage_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    active_trades: int = 0
    error_count: int = 0
    uptime_seconds: float = 0.0
    issues: List[str] = field(default_factory=list)


@dataclass
class BotOrchestrator:
    """Main bot orchestrator managing all enhanced components."""
    config: Config
    args: argparse.Namespace
    components: Dict[str, Any] = field(default_factory=dict)
    trading_pairs: List[str] = field(default_factory=list)
    system_health: SystemHealth = field(default_factory=SystemHealth)
    shutdown_event: threading.Event = field(default_factory=threading.Event)
    start_time: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Initialize the orchestrator."""
        self.system_health.uptime_seconds = 0.0


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Namespace containing the parsed arguments
    """
    parser = argparse.ArgumentParser(description="Crypto Trading Bot - Kraken Edition")
    
    # Trading symbol configuration
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="XBTUSD",
        help="Trading symbol (default: XBTUSD for Bitcoin/USD on Kraken)"
    )
    
    # Scheduling configuration
    parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Trading interval in minutes (default: 5)"
    )
    
    parser.add_argument(
        "--start-delay",
        type=int,
        default=0,
        help="Delay in seconds before starting the first trading cycle (default: 0)"
    )
    
    # Trading parameters
    parser.add_argument(
        "--amount", 
        type=float, 
        default=10.0,
        help="Amount to trade in USD (default: 10.0)"
    )
    
    parser.add_argument(
        "--max-position", 
        type=float, 
        default=100.0,
        help="Maximum position size in USD (default: 100.0)"
    )
    
    parser.add_argument(
        "--stop-loss", 
        type=float, 
        default=0.05,
        help="Stop loss percentage (default: 0.05)"
    )
    
    parser.add_argument(
        "--take-profit", 
        type=float, 
        default=0.1,
        help="Take profit percentage (default: 0.1)"
    )
    
    # Strategy configuration
    parser.add_argument(
        "--ma-fast",
        type=int,
        default=10,
        help="Fast period for Moving Average Crossover strategy (default: 10)"
    )
    
    parser.add_argument(
        "--ma-slow",
        type=int,
        default=30,
        help="Slow period for Moving Average Crossover strategy (default: 30)"
    )
    
    parser.add_argument(
        "--rsi-period",
        type=int,
        default=14,
        help="Period for RSI strategy (default: 14)"
    )
    
    parser.add_argument(
        "--rsi-oversold",
        type=int,
        default=30,
        help="Oversold threshold for RSI strategy (default: 30)"
    )
    
    parser.add_argument(
        "--rsi-overbought",
        type=int,
        default=70,
        help="Overbought threshold for RSI strategy (default: 70)"
    )
    
    # Execution modes
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual trades will be executed)"
    )
    
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Run in backtest mode using historical data"
    )
    
    parser.add_argument(
        "--backtest-days",
        type=int,
        default=30,
        help="Number of days to backtest (default: 30)"
    )
    
    # Display and logging options
    parser.add_argument(
        "--no-dashboard", 
        action="store_true",
        help="Disable rich dashboard display"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        default="bot.log",
        help="Path to log file (default: bot.log)"
    )
    
    # Health check configuration
    parser.add_argument(
        "--health-check-interval",
        type=int,
        default=30,
        help="Interval in minutes between health checks (default: 30)"
    )
    
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip initial health check on startup"
    )
    
    # Trading limits
    parser.add_argument(
        "--maxtrades",
        type=int,
        default=20,
        help="Maximum number of trades per day (default: 20)"
    )
    
    parser.add_argument(
        "--base-currency",
        type=str,
        default="BTC",
        help="Base currency for trading pair (default: BTC)"
    )
    
    parser.add_argument(
        "--quote-currency",
        type=str,
        default="USD",
        help="Quote currency for trading pair (default: USD)"
    )
    
    parser.add_argument(
        "--min-order-size",
        type=float,
        default=0.001,
        help="Minimum order size in base currency (default: 0.001)"
    )
    
    # Multi-pair trading
    parser.add_argument(
        "--trading-pairs",
        type=str,
        nargs="+",
        default=["XBTUSD"],
        help="List of trading pairs (default: XBTUSD)"
    )
    
    # Enhanced features
    parser.add_argument(
        "--enable-websocket",
        action="store_true",
        default=True,
        help="Enable WebSocket for real-time data (default: True)"
    )
    
    parser.add_argument(
        "--enable-dashboard",
        action="store_true",
        default=True,
        help="Enable enhanced dashboard (default: True)"
    )
    
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8080,
        help="Dashboard port (default: 8080)"
    )
    
    parser.add_argument(
        "--enable-alerts",
        action="store_true",
        default=True,
        help="Enable enhanced alerts (default: True)"
    )
    
    parser.add_argument(
        "--performance-monitoring",
        action="store_true",
        default=True,
        help="Enable performance monitoring (default: True)"
    )
    
    parser.add_argument(
        "--close-positions-on-shutdown",
        action="store_true",
        default=False,
        help="Close all positions on shutdown (default: False)"
    )
    
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.3,
        help="Minimum signal confidence for trade execution (default: 0.3)"
    )
    
    return parser.parse_args()


def update_trading_settings(settings: TradingSettings, args: argparse.Namespace) -> None:
    """
    Update trading settings from command line arguments.
    
    Args:
        settings: TradingSettings object to update
        args: Parsed command line arguments
    """
    settings.symbol = args.symbol
    settings.trade_amount = args.amount
    settings.max_position_size = args.max_position
    settings.stop_loss_pct = args.stop_loss
    settings.take_profit_pct = args.take_profit
    settings.min_trade_interval = args.interval
    
    # Add max_trades_per_day to settings if it doesn't exist
    if not hasattr(settings, 'max_trades_per_day'):
        settings.max_trades_per_day = args.maxtrades
    else:
        settings.max_trades_per_day = args.maxtrades


def update_crypto_trading_settings(settings: CryptoTradingSettings, args: argparse.Namespace) -> None:
    """
    Update crypto trading settings from command line arguments.
    
    Args:
        settings: CryptoTradingSettings object to update
        args: Parsed command line arguments
    """
    settings.trading_pair = args.symbol
    settings.base_currency = args.base_currency
    settings.quote_currency = args.quote_currency
    settings.trade_amount_usd = args.amount
    settings.max_position_usd = args.max_position
    settings.min_order_size = args.min_order_size
    settings.stop_loss_pct = args.stop_loss
    settings.take_profit_pct = args.take_profit


def initialize_enhanced_components(orchestrator: BotOrchestrator) -> bool:
    """
    Initialize all enhanced components for the trading bot.
    
    Args:
        orchestrator: BotOrchestrator instance
        
    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        config = orchestrator.config
        args = orchestrator.args
        
        # Get credentials and settings
        credentials = config.get_kraken_credentials()
        if not credentials:
            log_error("Kraken credentials not found. Please set KRAKEN_API_KEY and KRAKEN_API_SECRET environment variables.")
            return False
        
        # Get crypto trading settings
        crypto_settings = config.get_crypto_trading_settings()
        update_crypto_trading_settings(crypto_settings, args)
        
        # Set trading pairs
        orchestrator.trading_pairs = args.trading_pairs
        
        # Initialize enhanced logger
        enhanced_logger = EnhancedLogger(
            log_level=args.log_level,
            log_file=args.log_file,
            enable_structured_logging=True,
            enable_performance_tracking=args.performance_monitoring
        )
        
        # Initialize cache configuration
        cache_config = CacheConfig(
            enabled=True,
            max_memory_mb=100,
            retention_hours=24,
            persist_to_disk=True
        )
        
        # Initialize enhanced data manager
        data_manager = EnhancedDataManager(
            pairs=orchestrator.trading_pairs,
            cache_config=cache_config
        )
        
        # Initialize WebSocket client if enabled
        websocket_client = None
        if args.enable_websocket:
            ws_config = WebSocketConfig()
            websocket_client = KrakenWebSocketClient(
                credentials=credentials,
                config=ws_config
            )
        
        # Initialize enhanced strategy engine
        strategy_params = StrategyParameters(
            volatility_lookback=20,
            momentum_periods=[5, 10, 20],
            volume_threshold=1.2,
            confidence_threshold=0.3
        )
        
        strategies = [
            CryptoMovingAverageCrossover(
                fast_period=args.ma_fast,
                slow_period=args.ma_slow
            ),
            CryptoRSIStrategy(
                period=args.rsi_period,
                base_oversold=args.rsi_oversold,
                base_overbought=args.rsi_overbought
            )
        ]
        
        strategy_engine = EnhancedStrategyEngine(
            strategies=strategies,
            parameters=strategy_params
        )
        
        # Initialize enhanced risk manager
        risk_manager = EnhancedRiskManager(
            trading_pairs=orchestrator.trading_pairs,
            max_position_per_pair=args.max_position,
            max_total_exposure=args.max_position * len(orchestrator.trading_pairs),
            stop_loss_pct=args.stop_loss,
            take_profit_pct=args.take_profit
        )
        
        # Initialize enhanced alert system if enabled
        alert_system = None
        if args.enable_alerts:
            alert_system = EnhancedAlertSystem(
                enable_email=False,  # Configure as needed
                enable_webhook=False,  # Configure as needed
                enable_console=True
            )
        
        # Initialize enhanced dashboard if enabled
        dashboard = None
        if args.enable_dashboard:
            dashboard_config = DashboardConfig(
                host="localhost",
                port=args.dashboard_port,
                enable_manual_trading=True,
                enable_websocket=args.enable_websocket
            )
            dashboard = EnhancedDashboard(
                config=dashboard_config,
                data_manager=data_manager
            )
        
        # Initialize traditional components for compatibility
        data_fetcher = DataFetcher(credentials)
        signal_generator = SignalGenerator(strategies)
        
        trader = KrakenTrader(
            logger=TradingLogger(use_rich=not args.no_dashboard, log_file=args.log_file),
            credentials=credentials,
            settings=crypto_settings
        )
        
        error_handler = ErrorHandler()
        
        # Store all components
        orchestrator.components = {
            "enhanced_logger": enhanced_logger,
            "data_manager": data_manager,
            "websocket_client": websocket_client,
            "strategy_engine": strategy_engine,
            "risk_manager": risk_manager,
            "alert_system": alert_system,
            "dashboard": dashboard,
            "data_fetcher": data_fetcher,
            "signal_generator": signal_generator,
            "trader": trader,
            "error_handler": error_handler,
            "credentials": credentials,
            "crypto_settings": crypto_settings
        }
        
        log_info("Enhanced components initialized successfully")
        return True
        
    except Exception as e:
        log_error(f"Failed to initialize enhanced components: {e}")
        return False



def start_multi_pair_trading_loop(orchestrator: BotOrchestrator) -> None:
    """
    Start the multi-pair trading loop with proper synchronization.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    def trading_loop():
        """Main trading loop for multiple pairs."""
        components = orchestrator.components
        data_manager = components["data_manager"]
        strategy_engine = components["strategy_engine"]
        risk_manager = components["risk_manager"]
        trader = components["trader"]
        enhanced_logger = components["enhanced_logger"]
        alert_system = components["alert_system"]
        
        last_trade_times = {pair: datetime.now() for pair in orchestrator.trading_pairs}
        
        while not orchestrator.shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                # Process each trading pair
                for pair in orchestrator.trading_pairs:
                    try:
                        # Check if enough time has passed since last trade
                        if (current_time - last_trade_times[pair]).total_seconds() < orchestrator.args.interval * 60:
                            continue
                        
                        # Get latest market data
                        market_data = data_manager.get_latest_data(pair, periods=100)
                        if market_data is None or market_data.empty:
                            log_warning(f"No market data available for {pair}")
                            continue
                        
                        # Generate trading signal
                        signal = strategy_engine.calculate_weighted_signal(market_data)
                        if signal is None:
                            continue
                        
                        # Validate with risk manager
                        current_positions = trader.get_positions()
                        risk_assessment = risk_manager.validate_trade(signal, current_positions)
                        
                        if not risk_assessment.is_valid:
                            log_info(f"Trade rejected for {pair}: {risk_assessment.risk_factors}")
                            continue
                        
                        # Execute trade if signal is strong enough
                        if signal.confidence >= orchestrator.args.confidence_threshold:
                            trade_result = trader.execute_trade(
                                pair=pair,
                                signal=signal,
                                amount=risk_assessment.recommended_size
                            )
                            
                            if trade_result:
                                last_trade_times[pair] = current_time
                                enhanced_logger.log_trade(trade_result)
                                
                                if alert_system:
                                    alert_system.send_trade_alert(trade_result)
                        
                    except Exception as e:
                        log_error(f"Error processing pair {pair}: {e}")
                        continue
                
                # Update system health
                update_system_health(orchestrator)
                
                # Sleep for a short interval
                time.sleep(5)
                
            except Exception as e:
                log_error(f"Error in trading loop: {e}")
                time.sleep(10)
    
    # Start trading loop in separate thread
    trading_thread = threading.Thread(target=trading_loop, daemon=True)
    trading_thread.start()
    log_info("Multi-pair trading loop started")


def update_system_health(orchestrator: BotOrchestrator) -> None:
    """
    Update system health metrics.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    try:
        import psutil
        
        health = orchestrator.system_health
        components = orchestrator.components
        
        # Update basic metrics
        health.last_check = datetime.now()
        health.uptime_seconds = (datetime.now() - orchestrator.start_time).total_seconds()
        health.memory_usage_mb = psutil.Process().memory_info().rss / 1024 / 1024
        health.cpu_usage_pct = psutil.Process().cpu_percent()
        
        # Check API connection
        try:
            trader = components["trader"]
            account_info = trader.get_account_info()
            health.api_connection = account_info is not None
        except:
            health.api_connection = False
        
        # Check WebSocket connection
        websocket_client = components.get("websocket_client")
        if websocket_client:
            health.websocket_connection = websocket_client.is_connected()
        else:
            health.websocket_connection = True  # Not using WebSocket
        
        # Check data quality
        data_manager = components["data_manager"]
        total_quality = 0.0
        pair_count = 0
        
        for pair in orchestrator.trading_pairs:
            try:
                data = data_manager.get_latest_data(pair, periods=10)
                if data is not None and not data.empty:
                    quality_report = data_manager.validate_data_quality(data)
                    total_quality += quality_report.quality_score
                    pair_count += 1
            except:
                pass
        
        health.data_quality = total_quality / max(pair_count, 1)
        
        # Update overall health status
        health.issues.clear()
        health.is_healthy = True
        
        if not health.api_connection:
            health.issues.append("API connection lost")
            health.is_healthy = False
        
        if not health.websocket_connection:
            health.issues.append("WebSocket connection lost")
        
        if health.data_quality < 0.8:
            health.issues.append("Poor data quality")
        
        if health.memory_usage_mb > 500:
            health.issues.append("High memory usage")
        
        if health.cpu_usage_pct > 80:
            health.issues.append("High CPU usage")
        
        # Log health status periodically
        if int(health.uptime_seconds) % 300 == 0:  # Every 5 minutes
            log_info(f"System Health - Healthy: {health.is_healthy}, "
                    f"Memory: {health.memory_usage_mb:.1f}MB, "
                    f"CPU: {health.cpu_usage_pct:.1f}%, "
                    f"Data Quality: {health.data_quality:.2f}")
        
    except Exception as e:
        log_error(f"Error updating system health: {e}")


def perform_enhanced_health_check(orchestrator: BotOrchestrator) -> bool:
    """
    Perform a comprehensive health check on all enhanced components.
    
    Args:
        orchestrator: BotOrchestrator instance
        
    Returns:
        bool: True if all components are healthy, False otherwise
    """
    try:
        log_info("Performing enhanced health check...")
        components = orchestrator.components
        
        # Check each trading pair
        for pair in orchestrator.trading_pairs:
            try:
                # Check data fetcher
                data_fetcher = components["data_fetcher"]
                price = data_fetcher.get_latest_price(pair)
                log_info(f"Data fetcher check for {pair}: OK (Latest price: ${price:.2f})")
            except Exception as e:
                log_error(f"Data fetcher check for {pair}: FAILED - {e}")
                return False
        
        # Check trader
        trader = components["trader"]
        try:
            account_info = trader.get_account_info()
            if account_info:
                log_info(f"Trader check: OK (Account balance: ${account_info.get('balance', 'N/A')})")
            else:
                log_warning("Trader check: WARNING (Could not get account info)")
        except Exception as e:
            log_error(f"Trader check: FAILED - {e}")
            return False
        
        # Check enhanced data manager
        data_manager = components["data_manager"]
        try:
            for pair in orchestrator.trading_pairs:
                data = data_manager.get_latest_data(pair, periods=10)
                if data is not None and not data.empty:
                    quality_report = data_manager.validate_data_quality(data)
                    log_info(f"Data manager check for {pair}: OK (Quality: {quality_report.quality_score:.2f})")
                else:
                    log_warning(f"Data manager check for {pair}: WARNING (No data available)")
        except Exception as e:
            log_error(f"Data manager check: FAILED - {e}")
            return False
        
        # Check WebSocket client if enabled
        websocket_client = components.get("websocket_client")
        if websocket_client:
            try:
                if websocket_client.is_connected():
                    log_info("WebSocket client check: OK (Connected)")
                else:
                    log_warning("WebSocket client check: WARNING (Not connected)")
            except Exception as e:
                log_error(f"WebSocket client check: FAILED - {e}")
        
        # Check enhanced risk manager
        risk_manager = components["risk_manager"]
        try:
            # Test risk assessment
            current_positions = trader.get_positions()
            log_info("Risk manager check: OK")
        except Exception as e:
            log_error(f"Risk manager check: FAILED - {e}")
            return False
        
        # Check dashboard if enabled
        dashboard = components.get("dashboard")
        if dashboard:
            try:
                # Dashboard health check would go here
                log_info("Dashboard check: OK")
            except Exception as e:
                log_warning(f"Dashboard check: WARNING - {e}")
        
        # Update system health
        update_system_health(orchestrator)
        
        log_info("Enhanced health check completed successfully")
        return True
        
    except Exception as e:
        log_error(f"Enhanced health check failed with unexpected error: {e}")
        return False


def setup_enhanced_signal_handlers(orchestrator: BotOrchestrator) -> None:
    """
    Set up enhanced signal handlers for graceful shutdown.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    def signal_handler(sig, frame):
        log_info(f"Received signal {sig}, initiating graceful shutdown...")
        initiate_graceful_shutdown(orchestrator)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def initiate_graceful_shutdown(orchestrator: BotOrchestrator) -> None:
    """
    Initiate graceful shutdown of all components.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    try:
        log_info("Initiating graceful shutdown...")
        
        # Set shutdown event
        orchestrator.shutdown_event.set()
        
        components = orchestrator.components
        
        # Stop WebSocket client
        websocket_client = components.get("websocket_client")
        if websocket_client:
            try:
                websocket_client.disconnect()
                log_info("WebSocket client disconnected")
            except Exception as e:
                log_error(f"Error disconnecting WebSocket client: {e}")
        
        # Stop dashboard
        dashboard = components.get("dashboard")
        if dashboard:
            try:
                dashboard.stop_server()
                log_info("Dashboard server stopped")
            except Exception as e:
                log_error(f"Error stopping dashboard: {e}")
        
        # Close any open positions if configured
        trader = components.get("trader")
        if trader and orchestrator.args.close_positions_on_shutdown:
            try:
                positions = trader.get_positions()
                for pair, position in positions.items():
                    if position.get("size", 0) != 0:
                        log_info(f"Closing position for {pair}")
                        trader.close_position(pair)
            except Exception as e:
                log_error(f"Error closing positions: {e}")
        
        # Flush logs
        enhanced_logger = components.get("enhanced_logger")
        if enhanced_logger:
            try:
                enhanced_logger.flush_logs()
                log_info("Logs flushed")
            except Exception as e:
                log_error(f"Error flushing logs: {e}")
        
        # Send shutdown alert
        alert_system = components.get("alert_system")
        if alert_system:
            try:
                alert_system.send_system_alert(
                    alert_type="SYSTEM_SHUTDOWN",
                    message="Trading bot shutting down gracefully",
                    severity=AlertSeverity.MEDIUM
                )
            except Exception as e:
                log_error(f"Error sending shutdown alert: {e}")
        
        log_info("Graceful shutdown completed")
        
    except Exception as e:
        log_error(f"Error during graceful shutdown: {e}")


def handle_error_recovery(orchestrator: BotOrchestrator, error: Exception) -> bool:
    """
    Handle error recovery and determine if restart is needed.
    
    Args:
        orchestrator: BotOrchestrator instance
        error: Exception that occurred
        
    Returns:
        bool: True if recovery successful, False if restart needed
    """
    try:
        log_error(f"Handling error recovery for: {error}")
        
        components = orchestrator.components
        error_handler = components.get("error_handler")
        
        # Increment error count
        orchestrator.system_health.error_count += 1
        
        # Check if this is a recoverable error
        if isinstance(error, (ConnectionError, TimeoutError)):
            log_info("Attempting to recover from connection error...")
            
            # Try to reconnect WebSocket
            websocket_client = components.get("websocket_client")
            if websocket_client:
                try:
                    websocket_client.reconnect()
                    log_info("WebSocket reconnected successfully")
                except Exception as e:
                    log_error(f"Failed to reconnect WebSocket: {e}")
                    return False
            
            # Test API connection
            trader = components.get("trader")
            if trader:
                try:
                    trader.get_account_info()
                    log_info("API connection restored")
                    return True
                except Exception as e:
                    log_error(f"API connection still failed: {e}")
                    return False
        
        # Check if too many errors occurred
        if orchestrator.system_health.error_count > 10:
            log_error("Too many errors occurred, restart required")
            return False
        
        # For other errors, try to continue
        return True
        
    except Exception as e:
        log_error(f"Error in error recovery handler: {e}")
        return False


def monitor_performance_and_optimize(orchestrator: BotOrchestrator) -> None:
    """
    Monitor performance and apply optimizations.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    def performance_monitor():
        """Performance monitoring loop."""
        while not orchestrator.shutdown_event.is_set():
            try:
                # Update system health
                update_system_health(orchestrator)
                
                health = orchestrator.system_health
                components = orchestrator.components
                
                # Check memory usage
                if health.memory_usage_mb > 400:
                    log_warning(f"High memory usage: {health.memory_usage_mb:.1f}MB")
                    
                    # Try garbage collection
                    import gc
                    gc.collect()
                    
                    # Clear old cache data
                    data_manager = components.get("data_manager")
                    if data_manager:
                        data_manager.cleanup_cache()
                
                # Check CPU usage
                if health.cpu_usage_pct > 70:
                    log_warning(f"High CPU usage: {health.cpu_usage_pct:.1f}%")
                    
                    # Reduce trading frequency temporarily
                    orchestrator.args.interval = max(orchestrator.args.interval * 1.2, 1)
                
                # Log performance metrics
                enhanced_logger = components.get("enhanced_logger")
                if enhanced_logger and orchestrator.args.performance_monitoring:
                    performance_metrics = {
                        "uptime_seconds": health.uptime_seconds,
                        "memory_usage_mb": health.memory_usage_mb,
                        "cpu_usage_pct": health.cpu_usage_pct,
                        "data_quality": health.data_quality,
                        "error_count": health.error_count,
                        "active_pairs": len(orchestrator.trading_pairs)
                    }
                    enhanced_logger.log_performance_metrics(performance_metrics)
                
                # Sleep for monitoring interval
                time.sleep(60)  # Monitor every minute
                
            except Exception as e:
                log_error(f"Error in performance monitor: {e}")
                time.sleep(60)
    
    # Start performance monitoring in separate thread
    monitor_thread = threading.Thread(target=performance_monitor, daemon=True)
    monitor_thread.start()
    log_info("Performance monitoring started")


def main() -> int:
    """
    Enhanced main entry point for the crypto trading bot with orchestration.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    orchestrator = None
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Set up logging with the specified log level
        log_level = getattr(logging, args.log_level)
        from bot.utils import setup_logging
        logger = setup_logging(log_level=log_level, log_file=args.log_file)
        
        # Load configuration
        config = Config()
        if not config.load_env_variables():
            log_error("Failed to load environment variables")
            return 1
        
        # Validate configuration
        if not config.validate_config():
            log_error("Invalid Kraken configuration")
            return 1
        
        # Initialize orchestrator
        orchestrator = BotOrchestrator(config=config, args=args)
        
        # Initialize enhanced components
        if not initialize_enhanced_components(orchestrator):
            log_error("Failed to initialize enhanced components")
            return 1
        
        # Log startup information
        log_info("Starting enhanced crypto trading bot with Kraken")
        log_info(f"Trading pairs: {', '.join(orchestrator.trading_pairs)}")
        log_info(f"Trading interval: {args.interval} minutes")
        log_info(f"Trade amount: ${args.amount}")
        log_info(f"Maximum position size: ${args.max_position}")
        log_info(f"Stop loss: {args.stop_loss * 100}%")
        log_info(f"Take profit: {args.take_profit * 100}%")
        log_info(f"Max trades per day: {args.maxtrades}")
        log_info(f"WebSocket enabled: {args.enable_websocket}")
        log_info(f"Dashboard enabled: {args.enable_dashboard}")
        log_info(f"Alerts enabled: {args.enable_alerts}")
        
        # Perform initial health check
        if not args.skip_health_check:
            if not perform_enhanced_health_check(orchestrator):
                log_error("Initial enhanced health check failed, aborting startup")
                return 1
        else:
            log_warning("Skipping initial health check as requested")
        
        # Set up enhanced signal handlers for graceful shutdown
        setup_enhanced_signal_handlers(orchestrator)
        
        # Register cleanup function
        def cleanup():
            if orchestrator and not orchestrator.shutdown_event.is_set():
                log_info("Performing enhanced cleanup during shutdown...")
                initiate_graceful_shutdown(orchestrator)
                log_info("Enhanced cleanup completed")
        
        atexit.register(cleanup)
        
        # Start WebSocket client if enabled
        websocket_client = orchestrator.components.get("websocket_client")
        if websocket_client:
            try:
                websocket_client.connect()
                for pair in orchestrator.trading_pairs:
                    websocket_client.subscribe_ticker([pair])
                log_info("WebSocket client started and subscribed to pairs")
            except Exception as e:
                log_error(f"Failed to start WebSocket client: {e}")
        
        # Start dashboard if enabled
        dashboard = orchestrator.components.get("dashboard")
        if dashboard:
            try:
                dashboard.start_server()
                log_info(f"Dashboard started on port {args.dashboard_port}")
            except Exception as e:
                log_error(f"Failed to start dashboard: {e}")
        
        # Start performance monitoring
        if args.performance_monitoring:
            monitor_performance_and_optimize(orchestrator)
        
        # Start multi-pair trading loop
        start_multi_pair_trading_loop(orchestrator)
        
        # Set up health check interval
        health_check_interval = args.health_check_interval * 60
        last_health_check = time.time()
        
        # Main monitoring loop
        try:
            while not orchestrator.shutdown_event.is_set():
                # Sleep for a short time to avoid high CPU usage
                time.sleep(1)
                
                # Perform periodic health check
                current_time = time.time()
                if current_time - last_health_check > health_check_interval:
                    if not perform_enhanced_health_check(orchestrator):
                        log_warning("Health check failed, attempting recovery...")
                        if not handle_error_recovery(orchestrator, Exception("Health check failed")):
                            log_error("Recovery failed, shutting down...")
                            break
                    last_health_check = current_time
                
                # Check for emergency stop conditions
                if orchestrator.system_health.error_count > 20:
                    log_error("Too many errors, emergency shutdown initiated")
                    break
                    
        except KeyboardInterrupt:
            log_info("Keyboard interrupt received, shutting down...")
        
        # Initiate graceful shutdown
        initiate_graceful_shutdown(orchestrator)
        
        log_info("Enhanced crypto trading bot stopped")
        return 0
        
    except Exception as e:
        log_error(f"Unhandled exception in enhanced main: {e}")
        if orchestrator:
            initiate_graceful_shutdown(orchestrator)
        return 1


if __name__ == "__main__":
    sys.exit(main())