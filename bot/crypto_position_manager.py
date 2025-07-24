"""
Crypto-specific position and balance management for Coinbase integration.

This module implements cryptocurrency position tracking, balance management, and portfolio
calculations for the Coinbase Advanced Trade API integration. It provides real-time
position tracking, USD value calculations, and portfolio summary functionality.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import logging
import json

from bot.coinbase_client import CoinbaseClient


@dataclass
class CryptoBalance:
    """
    Data class for cryptocurrency balance information.
    
    Attributes:
        currency: Currency code (e.g., 'BTC', 'ETH')
        balance: Total balance amount
        available: Available balance for trading
        hold: Amount on hold (in orders)
        profile_id: Coinbase profile ID
        trading_enabled: Whether trading is enabled for this currency
    """
    currency: str
    balance: float
    available: float
    hold: float
    profile_id: str = ""
    trading_enabled: bool = True


@dataclass
class CryptoPositionEntry:
    """
    Individual position entry for tracking multiple entries into a cryptocurrency position.
    
    Attributes:
        quantity: Amount of cryptocurrency
        price: Price in USD at entry
        timestamp: When the entry was made
        fees: Trading fees paid
        entry_id: Unique identifier for this entry
    """
    quantity: float
    price: float
    timestamp: datetime
    fees: float = 0.0
    entry_id: str = field(default_factory=lambda: str(int(time.time() * 1000000)))


@dataclass
class CryptoTradeRecord:
    """
    Record of a completed cryptocurrency trade for P&L tracking.
    
    Attributes:
        currency: Currency code (e.g., 'BTC', 'ETH')
        quantity: Amount traded
        entry_price: Entry price in USD
        exit_price: Exit price in USD
        entry_time: When position was entered
        exit_time: When position was exited
        realized_pnl: Realized profit/loss in USD
        fees: Total fees paid
        holding_period: How long the position was held
    """
    currency: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    realized_pnl: float
    fees: float
    holding_period: timedelta


class CryptoPnLCalculator:
    """
    Handles profit and loss calculations for cryptocurrency positions.
    Provides real-time and realized P&L calculations with accurate cost basis tracking.
    """
    
    def __init__(self):
        """Initialize the P&L calculator."""
        self.logger = logging.getLogger(__name__)
    
    def calculate_unrealized_pnl(self, currency: str, quantity: float, 
                               avg_entry_price: float, current_price: float) -> float:
        """
        Calculate unrealized P&L for a cryptocurrency position.
        
        Args:
            currency: Currency code
            quantity: Position quantity
            avg_entry_price: Average entry price
            current_price: Current market price
            
        Returns:
            float: Unrealized profit/loss in USD
        """
        if quantity == 0:
            return 0.0
        
        return quantity * (current_price - avg_entry_price)
    
    def calculate_realized_pnl(self, entry_price: float, exit_price: float, 
                             quantity: float, fees: float = 0.0) -> float:
        """
        Calculate realized P&L for a cryptocurrency trade.
        
        Args:
            entry_price: Entry price in USD
            exit_price: Exit price in USD
            quantity: Amount of cryptocurrency
            fees: Total fees for the trade
            
        Returns:
            float: Realized profit/loss in USD
        """
        if quantity == 0:
            return 0.0
        
        # Calculate gross P&L
        gross_pnl = quantity * (exit_price - entry_price)
        
        # Subtract fees
        net_pnl = gross_pnl - fees
        
        return net_pnl
    
    def calculate_position_pnl_percentage(self, cost_basis: float, unrealized_pnl: float) -> float:
        """
        Calculate P&L percentage for a position.
        
        Args:
            cost_basis: Total cost basis of the position
            unrealized_pnl: Unrealized profit/loss
            
        Returns:
            float: P&L percentage
        """
        if cost_basis == 0:
            return 0.0
        
        return (unrealized_pnl / cost_basis) * 100


class CryptoPositionManager:
    """
    Manages cryptocurrency positions and balances for Coinbase integration.
    Provides position tracking, USD value calculations, and portfolio summaries.
    """
    
    def __init__(self, coinbase_client: CoinbaseClient):
        """
        Initialize the crypto position manager.
        
        Args:
            coinbase_client: Authenticated Coinbase client
        """
        self.client = coinbase_client
        self.balances: Dict[str, CryptoBalance] = {}
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.pnl_calculator = CryptoPnLCalculator()
        self.trade_history: List[CryptoTradeRecord] = []
        self.position_history: Dict[str, List[Dict[str, Any]]] = {}
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.daily_pnl_history: Dict[str, float] = {}
        self.high_water_mark = 0.0
        self.max_drawdown = 0.0
        
        # Position entries tracking
        self.position_entries: Dict[str, List[CryptoPositionEntry]] = {}
        
        self.logger.info("CryptoPositionManager initialized")
        
        # Initial balance fetch
        self._refresh_balances()
    
    def _refresh_balances(self) -> bool:
        """
        Refresh all cryptocurrency balances from Coinbase.
        
        Returns:
            bool: True if successful
        """
        try:
            accounts = self.client.get_accounts()
            
            # Reset balances
            self.balances = {}
            
            for account in accounts:
                currency = account.get('currency', '')
                if not currency:
                    continue
                
                self.balances[currency] = CryptoBalance(
                    currency=currency,
                    balance=float(account.get('balance', 0.0)),
                    available=float(account.get('available', 0.0)),
                    hold=float(account.get('hold', 0.0)),
                    profile_id=account.get('profile_id', ''),
                    trading_enabled=account.get('trading_enabled', True)
                )
            
            self.logger.info(f"Refreshed balances for {len(self.balances)} currencies")
            return True
            
        except Exception as e:
            self.logger.error(f"Error refreshing balances: {str(e)}")
            return False
    
    def get_crypto_balance(self, currency: str) -> Optional[CryptoBalance]:
        """
        Get balance information for a specific cryptocurrency.
        
        Args:
            currency: Currency code (e.g., 'BTC', 'ETH')
            
        Returns:
            CryptoBalance if exists, None otherwise
        """
        # Try to get from cache first
        if currency in self.balances:
            return self.balances[currency]
        
        # If not in cache, refresh balances and try again
        if self._refresh_balances() and currency in self.balances:
            return self.balances[currency]
        
        return None
    
    def get_all_balances(self) -> Dict[str, CryptoBalance]:
        """
        Get all cryptocurrency balances.
        
        Returns:
            Dictionary of currency code to CryptoBalance
        """
        # Refresh balances to ensure they're up to date
        self._refresh_balances()
        return self.balances.copy()
    
    def get_position_value_usd(self, currency: str, current_price: float) -> float:
        """
        Calculate the USD value of a cryptocurrency position.
        
        Args:
            currency: Currency code
            current_price: Current price in USD
            
        Returns:
            float: Position value in USD
        """
        balance = self.get_crypto_balance(currency)
        if not balance:
            return 0.0
        
        return balance.balance * current_price
    
    def calculate_available_balance(self, currency: str) -> float:
        """
        Get available balance for a cryptocurrency.
        
        Args:
            currency: Currency code
            
        Returns:
            float: Available balance amount
        """
        balance = self.get_crypto_balance(currency)
        if not balance:
            return 0.0
        
        return balance.available
    
    def track_crypto_position(self, currency: str, amount: float, price: float, 
                            timestamp: Optional[datetime] = None, fees: float = 0.0) -> None:
        """
        Track a cryptocurrency position change.
        
        Args:
            currency: Currency code
            amount: Amount of cryptocurrency (positive for buy, negative for sell)
            price: Price in USD
            timestamp: When the position change occurred (default: now)
            fees: Trading fees paid
        """
        if amount == 0:
            return
        
        # Use current time if timestamp not provided
        if timestamp is None:
            timestamp = datetime.now()
        
        # Initialize position entries if needed
        if currency not in self.position_entries:
            self.position_entries[currency] = []
        
        # Initialize position history if needed
        if currency not in self.position_history:
            self.position_history[currency] = []
        
        # Handle position tracking
        if amount > 0:  # Buy
            # Add new entry
            entry = CryptoPositionEntry(
                quantity=amount,
                price=price,
                timestamp=timestamp,
                fees=fees
            )
            self.position_entries[currency].append(entry)
            
        else:  # Sell (amount is negative)
            # Process FIFO (First In, First Out) for position closing
            remaining_amount = abs(amount)
            realized_pnl = 0.0
            
            while remaining_amount > 0 and self.position_entries[currency]:
                entry = self.position_entries[currency][0]
                
                # Calculate how much of this entry to close
                close_amount = min(remaining_amount, entry.quantity)
                
                # Calculate realized P&L for this portion
                trade_realized_pnl = self.pnl_calculator.calculate_realized_pnl(
                    entry_price=entry.price,
                    exit_price=price,
                    quantity=close_amount,
                    fees=fees * (close_amount / abs(amount))  # Proportional fees
                )
                realized_pnl += trade_realized_pnl
                
                # Record the trade
                self.trade_history.append(CryptoTradeRecord(
                    currency=currency,
                    quantity=close_amount,
                    entry_price=entry.price,
                    exit_price=price,
                    entry_time=entry.timestamp,
                    exit_time=timestamp,
                    realized_pnl=trade_realized_pnl,
                    fees=fees * (close_amount / abs(amount)),
                    holding_period=timestamp - entry.timestamp
                ))
                
                # Update entry or remove if fully closed
                if close_amount >= entry.quantity:
                    self.position_entries[currency].pop(0)
                    remaining_amount -= entry.quantity
                else:
                    entry.quantity -= close_amount
                    remaining_amount = 0
        
        # Update position history
        position_snapshot = self.get_position_summary(currency, price)
        self.position_history[currency].append({
            "timestamp": timestamp,
            "action": "buy" if amount > 0 else "sell",
            "amount": abs(amount),
            "price": price,
            "fees": fees,
            "position_after": position_snapshot
        })
        
        # Keep history size manageable
        if len(self.position_history[currency]) > 1000:
            self.position_history[currency] = self.position_history[currency][-1000:]
        
        self.logger.info(
            f"Tracked {currency} position change: {'Buy' if amount > 0 else 'Sell'} "
            f"{abs(amount)} @ ${price:.2f}, Fees: ${fees:.2f}"
        )
    
    def get_position_summary(self, currency: str, current_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Get comprehensive position summary for a cryptocurrency.
        
        Args:
            currency: Currency code
            current_price: Current price in USD (optional)
            
        Returns:
            Dictionary with position details
        """
        balance = self.get_crypto_balance(currency)
        
        if not balance or balance.balance == 0:
            return {
                "currency": currency,
                "balance": 0.0,
                "available": 0.0,
                "hold": 0.0,
                "market_value_usd": 0.0,
                "avg_entry_price": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "cost_basis": 0.0,
                "pnl_percentage": 0.0,
                "fees_paid": 0.0,
                "has_position": False,
                "entry_count": 0,
                "last_price": current_price or 0.0
            }
        
        # Calculate average entry price and cost basis
        total_quantity = 0.0
        total_cost = 0.0
        total_fees = 0.0
        
        for entry in self.position_entries.get(currency, []):
            total_quantity += entry.quantity
            total_cost += entry.quantity * entry.price
            total_fees += entry.fees
        
        avg_entry_price = total_cost / total_quantity if total_quantity > 0 else 0.0
        cost_basis = total_cost + total_fees
        
        # Calculate realized P&L for this currency
        realized_pnl = sum(
            trade.realized_pnl for trade in self.trade_history 
            if trade.currency == currency
        )
        
        # Calculate unrealized P&L if current price is provided
        unrealized_pnl = 0.0
        pnl_percentage = 0.0
        market_value_usd = 0.0
        
        if current_price and current_price > 0:
            # Only calculate unrealized P&L for the tracked position quantity, not the full balance
            tracked_quantity = sum(entry.quantity for entry in self.position_entries.get(currency, []))
            
            unrealized_pnl = self.pnl_calculator.calculate_unrealized_pnl(
                currency=currency,
                quantity=tracked_quantity,
                avg_entry_price=avg_entry_price,
                current_price=current_price
            )
            
            pnl_percentage = self.pnl_calculator.calculate_position_pnl_percentage(
                cost_basis=cost_basis,
                unrealized_pnl=unrealized_pnl
            )
            
            market_value_usd = balance.balance * current_price
        
        return {
            "currency": currency,
            "balance": balance.balance,
            "available": balance.available,
            "hold": balance.hold,
            "market_value_usd": market_value_usd,
            "avg_entry_price": avg_entry_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "cost_basis": cost_basis,
            "pnl_percentage": pnl_percentage,
            "fees_paid": total_fees,
            "has_position": balance.balance > 0,
            "entry_count": len(self.position_entries.get(currency, [])),
            "last_price": current_price or 0.0,
            "trading_enabled": balance.trading_enabled
        }
    
    def get_portfolio_summary(self, market_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Get comprehensive portfolio summary across all cryptocurrencies.
        
        Args:
            market_prices: Dictionary of currency code to current price in USD
            
        Returns:
            Dictionary with portfolio summary
        """
        # Refresh balances to ensure they're up to date
        self._refresh_balances()
        
        total_market_value_usd = 0.0
        total_cost_basis = 0.0
        total_unrealized_pnl = 0.0
        total_realized_pnl = 0.0
        total_fees_paid = 0.0
        positions_data = []
        
        # Calculate portfolio metrics
        for currency, balance in self.balances.items():
            if balance.balance <= 0:
                continue
                
            current_price = market_prices.get(currency, 0.0)
            if current_price <= 0:
                continue
                
            # Only include currencies that have position entries
            if currency in self.position_entries and self.position_entries[currency]:
                position_summary = self.get_position_summary(currency, current_price)
                
                total_market_value_usd += position_summary["market_value_usd"]
                total_cost_basis += position_summary["cost_basis"]
                total_unrealized_pnl += position_summary["unrealized_pnl"]
                total_realized_pnl += position_summary["realized_pnl"]
                total_fees_paid += position_summary["fees_paid"]
                
                positions_data.append(position_summary)
        
        # Calculate total P&L percentage
        total_pnl_percentage = 0.0
        if total_cost_basis > 0:
            total_pnl_percentage = (total_unrealized_pnl / total_cost_basis) * 100
        
        # Calculate daily P&L
        today = datetime.now().date().isoformat()
        previous_value = self.daily_pnl_history.get(today, total_market_value_usd)
        daily_pnl = total_market_value_usd - previous_value
        
        # Update daily P&L history
        self.daily_pnl_history[today] = total_market_value_usd
        
        # Update performance tracking
        self._update_performance_metrics(total_market_value_usd)
        
        return {
            "timestamp": datetime.now(),
            "total_market_value_usd": total_market_value_usd,
            "total_cost_basis": total_cost_basis,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "total_pnl": total_unrealized_pnl + total_realized_pnl,
            "total_pnl_percentage": total_pnl_percentage,
            "daily_pnl": daily_pnl,
            "total_fees_paid": total_fees_paid,
            "position_count": len(positions_data),
            "positions": positions_data,
            "high_water_mark": self.high_water_mark,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown * 100
        }
    
    def _update_performance_metrics(self, current_portfolio_value: float) -> None:
        """
        Update performance tracking metrics.
        
        Args:
            current_portfolio_value: Current total portfolio value in USD
        """
        # Update high water mark
        if current_portfolio_value > self.high_water_mark:
            self.high_water_mark = current_portfolio_value
        
        # Calculate current drawdown
        if self.high_water_mark > 0:
            current_drawdown = (self.high_water_mark - current_portfolio_value) / self.high_water_mark
            
            # Update max drawdown
            if current_drawdown > self.max_drawdown:
                self.max_drawdown = current_drawdown
    
    def get_position_history(self, currency: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get position history for a cryptocurrency.
        
        Args:
            currency: Currency code
            limit: Maximum number of history entries to return
            
        Returns:
            List of position history entries
        """
        history = self.position_history.get(currency, [])
        return history[-limit:] if history else []
    
    def export_position_data(self, file_path: str) -> bool:
        """
        Export position data to a JSON file.
        
        Args:
            file_path: Path to save the JSON file
            
        Returns:
            bool: True if successful
        """
        try:
            # Prepare data for export
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "balances": {
                    currency: {
                        "balance": balance.balance,
                        "available": balance.available,
                        "hold": balance.hold,
                        "trading_enabled": balance.trading_enabled
                    }
                    for currency, balance in self.balances.items()
                },
                "position_entries": {
                    currency: [
                        {
                            "quantity": entry.quantity,
                            "price": entry.price,
                            "timestamp": entry.timestamp.isoformat(),
                            "fees": entry.fees,
                            "entry_id": entry.entry_id
                        }
                        for entry in entries
                    ]
                    for currency, entries in self.position_entries.items()
                },
                "trade_history": [
                    {
                        "currency": trade.currency,
                        "quantity": trade.quantity,
                        "entry_price": trade.entry_price,
                        "exit_price": trade.exit_price,
                        "entry_time": trade.entry_time.isoformat(),
                        "exit_time": trade.exit_time.isoformat(),
                        "realized_pnl": trade.realized_pnl,
                        "fees": trade.fees,
                        "holding_period_seconds": trade.holding_period.total_seconds()
                    }
                    for trade in self.trade_history
                ]
            }
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(f"Position data exported to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting position data: {str(e)}")
            return False
    
    def import_position_data(self, file_path: str) -> bool:
        """
        Import position data from a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            bool: True if successful
        """
        try:
            # Read from file
            with open(file_path, 'r') as f:
                import_data = json.load(f)
            
            # Import balances (but don't override actual balances from Coinbase)
            # Just log the differences
            for currency, balance_data in import_data.get("balances", {}).items():
                if currency in self.balances:
                    current_balance = self.balances[currency].balance
                    imported_balance = balance_data.get("balance", 0.0)
                    
                    if abs(current_balance - imported_balance) > 0.0001:
                        self.logger.warning(
                            f"Balance discrepancy for {currency}: "
                            f"Current {current_balance}, Imported {imported_balance}"
                        )
            
            # Import position entries
            for currency, entries_data in import_data.get("position_entries", {}).items():
                self.position_entries[currency] = []
                
                for entry_data in entries_data:
                    entry = CryptoPositionEntry(
                        quantity=entry_data.get("quantity", 0.0),
                        price=entry_data.get("price", 0.0),
                        timestamp=datetime.fromisoformat(entry_data.get("timestamp")),
                        fees=entry_data.get("fees", 0.0),
                        entry_id=entry_data.get("entry_id", str(int(time.time() * 1000000)))
                    )
                    self.position_entries[currency].append(entry)
            
            # Import trade history
            self.trade_history = []
            for trade_data in import_data.get("trade_history", []):
                trade = CryptoTradeRecord(
                    currency=trade_data.get("currency", ""),
                    quantity=trade_data.get("quantity", 0.0),
                    entry_price=trade_data.get("entry_price", 0.0),
                    exit_price=trade_data.get("exit_price", 0.0),
                    entry_time=datetime.fromisoformat(trade_data.get("entry_time")),
                    exit_time=datetime.fromisoformat(trade_data.get("exit_time")),
                    realized_pnl=trade_data.get("realized_pnl", 0.0),
                    fees=trade_data.get("fees", 0.0),
                    holding_period=timedelta(seconds=trade_data.get("holding_period_seconds", 0))
                )
                self.trade_history.append(trade)
            
            self.logger.info(f"Position data imported from {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing position data: {str(e)}")
            return False