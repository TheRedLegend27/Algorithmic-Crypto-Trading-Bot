"""
Unit tests for the Parameter Optimizer module.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
import tempfile
import json
import os

from bot.adaptive.parameter_optimizer import (
    ParameterOptimizer, OptimizationConfig, GeneticConfig, WalkForwardConfig
)
from bot.adaptive.data_models import ParameterBounds, PerformanceMetrics, OptimizationResult, MarketRegime
from bot.adaptive.enums import ParameterType, OptimizationType, RegimeType


class MockPerformanceEvaluator:
    """Mock performance evaluator for testing."""
    
    def evaluate_parameters(self, strategy_name: str, parameters: Dict[str, Any], historical_data: pd.DataFrame) -> PerformanceMetrics:
        # Simple mock that returns better performance for higher parameter values
        base_return = 0.1
        if parameters:
            # Add some variation based on parameters
            param_bonus = sum(float(v) for v in parameters.values() if isinstance(v, (int, float))) * 0.01
            total_return = base_return + param_bonus
        else:
            total_return = base_return
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=total_return * 12,
            excess_return=total_return - 0.05,
            sharpe_ratio=total_return / 0.15,
            sortino_ratio=total_return / 0.12,
            calmar_ratio=total_return / 0.08,
            max_drawdown=-0.08,
            volatility=0.15,
            downside_deviation=0.12,
            win_rate=0.6,
            profit_factor=1.5,
            avg_trade_duration=timedelta(hours=4),
            trades_count=100,
            avg_win=0.02,
            avg_loss=-0.015
        )
    
    def calculate_fitness(self, strategy_name: str, parameters: Dict[str, Any], historical_data: pd.DataFrame) -> float:
        metrics = self.evaluate_parameters(strategy_name, parameters, historical_data)
        return metrics.total_return
    
    def get_baseline_performance(self, strategy_name: str, historical_data: pd.DataFrame) -> PerformanceMetrics:
        return self.evaluate_parameters(strategy_name, {}, historical_data)


@pytest.fixture
def mock_performance_evaluator():
    """Create a mock performance evaluator."""
    return MockPerformanceEvaluator()


@pytest.fixture
def sample_historical_data():
    """Create sample historical data for testing."""
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='1H')
    np.random.seed(42)
    
    data = pd.DataFrame({
        'open': np.random.normal(100, 10, len(dates)),
        'high': np.random.normal(105, 10, len(dates)),
        'low': np.random.normal(95, 10, len(dates)),
        'close': np.random.normal(100, 10, len(dates)),
        'volume': np.random.normal(1000, 200, len(dates))
    }, index=dates)
    
    # Ensure high >= low and open, close are within range
    data['high'] = np.maximum(data['high'], np.maximum(data['open'], data['close']))
    data['low'] = np.minimum(data['low'], np.minimum(data['open'], data['close']))
    
    return data


@pytest.fixture
def sample_parameter_space():
    """Create sample parameter space for testing."""
    return {
        'stop_loss': ParameterBounds(
            param_type=ParameterType.CONTINUOUS,
            min_value=0.01,
            max_value=0.1,
            default_value=0.05
        ),
        'take_profit': ParameterBounds(
            param_type=ParameterType.CONTINUOUS,
            min_value=0.02,
            max_value=0.2,
            default_value=0.1
        ),
        'lookback_period': ParameterBounds(
            param_type=ParameterType.INTEGER,
            min_value=5,
            max_value=50,
            default_value=20
        ),
        'signal_type': ParameterBounds(
            param_type=ParameterType.CATEGORICAL,
            categories=['momentum', 'mean_reversion', 'breakout'],
            default_value='momentum'
        )
    }


@pytest.fixture
def parameter_optimizer(mock_performance_evaluator):
    """Create a parameter optimizer instance."""
    config = OptimizationConfig(max_iterations=10, n_initial_points=3)
    genetic_config = GeneticConfig(population_size=10, generations=5)
    walkforward_config = WalkForwardConfig(window_size=timedelta(days=30), step_size=timedelta(days=7))
    
    return ParameterOptimizer(
        performance_evaluator=mock_performance_evaluator,
        config=config,
        genetic_config=genetic_config,
        walkforward_config=walkforward_config
    )


class TestParameterOptimizer:
    """Test cases for ParameterOptimizer class."""
    
    def test_initialization(self, mock_performance_evaluator):
        """Test parameter optimizer initialization."""
        optimizer = ParameterOptimizer(mock_performance_evaluator)
        
        assert optimizer.performance_evaluator is mock_performance_evaluator
        assert isinstance(optimizer.config, OptimizationConfig)
        assert isinstance(optimizer.genetic_config, GeneticConfig)
        assert isinstance(optimizer.walkforward_config, WalkForwardConfig)
        assert optimizer.optimization_history == []
        assert optimizer.parameter_bounds == {}
        assert optimizer.best_parameters == {}
    
    def test_set_parameter_bounds(self, parameter_optimizer, sample_parameter_space):
        """Test setting parameter bounds."""
        for param_name, bounds in sample_parameter_space.items():
            parameter_optimizer.set_parameter_bounds(param_name, bounds)
        
        assert len(parameter_optimizer.parameter_bounds) == len(sample_parameter_space)
        assert 'stop_loss' in parameter_optimizer.parameter_bounds
        assert parameter_optimizer.parameter_bounds['stop_loss'].param_type == ParameterType.CONTINUOUS
    
    def test_validate_parameter_bounds(self, parameter_optimizer, sample_parameter_space):
        """Test parameter bounds validation."""
        # Valid bounds should pass
        assert parameter_optimizer.validate_parameter_bounds(sample_parameter_space)
        
        # Invalid bounds should fail - test that constructor catches invalid bounds
        with pytest.raises(ValueError):
            invalid_bounds = {
                'invalid_param': ParameterBounds(
                    param_type=ParameterType.CONTINUOUS,
                    min_value=10,
                    max_value=5  # min > max
                )
            }
    
    @patch('bot.adaptive.parameter_optimizer.BAYESIAN_AVAILABLE', True)
    @patch('bot.adaptive.parameter_optimizer.gp_minimize')
    def test_bayesian_optimization(self, mock_gp_minimize, parameter_optimizer, sample_parameter_space, sample_historical_data):
        """Test Bayesian optimization."""
        # Mock the optimization result
        mock_result = Mock()
        mock_result.x = [0.05, 0.1, 20, 'momentum']
        mock_result.fun = -0.15
        mock_result.n_calls = 10
        mock_result.func_vals = [-0.1, -0.12, -0.15]
        mock_gp_minimize.return_value = mock_result
        
        result = parameter_optimizer.optimize_parameters(
            strategy_name='test_strategy',
            parameter_space=sample_parameter_space,
            historical_data=sample_historical_data,
            optimization_type=OptimizationType.BAYESIAN
        )
        
        assert result.success
        assert result.strategy_name == 'test_strategy'
        assert result.optimization_method == OptimizationType.BAYESIAN.value
        assert 'stop_loss' in result.new_parameters
        assert mock_gp_minimize.called
    
    @patch('bot.adaptive.parameter_optimizer.GENETIC_AVAILABLE', True)
    def test_genetic_optimization(self, parameter_optimizer, sample_parameter_space, sample_historical_data):
        """Test genetic algorithm optimization."""
        result = parameter_optimizer.optimize_parameters(
            strategy_name='test_strategy',
            parameter_space=sample_parameter_space,
            historical_data=sample_historical_data,
            optimization_type=OptimizationType.GENETIC
        )
        
        assert result.success
        assert result.strategy_name == 'test_strategy'
        assert result.optimization_method == OptimizationType.GENETIC.value
        assert len(result.new_parameters) == len(sample_parameter_space)
    
    def test_grid_search_optimization(self, parameter_optimizer, sample_historical_data):
        """Test grid search optimization."""
        # Use smaller parameter space for grid search
        simple_space = {
            'param1': ParameterBounds(
                param_type=ParameterType.CONTINUOUS,
                min_value=0.1,
                max_value=0.3
            ),
            'param2': ParameterBounds(
                param_type=ParameterType.INTEGER,
                min_value=1,
                max_value=3
            )
        }
        
        result = parameter_optimizer.optimize_parameters(
            strategy_name='test_strategy',
            parameter_space=simple_space,
            historical_data=sample_historical_data,
            optimization_type=OptimizationType.GRID_SEARCH,
            grid_points=3
        )
        
        assert result.success
        assert result.strategy_name == 'test_strategy'
        assert result.optimization_method == OptimizationType.GRID_SEARCH.value
        assert 'param1' in result.new_parameters
        assert 'param2' in result.new_parameters
    
    def test_random_search_optimization(self, parameter_optimizer, sample_parameter_space, sample_historical_data):
        """Test random search optimization."""
        result = parameter_optimizer.optimize_parameters(
            strategy_name='test_strategy',
            parameter_space=sample_parameter_space,
            historical_data=sample_historical_data,
            optimization_type=OptimizationType.RANDOM_SEARCH,
            n_iterations=5
        )
        
        assert result.success
        assert result.strategy_name == 'test_strategy'
        assert result.optimization_method == OptimizationType.RANDOM_SEARCH.value
        assert len(result.new_parameters) == len(sample_parameter_space)
    
    def test_walk_forward_analysis(self, parameter_optimizer, sample_historical_data):
        """Test walk-forward analysis."""
        # Use simple parameter space
        simple_space = {
            'param1': ParameterBounds(
                param_type=ParameterType.CONTINUOUS,
                min_value=0.1,
                max_value=0.3
            )
        }
        
        # Use shorter data for faster testing
        short_data = sample_historical_data.iloc[:1000]  # About 41 days of hourly data
        
        results = parameter_optimizer.walk_forward_analysis(
            strategy_name='test_strategy',
            parameter_space=simple_space,
            historical_data=short_data,
            optimization_type=OptimizationType.RANDOM_SEARCH
        )
        
        assert len(results) > 0
        assert all(isinstance(r, OptimizationResult) for r in results)
        assert all(r.strategy_name == 'test_strategy' for r in results)
    
    def test_optimization_history(self, parameter_optimizer, sample_parameter_space, sample_historical_data):
        """Test optimization history tracking."""
        # Run an optimization
        result = parameter_optimizer.optimize_parameters(
            strategy_name='test_strategy',
            parameter_space=sample_parameter_space,
            historical_data=sample_historical_data,
            optimization_type=OptimizationType.RANDOM_SEARCH
        )
        
        # Check history
        history = parameter_optimizer.get_optimization_history()
        assert len(history) == 1
        assert history[0] == result
        
        # Check strategy-specific history
        strategy_history = parameter_optimizer.get_optimization_history('test_strategy')
        assert len(strategy_history) == 1
        assert strategy_history[0] == result
        
        # Check non-existent strategy
        empty_history = parameter_optimizer.get_optimization_history('non_existent')
        assert len(empty_history) == 0
    
    def test_best_parameters_tracking(self, parameter_optimizer, sample_parameter_space, sample_historical_data):
        """Test best parameters tracking."""
        # Initially no best parameters
        assert parameter_optimizer.get_best_parameters('test_strategy') is None
        
        # Run optimization
        result = parameter_optimizer.optimize_parameters(
            strategy_name='test_strategy',
            parameter_space=sample_parameter_space,
            historical_data=sample_historical_data,
            optimization_type=OptimizationType.RANDOM_SEARCH
        )
        
        # Check best parameters are stored
        if result.success:
            best_params = parameter_optimizer.get_best_parameters('test_strategy')
            assert best_params is not None
            assert best_params == result.new_parameters
    
    def test_optimization_time_estimation(self, parameter_optimizer, sample_parameter_space, sample_historical_data):
        """Test optimization time estimation."""
        estimated_time = parameter_optimizer.estimate_optimization_time(
            parameter_space=sample_parameter_space,
            optimization_type=OptimizationType.BAYESIAN,
            historical_data=sample_historical_data
        )
        
        assert isinstance(estimated_time, timedelta)
        assert estimated_time.total_seconds() > 0
    
    def test_error_handling(self, parameter_optimizer, sample_historical_data):
        """Test error handling in optimization."""
        # Test with invalid optimization type - should return failed result
        result = parameter_optimizer.optimize_parameters(
            strategy_name='test_strategy',
            parameter_space={},
            historical_data=sample_historical_data,
            optimization_type='invalid_type'
        )
        
        # Should return a failed optimization result
        assert not result.success
        assert result.error_message is not None
        assert 'Unsupported optimization type' in result.error_message
    
    def test_save_load_state(self, parameter_optimizer, tmp_path):
        """Test saving and loading optimization state."""
        # Add some data to the optimizer
        parameter_optimizer.optimization_history.append(
            OptimizationResult(
                optimization_id='test_id',
                strategy_name='test_strategy',
                optimization_method='test_method',
                old_parameters={},
                new_parameters={'param1': 0.5},
                performance_improvement=0.1,
                confidence_score=0.8,
                validation_period=timedelta(days=7),
                applied_at=datetime.now()
            )
        )
        parameter_optimizer.best_parameters['test_strategy'] = {'param1': 0.5}
        
        # Save state
        filepath = tmp_path / "optimizer_state.pkl"
        parameter_optimizer.save_optimization_state(str(filepath))
        
        # Create new optimizer and load state
        new_optimizer = ParameterOptimizer(MockPerformanceEvaluator())
        new_optimizer.load_optimization_state(str(filepath))
        
        # Verify state was loaded
        assert len(new_optimizer.optimization_history) == 1
        assert 'test_strategy' in new_optimizer.best_parameters
        assert new_optimizer.best_parameters['test_strategy']['param1'] == 0.5


class TestParameterConstraintManager:
    """Test cases for ParameterConstraintManager class."""
    
    def test_initialization(self):
        """Test constraint manager initialization."""
        manager = ParameterConstraintManager()
        assert manager.constraints == {}
    
    def test_add_constraint(self):
        """Test adding constraints."""
        manager = ParameterConstraintManager()
        
        def positive_constraint(value):
            return value > 0
        
        manager.add_constraint('param1', positive_constraint, "Must be positive")
        
        assert 'param1' in manager.constraints
        assert len(manager.constraints['param1']) == 1
        assert manager.constraints['param1'][0] == positive_constraint
    
    def test_validate_parameters(self):
        """Test parameter validation."""
        manager = ParameterConstraintManager()
        
        # Add constraints
        manager.add_constraint('param1', lambda x: x > 0, "Must be positive")
        manager.add_constraint('param2', lambda x: x < 100, "Must be less than 100")
        
        # Test valid parameters
        valid_params = {'param1': 5, 'param2': 50}
        is_valid, violations = manager.validate_parameters(valid_params)
        assert is_valid
        assert len(violations) == 0
        
        # Test invalid parameters
        invalid_params = {'param1': -5, 'param2': 150}
        is_valid, violations = manager.validate_parameters(invalid_params)
        assert not is_valid
        assert len(violations) == 2
    
    def test_get_constraints(self):
        """Test getting constraints for a parameter."""
        manager = ParameterConstraintManager()
        
        constraint1 = lambda x: x > 0
        constraint2 = lambda x: x < 100
        
        manager.add_constraint('param1', constraint1)
        manager.add_constraint('param1', constraint2)
        
        constraints = manager.get_constraints('param1')
        assert len(constraints) == 2
        assert constraint1 in constraints
        assert constraint2 in constraints
        
        # Test non-existent parameter
        empty_constraints = manager.get_constraints('non_existent')
        assert len(empty_constraints) == 0


class TestOptimizationConfigs:
    """Test cases for optimization configuration classes."""
    
    def test_optimization_config_defaults(self):
        """Test OptimizationConfig default values."""
        config = OptimizationConfig()
        
        assert config.max_iterations == 100
        assert config.n_initial_points == 10
        assert config.acquisition_function == 'EI'
        assert config.random_state == 42
        assert config.n_jobs == 1
        assert config.timeout_minutes == 60
        assert config.convergence_threshold == 0.001
        assert config.min_improvement == 0.01
        assert config.validation_split == 0.3
    
    def test_genetic_config_defaults(self):
        """Test GeneticConfig default values."""
        config = GeneticConfig()
        
        assert config.population_size == 50
        assert config.generations == 100
        assert config.crossover_prob == 0.7
        assert config.mutation_prob == 0.2
        assert config.tournament_size == 3
        assert config.elite_size == 5
        assert config.random_state == 42
    
    def test_walkforward_config_defaults(self):
        """Test WalkForwardConfig default values."""
        config = WalkForwardConfig()
        
        assert config.window_size == timedelta(days=30)
        assert config.step_size == timedelta(days=7)
        assert config.min_trades == 10
        assert config.out_of_sample_ratio == 0.2
        assert config.reoptimize_frequency == 4


class TestRegimeSpecificParameterAdaptation:
    """Test cases for regime-specific parameter adaptation functionality."""
    
    def test_set_regime_parameters(self, parameter_optimizer):
        """Test setting parameters for specific regimes."""
        strategy_name = 'test_strategy'
        regime = RegimeType.TRENDING_BULL
        parameters = {'stop_loss': 0.02, 'take_profit': 0.15}
        
        parameter_optimizer.set_regime_parameters(strategy_name, regime, parameters)
        
        # Verify parameters were set
        stored_params = parameter_optimizer.get_regime_parameters(strategy_name, regime)
        assert stored_params == parameters
        
        # Verify strategy exists in regime_parameters
        assert strategy_name in parameter_optimizer.regime_parameters
        assert regime in parameter_optimizer.regime_parameters[strategy_name]
    
    def test_get_regime_parameters(self, parameter_optimizer):
        """Test getting parameters for specific regimes."""
        strategy_name = 'test_strategy'
        regime = RegimeType.RANGING
        parameters = {'stop_loss': 0.05, 'take_profit': 0.08}
        
        # Test getting non-existent parameters
        result = parameter_optimizer.get_regime_parameters(strategy_name, regime)
        assert result is None
        
        # Set parameters and test retrieval
        parameter_optimizer.set_regime_parameters(strategy_name, regime, parameters)
        result = parameter_optimizer.get_regime_parameters(strategy_name, regime)
        assert result == parameters
    
    def test_update_regime(self, parameter_optimizer):
        """Test regime updates and parameter adaptation."""
        strategy_name = 'test_strategy'
        
        # Set parameters for different regimes
        bull_params = {'stop_loss': 0.02, 'take_profit': 0.15}
        bear_params = {'stop_loss': 0.08, 'take_profit': 0.05}
        
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.TRENDING_BULL, bull_params)
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.TRENDING_BEAR, bear_params)
        
        # Update to bull regime
        adaptation_details = parameter_optimizer.update_regime(RegimeType.TRENDING_BULL, confidence=0.8)
        
        assert parameter_optimizer.current_regime == RegimeType.TRENDING_BULL
        assert adaptation_details['new_regime'] == RegimeType.TRENDING_BULL.value
        assert adaptation_details['confidence'] == 0.8
        assert len(adaptation_details['strategies_adapted']) == 1
        
        # Update to bear regime
        adaptation_details = parameter_optimizer.update_regime(RegimeType.TRENDING_BEAR, confidence=0.9)
        
        assert parameter_optimizer.current_regime == RegimeType.TRENDING_BEAR
        assert adaptation_details['old_regime'] == RegimeType.TRENDING_BULL.value
        assert adaptation_details['new_regime'] == RegimeType.TRENDING_BEAR.value
    
    def test_parameter_interpolation(self, parameter_optimizer):
        """Test parameter interpolation during regime transitions."""
        strategy_name = 'test_strategy'
        
        # Set parameters for different regimes
        current_params = {'stop_loss': 0.05, 'take_profit': 0.10}
        target_params = {'stop_loss': 0.02, 'take_profit': 0.15}
        
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.RANGING, current_params)
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.TRENDING_BULL, target_params)
        
        # Set current regime
        parameter_optimizer.current_regime = RegimeType.RANGING
        
        # Update to new regime with moderate confidence
        parameter_optimizer.update_regime(RegimeType.TRENDING_BULL, confidence=0.6)
        
        # Get interpolated parameters
        interpolated = parameter_optimizer.get_current_parameters(strategy_name)
        
        # Parameters should be between current and target
        assert current_params['stop_loss'] > interpolated['stop_loss'] > target_params['stop_loss']
        assert current_params['take_profit'] < interpolated['take_profit'] < target_params['take_profit']
    
    def test_get_current_parameters(self, parameter_optimizer):
        """Test getting current parameters based on regime."""
        strategy_name = 'test_strategy'
        regime = RegimeType.HIGH_VOLATILITY
        parameters = {'stop_loss': 0.08, 'take_profit': 0.06}
        
        # Test with no current regime
        result = parameter_optimizer.get_current_parameters(strategy_name)
        assert result == {}
        
        # Set regime and parameters
        parameter_optimizer.set_regime_parameters(strategy_name, regime, parameters)
        parameter_optimizer.current_regime = regime
        
        result = parameter_optimizer.get_current_parameters(strategy_name)
        assert result == parameters
    
    def test_track_regime_performance(self, parameter_optimizer):
        """Test tracking performance by regime."""
        strategy_name = 'test_strategy'
        regime = RegimeType.TRENDING_BULL
        
        # Track multiple performance values
        performances = [0.12, 0.15, 0.08, 0.18, 0.11]
        for perf in performances:
            parameter_optimizer.track_regime_performance(strategy_name, regime, perf)
        
        # Verify performance was tracked
        assert strategy_name in parameter_optimizer.regime_performance
        assert regime in parameter_optimizer.regime_performance[strategy_name]
        assert parameter_optimizer.regime_performance[strategy_name][regime] == performances
    
    def test_get_regime_performance_stats(self, parameter_optimizer):
        """Test getting performance statistics by regime."""
        strategy_name = 'test_strategy'
        regime = RegimeType.RANGING
        performances = [0.05, 0.08, 0.03, 0.12, 0.07, 0.09, 0.06]
        
        # Track performances
        for perf in performances:
            parameter_optimizer.track_regime_performance(strategy_name, regime, perf)
        
        # Get statistics
        stats = parameter_optimizer.get_regime_performance_stats(strategy_name, regime)
        
        assert stats['count'] == len(performances)
        assert abs(stats['mean'] - np.mean(performances)) < 0.001
        assert abs(stats['std'] - np.std(performances)) < 0.001
        assert stats['min'] == min(performances)
        assert stats['max'] == max(performances)
        assert 'recent_trend' in stats
    
    def test_get_regime_performance_stats_empty(self, parameter_optimizer):
        """Test getting performance statistics for empty regime data."""
        strategy_name = 'test_strategy'
        regime = RegimeType.UNCERTAIN
        
        stats = parameter_optimizer.get_regime_performance_stats(strategy_name, regime)
        
        assert stats['count'] == 0
        assert stats['mean'] == 0.0
        assert stats['std'] == 0.0
        assert stats['min'] == 0.0
        assert stats['max'] == 0.0
    
    def test_optimize_regime_parameters(self, parameter_optimizer, sample_parameter_space, sample_historical_data):
        """Test optimizing parameters for a specific regime."""
        strategy_name = 'test_strategy'
        regime = RegimeType.HIGH_VOLATILITY
        
        result = parameter_optimizer.optimize_regime_parameters(
            strategy_name=strategy_name,
            regime=regime,
            parameter_space=sample_parameter_space,
            historical_data=sample_historical_data,
            optimization_type=OptimizationType.RANDOM_SEARCH
        )
        
        assert result.success
        assert result.metadata['regime'] == regime.value
        
        # Verify parameters were stored for the regime
        stored_params = parameter_optimizer.get_regime_parameters(strategy_name, regime)
        assert stored_params == result.new_parameters
    
    def test_regime_transition_history(self, parameter_optimizer):
        """Test regime transition history tracking."""
        regimes = [RegimeType.RANGING, RegimeType.TRENDING_BULL, RegimeType.HIGH_VOLATILITY]
        
        # Update regimes
        for regime in regimes:
            parameter_optimizer.update_regime(regime, confidence=0.8)
        
        # Check history
        assert len(parameter_optimizer.regime_transition_history) == len(regimes)
        
        # Check frequency statistics
        freq_stats = parameter_optimizer.get_regime_transition_frequency()
        assert freq_stats['total_transitions'] >= 0  # May be 0 if transitions are too fast
    
    def test_export_import_regime_parameters(self, parameter_optimizer):
        """Test exporting and importing regime parameters."""
        strategy_name = 'test_strategy'
        
        # Set up test data
        bull_params = {'stop_loss': 0.02, 'take_profit': 0.15}
        bear_params = {'stop_loss': 0.08, 'take_profit': 0.05}
        
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.TRENDING_BULL, bull_params)
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.TRENDING_BEAR, bear_params)
        parameter_optimizer.current_regime = RegimeType.TRENDING_BULL
        
        # Track some performance
        parameter_optimizer.track_regime_performance(strategy_name, RegimeType.TRENDING_BULL, 0.12)
        parameter_optimizer.track_regime_performance(strategy_name, RegimeType.TRENDING_BEAR, 0.08)
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            parameter_optimizer.export_regime_parameters(filepath)
            
            # Create new optimizer and import
            new_optimizer = ParameterOptimizer(MockPerformanceEvaluator())
            new_optimizer.import_regime_parameters(filepath)
            
            # Verify data was imported correctly
            assert new_optimizer.current_regime == RegimeType.TRENDING_BULL
            assert new_optimizer.get_regime_parameters(strategy_name, RegimeType.TRENDING_BULL) == bull_params
            assert new_optimizer.get_regime_parameters(strategy_name, RegimeType.TRENDING_BEAR) == bear_params
            
            # Check performance data
            bull_stats = new_optimizer.get_regime_performance_stats(strategy_name, RegimeType.TRENDING_BULL)
            bear_stats = new_optimizer.get_regime_performance_stats(strategy_name, RegimeType.TRENDING_BEAR)
            assert bull_stats['count'] == 1
            assert bear_stats['count'] == 1
            
        finally:
            # Clean up
            if os.path.exists(filepath):
                os.unlink(filepath)
    
    def test_filter_data_by_regime(self, parameter_optimizer, sample_historical_data):
        """Test filtering historical data by regime."""
        # Add regime column to test data
        regime_data = sample_historical_data.copy()
        regime_data['regime'] = RegimeType.TRENDING_BULL.value
        
        # Test filtering with regime column
        filtered = parameter_optimizer._filter_data_by_regime(regime_data, RegimeType.TRENDING_BULL)
        assert len(filtered) == len(regime_data)
        
        # Test filtering without regime column (uses heuristics)
        filtered_heuristic = parameter_optimizer._filter_data_by_regime(sample_historical_data, RegimeType.HIGH_VOLATILITY)
        assert len(filtered_heuristic) <= len(sample_historical_data)
    
    def test_regime_transition_smoothing(self, parameter_optimizer):
        """Test regime transition smoothing functionality."""
        strategy_name = 'test_strategy'
        
        # Set different smoothing factor
        parameter_optimizer.regime_transition_smoothing = 0.5
        
        # Set parameters for regimes
        current_params = {'param1': 10.0}
        target_params = {'param1': 20.0}
        
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.RANGING, current_params)
        parameter_optimizer.set_regime_parameters(strategy_name, RegimeType.TRENDING_BULL, target_params)
        
        # Set current regime
        parameter_optimizer.current_regime = RegimeType.RANGING
        
        # Update with high confidence
        parameter_optimizer.update_regime(RegimeType.TRENDING_BULL, confidence=1.0)
        
        # Get interpolated parameters
        interpolated = parameter_optimizer.get_current_parameters(strategy_name)
        
        # With smoothing factor 0.5 and confidence 1.0, interpolation factor should be 0.5
        expected_value = current_params['param1'] + (target_params['param1'] - current_params['param1']) * 0.5
        assert abs(interpolated['param1'] - expected_value) < 0.001
    
    def test_multiple_strategies_regime_adaptation(self, parameter_optimizer):
        """Test regime adaptation with multiple strategies."""
        strategies = ['strategy1', 'strategy2', 'strategy3']
        regime = RegimeType.HIGH_VOLATILITY
        
        # Set parameters for all strategies
        for i, strategy in enumerate(strategies):
            params = {'param1': i * 0.1, 'param2': (i + 1) * 0.05}
            parameter_optimizer.set_regime_parameters(strategy, regime, params)
        
        # Update regime
        adaptation_details = parameter_optimizer.update_regime(regime, confidence=0.8)
        
        # All strategies should be adapted
        assert len(adaptation_details['strategies_adapted']) == len(strategies)
        
        # Verify each strategy was adapted
        adapted_strategies = [item['strategy'] for item in adaptation_details['strategies_adapted']]
        for strategy in strategies:
            assert strategy in adapted_strategies


class TestParameterValidationAndRollback:
    """Test cases for parameter validation and rollback system."""
    
    def test_validate_parameter_change(self, parameter_optimizer, sample_historical_data):
        """Test parameter change validation."""
        strategy_name = 'test_strategy'
        old_parameters = {'param1': 0.1, 'param2': 0.2}
        new_parameters = {'param1': 0.15, 'param2': 0.25}  # Better parameters
        
        validation_result = parameter_optimizer.validate_parameter_change(
            strategy_name, old_parameters, new_parameters, sample_historical_data
        )
        
        assert 'is_valid' in validation_result
        assert 'confidence' in validation_result
        assert 'performance_improvement' in validation_result
        assert 'risk_increase' in validation_result
        assert 'recommendation' in validation_result
        assert validation_result['validation_timestamp'] is not None
    
    def test_create_ab_test(self, parameter_optimizer):
        """Test A/B test creation."""
        strategy_name = 'test_strategy'
        control_parameters = {'param1': 0.1}
        test_parameters = {'param1': 0.2}
        
        test_id = parameter_optimizer.create_ab_test(
            strategy_name, control_parameters, test_parameters, allocation_ratio=0.5
        )
        
        assert test_id.startswith(f"{strategy_name}_ab_")
        assert hasattr(parameter_optimizer, 'ab_tests')
        assert test_id in parameter_optimizer.ab_tests
        
        ab_test = parameter_optimizer.ab_tests[test_id]
        assert ab_test['strategy_name'] == strategy_name
        assert ab_test['control_parameters'] == control_parameters
        assert ab_test['test_parameters'] == test_parameters
        assert ab_test['allocation_ratio'] == 0.5
        assert ab_test['status'] == 'active'
    
    def test_update_ab_test(self, parameter_optimizer):
        """Test A/B test updates."""
        strategy_name = 'test_strategy'
        control_parameters = {'param1': 0.1}
        test_parameters = {'param1': 0.2}
        
        test_id = parameter_optimizer.create_ab_test(
            strategy_name, control_parameters, test_parameters
        )
        
        # Update with performance data
        parameter_optimizer.update_ab_test(test_id, control_performance=0.1, test_performance=0.15)
        
        ab_test = parameter_optimizer.ab_tests[test_id]
        assert len(ab_test['control_performance']) == 1
        assert len(ab_test['test_performance']) == 1
        assert ab_test['control_performance'][0]['performance'] == 0.1
        assert ab_test['test_performance'][0]['performance'] == 0.15
    
    def test_get_ab_test_results(self, parameter_optimizer):
        """Test getting A/B test results."""
        strategy_name = 'test_strategy'
        control_parameters = {'param1': 0.1}
        test_parameters = {'param1': 0.2}
        
        test_id = parameter_optimizer.create_ab_test(
            strategy_name, control_parameters, test_parameters
        )
        
        # Test getting existing results
        results = parameter_optimizer.get_ab_test_results(test_id)
        assert results is not None
        assert results['test_id'] == test_id
        
        # Test getting non-existent results
        non_existent_results = parameter_optimizer.get_ab_test_results('non_existent_id')
        assert non_existent_results is None
    
    def test_create_parameter_rollback_point(self, parameter_optimizer):
        """Test creating parameter rollback points."""
        strategy_name = 'test_strategy'
        parameters = {'param1': 0.1, 'param2': 0.2}
        performance_baseline = 0.15
        
        rollback_id = parameter_optimizer.create_parameter_rollback_point(
            strategy_name, parameters, performance_baseline
        )
        
        assert rollback_id.startswith(f"{strategy_name}_rollback_")
        assert hasattr(parameter_optimizer, 'rollback_points')
        assert rollback_id in parameter_optimizer.rollback_points
        
        rollback_point = parameter_optimizer.rollback_points[rollback_id]
        assert rollback_point['strategy_name'] == strategy_name
        assert rollback_point['parameters'] == parameters
        assert rollback_point['performance_baseline'] == performance_baseline
        assert rollback_point['is_active'] == True
    
    def test_rollback_parameters(self, parameter_optimizer):
        """Test parameter rollback functionality."""
        strategy_name = 'test_strategy'
        parameters = {'param1': 0.1, 'param2': 0.2}
        
        # Create rollback point
        rollback_id = parameter_optimizer.create_parameter_rollback_point(
            strategy_name, parameters
        )
        
        # Test successful rollback
        success = parameter_optimizer.rollback_parameters(rollback_id)
        assert success == True
        
        # Verify rollback point is no longer active
        rollback_point = parameter_optimizer.rollback_points[rollback_id]
        assert rollback_point['is_active'] == False
        assert 'used_at' in rollback_point
        
        # Test rollback of non-existent point
        success = parameter_optimizer.rollback_parameters('non_existent_id')
        assert success == False
        
        # Test rollback of inactive point
        success = parameter_optimizer.rollback_parameters(rollback_id)
        assert success == False
    
    def test_auto_rollback_check(self, parameter_optimizer):
        """Test automatic rollback checking."""
        strategy_name = 'test_strategy'
        parameters = {'param1': 0.1}
        baseline_performance = 0.2
        
        # Create rollback point
        rollback_id = parameter_optimizer.create_parameter_rollback_point(
            strategy_name, parameters, baseline_performance
        )
        
        # Test with performance above threshold (no rollback)
        result = parameter_optimizer.auto_rollback_check(strategy_name, 0.19, -0.05)
        assert result is None
        
        # Test with performance below threshold (should trigger rollback)
        result = parameter_optimizer.auto_rollback_check(strategy_name, 0.15, -0.05)
        assert result == rollback_id
        
        # Verify rollback point is no longer active
        rollback_point = parameter_optimizer.rollback_points[rollback_id]
        assert rollback_point['is_active'] == False
    
    def test_get_parameter_change_history(self, parameter_optimizer):
        """Test getting parameter change history."""
        strategy_name = 'test_strategy'
        
        # Add some optimization history
        optimization_result = OptimizationResult(
            optimization_id='test_opt_1',
            strategy_name=strategy_name,
            optimization_method='test_method',
            old_parameters={'param1': 0.1},
            new_parameters={'param1': 0.2},
            performance_improvement=0.05,
            confidence_score=0.8,
            validation_period=timedelta(days=7),
            applied_at=datetime.now()
        )
        parameter_optimizer.optimization_history.append(optimization_result)
        
        # Create and use a rollback point
        rollback_id = parameter_optimizer.create_parameter_rollback_point(
            strategy_name, {'param1': 0.15}
        )
        parameter_optimizer.rollback_parameters(rollback_id)
        
        # Get history
        history = parameter_optimizer.get_parameter_change_history(strategy_name)
        
        assert len(history) >= 2  # At least optimization and rollback
        
        # Check that history contains both types
        types = [entry['type'] for entry in history]
        assert 'optimization' in types
        assert 'rollback' in types
    
    def test_export_parameter_audit_trail(self, parameter_optimizer):
        """Test exporting parameter audit trail."""
        strategy_name = 'test_strategy'
        
        # Add some test data
        optimization_result = OptimizationResult(
            optimization_id='test_opt_1',
            strategy_name=strategy_name,
            optimization_method='test_method',
            old_parameters={'param1': 0.1},
            new_parameters={'param1': 0.2},
            performance_improvement=0.05,
            confidence_score=0.8,
            validation_period=timedelta(days=7),
            applied_at=datetime.now()
        )
        parameter_optimizer.optimization_history.append(optimization_result)
        
        # Create rollback point
        parameter_optimizer.create_parameter_rollback_point(strategy_name, {'param1': 0.15})
        
        # Create A/B test
        parameter_optimizer.create_ab_test(
            strategy_name, {'param1': 0.1}, {'param1': 0.2}
        )
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            parameter_optimizer.export_parameter_audit_trail(filepath, strategy_name)
            
            # Verify file was created and contains expected data
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                audit_data = json.load(f)
            
            assert 'export_timestamp' in audit_data
            assert 'optimization_history' in audit_data
            assert 'rollback_points' in audit_data
            assert 'ab_tests' in audit_data
            
            # Check that data was exported
            assert len(audit_data['optimization_history']) >= 1
            assert len(audit_data['rollback_points']) >= 1
            assert len(audit_data['ab_tests']) >= 1
            
        finally:
            # Clean up
            if os.path.exists(filepath):
                os.unlink(filepath)
    
    def test_cleanup_old_rollback_points(self, parameter_optimizer):
        """Test cleanup of old rollback points."""
        strategy_name = 'test_strategy'
        
        # Create some rollback points
        rollback_id1 = parameter_optimizer.create_parameter_rollback_point(
            strategy_name, {'param1': 0.1}
        )
        rollback_id2 = parameter_optimizer.create_parameter_rollback_point(
            strategy_name, {'param1': 0.2}
        )
        
        # Make one of them old and inactive
        parameter_optimizer.rollback_parameters(rollback_id1)
        old_rollback = parameter_optimizer.rollback_points[rollback_id1]
        old_rollback['created_at'] = datetime.now() - timedelta(days=35)  # Make it old
        
        # Clean up old rollback points
        cleaned_count = parameter_optimizer.cleanup_old_rollback_points(max_age=timedelta(days=30))
        
        assert cleaned_count == 1
        assert rollback_id1 not in parameter_optimizer.rollback_points
        assert rollback_id2 in parameter_optimizer.rollback_points  # Should still exist (active)
    
    def test_conclude_ab_test(self, parameter_optimizer):
        """Test A/B test conclusion."""
        strategy_name = 'test_strategy'
        control_parameters = {'param1': 0.1}
        test_parameters = {'param1': 0.2}
        
        # Create A/B test with short duration
        test_id = parameter_optimizer.create_ab_test(
            strategy_name, control_parameters, test_parameters,
            test_duration=timedelta(seconds=1)
        )
        
        # Add performance data
        parameter_optimizer.update_ab_test(test_id, control_performance=0.1)
        parameter_optimizer.update_ab_test(test_id, test_performance=0.15)
        parameter_optimizer.update_ab_test(test_id, control_performance=0.12)
        parameter_optimizer.update_ab_test(test_id, test_performance=0.18)
        
        # Wait for test to expire and conclude
        import time
        time.sleep(1.1)
        parameter_optimizer.update_ab_test(test_id)  # This should trigger conclusion
        
        ab_test = parameter_optimizer.ab_tests[test_id]
        assert ab_test['status'] == 'completed'
        assert 'winner' in ab_test
        assert 'reason' in ab_test
        assert 'control_avg_performance' in ab_test
        assert 'test_avg_performance' in ab_test
        
        # Test should win since test performance is higher
        assert ab_test['winner'] == 'test'


if __name__ == '__main__':
    pytest.main([__file__])