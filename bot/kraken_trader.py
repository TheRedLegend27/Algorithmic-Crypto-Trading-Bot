"""
Kraken trader implementation - simple and reliable crypto trading.
"""
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_DOWN

from bot.kraken_client import KrakenClient, KrakenCredentials
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_error, log_info, log_warning


@dataclass
class KrakenTradingConfig:
    """Configuration for Kraken trading."""
    trading_pair: str = "XBTUSD"  # BTC/USD on Kraken
    trade_amount_usd: float = 10.0
    max_position_usd: float = 100.0
    min_order_size: float = 0.0001  # Minimum BTC order size
    min_trade_interval: int = 300  # 5 minutes in seconds


@dataclass
class KrakenBalance:
    """Account balance information."""
    currency: str
    balance: float
    available: float  # Same as balance for Kraken (no separate available field)


@dataclass
class KrakenTradeResult:
    """Result of a trade execution."""
    success: bool
    order_id: Optional[str] = None
    side: Optional[str] = None
    volume: Optional[str] = None
    price: Optional[str] = None
    pair: Optional[str] = None
    error: Optional[str] = None


class KrakenTrader:
    """
    Simple, reliable Kraken trader.
    Much simpler than Coinbase implementation.
    """
    
    def __init__(self, credentials: KrakenCredentials, config: KrakenTradingConfig):
        """Initialize Kraken trader."""
        self.credentials = credentials
        self.config = config
        self.client = KrakenClient(credentials)
        self.last_trade_time = 0
        
        # Cache for account and pair info
        self._balance_cache = {}
        self._pairs_cache = {}
        self._cache_time = 0
        self._cache_ttl = 60  # 1 minute cache
        
        log_info(f"KrakenTrader initialized for {config.trading_pair}")
    
    def test_connection(self) -> bool:
        """Test connection to Kraken API."""
        return self.client.test_connection()
    
    def _refresh_cache_if_needed(self) -> None:
        """Refresh cached data if needed."""
        current_time = time.time()
        if current_time - self._cache_time > self._cache_ttl:
            try:
                # Refresh balance
                balance_data = self.client.get_account_balance()
                self._balance_cache = balance_data
                
                # Refresh trading pairs info
                pairs_data = self.client.get_tradable_pairs([self.config.trading_pair])
                self._pairs_cache = pairs_data
                
                self._cache_time = current_time
                log_info("Cache refreshed successfully")
            except Exception as e:
                log_warning(f"Failed to refresh cache: {str(e)}")
    
    def get_balance(self, currency: str) -> Optional[KrakenBalance]:
        """Get balance for a specific currency."""
        try:
            self._refresh_cache_if_needed()
            
            # Kraken uses different currency codes (e.g., XXBT for BTC, ZUSD for USD)
            kraken_currency = self._get_kraken_currency_code(currency)
            
            balance_str = self._balance_cache.get(kraken_currency, '0')
            balance = float(balance_str)
            
            return KrakenBalance(
                currency=currency,
                balance=balance,
                available=balance  # Kraken doesn't separate available/total
            )
        except Exception as e:
            log_error(f"Error getting balance for {currency}: {str(e)}")
            return None
    
    def _get_kraken_currency_code(self, currency: str) -> str:
        """Convert standard currency codes to Kraken format."""
        mapping = {
            'BTC': 'XXBT',
            'USD': 'ZUSD',
            'EUR': 'ZEUR',
            'ETH': 'XETH',
            'LTC': 'XLTC'
        }
        return mapping.get(currency.upper(), currency.upper())
    
    def get_current_price(self, pair: str) -> Optional[float]:
        """Get current market price for a trading pair."""
        return self.client.get_current_price(pair)
    
    def _calculate_order_volume(self, side: str, price: float) -> Optional[str]:
        """Calculate appropriate order volume."""
        try:
            if side.upper() == 'BUY':
                # Calculate volume based on USD amount
                volume = self.config.trade_amount_usd / price
                
                # Check minimum order size
                if volume < self.config.min_order_size:
                    log_warning(f"Calculated volume {volume} below minimum {self.config.min_order_size}")
                    return None
                
                # Check available USD balance
                usd_balance = self.get_balance('USD')
                if not usd_balance or usd_balance.available < self.config.trade_amount_usd:
                    log_warning(f"Insufficient USD balance for ${self.config.trade_amount_usd} trade")
                    return None
                
            else:  # SELL
                # Get BTC balance
                btc_balance = self.get_balance('BTC')
                
                if not btc_balance or btc_balance.available <= 0:
                    log_warning("No BTC available to sell")
                    return None
                
                # Use available balance, but respect trade amount limit
                max_volume_by_amount = self.config.trade_amount_usd / price
                volume = min(btc_balance.available, max_volume_by_amount)
                
                if volume < self.config.min_order_size:
                    log_warning(f"Available volume {volume} below minimum {self.config.min_order_size}")
                    return None
            
            # Round to 8 decimal places (standard for crypto)
            volume_decimal = Decimal(str(volume)).quantize(
                Decimal('0.00000001'), 
                rounding=ROUND_DOWN
            )
            
            return str(volume_decimal)
            
        except Exception as e:
            log_error(f"Error calculating order volume: {str(e)}")
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
    
    def execute_trade(self, signal: TradingSignal) -> KrakenTradeResult:
        """Execute a trade based on a signal."""
        try:
            if not self._should_trade(signal):
                return KrakenTradeResult(success=False, error="Trade conditions not met")
            
            # Get current price
            current_price = self.get_current_price(self.config.trading_pair)
            if not current_price:
                return KrakenTradeResult(success=False, error="Could not get current price")
            
            # Determine trade side
            side = "buy" if signal.action == SignalType.BUY else "sell"
            
            # Calculate order volume
            volume = self._calculate_order_volume(side, current_price)
            if not volume:
                return KrakenTradeResult(success=False, error="Could not calculate valid order volume")
            
            log_info(f"Placing {side.upper()} order: {volume} BTC at ~${current_price:.2f}")
            
            # Place market order
            order_response = self.client.place_market_order(
                pair=self.config.trading_pair,
                side=side,
                volume=volume
            )
            
            # Check if order was successful
            if 'txid' not in order_response:
                error_msg = f"Order failed: {order_response}"
                return KrakenTradeResult(success=False, error=error_msg)
            
            order_id = order_response['txid'][0]  # Kraken returns list of transaction IDs
            self.last_trade_time = time.time()
            
            log_info(f"Order placed successfully: {order_id}")
            
            return KrakenTradeResult(
                success=True,
                order_id=order_id,
                side=side,
                volume=volume,
                price=str(current_price),
                pair=self.config.trading_pair
            )
            
        except Exception as e:
            error_msg = f"Trade execution failed: {str(e)}"
            log_error(error_msg)
            return KrakenTradeResult(success=False, error=error_msg)
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        try:
            self._refresh_cache_if_needed()
            
            # Get current price
            current_price = self.get_current_price(self.config.trading_pair)
            if not current_price:
                current_price = 0.0
            
            # Get balances
            btc_balance = self.get_balance('BTC')
            usd_balance = self.get_balance('USD')
            
            # Calculate values
            btc_value = (btc_balance.balance * current_price) if btc_balance else 0.0
            usd_value = usd_balance.balance if usd_balance else 0.0
            total_value = btc_value + usd_value
            
            return {
                'trading_pair': self.config.trading_pair,
                'current_price': current_price,
                'btc_balance': btc_balance.balance if btc_balance else 0.0,
                'btc_available': btc_balance.available if btc_balance else 0.0,
                'btc_value_usd': btc_value,
                'usd_balance': usd_balance.balance if usd_balance else 0.0,
                'usd_available': usd_balance.available if usd_balance else 0.0,
                'total_portfolio_value': total_value,
                'last_trade_time': self.last_trade_time
            }
            
        except Exception as e:
            log_error(f"Error getting portfolio summary: {str(e)}")
            return {}
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict]:
        """Get recent orders."""
        try:
            # Get closed orders (Kraken doesn't have a simple "recent orders" endpoint)
            closed_orders = self.client.get_closed_orders(trades=False)
            
            # Convert to list and sort by time
            orders_list = []
            for order_id, order_data in closed_orders.items():
                order_data['order_id'] = order_id
                orders_list.append(order_data)
            
            # Sort by close time (most recent first) and limit
            orders_list.sort(key=lambda x: x.get('closetm', 0), reverse=True)
            return orders_list[:limit]
            
        except Exception as e:
            log_error(f"Error getting recent orders: {str(e)}")
            return []
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        try:
            result = self.client.cancel_all_orders()
            count = result.get('count', 0)
            log_info(f"Cancelled {count} orders")
            return True
        except Exception as e:
            log_error(f"Error cancelling orders: {str(e)}")
            return False