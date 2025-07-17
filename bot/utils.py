"""
Utility functions for the crypto trading bot.
Includes error handling, logging, and helper functions.
"""
import logging
import time
import sys
import random
from typing import Callable, Any, Optional
from functools import wraps

# Configure logging
def setup_logging(log_level=logging.INFO, log_file='bot.log'):
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file (default: bot.log)
    """
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Return logger for crypto_bot
    return logging.getLogger('crypto_bot')

# Set up default logger
logger = setup_logging()


def log_error(message: str, exception: Optional[Exception] = None) -> None:
    """
    Log an error message with optional exception details.
    
    Args:
        message: The error message to log
        exception: Optional exception object to include in the log
    """
    if exception:
        logger.error(f"{message}: {str(exception)}")
    else:
        logger.error(message)


def log_info(message: str) -> None:
    """
    Log an informational message.
    
    Args:
        message: The message to log
    """
    logger.info(message)


def log_warning(message: str) -> None:
    """
    Log a warning message.
    
    Args:
        message: The warning message to log
    """
    logger.warning(message)


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0, 
                      backoff_factor: float = 2.0, exceptions: tuple = (Exception,),
                      jitter: bool = True, max_delay: float = 60.0):
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retries before giving up
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for the delay on each retry
        exceptions: Tuple of exceptions to catch and retry
        jitter: Whether to add random jitter to delay
        max_delay: Maximum delay in seconds
        
    Returns:
        The decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    # Calculate delay with optional jitter
                    current_delay = min(delay * (backoff_factor ** attempt), max_delay)
                    
                    if jitter:
                        # Add random jitter between 0-25%
                        jitter_amount = random.uniform(0, 0.25) * current_delay
                        current_delay += jitter_amount
                        
                    log_warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                               f"after error: {str(e)}. Waiting {current_delay:.2f}s")
                    time.sleep(current_delay)
            
            log_error(f"Function {func.__name__} failed after {max_retries} retries", 
                     last_exception)
            raise last_exception
            
        return wrapper
    return decorator


def validate_numeric(value: Any, min_value: Optional[float] = None, 
                    max_value: Optional[float] = None) -> bool:
    """
    Validate that a value is numeric and within specified range.
    
    Args:
        value: The value to validate
        min_value: Optional minimum value
        max_value: Optional maximum value
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        numeric_value = float(value)
        
        if min_value is not None and numeric_value < min_value:
            return False
            
        if max_value is not None and numeric_value > max_value:
            return False
            
        return True
    except (ValueError, TypeError):
        return False


def safe_execute(func: Callable, *args, default_return: Any = None, **kwargs) -> Any:
    """
    Safely execute a function and return a default value on exception.
    
    Args:
        func: The function to execute
        *args: Arguments to pass to the function
        default_return: Value to return if an exception occurs
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The function result or default_return on exception
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_error(f"Error executing {func.__name__}", e)
        return default_return