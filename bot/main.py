#!/usr/bin/env python
"""
Main entry point for the crypto trading bot.
Initializes components and starts the trading scheduler.
"""
import argparse
import sys
import time
import signal
import logging
import os
import atexit
from typing import Dict, Any, Optional, List, Tuple

from bot.config import Config, TradingSettings, AlpacaCredentials
from bot.data_fetcher import DataFetcher
from bot.strategy import MovingAverageCrossover, RSIStrategy, SignalGenerator, BaseStrategy
from bot.trader import Trader
from bot.logger import TradingLogger
from bot.scheduler import TradingCycle, TradingScheduler
from bot.utils import log_info, log_error, log_warning, retry_with_backoff
from bot.error_handler import ErrorHandler


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Namespace containing the parsed arguments
    """
    parser = argparse.ArgumentParser(description="Crypto Trading Bot")
    
    # Trading symbol configuration
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="BTC/USD",
        help="Trading symbol (default: BTC/USD)"
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


def initialize_components(config: Config, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Initialize all components needed for the trading bot.
    
    Args:
        config: Config object containing credentials and settings
        args: Parsed command line arguments
        
    Returns:
        Dictionary containing initialized components
    """
    # Get credentials and settings
    credentials = config.get_alpaca_credentials()
    settings = config.get_trading_settings()
    
    # Update settings from command line arguments
    update_trading_settings(settings, args)
    
    # Update settings for execution modes
    if args.dry_run:
        log_info("Running in dry-run mode - no actual trades will be executed")
        settings.dry_run = True
    
    # Initialize logger with specified options
    logger = TradingLogger(
        use_rich=not args.no_dashboard,
        log_file=args.log_file
    )
    
    # Initialize data fetcher
    data_fetcher = DataFetcher(credentials)
    
    # Initialize strategies with command-line parameters
    strategies: List[BaseStrategy] = [
        MovingAverageCrossover(
            fast_period=args.ma_fast,
            slow_period=args.ma_slow
        ),
        RSIStrategy(
            period=args.rsi_period,
            oversold=args.rsi_oversold,
            overbought=args.rsi_overbought
        )
    ]
    signal_generator = SignalGenerator(strategies)
    
    # Initialize trader with appropriate settings
    # Update paper_trading in credentials if dry run is enabled
    if args.dry_run:
        credentials.paper_trading = True
        
    trader = Trader(
        credentials=credentials,
        settings=settings
    )
    
    # Initialize error handler
    error_handler = ErrorHandler()
    
    # Initialize trading cycle
    trading_cycle = TradingCycle(
        data_fetcher=data_fetcher,
        signal_generator=signal_generator,
        trader=trader,
        logger=logger,
        error_handler=error_handler,
        symbol=settings.symbol
    )
    
    # Initialize scheduler with appropriate settings
    scheduler = TradingScheduler(
        trading_cycle=trading_cycle,
        interval_minutes=args.interval,
        error_handler=error_handler
    )
    
    return {
        "logger": logger,
        "data_fetcher": data_fetcher,
        "signal_generator": signal_generator,
        "trader": trader,
        "trading_cycle": trading_cycle,
        "scheduler": scheduler
    }


def perform_health_check(components: Dict[str, Any]) -> bool:
    """
    Perform a health check on all components.
    
    Args:
        components: Dictionary containing all components
        
    Returns:
        bool: True if all components are healthy, False otherwise
    """
    try:
        log_info("Performing health check...")
        
        # Check data fetcher
        data_fetcher = components["data_fetcher"]
        symbol = components["trading_cycle"].symbol
        
        try:
            # Try to fetch the latest price
            price = data_fetcher.get_latest_price(symbol)
            log_info(f"Data fetcher check: OK (Latest {symbol} price: ${price:.2f})")
        except Exception as e:
            log_error("Data fetcher check: FAILED", e)
            return False
            
        # Check trader
        trader = components["trader"]
        try:
            # Try to get account info
            account_info = trader.get_account_info()
            if account_info:
                log_info(f"Trader check: OK (Account equity: ${account_info.get('equity', 'N/A')})")
            else:
                log_warning("Trader check: WARNING (Could not get account info)")
        except Exception as e:
            log_error("Trader check: FAILED", e)
            return False
            
        # Check position manager
        try:
            # Try to reconcile positions
            if trader.position_manager.reconcile_positions():
                log_info("Position manager check: OK")
            else:
                log_warning("Position manager check: WARNING (Could not reconcile positions)")
        except Exception as e:
            log_error("Position manager check: FAILED", e)
            return False
            
        log_info("Health check completed successfully")
        return True
        
    except Exception as e:
        log_error("Health check failed with unexpected error", e)
        return False


def setup_signal_handlers(scheduler: TradingScheduler) -> None:
    """
    Set up signal handlers for graceful shutdown.
    
    Args:
        scheduler: TradingScheduler instance to stop on signal
    """
    def signal_handler(sig, frame):
        log_info(f"Received signal {sig}, initiating graceful shutdown...")
        scheduler.stop_scheduler()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main() -> int:
    """
    Main entry point for the crypto trading bot.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
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
            
        if not config.validate_config():
            log_error("Invalid configuration")
            return 1
            
        # Initialize components
        components = initialize_components(config, args)
        logger = components["logger"]
        scheduler = components["scheduler"]
        
        # Start the live display
        logger.start_live_display()
        
        # Log startup information
        log_info(f"Starting crypto trading bot with symbol {args.symbol}")
        log_info(f"Trading interval: {args.interval} minutes")
        log_info(f"Trade amount: ${args.amount}")
        log_info(f"Maximum position size: ${args.max_position}")
        log_info(f"Stop loss: {args.stop_loss * 100}%")
        log_info(f"Take profit: {args.take_profit * 100}%")
        log_info(f"Max trades per day: {args.maxtrades}")
        
        # Perform initial health check
        if not args.skip_health_check:
            if not perform_health_check(components):
                log_error("Initial health check failed, aborting startup")
                logger.stop_live_display()
                return 1
        else:
            log_warning("Skipping initial health check as requested")
        
        # Set up signal handlers for graceful shutdown
        setup_signal_handlers(scheduler)
        
        # Register cleanup function to ensure graceful shutdown
        def cleanup():
            if scheduler.is_running:
                log_info("Performing cleanup during shutdown...")
                scheduler.stop_scheduler()
                logger.stop_live_display()
                log_info("Cleanup completed")
        
        # Register the cleanup function to be called on exit
        atexit.register(cleanup)
        
        # Start the scheduler
        if not scheduler.start_scheduler():
            log_error("Failed to start scheduler")
            logger.stop_live_display()
            return 1
            
        # Set up health check interval (every 30 minutes)
        health_check_interval = args.health_check_interval * 60  # convert minutes to seconds
        last_health_check = time.time()
        
        # Keep the main thread alive
        try:
            while scheduler.is_running:
                # Sleep for a short time to avoid high CPU usage
                time.sleep(1)
                
                # Perform periodic health check
                current_time = time.time()
                if current_time - last_health_check > health_check_interval:
                    perform_health_check(components)
                    last_health_check = current_time
                    
        except KeyboardInterrupt:
            log_info("Keyboard interrupt received, shutting down...")
            scheduler.stop_scheduler()
            
        # Stop the live display
        logger.stop_live_display()
        
        log_info("Crypto trading bot stopped")
        return 0
        
    except Exception as e:
        log_error("Unhandled exception in main", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())