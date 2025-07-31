#!/usr/bin/env python3
"""
Enhanced Kraken Trading Bot

This is the main entry point for the enhanced Kraken trading bot with all
the advanced features including multi-pair trading, enhanced risk management,
real-time monitoring, and comprehensive logging.
"""
import os
import sys
import time
import signal
import logging
import argparse
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

# Import enhanced components
from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig
from bot.enhanced_strategies import EnhancedStrategyEngine, StrategyParameters
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.enhanced_logger import EnhancedLogger, TradeExecution
from bot.enhanced_alerts import EnhancedAlertSystem
from bot.enhanced_dashboard import EnhancedDashboard, DashboardConfig
from bot.crypto_position_manager import CryptoPositionManager
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_info, log_error, log_warning


@dataclass
class BotConfig:
    """Configuration for the enhanced Kraken bot."""
    trading_pairs: List[str]
    paper_trading: bool = True
    trade_amount_usd: float = 10.0
    max_position_usd: float = 100.0
    min_trade_interval: int = 60
    confidence_threshold: float = 0.3
    max_trades_per_day: int = 20
    enable_dashboard: bool = True
    enable_alerts: bool = True
    dashboard_port: int = 8080
    log_level: str = "INFO"


def convert_trade_result_to_execution(trade_result, signal: TradingSignal, strategy: str = "enhanced") -> TradeExecution:
    """Convert KrakenTradeResult to TradeExecution for logging and alerts."""
    return TradeExecution(
        trade_id=trade_result.order_id or f"trade_{int(time.time())}",
        pair=trade_result.pair or signal.pair,
        side=trade_result.side.upper() if trade_result.side else signal.action.name,
        order_type="market",
        volume=float(trade_result.volume) if trade_result.volume else 0.0,
        price=float(trade_result.price) if trade_result.price else signal.price,
        fee=0.0,  # Kraken fees are calculated separately
        timestamp=datetime.now(),
        strategy=strategy,
        signal_confidence=signal.confidence,
        execution_time_ms=0,  # Not tracked in current implementation
        status="filled" if trade_result.success else "failed",
        order_id=trade_result.order_id,
        fill_price=float(trade_result.price) if trade_result.price else None,
        slippage=None  # Not calculated in current implementation
    )
    log_level: str = "INFO"


class EnhancedKrakenBot:
    """Enhanced Kraken trading bot with all advanced features."""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.credentials = None
        self.components = {}
        self.shutdown_event = threading.Event()
        self.trading_active = False
        
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
    
    def initialize_components(self) -> bool:
        """Initialize all enhanced components."""
        try:
            log_info("🔧 Initializing enhanced components...")
            
            # Enhanced Logger
            enhanced_logger = EnhancedLogger({
                'log_level': getattr(logging, self.config.log_level.upper()),
                'log_dir': 'logs',
                'structured_logging': True,
                'performance_tracking': True
            })
            
            # Cache Configuration
            cache_config = CacheConfig(
                enabled=True,
                max_memory_mb=100,
                retention_hours=24,
                persist_to_disk=True
            )
            
            # Enhanced Data Manager
            data_manager = EnhancedDataManager(
                pairs=self.config.trading_pairs,
                cache_config=cache_config
            )
            
            # Aggressive Strategy Engine (like the old enhanced bot)
            strategy_params = StrategyParameters(
                volatility_lookback=15,  # Shorter lookback for faster response
                momentum_periods=[3, 8, 15],  # Shorter periods for more aggressive signals
                volume_threshold=1.1,  # Lower threshold for more signals
                confidence_threshold=self.config.confidence_threshold
            )
            
            # Import and create aggressive strategies (like the old enhanced bot)
            from bot.enhanced_strategies import create_enhanced_strategy_suite
            strategies = create_enhanced_strategy_suite()
            
            strategy_engine = EnhancedStrategyEngine(
                strategies=strategies,
                parameters=strategy_params
            )
            
            # Kraken Client and Position Manager
            kraken_client = KrakenClient(self.credentials)
            position_manager = CryptoPositionManager(kraken_client)
            
            # Enhanced Risk Manager
            risk_manager = EnhancedRiskManager(
                position_manager=position_manager,
                data_manager=data_manager,
                kraken_client=kraken_client,
                trading_pairs=self.config.trading_pairs
            )
            
            # Alert System
            if self.config.enable_alerts:
                alert_config = {
                    'enabled': True,
                    'channels': {
                        'console': {'enabled': True}
                    }
                }
                alert_system = EnhancedAlertSystem(alert_config, enhanced_logger)
            else:
                alert_system = None
            
            # Dashboard
            if self.config.enable_dashboard:
                dashboard_config = DashboardConfig(
                    host="localhost",
                    port=self.config.dashboard_port,
                    enable_manual_trading=not self.config.paper_trading,
                    enable_websocket=True
                )
                dashboard = EnhancedDashboard(
                    config=dashboard_config,
                    data_manager=data_manager,
                    logger=enhanced_logger,
                    risk_manager=risk_manager,
                    kraken_client=kraken_client
                )
            else:
                dashboard = None
            
            # Create traders for each pair
            traders = {}
            for pair in self.config.trading_pairs:
                trading_config = KrakenTradingConfig(
                    trading_pair=pair,
                    trade_amount_usd=self.config.trade_amount_usd,
                    max_position_usd=self.config.max_position_usd,
                    min_trade_interval=self.config.min_trade_interval
                )
                traders[pair] = KrakenTrader(self.credentials, trading_config)
            
            # Store all components
            self.components = {
                "enhanced_logger": enhanced_logger,
                "data_manager": data_manager,
                "strategy_engine": strategy_engine,
                "risk_manager": risk_manager,
                "alert_system": alert_system,
                "dashboard": dashboard,
                "kraken_client": kraken_client,
                "position_manager": position_manager,
                "traders": traders
            }
            
            log_info("✅ All enhanced components initialized successfully")
            return True
            
        except Exception as e:
            log_error(f"Failed to initialize enhanced components: {e}")
            return False
    
    def start_dashboard(self):
        """Start the dashboard if enabled."""
        if self.components.get("dashboard"):
            try:
                dashboard = self.components["dashboard"]
                dashboard.start_server()
                log_info(f"📊 Dashboard started at http://localhost:{self.config.dashboard_port}")
            except Exception as e:
                log_error(f"Failed to start dashboard: {e}")
    
    def test_connections(self) -> bool:
        """Test all connections before starting trading."""
        try:
            log_info("🔍 Testing connections...")
            
            # Test Kraken API connection
            kraken_client = self.components["kraken_client"]
            if not kraken_client.get_server_time():
                log_error("Failed to connect to Kraken API")
                return False
            
            # Test each trading pair
            for pair in self.config.trading_pairs:
                trader = self.components["traders"][pair]
                if not trader.test_connection():
                    log_error(f"Failed to connect for trading pair {pair}")
                    return False
                
                # Get current price to verify market data access
                price = trader.get_current_price(pair)
                if not price:
                    log_error(f"Failed to get market data for {pair}")
                    return False
                
                log_info(f"✅ {pair}: ${price:,.2f}")
            
            log_info("✅ All connections tested successfully")
            return True
            
        except Exception as e:
            log_error(f"Connection test failed: {e}")
            return False
    
    def trading_loop(self):
        """Main trading loop."""
        log_info("🚀 Starting enhanced trading loop...")
        
        components = self.components
        data_manager = components["data_manager"]
        strategy_engine = components["strategy_engine"]
        risk_manager = components["risk_manager"]
        traders = components["traders"]
        enhanced_logger = components["enhanced_logger"]
        alert_system = components.get("alert_system")
        dashboard = components.get("dashboard")
        
        # Trading state
        trade_counts = {pair: 0 for pair in self.config.trading_pairs}
        last_trade_times = {pair: datetime.now() for pair in self.config.trading_pairs}
        
        cycle_count = 0
        
        while not self.shutdown_event.is_set() and self.trading_active:
            try:
                cycle_count += 1
                current_time = datetime.now()
                
                log_info(f"🔄 Trading Cycle #{cycle_count} - {current_time.strftime('%H:%M:%S')}")
                
                # Process each trading pair
                for pair in self.config.trading_pairs:
                    if self.shutdown_event.is_set():
                        break
                    
                    try:
                        # Check trade limits
                        if trade_counts[pair] >= self.config.max_trades_per_day:
                            log_info(f"Daily trade limit reached for {pair}")
                            continue
                        
                        # Check time since last trade
                        time_since_last = (current_time - last_trade_times[pair]).total_seconds()
                        if time_since_last < self.config.min_trade_interval:
                            continue
                        
                        trader = traders[pair]
                        
                        # Get current market data
                        current_price = trader.get_current_price(pair)
                        if not current_price:
                            log_warning(f"Failed to get current price for {pair}")
                            continue
                        
                        # Get historical data for strategy analysis
                        market_data = data_manager.get_latest_data(pair, periods=100)
                        if market_data is None or (hasattr(market_data, 'empty') and market_data.empty) or (isinstance(market_data, list) and len(market_data) == 0):
                            # Try to fetch fresh data
                            log_info(f"Fetching fresh market data for {pair}")
                            ohlc_data = components["kraken_client"].get_ohlc_data(pair, interval=5)
                            if ohlc_data and pair in ohlc_data:
                                # Add data to manager
                                pair_data = ohlc_data[pair]
                                for timestamp, open_price, high, low, close, vwap, volume, count in pair_data[-50:]:
                                    market_data_point = {
                                        'timestamp': datetime.fromtimestamp(timestamp),
                                        'price': float(close),
                                        'volume': float(volume),
                                        'high': float(high),
                                        'low': float(low),
                                        'open': float(open_price)
                                    }
                                    data_manager.add_market_data(pair, market_data_point)
                                
                                market_data = data_manager.get_latest_data(pair, periods=100)
                        
                        if market_data is None or (hasattr(market_data, 'empty') and market_data.empty) or (isinstance(market_data, list) and len(market_data) == 0):
                            log_warning(f"No market data available for {pair}")
                            continue
                        
                        # Generate trading signal
                        signal = strategy_engine.calculate_weighted_signal(market_data)
                        if not signal:
                            log_info(f"No signal generated for {pair}")
                            continue
                        
                        log_info(f"📊 {pair} Signal: {signal.action.name} (confidence: {signal.confidence:.3f})")
                        
                        # Check if signal is strong enough
                        if signal.confidence < self.config.confidence_threshold:
                            log_info(f"Signal confidence too low for {pair}: {signal.confidence:.3f}")
                            continue
                        
                        # Get current positions for risk assessment
                        current_positions = components["position_manager"].get_positions()
                        
                        # Validate trade with risk manager
                        risk_assessment = risk_manager.validate_trade(
                            pair=pair,
                            side=signal.action.name.lower(),
                            quantity=self.config.trade_amount_usd / current_price,
                            price=current_price,
                            signal_confidence=signal.confidence
                        )
                        
                        if not risk_assessment.is_valid:
                            log_info(f"Trade rejected by risk manager for {pair}: {', '.join(risk_assessment.risk_factors)}")
                            continue
                        
                        # Execute trade
                        log_info(f"🚨 Executing {signal.action.name} trade for {pair}")
                        log_info(f"   Price: ${current_price:,.2f}")
                        log_info(f"   Confidence: {signal.confidence:.3f}")
                        log_info(f"   Amount: ${self.config.trade_amount_usd}")
                        
                        if self.config.paper_trading:
                            # Simulate paper trade
                            log_info("   📝 PAPER TRADE")
                            
                            # Simple simulation based on signal confidence
                            import random
                            success_rate = 0.4 + (signal.confidence * 0.3)  # 40-70% success rate
                            
                            if random.random() < success_rate:
                                profit_pct = random.uniform(0.005, 0.025)  # 0.5% to 2.5%
                                pnl = self.config.trade_amount_usd * profit_pct
                                log_info(f"   ✅ Simulated Profit: +${pnl:.2f} ({profit_pct*100:.1f}%)")
                            else:
                                loss_pct = random.uniform(0.005, 0.015)  # 0.5% to 1.5%
                                pnl = -self.config.trade_amount_usd * loss_pct
                                log_info(f"   ❌ Simulated Loss: ${pnl:.2f} ({loss_pct*100:.1f}%)")
                            
                            # Log the trade
                            trade_data = {
                                'trade_id': f'paper_{pair}_{int(time.time())}',
                                'pair': pair,
                                'side': signal.action.name.lower(),
                                'volume': self.config.trade_amount_usd / current_price,
                                'price': current_price,
                                'timestamp': current_time,
                                'strategy': signal.strategy if hasattr(signal, 'strategy') else 'enhanced',
                                'fee': 0.0,  # No fees in paper trading
                                'order_type': 'market',
                                'signal_confidence': signal.confidence,
                                'execution_time_ms': 100,
                                'pnl': pnl if 'pnl' in locals() else 0.0
                            }
                            
                            # Log trade
                            try:
                                enhanced_logger.log_trade(trade_data)
                            except Exception as e:
                                log_warning(f"Failed to log trade: {e}")
                            
                            # Send alerts
                            if alert_system:
                                try:
                                    alert_system.send_trade_alert(trade_data)
                                except Exception as e:
                                    log_warning(f"Failed to send trade alert: {e}")
                            
                            # Update dashboard
                            if dashboard:
                                try:
                                    dashboard.add_trade_event(trade_data)
                                except Exception as e:
                                    log_warning(f"Failed to update dashboard: {e}")
                        
                        else:
                            # Execute real trade
                            log_info("   💰 REAL TRADE")
                            trade_result = trader.execute_trade(signal)
                            
                            if trade_result and trade_result.success:
                                log_info(f"   ✅ Trade executed successfully: {trade_result.order_id}")
                                
                                # Convert to TradeExecution format
                                trade_execution = convert_trade_result_to_execution(trade_result, signal)
                                
                                # Log the trade
                                try:
                                    enhanced_logger.log_trade(trade_execution)
                                except Exception as e:
                                    log_warning(f"Failed to log trade: {e}")
                                
                                # Send alerts
                                if alert_system:
                                    try:
                                        alert_system.send_trade_alert(trade_execution)
                                    except Exception as e:
                                        log_warning(f"Failed to send trade alert: {e}")
                                
                                # Update dashboard
                                if dashboard:
                                    try:
                                        dashboard.add_trade_event(trade_execution.to_dict())
                                    except Exception as e:
                                        log_warning(f"Failed to update dashboard: {e}")
                            else:
                                log_error(f"   ❌ Trade execution failed: {trade_result.error if trade_result else 'Unknown error'}")
                        
                        # Update tracking
                        trade_counts[pair] += 1
                        last_trade_times[pair] = current_time
                        
                    except Exception as e:
                        log_error(f"Error processing {pair}: {e}")
                        continue
                
                # Show status
                total_trades = sum(trade_counts.values())
                log_info(f"📊 Status: {total_trades} trades today across {len(self.config.trading_pairs)} pairs")
                
                # Wait before next cycle
                log_info(f"⏳ Waiting {self.config.min_trade_interval} seconds...")
                time.sleep(self.config.min_trade_interval)
                
            except Exception as e:
                log_error(f"Error in trading loop: {e}")
                time.sleep(30)  # Longer sleep on error
        
        log_info("🛑 Trading loop stopped")
    
    def start_trading(self):
        """Start the trading bot."""
        try:
            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                log_info("Received shutdown signal, stopping bot...")
                self.stop_trading()
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Start dashboard if enabled
            if self.config.enable_dashboard:
                dashboard_thread = threading.Thread(target=self.start_dashboard, daemon=True)
                dashboard_thread.start()
                time.sleep(2)  # Give dashboard time to start
            
            # Start trading
            self.trading_active = True
            self.trading_loop()
            
        except Exception as e:
            log_error(f"Error starting trading: {e}")
            self.stop_trading()
    
    def stop_trading(self):
        """Stop the trading bot gracefully."""
        log_info("🛑 Stopping enhanced Kraken bot...")
        self.trading_active = False
        self.shutdown_event.set()
        
        # Stop dashboard if running
        if self.components.get("dashboard"):
            try:
                self.components["dashboard"].stop_server()
            except Exception as e:
                log_warning(f"Error stopping dashboard: {e}")
        
        log_info("✅ Bot stopped successfully")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhanced Kraken Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with paper trading (recommended)
    python run_enhanced_kraken_bot.py --paper-trading
    
    # Run with multiple pairs
    python run_enhanced_kraken_bot.py --paper-trading --pairs XBTUSD XETHZUSD
    
    # Run with custom settings
    python run_enhanced_kraken_bot.py --paper-trading --trade-amount 25 --confidence 0.4
        """
    )
    
    parser.add_argument(
        "--paper-trading",
        action="store_true",
        help="Run in paper trading mode (simulated trades)"
    )
    
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=["XBTUSD"],
        help="Trading pairs (default: XBTUSD)"
    )
    
    parser.add_argument(
        "--trade-amount",
        type=float,
        default=10.0,
        help="Trade amount in USD (default: 10.0)"
    )
    
    parser.add_argument(
        "--max-position",
        type=float,
        default=100.0,
        help="Maximum position size in USD (default: 100.0)"
    )
    
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.3,
        help="Minimum signal confidence (default: 0.3)"
    )
    
    parser.add_argument(
        "--max-trades",
        type=int,
        default=20,
        help="Maximum trades per day (default: 20)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Trading interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Disable dashboard"
    )
    
    parser.add_argument(
        "--no-alerts",
        action="store_true",
        help="Disable alerts"
    )
    
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8080,
        help="Dashboard port (default: 8080)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (same as --log-level DEBUG)"
    )
    
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_arguments()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else args.log_level
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create bot configuration
    config = BotConfig(
        trading_pairs=args.pairs,
        paper_trading=args.paper_trading,
        trade_amount_usd=args.trade_amount,
        max_position_usd=args.max_position,
        min_trade_interval=args.interval,
        confidence_threshold=args.confidence,
        max_trades_per_day=args.max_trades,
        enable_dashboard=not args.no_dashboard,
        enable_alerts=not args.no_alerts,
        dashboard_port=args.dashboard_port,
        log_level=log_level
    )
    
    # Display configuration
    print("🚀 Enhanced Kraken Trading Bot")
    print("=" * 50)
    print(f"Trading Pairs: {', '.join(config.trading_pairs)}")
    print(f"Paper Trading: {'YES' if config.paper_trading else 'NO'}")
    print(f"Trade Amount: ${config.trade_amount_usd}")
    print(f"Max Position: ${config.max_position_usd}")
    print(f"Confidence Threshold: {config.confidence_threshold}")
    print(f"Max Trades/Day: {config.max_trades_per_day}")
    print(f"Trading Interval: {config.min_trade_interval}s")
    print(f"Dashboard: {'Enabled' if config.enable_dashboard else 'Disabled'}")
    print(f"Alerts: {'Enabled' if config.enable_alerts else 'Disabled'}")
    print("=" * 50)
    
    if not config.paper_trading:
        print("⚠️  WARNING: REAL MONEY TRADING ENABLED!")
        response = input("Type 'YES' to continue with real trading: ")
        if response != 'YES':
            print("Exiting...")
            return 0
    
    # Initialize and start bot
    bot = EnhancedKrakenBot(config)
    
    try:
        # Setup credentials
        if not bot.setup_credentials():
            log_error("Failed to setup credentials")
            return 1
        
        # Initialize components
        if not bot.initialize_components():
            log_error("Failed to initialize components")
            return 1
        
        # Test connections
        if not bot.test_connections():
            log_error("Connection tests failed")
            return 1
        
        print(f"\n🚀 Starting enhanced Kraken bot at {datetime.now()}")
        if config.enable_dashboard:
            print(f"📊 Dashboard: http://localhost:{config.dashboard_port}")
        print("Press Ctrl+C to stop\n")
        
        # Start trading
        bot.start_trading()
        
        return 0
        
    except KeyboardInterrupt:
        log_info("Bot stopped by user")
        bot.stop_trading()
        return 0
    except Exception as e:
        log_error(f"Critical error: {e}")
        bot.stop_trading()
        return 1


if __name__ == "__main__":
    sys.exit(main())