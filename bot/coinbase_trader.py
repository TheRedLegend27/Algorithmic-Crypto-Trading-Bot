"""
Coinbase trader class integrating all components for cryptocurrency trading.

This module implements the main CoinbaseTrader class that orchestrates trading operations
by integrating the position manager, order manager, and data fetcher components.
It handles trade execution for buy/sell signals and implements account balance checks.
"""
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials
from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.crypto_position_manager import CryptoPositionManager
from bot.crypto_order_manager import CryptoOrderManager, CryptoTradeResult
from bot.strategy import TradingSignal, SignalType
from bot.utils import log_error, log_info, log_warning, validate_numeric


@dataclass
class CryptoTradingSettings:
    """
    Data class for cryptocurrency trading settings.
    
    Attributes:
        trading_pair: Trading pair symbol (e.g., "BTC-USD")
        base_currency: Base currency code (e.g., "BTC")
        quote_currency: Quote currency code (e.g., "USD")
        trade_amount_usd: Amount in USD to trade per transaction
        max_position_usd: Maximum position size in USD
        min_order_size: Minimum order size in base currency
        price_precision: Decimal places for price
        size_precision: Decimal places for size
        maker_fee_rate: Fee rate for maker orders
        taker_fee_rate: Fee rate for taker orders
        min_trade_interval: Minimum time between trades in minutes
        stop_loss_pct: Stop loss percentage (0.05 = 5%)
        take_profit_pct: Take profit percentage (0.1 = 10%)
    """
    trading_pair: str = "BTC-USD"
    base_currency: str = "BTC"
    quote_currency: str = "USD"
    trade_amount_usd: float = 10.0
    max_position_usd: float = 100.0
    min_order_size: float = 0.001
    price_precision: int = 2
    size_precision: int = 8
    maker_fee_rate: float = 0.005  # 0.5%
    taker_fee_rate: float = 0.005  # 0.5%
    min_trade_interval: int = 5  # minutes
    stop_loss_pct: float = 0.05  # 5%
    take_profit_pct: float = 0.1  # 10%


class CoinbaseTrader:
    """
    Main trader class that orchestrates cryptocurrency trading operations.
    Integrates position manager, order manager, and data fetcher components.
    """
    
    def __init__(self, credentials: CoinbaseCredentials, settings: CryptoTradingSettings):
        """
        Initialize the CoinbaseTrader with API credentials and trading settings.
        
        Args:
            credentials: CoinbaseCredentials object containing API keys and settings
            settings: CryptoTradingSettings object containing trading parameters
        """
        self.credentials = credentials
        self.settings = settings
        
        # Initialize Coinbase client
        self.client = CoinbaseClient(credentials)
        
        # Initialize components
        self.data_fetcher = CoinbaseDataFetcher(credentials)
        self.position_manager = CryptoPositionManager(self.client)
        self.order_manager = CryptoOrderManager(self.client)
        
        # Update fee rates in order manager
        self.order_manager.update_fee_rates(
            maker_fee=settings.maker_fee_rate,
            taker_fee=settings.taker_fee_rate
        )
        
        # Track last trade time to prevent excessive trading
        self.last_trade_time = 0
        
        # Subscribe to WebSocket for real-time data
        self._setup_websocket()
        
        log_info(f"CoinbaseTrader initialized for {settings.trading_pair}")
    
    def _setup_websocket(self) -> None:
        """
        Set up WebSocket connection for real-time market data.
        """
        try:
            # Subscribe to WebSocket for the configured trading pair
            self.data_fetcher.subscribe_to_websocket([self.settings.trading_pair])
            log_info(f"WebSocket subscription set up for {self.settings.trading_pair}")
        except Exception as e:
            log_warning(f"Failed to set up WebSocket, will use REST API: {str(e)}")
    
    def execute_trade(self, signal: TradingSignal) -> Optional[CryptoTradeResult]:
        """
        Execute a trade based on a trading signal.
        
        Args:
            signal: TradingSignal object containing trade information
            
        Returns:
            CryptoTradeResult if trade was executed, None otherwise
        """
        # Check if we should trade based on signal
        if not self._should_trade(signal):
            return None
        
        # Get the trading pair from settings
        trading_pair = self.settings.trading_pair
        
        # Execute buy or sell based on signal
        if signal.action == SignalType.BUY:
            return self._execute_buy(trading_pair, signal)
        elif signal.action == SignalType.SELL:
            return self._execute_sell(trading_pair, signal)
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
    
    def _execute_buy(self, trading_pair: str, signal: TradingSignal) -> Optional[CryptoTradeResult]:
        """
        Execute a buy order.
        
        Args:
            trading_pair: The trading pair (e.g., "BTC-USD")
            signal: TradingSignal object
            
        Returns:
            CryptoTradeResult if successful, None otherwise
        """
        try:
            # Get current price if not provided in signal
            price = signal.price
            if price <= 0:
                price = self.data_fetcher.get_latest_price(trading_pair)
                if price <= 0:
                    log_error(f"Invalid price for buy order: {price}")
                    return None
            
            # Calculate quantity based on USD amount
            quantity = self._calculate_buy_quantity(trading_pair, price)
            
            if quantity < self.settings.min_order_size:
                log_warning(f"Buy quantity too small: {quantity}, minimum is {self.settings.min_order_size}")
                return None
            
            # Check account balance before placing order
            if not self._check_sufficient_balance_for_buy(trading_pair, quantity, price):
                log_warning(f"Insufficient balance for buy order of {quantity} {self.settings.base_currency}")
                return None
            
            # Place the market order
            result = self.order_manager.place_market_order(
                product_id=trading_pair,
                side="buy",
                size=quantity
            )
            
            if not result:
                return None
            
            # Update last trade time
            self.last_trade_time = time.time()
            
            # Update position tracking
            self.position_manager.track_crypto_position(
                currency=self.settings.base_currency,
                amount=quantity,
                price=price,
                fees=result.fees
            )
            
            log_info(f"Buy order executed: {quantity} {self.settings.base_currency} at ${price:.2f}")
            
            # Set up risk management monitoring
            self._setup_risk_management(trading_pair, price, "buy")
                
            return result
            
        except Exception as e:
            log_error(f"Error executing buy order for {trading_pair}", e)
            return None
    
    def _execute_sell(self, trading_pair: str, signal: TradingSignal) -> Optional[CryptoTradeResult]:
        """
        Execute a sell order.
        
        Args:
            trading_pair: The trading pair (e.g., "BTC-USD")
            signal: TradingSignal object
            
        Returns:
            CryptoTradeResult if successful, None otherwise
        """
        try:
            # Get current price if not provided in signal
            price = signal.price
            if price <= 0:
                price = self.data_fetcher.get_latest_price(trading_pair)
                if price <= 0:
                    log_error(f"Invalid price for sell order: {price}")
                    return None
            
            # Get current position
            balance = self.position_manager.get_crypto_balance(self.settings.base_currency)
            
            if not balance or balance.available <= 0:
                log_info(f"No position to sell for {self.settings.base_currency}")
                return None
            
            # Use available balance for sell order
            quantity = balance.available
            
            # Check minimum order size
            if quantity < self.settings.min_order_size:
                log_warning(f"Sell quantity too small: {quantity}, minimum is {self.settings.min_order_size}")
                return None
            
            # Place the market order
            result = self.order_manager.place_market_order(
                product_id=trading_pair,
                side="sell",
                size=quantity
            )
            
            if not result:
                return None
            
            # Update last trade time
            self.last_trade_time = time.time()
            
            # Update position tracking (negative amount for sell)
            self.position_manager.track_crypto_position(
                currency=self.settings.base_currency,
                amount=-quantity,
                price=price,
                fees=result.fees
            )
            
            log_info(f"Sell order executed: {quantity} {self.settings.base_currency} at ${price:.2f}")
            return result
            
        except Exception as e:
            log_error(f"Error executing sell order for {trading_pair}", e)
            return None
    
    def _calculate_buy_quantity(self, trading_pair: str, price: float) -> float:
        """
        Calculate the quantity to buy based on trade amount and current price.
        
        Args:
            trading_pair: The trading pair
            price: Current price
            
        Returns:
            float: Quantity to buy
        """
        # Get trade amount from settings
        trade_amount = self.settings.trade_amount_usd
        
        # Calculate quantity
        quantity = trade_amount / price
        
        # Round to appropriate precision
        quantity = round(quantity, self.settings.size_precision)
        
        # Check against maximum position size
        position_summary = self.position_manager.get_position_summary(
            self.settings.base_currency, 
            price
        )
        current_position_value = position_summary.get("market_value_usd", 0.0)
        max_position_value = self.settings.max_position_usd
        
        if current_position_value + (quantity * price) > max_position_value:
            # Adjust quantity to respect maximum position size
            adjusted_quantity = (max_position_value - current_position_value) / price
            adjusted_quantity = max(0, round(adjusted_quantity, self.settings.size_precision))
            
            log_info(f"Adjusted buy quantity from {quantity} to {adjusted_quantity} to respect max position size")
            quantity = adjusted_quantity
        
        return quantity
    
    def _check_sufficient_balance_for_buy(self, trading_pair: str, quantity: float, price: float) -> bool:
        """
        Check if there is sufficient balance for a buy order.
        
        Args:
            trading_pair: The trading pair
            quantity: Quantity to buy
            price: Current price
            
        Returns:
            bool: True if sufficient balance
        """
        try:
            # Calculate order value
            order_value = quantity * price
            
            # Add estimated fees
            fees = self.order_manager.calculate_fees("market", quantity, price)
            total_cost = order_value + fees
            
            # Get USD balance
            balance = self.position_manager.get_crypto_balance(self.settings.quote_currency)
            
            if not balance:
                log_warning(f"Could not retrieve {self.settings.quote_currency} balance")
                return False
            
            # Check if available balance is sufficient
            if balance.available < total_cost:
                log_warning(f"Insufficient {self.settings.quote_currency} balance: "
                          f"Available {balance.available:.2f}, Required {total_cost:.2f}")
                return False
            
            return True
            
        except Exception as e:
            log_error(f"Error checking balance for buy order: {str(e)}")
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict containing account information
        """
        try:
            # Get balances for base and quote currencies
            base_balance = self.position_manager.get_crypto_balance(self.settings.base_currency)
            quote_balance = self.position_manager.get_crypto_balance(self.settings.quote_currency)
            
            # Get current price
            current_price = self.data_fetcher.get_latest_price(self.settings.trading_pair)
            
            # Calculate portfolio value
            base_value = base_balance.balance * current_price if base_balance else 0
            quote_value = quote_balance.balance if quote_balance else 0
            portfolio_value = base_value + quote_value
            
            return {
                "base_currency": self.settings.base_currency,
                "base_balance": base_balance.balance if base_balance else 0,
                "base_available": base_balance.available if base_balance else 0,
                "base_value_usd": base_value,
                "quote_currency": self.settings.quote_currency,
                "quote_balance": quote_balance.balance if quote_balance else 0,
                "quote_available": quote_balance.available if quote_balance else 0,
                "portfolio_value": portfolio_value,
                "current_price": current_price
            }
        except Exception as e:
            log_error("Error getting account information", e)
            return {}
    
    def _setup_risk_management(self, trading_pair: str, entry_price: float, side: str) -> None:
        """
        Set up risk management monitoring for a position.
        
        Args:
            trading_pair: The trading pair (e.g., "BTC-USD")
            entry_price: The entry price of the position
            side: "buy" or "sell"
        """
        try:
            # For crypto, we don't place actual stop loss orders, but monitor price
            # and execute market orders when thresholds are reached
            
            if side.lower() == "buy":
                # For long positions
                stop_loss_price = entry_price * (1 - self.settings.stop_loss_pct)
                take_profit_price = entry_price * (1 + self.settings.take_profit_pct)
                
                log_info(f"Setting up risk management for long position: "
                        f"Stop loss at ${stop_loss_price:.2f} (-{self.settings.stop_loss_pct*100:.1f}%), "
                        f"Take profit at ${take_profit_price:.2f} (+{self.settings.take_profit_pct*100:.1f}%)")
                
            elif side.lower() == "sell":
                # For short positions (if supported)
                stop_loss_price = entry_price * (1 + self.settings.stop_loss_pct)
                take_profit_price = entry_price * (1 - self.settings.take_profit_pct)
                
                log_info(f"Setting up risk management for short position: "
                        f"Stop loss at ${stop_loss_price:.2f} (+{self.settings.stop_loss_pct*100:.1f}%), "
                        f"Take profit at ${take_profit_price:.2f} (-{self.settings.take_profit_pct*100:.1f}%)")
            
        except Exception as e:
            log_error(f"Error setting up risk management for {trading_pair}", e)
            
    def check_risk_management_triggers(self) -> bool:
        """
        Check if current price has triggered any stop loss or take profit levels.
        
        Returns:
            bool: True if a risk management action was taken
        """
        try:
            trading_pair = self.settings.trading_pair
            base_currency = self.settings.base_currency
            
            # Get current price
            current_price = self.data_fetcher.get_latest_price(trading_pair)
            if current_price <= 0:
                return False
                
            # Get position summary
            position_summary = self.position_manager.get_position_summary(base_currency, current_price)
            
            if not position_summary.get("has_position", False):
                return False
                
            # Get position details
            position_qty = position_summary.get("balance", 0.0)
            avg_entry_price = position_summary.get("avg_entry_price", 0.0)
            
            if position_qty <= 0 or avg_entry_price <= 0:
                return False
                
            # Calculate price change percentage
            price_change_pct = (current_price - avg_entry_price) / avg_entry_price
            
            # Check for stop loss trigger (loss exceeds stop loss percentage)
            if price_change_pct < -self.settings.stop_loss_pct:
                log_warning(f"Stop loss triggered for {trading_pair} at ${current_price:.2f} "
                          f"(Entry: ${avg_entry_price:.2f}, Loss: {price_change_pct*100:.2f}%)")
                
                # Execute sell order to close position
                self._execute_emergency_sell(trading_pair, position_qty, current_price, "stop_loss")
                return True
                
            # Check for take profit trigger (gain exceeds take profit percentage)
            elif price_change_pct > self.settings.take_profit_pct:
                log_info(f"Take profit triggered for {trading_pair} at ${current_price:.2f} "
                       f"(Entry: ${avg_entry_price:.2f}, Gain: {price_change_pct*100:.2f}%)")
                
                # Execute sell order to close position
                self._execute_emergency_sell(trading_pair, position_qty, current_price, "take_profit")
                return True
                
            return False
            
        except Exception as e:
            log_error(f"Error checking risk management triggers", e)
            return False
            
    def _execute_emergency_sell(self, trading_pair: str, quantity: float, 
                              current_price: float, reason: str) -> Optional[CryptoTradeResult]:
        """
        Execute an emergency sell order for risk management.
        
        Args:
            trading_pair: The trading pair (e.g., "BTC-USD")
            quantity: Quantity to sell
            current_price: Current market price
            reason: Reason for the emergency sell (stop_loss or take_profit)
            
        Returns:
            CryptoTradeResult if successful, None otherwise
        """
        try:
            log_info(f"Executing emergency sell ({reason}) for {quantity} {self.settings.base_currency} at ${current_price:.2f}")
            
            # Place market sell order
            result = self.order_manager.place_market_order(
                product_id=trading_pair,
                side="sell",
                size=quantity
            )
            
            if not result:
                return None
                
            # Update position tracking (negative amount for sell)
            self.position_manager.track_crypto_position(
                currency=self.settings.base_currency,
                amount=-quantity,
                price=current_price,
                fees=result.fees
            )
            
            log_info(f"Emergency sell order executed: {quantity} {self.settings.base_currency} at ${current_price:.2f}")
            return result
            
        except Exception as e:
            log_error(f"Error executing emergency sell order: {str(e)}")
            return None
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive portfolio summary.
        
        Returns:
            Dict containing portfolio summary
        """
        try:
            # Get current prices for all currencies
            current_price = self.data_fetcher.get_latest_price(self.settings.trading_pair)
            
            # Create price dictionary for portfolio summary
            market_prices = {
                self.settings.base_currency: current_price,
                self.settings.quote_currency: 1.0  # USD is always 1.0
            }
            
            # Get portfolio summary
            return self.position_manager.get_portfolio_summary(market_prices)
            
        except Exception as e:
            log_error(f"Error getting portfolio summary: {str(e)}")
            return {}
    
    def close_all_positions(self) -> bool:
        """
        Close all open positions.
        
        Returns:
            bool: True if all positions were closed successfully
        """
        try:
            # Get base currency balance
            balance = self.position_manager.get_crypto_balance(self.settings.base_currency)
            
            if not balance or balance.available <= 0:
                log_info(f"No positions to close for {self.settings.base_currency}")
                return True
            
            # Get current price
            current_price = self.data_fetcher.get_latest_price(self.settings.trading_pair)
            if current_price <= 0:
                log_error("Could not get current price for closing positions")
                return False
            
            # Place sell order for entire balance
            result = self.order_manager.place_market_order(
                product_id=self.settings.trading_pair,
                side="sell",
                size=balance.available
            )
            
            if not result:
                return False
            
            # Update position tracking
            self.position_manager.track_crypto_position(
                currency=self.settings.base_currency,
                amount=-balance.available,
                price=current_price,
                fees=result.fees
            )
            
            log_info(f"Closed all positions: {balance.available} {self.settings.base_currency} at ${current_price:.2f}")
            return True
            
        except Exception as e:
            log_error(f"Error closing all positions: {str(e)}")
            return False
    
    def shutdown(self) -> None:
        """
        Clean shutdown of the trader.
        Close WebSocket connections and perform cleanup.
        """
        try:
            # Unsubscribe from WebSocket
            self.data_fetcher.unsubscribe_from_websocket()
            log_info("CoinbaseTrader shutdown complete")
        except Exception as e:
            log_error(f"Error during trader shutdown: {str(e)}")