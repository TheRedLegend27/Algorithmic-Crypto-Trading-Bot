"""
Comprehensive error handling system for the crypto trading bot.

This module provides centralized error handling functionality including:
- Error categorization and prioritization
- Recovery strategies for different error types
- Notification and reporting mechanisms
- Metrics collection for error frequency and patterns

Classes:
    ErrorCategory: Enum for categorizing errors
    ErrorHandler: Main error handling orchestrator
    RecoveryStrategy: Base class for error recovery strategies
"""
import logging
import time
import traceback
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Type, Union
from dataclasses import dataclass, field

from bot.utils import retry_with_backoff, format_error_for_user


class ErrorCategory(Enum):
    """Categorization of errors by severity and type"""
    # Severity levels
    CRITICAL = "critical"  # Requires immediate attention, cannot continue
    SEVERE = "severe"      # Serious issue but can continue with degraded functionality
    WARNING = "warning"    # Issue that should be addressed but doesn't affect core functionality
    INFO = "info"          # Informational error, no action required
    
    # Error types
    API_ERROR = "api_error"                # API-related errors (rate limits, auth issues)
    NETWORK_ERROR = "network_error"        # Network connectivity issues
    DATA_ERROR = "data_error"              # Data validation or processing errors
    CONFIGURATION_ERROR = "config_error"   # Configuration or setup errors
    RUNTIME_ERROR = "runtime_error"        # Unexpected runtime errors
    SYSTEM_ERROR = "system_error"          # System-level errors (disk space, memory)


@dataclass
class ErrorContext:
    """Context information about an error"""
    error: Exception
    category: ErrorCategory
    component: str
    timestamp: float = field(default_factory=time.time)
    traceback: str = field(default_factory=str)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Capture traceback if not provided"""
        if not self.traceback:
            self.traceback = traceback.format_exc()


class RecoveryStrategy:
    """Base class for error recovery strategies"""
    
    def __init__(self, name: str, max_attempts: int = 3):
        """
        Initialize the recovery strategy.
        
        Args:
            name: Name of the recovery strategy
            max_attempts: Maximum number of recovery attempts
        """
        self.name = name
        self.max_attempts = max_attempts
        self.attempts = 0
    
    def can_recover(self, error_context: ErrorContext) -> bool:
        """
        Determine if this strategy can recover from the given error.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            bool: True if this strategy can recover from the error
        """
        return self.attempts < self.max_attempts
    
    def execute(self, error_context: ErrorContext) -> bool:
        """
        Execute the recovery strategy.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            bool: True if recovery was successful
        """
        self.attempts += 1
        return False  # Base implementation does nothing
    
    def reset(self) -> None:
        """Reset the recovery strategy state"""
        self.attempts = 0


class RetryRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy that retries the operation with backoff"""
    
    def __init__(self, name: str = "retry", max_attempts: int = 3, 
                initial_delay: float = 1.0, backoff_factor: float = 2.0,
                max_delay: float = 60.0):
        """
        Initialize the retry recovery strategy.
        
        Args:
            name: Name of the recovery strategy
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            backoff_factor: Multiplier for the delay on each retry
            max_delay: Maximum delay in seconds
        """
        super().__init__(name, max_attempts)
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
    
    def execute(self, error_context: ErrorContext) -> bool:
        """
        Execute the retry recovery strategy.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            bool: True if retry was scheduled
        """
        super().execute(error_context)
        
        # Calculate delay with exponential backoff
        delay = min(
            self.initial_delay * (self.backoff_factor ** (self.attempts - 1)),
            self.max_delay
        )
        
        # Log the retry attempt
        logging.warning(
            f"Recovery strategy '{self.name}' scheduling retry {self.attempts}/{self.max_attempts} "
            f"in {delay:.2f}s for error in component '{error_context.component}'"
        )
        
        # Sleep for the calculated delay
        time.sleep(delay)
        
        return True


class FallbackRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy that falls back to an alternative implementation"""
    
    def __init__(self, name: str = "fallback", fallback_function: Callable = None):
        """
        Initialize the fallback recovery strategy.
        
        Args:
            name: Name of the recovery strategy
            fallback_function: Function to call as a fallback
        """
        super().__init__(name, max_attempts=1)
        self.fallback_function = fallback_function
    
    def execute(self, error_context: ErrorContext) -> bool:
        """
        Execute the fallback recovery strategy.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            bool: True if fallback was executed
        """
        super().execute(error_context)
        
        if self.fallback_function:
            try:
                # Log the fallback attempt
                logging.warning(
                    f"Recovery strategy '{self.name}' executing fallback for error "
                    f"in component '{error_context.component}'"
                )
                
                # Execute the fallback function
                self.fallback_function(error_context)
                return True
            except Exception as e:
                logging.error(f"Fallback function failed: {str(e)}")
                return False
        
        return False


class ErrorHandler:
    """
    Centralized error handling system for the crypto trading bot.
    
    This class provides methods for handling errors, applying recovery strategies,
    and tracking error metrics.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the error handler.
        
        Args:
            logger: Logger instance to use (uses root logger if None)
        """
        self.logger = logger or logging.getLogger()
        self.recovery_strategies: Dict[ErrorCategory, List[RecoveryStrategy]] = {}
        self.error_counts: Dict[ErrorCategory, int] = {cat: 0 for cat in ErrorCategory}
        self.recent_errors: List[ErrorContext] = []
        self.max_recent_errors = 100
        
        # Register default recovery strategies
        self._register_default_strategies()
    
    def _register_default_strategies(self) -> None:
        """Register default recovery strategies for different error categories"""
        # API errors - retry with backoff
        self.register_recovery_strategy(
            ErrorCategory.API_ERROR,
            RetryRecoveryStrategy(
                name="api_retry",
                max_attempts=5,
                initial_delay=2.0,
                backoff_factor=2.0
            )
        )
        
        # Network errors - retry with backoff
        self.register_recovery_strategy(
            ErrorCategory.NETWORK_ERROR,
            RetryRecoveryStrategy(
                name="network_retry",
                max_attempts=3,
                initial_delay=1.0,
                backoff_factor=2.0
            )
        )
    
    def register_recovery_strategy(self, category: ErrorCategory, 
                                 strategy: RecoveryStrategy) -> None:
        """
        Register a recovery strategy for an error category.
        
        Args:
            category: Error category to register the strategy for
            strategy: Recovery strategy to register
        """
        if category not in self.recovery_strategies:
            self.recovery_strategies[category] = []
        
        self.recovery_strategies[category].append(strategy)
    
    def categorize_error(self, error: Exception, component: str) -> ErrorCategory:
        """
        Categorize an error based on its type and context.
        
        Args:
            error: The exception to categorize
            component: The component where the error occurred
            
        Returns:
            ErrorCategory: The categorization of the error
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # API errors
        if any(term in error_msg for term in ["api", "rate limit", "unauthorized", "forbidden"]):
            return ErrorCategory.API_ERROR
        
        # Network errors
        if any(term in error_msg for term in ["connection", "timeout", "network", "socket"]):
            return ErrorCategory.NETWORK_ERROR
        
        # Data errors
        if any(term in error_msg for term in ["data", "parse", "json", "value", "type"]):
            return ErrorCategory.DATA_ERROR
        
        # Configuration errors
        if any(term in error_msg for term in ["config", "setting", "parameter", "argument"]):
            return ErrorCategory.CONFIGURATION_ERROR
        
        # System errors
        if any(term in error_msg for term in ["memory", "disk", "space", "resource"]):
            return ErrorCategory.SYSTEM_ERROR
        
        # Default to runtime error
        return ErrorCategory.RUNTIME_ERROR
    
    def handle_error(self, error: Exception, component: str, 
                   additional_info: Dict[str, Any] = None) -> bool:
        """
        Handle an error by categorizing it and applying recovery strategies.
        
        Args:
            error: The exception to handle
            component: The component where the error occurred
            additional_info: Additional context information
            
        Returns:
            bool: True if recovery was successful
        """
        # Categorize the error
        category = self.categorize_error(error, component)
        
        # Create error context
        context = ErrorContext(
            error=error,
            category=category,
            component=component,
            additional_info=additional_info or {}
        )
        
        # Log the error
        self._log_error(context)
        
        # Track error metrics
        self._track_error(context)
        
        # Apply recovery strategies
        return self._apply_recovery_strategies(context)
    
    def _log_error(self, context: ErrorContext) -> None:
        """
        Log an error with appropriate severity level.
        
        Args:
            context: Error context to log
        """
        error_msg = f"Error in {context.component}: {str(context.error)}"
        
        if context.category in [ErrorCategory.CRITICAL, ErrorCategory.SEVERE]:
            self.logger.error(error_msg)
            self.logger.debug(f"Traceback: {context.traceback}")
        elif context.category == ErrorCategory.WARNING:
            self.logger.warning(error_msg)
        else:
            self.logger.info(error_msg)
    
    def _track_error(self, context: ErrorContext) -> None:
        """
        Track error metrics.
        
        Args:
            context: Error context to track
        """
        # Increment error count for this category
        self.error_counts[context.category] = self.error_counts.get(context.category, 0) + 1
        
        # Add to recent errors
        self.recent_errors.append(context)
        
        # Trim recent errors list if needed
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]
    
    def _apply_recovery_strategies(self, context: ErrorContext) -> bool:
        """
        Apply recovery strategies for an error.
        
        Args:
            context: Error context to recover from
            
        Returns:
            bool: True if recovery was successful
        """
        # Get strategies for this error category
        strategies = self.recovery_strategies.get(context.category, [])
        
        # Try each strategy in order
        for strategy in strategies:
            if strategy.can_recover(context):
                if strategy.execute(context):
                    return True
        
        # No successful recovery
        return False
    
    def get_error_metrics(self) -> Dict[str, Any]:
        """
        Get error metrics.
        
        Returns:
            Dict: Error metrics
        """
        return {
            "counts": {cat.name: count for cat, count in self.error_counts.items()},
            "recent": len(self.recent_errors),
            "categories": {cat.name: cat.value for cat in ErrorCategory}
        }
    
    def reset_metrics(self) -> None:
        """Reset error metrics"""
        self.error_counts = {cat: 0 for cat in ErrorCategory}
        self.recent_errors = []


# Create a global instance for convenience
global_error_handler = ErrorHandler()


def handle_error(error: Exception, component: str, 
               additional_info: Dict[str, Any] = None) -> bool:
    """
    Handle an error using the global error handler.
    
    Args:
        error: The exception to handle
        component: The component where the error occurred
        additional_info: Additional context information
        
    Returns:
        bool: True if recovery was successful
    """
    return global_error_handler.handle_error(error, component, additional_info)


@dataclass
class ErrorReport:
    """Report of errors for a time period"""
    start_time: float
    end_time: float
    total_errors: int
    errors_by_category: Dict[ErrorCategory, int]
    errors_by_component: Dict[str, int]
    most_frequent_errors: List[Dict[str, Any]]
    
    @classmethod
    def generate(cls, error_handler: ErrorHandler, 
               time_window: Optional[float] = None) -> 'ErrorReport':
        """
        Generate an error report.
        
        Args:
            error_handler: Error handler to generate report from
            time_window: Time window in seconds (None for all time)
            
        Returns:
            ErrorReport: Generated report
        """
        now = time.time()
        start_time = now - time_window if time_window else 0
        
        # Filter errors by time window
        errors = [e for e in error_handler.recent_errors if e.timestamp >= start_time]
        
        # Count errors by category
        errors_by_category = {}
        for error in errors:
            if error.category not in errors_by_category:
                errors_by_category[error.category] = 0
            errors_by_category[error.category] += 1
        
        # Count errors by component
        errors_by_component = {}
        for error in errors:
            if error.component not in errors_by_component:
                errors_by_component[error.component] = 0
            errors_by_component[error.component] += 1
        
        # Find most frequent errors
        error_types = {}
        for error in errors:
            error_type = type(error.error).__name__
            if error_type not in error_types:
                error_types[error_type] = {
                    "type": error_type,
                    "count": 0,
                    "examples": []
                }
            
            error_types[error_type]["count"] += 1
            
            # Add example if we have fewer than 3
            if len(error_types[error_type]["examples"]) < 3:
                error_types[error_type]["examples"].append(str(error.error))
        
        # Sort by count and take top 5
        most_frequent = sorted(
            error_types.values(),
            key=lambda x: x["count"],
            reverse=True
        )[:5]
        
        return cls(
            start_time=start_time,
            end_time=now,
            total_errors=len(errors),
            errors_by_category=errors_by_category,
            errors_by_component=errors_by_component,
            most_frequent_errors=most_frequent
        )