"""
Portfolio Optimization for Multi-Pair Coordination

This module implements portfolio-level optimization across multiple trading pairs,
including capital allocation optimization, correlation-aware position management,
and portfolio rebalancing based on market conditions and performance.
"""
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, 
    StrategyAllocation, AdaptationEvent
)
from .enums import RegimeType, SignalStrength
from .interfaces import PerformanceAnalyzerInterface


@dataclass
class PortfolioPosition:
    """Represents a position in the portfolio."""
    pair: str
    size: float  # Position size in USD
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    allocation_percentage: float  # Percentage of total portfolio
    risk_contribution: float  # Risk contribution to portfolio
    correlation_exposure: Dict[str, float] = field(default_factory=dict)
    
    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return abs(self.size) * self.current_price
    
    @property
    def pnl_percentage(self) -> float:
        """P&L as percentage of position size."""
        if self.size == 0:
            return 0.0
        return (self.unrealized_pnl + self.realized_pnl) / abs(self.size)


@dataclass
class PortfolioMetrics:
    """Portfolio-level performance metrics."""
    total_value: float
    total_pnl: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    
    # Risk metrics
    var_95: float  # Value at Risk (95% confidence)
    expected_shortfall: float  # Expected shortfall beyond VaR
    
    # Diversification metrics
    correlation_risk: float  # Portfolio correlation risk
    concentration_risk: float  # Concentration in single positions
    
    # Allocation metrics
    pair_allocations: Dict[str, float] = field(default_factory=dict)
    regime_exposure: Dict[RegimeType, float] = field(default_factory=dict)
    
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class OpportunityScore:
    """Scoring for trading opportunities across pairs."""
    pair: str
    signal: AdaptiveSignal
    opportunity_strength: float  # 0.0 to 1.0
    risk_adjusted_return: float
    correlation_penalty: float  # Penalty for high correlation with existing positions
    regime_bonus: float  # Bonus for favorable regime
    final_score: float
    
    def calculate_final_score(self, 
                            base_weight: float = 0.4,
                            risk_weight: float = 0.3,
                            correlation_weight: float = 0.2,
                            regime_weight: float = 0.1) -> float:
        """Calculate final opportunity score with weighted components."""
        self.final_score = (
            base_weight * self.opportunity_strength +
            risk_weight * self.risk_adjusted_return +
            correlation_weight * (1.0 - self.correlation_penalty) +
            regime_weight * self.regime_bonus
        )
        return self.final_score


class PortfolioOptimizer:
    """
    Portfolio optimizer for multi-pair coordination and capital allocation.
    
    Features:
    - Portfolio-level optimization across multiple trading pairs
    - Capital allocation optimization based on opportunity strength
    - Correlation-aware position management
    - Portfolio rebalancing based on market conditions and performance
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the portfolio optimizer.
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        
        # Default configuration
        self.config = {
            'max_pairs': 10,
            'max_correlation': 0.7,
            'max_single_pair_allocation': 0.4,  # 40% max in single pair
            'min_single_pair_allocation': 0.05,  # 5% min in single pair
            'rebalance_threshold': 0.1,  # 10% deviation triggers rebalance
            'correlation_lookback_days': 30,
            'volatility_lookback_days': 20,
            'risk_free_rate': 0.02,  # 2% annual risk-free rate
            'target_volatility': 0.15,  # 15% annual volatility target
            'max_portfolio_var': 0.05,  # 5% daily VaR limit
            'rebalance_frequency_hours': 6,
            'opportunity_decay_hours': 2,  # How long opportunities remain valid
        }
        
        if config:
            self.config.update(config)
        
        # Portfolio state
        self.positions: Dict[str, PortfolioPosition] = {}
        self.total_capital: float = 0.0
        self.available_capital: float = 0.0
        self.portfolio_metrics: Optional[PortfolioMetrics] = None
        
        # Opportunity tracking
        self.opportunities: Dict[str, OpportunityScore] = {}
        self.last_rebalance: datetime = datetime.now()
        
        # Correlation matrix and risk models
        self.correlation_matrix: Optional[pd.DataFrame] = None
        self.volatility_estimates: Dict[str, float] = {}
        self.last_correlation_update: datetime = datetime.now()
        
        # Performance tracking
        self.performance_history: List[PortfolioMetrics] = []
        self.rebalance_history: List[Dict[str, Any]] = []
        
        self.logger.info("Portfolio optimizer initialized")
    
    def update_portfolio_state(self, 
                             positions: Dict[str, PortfolioPosition],
                             total_capital: float,
                             available_capital: float):
        """Update the current portfolio state."""
        self.positions = positions.copy()
        self.total_capital = total_capital
        self.available_capital = available_capital
        
        # Calculate portfolio metrics
        self.portfolio_metrics = self._calculate_portfolio_metrics()
        
        self.logger.debug(f"Portfolio state updated: {len(positions)} positions, "
                         f"${total_capital:,.2f} total capital")
    
    def add_opportunity(self, signal: AdaptiveSignal, market_data: pd.DataFrame) -> OpportunityScore:
        """
        Add a trading opportunity for consideration.
        
        Args:
            signal: Adaptive trading signal
            market_data: Market data for the pair
            
        Returns:
            OpportunityScore: Scored opportunity
        """
        # Calculate opportunity strength based on signal confidence and strength
        opportunity_strength = signal.confidence * signal.strength.value
        
        # Calculate risk-adjusted return estimate
        volatility = self._estimate_volatility(market_data)
        expected_return = self._estimate_expected_return(signal, market_data)
        risk_adjusted_return = expected_return / max(volatility, 0.01)  # Avoid division by zero
        
        # Calculate correlation penalty
        correlation_penalty = self._calculate_correlation_penalty(signal.pair)
        
        # Calculate regime bonus
        regime_bonus = self._calculate_regime_bonus(signal.regime_context)
        
        # Create opportunity score
        opportunity = OpportunityScore(
            pair=signal.pair,
            signal=signal,
            opportunity_strength=opportunity_strength,
            risk_adjusted_return=risk_adjusted_return,
            correlation_penalty=correlation_penalty,
            regime_bonus=regime_bonus,
            final_score=0.0
        )
        
        # Calculate final score
        opportunity.calculate_final_score()
        
        # Store opportunity
        self.opportunities[signal.pair] = opportunity
        
        self.logger.debug(f"Added opportunity for {signal.pair}: score={opportunity.final_score:.3f}")
        
        return opportunity
    
    def optimize_capital_allocation(self, 
                                  opportunities: Optional[Dict[str, OpportunityScore]] = None) -> Dict[str, float]:
        """
        Optimize capital allocation across trading pairs.
        
        Args:
            opportunities: Optional dictionary of opportunities to consider
            
        Returns:
            Dict[str, float]: Optimal allocation percentages by pair
        """
        if opportunities is None:
            opportunities = self.opportunities
        
        if not opportunities:
            self.logger.warning("No opportunities available for allocation optimization")
            return {}
        
        # Filter valid opportunities
        valid_opportunities = {
            pair: opp for pair, opp in opportunities.items()
            if opp.final_score > 0.1  # Minimum score threshold
        }
        
        if not valid_opportunities:
            self.logger.warning("No valid opportunities meet minimum score threshold")
            return {}
        
        # Sort opportunities by score
        sorted_opportunities = sorted(
            valid_opportunities.items(),
            key=lambda x: x[1].final_score,
            reverse=True
        )
        
        # Apply portfolio optimization
        if len(sorted_opportunities) == 1:
            # Single opportunity - allocate up to max single pair allocation
            pair, opportunity = sorted_opportunities[0]
            allocation = min(self.config['max_single_pair_allocation'], 
                           opportunity.final_score)
            return {pair: allocation}
        
        # Multiple opportunities - use mean-variance optimization
        allocations = self._mean_variance_optimization(sorted_opportunities)
        
        # Apply allocation constraints
        allocations = self._apply_allocation_constraints(allocations)
        
        self.logger.info(f"Optimized allocation for {len(allocations)} pairs")
        
        return allocations
    
    def _mean_variance_optimization(self, 
                                  opportunities: List[Tuple[str, OpportunityScore]]) -> Dict[str, float]:
        """
        Apply mean-variance optimization for capital allocation.
        
        Args:
            opportunities: List of (pair, opportunity) tuples
            
        Returns:
            Dict[str, float]: Allocation percentages
        """
        pairs = [pair for pair, _ in opportunities]
        scores = np.array([opp.final_score for _, opp in opportunities])
        
        # Get correlation matrix for these pairs
        correlation_matrix = self._get_correlation_matrix(pairs)
        
        # Estimate expected returns (use opportunity scores as proxy)
        expected_returns = scores
        
        # Estimate volatilities
        volatilities = np.array([
            self.volatility_estimates.get(pair, 0.2) for pair in pairs
        ])
        
        # Create covariance matrix
        cov_matrix = np.outer(volatilities, volatilities) * correlation_matrix
        
        # Mean-variance optimization with constraints
        try:
            # Simple equal-risk-contribution approach
            risk_contributions = 1.0 / np.diag(cov_matrix)
            risk_contributions = risk_contributions / np.sum(risk_contributions)
            
            # Adjust by opportunity scores
            score_weights = scores / np.sum(scores)
            
            # Combine risk and score weights
            weights = 0.6 * score_weights + 0.4 * risk_contributions
            weights = weights / np.sum(weights)
            
            # Convert to dictionary
            allocations = {pair: weight for pair, weight in zip(pairs, weights)}
            
        except Exception as e:
            self.logger.warning(f"Mean-variance optimization failed: {e}, using score-based allocation")
            # Fallback to score-based allocation
            total_score = sum(scores)
            allocations = {
                pair: score / total_score 
                for (pair, _), score in zip(opportunities, scores)
            }
        
        return allocations
    
    def _apply_allocation_constraints(self, allocations: Dict[str, float]) -> Dict[str, float]:
        """Apply allocation constraints and normalize."""
        constrained_allocations = {}
        
        for pair, allocation in allocations.items():
            # Apply min/max constraints
            constrained_allocation = max(
                self.config['min_single_pair_allocation'],
                min(self.config['max_single_pair_allocation'], allocation)
            )
            constrained_allocations[pair] = constrained_allocation
        
        # Normalize to sum to 1.0
        total_allocation = sum(constrained_allocations.values())
        if total_allocation > 0:
            constrained_allocations = {
                pair: allocation / total_allocation
                for pair, allocation in constrained_allocations.items()
            }
        
        return constrained_allocations
    
    def should_rebalance(self) -> bool:
        """
        Determine if portfolio should be rebalanced.
        
        Returns:
            bool: True if rebalancing is needed
        """
        # Check time since last rebalance
        time_since_rebalance = datetime.now() - self.last_rebalance
        if time_since_rebalance < timedelta(hours=self.config['rebalance_frequency_hours']):
            return False
        
        if not self.positions or not self.portfolio_metrics:
            return False
        
        # Check allocation drift
        current_allocations = {
            pair: pos.allocation_percentage 
            for pair, pos in self.positions.items()
        }
        
        # Get optimal allocations
        optimal_allocations = self.optimize_capital_allocation()
        
        # Calculate allocation drift
        max_drift = 0.0
        for pair in set(current_allocations.keys()) | set(optimal_allocations.keys()):
            current = current_allocations.get(pair, 0.0)
            optimal = optimal_allocations.get(pair, 0.0)
            drift = abs(current - optimal)
            max_drift = max(max_drift, drift)
        
        should_rebalance = max_drift > self.config['rebalance_threshold']
        
        if should_rebalance:
            self.logger.info(f"Rebalancing triggered: max drift {max_drift:.3f} > threshold {self.config['rebalance_threshold']}")
        
        return should_rebalance
    
    def generate_rebalancing_orders(self) -> List[Dict[str, Any]]:
        """
        Generate orders needed for portfolio rebalancing.
        
        Returns:
            List[Dict]: List of rebalancing orders
        """
        if not self.should_rebalance():
            return []
        
        # Get optimal allocations
        optimal_allocations = self.optimize_capital_allocation()
        
        if not optimal_allocations:
            return []
        
        orders = []
        
        # Calculate target position sizes
        for pair, target_allocation in optimal_allocations.items():
            target_size = target_allocation * self.total_capital
            current_position = self.positions.get(pair)
            current_size = current_position.market_value if current_position else 0.0
            
            size_difference = target_size - current_size
            
            # Only create orders for significant differences
            if abs(size_difference) > self.total_capital * 0.01:  # 1% threshold
                order_type = "buy" if size_difference > 0 else "sell"
                
                orders.append({
                    'pair': pair,
                    'type': order_type,
                    'size': abs(size_difference),
                    'reason': 'portfolio_rebalancing',
                    'target_allocation': target_allocation,
                    'current_allocation': current_position.allocation_percentage if current_position else 0.0
                })
        
        # Handle positions that should be closed (not in optimal allocation)
        for pair, position in self.positions.items():
            if pair not in optimal_allocations and position.market_value > 0:
                orders.append({
                    'pair': pair,
                    'type': 'sell',
                    'size': position.market_value,
                    'reason': 'position_closure',
                    'target_allocation': 0.0,
                    'current_allocation': position.allocation_percentage
                })
        
        if orders:
            self.last_rebalance = datetime.now()
            self.rebalance_history.append({
                'timestamp': datetime.now(),
                'orders': orders,
                'trigger_reason': 'allocation_drift'
            })
            
            self.logger.info(f"Generated {len(orders)} rebalancing orders")
        
        return orders
    
    def calculate_correlation_risk(self) -> float:
        """Calculate portfolio correlation risk."""
        if len(self.positions) < 2:
            return 0.0
        
        pairs = list(self.positions.keys())
        weights = np.array([pos.allocation_percentage for pos in self.positions.values()])
        
        correlation_matrix = self._get_correlation_matrix(pairs)
        
        # Calculate weighted average correlation
        weighted_correlation = 0.0
        total_weight = 0.0
        
        for i, pair1 in enumerate(pairs):
            for j, pair2 in enumerate(pairs):
                if i != j:
                    correlation = correlation_matrix.iloc[i, j] if correlation_matrix is not None else 0.5
                    weight = weights[i] * weights[j]
                    weighted_correlation += correlation * weight
                    total_weight += weight
        
        if total_weight > 0:
            weighted_correlation /= total_weight
        
        return max(0.0, weighted_correlation)
    
    def _calculate_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate comprehensive portfolio metrics."""
        if not self.positions:
            return PortfolioMetrics(
                total_value=self.total_capital,
                total_pnl=0.0,
                total_return_pct=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                volatility=0.0,
                var_95=0.0,
                expected_shortfall=0.0,
                correlation_risk=0.0,
                concentration_risk=0.0
            )
        
        # Basic metrics
        total_value = sum(pos.market_value for pos in self.positions.values())
        total_pnl = sum(pos.unrealized_pnl + pos.realized_pnl for pos in self.positions.values())
        total_return_pct = total_pnl / self.total_capital if self.total_capital > 0 else 0.0
        
        # Risk metrics
        correlation_risk = self.calculate_correlation_risk()
        concentration_risk = self._calculate_concentration_risk()
        
        # Allocation metrics
        pair_allocations = {
            pair: pos.allocation_percentage 
            for pair, pos in self.positions.items()
        }
        
        # Regime exposure (simplified)
        regime_exposure = defaultdict(float)
        for pos in self.positions.values():
            # This would need regime information for each position
            regime_exposure[RegimeType.UNCERTAIN] += pos.allocation_percentage
        
        return PortfolioMetrics(
            total_value=total_value,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            sharpe_ratio=0.0,  # Would need historical returns to calculate
            max_drawdown=0.0,  # Would need historical equity curve
            volatility=0.0,    # Would need historical returns
            var_95=0.0,        # Would need return distribution
            expected_shortfall=0.0,
            correlation_risk=correlation_risk,
            concentration_risk=concentration_risk,
            pair_allocations=pair_allocations,
            regime_exposure=dict(regime_exposure)
        )
    
    def _calculate_concentration_risk(self) -> float:
        """Calculate portfolio concentration risk using Herfindahl index."""
        if not self.positions:
            return 0.0
        
        allocations = [pos.allocation_percentage for pos in self.positions.values()]
        herfindahl_index = sum(allocation ** 2 for allocation in allocations)
        
        # Normalize to 0-1 scale (1 = maximum concentration, 0 = perfect diversification)
        n_positions = len(self.positions)
        min_herfindahl = 1.0 / n_positions  # Perfect diversification
        max_herfindahl = 1.0  # All in one position
        
        if max_herfindahl > min_herfindahl:
            concentration_risk = (herfindahl_index - min_herfindahl) / (max_herfindahl - min_herfindahl)
        else:
            concentration_risk = 0.0
        
        return max(0.0, min(1.0, concentration_risk))
    
    def _estimate_volatility(self, market_data: pd.DataFrame) -> float:
        """Estimate volatility from market data."""
        if market_data is None or market_data.empty:
            return 0.2  # Default volatility
        
        if 'close' not in market_data.columns:
            return 0.2
        
        returns = market_data['close'].pct_change().dropna()
        if len(returns) < 2:
            return 0.2
        
        # Annualized volatility (assuming 5-minute data)
        volatility = returns.std() * np.sqrt(365 * 24 * 12)  # 5-min periods per year
        return max(0.01, min(2.0, volatility))  # Clamp between 1% and 200%
    
    def _estimate_expected_return(self, signal: AdaptiveSignal, market_data: pd.DataFrame) -> float:
        """Estimate expected return from signal."""
        # Simple heuristic based on signal strength and confidence
        base_return = signal.confidence * signal.strength.value * 0.02  # Up to 2% expected return
        
        # Adjust based on regime
        regime_multiplier = {
            RegimeType.TRENDING_BULL: 1.2,
            RegimeType.TRENDING_BEAR: 0.8,
            RegimeType.RANGING: 1.0,
            RegimeType.HIGH_VOLATILITY: 1.1,
            RegimeType.LOW_VOLATILITY: 0.9,
            RegimeType.UNCERTAIN: 0.7
        }.get(signal.regime_context.regime_type, 1.0)
        
        return base_return * regime_multiplier
    
    def _calculate_correlation_penalty(self, pair: str) -> float:
        """Calculate correlation penalty for a pair."""
        if not self.positions:
            return 0.0
        
        # Get correlations with existing positions
        correlations = []
        for existing_pair, position in self.positions.items():
            if existing_pair != pair:
                correlation = self._get_pair_correlation(pair, existing_pair)
                # Weight by position size
                weighted_correlation = correlation * position.allocation_percentage
                correlations.append(weighted_correlation)
        
        if not correlations:
            return 0.0
        
        # Average weighted correlation
        avg_correlation = sum(correlations) / len(correlations)
        
        # Convert to penalty (higher correlation = higher penalty)
        penalty = max(0.0, (avg_correlation - 0.3) / 0.7)  # Penalty starts at 30% correlation
        
        return min(1.0, penalty)
    
    def _calculate_regime_bonus(self, regime: MarketRegime) -> float:
        """Calculate regime bonus based on market conditions."""
        # Bonus based on regime confidence and favorability
        regime_favorability = {
            RegimeType.TRENDING_BULL: 0.8,
            RegimeType.TRENDING_BEAR: 0.6,
            RegimeType.RANGING: 0.5,
            RegimeType.HIGH_VOLATILITY: 0.7,
            RegimeType.LOW_VOLATILITY: 0.4,
            RegimeType.UNCERTAIN: 0.2
        }.get(regime.regime_type, 0.5)
        
        return regime.confidence * regime_favorability
    
    def _get_correlation_matrix(self, pairs: List[str]) -> Optional[pd.DataFrame]:
        """Get correlation matrix for given pairs."""
        if self.correlation_matrix is None:
            # Create identity matrix as fallback
            return pd.DataFrame(
                np.eye(len(pairs)),
                index=pairs,
                columns=pairs
            )
        
        # Filter correlation matrix for requested pairs
        available_pairs = [pair for pair in pairs if pair in self.correlation_matrix.index]
        
        if not available_pairs:
            return pd.DataFrame(
                np.eye(len(pairs)),
                index=pairs,
                columns=pairs
            )
        
        return self.correlation_matrix.loc[available_pairs, available_pairs]
    
    def _get_pair_correlation(self, pair1: str, pair2: str) -> float:
        """Get correlation between two pairs."""
        if self.correlation_matrix is None:
            return 0.5  # Default moderate correlation
        
        if pair1 in self.correlation_matrix.index and pair2 in self.correlation_matrix.columns:
            return self.correlation_matrix.loc[pair1, pair2]
        
        return 0.5  # Default
    
    def update_correlation_matrix(self, market_data: Dict[str, pd.DataFrame]):
        """Update correlation matrix from market data."""
        if not market_data:
            return
        
        try:
            # Calculate returns for each pair
            returns_data = {}
            for pair, data in market_data.items():
                if 'close' in data.columns and len(data) > 1:
                    returns = data['close'].pct_change().dropna()
                    if len(returns) > 0:
                        returns_data[pair] = returns
            
            if len(returns_data) < 2:
                return
            
            # Align returns data
            returns_df = pd.DataFrame(returns_data)
            returns_df = returns_df.dropna()
            
            if len(returns_df) < 10:  # Need minimum data points
                return
            
            # Calculate correlation matrix
            self.correlation_matrix = returns_df.corr()
            self.last_correlation_update = datetime.now()
            
            self.logger.debug(f"Updated correlation matrix for {len(returns_data)} pairs")
            
        except Exception as e:
            self.logger.error(f"Error updating correlation matrix: {e}")
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary for monitoring."""
        if not self.portfolio_metrics:
            return {}
        
        return {
            'total_value': self.portfolio_metrics.total_value,
            'total_pnl': self.portfolio_metrics.total_pnl,
            'return_pct': self.portfolio_metrics.total_return_pct,
            'num_positions': len(self.positions),
            'correlation_risk': self.portfolio_metrics.correlation_risk,
            'concentration_risk': self.portfolio_metrics.concentration_risk,
            'largest_position': max(
                (pos.allocation_percentage for pos in self.positions.values()),
                default=0.0
            ),
            'opportunities_count': len(self.opportunities),
            'last_rebalance': self.last_rebalance.isoformat(),
            'should_rebalance': self.should_rebalance()
        }
    
    def cleanup_expired_opportunities(self):
        """Remove expired opportunities."""
        current_time = datetime.now()
        expired_pairs = []
        
        for pair, opportunity in self.opportunities.items():
            time_since_signal = current_time - opportunity.signal.timestamp
            if time_since_signal > timedelta(hours=self.config['opportunity_decay_hours']):
                expired_pairs.append(pair)
        
        for pair in expired_pairs:
            del self.opportunities[pair]
        
        if expired_pairs:
            self.logger.debug(f"Cleaned up {len(expired_pairs)} expired opportunities")