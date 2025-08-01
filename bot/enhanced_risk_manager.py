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

# Adaptive components imports
try:
    from bot.adaptive.data_models import AdaptiveSignal, MarketRegime, PerformanceMetrics
    from bot.adaptive.enums import RegimeType
    from bot.adaptive.interfaces import RiskManagerInterface
    ADAPTIVE_AVAILABLE = True
except ImportError:
    # Fallback for when adaptive components are not available
    ADAPTIVE_AVAILABLE = False
    AdaptiveSignal = None
    MarketRegime = None
    PerformanceMetrics = None
    RegimeType = None
    RiskManagerInterface = object


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
    
    # Adaptive risk management settings
    enable_adaptive_risk: bool = True
    ml_confidence_threshold: float = 0.5  # Minimum ML confidence for adaptive signals
    regime_risk_multipliers: Dict[str, float] = field(default_factory=lambda: {
        'trending_bull': 1.2,  # Increase risk in bull trends
        'trending_bear': 0.8,  # Reduce risk in bear trends
        'ranging': 1.0,        # Normal risk in ranging markets
        'high_volatility': 0.6, # Reduce risk in high volatility
        'low_volatility': 1.1,  # Slightly increase risk in low volatility
        'uncertain': 0.7       # Reduce risk when uncertain
    })
    adaptation_failure_penalty: float = 0.5  # Risk reduction factor after adaptation failures


class EnhancedRiskManager(RiskManagerInterface if ADAPTIVE_AVAILABLE else object):
    """
    Advanced risk management system with dynamic position sizing, portfolio-level
    exposure limits, correlation analysis, emergency stop mechanisms, and adaptive
    signal integration.
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
        
        # Adaptive risk management state
        self.current_regime: Optional[MarketRegime] = None if not ADAPTIVE_AVAILABLE else None
        self.adaptation_failures: int = 0
        self.regime_risk_adjustments: Dict[str, float] = {}
        
        self.logger.info(f"EnhancedRiskManager initialized for {len(trading_pairs)} trading pairs"
                        f" with adaptive features {'enabled' if ADAPTIVE_AVAILABLE else 'disabled'}")
    
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
    
    # Adaptive Risk Management Methods
    
    def validate_adaptive_signal(self, signal: 'AdaptiveSignal', current_positions: Dict[str, Any]) -> bool:
        """
        Validate an adaptive signal against risk parameters.
        
        Args:
            signal: Adaptive signal to validate
            current_positions: Current portfolio positions
            
        Returns:
            bool: True if signal passes validation
        """
        if not ADAPTIVE_AVAILABLE or not self.settings.enable_adaptive_risk:
            # Fall back to basic validation
            return self.base_risk_manager.validate_position_size(
                signal.pair.split('/')[0], 
                signal.suggested_position_size or 0.01,
                signal.price
            )[0]
        
        try:
            # Check ML confidence threshold
            if signal.ml_confidence < self.settings.ml_confidence_threshold:
                self.logger.warning(
                    f"Adaptive signal for {signal.pair} rejected: "
                    f"ML confidence {signal.ml_confidence:.3f} below threshold {self.settings.ml_confidence_threshold}"
                )
                return False
            
            # Check signal confidence with regime adjustment
            regime_adjusted_threshold = self._get_regime_adjusted_confidence_threshold(signal.regime_context)
            if signal.confidence < regime_adjusted_threshold:
                self.logger.warning(
                    f"Adaptive signal for {signal.pair} rejected: "
                    f"Signal confidence {signal.confidence:.3f} below regime-adjusted threshold {regime_adjusted_threshold:.3f}"
                )
                return False
            
            # Validate position size with adaptive adjustments
            suggested_size = signal.suggested_position_size or self._calculate_adaptive_position_size(signal)
            
            # Check against portfolio risk limits
            portfolio_risk = self._assess_adaptive_portfolio_risk(signal, current_positions, suggested_size)
            if portfolio_risk['risk_level'] == RiskLevel.EXTREME:
                self.logger.warning(
                    f"Adaptive signal for {signal.pair} rejected: Extreme portfolio risk"
                )
                return False
            
            # Check correlation with adaptive weighting
            correlation_impact = self._calculate_adaptive_correlation_impact(signal, current_positions)
            if correlation_impact > self.settings.correlation_threshold * 1.2:  # 20% higher threshold for adaptive
                self.logger.warning(
                    f"Adaptive signal for {signal.pair} rejected: "
                    f"High correlation impact {correlation_impact:.3f}"
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating adaptive signal: {str(e)}")
            return False
    
    def calculate_adaptive_position_size(self, signal: 'AdaptiveSignal', account_balance: float) -> float:
        """
        Calculate appropriate position size for adaptive signal.
        
        Args:
            signal: Adaptive signal
            account_balance: Available account balance
            
        Returns:
            float: Calculated position size
        """
        if not ADAPTIVE_AVAILABLE or not self.settings.enable_adaptive_risk:
            return self.calculate_position_size(
                signal.pair, signal.confidence, signal.price, account_balance
            ).final_size
        
        try:
            # Start with base calculation
            base_calc = self.calculate_position_size(
                signal.pair, signal.confidence, signal.price, account_balance
            )
            
            # Apply regime-based adjustments
            regime_multiplier = self._get_regime_risk_multiplier(signal.regime_context)
            regime_adjusted_size = base_calc.final_size * regime_multiplier
            
            # Apply ML confidence scaling
            ml_confidence_multiplier = 0.5 + (signal.ml_confidence * 0.5)  # Scale from 0.5 to 1.0
            ml_adjusted_size = regime_adjusted_size * ml_confidence_multiplier
            
            # Apply strategy weight adjustments
            strategy_weight_multiplier = self._calculate_strategy_weight_multiplier(signal)
            final_size = ml_adjusted_size * strategy_weight_multiplier
            
            # Apply adaptation failure penalty if applicable
            if self.adaptation_failures > 0:
                penalty_factor = self.settings.adaptation_failure_penalty ** min(self.adaptation_failures, 3)
                final_size *= penalty_factor
            
            # Ensure within bounds
            min_size = base_calc.final_size * 0.1  # At least 10% of base size
            max_size = base_calc.final_size * 2.0   # At most 200% of base size
            final_size = max(min_size, min(final_size, max_size))
            
            self.logger.info(
                f"Adaptive position size for {signal.pair}: "
                f"base={base_calc.final_size:.6f}, "
                f"regime_mult={regime_multiplier:.3f}, "
                f"ml_mult={ml_confidence_multiplier:.3f}, "
                f"strategy_mult={strategy_weight_multiplier:.3f}, "
                f"final={final_size:.6f}"
            )
            
            return final_size
            
        except Exception as e:
            self.logger.error(f"Error calculating adaptive position size: {str(e)}")
            # Fall back to base calculation
            return self.calculate_position_size(
                signal.pair, signal.confidence, signal.price, account_balance
            ).final_size
    
    def update_risk_parameters(self, regime: 'MarketRegime', performance_metrics: 'PerformanceMetrics') -> None:
        """
        Update risk parameters based on market regime and performance.
        
        Args:
            regime: Current market regime
            performance_metrics: Recent performance metrics
        """
        if not ADAPTIVE_AVAILABLE or not self.settings.enable_adaptive_risk:
            return
        
        try:
            self.current_regime = regime
            
            # Update regime-specific risk adjustments
            regime_key = regime.regime_type.value if hasattr(regime.regime_type, 'value') else str(regime.regime_type)
            
            # Adjust risk parameters based on regime confidence
            confidence_factor = regime.confidence
            base_multiplier = self.settings.regime_risk_multipliers.get(regime_key, 1.0)
            
            # Adjust multiplier based on regime confidence
            adjusted_multiplier = base_multiplier * confidence_factor + (1.0 - confidence_factor)
            self.regime_risk_adjustments[regime_key] = adjusted_multiplier
            
            # Adjust based on recent performance
            if performance_metrics.sharpe_ratio < 0:
                # Poor performance - reduce risk
                performance_penalty = max(0.5, 1.0 + performance_metrics.sharpe_ratio * 0.2)
                adjusted_multiplier *= performance_penalty
            elif performance_metrics.sharpe_ratio > 1.0:
                # Good performance - slightly increase risk
                performance_bonus = min(1.2, 1.0 + (performance_metrics.sharpe_ratio - 1.0) * 0.1)
                adjusted_multiplier *= performance_bonus
            
            # Update base risk per trade
            original_base_risk = self.settings.base_risk_per_trade
            self.settings.base_risk_per_trade = original_base_risk * adjusted_multiplier
            
            # Ensure within bounds
            self.settings.base_risk_per_trade = max(
                self.settings.min_risk_per_trade,
                min(self.settings.base_risk_per_trade, self.settings.max_risk_per_trade)
            )
            
            self.logger.info(
                f"Updated risk parameters for regime {regime_key}: "
                f"multiplier={adjusted_multiplier:.3f}, "
                f"base_risk={self.settings.base_risk_per_trade:.4f}"
            )
            
        except Exception as e:
            self.logger.error(f"Error updating risk parameters: {str(e)}")
    
    def check_portfolio_risk_adaptive(self, proposed_signal: 'AdaptiveSignal', 
                                    current_portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check portfolio-level risk for a proposed adaptive trade.
        
        Args:
            proposed_signal: Proposed adaptive signal
            current_portfolio: Current portfolio state
            
        Returns:
            Dict: Risk assessment results
        """
        if not ADAPTIVE_AVAILABLE:
            return {'risk_level': 'unknown', 'adaptive_features': False}
        
        try:
            # Get base portfolio risk
            base_risk = self.check_portfolio_risk()
            
            # Calculate proposed position impact
            proposed_size = proposed_signal.suggested_position_size or self._calculate_adaptive_position_size(proposed_signal)
            position_value = proposed_size * proposed_signal.price
            
            # Assess regime-specific risks
            regime_risks = self._assess_regime_specific_risks(proposed_signal.regime_context, position_value)
            
            # Calculate ML model risk contribution
            ml_risk_factor = 1.0 - proposed_signal.ml_confidence  # Higher ML confidence = lower risk
            
            # Assess strategy diversification impact
            strategy_concentration = self._calculate_strategy_concentration_risk(proposed_signal)
            
            return {
                'base_portfolio_risk': base_risk,
                'regime_risks': regime_risks,
                'ml_risk_factor': ml_risk_factor,
                'strategy_concentration': strategy_concentration,
                'position_value': position_value,
                'overall_risk_level': self._determine_overall_adaptive_risk_level(
                    base_risk, regime_risks, ml_risk_factor, strategy_concentration
                ),
                'adaptive_features': True,
                'recommendations': self._generate_risk_recommendations(
                    proposed_signal, base_risk, regime_risks
                )
            }
            
        except Exception as e:
            self.logger.error(f"Error checking adaptive portfolio risk: {str(e)}")
            return {'error': str(e), 'adaptive_features': True}
    
    def get_emergency_stop_conditions_adaptive(self) -> Dict[str, Any]:
        """
        Get conditions that would trigger emergency stops with adaptive considerations.
        
        Returns:
            Dict: Emergency stop conditions and thresholds
        """
        base_conditions = {
            'max_drawdown': self.settings.max_portfolio_drawdown,
            'volatility_spike': self.settings.volatility_spike_threshold,
            'correlation_spike': self.settings.correlation_spike_threshold,
            'consecutive_losses': self.settings.consecutive_loss_limit
        }
        
        if not ADAPTIVE_AVAILABLE or not self.current_regime:
            return base_conditions
        
        try:
            # Adjust thresholds based on current regime
            regime_key = (self.current_regime.regime_type.value 
                         if hasattr(self.current_regime.regime_type, 'value') 
                         else str(self.current_regime.regime_type))
            
            adaptive_conditions = base_conditions.copy()
            
            # Tighten emergency stops in uncertain or high volatility regimes
            if regime_key in ['uncertain', 'high_volatility']:
                adaptive_conditions['max_drawdown'] *= 0.8  # 20% tighter
                adaptive_conditions['consecutive_losses'] = max(3, int(base_conditions['consecutive_losses'] * 0.6))
            
            # Relax slightly in stable trending markets
            elif regime_key in ['trending_bull', 'trending_bear'] and self.current_regime.confidence > 0.8:
                adaptive_conditions['max_drawdown'] *= 1.1  # 10% more lenient
                adaptive_conditions['consecutive_losses'] = min(8, int(base_conditions['consecutive_losses'] * 1.2))
            
            # Add adaptive-specific conditions
            adaptive_conditions.update({
                'ml_confidence_degradation': 0.3,  # Stop if ML confidence drops below 30%
                'adaptation_failure_limit': 3,     # Stop after 3 consecutive adaptation failures
                'regime_confidence_collapse': 0.2  # Stop if regime confidence drops below 20%
            })
            
            return adaptive_conditions
            
        except Exception as e:
            self.logger.error(f"Error getting adaptive emergency stop conditions: {str(e)}")
            return base_conditions
    
    def record_adaptation_failure(self) -> None:
        """Record an adaptation failure for risk adjustment."""
        self.adaptation_failures += 1
        self.logger.warning(f"Adaptation failure recorded. Total failures: {self.adaptation_failures}")
        
        # Trigger emergency stop if too many failures
        if self.adaptation_failures >= 3:
            self.emergency_stops[EmergencyStopReason.SYSTEM_ERROR] = True
            self.logger.error("Emergency stop triggered due to repeated adaptation failures")
    
    def reset_adaptation_failures(self) -> None:
        """Reset adaptation failure counter after successful period."""
        if self.adaptation_failures > 0:
            self.logger.info(f"Resetting {self.adaptation_failures} adaptation failures")
            self.adaptation_failures = 0
    
    # Helper methods for adaptive risk management
    
    def _get_regime_adjusted_confidence_threshold(self, regime: 'MarketRegime') -> float:
        """Get confidence threshold adjusted for market regime."""
        base_threshold = self.settings.confidence_threshold
        
        if not regime:
            return base_threshold
        
        # Adjust threshold based on regime uncertainty
        regime_confidence_factor = regime.confidence
        adjusted_threshold = base_threshold * (2.0 - regime_confidence_factor)  # Higher threshold when regime uncertain
        
        return min(0.9, max(0.3, adjusted_threshold))  # Clamp between 30% and 90%
    
    def _get_regime_risk_multiplier(self, regime: 'MarketRegime') -> float:
        """Get risk multiplier based on market regime."""
        if not regime:
            return 1.0
        
        regime_key = (regime.regime_type.value 
                     if hasattr(regime.regime_type, 'value') 
                     else str(regime.regime_type))
        
        base_multiplier = self.settings.regime_risk_multipliers.get(regime_key, 1.0)
        
        # Adjust based on regime confidence
        confidence_adjustment = 0.5 + (regime.confidence * 0.5)  # Scale from 0.5 to 1.0
        
        return base_multiplier * confidence_adjustment
    
    def _calculate_adaptive_position_size(self, signal: 'AdaptiveSignal') -> float:
        """Calculate position size for adaptive signal."""
        if signal.suggested_position_size:
            return signal.suggested_position_size
        
        # Use portfolio percentage approach
        portfolio_value = self._get_portfolio_value()
        if portfolio_value <= 0:
            return 0.0
        
        risk_amount = portfolio_value * self.settings.base_risk_per_trade
        return risk_amount / signal.price
    
    def _calculate_strategy_weight_multiplier(self, signal: 'AdaptiveSignal') -> float:
        """Calculate position size multiplier based on strategy weights."""
        if not signal.strategy_weights:
            return 1.0
        
        # Use weighted average of strategy weights
        total_weight = sum(signal.strategy_weights.values())
        if total_weight == 0:
            return 1.0
        
        # Normalize and use as multiplier (0.5 to 1.5 range)
        normalized_weight = total_weight / len(signal.strategy_weights)
        return 0.5 + normalized_weight
    
    def _assess_adaptive_portfolio_risk(self, signal: 'AdaptiveSignal', 
                                      current_positions: Dict[str, Any], 
                                      position_size: float) -> Dict[str, Any]:
        """Assess portfolio risk for adaptive signal."""
        # Get base portfolio risk
        base_risk = self.check_portfolio_risk()
        
        # Add adaptive-specific risk factors
        position_value = position_size * signal.price
        portfolio_value = self._get_portfolio_value()
        
        if portfolio_value > 0:
            position_impact = position_value / portfolio_value
        else:
            position_impact = 1.0
        
        # Determine risk level
        if position_impact > 0.3 or base_risk.risk_level == RiskLevel.EXTREME:
            risk_level = RiskLevel.EXTREME
        elif position_impact > 0.2 or base_risk.risk_level == RiskLevel.HIGH:
            risk_level = RiskLevel.HIGH
        elif position_impact > 0.1 or base_risk.risk_level == RiskLevel.MEDIUM:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        return {
            'risk_level': risk_level,
            'position_impact': position_impact,
            'base_risk': base_risk
        }
    
    def _calculate_adaptive_correlation_impact(self, signal: 'AdaptiveSignal', 
                                             current_positions: Dict[str, Any]) -> float:
        """Calculate correlation impact with adaptive considerations."""
        base_correlation = self._calculate_correlation_impact(
            signal.pair, 
            signal.suggested_position_size or self._calculate_adaptive_position_size(signal),
            signal.price
        )
        
        # Adjust based on regime - correlations may be higher in certain regimes
        if signal.regime_context:
            regime_key = (signal.regime_context.regime_type.value 
                         if hasattr(signal.regime_context.regime_type, 'value') 
                         else str(signal.regime_context.regime_type))
            
            if regime_key in ['high_volatility', 'uncertain']:
                # Correlations tend to increase during stress
                base_correlation *= 1.2
        
        return base_correlation
    
    def _assess_regime_specific_risks(self, regime: 'MarketRegime', position_value: float) -> Dict[str, float]:
        """Assess risks specific to the current market regime."""
        if not regime:
            return {}
        
        risks = {}
        
        # Volatility risk
        if regime.volatility_level > 2.0:  # High volatility
            risks['volatility_risk'] = min(1.0, regime.volatility_level / 3.0)
        
        # Trend reversal risk
        if abs(regime.trend_strength) > 0.8 and regime.confidence < 0.6:
            risks['trend_reversal_risk'] = (abs(regime.trend_strength) * (1.0 - regime.confidence))
        
        # Momentum divergence risk
        if abs(regime.momentum - regime.trend_strength) > 0.5:
            risks['momentum_divergence_risk'] = abs(regime.momentum - regime.trend_strength)
        
        return risks
    
    def _calculate_strategy_concentration_risk(self, signal: 'AdaptiveSignal') -> float:
        """Calculate risk from strategy concentration."""
        if not signal.strategy_weights:
            return 0.0
        
        # Calculate Herfindahl index for strategy concentration
        total_weight = sum(signal.strategy_weights.values())
        if total_weight == 0:
            return 0.0
        
        normalized_weights = [w / total_weight for w in signal.strategy_weights.values()]
        herfindahl_index = sum(w ** 2 for w in normalized_weights)
        
        return herfindahl_index  # Higher values indicate more concentration
    
    def _determine_overall_adaptive_risk_level(self, base_risk: PortfolioRisk, 
                                             regime_risks: Dict[str, float],
                                             ml_risk_factor: float,
                                             strategy_concentration: float) -> str:
        """Determine overall risk level for adaptive trading."""
        # Start with base risk level
        risk_score = 0.0
        
        if base_risk.risk_level == RiskLevel.LOW:
            risk_score = 0.25
        elif base_risk.risk_level == RiskLevel.MEDIUM:
            risk_score = 0.5
        elif base_risk.risk_level == RiskLevel.HIGH:
            risk_score = 0.75
        else:  # EXTREME
            risk_score = 1.0
        
        # Add regime-specific risks
        regime_risk_contribution = sum(regime_risks.values()) * 0.2  # 20% weight
        risk_score += regime_risk_contribution
        
        # Add ML uncertainty risk
        ml_risk_contribution = ml_risk_factor * 0.15  # 15% weight
        risk_score += ml_risk_contribution
        
        # Add strategy concentration risk
        concentration_risk_contribution = strategy_concentration * 0.1  # 10% weight
        risk_score += concentration_risk_contribution
        
        # Determine final risk level
        if risk_score >= 0.8:
            return 'extreme'
        elif risk_score >= 0.6:
            return 'high'
        elif risk_score >= 0.4:
            return 'medium'
        else:
            return 'low'
    
    def _generate_risk_recommendations(self, signal: 'AdaptiveSignal', 
                                     base_risk: PortfolioRisk,
                                     regime_risks: Dict[str, float]) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        # Base risk recommendations
        if base_risk.risk_level in [RiskLevel.HIGH, RiskLevel.EXTREME]:
            recommendations.append("Consider reducing overall portfolio exposure")
        
        # Regime-specific recommendations
        if 'volatility_risk' in regime_risks and regime_risks['volatility_risk'] > 0.5:
            recommendations.append("High volatility detected - consider tighter stop losses")
        
        if 'trend_reversal_risk' in regime_risks and regime_risks['trend_reversal_risk'] > 0.4:
            recommendations.append("Trend reversal risk - consider taking profits on existing positions")
        
        # ML confidence recommendations
        if signal.ml_confidence < 0.7:
            recommendations.append("Low ML confidence - consider reducing position size")
        
        # Strategy diversification recommendations
        if len(signal.strategy_weights) < 2:
            recommendations.append("Single strategy signal - consider waiting for ensemble confirmation")
        
        return recommendations