"""
Unit tests for the portfolio optimizer.

Tests portfolio-level optimization, capital allocation, correlation-aware
position management, and portfolio rebalancing functionality.
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from bot.adaptive.portfolio_optimizer import (
    PortfolioOptimizer, PortfolioPosition, OpportunityScore, PortfolioMetrics
)
from bot.adaptive.data_models import MarketRegime, AdaptiveSignal
from bot.adaptive.enums import RegimeType, SignalStrength


class TestPortfolioOptimizer:
    """Test the portfolio optimizer functionality."""
    
    @pytest.fixture
    def optimizer_config(self):
        """Create test configuration for portfolio optimizer."""
        return {
            'max_pairs': 5,
            'max_correlation': 0.7,
            'max_single_pair_allocation': 0.4,
            'min_single_pair_allocation': 0.05,
            'rebalance_threshold': 0.1,
            'correlation_lookback_days': 30,
            'target_volatility': 0.15,
            'rebalance_frequency_hours': 6
        }
    
    @pytest.fixture
    def portfolio_optimizer(self, optimizer_config):
        """Create portfolio optimizer instance."""
        return PortfolioOptimizer(optimizer_config)
    
    @pytest.fixture
    def sample_positions(self):
        """Create sample portfolio positions."""
        return {
            'BTC/USD': PortfolioPosition(
                pair='BTC/USD',
                size=1000.0,
                entry_price=45000.0,
                current_price=46000.0,
                unrealized_pnl=100.0,
                realized_pnl=50.0,
                allocation_percentage=0.5,
                risk_contribution=0.3
            ),
            'ETH/USD': PortfolioPosition(
                pair='ETH/USD',
                size=800.0,
                entry_price=3000.0,
                current_price=3100.0,
                unrealized_pnl=80.0,
                realized_pnl=20.0,
                allocation_percentage=0.3,
                risk_contribution=0.2
            )
        }
    
    @pytest.fixture
    def sample_market_data(self):
        """Create sample market data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
        return pd.DataFrame({
            'timestamp': dates,
            'open': np.random.uniform(40000, 45000, 100),
            'high': np.random.uniform(45000, 50000, 100),
            'low': np.random.uniform(35000, 40000, 100),
            'close': np.random.uniform(40000, 45000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        })
    
    @pytest.fixture
    def sample_signal(self):
        """Create sample adaptive signal."""
        return AdaptiveSignal(
            pair="BTC/USD",
            signal_type="buy",
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=45000.0,
            timestamp=datetime.now(),
            regime_context=MarketRegime(
                regime_type=RegimeType.TRENDING_BULL,
                confidence=0.8,
                volatility_level=0.6,
                trend_strength=0.7,
                momentum=0.5,
                detected_at=datetime.now()
            ),
            ml_confidence=0.75,
            strategy_weights={'momentum': 0.6, 'mean_reversion': 0.4}
        )
    
    def test_portfolio_optimizer_initialization(self, optimizer_config):
        """Test portfolio optimizer initialization."""
        optimizer = PortfolioOptimizer(optimizer_config)
        
        assert optimizer.config['max_pairs'] == 5
        assert optimizer.config['max_correlation'] == 0.7
        assert optimizer.total_capital == 0.0
        assert optimizer.available_capital == 0.0
        assert len(optimizer.positions) == 0
        assert len(optimizer.opportunities) == 0
    
    def test_update_portfolio_state(self, portfolio_optimizer, sample_positions):
        """Test updating portfolio state."""
        total_capital = 10000.0
        available_capital = 2000.0
        
        portfolio_optimizer.update_portfolio_state(
            sample_positions, total_capital, available_capital
        )
        
        assert portfolio_optimizer.total_capital == total_capital
        assert portfolio_optimizer.available_capital == available_capital
        assert len(portfolio_optimizer.positions) == 2
        assert 'BTC/USD' in portfolio_optimizer.positions
        assert 'ETH/USD' in portfolio_optimizer.positions
        assert portfolio_optimizer.portfolio_metrics is not None
    
    def test_add_opportunity(self, portfolio_optimizer, sample_signal, sample_market_data):
        """Test adding trading opportunities."""
        opportunity = portfolio_optimizer.add_opportunity(sample_signal, sample_market_data)
        
        assert isinstance(opportunity, OpportunityScore)
        assert opportunity.pair == "BTC/USD"
        assert opportunity.signal == sample_signal
        assert 0.0 <= opportunity.final_score <= 1.0
        assert opportunity.opportunity_strength > 0
        assert "BTC/USD" in portfolio_optimizer.opportunities
    
    def test_opportunity_scoring(self, portfolio_optimizer, sample_signal, sample_market_data):
        """Test opportunity scoring calculation."""
        opportunity = portfolio_optimizer.add_opportunity(sample_signal, sample_market_data)
        
        # Test that final score is calculated
        assert opportunity.final_score > 0
        
        # Test score components
        assert 0.0 <= opportunity.opportunity_strength <= 1.0
        assert opportunity.risk_adjusted_return != 0
        assert 0.0 <= opportunity.correlation_penalty <= 1.0
        assert 0.0 <= opportunity.regime_bonus <= 1.0
        
        # Test manual score calculation
        manual_score = opportunity.calculate_final_score()
        assert manual_score == opportunity.final_score
    
    def test_capital_allocation_optimization_single_opportunity(self, portfolio_optimizer, sample_signal, sample_market_data):
        """Test capital allocation with single opportunity."""
        # Add single opportunity
        portfolio_optimizer.add_opportunity(sample_signal, sample_market_data)
        
        # Optimize allocation
        allocations = portfolio_optimizer.optimize_capital_allocation()
        
        assert len(allocations) == 1
        assert "BTC/USD" in allocations
        assert 0.0 < allocations["BTC/USD"] <= portfolio_optimizer.config['max_single_pair_allocation']
    
    def test_capital_allocation_optimization_multiple_opportunities(self, portfolio_optimizer, sample_market_data):
        """Test capital allocation with multiple opportunities."""
        # Create multiple signals
        signals = []
        for i, pair in enumerate(['BTC/USD', 'ETH/USD', 'SOL/USD']):
            signal = AdaptiveSignal(
                pair=pair,
                signal_type="buy",
                strength=SignalStrength.STRONG,
                confidence=0.7 + i * 0.1,  # Different confidences
                price=1000.0 * (i + 1),
                timestamp=datetime.now(),
                regime_context=MarketRegime(
                    regime_type=RegimeType.TRENDING_BULL,
                    confidence=0.8,
                    volatility_level=0.6,
                    trend_strength=0.7,
                    momentum=0.5,
                    detected_at=datetime.now()
                ),
                ml_confidence=0.75,
                strategy_weights={'momentum': 0.6}
            )
            signals.append(signal)
            portfolio_optimizer.add_opportunity(signal, sample_market_data)
        
        # Optimize allocation
        allocations = portfolio_optimizer.optimize_capital_allocation()
        
        assert len(allocations) <= 3
        assert all(0.0 < allocation <= portfolio_optimizer.config['max_single_pair_allocation'] 
                  for allocation in allocations.values())
        
        # Test that allocations sum to reasonable total
        total_allocation = sum(allocations.values())
        assert 0.0 < total_allocation <= 1.0
    
    def test_allocation_constraints(self, portfolio_optimizer):
        """Test allocation constraint application."""
        # Test with allocations that violate constraints
        test_allocations = {
            'BTC/USD': 0.6,  # Above max
            'ETH/USD': 0.02,  # Below min
            'SOL/USD': 0.3
        }
        
        constrained = portfolio_optimizer._apply_allocation_constraints(test_allocations)
        
        assert constrained['BTC/USD'] <= portfolio_optimizer.config['max_single_pair_allocation']
        assert constrained['ETH/USD'] >= portfolio_optimizer.config['min_single_pair_allocation']
        
        # Test normalization
        total = sum(constrained.values())
        assert abs(total - 1.0) < 1e-6  # Should sum to 1.0
    
    def test_correlation_risk_calculation(self, portfolio_optimizer, sample_positions):
        """Test correlation risk calculation."""
        # Update portfolio with positions
        portfolio_optimizer.update_portfolio_state(sample_positions, 10000.0, 2000.0)
        
        # Mock correlation matrix
        correlation_matrix = pd.DataFrame(
            [[1.0, 0.6], [0.6, 1.0]],
            index=['BTC/USD', 'ETH/USD'],
            columns=['BTC/USD', 'ETH/USD']
        )
        portfolio_optimizer.correlation_matrix = correlation_matrix
        
        correlation_risk = portfolio_optimizer.calculate_correlation_risk()
        
        assert 0.0 <= correlation_risk <= 1.0
        assert correlation_risk > 0  # Should have some correlation risk
    
    def test_concentration_risk_calculation(self, portfolio_optimizer, sample_positions):
        """Test concentration risk calculation."""
        # Update portfolio with positions
        portfolio_optimizer.update_portfolio_state(sample_positions, 10000.0, 2000.0)
        
        concentration_risk = portfolio_optimizer._calculate_concentration_risk()
        
        assert 0.0 <= concentration_risk <= 1.0
        
        # Test with single position (maximum concentration)
        single_position = {'BTC/USD': sample_positions['BTC/USD']}
        single_position['BTC/USD'].allocation_percentage = 1.0
        
        portfolio_optimizer.positions = single_position
        max_concentration = portfolio_optimizer._calculate_concentration_risk()
        assert max_concentration > concentration_risk
    
    def test_rebalancing_decision(self, portfolio_optimizer, sample_positions):
        """Test rebalancing decision logic."""
        # Set up portfolio
        portfolio_optimizer.update_portfolio_state(sample_positions, 10000.0, 2000.0)
        
        # Test time-based rebalancing prevention
        portfolio_optimizer.last_rebalance = datetime.now()
        assert not portfolio_optimizer.should_rebalance()
        
        # Test with old rebalance time
        portfolio_optimizer.last_rebalance = datetime.now() - timedelta(hours=12)
        
        # Mock optimal allocations that differ from current
        with patch.object(portfolio_optimizer, 'optimize_capital_allocation') as mock_optimize:
            mock_optimize.return_value = {
                'BTC/USD': 0.3,  # Different from current 0.5
                'ETH/USD': 0.7   # Different from current 0.3
            }
            
            should_rebalance = portfolio_optimizer.should_rebalance()
            assert should_rebalance  # Should trigger due to allocation drift
    
    def test_rebalancing_orders_generation(self, portfolio_optimizer, sample_positions):
        """Test generation of rebalancing orders."""
        # Set up portfolio
        portfolio_optimizer.update_portfolio_state(sample_positions, 10000.0, 2000.0)
        portfolio_optimizer.last_rebalance = datetime.now() - timedelta(hours=12)
        
        # Mock should_rebalance to return True
        with patch.object(portfolio_optimizer, 'should_rebalance', return_value=True):
            with patch.object(portfolio_optimizer, 'optimize_capital_allocation') as mock_optimize:
                mock_optimize.return_value = {
                    'BTC/USD': 0.3,  # Reduce from 0.5
                    'ETH/USD': 0.7   # Increase from 0.3
                }
                
                orders = portfolio_optimizer.generate_rebalancing_orders()
                
                assert len(orders) > 0
                assert all('pair' in order for order in orders)
                assert all('type' in order for order in orders)
                assert all('size' in order for order in orders)
                assert all(order['type'] in ['buy', 'sell'] for order in orders)
    
    def test_portfolio_metrics_calculation(self, portfolio_optimizer, sample_positions):
        """Test portfolio metrics calculation."""
        portfolio_optimizer.update_portfolio_state(sample_positions, 10000.0, 2000.0)
        
        metrics = portfolio_optimizer.portfolio_metrics
        
        assert isinstance(metrics, PortfolioMetrics)
        assert metrics.total_value > 0
        assert metrics.total_pnl != 0  # Should have some P&L from sample positions
        assert -1.0 <= metrics.total_return_pct <= 1.0
        assert 0.0 <= metrics.correlation_risk <= 1.0
        assert 0.0 <= metrics.concentration_risk <= 1.0
        assert len(metrics.pair_allocations) == 2
    
    def test_volatility_estimation(self, portfolio_optimizer, sample_market_data):
        """Test volatility estimation from market data."""
        volatility = portfolio_optimizer._estimate_volatility(sample_market_data)
        
        assert volatility > 0
        assert 0.01 <= volatility <= 2.0  # Within reasonable bounds
        
        # Test with empty data
        empty_data = pd.DataFrame()
        default_vol = portfolio_optimizer._estimate_volatility(empty_data)
        assert default_vol == 0.2  # Default volatility
    
    def test_expected_return_estimation(self, portfolio_optimizer, sample_signal, sample_market_data):
        """Test expected return estimation."""
        expected_return = portfolio_optimizer._estimate_expected_return(sample_signal, sample_market_data)
        
        assert expected_return > 0  # Should be positive for buy signal with good confidence
        assert expected_return <= 0.1  # Should be reasonable (<=10%)
        
        # Test with different regime
        sample_signal.regime_context.regime_type = RegimeType.TRENDING_BEAR
        bear_return = portfolio_optimizer._estimate_expected_return(sample_signal, sample_market_data)
        assert bear_return < expected_return  # Should be lower in bear market
    
    def test_correlation_penalty_calculation(self, portfolio_optimizer, sample_positions):
        """Test correlation penalty calculation."""
        # Set up portfolio with positions
        portfolio_optimizer.update_portfolio_state(sample_positions, 10000.0, 2000.0)
        
        # Mock correlation matrix
        correlation_matrix = pd.DataFrame(
            [[1.0, 0.8, 0.3], [0.8, 1.0, 0.4], [0.3, 0.4, 1.0]],
            index=['BTC/USD', 'ETH/USD', 'SOL/USD'],
            columns=['BTC/USD', 'ETH/USD', 'SOL/USD']
        )
        portfolio_optimizer.correlation_matrix = correlation_matrix
        
        # Test penalty for highly correlated pair
        penalty_sol = portfolio_optimizer._calculate_correlation_penalty('SOL/USD')
        assert 0.0 <= penalty_sol <= 1.0
        
        # Test penalty for new uncorrelated pair
        penalty_new = portfolio_optimizer._calculate_correlation_penalty('AAPL/USD')
        assert penalty_new == 0.0  # No existing positions to correlate with initially
    
    def test_regime_bonus_calculation(self, portfolio_optimizer):
        """Test regime bonus calculation."""
        # Test different regimes
        bull_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.9,
            volatility_level=0.5,
            trend_strength=0.8,
            momentum=0.7,
            detected_at=datetime.now()
        )
        
        bear_regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BEAR,
            confidence=0.9,
            volatility_level=0.5,
            trend_strength=-0.8,
            momentum=-0.7,
            detected_at=datetime.now()
        )
        
        uncertain_regime = MarketRegime(
            regime_type=RegimeType.UNCERTAIN,
            confidence=0.3,
            volatility_level=0.8,
            trend_strength=0.0,
            momentum=0.0,
            detected_at=datetime.now()
        )
        
        bull_bonus = portfolio_optimizer._calculate_regime_bonus(bull_regime)
        bear_bonus = portfolio_optimizer._calculate_regime_bonus(bear_regime)
        uncertain_bonus = portfolio_optimizer._calculate_regime_bonus(uncertain_regime)
        
        assert bull_bonus > bear_bonus  # Bull should have higher bonus
        assert bull_bonus > uncertain_bonus  # Bull should have higher bonus than uncertain
        assert all(0.0 <= bonus <= 1.0 for bonus in [bull_bonus, bear_bonus, uncertain_bonus])
    
    def test_correlation_matrix_update(self, portfolio_optimizer):
        """Test correlation matrix update from market data."""
        # Create market data for multiple pairs
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
        
        market_data = {
            'BTC/USD': pd.DataFrame({
                'close': np.random.normal(45000, 1000, 100)
            }),
            'ETH/USD': pd.DataFrame({
                'close': np.random.normal(3000, 100, 100)
            }),
            'SOL/USD': pd.DataFrame({
                'close': np.random.normal(100, 10, 100)
            })
        }
        
        portfolio_optimizer.update_correlation_matrix(market_data)
        
        assert portfolio_optimizer.correlation_matrix is not None
        assert portfolio_optimizer.correlation_matrix.shape == (3, 3)
        assert list(portfolio_optimizer.correlation_matrix.index) == ['BTC/USD', 'ETH/USD', 'SOL/USD']
        
        # Test diagonal elements are 1.0
        for pair in portfolio_optimizer.correlation_matrix.index:
            assert abs(portfolio_optimizer.correlation_matrix.loc[pair, pair] - 1.0) < 1e-6
    
    def test_opportunity_cleanup(self, portfolio_optimizer, sample_signal, sample_market_data):
        """Test cleanup of expired opportunities."""
        # Add opportunity
        portfolio_optimizer.add_opportunity(sample_signal, sample_market_data)
        assert len(portfolio_optimizer.opportunities) == 1
        
        # Mock old timestamp
        old_signal = sample_signal
        old_signal.timestamp = datetime.now() - timedelta(hours=5)  # Older than decay time
        portfolio_optimizer.opportunities['BTC/USD'].signal = old_signal
        
        # Cleanup
        portfolio_optimizer.cleanup_expired_opportunities()
        
        assert len(portfolio_optimizer.opportunities) == 0  # Should be cleaned up
    
    def test_portfolio_summary(self, portfolio_optimizer, sample_positions):
        """Test portfolio summary generation."""
        portfolio_optimizer.update_portfolio_state(sample_positions, 10000.0, 2000.0)
        
        summary = portfolio_optimizer.get_portfolio_summary()
        
        assert 'total_value' in summary
        assert 'total_pnl' in summary
        assert 'return_pct' in summary
        assert 'num_positions' in summary
        assert 'correlation_risk' in summary
        assert 'concentration_risk' in summary
        assert 'largest_position' in summary
        assert 'should_rebalance' in summary
        
        assert summary['num_positions'] == 2
        assert summary['total_value'] > 0


class TestPortfolioPosition:
    """Test the PortfolioPosition data class."""
    
    def test_portfolio_position_creation(self):
        """Test portfolio position creation and properties."""
        position = PortfolioPosition(
            pair='BTC/USD',
            size=1000.0,
            entry_price=45000.0,
            current_price=46000.0,
            unrealized_pnl=100.0,
            realized_pnl=50.0,
            allocation_percentage=0.3,
            risk_contribution=0.2
        )
        
        assert position.pair == 'BTC/USD'
        assert position.size == 1000.0
        assert position.market_value == 46000000.0  # size * current_price
        assert position.pnl_percentage == 0.15  # (100 + 50) / 1000
    
    def test_portfolio_position_zero_size(self):
        """Test portfolio position with zero size."""
        position = PortfolioPosition(
            pair='BTC/USD',
            size=0.0,
            entry_price=45000.0,
            current_price=46000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            allocation_percentage=0.0,
            risk_contribution=0.0
        )
        
        assert position.market_value == 0.0
        assert position.pnl_percentage == 0.0


class TestOpportunityScore:
    """Test the OpportunityScore data class."""
    
    def test_opportunity_score_calculation(self):
        """Test opportunity score calculation."""
        signal = AdaptiveSignal(
            pair="BTC/USD",
            signal_type="buy",
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=45000.0,
            timestamp=datetime.now(),
            regime_context=MarketRegime(
                regime_type=RegimeType.TRENDING_BULL,
                confidence=0.8,
                volatility_level=0.6,
                trend_strength=0.7,
                momentum=0.5,
                detected_at=datetime.now()
            ),
            ml_confidence=0.75
        )
        
        opportunity = OpportunityScore(
            pair="BTC/USD",
            signal=signal,
            opportunity_strength=0.8,
            risk_adjusted_return=0.15,
            correlation_penalty=0.2,
            regime_bonus=0.6,
            final_score=0.0
        )
        
        # Calculate final score
        final_score = opportunity.calculate_final_score()
        
        assert 0.0 <= final_score <= 1.0
        assert opportunity.final_score == final_score
        
        # Test with custom weights
        custom_score = opportunity.calculate_final_score(
            base_weight=0.5,
            risk_weight=0.3,
            correlation_weight=0.1,
            regime_weight=0.1
        )
        
        assert 0.0 <= custom_score <= 1.0
        assert custom_score != final_score  # Should be different with different weights


if __name__ == "__main__":
    pytest.main([__file__])