"""
Mock Trading Interface

This module implements the main mock trader interface that provides complete API compatibility
with the live Alpaca trading system. It includes MockTrader class for seamless integration
and MockAlpacaAPI class to simulate Alpaca API responses and data structures.
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
    from alpaca.trading.models import Order as AlpacaOrder, Position as AlpacaPosition
except ImportError:
    # Fallback for testing without alpaca-py
    class TradingClient:
        pass
    
    class MarketOrderRequest:
        pass
    
    class GetOrdersRequest:
        pass
    
    class OrderSide:
        BUY = "BUY"
        SELL = "SELL"
    
    class TimeInForce:
        GTC = "GTC"
        DAY = "DAY"
    
    class OrderStatus:
        NEW = "NEW"
        ACCEPTED = "ACCEPTED"
        PARTIALLY_FILLED = "PARTIALLY_FILLED"
        FILLED = "FILLED"
        CANCELED = "CANCELED"
        REJECTED = "REJECTED"
        EXPIRED = "EXPIRED"
    
    class AlpacaOrder:
        pass
    
    class AlpacaPosition:
        pass

from .mock_models import (
    Order, OrderResult, OrderType, MockPosition, ExecutionResult,
    validate_order
)
from .mock_config import MockTradingConfig, load_mock_config
from .execution_engine import ExecutionEngine, MarketData
from .order_manager import OrderManager, Portfolio
from .position_manager import PositionManager
from bot.config import AlpacaCredentials, TradingSettings
from bot.strategy import TradingSignal, SignalType
from bot.trader import TradeResult
from bot.utils import log_error, log_info, log_warning, retry_with_backoff, validate_numeric


@dataclass
class MockCredentials:
    """Mock credentials for simulation environment."""
    api_key: str = "mock_api_key"
    secret_key: str = "mock_secret_key"
    base_url: str = "https://mock.alpaca.markets"
    paper_trading: bool = True


class MockAlpacaAPI:
    """
    Simulates Alpaca API responses and data structures for seamless integration.
    Provides the same interface as Alpaca's TradingClient but operates in simulation mode.
    """
    
    def __init__(self, config: MockTradingConfig):
        """
        Initialize mock Alpaca API.
        
        Args:
            config: Mock trading configuration
        """
        self.config = config
        self.positions: Dict[str, MockPosition] = {}
        self.orders: Dict[str, Order] = {}
        self.account_info = {
            "cash": config.starting_capital,
            "portfolio_value": config.starting_capital,
            "buying_power": config.starting_capital,
            "equity": config.starting_capital
        }
        
        log_info("MockAlpacaAPI initialized in simulation mode")
    
    def get_all_positions(self) -> List[MockPosition]:
        """
        Get all current positions (simulates Alpaca's get_all_positions).
        
        Returns:
            List[MockPosition]: List of current positions
        """
        return [pos for pos in self.positions.values() if abs(pos.quantity) > 0.0001]
    
    def get_position(self, symbol: str) -> Optional[MockPosition]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            MockPosition if exists, None otherwise
        """
        formatted_symbol = symbol.replace("/", "")
        return self.positions.get(formatted_symbol)
    
    def submit_order(self, order_request) -> Order:
        """
        Submit an order (simulates Alpaca's submit_order).
        
        Args:
            order_request: Order request object
            
        Returns:
            Order: Submitted order
        """
        # Create mock order from request
        order = Order(
            symbol=order_request.symbol,
            quantity=float(order_request.qty),
            side=order_request.side,
            order_type=OrderType.MARKET,
            time_in_force=order_request.time_in_force,
            status=OrderStatus.ACCEPTED
        )
        
        # Store order
        self.orders[order.id] = order
        
        log_info(f"Mock order submitted: {order.id} {order.side.value} {order.quantity} {order.symbol}")
        return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order by ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order if found, None otherwise
        """
        return self.orders.get(order_id)
    
    def get_orders(self, request=None) -> List[Order]:
        """
        Get orders with optional filtering.
        
        Args:
            request: Optional request parameters
            
        Returns:
            List[Order]: List of orders
        """
        orders = list(self.orders.values())
        
        if request and hasattr(request, 'limit'):
            orders = orders[-request.limit:]
        
        return orders
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            bool: True if cancelled successfully
        """
        order = self.orders.get(order_id)
        if order and order.can_cancel():
            order.status = OrderStatus.CANCELED
            order.updated_at = datetime.now()
            log_info(f"Mock order cancelled: {order_id}")
            return True
        return False
    
    def get_account(self):
        """
        Get account information.
        
        Returns:
            Mock account object with required attributes
        """
        class MockAccount:
            def __init__(self, account_info):
                self.cash = str(account_info["cash"])
                self.portfolio_value = str(account_info["portfolio_value"])
                self.buying_power = str(account_info["buying_power"])
                self.equity = str(account_info["equity"])
        
        return MockAccount(self.account_info)
    
    def update_account(self, cash_change: float, portfolio_value: float):
        """
        Update account information after trades.
        
        Args:
            cash_change: Change in cash balance
            portfolio_value: New portfolio value
        """
        self.account_info["cash"] += cash_change
        self.account_info["portfolio_value"] = portfolio_value
        self.account_info["buying_power"] = self.account_info["cash"]
        self.account_info["equity"] = portfolio_value
    
    def update_position(self, symbol: str, position: MockPosition):
        """
        Update position information.
        
        Args:
            symbol: Trading symbol
            position: Updated position
        """
        formatted_symbol = symbol.replace("/", "")
        if abs(position.quantity) > 0.0001:
            self.positions[formatted_symbol] = position
        else:
            # Remove zero positions
            if formatted_symbol in self.positions:
                del self.positions[formatted_symbol]


class MockPositionManager:
    """
    Mock position manager that mimics the interface of the live PositionManager.
    """
    
    def __init__(self, mock_api: MockAlpacaAPI, position_manager: PositionManager, mock_trader=None):
        """
        Initialize mock position manager.
        
        Args:
            mock_api: Mock Alpaca API instance
            position_manager: Underlying position manager
            mock_trader: Reference to parent MockTrader instance
        """
        self.mock_api = mock_api
        self.position_manager = position_manager
        self.mock_trader = mock_trader
        self.last_update_time = 0
        self.update_interval = 60
        self.position_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def get_position(self, symbol: str) -> Optional[MockPosition]:
        """Get position for a symbol."""
        # Format symbol to match how it's stored (remove slashes)
        formatted_symbol = symbol.replace("/", "")
        return self.position_manager.get_position(formatted_symbol)
    
    def get_position_quantity(self, symbol: str) -> float:
        """Get position quantity."""
        position = self.get_position(symbol)
        return position.quantity if position else 0.0
    
    def get_position_value(self, symbol: str) -> float:
        """Get position market value."""
        position = self.get_position(symbol)
        if not position:
            return 0.0
        
        # If we have a current price in the market data cache, use it
        formatted_symbol = symbol.replace("/", "")
        if formatted_symbol in self.mock_trader.market_data_cache:
            current_price = self.mock_trader.market_data_cache[formatted_symbol].price
            return abs(position.quantity * current_price)
        
        # Otherwise, use the position's stored market value or calculate from avg entry price
        if position.market_value != 0.0:
            return abs(position.market_value)
        else:
            # Fallback to cost basis if market value is not set
            return abs(position.quantity * position.avg_entry_price)
    
    def get_unrealized_pnl(self, symbol: str) -> float:
        """Get unrealized P&L."""
        position = self.get_position(symbol)
        return position.unrealized_pl if position else 0.0
    
    def get_average_entry_price(self, symbol: str) -> float:
        """Get average entry price."""
        position = self.get_position(symbol)
        return position.avg_entry_price if position else 0.0
    
    def get_position_summary(self, symbol: str) -> Dict[str, Any]:
        """Get position summary."""
        return self.position_manager.get_position_summary(symbol)
    
    def track_position_change(self, symbol: str, current_price: float) -> None:
        """Track position changes."""
        # Implementation matches live trader interface
        formatted_symbol = symbol.replace("/", "")
        position = self.get_position(symbol)
        
        if position:
            snapshot = {
                "timestamp": datetime.now(),
                "quantity": position.quantity,
                "market_value": position.market_value,
                "unrealized_pnl": position.unrealized_pl,
                "avg_entry_price": position.avg_entry_price,
                "current_price": current_price
            }
            
            if formatted_symbol not in self.position_history:
                self.position_history[formatted_symbol] = []
            
            self.position_history[formatted_symbol].append(snapshot)
            if len(self.position_history[formatted_symbol]) > 100:
                self.position_history[formatted_symbol].pop(0)
    
    def get_position_history(self, symbol: str) -> List[Dict[str, Any]]:
        """Get position history."""
        formatted_symbol = symbol.replace("/", "")
        return self.position_history.get(formatted_symbol, [])
    
    def reconcile_positions(self) -> bool:
        """Reconcile positions."""
        try:
            # In mock mode, positions are always consistent
            log_info("Mock position reconciliation completed successfully")
            return True
        except Exception as e:
            log_error(f"Mock position reconciliation failed: {e}")
            return False
    
    def verify_position_accuracy(self, symbol: str, expected_qty: float) -> Tuple[bool, float]:
        """Verify position accuracy."""
        actual_qty = self.get_position_quantity(symbol)
        is_accurate = abs(actual_qty - expected_qty) < 0.0001
        
        if not is_accurate:
            log_warning(f"Mock position discrepancy for {symbol}: "
                      f"Expected {expected_qty}, Actual {actual_qty}")
        
        return is_accurate, actual_qty


class MockOrderManager:
    """
    Mock order manager that mimics the interface of the live OrderManager.
    """
    
    def __init__(self, mock_api: MockAlpacaAPI, order_manager: OrderManager):
        """
        Initialize mock order manager.
        
        Args:
            mock_api: Mock Alpaca API instance
            order_manager: Underlying order manager
        """
        self.mock_api = mock_api
        self.order_manager = order_manager
    
    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def place_market_order(self, symbol: str, side: OrderSide, qty: float) -> Optional[Order]:
        """Place a market order."""
        formatted_symbol = symbol.replace("/", "")
        
        if not validate_numeric(qty, min_value=0.0001):
            log_error(f"Invalid order quantity: {qty}")
            return None
        
        # Create mock order request
        class MockOrderRequest:
            def __init__(self, symbol, qty, side, time_in_force):
                self.symbol = symbol
                self.qty = qty
                self.side = side
                self.time_in_force = time_in_force
        
        order_request = MockOrderRequest(
            symbol=formatted_symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC
        )
        
        try:
            order = self.mock_api.submit_order(order_request)
            log_info(f"Placed mock {side.value} order for {qty} {formatted_symbol}, order ID: {order.id}")
            return order
        except Exception as e:
            log_error(f"Error placing mock {side.value} order for {formatted_symbol}", e)
            return None
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get order status."""
        order = self.mock_api.get_order(order_id)
        return order.status.value if order else None
    
    def is_order_filled(self, order_id: str) -> bool:
        """Check if order is filled."""
        status = self.get_order_status(order_id)
        return status == OrderStatus.FILLED.value
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        return self.mock_api.cancel_order(order_id)
    
    def get_recent_orders(self, symbol: str = None, limit: int = 10) -> List[Order]:
        """Get recent orders."""
        class MockGetOrdersRequest:
            def __init__(self, limit, symbols=None):
                self.limit = limit
                self.symbols = symbols
        
        request = MockGetOrdersRequest(limit=limit)
        if symbol:
            formatted_symbol = symbol.replace("/", "")
            request.symbols = [formatted_symbol]
        
        return self.mock_api.get_orders(request)


class MockTrader:
    """
    Main mock trader interface that provides complete API compatibility with the live Trader class.
    Handles trade execution, position tracking, and portfolio management in simulation mode.
    """
    
    def __init__(self, credentials: AlpacaCredentials, settings: TradingSettings, 
                 config_path: Optional[str] = None):
        """
        Initialize the MockTrader.
        
        Args:
            credentials: Alpaca credentials (used for interface compatibility)
            settings: Trading settings
            config_path: Optional path to mock trading configuration
        """
        self.credentials = MockCredentials()  # Use mock credentials
        self.settings = settings
        
        # Load mock trading configuration
        self.config = load_mock_config(config_path)
        
        # Initialize mock components
        self.mock_api = MockAlpacaAPI(self.config)
        self.execution_engine = ExecutionEngine(self.config)
        self.order_manager_impl = OrderManager(self.config)
        self.position_manager_impl = PositionManager(self.config, self.config.starting_capital)
        
        # Create interface-compatible managers
        self.position_manager = MockPositionManager(self.mock_api, self.position_manager_impl, self)
        self.order_manager = MockOrderManager(self.mock_api, self.order_manager_impl)
        
        # Track last trade time
        self.last_trade_time = 0
        
        # Market data cache for execution
        self.market_data_cache: Dict[str, MarketData] = {}
        
        log_info(f"MockTrader initialized with ${self.config.starting_capital:,.2f} starting capital")
    
    def execute_trade(self, signal: TradingSignal) -> Optional[TradeResult]:
        """
        Execute a trade based on a trading signal (matches live Trader interface).
        
        Args:
            signal: TradingSignal object containing trade information
            
        Returns:
            TradeResult if trade was executed, None otherwise
        """
        if not self._should_trade(signal):
            return None
        
        symbol = self.settings.symbol
        
        if signal.action == SignalType.BUY:
            return self._execute_buy(symbol, signal)
        elif signal.action == SignalType.SELL:
            return self._execute_sell(symbol, signal)
        else:
            log_info(f"HOLD signal received with confidence {signal.confidence:.2f}, no trade executed")
            return None
    
    def _should_trade(self, signal: TradingSignal) -> bool:
        """Determine if we should execute a trade."""
        if signal.action == SignalType.HOLD:
            return False
        
        if signal.confidence < 0.5:
            log_info(f"Signal confidence too low: {signal.confidence:.2f}")
            return False
        
        current_time = time.time()
        min_interval_seconds = self.settings.min_trade_interval * 60
        if current_time - self.last_trade_time < min_interval_seconds:
            log_info(f"Minimum trade interval not met, skipping trade")
            return False
        
        return True
    
    def _execute_buy(self, symbol: str, signal: TradingSignal) -> Optional[TradeResult]:
        """Execute a buy order."""
        try:
            price = signal.price
            if price <= 0:
                log_error(f"Invalid price for buy order: {price}")
                return None
            
            quantity = self._calculate_buy_quantity(symbol, price)
            
            if quantity < 0.0001:
                log_warning(f"Buy quantity too small: {quantity}, minimum is 0.0001")
                return None
            
            # Create market data for execution
            market_data = self._create_market_data(symbol, price)
            
            # Create order
            order = Order(
                symbol=symbol.replace("/", ""),
                quantity=quantity,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET
            )
            
            # Execute order through execution engine
            execution_result = self.execution_engine.execute_market_order(order, market_data)
            
            if execution_result.executed_quantity > 0:
                # Update position
                self.position_manager_impl.update_position(execution_result)
                
                # Update mock API
                position = self.position_manager_impl.get_position(symbol)
                if position:
                    self.mock_api.update_position(symbol, position)
                
                # Update account
                cash_change = -(execution_result.executed_quantity * execution_result.execution_price + execution_result.fees)
                portfolio_value = self.position_manager_impl.calculate_portfolio_value({symbol: price})
                self.mock_api.update_account(cash_change, portfolio_value)
                
                # Update last trade time
                self.last_trade_time = time.time()
                
                # Create trade result
                result = TradeResult(
                    order_id=order.id,
                    symbol=symbol,
                    side="BUY",
                    quantity=execution_result.executed_quantity,
                    price=execution_result.execution_price,
                    status=OrderStatus.FILLED.value,
                    timestamp=execution_result.execution_time,
                    fees=execution_result.fees
                )
                
                log_info(f"Mock buy order executed: {quantity} {symbol} at ${execution_result.execution_price:.4f}")
                
                # Set up risk management
                if self.settings.stop_loss_pct > 0 or self.settings.take_profit_pct > 0:
                    self._setup_risk_management(symbol, execution_result.execution_price, OrderSide.BUY)
                
                return result
            
            return None
            
        except Exception as e:
            log_error(f"Error executing mock buy order for {symbol}", e)
            return None
    
    def _execute_sell(self, symbol: str, signal: TradingSignal) -> Optional[TradeResult]:
        """Execute a sell order."""
        try:
            position_qty = self.position_manager.get_position_quantity(symbol)
            
            if position_qty <= 0:
                log_info(f"No position to sell for {symbol}")
                return None
            
            # Create market data for execution
            market_data = self._create_market_data(symbol, signal.price)
            
            # Create order
            order = Order(
                symbol=symbol.replace("/", ""),
                quantity=position_qty,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET
            )
            
            # Execute order through execution engine
            execution_result = self.execution_engine.execute_market_order(order, market_data)
            
            if execution_result.executed_quantity > 0:
                # Update position (sell is negative quantity)
                sell_execution = ExecutionResult(
                    order_id=execution_result.order_id,
                    symbol=execution_result.symbol,
                    executed_quantity=-execution_result.executed_quantity,  # Negative for sell
                    execution_price=execution_result.execution_price,
                    slippage=execution_result.slippage,
                    fees=execution_result.fees,
                    execution_time=execution_result.execution_time,
                    market_impact=execution_result.market_impact,
                    partial_fill=execution_result.partial_fill,
                    remaining_quantity=execution_result.remaining_quantity,
                    execution_delay_ms=execution_result.execution_delay_ms,
                    liquidity_impact=execution_result.liquidity_impact
                )
                
                self.position_manager_impl.update_position(sell_execution)
                
                # Update mock API
                position = self.position_manager_impl.get_position(symbol)
                if position:
                    self.mock_api.update_position(symbol, position)
                else:
                    # Position was closed, remove from API
                    formatted_symbol = symbol.replace("/", "")
                    if formatted_symbol in self.mock_api.positions:
                        del self.mock_api.positions[formatted_symbol]
                
                # Update account
                cash_change = execution_result.executed_quantity * execution_result.execution_price - execution_result.fees
                portfolio_value = self.position_manager_impl.calculate_portfolio_value({symbol: signal.price})
                self.mock_api.update_account(cash_change, portfolio_value)
                
                # Update last trade time
                self.last_trade_time = time.time()
                
                # Create trade result
                result = TradeResult(
                    order_id=order.id,
                    symbol=symbol,
                    side="SELL",
                    quantity=execution_result.executed_quantity,
                    price=execution_result.execution_price,
                    status=OrderStatus.FILLED.value,
                    timestamp=execution_result.execution_time,
                    fees=execution_result.fees
                )
                
                log_info(f"Mock sell order executed: {execution_result.executed_quantity} {symbol} at ${execution_result.execution_price:.4f}")
                return result
            
            return None
            
        except Exception as e:
            log_error(f"Error executing mock sell order for {symbol}", e)
            return None
    
    def _calculate_buy_quantity(self, symbol: str, price: float) -> float:
        """Calculate buy quantity based on trade amount and price."""
        trade_amount = self.settings.trade_amount
        quantity = trade_amount / price
        quantity = round(quantity, 4)
        
        # Check against maximum position size
        current_position_value = self.position_manager.get_position_value(symbol)
        max_position_value = self.settings.max_position_size
        
        if current_position_value + (quantity * price) > max_position_value:
            adjusted_quantity = (max_position_value - current_position_value) / price
            adjusted_quantity = max(0, round(adjusted_quantity, 4))
            
            log_info(f"Adjusted buy quantity from {quantity} to {adjusted_quantity} to respect max position size")
            quantity = adjusted_quantity
        
        return quantity
    
    def _create_market_data(self, symbol: str, price: float) -> MarketData:
        """Create market data for execution simulation."""
        spread = price * 0.001  # 0.1% spread
        bid = price - spread / 2
        ask = price + spread / 2
        
        return MarketData(
            symbol=symbol.replace("/", ""),
            price=price,
            bid=bid,
            ask=ask,
            volume=1000000,  # Mock volume
            volatility=0.02,  # Mock volatility
            timestamp=datetime.now()
        )
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        try:
            account = self.mock_api.get_account()
            return {
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity)
            }
        except Exception as e:
            log_error("Error getting mock account information", e)
            return {}
    
    def validate_order(self, order: Order) -> bool:
        """Validate an order for correctness."""
        if not order:
            return False
        
        if order.status in [OrderStatus.REJECTED, OrderStatus.CANCELED, OrderStatus.EXPIRED]:
            log_warning(f"Order {order.id} has invalid status: {order.status}")
            return False
        
        try:
            qty = float(order.quantity)
            if qty <= 0:
                log_warning(f"Order {order.id} has invalid quantity: {qty}")
                return False
        except (ValueError, TypeError):
            log_warning(f"Order {order.id} has invalid quantity format")
            return False
        
        return True
    
    def _setup_risk_management(self, symbol: str, entry_price: float, side: OrderSide) -> None:
        """Set up stop loss and take profit monitoring."""
        try:
            position_qty = self.position_manager.get_position_quantity(symbol)
            
            if position_qty <= 0:
                log_warning(f"No position found for {symbol} to set up risk management")
                return
            
            if side == OrderSide.BUY:
                stop_loss_price = entry_price * (1 - self.settings.stop_loss_pct)
                take_profit_price = entry_price * (1 + self.settings.take_profit_pct)
                
                log_info(f"Setting up mock risk management for long position: "
                        f"Stop loss at ${stop_loss_price:.2f} (-{self.settings.stop_loss_pct*100:.1f}%), "
                        f"Take profit at ${take_profit_price:.2f} (+{self.settings.take_profit_pct*100:.1f}%)")
                
                self.position_manager.track_position_change(symbol, entry_price)
            
        except Exception as e:
            log_error(f"Error setting up mock risk management for {symbol}", e)
    
    def check_risk_management_triggers(self, symbol: str, current_price: float) -> bool:
        """Check if current price has triggered any stop loss or take profit levels."""
        try:
            position = self.position_manager.get_position(symbol)
            
            if not position:
                return False
            
            position_qty = position.quantity
            avg_entry_price = position.avg_entry_price
            
            if position_qty <= 0:
                return False
            
            price_change_pct = (current_price - avg_entry_price) / avg_entry_price
            
            self.position_manager.track_position_change(symbol, current_price)
            
            # Check for stop loss trigger
            if price_change_pct < -self.settings.stop_loss_pct:
                log_warning(f"Mock stop loss triggered for {symbol} at ${current_price:.2f} "
                          f"(Entry: ${avg_entry_price:.2f}, Loss: {price_change_pct*100:.2f}%)")
                
                self._execute_emergency_sell(symbol, position_qty, current_price, "stop_loss")
                return True
            
            # Check for take profit trigger
            elif price_change_pct > self.settings.take_profit_pct:
                log_info(f"Mock take profit triggered for {symbol} at ${current_price:.2f} "
                       f"(Entry: ${avg_entry_price:.2f}, Gain: {price_change_pct*100:.2f}%)")
                
                self._execute_emergency_sell(symbol, position_qty, current_price, "take_profit")
                return True
            
            return False
            
        except Exception as e:
            log_error(f"Error checking mock risk management triggers for {symbol}", e)
            return False
    
    def _execute_emergency_sell(self, symbol: str, quantity: float, 
                              current_price: float, reason: str) -> Optional[TradeResult]:
        """Execute an emergency sell order for risk management."""
        try:
            # Create market data
            market_data = self._create_market_data(symbol, current_price)
            
            # Create order
            order = Order(
                symbol=symbol.replace("/", ""),
                quantity=quantity,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET
            )
            
            # Execute order
            execution_result = self.execution_engine.execute_market_order(order, market_data)
            
            if execution_result.executed_quantity > 0:
                # Update position (sell is negative quantity)
                sell_execution = ExecutionResult(
                    order_id=execution_result.order_id,
                    symbol=execution_result.symbol,
                    executed_quantity=-execution_result.executed_quantity,
                    execution_price=execution_result.execution_price,
                    slippage=execution_result.slippage,
                    fees=execution_result.fees,
                    execution_time=execution_result.execution_time,
                    market_impact=execution_result.market_impact,
                    partial_fill=execution_result.partial_fill,
                    remaining_quantity=execution_result.remaining_quantity,
                    execution_delay_ms=execution_result.execution_delay_ms,
                    liquidity_impact=execution_result.liquidity_impact
                )
                
                self.position_manager_impl.update_position(sell_execution)
                
                # Update mock API
                position = self.position_manager_impl.get_position(symbol)
                if position:
                    self.mock_api.update_position(symbol, position)
                else:
                    formatted_symbol = symbol.replace("/", "")
                    if formatted_symbol in self.mock_api.positions:
                        del self.mock_api.positions[formatted_symbol]
                
                # Update account
                cash_change = execution_result.executed_quantity * execution_result.execution_price - execution_result.fees
                portfolio_value = self.position_manager_impl.calculate_portfolio_value({symbol: current_price})
                self.mock_api.update_account(cash_change, portfolio_value)
                
                # Create trade result
                result = TradeResult(
                    order_id=order.id,
                    symbol=symbol,
                    side="SELL",
                    quantity=execution_result.executed_quantity,
                    price=execution_result.execution_price,
                    status=OrderStatus.FILLED.value,
                    timestamp=execution_result.execution_time,
                    fees=execution_result.fees
                )
                
                log_info(f"Mock emergency sell executed ({reason}): {execution_result.executed_quantity} {symbol} at ${execution_result.execution_price:.4f}")
                return result
            
            return None
            
        except Exception as e:
            log_error(f"Error executing mock emergency sell for {symbol}", e)
            return None