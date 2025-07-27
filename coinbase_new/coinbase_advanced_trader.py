"""
Simplified Coinbase Advanced Trade API trader.
Clean implementation focused on essential trading functionality.
"""
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_DOWN

from bot.coinbase_advanced_client import CoinbaseAdvancedClient, AdvancedTradeCredentials
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_error, log_info, log_warning


@dataclass
class TradingConfig:
    """Configuration for trading operations."""
    product_id: str = "BTC-USD"
    trade_amount_usd: float = 10.0
    max_position_usd: float = 100.0
    min_order_size: float = 0.001
    price_precision: int = 2
    size_precision: int = 8
    min_trade_interval: int = 300  # 5 minutes in seconds


@dataclass
class Balance:
    """Account balance information."""
    currency: str
    available: float
    hold: float
    total: float


@dataclass
class TradeResult:
    """Result of a trade execution."""
    success: bool
    order_id: Optional[str] = None
    side: Optional[str] = None
    size: Optional[str] = None
    price: Optional[str] = None
    product_id: Optional[str] = None
    error: Optional[str] = None


class CoinbaseAdvancedTrader:
    """
    Simplified trader for Coinbase Advanced Trade API.
    Focuses on essential functionality with clean error handling.
    """
    
    def __init__(self, credentials: AdvancedTradeCredentials, config: TradingConfig):
        """Initialize the trader."""
        self.credentials = credentials
        self.config = config
        self.client = CoinbaseAdvancedClient(credentials)
        self.last_trade_time = 0
        
        # Cache for account and product info
        self._accounts_cache = {}
        self._products_cache = {}
        self._cache_time = 0
        self._cache_ttl = 300  # 5 minutes
        
        log_info(f"CoinbaseAdvancedTrader initialized for {config.product_id}")
    
    def test_connection(self) -> bool:
        """Test connection to Coinbase API."""
        return self.client.test_connection()
    
    def _refresh_cache_if_needed(self) -> None:
        """Refresh cached data if needed."""
        current_time = time.time()
        if current_time - self._cache_time > self._cache_ttl:
            try:
                # Refresh accounts
                accounts = self.client.get_accounts()
                self._accounts_cache = {acc['currency']: acc for acc in accounts}
                
                # Refresh products
                products = self.client.get_products()
                self._products_cache = {prod['product_id']: prod for prod in products}
                
                self._cache_time = current_time
                log_info("Cache refreshed successfully")
            except Exception as e:
                log_warning(f"Failed to refresh cache: {str(e)}")
    
    def get_balance(self, currency: str) -> Optional[Balance]:
        """Get balance for a specific currency."""
        try:
            self._refresh_cache_if_needed()
            
            account = self._accounts_cache.get(currency)
            if not account:
                log_warning(f"No account found for currency: {currency}")
                return None
            
            available = float(account.get('available_balance', {}).get('value', '0'))
            hold = float(account.get('hold', {}).get('value', '0'))
            total = available + hold
            
            return Balance(
                currency=currency,
                available=available,
                hold=hold,
                total=total
            )
        except Exception as e:
            log_error(f"Error getting balance for {currency}: {str(e)}")
            return None
    
    def get_current_price(self, product_id: str) -> Optional[float]:
        """Get current market price for a product."""
        try:
            product_data = self.client.get_product(product_id)
            price_str = product_data.get('price')
            if price_str:
                return float(price_str)
            return None
        except Exception as e:
            log_error(f"Error getting price for {product_id}: {str(e)}")
            return None
    
    def _calculate_order_size(self, side: str, price: float) -> Optional[str]:
        """Calculate appropriate order size."""
        try:
            if side.upper() == 'BUY':
                # Calculate size based on USD amount
                size = self.config.trade_amount_usd / price
                
                # Check minimum order size
                if size < self.config.min_order_size:
                    log_warning(f"Calculated size {size} below minimum {self.config.min_order_size}")
                    return None
                
                # Check available USD balance
                usd_balance = self.get_balance('USD')
                if not usd_balance or usd_balance.available < self.config.trade_amount_usd:
                    log_warning(f"Insufficient USD balance for ${self.config.trade_amount_usd} trade")
                    return None
                
            else:  # SELL
                # Get base currency from product_id (e.g., BTC from BTC-USD)
                base_currency = self.config.product_id.split('-')[0]
                balance = self.get_balance(base_currency)
                
                if not balance or balance.available <= 0:
                    log_warning(f"No {base_currency} available to sell")
                    return None
                
                # Use available balance, but respect trade amount limit
                max_size_by_amount = self.config.trade_amount_usd / price
                size = min(balance.available, max_size_by_amount)
                
                if size < self.config.min_order_size:
                    log_warning(f"Available size {size} below minimum {self.config.min_order_size}")
                    return None
            
            # Round to appropriate precision
            size_decimal = Decimal(str(size)).quantize(
                Decimal('0.' + '0' * self.config.size_precision), 
                rounding=ROUND_DOWN
            )
            
            return str(size_decimal)
            
        except Exception as e:
            log_error(f"Error calculating order size: {str(e)}")
            return None
    
    def _should_trade(self, signal: TradingSignal) -> bool:
        """Check if we should execute a trade."""
        # Skip HOLD signals
        if signal.action == SignalType.HOLD:
            return False
        
        # Check signal confidence
        if signal.confidence < 0.6:
            log_info(f"Signal confidence too low: {signal.confidence:.2f}")
            return False
        
        # Check minimum trade interval
        current_time = time.time()
        if current_time - self.last_trade_time < self.config.min_trade_interval:
            remaining = self.config.min_trade_interval - (current_time - self.last_trade_time)
            log_info(f"Trade interval not met, {remaining:.0f}s remaining")
            return False
        
        return True
    
    def execute_trade(self, signal: TradingSignal) -> TradeResult:
        """Execute a trade based on a signal."""
        try:
            if not self._should_trade(signal):
                return TradeResult(success=False, error="Trade conditions not met")
            
            # Get current price
            current_price = self.get_current_price(self.config.product_id)
            if not current_price:
                return TradeResult(success=False, error="Could not get current price")
            
            # Determine trade side
            side = "BUY" if signal.action == SignalType.BUY else "SELL"
            
            # Calculate order size
            size = self._calculate_order_size(side, current_price)
            if not size:
                return TradeResult(success=False, error="Could not calculate valid order size")
            
            log_info(f"Placing {side} order: {size} {self.config.product_id} at ~${current_price:.2f}")
            
            # Place market order
            order_response = self.client.place_market_order(
                product_id=self.config.product_id,
                side=side,
                size=size
            )
            
            # Check if order was successful
            if not order_response.get('success', False):
                error_msg = order_response.get('error_response', {}).get('message', 'Unknown error')
                return TradeResult(success=False, error=f"Order failed: {error_msg}")
            
            order_id = order_response.get('order_id')
            self.last_trade_time = time.time()
            
            log_info(f"Order placed successfully: {order_id}")
            
            return TradeResult(
                success=True,
                order_id=order_id,
                side=side,
                size=size,
                price=str(current_price),
                product_id=self.config.product_id
            )
            
        except Exception as e:
            error_msg = f"Trade execution failed: {str(e)}"
            log_error(error_msg)
            return TradeResult(success=False, error=error_msg)
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        try:
            self._refresh_cache_if_needed()
            
            # Get current price
            current_price = self.get_current_price(self.config.product_id)
            if not current_price:
                current_price = 0.0
            
            # Get balances
            base_currency = self.config.product_id.split('-')[0]
            quote_currency = self.config.product_id.split('-')[1]
            
            base_balance = self.get_balance(base_currency)
            quote_balance = self.get_balance(quote_currency)
            
            # Calculate values
            base_value = (base_balance.total * current_price) if base_balance else 0.0
            quote_value = quote_balance.total if quote_balance else 0.0
            total_value = base_value + quote_value
            
            return {
                'product_id': self.config.product_id,
                'current_price': current_price,
                'base_currency': base_currency,
                'base_balance': base_balance.total if base_balance else 0.0,
                'base_available': base_balance.available if base_balance else 0.0,
                'base_value_usd': base_value,
                'quote_currency': quote_currency,
                'quote_balance': quote_balance.total if quote_balance else 0.0,
                'quote_available': quote_balance.available if quote_balance else 0.0,
                'total_portfolio_value': total_value,
                'last_trade_time': self.last_trade_time
            }
            
        except Exception as e:
            log_error(f"Error getting portfolio summary: {str(e)}")
            return {}
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict]:
        """Get recent orders."""
        try:
            return self.client.list_orders(
                product_id=self.config.product_id,
                limit=limit
            )
        except Exception as e:
            log_error(f"Error getting recent orders: {str(e)}")
            return []
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        try:
            # Get open orders
            open_orders = self.client.list_orders(
                product_id=self.config.product_id,
                order_status='OPEN'
            )
            
            if not open_orders:
                log_info("No open orders to cancel")
                return True
            
            # Extract order IDs
            order_ids = [order['order_id'] for order in open_orders]
            
            # Cancel orders
            result = self.client.cancel_orders(order_ids)
            
            success_count = len(result.get('results', []))
            log_info(f"Cancelled {success_count}/{len(order_ids)} orders")
            
            return success_count == len(order_ids)
            
        except Exception as e:
            log_error(f"Error cancelling orders: {str(e)}")
            return False