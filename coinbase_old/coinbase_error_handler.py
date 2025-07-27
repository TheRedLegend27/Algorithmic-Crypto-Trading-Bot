"""
Coinbase-specific error handling for the crypto trading bot.

This module provides specialized error handling for Coinbase Advanced Trade API,
including authentication errors, rate limiting, order validation errors, and
network issues specific to the Coinbase API.

Classes:
    CoinbaseErrorHandler: Main error handler for Coinbase API
    CoinbaseErrorCategory: Enum for Coinbase-specific error categories
    CoinbaseRecoveryStrategy: Base class for Coinbase-specific recovery strategies
"""
import logging
import time
import json
import re
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import requests

from bot.error_handler import (
    ErrorHandler, ErrorCategory, ErrorContext, RecoveryStrategy,
    RetryRecoveryStrategy, FallbackRecoveryStrategy
)
from bot.utils import retry_with_backoff


class CoinbaseErrorCategory(Enum):
    """Coinbase-specific error categories"""
    # Authentication errors
    AUTH_INVALID_KEY = "auth_invalid_key"
    AUTH_INVALID_SIGNATURE = "auth_invalid_signature"
    AUTH_INVALID_PASSPHRASE = "auth_invalid_passphrase"
    AUTH_EXPIRED_TOKEN = "auth_expired_token"
    
    # Rate limiting errors
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # Order errors
    ORDER_INSUFFICIENT_FUNDS = "order_insufficient_funds"
    ORDER_INVALID_SIZE = "order_invalid_size"
    ORDER_INVALID_PRICE = "order_invalid_price"
    ORDER_DUPLICATE = "order_duplicate"
    ORDER_POST_ONLY_FAILED = "order_post_only_failed"
    ORDER_NOT_FOUND = "order_not_found"
    
    # Market data errors
    MARKET_INVALID_PRODUCT = "market_invalid_product"
    MARKET_PRODUCT_NOT_AVAILABLE = "market_product_not_available"
    
    # Network errors
    NETWORK_CONNECTION_ERROR = "network_connection_error"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_DNS_ERROR = "network_dns_error"
    
    # System errors
    SYSTEM_MAINTENANCE = "system_maintenance"
    SYSTEM_OVERLOADED = "system_overloaded"


@dataclass
class CoinbaseErrorConfig:
    """Configuration for Coinbase error handling"""
    # Rate limiting settings
    rate_limit_public_max_retries: int = 5
    rate_limit_private_max_retries: int = 3
    rate_limit_initial_delay: float = 1.0
    rate_limit_max_delay: float = 60.0
    rate_limit_backoff_factor: float = 2.0
    
    # Authentication settings
    auth_error_retry: bool = False
    
    # Network settings
    network_error_max_retries: int = 3
    network_error_initial_delay: float = 2.0
    network_error_max_delay: float = 30.0
    network_error_backoff_factor: float = 2.0
    
    # Order error settings
    order_error_retry: bool = False
    
    # System error settings
    system_error_max_retries: int = 2
    system_error_initial_delay: float = 5.0
    system_error_max_delay: float = 120.0
    system_error_backoff_factor: float = 3.0


class CoinbaseErrorHandler:
    """
    Specialized error handler for Coinbase Advanced Trade API.
    
    This class extends the base ErrorHandler with Coinbase-specific error
    handling logic, error categorization, and recovery strategies.
    """
    
    def __init__(self, config: Optional[CoinbaseErrorConfig] = None, 
                logger: Optional[logging.Logger] = None):
        """
        Initialize the Coinbase error handler.
        
        Args:
            config: Configuration for error handling
            logger: Logger instance to use
        """
        self.config = config or CoinbaseErrorConfig()
        self.logger = logger or logging.getLogger(__name__)
        self.error_handler = ErrorHandler(logger=self.logger)
        
        # Register Coinbase-specific recovery strategies
        self._register_coinbase_strategies()
        
        # Error metrics specific to Coinbase
        self.coinbase_error_counts: Dict[CoinbaseErrorCategory, int] = {
            cat: 0 for cat in CoinbaseErrorCategory
        }
        self.recent_coinbase_errors: List[Dict[str, Any]] = []
        self.max_recent_errors = 100
    
    def _register_coinbase_strategies(self) -> None:
        """Register Coinbase-specific recovery strategies"""
        # Rate limit recovery strategy
        self.error_handler.register_recovery_strategy(
            ErrorCategory.API_ERROR,
            RetryRecoveryStrategy(
                name="coinbase_rate_limit_retry",
                max_attempts=self.config.rate_limit_public_max_retries,
                initial_delay=self.config.rate_limit_initial_delay,
                backoff_factor=self.config.rate_limit_backoff_factor,
                max_delay=self.config.rate_limit_max_delay
            )
        )
        
        # Network error recovery strategy
        self.error_handler.register_recovery_strategy(
            ErrorCategory.NETWORK_ERROR,
            RetryRecoveryStrategy(
                name="coinbase_network_retry",
                max_attempts=self.config.network_error_max_retries,
                initial_delay=self.config.network_error_initial_delay,
                backoff_factor=self.config.network_error_backoff_factor,
                max_delay=self.config.network_error_max_delay
            )
        )
        
        # System error recovery strategy
        self.error_handler.register_recovery_strategy(
            ErrorCategory.SYSTEM_ERROR,
            RetryRecoveryStrategy(
                name="coinbase_system_retry",
                max_attempts=self.config.system_error_max_retries,
                initial_delay=self.config.system_error_initial_delay,
                backoff_factor=self.config.system_error_backoff_factor,
                max_delay=self.config.system_error_max_delay
            )
        )
    
    def categorize_coinbase_error(self, error: Exception, 
                                response: Optional[requests.Response] = None) -> CoinbaseErrorCategory:
        """
        Categorize a Coinbase API error based on its type and response.
        
        Args:
            error: The exception to categorize
            response: The API response if available
            
        Returns:
            CoinbaseErrorCategory: The categorization of the error
        """
        error_msg = str(error).lower()
        
        # Check if we have a response with JSON data
        response_data = None
        if response and hasattr(response, 'text') and response.text:
            try:
                response_data = json.loads(response.text)
            except json.JSONDecodeError:
                pass
        
        # Extract error code and message from response if available
        error_code = None
        if response_data and isinstance(response_data, dict):
            error_code = response_data.get('code', None)
            error_message = response_data.get('message', '')
            if error_message:
                error_msg = error_message.lower()
        
        # Authentication errors
        if response and response.status_code == 401:
            if 'invalid key' in error_msg or 'invalid api key' in error_msg:
                return CoinbaseErrorCategory.AUTH_INVALID_KEY
            elif 'invalid signature' in error_msg:
                return CoinbaseErrorCategory.AUTH_INVALID_SIGNATURE
            elif 'invalid passphrase' in error_msg:
                return CoinbaseErrorCategory.AUTH_INVALID_PASSPHRASE
            elif 'token expired' in error_msg or 'expired timestamp' in error_msg:
                return CoinbaseErrorCategory.AUTH_EXPIRED_TOKEN
        
        # Rate limiting errors
        if response and response.status_code == 429:
            return CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED
        
        # Order errors
        if 'insufficient funds' in error_msg:
            return CoinbaseErrorCategory.ORDER_INSUFFICIENT_FUNDS
        elif 'size too small' in error_msg or 'invalid size' in error_msg:
            return CoinbaseErrorCategory.ORDER_INVALID_SIZE
        elif 'invalid price' in error_msg:
            return CoinbaseErrorCategory.ORDER_INVALID_PRICE
        elif 'duplicate order' in error_msg:
            return CoinbaseErrorCategory.ORDER_DUPLICATE
        elif 'post only' in error_msg and 'failed' in error_msg:
            return CoinbaseErrorCategory.ORDER_POST_ONLY_FAILED
        elif 'order not found' in error_msg:
            return CoinbaseErrorCategory.ORDER_NOT_FOUND
        
        # Market data errors
        if 'product not found' in error_msg or 'invalid product' in error_msg:
            return CoinbaseErrorCategory.MARKET_INVALID_PRODUCT
        elif 'product not available' in error_msg:
            return CoinbaseErrorCategory.MARKET_PRODUCT_NOT_AVAILABLE
        
        # Network errors
        if isinstance(error, requests.ConnectionError):
            return CoinbaseErrorCategory.NETWORK_CONNECTION_ERROR
        elif isinstance(error, requests.Timeout):
            return CoinbaseErrorCategory.NETWORK_TIMEOUT
        elif 'dns' in error_msg:
            return CoinbaseErrorCategory.NETWORK_DNS_ERROR
        
        # System errors
        if 'maintenance' in error_msg:
            return CoinbaseErrorCategory.SYSTEM_MAINTENANCE
        elif 'overloaded' in error_msg or 'service unavailable' in error_msg:
            return CoinbaseErrorCategory.SYSTEM_OVERLOADED
        
        # Default to network connection error for other request exceptions
        if isinstance(error, requests.RequestException):
            return CoinbaseErrorCategory.NETWORK_CONNECTION_ERROR
        
        # If we can't categorize specifically, return None
        return None
    
    def map_to_error_category(self, coinbase_category: Optional[CoinbaseErrorCategory]) -> ErrorCategory:
        """
        Map Coinbase error category to base error category.
        
        Args:
            coinbase_category: Coinbase-specific error category
            
        Returns:
            ErrorCategory: Base error category
        """
        if coinbase_category is None:
            return ErrorCategory.RUNTIME_ERROR
        
        # Authentication errors
        if coinbase_category in [
            CoinbaseErrorCategory.AUTH_INVALID_KEY,
            CoinbaseErrorCategory.AUTH_INVALID_SIGNATURE,
            CoinbaseErrorCategory.AUTH_INVALID_PASSPHRASE,
            CoinbaseErrorCategory.AUTH_EXPIRED_TOKEN
        ]:
            return ErrorCategory.API_ERROR
        
        # Rate limiting errors
        if coinbase_category == CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED:
            return ErrorCategory.API_ERROR
        
        # Order errors
        if coinbase_category in [
            CoinbaseErrorCategory.ORDER_INSUFFICIENT_FUNDS,
            CoinbaseErrorCategory.ORDER_INVALID_SIZE,
            CoinbaseErrorCategory.ORDER_INVALID_PRICE,
            CoinbaseErrorCategory.ORDER_DUPLICATE,
            CoinbaseErrorCategory.ORDER_POST_ONLY_FAILED,
            CoinbaseErrorCategory.ORDER_NOT_FOUND
        ]:
            return ErrorCategory.API_ERROR
        
        # Market data errors
        if coinbase_category in [
            CoinbaseErrorCategory.MARKET_INVALID_PRODUCT,
            CoinbaseErrorCategory.MARKET_PRODUCT_NOT_AVAILABLE
        ]:
            return ErrorCategory.DATA_ERROR
        
        # Network errors
        if coinbase_category in [
            CoinbaseErrorCategory.NETWORK_CONNECTION_ERROR,
            CoinbaseErrorCategory.NETWORK_TIMEOUT,
            CoinbaseErrorCategory.NETWORK_DNS_ERROR
        ]:
            return ErrorCategory.NETWORK_ERROR
        
        # System errors
        if coinbase_category in [
            CoinbaseErrorCategory.SYSTEM_MAINTENANCE,
            CoinbaseErrorCategory.SYSTEM_OVERLOADED
        ]:
            return ErrorCategory.SYSTEM_ERROR
        
        return ErrorCategory.RUNTIME_ERROR
    
    def handle_coinbase_error(self, error: Exception, component: str,
                            response: Optional[requests.Response] = None,
                            additional_info: Dict[str, Any] = None) -> bool:
        """
        Handle a Coinbase API error.
        
        Args:
            error: The exception to handle
            component: The component where the error occurred
            response: The API response if available
            additional_info: Additional context information
            
        Returns:
            bool: True if recovery was successful
        """
        # Categorize the error
        coinbase_category = self.categorize_coinbase_error(error, response)
        base_category = self.map_to_error_category(coinbase_category)
        
        # Track Coinbase-specific error metrics
        if coinbase_category:
            self.coinbase_error_counts[coinbase_category] = self.coinbase_error_counts.get(coinbase_category, 0) + 1
            
            # Add to recent errors
            error_details = {
                'timestamp': time.time(),
                'error_type': str(type(error).__name__),
                'error_message': str(error),
                'component': component,
                'coinbase_category': coinbase_category.value if coinbase_category else None,
                'response_code': response.status_code if response else None,
                'additional_info': additional_info or {}
            }
            self.recent_coinbase_errors.append(error_details)
            
            # Trim recent errors list if needed
            if len(self.recent_coinbase_errors) > self.max_recent_errors:
                self.recent_coinbase_errors = self.recent_coinbase_errors[-self.max_recent_errors:]
        
        # Add Coinbase-specific info to additional_info
        if additional_info is None:
            additional_info = {}
        
        additional_info['coinbase_category'] = coinbase_category.value if coinbase_category else None
        if response:
            additional_info['response_code'] = response.status_code
            additional_info['response_headers'] = dict(response.headers)
            try:
                additional_info['response_body'] = response.json() if response.text else None
            except json.JSONDecodeError:
                additional_info['response_body'] = response.text if response.text else None
        
        # Use the base error handler
        return self.error_handler.handle_error(error, component, additional_info)
    
    def handle_authentication_error(self, error: Exception, component: str,
                                  response: Optional[requests.Response] = None) -> bool:
        """
        Handle Coinbase authentication errors.
        
        Args:
            error: The exception to handle
            component: The component where the error occurred
            response: The API response if available
            
        Returns:
            bool: True if recovery was successful
        """
        coinbase_category = self.categorize_coinbase_error(error, response)
        
        # Only handle authentication errors
        if coinbase_category not in [
            CoinbaseErrorCategory.AUTH_INVALID_KEY,
            CoinbaseErrorCategory.AUTH_INVALID_SIGNATURE,
            CoinbaseErrorCategory.AUTH_INVALID_PASSPHRASE,
            CoinbaseErrorCategory.AUTH_EXPIRED_TOKEN
        ]:
            return False
        
        # Log detailed authentication error
        self.logger.error(f"Coinbase authentication error: {coinbase_category.value}")
        self.logger.error(f"Error details: {str(error)}")
        
        # For expired tokens, we might be able to retry with a new timestamp
        if coinbase_category == CoinbaseErrorCategory.AUTH_EXPIRED_TOKEN and self.config.auth_error_retry:
            self.logger.info("Retrying with new authentication timestamp")
            return True
        
        # Other authentication errors typically require manual intervention
        self.logger.critical("Authentication error requires manual intervention")
        return False
    
    def handle_rate_limit_error(self, error: Exception, component: str,
                              response: Optional[requests.Response] = None,
                              additional_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle Coinbase rate limit errors.
        
        Args:
            error: The exception to handle
            component: The component where the error occurred
            response: The API response if available
            additional_info: Additional context information
            
        Returns:
            bool: True if recovery was successful
        """
        coinbase_category = self.categorize_coinbase_error(error, response)
        
        # Only handle rate limit errors
        if coinbase_category != CoinbaseErrorCategory.RATE_LIMIT_EXCEEDED:
            return False
        
        # Get retry-after header if available
        retry_after = None
        if response and 'Retry-After' in response.headers:
            try:
                retry_after = int(response.headers['Retry-After'])
            except (ValueError, TypeError):
                pass
        
        # If we have a retry-after header, use that
        if retry_after:
            self.logger.warning(f"Rate limited by Coinbase API. Waiting {retry_after} seconds as specified by API")
            time.sleep(retry_after)
            return True
        
        # Otherwise use exponential backoff
        attempt = additional_info.get('attempt', 1) if additional_info else 1
        delay = min(
            self.config.rate_limit_initial_delay * (self.config.rate_limit_backoff_factor ** (attempt - 1)),
            self.config.rate_limit_max_delay
        )
        
        self.logger.warning(f"Rate limited by Coinbase API. Using exponential backoff: waiting {delay:.2f} seconds")
        time.sleep(delay)
        
        return True
    
    def handle_order_error(self, error: Exception, component: str,
                         response: Optional[requests.Response] = None,
                         order_params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle Coinbase order errors.
        
        Args:
            error: The exception to handle
            component: The component where the error occurred
            response: The API response if available
            order_params: The original order parameters
            
        Returns:
            Tuple[bool, Dict]: (Success flag, Modified order parameters if any)
        """
        coinbase_category = self.categorize_coinbase_error(error, response)
        
        # Only handle order errors
        if coinbase_category not in [
            CoinbaseErrorCategory.ORDER_INSUFFICIENT_FUNDS,
            CoinbaseErrorCategory.ORDER_INVALID_SIZE,
            CoinbaseErrorCategory.ORDER_INVALID_PRICE,
            CoinbaseErrorCategory.ORDER_DUPLICATE,
            CoinbaseErrorCategory.ORDER_POST_ONLY_FAILED,
            CoinbaseErrorCategory.ORDER_NOT_FOUND
        ]:
            return False, {}
        
        # Log order error
        self.logger.error(f"Coinbase order error: {coinbase_category.value}")
        self.logger.error(f"Error details: {str(error)}")
        
        # If we don't have order parameters, we can't modify them
        if not order_params:
            return False, {}
        
        modified_params = order_params.copy()
        
        # Handle specific order errors
        if coinbase_category == CoinbaseErrorCategory.ORDER_INVALID_SIZE:
            # Extract minimum size from error message if possible
            min_size_match = re.search(r'size must be at least ([0-9.]+)', str(error))
            if min_size_match:
                min_size = float(min_size_match.group(1))
                self.logger.info(f"Adjusting order size to minimum: {min_size}")
                modified_params['size'] = min_size
                return True, modified_params
        
        elif coinbase_category == CoinbaseErrorCategory.ORDER_INVALID_PRICE:
            # For invalid price, we could switch to a market order
            if modified_params.get('type') == 'limit':
                self.logger.info("Converting limit order to market order due to invalid price")
                modified_params['type'] = 'market'
                if 'price' in modified_params:
                    del modified_params['price']
                return True, modified_params
        
        elif coinbase_category == CoinbaseErrorCategory.ORDER_POST_ONLY_FAILED:
            # For post-only failure, we could remove the post_only flag
            if modified_params.get('post_only'):
                self.logger.info("Removing post_only flag from order")
                modified_params['post_only'] = False
                return True, modified_params
        
        # For other order errors, we typically can't recover automatically
        return False, {}
    
    def handle_network_error(self, error: Exception, component: str) -> bool:
        """
        Handle network errors when communicating with Coinbase API.
        
        Args:
            error: The exception to handle
            component: The component where the error occurred
            
        Returns:
            bool: True if recovery was successful
        """
        coinbase_category = self.categorize_coinbase_error(error)
        
        # Only handle network errors
        if coinbase_category not in [
            CoinbaseErrorCategory.NETWORK_CONNECTION_ERROR,
            CoinbaseErrorCategory.NETWORK_TIMEOUT,
            CoinbaseErrorCategory.NETWORK_DNS_ERROR
        ]:
            return False
        
        # Log network error
        self.logger.error(f"Coinbase network error: {coinbase_category.value}")
        self.logger.error(f"Error details: {str(error)}")
        
        # Use retry with backoff for network errors
        return retry_with_backoff(
            lambda: None,  # No-op function, we just want the delay
            max_retries=self.config.network_error_max_retries,
            initial_delay=self.config.network_error_initial_delay,
            backoff_factor=self.config.network_error_backoff_factor,
            max_delay=self.config.network_error_max_delay,
            retry_on_exceptions=(requests.RequestException,)
        )
    
    def get_error_metrics(self) -> Dict[str, Any]:
        """
        Get Coinbase-specific error metrics.
        
        Returns:
            Dict: Error metrics
        """
        # Get base metrics
        base_metrics = self.error_handler.get_error_metrics()
        
        # Add Coinbase-specific metrics
        coinbase_metrics = {
            'coinbase_errors': {cat.name: count for cat, count in self.coinbase_error_counts.items()},
            'recent_coinbase_errors': len(self.recent_coinbase_errors),
            'coinbase_categories': {cat.name: cat.value for cat in CoinbaseErrorCategory}
        }
        
        # Combine metrics
        return {**base_metrics, **coinbase_metrics}
    
    def reset_metrics(self) -> None:
        """Reset error metrics"""
        # Reset base metrics
        self.error_handler.reset_metrics()
        
        # Reset Coinbase-specific metrics
        self.coinbase_error_counts = {cat: 0 for cat in CoinbaseErrorCategory}
        self.recent_coinbase_errors = []


# Create a global instance for convenience
global_coinbase_error_handler = CoinbaseErrorHandler()


def handle_coinbase_error(error: Exception, component: str,
                        response: Optional[requests.Response] = None,
                        additional_info: Dict[str, Any] = None) -> bool:
    """
    Handle a Coinbase API error using the global error handler.
    
    Args:
        error: The exception to handle
        component: The component where the error occurred
        response: The API response if available
        additional_info: Additional context information
        
    Returns:
        bool: True if recovery was successful
    """
    return global_coinbase_error_handler.handle_coinbase_error(
        error, component, response, additional_info
    )