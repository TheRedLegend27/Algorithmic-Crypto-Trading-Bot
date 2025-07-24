"""
Coinbase order management with crypto trading rules.

This module implements order management for Coinbase Advanced Trade API integration,
including market and limit order placement, order validation, size checks, and fee calculations.
"""
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import logging

from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials
from bot.utils import log_error, log_info, log_warning


@dataclass
class CryptoProduct:
    """
    Data class for cryptocurrency product information.
    
    Attributes:
        id: Product ID (e.g., "BTC-USD")
        base_currency: Base currency code (e.g., "BTC")
        quote_currency: Quote currency code (e.g., "USD")
        base_min_size: Minimum order size in base currency
        base_max_size: Maximum order size in base currency
        quote_increment: Price precision for quote currency
        base_increment: Size precision for base currency
        display_name: Display name for the product
        min_market_funds: Minimum order size in quote currency
        max_market_funds: Maximum order size in quote currency
        status: Product status (e.g., "online")
        status_message: Status message if applicable
    """
    id: str
    base_currency: str
    quote_currency: str
    base_min_size: float
    base_max_size: float
    quote_increment: float
    base_increment: float
    display_name: str
    min_market_funds: float
    max_market_funds: float
    status: str
    status_message: str = ""


@dataclass
class CryptoOrderParams:
    """
    Data class for cryptocurrency order parameters.
    
    Attributes:
        product_id: Product ID (e.g., "BTC-USD")
        side: Order side ("buy" or "sell")
        order_type: Order type ("market" or "limit")
        size: Order size in base currency
        price: Limit price (required for limit orders)
        time_in_force: Time in force (e.g., "GTC", "IOC", "GTT")
        cancel_after: Cancel after time for GTT orders
        post_only: Whether the order must be a maker order
        client_oid: Client-provided order ID
    """
    product_id: str
    side: str
    order_type: str
    size: float
    price: Optional[float] = None
    time_in_force: str = "GTC"  # Good Till Canceled
    cancel_after: Optional[str] = None
    post_only: bool = False
    client_oid: str = ""


@dataclass
class CryptoTradeResult:
    """
    Data class for cryptocurrency trade result.
    
    Attributes:
        order_id: Coinbase order ID
        product_id: Product ID (e.g., "BTC-USD")
        side: Order side ("buy" or "sell")
        size: Order size in base currency
        price: Execution price
        total_value: Total value in quote currency
        fees: Trading fees
        status: Order status
        timestamp: Order timestamp
        fill_fees: Fees for filled portion
        settled: Whether the order is settled
    """
    order_id: str
    product_id: str
    side: str
    size: float
    price: float
    total_value: float
    fees: float
    status: str
    timestamp: datetime
    fill_fees: float = 0.0
    settled: bool = False


class OrderValidationError(Exception):
    """Exception raised for order validation errors."""
    pass


class CryptoOrderManager:
    """
    Manages cryptocurrency orders for Coinbase Advanced Trade API integration.
    Provides order placement, validation, and fee calculation functionality.
    """
    
    def __init__(self, coinbase_client: CoinbaseClient):
        """
        Initialize the crypto order manager.
        
        Args:
            coinbase_client: Authenticated Coinbase client
        """
        self.client = coinbase_client
        self.logger = logging.getLogger(__name__)
        self.products: Dict[str, CryptoProduct] = {}
        self.fee_rates = {
            "maker": 0.005,  # 0.5% default maker fee
            "taker": 0.005   # 0.5% default taker fee
        }
        
        # Cache of recent orders
        self.recent_orders: Dict[str, Dict[str, Any]] = {}
        
        # Initialize product information
        self._refresh_products()
        
        self.logger.info("CryptoOrderManager initialized")
    
    def _refresh_products(self) -> bool:
        """
        Refresh product information from Coinbase.
        
        Returns:
            bool: True if successful
        """
        try:
            products_data = self.client.get_products()
            
            # Reset products
            self.products = {}
            
            for product_data in products_data:
                product_id = product_data.get('id', '')
                if not product_id:
                    continue
                
                self.products[product_id] = CryptoProduct(
                    id=product_id,
                    base_currency=product_data.get('base_currency', ''),
                    quote_currency=product_data.get('quote_currency', ''),
                    base_min_size=float(product_data.get('base_min_size', 0.0)),
                    base_max_size=float(product_data.get('base_max_size', 0.0)),
                    quote_increment=float(product_data.get('quote_increment', 0.0)),
                    base_increment=float(product_data.get('base_increment', 0.0)),
                    display_name=product_data.get('display_name', ''),
                    min_market_funds=float(product_data.get('min_market_funds', 0.0)),
                    max_market_funds=float(product_data.get('max_market_funds', 0.0)),
                    status=product_data.get('status', ''),
                    status_message=product_data.get('status_message', '')
                )
            
            self.logger.info(f"Refreshed {len(self.products)} products")
            return True
            
        except Exception as e:
            self.logger.error(f"Error refreshing products: {str(e)}")
            return False
    
    def get_product(self, product_id: str) -> Optional[CryptoProduct]:
        """
        Get product information for a specific product ID.
        
        Args:
            product_id: Product ID (e.g., "BTC-USD")
            
        Returns:
            CryptoProduct if exists, None otherwise
        """
        # Try to get from cache first
        if product_id in self.products:
            return self.products[product_id]
        
        # If not in cache, refresh products and try again
        if self._refresh_products() and product_id in self.products:
            return self.products[product_id]
        
        return None
    
    def validate_order_size(self, product_id: str, size: float, price: Optional[float] = None) -> Tuple[bool, str]:
        """
        Validate order size against product constraints.
        
        Args:
            product_id: Product ID
            size: Order size in base currency
            price: Order price (for calculating quote currency value)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        product = self.get_product(product_id)
        if not product:
            return False, f"Unknown product: {product_id}"
        
        # Check minimum size
        if size < product.base_min_size:
            return False, f"Order size {size} below minimum {product.base_min_size} {product.base_currency}"
        
        # Check maximum size
        if size > product.base_max_size:
            return False, f"Order size {size} above maximum {product.base_max_size} {product.base_currency}"
        
        # Check size precision
        size_precision = self._get_precision_from_increment(product.base_increment)
        rounded_size = round(size, size_precision)
        if rounded_size != size:
            return False, f"Invalid size precision: {size}, must be rounded to {size_precision} decimal places"
        
        # Check minimum funds if price is provided
        if price is not None:
            order_value = size * price
            if order_value < product.min_market_funds:
                return False, (f"Order value ${order_value:.2f} below minimum "
                              f"${product.min_market_funds:.2f}")
            
            # Check maximum funds
            if order_value > product.max_market_funds:
                return False, (f"Order value ${order_value:.2f} above maximum "
                              f"${product.max_market_funds:.2f}")
        
        return True, ""
    
    def validate_price(self, product_id: str, price: float) -> Tuple[bool, str]:
        """
        Validate order price against product constraints.
        
        Args:
            product_id: Product ID
            price: Order price
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        product = self.get_product(product_id)
        if not product:
            return False, f"Unknown product: {product_id}"
        
        # Check price is positive
        if price <= 0:
            return False, "Price must be positive"
        
        # Check price precision
        price_precision = self._get_precision_from_increment(product.quote_increment)
        rounded_price = round(price, price_precision)
        if rounded_price != price:
            return False, f"Invalid price precision: {price}, must be rounded to {price_precision} decimal places"
        
        return True, ""
    
    def _get_precision_from_increment(self, increment: float) -> int:
        """
        Calculate decimal precision from increment value.
        
        Args:
            increment: Increment value (e.g., 0.01 for 2 decimal places)
            
        Returns:
            int: Number of decimal places
        """
        increment_str = str(increment).rstrip('0')
        if '.' in increment_str:
            return len(increment_str) - increment_str.index('.') - 1
        return 0
    
    def round_size(self, product_id: str, size: float) -> float:
        """
        Round order size to valid precision for a product.
        
        Args:
            product_id: Product ID
            size: Order size to round
            
        Returns:
            float: Rounded size
        """
        product = self.get_product(product_id)
        if not product:
            return size
        
        # For testing purposes, handle the case where base_increment is 0
        if product.base_increment == 0:
            return size
            
        precision = self._get_precision_from_increment(product.base_increment)
        return round(size, precision)
    
    def round_price(self, product_id: str, price: float, round_up: bool = False) -> float:
        """
        Round price to valid precision for a product.
        
        Args:
            product_id: Product ID
            price: Price to round
            round_up: Whether to round up (for sell orders) or down (for buy orders)
            
        Returns:
            float: Rounded price
        """
        product = self.get_product(product_id)
        if not product:
            return price
        
        precision = self._get_precision_from_increment(product.quote_increment)
        
        # Use Decimal for precise rounding
        price_decimal = Decimal(str(price))
        factor = Decimal(10) ** precision
        
        if round_up:
            return float(price_decimal.quantize(Decimal('1') / factor, rounding=ROUND_UP))
        else:
            return float(price_decimal.quantize(Decimal('1') / factor, rounding=ROUND_DOWN))
    
    def calculate_fees(self, order_type: str, size: float, price: float) -> float:
        """
        Calculate trading fees for an order.
        
        Args:
            order_type: Order type ("market" or "limit")
            size: Order size in base currency
            price: Order price
            
        Returns:
            float: Estimated fees in quote currency
        """
        order_value = size * price
        
        # Use taker fee for market orders, maker fee for limit orders
        if order_type.lower() == "market":
            fee_rate = self.fee_rates["taker"]
        else:
            fee_rate = self.fee_rates["maker"]
        
        return order_value * fee_rate
    
    def place_market_order(self, product_id: str, side: str, size: float) -> Optional[CryptoTradeResult]:
        """
        Place a market order.
        
        Args:
            product_id: Product ID (e.g., "BTC-USD")
            side: Order side ("buy" or "sell")
            size: Order size in base currency
            
        Returns:
            CryptoTradeResult if successful, None otherwise
        """
        try:
            # Validate product
            product = self.get_product(product_id)
            if not product:
                self.logger.error(f"Unknown product: {product_id}")
                return None
            
            # Normalize side
            side = side.lower()
            if side not in ["buy", "sell"]:
                self.logger.error(f"Invalid side: {side}, must be 'buy' or 'sell'")
                return None
            
            # Round size to valid precision
            rounded_size = self.round_size(product_id, size)
            
            # Validate order size
            is_valid, error_message = self.validate_order_size(product_id, rounded_size)
            if not is_valid:
                self.logger.error(f"Invalid order size: {error_message}")
                return None
            
            # Generate client order ID
            client_oid = str(uuid.uuid4())
            
            # Prepare order parameters
            order_params = {
                "product_id": product_id,
                "side": side,
                "type": "market",
                "size": str(rounded_size),
                "client_oid": client_oid
            }
            
            # Place order
            response = self.client.create_order(order_params)
            
            # Get current price for fee estimation
            ticker = self.client.get_product_ticker(product_id)
            current_price = float(ticker.get("price", 0.0))
            
            # Calculate estimated fees
            estimated_fees = self.calculate_fees("market", rounded_size, current_price)
            
            # Create trade result
            result = CryptoTradeResult(
                order_id=response.get("id", ""),
                product_id=product_id,
                side=side,
                size=rounded_size,
                price=current_price,
                total_value=rounded_size * current_price,
                fees=estimated_fees,
                status=response.get("status", "pending"),
                timestamp=datetime.now(),
                settled=response.get("settled", False)
            )
            
            # Cache the order
            self.recent_orders[result.order_id] = response
            
            self.logger.info(
                f"Placed market {side} order for {rounded_size} {product.base_currency} "
                f"at ~${current_price:.2f}, fees: ${estimated_fees:.2f}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error placing market order: {str(e)}")
            return None
    
    def place_limit_order(self, product_id: str, side: str, size: float, price: float, 
                         post_only: bool = False) -> Optional[CryptoTradeResult]:
        """
        Place a limit order.
        
        Args:
            product_id: Product ID (e.g., "BTC-USD")
            side: Order side ("buy" or "sell")
            size: Order size in base currency
            price: Limit price
            post_only: Whether the order must be a maker order
            
        Returns:
            CryptoTradeResult if successful, None otherwise
        """
        try:
            # Validate product
            product = self.get_product(product_id)
            if not product:
                self.logger.error(f"Unknown product: {product_id}")
                return None
            
            # Normalize side
            side = side.lower()
            if side not in ["buy", "sell"]:
                self.logger.error(f"Invalid side: {side}, must be 'buy' or 'sell'")
                return None
            
            # Round size and price to valid precision
            rounded_size = self.round_size(product_id, size)
            rounded_price = self.round_price(product_id, price, round_up=(side == "sell"))
            
            # Validate order size
            is_valid, error_message = self.validate_order_size(product_id, rounded_size, rounded_price)
            if not is_valid:
                self.logger.error(f"Invalid order size: {error_message}")
                return None
            
            # Validate price
            is_valid, error_message = self.validate_price(product_id, rounded_price)
            if not is_valid:
                self.logger.error(f"Invalid price: {error_message}")
                return None
            
            # Generate client order ID
            client_oid = str(uuid.uuid4())
            
            # Prepare order parameters
            order_params = {
                "product_id": product_id,
                "side": side,
                "type": "limit",
                "size": str(rounded_size),
                "price": str(rounded_price),
                "time_in_force": "GTC",  # Good Till Canceled
                "post_only": post_only,
                "client_oid": client_oid
            }
            
            # Place order
            response = self.client.create_order(order_params)
            
            # Calculate estimated fees
            estimated_fees = self.calculate_fees("limit", rounded_size, rounded_price)
            
            # Create trade result
            result = CryptoTradeResult(
                order_id=response.get("id", ""),
                product_id=product_id,
                side=side,
                size=rounded_size,
                price=rounded_price,
                total_value=rounded_size * rounded_price,
                fees=estimated_fees,
                status=response.get("status", "pending"),
                timestamp=datetime.now(),
                settled=response.get("settled", False)
            )
            
            # Cache the order
            self.recent_orders[result.order_id] = response
            
            self.logger.info(
                f"Placed limit {side} order for {rounded_size} {product.base_currency} "
                f"at ${rounded_price:.2f}, fees: ${estimated_fees:.2f}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error placing limit order: {str(e)}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            bool: True if successful
        """
        try:
            response = self.client.cancel_order(order_id)
            
            # Remove from cache
            if order_id in self.recent_orders:
                del self.recent_orders[order_id]
            
            self.logger.info(f"Cancelled order {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {str(e)}")
            return False
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get the status of an order.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Dictionary with order status information
        """
        try:
            # Check cache first
            if order_id in self.recent_orders:
                # If order is in final state, return cached version
                cached_order = self.recent_orders[order_id]
                if cached_order.get("status") in ["done", "rejected", "cancelled"]:
                    return cached_order
            
            # Get fresh status from API
            response = self.client.get_order(order_id)
            
            # Update cache
            self.recent_orders[order_id] = response
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {str(e)}")
            return {"id": order_id, "status": "unknown", "error": str(e)}
    
    def get_open_orders(self, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders, optionally filtered by product.
        
        Args:
            product_id: Optional product ID filter
            
        Returns:
            List of open orders
        """
        try:
            params = {"status": "open"}
            if product_id:
                params["product_id"] = product_id
                
            response = self.client.list_orders(**params)
            
            # Update cache with these orders
            for order in response:
                order_id = order.get("id")
                if order_id:
                    self.recent_orders[order_id] = order
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting open orders: {str(e)}")
            return []
    
    def update_fee_rates(self, maker_fee: float, taker_fee: float) -> None:
        """
        Update fee rates for calculations.
        
        Args:
            maker_fee: Maker fee rate (e.g., 0.005 for 0.5%)
            taker_fee: Taker fee rate (e.g., 0.005 for 0.5%)
        """
        self.fee_rates["maker"] = maker_fee
        self.fee_rates["taker"] = taker_fee
        self.logger.info(f"Updated fee rates: maker {maker_fee:.4f}, taker {taker_fee:.4f}")