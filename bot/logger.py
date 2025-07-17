"""
Comprehensive logging system for the crypto trading bot.
Provides rich terminal display and file-based logging with configurable verbosity levels.

This module implements a flexible logging system that supports:
- Colored console output using the rich library
- File-based logging for trades, signals, and errors
- Configurable verbosity levels
- Real-time dashboard display

Classes:
    TradeRecord: Data structure for trade information
    SignalRecord: Data structure for trading signals
    PositionRecord: Data structure for position information
    TradingLogger: Main logging orchestrator
"""
import os
import logging
import datetime
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.logging import RichHandler


class LogLevel(Enum):
    """Enum for log levels with descriptive names"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    
    @classmethod
    def from_string(cls, level_name: str) -> int:
        """Convert string log level to numeric value"""
        try:
            return cls[level_name].value
        except KeyError:
            valid_levels = [level.name for level in cls]
            raise ValueError(f"Invalid log level: {level_name}. Valid levels are: {', '.join(valid_levels)}")
            
    @classmethod
    def get_description(cls, level: Union[int, str]) -> str:
        """Get description for a log level"""
        if isinstance(level, str):
            level = cls.from_string(level)
            
        descriptions = {
            logging.DEBUG: "Detailed debugging information",
            logging.INFO: "Confirmation that things are working as expected",
            logging.WARNING: "Indication that something unexpected happened",
            logging.ERROR: "Due to a more serious problem, the software has not been able to perform some function",
            logging.CRITICAL: "A serious error, indicating that the program itself may be unable to continue running"
        }
        
        return descriptions.get(level, "Unknown log level")

# Define data structures for logging
@dataclass
class TradeRecord:
    """Data structure for trade information"""
    order_id: str
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: float
    price: float
    timestamp: datetime.datetime
    status: str
    fees: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return asdict(self)

@dataclass
class SignalRecord:
    """Data structure for trading signals"""
    action: str  # 'BUY', 'SELL', or 'HOLD'
    symbol: str
    confidence: float
    strategy: str
    price: float
    timestamp: datetime.datetime
    reasoning: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return asdict(self)

@dataclass
class PositionRecord:
    """Data structure for position information"""
    symbol: str
    quantity: float
    market_value: float
    unrealized_pnl: float
    avg_entry_price: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return asdict(self)


class TradingLogger:
    """
    Comprehensive logging system for the crypto trading bot.
    Provides rich terminal display and file-based logging.
    """
    
    def __init__(self, log_dir: str = "logs", use_rich: bool = True, 
                 log_level: Union[str, int] = logging.INFO, log_file: str = "bot.log",
                 max_trades_history: int = 50, max_signals_history: int = 50,
                 max_errors_history: int = 20, console_width: int = None):
        """
        Initialize the trading logger.
        
        Args:
            log_dir: Directory for log files
            use_rich: Whether to use rich for terminal display
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to main log file
            max_trades_history: Maximum number of trades to keep in history
            max_signals_history: Maximum number of signals to keep in history
            max_errors_history: Maximum number of errors to keep in history
            console_width: Width of the console display (None for auto-detect)
        """
        self.use_rich = use_rich
        self.log_dir = log_dir
        self.log_file = log_file
        self.max_trades_history = max_trades_history
        self.max_signals_history = max_signals_history
        self.max_errors_history = max_errors_history
        
        # Convert string log level to numeric if needed
        if isinstance(log_level, str):
            self.log_level = LogLevel.from_string(log_level)
        else:
            self.log_level = log_level
            
        # Initialize console with optional width
        self.console = Console(width=console_width)
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Set up file loggers
        self._setup_file_loggers()
        
        # Set up rich handler for console
        if use_rich:
            self._setup_rich_logger()
        
        # Dashboard state
        self.current_price = 0.0
        self.current_position = None
        self.recent_signals: List[SignalRecord] = []
        self.recent_trades: List[TradeRecord] = []
        self.errors: List[str] = []
        
        # Live display
        self.layout = self._create_layout()
        self.live = None
        
        # Log initialization
        self.log_info(f"Logger initialized with level: {logging.getLevelName(self.log_level)} "
                     f"({LogLevel.get_description(self.log_level)})")
    
    def _setup_file_loggers(self) -> None:
        """
        Set up file-based loggers for different types of logs with configurable log levels.
        
        This method configures multiple loggers:
        - Main logger: General application logs
        - Trade logger: Records of executed trades
        - Signal logger: Records of generated trading signals
        - Error logger: Detailed error logs
        """
        # Create formatter with more detailed format for file logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Main logger
        self.logger = logging.getLogger("crypto_bot")
        self.logger.setLevel(self.log_level)
        
        # Add file handler to main logger if log_file is specified
        if self.log_file:
            main_handler = logging.FileHandler(self.log_file)
            main_handler.setFormatter(formatter)
            main_handler.setLevel(self.log_level)
            
            # Remove existing handlers
            for handler in self.logger.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    self.logger.removeHandler(handler)
                    
            self.logger.addHandler(main_handler)
        
        # Trade logger - always at INFO level or lower
        self.trade_logger = logging.getLogger("crypto_bot.trades")
        trade_level = min(self.log_level, logging.INFO)  # Don't hide trades even at higher log levels
        self.trade_logger.setLevel(trade_level)
        
        # Remove existing handlers
        for handler in self.trade_logger.handlers[:]:
            self.trade_logger.removeHandler(handler)
            
        trade_handler = logging.FileHandler(f"{self.log_dir}/trades.log")
        trade_handler.setFormatter(formatter)
        self.trade_logger.addHandler(trade_handler)
        
        # Signal logger - configurable level
        self.signal_logger = logging.getLogger("crypto_bot.signals")
        self.signal_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        for handler in self.signal_logger.handlers[:]:
            self.signal_logger.removeHandler(handler)
            
        signal_handler = logging.FileHandler(f"{self.log_dir}/signals.log")
        signal_handler.setFormatter(formatter)
        self.signal_logger.addHandler(signal_handler)
        
        # Error logger - always at ERROR level or lower
        self.error_logger = logging.getLogger("crypto_bot.errors")
        error_level = min(self.log_level, logging.ERROR)  # Don't hide errors even at higher log levels
        self.error_logger.setLevel(error_level)
        
        # Remove existing handlers
        for handler in self.error_logger.handlers[:]:
            self.error_logger.removeHandler(handler)
            
        error_handler = logging.FileHandler(f"{self.log_dir}/errors.log")
        error_handler.setFormatter(formatter)
        self.error_logger.addHandler(error_handler)
    
    def _setup_rich_logger(self) -> None:
        """Set up rich handler for console logging"""
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add rich handler
        rich_handler = RichHandler(
            rich_tracebacks=True,
            console=self.console,
            show_time=True,
            omit_repeated_times=False
        )
        self.logger.addHandler(rich_handler)
    
    def _create_layout(self) -> Layout:
        """Create the layout for the rich live display"""
        layout = Layout(name="root")
        
        # Split into top and bottom
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Split main area into left and right
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Split left area into positions and trades
        layout["left"].split(
            Layout(name="market", size=10),
            Layout(name="positions", size=10),
            Layout(name="trades", ratio=1)
        )
        
        # Split right area into signals and errors
        layout["right"].split(
            Layout(name="signals", ratio=2),
            Layout(name="errors", ratio=1)
        )
        
        return layout
    
    def start_live_display(self) -> None:
        """Start the live display"""
        if not self.use_rich:
            return
            
        if self.live is None:
            self.live = Live(self.layout, refresh_per_second=1, screen=True)
            self.live.start()
            self.update_live_display()
    
    def stop_live_display(self) -> None:
        """Stop the live display"""
        if self.live:
            self.live.stop()
            self.live = None
    
    def update_live_display(self) -> None:
        """Update the live display with current data"""
        if not self.use_rich or not self.live:
            return
            
        # Update header
        self.layout["header"].update(
            Panel(
                Text(f"Crypto Trading Bot - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                     style="bold white on blue"),
                style="blue"
            )
        )
        
        # Update market data
        market_table = Table(title="Market Data", show_header=True, header_style="bold magenta")
        market_table.add_column("Symbol", style="dim")
        market_table.add_column("Price", justify="right")
        market_table.add_column("Last Updated", justify="right")
        
        if self.current_price > 0:
            market_table.add_row(
                "BTC/USD",
                f"${self.current_price:,.2f}",
                datetime.datetime.now().strftime("%H:%M:%S")
            )
        
        self.layout["market"].update(market_table)
        
        # Update positions
        position_table = Table(title="Current Positions", show_header=True, header_style="bold green")
        position_table.add_column("Symbol", style="dim")
        position_table.add_column("Quantity", justify="right")
        position_table.add_column("Value", justify="right")
        position_table.add_column("Avg Entry", justify="right")
        position_table.add_column("P&L", justify="right")
        
        if self.current_position:
            pnl_style = "green" if self.current_position.unrealized_pnl >= 0 else "red"
            position_table.add_row(
                self.current_position.symbol,
                f"{self.current_position.quantity:.8f}",
                f"${self.current_position.market_value:.2f}",
                f"${self.current_position.avg_entry_price:.2f}",
                Text(f"${self.current_position.unrealized_pnl:.2f}", style=pnl_style)
            )
        
        self.layout["positions"].update(position_table)
        
        # Update trades
        trades_table = Table(title="Recent Trades", show_header=True, header_style="bold yellow")
        trades_table.add_column("Time", style="dim")
        trades_table.add_column("Symbol")
        trades_table.add_column("Side", justify="center")
        trades_table.add_column("Quantity", justify="right")
        trades_table.add_column("Price", justify="right")
        trades_table.add_column("Status", justify="center")
        
        for trade in self.recent_trades[-10:]:  # Show last 10 trades
            side_style = "green" if trade.side == "BUY" else "red"
            trades_table.add_row(
                trade.timestamp.strftime("%H:%M:%S"),
                trade.symbol,
                Text(trade.side, style=side_style),
                f"{trade.quantity:.8f}",
                f"${trade.price:.2f}",
                trade.status
            )
        
        self.layout["trades"].update(trades_table)
        
        # Update signals
        signals_table = Table(title="Trading Signals", show_header=True, header_style="bold cyan")
        signals_table.add_column("Time", style="dim")
        signals_table.add_column("Action", justify="center")
        signals_table.add_column("Conf", justify="right")
        signals_table.add_column("Strategy")
        signals_table.add_column("Price", justify="right")
        
        for signal in self.recent_signals[-10:]:  # Show last 10 signals
            action_style = "green" if signal.action == "BUY" else "red" if signal.action == "SELL" else "yellow"
            signals_table.add_row(
                signal.timestamp.strftime("%H:%M:%S"),
                Text(signal.action, style=action_style),
                f"{signal.confidence:.2f}",
                signal.strategy,
                f"${signal.price:.2f}"
            )
        
        self.layout["signals"].update(signals_table)
        
        # Update errors
        errors_panel = Panel(
            "\n".join(self.errors[-5:]) if self.errors else "No errors",
            title="Recent Errors",
            border_style="red"
        )
        self.layout["errors"].update(errors_panel)
        
        # Update footer
        self.layout["footer"].update(
            Panel(
                Text("Press Ctrl+C to exit", style="italic"),
                style="blue"
            )
        )
    
    def log_trade(self, trade: TradeRecord) -> None:
        """
        Log a trade to both file and terminal display.
        
        Args:
            trade: Trade record to log
        """
        # Log to file
        self.trade_logger.info(f"TRADE: {trade.side} {trade.quantity} {trade.symbol} @ ${trade.price:.2f} - Status: {trade.status}")
        
        # Add to recent trades
        self.recent_trades.append(trade)
        if len(self.recent_trades) > self.max_trades_history:
            self.recent_trades.pop(0)
        
        # Update terminal display
        if self.use_rich:
            side_color = "green" if trade.side == "BUY" else "red"
            self.console.print(f"[bold {side_color}]{trade.side}[/bold {side_color}] {trade.quantity} {trade.symbol} @ ${trade.price:.2f} - Status: {trade.status}")
            self.update_live_display()
    
    def log_signal(self, signal: SignalRecord) -> None:
        """
        Log a trading signal to both file and terminal display.
        
        Args:
            signal: Signal record to log
        """
        # Log to file
        self.signal_logger.info(f"SIGNAL: {signal.action} {signal.symbol} (Confidence: {signal.confidence:.2f}) - Strategy: {signal.strategy}")
        
        # Add to recent signals
        self.recent_signals.append(signal)
        if len(self.recent_signals) > self.max_signals_history:
            self.recent_signals.pop(0)
        
        # Update terminal display
        if self.use_rich:
            action_color = "green" if signal.action == "BUY" else "red" if signal.action == "SELL" else "yellow"
            self.console.print(f"[bold {action_color}]{signal.action}[/bold {action_color}] signal for {signal.symbol} - Confidence: {signal.confidence:.2f} - Strategy: {signal.strategy}")
            self.update_live_display()
    
    def log_error(self, error: Exception, context: str) -> None:
        """
        Log an error to both file and terminal display.
        
        Args:
            error: Exception that occurred
            context: Context in which the error occurred
        """
        error_msg = f"{context}: {str(error)}"
        
        # Log to file
        self.error_logger.error(error_msg, exc_info=True)
        
        # Add to recent errors
        self.errors.append(error_msg)
        if len(self.errors) > self.max_errors_history:
            self.errors.pop(0)
        
        # Update terminal display
        if self.use_rich:
            self.console.print(f"[bold red]ERROR:[/bold red] {error_msg}")
            self.update_live_display()
    
    def log_info(self, message: str) -> None:
        """
        Log an informational message.
        
        Args:
            message: Message to log
        """
        self.logger.info(message)
    
    def log_warning(self, message: str) -> None:
        """
        Log a warning message.
        
        Args:
            message: Warning message to log
        """
        self.logger.warning(message)
        
        if self.use_rich:
            self.console.print(f"[bold yellow]WARNING:[/bold yellow] {message}")
    
    def update_price(self, symbol: str, price: float) -> None:
        """
        Update the current price for a symbol.
        
        Args:
            symbol: Symbol to update price for
            price: Current price
        """
        self.current_price = price
        self.update_live_display()
    
    def update_position(self, position: PositionRecord) -> None:
        """
        Update the current position.
        
        Args:
            position: Current position record
        """
        self.current_position = position
        self.update_live_display()
    
    def display_dashboard(self, data: Dict[str, Any]) -> None:
        """
        Display a dashboard with the provided data.
        
        Args:
            data: Dictionary of data to display
        """
        if not self.use_rich:
            return
            
        # Update data
        if "price" in data:
            self.current_price = data["price"]
        if "position" in data:
            self.current_position = data["position"]
        
        self.update_live_display()