"""
Crypto-specific logging and monitoring for the trading bot.

This module extends the base TradingLogger with cryptocurrency-specific
logging features, metrics, and monitoring capabilities.

Classes:
    CryptoTradeRecord: Data structure for crypto trade information
    CryptoBalanceRecord: Data structure for crypto balance information
    CryptoMetricsRecord: Data structure for crypto trading metrics
    CryptoLogger: Main logger for crypto trading operations
"""
import os
import logging
import datetime
import json
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path

from bot.logger import TradingLogger, TradeRecord, SignalRecord, PositionRecord


@dataclass
class CryptoTradeRecord:
    """Data structure for crypto trade information"""
    order_id: str
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: float
    price: float
    timestamp: datetime.datetime
    status: str
    product_id: str  # e.g., "BTC-USD"
    base_currency: str  # e.g., "BTC"
    quote_currency: str  # e.g., "USD"
    fees: Optional[float] = None
    fee_currency: str = "USD"  # Currency in which fees are paid
    network_fee: Optional[float] = None  # Blockchain network fee if applicable
    exchange_fee: Optional[float] = None  # Exchange trading fee
    trade_type: str = "spot"  # spot, margin, futures, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        data = asdict(self)
        # Convert datetime to string for JSON serialization
        if "timestamp" in data and isinstance(data["timestamp"], datetime.datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data
        
    def to_trade_record(self) -> TradeRecord:
        """Convert to base TradeRecord"""
        return TradeRecord(
            order_id=self.order_id,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            price=self.price,
            timestamp=self.timestamp,
            status=self.status,
            fees=self.fees
        )


@dataclass
class CryptoBalanceRecord:
    """Data structure for crypto balance information"""
    currency: str  # e.g., "BTC"
    available: float  # Amount available for trading
    hold: float  # Amount on hold (in orders)
    total: float  # Total balance (available + hold)
    usd_value: float  # USD equivalent value
    timestamp: datetime.datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        data = asdict(self)
        # Convert datetime to string for JSON serialization
        if "timestamp" in data and isinstance(data["timestamp"], datetime.datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


@dataclass
class CryptoMetricsRecord:
    """Data structure for crypto trading metrics"""
    timestamp: datetime.datetime
    api_calls: int = 0  # Number of API calls made
    api_errors: int = 0  # Number of API errors encountered
    api_latency_ms: float = 0.0  # Average API latency in milliseconds
    websocket_messages: int = 0  # Number of WebSocket messages received
    websocket_errors: int = 0  # Number of WebSocket errors
    trades_executed: int = 0  # Number of trades executed
    trade_volume_usd: float = 0.0  # Total trade volume in USD
    fees_paid_usd: float = 0.0  # Total fees paid in USD
    rate_limit_hits: int = 0  # Number of rate limit hits
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        data = asdict(self)
        # Convert datetime to string for JSON serialization
        if "timestamp" in data and isinstance(data["timestamp"], datetime.datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


class CryptoLogger(TradingLogger):
    """
    Extended logger for cryptocurrency trading operations.
    
    This class extends the base TradingLogger with crypto-specific logging
    features, metrics tracking, and monitoring capabilities.
    """
    
    def __init__(self, log_dir: str = "logs", use_rich: bool = True,
                 log_level: Union[str, int] = logging.INFO, log_file: str = "bot.log",
                 max_trades_history: int = 50, max_signals_history: int = 50,
                 max_errors_history: int = 20, console_width: int = None,
                 metrics_interval_seconds: int = 60):
        """
        Initialize the crypto logger.
        
        Args:
            log_dir: Directory for log files
            use_rich: Whether to use rich for terminal display
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to main log file
            max_trades_history: Maximum number of trades to keep in history
            max_signals_history: Maximum number of signals to keep in history
            max_errors_history: Maximum number of errors to keep in history
            console_width: Width of the console display (None for auto-detect)
            metrics_interval_seconds: Interval for recording metrics in seconds
        """
        # Initialize the base logger
        super().__init__(log_dir, use_rich, log_level, log_file,
                         max_trades_history, max_signals_history,
                         max_errors_history, console_width)
        
        # Crypto-specific state
        self.crypto_balances: Dict[str, CryptoBalanceRecord] = {}
        self.recent_crypto_trades: List[CryptoTradeRecord] = []
        self.metrics_history: List[CryptoMetricsRecord] = []
        self.current_metrics = CryptoMetricsRecord(timestamp=datetime.datetime.now())
        self.metrics_interval_seconds = metrics_interval_seconds
        self.last_metrics_time = datetime.datetime.now()
        
        # Set up crypto-specific loggers
        self._setup_crypto_loggers()
        
        # Log initialization
        self.log_info("Crypto logger initialized")
    
    def _setup_crypto_loggers(self) -> None:
        """Set up crypto-specific loggers"""
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Balance logger
        self.balance_logger = logging.getLogger("crypto_bot.balances")
        self.balance_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        for handler in self.balance_logger.handlers[:]:
            self.balance_logger.removeHandler(handler)
            
        balance_handler = logging.FileHandler(f"{self.log_dir}/balances.log")
        balance_handler.setFormatter(formatter)
        self.balance_logger.addHandler(balance_handler)
        
        # Metrics logger
        self.metrics_logger = logging.getLogger("crypto_bot.metrics")
        self.metrics_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        for handler in self.metrics_logger.handlers[:]:
            self.metrics_logger.removeHandler(handler)
            
        metrics_handler = logging.FileHandler(f"{self.log_dir}/metrics.log")
        metrics_handler.setFormatter(formatter)
        self.metrics_logger.addHandler(metrics_handler)
    
    def log_crypto_trade(self, trade: CryptoTradeRecord) -> None:
        """
        Log a cryptocurrency trade with extended information.
        
        Args:
            trade: Crypto trade record to log
        """
        # Log to file with crypto-specific details
        self.trade_logger.info(
            f"CRYPTO_TRADE: {trade.side} {trade.quantity} {trade.base_currency} @ "
            f"${trade.price:.2f} - Fees: ${trade.fees if trade.fees else 0:.2f} - Status: {trade.status}"
        )
        
        # Add to recent trades
        self.recent_crypto_trades.append(trade)
        if len(self.recent_crypto_trades) > self.max_trades_history:
            self.recent_crypto_trades.pop(0)
        
        # Also add to base class trades for compatibility
        super().log_trade(trade.to_trade_record())
        
        # Update metrics
        self.current_metrics.trades_executed += 1
        self.current_metrics.trade_volume_usd += trade.quantity * trade.price
        self.current_metrics.fees_paid_usd += trade.fees if trade.fees else 0
        
        # Check if it's time to record metrics
        self._check_record_metrics()
    
    def log_balance_update(self, balance: CryptoBalanceRecord) -> None:
        """
        Log a cryptocurrency balance update.
        
        Args:
            balance: Crypto balance record to log
        """
        # Log to file
        self.balance_logger.info(
            f"BALANCE: {balance.currency} - Available: {balance.available:.8f} - "
            f"Hold: {balance.hold:.8f} - Total: {balance.total:.8f} - "
            f"USD Value: ${balance.usd_value:.2f}"
        )
        
        # Update stored balance
        self.crypto_balances[balance.currency] = balance
        
        # Update terminal display
        if self.use_rich:
            self.console.print(
                f"Balance updated: [bold]{balance.currency}[/bold] - "
                f"Total: {balance.total:.8f} (${balance.usd_value:.2f})"
            )
            self.update_live_display()
    
    def log_api_call(self, endpoint: str, latency_ms: float, success: bool) -> None:
        """
        Log an API call with performance metrics.
        
        Args:
            endpoint: API endpoint called
            latency_ms: Latency of the call in milliseconds
            success: Whether the call was successful
        """
        # Update metrics
        self.current_metrics.api_calls += 1
        
        # Update average latency
        if self.current_metrics.api_latency_ms == 0:
            self.current_metrics.api_latency_ms = latency_ms
        else:
            # Weighted average to smooth out spikes
            self.current_metrics.api_latency_ms = (
                0.9 * self.current_metrics.api_latency_ms + 0.1 * latency_ms
            )
        
        # Log errors
        if not success:
            self.current_metrics.api_errors += 1
        
        # Log to file if it's a slow call or error
        if latency_ms > 1000 or not success:
            status = "SUCCESS" if success else "ERROR"
            self.metrics_logger.info(
                f"API_CALL: {endpoint} - Latency: {latency_ms:.2f}ms - Status: {status}"
            )
        
        # Check if it's time to record metrics
        self._check_record_metrics()
    
    def log_websocket_message(self, channel: str, success: bool) -> None:
        """
        Log a WebSocket message.
        
        Args:
            channel: WebSocket channel
            success: Whether the message was processed successfully
        """
        # Update metrics
        self.current_metrics.websocket_messages += 1
        
        # Log errors
        if not success:
            self.current_metrics.websocket_errors += 1
            self.metrics_logger.warning(
                f"WEBSOCKET_ERROR: Failed to process message on channel {channel}"
            )
        
        # Check if it's time to record metrics
        self._check_record_metrics()
    
    def log_rate_limit_hit(self, endpoint: str, reset_time_seconds: int) -> None:
        """
        Log a rate limit hit.
        
        Args:
            endpoint: API endpoint that hit the rate limit
            reset_time_seconds: Time until rate limit resets in seconds
        """
        # Update metrics
        self.current_metrics.rate_limit_hits += 1
        
        # Log to file
        self.metrics_logger.warning(
            f"RATE_LIMIT: {endpoint} - Reset in {reset_time_seconds} seconds"
        )
        
        # Log to console
        if self.use_rich:
            self.console.print(
                f"[bold yellow]RATE LIMIT[/bold yellow]: {endpoint} - "
                f"Reset in {reset_time_seconds} seconds"
            )
        
        # Check if it's time to record metrics
        self._check_record_metrics()
    
    def _check_record_metrics(self) -> None:
        """Check if it's time to record metrics and do so if needed"""
        now = datetime.datetime.now()
        elapsed = (now - self.last_metrics_time).total_seconds()
        
        if elapsed >= self.metrics_interval_seconds:
            # Update timestamp
            self.current_metrics.timestamp = now
            
            # Record metrics
            self.metrics_history.append(self.current_metrics)
            
            # Log to file
            self.metrics_logger.info(
                f"METRICS: {json.dumps(self.current_metrics.to_dict())}"
            )
            
            # Reset metrics
            self.current_metrics = CryptoMetricsRecord(timestamp=now)
            self.last_metrics_time = now
            
            # Trim metrics history if needed (keep last 24 hours at 1-minute intervals)
            max_metrics = 24 * 60 * 60 // self.metrics_interval_seconds
            if len(self.metrics_history) > max_metrics:
                self.metrics_history = self.metrics_history[-max_metrics:]
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current portfolio.
        
        Returns:
            Dict: Portfolio summary
        """
        total_usd_value = sum(balance.usd_value for balance in self.crypto_balances.values())
        
        return {
            "total_usd_value": total_usd_value,
            "balances": {
                currency: {
                    "amount": balance.total,
                    "usd_value": balance.usd_value,
                    "percentage": (balance.usd_value / total_usd_value * 100) if total_usd_value > 0 else 0
                }
                for currency, balance in self.crypto_balances.items()
                if balance.total > 0
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the trading system.
        
        Returns:
            Dict: Performance metrics
        """
        if not self.metrics_history:
            return {
                "api_calls_per_minute": 0,
                "api_errors_rate": 0,
                "avg_latency_ms": 0,
                "websocket_messages_per_minute": 0,
                "websocket_error_rate": 0,
                "trades_per_minute": 0,
                "avg_trade_size_usd": 0,
                "rate_limit_hits": 0
            }
        
        # Calculate metrics from history
        total_api_calls = sum(m.api_calls for m in self.metrics_history)
        total_api_errors = sum(m.api_errors for m in self.metrics_history)
        total_ws_messages = sum(m.websocket_messages for m in self.metrics_history)
        total_ws_errors = sum(m.websocket_errors for m in self.metrics_history)
        total_trades = sum(m.trades_executed for m in self.metrics_history)
        total_volume = sum(m.trade_volume_usd for m in self.metrics_history)
        total_rate_limits = sum(m.rate_limit_hits for m in self.metrics_history)
        
        # Calculate averages
        minutes = len(self.metrics_history) * (self.metrics_interval_seconds / 60)
        if minutes == 0:
            minutes = 1  # Avoid division by zero
            
        api_calls_per_minute = total_api_calls / minutes
        api_error_rate = total_api_errors / total_api_calls if total_api_calls > 0 else 0
        ws_messages_per_minute = total_ws_messages / minutes
        ws_error_rate = total_ws_errors / total_ws_messages if total_ws_messages > 0 else 0
        trades_per_minute = total_trades / minutes
        avg_trade_size = total_volume / total_trades if total_trades > 0 else 0
        
        # Calculate average latency (weighted by number of calls)
        weighted_latency_sum = sum(m.api_latency_ms * m.api_calls for m in self.metrics_history)
        avg_latency = weighted_latency_sum / total_api_calls if total_api_calls > 0 else 0
        
        return {
            "api_calls_per_minute": api_calls_per_minute,
            "api_errors_rate": api_error_rate,
            "avg_latency_ms": avg_latency,
            "websocket_messages_per_minute": ws_messages_per_minute,
            "websocket_error_rate": ws_error_rate,
            "trades_per_minute": trades_per_minute,
            "avg_trade_size_usd": avg_trade_size,
            "rate_limit_hits": total_rate_limits
        }
    
    def update_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for updating the dashboard.
        
        Returns:
            Dict: Dashboard data
        """
        return {
            "portfolio": self.get_portfolio_summary(),
            "performance": self.get_performance_metrics(),
            "recent_trades": [trade.to_dict() for trade in self.recent_crypto_trades[-10:]],
            "recent_signals": [signal.to_dict() for signal in self.recent_signals[-10:]],
            "recent_errors": self.errors[-10:],
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    def export_metrics_to_json(self, filepath: str) -> None:
        """
        Export metrics to a JSON file.
        
        Args:
            filepath: Path to the output JSON file
        """
        data = {
            "portfolio": self.get_portfolio_summary(),
            "performance": self.get_performance_metrics(),
            "metrics_history": [m.to_dict() for m in self.metrics_history],
            "balances": {k: v.to_dict() for k, v in self.crypto_balances.items()},
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        self.log_info(f"Metrics exported to {filepath}")
    
    def _create_layout(self) -> Any:
        """Create the layout for the rich live display with crypto-specific panels"""
        # Get the base layout
        layout = super()._create_layout()
        
        # We'll just use the existing layout without modification for testing
        # In a real implementation, we would add crypto-specific panels
        
        return layout
    
    def update_live_display(self) -> None:
        """Update the live display with crypto-specific data"""
        if not self.use_rich or not self.live:
            return
            
        # Update the base display
        super().update_live_display()
        
        # In a real implementation, we would add crypto-specific metrics to the display
        # For testing, we'll just use the base display


# Create a global instance for convenience
global_crypto_logger = CryptoLogger()


def get_crypto_logger() -> CryptoLogger:
    """
    Get the global crypto logger instance.
    
    Returns:
        CryptoLogger: Global crypto logger instance
    """
    return global_crypto_logger