"""
Enhanced risk management system for Kraken crypto trading bot.

This module implements advanced risk management features including dynamic position sizing,
portfolio-level exposure limits, correlation analysis, drawdown protection, and emergency
stop mechanisms for multi-pair cryptocurrency trading.
"""
import logging
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd

from bot.crypto_risk_manager import CryptoRiskManager, RiskAlert, AlertLevel, CryptoRiskSettings
from bot.crypto_position_manager import CryptoPositionManager
from bot.kraken_client import KrakenClient
from bot.enhanced_data_manager import EnhancedDataManager


class RiskLevel(Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class EmergencyStopReason(Enum):
    """Reasons for emergency stop activation."""
    MAX_DRAWDOWN = "max_drawdown"
    PORTFOLIO_CORRELATION = "portfolio_correlation"
    VOLATILITY_SPIKE = "volatility_spike"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    MARGIN_CALL = "margin_call"
    SYSTEM_ERROR = "system_error"


@dataclass
class RiskAssessment:
    """Comprehensive risk assessment for a trading signal."""
    is_valid: bool
    risk_level: RiskLevel
    recommended_size: float
    max_allowed_size: float
    risk_factors: List[str]
    confidence_score: float
    warnings: List[str]
    correlation_impact: float
    volatility_adjustment: float
    portfolio_impact: float


@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics."""
    total_exposure_usd: float
    exposure_by_pair: Dict[str, float]
    correlation_matrix: Dict[Tuple[str, str], float]
    concentration_risk: float
    beta_to_market: float
    value_at_risk_95: float
    expected_shortfall: float
    max_drawdown: float
    sharpe_ratio: float
    risk_level: RiskLevel


@dataclass
class PositionSizeCalculation:
    """Result of position size calculation."""
    base_size: float
    volatility_adjusted_size: float
    correlation_adjusted_size: float
    final_size: float
    risk_per_trade: float
    confidence_multiplier: float
    adjustments_applied: List[str]


@dataclass
class EnhancedRiskSettings:
    """Enhanced risk management configuration."""
    # Base settings from CryptoRiskSettings
    base_settings: CryptoRiskSettings = field(default_factory=CryptoRiskSettings)
    
    # Dynamic position sizing
    enable_dynamic_sizing: bool = True
    base_risk_per_trade: float = 0.02  # 2% of portfolio per trade
    max_risk_per_trade: float = 0.05  # 5% maximum risk per trade
    min_risk_per_trade: float = 0.005  # 0.5% minimum risk per trade
    volatility_lookback_days: int = 30
    
    # Portfolio-level limits
    max_portfolio_exposure: float = 0.80  # 80% max portfolio exposure
    max_single_pair_exposure: float = 0.25  # 25% max exposure to single pair
    max_correlated_exposure: float = 0.40  # 40% max exposure to correlated assets
    correlation_threshold: float = 0.7  # Assets with >70% correlation are considered correlated
    
    # Drawdown protection
    max_portfolio_drawdown: float = 0.15  # 15% max portfolio drawdown
    daily_drawdown_limit: float = 0.08  # 8% max daily drawdown
    trailing_stop_activation: float = 0.10  # Activate trailing stops at 10% profit
    trailing_stop_distance: float = 0.05  # 5% trailing stop distance
    
    # Emergency stops
    enable_emergency_stops: bool = True
    volatility_spike_threshold: float = 3.0  # 3x normal volatility triggers emergency stop
    correlation_spike_threshold: float = 0.9  # >90% correlation triggers emergency stop
    consecutive_loss_limit: int = 5  # 5 consecutive losses triggers emergency stop
    
    # Risk scoring
    confidence_threshold: float = 0.6  # Minimum confidence for trade execution
    risk_score_weights: Dict[str, float] = field(default_factory=lambda: {
        'volatility': 0.3,
        'correlation': 0.2,
        'momentum': 0.2,
        'portfolio_exposure': 0.15,
        'drawdown': 0.15
    })


class EnhancedRiskManager:
    """
    Advanced risk management system with dynamic position sizing, portfolio-level
    exposure limits, correlation analysis, and emergency stop mechanisms.
    """
    
    def __init__(self,
                 position_manager: CryptoPositionManager,
                 data_manager: EnhancedDataManager,
                 kraken_client: KrakenClient,
                 trading_pairs: List[str],
                 settings: Optional[EnhancedRiskSettings] = None):
        """
        Initialize the enhanced risk manager.
        
        Args:
            position_manager: Position manager for tracking balances
            data_manager: Enhanced data manager for market data
            kraken_client: Kraken API client
            trading_pairs: List of trading pairs to monitor
            settings: Enhanced risk management settings
        """
        self.position_manager = position_manager
        self.data_manager = data_manager
        self.kraken_client = kraken_client
        self.trading_pairs = trading_pairs
        self.settings = settings or EnhancedRiskSettings()
        self.logger = logging.getLogger(__name__)
        
        # Initialize base risk manager
        self.base_risk_manager = CryptoRiskManager(
            position_manager=position_manager,
            data_fetcher=None,  # We'll use data_manager instead
            client=kraken_client,
            risk_settings=self.settings.base_settings
        )
        
        # Risk tracking state
        self.portfolio_metrics: Dict[str, Any] = {}
        self.correlation_matrix: Dict[Tuple[str, str], float] = {}
        self.volatility_cache: Dict[str, Tuple[float, datetime]] = {}
        self.emergency_stops: Dict[EmergencyStopReason, bool] = {
            reason: False for reason in EmergencyStopReason
        }
        self.risk_alerts: List[RiskAlert] = []
        
        # Performance tracking
        self.trade_history: List[Dict[str, Any]] = []
        self.drawdown_history: List[Tuple[datetime, float]] = []
        self.portfolio_value_history: List[Tuple[datetime, float]] = []
        
        self.logger.info(f"EnhancedRiskManager initialized for {len(trading_pairs)} trading pairs")
    
    def validate_trade(self, pair: str, side: str, quantity: float, 
                      price: float, signal_confidence: float) -> RiskAssessment:
        """
        Comprehensive trade validation with advanced risk assessment.
        
        Args:
            pair: Trading pair (e.g., 'BTC/USD')
            side: Trade side ('buy' or 'sell')
            quantity: Proposed quantity
            price: Current price
            signal_confidence: Confidence in trading signal (0-1)
            
        Returns:
            RiskAssessment: Comprehensive risk assessment
        """
        try:
            # Initialize assessment
            assessment = RiskAssessment(
                is_valid=False,
                risk_level=RiskLevel.HIGH,
                recommended_size=0.0,
                max_allowed_size=0.0,
                risk_factors=[],
                confidence_score=signal_confidence,
                warnings=[],
                correlation_impact=0.0,
                volatility_adjustment=1.0,
                portfolio_impact=0.0
            )
            
            # Check emergency stops
            if self._check_emergency_stops():
                assessment.risk_factors.append("emergency_stop_active")
                assessment.warnings.append("Trading halted due to emergency stop")
                return assessment
            
            # Check basic validation from base risk manager
            base_valid, adjusted_size, reason = self.base_risk_manager.validate_position_size(
                pair.split('/')[0], quantity, price
            )
            
            if not base_valid and adjusted_size == 0:
                assessment.risk_factors.append("base_validation_failed")
                assessment.warnings.append(reason)
                return assessment
            
            # Calculate dynamic position size
            position_calc = self._calculate_dynamic_position_size(
                pair, quantity, price, signal_confidence
            )
            
            # Assess portfolio impact
            portfolio_impact = self._assess_portfolio_impact(pair, position_calc.final_size, price)
            
            # Calculate correlation impact
            correlation_impact = self._calculate_correlation_impact(pair, position_calc.final_size, price)
            
            # Determine risk level
            risk_level = self._determine_risk_level(
                pair, position_calc.final_size, price, signal_confidence, 
                portfolio_impact, correlation_impact
            )
            
            # Final validation
            is_valid = (
                risk_level != RiskLevel.EXTREME and
                signal_confidence >= self.settings.confidence_threshold and
                position_calc.final_size > 0
            )
            
            # Update assessment
            assessment.is_valid = is_valid
            assessment.risk_level = risk_level
            assessment.recommended_size = position_calc.final_size
            assessment.max_allowed_size = position_calc.base_size
            assessment.correlation_impact = correlation_impact
            assessment.volatility_adjustment = position_calc.volatility_adjusted_size / position_calc.base_size
            assessment.portfolio_impact = portfolio_impact
            
            # Add risk factors and warnings
            if risk_level == RiskLevel.HIGH:
                assessment.warnings.append("High risk trade - consider reducing size")
            if correlation_impact > 0.5:
                assessment.warnings.append("High correlation with existing positions")
            if portfolio_impact > 0.3:
                assessment.warnings.append("Large portfolio impact")
            
            return assessment
            
        except Exception as e:
            self.logger.error(f"Error in trade validation: {str(e)}")
            return RiskAssessment(
                is_valid=False,
                risk_level=RiskLevel.EXTREME,
                recommended_size=0.0,
                max_allowed_size=0.0,
                risk_factors=["validation_error"],
                confidence_score=0.0,
                warnings=[f"Validation error: {str(e)}"],
                correlation_impact=0.0,
                volatility_adjustment=0.0,
                portfolio_impact=0.0
            )
    
    def calculate_position_size(self, pair: str, signal_confidence: float, 
                              current_price: float, account_balance: float) -> PositionSizeCalculation:
        """
        Calculate optimal position size using dynamic sizing algorithm.
        
        Args:
            pair: Trading pair
            signal_confidence: Confidence in signal (0-1)
            current_price: Current market price
            account_balance: Available account balance
            
        Returns:
            PositionSizeCalculation: Detailed position size calculation
        """
        return self._calculate_dynamic_position_size(
            pair, account_balance / current_price, current_price, signal_confidence
        )
    
    def check_portfolio_risk(self) -> PortfolioRisk:
        """
        Comprehensive portfolio risk assessment.
        
        Returns:
            PortfolioRisk: Portfolio risk metrics
        """
        try:
            # Get current positions
            positions = self._get_current_positions()
            
            # Calculate total exposure
            total_exposure = sum(pos['value_usd'] for pos in positions.values())
            
            # Calculate exposure by pair
            exposure_by_pair = {pair: pos['value_usd'] for pair, pos in positions.items()}
            
            # Update correlation matrix
            self._update_correlation_matrix()
            
            # Calculate concentration risk (Herfindahl index)
            if total_exposure > 0:
                concentration_risk = sum(
                    (exposure / total_exposure) ** 2 
                    for exposure in exposure_by_pair.values()
                )
            else:
                concentration_risk = 0.0
            
            # Calculate portfolio beta (simplified - relative to BTC if available)
            beta_to_market = self._calculate_portfolio_beta(positions)
            
            # Calculate Value at Risk (95% confidence)
            var_95 = self._calculate_portfolio_var(positions, confidence=0.95)
            
            # Calculate Expected Shortfall
            expected_shortfall = self._calculate_expected_shortfall(positions)
            
            # Get current drawdown
            max_drawdown = self._calculate_current_drawdown()
            
            # Calculate Sharpe ratio
            sharpe_ratio = self._calculate_portfolio_sharpe_ratio()
            
            # Determine overall risk level
            risk_level = self._determine_portfolio_risk_level(
                concentration_risk, max_drawdown, var_95, total_exposure
            )
            
            return PortfolioRisk(
                total_exposure_usd=total_exposure,
                exposure_by_pair=exposure_by_pair,
                correlation_matrix=self.correlation_matrix,
                concentration_risk=concentration_risk,
                beta_to_market=beta_to_market,
                value_at_risk_95=var_95,
                expected_shortfall=expected_shortfall,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                risk_level=risk_level
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {str(e)}")
            return PortfolioRisk(
                total_exposure_usd=0.0,
                exposure_by_pair={},
                correlation_matrix={},
                concentration_risk=0.0,
                beta_to_market=1.0,
                value_at_risk_95=0.0,
                expected_shortfall=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                risk_level=RiskLevel.EXTREME
            )
    
    def should_emergency_stop(self) -> Tuple[bool, Optional[EmergencyStopReason]]:
        """
        Check if emergency stop should be triggered.
        
        Returns:
            Tuple[bool, Optional[EmergencyStopReason]]: (Should stop, Reason)
        """
        if not self.settings.enable_emergency_stops:
            return False, None
        
        # Check drawdown limits
        current_drawdown = self._calculate_current_drawdown()
        if current_drawdown > self.settings.max_portfolio_drawdown:
            self.emergency_stops[EmergencyStopReason.MAX_DRAWDOWN] = True
            return True, EmergencyStopReason.MAX_DRAWDOWN
        
        # Check volatility spikes
        if self._check_volatility_spike():
            self.emergency_stops[EmergencyStopReason.VOLATILITY_SPIKE] = True
            return True, EmergencyStopReason.VOLATILITY_SPIKE
        
        # Check correlation spikes
        if self._check_correlation_spike():
            self.emergency_stops[EmergencyStopReason.PORTFOLIO_CORRELATION] = True
            return True, EmergencyStopReason.PORTFOLIO_CORRELATION
        
        # Check consecutive losses
        if self.base_risk_manager.consecutive_losses >= self.settings.consecutive_loss_limit:
            self.emergency_stops[EmergencyStopReason.CONSECUTIVE_LOSSES] = True
            return True, EmergencyStopReason.CONSECUTIVE_LOSSES
        
        return False, None
    
    def adjust_for_correlation(self, pair: str, proposed_size: float, 
                             current_price: float) -> float:
        """
        Adjust position size based on correlation with existing positions.
        
        Args:
            pair: Trading pair
            proposed_size: Proposed position size
            current_price: Current price
            
        Returns:
            float: Correlation-adjusted position size
        """
        try:
            correlation_impact = self._calculate_correlation_impact(
                pair, proposed_size, current_price
            )
            
            # Reduce size based on correlation impact
            if correlation_impact > self.settings.correlation_threshold:
                reduction_factor = 1 - (correlation_impact - self.settings.correlation_threshold) / (1 - self.settings.correlation_threshold)
                adjusted_size = proposed_size * reduction_factor
                
                self.logger.info(
                    f"Reducing {pair} position size by {(1-reduction_factor)*100:.1f}% "
                    f"due to correlation impact ({correlation_impact:.2f})"
                )
                
                return adjusted_size
            
            return proposed_size
            
        except Exception as e:
            self.logger.error(f"Error adjusting for correlation: {str(e)}")
            return proposed_size * 0.5  # Conservative fallback
    
    def _calculate_dynamic_position_size(self, pair: str, base_quantity: float, 
                                       price: float, signal_confidence: float) -> PositionSizeCalculation:
        """
        Calculate dynamic position size based on multiple factors.
        
        Args:
            pair: Trading pair
            base_quantity: Base quantity to trade
            price: Current price
            signal_confidence: Signal confidence (0-1)
            
        Returns:
            PositionSizeCalculation: Detailed calculation result
        """
        try:
            # Get portfolio value
            portfolio_value = self._get_portfolio_value()
            if portfolio_value <= 0:
                return PositionSizeCalculation(
                    base_size=0.0, volatility_adjusted_size=0.0,
                    correlation_adjusted_size=0.0, final_size=0.0,
                    risk_per_trade=0.0, confidence_multiplier=0.0,
                    adjustments_applied=["zero_portfolio_value"]
                )
            
            # Calculate base size using Kelly criterion with modifications
            base_risk = self.settings.base_risk_per_trade
            max_risk = min(self.settings.max_risk_per_trade, base_risk * 2)
            min_risk = self.settings.min_risk_per_trade
            
            # Adjust risk based on confidence
            confidence_multiplier = signal_confidence ** 2  # Square for more conservative scaling
            adjusted_risk = base_risk * confidence_multiplier
            adjusted_risk = max(min_risk, min(adjusted_risk, max_risk))
            
            # Calculate base position size
            base_size = (portfolio_value * adjusted_risk) / price
            
            # Get volatility for the pair
            volatility = self._get_pair_volatility(pair)
            
            # Adjust for volatility (higher volatility = smaller position)
            volatility_multiplier = 1.0 / (1.0 + volatility * 2)  # Scale down with volatility
            volatility_adjusted_size = base_size * volatility_multiplier
            
            # Adjust for correlation
            correlation_adjusted_size = self.adjust_for_correlation(
                pair, volatility_adjusted_size, price
            )
            
            # Apply final constraints
            final_size = min(correlation_adjusted_size, base_quantity)
            
            # Track adjustments
            adjustments = []
            if volatility_multiplier < 0.9:
                adjustments.append(f"volatility_reduction_{volatility_multiplier:.2f}")
            if correlation_adjusted_size < volatility_adjusted_size:
                adjustments.append("correlation_adjustment")
            if final_size < correlation_adjusted_size:
                adjustments.append("quantity_constraint")
            
            return PositionSizeCalculation(
                base_size=base_size,
                volatility_adjusted_size=volatility_adjusted_size,
                correlation_adjusted_size=correlation_adjusted_size,
                final_size=final_size,
                risk_per_trade=adjusted_risk,
                confidence_multiplier=confidence_multiplier,
                adjustments_applied=adjustments
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating dynamic position size: {str(e)}")
            return PositionSizeCalculation(
                base_size=0.0, volatility_adjusted_size=0.0,
                correlation_adjusted_size=0.0, final_size=0.0,
                risk_per_trade=0.0, confidence_multiplier=0.0,
                adjustments_applied=["calculation_error"]
            )
    
    def _get_pair_volatility(self, pair: str) -> float:
        """
        Get volatility for a trading pair with caching.
        
        Args:
            pair: Trading pair
            
        Returns:
            float: Volatility (annualized)
        """
        try:
            # Check cache
            if pair in self.volatility_cache:
                volatility, timestamp = self.volatility_cache[pair]
                if datetime.now() - timestamp < timedelta(minutes=15):
                    return volatility
            
            # Get historical data
            end_time = datetime.now()
            start_time = end_time - timedelta(days=self.settings.volatility_lookback_days)
            
            historical_data = self.data_manager.get_historical_data(
                pair, start_time, end_time
            )
            
            if historical_data.empty or len(historical_data) < 2:
                return 0.5  # Default moderate volatility
            
            # Calculate returns
            returns = historical_data['close'].pct_change().dropna()
            
            if len(returns) < 2:
                return 0.5
            
            # Calculate volatility (annualized)
            daily_volatility = returns.std()
            annualized_volatility = daily_volatility * math.sqrt(365)
            
            # Cache result
            self.volatility_cache[pair] = (annualized_volatility, datetime.now())
            
            return annualized_volatility
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility for {pair}: {str(e)}")
            return 0.5  # Default moderate volatility
    
    def _get_current_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current positions across all trading pairs.
        
        Returns:
            Dict: Current positions with values
        """
        positions = {}
        
        try:
            for pair in self.trading_pairs:
                base_currency = pair.split('/')[0]
                
                # Get balance
                balance = self.position_manager.get_crypto_balance(base_currency)
                if balance and balance.balance > 0:
                    # Get current price
                    current_price = self.data_manager.get_latest_data(pair, 1)
                    if not current_price.empty:
                        price = current_price.iloc[-1]['close']
                        value_usd = balance.balance * price
                        
                        positions[pair] = {
                            'quantity': balance.balance,
                            'price': price,
                            'value_usd': value_usd,
                            'currency': base_currency
                        }
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting current positions: {str(e)}")
            return {}
    
    def _get_portfolio_value(self) -> float:
        """
        Get total portfolio value in USD.
        
        Returns:
            float: Portfolio value
        """
        try:
            return self.base_risk_manager._get_portfolio_value()
        except Exception as e:
            self.logger.error(f"Error getting portfolio value: {str(e)}")
            return 0.0
    
    def _update_correlation_matrix(self) -> None:
        """Update correlation matrix for all trading pairs."""
        try:
            if len(self.trading_pairs) < 2:
                return
            
            # Get price data for all pairs
            price_data = {}
            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)  # 30 days for correlation
            
            for pair in self.trading_pairs:
                try:
                    data = self.data_manager.get_historical_data(pair, start_time, end_time)
                    if not data.empty:
                        price_data[pair] = data['close'].pct_change().dropna()
                except Exception as e:
                    self.logger.warning(f"Could not get data for {pair}: {str(e)}")
            
            # Calculate correlations
            for i, pair1 in enumerate(self.trading_pairs):
                for j, pair2 in enumerate(self.trading_pairs):
                    if i >= j:  # Only calculate upper triangle
                        continue
                    
                    if pair1 in price_data and pair2 in price_data:
                        try:
                            # Align data
                            common_dates = price_data[pair1].index.intersection(
                                price_data[pair2].index
                            )
                            
                            if len(common_dates) > 10:  # Need sufficient data
                                returns1 = price_data[pair1].loc[common_dates]
                                returns2 = price_data[pair2].loc[common_dates]
                                
                                correlation = returns1.corr(returns2)
                                if not math.isnan(correlation):
                                    self.correlation_matrix[(pair1, pair2)] = correlation
                                    self.correlation_matrix[(pair2, pair1)] = correlation
                        except Exception as e:
                            self.logger.warning(f"Error calculating correlation for {pair1}-{pair2}: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Error updating correlation matrix: {str(e)}")
    
    def _calculate_correlation_impact(self, pair: str, quantity: float, price: float) -> float:
        """
        Calculate correlation impact of a new position.
        
        Args:
            pair: Trading pair
            quantity: Position quantity
            price: Current price
            
        Returns:
            float: Correlation impact (0-1)
        """
        try:
            current_positions = self._get_current_positions()
            if not current_positions:
                return 0.0
            
            position_value = quantity * price
            max_correlation = 0.0
            
            for existing_pair, position in current_positions.items():
                if existing_pair == pair:
                    continue
                
                # Get correlation
                correlation_key = (pair, existing_pair)
                if correlation_key in self.correlation_matrix:
                    correlation = abs(self.correlation_matrix[correlation_key])
                    
                    # Weight by position size
                    weight = position['value_usd'] / (position['value_usd'] + position_value)
                    weighted_correlation = correlation * weight
                    
                    max_correlation = max(max_correlation, weighted_correlation)
            
            return max_correlation
            
        except Exception as e:
            self.logger.error(f"Error calculating correlation impact: {str(e)}")
            return 0.0
    
    def _assess_portfolio_impact(self, pair: str, quantity: float, price: float) -> float:
        """
        Assess the impact of a new position on portfolio.
        
        Args:
            pair: Trading pair
            quantity: Position quantity
            price: Current price
            
        Returns:
            float: Portfolio impact (0-1)
        """
        try:
            portfolio_value = self._get_portfolio_value()
            if portfolio_value <= 0:
                return 1.0  # Maximum impact if no portfolio
            
            position_value = quantity * price
            impact = position_value / portfolio_value
            
            return min(impact, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error assessing portfolio impact: {str(e)}")
            return 1.0
    
    def _determine_risk_level(self, pair: str, quantity: float, price: float,
                            signal_confidence: float, portfolio_impact: float,
                            correlation_impact: float) -> RiskLevel:
        """
        Determine overall risk level for a trade.
        
        Args:
            pair: Trading pair
            quantity: Position quantity
            price: Current price
            signal_confidence: Signal confidence
            portfolio_impact: Portfolio impact
            correlation_impact: Correlation impact
            
        Returns:
            RiskLevel: Overall risk level
        """
        try:
            # Calculate individual risk scores (0-1)
            volatility = self._get_pair_volatility(pair)
            volatility_score = min(volatility / 2.0, 1.0)  # Normalize to 0-1
            
            confidence_score = 1.0 - signal_confidence
            
            # Combine scores using weights
            weights = self.settings.risk_score_weights
            total_score = (
                weights.get('volatility', 0.3) * volatility_score +
                weights.get('correlation', 0.2) * correlation_impact +
                weights.get('portfolio_exposure', 0.15) * portfolio_impact +
                weights.get('momentum', 0.2) * confidence_score +
                weights.get('drawdown', 0.15) * (self._calculate_current_drawdown() / self.settings.max_portfolio_drawdown)
            )
            
            # Map score to risk level
            if total_score >= 0.8:
                return RiskLevel.EXTREME
            elif total_score >= 0.6:
                return RiskLevel.HIGH
            elif total_score >= 0.4:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.LOW
                
        except Exception as e:
            self.logger.error(f"Error determining risk level: {str(e)}")
            return RiskLevel.EXTREME
    
    def _check_emergency_stops(self) -> bool:
        """Check if any emergency stops are active."""
        return any(self.emergency_stops.values())
    
    def _check_volatility_spike(self) -> bool:
        """Check for volatility spikes across the portfolio."""
        try:
            for pair in self.trading_pairs:
                current_vol = self._get_pair_volatility(pair)
                
                # Get historical average volatility
                historical_vol = self._get_historical_volatility(pair, days=90)
                
                if historical_vol > 0 and current_vol / historical_vol > self.settings.volatility_spike_threshold:
                    self.logger.warning(f"Volatility spike detected in {pair}: {current_vol:.2f} vs {historical_vol:.2f}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking volatility spike: {str(e)}")
            return True  # Conservative: assume spike if error
    
    def _check_correlation_spike(self) -> bool:
        """Check for correlation spikes in the portfolio."""
        try:
            positions = self._get_current_positions()
            if len(positions) < 2:
                return False
            
            pairs = list(positions.keys())
            high_correlations = 0
            total_pairs = 0
            
            for i, pair1 in enumerate(pairs):
                for j, pair2 in enumerate(pairs):
                    if i >= j:
                        continue
                    
                    total_pairs += 1
                    correlation_key = (pair1, pair2)
                    
                    if correlation_key in self.correlation_matrix:
                        correlation = abs(self.correlation_matrix[correlation_key])
                        if correlation > self.settings.correlation_spike_threshold:
                            high_correlations += 1
            
            if total_pairs > 0:
                correlation_ratio = high_correlations / total_pairs
                return correlation_ratio > 0.5  # More than 50% of pairs highly correlated
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking correlation spike: {str(e)}")
            return True  # Conservative: assume spike if error
    
    def _get_historical_volatility(self, pair: str, days: int = 90) -> float:
        """Get historical average volatility for a pair."""
        try:
            end_time = datetime.now() - timedelta(days=30)  # Exclude recent period
            start_time = end_time - timedelta(days=days)
            
            historical_data = self.data_manager.get_historical_data(pair, start_time, end_time)
            
            if historical_data.empty or len(historical_data) < 2:
                return 0.5  # Default
            
            returns = historical_data['close'].pct_change().dropna()
            if len(returns) < 2:
                return 0.5
            
            daily_volatility = returns.std()
            return daily_volatility * math.sqrt(365)
            
        except Exception as e:
            self.logger.error(f"Error getting historical volatility for {pair}: {str(e)}")
            return 0.5
    
    def _calculate_current_drawdown(self) -> float:
        """Calculate current portfolio drawdown."""
        try:
            return self.base_risk_manager.current_drawdown
        except Exception as e:
            self.logger.error(f"Error calculating current drawdown: {str(e)}")
            return 0.0
    
    def _calculate_portfolio_beta(self, positions: Dict[str, Dict[str, Any]]) -> float:
        """Calculate portfolio beta relative to market (BTC)."""
        try:
            if 'BTC/USD' not in positions and 'XBTUSD' not in positions:
                return 1.0  # Default beta
            
            # Simplified beta calculation
            # In a real implementation, this would use regression analysis
            weighted_beta = 0.0
            total_weight = 0.0
            
            for pair, position in positions.items():
                weight = position['value_usd']
                # Simplified: assume beta of 1 for BTC, 1.5 for ETH, 2.0 for others
                if 'BTC' in pair:
                    beta = 1.0
                elif 'ETH' in pair:
                    beta = 1.5
                else:
                    beta = 2.0
                
                weighted_beta += beta * weight
                total_weight += weight
            
            return weighted_beta / total_weight if total_weight > 0 else 1.0
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio beta: {str(e)}")
            return 1.0
    
    def _calculate_portfolio_var(self, positions: Dict[str, Dict[str, Any]], 
                               confidence: float = 0.95) -> float:
        """Calculate portfolio Value at Risk."""
        try:
            if not positions:
                return 0.0
            
            total_var = 0.0
            
            for pair, position in positions.items():
                volatility = self._get_pair_volatility(pair)
                position_value = position['value_usd']
                
                # Calculate individual VaR (assuming normal distribution)
                z_score = 1.65 if confidence == 0.95 else 2.33  # 95% or 99%
                individual_var = position_value * volatility * z_score / math.sqrt(365)
                
                total_var += individual_var ** 2  # Sum of squares for portfolio VaR
            
            return math.sqrt(total_var)  # Portfolio VaR
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio VaR: {str(e)}")
            return 0.0
    
    def _calculate_expected_shortfall(self, positions: Dict[str, Dict[str, Any]]) -> float:
        """Calculate Expected Shortfall (Conditional VaR)."""
        try:
            var_95 = self._calculate_portfolio_var(positions, 0.95)
            # Simplified: ES is approximately 1.3 times VaR for normal distribution
            return var_95 * 1.3
            
        except Exception as e:
            self.logger.error(f"Error calculating expected shortfall: {str(e)}")
            return 0.0
    
    def _calculate_portfolio_sharpe_ratio(self) -> float:
        """Calculate portfolio Sharpe ratio."""
        try:
            if len(self.portfolio_value_history) < 30:
                return 0.0  # Need sufficient history
            
            # Calculate returns from portfolio value history
            values = [value for _, value in self.portfolio_value_history[-30:]]
            returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
            
            if not returns:
                return 0.0
            
            avg_return = statistics.mean(returns)
            return_std = statistics.stdev(returns) if len(returns) > 1 else 0.0
            
            if return_std == 0:
                return 0.0
            
            # Annualize (assuming daily data)
            annual_return = avg_return * 365
            annual_std = return_std * math.sqrt(365)
            
            # Assume risk-free rate of 2%
            risk_free_rate = 0.02
            
            return (annual_return - risk_free_rate) / annual_std
            
        except Exception as e:
            self.logger.error(f"Error calculating Sharpe ratio: {str(e)}")
            return 0.0
    
    def _determine_portfolio_risk_level(self, concentration_risk: float, 
                                      max_drawdown: float, var_95: float,
                                      total_exposure: float) -> RiskLevel:
        """Determine overall portfolio risk level."""
        try:
            portfolio_value = self._get_portfolio_value()
            
            # Calculate risk scores
            concentration_score = min(concentration_risk / 0.5, 1.0)  # Normalize
            drawdown_score = max_drawdown / self.settings.max_portfolio_drawdown
            var_score = (var_95 / portfolio_value) if portfolio_value > 0 else 1.0
            exposure_score = total_exposure / (portfolio_value * self.settings.max_portfolio_exposure) if portfolio_value > 0 else 1.0
            
            # Weighted average
            total_score = (
                0.3 * concentration_score +
                0.3 * drawdown_score +
                0.2 * var_score +
                0.2 * exposure_score
            )
            
            if total_score >= 0.8:
                return RiskLevel.EXTREME
            elif total_score >= 0.6:
                return RiskLevel.HIGH
            elif total_score >= 0.4:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.LOW
                
        except Exception as e:
            self.logger.error(f"Error determining portfolio risk level: {str(e)}")
            return RiskLevel.EXTREME
    
    def update_portfolio_metrics(self) -> None:
        """Update portfolio metrics and history."""
        try:
            current_value = self._get_portfolio_value()
            current_time = datetime.now()
            
            # Update value history
            self.portfolio_value_history.append((current_time, current_value))
            
            # Keep only last 1000 entries
            if len(self.portfolio_value_history) > 1000:
                self.portfolio_value_history = self.portfolio_value_history[-1000:]
            
            # Update drawdown history
            if self.portfolio_value_history:
                high_water_mark = max(value for _, value in self.portfolio_value_history)
                current_drawdown = (high_water_mark - current_value) / high_water_mark if high_water_mark > 0 else 0
                self.drawdown_history.append((current_time, current_drawdown))
                
                if len(self.drawdown_history) > 1000:
                    self.drawdown_history = self.drawdown_history[-1000:]
            
            # Update base risk manager
            self.base_risk_manager.update_portfolio_metrics()
            
        except Exception as e:
            self.logger.error(f"Error updating portfolio metrics: {str(e)}")
    
    def reset_emergency_stops(self) -> None:
        """Reset all emergency stops."""
        self.emergency_stops = {reason: False for reason in EmergencyStopReason}
        self.logger.info("All emergency stops reset")
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary."""
        try:
            portfolio_risk = self.check_portfolio_risk()
            emergency_stop, stop_reason = self.should_emergency_stop()
            
            return {
                'timestamp': datetime.now(),
                'portfolio_risk': portfolio_risk,
                'emergency_stop_active': emergency_stop,
                'emergency_stop_reason': stop_reason.value if stop_reason else None,
                'active_emergency_stops': [
                    reason.value for reason, active in self.emergency_stops.items() if active
                ],
                'correlation_matrix_size': len(self.correlation_matrix),
                'volatility_cache_size': len(self.volatility_cache),
                'recent_alerts': len([a for a in self.risk_alerts if 
                                    datetime.now() - a.timestamp < timedelta(hours=24)])
            }
            
        except Exception as e:
            self.logger.error(f"Error generating risk summary: {str(e)}")
            return {'error': str(e), 'timestamp': datetime.now()}