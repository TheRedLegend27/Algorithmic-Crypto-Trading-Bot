"""
Crypto-specific risk management and monitoring for Coinbase integration.

This module implements risk management features for cryptocurrency trading,
including position size limits, real-time P&L monitoring, volatility-based
risk adjustments, and alerting for large position changes and losses.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
import json
import math
import statistics
from enum import Enum

from bot.crypto_position_manager import CryptoPositionManager
from bot.coinbase_client import CoinbaseClient
from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.utils import log_error, log_warning, log_info


class AlertLevel(Enum):
    """Alert severity levels for risk monitoring."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class RiskAlert:
    """Data class for risk alerts."""
    timestamp: datetime
    level: AlertLevel
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


@dataclass
class CryptoRiskSettings:
    """Configuration settings for crypto risk management."""
    # Position size limits
    max_position_size_usd: float = 1000.0  # Maximum position size in USD
    max_position_size_pct: float = 0.10  # Maximum position as % of portfolio
    max_single_order_usd: float = 500.0  # Maximum single order size in USD
    
    # Loss limits
    max_daily_loss_usd: float = 100.0  # Maximum daily loss in USD
    max_daily_loss_pct: float = 0.05  # Maximum daily loss as % of portfolio
    max_drawdown_pct: float = 0.15  # Maximum drawdown before stopping trading
    
    # Volatility settings
    high_volatility_threshold: float = 0.05  # 5% price change in 1 hour
    extreme_volatility_threshold: float = 0.10  # 10% price change in 1 hour
    volatility_lookback_hours: int = 24  # Hours to look back for volatility calculation
    volatility_position_reduction: float = 0.5  # Reduce position by 50% in high volatility
    
    # Alert thresholds
    large_position_change_pct: float = 0.20  # Alert on 20% position change
    large_loss_pct: float = 0.10  # Alert on 10% loss
    large_profit_pct: float = 0.20  # Alert on 20% profit
    
    # Trading limits
    max_open_positions: int = 5  # Maximum number of open positions
    max_trades_per_day: int = 20  # Maximum trades per day
    max_trade_frequency: int = 5  # Minimum minutes between trades
    
    # Circuit breakers
    enable_circuit_breakers: bool = True  # Enable automatic trading pauses
    market_drop_circuit_breaker_pct: float = 0.10  # Pause on 10% market drop
    consecutive_losses_limit: int = 3  # Pause after 3 consecutive losses


class CryptoRiskManager:
    """
    Manages risk for cryptocurrency trading operations.
    
    This class provides position size limits, real-time P&L monitoring,
    volatility-based risk adjustments, and alerting for large position
    changes and losses.
    """
    
    def __init__(self, 
                 position_manager: CryptoPositionManager,
                 data_fetcher: CoinbaseDataFetcher,
                 client: CoinbaseClient,
                 risk_settings: Optional[CryptoRiskSettings] = None,
                 alert_callback: Optional[Callable[[RiskAlert], None]] = None):
        """
        Initialize the crypto risk manager.
        
        Args:
            position_manager: CryptoPositionManager instance for position tracking
            data_fetcher: CoinbaseDataFetcher for market data
            client: CoinbaseClient for API access
            risk_settings: Risk management configuration settings
            alert_callback: Optional callback function for alerts
        """
        self.position_manager = position_manager
        self.data_fetcher = data_fetcher
        self.client = client
        self.settings = risk_settings or CryptoRiskSettings()
        self.alert_callback = alert_callback
        self.logger = logging.getLogger(__name__)
        
        # Risk monitoring state
        self.alerts: List[RiskAlert] = []
        self.trading_paused = False
        self.trading_pause_reason = ""
        self.daily_pnl = 0.0
        self.daily_trades_count = 0
        self.consecutive_losses = 0
        self.last_trade_time = datetime.min
        self.volatility_cache: Dict[str, float] = {}
        self.volatility_cache_time: Dict[str, datetime] = {}
        self.volatility_cache_ttl = timedelta(minutes=15)  # Cache volatility for 15 minutes
        
        # Portfolio metrics
        self.starting_portfolio_value = 0.0
        self.high_water_mark = 0.0
        self.current_drawdown = 0.0
        
        # Initialize portfolio value
        self._initialize_portfolio_metrics()
        
        self.logger.info("CryptoRiskManager initialized")
    
    def _initialize_portfolio_metrics(self) -> None:
        """Initialize portfolio metrics for tracking performance."""
        try:
            # Get current portfolio value
            portfolio = self._get_portfolio_value()
            self.starting_portfolio_value = portfolio
            self.high_water_mark = portfolio
            self.logger.info(f"Initial portfolio value: ${portfolio:.2f}")
        except Exception as e:
            self.logger.error(f"Error initializing portfolio metrics: {str(e)}")
            self.starting_portfolio_value = 0.0
            self.high_water_mark = 0.0
    
    def _get_portfolio_value(self) -> float:
        """
        Get the current portfolio value in USD.
        
        Returns:
            float: Total portfolio value in USD
        """
        try:
            # Get current prices for all currencies
            balances = self.position_manager.get_all_balances()
            
            if not balances:
                return 0.0
            
            # Fetch prices for all currencies with non-zero balances
            prices = {}
            for currency, balance in balances.items():
                if balance.balance > 0:
                    if currency == "USD":
                        prices[currency] = 1.0
                    else:
                        try:
                            # Try to get price for currency-USD pair
                            ticker = self.data_fetcher.get_latest_price(f"{currency}-USD")
                            prices[currency] = ticker
                        except Exception:
                            # If failed, skip this currency
                            self.logger.warning(f"Could not get price for {currency}")
            
            # Calculate total portfolio value
            total_value = 0.0
            for currency, balance in balances.items():
                if currency in prices and balance.balance > 0:
                    total_value += balance.balance * prices[currency]
            
            return total_value
        except Exception as e:
            self.logger.error(f"Error calculating portfolio value: {str(e)}")
            return 0.0
    
    def validate_position_size(self, currency: str, size: float, price: float) -> Tuple[bool, float, str]:
        """
        Validate if a position size is within risk limits.
        
        Args:
            currency: Currency code (e.g., 'BTC')
            size: Position size in base currency
            price: Current price in USD
            
        Returns:
            Tuple[bool, float, str]: (Is valid, Adjusted size, Reason if invalid)
        """
        # Calculate position value in USD
        position_value_usd = size * price
        
        # Get current portfolio value
        portfolio_value = self._get_portfolio_value()
        
        # Check if trading is paused
        if self.trading_paused:
            return False, 0.0, f"Trading is paused: {self.trading_pause_reason}"
        
        # Check absolute position size limit
        if position_value_usd > self.settings.max_single_order_usd:
            adjusted_size = self.settings.max_single_order_usd / price
            reason = f"Position size ${position_value_usd:.2f} exceeds max single order ${self.settings.max_single_order_usd:.2f}"
            return False, adjusted_size, reason
        
        # Check position size as percentage of portfolio
        if portfolio_value > 0:
            position_pct = position_value_usd / portfolio_value
            if position_pct > self.settings.max_position_size_pct:
                adjusted_size = (self.settings.max_position_size_pct * portfolio_value) / price
                reason = f"Position size {position_pct:.1%} exceeds max {self.settings.max_position_size_pct:.1%} of portfolio"
                return False, adjusted_size, reason
        
        # Check if adding this position would exceed max open positions
        current_positions = self._count_open_positions()
        # Check if we already have a position in this currency
        try:
            balance = self.position_manager.get_crypto_balance(currency)
            has_position = balance is not None and getattr(balance, 'balance', 0) > 0
        except (AttributeError, TypeError):
            has_position = False
                      
        if current_positions >= self.settings.max_open_positions and not has_position:
            reason = f"Max open positions limit reached ({self.settings.max_open_positions})"
            return False, 0.0, reason
        
        # Check daily trade count
        if self.daily_trades_count >= self.settings.max_trades_per_day:
            reason = f"Max daily trades limit reached ({self.settings.max_trades_per_day})"
            return False, 0.0, reason
        
        # Check trade frequency
        time_since_last_trade = datetime.now() - self.last_trade_time
        if time_since_last_trade.total_seconds() < self.settings.max_trade_frequency * 60:
            reason = f"Trade frequency limit: wait {self.settings.max_trade_frequency} minutes between trades"
            return False, 0.0, reason
        
        # Check market volatility and adjust position size if needed
        volatility = self.get_market_volatility(f"{currency}-USD")
        if volatility > self.settings.extreme_volatility_threshold:
            # Extreme volatility - reject trade
            reason = f"Extreme market volatility detected ({volatility:.1%})"
            return False, 0.0, reason
        elif volatility > self.settings.high_volatility_threshold:
            # High volatility - reduce position size
            adjusted_size = size * (1 - self.settings.volatility_position_reduction)
            self.logger.warning(
                f"High volatility ({volatility:.1%}) detected for {currency}. "
                f"Reducing position size by {self.settings.volatility_position_reduction:.0%}"
            )
            return True, adjusted_size, "Position size reduced due to high volatility"
        
        # All checks passed
        return True, size, "Position size within risk limits"
    
    def get_market_volatility(self, symbol: str) -> float:
        """
        Calculate market volatility for a trading pair.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USD')
            
        Returns:
            float: Volatility as a decimal (e.g., 0.05 for 5%)
        """
        # Check cache first
        now = datetime.now()
        if symbol in self.volatility_cache and \
           now - self.volatility_cache_time.get(symbol, datetime.min) < self.volatility_cache_ttl:
            return self.volatility_cache[symbol]
        
        try:
            # Get hourly candles for the lookback period
            hours = self.settings.volatility_lookback_hours
            candles = self.data_fetcher.fetch_crypto_ohlcv(
                symbol=symbol,
                timeframe="1h",
                limit=hours
            )
            
            if candles.empty or len(candles) < 2:
                return 0.0
            
            # Calculate returns
            returns = []
            for i in range(1, len(candles)):
                prev_close = candles.iloc[i-1]['close']
                curr_close = candles.iloc[i]['close']
                if prev_close > 0:
                    returns.append((curr_close - prev_close) / prev_close)
            
            if not returns:
                return 0.0
            
            # Calculate volatility as standard deviation of returns
            volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
            
            # Annualize volatility (multiply by sqrt of number of periods in a year)
            # For hourly data: sqrt(24 * 365) ≈ 93.8
            annualized_volatility = volatility * math.sqrt(24 * 365)
            
            # Convert to a daily volatility estimate
            daily_volatility = annualized_volatility / math.sqrt(365)
            
            # Cache the result
            self.volatility_cache[symbol] = daily_volatility
            self.volatility_cache_time[symbol] = now
            
            return daily_volatility
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility for {symbol}: {str(e)}")
            return 0.0
    
    def update_portfolio_metrics(self) -> Dict[str, Any]:
        """
        Update portfolio metrics and check for risk threshold breaches.
        
        Returns:
            Dict: Updated portfolio metrics
        """
        try:
            # Get current portfolio value
            current_value = self._get_portfolio_value()
            
            # Update high water mark
            if current_value > self.high_water_mark:
                self.high_water_mark = current_value
            
            # Calculate current drawdown
            if self.high_water_mark > 0:
                self.current_drawdown = (self.high_water_mark - current_value) / self.high_water_mark
            
            # Calculate daily P&L
            self.daily_pnl = current_value - self.starting_portfolio_value
            daily_pnl_pct = self.daily_pnl / self.starting_portfolio_value if self.starting_portfolio_value > 0 else 0
            
            # Check for drawdown circuit breaker
            if self.settings.enable_circuit_breakers and \
               self.current_drawdown > self.settings.max_drawdown_pct:
                self._pause_trading(
                    f"Max drawdown exceeded: {self.current_drawdown:.1%} > {self.settings.max_drawdown_pct:.1%}"
                )
            
            # Check for daily loss circuit breaker
            if self.settings.enable_circuit_breakers and \
               self.daily_pnl < 0 and abs(self.daily_pnl) > self.settings.max_daily_loss_usd:
                self._pause_trading(
                    f"Max daily loss exceeded: ${abs(self.daily_pnl):.2f} > ${self.settings.max_daily_loss_usd:.2f}"
                )
            
            # Check for daily loss percentage circuit breaker
            if self.settings.enable_circuit_breakers and \
               daily_pnl_pct < 0 and abs(daily_pnl_pct) > self.settings.max_daily_loss_pct:
                self._pause_trading(
                    f"Max daily loss % exceeded: {abs(daily_pnl_pct):.1%} > {self.settings.max_daily_loss_pct:.1%}"
                )
            
            # Return current metrics
            return {
                "timestamp": datetime.now(),
                "portfolio_value": current_value,
                "starting_value": self.starting_portfolio_value,
                "high_water_mark": self.high_water_mark,
                "current_drawdown": self.current_drawdown,
                "daily_pnl": self.daily_pnl,
                "daily_pnl_pct": daily_pnl_pct,
                "daily_trades_count": self.daily_trades_count,
                "trading_paused": self.trading_paused,
                "trading_pause_reason": self.trading_pause_reason if self.trading_paused else "",
                "consecutive_losses": self.consecutive_losses
            }
            
        except Exception as e:
            self.logger.error(f"Error updating portfolio metrics: {str(e)}")
            return {
                "timestamp": datetime.now(),
                "error": str(e)
            }
    
    def _pause_trading(self, reason: str) -> None:
        """
        Pause trading due to risk threshold breach.
        
        Args:
            reason: Reason for pausing trading
        """
        if not self.trading_paused:
            self.trading_paused = True
            self.trading_pause_reason = reason
            self.logger.warning(f"Trading paused: {reason}")
            
            # Create critical alert
            self.create_alert(
                level=AlertLevel.CRITICAL,
                message=f"Trading automatically paused: {reason}",
                data={"reason": reason}
            )
    
    def resume_trading(self) -> bool:
        """
        Resume trading after a pause.
        
        Returns:
            bool: True if trading was resumed, False if it was already active
        """
        if self.trading_paused:
            self.trading_paused = False
            self.trading_pause_reason = ""
            self.logger.info("Trading resumed")
            
            # Create info alert
            self.create_alert(
                level=AlertLevel.INFO,
                message="Trading resumed",
                data={}
            )
            return True
        return False
    
    def monitor_position_change(self, currency: str, old_position: float, 
                              new_position: float, price: float) -> None:
        """
        Monitor position changes and create alerts for large changes.
        
        Args:
            currency: Currency code
            old_position: Previous position size
            new_position: New position size
            price: Current price in USD
        """
        if old_position == 0:
            # New position opened
            position_value = new_position * price
            self.logger.info(f"New {currency} position opened: {new_position} (${position_value:.2f})")
            return
        
        # Calculate position change
        position_change = new_position - old_position
        position_change_pct = position_change / old_position if old_position != 0 else 0
        position_value_change = position_change * price
        
        # Check for large position change
        if abs(position_change_pct) >= self.settings.large_position_change_pct:
            message = (
                f"Large {currency} position change: {position_change_pct:.1%} "
                f"({position_change} {currency}, ${position_value_change:.2f})"
            )
            
            # Create alert
            self.create_alert(
                level=AlertLevel.WARNING,
                message=message,
                data={
                    "currency": currency,
                    "old_position": old_position,
                    "new_position": new_position,
                    "change_pct": position_change_pct,
                    "price": price,
                    "value_change": position_value_change
                }
            )
    
    def monitor_pnl_change(self, currency: str, old_pnl: float, new_pnl: float, 
                         position_value: float) -> None:
        """
        Monitor P&L changes and create alerts for large losses or gains.
        
        Args:
            currency: Currency code
            old_pnl: Previous unrealized P&L
            new_pnl: New unrealized P&L
            position_value: Current position value in USD
        """
        if position_value == 0:
            return
        
        # Calculate P&L change
        pnl_change = new_pnl - old_pnl
        pnl_change_pct = pnl_change / position_value if position_value != 0 else 0
        
        # Check for large loss
        if new_pnl < 0 and abs(new_pnl) / position_value >= self.settings.large_loss_pct:
            message = (
                f"Large {currency} loss: {new_pnl / position_value:.1%} "
                f"(${new_pnl:.2f} on ${position_value:.2f} position)"
            )
            
            # Create alert
            self.create_alert(
                level=AlertLevel.WARNING,
                message=message,
                data={
                    "currency": currency,
                    "pnl": new_pnl,
                    "position_value": position_value,
                    "pnl_pct": new_pnl / position_value
                }
            )
        
        # Check for large profit
        elif new_pnl > 0 and new_pnl / position_value >= self.settings.large_profit_pct:
            message = (
                f"Large {currency} profit: {new_pnl / position_value:.1%} "
                f"(${new_pnl:.2f} on ${position_value:.2f} position)"
            )
            
            # Create alert
            self.create_alert(
                level=AlertLevel.INFO,
                message=message,
                data={
                    "currency": currency,
                    "pnl": new_pnl,
                    "position_value": position_value,
                    "pnl_pct": new_pnl / position_value
                }
            )
    
    def track_trade_result(self, is_profitable: bool) -> None:
        """
        Track trade result for consecutive loss monitoring.
        
        Args:
            is_profitable: Whether the trade was profitable
        """
        # Update trade count
        self.daily_trades_count += 1
        self.last_trade_time = datetime.now()
        
        # Update consecutive losses
        if is_profitable:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            
            # Check for consecutive losses circuit breaker
            if self.settings.enable_circuit_breakers and \
               self.consecutive_losses >= self.settings.consecutive_losses_limit:
                self._pause_trading(
                    f"Consecutive losses limit reached: {self.consecutive_losses} losses in a row"
                )
    
    def create_alert(self, level: AlertLevel, message: str, data: Dict[str, Any]) -> None:
        """
        Create a risk alert and trigger the alert callback if configured.
        
        Args:
            level: Alert severity level
            message: Alert message
            data: Additional alert data
        """
        alert = RiskAlert(
            timestamp=datetime.now(),
            level=level,
            message=message,
            data=data
        )
        
        # Add to alerts list
        self.alerts.append(alert)
        
        # Trim alerts list if needed
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]
        
        # Log alert
        if level == AlertLevel.INFO:
            self.logger.info(message)
        elif level == AlertLevel.WARNING:
            self.logger.warning(message)
        elif level == AlertLevel.CRITICAL:
            self.logger.critical(message)
        
        # Trigger callback if configured
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {str(e)}")
    
    def get_alerts(self, level: Optional[AlertLevel] = None, 
                 limit: int = 100, include_acknowledged: bool = False) -> List[RiskAlert]:
        """
        Get recent risk alerts.
        
        Args:
            level: Filter by alert level
            limit: Maximum number of alerts to return
            include_acknowledged: Whether to include acknowledged alerts
            
        Returns:
            List[RiskAlert]: List of alerts
        """
        filtered_alerts = self.alerts
        
        # Filter by level if specified
        if level:
            filtered_alerts = [a for a in filtered_alerts if a.level == level]
        
        # Filter out acknowledged alerts if requested
        if not include_acknowledged:
            filtered_alerts = [a for a in filtered_alerts if not a.acknowledged]
        
        # Sort by timestamp (newest first) and limit
        return sorted(filtered_alerts, key=lambda a: a.timestamp, reverse=True)[:limit]
    
    def acknowledge_alert(self, alert_index: int) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_index: Index of the alert in the alerts list
            
        Returns:
            bool: True if alert was acknowledged, False otherwise
        """
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index].acknowledged = True
            return True
        return False
    
    def reset_daily_metrics(self) -> None:
        """Reset daily metrics (should be called at the start of each trading day)."""
        # Store current portfolio value as new starting value
        self.starting_portfolio_value = self._get_portfolio_value()
        self.daily_pnl = 0.0
        self.daily_trades_count = 0
        self.logger.info(f"Daily metrics reset. New starting portfolio value: ${self.starting_portfolio_value:.2f}")
    
    def _count_open_positions(self) -> int:
        """
        Count the number of open positions.
        
        Returns:
            int: Number of open positions
        """
        count = 0
        balances = self.position_manager.get_all_balances()
        
        for currency, balance in balances.items():
            # Skip USD
            if currency == "USD":
                continue
                
            # Count as open position if balance > 0
            if balance.balance > 0:
                count += 1
                
        return count
    
    def calculate_real_time_pnl(self, currency: str, current_price: float) -> Dict[str, Any]:
        """
        Calculate real-time P&L for a cryptocurrency position.
        
        Args:
            currency: Currency code
            current_price: Current price in USD
            
        Returns:
            Dict: P&L metrics
        """
        # Get position summary
        position_summary = self.position_manager.get_position_summary(currency, current_price)
        
        # Calculate additional risk metrics
        position_value = position_summary.get("market_value_usd", 0.0)
        unrealized_pnl = position_summary.get("unrealized_pnl", 0.0)
        realized_pnl = position_summary.get("realized_pnl", 0.0)
        cost_basis = position_summary.get("cost_basis", 0.0)
        
        # Calculate P&L percentage
        pnl_pct = position_summary.get("pnl_percentage", 0.0) / 100.0  # Convert from percentage to decimal
        
        # Calculate risk metrics
        portfolio_value = self._get_portfolio_value()
        position_pct_of_portfolio = position_value / portfolio_value if portfolio_value > 0 else 0
        
        # Get volatility
        volatility = self.get_market_volatility(f"{currency}-USD")
        
        # Calculate value at risk (VaR) - simple approximation
        # Using 1.65 for 95% confidence level
        daily_var_95 = position_value * volatility * 1.65
        
        # Return comprehensive P&L and risk metrics
        return {
            "timestamp": datetime.now(),
            "currency": currency,
            "current_price": current_price,
            "position_size": position_summary.get("balance", 0.0),
            "position_value_usd": position_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl": unrealized_pnl + realized_pnl,
            "pnl_percentage": pnl_pct,
            "cost_basis": cost_basis,
            "position_pct_of_portfolio": position_pct_of_portfolio,
            "volatility": volatility,
            "daily_value_at_risk_95": daily_var_95,
            "risk_level": self._calculate_risk_level(position_pct_of_portfolio, pnl_pct, volatility)
        }
    
    def _calculate_risk_level(self, position_pct: float, pnl_pct: float, volatility: float) -> str:
        """
        Calculate overall risk level based on position size, P&L, and volatility.
        
        Args:
            position_pct: Position as percentage of portfolio
            pnl_pct: P&L as percentage
            volatility: Market volatility
            
        Returns:
            str: Risk level ("low", "medium", "high", "extreme")
        """
        # Score each component from 0-3
        position_score = 0
        if position_pct > 0.25:
            position_score = 3
        elif position_pct > 0.15:
            position_score = 2
        elif position_pct > 0.05:
            position_score = 1
        
        pnl_score = 0
        if pnl_pct < -0.10:
            pnl_score = 3
        elif pnl_pct < -0.05:
            pnl_score = 2
        elif pnl_pct < -0.02:
            pnl_score = 1
        
        volatility_score = 0
        if volatility > self.settings.extreme_volatility_threshold:
            volatility_score = 3
        elif volatility > self.settings.high_volatility_threshold:
            volatility_score = 2
        elif volatility > self.settings.high_volatility_threshold / 2:
            volatility_score = 1
        
        # Calculate total score
        total_score = position_score + pnl_score + volatility_score
        
        # Map score to risk level
        if total_score >= 7:
            return "extreme"
        elif total_score >= 5:
            return "high"
        elif total_score >= 3:
            return "medium"
        else:
            return "low"
    
    def export_risk_data(self, file_path: str) -> bool:
        """
        Export risk management data to a JSON file.
        
        Args:
            file_path: Path to save the JSON file
            
        Returns:
            bool: True if successful
        """
        try:
            # Prepare data for export
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "portfolio_metrics": {
                    "portfolio_value": self._get_portfolio_value(),
                    "starting_value": self.starting_portfolio_value,
                    "high_water_mark": self.high_water_mark,
                    "current_drawdown": self.current_drawdown,
                    "daily_pnl": self.daily_pnl,
                    "daily_trades_count": self.daily_trades_count,
                    "consecutive_losses": self.consecutive_losses
                },
                "risk_settings": {
                    attr: getattr(self.settings, attr)
                    for attr in dir(self.settings)
                    if not attr.startswith('_') and not callable(getattr(self.settings, attr))
                },
                "trading_status": {
                    "trading_paused": self.trading_paused,
                    "trading_pause_reason": self.trading_pause_reason
                },
                "alerts": [
                    {
                        "timestamp": alert.timestamp.isoformat(),
                        "level": alert.level.value,
                        "message": alert.message,
                        "acknowledged": alert.acknowledged
                    }
                    for alert in self.alerts[-100:]  # Export last 100 alerts
                ]
            }
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(f"Risk data exported to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting risk data: {str(e)}")
            return False