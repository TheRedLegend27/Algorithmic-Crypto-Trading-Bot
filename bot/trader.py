"""
Trade execution module for placing orders through Alpaca API.
Handles order placement, position management, and trade execution.
"""
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
from alpaca.trading.models import Order, Position

from bot.config import AlpacaCredentials, TradingSettings
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_error, log_info, log_warning, retry_with_backoff, validate_numeric


@dataclass
class TradeResult:
    """Data class for trade execution results."""
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
    timestamp: datetime
    fees: float = 0.0


class PositionManager:
    """
    Manages and tracks cryptocurrency positions.
    Provides methods to get current positions and reconcile with Alpaca API.
    """
    
    def __init__(self, trading_client: TradingClient):
        """
        Initialize the PositionManager.
        
        Args:
            trading_client: Alpaca TradingClient instance
        """
        self.trading_client = trading_client
        self.positions: Dict[str, Position] = {}
        self.last_update_time = 0
        self.update_interval = 60  # Update positions every 60 seconds
        self.position_history: Dict[str, List[Dict[str, Any]]] = {}  # Track position changes over time
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get the current position for a symbol.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            Position object if position exists, None otherwise
        """
        self._update_positions_if_needed()
        
        # Convert symbol format if needed (BTC/USD -> BTCUSD)
        formatted_symbol = symbol.replace("/", "")
        
        return self.positions.get(formatted_symbol)
    
    def get_position_quantity(self, symbol: str) -> float:
        """
        Get the quantity of a position.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            float: Quantity of the position, 0 if no position
        """
        position = self.get_position(symbol)
        return float(position.qty) if position else 0.0
    
    def get_position_value(self, symbol: str) -> float:
        """
        Get the current market value of a position.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            float: Market value of the position, 0 if no position
        """
        position = self.get_position(symbol)
        return float(position.market_value) if position else 0.0
    
    def get_unrealized_pnl(self, symbol: str) -> float:
        """
        Get the unrealized profit/loss for a position.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            float: Unrealized P&L, 0 if no position
        """
        position = self.get_position(symbol)
        return float(position.unrealized_pl) if position else 0.0
    
    def get_average_entry_price(self, symbol: str) -> float:
        """
        Get the average entry price for a position.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            float: Average entry price, 0 if no position
        """
        position = self.get_position(symbol)
        return float(position.avg_entry_price) if position else 0.0
    
    def get_position_summary(self, symbol: str) -> Dict[str, Any]:
        """
        Get a comprehensive summary of a position.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            Dict: Position summary with key metrics
        """
        position = self.get_position(symbol)
        
        if not position:
            return {
                "symbol": symbol.replace("/", ""),
                "quantity": 0.0,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
                "avg_entry_price": 0.0,
                "pnl_percentage": 0.0,
                "has_position": False
            }
        
        avg_entry = float(position.avg_entry_price)
        current_value = float(position.market_value)
        unrealized_pnl = float(position.unrealized_pl)
        
        # Calculate P&L percentage
        cost_basis = avg_entry * float(position.qty)
        pnl_percentage = (unrealized_pnl / cost_basis) * 100 if cost_basis > 0 else 0.0
        
        return {
            "symbol": position.symbol,
            "quantity": float(position.qty),
            "market_value": current_value,
            "unrealized_pnl": unrealized_pnl,
            "avg_entry_price": avg_entry,
            "pnl_percentage": pnl_percentage,
            "has_position": True
        }
    
    def track_position_change(self, symbol: str, current_price: float) -> None:
        """
        Track position changes over time for historical analysis.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            current_price: Current market price
        """
        formatted_symbol = symbol.replace("/", "")
        position = self.get_position(symbol)
        
        if position:
            # Create position snapshot
            snapshot = {
                "timestamp": datetime.now(),
                "quantity": float(position.qty),
                "market_value": float(position.market_value),
                "unrealized_pnl": float(position.unrealized_pl),
                "avg_entry_price": float(position.avg_entry_price),
                "current_price": current_price
            }
            
            # Initialize history for this symbol if needed
            if formatted_symbol not in self.position_history:
                self.position_history[formatted_symbol] = []
                
            # Add snapshot to history (keep last 100 entries)
            self.position_history[formatted_symbol].append(snapshot)
            if len(self.position_history[formatted_symbol]) > 100:
                self.position_history[formatted_symbol].pop(0)
    
    def get_position_history(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get position history for a symbol.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            List: Position history snapshots
        """
        formatted_symbol = symbol.replace("/", "")
        return self.position_history.get(formatted_symbol, [])
    
    def _update_positions_if_needed(self) -> None:
        """
        Update positions from Alpaca API if the update interval has passed.
        """
        current_time = time.time()
        if current_time - self.last_update_time > self.update_interval:
            self._update_positions()
            self.last_update_time = current_time
    
    def _update_positions(self) -> None:
        """
        Fetch and update all positions from Alpaca API.
        
        Raises:
            Exception: If there's an error fetching positions
        """
        try:
            positions = self.trading_client.get_all_positions()
            
            # Update positions dictionary
            self.positions = {p.symbol: p for p in positions}
            log_info(f"Updated positions: {len(self.positions)} active positions")
            
        except Exception as e:
            log_error("Error updating positions", e)
            # Re-raise the exception to be caught by reconcile_positions
            raise
    
    def reconcile_positions(self) -> bool:
        """
        Force reconciliation of positions with Alpaca API.
        Ensures local position data matches the broker's records.
        
        Returns:
            bool: True if reconciliation was successful
        """
        try:
            # Force update from API
            self._update_positions()
            
            # Log position details after reconciliation
            for symbol, position in self.positions.items():
                log_info(f"Reconciled position: {symbol}, "
                        f"Qty: {position.qty}, "
                        f"Value: ${float(position.market_value):.2f}, "
                        f"P&L: ${float(position.unrealized_pl):.2f}")
            
            return True
        except Exception as e:
            log_error("Failed to reconcile positions", e)
            return False
    
    def verify_position_accuracy(self, symbol: str, expected_qty: float) -> Tuple[bool, float]:
        """
        Verify that the position quantity matches the expected quantity.
        Useful for detecting discrepancies between local tracking and broker records.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            expected_qty: Expected position quantity
            
        Returns:
            Tuple[bool, float]: (is_accurate, actual_quantity)
        """
        # Force position update from API
        self.reconcile_positions()
        
        # Get actual position
        actual_qty = self.get_position_quantity(symbol)
        
        # Check if quantities match within a small tolerance (0.0001)
        is_accurate = abs(actual_qty - expected_qty) < 0.0001
        
        if not is_accurate:
            log_warning(f"Position discrepancy for {symbol}: "
                      f"Expected {expected_qty}, Actual {actual_qty}")
        
        return is_accurate, actual_qty


class OrderManager:
    """
    Manages order placement and tracking.
    Provides methods to place orders and check order status.
    """
    
    def __init__(self, trading_client: TradingClient):
        """
        Initialize the OrderManager.
        
        Args:
            trading_client: Alpaca TradingClient instance
        """
        self.trading_client = trading_client
    
    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def place_market_order(self, symbol: str, side: OrderSide, 
                          qty: float) -> Optional[Order]:
        """
        Place a market order.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            side: OrderSide.BUY or OrderSide.SELL
            qty: Quantity to buy or sell
            
        Returns:
            Order object if successful, None otherwise
        """
        # Format symbol for Alpaca API (BTC/USD -> BTCUSD)
        formatted_symbol = symbol.replace("/", "")
        
        # Validate quantity
        if not validate_numeric(qty, min_value=0.0001):
            log_error(f"Invalid order quantity: {qty}")
            return None
        
        # Create order request
        order_request = MarketOrderRequest(
            symbol=formatted_symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC
        )
        
        try:
            # Submit order
            order = self.trading_client.submit_order(order_request)
            log_info(f"Placed {side.name} order for {qty} {formatted_symbol}, order ID: {order.id}")
            return order
        except Exception as e:
            log_error(f"Error placing {side.name} order for {formatted_symbol}", e)
            return None
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """
        Get the status of an order.
        
        Args:
            order_id: The order ID
            
        Returns:
            str: Order status if found, None otherwise
        """
        try:
            order = self.trading_client.get_order(order_id)
            return order.status
        except Exception as e:
            log_error(f"Error getting order status for order {order_id}", e)
            return None
            
    def is_order_filled(self, order_id: str) -> bool:
        """
        Check if an order has been filled.
        
        Args:
            order_id: The order ID
            
        Returns:
            bool: True if order is filled, False otherwise
        """
        status = self.get_order_status(order_id)
        return status == OrderStatus.FILLED
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: The order ID
            
        Returns:
            bool: True if cancellation was successful
        """
        try:
            self.trading_client.cancel_order(order_id)
            log_info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            log_error(f"Error cancelling order {order_id}", e)
            return False
    
    def get_recent_orders(self, symbol: str = None, limit: int = 10) -> List[Order]:
        """
        Get recent orders.
        
        Args:
            symbol: Optional symbol to filter orders
            limit: Maximum number of orders to return
            
        Returns:
            List[Order]: List of recent orders
        """
        try:
            # Format symbol if provided
            formatted_symbol = symbol.replace("/", "") if symbol else None
            
            # Create request parameters
            request_params = GetOrdersRequest(
                limit=limit,
                nested=True  # Include nested orders
            )
            
            if formatted_symbol:
                request_params.symbols = [formatted_symbol]
            
            # Get orders
            orders = self.trading_client.get_orders(request_params)
            return orders
        except Exception as e:
            log_error("Error getting recent orders", e)
            return []


class Trader:
    """
    Handles trade execution through Alpaca API.
    Manages order placement, position tracking, and trade execution.
    """
    
    def __init__(self, credentials: AlpacaCredentials, settings: TradingSettings):
        """
        Initialize the Trader with Alpaca API credentials.
        
        Args:
            credentials: AlpacaCredentials object containing API keys and settings
            settings: TradingSettings object containing trading parameters
        """
        self.credentials = credentials
        self.settings = settings
        
        # Initialize Alpaca trading client
        self.trading_client = TradingClient(
            api_key=credentials.api_key,
            secret_key=credentials.secret_key,
            paper=credentials.paper_trading
        )
        
        # Initialize position and order managers
        self.position_manager = PositionManager(self.trading_client)
        self.order_manager = OrderManager(self.trading_client)
        
        # Track last trade time to prevent excessive trading
        self.last_trade_time = 0
        
        log_info(f"Trader initialized with paper trading: {credentials.paper_trading}")
    
    def execute_trade(self, signal: TradingSignal) -> Optional[TradeResult]:
        """
        Execute a trade based on a trading signal.
        
        Args:
            signal: TradingSignal object containing trade information
            
        Returns:
            TradeResult if trade was executed, None otherwise
        """
        # Check if we should trade based on signal
        if not self._should_trade(signal):
            return None
        
        # Get the symbol from settings
        symbol = self.settings.symbol
        
        # Execute buy or sell based on signal
        if signal.action == SignalType.BUY:
            return self._execute_buy(symbol, signal)
        elif signal.action == SignalType.SELL:
            return self._execute_sell(symbol, signal)
        else:
            # HOLD signal, no trade
            log_info(f"HOLD signal received with confidence {signal.confidence:.2f}, no trade executed")
            return None
    
    def _should_trade(self, signal: TradingSignal) -> bool:
        """
        Determine if we should execute a trade based on the signal and trading rules.
        
        Args:
            signal: TradingSignal object
            
        Returns:
            bool: True if we should trade, False otherwise
        """
        # Don't trade on HOLD signals
        if signal.action == SignalType.HOLD:
            return False
        
        # Check signal confidence
        if signal.confidence < 0.5:
            log_info(f"Signal confidence too low: {signal.confidence:.2f}")
            return False
        
        # Check minimum trade interval
        current_time = time.time()
        min_interval_seconds = self.settings.min_trade_interval * 60
        if current_time - self.last_trade_time < min_interval_seconds:
            log_info(f"Minimum trade interval not met, skipping trade")
            return False
        
        return True
    
    def _execute_buy(self, symbol: str, signal: TradingSignal) -> Optional[TradeResult]:
        """
        Execute a buy order.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            signal: TradingSignal object
            
        Returns:
            TradeResult if successful, None otherwise
        """
        try:
            # Calculate quantity based on trade amount
            price = signal.price
            if price <= 0:
                log_error(f"Invalid price for buy order: {price}")
                return None
            
            # Calculate quantity based on USD amount
            quantity = self._calculate_buy_quantity(symbol, price)
            
            if quantity < 0.0001:  # Minimum quantity for fractional crypto
                log_warning(f"Buy quantity too small: {quantity}, minimum is 0.0001")
                return None
            
            # Place the order
            order = self.order_manager.place_market_order(
                symbol=symbol,
                side=OrderSide.BUY,
                qty=quantity
            )
            
            if not order:
                return None
            
            # Update last trade time
            self.last_trade_time = time.time()
            
            # Create trade result
            result = TradeResult(
                order_id=order.id,
                symbol=symbol,
                side="BUY",
                quantity=float(quantity),
                price=price,
                status=order.status.value,
                timestamp=datetime.now()
            )
            
            log_info(f"Buy order executed: {quantity} {symbol} at ${price:.2f}")
            
            # Set up stop loss and take profit if configured
            if self.settings.stop_loss_pct > 0 or self.settings.take_profit_pct > 0:
                self._setup_risk_management(symbol, price, OrderSide.BUY)
                
            return result
            
        except Exception as e:
            log_error(f"Error executing buy order for {symbol}", e)
            return None
    
    def _execute_sell(self, symbol: str, signal: TradingSignal) -> Optional[TradeResult]:
        """
        Execute a sell order.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            signal: TradingSignal object
            
        Returns:
            TradeResult if successful, None otherwise
        """
        try:
            # Get current position
            position_qty = self.position_manager.get_position_quantity(symbol)
            
            if position_qty <= 0:
                log_info(f"No position to sell for {symbol}")
                return None
            
            # Place the order to sell entire position
            order = self.order_manager.place_market_order(
                symbol=symbol,
                side=OrderSide.SELL,
                qty=position_qty
            )
            
            if not order:
                return None
            
            # Update last trade time
            self.last_trade_time = time.time()
            
            # Create trade result
            result = TradeResult(
                order_id=order.id,
                symbol=symbol,
                side="SELL",
                quantity=float(position_qty),
                price=signal.price,
                status=order.status.value,
                timestamp=datetime.now()
            )
            
            log_info(f"Sell order executed: {position_qty} {symbol} at ${signal.price:.2f}")
            return result
            
        except Exception as e:
            log_error(f"Error executing sell order for {symbol}", e)
            return None
    
    def _calculate_buy_quantity(self, symbol: str, price: float) -> float:
        """
        Calculate the quantity to buy based on trade amount and current price.
        
        Args:
            symbol: The trading pair symbol
            price: Current price
            
        Returns:
            float: Quantity to buy
        """
        # Get trade amount from settings
        trade_amount = self.settings.trade_amount
        
        # Calculate quantity (with 4 decimal places for fractional crypto)
        quantity = trade_amount / price
        
        # Round to 4 decimal places (minimum for fractional crypto)
        quantity = round(quantity, 4)
        
        # Check against maximum position size
        current_position_value = self.position_manager.get_position_value(symbol)
        max_position_value = self.settings.max_position_size
        
        if current_position_value + (quantity * price) > max_position_value:
            # Adjust quantity to respect maximum position size
            adjusted_quantity = (max_position_value - current_position_value) / price
            adjusted_quantity = max(0, round(adjusted_quantity, 4))
            
            log_info(f"Adjusted buy quantity from {quantity} to {adjusted_quantity} to respect max position size")
            quantity = adjusted_quantity
        
        return quantity
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict containing account information
        """
        try:
            account = self.trading_client.get_account()
            return {
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity)
            }
        except Exception as e:
            log_error("Error getting account information", e)
            return {}
    
    def validate_order(self, order: Order) -> bool:
        """
        Validate an order for correctness.
        
        Args:
            order: Order object to validate
            
        Returns:
            bool: True if order is valid
        """
        if not order:
            return False
        
        # Check order status
        if order.status in [OrderStatus.REJECTED, OrderStatus.CANCELED, OrderStatus.EXPIRED]:
            log_warning(f"Order {order.id} has invalid status: {order.status}")
            return False
        
        # Check order quantity
        try:
            qty = float(order.qty)
            if qty <= 0:
                log_warning(f"Order {order.id} has invalid quantity: {qty}")
                return False
        except (ValueError, TypeError):
            log_warning(f"Order {order.id} has invalid quantity format")
            return False
        
        return True
        
    def _setup_risk_management(self, symbol: str, entry_price: float, side: OrderSide) -> None:
        """
        Set up stop loss and take profit orders for a position.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            entry_price: The entry price of the position
            side: OrderSide.BUY or OrderSide.SELL
        """
        try:
            # Get position quantity
            position_qty = self.position_manager.get_position_quantity(symbol)
            
            if position_qty <= 0:
                log_warning(f"No position found for {symbol} to set up risk management")
                return
                
            # Calculate stop loss and take profit prices
            if side == OrderSide.BUY:
                # For long positions
                stop_loss_price = entry_price * (1 - self.settings.stop_loss_pct)
                take_profit_price = entry_price * (1 + self.settings.take_profit_pct)
                
                log_info(f"Setting up risk management for long position: "
                        f"Stop loss at ${stop_loss_price:.2f} (-{self.settings.stop_loss_pct*100:.1f}%), "
                        f"Take profit at ${take_profit_price:.2f} (+{self.settings.take_profit_pct*100:.1f}%)")
                
                # Track position for monitoring
                self.position_manager.track_position_change(symbol, entry_price)
                
            elif side == OrderSide.SELL:
                # For short positions (if supported)
                stop_loss_price = entry_price * (1 + self.settings.stop_loss_pct)
                take_profit_price = entry_price * (1 - self.settings.take_profit_pct)
                
                log_info(f"Setting up risk management for short position: "
                        f"Stop loss at ${stop_loss_price:.2f} (+{self.settings.stop_loss_pct*100:.1f}%), "
                        f"Take profit at ${take_profit_price:.2f} (-{self.settings.take_profit_pct*100:.1f}%)")
                
                # Track position for monitoring
                self.position_manager.track_position_change(symbol, entry_price)
            
        except Exception as e:
            log_error(f"Error setting up risk management for {symbol}", e)
            
    def check_risk_management_triggers(self, symbol: str, current_price: float) -> bool:
        """
        Check if current price has triggered any stop loss or take profit levels.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            current_price: The current market price
            
        Returns:
            bool: True if a risk management action was taken
        """
        try:
            # Get current position
            position = self.position_manager.get_position(symbol)
            
            if not position:
                return False
                
            # Get position details
            position_qty = float(position.qty)
            avg_entry_price = float(position.avg_entry_price)
            
            if position_qty <= 0:
                return False
                
            # Calculate price change percentage
            price_change_pct = (current_price - avg_entry_price) / avg_entry_price
            
            # Track position change with current price
            self.position_manager.track_position_change(symbol, current_price)
            
            # Check for stop loss trigger (loss exceeds stop loss percentage)
            if price_change_pct < -self.settings.stop_loss_pct:
                log_warning(f"Stop loss triggered for {symbol} at ${current_price:.2f} "
                          f"(Entry: ${avg_entry_price:.2f}, Loss: {price_change_pct*100:.2f}%)")
                
                # Execute sell order to close position
                self._execute_emergency_sell(symbol, position_qty, current_price, "stop_loss")
                return True
                
            # Check for take profit trigger (gain exceeds take profit percentage)
            elif price_change_pct > self.settings.take_profit_pct:
                log_info(f"Take profit triggered for {symbol} at ${current_price:.2f} "
                       f"(Entry: ${avg_entry_price:.2f}, Gain: {price_change_pct*100:.2f}%)")
                
                # Execute sell order to close position
                self._execute_emergency_sell(symbol, position_qty, current_price, "take_profit")
                return True
                
            return False
            
        except Exception as e:
            log_error(f"Error checking risk management triggers for {symbol}", e)
            return False
            
    def _execute_emergency_sell(self, symbol: str, quantity: float, 
                              current_price: float, reason: str) -> Optional[TradeResult]:
        """
        Execute an emergency sell order for risk management.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            quantity: Quantity to sell
            current_price: Current market price
            reason: Reason for the emergency sell (stop_loss or take_profit)
            
        Returns:
            TradeResult if successful, None otherwise
        """
        try:
            # Place market sell order
            order = self.order_manager.place_market_order(
                symbol=symbol,
                side=OrderSide.SELL,
                qty=quantity
            )
            
            if not order:
                return None
                
            # Create trade result
            result = TradeResult(
                order_id=order.id,
                symbol=symbol,
                side="SELL",
                quantity=float(quantity),
                price=current_price,
                status=order.status.value,
                timestamp=datetime.now(),
                fees=0.0  # Actual fees would be calculated from the order response
            )
            
            log_info(f"Emergency sell executed ({reason}): {quantity} {symbol} at ${current_price:.2f}")
            
            # Verify position was closed
            self.position_manager.reconcile_positions()
            remaining_qty = self.position_manager.get_position_quantity(symbol)
            
            if remaining_qty > 0.0001:
                log_warning(f"Position not fully closed after emergency sell. Remaining: {remaining_qty}")
            
            return result
            
        except Exception as e:
            log_error(f"Error executing emergency sell for {symbol}", e)
            return None
            
    def get_risk_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        Get risk metrics for a position.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            Dict: Risk metrics including stop loss and take profit levels
        """
        try:
            # Get position summary
            position_summary = self.position_manager.get_position_summary(symbol)
            
            if not position_summary["has_position"]:
                return {
                    "has_position": False,
                    "symbol": symbol.replace("/", ""),
                    "stop_loss_level": 0.0,
                    "take_profit_level": 0.0,
                    "risk_reward_ratio": 0.0
                }
            
            # Calculate stop loss and take profit levels
            avg_entry_price = position_summary["avg_entry_price"]
            stop_loss_level = avg_entry_price * (1 - self.settings.stop_loss_pct)
            take_profit_level = avg_entry_price * (1 + self.settings.take_profit_pct)
            
            # Calculate risk-reward ratio
            potential_loss = avg_entry_price - stop_loss_level
            potential_gain = take_profit_level - avg_entry_price
            risk_reward_ratio = potential_gain / potential_loss if potential_loss > 0 else 0.0
            
            return {
                "has_position": True,
                "symbol": position_summary["symbol"],
                "current_price": position_summary["market_value"] / position_summary["quantity"] if position_summary["quantity"] > 0 else 0.0,
                "avg_entry_price": avg_entry_price,
                "stop_loss_level": stop_loss_level,
                "take_profit_level": take_profit_level,
                "stop_loss_pct": self.settings.stop_loss_pct * 100,
                "take_profit_pct": self.settings.take_profit_pct * 100,
                "risk_reward_ratio": risk_reward_ratio,
                "unrealized_pnl": position_summary["unrealized_pnl"],
                "pnl_percentage": position_summary["pnl_percentage"]
            }
            
        except Exception as e:
            log_error(f"Error getting risk metrics for {symbol}", e)
            return {
                "has_position": False,
                "symbol": symbol.replace("/", ""),
                "error": str(e)
            }