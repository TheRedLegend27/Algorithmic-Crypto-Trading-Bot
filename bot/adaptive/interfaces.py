"""
Interfaces for the adaptive trading bot system components.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd

from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, 
    OptimizationResult, AdaptationEvent, MLModelMetadata, StrategyAllocation
)
from .enums import RegimeType, AdaptationType, OptimizationMethod, ModelType


class MarketRegimeDetectorInterface(ABC):
    """Interface for market regime detection components."""
    
    @abstractmethod
    def detect_regime(self, market_data: pd.DataFrame, pair: str) -> MarketRegime:
        """
        Detect the current market regime for a given trading pair.
        
        Args:
            market_data: Historical market data
            pair: Trading pair symbol
            
        Returns:
            MarketRegime object with detected regime and metadata
        """
        pass
    
    @abstractmethod
    def get_regime_confidence(self, pair: str) -> float:
        """Get confidence level for the current regime detection."""
        pass
    
    @abstractmethod
    def get_regime_history(self, pair: str, lookback_hours: int = 24) -> List[MarketRegime]:
        """Get historical regime detections for analysis."""
        pass
    
    @abstractmethod
    def update_regime_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update regime detection parameters."""
        pass


class AdaptiveStrategyEngineInterface(ABC):
    """Interface for the adaptive strategy engine."""
    
    @abstractmethod
    def select_optimal_strategy(self, pair: str, regime: MarketRegime) -> str:
        """Select the optimal strategy for current conditions."""
        pass
    
    @abstractmethod
    def execute_adaptive_signal(self, pair: str, market_data: pd.DataFrame) -> Optional[AdaptiveSignal]:
        """Generate an adaptive trading signal."""
        pass
    
    @abstractmethod
    def update_strategy_weights(self, performance_data: Dict[str, PerformanceMetrics]) -> None:
        """Update strategy weights based on performance."""
        pass
    
    @abstractmethod
    def get_strategy_allocation(self) -> Dict[str, StrategyAllocation]:
        """Get current strategy allocation."""
        pass
    
    @abstractmethod
    def add_strategy(self, strategy_name: str, strategy_config: Dict[str, Any]) -> None:
        """Add a new strategy to the engine."""
        pass
    
    @abstractmethod
    def remove_strategy(self, strategy_name: str) -> None:
        """Remove a strategy from the engine."""
        pass


class MLEngineInterface(ABC):
    """Interface for machine learning components."""
    
    @abstractmethod
    def train_models(self, historical_data: pd.DataFrame, trade_outcomes: List[Dict]) -> None:
        """Train ML models on historical data and trade outcomes."""
        pass
    
    @abstractmethod
    def predict_trade_outcome(self, signal: AdaptiveSignal, market_conditions: Dict[str, Any]) -> float:
        """Predict the probability of a successful trade."""
        pass
    
    @abstractmethod
    def update_online(self, trade_result: Dict[str, Any]) -> None:
        """Update models with new trade result."""
        pass
    
    @abstractmethod
    def get_model_confidence(self, model_type: ModelType) -> float:
        """Get confidence level for a specific model."""
        pass
    
    @abstractmethod
    def get_feature_importance(self, model_type: ModelType) -> Dict[str, float]:
        """Get feature importance for a model."""
        pass
    
    @abstractmethod
    def get_model_metadata(self, model_type: ModelType) -> MLModelMetadata:
        """Get metadata for a specific model."""
        pass


class ParameterOptimizerInterface(ABC):
    """Interface for parameter optimization components."""
    
    @abstractmethod
    def optimize_parameters(
        self, 
        strategy_name: str, 
        current_parameters: Dict[str, float],
        performance_data: pd.DataFrame,
        optimization_method: OptimizationMethod = OptimizationMethod.BAYESIAN
    ) -> OptimizationResult:
        """Optimize parameters for a strategy."""
        pass
    
    @abstractmethod
    def update_parameter_bounds(self, strategy_name: str, bounds: Dict[str, Tuple[float, float]]) -> None:
        """Update parameter bounds for optimization."""
        pass
    
    @abstractmethod
    def get_optimization_history(self, strategy_name: str) -> List[OptimizationResult]:
        """Get optimization history for a strategy."""
        pass
    
    @abstractmethod
    def validate_parameters(self, strategy_name: str, parameters: Dict[str, float]) -> bool:
        """Validate if parameters are within acceptable bounds."""
        pass


class PerformanceAnalyzerInterface(ABC):
    """Interface for performance analysis components."""
    
    @abstractmethod
    def analyze_strategy_performance(
        self, 
        strategy_name: str, 
        timeframe: str = "24h"
    ) -> PerformanceMetrics:
        """Analyze performance of a specific strategy."""
        pass
    
    @abstractmethod
    def calculate_risk_adjusted_returns(self, strategy_name: str) -> Dict[str, float]:
        """Calculate risk-adjusted return metrics."""
        pass
    
    @abstractmethod
    def detect_performance_degradation(self, threshold: float = -0.1) -> List[str]:
        """Detect strategies with performance degradation."""
        pass
    
    @abstractmethod
    def generate_performance_report(self, include_charts: bool = False) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        pass
    
    @abstractmethod
    def compare_strategies(self, strategy_names: List[str]) -> Dict[str, PerformanceMetrics]:
        """Compare performance across multiple strategies."""
        pass
    
    @abstractmethod
    def get_regime_performance(self, regime_type: RegimeType) -> Dict[str, float]:
        """Get performance breakdown by market regime."""
        pass


class AdaptationControllerInterface(ABC):
    """Interface for adaptation control components."""
    
    @abstractmethod
    def should_adapt(self, performance_metrics: PerformanceMetrics, strategy_name: str) -> bool:
        """Determine if adaptation should be triggered."""
        pass
    
    @abstractmethod
    def get_adaptation_rate(self) -> float:
        """Get current adaptation rate/frequency."""
        pass
    
    @abstractmethod
    def validate_adaptation(self, proposed_changes: Dict[str, Any]) -> bool:
        """Validate proposed adaptation changes."""
        pass
    
    @abstractmethod
    def execute_adaptation(self, adaptation_event: AdaptationEvent) -> bool:
        """Execute an adaptation."""
        pass
    
    @abstractmethod
    def rollback_adaptation(self, event_id: str) -> bool:
        """Rollback a previous adaptation."""
        pass
    
    @abstractmethod
    def get_adaptation_history(self, hours_back: int = 24) -> List[AdaptationEvent]:
        """Get recent adaptation history."""
        pass
    
    @abstractmethod
    def set_adaptation_limits(self, limits: Dict[str, Any]) -> None:
        """Set limits on adaptation behavior."""
        pass


class DataManagerInterface(ABC):
    """Interface for adaptive data management."""
    
    @abstractmethod
    def store_regime_data(self, regime: MarketRegime, pair: str) -> None:
        """Store regime detection data."""
        pass
    
    @abstractmethod
    def store_performance_data(self, metrics: PerformanceMetrics, strategy_name: str) -> None:
        """Store performance metrics."""
        pass
    
    @abstractmethod
    def store_adaptation_event(self, event: AdaptationEvent) -> None:
        """Store adaptation event data."""
        pass
    
    @abstractmethod
    def get_historical_regimes(self, pair: str, start_time: datetime, end_time: datetime) -> List[MarketRegime]:
        """Retrieve historical regime data."""
        pass
    
    @abstractmethod
    def get_performance_history(self, strategy_name: str, days_back: int = 30) -> List[PerformanceMetrics]:
        """Get performance history for a strategy."""
        pass
    
    @abstractmethod
    def cleanup_old_data(self, retention_days: int = 90) -> None:
        """Clean up old data beyond retention period."""
        pass


class RiskManagerInterface(ABC):
    """Interface for adaptive risk management."""
    
    @abstractmethod
    def validate_adaptive_signal(self, signal: AdaptiveSignal, current_positions: Dict[str, Any]) -> bool:
        """Validate an adaptive signal against risk parameters."""
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: AdaptiveSignal, account_balance: float) -> float:
        """Calculate appropriate position size for adaptive signal."""
        pass
    
    @abstractmethod
    def update_risk_parameters(self, regime: MarketRegime, performance_metrics: PerformanceMetrics) -> None:
        """Update risk parameters based on market regime and performance."""
        pass
    
    @abstractmethod
    def check_portfolio_risk(self, proposed_signal: AdaptiveSignal, current_portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Check portfolio-level risk for a proposed trade."""
        pass
    
    @abstractmethod
    def get_emergency_stop_conditions(self) -> Dict[str, Any]:
        """Get conditions that would trigger emergency stops."""
        pass


class MonitoringInterface(ABC):
    """Interface for system monitoring and alerting."""
    
    @abstractmethod
    def monitor_system_health(self) -> Dict[str, Any]:
        """Monitor overall system health."""
        pass
    
    @abstractmethod
    def monitor_adaptation_performance(self) -> Dict[str, Any]:
        """Monitor performance of recent adaptations."""
        pass
    
    @abstractmethod
    def generate_alerts(self, alert_conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on conditions."""
        pass
    
    @abstractmethod
    def log_system_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log system events for monitoring."""
        pass
    
    @abstractmethod
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics."""
        pass


class IParameterOptimizer(ABC):
    """Enhanced interface for parameter optimization with additional methods."""
    
    @abstractmethod
    def optimize_parameters(self, 
                          strategy_name: str,
                          parameter_space: Dict[str, Any],
                          historical_data: pd.DataFrame,
                          optimization_type: Any = None,
                          **kwargs) -> OptimizationResult:
        """Optimize parameters using specified algorithm."""
        pass
    
    @abstractmethod
    def walk_forward_analysis(self, 
                             strategy_name: str,
                             parameter_space: Dict[str, Any],
                             historical_data: pd.DataFrame,
                             optimization_type: Any = None) -> List[OptimizationResult]:
        """Perform walk-forward analysis for parameter validation."""
        pass
    
    @abstractmethod
    def set_parameter_bounds(self, parameter_name: str, bounds: Any):
        """Set bounds for a parameter."""
        pass
    
    @abstractmethod
    def get_optimization_history(self, strategy_name: Optional[str] = None) -> List[OptimizationResult]:
        """Get optimization history."""
        pass
    
    @abstractmethod
    def get_best_parameters(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get best parameters for a strategy."""
        pass
    
    @abstractmethod
    def validate_parameter_bounds(self, parameter_space: Dict[str, Any]) -> bool:
        """Validate parameter bounds for consistency."""
        pass


class IPerformanceEvaluator(ABC):
    """Interface for evaluating parameter performance."""
    
    @abstractmethod
    def evaluate_parameters(self, 
                          strategy_name: str, 
                          parameters: Dict[str, Any], 
                          historical_data: pd.DataFrame) -> PerformanceMetrics:
        """Evaluate performance of parameters on historical data."""
        pass
    
    @abstractmethod
    def calculate_fitness(self, 
                         strategy_name: str, 
                         parameters: Dict[str, Any], 
                         historical_data: pd.DataFrame) -> float:
        """Calculate fitness score for optimization algorithms."""
        pass
    
    @abstractmethod
    def get_baseline_performance(self, 
                               strategy_name: str, 
                               historical_data: pd.DataFrame) -> PerformanceMetrics:
        """Get baseline performance with default parameters."""
        pass