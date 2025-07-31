"""
Enhanced logging system with structured data for the crypto trading bot.

This module provides comprehensive logging capabilities with JSON structured logging,
performance metrics tracking, daily reporting, error categorization, and log rotation.

Classes:
    ErrorSeverity: Enum for error severity levels
    TradeExecution: Data structure for trade execution records
    TradingSignal: Data structure for trading signals
    PerformanceMetrics: Data structure for performance metrics
    SystemHealth: Data structure for system health metrics
    DailyReport: Data structure for daily reports
    EnhancedLogger: Main enhanced logging class
"""
import os
import json
import logging
import datetime
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import gzip
import shutil


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TradeExecution:
    """Data structure for trade execution records"""
    trade_id: str
    pair: str
    side: str  # 'BUY' or 'SELL'
    order_type: str  # 'market', 'limit', 'stop_loss', etc.
    volume: float
    price: float
    fee: float
    timestamp: datetime.datetime
    strategy: str
    signal_confidence: float
    execution_time_ms: int
    status: str  # 'filled', 'partial', 'cancelled', 'failed'
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    slippage: Optional[float] = None
    
    @property
    def quantity(self) -> float:
        """Alias for volume to maintain compatibility with alert system."""
        return self.volume
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime to ISO string
        if isinstance(data.get('timestamp'), datetime.datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        # Add quantity for compatibility
        data['quantity'] = self.quantity
        return data


@dataclass
class TradingSignal:
    """Data structure for trading signals"""
    signal_id: str
    pair: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    strategy: str
    price: float
    timestamp: datetime.datetime
    reasoning: str
    indicators: Dict[str, float] = field(default_factory=dict)
    risk_score: Optional[float] = None
    expected_return: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime to ISO string
        if isinstance(data.get('timestamp'), datetime.datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data


@dataclass
class PerformanceMetrics:
    """Data structure for performance metrics"""
    timestamp: datetime.datetime
    total_trades: int
    successful_trades: int
    failed_trades: int
    total_volume_usd: float
    total_fees_usd: float
    realized_pnl: float
    unrealized_pnl: float
    win_rate: float
    average_trade_duration_minutes: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    portfolio_value_usd: float = 0.0
    daily_return: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime to ISO string
        if isinstance(data.get('timestamp'), datetime.datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data


@dataclass
class SystemHealth:
    """Data structure for system health metrics"""
    timestamp: datetime.datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    api_response_time_ms: float
    websocket_connection_status: str
    active_orders: int
    open_positions: int
    last_trade_time: Optional[datetime.datetime] = None
    error_count_last_hour: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime to ISO string
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = value.isoformat()
        return data


@dataclass
class DailyReport:
    """Data structure for daily reports"""
    date: datetime.date
    total_trades: int
    successful_trades: int
    total_volume_usd: float
    total_fees_usd: float
    realized_pnl: float
    unrealized_pnl: float
    net_pnl: float
    win_rate: float
    best_trade_pnl: float
    worst_trade_pnl: float
    average_trade_size_usd: float
    portfolio_start_value: float
    portfolio_end_value: float
    daily_return_percent: float
    strategies_used: List[str] = field(default_factory=list)
    error_count: int = 0
    api_calls: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert date to ISO string
        if isinstance(data.get('date'), datetime.date):
            data['date'] = data['date'].isoformat()
        return data


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            'timestamp': datetime.datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        
        return json.dumps(log_entry, default=str)


class EnhancedLogger:
    """
    Enhanced logging system with structured data, performance metrics,
    and comprehensive reporting capabilities.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the enhanced logger.
        
        Args:
            config: Configuration dictionary with logging settings
        """
        # Default configuration
        default_config = {
            'log_dir': 'logs',
            'log_level': logging.INFO,
            'max_file_size_mb': 50,
            'backup_count': 10,
            'rotation_when': 'midnight',
            'rotation_interval': 1,
            'compression': True,
            'structured_logging': True,
            'performance_tracking': True,
            'daily_reports': True
        }
        
        # Merge with provided config
        self.config = {**default_config, **(config or {})}
        
        # Create log directory
        self.log_dir = Path(self.config['log_dir'])
        self.log_dir.mkdir(exist_ok=True)
        
        # Initialize loggers
        self._setup_loggers()
        
        # Performance tracking
        self.trades_today: List[TradeExecution] = []
        self.signals_today: List[TradingSignal] = []
        self.errors_today: List[Dict[str, Any]] = []
        self.daily_metrics: Dict[str, Any] = {}
        self.last_report_date = datetime.date.today()
        
        # System health tracking
        self.last_health_check = datetime.datetime.now()
        self.health_check_interval = 300  # 5 minutes
        
        self.logger.info("Enhanced logger initialized", extra={
            'extra_data': {'config': self.config}
        })
    
    def _setup_loggers(self) -> None:
        """Set up all loggers with appropriate handlers"""
        # Main logger
        self.logger = logging.getLogger("enhanced_crypto_bot")
        self.logger.setLevel(self.config['log_level'])
        self.logger.handlers.clear()
        
        # JSON formatter for structured logging
        if self.config['structured_logging']:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Main log file with rotation
        main_handler = TimedRotatingFileHandler(
            filename=self.log_dir / 'enhanced_bot.log',
            when=self.config['rotation_when'],
            interval=self.config['rotation_interval'],
            backupCount=self.config['backup_count']
        )
        main_handler.setFormatter(formatter)
        if self.config['compression']:
            main_handler.rotator = self._compress_rotated_file
        self.logger.addHandler(main_handler)
        
        # Trade execution logger
        self.trade_logger = logging.getLogger("enhanced_crypto_bot.trades")
        self.trade_logger.setLevel(logging.INFO)
        self.trade_logger.handlers.clear()
        
        trade_handler = RotatingFileHandler(
            filename=self.log_dir / 'trades.log',
            maxBytes=self.config['max_file_size_mb'] * 1024 * 1024,
            backupCount=self.config['backup_count']
        )
        trade_handler.setFormatter(formatter)
        if self.config['compression']:
            trade_handler.rotator = self._compress_rotated_file
        self.trade_logger.addHandler(trade_handler)
        
        # Signal logger
        self.signal_logger = logging.getLogger("enhanced_crypto_bot.signals")
        self.signal_logger.setLevel(logging.INFO)
        self.signal_logger.handlers.clear()
        
        signal_handler = RotatingFileHandler(
            filename=self.log_dir / 'signals.log',
            maxBytes=self.config['max_file_size_mb'] * 1024 * 1024,
            backupCount=self.config['backup_count']
        )
        signal_handler.setFormatter(formatter)
        if self.config['compression']:
            signal_handler.rotator = self._compress_rotated_file
        self.signal_logger.addHandler(signal_handler)
        
        # Performance metrics logger
        self.metrics_logger = logging.getLogger("enhanced_crypto_bot.metrics")
        self.metrics_logger.setLevel(logging.INFO)
        self.metrics_logger.handlers.clear()
        
        metrics_handler = TimedRotatingFileHandler(
            filename=self.log_dir / 'performance_metrics.log',
            when='midnight',
            interval=1,
            backupCount=30  # Keep 30 days of metrics
        )
        metrics_handler.setFormatter(formatter)
        if self.config['compression']:
            metrics_handler.rotator = self._compress_rotated_file
        self.metrics_logger.addHandler(metrics_handler)
        
        # Error logger with categorization
        self.error_logger = logging.getLogger("enhanced_crypto_bot.errors")
        self.error_logger.setLevel(logging.WARNING)
        self.error_logger.handlers.clear()
        
        error_handler = RotatingFileHandler(
            filename=self.log_dir / 'errors.log',
            maxBytes=self.config['max_file_size_mb'] * 1024 * 1024,
            backupCount=self.config['backup_count']
        )
        error_handler.setFormatter(formatter)
        if self.config['compression']:
            error_handler.rotator = self._compress_rotated_file
        self.error_logger.addHandler(error_handler)
        
        # Daily reports logger
        self.report_logger = logging.getLogger("enhanced_crypto_bot.reports")
        self.report_logger.setLevel(logging.INFO)
        self.report_logger.handlers.clear()
        
        report_handler = TimedRotatingFileHandler(
            filename=self.log_dir / 'daily_reports.log',
            when='midnight',
            interval=1,
            backupCount=365  # Keep 1 year of daily reports
        )
        report_handler.setFormatter(formatter)
        if self.config['compression']:
            report_handler.rotator = self._compress_rotated_file
        self.report_logger.addHandler(report_handler)
    
    def _compress_rotated_file(self, source: str, dest: str) -> None:
        """Compress rotated log files"""
        with open(source, 'rb') as f_in:
            with gzip.open(f"{dest}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)
    
    def log_trade(self, trade: TradeExecution) -> None:
        """
        Log a trade execution with structured data.
        
        Args:
            trade: Trade execution record
        """
        trade_data = trade.to_dict()
        
        # Log to trade logger
        self.trade_logger.info("Trade executed", extra={
            'extra_data': {
                'event_type': 'trade_execution',
                'trade_data': trade_data
            }
        })
        
        # Add to daily tracking
        self.trades_today.append(trade)
        
        # Log summary to main logger
        self.logger.info(
            f"Trade executed: {trade.side} {trade.volume} {trade.pair} @ {trade.price}",
            extra={
                'extra_data': {
                    'trade_id': trade.trade_id,
                    'strategy': trade.strategy,
                    'confidence': trade.signal_confidence
                }
            }
        )
        
        # Check if daily report is needed
        self._check_daily_report()
    
    def log_signal(self, signal: TradingSignal, execution_result: Optional[TradeExecution] = None) -> None:
        """
        Log a trading signal with execution result.
        
        Args:
            signal: Trading signal record
            execution_result: Optional trade execution result
        """
        signal_data = signal.to_dict()
        
        # Add execution result if provided
        if execution_result:
            signal_data['execution_result'] = execution_result.to_dict()
        
        # Log to signal logger
        self.signal_logger.info("Trading signal generated", extra={
            'extra_data': {
                'event_type': 'trading_signal',
                'signal_data': signal_data
            }
        })
        
        # Add to daily tracking
        self.signals_today.append(signal)
        
        # Log summary to main logger
        self.logger.info(
            f"Signal: {signal.action} {signal.pair} (confidence: {signal.confidence:.2f})",
            extra={
                'extra_data': {
                    'signal_id': signal.signal_id,
                    'strategy': signal.strategy,
                    'reasoning': signal.reasoning
                }
            }
        )
    
    def log_performance_metrics(self, metrics: PerformanceMetrics) -> None:
        """
        Log performance metrics.
        
        Args:
            metrics: Performance metrics record
        """
        metrics_data = metrics.to_dict()
        
        # Log to metrics logger
        self.metrics_logger.info("Performance metrics", extra={
            'extra_data': {
                'event_type': 'performance_metrics',
                'metrics_data': metrics_data
            }
        })
        
        # Update daily metrics
        self.daily_metrics.update(metrics_data)
        
        # Log key metrics to main logger
        self.logger.info(
            f"Performance: {metrics.total_trades} trades, "
            f"Win rate: {metrics.win_rate:.1%}, "
            f"P&L: ${metrics.realized_pnl:.2f}",
            extra={
                'extra_data': {
                    'portfolio_value': metrics.portfolio_value_usd,
                    'sharpe_ratio': metrics.sharpe_ratio
                }
            }
        )
    
    def log_error(self, error: Exception, context: Dict[str, Any], severity: ErrorSeverity) -> None:
        """
        Log an error with categorization and context.
        
        Args:
            error: Exception that occurred
            context: Context information
            severity: Error severity level
        """
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'severity': severity.value,
            'context': context,
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        # Log to error logger
        log_level = self._get_log_level_for_severity(severity)
        self.error_logger.log(log_level, "Error occurred", extra={
            'extra_data': {
                'event_type': 'error',
                'error_data': error_data
            }
        }, exc_info=True)
        
        # Add to daily tracking
        self.errors_today.append(error_data)
        
        # Log to main logger based on severity
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.error(
                f"[{severity.value.upper()}] {type(error).__name__}: {str(error)}",
                extra={'extra_data': context},
                exc_info=True
            )
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(
                f"[{severity.value.upper()}] {type(error).__name__}: {str(error)}",
                extra={'extra_data': context}
            )
        else:
            self.logger.info(
                f"[{severity.value.upper()}] {type(error).__name__}: {str(error)}",
                extra={'extra_data': context}
            )
    
    def log_system_health(self, health_metrics: SystemHealth) -> None:
        """
        Log system health metrics.
        
        Args:
            health_metrics: System health metrics
        """
        health_data = health_metrics.to_dict()
        
        # Log to main logger
        self.logger.info("System health check", extra={
            'extra_data': {
                'event_type': 'system_health',
                'health_data': health_data
            }
        })
        
        # Check for health issues
        if health_metrics.cpu_usage_percent > 80:
            self.log_error(
                RuntimeError("High CPU usage detected"),
                {'cpu_usage': health_metrics.cpu_usage_percent},
                ErrorSeverity.MEDIUM
            )
        
        if health_metrics.memory_usage_percent > 85:
            self.log_error(
                RuntimeError("High memory usage detected"),
                {'memory_usage': health_metrics.memory_usage_percent},
                ErrorSeverity.MEDIUM
            )
        
        if health_metrics.websocket_connection_status != 'connected':
            self.log_error(
                ConnectionError("WebSocket connection issue"),
                {'status': health_metrics.websocket_connection_status},
                ErrorSeverity.HIGH
            )
        
        self.last_health_check = datetime.datetime.now()
    
    def generate_daily_report(self, date: Optional[datetime.date] = None) -> DailyReport:
        """
        Generate a daily trading report.
        
        Args:
            date: Date for the report (defaults to today)
            
        Returns:
            DailyReport: Generated daily report
        """
        if date is None:
            date = datetime.date.today()
        
        # Calculate metrics from today's trades
        trades = [t for t in self.trades_today if t.timestamp.date() == date]
        successful_trades = [t for t in trades if t.status == 'filled']
        
        total_volume = sum(t.volume * t.price for t in trades)
        total_fees = sum(t.fee for t in trades)
        # Calculate realized P&L
        realized_pnl = 0
        for t in successful_trades:
            if t.side == "BUY":
                pnl = ((t.fill_price or t.price) - t.price) * t.volume - t.fee
            else:
                pnl = (t.price - (t.fill_price or t.price)) * t.volume - t.fee
            realized_pnl += pnl
        
        # Calculate win rate
        profitable_trades = []
        for t in successful_trades:
            if t.side == "BUY":
                # For buy orders, profit is when fill_price > price (bought low, can sell high)
                profit = ((t.fill_price or t.price) - t.price) * t.volume - t.fee
            else:
                # For sell orders, profit is when price > fill_price (sold high, bought low)
                profit = (t.price - (t.fill_price or t.price)) * t.volume - t.fee
            
            if profit > 0:
                profitable_trades.append(t)
        win_rate = len(profitable_trades) / len(successful_trades) if successful_trades else 0
        
        # Best and worst trades
        trade_pnls = []
        for t in successful_trades:
            if t.side == "BUY":
                pnl = ((t.fill_price or t.price) - t.price) * t.volume - t.fee
            else:
                pnl = (t.price - (t.fill_price or t.price)) * t.volume - t.fee
            trade_pnls.append(pnl)
        best_trade = max(trade_pnls) if trade_pnls else 0
        worst_trade = min(trade_pnls) if trade_pnls else 0
        
        # Average trade size
        avg_trade_size = total_volume / len(trades) if trades else 0
        
        # Strategies used
        strategies = list(set(t.strategy for t in trades))
        
        # Create report
        report = DailyReport(
            date=date,
            total_trades=len(trades),
            successful_trades=len(successful_trades),
            total_volume_usd=total_volume,
            total_fees_usd=total_fees,
            realized_pnl=realized_pnl,
            unrealized_pnl=self.daily_metrics.get('unrealized_pnl', 0),
            net_pnl=realized_pnl + self.daily_metrics.get('unrealized_pnl', 0),
            win_rate=win_rate,
            best_trade_pnl=best_trade,
            worst_trade_pnl=worst_trade,
            average_trade_size_usd=avg_trade_size,
            portfolio_start_value=self.daily_metrics.get('portfolio_start_value', 0),
            portfolio_end_value=self.daily_metrics.get('portfolio_value_usd', 0),
            daily_return_percent=self.daily_metrics.get('daily_return', 0),
            strategies_used=strategies,
            error_count=len(self.errors_today),
            api_calls=self.daily_metrics.get('api_calls', 0)
        )
        
        # Log the report
        self.report_logger.info("Daily report generated", extra={
            'extra_data': {
                'event_type': 'daily_report',
                'report_data': report.to_dict()
            }
        })
        
        # Save report to file
        report_file = self.log_dir / f"daily_report_{date.isoformat()}.json"
        with open(report_file, 'w') as f:
            json.dump(report.to_dict(), f, indent=2, default=str)
        
        self.logger.info(f"Daily report generated for {date}", extra={
            'extra_data': {
                'trades': report.total_trades,
                'pnl': report.net_pnl,
                'win_rate': report.win_rate
            }
        })
        
        return report
    
    def _check_daily_report(self) -> None:
        """Check if a daily report should be generated"""
        today = datetime.date.today()
        if today > self.last_report_date:
            # Generate report for previous day
            self.generate_daily_report(self.last_report_date)
            
            # Reset daily tracking
            self.trades_today = []
            self.signals_today = []
            self.errors_today = []
            self.daily_metrics = {}
            self.last_report_date = today
    
    def _get_log_level_for_severity(self, severity: ErrorSeverity) -> int:
        """Get logging level for error severity"""
        severity_map = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        return severity_map[severity]
    
    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get statistics about logged events.
        
        Returns:
            Dict: Log statistics
        """
        return {
            'trades_today': len(self.trades_today),
            'signals_today': len(self.signals_today),
            'errors_today': len(self.errors_today),
            'last_health_check': self.last_health_check.isoformat(),
            'log_directory': str(self.log_dir),
            'config': self.config
        }
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> None:
        """
        Clean up old log files.
        
        Args:
            days_to_keep: Number of days of logs to keep
        """
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        
        for log_file in self.log_dir.glob("*.log*"):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                log_file.unlink()
                self.logger.info(f"Cleaned up old log file: {log_file}")
    
    def export_logs_to_json(self, start_date: datetime.date, end_date: datetime.date, 
                           output_file: str) -> None:
        """
        Export logs to JSON format for analysis.
        
        Args:
            start_date: Start date for export
            end_date: End date for export
            output_file: Output file path
        """
        export_data = {
            'export_info': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'generated_at': datetime.datetime.now().isoformat()
            },
            'trades': [],
            'signals': [],
            'errors': [],
            'daily_reports': []
        }
        
        # Export trades
        for trade in self.trades_today:
            if start_date <= trade.timestamp.date() <= end_date:
                export_data['trades'].append(trade.to_dict())
        
        # Export signals
        for signal in self.signals_today:
            if start_date <= signal.timestamp.date() <= end_date:
                export_data['signals'].append(signal.to_dict())
        
        # Export errors
        for error in self.errors_today:
            error_date = datetime.datetime.fromisoformat(error['timestamp']).date()
            if start_date <= error_date <= end_date:
                export_data['errors'].append(error)
        
        # Export daily reports
        current_date = start_date
        while current_date <= end_date:
            report_file = self.log_dir / f"daily_report_{current_date.isoformat()}.json"
            if report_file.exists():
                with open(report_file, 'r') as f:
                    export_data['daily_reports'].append(json.load(f))
            current_date += datetime.timedelta(days=1)
        
        # Write export file
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        self.logger.info(f"Logs exported to {output_file}", extra={
            'extra_data': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'trades_count': len(export_data['trades']),
                'signals_count': len(export_data['signals']),
                'errors_count': len(export_data['errors'])
            }
        })


# Global instance for convenience
_global_enhanced_logger: Optional[EnhancedLogger] = None


def get_enhanced_logger(config: Optional[Dict[str, Any]] = None) -> EnhancedLogger:
    """
    Get the global enhanced logger instance.
    
    Args:
        config: Optional configuration for the logger
        
    Returns:
        EnhancedLogger: Global enhanced logger instance
    """
    global _global_enhanced_logger
    if _global_enhanced_logger is None:
        _global_enhanced_logger = EnhancedLogger(config)
    return _global_enhanced_logger