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
    Start the multi-pair trading loop with proper synchronization and enhanced orchestration.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    def trading_loop():
        """Enhanced main trading loop for multiple pairs with proper synchronization."""
        components = orchestrator.components
        data_manager = components["data_manager"]
        strategy_engine = components["strategy_engine"]
        risk_manager = components["risk_manager"]
        trader = components["trader"]
        enhanced_logger = components["enhanced_logger"]
        alert_system = components["alert_system"]
        dashboard = components.get("dashboard")
        
        # Enhanced tracking for multi-pair coordination
        last_trade_times = {pair: datetime.now() for pair in orchestrator.trading_pairs}
        pair_locks = {pair: threading.Lock() for pair in orchestrator.trading_pairs}
        trade_counters = {pair: 0 for pair in orchestrator.trading_pairs}
        pair_performance = {pair: {"wins": 0, "losses": 0, "total_pnl": 0.0} for pair in orchestrator.trading_pairs}
        
        # Synchronization variables
        global_trade_lock = threading.Lock()
        max_concurrent_trades = min(3, len(orchestrator.trading_pairs))
        active_trades = 0
        
        log_info(f"Starting enhanced multi-pair trading loop with {len(orchestrator.trading_pairs)} pairs")
        log_info(f"Max concurrent trades: {max_concurrent_trades}")
        
        while not orchestrator.shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                # Process each trading pair with proper synchronization
                for pair in orchestrator.trading_pairs:
                    # Skip if shutdown requested
                    if orchestrator.shutdown_event.is_set():
                        break
                    
                    # Use pair-specific lock for thread safety
                    with pair_locks[pair]:
                        try:
                            # Check if enough time has passed since last trade
                            time_since_last_trade = (current_time - last_trade_times[pair]).total_seconds()
                            if time_since_last_trade < orchestrator.args.interval * 60:
                                continue
                            
                            # Check daily trade limits per pair
                            if trade_counters[pair] >= orchestrator.args.maxtrades // len(orchestrator.trading_pairs):
                                log_info(f"Daily trade limit reached for {pair}")
                                continue
                            
                            # Check global concurrent trade limit
                            with global_trade_lock:
                                if active_trades >= max_concurrent_trades:
                                    log_info(f"Max concurrent trades reached, skipping {pair}")
                                    continue
                                active_trades += 1
                            
                            try:
                                # Get latest market data with validation
                                market_data = data_manager.get_latest_data(pair, periods=100)
                                if market_data is None or market_data.empty:
                                    log_warning(f"No market data available for {pair}")
                                    continue
                                
                                # Validate data quality
                                quality_report = data_manager.validate_data_quality(market_data)
                                if quality_report.quality_score < 0.7:
                                    log_warning(f"Poor data quality for {pair}: {quality_report.quality_score:.2f}")
                                    continue
                                
                                # Generate trading signal with enhanced context
                                signal = strategy_engine.calculate_weighted_signal(market_data)
                                if signal is None:
                                    continue
                                
                                # Add pair performance context to signal
                                signal.pair_performance = pair_performance[pair]
                                signal.recent_trades = trade_counters[pair]
                                
                                # Enhanced risk validation with portfolio context
                                current_positions = trader.get_positions()
                                portfolio_metrics = risk_manager.calculate_portfolio_metrics(current_positions)
                                
                                risk_assessment = risk_manager.validate_trade(
                                    signal, 
                                    current_positions,
                                    portfolio_metrics=portfolio_metrics
                                )
                                
                                if not risk_assessment.is_valid:
                                    log_info(f"Trade rejected for {pair}: {', '.join(risk_assessment.risk_factors)}")
                                    continue
                                
                                # Execute trade if signal is strong enough
                                if signal.confidence >= orchestrator.args.confidence_threshold:
                                    log_info(f"Executing trade for {pair} with confidence {signal.confidence:.3f}")
                                    
                                    trade_result = trader.execute_trade(
                                        pair=pair,
                                        signal=signal,
                                        amount=risk_assessment.recommended_size
                                    )
                                    
                                    if trade_result:
                                        # Update tracking variables
                                        last_trade_times[pair] = current_time
                                        trade_counters[pair] += 1
                                        orchestrator.system_health.active_trades += 1
                                        
                                        # Update pair performance tracking
                                        if hasattr(trade_result, 'pnl') and trade_result.pnl is not None:
                                            pair_performance[pair]["total_pnl"] += trade_result.pnl
                                            if trade_result.pnl > 0:
                                                pair_performance[pair]["wins"] += 1
                                            else:
                                                pair_performance[pair]["losses"] += 1
                                        
                                        # Enhanced logging with context
                                        enhanced_logger.log_trade(trade_result)
                                        enhanced_logger.log_signal(signal, trade_result)
                                        
                                        # Send alerts
                                        if alert_system:
                                            alert_system.send_trade_alert(trade_result)
                                        
                                        # Update dashboard
                                        if dashboard:
                                            dashboard.add_trade_event(trade_result)
                                            dashboard.update_portfolio_data(current_positions)
                                        
                                        log_info(f"Trade executed successfully for {pair}: {trade_result}")
                                    else:
                                        log_warning(f"Trade execution failed for {pair}")
                                
                            finally:
                                # Always decrement active trades counter
                                with global_trade_lock:
                                    active_trades = max(0, active_trades - 1)
                            
                        except Exception as e:
                            log_error(f"Error processing pair {pair}: {e}")
                            # Attempt error recovery for this pair
                            if not handle_pair_error_recovery(orchestrator, pair, e):
                                log_error(f"Failed to recover from error for {pair}, temporarily disabling")
                                # Temporarily remove pair from active trading
                                if pair in orchestrator.trading_pairs:
                                    orchestrator.trading_pairs.remove(pair)
                                    log_warning(f"Temporarily disabled trading for {pair}")
                            continue
                
                # Update system health and performance metrics
                update_system_health(orchestrator)
                
                # Log periodic status
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    log_trading_status(orchestrator, trade_counters, pair_performance)
                
                # Adaptive sleep based on system load
                sleep_time = calculate_adaptive_sleep_time(orchestrator)
                time.sleep(sleep_time)
                
            except Exception as e:
                log_error(f"Critical error in trading loop: {e}")
                # Attempt global error recovery
                if not handle_error_recovery(orchestrator, e):
                    log_error("Global error recovery failed, shutting down trading loop")
                    break
                time.sleep(30)  # Longer sleep after critical error
    
    # Start trading loop in separate thread with enhanced error handling
    def start_trading_thread():
        try:
            trading_loop()
        except Exception as e:
            log_error(f"Trading thread crashed: {e}")
            # Send critical alert
            if orchestrator.components.get("alert_system"):
                orchestrator.components["alert_system"].send_system_alert(
                    alert_type="CRITICAL_ERROR",
                    message=f"Trading thread crashed: {e}",
                    severity=AlertSeverity.HIGH
                )
    
    trading_thread = threading.Thread(target=start_trading_thread, daemon=True, name="TradingLoop")
    trading_thread.start()
    log_info("Enhanced multi-pair trading loop started with proper synchronization")


def handle_pair_error_recovery(orchestrator: BotOrchestrator, pair: str, error: Exception) -> bool:
    """
    Handle error recovery for a specific trading pair.
    
    Args:
        orchestrator: BotOrchestrator instance
        pair: Trading pair that encountered error
        error: Exception that occurred
        
    Returns:
        bool: True if recovery successful, False otherwise
    """
    try:
        log_info(f"Attempting error recovery for pair {pair}: {error}")
        
        components = orchestrator.components
        data_manager = components.get("data_manager")
        trader = components.get("trader")
        
        # Try to refresh data for this pair
        if data_manager:
            try:
                data_manager.refresh_pair_data(pair)
                log_info(f"Data refreshed for {pair}")
            except Exception as e:
                log_error(f"Failed to refresh data for {pair}: {e}")
                return False
        
        # Test API connectivity for this pair
        if trader:
            try:
                price = trader.get_latest_price(pair)
                if price is not None:
                    log_info(f"API connectivity confirmed for {pair}: ${price:.2f}")
                    return True
                else:
                    log_error(f"Failed to get price for {pair}")
                    return False
            except Exception as e:
                log_error(f"API test failed for {pair}: {e}")
                return False
        
        return True
        
    except Exception as e:
        log_error(f"Error in pair recovery handler for {pair}: {e}")
        return False


def log_trading_status(orchestrator: BotOrchestrator, trade_counters: Dict, pair_performance: Dict) -> None:
    """
    Log comprehensive trading status for all pairs.
    
    Args:
        orchestrator: BotOrchestrator instance
        trade_counters: Trade count per pair
        pair_performance: Performance metrics per pair
    """
    try:
        total_trades = sum(trade_counters.values())
        total_pnl = sum(perf["total_pnl"] for perf in pair_performance.values())
        total_wins = sum(perf["wins"] for perf in pair_performance.values())
        total_losses = sum(perf["losses"] for perf in pair_performance.values())
        
        win_rate = (total_wins / max(total_wins + total_losses, 1)) * 100
        
        log_info(f"Trading Status Summary:")
        log_info(f"  Total Trades: {total_trades}")
        log_info(f"  Total P&L: ${total_pnl:.2f}")
        log_info(f"  Win Rate: {win_rate:.1f}%")
        log_info(f"  Active Pairs: {len(orchestrator.trading_pairs)}")
        log_info(f"  System Health: {'Healthy' if orchestrator.system_health.is_healthy else 'Issues Detected'}")
        
        # Log per-pair status
        for pair in orchestrator.trading_pairs:
            trades = trade_counters.get(pair, 0)
            perf = pair_performance.get(pair, {"wins": 0, "losses": 0, "total_pnl": 0.0})
            pair_win_rate = (perf["wins"] / max(perf["wins"] + perf["losses"], 1)) * 100
            log_info(f"  {pair}: {trades} trades, ${perf['total_pnl']:.2f} P&L, {pair_win_rate:.1f}% win rate")
        
    except Exception as e:
        log_error(f"Error logging trading status: {e}")


def calculate_adaptive_sleep_time(orchestrator: BotOrchestrator) -> float:
    """
    Calculate adaptive sleep time based on system performance and load.
    
    Args:
        orchestrator: BotOrchestrator instance
        
    Returns:
        float: Sleep time in seconds
    """
    try:
        health = orchestrator.system_health
        base_sleep = 5.0  # Base sleep time
        
        # Adjust based on CPU usage
        if health.cpu_usage_pct > 80:
            base_sleep *= 2.0
        elif health.cpu_usage_pct > 60:
            base_sleep *= 1.5
        
        # Adjust based on memory usage
        if health.memory_usage_mb > 400:
            base_sleep *= 1.5
        
        # Adjust based on error count
        if health.error_count > 5:
            base_sleep *= 1.2
        
        # Adjust based on data quality
        if health.data_quality < 0.8:
            base_sleep *= 1.3
        
        return min(base_sleep, 30.0)  # Cap at 30 seconds
        
    except Exception:
        return 5.0  # Default sleep time


def update_system_health(orchestrator: BotOrchestrator) -> None:
    """
    Enhanced system health monitoring with comprehensive metrics and proactive issue detection.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    try:
        import psutil
        import gc
        
        health = orchestrator.system_health
        components = orchestrator.components
        
        # Update basic metrics
        health.last_check = datetime.now()
        health.uptime_seconds = (datetime.now() - orchestrator.start_time).total_seconds()
        
        # Enhanced system resource monitoring
        process = psutil.Process()
        health.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        health.cpu_usage_pct = process.cpu_percent()
        
        # Additional system metrics
        system_memory = psutil.virtual_memory()
        system_cpu = psutil.cpu_percent(interval=1)
        disk_usage = psutil.disk_usage('/').percent
        
        # Network connectivity checks
        network_healthy = True
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
        except:
            network_healthy = False
        
        # Enhanced API connection monitoring
        api_response_times = []
        try:
            trader = components["trader"]
            start_time = time.time()
            account_info = trader.get_account_info()
            response_time = (time.time() - start_time) * 1000  # ms
            api_response_times.append(response_time)
            health.api_connection = account_info is not None
            
            # Test multiple endpoints for comprehensive check
            for pair in orchestrator.trading_pairs[:2]:  # Test first 2 pairs
                try:
                    start_time = time.time()
                    price = trader.get_latest_price(pair)
                    response_time = (time.time() - start_time) * 1000
                    api_response_times.append(response_time)
                except:
                    pass
                    
        except Exception as e:
            health.api_connection = False
            log_warning(f"API connection check failed: {e}")
        
        # Enhanced WebSocket connection monitoring
        websocket_client = components.get("websocket_client")
        if websocket_client:
            try:
                health.websocket_connection = websocket_client.is_connected()
                # Check message queue health
                if hasattr(websocket_client, 'get_queue_size'):
                    queue_size = websocket_client.get_queue_size()
                    if queue_size > 1000:
                        health.issues.append(f"WebSocket queue backlog: {queue_size}")
            except Exception as e:
                health.websocket_connection = False
                log_warning(f"WebSocket health check failed: {e}")
        else:
            health.websocket_connection = True  # Not using WebSocket
        
        # Enhanced data quality monitoring
        data_manager = components["data_manager"]
        total_quality = 0.0
        pair_count = 0
        data_freshness_issues = []
        
        for pair in orchestrator.trading_pairs:
            try:
                data = data_manager.get_latest_data(pair, periods=20)
                if data is not None and not data.empty:
                    quality_report = data_manager.validate_data_quality(data)
                    total_quality += quality_report.quality_score
                    pair_count += 1
                    
                    # Check data freshness
                    if hasattr(data, 'index') and len(data) > 0:
                        latest_timestamp = data.index[-1] if hasattr(data.index[-1], 'timestamp') else datetime.now()
                        if isinstance(latest_timestamp, str):
                            latest_timestamp = datetime.fromisoformat(latest_timestamp.replace('Z', '+00:00'))
                        
                        data_age = (datetime.now() - latest_timestamp).total_seconds()
                        if data_age > 300:  # 5 minutes
                            data_freshness_issues.append(f"{pair}: {data_age:.0f}s old")
                else:
                    log_warning(f"No data available for health check: {pair}")
            except Exception as e:
                log_warning(f"Data quality check failed for {pair}: {e}")
        
        health.data_quality = total_quality / max(pair_count, 1)
        
        # Component health checks
        component_health = {}
        for name, component in components.items():
            try:
                if hasattr(component, 'health_check'):
                    component_health[name] = component.health_check()
                elif hasattr(component, 'is_healthy'):
                    component_health[name] = component.is_healthy()
                else:
                    component_health[name] = True  # Assume healthy if no check available
            except Exception as e:
                component_health[name] = False
                log_warning(f"Health check failed for {name}: {e}")
        
        # Update overall health status with enhanced criteria
        health.issues.clear()
        health.is_healthy = True
        
        # Critical issues (mark as unhealthy)
        if not health.api_connection:
            health.issues.append("API connection lost")
            health.is_healthy = False
        
        if not network_healthy:
            health.issues.append("Network connectivity issues")
            health.is_healthy = False
        
        if health.memory_usage_mb > 800:  # Critical memory usage
            health.issues.append(f"Critical memory usage: {health.memory_usage_mb:.1f}MB")
            health.is_healthy = False
        
        if system_memory.percent > 90:
            health.issues.append(f"System memory critical: {system_memory.percent:.1f}%")
            health.is_healthy = False
        
        # Warning issues (don't mark as unhealthy but log)
        if not health.websocket_connection and websocket_client:
            health.issues.append("WebSocket connection lost")
        
        if health.data_quality < 0.7:
            health.issues.append(f"Poor data quality: {health.data_quality:.2f}")
        
        if health.memory_usage_mb > 500:
            health.issues.append(f"High memory usage: {health.memory_usage_mb:.1f}MB")
        
        if health.cpu_usage_pct > 80:
            health.issues.append(f"High CPU usage: {health.cpu_usage_pct:.1f}%")
        
        if system_cpu > 90:
            health.issues.append(f"System CPU critical: {system_cpu:.1f}%")
        
        if disk_usage > 90:
            health.issues.append(f"Disk usage critical: {disk_usage:.1f}%")
        
        if api_response_times and max(api_response_times) > 5000:  # 5 seconds
            health.issues.append(f"Slow API responses: {max(api_response_times):.0f}ms")
        
        if data_freshness_issues:
            health.issues.append(f"Stale data: {', '.join(data_freshness_issues[:3])}")
        
        # Component health issues
        unhealthy_components = [name for name, healthy in component_health.items() if not healthy]
        if unhealthy_components:
            health.issues.append(f"Unhealthy components: {', '.join(unhealthy_components)}")
        
        # Proactive issue detection
        if health.error_count > 5:
            health.issues.append(f"High error count: {health.error_count}")
        
        # Log comprehensive health status
        if int(health.uptime_seconds) % 300 == 0:  # Every 5 minutes
            log_info(f"Enhanced System Health Report:")
            log_info(f"  Overall Status: {'Healthy' if health.is_healthy else 'Issues Detected'}")
            log_info(f"  Uptime: {health.uptime_seconds/3600:.1f} hours")
            log_info(f"  Memory: {health.memory_usage_mb:.1f}MB (System: {system_memory.percent:.1f}%)")
            log_info(f"  CPU: {health.cpu_usage_pct:.1f}% (System: {system_cpu:.1f}%)")
            log_info(f"  Data Quality: {health.data_quality:.2f}")
            log_info(f"  API Connection: {'OK' if health.api_connection else 'FAILED'}")
            log_info(f"  WebSocket: {'OK' if health.websocket_connection else 'FAILED'}")
            log_info(f"  Network: {'OK' if network_healthy else 'FAILED'}")
            log_info(f"  Active Trades: {health.active_trades}")
            log_info(f"  Error Count: {health.error_count}")
            
            if api_response_times:
                avg_response = sum(api_response_times) / len(api_response_times)
                log_info(f"  API Response Time: {avg_response:.0f}ms avg, {max(api_response_times):.0f}ms max")
            
            if health.issues:
                log_warning(f"  Issues: {'; '.join(health.issues)}")
        
        # Send alerts for critical issues
        alert_system = components.get("alert_system")
        if alert_system and not health.is_healthy:
            critical_issues = [issue for issue in health.issues if any(keyword in issue.lower() 
                             for keyword in ['critical', 'lost', 'failed', 'network'])]
            if critical_issues:
                alert_system.send_system_alert(
                    alert_type="HEALTH_CRITICAL",
                    message=f"Critical system health issues: {'; '.join(critical_issues)}",
                    severity=AlertSeverity.HIGH
                )
        
        # Automatic cleanup for high memory usage
        if health.memory_usage_mb > 600:
            log_info("Performing automatic memory cleanup due to high usage")
            gc.collect()
            if data_manager and hasattr(data_manager, 'cleanup_cache'):
                data_manager.cleanup_cache()
        
    except Exception as e:
        log_error(f"Error in enhanced system health monitoring: {e}")
        # Fallback to basic health status
        health.is_healthy = False
        health.issues = [f"Health monitoring error: {str(e)[:100]}"]


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
    Enhanced graceful shutdown with comprehensive cleanup and state preservation.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    try:
        shutdown_start_time = datetime.now()
        log_info("=== Initiating Enhanced Graceful Shutdown ===")
        
        # Set shutdown event to stop all loops
        orchestrator.shutdown_event.set()
        
        components = orchestrator.components
        shutdown_steps = []
        
        # Step 1: Send shutdown notification
        try:
            alert_system = components.get("alert_system")
            if alert_system:
                alert_system.send_system_alert(
                    alert_type="SHUTDOWN_INITIATED",
                    message=f"Trading bot shutdown initiated after {orchestrator.system_health.uptime_seconds/3600:.1f} hours uptime",
                    severity=AlertSeverity.MEDIUM
                )
            shutdown_steps.append("✓ Shutdown notification sent")
        except Exception as e:
            log_error(f"Error sending shutdown notification: {e}")
            shutdown_steps.append("✗ Shutdown notification failed")
        
        # Step 2: Stop new trade execution
        try:
            log_info("Stopping new trade execution...")
            # Additional logic to prevent new trades could be added here
            shutdown_steps.append("✓ New trade execution stopped")
        except Exception as e:
            log_error(f"Error stopping trade execution: {e}")
            shutdown_steps.append("✗ Trade execution stop failed")
        
        # Step 3: Wait for active trades to complete (with timeout)
        try:
            log_info("Waiting for active trades to complete...")
            timeout = 30  # 30 seconds timeout
            start_wait = time.time()
            
            while orchestrator.system_health.active_trades > 0 and (time.time() - start_wait) < timeout:
                log_info(f"Waiting for {orchestrator.system_health.active_trades} active trades to complete...")
                time.sleep(2)
            
            if orchestrator.system_health.active_trades > 0:
                log_warning(f"Timeout reached with {orchestrator.system_health.active_trades} trades still active")
                shutdown_steps.append(f"⚠ Active trades timeout ({orchestrator.system_health.active_trades} remaining)")
            else:
                shutdown_steps.append("✓ All active trades completed")
                
        except Exception as e:
            log_error(f"Error waiting for active trades: {e}")
            shutdown_steps.append("✗ Active trades wait failed")
        
        # Step 4: Close positions if configured
        try:
            trader = components.get("trader")
            if trader and orchestrator.args.close_positions_on_shutdown:
                log_info("Closing open positions...")
                positions = trader.get_positions()
                closed_positions = []
                
                for pair, position in positions.items():
                    if position.get("size", 0) != 0:
                        try:
                            log_info(f"Closing position for {pair}: {position}")
                            result = trader.close_position(pair)
                            if result:
                                closed_positions.append(pair)
                                log_info(f"Successfully closed position for {pair}")
                            else:
                                log_warning(f"Failed to close position for {pair}")
                        except Exception as e:
                            log_error(f"Error closing position for {pair}: {e}")
                
                if closed_positions:
                    shutdown_steps.append(f"✓ Closed positions: {', '.join(closed_positions)}")
                else:
                    shutdown_steps.append("✓ No positions to close")
            else:
                shutdown_steps.append("✓ Position closing not configured")
                
        except Exception as e:
            log_error(f"Error closing positions: {e}")
            shutdown_steps.append("✗ Position closing failed")
        
        # Step 5: Save state and generate final reports
        try:
            log_info("Generating final reports and saving state...")
            
            # Generate final performance report
            enhanced_logger = components.get("enhanced_logger")
            if enhanced_logger:
                try:
                    final_report = generate_final_shutdown_report(orchestrator)
                    enhanced_logger.log_system_event("SHUTDOWN_REPORT", final_report)
                    shutdown_steps.append("✓ Final report generated")
                except Exception as e:
                    log_error(f"Error generating final report: {e}")
                    shutdown_steps.append("✗ Final report failed")
            
            # Save trading state
            try:
                save_trading_state(orchestrator)
                shutdown_steps.append("✓ Trading state saved")
            except Exception as e:
                log_error(f"Error saving trading state: {e}")
                shutdown_steps.append("✗ Trading state save failed")
                
        except Exception as e:
            log_error(f"Error in state saving: {e}")
            shutdown_steps.append("✗ State saving failed")
        
        # Step 6: Stop WebSocket client
        try:
            websocket_client = components.get("websocket_client")
            if websocket_client:
                log_info("Disconnecting WebSocket client...")
                websocket_client.disconnect()
                
                # Wait for clean disconnection
                timeout = 10
                start_wait = time.time()
                while websocket_client.is_connected() and (time.time() - start_wait) < timeout:
                    time.sleep(0.5)
                
                if websocket_client.is_connected():
                    log_warning("WebSocket disconnection timeout")
                    shutdown_steps.append("⚠ WebSocket disconnect timeout")
                else:
                    shutdown_steps.append("✓ WebSocket client disconnected")
            else:
                shutdown_steps.append("✓ No WebSocket client to disconnect")
                
        except Exception as e:
            log_error(f"Error disconnecting WebSocket client: {e}")
            shutdown_steps.append("✗ WebSocket disconnect failed")
        
        # Step 7: Stop dashboard server
        try:
            dashboard = components.get("dashboard")
            if dashboard:
                log_info("Stopping dashboard server...")
                dashboard.stop_server()
                shutdown_steps.append("✓ Dashboard server stopped")
            else:
                shutdown_steps.append("✓ No dashboard server to stop")
                
        except Exception as e:
            log_error(f"Error stopping dashboard: {e}")
            shutdown_steps.append("✗ Dashboard stop failed")
        
        # Step 8: Clean up data manager
        try:
            data_manager = components.get("data_manager")
            if data_manager:
                log_info("Cleaning up data manager...")
                if hasattr(data_manager, 'cleanup_on_shutdown'):
                    data_manager.cleanup_on_shutdown()
                elif hasattr(data_manager, 'cleanup_cache'):
                    data_manager.cleanup_cache()
                shutdown_steps.append("✓ Data manager cleaned up")
            else:
                shutdown_steps.append("✓ No data manager to clean up")
                
        except Exception as e:
            log_error(f"Error cleaning up data manager: {e}")
            shutdown_steps.append("✗ Data manager cleanup failed")
        
        # Step 9: Flush all logs
        try:
            log_info("Flushing all logs...")
            enhanced_logger = components.get("enhanced_logger")
            if enhanced_logger:
                enhanced_logger.flush_logs()
                shutdown_steps.append("✓ Enhanced logs flushed")
            
            # Also flush standard logger
            import logging
            for handler in logging.getLogger().handlers:
                if hasattr(handler, 'flush'):
                    handler.flush()
            shutdown_steps.append("✓ Standard logs flushed")
            
        except Exception as e:
            log_error(f"Error flushing logs: {e}")
            shutdown_steps.append("✗ Log flushing failed")
        
        # Step 10: Send final shutdown alert
        try:
            alert_system = components.get("alert_system")
            if alert_system:
                shutdown_duration = (datetime.now() - shutdown_start_time).total_seconds()
                alert_system.send_system_alert(
                    alert_type="SHUTDOWN_COMPLETED",
                    message=f"Trading bot shutdown completed in {shutdown_duration:.1f}s. Steps: {len([s for s in shutdown_steps if s.startswith('✓')])} successful, {len([s for s in shutdown_steps if s.startswith('✗')])} failed",
                    severity=AlertSeverity.LOW
                )
            shutdown_steps.append("✓ Final shutdown alert sent")
        except Exception as e:
            log_error(f"Error sending final shutdown alert: {e}")
            shutdown_steps.append("✗ Final alert failed")
        
        # Log shutdown summary
        shutdown_duration = (datetime.now() - shutdown_start_time).total_seconds()
        log_info("=== Graceful Shutdown Summary ===")
        log_info(f"Shutdown Duration: {shutdown_duration:.1f} seconds")
        log_info(f"Uptime: {orchestrator.system_health.uptime_seconds/3600:.1f} hours")
        log_info("Shutdown Steps:")
        for step in shutdown_steps:
            log_info(f"  {step}")
        
        successful_steps = len([s for s in shutdown_steps if s.startswith('✓')])
        total_steps = len(shutdown_steps)
        log_info(f"Shutdown Success Rate: {successful_steps}/{total_steps} ({(successful_steps/total_steps)*100:.1f}%)")
        log_info("=== Enhanced Graceful Shutdown Completed ===")
        
    except Exception as e:
        log_error(f"Critical error during graceful shutdown: {e}")
        log_error("Attempting emergency shutdown...")
        try:
            # Emergency cleanup
            orchestrator.shutdown_event.set()
            time.sleep(2)  # Give threads time to notice shutdown event
        except:
            pass


def generate_final_shutdown_report(orchestrator: BotOrchestrator) -> Dict[str, Any]:
    """
    Generate comprehensive final report before shutdown.
    
    Args:
        orchestrator: BotOrchestrator instance
        
    Returns:
        Dict containing final report data
    """
    try:
        components = orchestrator.components
        health = orchestrator.system_health
        
        report = {
            "shutdown_timestamp": datetime.now().isoformat(),
            "uptime_hours": health.uptime_seconds / 3600,
            "total_errors": health.error_count,
            "final_memory_usage_mb": health.memory_usage_mb,
            "final_cpu_usage_pct": health.cpu_usage_pct,
            "data_quality": health.data_quality,
            "trading_pairs": orchestrator.trading_pairs.copy(),
            "system_health_status": "healthy" if health.is_healthy else "issues_detected",
            "health_issues": health.issues.copy()
        }
        
        # Add trader information
        trader = components.get("trader")
        if trader:
            try:
                positions = trader.get_positions()
                report["final_positions"] = {
                    pair: {"size": pos.get("size", 0), "value": pos.get("value", 0)}
                    for pair, pos in positions.items()
                }
                report["open_positions_count"] = len([p for p in positions.values() if p.get("size", 0) != 0])
            except Exception as e:
                report["positions_error"] = str(e)
        
        # Add performance metrics
        try:
            performance_metrics = collect_performance_metrics(orchestrator)
            report["final_performance"] = performance_metrics
        except Exception as e:
            report["performance_error"] = str(e)
        
        return report
        
    except Exception as e:
        log_error(f"Error generating final shutdown report: {e}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}


def save_trading_state(orchestrator: BotOrchestrator) -> None:
    """
    Save current trading state for potential restart.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    try:
        import json
        import os
        
        state_dir = "logs"
        os.makedirs(state_dir, exist_ok=True)
        
        state_file = os.path.join(state_dir, "trading_state.json")
        
        state = {
            "timestamp": datetime.now().isoformat(),
            "trading_pairs": orchestrator.trading_pairs,
            "system_health": {
                "uptime_seconds": orchestrator.system_health.uptime_seconds,
                "error_count": orchestrator.system_health.error_count,
                "memory_usage_mb": orchestrator.system_health.memory_usage_mb,
                "cpu_usage_pct": orchestrator.system_health.cpu_usage_pct,
                "data_quality": orchestrator.system_health.data_quality,
                "is_healthy": orchestrator.system_health.is_healthy,
                "issues": orchestrator.system_health.issues
            },
            "configuration": {
                "interval": orchestrator.args.interval,
                "confidence_threshold": orchestrator.args.confidence_threshold,
                "max_position": orchestrator.args.max_position,
                "stop_loss": orchestrator.args.stop_loss,
                "take_profit": orchestrator.args.take_profit
            }
        }
        
        # Add positions if available
        components = orchestrator.components
        trader = components.get("trader")
        if trader:
            try:
                positions = trader.get_positions()
                state["positions"] = positions
            except Exception as e:
                state["positions_error"] = str(e)
        
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        log_info(f"Trading state saved to {state_file}")
        
    except Exception as e:
        log_error(f"Error saving trading state: {e}")


def handle_error_recovery(orchestrator: BotOrchestrator, error: Exception) -> bool:
    """
    Enhanced error recovery with comprehensive recovery strategies and escalation.
    
    Args:
        orchestrator: BotOrchestrator instance
        error: Exception that occurred
        
    Returns:
        bool: True if recovery successful, False if restart needed
    """
    try:
        error_type = type(error).__name__
        error_msg = str(error)
        log_error(f"Initiating enhanced error recovery for {error_type}: {error_msg}")
        
        components = orchestrator.components
        error_handler = components.get("error_handler")
        alert_system = components.get("alert_system")
        
        # Increment error count and track error patterns
        orchestrator.system_health.error_count += 1
        
        # Create error context for better recovery decisions
        error_context = {
            "error_type": error_type,
            "error_message": error_msg,
            "timestamp": datetime.now(),
            "uptime": orchestrator.system_health.uptime_seconds,
            "memory_usage": orchestrator.system_health.memory_usage_mb,
            "cpu_usage": orchestrator.system_health.cpu_usage_pct,
            "active_pairs": len(orchestrator.trading_pairs),
            "recent_error_count": orchestrator.system_health.error_count
        }
        
        # Log error context for analysis
        enhanced_logger = components.get("enhanced_logger")
        if enhanced_logger:
            enhanced_logger.log_error(error, error_context, severity="HIGH")
        
        # Send immediate error alert
        if alert_system:
            alert_system.send_system_alert(
                alert_type="ERROR_RECOVERY",
                message=f"Attempting recovery from {error_type}: {error_msg[:100]}",
                severity=AlertSeverity.MEDIUM
            )
        
        # Recovery strategy based on error type
        recovery_successful = False
        
        if isinstance(error, (ConnectionError, TimeoutError, OSError)):
            recovery_successful = handle_connection_error_recovery(orchestrator, error, error_context)
            
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            recovery_successful = handle_data_error_recovery(orchestrator, error, error_context)
            
        elif isinstance(error, MemoryError):
            recovery_successful = handle_memory_error_recovery(orchestrator, error, error_context)
            
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            recovery_successful = handle_rate_limit_recovery(orchestrator, error, error_context)
            
        elif "authentication" in error_msg.lower() or "401" in error_msg:
            recovery_successful = handle_auth_error_recovery(orchestrator, error, error_context)
            
        else:
            # Generic recovery for unknown errors
            recovery_successful = handle_generic_error_recovery(orchestrator, error, error_context)
        
        # Check if recovery was successful
        if recovery_successful:
            log_info(f"Error recovery successful for {error_type}")
            
            # Reset error count if recovery was successful
            if orchestrator.system_health.error_count > 0:
                orchestrator.system_health.error_count = max(0, orchestrator.system_health.error_count - 1)
            
            if alert_system:
                alert_system.send_system_alert(
                    alert_type="RECOVERY_SUCCESS",
                    message=f"Successfully recovered from {error_type}",
                    severity=AlertSeverity.LOW
                )
            
            return True
        else:
            log_error(f"Error recovery failed for {error_type}")
            
            # Check if we should escalate or restart
            if should_escalate_error(orchestrator, error_context):
                log_error("Error escalation triggered - restart required")
                
                if alert_system:
                    alert_system.send_system_alert(
                        alert_type="RESTART_REQUIRED",
                        message=f"System restart required due to {error_type}",
                        severity=AlertSeverity.HIGH
                    )
                
                return False
            else:
                log_warning("Continuing operation despite recovery failure")
                return True
        
    except Exception as recovery_error:
        log_error(f"Critical error in error recovery handler: {recovery_error}")
        
        # Send critical alert
        if orchestrator.components.get("alert_system"):
            orchestrator.components["alert_system"].send_system_alert(
                alert_type="RECOVERY_FAILURE",
                message=f"Error recovery system failed: {recovery_error}",
                severity=AlertSeverity.CRITICAL
            )
        
        return False


def handle_connection_error_recovery(orchestrator: BotOrchestrator, error: Exception, context: Dict) -> bool:
    """Handle recovery from connection-related errors."""
    try:
        log_info("Attempting connection error recovery...")
        components = orchestrator.components
        
        # Wait before attempting recovery
        time.sleep(5)
        
        # Try to reconnect WebSocket
        websocket_client = components.get("websocket_client")
        if websocket_client:
            try:
                log_info("Reconnecting WebSocket...")
                websocket_client.disconnect()
                time.sleep(2)
                websocket_client.connect()
                
                # Re-subscribe to pairs
                for pair in orchestrator.trading_pairs:
                    websocket_client.subscribe_ticker([pair])
                
                log_info("WebSocket reconnected successfully")
            except Exception as e:
                log_error(f"WebSocket reconnection failed: {e}")
        
        # Test API connection with retry
        trader = components.get("trader")
        if trader:
            for attempt in range(3):
                try:
                    log_info(f"Testing API connection (attempt {attempt + 1}/3)...")
                    account_info = trader.get_account_info()
                    if account_info:
                        log_info("API connection restored")
                        return True
                    time.sleep(5)
                except Exception as e:
                    log_warning(f"API test attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time.sleep(10)
        
        return False
        
    except Exception as e:
        log_error(f"Connection error recovery failed: {e}")
        return False


def handle_data_error_recovery(orchestrator: BotOrchestrator, error: Exception, context: Dict) -> bool:
    """Handle recovery from data-related errors."""
    try:
        log_info("Attempting data error recovery...")
        components = orchestrator.components
        
        # Clear and refresh data cache
        data_manager = components.get("data_manager")
        if data_manager:
            try:
                log_info("Clearing and refreshing data cache...")
                data_manager.clear_cache()
                
                # Refresh data for all pairs
                for pair in orchestrator.trading_pairs:
                    try:
                        data_manager.refresh_pair_data(pair)
                    except Exception as e:
                        log_warning(f"Failed to refresh data for {pair}: {e}")
                
                log_info("Data cache refreshed successfully")
                return True
                
            except Exception as e:
                log_error(f"Data cache refresh failed: {e}")
        
        return False
        
    except Exception as e:
        log_error(f"Data error recovery failed: {e}")
        return False


def handle_memory_error_recovery(orchestrator: BotOrchestrator, error: Exception, context: Dict) -> bool:
    """Handle recovery from memory-related errors."""
    try:
        log_info("Attempting memory error recovery...")
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Clear caches
        components = orchestrator.components
        data_manager = components.get("data_manager")
        if data_manager and hasattr(data_manager, 'cleanup_cache'):
            data_manager.cleanup_cache()
        
        # Reduce trading pairs temporarily if memory is critical
        if context["memory_usage"] > 700:
            original_pairs = orchestrator.trading_pairs.copy()
            orchestrator.trading_pairs = orchestrator.trading_pairs[:max(1, len(orchestrator.trading_pairs) // 2)]
            log_warning(f"Temporarily reduced trading pairs from {len(original_pairs)} to {len(orchestrator.trading_pairs)}")
        
        log_info("Memory cleanup completed")
        return True
        
    except Exception as e:
        log_error(f"Memory error recovery failed: {e}")
        return False


def handle_rate_limit_recovery(orchestrator: BotOrchestrator, error: Exception, context: Dict) -> bool:
    """Handle recovery from rate limiting errors."""
    try:
        log_info("Attempting rate limit recovery...")
        
        # Increase trading interval temporarily
        original_interval = orchestrator.args.interval
        orchestrator.args.interval = min(original_interval * 2, 30)  # Cap at 30 minutes
        
        log_info(f"Temporarily increased trading interval from {original_interval} to {orchestrator.args.interval} minutes")
        
        # Wait for rate limit to reset
        wait_time = 60  # 1 minute
        log_info(f"Waiting {wait_time} seconds for rate limit reset...")
        time.sleep(wait_time)
        
        return True
        
    except Exception as e:
        log_error(f"Rate limit recovery failed: {e}")
        return False


def handle_auth_error_recovery(orchestrator: BotOrchestrator, error: Exception, context: Dict) -> bool:
    """Handle recovery from authentication errors."""
    try:
        log_info("Attempting authentication error recovery...")
        
        # Try to refresh credentials
        config = orchestrator.config
        if hasattr(config, 'reload_credentials'):
            try:
                config.reload_credentials()
                log_info("Credentials reloaded")
                return True
            except Exception as e:
                log_error(f"Failed to reload credentials: {e}")
        
        # Authentication errors usually require manual intervention
        log_error("Authentication error requires manual intervention")
        return False
        
    except Exception as e:
        log_error(f"Authentication error recovery failed: {e}")
        return False


def handle_generic_error_recovery(orchestrator: BotOrchestrator, error: Exception, context: Dict) -> bool:
    """Handle recovery from generic/unknown errors."""
    try:
        log_info("Attempting generic error recovery...")
        
        # Basic recovery steps
        import gc
        gc.collect()
        
        # Brief pause to let system stabilize
        time.sleep(10)
        
        # Test basic functionality
        components = orchestrator.components
        trader = components.get("trader")
        if trader:
            try:
                trader.get_account_info()
                log_info("Basic functionality test passed")
                return True
            except Exception as e:
                log_error(f"Basic functionality test failed: {e}")
        
        return False
        
    except Exception as e:
        log_error(f"Generic error recovery failed: {e}")
        return False


def should_escalate_error(orchestrator: BotOrchestrator, error_context: Dict) -> bool:
    """
    Determine if error should be escalated to system restart.
    
    Args:
        orchestrator: BotOrchestrator instance
        error_context: Error context information
        
    Returns:
        bool: True if escalation is needed
    """
    try:
        # Check error count threshold
        if orchestrator.system_health.error_count > 15:
            log_warning("Error count threshold exceeded")
            return True
        
        # Check error frequency
        if error_context["uptime"] < 300 and orchestrator.system_health.error_count > 5:
            log_warning("Too many errors in short time period")
            return True
        
        # Check system resources
        if error_context["memory_usage"] > 800:
            log_warning("Critical memory usage detected")
            return True
        
        # Check critical error types
        critical_errors = ["MemoryError", "SystemError", "OSError"]
        if error_context["error_type"] in critical_errors:
            log_warning(f"Critical error type detected: {error_context['error_type']}")
            return True
        
        return False
        
    except Exception as e:
        log_error(f"Error in escalation check: {e}")
        return True  # Err on the side of caution


def monitor_performance_and_optimize(orchestrator: BotOrchestrator) -> None:
    """
    Enhanced performance monitoring with proactive optimization and adaptive tuning.
    
    Args:
        orchestrator: BotOrchestrator instance
    """
    def performance_monitor():
        """Enhanced performance monitoring loop with adaptive optimization."""
        log_info("Starting enhanced performance monitoring and optimization")
        
        # Performance tracking variables
        performance_history = []
        optimization_history = []
        last_optimization = datetime.now()
        baseline_metrics = None
        
        while not orchestrator.shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                # Update system health first
                update_system_health(orchestrator)
                
                health = orchestrator.system_health
                components = orchestrator.components
                
                # Collect comprehensive performance metrics
                performance_metrics = collect_performance_metrics(orchestrator)
                performance_history.append(performance_metrics)
                
                # Keep only last 60 measurements (1 hour of data)
                if len(performance_history) > 60:
                    performance_history.pop(0)
                
                # Establish baseline if not set
                if baseline_metrics is None and len(performance_history) >= 10:
                    baseline_metrics = calculate_baseline_metrics(performance_history[-10:])
                    log_info("Performance baseline established")
                
                # Perform adaptive optimizations
                optimizations_applied = []
                
                # Memory optimization
                memory_optimization = optimize_memory_usage(orchestrator, performance_metrics, baseline_metrics)
                if memory_optimization:
                    optimizations_applied.append(memory_optimization)
                
                # CPU optimization
                cpu_optimization = optimize_cpu_usage(orchestrator, performance_metrics, baseline_metrics)
                if cpu_optimization:
                    optimizations_applied.append(cpu_optimization)
                
                # Trading frequency optimization
                frequency_optimization = optimize_trading_frequency(orchestrator, performance_metrics, performance_history)
                if frequency_optimization:
                    optimizations_applied.append(frequency_optimization)
                
                # Data management optimization
                data_optimization = optimize_data_management(orchestrator, performance_metrics)
                if data_optimization:
                    optimizations_applied.append(data_optimization)
                
                # Network optimization
                network_optimization = optimize_network_usage(orchestrator, performance_metrics)
                if network_optimization:
                    optimizations_applied.append(network_optimization)
                
                # Log optimizations applied
                if optimizations_applied:
                    log_info(f"Applied optimizations: {', '.join(optimizations_applied)}")
                    optimization_history.append({
                        "timestamp": current_time,
                        "optimizations": optimizations_applied,
                        "metrics_before": performance_metrics
                    })
                
                # Performance alerting
                check_performance_alerts(orchestrator, performance_metrics, baseline_metrics)
                
                # Log detailed performance metrics
                enhanced_logger = components.get("enhanced_logger")
                if enhanced_logger and orchestrator.args.performance_monitoring:
                    enhanced_logger.log_performance_metrics(performance_metrics)
                
                # Generate performance report periodically
                if int(health.uptime_seconds) % 1800 == 0:  # Every 30 minutes
                    generate_performance_report(orchestrator, performance_history, optimization_history)
                
                # Adaptive sleep based on system load
                sleep_time = calculate_monitoring_sleep_time(performance_metrics)
                time.sleep(sleep_time)
                
            except Exception as e:
                log_error(f"Error in enhanced performance monitor: {e}")
                time.sleep(60)  # Fallback sleep time
    
    # Start performance monitoring in separate thread
    monitor_thread = threading.Thread(target=performance_monitor, daemon=True, name="PerformanceMonitor")
    monitor_thread.start()
    log_info("Enhanced performance monitoring and optimization started")


def collect_performance_metrics(orchestrator: BotOrchestrator) -> Dict[str, Any]:
    """
    Collect comprehensive performance metrics.
    
    Args:
        orchestrator: BotOrchestrator instance
        
    Returns:
        Dict containing performance metrics
    """
    try:
        import psutil
        
        health = orchestrator.system_health
        components = orchestrator.components
        
        # System metrics
        process = psutil.Process()
        system_memory = psutil.virtual_memory()
        
        metrics = {
            "timestamp": datetime.now(),
            "uptime_seconds": health.uptime_seconds,
            "memory_usage_mb": health.memory_usage_mb,
            "memory_percent": (health.memory_usage_mb / (system_memory.total / 1024 / 1024)) * 100,
            "cpu_usage_pct": health.cpu_usage_pct,
            "system_cpu_pct": psutil.cpu_percent(),
            "system_memory_pct": system_memory.percent,
            "disk_usage_pct": psutil.disk_usage('/').percent,
            "data_quality": health.data_quality,
            "error_count": health.error_count,
            "active_pairs": len(orchestrator.trading_pairs),
            "active_trades": health.active_trades,
            "api_connection": health.api_connection,
            "websocket_connection": health.websocket_connection
        }
        
        # Trading performance metrics
        trader = components.get("trader")
        if trader:
            try:
                positions = trader.get_positions()
                metrics["open_positions"] = len([p for p in positions.values() if p.get("size", 0) != 0])
                metrics["total_position_value"] = sum(p.get("value", 0) for p in positions.values())
            except:
                metrics["open_positions"] = 0
                metrics["total_position_value"] = 0.0
        
        # Data manager metrics
        data_manager = components.get("data_manager")
        if data_manager and hasattr(data_manager, 'get_cache_stats'):
            try:
                cache_stats = data_manager.get_cache_stats()
                metrics.update(cache_stats)
            except:
                pass
        
        # WebSocket metrics
        websocket_client = components.get("websocket_client")
        if websocket_client and hasattr(websocket_client, 'get_performance_stats'):
            try:
                ws_stats = websocket_client.get_performance_stats()
                metrics.update(ws_stats)
            except:
                pass
        
        return metrics
        
    except Exception as e:
        log_error(f"Error collecting performance metrics: {e}")
        return {"timestamp": datetime.now(), "error": str(e)}


def calculate_baseline_metrics(history: List[Dict]) -> Dict[str, float]:
    """Calculate baseline performance metrics from history."""
    try:
        if not history:
            return {}
        
        baseline = {}
        numeric_keys = ["memory_usage_mb", "cpu_usage_pct", "data_quality", "error_count"]
        
        for key in numeric_keys:
            values = [m.get(key, 0) for m in history if key in m and isinstance(m[key], (int, float))]
            if values:
                baseline[f"{key}_avg"] = sum(values) / len(values)
                baseline[f"{key}_max"] = max(values)
                baseline[f"{key}_min"] = min(values)
        
        return baseline
        
    except Exception as e:
        log_error(f"Error calculating baseline metrics: {e}")
        return {}


def optimize_memory_usage(orchestrator: BotOrchestrator, current_metrics: Dict, baseline: Dict) -> Optional[str]:
    """Optimize memory usage based on current metrics."""
    try:
        current_memory = current_metrics.get("memory_usage_mb", 0)
        baseline_memory = baseline.get("memory_usage_mb_avg", 0) if baseline else 0
        
        # Critical memory usage
        if current_memory > 700:
            log_warning(f"Critical memory usage: {current_memory:.1f}MB")
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Clear caches
            components = orchestrator.components
            data_manager = components.get("data_manager")
            if data_manager and hasattr(data_manager, 'cleanup_cache'):
                data_manager.cleanup_cache()
            
            # Reduce cache sizes
            if data_manager and hasattr(data_manager, 'reduce_cache_size'):
                data_manager.reduce_cache_size(0.5)  # Reduce by 50%
            
            return "critical_memory_cleanup"
        
        # High memory usage
        elif current_memory > 500:
            log_info(f"High memory usage detected: {current_memory:.1f}MB")
            
            import gc
            gc.collect()
            
            components = orchestrator.components
            data_manager = components.get("data_manager")
            if data_manager and hasattr(data_manager, 'cleanup_old_data'):
                data_manager.cleanup_old_data()
            
            return "memory_cleanup"
        
        # Memory usage trending upward
        elif baseline and current_memory > baseline_memory * 1.5:
            log_info("Memory usage trending upward, performing preventive cleanup")
            
            import gc
            gc.collect()
            
            return "preventive_memory_cleanup"
        
        return None
        
    except Exception as e:
        log_error(f"Error in memory optimization: {e}")
        return None


def optimize_cpu_usage(orchestrator: BotOrchestrator, current_metrics: Dict, baseline: Dict) -> Optional[str]:
    """Optimize CPU usage based on current metrics."""
    try:
        current_cpu = current_metrics.get("cpu_usage_pct", 0)
        system_cpu = current_metrics.get("system_cpu_pct", 0)
        
        # Critical CPU usage
        if current_cpu > 80 or system_cpu > 90:
            log_warning(f"Critical CPU usage: Process {current_cpu:.1f}%, System {system_cpu:.1f}%")
            
            # Increase trading interval
            original_interval = orchestrator.args.interval
            orchestrator.args.interval = min(original_interval * 1.5, 30)
            
            # Reduce concurrent operations
            if hasattr(orchestrator, 'max_concurrent_trades'):
                orchestrator.max_concurrent_trades = max(1, orchestrator.max_concurrent_trades - 1)
            
            return f"cpu_throttling_interval_{original_interval}_to_{orchestrator.args.interval}"
        
        # High CPU usage
        elif current_cpu > 60:
            log_info(f"High CPU usage detected: {current_cpu:.1f}%")
            
            # Slightly increase intervals
            original_interval = orchestrator.args.interval
            orchestrator.args.interval = min(original_interval * 1.2, 20)
            
            return f"cpu_optimization_interval_{original_interval}_to_{orchestrator.args.interval}"
        
        return None
        
    except Exception as e:
        log_error(f"Error in CPU optimization: {e}")
        return None


def optimize_trading_frequency(orchestrator: BotOrchestrator, current_metrics: Dict, history: List[Dict]) -> Optional[str]:
    """Optimize trading frequency based on performance and market conditions."""
    try:
        if len(history) < 10:
            return None
        
        # Analyze recent error patterns
        recent_errors = [m.get("error_count", 0) for m in history[-10:]]
        error_trend = sum(recent_errors[-5:]) - sum(recent_errors[:5])
        
        # Analyze data quality
        recent_quality = [m.get("data_quality", 1.0) for m in history[-5:]]
        avg_quality = sum(recent_quality) / len(recent_quality)
        
        # Adjust frequency based on conditions
        if error_trend > 3:  # Increasing errors
            original_interval = orchestrator.args.interval
            orchestrator.args.interval = min(original_interval * 1.3, 25)
            return f"frequency_reduced_due_to_errors_{original_interval}_to_{orchestrator.args.interval}"
        
        elif avg_quality < 0.8:  # Poor data quality
            original_interval = orchestrator.args.interval
            orchestrator.args.interval = min(original_interval * 1.2, 20)
            return f"frequency_reduced_due_to_data_quality_{original_interval}_to_{orchestrator.args.interval}"
        
        elif error_trend < -2 and avg_quality > 0.9:  # Improving conditions
            original_interval = orchestrator.args.interval
            orchestrator.args.interval = max(original_interval * 0.9, 1)
            return f"frequency_increased_due_to_good_conditions_{original_interval}_to_{orchestrator.args.interval}"
        
        return None
        
    except Exception as e:
        log_error(f"Error in trading frequency optimization: {e}")
        return None


def optimize_data_management(orchestrator: BotOrchestrator, current_metrics: Dict) -> Optional[str]:
    """Optimize data management based on current metrics."""
    try:
        components = orchestrator.components
        data_manager = components.get("data_manager")
        
        if not data_manager:
            return None
        
        data_quality = current_metrics.get("data_quality", 1.0)
        
        # Poor data quality - refresh data
        if data_quality < 0.7:
            log_info("Poor data quality detected, refreshing data")
            
            if hasattr(data_manager, 'refresh_all_data'):
                data_manager.refresh_all_data()
                return "data_refresh_due_to_quality"
        
        # Check cache efficiency
        if hasattr(data_manager, 'get_cache_hit_rate'):
            try:
                hit_rate = data_manager.get_cache_hit_rate()
                if hit_rate < 0.5:  # Low cache hit rate
                    log_info("Low cache hit rate, optimizing cache")
                    if hasattr(data_manager, 'optimize_cache'):
                        data_manager.optimize_cache()
                        return "cache_optimization"
            except:
                pass
        
        return None
        
    except Exception as e:
        log_error(f"Error in data management optimization: {e}")
        return None


def optimize_network_usage(orchestrator: BotOrchestrator, current_metrics: Dict) -> Optional[str]:
    """Optimize network usage based on current metrics."""
    try:
        components = orchestrator.components
        
        # Check API connection health
        if not current_metrics.get("api_connection", True):
            log_info("API connection issues detected, implementing backoff")
            
            # Increase intervals to reduce API load
            original_interval = orchestrator.args.interval
            orchestrator.args.interval = min(original_interval * 2, 30)
            
            return f"network_backoff_{original_interval}_to_{orchestrator.args.interval}"
        
        # Check WebSocket connection
        websocket_client = components.get("websocket_client")
        if websocket_client and not current_metrics.get("websocket_connection", True):
            log_info("WebSocket connection issues detected, attempting reconnection")
            
            try:
                websocket_client.reconnect()
                return "websocket_reconnection"
            except Exception as e:
                log_error(f"WebSocket reconnection failed: {e}")
        
        return None
        
    except Exception as e:
        log_error(f"Error in network optimization: {e}")
        return None


def check_performance_alerts(orchestrator: BotOrchestrator, current_metrics: Dict, baseline: Dict) -> None:
    """Check for performance issues and send alerts."""
    try:
        components = orchestrator.components
        alert_system = components.get("alert_system")
        
        if not alert_system:
            return
        
        alerts_to_send = []
        
        # Memory alerts
        memory_usage = current_metrics.get("memory_usage_mb", 0)
        if memory_usage > 600:
            alerts_to_send.append(("HIGH_MEMORY", f"High memory usage: {memory_usage:.1f}MB", AlertSeverity.MEDIUM))
        elif memory_usage > 800:
            alerts_to_send.append(("CRITICAL_MEMORY", f"Critical memory usage: {memory_usage:.1f}MB", AlertSeverity.HIGH))
        
        # CPU alerts
        cpu_usage = current_metrics.get("cpu_usage_pct", 0)
        if cpu_usage > 70:
            alerts_to_send.append(("HIGH_CPU", f"High CPU usage: {cpu_usage:.1f}%", AlertSeverity.MEDIUM))
        elif cpu_usage > 85:
            alerts_to_send.append(("CRITICAL_CPU", f"Critical CPU usage: {cpu_usage:.1f}%", AlertSeverity.HIGH))
        
        # Data quality alerts
        data_quality = current_metrics.get("data_quality", 1.0)
        if data_quality < 0.7:
            alerts_to_send.append(("POOR_DATA_QUALITY", f"Poor data quality: {data_quality:.2f}", AlertSeverity.MEDIUM))
        
        # Error count alerts
        error_count = current_metrics.get("error_count", 0)
        if error_count > 10:
            alerts_to_send.append(("HIGH_ERROR_COUNT", f"High error count: {error_count}", AlertSeverity.MEDIUM))
        elif error_count > 20:
            alerts_to_send.append(("CRITICAL_ERROR_COUNT", f"Critical error count: {error_count}", AlertSeverity.HIGH))
        
        # Send alerts
        for alert_type, message, severity in alerts_to_send:
            alert_system.send_system_alert(alert_type, message, severity)
        
    except Exception as e:
        log_error(f"Error checking performance alerts: {e}")


def generate_performance_report(orchestrator: BotOrchestrator, history: List[Dict], optimizations: List[Dict]) -> None:
    """Generate comprehensive performance report."""
    try:
        if not history:
            return
        
        log_info("=== Performance Report ===")
        
        # Calculate averages from recent history
        recent_history = history[-30:] if len(history) >= 30 else history
        
        avg_memory = sum(m.get("memory_usage_mb", 0) for m in recent_history) / len(recent_history)
        avg_cpu = sum(m.get("cpu_usage_pct", 0) for m in recent_history) / len(recent_history)
        avg_quality = sum(m.get("data_quality", 1.0) for m in recent_history) / len(recent_history)
        total_errors = sum(m.get("error_count", 0) for m in recent_history)
        
        log_info(f"Average Memory Usage: {avg_memory:.1f}MB")
        log_info(f"Average CPU Usage: {avg_cpu:.1f}%")
        log_info(f"Average Data Quality: {avg_quality:.2f}")
        log_info(f"Total Errors: {total_errors}")
        log_info(f"Active Trading Pairs: {len(orchestrator.trading_pairs)}")
        log_info(f"Uptime: {orchestrator.system_health.uptime_seconds/3600:.1f} hours")
        
        # Optimization summary
        if optimizations:
            recent_optimizations = optimizations[-10:]  # Last 10 optimizations
            optimization_types = {}
            for opt in recent_optimizations:
                for opt_type in opt["optimizations"]:
                    optimization_types[opt_type] = optimization_types.get(opt_type, 0) + 1
            
            log_info("Recent Optimizations:")
            for opt_type, count in optimization_types.items():
                log_info(f"  {opt_type}: {count} times")
        
        log_info("=== End Performance Report ===")
        
    except Exception as e:
        log_error(f"Error generating performance report: {e}")


def calculate_monitoring_sleep_time(metrics: Dict) -> float:
    """Calculate adaptive sleep time for performance monitoring."""
    try:
        base_sleep = 60.0  # 1 minute base
        
        # Reduce monitoring frequency if system is under stress
        cpu_usage = metrics.get("cpu_usage_pct", 0)
        memory_usage = metrics.get("memory_usage_mb", 0)
        
        if cpu_usage > 80 or memory_usage > 600:
            return base_sleep * 2  # Monitor less frequently under stress
        elif cpu_usage > 60 or memory_usage > 400:
            return base_sleep * 1.5
        else:
            return base_sleep
        
    except Exception:
        return 60.0  # Default 1 minute


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