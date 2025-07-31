"""
Parameter Optimization System for Adaptive Trading Bot

This module implements various parameter optimization algorithms including:
- Bayesian Optimization for efficient parameter space exploration
- Genetic Algorithms for complex multi-parameter optimization
- Walk-forward analysis for parameter validation
- Parameter bounds management and constraint handling
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import pickle
from pathlib import Path
import threading
import time

# Third-party imports for optimization
try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    BAYESIAN_AVAILABLE = True
except ImportError:
    BAYESIAN_AVAILABLE = False
    logging.warning("scikit-optimize not available. Bayesian optimization disabled.")

try:
    import deap
    from deap import base, creator, tools, algorithms
    GENETIC_AVAILABLE = True
except ImportError:
    GENETIC_AVAILABLE = False
    logging.warning("DEAP not available. Genetic algorithm optimization disabled.")

from .data_models import OptimizationResult, ParameterBounds, ParameterSet, MarketRegime
from .enums import OptimizationType, ParameterType, RegimeType
from .interfaces import IParameterOptimizer, IPerformanceEvaluator


@dataclass
class OptimizationConfig:
    """Configuration for parameter optimization"""
    max_iterations: int = 100
    n_initial_points: int = 10
    acquisition_function: str = 'EI'  # Expected Improvement
    random_state: int = 42
    n_jobs: int = 1
    timeout_minutes: int = 60
    convergence_threshold: float = 0.001
    min_improvement: float = 0.01
    validation_split: float = 0.3


@dataclass
class GeneticConfig:
    """Configuration for genetic algorithm optimization"""
    population_size: int = 50
    generations: int = 100
    crossover_prob: float = 0.7
    mutation_prob: float = 0.2
    tournament_size: int = 3
    elite_size: int = 5
    random_state: int = 42


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward analysis"""
    window_size: timedelta = timedelta(days=30)
    step_size: timedelta = timedelta(days=7)
    min_trades: int = 10
    out_of_sample_ratio: float = 0.2
    reoptimize_frequency: int = 4  # Every N steps


class ParameterOptimizer(IParameterOptimizer):
    """
    Main parameter optimization class that implements multiple optimization algorithms
    """
    
    def __init__(self, 
                 performance_evaluator: IPerformanceEvaluator,
                 config: OptimizationConfig = None,
                 genetic_config: GeneticConfig = None,
                 walkforward_config: WalkForwardConfig = None):
        self.performance_evaluator = performance_evaluator
        self.config = config or OptimizationConfig()
        self.genetic_config = genetic_config or GeneticConfig()
        self.walkforward_config = walkforward_config or WalkForwardConfig()
        
        self.logger = logging.getLogger(__name__)
        self.optimization_history: List[OptimizationResult] = []
        self.parameter_bounds: Dict[str, ParameterBounds] = {}
        self.best_parameters: Dict[str, Any] = {}
        self.current_optimization_id: Optional[str] = None
        
        # Regime-specific parameter management
        self.regime_parameters: Dict[str, Dict[RegimeType, Dict[str, Any]]] = {}  # strategy -> regime -> params
        self.regime_performance: Dict[str, Dict[RegimeType, List[float]]] = {}  # strategy -> regime -> performance history
        self.current_regime: Optional[RegimeType] = None
        self.regime_transition_smoothing: float = 0.3  # Smoothing factor for parameter transitions
        self.parameter_interpolation_steps: int = 5  # Steps for smooth parameter transitions
        self.regime_transition_history: List[Tuple[RegimeType, datetime]] = []  # Track regime changes
        self.interpolation_cache: Dict[str, Dict[str, Any]] = {}  # Cache for interpolated parameters
        
        # Initialize optimization algorithms
        self._setup_bayesian_optimizer()
        self._setup_genetic_algorithm()
    
    def _setup_bayesian_optimizer(self):
        """Initialize Bayesian optimization components"""
        if not BAYESIAN_AVAILABLE:
            self.logger.warning("Bayesian optimization not available")
            return
        
        self.bayesian_results = {}
        self.bayesian_spaces = {}
    
    def _setup_genetic_algorithm(self):
        """Initialize genetic algorithm components"""
        if not GENETIC_AVAILABLE:
            self.logger.warning("Genetic algorithm optimization not available")
            return
        
        # Setup DEAP framework
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMax)
        
        self.toolbox = base.Toolbox()
    
    def set_parameter_bounds(self, parameter_name: str, bounds: ParameterBounds):
        """Set bounds for a parameter"""
        self.parameter_bounds[parameter_name] = bounds
        self.logger.info(f"Set bounds for {parameter_name}: {bounds}")
    
    def optimize_parameters(self, 
                          strategy_name: str,
                          parameter_space: Dict[str, ParameterBounds],
                          historical_data: pd.DataFrame,
                          optimization_type: OptimizationType = OptimizationType.BAYESIAN,
                          **kwargs) -> OptimizationResult:
        """
        Optimize parameters using specified algorithm
        
        Args:
            strategy_name: Name of the strategy to optimize
            parameter_space: Dictionary of parameter names to bounds
            historical_data: Historical market data for optimization
            optimization_type: Type of optimization algorithm to use
            **kwargs: Additional arguments for specific optimizers
        
        Returns:
            OptimizationResult with optimization details
        """
        self.logger.info(f"Starting parameter optimization for {strategy_name}")
        self.logger.info(f"Optimization type: {optimization_type}")
        self.logger.info(f"Parameter space: {list(parameter_space.keys())}")
        
        start_time = datetime.now()
        self.current_optimization_id = f"{strategy_name}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        try:
            if optimization_type == OptimizationType.BAYESIAN:
                result = self._bayesian_optimize(strategy_name, parameter_space, historical_data, **kwargs)
            elif optimization_type == OptimizationType.GENETIC:
                result = self._genetic_optimize(strategy_name, parameter_space, historical_data, **kwargs)
            elif optimization_type == OptimizationType.GRID_SEARCH:
                result = self._grid_search_optimize(strategy_name, parameter_space, historical_data, **kwargs)
            elif optimization_type == OptimizationType.RANDOM_SEARCH:
                result = self._random_search_optimize(strategy_name, parameter_space, historical_data, **kwargs)
            else:
                raise ValueError(f"Unsupported optimization type: {optimization_type}")
            
            # Store result
            self.optimization_history.append(result)
            if result.success:
                self.best_parameters[strategy_name] = result.new_parameters
            
            self.logger.info(f"Optimization completed in {datetime.now() - start_time}")
            return result
            
        except Exception as e:
            self.logger.error(f"Optimization failed: {str(e)}")
            # Handle case where optimization_type might be a string
            method_name = optimization_type.value if hasattr(optimization_type, 'value') else str(optimization_type)
            return OptimizationResult(
                optimization_id=self.current_optimization_id,
                strategy_name=strategy_name,
                old_parameters={},
                new_parameters={},
                performance_improvement=0.0,
                confidence_score=0.0,
                optimization_method=method_name,
                validation_period=timedelta(),
                applied_at=datetime.now(),
                success=False,
                error_message=str(e)
            )
        finally:
            self.current_optimization_id = None
    
    def _bayesian_optimize(self, 
                          strategy_name: str,
                          parameter_space: Dict[str, ParameterBounds],
                          historical_data: pd.DataFrame,
                          **kwargs) -> OptimizationResult:
        """Bayesian optimization implementation"""
        if not BAYESIAN_AVAILABLE:
            raise RuntimeError("Bayesian optimization not available. Install scikit-optimize.")
        
        self.logger.info("Starting Bayesian optimization")
        
        # Convert parameter space to skopt format
        dimensions = []
        param_names = []
        
        for param_name, bounds in parameter_space.items():
            param_names.append(param_name)
            
            if bounds.param_type == ParameterType.CONTINUOUS:
                dimensions.append(Real(bounds.min_value, bounds.max_value, name=param_name))
            elif bounds.param_type == ParameterType.INTEGER:
                dimensions.append(Integer(int(bounds.min_value), int(bounds.max_value), name=param_name))
            elif bounds.param_type == ParameterType.CATEGORICAL:
                dimensions.append(Categorical(bounds.categories, name=param_name))
        
        # Define objective function
        @use_named_args(dimensions)
        def objective(**params):
            try:
                # Evaluate parameters
                performance = self.performance_evaluator.evaluate_parameters(
                    strategy_name, params, historical_data
                )
                # Return negative because skopt minimizes
                return -performance.total_return
            except Exception as e:
                self.logger.error(f"Error evaluating parameters {params}: {str(e)}")
                return float('inf')  # Bad performance for failed evaluations
        
        # Run optimization
        result = gp_minimize(
            func=objective,
            dimensions=dimensions,
            n_calls=self.config.max_iterations,
            n_initial_points=self.config.n_initial_points,
            acq_func=self.config.acquisition_function,
            random_state=self.config.random_state,
            n_jobs=self.config.n_jobs
        )
        
        # Extract best parameters
        best_params = {}
        for i, param_name in enumerate(param_names):
            best_params[param_name] = result.x[i]
        
        # Calculate performance improvement
        baseline_performance = self.performance_evaluator.evaluate_parameters(
            strategy_name, {}, historical_data  # Use default parameters
        )
        optimized_performance = self.performance_evaluator.evaluate_parameters(
            strategy_name, best_params, historical_data
        )
        
        improvement = optimized_performance.total_return - baseline_performance.total_return
        confidence = self._calculate_optimization_confidence(result)
        
        return OptimizationResult(
            optimization_id=self.current_optimization_id,
            strategy_name=strategy_name,
            old_parameters={},  # Would need baseline parameters
            new_parameters=best_params,
            performance_improvement=improvement,
            confidence_score=confidence,
            optimization_method=OptimizationType.BAYESIAN.value,
            validation_period=timedelta(days=len(historical_data)),
            applied_at=datetime.now(),
            success=True,
            metadata={
                'n_calls': result.n_calls,
                'best_objective': -result.fun,
                'convergence': result.func_vals
            }
        )
    
    def _genetic_optimize(self, 
                         strategy_name: str,
                         parameter_space: Dict[str, ParameterBounds],
                         historical_data: pd.DataFrame,
                         **kwargs) -> OptimizationResult:
        """Genetic algorithm optimization implementation"""
        if not GENETIC_AVAILABLE:
            raise RuntimeError("Genetic algorithm optimization not available. Install DEAP.")
        
        self.logger.info("Starting genetic algorithm optimization")
        
        # Setup genetic algorithm
        param_names = list(parameter_space.keys())
        param_bounds = list(parameter_space.values())
        
        # Define individual creation
        def create_individual():
            individual = []
            for bounds in param_bounds:
                if bounds.param_type == ParameterType.CONTINUOUS:
                    value = np.random.uniform(bounds.min_value, bounds.max_value)
                elif bounds.param_type == ParameterType.INTEGER:
                    value = np.random.randint(int(bounds.min_value), int(bounds.max_value) + 1)
                elif bounds.param_type == ParameterType.CATEGORICAL:
                    value = np.random.choice(bounds.categories)
                individual.append(value)
            return creator.Individual(individual)
        
        # Define fitness function
        def evaluate_individual(individual):
            params = dict(zip(param_names, individual))
            try:
                performance = self.performance_evaluator.evaluate_parameters(
                    strategy_name, params, historical_data
                )
                return (performance.total_return,)
            except Exception as e:
                self.logger.error(f"Error evaluating individual {params}: {str(e)}")
                return (-float('inf'),)
        
        # Setup toolbox
        self.toolbox.register("individual", create_individual)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("evaluate", evaluate_individual)
        self.toolbox.register("mate", self._crossover)
        self.toolbox.register("mutate", self._mutate, param_bounds=param_bounds)
        self.toolbox.register("select", tools.selTournament, tournsize=self.genetic_config.tournament_size)
        
        # Create initial population
        population = self.toolbox.population(n=self.genetic_config.population_size)
        
        # Evaluate initial population
        fitnesses = list(map(self.toolbox.evaluate, population))
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit
        
        # Evolution loop
        for generation in range(self.genetic_config.generations):
            # Select next generation
            offspring = self.toolbox.select(population, len(population))
            offspring = list(map(self.toolbox.clone, offspring))
            
            # Apply crossover and mutation
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if np.random.random() < self.genetic_config.crossover_prob:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
            
            for mutant in offspring:
                if np.random.random() < self.genetic_config.mutation_prob:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values
            
            # Evaluate individuals with invalid fitness
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(self.toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit
            
            # Replace population
            population[:] = offspring
            
            # Log progress
            if generation % 10 == 0:
                best_fitness = max(ind.fitness.values[0] for ind in population)
                self.logger.info(f"Generation {generation}: Best fitness = {best_fitness:.4f}")
        
        # Get best individual
        best_individual = tools.selBest(population, 1)[0]
        best_params = dict(zip(param_names, best_individual))
        
        # Calculate performance improvement
        baseline_performance = self.performance_evaluator.evaluate_parameters(
            strategy_name, {}, historical_data
        )
        improvement = best_individual.fitness.values[0] - baseline_performance.total_return
        
        return OptimizationResult(
            optimization_id=self.current_optimization_id,
            strategy_name=strategy_name,
            old_parameters={},
            new_parameters=best_params,
            performance_improvement=improvement,
            confidence_score=0.8,  # Fixed confidence for genetic algorithm
            optimization_method=OptimizationType.GENETIC.value,
            validation_period=timedelta(days=len(historical_data)),
            applied_at=datetime.now(),
            success=True,
            metadata={
                'generations': self.genetic_config.generations,
                'population_size': self.genetic_config.population_size,
                'best_fitness': best_individual.fitness.values[0]
            }
        )
    
    def _crossover(self, ind1, ind2):
        """Crossover operation for genetic algorithm"""
        for i in range(len(ind1)):
            if np.random.random() < 0.5:
                ind1[i], ind2[i] = ind2[i], ind1[i]
        return ind1, ind2
    
    def _mutate(self, individual, param_bounds):
        """Mutation operation for genetic algorithm"""
        for i, bounds in enumerate(param_bounds):
            if np.random.random() < 0.1:  # 10% mutation rate per gene
                if bounds.param_type == ParameterType.CONTINUOUS:
                    # Gaussian mutation
                    mutation_strength = (bounds.max_value - bounds.min_value) * 0.1
                    individual[i] += np.random.normal(0, mutation_strength)
                    individual[i] = np.clip(individual[i], bounds.min_value, bounds.max_value)
                elif bounds.param_type == ParameterType.INTEGER:
                    individual[i] = np.random.randint(int(bounds.min_value), int(bounds.max_value) + 1)
                elif bounds.param_type == ParameterType.CATEGORICAL:
                    individual[i] = np.random.choice(bounds.categories)
        return (individual,)
    
    def _grid_search_optimize(self, 
                             strategy_name: str,
                             parameter_space: Dict[str, ParameterBounds],
                             historical_data: pd.DataFrame,
                             **kwargs) -> OptimizationResult:
        """Grid search optimization implementation"""
        self.logger.info("Starting grid search optimization")
        
        # Generate parameter grid
        param_grid = self._generate_parameter_grid(parameter_space, kwargs.get('grid_points', 5))
        
        best_params = None
        best_performance = -float('inf')
        
        for params in param_grid:
            try:
                performance = self.performance_evaluator.evaluate_parameters(
                    strategy_name, params, historical_data
                )
                if performance.total_return > best_performance:
                    best_performance = performance.total_return
                    best_params = params.copy()
            except Exception as e:
                self.logger.error(f"Error evaluating parameters {params}: {str(e)}")
        
        # Calculate improvement
        baseline_performance = self.performance_evaluator.evaluate_parameters(
            strategy_name, {}, historical_data
        )
        improvement = best_performance - baseline_performance.total_return
        
        return OptimizationResult(
            optimization_id=self.current_optimization_id,
            strategy_name=strategy_name,
            old_parameters={},
            new_parameters=best_params or {},
            performance_improvement=improvement,
            confidence_score=0.9,  # High confidence for exhaustive search
            optimization_method=OptimizationType.GRID_SEARCH.value,
            validation_period=timedelta(days=len(historical_data)),
            applied_at=datetime.now(),
            success=best_params is not None,
            metadata={
                'grid_size': len(param_grid),
                'best_performance': best_performance
            }
        )
    
    def _random_search_optimize(self, 
                               strategy_name: str,
                               parameter_space: Dict[str, ParameterBounds],
                               historical_data: pd.DataFrame,
                               **kwargs) -> OptimizationResult:
        """Random search optimization implementation"""
        self.logger.info("Starting random search optimization")
        
        n_iterations = kwargs.get('n_iterations', self.config.max_iterations)
        best_params = None
        best_performance = -float('inf')
        
        for _ in range(n_iterations):
            # Generate random parameters
            params = {}
            for param_name, bounds in parameter_space.items():
                if bounds.param_type == ParameterType.CONTINUOUS:
                    params[param_name] = np.random.uniform(bounds.min_value, bounds.max_value)
                elif bounds.param_type == ParameterType.INTEGER:
                    params[param_name] = np.random.randint(int(bounds.min_value), int(bounds.max_value) + 1)
                elif bounds.param_type == ParameterType.CATEGORICAL:
                    params[param_name] = np.random.choice(bounds.categories)
            
            try:
                performance = self.performance_evaluator.evaluate_parameters(
                    strategy_name, params, historical_data
                )
                if performance.total_return > best_performance:
                    best_performance = performance.total_return
                    best_params = params.copy()
            except Exception as e:
                self.logger.error(f"Error evaluating parameters {params}: {str(e)}")
        
        # Calculate improvement
        baseline_performance = self.performance_evaluator.evaluate_parameters(
            strategy_name, {}, historical_data
        )
        improvement = best_performance - baseline_performance.total_return
        
        return OptimizationResult(
            optimization_id=self.current_optimization_id,
            strategy_name=strategy_name,
            old_parameters={},
            new_parameters=best_params or {},
            performance_improvement=improvement,
            confidence_score=0.6,  # Lower confidence for random search
            optimization_method=OptimizationType.RANDOM_SEARCH.value,
            validation_period=timedelta(days=len(historical_data)),
            applied_at=datetime.now(),
            success=best_params is not None,
            metadata={
                'n_iterations': n_iterations,
                'best_performance': best_performance
            }
        )
    
    def walk_forward_analysis(self, 
                             strategy_name: str,
                             parameter_space: Dict[str, ParameterBounds],
                             historical_data: pd.DataFrame,
                             optimization_type: OptimizationType = OptimizationType.BAYESIAN) -> List[OptimizationResult]:
        """
        Perform walk-forward analysis for parameter validation
        
        Args:
            strategy_name: Name of the strategy to optimize
            parameter_space: Dictionary of parameter names to bounds
            historical_data: Historical market data
            optimization_type: Type of optimization to use
        
        Returns:
            List of optimization results for each walk-forward window
        """
        self.logger.info(f"Starting walk-forward analysis for {strategy_name}")
        
        results = []
        data_start = historical_data.index[0]
        data_end = historical_data.index[-1]
        
        current_start = data_start
        step_count = 0
        
        while current_start + self.walkforward_config.window_size <= data_end:
            # Define training and testing windows
            train_end = current_start + self.walkforward_config.window_size
            test_start = train_end
            test_end = min(test_start + self.walkforward_config.step_size, data_end)
            
            # Extract data windows
            train_data = historical_data[current_start:train_end]
            test_data = historical_data[test_start:test_end]
            
            self.logger.info(f"Walk-forward step {step_count + 1}")
            self.logger.info(f"Training: {current_start} to {train_end}")
            self.logger.info(f"Testing: {test_start} to {test_end}")
            
            # Skip if insufficient data
            if len(train_data) < 100 or len(test_data) < 10:
                self.logger.warning("Insufficient data for this window, skipping")
                current_start += self.walkforward_config.step_size
                step_count += 1
                continue
            
            try:
                # Optimize on training data
                optimization_result = self.optimize_parameters(
                    strategy_name=strategy_name,
                    parameter_space=parameter_space,
                    historical_data=train_data,
                    optimization_type=optimization_type
                )
                
                # Validate on test data
                if optimization_result.success:
                    test_performance = self.performance_evaluator.evaluate_parameters(
                        strategy_name, optimization_result.new_parameters, test_data
                    )
                    
                    # Update result with out-of-sample performance
                    optimization_result.out_of_sample_performance = test_performance.total_return
                    optimization_result.validation_period = test_end - test_start
                
                results.append(optimization_result)
                
            except Exception as e:
                self.logger.error(f"Error in walk-forward step {step_count + 1}: {str(e)}")
            
            # Move to next window
            current_start += self.walkforward_config.step_size
            step_count += 1
        
        # Calculate walk-forward statistics
        self._calculate_walkforward_statistics(results)
        
        self.logger.info(f"Walk-forward analysis completed with {len(results)} windows")
        return results
    
    # Regime-specific parameter adaptation methods
    
    def set_regime_parameters(self, strategy_name: str, regime: RegimeType, parameters: Dict[str, Any]) -> None:
        """
        Set parameters for a specific strategy and market regime
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime type
            parameters: Dictionary of parameter values for this regime
        """
        if strategy_name not in self.regime_parameters:
            self.regime_parameters[strategy_name] = {}
        
        self.regime_parameters[strategy_name][regime] = parameters.copy()
        self.logger.info(f"Set parameters for {strategy_name} in {regime.value} regime: {parameters}")
    
    def get_regime_parameters(self, strategy_name: str, regime: RegimeType) -> Optional[Dict[str, Any]]:
        """
        Get parameters for a specific strategy and market regime
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime type
            
        Returns:
            Dictionary of parameters or None if not found
        """
        return self.regime_parameters.get(strategy_name, {}).get(regime)
    
    def update_regime(self, new_regime: RegimeType, confidence: float = 1.0) -> Dict[str, Any]:
        """
        Update the current market regime and trigger parameter adaptation
        
        Args:
            new_regime: New market regime
            confidence: Confidence in the regime detection (0.0 to 1.0)
            
        Returns:
            Dictionary containing adaptation details
        """
        old_regime = self.current_regime
        self.current_regime = new_regime
        
        # Record regime transition
        self.regime_transition_history.append((new_regime, datetime.now()))
        
        # Keep only recent history (last 100 transitions)
        if len(self.regime_transition_history) > 100:
            self.regime_transition_history = self.regime_transition_history[-100:]
        
        adaptation_details = {
            'old_regime': old_regime.value if old_regime else None,
            'new_regime': new_regime.value,
            'confidence': confidence,
            'timestamp': datetime.now(),
            'strategies_adapted': []
        }
        
        # Adapt parameters for all strategies if regime changed
        if old_regime != new_regime:
            self.logger.info(f"Regime changed from {old_regime} to {new_regime} (confidence: {confidence:.2f})")
            
            for strategy_name in self.regime_parameters.keys():
                try:
                    adapted_params = self._adapt_strategy_to_regime(strategy_name, new_regime, old_regime, confidence)
                    if adapted_params:
                        adaptation_details['strategies_adapted'].append({
                            'strategy': strategy_name,
                            'parameters': adapted_params
                        })
                except Exception as e:
                    self.logger.error(f"Error adapting {strategy_name} to regime {new_regime}: {str(e)}")
        
        return adaptation_details
    
    def _adapt_strategy_to_regime(self, strategy_name: str, new_regime: RegimeType, 
                                 old_regime: Optional[RegimeType], confidence: float) -> Optional[Dict[str, Any]]:
        """
        Adapt a strategy's parameters to a new market regime
        
        Args:
            strategy_name: Name of the strategy to adapt
            new_regime: New market regime
            old_regime: Previous market regime
            confidence: Confidence in regime detection
            
        Returns:
            Adapted parameters or None if no adaptation needed
        """
        # Get target parameters for new regime
        target_params = self.get_regime_parameters(strategy_name, new_regime)
        if not target_params:
            self.logger.warning(f"No parameters defined for {strategy_name} in {new_regime.value} regime")
            return None
        
        # Get current parameters (from old regime or defaults)
        current_params = {}
        if old_regime:
            current_params = self.get_regime_parameters(strategy_name, old_regime) or {}
        
        # If no current parameters, use target parameters directly
        if not current_params:
            self.logger.info(f"No current parameters for {strategy_name}, using target parameters directly")
            return target_params
        
        # Calculate interpolated parameters for smooth transition
        interpolated_params = self._interpolate_parameters(
            current_params, target_params, confidence, strategy_name
        )
        
        self.logger.info(f"Adapted {strategy_name} parameters for {new_regime.value} regime")
        return interpolated_params
    
    def _interpolate_parameters(self, current_params: Dict[str, Any], target_params: Dict[str, Any], 
                               confidence: float, strategy_name: str) -> Dict[str, Any]:
        """
        Interpolate between current and target parameters for smooth transitions
        
        Args:
            current_params: Current parameter values
            target_params: Target parameter values
            confidence: Confidence in the regime change (affects interpolation speed)
            strategy_name: Name of the strategy (for caching)
            
        Returns:
            Interpolated parameters
        """
        interpolated = {}
        
        # Adjust interpolation factor based on confidence and smoothing setting
        interpolation_factor = confidence * (1.0 - self.regime_transition_smoothing)
        
        for param_name in target_params:
            current_value = current_params.get(param_name)
            target_value = target_params[param_name]
            
            if current_value is None:
                # No current value, use target
                interpolated[param_name] = target_value
            elif isinstance(current_value, (int, float)) and isinstance(target_value, (int, float)):
                # Numeric interpolation
                interpolated[param_name] = current_value + (target_value - current_value) * interpolation_factor
            else:
                # Non-numeric values - use target if confidence is high enough
                if confidence > 0.7:
                    interpolated[param_name] = target_value
                else:
                    interpolated[param_name] = current_value
        
        # Cache interpolated parameters for gradual application
        cache_key = f"{strategy_name}_{self.current_regime.value if self.current_regime else 'unknown'}"
        self.interpolation_cache[cache_key] = interpolated
        
        return interpolated
    
    def get_current_parameters(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get current parameters for a strategy based on the current regime
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Current parameters for the strategy
        """
        if not self.current_regime:
            self.logger.warning(f"No current regime set, returning empty parameters for {strategy_name}")
            return {}
        
        # Check interpolation cache first
        cache_key = f"{strategy_name}_{self.current_regime.value}"
        if cache_key in self.interpolation_cache:
            return self.interpolation_cache[cache_key]
        
        # Get regime-specific parameters
        regime_params = self.get_regime_parameters(strategy_name, self.current_regime)
        if regime_params:
            return regime_params
        
        # Fallback to best known parameters
        if strategy_name in self.best_parameters:
            return self.best_parameters[strategy_name]
        
        return {}
    
    def track_regime_performance(self, strategy_name: str, regime: RegimeType, performance: float) -> None:
        """
        Track performance of a strategy in a specific regime
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime during the performance period
            performance: Performance metric (e.g., return, Sharpe ratio)
        """
        if strategy_name not in self.regime_performance:
            self.regime_performance[strategy_name] = {}
        
        if regime not in self.regime_performance[strategy_name]:
            self.regime_performance[strategy_name][regime] = []
        
        self.regime_performance[strategy_name][regime].append(performance)
        
        # Keep only recent performance history (last 100 observations per regime)
        if len(self.regime_performance[strategy_name][regime]) > 100:
            self.regime_performance[strategy_name][regime] = self.regime_performance[strategy_name][regime][-100:]
        
        self.logger.debug(f"Tracked performance for {strategy_name} in {regime.value}: {performance:.4f}")
    
    def get_regime_performance_stats(self, strategy_name: str, regime: RegimeType) -> Dict[str, float]:
        """
        Get performance statistics for a strategy in a specific regime
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime
            
        Returns:
            Dictionary with performance statistics
        """
        performance_history = self.regime_performance.get(strategy_name, {}).get(regime, [])
        
        if not performance_history:
            return {
                'count': 0,
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0
            }
        
        performance_array = np.array(performance_history)
        
        return {
            'count': len(performance_history),
            'mean': float(np.mean(performance_array)),
            'std': float(np.std(performance_array)),
            'min': float(np.min(performance_array)),
            'max': float(np.max(performance_array)),
            'recent_trend': self._calculate_recent_trend(performance_array)
        }
    
    def _calculate_recent_trend(self, performance_array: np.ndarray, window: int = 10) -> float:
        """
        Calculate recent performance trend
        
        Args:
            performance_array: Array of performance values
            window: Number of recent observations to consider
            
        Returns:
            Trend value (positive = improving, negative = declining)
        """
        if len(performance_array) < 2:
            return 0.0
        
        recent_data = performance_array[-window:] if len(performance_array) >= window else performance_array
        
        if len(recent_data) < 2:
            return 0.0
        
        # Simple linear trend calculation
        x = np.arange(len(recent_data))
        slope = np.polyfit(x, recent_data, 1)[0]
        
        return float(slope)
    
    def optimize_regime_parameters(self, strategy_name: str, regime: RegimeType, 
                                  parameter_space: Dict[str, ParameterBounds],
                                  historical_data: pd.DataFrame,
                                  optimization_type: OptimizationType = OptimizationType.BAYESIAN) -> OptimizationResult:
        """
        Optimize parameters specifically for a market regime
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime to optimize for
            parameter_space: Parameter space to optimize
            historical_data: Historical data filtered for the specific regime
            optimization_type: Optimization algorithm to use
            
        Returns:
            Optimization result
        """
        self.logger.info(f"Optimizing {strategy_name} parameters for {regime.value} regime")
        
        # Filter historical data for the specific regime if regime information is available
        regime_data = self._filter_data_by_regime(historical_data, regime)
        
        if len(regime_data) < 50:  # Minimum data requirement
            self.logger.warning(f"Insufficient data for {regime.value} regime optimization: {len(regime_data)} points")
            # Use full dataset as fallback
            regime_data = historical_data
        
        # Perform optimization
        result = self.optimize_parameters(
            strategy_name=f"{strategy_name}_{regime.value}",
            parameter_space=parameter_space,
            historical_data=regime_data,
            optimization_type=optimization_type
        )
        
        # Store regime-specific parameters if optimization was successful
        if result.success:
            self.set_regime_parameters(strategy_name, regime, result.new_parameters)
            
            # Track this as a regime-specific optimization
            result.metadata = result.metadata or {}
            result.metadata['regime'] = regime.value
            result.metadata['regime_data_points'] = len(regime_data)
        
        return result
    
    def _filter_data_by_regime(self, data: pd.DataFrame, regime: RegimeType) -> pd.DataFrame:
        """
        Filter historical data to include only periods matching the specified regime
        
        Args:
            data: Historical market data
            regime: Target regime to filter for
            
        Returns:
            Filtered data
        """
        # This is a placeholder implementation
        # In a real system, you would have regime labels in your data
        # For now, we'll use simple heuristics based on volatility and trend
        
        if 'regime' in data.columns:
            # If regime data is available, use it directly
            return data[data['regime'] == regime.value]
        
        # Fallback: use simple heuristics to approximate regime periods
        if len(data) < 20:
            return data
        
        # Calculate rolling volatility and trend
        window = min(20, len(data) // 4)
        data = data.copy()
        
        if 'close' in data.columns:
            data['returns'] = data['close'].pct_change()
            data['volatility'] = data['returns'].rolling(window).std()
            data['trend'] = data['close'].rolling(window).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0])
            
            # Simple regime classification
            vol_threshold = data['volatility'].quantile(0.7)
            trend_threshold = 0.001  # Adjust based on your data
            
            if regime == RegimeType.HIGH_VOLATILITY:
                return data[data['volatility'] > vol_threshold]
            elif regime == RegimeType.LOW_VOLATILITY:
                return data[data['volatility'] <= data['volatility'].quantile(0.3)]
            elif regime == RegimeType.TRENDING_BULL:
                return data[data['trend'] > trend_threshold]
            elif regime == RegimeType.TRENDING_BEAR:
                return data[data['trend'] < -trend_threshold]
            elif regime == RegimeType.RANGING:
                return data[abs(data['trend']) <= trend_threshold]
        
        # If we can't filter effectively, return original data
        return data
    
    def get_regime_transition_frequency(self) -> Dict[str, float]:
        """
        Calculate regime transition frequencies
        
        Returns:
            Dictionary with transition statistics
        """
        if len(self.regime_transition_history) < 2:
            return {'total_transitions': 0, 'avg_regime_duration': 0.0}
        
        transitions = []
        for i in range(1, len(self.regime_transition_history)):
            prev_regime, prev_time = self.regime_transition_history[i-1]
            curr_regime, curr_time = self.regime_transition_history[i]
            
            if prev_regime != curr_regime:
                duration = (curr_time - prev_time).total_seconds() / 3600  # Hours
                transitions.append(duration)
        
        if not transitions:
            return {'total_transitions': 0, 'avg_regime_duration': 0.0}
        
        return {
            'total_transitions': len(transitions),
            'avg_regime_duration': np.mean(transitions),
            'min_regime_duration': np.min(transitions),
            'max_regime_duration': np.max(transitions),
            'std_regime_duration': np.std(transitions)
        }
    
    def export_regime_parameters(self, filepath: str) -> None:
        """
        Export regime-specific parameters to a file
        
        Args:
            filepath: Path to save the parameters
        """
        export_data = {
            'regime_parameters': {
                strategy: {regime.value: params for regime, params in regimes.items()}
                for strategy, regimes in self.regime_parameters.items()
            },
            'regime_performance': {
                strategy: {regime.value: perf_list for regime, perf_list in regimes.items()}
                for strategy, regimes in self.regime_performance.items()
            },
            'current_regime': self.current_regime.value if self.current_regime else None,
            'transition_history': [
                (regime.value, timestamp.isoformat()) 
                for regime, timestamp in self.regime_transition_history
            ],
            'export_timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        self.logger.info(f"Exported regime parameters to {filepath}")
    
    def import_regime_parameters(self, filepath: str) -> None:
        """
        Import regime-specific parameters from a file
        
        Args:
            filepath: Path to load the parameters from
        """
        try:
            with open(filepath, 'r') as f:
                import_data = json.load(f)
            
            # Import regime parameters
            for strategy, regimes in import_data.get('regime_parameters', {}).items():
                self.regime_parameters[strategy] = {}
                for regime_str, params in regimes.items():
                    regime = RegimeType(regime_str)
                    self.regime_parameters[strategy][regime] = params
            
            # Import performance history
            for strategy, regimes in import_data.get('regime_performance', {}).items():
                self.regime_performance[strategy] = {}
                for regime_str, perf_list in regimes.items():
                    regime = RegimeType(regime_str)
                    self.regime_performance[strategy][regime] = perf_list
            
            # Import current regime
            if import_data.get('current_regime'):
                self.current_regime = RegimeType(import_data['current_regime'])
            
            # Import transition history
            self.regime_transition_history = []
            for regime_str, timestamp_str in import_data.get('transition_history', []):
                regime = RegimeType(regime_str)
                timestamp = datetime.fromisoformat(timestamp_str)
                self.regime_transition_history.append((regime, timestamp))
            
            self.logger.info(f"Imported regime parameters from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error importing regime parameters: {str(e)}")
            raise
    
    def get_optimization_history(self, strategy_name: Optional[str] = None) -> List[OptimizationResult]:
        """
        Get optimization history, optionally filtered by strategy
        
        Args:
            strategy_name: Optional strategy name to filter by
            
        Returns:
            List of optimization results
        """
        if strategy_name is None:
            return self.optimization_history.copy()
        
        return [result for result in self.optimization_history if result.strategy_name == strategy_name]
    
    def get_best_parameters(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        Get best parameters for a strategy
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Best parameters or None if not found
        """
        return self.best_parameters.get(strategy_name)
    
    def estimate_optimization_time(self, parameter_space: Dict[str, ParameterBounds], 
                                  optimization_type: OptimizationType,
                                  historical_data: pd.DataFrame) -> timedelta:
        """
        Estimate optimization time based on parameter space and data size
        
        Args:
            parameter_space: Parameter space to optimize
            optimization_type: Type of optimization
            historical_data: Historical data
            
        Returns:
            Estimated optimization time
        """
        # Simple estimation based on parameter space size and optimization type
        param_count = len(parameter_space)
        data_size = len(historical_data)
        
        # Base time estimates (in seconds)
        base_times = {
            OptimizationType.BAYESIAN: 2.0,
            OptimizationType.GENETIC: 5.0,
            OptimizationType.GRID_SEARCH: 1.0,
            OptimizationType.RANDOM_SEARCH: 0.5
        }
        
        base_time = base_times.get(optimization_type, 2.0)
        
        # Scale by parameter count and data size
        scaling_factor = (param_count ** 1.5) * (data_size / 1000) ** 0.5
        estimated_seconds = base_time * scaling_factor * self.config.max_iterations / 100
        
        return timedelta(seconds=max(1, estimated_seconds))
    
    def validate_parameter_bounds(self, parameter_space: Dict[str, ParameterBounds]) -> bool:
        """
        Validate parameter bounds
        
        Args:
            parameter_space: Parameter space to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            for param_name, bounds in parameter_space.items():
                # ParameterBounds constructor will raise ValueError if invalid
                if bounds.param_type in [ParameterType.CONTINUOUS, ParameterType.INTEGER]:
                    if bounds.min_value is None or bounds.max_value is None:
                        return False
                    if bounds.min_value >= bounds.max_value:
                        return False
                elif bounds.param_type == ParameterType.CATEGORICAL:
                    if not bounds.categories or len(bounds.categories) == 0:
                        return False
            return True
        except Exception:
            return False
    
    def save_optimization_state(self, filepath: str) -> None:
        """
        Save optimization state to file
        
        Args:
            filepath: Path to save the state
        """
        state_data = {
            'optimization_history': [
                {
                    'optimization_id': result.optimization_id,
                    'strategy_name': result.strategy_name,
                    'optimization_method': result.optimization_method,
                    'old_parameters': result.old_parameters,
                    'new_parameters': result.new_parameters,
                    'performance_improvement': result.performance_improvement,
                    'confidence_score': result.confidence_score,
                    'validation_period': result.validation_period.total_seconds(),
                    'applied_at': result.applied_at.isoformat() if result.applied_at else None,
                    'success': result.success,
                    'error_message': result.error_message,
                    'metadata': result.metadata
                }
                for result in self.optimization_history
            ],
            'best_parameters': self.best_parameters,
            'parameter_bounds': {
                name: {
                    'param_type': bounds.param_type.value,
                    'min_value': bounds.min_value,
                    'max_value': bounds.max_value,
                    'categories': bounds.categories,
                    'default_value': bounds.default_value
                }
                for name, bounds in self.parameter_bounds.items()
            }
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(state_data, f)
        
        self.logger.info(f"Saved optimization state to {filepath}")
    
    def load_optimization_state(self, filepath: str) -> None:
        """
        Load optimization state from file
        
        Args:
            filepath: Path to load the state from
        """
        try:
            with open(filepath, 'rb') as f:
                state_data = pickle.load(f)
            
            # Restore optimization history
            self.optimization_history = []
            for result_data in state_data.get('optimization_history', []):
                result = OptimizationResult(
                    optimization_id=result_data['optimization_id'],
                    strategy_name=result_data['strategy_name'],
                    optimization_method=result_data['optimization_method'],
                    old_parameters=result_data['old_parameters'],
                    new_parameters=result_data['new_parameters'],
                    performance_improvement=result_data['performance_improvement'],
                    confidence_score=result_data['confidence_score'],
                    validation_period=timedelta(seconds=result_data['validation_period']),
                    applied_at=datetime.fromisoformat(result_data['applied_at']) if result_data['applied_at'] else None,
                    success=result_data['success'],
                    error_message=result_data.get('error_message'),
                    metadata=result_data.get('metadata')
                )
                self.optimization_history.append(result)
            
            # Restore best parameters
            self.best_parameters = state_data.get('best_parameters', {})
            
            # Restore parameter bounds
            self.parameter_bounds = {}
            for name, bounds_data in state_data.get('parameter_bounds', {}).items():
                bounds = ParameterBounds(
                    param_type=ParameterType(bounds_data['param_type']),
                    min_value=bounds_data['min_value'],
                    max_value=bounds_data['max_value'],
                    categories=bounds_data['categories'],
                    default_value=bounds_data['default_value']
                )
                self.parameter_bounds[name] = bounds
            
            self.logger.info(f"Loaded optimization state from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error loading optimization state: {str(e)}")
            raise
    
    # Parameter validation and rollback system methods
    
    def validate_parameter_change(self, strategy_name: str, old_parameters: Dict[str, Any], 
                                 new_parameters: Dict[str, Any], validation_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate parameter changes before application
        
        Args:
            strategy_name: Name of the strategy
            old_parameters: Current parameters
            new_parameters: Proposed new parameters
            validation_data: Data to use for validation
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'is_valid': True,
            'confidence': 0.0,
            'performance_improvement': 0.0,
            'risk_increase': 0.0,
            'validation_errors': [],
            'recommendation': 'approve',
            'validation_timestamp': datetime.now()
        }
        
        try:
            # Evaluate old parameters performance
            old_performance = self.performance_evaluator.evaluate_parameters(
                strategy_name, old_parameters, validation_data
            )
            
            # Evaluate new parameters performance
            new_performance = self.performance_evaluator.evaluate_parameters(
                strategy_name, new_parameters, validation_data
            )
            
            # Calculate performance improvement
            performance_improvement = new_performance.total_return - old_performance.total_return
            validation_result['performance_improvement'] = performance_improvement
            
            # Calculate risk increase
            risk_increase = new_performance.max_drawdown - old_performance.max_drawdown
            validation_result['risk_increase'] = risk_increase
            
            # Validation rules
            min_improvement_threshold = 0.01  # 1% minimum improvement
            max_risk_increase = 0.02  # 2% maximum risk increase
            
            # Check minimum improvement
            if performance_improvement < min_improvement_threshold:
                validation_result['validation_errors'].append(
                    f"Performance improvement {performance_improvement:.4f} below threshold {min_improvement_threshold}"
                )
                validation_result['is_valid'] = False
            
            # Check risk increase
            if risk_increase > max_risk_increase:
                validation_result['validation_errors'].append(
                    f"Risk increase {risk_increase:.4f} exceeds threshold {max_risk_increase}"
                )
                validation_result['is_valid'] = False
            
            # Calculate confidence based on improvement and risk
            if performance_improvement > 0 and risk_increase <= 0:
                validation_result['confidence'] = min(0.95, performance_improvement * 10)
            elif performance_improvement > 0:
                validation_result['confidence'] = max(0.1, performance_improvement * 5 - risk_increase * 10)
            else:
                validation_result['confidence'] = 0.1
            
            # Set recommendation
            if validation_result['is_valid'] and validation_result['confidence'] > 0.7:
                validation_result['recommendation'] = 'approve'
            elif validation_result['is_valid'] and validation_result['confidence'] > 0.4:
                validation_result['recommendation'] = 'approve_with_caution'
            else:
                validation_result['recommendation'] = 'reject'
            
            self.logger.info(f"Parameter validation for {strategy_name}: {validation_result['recommendation']}")
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['validation_errors'].append(f"Validation error: {str(e)}")
            validation_result['recommendation'] = 'reject'
            self.logger.error(f"Error validating parameters for {strategy_name}: {str(e)}")
        
        return validation_result
    
    def create_ab_test(self, strategy_name: str, control_parameters: Dict[str, Any], 
                      test_parameters: Dict[str, Any], allocation_ratio: float = 0.5,
                      test_duration: timedelta = timedelta(days=7)) -> str:
        """
        Create an A/B test for parameter changes
        
        Args:
            strategy_name: Name of the strategy
            control_parameters: Current (control) parameters
            test_parameters: New (test) parameters
            allocation_ratio: Fraction of capital to allocate to test parameters (0.0 to 1.0)
            test_duration: Duration of the A/B test
            
        Returns:
            A/B test ID
        """
        test_id = f"{strategy_name}_ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        ab_test = {
            'test_id': test_id,
            'strategy_name': strategy_name,
            'control_parameters': control_parameters.copy(),
            'test_parameters': test_parameters.copy(),
            'allocation_ratio': allocation_ratio,
            'start_time': datetime.now(),
            'end_time': datetime.now() + test_duration,
            'status': 'active',
            'control_performance': [],
            'test_performance': [],
            'control_trades': [],
            'test_trades': []
        }
        
        # Store A/B test
        if not hasattr(self, 'ab_tests'):
            self.ab_tests = {}
        self.ab_tests[test_id] = ab_test
        
        self.logger.info(f"Created A/B test {test_id} for {strategy_name}")
        return test_id
    
    def update_ab_test(self, test_id: str, control_performance: Optional[float] = None,
                      test_performance: Optional[float] = None) -> None:
        """
        Update A/B test with performance data
        
        Args:
            test_id: A/B test ID
            control_performance: Performance of control parameters
            test_performance: Performance of test parameters
        """
        if not hasattr(self, 'ab_tests') or test_id not in self.ab_tests:
            self.logger.error(f"A/B test {test_id} not found")
            return
        
        ab_test = self.ab_tests[test_id]
        
        if control_performance is not None:
            ab_test['control_performance'].append({
                'timestamp': datetime.now(),
                'performance': control_performance
            })
        
        if test_performance is not None:
            ab_test['test_performance'].append({
                'timestamp': datetime.now(),
                'performance': test_performance
            })
        
        # Check if test should be concluded
        if datetime.now() >= ab_test['end_time']:
            self._conclude_ab_test(test_id)
    
    def _conclude_ab_test(self, test_id: str) -> Dict[str, Any]:
        """
        Conclude an A/B test and determine the winner
        
        Args:
            test_id: A/B test ID
            
        Returns:
            A/B test results
        """
        if not hasattr(self, 'ab_tests') or test_id not in self.ab_tests:
            return {'error': f'A/B test {test_id} not found'}
        
        ab_test = self.ab_tests[test_id]
        ab_test['status'] = 'completed'
        ab_test['conclusion_time'] = datetime.now()
        
        # Calculate average performance
        control_performances = [p['performance'] for p in ab_test['control_performance']]
        test_performances = [p['performance'] for p in ab_test['test_performance']]
        
        if not control_performances or not test_performances:
            ab_test['winner'] = 'inconclusive'
            ab_test['reason'] = 'Insufficient data'
            return ab_test
        
        control_avg = np.mean(control_performances)
        test_avg = np.mean(test_performances)
        
        # Statistical significance test (simple t-test approximation)
        if len(control_performances) > 1 and len(test_performances) > 1:
            control_std = np.std(control_performances)
            test_std = np.std(test_performances)
            
            # Simple significance test
            pooled_std = np.sqrt((control_std**2 + test_std**2) / 2)
            if pooled_std > 0:
                t_stat = abs(test_avg - control_avg) / pooled_std
                significant = t_stat > 1.96  # Approximate 95% confidence
            else:
                significant = test_avg != control_avg
        else:
            significant = abs(test_avg - control_avg) > 0.01  # 1% threshold
        
        # Determine winner
        if significant:
            if test_avg > control_avg:
                ab_test['winner'] = 'test'
                ab_test['reason'] = f'Test parameters performed {((test_avg - control_avg) / control_avg * 100):.2f}% better'
            else:
                ab_test['winner'] = 'control'
                ab_test['reason'] = f'Control parameters performed {((control_avg - test_avg) / test_avg * 100):.2f}% better'
        else:
            ab_test['winner'] = 'inconclusive'
            ab_test['reason'] = 'No statistically significant difference'
        
        ab_test['control_avg_performance'] = control_avg
        ab_test['test_avg_performance'] = test_avg
        
        self.logger.info(f"A/B test {test_id} concluded: {ab_test['winner']} - {ab_test['reason']}")
        return ab_test
    
    def get_ab_test_results(self, test_id: str) -> Optional[Dict[str, Any]]:
        """
        Get A/B test results
        
        Args:
            test_id: A/B test ID
            
        Returns:
            A/B test results or None if not found
        """
        if not hasattr(self, 'ab_tests'):
            return None
        return self.ab_tests.get(test_id)
    
    def create_parameter_rollback_point(self, strategy_name: str, parameters: Dict[str, Any],
                                       performance_baseline: Optional[float] = None) -> str:
        """
        Create a rollback point for parameters
        
        Args:
            strategy_name: Name of the strategy
            parameters: Current parameters to save
            performance_baseline: Optional performance baseline
            
        Returns:
            Rollback point ID
        """
        rollback_id = f"{strategy_name}_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        rollback_point = {
            'rollback_id': rollback_id,
            'strategy_name': strategy_name,
            'parameters': parameters.copy(),
            'performance_baseline': performance_baseline,
            'created_at': datetime.now(),
            'regime_context': self.current_regime,
            'is_active': True
        }
        
        # Store rollback point
        if not hasattr(self, 'rollback_points'):
            self.rollback_points = {}
        self.rollback_points[rollback_id] = rollback_point
        
        self.logger.info(f"Created rollback point {rollback_id} for {strategy_name}")
        return rollback_id
    
    def rollback_parameters(self, rollback_id: str) -> bool:
        """
        Rollback parameters to a previous state
        
        Args:
            rollback_id: Rollback point ID
            
        Returns:
            True if rollback was successful, False otherwise
        """
        if not hasattr(self, 'rollback_points') or rollback_id not in self.rollback_points:
            self.logger.error(f"Rollback point {rollback_id} not found")
            return False
        
        rollback_point = self.rollback_points[rollback_id]
        
        if not rollback_point['is_active']:
            self.logger.error(f"Rollback point {rollback_id} is not active")
            return False
        
        try:
            strategy_name = rollback_point['strategy_name']
            parameters = rollback_point['parameters']
            regime = rollback_point['regime_context']
            
            # Restore parameters
            if regime and regime in self.regime_parameters.get(strategy_name, {}):
                self.regime_parameters[strategy_name][regime] = parameters.copy()
            
            # Update best parameters
            self.best_parameters[strategy_name] = parameters.copy()
            
            # Mark rollback point as used
            rollback_point['is_active'] = False
            rollback_point['used_at'] = datetime.now()
            
            self.logger.info(f"Successfully rolled back parameters for {strategy_name} using {rollback_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error rolling back parameters: {str(e)}")
            return False
    
    def auto_rollback_check(self, strategy_name: str, current_performance: float,
                           performance_threshold: float = -0.05) -> Optional[str]:
        """
        Check if automatic rollback should be triggered
        
        Args:
            strategy_name: Name of the strategy
            current_performance: Current performance metric
            performance_threshold: Threshold for triggering rollback (negative value)
            
        Returns:
            Rollback ID if rollback was triggered, None otherwise
        """
        if not hasattr(self, 'rollback_points'):
            return None
        
        # Find the most recent active rollback point for this strategy
        strategy_rollbacks = [
            (rollback_id, rollback_point) 
            for rollback_id, rollback_point in self.rollback_points.items()
            if (rollback_point['strategy_name'] == strategy_name and 
                rollback_point['is_active'] and 
                rollback_point['performance_baseline'] is not None)
        ]
        
        if not strategy_rollbacks:
            return None
        
        # Get the most recent rollback point
        latest_rollback_id, latest_rollback = max(
            strategy_rollbacks, 
            key=lambda x: x[1]['created_at']
        )
        
        baseline_performance = latest_rollback['performance_baseline']
        performance_decline = (current_performance - baseline_performance) / abs(baseline_performance)
        
        if performance_decline < performance_threshold:
            self.logger.warning(
                f"Performance decline {performance_decline:.2%} exceeds threshold {performance_threshold:.2%} "
                f"for {strategy_name}. Triggering automatic rollback."
            )
            
            if self.rollback_parameters(latest_rollback_id):
                return latest_rollback_id
        
        return None
    
    def get_parameter_change_history(self, strategy_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get parameter change history for a strategy
        
        Args:
            strategy_name: Name of the strategy
            limit: Maximum number of history entries to return
            
        Returns:
            List of parameter change history entries
        """
        history = []
        
        # Get optimization history
        for result in self.optimization_history:
            if result.strategy_name == strategy_name:
                history.append({
                    'timestamp': result.applied_at or datetime.now(),
                    'type': 'optimization',
                    'old_parameters': result.old_parameters,
                    'new_parameters': result.new_parameters,
                    'performance_improvement': result.performance_improvement,
                    'method': result.optimization_method,
                    'confidence': result.confidence_score
                })
        
        # Get rollback history
        if hasattr(self, 'rollback_points'):
            for rollback_id, rollback_point in self.rollback_points.items():
                if rollback_point['strategy_name'] == strategy_name and not rollback_point['is_active']:
                    history.append({
                        'timestamp': rollback_point.get('used_at', rollback_point['created_at']),
                        'type': 'rollback',
                        'parameters': rollback_point['parameters'],
                        'rollback_id': rollback_id,
                        'regime_context': rollback_point['regime_context']
                    })
        
        # Sort by timestamp and limit
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        return history[:limit]
    
    def export_parameter_audit_trail(self, filepath: str, strategy_name: Optional[str] = None) -> None:
        """
        Export parameter change audit trail to file
        
        Args:
            filepath: Path to save the audit trail
            strategy_name: Optional strategy name to filter by
        """
        audit_data = {
            'export_timestamp': datetime.now().isoformat(),
            'optimization_history': [],
            'rollback_points': [],
            'ab_tests': []
        }
        
        # Export optimization history
        for result in self.optimization_history:
            if strategy_name is None or result.strategy_name == strategy_name:
                audit_data['optimization_history'].append({
                    'optimization_id': result.optimization_id,
                    'strategy_name': result.strategy_name,
                    'optimization_method': result.optimization_method,
                    'old_parameters': result.old_parameters,
                    'new_parameters': result.new_parameters,
                    'performance_improvement': result.performance_improvement,
                    'confidence_score': result.confidence_score,
                    'applied_at': result.applied_at.isoformat() if result.applied_at else None,
                    'success': result.success,
                    'metadata': result.metadata
                })
        
        # Export rollback points
        if hasattr(self, 'rollback_points'):
            for rollback_id, rollback_point in self.rollback_points.items():
                if strategy_name is None or rollback_point['strategy_name'] == strategy_name:
                    audit_data['rollback_points'].append({
                        'rollback_id': rollback_id,
                        'strategy_name': rollback_point['strategy_name'],
                        'parameters': rollback_point['parameters'],
                        'performance_baseline': rollback_point['performance_baseline'],
                        'created_at': rollback_point['created_at'].isoformat(),
                        'regime_context': rollback_point['regime_context'].value if rollback_point['regime_context'] else None,
                        'is_active': rollback_point['is_active'],
                        'used_at': rollback_point.get('used_at').isoformat() if rollback_point.get('used_at') else None
                    })
        
        # Export A/B tests
        if hasattr(self, 'ab_tests'):
            for test_id, ab_test in self.ab_tests.items():
                if strategy_name is None or ab_test['strategy_name'] == strategy_name:
                    audit_data['ab_tests'].append({
                        'test_id': test_id,
                        'strategy_name': ab_test['strategy_name'],
                        'control_parameters': ab_test['control_parameters'],
                        'test_parameters': ab_test['test_parameters'],
                        'allocation_ratio': ab_test['allocation_ratio'],
                        'start_time': ab_test['start_time'].isoformat(),
                        'end_time': ab_test['end_time'].isoformat(),
                        'status': ab_test['status'],
                        'winner': ab_test.get('winner'),
                        'reason': ab_test.get('reason'),
                        'control_avg_performance': ab_test.get('control_avg_performance'),
                        'test_avg_performance': ab_test.get('test_avg_performance')
                    })
        
        with open(filepath, 'w') as f:
            json.dump(audit_data, f, indent=2)
        
        self.logger.info(f"Exported parameter audit trail to {filepath}")
    
    def cleanup_old_rollback_points(self, max_age: timedelta = timedelta(days=30)) -> int:
        """
        Clean up old rollback points
        
        Args:
            max_age: Maximum age of rollback points to keep
            
        Returns:
            Number of rollback points cleaned up
        """
        if not hasattr(self, 'rollback_points'):
            return 0
        
        cutoff_time = datetime.now() - max_age
        to_remove = []
        
        for rollback_id, rollback_point in self.rollback_points.items():
            if rollback_point['created_at'] < cutoff_time and not rollback_point['is_active']:
                to_remove.append(rollback_id)
        
        for rollback_id in to_remove:
            del self.rollback_points[rollback_id]
        
        if to_remove:
            self.logger.info(f"Cleaned up {len(to_remove)} old rollback points")
        
        return len(to_remove)


class ParameterConstraintManager:
    """Manages parameter constraints for optimization."""
    
    def __init__(self):
        self.constraints: Dict[str, List[Callable]] = {}
        self.constraint_descriptions: Dict[str, List[str]] = {}
    
    def add_constraint(self, parameter_name: str, constraint_func: Callable, description: str = ""):
        """Add a constraint for a parameter."""
        if parameter_name not in self.constraints:
            self.constraints[parameter_name] = []
            self.constraint_descriptions[parameter_name] = []
        
        self.constraints[parameter_name].append(constraint_func)
        self.constraint_descriptions[parameter_name].append(description)
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate parameters against constraints."""
        violations = []
        
        for param_name, value in parameters.items():
            if param_name in self.constraints:
                for i, constraint in enumerate(self.constraints[param_name]):
                    try:
                        if not constraint(value):
                            description = self.constraint_descriptions[param_name][i]
                            violations.append(f"{param_name}: {description}")
                    except Exception as e:
                        violations.append(f"{param_name}: Constraint evaluation error - {str(e)}")
        
        return len(violations) == 0, violations
    
    def get_constraints(self, parameter_name: str) -> List[Callable]:
        """Get constraints for a parameter."""
        return self.constraints.get(parameter_name, [])
    
    def _calculate_walkforward_statistics(self, results: List[OptimizationResult]):
        """Calculate statistics for walk-forward analysis results"""
        if not results:
            return
        
        successful_results = [r for r in results if r.success and hasattr(r, 'out_of_sample_performance')]
        
        if not successful_results:
            self.logger.warning("No successful walk-forward results")
            return
        
        # Calculate statistics
        oos_returns = [r.out_of_sample_performance for r in successful_results]
        improvements = [r.performance_improvement for r in successful_results]
        
        stats = {
            'total_windows': len(results),
            'successful_windows': len(successful_results),
            'success_rate': len(successful_results) / len(results),
            'avg_oos_return': np.mean(oos_returns),
            'std_oos_return': np.std(oos_returns),
            'avg_improvement': np.mean(improvements),
            'positive_improvement_rate': sum(1 for imp in improvements if imp > 0) / len(improvements),
            'sharpe_ratio': np.mean(oos_returns) / np.std(oos_returns) if np.std(oos_returns) > 0 else 0
        }
        
        self.logger.info(f"Walk-forward statistics: {stats}")
        
        # Store statistics in the last result
        if results:
            results[-1].metadata = results[-1].metadata or {}
            results[-1].metadata['walkforward_stats'] = stats
    
    def _generate_parameter_grid(self, parameter_space: Dict[str, ParameterBounds], grid_points: int) -> List[Dict]:
        """Generate parameter grid for grid search"""
        param_values = {}
        
        for param_name, bounds in parameter_space.items():
            if bounds.param_type == ParameterType.CONTINUOUS:
                param_values[param_name] = np.linspace(bounds.min_value, bounds.max_value, grid_points)
            elif bounds.param_type == ParameterType.INTEGER:
                param_values[param_name] = np.linspace(int(bounds.min_value), int(bounds.max_value), 
                                                     min(grid_points, int(bounds.max_value) - int(bounds.min_value) + 1), 
                                                     dtype=int)
            elif bounds.param_type == ParameterType.CATEGORICAL:
                param_values[param_name] = bounds.categories
        
        # Generate all combinations
        import itertools
        param_names = list(param_values.keys())
        param_combinations = itertools.product(*[param_values[name] for name in param_names])
        
        grid = []
        for combination in param_combinations:
            grid.append(dict(zip(param_names, combination)))
        
        return grid
    
    def _calculate_optimization_confidence(self, result) -> float:
        """Calculate confidence score for Bayesian optimization result"""
        if not hasattr(result, 'func_vals') or len(result.func_vals) < 2:
            return 0.5
        
        # Calculate improvement over iterations
        improvements = []
        best_so_far = result.func_vals[0]
        
        for val in result.func_vals[1:]:
            if val < best_so_far:  # Remember we minimize, so lower is better
                improvement = (best_so_far - val) / abs(best_so_far) if best_so_far != 0 else 0
                improvements.append(improvement)
                best_so_far = val
        
        if not improvements:
            return 0.3  # Low confidence if no improvements
        
        # Confidence based on consistency of improvements
        avg_improvement = np.mean(improvements)
        std_improvement = np.std(improvements) if len(improvements) > 1 else 0
        
        # Higher confidence for consistent improvements
        confidence = min(0.9, 0.5 + avg_improvement * 10 - std_improvement * 2)
        return max(0.1, confidence)

        
        # Convergence score (0-1)
        improvement_ratio = (func_vals[0] - overall_best) / abs(func_vals[0]) if func_vals[0] != 0 else 0
        convergence_score = min(1.0, improvement_ratio)
        
        # Stability score (lower variance in recent results = higher confidence)
        recent_variance = np.var(func_vals[-n_recent:])
        stability_score = 1.0 / (1.0 + recent_variance)
        
        # Combined confidence
        confidence = (convergence_score + stability_score) / 2
        return max(0.1, min(0.95, confidence))
    
    # Regime-specific parameter adaptation methods
    
    def set_regime_parameters(self, strategy_name: str, regime: RegimeType, parameters: Dict[str, Any]) -> None:
        """
        Set parameters for a specific strategy and market regime.
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime type
            parameters: Parameter dictionary for this regime
        """
        if strategy_name not in self.regime_parameters:
            self.regime_parameters[strategy_name] = {}
        
        self.regime_parameters[strategy_name][regime] = parameters.copy()
        self.logger.info(f"Set regime parameters for {strategy_name} in {regime}: {parameters}")
    
    def get_regime_parameters(self, strategy_name: str, regime: RegimeType) -> Optional[Dict[str, Any]]:
        """
        Get parameters for a specific strategy and market regime.
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime type
            
        Returns:
            Parameter dictionary or None if not found
        """
        if strategy_name in self.regime_parameters:
            return self.regime_parameters[strategy_name].get(regime)
        return None
    
    def adapt_parameters_to_regime(self, strategy_name: str, current_regime: RegimeType, 
                                 market_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Adapt parameters based on current market regime.
        
        Args:
            strategy_name: Name of the strategy
            current_regime: Current market regime
            market_data: Recent market data for context
            
        Returns:
            Adapted parameters or None if no regime-specific parameters exist
        """
        self.logger.info(f"Adapting parameters for {strategy_name} to regime {current_regime}")
        
        # Get regime-specific parameters
        regime_params = self.get_regime_parameters(strategy_name, current_regime)
        if not regime_params:
            self.logger.info(f"No specific parameters for {strategy_name} in {current_regime}")
            return None
        
        # If this is a regime transition, apply smoothing
        if self.current_regime and self.current_regime != current_regime:
            previous_params = self.get_regime_parameters(strategy_name, self.current_regime)
            if previous_params:
                regime_params = self._interpolate_parameters(
                    previous_params, regime_params, self.regime_transition_smoothing
                )
                self.logger.info(f"Applied transition smoothing from {self.current_regime} to {current_regime}")
        
        self.current_regime = current_regime
        return regime_params
    
    def optimize_regime_parameters(self, strategy_name: str, regime: RegimeType,
                                 parameter_space: Dict[str, ParameterBounds],
                                 historical_data: pd.DataFrame,
                                 optimization_type: OptimizationType = OptimizationType.BAYESIAN) -> OptimizationResult:
        """
        Optimize parameters specifically for a market regime.
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime to optimize for
            parameter_space: Parameter space for optimization
            historical_data: Historical data filtered for this regime
            optimization_type: Optimization algorithm to use
            
        Returns:
            OptimizationResult with regime-specific optimization details
        """
        self.logger.info(f"Optimizing parameters for {strategy_name} in regime {regime}")
        
        # Filter historical data for this regime (if regime data is available)
        regime_data = self._filter_data_by_regime(historical_data, regime)
        if len(regime_data) < 50:  # Minimum data points for meaningful optimization
            self.logger.warning(f"Insufficient regime-specific data for {regime}: {len(regime_data)} points")
            regime_data = historical_data  # Fall back to all data
        
        # Perform optimization
        result = self.optimize_parameters(
            strategy_name=f"{strategy_name}_{regime.value}",
            parameter_space=parameter_space,
            historical_data=regime_data,
            optimization_type=optimization_type
        )
        
        # Store regime-specific results
        if result.success:
            self.set_regime_parameters(strategy_name, regime, result.new_parameters)
            self._update_regime_performance(strategy_name, regime, result.performance_improvement)
        
        # Update result metadata
        result.metadata = result.metadata or {}
        result.metadata['regime'] = regime.value
        result.metadata['regime_data_points'] = len(regime_data)
        
        return result
    
    def get_regime_performance_history(self, strategy_name: str, regime: RegimeType) -> List[float]:
        """
        Get performance history for a strategy in a specific regime.
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime type
            
        Returns:
            List of performance values
        """
        if strategy_name in self.regime_performance:
            return self.regime_performance[strategy_name].get(regime, [])
        return []
    
    def get_best_regime_for_strategy(self, strategy_name: str) -> Optional[RegimeType]:
        """
        Get the market regime where a strategy performs best.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Best performing regime or None if no data available
        """
        if strategy_name not in self.regime_performance:
            return None
        
        regime_avg_performance = {}
        for regime, performance_list in self.regime_performance[strategy_name].items():
            if performance_list:
                regime_avg_performance[regime] = np.mean(performance_list)
        
        if not regime_avg_performance:
            return None
        
        best_regime = max(regime_avg_performance, key=regime_avg_performance.get)
        self.logger.info(f"Best regime for {strategy_name}: {best_regime} (avg performance: {regime_avg_performance[best_regime]:.4f})")
        return best_regime
    
    def create_regime_parameter_sets(self, strategy_name: str, base_parameters: Dict[str, Any],
                                   parameter_variations: Dict[RegimeType, Dict[str, float]]) -> None:
        """
        Create parameter sets for different market regimes based on variations from base parameters.
        
        Args:
            strategy_name: Name of the strategy
            base_parameters: Base parameter set
            parameter_variations: Regime-specific parameter variations (multipliers or absolute changes)
        """
        self.logger.info(f"Creating regime parameter sets for {strategy_name}")
        
        for regime, variations in parameter_variations.items():
            regime_params = base_parameters.copy()
            
            for param_name, variation in variations.items():
                if param_name in regime_params:
                    base_value = regime_params[param_name]
                    
                    # Apply variation (assume multiplier if > 0.1, otherwise absolute change)
                    if abs(variation) > 0.1 and abs(variation) < 10:
                        regime_params[param_name] = base_value * variation
                    else:
                        regime_params[param_name] = base_value + variation
                    
                    self.logger.debug(f"Regime {regime}: {param_name} {base_value} -> {regime_params[param_name]}")
            
            self.set_regime_parameters(strategy_name, regime, regime_params)
    
    def validate_regime_parameters(self, strategy_name: str, regime: RegimeType, 
                                 parameters: Dict[str, Any]) -> bool:
        """
        Validate regime-specific parameters against bounds and constraints.
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime type
            parameters: Parameters to validate
            
        Returns:
            True if parameters are valid, False otherwise
        """
        for param_name, value in parameters.items():
            if param_name in self.parameter_bounds:
                bounds = self.parameter_bounds[param_name]
                if not bounds.is_valid_value(value):
                    self.logger.warning(f"Invalid parameter {param_name}={value} for {strategy_name} in {regime}")
                    return False
        
        return True
    
    def get_regime_transition_parameters(self, strategy_name: str, from_regime: RegimeType, 
                                       to_regime: RegimeType, transition_progress: float) -> Dict[str, Any]:
        """
        Get interpolated parameters during regime transitions.
        
        Args:
            strategy_name: Name of the strategy
            from_regime: Previous regime
            to_regime: New regime
            transition_progress: Progress of transition (0.0 to 1.0)
            
        Returns:
            Interpolated parameters
        """
        from_params = self.get_regime_parameters(strategy_name, from_regime)
        to_params = self.get_regime_parameters(strategy_name, to_regime)
        
        if not from_params or not to_params:
            return to_params or from_params or {}
        
        return self._interpolate_parameters(from_params, to_params, transition_progress)
    
    def _interpolate_parameters(self, from_params: Dict[str, Any], to_params: Dict[str, Any], 
                              progress: float) -> Dict[str, Any]:
        """
        Interpolate between two parameter sets.
        
        Args:
            from_params: Starting parameters
            to_params: Target parameters
            progress: Interpolation progress (0.0 to 1.0)
            
        Returns:
            Interpolated parameters
        """
        interpolated = {}
        
        for param_name in from_params:
            if param_name in to_params:
                from_val = from_params[param_name]
                to_val = to_params[param_name]
                
                # Handle numeric parameters
                if isinstance(from_val, (int, float)) and isinstance(to_val, (int, float)):
                    interpolated[param_name] = from_val + (to_val - from_val) * progress
                else:
                    # For non-numeric parameters, switch at 50% progress
                    interpolated[param_name] = to_val if progress > 0.5 else from_val
            else:
                interpolated[param_name] = from_params[param_name]
        
        # Add any new parameters from to_params
        for param_name in to_params:
            if param_name not in interpolated:
                interpolated[param_name] = to_params[param_name]
        
        return interpolated
    
    def _filter_data_by_regime(self, historical_data: pd.DataFrame, regime: RegimeType) -> pd.DataFrame:
        """
        Filter historical data to include only periods matching the specified regime.
        
        Args:
            historical_data: Full historical data
            regime: Regime to filter for
            
        Returns:
            Filtered data for the specified regime
        """
        # This is a placeholder implementation
        # In a real implementation, you would need regime detection data
        # For now, return all data as we don't have regime labels in historical data
        self.logger.debug(f"Filtering data for regime {regime} (placeholder implementation)")
        return historical_data
    
    def _update_regime_performance(self, strategy_name: str, regime: RegimeType, performance: float) -> None:
        """
        Update performance tracking for a strategy in a specific regime.
        
        Args:
            strategy_name: Name of the strategy
            regime: Market regime type
            performance: Performance value to add
        """
        if strategy_name not in self.regime_performance:
            self.regime_performance[strategy_name] = {}
        
        if regime not in self.regime_performance[strategy_name]:
            self.regime_performance[strategy_name][regime] = []
        
        self.regime_performance[strategy_name][regime].append(performance)
        
        # Keep only recent performance data (last 100 values)
        if len(self.regime_performance[strategy_name][regime]) > 100:
            self.regime_performance[strategy_name][regime] = self.regime_performance[strategy_name][regime][-100:]
        
        self.logger.debug(f"Updated performance for {strategy_name} in {regime}: {performance}")
    
    def get_regime_parameter_summary(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get a summary of regime-specific parameters for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Summary dictionary with regime parameters and performance
        """
        summary = {
            'strategy_name': strategy_name,
            'regimes': {},
            'best_regime': self.get_best_regime_for_strategy(strategy_name),
            'current_regime': self.current_regime
        }
        
        if strategy_name in self.regime_parameters:
            for regime, params in self.regime_parameters[strategy_name].items():
                performance_history = self.get_regime_performance_history(strategy_name, regime)
                summary['regimes'][regime.value] = {
                    'parameters': params,
                    'performance_history': performance_history,
                    'avg_performance': np.mean(performance_history) if performance_history else None,
                    'performance_count': len(performance_history)
                }
        

    
    def get_optimization_history(self, strategy_name: Optional[str] = None) -> List[OptimizationResult]:
        """Get optimization history, optionally filtered by strategy."""
        if strategy_name is None:
            return self.optimization_history.copy()
        else:
            return [result for result in self.optimization_history if result.strategy_name == strategy_name]
    
    def get_best_parameters(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get the best parameters for a strategy."""
        return self.best_parameters.get(strategy_name)
    
    def validate_parameter_bounds(self, parameter_space: Dict[str, ParameterBounds]) -> bool:
        """Validate parameter bounds for consistency."""
        try:
            for param_name, bounds in parameter_space.items():
                if bounds.param_type in [ParameterType.CONTINUOUS, ParameterType.INTEGER]:
                    if bounds.min_value is None or bounds.max_value is None:
                        self.logger.error(f"Missing min/max values for {param_name}")
                        return False
                    if bounds.min_value >= bounds.max_value:
                        self.logger.error(f"Invalid bounds for {param_name}: min >= max")
                        return False
                elif bounds.param_type == ParameterType.CATEGORICAL:
                    if not bounds.categories or len(bounds.categories) == 0:
                        self.logger.error(f"Missing categories for {param_name}")
                        return False
            return True
        except Exception as e:
            self.logger.error(f"Error validating parameter bounds: {str(e)}")
            return False
    
    def estimate_optimization_time(self, 
                                 parameter_space: Dict[str, ParameterBounds],
                                 optimization_type: OptimizationType,
                                 historical_data: pd.DataFrame) -> timedelta:
        """Estimate the time required for optimization."""
        # Base time estimates per evaluation (in seconds)
        base_times = {
            OptimizationType.BAYESIAN: 2.0,
            OptimizationType.GENETIC: 1.5,
            OptimizationType.GRID_SEARCH: 1.0,
            OptimizationType.RANDOM_SEARCH: 1.0
        }
        
        # Calculate number of evaluations
        if optimization_type == OptimizationType.BAYESIAN:
            n_evaluations = self.config.max_iterations
        elif optimization_type == OptimizationType.GENETIC:
            n_evaluations = self.genetic_config.population_size * self.genetic_config.generations
        elif optimization_type == OptimizationType.GRID_SEARCH:
            # Estimate grid size (5 points per dimension)
            n_evaluations = 5 ** len(parameter_space)
        else:  # Random search
            n_evaluations = self.config.max_iterations
        
        # Adjust for data size
        data_factor = max(1.0, len(historical_data) / 1000)
        
        # Calculate total time
        base_time = base_times.get(optimization_type, 1.5)
        total_seconds = n_evaluations * base_time * data_factor
        
        return timedelta(seconds=total_seconds)
    
    def save_optimization_state(self, filepath: str):
        """Save optimization state to file."""
        try:
            state = {
                'optimization_history': self.optimization_history,
                'parameter_bounds': self.parameter_bounds,
                'best_parameters': self.best_parameters,
                'config': self.config,
                'genetic_config': self.genetic_config,
                'walkforward_config': self.walkforward_config
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(state, f)
            
            self.logger.info(f"Optimization state saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving optimization state: {str(e)}")
    
    def load_optimization_state(self, filepath: str):
        """Load optimization state from file."""
        try:
            with open(filepath, 'rb') as f:
                state = pickle.load(f)
            
            self.optimization_history = state.get('optimization_history', [])
            self.parameter_bounds = state.get('parameter_bounds', {})
            self.best_parameters = state.get('best_parameters', {})
            
            # Update configs if they exist in the saved state
            if 'config' in state:
                self.config = state['config']
            if 'genetic_config' in state:
                self.genetic_config = state['genetic_config']
            if 'walkforward_config' in state:
                self.walkforward_config = state['walkforward_config']
            
            self.logger.info(f"Optimization state loaded from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error loading optimization state: {str(e)}")


class ParameterConstraintManager:
    """Manages parameter constraints and validation."""
    
    def __init__(self):
        self.constraints: Dict[str, List[Callable]] = {}
        self.constraint_descriptions: Dict[str, List[str]] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_constraint(self, parameter_name: str, constraint_func: Callable[[Any], bool], description: str = ""):
        """Add a constraint for a parameter."""
        if parameter_name not in self.constraints:
            self.constraints[parameter_name] = []
            self.constraint_descriptions[parameter_name] = []
        
        self.constraints[parameter_name].append(constraint_func)
        self.constraint_descriptions[parameter_name].append(description)
        
        self.logger.info(f"Added constraint for {parameter_name}: {description}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate parameters against all constraints."""
        violations = []
        
        for param_name, value in parameters.items():
            if param_name in self.constraints:
                for i, constraint in enumerate(self.constraints[param_name]):
                    try:
                        if not constraint(value):
                            description = self.constraint_descriptions[param_name][i]
                            violations.append(f"{param_name}: {description}")
                    except Exception as e:
                        violations.append(f"{param_name}: Constraint evaluation error - {str(e)}")
        
        return len(violations) == 0, violations
    
    def get_constraints(self, parameter_name: str) -> List[Callable]:
        """Get all constraints for a parameter."""
        return self.constraints.get(parameter_name, [])
    
    def remove_constraint(self, parameter_name: str, constraint_index: int = None):
        """Remove constraints for a parameter."""
        if parameter_name in self.constraints:
            if constraint_index is None:
                # Remove all constraints
                del self.constraints[parameter_name]
                del self.constraint_descriptions[parameter_name]
            else:
                # Remove specific constraint
                if 0 <= constraint_index < len(self.constraints[parameter_name]):
                    self.constraints[parameter_name].pop(constraint_index)
                    self.constraint_descriptions[parameter_name].pop(constraint_index)
    
    def clear_all_constraints(self):
        """Clear all constraints."""
        self.constraints.clear()
        self.constraint_descriptions.clear()


class ParameterValidator:
    """Validates parameter values and combinations."""
    
    def __init__(self, constraint_manager: ParameterConstraintManager = None):
        self.constraint_manager = constraint_manager or ParameterConstraintManager()
        self.logger = logging.getLogger(__name__)
    
    def validate_single_parameter(self, param_name: str, value: Any, bounds: ParameterBounds) -> Tuple[bool, str]:
        """Validate a single parameter value."""
        try:
            # Check type and bounds
            if not bounds.is_valid_value(value):
                return False, f"Value {value} is not valid for parameter {param_name} with bounds {bounds}"
            
            # Check custom constraints
            constraints = self.constraint_manager.get_constraints(param_name)
            for constraint in constraints:
                if not constraint(value):
                    return False, f"Value {value} violates constraint for parameter {param_name}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Error validating parameter {param_name}: {str(e)}"
    
    def validate_parameter_set(self, parameters: Dict[str, Any], parameter_space: Dict[str, ParameterBounds]) -> Tuple[bool, List[str]]:
        """Validate a complete parameter set."""
        errors = []
        
        # Validate individual parameters
        for param_name, value in parameters.items():
            if param_name in parameter_space:
                is_valid, error = self.validate_single_parameter(param_name, value, parameter_space[param_name])
                if not is_valid:
                    errors.append(error)
            else:
                errors.append(f"Unknown parameter: {param_name}")
        
        # Check for missing required parameters
        for param_name in parameter_space:
            if param_name not in parameters:
                if parameter_space[param_name].default_value is not None:
                    parameters[param_name] = parameter_space[param_name].default_value
                else:
                    errors.append(f"Missing required parameter: {param_name}")
        
        # Validate parameter combinations
        is_valid, constraint_violations = self.constraint_manager.validate_parameters(parameters)
        if not is_valid:
            errors.extend(constraint_violations)
        
        return len(errors) == 0, errors
    
    def sanitize_parameters(self, parameters: Dict[str, Any], parameter_space: Dict[str, ParameterBounds]) -> Dict[str, Any]:
        """Sanitize parameters to ensure they're within bounds."""
        sanitized = {}
        
        for param_name, value in parameters.items():
            if param_name in parameter_space:
                bounds = parameter_space[param_name]
                
                if bounds.param_type == ParameterType.CONTINUOUS:
                    sanitized[param_name] = max(bounds.min_value, min(bounds.max_value, float(value)))
                elif bounds.param_type == ParameterType.INTEGER:
                    sanitized[param_name] = max(int(bounds.min_value), min(int(bounds.max_value), int(value)))
                elif bounds.param_type == ParameterType.CATEGORICAL:
                    if value in bounds.categories:
                        sanitized[param_name] = value
                    else:
                        sanitized[param_name] = bounds.categories[0]  # Default to first category
                else:
                    sanitized[param_name] = value
            else:
                sanitized[param_name] = value
        
        return sanitized


